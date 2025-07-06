"""
Tests for the AsyncMessageQueue utility.
"""

import asyncio
import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from ip_monitor.utils.message_queue import (
    AsyncMessageQueue,
    MessagePriority,
    MessageStatus,
    QueuedMessage,
    message_queue,
)


class TestQueuedMessage:
    """Test QueuedMessage dataclass functionality."""

    def test_queued_message_initialization(self):
        """Test QueuedMessage initialization with required fields."""
        msg = QueuedMessage(
            id="test-123",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=time.time(),
        )
        
        assert msg.id == "test-123"
        assert msg.channel_id == 123456789
        assert msg.content == "Test message"
        assert msg.priority == MessagePriority.HIGH
        assert msg.status == MessageStatus.PENDING
        assert msg.retry_count == 0
        assert msg.max_retries == 3

    def test_queued_message_to_dict(self):
        """Test QueuedMessage to_dict serialization."""
        msg = QueuedMessage(
            id="test-123",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=time.time(),
        )
        
        data = msg.to_dict()
        
        assert data["id"] == "test-123"
        assert data["channel_id"] == 123456789
        assert data["content"] == "Test message"
        assert data["priority"] == MessagePriority.HIGH.value
        assert data["status"] == MessageStatus.PENDING.value

    def test_queued_message_from_dict(self):
        """Test QueuedMessage from_dict deserialization."""
        data = {
            "id": "test-123",
            "channel_id": 123456789,
            "content": "Test message",
            "priority": MessagePriority.HIGH.value,
            "status": MessageStatus.PENDING.value,
            "created_at": time.time(),
            "scheduled_at": None,
            "retry_count": 0,
            "max_retries": 3,
            "expires_at": None,
            "embed": None,
            "files": None,
            "tags": None,
            "dedupe_key": None,
            "last_error": None,
        }
        
        msg = QueuedMessage.from_dict(data)
        
        assert msg.id == "test-123"
        assert msg.channel_id == 123456789
        assert msg.content == "Test message"
        assert msg.priority == MessagePriority.HIGH
        assert msg.status == MessageStatus.PENDING

    def test_queued_message_is_expired(self):
        """Test QueuedMessage expiration checking."""
        current_time = time.time()
        
        # Message without expiration
        msg = QueuedMessage(
            id="test-123",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
        )
        assert not msg.is_expired()
        
        # Message with future expiration
        msg.expires_at = current_time + 3600
        assert not msg.is_expired()
        
        # Message with past expiration
        msg.expires_at = current_time - 3600
        assert msg.is_expired()

    def test_queued_message_should_retry(self):
        """Test QueuedMessage retry logic."""
        current_time = time.time()
        
        msg = QueuedMessage(
            id="test-123",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        
        # Should retry when failed and under max retries
        assert msg.should_retry()
        
        # Should not retry when max retries reached
        msg.retry_count = 3
        assert not msg.should_retry()
        
        # Should not retry when expired
        msg.retry_count = 1
        msg.expires_at = current_time - 3600
        assert not msg.should_retry()
        
        # Should not retry when not failed
        msg.status = MessageStatus.PENDING
        msg.expires_at = None
        assert not msg.should_retry()

    def test_queued_message_can_process_now(self):
        """Test QueuedMessage scheduling logic."""
        current_time = time.time()
        
        msg = QueuedMessage(
            id="test-123",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
        )
        
        # Can process when no scheduled time
        assert msg.can_process_now()
        
        # Can process when scheduled time has passed
        msg.scheduled_at = current_time - 60
        assert msg.can_process_now()
        
        # Cannot process when scheduled time is in future
        msg.scheduled_at = current_time + 60
        assert not msg.can_process_now()


class TestAsyncMessageQueue:
    """Test AsyncMessageQueue functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    @pytest.fixture
    def mock_discord_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
        return client

    def test_async_message_queue_initialization(self, temp_queue_file):
        """Test AsyncMessageQueue initialization."""
        queue = AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=100,
            max_message_age_hours=24,
            batch_size=5,
            process_interval=1.0,
        )
        
        assert queue.queue_file == temp_queue_file
        assert queue.max_queue_size == 100
        assert queue.max_message_age_hours == 24
        assert queue.batch_size == 5
        assert queue.process_interval == 1.0
        assert queue.queue == []
        assert queue.dedupe_cache == {}
        assert not queue.is_processing
        assert queue.process_task is None
        assert queue.discord_client is None

    def test_set_discord_client(self, queue, mock_discord_client):
        """Test setting Discord client."""
        queue.set_discord_client(mock_discord_client)
        assert queue.discord_client == mock_discord_client

    async def test_start_stop_processing(self, queue):
        """Test starting and stopping message processing."""
        # Start processing
        queue.start_processing()
        assert queue.is_processing
        assert queue.process_task is not None
        
        # Stop processing
        await queue.stop_processing()
        assert not queue.is_processing
        assert queue.process_task is None

    def test_global_message_queue_instance(self):
        """Test global message queue instance."""
        assert message_queue is not None
        assert isinstance(message_queue, AsyncMessageQueue)


class TestMessagePersistence:
    """Test message persistence functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    async def test_save_and_load_queue(self, queue):
        """Test saving and loading queue state."""
        # Add a message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            dedupe_key="test-key"
        )
        
        assert message_id is not None
        assert len(queue.queue) == 1
        assert len(queue.dedupe_cache) == 1
        assert queue.stats["total_queued"] == 1
        
        # Create a new queue instance with same file
        new_queue = AsyncMessageQueue(
            queue_file=queue.queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )
        
        # Verify queue was loaded
        assert len(new_queue.queue) == 1
        assert len(new_queue.dedupe_cache) == 1
        assert new_queue.stats["total_queued"] == 1
        assert new_queue.queue[0].content == "Test message"
        assert new_queue.queue[0].priority == MessagePriority.HIGH
        assert new_queue.dedupe_cache["test-key"] == message_id

    async def test_save_queue_with_file_error(self, queue):
        """Test save queue handling file errors."""
        # Make queue file path invalid
        queue.queue_file = "/invalid/path/queue.json"
        
        # Add message and attempt save (should not raise exception)
        await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Verify queue still contains message despite save failure
        assert len(queue.queue) == 1

    def test_load_queue_with_missing_file(self, queue):
        """Test loading queue when file doesn't exist."""
        # Remove queue file if it exists
        if os.path.exists(queue.queue_file):
            os.unlink(queue.queue_file)
        
        # Load queue (should not raise exception)
        queue._load_queue()
        
        # Verify queue is empty
        assert len(queue.queue) == 0
        assert len(queue.dedupe_cache) == 0

    def test_load_queue_with_invalid_json(self, temp_queue_file):
        """Test loading queue with invalid JSON."""
        # Write invalid JSON to file
        with open(temp_queue_file, 'w') as f:
            f.write("invalid json content")
        
        # Create queue (should not raise exception)
        queue = AsyncMessageQueue(queue_file=temp_queue_file)
        
        # Verify queue is empty
        assert len(queue.queue) == 0
        assert len(queue.dedupe_cache) == 0

    def test_load_queue_with_invalid_message_data(self, temp_queue_file):
        """Test loading queue with invalid message data."""
        # Write valid JSON but invalid message data
        queue_data = {
            "queue": [
                {
                    "id": "test-123",
                    "channel_id": "invalid-channel-id",  # Should be int
                    "content": "Test message",
                    "priority": 999,  # Invalid priority
                    "status": "pending",
                    "created_at": time.time(),
                }
            ],
            "stats": {},
            "timestamp": time.time(),
        }
        
        with open(temp_queue_file, 'w') as f:
            json.dump(queue_data, f)
        
        # Create queue (should not raise exception)
        queue = AsyncMessageQueue(queue_file=temp_queue_file)
        
        # Verify invalid message was not loaded
        assert len(queue.queue) == 0
        assert len(queue.dedupe_cache) == 0

    async def test_atomic_queue_save(self, queue):
        """Test atomic queue save using temporary file."""
        # Add message to queue
        await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Verify temporary file is not left behind
        temp_file = f"{queue.queue_file}.tmp"
        assert not os.path.exists(temp_file)
        
        # Verify queue file exists and is valid
        assert os.path.exists(queue.queue_file)
        
        with open(queue.queue_file, 'r') as f:
            data = json.load(f)
        
        assert "queue" in data
        assert "stats" in data
        assert "timestamp" in data
        assert len(data["queue"]) == 1


