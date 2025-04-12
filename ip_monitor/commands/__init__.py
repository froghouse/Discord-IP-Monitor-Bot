"""
Command handling for the IP Monitor Bot.
"""

from typing import Protocol

import discord


class CommandHandler(Protocol):
    """Protocol for command handlers."""

    async def handle(self, message: discord.Message) -> bool:
        """
        Handle a command message.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if command was handled, False otherwise
        """
        ...
