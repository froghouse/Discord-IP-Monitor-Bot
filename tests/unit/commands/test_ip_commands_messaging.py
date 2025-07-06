"""
Tests for IPCommands messaging functionality - rate limiting and message queue integration.

This module provides test coverage for the messaging aspects of the IP monitoring bot's
user commands, including rate limiting integration, message queue handling, and retry logic.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.commands.ip_commands import IPCommands
from ip_monitor.utils.message_queue import MessagePriority


class TestRateLimitingIntegration:
    """Test suite for rate limiting behavior in user commands."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_ip_command_respects_rate_limit(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test that IP command respects rate limiting."""
        # Setup rate limit
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(True, 300))

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )

            # Verify rate limit check and message
            assert result is True
            ip_commands.rate_limiter.is_limited.assert_called_once()
            mock_send.assert_called_once()

            # Verify IP service was not called due to rate limit
            ip_commands.ip_service.get_public_ip.assert_not_called()

    async def test_status_command_rate_limit_display(self, ip_commands, mock_message):
        """Test that status command displays current rate limit information."""
        # Setup rate limit state
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(True, 150))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=2)
        ip_commands.rate_limiter.max_calls = 10

        # Setup other required mocks
        ip_commands.ip_service.max_retries = 3
        ip_commands.ip_service.use_concurrent_checks = True
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            return_value={"enabled": False}
        )
        ip_commands.ip_service.get_cache_info = Mock(return_value={"enabled": False})
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
        ):
            mock_health.get_system_health.return_value = {
                "degradation_level": "normal",
                "services": {},
                "system_capabilities": {"active_fallbacks": []},
            }

            mock_queue.get_queue_status.return_value = {
                "queue_size": 0,
                "max_queue_size": 1000,
                "ready_to_process": 0,
                "scheduled_for_later": 0,
                "statistics": {"total_delivered": 100, "total_failed": 1},
            }

            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_status_command(mock_message)

            # Verify rate limit info in status
            assert result is True
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "Limited (wait 150 seconds)" in message_content
            assert "2/10" in message_content

    async def test_rate_limit_recovery_scenario(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test scenario where rate limit expires between checks."""
        # Setup side effect for multiple calls - need more calls since each handle_ip_command calls is_limited twice
        ip_commands.rate_limiter.is_limited = AsyncMock(
            side_effect=[(True, 1), (False, 0), (False, 0)]
        )
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")
        ip_commands.storage.save_current_ip = Mock(return_value=True)

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
        ):
            mock_health.is_fallback_active.return_value = False
            mock_send.return_value = True

            # First call - should be rate limited
            result1 = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )
            assert result1 is True

            # Second call - should succeed
            result2 = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )
            assert result2 is True

            # Verify rate limit checks occurred (should be called at least twice)
            assert ip_commands.rate_limiter.is_limited.call_count >= 2

    async def test_rate_limit_different_wait_times(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test rate limiting with different wait times."""
        wait_times = [30, 60, 120, 300]

        for wait_time in wait_times:
            ip_commands.rate_limiter.is_limited = AsyncMock(
                return_value=(True, wait_time)
            )

            with patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send:
                mock_send.return_value = True

                # Execute command
                result = await ip_commands.handle_ip_command(
                    mock_message, mock_discord_client
                )

                # Verify wait time is communicated correctly
                assert result is True
                call_args = mock_send.call_args
                assert f"{wait_time} seconds" in call_args[0][1]

    async def test_rate_limit_status_remaining_calls(self, ip_commands, mock_message):
        """Test that status command shows accurate remaining calls."""
        remaining_calls_scenarios = [0, 1, 5, 10]

        for remaining in remaining_calls_scenarios:
            ip_commands.rate_limiter.is_limited = AsyncMock(
                return_value=(remaining == 0, 0)
            )
            ip_commands.rate_limiter.get_remaining_calls = AsyncMock(
                return_value=remaining
            )
            ip_commands.rate_limiter.max_calls = 10

            # Setup other required mocks
            ip_commands.ip_service.max_retries = 3
            ip_commands.ip_service.use_concurrent_checks = True
            ip_commands.ip_service.get_circuit_breaker_info = Mock(
                return_value={"enabled": False}
            )
            ip_commands.ip_service.get_cache_info = Mock(
                return_value={"enabled": False}
            )
            ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

            with (
                patch.object(
                    ip_commands, "send_message_with_retry", new_callable=AsyncMock
                ) as mock_send,
                patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
                patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            ):
                mock_health.get_system_health.return_value = {
                    "degradation_level": "normal",
                    "services": {},
                    "system_capabilities": {"active_fallbacks": []},
                }

                mock_queue.get_queue_status.return_value = {
                    "queue_size": 0,
                    "max_queue_size": 1000,
                    "ready_to_process": 0,
                    "scheduled_for_later": 0,
                    "statistics": {"total_delivered": 50, "total_failed": 0},
                }

                mock_send.return_value = True

                # Execute command
                result = await ip_commands.handle_status_command(mock_message)

                # Verify remaining calls display
                assert result is True
                call_args = mock_send.call_args
                message_content = call_args[0][1]
                assert f"{remaining}/10" in message_content


class TestMessageSendingWithRetry:
    """Test suite for message sending with retry logic and queuing."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_send_message_with_retry_success(self, ip_commands):
        """Test successful message sending without retry."""
        channel = AsyncMock()
        content = "Test message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "healthy"
            mock_send.return_value = Mock()  # Successful message

            # Execute
            result = await ip_commands.send_message_with_retry(channel, content)

            # Verify success
            assert result is True
            mock_send.assert_called_once_with(channel, content)
            mock_health.record_success.assert_called_once()

    async def test_send_message_with_retry_queue_fallback(self, ip_commands):
        """Test message queuing when direct send fails."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Test message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "healthy"
            mock_send.side_effect = Exception("Send failed")  # Simulate send failure
            mock_queue.enqueue = AsyncMock(return_value="msg_123")

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=True
            )

            # Verify queue fallback
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["channel_id"] == 12345
            assert call_args[1]["content"] == content
            assert call_args[1]["priority"] == MessagePriority.NORMAL

    async def test_send_message_notifications_disabled(self, ip_commands):
        """Test message sending when notifications are disabled due to degradation."""
        channel = AsyncMock()
        content = "Test message"

        with patch("ip_monitor.commands.ip_commands.service_health") as mock_health:
            mock_health.should_enable_feature.return_value = (
                False  # Notifications disabled
            )

            # Execute
            result = await ip_commands.send_message_with_retry(channel, content)

            # Verify pretend success
            assert result is True
            # No actual sending should occur - we can't verify this easily since
            # discord_rate_limiter is created during initialization

    async def test_send_message_priority_handling(self, ip_commands):
        """Test message priority handling in queue."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Critical message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = (
                "degraded"  # Force queue usage
            )
            mock_queue.enqueue = AsyncMock(return_value="msg_456")

            # Execute with HIGH priority
            result = await ip_commands.send_message_with_retry(
                channel, content, priority=MessagePriority.HIGH, use_queue=True
            )

            # Verify priority is passed to queue
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["priority"] == MessagePriority.HIGH

    async def test_send_message_deduplication(self, ip_commands):
        """Test message deduplication for IP-related messages."""
        channel = AsyncMock()
        channel.id = 12345
        content = "IP address has changed to 203.0.113.1"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")
            mock_queue.enqueue = AsyncMock(return_value="msg_789")

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=True
            )

            # Verify deduplication key is generated for IP messages
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["dedupe_key"] is not None
            assert "ip_notification_" in call_args[1]["dedupe_key"]

    async def test_send_message_no_deduplication_for_non_ip_messages(self, ip_commands):
        """Test that non-IP messages don't get deduplication keys."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Help message - no IP content"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")
            mock_queue.enqueue = AsyncMock(return_value="msg_101")

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=True
            )

            # Verify no deduplication key for non-IP messages
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["dedupe_key"] is None

    async def test_send_message_max_retries_parameter(self, ip_commands):
        """Test that max_retries parameter is passed to message queue."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Test message"
        max_retries = 5

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")
            mock_queue.enqueue = AsyncMock(return_value="msg_retry")

            # Execute with custom max_retries
            result = await ip_commands.send_message_with_retry(
                channel, content, max_retries=max_retries, use_queue=True
            )

            # Verify max_retries is passed correctly
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["max_retries"] == max_retries

    async def test_send_message_discord_api_health_check(self, ip_commands):
        """Test that Discord API health is checked before sending."""
        channel = AsyncMock()
        content = "Test message"

        # Test with healthy Discord API
        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "healthy"
            mock_send.return_value = Mock()

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=False
            )

            # Verify direct send attempt
            assert result is True
            mock_health.get_service_health.assert_called_with("discord_api")
            mock_send.assert_called_once()

    async def test_send_message_queue_disabled(self, ip_commands):
        """Test message sending when queue is disabled."""
        channel = AsyncMock()
        content = "Test message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")

            # Execute with queue disabled
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=False
            )

            # Verify failure when queue is disabled and direct send fails
            assert result is False
            mock_health.record_failure.assert_called()

    async def test_send_message_queue_error_handling(self, ip_commands):
        """Test handling of message queue errors."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Test message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")
            mock_queue.enqueue = AsyncMock(side_effect=Exception("Queue error"))

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=True
            )

            # Verify graceful handling of queue errors
            assert result is False
            mock_health.record_failure.assert_called()

    async def test_send_message_tags_included(self, ip_commands):
        """Test that IP monitor tags are included in queued messages."""
        channel = AsyncMock()
        channel.id = 12345
        content = "Tagged message"

        with (
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
            patch.object(
                ip_commands.discord_rate_limiter,
                "send_message_with_backoff",
                new_callable=AsyncMock,
            ) as mock_send,
        ):
            mock_health.should_enable_feature.return_value = True
            mock_health.get_service_health.return_value = Mock()
            mock_health.get_service_health.return_value.status.value = "degraded"
            mock_send.side_effect = Exception("Send failed")
            mock_queue.enqueue = AsyncMock(return_value="msg_tagged")

            # Execute
            result = await ip_commands.send_message_with_retry(
                channel, content, use_queue=True
            )

            # Verify tags are included
            assert result is True
            mock_queue.enqueue.assert_called_once()
            call_args = mock_queue.enqueue.call_args
            assert call_args[1]["tags"] == ["ip_monitor"]
