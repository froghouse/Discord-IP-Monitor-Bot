"""
Tests for IPMonitorBot scheduled tasks and IP checking.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot


class TestScheduledIPCheck:
    """Test suite for scheduled IP checking functionality."""

    async def test_scheduled_ip_check_normal_operation(self, mock_bot_instance):
        """Test normal scheduled IP check operation."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            return_value=(True, "192.168.1.2")
        )
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.storage.add_ip_to_history = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once_with("192.168.1.2")
        mock_bot_instance.storage.add_ip_to_history.assert_called_once()
        mock_bot_instance.message_queue.add_message.assert_called_once()

    async def test_scheduled_ip_check_no_change(self, mock_bot_instance):
        """Test scheduled IP check when IP hasn't changed."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            return_value=(False, "192.168.1.1")
        )
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_not_called()
        mock_bot_instance.message_queue.add_message.assert_not_called()

    async def test_scheduled_ip_check_rate_limited(self, mock_bot_instance):
        """Test scheduled IP check when rate limited."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(True, 60))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify
        mock_bot_instance.ip_service.check_ip_change.assert_not_called()

    async def test_scheduled_ip_check_silent_monitoring_mode(self, mock_bot_instance):
        """Test scheduled IP check in silent monitoring mode."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.service_health.is_degraded = Mock(return_value=True)
        mock_bot_instance.service_health.get_degradation_level = Mock(
            return_value=4
        )  # SEVERE
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            return_value=(True, "192.168.1.2")
        )
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once()
        # In silent mode, no message should be sent
        mock_bot_instance.message_queue.add_message.assert_not_called()

    async def test_scheduled_ip_check_discord_exception(self, mock_bot_instance):
        """Test scheduled IP check with Discord exception."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            return_value=(True, "192.168.1.2")
        )
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock(
            side_effect=Exception("Discord API error")
        )

        # Execute (should not raise exception)
        await mock_bot_instance._scheduled_check_ip()

        # Verify
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once()

    async def test_scheduled_ip_check_unexpected_exception(self, mock_bot_instance):
        """Test scheduled IP check with unexpected exception."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        # Execute (should not raise exception)
        await mock_bot_instance._scheduled_check_ip()

        # Verify graceful error handling
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()

    async def test_cache_cleanup_task_creation(self, mock_bot_instance):
        """Test cache cleanup task is created properly."""
        # Verify cache cleanup task is initialized to None
        assert mock_bot_instance.cache_cleanup_task is None


class TestTaskCreationAndManagement:
    """Test suite for task creation and lifecycle management."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_create_check_ip_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
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
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task (test that it doesn't raise exceptions)
        task = bot._create_check_ip_task()

        # Verify service health was consulted
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_bot_config.check_interval
        )

        # Verify task is returned
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
    async def test_create_check_ip_task_detailed(
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
        """Test detailed creation of IP check task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
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


class TestTaskIntervalAdjustment:
    """Test suite for task interval adjustment based on service health."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_adjust_check_interval_for_degradation(
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
        """Test adjustment of check interval for service degradation."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 10.0
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.minutes = 5.0
        mock_task.cancel = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()
        new_task = AsyncMock()
        new_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = new_task

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify task was restarted with new interval
        mock_task.cancel.assert_called_once()
        bot._create_check_ip_task.assert_called_once()
        new_task.start.assert_called_once()
        assert bot.check_ip_task == new_task

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_adjust_check_interval_no_significant_change(
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
        """Test adjustment with no significant interval change."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 5.05  # Small change
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.minutes = 5.0
        mock_task.cancel = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify task was not restarted
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
    def test_adjust_check_interval_no_task(
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
        """Test adjustment when no task exists."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = None
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify no action was taken
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
    def test_adjust_check_interval_stopped_task(
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
        """Test adjustment when task is stopped."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 10.0
        mock_task = AsyncMock()
        mock_task.is_running.return_value = False
        mock_task.minutes = 5.0
        mock_task.cancel = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify task was not restarted when not running
        mock_task.cancel.assert_not_called()
        bot._create_check_ip_task.assert_not_called()
