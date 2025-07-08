"""
Admin command router for the IP Monitor Bot.
"""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter

from .api_handler import ApiHandler
from .base_handler import BaseHandler
from .bot_lifecycle_handler import BotLifecycleHandler
from .cache_handler import CacheHandler
from .config_handler import ConfigHandler
from .queue_handler import QueueHandler

logger = logging.getLogger(__name__)


class AdminCommandRouter:
    """
    Routes admin commands to appropriate handlers.

    This class replaces the monolithic AdminCommands class and provides
    a clean interface for handling all admin commands through specialized handlers.
    """

    def __init__(
        self,
        client: discord.Client,
        ip_service: IPService,
        storage: IPStorage | SQLiteIPStorage,
        stop_callback: Callable[[], Coroutine[Any, Any, None]],
        config: AppConfig,
    ) -> None:
        """
        Initialize the admin command router.

        Args:
            client: Discord client instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback to stop the bot
            config: Application configuration
        """
        self.client = client
        self.ip_service = ip_service
        self.storage = storage
        self.stop_callback = stop_callback
        self.config = config
        self.discord_rate_limiter = DiscordRateLimiter()

        # Initialize all command handlers
        self.handlers: list[BaseHandler] = [
            BotLifecycleHandler(client, ip_service, storage, stop_callback, config),
            ConfigHandler(client, ip_service, storage, stop_callback, config),
            QueueHandler(client, ip_service, storage, stop_callback, config),
            ApiHandler(client, ip_service, storage, stop_callback, config),
            CacheHandler(client, ip_service, storage, stop_callback, config),
        ]

        # Create command mapping for quick lookup
        self.command_map = {
            "stop": self.handlers[0],  # BotLifecycleHandler
            "config": self.handlers[1],  # ConfigHandler
            "queue": self.handlers[2],  # QueueHandler
            "api": self.handlers[3],  # ApiHandler
            "cache": self.handlers[4],  # CacheHandler
        }

    def check_admin_permissions(self, message: discord.Message) -> bool:
        """
        Check if the user has administrator permissions.

        Args:
            message: The Discord message to check permissions for

        Returns:
            bool: True if user has admin permissions, False otherwise
        """
        return message.author.guild_permissions.administrator

    async def handle_admin_command(self, message: discord.Message) -> bool:
        """
        Handle admin commands by routing to appropriate handlers.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        # Check admin permissions first
        if not self.check_admin_permissions(message):
            await self._send_permission_denied(message)
            return False

        # Parse the command
        parts = message.content.split()
        if len(parts) < 2:
            await self._send_admin_help(message)
            return True

        # Extract command and arguments
        command = parts[1].lower()
        args = parts[1:]  # Include the command as first argument for handlers

        # Route to appropriate handler
        handler = self.command_map.get(command)
        if handler:
            try:
                return await handler.handle_command(message, args)
            except Exception as e:
                logger.error(
                    f"Error in admin command handler for '{command}': {e}",
                    exc_info=True,
                )
                await self._send_error_message(
                    message,
                    f"An error occurred while processing the '{command}' command. Please try again.",
                )
                return False
        else:
            await self._send_unknown_command(message, command)
            return False

    async def handle_stop_command(self, message: discord.Message) -> bool:
        """
        Handle the !stop command specifically.

        This method is kept for backward compatibility with the bot's main loop.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        return await self.command_map["stop"].handle_command(message, ["stop"])

    async def handle_config_command(self, message: discord.Message) -> bool:
        """
        Handle the !config command specifically.

        This method is kept for backward compatibility with the bot's main loop.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        parts = message.content.split()
        args = parts[1:] if len(parts) > 1 else ["config"]
        return await self.command_map["config"].handle_command(message, args)

    async def handle_queue_command(self, message: discord.Message) -> bool:
        """
        Handle the !queue command specifically.

        This method is kept for backward compatibility with the bot's main loop.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        parts = message.content.split()
        args = parts[1:] if len(parts) > 1 else ["queue"]
        return await self.command_map["queue"].handle_command(message, args)

    async def handle_api_command(self, message: discord.Message) -> bool:
        """
        Handle the !api command specifically.

        This method is kept for backward compatibility with the bot's main loop.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        parts = message.content.split()
        args = parts[1:] if len(parts) > 1 else ["api"]
        return await self.command_map["api"].handle_command(message, args)

    async def handle_cache_command(self, message: discord.Message) -> bool:
        """
        Handle the !cache command specifically.

        This method is kept for backward compatibility with the bot's main loop.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        parts = message.content.split()
        args = parts[1:] if len(parts) > 1 else ["cache"]
        return await self.command_map["cache"].handle_command(message, args)

    async def _send_permission_denied(self, message: discord.Message) -> None:
        """
        Send a permission denied message to the user.

        Args:
            message: The original message to respond to
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel,
            "❌ You don't have permission to use admin commands. Administrator privileges required.",
        )

    async def _send_error_message(self, message: discord.Message, error: str) -> None:
        """
        Send an error message to the user.

        Args:
            message: The original message to respond to
            error: Error message to send
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, f"❌ {error}"
        )

    async def _send_unknown_command(
        self, message: discord.Message, command: str
    ) -> None:
        """
        Send an unknown command message to the user.

        Args:
            message: The original message to respond to
            command: The unknown command
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel,
            f"❌ Unknown admin command: `{command}`. Use `!admin` for help.",
        )

    async def _send_admin_help(self, message: discord.Message) -> None:
        """
        Send comprehensive admin help message.

        Args:
            message: The original message to respond to
        """
        help_text = self._get_admin_help_text()
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, help_text
        )

    def _get_admin_help_text(self) -> str:
        """
        Get comprehensive help text for all admin commands.

        Returns:
            str: Complete help text for admin commands
        """
        help_sections = []

        # Add help from each handler
        for handler in self.handlers:
            help_sections.append(handler.get_help_text())

        # Create comprehensive help text
        help_text = "**🔧 Admin Commands Help**\n\n"
        help_text += "\n\n".join(help_sections)

        help_text += "\n\n**General Information:**\n"
        help_text += "• All admin commands require administrator permissions\n"
        help_text += "• Commands are case-insensitive\n"
        help_text += "• Use `!<command>` for specific command help\n"
        help_text += "• Most configuration changes take effect immediately\n"
        help_text += "• Some settings require a bot restart (marked with ⚠️)\n"

        return help_text

    def get_available_commands(self) -> list[str]:
        """
        Get a list of all available admin commands.

        Returns:
            list[str]: List of command names
        """
        return list(self.command_map.keys())

    def get_handler_for_command(self, command: str) -> BaseHandler:
        """
        Get the handler for a specific command.

        Args:
            command: The command name

        Returns:
            BaseHandler: The handler for the command, or None if not found
        """
        return self.command_map.get(command.lower())

    def add_handler(self, command: str, handler: BaseHandler) -> None:
        """
        Add a new command handler.

        Args:
            command: The command name
            handler: The handler instance
        """
        self.command_map[command.lower()] = handler
        if handler not in self.handlers:
            self.handlers.append(handler)

    def remove_handler(self, command: str) -> bool:
        """
        Remove a command handler.

        Args:
            command: The command name

        Returns:
            bool: True if handler was removed, False if not found
        """
        command_lower = command.lower()
        if command_lower in self.command_map:
            handler = self.command_map[command_lower]
            del self.command_map[command_lower]

            # Remove from handlers list if no other commands use it
            if handler not in self.command_map.values():
                self.handlers.remove(handler)

            return True
        return False
