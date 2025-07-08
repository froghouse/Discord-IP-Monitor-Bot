"""
Tests for IPCommands user interface functionality - history, status, and help commands.

This module provides test coverage for the user-facing command functionality of the IP
monitoring bot, including history retrieval, status display, and help information.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.commands.ip_commands import IPCommands
from ip_monitor.utils.message_queue import MessagePriority


class TestHistoryRetrieval:
    """Test suite for IP history retrieval functionality (!history command)."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_handle_history_command_with_data(
        self, ip_commands, mock_message, sample_ip_history
    ):
        """Test history command with existing IP history data."""
        # Setup mocks
        mock_message.author.name = "TestUser"
        ip_commands.storage.load_ip_history = Mock(return_value=sample_ip_history)

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_history_command(mock_message)

            # Verify success
            assert result is True
            ip_commands.storage.load_ip_history.assert_called_once()
            mock_send.assert_called_once()

            # Verify message content includes history
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "IP Address History" in message_content
            assert "192.168.1.1" in message_content
            assert "192.168.1.2" in message_content
            assert "192.168.1.3" in message_content

    async def test_handle_history_command_no_data(self, ip_commands, mock_message):
        """Test history command with no IP history available."""
        # Setup mocks
        ip_commands.storage.load_ip_history = Mock(return_value=[])

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_history_command(mock_message)

            # Verify success with no data message
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "No IP history available" in call_args[0][1]

    async def test_handle_history_command_large_history(
        self, ip_commands, mock_message
    ):
        """Test history command with large history that exceeds Discord message limits."""
        # Create large history list
        large_history = []
        for i in range(50):
            large_history.append(
                {"ip": f"192.168.1.{i}", "timestamp": f"2023-01-{i + 1:02d}T12:00:00Z"}
            )

        ip_commands.storage.load_ip_history = Mock(return_value=large_history)

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_history_command(mock_message)

            # Verify truncation occurs
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "more entries" in message_content
            assert len(message_content) < 2000  # Discord limit

    async def test_handle_history_command_invalid_timestamp(
        self, ip_commands, mock_message
    ):
        """Test history command with invalid timestamp format."""
        invalid_history = [
            {"ip": "192.168.1.1", "timestamp": "invalid-timestamp"},
            {"ip": "192.168.1.2", "timestamp": "2023-01-01T12:00:00Z"},
        ]

        ip_commands.storage.load_ip_history = Mock(return_value=invalid_history)

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_history_command(mock_message)

            # Verify command handles invalid timestamps gracefully
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "invalid-timestamp" in message_content  # Shows original timestamp

    async def test_handle_history_command_with_missing_fields(
        self, ip_commands, mock_message
    ):
        """Test history command with entries missing IP or timestamp fields."""
        incomplete_history = [
            {"ip": "192.168.1.1"},  # Missing timestamp
            {"timestamp": "2023-01-01T12:00:00Z"},  # Missing IP
            {
                "ip": "192.168.1.3",
                "timestamp": "2023-01-01T14:00:00Z",
            },  # Complete entry
        ]

        ip_commands.storage.load_ip_history = Mock(return_value=incomplete_history)

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_history_command(mock_message)

            # Verify command handles missing fields gracefully
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "Unknown" in message_content  # Default values for missing fields


