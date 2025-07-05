"""
Tests for IPMonitorBot integration points and configuration propagation.
"""

from unittest.mock import AsyncMock, Mock, patch
import pytest

from ip_monitor.bot import IPMonitorBot


class TestComponentIntegration:
    """Test suite for component integration and initialization."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_all_command_handlers_registered(
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
        """Test that all command handlers are properly registered."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify all handlers are initialized
        assert bot.ip_commands is not None
        assert bot.admin_commands is not None
        assert bot.ip_slash_cog is not None
        assert bot.admin_slash_cog is not None
        assert bot.rate_limiter is not None
        assert bot.discord_rate_limiter is not None
        assert bot.ip_service is not None
        assert bot.storage is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_configuration_propagation(
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
        """Test that configuration is properly propagated to services."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify configuration is passed to services
        mock_ip_service.assert_called_once_with(
            max_retries=mock_bot_config.max_retries,
            retry_delay=mock_bot_config.retry_delay,
            use_concurrent_checks=mock_bot_config.concurrent_api_checks,
            circuit_breaker_enabled=mock_bot_config.circuit_breaker_enabled,
            circuit_breaker_failure_threshold=mock_bot_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=mock_bot_config.circuit_breaker_recovery_timeout,
            use_custom_apis=mock_bot_config.custom_apis_enabled,
            connection_pool_size=mock_bot_config.connection_pool_size,
            connection_pool_max_keepalive=mock_bot_config.connection_pool_max_keepalive,
            connection_timeout=mock_bot_config.connection_timeout,
            read_timeout=mock_bot_config.read_timeout,
        )

        mock_storage.assert_called_once_with(
            db_file=mock_bot_config.db_file,
            history_size=mock_bot_config.ip_history_size,
        )

        mock_async_rate_limiter.assert_called_once_with(
            period=mock_bot_config.rate_limit_period,
            max_calls=mock_bot_config.max_checks_per_period,
        )

    async def test_service_dependencies(self, mock_bot_instance):
        """Test that services have proper dependencies."""
        # Verify all critical services are available
        assert mock_bot_instance.ip_service is not None
        assert mock_bot_instance.storage is not None
        assert mock_bot_instance.rate_limiter is not None
        assert mock_bot_instance.discord_rate_limiter is not None
        assert mock_bot_instance.message_queue is not None
        assert mock_bot_instance.service_health is not None

    async def test_command_handler_dependencies(self, mock_bot_instance):
        """Test that command handlers have proper dependencies."""
        # Verify command handlers are available
        assert mock_bot_instance.commands is not None
        assert mock_bot_instance.admin_commands is not None

        # Verify they can access bot services
        assert hasattr(mock_bot_instance.commands, 'handle_ip_command')
        assert hasattr(mock_bot_instance.admin_commands, 'handle_command')


class TestTaskIntegration:
    """Test suite for task integration and lifecycle."""

    async def test_task_creation_integration(self, mock_bot_instance):
        """Test task creation integrates with service health."""
        # Setup
        mock_bot_instance.service_health.get_adjusted_interval = Mock(return_value=5.0)

        # Execute
        task = mock_bot_instance._create_check_ip_task()

        # Verify
        assert task is not None
        mock_bot_instance.service_health.get_adjusted_interval.assert_called_once()

    async def test_task_lifecycle_integration(self, mock_bot_instance):
        """Test task lifecycle integrates with bot lifecycle."""
        # Setup
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.cancel = AsyncMock()
        mock_bot_instance.check_ip_task = mock_task

        # Execute cleanup
        await mock_bot_instance.cleanup()

        # Verify task is properly cleaned up
        mock_task.cancel.assert_called_once()

    async def test_no_task_cleanup_integration(self, mock_bot_instance):
        """Test cleanup works when no task exists."""
        # Setup
        mock_bot_instance.check_ip_task = None

        # Execute (should not raise exception)
        await mock_bot_instance.cleanup()

        # Verify cleanup completes successfully
        assert True  # Test passes if no exception is raised


class TestMessageFlowIntegration:
    """Test suite for message flow integration."""

    async def test_message_routing_integration(self, mock_bot_instance, mock_bot_message):
        """Test message routing between components."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.commands.handle_ip_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify routing works
        mock_bot_instance.commands.handle_ip_command.assert_called_once_with(mock_bot_message)

    async def test_admin_command_routing_integration(self, mock_bot_instance, mock_bot_admin_message):
        """Test admin command routing integration."""
        # Setup
        mock_bot_admin_message.content = "!config show"
        mock_bot_admin_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.admin_commands.handle_command = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_admin_message)

        # Verify admin routing works
        mock_bot_instance.admin_commands.handle_command.assert_called_once()

    async def test_message_queue_integration(self, mock_bot_instance):
        """Test message queue integration with bot."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(True, "192.168.1.2"))
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify message queue integration
        mock_bot_instance.message_queue.add_message.assert_called_once()


class TestConfigurationIntegration:
    """Test suite for configuration integration across components."""

    async def test_config_access_integration(self, mock_bot_instance):
        """Test configuration access across components."""
        # Verify config is accessible
        assert mock_bot_instance.config is not None
        assert hasattr(mock_bot_instance.config, 'channel_id')
        assert hasattr(mock_bot_instance.config, 'check_interval')
        assert hasattr(mock_bot_instance.config, 'max_retries')

    async def test_runtime_config_integration(self, mock_bot_instance):
        """Test runtime configuration changes integration."""
        # Setup
        original_interval = mock_bot_instance.base_check_interval
        
        # Verify base interval is set
        assert original_interval == mock_bot_instance.config.check_interval

    async def test_feature_flag_integration(self, mock_bot_instance):
        """Test feature flag integration."""
        # Verify feature flags are respected
        assert hasattr(mock_bot_instance.config, 'message_queue_enabled')
        assert hasattr(mock_bot_instance.config, 'startup_message_enabled')
        assert hasattr(mock_bot_instance.config, 'testing_mode')


class TestServiceHealthIntegration:
    """Test suite for service health integration."""

    async def test_health_monitoring_integration(self, mock_bot_instance):
        """Test service health monitoring integration."""
        # Verify service health is available
        assert mock_bot_instance.service_health is not None
        
        # Verify health methods are accessible
        assert hasattr(mock_bot_instance.service_health, 'get_status')
        assert hasattr(mock_bot_instance.service_health, 'is_degraded')

    async def test_degradation_response_integration(self, mock_bot_instance):
        """Test degradation response integration."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=True)
        mock_bot_instance.service_health.get_degradation_level = Mock(return_value=2)
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(False, "192.168.1.1"))

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify degradation is checked
        mock_bot_instance.service_health.is_degraded.assert_called()


class TestDiscordIntegration:
    """Test suite for Discord API integration."""

    async def test_discord_client_integration(self, mock_bot_instance):
        """Test Discord client integration."""
        # Verify Discord client is available
        assert mock_bot_instance.client is not None
        assert hasattr(mock_bot_instance.client, 'get_channel')
        assert hasattr(mock_bot_instance.client, 'user')

    async def test_discord_rate_limiter_integration(self, mock_bot_instance):
        """Test Discord rate limiter integration."""
        # Verify Discord rate limiter is available
        assert mock_bot_instance.discord_rate_limiter is not None

    async def test_slash_command_integration(self, mock_bot_instance):
        """Test slash command integration with Discord."""
        # Verify slash command cogs are available
        assert mock_bot_instance.ip_slash_cog is not None
        assert mock_bot_instance.admin_slash_cog is not None