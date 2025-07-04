"""
Bot lifecycle handler for admin commands.
"""

import logging
from typing import Any, Callable, Coroutine, Union

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class BotLifecycleHandler(BaseHandler):
    """
    Handles bot lifecycle commands like !stop.
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
        Initialize the bot lifecycle handler.

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
        Handle bot lifecycle commands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        if not args:
            return False

        command = args[0].lower()

        if command == "stop":
            return await self._handle_stop_command(message)

        return False

    async def _handle_stop_command(self, message: discord.Message) -> bool:
        """
        Handle the !stop command to stop the bot.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Check admin permissions
        if not self.check_admin_permissions(message):
            await self.send_permission_denied(message)
            return False

        self.log_command_usage(message, "stop")
        await self.add_reaction(message, "🛑")

        try:
            # First save the current IP one last time
            current_ip = await self.ip_service.get_public_ip()
            if current_ip:
                self.storage.save_current_ip(current_ip)
                logger.info(f"Final IP saved before shutdown: {current_ip}")

            # Send the goodbye message
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "🛑 Stopping bot. Goodbye!"
            )

            # Execute the stop callback
            await self.stop_callback()

            return True
        except Exception as e:
            await self.handle_command_error(message, e, "stop")

            # Try to force close even if there was an error
            try:
                await self.client.close()
            except Exception as close_error:
                logger.error(f"Error during force close: {close_error}", exc_info=True)

            return True

    def get_help_text(self) -> str:
        """
        Get help text for bot lifecycle commands.

        Returns:
            str: Help text describing available commands
        """
        return """**Bot Lifecycle Commands:**
• `!stop` - Gracefully shut down the bot (Admin only)
  - Saves current IP before shutdown
  - Sends goodbye message
  - Performs clean shutdown sequence"""
