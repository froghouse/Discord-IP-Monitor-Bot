"""
Tests for the BaseHandler class.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord
import logging

from ip_monitor.commands.admin_commands.base_handler import BaseHandler
from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage


class TestBaseHandler:
    """Test cases for BaseHandler class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for BaseHandler."""
        client = Mock(spec=discord.Client)
        ip_service = Mock(spec=IPService)
        storage = Mock(spec=IPStorage)
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
    def concrete_handler(self, mock_dependencies):
        """Create a concrete implementation of BaseHandler for testing."""

        class ConcreteHandler(BaseHandler):
            async def handle_command(self, message, args):
                return True

            def get_help_text(self):
                return "Test help text"

        return ConcreteHandler(**mock_dependencies)

    def test_init(self, mock_dependencies):
        """Test BaseHandler initialization."""

        class ConcreteHandler(BaseHandler):
            async def handle_command(self, message, args):
                return True

            def get_help_text(self):
                return "Test help text"

        handler = ConcreteHandler(**mock_dependencies)

        assert handler.client == mock_dependencies["client"]
        assert handler.ip_service == mock_dependencies["ip_service"]
        assert handler.storage == mock_dependencies["storage"]
        assert handler.stop_callback == mock_dependencies["stop_callback"]
        assert handler.config == mock_dependencies["config"]
        assert handler.discord_rate_limiter is not None

    def test_check_admin_permissions_true(self, concrete_handler):
        """Test check_admin_permissions when user has admin permissions."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True

        result = concrete_handler.check_admin_permissions(message)

        assert result is True

    def test_check_admin_permissions_false(self, concrete_handler):
        """Test check_admin_permissions when user doesn't have admin permissions."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = False

        result = concrete_handler.check_admin_permissions(message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_permission_denied(self, concrete_handler):
        """Test send_permission_denied method."""
        message = Mock(spec=discord.Message)
        message.channel = Mock()

        with patch.object(
            concrete_handler.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await concrete_handler.send_permission_denied(message)

            mock_send.assert_called_once_with(
                message.channel,
                "❌ You don't have permission to use this command. Administrator privileges required.",
            )

    @pytest.mark.asyncio
    async def test_send_error_message(self, concrete_handler):
        """Test send_error_message method."""
        message = Mock(spec=discord.Message)
        message.channel = Mock()
        error = "Test error"

        with patch.object(
            concrete_handler.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await concrete_handler.send_error_message(message, error)

            mock_send.assert_called_once_with(message.channel, f"❌ {error}")

    @pytest.mark.asyncio
    async def test_send_success_message(self, concrete_handler):
        """Test send_success_message method."""
        message = Mock(spec=discord.Message)
        message.channel = Mock()
        success = "Test success"

        with patch.object(
            concrete_handler.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await concrete_handler.send_success_message(message, success)

            mock_send.assert_called_once_with(message.channel, f"✅ {success}")

    @pytest.mark.asyncio
    async def test_send_info_message(self, concrete_handler):
        """Test send_info_message method."""
        message = Mock(spec=discord.Message)
        message.channel = Mock()
        info = "Test info"

        with patch.object(
            concrete_handler.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await concrete_handler.send_info_message(message, info)

            mock_send.assert_called_once_with(message.channel, f"ℹ️ {info}")

    @pytest.mark.asyncio
    async def test_add_reaction_success(self, concrete_handler):
        """Test add_reaction method with successful reaction."""
        message = Mock(spec=discord.Message)
        message.add_reaction = AsyncMock()
        emoji = "👍"

        await concrete_handler.add_reaction(message, emoji)

        message.add_reaction.assert_called_once_with(emoji)

    @pytest.mark.asyncio
    async def test_add_reaction_failure(self, concrete_handler, caplog):
        """Test add_reaction method with failed reaction."""
        message = Mock(spec=discord.Message)

        # Create a mock response with the necessary attributes
        mock_response = Mock()
        mock_response.status = 429
        mock_response.reason = "Too Many Requests"

        message.add_reaction = AsyncMock(
            side_effect=discord.HTTPException(mock_response, "Rate limited")
        )
        emoji = "👍"

        with caplog.at_level(logging.WARNING):
            await concrete_handler.add_reaction(message, emoji)

        message.add_reaction.assert_called_once_with(emoji)
        assert "Failed to add reaction" in caplog.text

    def test_log_command_usage(self, concrete_handler, caplog):
        """Test log_command_usage method."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.__str__ = Mock(return_value="TestUser")
        message.channel = Mock()
        message.channel.__str__ = Mock(return_value="test-channel")
        command = "test_command"

        with caplog.at_level(logging.INFO):
            concrete_handler.log_command_usage(message, command)

        assert "Admin command 'test_command' used by" in caplog.text

    @pytest.mark.asyncio
    async def test_handle_command_error(self, concrete_handler, caplog):
        """Test handle_command_error method."""
        message = Mock(spec=discord.Message)
        message.channel = Mock()
        error = Exception("Test error")
        command = "test_command"

        with patch.object(concrete_handler, "send_error_message") as mock_send_error:
            with caplog.at_level(logging.ERROR):
                await concrete_handler.handle_command_error(message, error, command)

        assert "Error in admin command 'test_command'" in caplog.text
        mock_send_error.assert_called_once_with(
            message,
            f"An error occurred while processing the '{command}' command. Please try again.",
        )

    def test_format_code_block(self, concrete_handler):
        """Test format_code_block method."""
        content = "print('hello')"
        language = "python"

        result = concrete_handler.format_code_block(content, language)

        assert result == f"```{language}\n{content}\n```"

    def test_format_code_block_no_language(self, concrete_handler):
        """Test format_code_block method without language."""
        content = "some text"

        result = concrete_handler.format_code_block(content)

        assert result == f"```\n{content}\n```"

    def test_format_inline_code(self, concrete_handler):
        """Test format_inline_code method."""
        content = "variable_name"

        result = concrete_handler.format_inline_code(content)

        assert result == f"`{content}`"

    def test_truncate_message_no_truncation(self, concrete_handler):
        """Test truncate_message with message under limit."""
        message = "Short message"
        max_length = 2000

        result = concrete_handler.truncate_message(message, max_length)

        assert result == message

    def test_truncate_message_with_truncation(self, concrete_handler, caplog):
        """Test truncate_message with message over limit."""
        message = "A" * 2010
        max_length = 2000

        with caplog.at_level(logging.WARNING):
            result = concrete_handler.truncate_message(message, max_length)

        assert len(result) == max_length
        assert result.endswith("...")
        assert "Message truncated" in caplog.text

    def test_truncate_message_custom_length(self, concrete_handler):
        """Test truncate_message with custom max length."""
        message = "A" * 100
        max_length = 50

        result = concrete_handler.truncate_message(message, max_length)

        assert len(result) == max_length
        assert result.endswith("...")

    def test_abstract_methods(self, mock_dependencies):
        """Test that abstract methods raise NotImplementedError."""

        # Test that BaseHandler cannot be instantiated directly
        with pytest.raises(TypeError):
            BaseHandler(**mock_dependencies)

    def test_concrete_implementation(self, concrete_handler):
        """Test that concrete implementation works correctly."""
        # Test abstract method implementations
        assert concrete_handler.get_help_text() == "Test help text"

        # Test that handle_command is implemented
        import asyncio

        result = asyncio.run(concrete_handler.handle_command(Mock(), []))
        assert result is True
