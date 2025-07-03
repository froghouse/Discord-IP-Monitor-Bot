"""
Administrative commands for the IP Monitor Bot.
"""

import logging
from typing import Any, Callable, Coroutine

import discord

from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter
from ip_monitor.utils.message_queue import message_queue

logger = logging.getLogger(__name__)


class AdminCommands:
    """
    Handles administrative bot commands.
    """

    def __init__(
        self,
        client: discord.Client,
        ip_service: IPService,
        storage: IPStorage,
        stop_callback: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Initialize the admin commands handler.

        Args:
            client: Discord client instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback to stop the bot
        """
        self.client = client
        self.ip_service = ip_service
        self.storage = storage
        self.stop_callback = stop_callback
        self.discord_rate_limiter = DiscordRateLimiter()

    async def handle_stop_command(self, message: discord.Message) -> bool:
        """
        Handle the !stop command to stop the bot.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can stop the bot
        if not message.author.guild_permissions.administrator:
            return False

        logger.info(f"Stop command received from {message.author}")
        await message.add_reaction("🛑")

        try:
            # First save the current IP one last time
            current_ip = await self.ip_service.get_public_ip()
            if current_ip:
                self.storage.save_current_ip(current_ip)

            # Send the goodbye message
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "🛑 Stopping bot. Goodbye!"
            )

            # Execute the stop callback
            await self.stop_callback()

            return True
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                "⚠️ Error during shutdown. The bot may not stop cleanly.",
            )
            # Try to force close even if there was an error
            await self.client.close()
            return True

    async def handle_queue_command(self, message: discord.Message) -> bool:
        """
        Handle the !queue command to manage message queue.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can manage the queue
        if not message.author.guild_permissions.administrator:
            return False

        parts = message.content.split()
        if len(parts) < 2:
            # Show queue status
            queue_status = message_queue.get_queue_status()
            status_text = "📥 **Message Queue Status**\n"
            status_text += f"Queue Size: {queue_status['queue_size']}/{queue_status['max_queue_size']}\n"
            status_text += (
                f"Processing: {'Yes' if queue_status['is_processing'] else 'No'}\n"
            )
            status_text += f"Ready to Process: {queue_status['ready_to_process']}\n"
            status_text += (
                f"Scheduled for Later: {queue_status['scheduled_for_later']}\n"
            )

            # Statistics
            stats = queue_status["statistics"]
            status_text += "\n📊 **Statistics**\n"
            status_text += f"Total Queued: {stats['total_queued']}\n"
            status_text += f"Total Delivered: {stats['total_delivered']}\n"
            status_text += f"Total Failed: {stats['total_failed']}\n"
            status_text += f"Total Expired: {stats['total_expired']}\n"
            status_text += f"Deduplicated: {stats['total_deduplicated']}\n"

            # Breakdowns
            if queue_status["status_breakdown"]:
                status_text += (
                    f"\n**Status Breakdown**: {queue_status['status_breakdown']}\n"
                )
            if queue_status["priority_breakdown"]:
                status_text += (
                    f"**Priority Breakdown**: {queue_status['priority_breakdown']}\n"
                )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, status_text
            )
            return True

        command = parts[1].lower()

        if command == "clear":
            # Clear the queue
            cleared = message_queue.clear_queue()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Cleared {cleared} messages from queue"
            )
            logger.info(
                f"Admin {message.author} cleared message queue ({cleared} messages)"
            )
            return True

        elif command == "retry":
            # Retry failed messages
            retried = message_queue.retry_failed_messages()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"🔄 Scheduled {retried} failed messages for retry"
            )
            logger.info(
                f"Admin {message.author} retried failed messages ({retried} messages)"
            )
            return True

        elif command == "start":
            # Start queue processing
            if not message_queue.is_processing:
                message_queue.start_processing()
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "▶️ Message queue processing started"
                )
                logger.info(f"Admin {message.author} started message queue processing")
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "ℹ️ Message queue is already processing"
                )
            return True

        elif command == "stop":
            # Stop queue processing
            if message_queue.is_processing:
                await message_queue.stop_processing()
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "⏹️ Message queue processing stopped"
                )
                logger.info(f"Admin {message.author} stopped message queue processing")
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "ℹ️ Message queue is not processing"
                )
            return True

        else:
            # Unknown command
            help_text = "**Queue Commands:**\n"
            help_text += "`!queue` - Show queue status\n"
            help_text += "`!queue clear` - Clear all queued messages\n"
            help_text += "`!queue retry` - Retry all failed messages\n"
            help_text += "`!queue start` - Start queue processing\n"
            help_text += "`!queue stop` - Stop queue processing\n"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True