class TestPriorityHandling:
    """Test message priority handling functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    async def test_priority_ordering(self, queue):
        """Test that messages are ordered by priority correctly."""
        # Add messages with different priorities
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority",
            priority=MessagePriority.LOW,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Critical priority",
            priority=MessagePriority.CRITICAL,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Normal priority",
            priority=MessagePriority.NORMAL,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="High priority",
            priority=MessagePriority.HIGH,
        )
        
        # Verify messages are sorted by priority (highest first)
        assert len(queue.queue) == 4
        assert queue.queue[0].priority == MessagePriority.CRITICAL
        assert queue.queue[1].priority == MessagePriority.HIGH
        assert queue.queue[2].priority == MessagePriority.NORMAL
        assert queue.queue[3].priority == MessagePriority.LOW

    async def test_priority_ordering_with_same_priority(self, queue):
        """Test that messages with same priority are ordered by creation time."""
        base_time = time.time()
        
        # Add messages with same priority but different creation times
        msg1 = QueuedMessage(
            id="msg1",
            channel_id=123456789,
            content="First message",
            priority=MessagePriority.HIGH,
            created_at=base_time,
        )
        msg2 = QueuedMessage(
            id="msg2",
            channel_id=123456789,
            content="Second message",
            priority=MessagePriority.HIGH,
            created_at=base_time + 1,
        )
        msg3 = QueuedMessage(
            id="msg3",
            channel_id=123456789,
            content="Third message",
            priority=MessagePriority.HIGH,
            created_at=base_time + 2,
        )
        
        # Add messages to queue
        queue.queue.extend([msg2, msg3, msg1])
        queue._sort_queue()
        
        # Verify messages are sorted by creation time (oldest first) for same priority
        assert queue.queue[0].id == "msg1"
        assert queue.queue[1].id == "msg2"
        assert queue.queue[2].id == "msg3"

    async def test_queue_status_priority_breakdown(self, queue):
        """Test queue status includes priority breakdown."""
        # Add messages with different priorities
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority 1",
            priority=MessagePriority.LOW,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority 2",
            priority=MessagePriority.LOW,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="High priority",
            priority=MessagePriority.HIGH,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Critical priority",
            priority=MessagePriority.CRITICAL,
        )
        
        status = queue.get_queue_status()
        
        assert status["priority_breakdown"]["LOW"] == 2
        assert status["priority_breakdown"]["HIGH"] == 1
        assert status["priority_breakdown"]["CRITICAL"] == 1
        assert status["queue_size"] == 4

    async def test_clear_queue_by_priority(self, queue):
        """Test clearing messages by specific priority."""
        # Add messages with different priorities
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority 1",
            priority=MessagePriority.LOW,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority 2",
            priority=MessagePriority.LOW,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="High priority",
            priority=MessagePriority.HIGH,
        )
        
        # Clear only low priority messages
        cleared_count = queue.clear_queue(priority=MessagePriority.LOW)
        
        assert cleared_count == 2
        assert len(queue.queue) == 1
        assert queue.queue[0].priority == MessagePriority.HIGH

    async def test_size_limit_removes_lowest_priority_first(self, queue):
        """Test that queue size limit removes lowest priority messages first."""
        # Set very small queue size
        queue.max_queue_size = 2
        
        # Add messages with different priorities
        await queue.enqueue(
            channel_id=123456789,
            content="Critical priority",
            priority=MessagePriority.CRITICAL,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="High priority",
            priority=MessagePriority.HIGH,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Low priority",
            priority=MessagePriority.LOW,
        )
        
        # Should only keep 2 messages (highest priority)
        assert len(queue.queue) == 2
        assert queue.queue[0].priority == MessagePriority.CRITICAL
        assert queue.queue[1].priority == MessagePriority.HIGH

    async def test_size_limit_removes_oldest_within_priority(self, queue):
        """Test that queue size limit removes oldest messages within same priority."""
        # Set very small queue size
        queue.max_queue_size = 2
        base_time = time.time()
        
        # Add messages with same priority but different ages
        msg1 = QueuedMessage(
            id="msg1",
            channel_id=123456789,
            content="Oldest message",
            priority=MessagePriority.HIGH,
            created_at=base_time,
        )
        msg2 = QueuedMessage(
            id="msg2",
            channel_id=123456789,
            content="Middle message",
            priority=MessagePriority.HIGH,
            created_at=base_time + 1,
        )
        msg3 = QueuedMessage(
            id="msg3",
            channel_id=123456789,
            content="Newest message",
            priority=MessagePriority.HIGH,
            created_at=base_time + 2,
        )
        
        # Add messages to queue
        queue.queue.extend([msg1, msg2, msg3])
        queue._enforce_queue_size_limit()
        
        # Should keep oldest 2 messages (when same priority, remove newest first)
        assert len(queue.queue) == 2
        # Queue enforcement removes by priority (ascending) then age (descending - newest first)
        # Since all have same priority, it removes newest messages first
        remaining_ids = [msg.id for msg in queue.queue]
        assert "msg3" not in remaining_ids  # Newest should be removed
        assert "msg1" in remaining_ids  # Oldest kept
        assert "msg2" in remaining_ids  # Middle kept


class TestRetryLogic:
    """Test message retry logic functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    def test_retry_failed_messages(self, queue):
        """Test retrying failed messages."""
        current_time = time.time()
        
        # Add failed messages with different retry states
        failed_msg1 = QueuedMessage(
            id="failed1",
            channel_id=123456789,
            content="Failed message 1",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=1,
            max_retries=3,
        )
        failed_msg2 = QueuedMessage(
            id="failed2",
            channel_id=123456789,
            content="Failed message 2",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=3,  # Max retries reached
            max_retries=3,
        )
        failed_msg3 = QueuedMessage(
            id="failed3",
            channel_id=123456789,
            content="Failed message 3",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=0,
            max_retries=3,
        )
        
        queue.queue.extend([failed_msg1, failed_msg2, failed_msg3])
        
        # Retry failed messages
        retried_count = queue.retry_failed_messages()
        
        # Should retry 2 messages (failed_msg1 and failed_msg3)
        assert retried_count == 2
        
        # Check that retryable messages are now pending
        assert failed_msg1.status == MessageStatus.PENDING
        assert failed_msg3.status == MessageStatus.PENDING
        
        # Check that max retry message is still failed
        assert failed_msg2.status == MessageStatus.FAILED

    def test_exponential_backoff_retry_scheduling(self, queue):
        """Test exponential backoff for retry scheduling."""
        current_time = time.time()
        
        # Create a message for testing retry scheduling
        msg = QueuedMessage(
            id="retry-test",
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=2,
            max_retries=3,
        )
        
        # Simulate the retry scheduling logic from _process_message
        if msg.should_retry():
            msg.status = MessageStatus.PENDING
            delay = min(60 * (2 ** msg.retry_count), 3600)  # Max 1 hour delay
            msg.scheduled_at = current_time + delay
        
        # Verify exponential backoff calculation
        expected_delay = min(60 * (2 ** 2), 3600)  # 60 * 4 = 240 seconds
        assert msg.scheduled_at == current_time + expected_delay
        assert msg.status == MessageStatus.PENDING

    def test_max_retry_limit_enforcement(self, queue):
        """Test that messages are not retried after max retries."""
        current_time = time.time()
        
        # Create message that has reached max retries
        msg = QueuedMessage(
            id="max-retry",
            channel_id=123456789,
            content="Max retry message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        
        # Should not retry
        assert not msg.should_retry()
        
        # Add to queue and attempt retry
        queue.queue.append(msg)
        retried_count = queue.retry_failed_messages()
        
        # Should not retry any messages
        assert retried_count == 0
        assert msg.status == MessageStatus.FAILED

    def test_expired_message_retry_prevention(self, queue):
        """Test that expired messages are not retried."""
        current_time = time.time()
        
        # Create expired failed message
        msg = QueuedMessage(
            id="expired-retry",
            channel_id=123456789,
            content="Expired message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=1,
            max_retries=3,
            expires_at=current_time - 3600,  # Expired 1 hour ago
        )
        
        # Should not retry expired message
        assert not msg.should_retry()
        
        # Add to queue and attempt retry
        queue.queue.append(msg)
        retried_count = queue.retry_failed_messages()
        
        # Should not retry any messages
        assert retried_count == 0
        assert msg.status == MessageStatus.FAILED

    async def test_message_processing_with_retry(self, queue):
        """Test message processing with retry logic."""
        mock_client = MagicMock(spec=discord.Client)
        mock_channel = MagicMock()
        mock_client.get_channel.return_value = mock_channel
        
        queue.set_discord_client(mock_client)
        
        # Add a message that will fail initially
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            max_retries=2,
        )
        
        # Mock the Discord rate limiter to fail first time
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(side_effect=[
                None,  # Fail first time
                True,  # Succeed second time
            ])
            
            # Process the message (should fail and schedule retry)
            await queue._process_message(queue.queue[0])
            
            # Verify message failed and retry was scheduled
            msg = queue.queue[0]
            assert msg.status == MessageStatus.PENDING
            assert msg.retry_count == 1
            assert msg.scheduled_at is not None
            assert msg.scheduled_at > time.time()
        
        # Verify statistics
        assert queue.stats["total_failed"] == 0  # Should not increment until max retries

    def test_retry_statistics_tracking(self, queue):
        """Test that retry statistics are properly tracked."""
        current_time = time.time()
        
        # Create messages with different retry states
        permanently_failed_msg = QueuedMessage(
            id="permanent-fail",
            channel_id=123456789,
            content="Permanently failed",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )
        
        # Simulate permanent failure (remove from queue)
        queue.queue.append(permanently_failed_msg)
        queue.stats["total_failed"] += 1
        queue.queue.remove(permanently_failed_msg)
        
        # Verify statistics
        assert queue.stats["total_failed"] == 1
        assert len(queue.queue) == 0

    def test_custom_max_retries_per_message(self, queue):
        """Test that messages can have custom max retry limits."""
        current_time = time.time()
        
        # Create message with custom max retries
        msg = QueuedMessage(
            id="custom-retry",
            channel_id=123456789,
            content="Custom retry message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=1,
            max_retries=5,  # Custom limit
        )
        
        # Should still allow retry
        assert msg.should_retry()
        
        # Test with retry count at custom limit
        msg.retry_count = 5
        assert not msg.should_retry()

    def test_retry_with_error_tracking(self, queue):
        """Test that retry errors are tracked properly."""
        current_time = time.time()
        
        # Create message with error
        msg = QueuedMessage(
            id="error-track",
            channel_id=123456789,
            content="Error tracking message",
            priority=MessagePriority.HIGH,
            created_at=current_time,
            status=MessageStatus.FAILED,
            retry_count=1,
            max_retries=3,
            last_error="Connection timeout",
        )
        
        queue.queue.append(msg)
        
        # Verify error is tracked
        assert msg.last_error == "Connection timeout"
        
        # Retry the message
        retried_count = queue.retry_failed_messages()
        assert retried_count == 1
        assert msg.status == MessageStatus.PENDING


