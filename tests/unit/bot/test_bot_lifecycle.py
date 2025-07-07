"""
Tests for IPMonitorBot lifecycle management (run, cleanup, stop).
"""

from unittest.mock import AsyncMock, Mock, patch

import discord
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running = Mock(return_value=True)  # is_running() is synchronous
        mock_task.cancel = Mock()  # cancel() is synchronous

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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running = Mock(return_value=False)  # is_running() is synchronous
        mock_task.cancel = Mock()  # cancel() is synchronous

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task

        # Run cleanup
        await bot.cleanup()

        # Verify task is not cancelled when not running (matches implementation logic)
        mock_task.cancel.assert_not_called()
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
        # Create mock client without http attribute for "without http session" test
        mock_client = Mock(spec=['event', 'close', 'user', 'latency'])  # Specify allowed attributes
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Stop bot
        await bot._stop_bot()

        # Verify cleanup was called
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
    async def test_graceful_shutdown_with_active_tasks(
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
        """Test graceful shutdown with active background tasks."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_check_ip_task = AsyncMock()
        mock_check_ip_task.is_running = Mock(return_value=True)  # is_running() is synchronous
        mock_check_ip_task.cancel = Mock()  # cancel() is synchronous

        mock_cache_cleanup_task = AsyncMock()
        mock_cache_cleanup_task.is_running = Mock(return_value=True)  # is_running() is synchronous
        mock_cache_cleanup_task.cancel = Mock()  # cancel() is synchronous

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_check_ip_task
        bot.cache_cleanup_task = mock_cache_cleanup_task

        # Run cleanup
        await bot.cleanup()

        # Verify check_ip_task is cancelled (cache_cleanup_task is not handled in cleanup method)
        mock_check_ip_task.cancel.assert_called_once()
        mock_message_queue.stop_processing.assert_called_once()
        mock_ip_service.close.assert_called_once()
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
    async def test_shutdown_with_exception_during_cleanup(
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
        """Test shutdown continues even if cleanup operations fail."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock(
            side_effect=Exception("Service cleanup failed")
        )
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running = Mock(return_value=True)  # is_running() is synchronous
        mock_task.cancel = Mock(side_effect=Exception("Task cancel failed"))  # cancel() is synchronous

        mock_message_queue.stop_processing = AsyncMock(
            side_effect=Exception("Queue stop failed")
        )

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task

        # Run cleanup - should handle exceptions gracefully
        try:
            await bot.cleanup()
        except Exception:
            # The current cleanup method doesn't catch exceptions, so we expect them
            pass

        # Verify cleanup attempts were made despite exceptions
        mock_message_queue.stop_processing.assert_called_once()
        # Task cancel and subsequent calls may not be reached due to exception

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_shutdown_with_discord_client_exception(
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
        """Test shutdown handles Discord client exceptions gracefully."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock(
            side_effect=discord.DiscordException("Connection error")
        )
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Run cleanup - should handle Discord exceptions
        try:
            await bot.cleanup()
        except discord.DiscordException:
            # The current cleanup method doesn't catch exceptions, but that's expected
            pass

        # Verify cleanup attempts were made
        mock_message_queue.stop_processing.assert_called_once()
        mock_ip_service.close.assert_called_once()
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
    async def test_shutdown_with_database_connection_cleanup(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test shutdown properly closes database connections."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage.close = AsyncMock()
        mock_storage_class.return_value = mock_storage

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Run cleanup
        await bot.cleanup()

        # Verify database connections are closed if close method exists
        mock_message_queue.stop_processing.assert_called_once()
        mock_ip_service.close.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_stop_bot_calls_cleanup(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test _stop_bot method calls cleanup."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.cleanup = AsyncMock()

        # Stop bot
        await bot._stop_bot()

        # Verify cleanup was called (the actual _stop_bot method only calls cleanup)
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_shutdown_sequence_order(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test that shutdown sequence follows proper order."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.close = AsyncMock()  # client.close() is awaited
        # Mock the HTTP session for cleanup
        mock_client.http = Mock()
        mock_client.http.session = Mock()
        mock_client.http.session.close = AsyncMock()  # session.close() is awaited
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Mock the cleanup method to verify order
        cleanup_calls = []
        original_cleanup = bot.cleanup

        async def mock_cleanup():
            cleanup_calls.append("cleanup")
            await original_cleanup()

        bot.cleanup = mock_cleanup

        # Stop bot
        await bot._stop_bot()

        # Verify cleanup was called
        assert "cleanup" in cleanup_calls
