"""
Tests for the BotLifecycleHandler class.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord
import logging

from ip_monitor.commands.admin_commands.bot_lifecycle_handler import BotLifecycleHandler
from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage


class TestBotLifecycleHandler:
    """Test cases for BotLifecycleHandler class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for BotLifecycleHandler."""
        client = Mock(spec=discord.Client)
        client.close = AsyncMock()
        ip_service = Mock(spec=IPService)
        ip_service.get_public_ip = AsyncMock(return_value="192.168.1.1")
        storage = Mock(spec=IPStorage)
        storage.save_current_ip = Mock()
        stop_callback = AsyncMock()
        config = Mock(spec=AppConfig)

        return {
            "client": client,
            "ip_service": ip_service,
            "storage": storage,
            "stop_callback": stop_callback,
            "config": config,
        }

    @pytest.fixture
    def handler(self, mock_dependencies):
        """Create a BotLifecycleHandler instance."""
        return BotLifecycleHandler(**mock_dependencies)

    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        message.add_reaction = AsyncMock()
        return message

    def test_init(self, mock_dependencies):
        """Test BotLifecycleHandler initialization."""
        handler = BotLifecycleHandler(**mock_dependencies)

        assert handler.client == mock_dependencies["client"]
        assert handler.ip_service == mock_dependencies["ip_service"]
        assert handler.storage == mock_dependencies["storage"]
        assert handler.stop_callback == mock_dependencies["stop_callback"]
        assert handler.config == mock_dependencies["config"]
        assert handler.discord_rate_limiter is not None

    @pytest.mark.asyncio
    async def test_handle_command_no_args(self, handler, mock_message):
        """Test handle_command with no arguments."""
        result = await handler.handle_command(mock_message, [])

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_command_unknown_command(self, handler, mock_message):
        """Test handle_command with unknown command."""
        result = await handler.handle_command(mock_message, ["unknown"])

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_command_stop(self, handler, mock_message):
        """Test handle_command with stop command."""
        with patch.object(
            handler, "_handle_stop_command", return_value=True
        ) as mock_stop:
            result = await handler.handle_command(mock_message, ["stop"])

            assert result is True
            mock_stop.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_handle_command_stop_case_insensitive(self, handler, mock_message):
        """Test handle_command with stop command in different cases."""
        with patch.object(
            handler, "_handle_stop_command", return_value=True
        ) as mock_stop:
            result = await handler.handle_command(mock_message, ["STOP"])

            assert result is True
            mock_stop.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_handle_stop_command_no_permissions(self, handler, mock_message):
        """Test _handle_stop_command when user doesn't have permissions."""
        # Set up message without admin permissions
        mock_message.author.guild_permissions.administrator = False

        with patch.object(handler, "send_permission_denied") as mock_send_denied:
            result = await handler._handle_stop_command(mock_message)

            assert result is False
            mock_send_denied.assert_called_once_with(mock_message)

    @pytest.mark.asyncio
    async def test_handle_stop_command_success(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_stop_command successful execution."""
        with patch.object(handler, "log_command_usage") as mock_log:
            with patch.object(handler, "add_reaction") as mock_reaction:
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ) as mock_send:
                    result = await handler._handle_stop_command(mock_message)

                    assert result is True
                    mock_log.assert_called_once_with(mock_message, "stop")
                    mock_reaction.assert_called_once_with(mock_message, "🛑")
                    mock_send.assert_called_once_with(
                        mock_message.channel, "🛑 Stopping bot. Goodbye!"
                    )
                    mock_dependencies["ip_service"].get_public_ip.assert_called_once()
                    mock_dependencies[
                        "storage"
                    ].save_current_ip.assert_called_once_with("192.168.1.1")
                    mock_dependencies["stop_callback"].assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_command_no_ip(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_stop_command when no IP is available."""
        # Set up IP service to return None
        mock_dependencies["ip_service"].get_public_ip.return_value = None

        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ):
                    result = await handler._handle_stop_command(mock_message)

                    assert result is True
                    mock_dependencies["ip_service"].get_public_ip.assert_called_once()
                    mock_dependencies["storage"].save_current_ip.assert_not_called()
                    mock_dependencies["stop_callback"].assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_command_ip_service_error(
        self, handler, mock_message, mock_dependencies, caplog
    ):
        """Test _handle_stop_command when IP service throws an error."""
        # Set up IP service to raise an exception
        mock_dependencies["ip_service"].get_public_ip.side_effect = Exception(
            "IP service error"
        )

        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(handler, "handle_command_error") as mock_error:
                    result = await handler._handle_stop_command(mock_message)

                    assert result is True
                    mock_error.assert_called_once()
                    mock_dependencies["client"].close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_command_stop_callback_error(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_stop_command when stop callback throws an error."""
        # Set up stop callback to raise an exception
        mock_dependencies["stop_callback"].side_effect = Exception(
            "Stop callback error"
        )

        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ):
                    with patch.object(handler, "handle_command_error") as mock_error:
                        result = await handler._handle_stop_command(mock_message)

                        assert result is True
                        mock_error.assert_called_once()
                        mock_dependencies["client"].close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stop_command_client_close_error(
        self, handler, mock_message, mock_dependencies, caplog
    ):
        """Test _handle_stop_command when client close throws an error."""
        # Set up both stop callback and client close to raise exceptions
        mock_dependencies["stop_callback"].side_effect = Exception(
            "Stop callback error"
        )
        mock_dependencies["client"].close.side_effect = Exception("Client close error")

        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ):
                    with patch.object(handler, "handle_command_error"):
                        with caplog.at_level(logging.ERROR):
                            result = await handler._handle_stop_command(mock_message)

                            assert result is True
                            assert "Error during force close" in caplog.text

    @pytest.mark.asyncio
    async def test_handle_stop_command_save_ip_logs_success(
        self, handler, mock_message, mock_dependencies, caplog
    ):
        """Test _handle_stop_command logs IP save success."""
        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ):
                    with caplog.at_level(logging.INFO):
                        result = await handler._handle_stop_command(mock_message)

                        assert result is True
                        assert (
                            "Final IP saved before shutdown: 192.168.1.1" in caplog.text
                        )

    def test_get_help_text(self, handler):
        """Test get_help_text method."""
        help_text = handler.get_help_text()

        assert "Bot Lifecycle Commands:" in help_text
        assert "!stop" in help_text
        assert "Gracefully shut down the bot" in help_text
        assert "Admin only" in help_text
        assert "Saves current IP before shutdown" in help_text
        assert "Sends goodbye message" in help_text
        assert "Performs clean shutdown sequence" in help_text

    @pytest.mark.asyncio
    async def test_stop_command_integration(
        self, handler, mock_message, mock_dependencies
    ):
        """Test complete stop command flow integration."""
        # This test verifies the complete flow from handle_command to _handle_stop_command

        with patch.object(handler, "log_command_usage") as mock_log:
            with patch.object(handler, "add_reaction") as mock_reaction:
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ) as mock_send:
                    result = await handler.handle_command(mock_message, ["stop"])

                    assert result is True
                    mock_log.assert_called_once_with(mock_message, "stop")
                    mock_reaction.assert_called_once_with(mock_message, "🛑")
                    mock_send.assert_called_once_with(
                        mock_message.channel, "🛑 Stopping bot. Goodbye!"
                    )
                    mock_dependencies["stop_callback"].assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_stop_commands(
        self, handler, mock_message, mock_dependencies
    ):
        """Test handling multiple stop commands."""
        # Test that multiple stop commands are handled correctly

        with patch.object(handler, "log_command_usage"):
            with patch.object(handler, "add_reaction"):
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ):
                    result1 = await handler.handle_command(mock_message, ["stop"])
                    result2 = await handler.handle_command(mock_message, ["stop"])

                    assert result1 is True
                    assert result2 is True
                    assert mock_dependencies["stop_callback"].call_count == 2