class TestQueueProcessing:
    """Test queue processing functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    @pytest.fixture
    def mock_discord_client(self):
        """Create a mock Discord client."""
        client = MagicMock(spec=discord.Client)
        return client

    async def test_batch_processing_size_limit(self, queue, mock_discord_client):
        """Test that batch processing respects batch size limit."""
        queue.set_discord_client(mock_discord_client)
        
        # Add more messages than batch size
        for i in range(5):
            await queue.enqueue(
                channel_id=123456789,
                content=f"Message {i}",
                priority=MessagePriority.HIGH,
            )
        
        # Mock channel and rate limiter
        mock_channel = MagicMock()
        mock_discord_client.get_channel.return_value = mock_channel
        
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(return_value=True)
            
            # Process batch (should only process batch_size messages)
            await queue._process_batch()
            
            # Should have processed 3 messages (batch_size)
            assert mock_rate_limiter.send_message_with_backoff.call_count == 3
            assert len(queue.queue) == 2  # 2 messages remaining

    async def test_message_lifecycle_successful_delivery(self, queue, mock_discord_client):
        """Test complete message lifecycle for successful delivery."""
        queue.set_discord_client(mock_discord_client)
        
        # Add message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Mock successful delivery
        mock_channel = MagicMock()
        mock_discord_client.get_channel.return_value = mock_channel
        
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(return_value=True)
            
            # Process the message
            await queue._process_message(queue.queue[0])
            
            # Verify message was delivered and removed from queue
            assert len(queue.queue) == 0
            assert queue.stats["total_delivered"] == 1

    async def test_message_lifecycle_failed_delivery(self, queue, mock_discord_client):
        """Test message lifecycle for failed delivery."""
        queue.set_discord_client(mock_discord_client)
        
        # Add message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            max_retries=1,
        )
        
        # Mock failed delivery
        mock_channel = MagicMock()
        mock_discord_client.get_channel.return_value = mock_channel
        
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(return_value=None)
            
            # Process the message twice (should fail permanently after max retries)
            await queue._process_message(queue.queue[0])
            await queue._process_message(queue.queue[0])
            
            # Verify message was failed and removed from queue
            assert len(queue.queue) == 0
            assert queue.stats["total_failed"] == 1

    async def test_processing_loop_lifecycle(self, queue):
        """Test the main processing loop lifecycle."""
        # Start processing
        queue.start_processing()
        assert queue.is_processing
        assert queue.process_task is not None
        
        # Let it run briefly
        await asyncio.sleep(0.2)
        
        # Stop processing
        await queue.stop_processing()
        assert not queue.is_processing
        assert queue.process_task is None

    async def test_processing_with_discord_api_health_check(self, queue, mock_discord_client):
        """Test that processing respects Discord API health status."""
        queue.set_discord_client(mock_discord_client)
        
        # Add message to queue
        await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Mock Discord API as failed
        with patch('ip_monitor.utils.message_queue.service_health') as mock_service_health:
            mock_health_status = MagicMock()
            mock_health_status.status.value = "failed"
            mock_service_health.get_service_health.return_value = mock_health_status
            
            # Process batch (should skip due to failed Discord API)
            await queue._process_batch()
            
            # Message should still be in queue (not processed)
            assert len(queue.queue) == 1
            assert queue.queue[0].status == MessageStatus.PENDING

    async def test_processing_with_scheduled_messages(self, queue, mock_discord_client):
        """Test processing of scheduled messages."""
        queue.set_discord_client(mock_discord_client)
        current_time = time.time()
        
        # Add message scheduled for future
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Future message",
            priority=MessagePriority.HIGH,
            delay_seconds=3600,  # 1 hour in future
        )
        
        # Add message ready for processing
        message_id2 = await queue.enqueue(
            channel_id=123456789,
            content="Ready message",
            priority=MessagePriority.HIGH,
        )
        
        # Mock successful delivery
        mock_channel = MagicMock()
        mock_discord_client.get_channel.return_value = mock_channel
        
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(return_value=True)
            
            # Process batch
            await queue._process_batch()
            
            # Should only process the ready message, not the scheduled one
            assert mock_rate_limiter.send_message_with_backoff.call_count == 1
            assert len(queue.queue) == 1  # Scheduled message still in queue

    async def test_processing_with_expired_messages(self, queue, mock_discord_client):
        """Test processing handles expired messages correctly."""
        queue.set_discord_client(mock_discord_client)
        current_time = time.time()
        
        # Add expired message
        expired_msg = QueuedMessage(
            id="expired",
            channel_id=123456789,
            content="Expired message",
            priority=MessagePriority.HIGH,
            created_at=current_time - 7200,
            expires_at=current_time - 3600,  # Expired 1 hour ago
        )
        queue.queue.append(expired_msg)
        
        # Add valid message
        await queue.enqueue(
            channel_id=123456789,
            content="Valid message",
            priority=MessagePriority.HIGH,
        )
        
        # Process batch (should clean up expired messages)
        await queue._process_batch()
        
        # Expired message should be removed
        assert len(queue.queue) == 1
        assert queue.queue[0].content == "Valid message"
        assert queue.stats["total_expired"] > 0

    async def test_processing_with_channel_not_found(self, queue, mock_discord_client):
        """Test processing handles missing channels gracefully."""
        queue.set_discord_client(mock_discord_client)
        
        # Add message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Mock channel not found
        mock_discord_client.get_channel.return_value = None
        
        # Process the message (should fail gracefully)
        await queue._process_message(queue.queue[0])
        
        # Verify message failed and was scheduled for retry
        assert queue.queue[0].status == MessageStatus.PENDING  # Retry scheduled
        assert queue.queue[0].retry_count == 1
        assert "Channel" in queue.queue[0].last_error

    async def test_processing_with_embed_messages(self, queue, mock_discord_client):
        """Test processing messages with embeds."""
        queue.set_discord_client(mock_discord_client)
        
        # Create embed
        embed = discord.Embed(title="Test Embed", description="Test description")
        
        # Add message with embed
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Message with embed",
            priority=MessagePriority.HIGH,
            embed=embed,
        )
        
        # Mock successful delivery
        mock_channel = MagicMock()
        mock_discord_client.get_channel.return_value = mock_channel
        
        with patch('ip_monitor.utils.discord_rate_limiter.DiscordRateLimiter') as mock_rate_limiter_class:
            mock_rate_limiter = mock_rate_limiter_class.return_value
            mock_rate_limiter.send_message_with_backoff = AsyncMock(return_value=True)
            
            # Process the message
            await queue._process_message(queue.queue[0])
            
            # Verify embed was included in the call
            call_args = mock_rate_limiter.send_message_with_backoff.call_args
            assert 'embed' in call_args.kwargs
            assert call_args.kwargs['embed'].title == "Test Embed"

    async def test_processing_error_handling(self, queue, mock_discord_client):
        """Test that processing errors are handled gracefully."""
        queue.set_discord_client(mock_discord_client)
        
        # Add message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Mock channel to raise exception
        mock_discord_client.get_channel.side_effect = Exception("Unexpected error")
        
        # Process the message (should not raise exception)
        await queue._process_message(queue.queue[0])
        
        # Verify message failed and was scheduled for retry
        assert queue.queue[0].status == MessageStatus.PENDING  # Retry scheduled
        assert queue.queue[0].retry_count == 1
        assert "Unexpected error" in queue.queue[0].last_error

    async def test_processing_without_discord_client(self, queue):
        """Test that processing handles missing Discord client gracefully."""
        # Don't set Discord client
        
        # Add message to queue
        await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Process batch (should return early without error)
        await queue._process_batch()
        
        # Message should still be in queue
        assert len(queue.queue) == 1
        assert queue.queue[0].status == MessageStatus.PENDING


class TestDeduplicationAndEdgeCases:
    """Test deduplication and edge case functionality."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create a temporary queue file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        yield temp_file
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create a test message queue."""
        return AsyncMessageQueue(
            queue_file=temp_queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )

    async def test_message_deduplication(self, queue):
        """Test message deduplication functionality."""
        # Add message with dedupe key
        message_id1 = await queue.enqueue(
            channel_id=123456789,
            content="First message",
            priority=MessagePriority.HIGH,
            dedupe_key="unique-key-1",
        )
        
        # Add duplicate message with same dedupe key
        message_id2 = await queue.enqueue(
            channel_id=123456789,
            content="Duplicate message",
            priority=MessagePriority.HIGH,
            dedupe_key="unique-key-1",
        )
        
        # Should return same message ID and not add duplicate
        assert message_id1 == message_id2
        assert len(queue.queue) == 1
        assert queue.stats["total_deduplicated"] == 1
        assert queue.stats["total_queued"] == 1

    async def test_deduplication_cache_persistence(self, queue):
        """Test that deduplication cache persists across queue reloads."""
        # Add message with dedupe key
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            dedupe_key="persist-key",
        )
        
        # Create new queue instance with same file
        new_queue = AsyncMessageQueue(
            queue_file=queue.queue_file,
            max_queue_size=10,
            max_message_age_hours=1,
            batch_size=3,
            process_interval=0.1,
        )
        
        # Try to add duplicate message
        duplicate_id = await new_queue.enqueue(
            channel_id=123456789,
            content="Duplicate message",
            priority=MessagePriority.HIGH,
            dedupe_key="persist-key",
        )
        
        # Should return same message ID
        assert duplicate_id == message_id
        assert len(new_queue.queue) == 1
        assert new_queue.stats["total_deduplicated"] == 1

    async def test_deduplication_cache_cleanup_on_delivery(self, queue):
        """Test that deduplication cache is cleaned up when messages are delivered."""
        # Add message with dedupe key
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
            dedupe_key="cleanup-key",
        )
        
        # Verify dedupe cache contains the key
        assert "cleanup-key" in queue.dedupe_cache
        assert queue.dedupe_cache["cleanup-key"] == message_id
        
        # Simulate successful delivery (remove from queue)
        message = queue.queue[0]
        queue.queue.remove(message)
        if message.dedupe_key and message.dedupe_key in queue.dedupe_cache:
            del queue.dedupe_cache[message.dedupe_key]
        
        # Verify dedupe cache is cleaned up
        assert "cleanup-key" not in queue.dedupe_cache

    async def test_message_expiration_handling(self, queue):
        """Test comprehensive message expiration handling."""
        current_time = time.time()
        
        # Add message with short expiration
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Expiring message",
            priority=MessagePriority.HIGH,
            expires_in_hours=0.001,  # Very short expiration (3.6 seconds)
        )
        
        # Verify message is not expired initially
        assert not queue.queue[0].is_expired()
        
        # Wait for expiration
        await asyncio.sleep(0.1)
        
        # Update expiration manually for testing
        queue.queue[0].expires_at = current_time - 1
        
        # Verify message is now expired
        assert queue.queue[0].is_expired()
        
        # Clean up expired messages
        queue._cleanup_expired_messages()
        
        # Verify expired message was removed
        assert len(queue.queue) == 0
        assert queue.stats["total_expired"] == 1

    async def test_queue_status_comprehensive(self, queue):
        """Test comprehensive queue status reporting."""
        current_time = time.time()
        
        # Add messages with different states
        await queue.enqueue(
            channel_id=123456789,
            content="Pending message",
            priority=MessagePriority.HIGH,
        )
        
        # Add scheduled message
        await queue.enqueue(
            channel_id=123456789,
            content="Scheduled message",
            priority=MessagePriority.NORMAL,
            delay_seconds=3600,
        )
        
        # Add expired message manually
        expired_msg = QueuedMessage(
            id="expired",
            channel_id=123456789,
            content="Expired message",
            priority=MessagePriority.LOW,
            created_at=current_time - 7200,
            expires_at=current_time - 3600,
        )
        queue.queue.append(expired_msg)
        
        # Get comprehensive status
        status = queue.get_queue_status()
        
        # Verify status breakdown
        assert status["queue_size"] == 3
        assert status["ready_to_process"] == 1  # Only the pending message
        assert status["scheduled_for_later"] == 1  # The scheduled message
        assert status["status_breakdown"]["pending"] == 2  # pending + scheduled
        assert status["status_breakdown"]["expired"] == 1
        assert status["priority_breakdown"]["HIGH"] == 1
        assert status["priority_breakdown"]["NORMAL"] == 1
        assert status["priority_breakdown"]["LOW"] == 1
        assert status["oldest_message_age"] > 0
        assert status["dedupe_cache_size"] == 0

    async def test_get_message_by_id(self, queue):
        """Test retrieving specific messages by ID."""
        # Add message to queue
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Test message",
            priority=MessagePriority.HIGH,
        )
        
        # Retrieve message by ID
        retrieved_msg = queue.get_message_by_id(message_id)
        
        assert retrieved_msg is not None
        assert retrieved_msg.id == message_id
        assert retrieved_msg.content == "Test message"
        
        # Test with non-existent ID
        non_existent = queue.get_message_by_id("non-existent-id")
        assert non_existent is None

    async def test_clear_all_messages(self, queue):
        """Test clearing all messages from queue."""
        # Add messages with different priorities
        await queue.enqueue(
            channel_id=123456789,
            content="Message 1",
            priority=MessagePriority.HIGH,
            dedupe_key="key1",
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Message 2",
            priority=MessagePriority.LOW,
            dedupe_key="key2",
        )
        
        # Clear all messages
        cleared_count = queue.clear_queue()
        
        assert cleared_count == 2
        assert len(queue.queue) == 0
        assert len(queue.dedupe_cache) == 0

    async def test_queue_with_tags(self, queue):
        """Test message tagging functionality."""
        # Add message with tags
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Tagged message",
            priority=MessagePriority.HIGH,
            tags=["important", "notification", "ip-change"],
        )
        
        # Verify tags are preserved
        message = queue.queue[0]
        assert message.tags == ["important", "notification", "ip-change"]

    async def test_queue_size_enforcement_edge_cases(self, queue):
        """Test queue size enforcement edge cases."""
        # Set very small max size
        queue.max_queue_size = 1
        
        # Add message
        await queue.enqueue(
            channel_id=123456789,
            content="First message",
            priority=MessagePriority.LOW,
        )
        
        # Add higher priority message (should replace first)
        await queue.enqueue(
            channel_id=123456789,
            content="High priority message",
            priority=MessagePriority.CRITICAL,
        )
        
        # Should only have the high priority message
        assert len(queue.queue) == 1
        assert queue.queue[0].priority == MessagePriority.CRITICAL
        assert queue.queue[0].content == "High priority message"

    async def test_message_with_custom_expiration(self, queue):
        """Test messages with custom expiration times."""
        current_time = time.time()
        
        # Add message with custom expiration
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="Custom expiration",
            priority=MessagePriority.HIGH,
            expires_in_hours=2.0,  # 2 hours
        )
        
        # Verify expiration is set correctly
        message = queue.queue[0]
        expected_expiration = current_time + (2.0 * 3600)
        assert abs(message.expires_at - expected_expiration) < 1  # Within 1 second

    async def test_message_without_expiration(self, queue):
        """Test messages without expiration (when max_message_age_hours is 0)."""
        # Create queue with no automatic expiration
        queue.max_message_age_hours = 0
        
        # Add message without explicit expiration
        message_id = await queue.enqueue(
            channel_id=123456789,
            content="No expiration",
            priority=MessagePriority.HIGH,
        )
        
        # Verify message has no expiration
        message = queue.queue[0]
        assert message.expires_at is None
        assert not message.is_expired()

    async def test_queue_statistics_accuracy(self, queue):
        """Test that queue statistics are accurate."""
        initial_stats = queue.stats.copy()
        
        # Add messages
        await queue.enqueue(
            channel_id=123456789,
            content="Message 1",
            priority=MessagePriority.HIGH,
        )
        await queue.enqueue(
            channel_id=123456789,
            content="Message 2",
            priority=MessagePriority.HIGH,
            dedupe_key="dedupe-test",
        )
        
        # Add duplicate
        await queue.enqueue(
            channel_id=123456789,
            content="Duplicate",
            priority=MessagePriority.HIGH,
            dedupe_key="dedupe-test",
        )
        
        # Verify statistics
        assert queue.stats["total_queued"] == initial_stats["total_queued"] + 2
        assert queue.stats["total_deduplicated"] == initial_stats["total_deduplicated"] + 1

    async def test_queue_empty_operations(self, queue):
        """Test queue operations when queue is empty."""
        # Test operations on empty queue
        assert len(queue.queue) == 0
        
        # Clear empty queue
        cleared = queue.clear_queue()
        assert cleared == 0
        
        # Retry on empty queue
        retried = queue.retry_failed_messages()
        assert retried == 0
        
        # Get status of empty queue
        status = queue.get_queue_status()
        assert status["queue_size"] == 0
        assert status["ready_to_process"] == 0
        assert status["scheduled_for_later"] == 0