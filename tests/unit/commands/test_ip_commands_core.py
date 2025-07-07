"""
Core tests for IPCommands class - initialization and basic IP check functionality.

This module provides test coverage for the core functionality of the IP monitoring
bot's user commands, including initialization, manual IP checks, and basic operations.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.commands.ip_commands import IPCommands
from ip_monitor.utils.message_queue import MessagePriority


class TestIPCommandsInitialization:
    """Test suite for IPCommands initialization and basic setup."""

    def test_ip_commands_init(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Test IPCommands initialization with all required dependencies."""
        channel_id = 12345

        ip_commands = IPCommands(
            channel_id=channel_id,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

        # Verify all attributes are set correctly
        assert ip_commands.channel_id == channel_id
        assert ip_commands.ip_service == mock_ip_service
        assert ip_commands.storage == mock_storage
        assert ip_commands.rate_limiter == mock_rate_limiter
        assert ip_commands.ip_check_lock is not None
        assert ip_commands.discord_rate_limiter is not None

    def test_ip_commands_init_with_sqlite_storage(
        self, mock_ip_service, sqlite_storage, mock_rate_limiter
    ):
        """Test IPCommands initialization with SQLite storage specifically."""
        channel_id = 54321

        ip_commands = IPCommands(
            channel_id=channel_id,
            ip_service=mock_ip_service,
            storage=sqlite_storage,
            rate_limiter=mock_rate_limiter,
        )

        assert ip_commands.channel_id == channel_id
        assert ip_commands.storage == sqlite_storage


class TestManualIPCheck:
    """Test suite for manual IP check functionality (!ip command)."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_handle_ip_command_success(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test successful manual IP check via !ip command."""
        # Setup mocks
        mock_message.author.name = "TestUser"
        mock_message.channel.send = AsyncMock()
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")
        ip_commands.storage.save_current_ip = Mock(return_value=True)

        # Mock get_channel to return a valid channel
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
        ):
            mock_health.is_fallback_active.return_value = False
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )

            # Verify success
            assert result is True
            # Rate limiter called twice - once in handle_ip_command, once in check_ip_once
            assert ip_commands.rate_limiter.is_limited.call_count == 2
            ip_commands.ip_service.get_public_ip.assert_called_once()
            ip_commands.storage.save_current_ip.assert_called_once_with("203.0.113.1")

            # Verify message was sent - since IP changed, it shows change notification
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "IP address has changed" in call_args[0][1]  # IP changed message
            assert "203.0.113.1" in call_args[0][1]  # Current IP
            assert "192.168.1.1" in call_args[0][1]  # Previous IP
            assert (
                call_args[1]["priority"] == MessagePriority.HIGH
            )  # High priority for IP change

    async def test_handle_ip_command_rate_limited(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test manual IP check when rate limited."""
        # Setup rate limiting
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(True, 120))

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute command
            result = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )

            # Verify rate limit handling
            assert result is True
            ip_commands.rate_limiter.is_limited.assert_called_once()
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Rate limit reached" in call_args[0][1]
            assert "120 seconds" in call_args[0][1]

    async def test_handle_ip_command_ip_retrieval_failure(
        self, ip_commands, mock_message, mock_discord_client
    ):
        """Test manual IP check when IP retrieval fails."""
        # Setup mocks
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value=None)

        with patch.object(
            ip_commands, "check_ip_once", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = False

            # Execute command
            result = await ip_commands.handle_ip_command(
                mock_message, mock_discord_client
            )

            # Verify failure handling
            assert result is False
            mock_check.assert_called_once_with(mock_discord_client, user_requested=True)

    async def test_check_ip_once_user_requested_no_change(
        self, ip_commands, mock_discord_client
    ):
        """Test check_ip_once with user request when IP hasn't changed."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="192.168.1.1")
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

            # Execute check
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=True
            )

            # Verify success and message content
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "IP address check complete" in call_args[0][1]
            assert "No change from previous IP" in call_args[0][1]
            assert call_args[1]["priority"] == MessagePriority.NORMAL

    async def test_check_ip_once_ip_changed(self, ip_commands, mock_discord_client):
        """Test check_ip_once when IP has changed."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
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

            # Execute check
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=False
            )

            # Verify success and HIGH priority message for IP change
            assert result is True
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "IP address has changed" in call_args[0][1]
            assert "192.168.1.1" in call_args[0][1]  # Previous IP
            assert "203.0.113.1" in call_args[0][1]  # Current IP
            assert call_args[1]["priority"] == MessagePriority.HIGH

    async def test_check_ip_once_channel_not_found(
        self, ip_commands, mock_discord_client
    ):
        """Test check_ip_once when Discord channel cannot be found."""
        # Setup mock to return None for channel
        mock_discord_client.get_channel.return_value = None

        # Execute check
        result = await ip_commands.check_ip_once(
            mock_discord_client, user_requested=True
        )

        # Verify failure
        assert result is False
        mock_discord_client.get_channel.assert_called_once_with(12345)

    async def test_check_ip_once_readonly_mode(self, ip_commands, mock_discord_client):
        """Test check_ip_once in read-only mode (service degradation)."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")
        ip_commands.storage.save_current_ip = Mock(return_value=True)

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
        ):
            mock_health.is_fallback_active.return_value = True  # Read-only mode active
            mock_send.return_value = True

            # Execute check
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=True
            )

            # Verify IP was not saved but check succeeded
            assert result is True
            ip_commands.storage.save_current_ip.assert_not_called()
            mock_send.assert_called_once()

    async def test_check_ip_once_scheduled_no_change_no_message(
        self, ip_commands, mock_discord_client
    ):
        """Test that scheduled checks don't send messages when IP hasn't changed."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="192.168.1.1")
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")  # Same IP
        ip_commands.storage.save_current_ip = Mock(return_value=True)

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
        ):
            mock_health.is_fallback_active.return_value = False
            mock_send.return_value = True

            # Execute scheduled check (user_requested=False)
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=False
            )

            # Verify success but no message sent
            assert result is True
            mock_send.assert_not_called()  # No message should be sent for scheduled checks with no change


class TestIPCheckErrorHandling:
    """Test suite for error handling in core IP check functionality."""

    @pytest.fixture
    def ip_commands(self, mock_ip_service, mock_storage, mock_rate_limiter):
        """Create IPCommands instance for testing."""
        return IPCommands(
            channel_id=12345,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
        )

    async def test_check_ip_once_exception_handling(
        self, ip_commands, mock_discord_client
    ):
        """Test exception handling in check_ip_once method."""
        # Setup mock to raise exception
        ip_commands.rate_limiter.is_limited = AsyncMock(
            side_effect=Exception("Rate limiter error")
        )

        # Execute check
        result = await ip_commands.check_ip_once(
            mock_discord_client, user_requested=True
        )

        # Verify graceful failure
        assert result is False

    async def test_ip_service_failure_in_check(self, ip_commands, mock_discord_client):
        """Test IP service failure during check operation."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(
            return_value=None
        )  # Simulate failure

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute check
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=True
            )

            # Verify failure handling
            assert result is False
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Failed to retrieve" in call_args[0][1]

    async def test_storage_save_failure(self, ip_commands, mock_discord_client):
        """Test storage save failure during IP check."""
        # Setup mocks
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        ip_commands.storage.load_last_ip = Mock(return_value="192.168.1.1")
        ip_commands.storage.save_current_ip = Mock(
            return_value=False
        )  # Simulate save failure

        with (
            patch.object(
                ip_commands, "send_message_with_retry", new_callable=AsyncMock
            ) as mock_send,
            patch("ip_monitor.commands.ip_commands.service_health") as mock_health,
        ):
            mock_health.is_fallback_active.return_value = False
            mock_send.return_value = True

            # Execute check
            result = await ip_commands.check_ip_once(
                mock_discord_client, user_requested=True
            )

            # Verify failure handling
            assert result is False
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert "Failed to save" in call_args[0][1]

    async def test_multiple_consecutive_failures(
        self, ip_commands, mock_discord_client
    ):
        """Test handling of multiple consecutive failures."""
        # Setup mocks for consistent failure
        channel = AsyncMock()
        mock_discord_client.get_channel.return_value = channel
        ip_commands.rate_limiter.is_limited = AsyncMock(return_value=(False, 0))
        ip_commands.ip_service.get_public_ip = AsyncMock(return_value=None)

        with patch.object(
            ip_commands, "send_message_with_retry", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = True

            # Execute multiple checks
            results = []
            for _ in range(3):
                result = await ip_commands.check_ip_once(
                    mock_discord_client, user_requested=True
                )
                results.append(result)

            # Verify all checks fail gracefully
            assert all(result is False for result in results)
            assert mock_send.call_count == 3  # Error message sent each time
