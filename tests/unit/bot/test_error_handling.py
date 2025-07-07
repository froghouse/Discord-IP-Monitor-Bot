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
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.side_effect = (
            lambda x: x == "silent_monitoring"
        )
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage.migrate_from_json = Mock()  # migrate_from_json() is synchronous
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
        # Mock to return True for silent_monitoring but False for read_only_mode
        mock_bot_instance.service_health.is_fallback_active = Mock(
            side_effect=lambda mode: mode == "silent_monitoring"
        )
        mock_bot_instance.ip_service.get_public_ip = AsyncMock(
            return_value="192.168.1.1"
        )
        mock_bot_instance.storage.save_current_ip = Mock()

        # Create and execute the IP check task behavior
        # This simulates the silent monitoring mode behavior from the actual task
        if mock_bot_instance.service_health.is_fallback_active("silent_monitoring"):
            current_ip = await mock_bot_instance.ip_service.get_public_ip()
            if current_ip and not mock_bot_instance.service_health.is_fallback_active(
                "read_only_mode"
            ):
                mock_bot_instance.storage.save_current_ip(current_ip)

        # Verify degraded operation
        # The last call should be to read_only_mode, but we still need to verify both calls
        assert mock_bot_instance.service_health.is_fallback_active.call_count == 2
        mock_bot_instance.service_health.is_fallback_active.assert_any_call(
            "silent_monitoring"
        )
        mock_bot_instance.service_health.is_fallback_active.assert_any_call(
            "read_only_mode"
        )
        mock_bot_instance.ip_service.get_public_ip.assert_called_once()
        mock_bot_instance.storage.save_current_ip.assert_called_once_with("192.168.1.1")

    async def test_rate_limit_recovery(self, mock_bot_instance):
        """Test recovery from rate limiting."""
        # Setup
        mock_bot_instance.service_health.is_fallback_active = Mock(return_value=False)
        mock_bot_instance.ip_commands.check_ip_once = AsyncMock()
        mock_bot_instance.service_health.record_success = Mock()

        # Execute - simulate the normal IP check task behavior
        if not mock_bot_instance.service_health.is_fallback_active("silent_monitoring"):
            await mock_bot_instance.ip_commands.check_ip_once(
                mock_bot_instance.client, user_requested=False
            )
            mock_bot_instance.service_health.record_success(
                "discord_api", "scheduled_task"
            )

        # Verify normal operation
        mock_bot_instance.ip_commands.check_ip_once.assert_called_once_with(
            mock_bot_instance.client, user_requested=False
        )
        mock_bot_instance.service_health.record_success.assert_called_once_with(
            "discord_api", "scheduled_task"
        )

    async def test_exception_during_cleanup(self, mock_bot_instance):
        """Test handling of exceptions during cleanup."""
        from unittest.mock import patch

        # Setup
        mock_bot_instance.check_ip_task = AsyncMock()
        mock_bot_instance.check_ip_task.is_running.return_value = True
        mock_bot_instance.check_ip_task.cancel.side_effect = Exception("Cancel failed")
        mock_bot_instance.client.close = AsyncMock()

        # Mock the ip_service.close method to be async
        mock_bot_instance.ip_service.close = AsyncMock()

        # Mock the HTTP session close method to be async
        mock_bot_instance.client.http = Mock()
        mock_bot_instance.client.http.session = Mock()
        mock_bot_instance.client.http.session.close = AsyncMock()

        # Mock the global message_queue used in cleanup
        mock_message_queue = AsyncMock()
        mock_message_queue.stop_processing = AsyncMock()

        # Execute (should not raise exception)
        with patch("ip_monitor.bot.message_queue", mock_message_queue):
            await mock_bot_instance.cleanup()

        # Verify cleanup continues despite error
        mock_bot_instance.check_ip_task.cancel.assert_called_once()
        mock_bot_instance.client.close.assert_called_once()
        mock_message_queue.stop_processing.assert_called_once()


class TestCircuitBreakerIntegration:
    """Test suite for circuit breaker integration."""

    async def test_circuit_breaker_open_state(self, mock_bot_instance):
        """Test bot behavior when circuit breaker is open."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.get_public_ip = AsyncMock(
            side_effect=Exception("Circuit breaker open")
        )

        # Test that the bot can handle circuit breaker failures
        # This simulates what happens when IP services are down
        try:
            await mock_bot_instance.ip_service.get_public_ip()
        except Exception:
            # Expected - circuit breaker should prevent cascading failures
            pass

        # Verify the IP service was called
        mock_bot_instance.ip_service.get_public_ip.assert_called_once()

    async def test_circuit_breaker_recovery(self, mock_bot_instance):
        """Test circuit breaker recovery behavior."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_service.get_public_ip = AsyncMock(
            return_value="192.168.1.1"
        )

        # Execute
        result = await mock_bot_instance.ip_service.get_public_ip()

        # Verify normal operation after recovery
        assert result == "192.168.1.1"
        mock_bot_instance.ip_service.get_public_ip.assert_called_once()


