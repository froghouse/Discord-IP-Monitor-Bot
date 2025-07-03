"""
IP-related commands for the IP Monitor Bot.
"""

import asyncio
import logging
from datetime import datetime
from typing import Union

import discord

from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter
from ip_monitor.utils.message_queue import MessagePriority, message_queue
from ip_monitor.utils.rate_limiter import RateLimiter
from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class IPCommands:
    """
    Handles IP-related bot commands.
    """

    def __init__(
        self,
        channel_id: int,
        ip_service: IPService,
        storage: Union[IPStorage, SQLiteIPStorage],
        rate_limiter: RateLimiter,
    ) -> None:
        """
        Initialize the IP commands handler.

        Args:
            channel_id: Discord channel ID for bot messages
            ip_service: Service for IP address operations
            storage: Storage for IP data
            rate_limiter: Rate limiter for IP checks
        """
        self.channel_id = channel_id
        self.ip_service = ip_service
        self.storage = storage
        self.rate_limiter = rate_limiter
        self.ip_check_lock = asyncio.Lock()
        self.discord_rate_limiter = DiscordRateLimiter()

    async def send_message_with_retry(
        self,
        channel: discord.TextChannel,
        content: str,
        max_retries: int = 3,
        priority: MessagePriority = MessagePriority.NORMAL,
        use_queue: bool = True,
    ) -> bool:
        """
        Send a message to a Discord channel with retry logic, rate limiting, and queuing.

        Args:
            channel: The Discord channel to send the message to
            content: The message content to send
            max_retries: The maximum number of retries (default is 3)
            priority: Message priority for queuing
            use_queue: Whether to use message queue for delivery

        Returns:
            bool: True if message was sent successfully or queued, False otherwise
        """
        try:
            # Check if notifications are enabled in current degradation mode
            if not service_health.should_enable_feature("notifications"):
                logger.debug("Notifications disabled in current degradation mode")
                return True  # Pretend success to not break logic

            # Check Discord API health
            discord_health = service_health.get_service_health("discord_api")

            # If Discord API is healthy, try direct send first
            if discord_health and discord_health.status.value in ["healthy", "unknown"]:
                try:
                    message = await self.discord_rate_limiter.send_message_with_backoff(
                        channel, content
                    )
                    if message is not None:
                        service_health.record_success("discord_api", "send_message")
                        return True
                except Exception as e:
                    logger.debug(f"Direct send failed, will queue message: {e}")
                    service_health.record_failure(
                        "discord_api", f"Direct send failed: {e}", "send_message"
                    )

            # Queue the message if direct send failed or Discord API is degraded
            if use_queue:
                # Check if message queue is enabled via service health (fallback check)
                try:
                    # Create dedupe key for IP-related messages to prevent spam
                    dedupe_key = None
                    if "IP address" in content or "IP check" in content:
                        dedupe_key = f"ip_notification_{hash(content) % 10000}"

                    message_id = await message_queue.enqueue(
                        channel_id=channel.id,
                        content=content,
                        priority=priority,
                        max_retries=max_retries,
                        dedupe_key=dedupe_key,
                        tags=["ip_monitor"],
                    )

                    if message_id:
                        logger.info(
                            f"Message queued with ID {message_id} (priority: {priority.name})"
                        )
                        return True
                    else:
                        logger.error("Failed to queue message")
                        return False
                except Exception as queue_error:
                    logger.error(f"Error accessing message queue: {queue_error}")
                    service_health.record_failure(
                        "discord_api", f"Queue error: {queue_error}", "message_queue"
                    )
                    return False
            else:
                # No queuing, mark as failed
                service_health.record_failure(
                    "discord_api",
                    "Direct send failed and queuing disabled",
                    "send_message",
                )
                return False

        except Exception as e:
            logger.error(f"Failed to send/queue message: {e}")
            service_health.record_failure(
                "discord_api", f"Send/queue error: {e}", "send_message"
            )
            return False

    async def check_ip_once(
        self, client: discord.Client, user_requested: bool = False
    ) -> bool:
        """
        Check the IP once (used at startup and for manual checks).

        Args:
            client: Discord client instance for channel access
            user_requested: Whether this check was requested by a user (default: False)

        Returns:
            bool: True if check was successful, False otherwise
        """
        try:
            channel = client.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Could not find channel with ID {self.channel_id}")
                return False

            # Check if we're rate limited
            is_limited, wait_time = self.rate_limiter.is_limited()
            if is_limited:
                logger.warning(f"Rate limit reached. Need to wait {wait_time} seconds.")
                await self.send_message_with_retry(
                    channel,
                    f"⚠️ Rate limit reached. Please wait {wait_time} seconds before checking again.",
                )
                return False

            # Get the current IP
            current_ip = await self.ip_service.get_public_ip()
            if not current_ip:
                logger.error("Failed to get current IP address")
                await self.send_message_with_retry(
                    channel,
                    "❌ Failed to retrieve the current IP address. Please try again later.",
                )
                return False

            # Get the last known IP
            last_ip = self.storage.load_last_ip()

            # Save the current IP (skip if in read-only mode)
            if not service_health.is_fallback_active("read_only_mode"):
                if not self.storage.save_current_ip(current_ip):
                    logger.error("Failed to save current IP address")
                    await self.send_message_with_retry(
                        channel,
                        "❌ Failed to save the current IP address. Please try again later.",
                    )
                    return False
            else:
                logger.debug("Skipping IP save due to read-only mode")

            # Only send a message if the IP has changed or if a user requested the check
            if last_ip and last_ip != current_ip:
                # IP has changed, always send a message (HIGH priority)
                message = "🔄 IP address has changed!\n\n"
                message += f"**Previous IP:** `{last_ip}`\n"
                message += f"**Current IP:** `{current_ip}`\n"
                message += f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                await self.send_message_with_retry(
                    channel, message, priority=MessagePriority.HIGH
                )
            elif user_requested:
                # User requested a check, send the result even if IP hasn't changed (NORMAL priority)
                message = "✅ IP address check complete.\n\n"
                message += f"**Current IP:** `{current_ip}`\n"
                message += f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                if last_ip:
                    message += f"\n\nNo change from previous IP: `{last_ip}`"
                await self.send_message_with_retry(
                    channel, message, priority=MessagePriority.NORMAL
                )
            else:
                # Scheduled check with no change, don't send a message
                logger.info(
                    f"Scheduled IP check: No change detected. Current IP: {current_ip}"
                )

            return True
        except Exception as e:
            logger.error(f"Error checking IP: {e}")
            return False

    async def handle_status_command(self, message: discord.Message) -> bool:
        """
        Handle the !status command to show bot status.

        Args:
            message: The Discord message containing the command
            client: Discord client instance

        Returns:
            bool: True if handled successfully
        """
        logger.info(f"Status check requested by {message.author}")

        # Format status info
        is_limited, wait_time = self.rate_limiter.is_limited()
        remaining_calls = self.rate_limiter.get_remaining_calls()
        check_interval = getattr(self, "check_interval", 30)  # Default to 30 if not set
        max_retries = self.ip_service.max_retries
        concurrent_api_checking = self.ip_service.use_concurrent_checks

        status_text = "📊 **IP Monitor Bot Status**\n"
        status_text += f"⏱️ Checking interval: Every {check_interval} minutes\n"
        status_text += f"🔄 IP API retry attempts: {max_retries}\n"
        status_text += f"⚡ Concurrent API checking: {'Enabled' if concurrent_api_checking else 'Disabled'}\n"
        status_text += f"⏳ Rate limit status: {'Limited (wait ' + str(wait_time) + ' seconds)' if is_limited else 'Not limited'}\n"
        status_text += f"📝 Checks remaining in current period: {remaining_calls}/{self.rate_limiter.max_calls}\n"

        # Add circuit breaker info
        cb_info = self.ip_service.get_circuit_breaker_info()
        if cb_info["enabled"]:
            cb_state = cb_info["state"]
            if cb_state == "closed":
                status_text += "🟢 Circuit breaker: CLOSED (normal operation)\n"
            elif cb_state == "open":
                time_until_half_open = cb_info.get("time_until_half_open", 0)
                status_text += (
                    f"🔴 Circuit breaker: OPEN (retry in {time_until_half_open:.0f}s)\n"
                )
            elif cb_state == "half_open":
                status_text += "🟡 Circuit breaker: HALF-OPEN (testing recovery)\n"

            if cb_info.get("last_known_ip"):
                status_text += f"💾 Cached IP: `{cb_info['last_known_ip']}`\n"
        else:
            status_text += "⚪ Circuit breaker: Disabled\n"

        # Add current IP info
        current_ip = self.storage.load_last_ip()
        if current_ip:
            status_text += f"🌐 Current IP: `{current_ip}`\n"

        # Add service health information
        system_health = service_health.get_system_health()
        degradation_level = system_health["degradation_level"]

        if degradation_level == "normal":
            status_text += "✅ System Health: NORMAL\n"
        elif degradation_level == "minor":
            status_text += "🟡 System Health: MINOR ISSUES\n"
        elif degradation_level == "moderate":
            status_text += "🟠 System Health: DEGRADED\n"
        elif degradation_level == "severe":
            status_text += "🔴 System Health: SEVERE DEGRADATION\n"
        elif degradation_level == "critical":
            status_text += "💀 System Health: CRITICAL\n"

        # Show failed/degraded services
        failed_services = [
            name
            for name, info in system_health["services"].items()
            if info["status"] == "failed"
        ]
        degraded_services = [
            name
            for name, info in system_health["services"].items()
            if info["status"] == "degraded"
        ]

        if failed_services:
            status_text += f"❌ Failed: {', '.join(failed_services)}\n"
        if degraded_services:
            status_text += f"⚠️ Degraded: {', '.join(degraded_services)}\n"

        # Show active fallbacks
        active_fallbacks = system_health["system_capabilities"]["active_fallbacks"]
        if active_fallbacks:
            status_text += f"🔄 Active Fallbacks: {', '.join(active_fallbacks)}\n"

        # Add message queue status
        queue_status = message_queue.get_queue_status()
        status_text += f"📥 Message Queue: {queue_status['queue_size']}/{queue_status['max_queue_size']} messages\n"

        if queue_status["queue_size"] > 0:
            status_text += f"   ↳ Ready: {queue_status['ready_to_process']}, Scheduled: {queue_status['scheduled_for_later']}\n"

        queue_stats = queue_status["statistics"]
        status_text += f"📊 Queue Stats: {queue_stats['total_delivered']} sent, {queue_stats['total_failed']} failed\n"

        await self.send_message_with_retry(
            message.channel, status_text, priority=MessagePriority.LOW
        )
        return True

    async def handle_help_command(self, message: discord.Message) -> bool:
        """
        Handle the !help command to show available commands.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        help_text = (
            "**IP Monitor Bot Commands**\n"
            "- `!ip` - Manually check the current IP address\n"
            "- `!history` - View IP address history\n"
            "- `!status` - View bot status and configuration\n"
            "- `!help` - Show this help message\n"
            "\n**Admin Commands:**\n"
            "- `!config` - Manage bot configuration\n"
            "- `!api` - Manage IP detection APIs\n"
            "- `!queue` - Manage message queue\n"
            "- `!stop` - Stop the bot\n"
        )
        await self.send_message_with_retry(message.channel, help_text)
        return True

    async def handle_history_command(self, message: discord.Message) -> bool:
        """
        Handle the !history command to show IP history.
        """
        logger.info(f"IP history requested by {message.author}")
        history = self.storage.load_ip_history()

        if not history:
            await self.send_message_with_retry(
                message.channel, "No IP history available."
            )
            return True

        history_text = "📜 **IP Address History**\n"
        for idx, entry in enumerate(reversed(history), 1):
            ip = entry.get("ip", "Unknown")
            timestamp_str = entry.get("timestamp", "Unknown time")
            try:
                # Convert ISO timestamp to more readable format
                dt = datetime.fromisoformat(timestamp_str)
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass

            history_text += f"{idx}. IP: `{ip}` - {timestamp_str}\n"

            # Discord message limit is 2000 chars, be safe and break if needed
            if len(history_text) > 1800 and idx < len(history):
                history_text += f"... and {len(history) - idx} more entries"
                break

        await self.send_message_with_retry(message.channel, history_text)
        return True

    async def handle_ip_command(
        self, message: discord.Message, client: discord.Client
    ) -> bool:
        """
        Handle the !ip command to manually check the current IP address.

        Args:
            message: The Discord message containing the command
            client: The Discord client instance
        """
        logger.info(f"IP check requested by {message.author}")

        # Check if we're rate limited
        is_limited, wait_time = self.rate_limiter.is_limited()
        if is_limited:
            logger.warning(f"Rate limit reached. Need to wait {wait_time} seconds.")
            await self.send_message_with_retry(
                message.channel,
                f"⚠️ Rate limit reached. Please wait {wait_time} seconds before checking again.",
            )
            return True

        # Use the check_ip_once method with user_requested=True
        # This will send a message regardless of whether the IP has changed
        return await self.check_ip_once(client, user_requested=True)
