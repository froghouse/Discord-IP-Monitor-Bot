"""
Base handler class for admin commands.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, Union

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter

logger = logging.getLogger(__name__)


class BaseHandler(ABC):
    """
    Base class for admin command handlers.

    Provides common functionality for permission checking, rate limiting,
    error handling, and response formatting.
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
        Initialize the base handler.

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

    def check_admin_permissions(self, message: discord.Message) -> bool:
        """
        Check if the user has administrator permissions.

        Args:
            message: The Discord message to check permissions for

        Returns:
            bool: True if user has admin permissions, False otherwise
        """
        return message.author.guild_permissions.administrator

    async def send_permission_denied(self, message: discord.Message) -> None:
        """
        Send a permission denied message to the user.

        Args:
            message: The original message to respond to
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel,
            "❌ You don't have permission to use this command. Administrator privileges required.",
        )

    async def send_error_message(self, message: discord.Message, error: str) -> None:
        """
        Send an error message to the user.

        Args:
            message: The original message to respond to
            error: Error message to send
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, f"❌ {error}"
        )

    async def send_success_message(
        self, message: discord.Message, success: str
    ) -> None:
        """
        Send a success message to the user.

        Args:
            message: The original message to respond to
            success: Success message to send
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, f"✅ {success}"
        )

    async def send_info_message(self, message: discord.Message, info: str) -> None:
        """
        Send an info message to the user.

        Args:
            message: The original message to respond to
            info: Info message to send
        """
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, f"ℹ️ {info}"
        )

    async def add_reaction(self, message: discord.Message, emoji: str) -> None:
        """
        Add a reaction to a message with error handling.

        Args:
            message: The message to add reaction to
            emoji: The emoji to add
        """
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException as e:
            logger.warning(f"Failed to add reaction {emoji}: {e}")

    def log_command_usage(self, message: discord.Message, command: str) -> None:
        """
        Log command usage for debugging and monitoring.

        Args:
            message: The Discord message containing the command
            command: The command that was used
        """
        logger.info(
            f"Admin command '{command}' used by {message.author} in #{message.channel}"
        )

    async def handle_command_error(
        self, message: discord.Message, error: Exception, command: str
    ) -> None:
        """
        Handle errors that occur during command execution.

        Args:
            message: The original message
            error: The exception that occurred
            command: The command that failed
        """
        logger.error(f"Error in admin command '{command}': {error}", exc_info=True)
        await self.send_error_message(
            message,
            f"An error occurred while processing the '{command}' command. Please try again.",
        )

    def format_code_block(self, content: str, language: str = "") -> str:
        """
        Format content as a Discord code block.

        Args:
            content: The content to format
            language: Optional language for syntax highlighting

        Returns:
            str: Formatted code block
        """
        return f"```{language}\n{content}\n```"

    def format_inline_code(self, content: str) -> str:
        """
        Format content as inline code.

        Args:
            content: The content to format

        Returns:
            str: Formatted inline code
        """
        return f"`{content}`"

    def truncate_message(self, message: str, max_length: int = 2000) -> str:
        """
        Truncate a message to fit Discord's character limits.

        Args:
            message: The message to truncate
            max_length: Maximum length (default: 2000 for Discord)

        Returns:
            str: Truncated message
        """
        if len(message) <= max_length:
            return message

        truncated = message[: max_length - 3] + "..."
        logger.warning(
            f"Message truncated from {len(message)} to {len(truncated)} characters"
        )
        return truncated

    @abstractmethod
    async def handle_command(self, message: discord.Message, args: list[str]) -> bool:
        """
        Handle the specific command for this handler.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        pass

    @abstractmethod
    def get_help_text(self) -> str:
        """
        Get help text for commands handled by this handler.

        Returns:
            str: Help text describing available commands
        """
        pass
