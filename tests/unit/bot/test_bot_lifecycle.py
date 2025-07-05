"""
Tests for IPMonitorBot lifecycle management (run, cleanup, stop).
"""

import discord
from unittest.mock import AsyncMock, Mock, patch
import pytest

from ip_monitor.bot import IPMonitorBot


class TestBotLifecycle:
    """Test suite for IPMonitorBot lifecycle methods."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_normal_mode(
        self,
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
        """Test bot run method in normal mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_bot_config.testing_mode = False

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify normal operation
        mock_client.start.assert_called_once_with(mock_bot_config.discord_token)
        assert result == 0
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_testing_mode_success(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test bot run method in testing mode with successful IP check."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service
        mock_bot_config.testing_mode = True

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify testing mode operation
        mock_ip_service.get_public_ip.assert_called_once()
        mock_client.start.assert_not_called()
        assert result == 0
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_testing_mode_failure(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test bot run method in testing mode with failed IP check."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = None
        mock_ip_service_class.return_value = mock_ip_service
        mock_bot_config.testing_mode = True

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify testing mode failure
        mock_ip_service.get_public_ip.assert_called_once()
        mock_client.start.assert_not_called()
        assert result == 1
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_login_failure(
        self,
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
        """Test bot run method with Discord login failure."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.start.side_effect = discord.LoginFailure("Invalid token")
        mock_bot_class.return_value = mock_client
        mock_bot_config.testing_mode = False

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify login failure handling
        mock_client.start.assert_called_once_with(mock_bot_config.discord_token)
        assert result == 1
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_all_resources(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test cleanup method properly closes all resources."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.http = Mock()
        mock_client.http.session = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.cancel = AsyncMock()

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task

        # Run cleanup
        await bot.cleanup()

        # Verify cleanup operations
        mock_message_queue.stop_processing.assert_called_once()
        mock_task.cancel.assert_called_once()
        mock_ip_service.close.assert_called_once()
        mock_client.http.session.close.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_with_stopped_task(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test cleanup method with already stopped task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.http = Mock()
        mock_client.http.session = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running.return_value = False
        mock_task.cancel = AsyncMock()

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task

        # Run cleanup
        await bot.cleanup()

        # Verify task is still cancelled even if not running (cleanup is safer)
        mock_task.cancel.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_without_http_session(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test cleanup method without HTTP session."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Run cleanup
        await bot.cleanup()

        # Verify cleanup completes without HTTP session
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_stop_bot(
        self,
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
        """Test stop bot method."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Stop bot
        await bot._stop_bot()

        # Verify cleanup was called
        bot.cleanup.assert_called_once()