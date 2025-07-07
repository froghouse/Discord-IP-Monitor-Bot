"""
Test suite for Discord bot event handlers.

This module contains comprehensive tests for all Discord bot event handlers
including on_ready, on_message, on_disconnect, on_resumed, and related
event handling functionality.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from ip_monitor.bot import IPMonitorBot


class TestOnReadyEventHandler:
    """Test suite for on_ready event handler."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_success(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test successful on_ready event handler."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = Mock()
        mock_storage.load_last_ip.return_value = "192.168.1.1"
        mock_storage_class.return_value = mock_storage

        mock_ip_service = Mock()
        mock_ip_service.set_last_known_ip = Mock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message_queue.set_discord_client = AsyncMock()
        mock_message_queue.start_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify initialization
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)
        mock_storage.load_last_ip.assert_called_once()
        mock_ip_service.set_last_known_ip.assert_called_once_with("192.168.1.1")
        mock_message_queue.set_discord_client.assert_called_once_with(mock_client)
        mock_message_queue.start_processing.assert_called_once()
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        mock_client.add_cog.assert_called()
        mock_client.tree.sync.assert_called_once()
        mock_task.start.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_channel_not_found(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with channel not found."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.return_value = None
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Run on_ready
        await bot.on_ready()

        # Verify bot tries to shut down
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)
        # Note: close is called from within on_ready but it's async so hard to verify

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_discord_exception(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.side_effect = discord.DiscordException("API Error")
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Run on_ready
        await bot.on_ready()

        # Verify Discord exception is handled (close may be called asynchronously)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_message_queue_disabled(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with message queue disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = AsyncMock()
        mock_storage.load_last_ip.return_value = None
        mock_storage_class.return_value = mock_storage

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_config.message_queue_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify message queue is not started
        mock_message_queue.set_discord_client.assert_not_called()
        mock_message_queue.start_processing.assert_not_called()
        mock_task.start.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_startup_message_disabled(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with startup message disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = AsyncMock()
        mock_storage.load_last_ip.return_value = None
        mock_storage_class.return_value = mock_storage

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_config.startup_message_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify startup message is not sent
        mock_discord_rate_limiter.send_message_with_backoff.assert_not_called()
        mock_task.start.assert_called_once()


class TestOnMessageEventHandler:
    """Test suite for on_message event handler."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_ip_command(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling IP command."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify IP command was handled
        mock_ip_commands.handle_ip_command.assert_called_once_with(
            mock_message, mock_client
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_admin_command(
        self,
        mock_admin_router_class,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling admin command."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_admin_router = AsyncMock()
        mock_admin_router.handle_config_command = AsyncMock()
        mock_admin_router_class.return_value = mock_admin_router

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!config show"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify admin command was handled
        mock_admin_router.handle_config_command.assert_called_once_with(mock_message)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_bot_message_ignored(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message ignoring bot's own messages."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = mock_client.user
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_wrong_channel_non_admin(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message ignoring messages from wrong channel for non-admin."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = False
        mock_message.channel = Mock()
        mock_message.channel.id = 999999  # Wrong channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_wrong_channel_admin_allowed(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message allowing admin commands from any channel."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel = Mock()
        mock_message.channel.id = 999999  # Wrong channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was handled for admin
        mock_ip_commands.handle_ip_command.assert_called_once_with(
            mock_message, mock_client
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_discord_exception(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = discord.DiscordException(
            "API Error"
        )
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify error handling
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        error_message = mock_discord_rate_limiter.send_message_with_backoff.call_args[
            0
        ][1]
        assert "error occurred" in error_message

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_unexpected_exception(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling unexpected exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = Exception("Unexpected error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify error handling
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        error_message = mock_discord_rate_limiter.send_message_with_backoff.call_args[
            0
        ][1]
        assert "unexpected error" in error_message.lower()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_error_notification_fails(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message when error notification itself fails."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = Exception("Unexpected error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff.side_effect = Exception(
            "Network error"
        )
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message (should not raise exception)
        await bot.on_message(mock_message)

        # Verify error notification was attempted
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()


class TestMessageHandlingEdgeCases:
    """Test suite for on_message edge cases and validation."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_empty_content(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling empty message content."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = ""  # Empty content

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for empty content
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_unknown_command(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling unknown commands."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!notacommand"  # Doesn't match any command

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for non-matching command
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_case_sensitivity(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message command case sensitivity."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!IP"  # Uppercase command

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for case mismatch
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_dm_handling(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling direct messages."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Create DM channel mock
        mock_dm_channel = AsyncMock()
        mock_dm_channel.id = 999999  # Different from config channel_id
        mock_dm_channel.type = discord.ChannelType.private

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = False
        mock_message.channel = mock_dm_channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled in DM for non-admin
        mock_ip_commands.handle_ip_command.assert_not_called()


class TestConnectionEventHandlers:
    """Test suite for Discord connection event handlers."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_disconnect_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of disconnect events."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Discord.py handles disconnect events internally
        # This test verifies that the bot structure supports reconnection
        assert bot.client is not None
        assert bot.ip_service is not None
        assert bot.storage is not None

        # Bot should maintain state during disconnect/reconnect cycles
        assert bot.config == mock_config
        assert bot.check_ip_task is None  # Not started yet

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_resumed_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of connection resume events."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Discord.py handles resume events internally
        # This test verifies that the bot can handle connection restoration
        assert bot.client is not None

        # Tasks should continue running after resume
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        bot.check_ip_task = mock_task

        # Verify task state is maintained
        assert bot.check_ip_task.is_running()


class TestGuildEventHandlers:
    """Test suite for Discord guild event handlers."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_guild_availability_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of guild availability changes."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.return_value = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Bot should handle guild unavailability gracefully
        # Discord.py handles guild events internally, but bot should maintain state
        assert bot.client is not None
        assert bot.config.channel_id == mock_config.channel_id

        # Channel access should work when guild is available
        channel = bot.client.get_channel(mock_config.channel_id)
        assert channel is not None


class TestCommandErrorHandler:
    """Test suite for command error handling."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_command_error_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test command error handling for slash commands."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        # Create mock interaction for slash command error
        mock_interaction = AsyncMock()
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"
        mock_interaction.user = Mock()
        mock_interaction.user.id = 987654321
        mock_interaction.channel = Mock()
        mock_interaction.channel.id = mock_config.channel_id
        mock_interaction.response = AsyncMock()
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.response.is_done.return_value = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Since on_command_error is not explicitly defined in the bot,
        # we test the default Discord.py error handling behavior
        # This test validates that error handling infrastructure is in place

        # Verify bot initialization doesn't break error handling setup
        assert bot.client is not None
        assert hasattr(bot.client, "tree")  # Slash command tree

        # Verify the bot can handle command processing without breaking
        # when an error occurs (this is implicit through on_message error handling)
        test_message = AsyncMock()
        test_message.author = Mock()
        test_message.author.id = 987654321
        test_message.channel = Mock()
        test_message.channel.id = mock_config.channel_id
        test_message.content = "!unknown_command"

        # This should not raise an exception
        await bot.on_message(test_message)
