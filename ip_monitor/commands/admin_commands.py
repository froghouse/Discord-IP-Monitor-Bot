"""
Administrative commands for the IP Monitor Bot.
"""

import logging
from typing import Any, Callable, Coroutine

import discord

from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter

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
