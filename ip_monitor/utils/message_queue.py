"""
Async message queue for Discord notifications during API downtime.
"""

import asyncio
from dataclasses import asdict, dataclass
from enum import Enum
import json
import logging
import os
import time
from typing import Any
from uuid import uuid4

import discord

from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageStatus(Enum):
    """Message processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class QueuedMessage:
    """Represents a queued Discord message."""

    id: str
    channel_id: int
    content: str
    priority: MessagePriority
    created_at: float
    scheduled_at: float | None = None
    status: MessageStatus = MessageStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    expires_at: float | None = None
    embed: dict[str, Any] | None = None
    files: list[str] | None = None
    tags: list[str] | None = None
    dedupe_key: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueuedMessage":
        """Create from dictionary after JSON deserialization."""
        data["priority"] = MessagePriority(data["priority"])
        data["status"] = MessageStatus(data["status"])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return (
            self.status == MessageStatus.FAILED
            and self.retry_count < self.max_retries
            and not self.is_expired()
        )

    def can_process_now(self) -> bool:
        """Check if message can be processed now."""
        if self.scheduled_at is None:
            return True
        return time.time() >= self.scheduled_at


class AsyncMessageQueue:
    """
    Async message queue for Discord notifications with persistence and retry logic.
    """

    def __init__(
        self,
        queue_file: str = "message_queue.json",
        max_queue_size: int = 1000,
        max_message_age_hours: int = 24,
        batch_size: int = 5,
        process_interval: float = 1.0,
    ):
        """
        Initialize the async message queue.

        Args:
            queue_file: File to persist queue state
            max_queue_size: Maximum number of messages in queue
            max_message_age_hours: Maximum age of messages before expiry
            batch_size: Number of messages to process in each batch
            process_interval: Interval between processing batches (seconds)
        """
        self.queue_file = queue_file
        self.max_queue_size = max_queue_size
        self.max_message_age_hours = max_message_age_hours
        self.batch_size = batch_size
        self.process_interval = process_interval

        # In-memory queue (priority queue)
        self.queue: list[QueuedMessage] = []
        self.dedupe_cache: dict[str, str] = {}  # dedupe_key -> message_id

        # Processing state
        self.is_processing = False
        self.process_task: asyncio.Task | None = None
        self.discord_client: discord.Client | None = None

        # Statistics
        self.stats = {
            "total_queued": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "total_expired": 0,
            "total_deduplicated": 0,
        }

        # Load existing queue
        self._load_queue()

    def set_discord_client(self, client: discord.Client) -> None:
        """Set the Discord client for message delivery."""
        self.discord_client = client

    def start_processing(self) -> None:
        """Start the async message processing loop."""
        if not self.is_processing and self.process_task is None:
            self.is_processing = True
            self.process_task = asyncio.create_task(self._process_loop())
            logger.info("Message queue processing started")

    async def stop_processing(self) -> None:
        """Stop the async message processing loop."""
        self.is_processing = False
        if self.process_task:
            try:
                # Check if the event loop is still running before cancelling
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    self.process_task.cancel()
                    await self.process_task
            except asyncio.CancelledError:
                pass
            except RuntimeError as e:
                # Handle event loop closure gracefully
                if "Event loop is closed" in str(e):
                    logger.debug("Event loop closed during task cancellation")
                else:
                    logger.error(f"Error during task cancellation: {e}")
            self.process_task = None
        logger.info("Message queue processing stopped")

    def _load_queue(self) -> None:
        """Load queue from persistent storage."""
        if not os.path.exists(self.queue_file):
            return

        try:
            with open(self.queue_file) as f:
                data = json.load(f)

            queue_data = data.get("queue", [])
            self.stats = data.get("stats", self.stats)

            # Reconstruct queue
            for msg_data in queue_data:
                try:
                    msg = QueuedMessage.from_dict(msg_data)
                    self.queue.append(msg)

                    # Rebuild dedupe cache
                    if msg.dedupe_key:
                        self.dedupe_cache[msg.dedupe_key] = msg.id

                except Exception as e:
                    logger.warning(f"Failed to load queued message: {e}")

            # Sort queue by priority and creation time
            self._sort_queue()

            logger.info(f"Loaded {len(self.queue)} messages from queue file")

        except Exception as e:
            logger.error(f"Failed to load message queue: {e}")

    def _save_queue(self) -> None:
        """Save queue to persistent storage."""
        try:
            # Clean up expired messages before saving
            self._cleanup_expired_messages()

            data = {
                "queue": [msg.to_dict() for msg in self.queue],
                "stats": self.stats,
                "timestamp": time.time(),
            }

            # Atomic write
            temp_file = f"{self.queue_file}.tmp"
            with open(temp_file, "w") as f:
                json.dump(data, f, indent=2)

            os.rename(temp_file, self.queue_file)

        except Exception as e:
            logger.error(f"Failed to save message queue: {e}")

    def _sort_queue(self) -> None:
        """Sort queue by priority (highest first) and creation time (oldest first)."""
        self.queue.sort(key=lambda msg: (-msg.priority.value, msg.created_at))

    def _cleanup_expired_messages(self) -> None:
        """Remove expired messages from queue."""
        initial_count = len(self.queue)

        self.queue = [msg for msg in self.queue if not msg.is_expired()]

        expired_count = initial_count - len(self.queue)
        if expired_count > 0:
            self.stats["total_expired"] += expired_count
            logger.debug(f"Cleaned up {expired_count} expired messages")

    def _enforce_queue_size_limit(self) -> None:
        """Enforce maximum queue size by removing oldest low-priority messages."""
        if len(self.queue) <= self.max_queue_size:
            return

        # Sort by priority (ascending) and age (descending) to remove oldest low-priority messages
        messages_to_remove = sorted(
            self.queue, key=lambda msg: (msg.priority.value, -msg.created_at)
        )

        excess_count = len(self.queue) - self.max_queue_size
        for msg in messages_to_remove[:excess_count]:
            self.queue.remove(msg)
            if msg.dedupe_key and msg.dedupe_key in self.dedupe_cache:
                del self.dedupe_cache[msg.dedupe_key]

        logger.warning(f"Removed {excess_count} messages due to queue size limit")

    async def enqueue(
        self,
        channel_id: int,
        content: str,
        priority: MessagePriority = MessagePriority.NORMAL,
        delay_seconds: float | None = None,
        expires_in_hours: float | None = None,
        embed: discord.Embed | None = None,
        tags: list[str] | None = None,
        dedupe_key: str | None = None,
        max_retries: int = 3,
    ) -> str | None:
        """
        Add a message to the queue.

        Args:
            channel_id: Discord channel ID
            content: Message content
            priority: Message priority level
            delay_seconds: Delay before processing (None = immediate)
            expires_in_hours: Hours until message expires (None = use default)
            embed: Discord embed object
            tags: List of tags for categorization
            dedupe_key: Key for deduplication (None = no deduplication)
            max_retries: Maximum retry attempts

        Returns:
            Message ID if queued successfully, None otherwise
        """
        current_time = time.time()

        # Check for deduplication
        if dedupe_key and dedupe_key in self.dedupe_cache:
            self.stats["total_deduplicated"] += 1
            logger.debug(f"Message deduplicated with key: {dedupe_key}")
            return self.dedupe_cache[dedupe_key]

        # Create message
        message_id = str(uuid4())

        scheduled_at = None
        if delay_seconds is not None:
            scheduled_at = current_time + delay_seconds

        expires_at = None
        if expires_in_hours is not None:
            expires_at = current_time + (expires_in_hours * 3600)
        elif self.max_message_age_hours > 0:
            expires_at = current_time + (self.max_message_age_hours * 3600)

        embed_dict = None
        if embed:
            embed_dict = embed.to_dict()

        message = QueuedMessage(
            id=message_id,
            channel_id=channel_id,
            content=content,
            priority=priority,
            created_at=current_time,
            scheduled_at=scheduled_at,
            expires_at=expires_at,
            embed=embed_dict,
            tags=tags,
            dedupe_key=dedupe_key,
            max_retries=max_retries,
        )

        # Add to queue
        self.queue.append(message)
        self._sort_queue()

        # Update dedupe cache
        if dedupe_key:
            self.dedupe_cache[dedupe_key] = message_id

        # Enforce queue size limits
        self._enforce_queue_size_limit()

        # Update stats
        self.stats["total_queued"] += 1

        # Save queue state
        self._save_queue()

        logger.debug(f"Queued message {message_id} with priority {priority.name}")
        return message_id

    async def _process_loop(self) -> None:
        """Main processing loop for queued messages."""
        logger.info("Starting message queue processing loop")

        while self.is_processing:
            try:
                # Process a batch of messages
                await self._process_batch()

                # Wait before next batch
                await asyncio.sleep(self.process_interval)

            except asyncio.CancelledError:
                logger.info("Message queue processing cancelled")
                break
            except Exception as e:
                logger.error(f"Error in message queue processing loop: {e}")
                # Continue processing despite errors
                await asyncio.sleep(self.process_interval)

    async def _process_batch(self) -> None:
        """Process a batch of queued messages."""
        if not self.discord_client:
            return

        # Check if Discord API is healthy enough to process messages
        discord_health = service_health.get_service_health("discord_api")
        if discord_health and discord_health.status.value == "failed":
            logger.debug("Discord API marked as failed, skipping message processing")
            return

        # Clean up expired messages
        self._cleanup_expired_messages()

        # Get messages ready for processing
        ready_messages = [
            msg
            for msg in self.queue[: self.batch_size]
            if msg.status == MessageStatus.PENDING
            and msg.can_process_now()
            and not msg.is_expired()
        ]

        if not ready_messages:
            return

        logger.debug(f"Processing batch of {len(ready_messages)} messages")

        # Process messages
        for message in ready_messages:
            try:
                await self._process_message(message)
            except Exception as e:
                logger.error(f"Error processing message {message.id}: {e}")
                message.status = MessageStatus.FAILED
                message.last_error = str(e)

        # Save queue state after processing
        self._save_queue()

    async def _process_message(self, message: QueuedMessage) -> None:
        """Process a single queued message."""
        logger.debug(f"Processing message {message.id}")

        message.status = MessageStatus.PROCESSING

        try:
            # Get the channel
            channel = self.discord_client.get_channel(message.channel_id)
            if not channel:
                raise ValueError(f"Channel {message.channel_id} not found")

            # Prepare message arguments
            kwargs = {}
            if message.embed:
                kwargs["embed"] = discord.Embed.from_dict(message.embed)

            # Send the message using the Discord rate limiter
            from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter

            rate_limiter = DiscordRateLimiter()

            result = await rate_limiter.send_message_with_backoff(
                channel, message.content, **kwargs
            )

            if result:
                message.status = MessageStatus.DELIVERED
                self.stats["total_delivered"] += 1
                logger.debug(f"Successfully delivered message {message.id}")

                # Remove from queue
                self.queue.remove(message)
                if message.dedupe_key and message.dedupe_key in self.dedupe_cache:
                    del self.dedupe_cache[message.dedupe_key]

                service_health.record_success("discord_api", "queue_delivery")
            else:
                raise ValueError("Failed to send message")

        except Exception as e:
            message.status = MessageStatus.FAILED
            message.last_error = str(e)
            message.retry_count += 1

            logger.warning(f"Failed to deliver message {message.id}: {e}")
            service_health.record_failure(
                "discord_api", f"Queue delivery failed: {e}", "queue_delivery"
            )

            # Check if we should retry
            if message.should_retry():
                message.status = MessageStatus.PENDING
                # Schedule retry with exponential backoff
                delay = min(60 * (2**message.retry_count), 3600)  # Max 1 hour delay
                message.scheduled_at = time.time() + delay
                logger.debug(
                    f"Scheduled retry for message {message.id} in {delay} seconds"
                )
            else:
                # Max retries reached or expired
                self.stats["total_failed"] += 1
                logger.error(
                    f"Message {message.id} failed permanently after {message.retry_count} retries"
                )

                # Remove from queue
                self.queue.remove(message)
                if message.dedupe_key and message.dedupe_key in self.dedupe_cache:
                    del self.dedupe_cache[message.dedupe_key]

    def get_queue_status(self) -> dict[str, Any]:
        """Get comprehensive queue status information."""
        current_time = time.time()

        # Count messages by status
        status_counts = {}
        priority_counts = {}

        for msg in self.queue:
            # Update expired status
            if msg.is_expired():
                msg.status = MessageStatus.EXPIRED

            status = msg.status.value
            priority = msg.priority.name

            status_counts[status] = status_counts.get(status, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        # Get ready and scheduled counts
        ready_count = len(
            [
                msg
                for msg in self.queue
                if msg.status == MessageStatus.PENDING and msg.can_process_now()
            ]
        )

        scheduled_count = len(
            [
                msg
                for msg in self.queue
                if msg.status == MessageStatus.PENDING and not msg.can_process_now()
            ]
        )

        return {
            "queue_size": len(self.queue),
            "max_queue_size": self.max_queue_size,
            "is_processing": self.is_processing,
            "ready_to_process": ready_count,
            "scheduled_for_later": scheduled_count,
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "statistics": self.stats.copy(),
            "oldest_message_age": current_time
            - min([msg.created_at for msg in self.queue], default=current_time),
            "dedupe_cache_size": len(self.dedupe_cache),
        }

    def clear_queue(self, priority: MessagePriority | None = None) -> int:
        """
        Clear messages from queue.

        Args:
            priority: If specified, only clear messages with this priority

        Returns:
            Number of messages cleared
        """
        initial_count = len(self.queue)

        if priority is None:
            # Clear all messages
            self.queue.clear()
            self.dedupe_cache.clear()
        else:
            # Clear messages with specific priority
            messages_to_remove = [msg for msg in self.queue if msg.priority == priority]
            for msg in messages_to_remove:
                self.queue.remove(msg)
                if msg.dedupe_key and msg.dedupe_key in self.dedupe_cache:
                    del self.dedupe_cache[msg.dedupe_key]

        cleared_count = initial_count - len(self.queue)
        self._save_queue()

        logger.info(f"Cleared {cleared_count} messages from queue")
        return cleared_count

    def get_message_by_id(self, message_id: str) -> QueuedMessage | None:
        """Get a specific message by ID."""
        for msg in self.queue:
            if msg.id == message_id:
                return msg
        return None

    def retry_failed_messages(self) -> int:
        """Retry all failed messages that haven't exceeded max retries."""
        retry_count = 0
        current_time = time.time()

        for msg in self.queue:
            if msg.status == MessageStatus.FAILED and msg.should_retry():
                msg.status = MessageStatus.PENDING
                msg.scheduled_at = current_time
                retry_count += 1

        if retry_count > 0:
            self._sort_queue()
            self._save_queue()
            logger.info(f"Scheduled {retry_count} failed messages for retry")

        return retry_count


# Global message queue instance
message_queue = AsyncMessageQueue()
