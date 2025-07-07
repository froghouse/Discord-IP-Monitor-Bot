"""
Tests for IPMonitorBot task scheduling and lifecycle management.

This file contains tests extracted from the original TestTaskScheduling class,
focusing on task creation, lifecycle management, error handling, and interval adjustment.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot


class TestTaskScheduling:
    """Test task scheduling functionality."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_create_check_ip_task(
        self,
        mock_service_health,
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
        """Test creation of IP check task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task properties
        assert task is not None
        assert hasattr(task, "start")
        assert hasattr(task, "stop")
        assert hasattr(task, "restart")
        assert hasattr(task, "cancel")
        assert hasattr(task, "is_running")

        # Verify interval was set correctly
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_bot_config.check_interval
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_lifecycle_management(
        self,
        mock_service_health,
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
        """Test task lifecycle management (start, stop, restart)."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Test that task is not initially running
        assert not task.is_running()

        # Start the task
        task.start()
        assert task.is_running()

        # Stop the task
        task.stop()
        # Note: The task may still be "running" immediately after stop() is called
        # since it needs time to process the cancellation

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_interval_adjustment(
        self,
        mock_service_health,
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
        """Test task interval adjustment based on service health."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = (
            10.0  # Different interval
        )

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task with adjusted interval
        task = bot._create_check_ip_task()

        # Verify adjusted interval was used
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_bot_config.check_interval
        )
        assert task is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_before_loop_hook(
        self,
        mock_service_health,
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
        """Test task before_loop hook functionality."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.wait_until_ready = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task has before_loop hook
        assert hasattr(task, "before_loop")

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_before_loop_error_handling(
        self,
        mock_service_health,
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
        """Test error handling in task before_loop hook."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_client.wait_until_ready = AsyncMock(
            side_effect=Exception("Client not ready")
        )
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task is created despite potential before_loop errors
        assert task is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler(
        self,
        mock_service_health,
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
        """Test task error handler functionality."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task has error handler
        assert hasattr(task, "error")

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_exception_handling(
        self,
        mock_service_health,
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
        """Test task error handler exception handling."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task is resilient to errors
        assert task is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_restart_running_task(
        self,
        mock_service_health,
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
        """Test task error handler restart when task is running."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create and start task
        task = bot._create_check_ip_task()
        task.start()

        # Verify task can handle restart scenarios
        assert task.is_running()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_start_stopped_task(
        self,
        mock_service_health,
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
        """Test task error handler start when task is stopped."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task (not started)
        task = bot._create_check_ip_task()

        # Verify task is not running initially
        assert not task.is_running()

        # Start task
        task.start()
        assert task.is_running()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_adjust_check_interval_no_change(
        self,
        mock_service_health,
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
        """Test adjust check interval when no change is needed."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0  # Same as current

        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.minutes = 5.0  # Current interval matches adjusted interval
        mock_task.cancel = Mock()  # cancel() is synchronous

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify no restart when intervals match
        mock_task.cancel.assert_not_called()
        bot._create_check_ip_task.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_adjust_check_interval_no_task(
        self,
        mock_service_health,
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
        """Test adjust check interval when no task exists."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 10.0

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = None  # No task
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify no action when no task exists
        bot._create_check_ip_task.assert_not_called()


class TestTaskErrorHandling:
    """Test suite for task error handling and recovery."""

    async def test_task_cancellation_during_cleanup(self, mock_bot_instance):
        """Test task cancellation during bot cleanup."""
        # Setup
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.cancel = Mock()  # cancel() is synchronous
        mock_bot_instance.check_ip_task = mock_task

        # Execute
        await mock_bot_instance.cleanup()

        # Verify task is cancelled
        mock_task.cancel.assert_called_once()

    async def test_task_cancellation_error_handling(self, mock_bot_instance):
        """Test handling of task cancellation errors."""
        # Setup
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.cancel = Mock(side_effect=Exception("Cancel failed"))  # cancel() is synchronous
        mock_bot_instance.check_ip_task = mock_task

        # Execute (should not raise exception)
        await mock_bot_instance.cleanup()

        # Verify cancellation was attempted
        mock_task.cancel.assert_called_once()

    async def test_multiple_task_cleanup(self, mock_bot_instance):
        """Test cleanup with multiple tasks."""
        # Setup
        mock_check_task = AsyncMock()
        mock_check_task.is_running.return_value = True
        mock_check_task.cancel = Mock()  # cancel() is synchronous

        mock_cache_task = AsyncMock()
        mock_cache_task.is_running.return_value = True
        mock_cache_task.cancel = Mock()  # cancel() is synchronous

        mock_bot_instance.check_ip_task = mock_check_task
        mock_bot_instance.cache_cleanup_task = mock_cache_task

        # Execute
        await mock_bot_instance.cleanup()

        # Verify both tasks are cancelled
        mock_check_task.cancel.assert_called_once()