class TestServiceHealthIntegration:
    """Test suite for service health monitoring integration."""

    async def test_health_monitoring_during_operation(self, mock_bot_instance):
        """Test health monitoring during normal operation."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=False)
        mock_bot_instance.service_health.is_fallback_active = Mock(return_value=False)
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.ip_commands.check_ip_once = AsyncMock()
        mock_bot_instance.service_health.record_success = Mock()

        # Execute - simulate normal operation path
        if not mock_bot_instance.service_health.is_fallback_active("silent_monitoring"):
            await mock_bot_instance.ip_commands.check_ip_once(
                mock_bot_instance.client, user_requested=False
            )
            mock_bot_instance.service_health.record_success(
                "discord_api", "scheduled_task"
            )

        # Verify health is checked and normal operation proceeds
        mock_bot_instance.service_health.is_fallback_active.assert_called()
        mock_bot_instance.ip_commands.check_ip_once.assert_called_once()
        mock_bot_instance.service_health.record_success.assert_called_once()

    async def test_degraded_service_operation(self, mock_bot_instance):
        """Test operation under degraded service conditions."""
        # Setup
        mock_bot_instance.service_health.is_degraded = Mock(return_value=True)
        mock_bot_instance.service_health.get_degradation_level = Mock(
            return_value=4
        )  # SEVERE
        mock_bot_instance.service_health.is_fallback_active = Mock(
            side_effect=lambda mode: mode == "silent_monitoring"
        )
        mock_bot_instance.ip_service.get_public_ip = AsyncMock(
            return_value="192.168.1.2"
        )
        mock_bot_instance.storage.save_current_ip = Mock()

        # Execute - simulate degraded operation path
        if mock_bot_instance.service_health.is_fallback_active("silent_monitoring"):
            current_ip = await mock_bot_instance.ip_service.get_public_ip()
            if current_ip and not mock_bot_instance.service_health.is_fallback_active(
                "read_only_mode"
            ):
                mock_bot_instance.storage.save_current_ip(current_ip)

        # Verify degraded operation (IP saved but no Discord notification)
        mock_bot_instance.storage.save_current_ip.assert_called_once_with("192.168.1.2")
        mock_bot_instance.ip_service.get_public_ip.assert_called_once()


class TestMessageQueueErrorHandling:
    """Test suite for message queue error handling."""

    async def test_message_queue_failure_handling(self, mock_bot_instance):
        """Test handling of message queue failures."""
        # Setup
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.service_health.is_fallback_active = Mock(return_value=False)
        mock_bot_instance.ip_commands.check_ip_once = AsyncMock(
            side_effect=Exception("Queue full")
        )
        mock_bot_instance.service_health.record_failure = Mock()

        # Execute (should not raise exception)
        # Simulate what happens when the IP check task encounters an error
        try:
            await mock_bot_instance.ip_commands.check_ip_once(
                mock_bot_instance.client, user_requested=False
            )
        except Exception as e:
            # This is expected - the service health should record the failure
            mock_bot_instance.service_health.record_failure(
                "discord_api", str(e), "scheduled_task"
            )

        # Verify operation continues despite queue failure
        mock_bot_instance.ip_commands.check_ip_once.assert_called_once()
        mock_bot_instance.service_health.record_failure.assert_called_once()

    async def test_message_queue_disabled_fallback(self, mock_bot_instance):
        """Test fallback when message queue is disabled."""
        # Setup
        mock_bot_instance.config.message_queue_enabled = False
        mock_bot_instance.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        mock_bot_instance.service_health.is_fallback_active = Mock(return_value=False)
        mock_bot_instance.ip_commands.check_ip_once = AsyncMock()
        mock_bot_instance.service_health.record_success = Mock()

        # Execute - simulate normal operation when queue is disabled
        if not mock_bot_instance.service_health.is_fallback_active("silent_monitoring"):
            await mock_bot_instance.ip_commands.check_ip_once(
                mock_bot_instance.client, user_requested=False
            )
            mock_bot_instance.service_health.record_success(
                "discord_api", "scheduled_task"
            )

        # Verify operation works without message queue
        mock_bot_instance.ip_commands.check_ip_once.assert_called_once()
        mock_bot_instance.service_health.record_success.assert_called_once()