class TestStatusDisplay:
    """Test suite for bot status display functionality (!status command)."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        ip_commands = IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )
        # Set check_interval for status display
        ip_commands.check_interval = 30
        return ip_commands

    async def test_handle_status_command_normal_state(self, ip_commands, mock_message):
        """Test status command with normal system state."""
        # Setup mocks for normal operation
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=8)
        ip_commands.rate_limiter.max_calls = 10
        ip_commands.ip_service.max_retries = 3
        ip_commands.ip_service.use_concurrent_checks = True
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

        # Mock circuit breaker info
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            return_value={
                "enabled": True,
                "state": "closed",
                "last_known_ip": "192.168.1.1",
            }
        )

        # Mock cache info
        ip_commands.ip_service.get_cache_info = Mock(
            return_value={
                "enabled": True,
                "stats": {
                    "hit_rate": 0.85,
                    "memory_entries": 10,
                    "memory_usage_mb": 2.5,
                },
                "stale_entries_count": 0,
            }
        )

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
        ):
            # Mock service health
            mock_health.get_system_health.return_value = {
                "degradation_level": "normal",
                "services": {},
                "system_capabilities": {"active_fallbacks": []},
            }

            # Mock message queue
            mock_queue.get_queue_status.return_value = {
                "queue_size": 0,
                "max_queue_size": 1000,
                "ready_to_process": 0,
                "scheduled_for_later": 0,
                "statistics": {"total_delivered": 150, "total_failed": 2},
            }

            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_status_command(mock_message)

            # Verify success and comprehensive status
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "IP Monitor Bot Status" in message_content
            assert "Every 30 minutes" in message_content
            assert "Not limited" in message_content
            assert "8/10" in message_content
            assert "CLOSED (normal operation)" in message_content
            assert "85.0% hit rate" in message_content
            assert "NORMAL" in message_content
            assert call_args[1]["priority"] == MessagePriority.LOW

    async def test_handle_status_command_degraded_state(
        self, ip_commands, mock_message
    ):
        """Test status command with degraded system state."""
        # Setup mocks for degraded operation
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(True, 45))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=0)
        ip_commands.rate_limiter.max_calls = 10
        ip_commands.ip_service.max_retries = 5
        ip_commands.ip_service.use_concurrent_checks = False
        ip_commands.storage.load_last_ip = Mock(return_value=None)

        # Mock circuit breaker in OPEN state
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            return_value={
                "enabled": True,
                "state": "open",
                "time_until_half_open": 90,
                "last_known_ip": "192.168.1.1",
            }
        )

        # Mock cache disabled
        ip_commands.ip_service.get_cache_info = Mock(return_value={"enabled": False})

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
        ):
            # Mock degraded service health
            mock_health.get_system_health.return_value = {
                "degradation_level": "severe",
                "services": {
                    "ip_api": {"status": "failed"},
                    "discord_api": {"status": "degraded"},
                },
                "system_capabilities": {
                    "active_fallbacks": ["cache_fallback", "readonly_mode"]
                },
            }

            # Mock message queue with backlog
            mock_queue.get_queue_status.return_value = {
                "queue_size": 25,
                "max_queue_size": 1000,
                "ready_to_process": 20,
                "scheduled_for_later": 5,
                "statistics": {"total_delivered": 120, "total_failed": 10},
            }

            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_status_command(mock_message)

            # Verify degraded state display
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "Limited (wait 45 seconds)" in message_content
            assert "0/10" in message_content
            assert "OPEN (retry in 90s)" in message_content
            assert "Cache: Disabled" in message_content
            assert "SEVERE DEGRADATION" in message_content
            assert "Failed: ip_api" in message_content
            assert "Degraded: discord_api" in message_content
            assert "Active Fallbacks: cache_fallback, readonly_mode" in message_content
            assert "25/1000 messages" in message_content

    async def test_handle_status_command_circuit_breaker_disabled(
        self, ip_commands, mock_message
    ):
        """Test status command when circuit breaker is disabled."""
        # Setup mocks
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=10)
        ip_commands.rate_limiter.max_calls = 10
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

        # Mock circuit breaker disabled
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            return_value={"enabled": False}
        )

        # Mock cache with no entries
        ip_commands.ip_service.get_cache_info = Mock(
            return_value={"enabled": True, "stats": {"memory_entries": 0}}
        )

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

            # Verify circuit breaker disabled status
            assert result is True
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "Circuit breaker: Disabled" in message_content
            assert "Cache: Enabled (no entries yet)" in message_content

    async def test_handle_status_command_half_open_circuit_breaker(
        self, ip_commands, mock_message
    ):
        """Test status command with circuit breaker in half-open state."""
        # Setup mocks
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=5)
        ip_commands.rate_limiter.max_calls = 10
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

        # Mock circuit breaker in HALF_OPEN state
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            return_value={
                "enabled": True,
                "state": "half_open",
                "last_known_ip": "192.168.1.1",
            }
        )

        # Mock cache with stale entries
        ip_commands.ip_service.get_cache_info = Mock(
            return_value={
                "enabled": True,
                "stats": {
                    "hit_rate": 0.65,
                    "memory_entries": 5,
                    "memory_usage_mb": 1.2,
                },
                "stale_entries_count": 2,
            }
        )

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
            patch("ip_monitor.commands.ip_commands.message_queue") as mock_queue,
        ):
            mock_health.get_system_health.return_value = {
                "degradation_level": "moderate",
                "services": {},
                "system_capabilities": {"active_fallbacks": []},
            }

            mock_queue.get_queue_status.return_value = {
                "queue_size": 2,
                "max_queue_size": 1000,
                "ready_to_process": 2,
                "scheduled_for_later": 0,
                "statistics": {"total_delivered": 200, "total_failed": 5},
            }

            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_status_command(mock_message)

            # Verify half-open state display
            assert result is True
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "HALF-OPEN (testing recovery)" in message_content
            assert "65.0% hit rate" in message_content
            assert "Stale: 2" in message_content
            assert "DEGRADED" in message_content


class TestHelpCommand:
    """Test suite for help command functionality (!help command)."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_handle_help_command_success(self, ip_commands, mock_message):
        """Test successful help command execution."""
        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_help_command(mock_message)

            # Verify success
            assert result is True
            mock_send.assert_called_once()

            # Verify help content
            call_args = mock_send.call_args
            message_content = call_args[0][1]
            assert "IP Monitor Bot Commands" in message_content
            assert "!ip" in message_content
            assert "!history" in message_content
            assert "!status" in message_content
            assert "!help" in message_content
            assert "Admin Commands" in message_content
            assert "!config" in message_content
            assert "!stop" in message_content

    async def test_handle_help_command_message_send_failure(
        self, ip_commands, mock_message
    ):
        """Test help command when message sending fails."""
        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = False

            # Execute command
            result = await ip_commands.handle_help_command(mock_message)

            # Verify failure handling
            assert (
                result is True
            )  # Command itself succeeds, just message delivery fails
            mock_send.assert_called_once()

    async def test_help_command_content_completeness(self, ip_commands, mock_message):
        """Test that help command includes all expected command categories."""
        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_help_command(mock_message)

            # Verify comprehensive help content
            assert result is True
            call_args = mock_send.call_args
            message_content = call_args[0][1]

            # Check user commands
            assert (
                "!ip" in message_content and "check the current IP" in message_content
            )
            assert (
                "!history" in message_content
                and "IP address history" in message_content
            )
            assert "!status" in message_content and "bot status" in message_content
            assert "!help" in message_content and "help message" in message_content

            # Check admin commands section
            assert "Admin Commands" in message_content
            assert "!config" in message_content
            assert "!api" in message_content
            assert "!cache" in message_content
            assert "!queue" in message_content
            assert "!stop" in message_content


