"""
Tests for IPMonitorBot Discord event handlers.
"""

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
        mock_bot_config,
    ):
        """Test successful on_ready event handler."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
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
        bot = IPMonitorBot(mock_bot_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify initialization
        mock_client.get_channel.assert_called_once_with(mock_bot_config.channel_id)
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
        mock_bot_config,
    ):
        """Test on_ready with channel not found."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.return_value = None
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Run on_ready
        await bot.on_ready()

        # Verify bot tries to shut down
        mock_client.get_channel.assert_called_once_with(mock_bot_config.channel_id)

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
        mock_bot_config,
    ):
        """Test on_ready with Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.side_effect = discord.DiscordException("API Error")
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Run on_ready
        await bot.on_ready()

        # Verify Discord exception is handled
        mock_client.get_channel.assert_called_once_with(mock_bot_config.channel_id)

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
        mock_bot_config,
    ):
        """Test on_ready with message queue disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
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

        mock_bot_config.message_queue_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
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
        mock_bot_config,
    ):
        """Test on_ready with startup message disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
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

        mock_bot_config.startup_message_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
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

    async def test_on_message_ip_command(self, mock_bot_instance, mock_bot_message):
        """Test IP command handling via on_message."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify
        mock_bot_instance.commands.handle_ip_command.assert_called_once_with(
            mock_bot_message, mock_bot_instance.client
        )

    async def test_on_message_admin_command(
        self, mock_bot_instance, mock_bot_admin_message
    ):
        """Test admin command routing via on_message."""
        # Setup
        mock_bot_admin_message.content = "!config show"
        mock_bot_admin_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.admin_commands.handle_config_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_admin_message)

        # Verify
        mock_bot_instance.admin_commands.handle_config_command.assert_called_once_with(
            mock_bot_admin_message
        )

    async def test_on_message_bot_message_ignored(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test that bot's own messages are ignored."""
        # Setup
        mock_bot_message.author = mock_bot_instance.client.user
        mock_bot_message.content = "!ip"
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify
        mock_bot_instance.commands.handle_ip_command.assert_not_called()

    async def test_on_message_wrong_channel_non_admin(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test non-admin users restricted to correct channel."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = 99999  # Wrong channel
        mock_bot_message.author.guild_permissions.administrator = False
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify
        mock_bot_instance.commands.handle_ip_command.assert_not_called()

    async def test_on_message_wrong_channel_admin_allowed(
        self, mock_bot_instance, mock_bot_admin_message
    ):
        """Test admin users can use commands in any channel."""
        # Setup
        mock_bot_admin_message.content = "!config show"
        mock_bot_admin_message.channel.id = 99999  # Wrong channel
        mock_bot_admin_message.author.guild_permissions.administrator = True
        mock_bot_instance.admin_commands.handle_config_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_admin_message)

        # Verify
        mock_bot_instance.admin_commands.handle_config_command.assert_called_once()

    async def test_on_message_discord_exception(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test Discord exception handling in on_message."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock(
            side_effect=discord.DiscordException("API Error")
        )
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify error handling
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff.assert_called()

    async def test_on_message_unexpected_exception(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test unexpected exception handling in on_message."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock(
            side_effect=Exception("Unexpected error")
        )
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify error handling
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff.assert_called()

    async def test_on_message_error_notification_fails(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test when error notification itself fails."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock(
            side_effect=Exception("Command error")
        )
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff = AsyncMock(
            side_effect=Exception("Notification error")
        )

        # Execute (should not raise exception)
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify both errors are handled gracefully
        mock_bot_instance.commands.handle_ip_command.assert_called_once()
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff.assert_called_once()


class TestMessageHandlingEdgeCases:
    """Test suite for message handling edge cases."""

    async def test_on_message_empty_content(self, mock_bot_instance, mock_bot_message):
        """Test handling of empty message content."""
        # Setup
        mock_bot_message.content = ""
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify no command is executed
        mock_bot_instance.commands.handle_ip_command.assert_not_called()

    async def test_on_message_unknown_command(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test handling of unknown commands."""
        # Setup
        mock_bot_message.content = "!unknown"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify no command is executed
        mock_bot_instance.commands.handle_ip_command.assert_not_called()

    async def test_on_message_case_sensitivity(
        self, mock_bot_instance, mock_bot_message
    ):
        """Test command case sensitivity."""
        # Setup
        mock_bot_message.content = "!IP"  # Uppercase
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify command is NOT executed (case sensitive)
        mock_bot_instance.commands.handle_ip_command.assert_not_called()

    async def test_on_message_dm_handling(self, mock_bot_instance, mock_bot_message):
        """Test direct message handling."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.guild = None  # DM has no guild
        mock_bot_message.channel.id = 99999  # Different from config.channel_id
        mock_bot_message.author.guild_permissions.administrator = (
            False  # Non-admin in DM
        )
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify DM is ignored
        mock_bot_instance.commands.handle_ip_command.assert_not_called()


class TestConnectionEventHandlers:
    """Test suite for Discord connection event handlers."""

    # Note: on_disconnect handler is not implemented in the current bot

    # Note: on_resumed handler is not implemented in the current bot


class TestGuildEventHandlers:
    """Test suite for guild-related event handlers."""

    # Note: Guild availability handlers are not implemented in the current bot


class TestCommandErrorHandler:
    """Test suite for command error handling."""

    # Note: Command error handlers are not implemented in the current bot
