"""
Tests for IPMonitorBot error handling and resilience.
"""

from unittest.mock import AsyncMock, Mock, patch
import pytest

from ip_monitor.bot import IPMonitorBot


class TestErrorHandling:
    """Test suite for error handling and resilience features."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_task_silent_monitoring(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test scheduled task in silent monitoring mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.side_effect = (
            lambda x: x == "silent_monitoring"
        )
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage.save_current_ip = AsyncMock()
        mock_storage_class.return_value = mock_storage

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Create task (test that it works with service health)
        task = bot._create_check_ip_task()

        # Verify task creation uses service health
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_bot_config.check_interval
        )

        # Verify task is created
        assert task is not None

    async def test_message_error_recovery(self, mock_bot_instance, mock_bot_message):
        """Test error recovery in message handling."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.ip_commands.handle_ip_command = AsyncMock(
            side_effect=Exception("Command failed")
        )
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff = AsyncMock()

        # Execute
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify error is handled gracefully
        mock_bot_instance.ip_commands.handle_ip_command.assert_called_once()
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff.assert_called()

    async def test_cascading_error_handling(self, mock_bot_instance, mock_bot_message):
        """Test handling of cascading errors."""
        # Setup
        mock_bot_message.content = "!ip"
        mock_bot_message.channel.id = mock_bot_instance.config.channel_id
        mock_bot_instance.ip_commands.handle_ip_command = AsyncMock(
            side_effect=Exception("Primary error")
        )
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff = AsyncMock(
            side_effect=Exception("Secondary error")
        )

        # Execute (should not raise exception)
        await mock_bot_instance.on_message(mock_bot_message)

        # Verify both errors are handled
        mock_bot_instance.ip_commands.handle_ip_command.assert_called_once()
        mock_bot_instance.discord_rate_limiter.send_message_with_backoff.assert_called_once()

    async def test_service_degradation_handling(self, mock_bot_instance):
        """Test handling of service degradation scenarios."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=True)
        mock_bot_instance.service_health.get_degradation_level = Mock(return_value=3)
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(False, "192.168.1.1"))

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify degraded operation
        mock_bot_instance.service_health.is_degraded.assert_called()
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()

    async def test_rate_limit_recovery(self, mock_bot_instance):
        """Test recovery from rate limiting."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(True, 30))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify rate limiting is respected
        mock_bot_instance.ip_service.check_ip_change.assert_not_called()

    async def test_exception_during_cleanup(self, mock_bot_instance):
        """Test handling of exceptions during cleanup."""
        # Setup
        mock_bot_instance.check_ip_task = AsyncMock()
        mock_bot_instance.check_ip_task.is_running.return_value = True
        mock_bot_instance.check_ip_task.cancel.side_effect = Exception("Cancel failed")
        mock_bot_instance.client.close = AsyncMock()

        # Execute (should not raise exception)
        await mock_bot_instance.cleanup()

        # Verify cleanup continues despite error
        mock_bot_instance.check_ip_task.cancel.assert_called_once()
        mock_bot_instance.client.close.assert_called_once()


class TestCircuitBreakerIntegration:
    """Test suite for circuit breaker integration."""

    async def test_circuit_breaker_open_state(self, mock_bot_instance):
        """Test bot behavior when circuit breaker is open."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(
            side_effect=Exception("Circuit breaker open")
        )

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify circuit breaker prevents cascading failures
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()

    async def test_circuit_breaker_recovery(self, mock_bot_instance):
        """Test circuit breaker recovery behavior."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(False, "192.168.1.1"))

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify normal operation after recovery
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()


class TestServiceHealthIntegration:
    """Test suite for service health monitoring integration."""

    async def test_health_monitoring_during_operation(self, mock_bot_instance):
        """Test health monitoring during normal operation."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=False)
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(True, "192.168.1.2"))
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify health is checked
        mock_bot_instance.service_health.is_degraded.assert_called()
        mock_bot_instance.message_queue.add_message.assert_called()

    async def test_degraded_service_operation(self, mock_bot_instance):
        """Test operation under degraded service conditions."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=True)
        mock_bot_instance.service_health.get_degradation_level = Mock(return_value=4)  # SEVERE
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(True, "192.168.1.2"))
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify degraded operation (no Discord notification)
        mock_bot_instance.storage.save_current_ip.assert_called()
        mock_bot_instance.message_queue.add_message.assert_not_called()


class TestMessageQueueErrorHandling:
    """Test suite for message queue error handling."""

    async def test_message_queue_failure_handling(self, mock_bot_instance):
        """Test handling of message queue failures."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(True, "192.168.1.2"))
        mock_bot_instance.storage.save_current_ip = Mock()
        mock_bot_instance.message_queue.add_message = AsyncMock(
            side_effect=Exception("Queue full")
        )

        # Execute (should not raise exception)
        await mock_bot_instance._scheduled_check_ip()

        # Verify operation continues despite queue failure
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once()

    async def test_message_queue_disabled_fallback(self, mock_bot_instance):
        """Test fallback when message queue is disabled."""
        # Setup
        mock_bot_instance.config.message_queue_enabled = False
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.check_ip_change = AsyncMock(return_value=(True, "192.168.1.2"))
        mock_bot_instance.storage.save_current_ip = Mock()

        # Execute
        await mock_bot_instance._scheduled_check_ip()

        # Verify operation works without message queue
        mock_bot_instance.ip_service.check_ip_change.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once()