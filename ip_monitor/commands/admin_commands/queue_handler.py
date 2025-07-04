"""
Queue handler for admin commands.
"""

import logging
from typing import Any, Callable, Coroutine, Union

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.message_queue import message_queue

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class QueueHandler(BaseHandler):
    """
    Handles message queue-related admin commands.
    """

    def __init__(
        self,
        client: discord.Client,
        ip_service: IPService,
        storage: Union[IPStorage, SQLiteIPStorage],
        stop_callback: Callable[[], Coroutine[Any, Any, None]],
        config: AppConfig,
    ) -> None:
        """
        Initialize the queue handler.

        Args:
            client: Discord client instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback to stop the bot
            config: Application configuration
        """
        super().__init__(client, ip_service, storage, stop_callback, config)

    async def handle_command(self, message: discord.Message, args: list[str]) -> bool:
        """
        Handle queue commands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        if not args:
            return False

        command = args[0].lower()

        if command == "queue":
            return await self._handle_queue_command(message, args[1:])

        return False

    async def _handle_queue_command(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !queue command and its subcommands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments (excluding 'queue')

        Returns:
            bool: True if handled successfully
        """
        # Check admin permissions
        if not self.check_admin_permissions(message):
            await self.send_permission_denied(message)
            return False

        self.log_command_usage(message, "queue")

        if not args:
            # Show queue status
            return await self._show_queue_status(message)

        subcommand = args[0].lower()

        try:
            if subcommand == "clear":
                return await self._handle_queue_clear(message)
            elif subcommand == "retry":
                return await self._handle_queue_retry(message)
            elif subcommand == "start":
                return await self._handle_queue_start(message)
            elif subcommand == "stop":
                return await self._handle_queue_stop(message)
            else:
                # Show help for unknown subcommand
                help_text = self._get_queue_help_text()
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, help_text
                )
                return True
        except Exception as e:
            await self.handle_command_error(message, e, f"queue {subcommand}")
            return False

    async def _show_queue_status(self, message: discord.Message) -> bool:
        """
        Show the current queue status.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        queue_status = message_queue.get_queue_status()
        status_text = "📥 **Message Queue Status**\n"
        status_text += f"Queue Size: {queue_status['queue_size']}/{queue_status['max_queue_size']}\n"
        status_text += (
            f"Processing: {'Yes' if queue_status['is_processing'] else 'No'}\n"
        )
        status_text += f"Ready to Process: {queue_status['ready_to_process']}\n"
        status_text += f"Scheduled for Later: {queue_status['scheduled_for_later']}\n"

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

        # Truncate if too long for Discord
        status_text = self.truncate_message(status_text)
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, status_text
        )
        return True

    async def _handle_queue_clear(self, message: discord.Message) -> bool:
        """
        Handle the !queue clear command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        cleared = message_queue.clear_queue()
        await self.send_success_message(
            message, f"Cleared {cleared} messages from queue"
        )
        logger.info(
            f"Admin {message.author} cleared message queue ({cleared} messages)"
        )
        return True

    async def _handle_queue_retry(self, message: discord.Message) -> bool:
        """
        Handle the !queue retry command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        retried = message_queue.retry_failed_messages()
        await self.send_success_message(
            message, f"Scheduled {retried} failed messages for retry"
        )
        logger.info(
            f"Admin {message.author} retried failed messages ({retried} messages)"
        )
        return True

    async def _handle_queue_start(self, message: discord.Message) -> bool:
        """
        Handle the !queue start command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        if not message_queue.is_processing:
            message_queue.start_processing()
            await self.send_success_message(message, "Message queue processing started")
            logger.info(f"Admin {message.author} started message queue processing")
        else:
            await self.send_info_message(message, "Message queue is already processing")
        return True

    async def _handle_queue_stop(self, message: discord.Message) -> bool:
        """
        Handle the !queue stop command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        if message_queue.is_processing:
            await message_queue.stop_processing()
            await self.send_success_message(message, "Message queue processing stopped")
            logger.info(f"Admin {message.author} stopped message queue processing")
        else:
            await self.send_info_message(message, "Message queue is not processing")
        return True

    def _get_queue_help_text(self) -> str:
        """
        Get help text for queue commands.

        Returns:
            str: Help text for queue commands
        """
        return """**Queue Commands:**
• `!queue` - Show queue status and statistics
• `!queue clear` - Clear all queued messages
• `!queue retry` - Retry all failed messages
• `!queue start` - Start queue processing
• `!queue stop` - Stop queue processing

**Queue Status Information:**
• Queue size and capacity
• Processing status
• Message counts by status and priority
• Statistics (delivered, failed, expired, deduplicated)"""

    def get_help_text(self) -> str:
        """
        Get help text for queue commands.

        Returns:
            str: Help text describing available commands
        """
        return self._get_queue_help_text()