class TestUserInterfaceErrorHandling:
    """Test suite for error handling in user interface commands."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_history_command_storage_exception(self, ip_commands, mock_message):
        """Test history command when storage raises exception."""
        # Setup storage to raise exception
        ip_commands.storage.load_ip_history = Mock(
            side_effect=Exception("Storage error")
        )

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command - should handle exception gracefully
            # Note: The actual implementation doesn't have explicit exception handling,
            # so this test verifies current behavior
            with pytest.raises(Exception):
                await ip_commands.handle_history_command(mock_message)

    async def test_status_command_service_exceptions(self, ip_commands, mock_message):
        """Test status command when various services raise exceptions."""
        # Setup mocks to raise exceptions
        ip_commands.rate_limiter.is_limited = AsyncMock(
            side_effect=Exception("Rate limiter error")
        )

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command - should handle exception gracefully
            with pytest.raises(Exception):
                await ip_commands.handle_status_command(mock_message)

    async def test_status_command_partial_service_failures(
        self, ip_commands, mock_message
    ):
        """Test status command when some services work and others fail."""
        # Setup partial failures
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.rate_limiter.get_remaining_calls = AsyncMock(return_value=5)
        ip_commands.rate_limiter.max_calls = 10
        ip_commands.ip_service.max_retries = 3
        ip_commands.ip_service.use_concurrent_checks = True
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")

        # Mock circuit breaker to raise exception
        ip_commands.ip_service.get_circuit_breaker_info = Mock(
            side_effect=Exception("Circuit breaker error")
        )

        # Mock cache info success
        ip_commands.ip_service.get_cache_info = Mock(
            return_value={
                "enabled": True,
                "stats": {
                    "hit_rate": 0.75,
                    "memory_entries": 3,
                    "memory_usage_mb": 0.8,
                },
                "stale_entries_count": 0,
            }
        )

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command - should handle partial failures
            with pytest.raises(Exception):
                await ip_commands.handle_status_command(mock_message)
