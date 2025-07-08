"""
Tests for the AdminCommandRouter class.

The AdminCommandRouter is responsible for routing admin commands to appropriate handlers
and managing the overall admin command system.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.commands.admin_commands.admin_command_router import AdminCommandRouter
from ip_monitor.commands.admin_commands.api_handler import ApiHandler
from ip_monitor.commands.admin_commands.base_handler import BaseHandler
from ip_monitor.commands.admin_commands.bot_lifecycle_handler import BotLifecycleHandler
from ip_monitor.commands.admin_commands.cache_handler import CacheHandler
from ip_monitor.commands.admin_commands.config_handler import ConfigHandler
from ip_monitor.commands.admin_commands.queue_handler import QueueHandler


class TestAdminCommandRouter:
    """Test class for AdminCommandRouter initialization and basic functionality."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message for testing."""
        message = Mock()
        message.content = "!admin help"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        message.channel.send = AsyncMock()
        return message

    def test_initialization(self, router):
        """Test router initialization with all required components."""
        assert router.client is not None
        assert router.ip_service is not None
        assert router.storage is not None
        assert router.stop_callback is not None
        assert router.config is not None
        assert router.discord_rate_limiter is not None
        assert len(router.handlers) == 5
        assert len(router.command_map) == 5

    def test_handler_registration(self, router):
        """Test that all handlers are properly registered."""
        expected_commands = ["stop", "config", "queue", "api", "cache"]
        assert list(router.command_map.keys()) == expected_commands

        # Verify handler types
        assert isinstance(router.command_map["stop"], BotLifecycleHandler)
        assert isinstance(router.command_map["config"], ConfigHandler)
        assert isinstance(router.command_map["queue"], QueueHandler)
        assert isinstance(router.command_map["api"], ApiHandler)
        assert isinstance(router.command_map["cache"], CacheHandler)

    def test_get_available_commands(self, router):
        """Test getting list of available commands."""
        commands = router.get_available_commands()
        assert len(commands) == 5
        assert "stop" in commands
        assert "config" in commands
        assert "queue" in commands
        assert "api" in commands
        assert "cache" in commands

    def test_get_handler_for_command(self, router):
        """Test getting handler for specific command."""
        # Test valid commands
        assert router.get_handler_for_command("stop") is not None
        assert router.get_handler_for_command("CONFIG") is not None  # Case insensitive
        assert isinstance(router.get_handler_for_command("config"), ConfigHandler)

        # Test invalid command
        assert router.get_handler_for_command("invalid") is None

    def test_add_handler(self, router):
        """Test adding a new command handler."""
        # Create a mock handler
        mock_handler = Mock(spec=BaseHandler)

        # Add the handler
        router.add_handler("test", mock_handler)

        # Verify it was added
        assert "test" in router.command_map
        assert router.command_map["test"] is mock_handler
        assert mock_handler in router.handlers

        # Test adding duplicate handler (should not duplicate in handlers list)
        router.add_handler("test2", mock_handler)
        handler_count = sum(1 for h in router.handlers if h is mock_handler)
        assert handler_count == 1

    def test_remove_handler(self, router):
        """Test removing a command handler."""
        # Test removing existing handler
        original_handler = router.command_map["stop"]
        assert router.remove_handler("stop") is True
        assert "stop" not in router.command_map
        assert original_handler not in router.handlers

        # Test removing non-existent handler
        assert router.remove_handler("nonexistent") is False

    def test_remove_handler_multiple_commands(self, router):
        """Test removing handler that serves multiple commands."""
        # Add same handler for multiple commands
        mock_handler = Mock(spec=BaseHandler)
        router.add_handler("test1", mock_handler)
        router.add_handler("test2", mock_handler)

        # Remove one command - handler should remain
        router.remove_handler("test1")
        assert "test1" not in router.command_map
        assert "test2" in router.command_map
        assert mock_handler in router.handlers

        # Remove second command - handler should be removed
        router.remove_handler("test2")
        assert "test2" not in router.command_map
        assert mock_handler not in router.handlers


class TestAdminCommandRouterPermissions:
    """Test class for permission checking functionality."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    def test_check_admin_permissions_true(self, router):
        """Test permission checking with admin user."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True

        assert router.check_admin_permissions(message) is True

    def test_check_admin_permissions_false(self, router):
        """Test permission checking with non-admin user."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = False

        assert router.check_admin_permissions(message) is False

    async def test_permission_denied_response(self, router):
        """Test permission denied response is sent correctly."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = False
        message.channel = Mock()
        message.content = "!admin stop"

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await router.handle_admin_command(message)

            assert result is False
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert "permission" in args[1].lower()
            assert "administrator" in args[1].lower()


class TestAdminCommandRouterRouting:
    """Test class for command routing functionality."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    @pytest.fixture
    def admin_message(self):
        """Create a mock admin message."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        return message

    async def test_handle_admin_command_stop(self, router, admin_message):
        """Test routing stop command."""
        admin_message.content = "!admin stop"

        with patch.object(router.command_map["stop"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_config(self, router, admin_message):
        """Test routing config command."""
        admin_message.content = "!admin config show"

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_queue(self, router, admin_message):
        """Test routing queue command."""
        admin_message.content = "!admin queue status"

        with patch.object(router.command_map["queue"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_api(self, router, admin_message):
        """Test routing api command."""
        admin_message.content = "!admin api list"

        with patch.object(router.command_map["api"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_cache(self, router, admin_message):
        """Test routing cache command."""
        admin_message.content = "!admin cache show"

        with patch.object(router.command_map["cache"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_case_insensitive(self, router, admin_message):
        """Test that command routing is case insensitive."""
        admin_message.content = "!admin STOP"

        with patch.object(router.command_map["stop"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_handle.assert_called_once()

    async def test_handle_admin_command_unknown(self, router, admin_message):
        """Test handling unknown admin command."""
        admin_message.content = "!admin unknown"

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await router.handle_admin_command(admin_message)

            assert result is False
            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert "unknown" in args[1].lower()

    async def test_handle_admin_command_no_subcommand(self, router, admin_message):
        """Test handling admin command without subcommand."""
        admin_message.content = "!admin"

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_send.assert_called_once()
            # Should send help message
            args = mock_send.call_args[0]
            assert "admin commands help" in args[1].lower()

    async def test_handle_admin_command_empty_content(self, router, admin_message):
        """Test handling admin command with empty content."""
        admin_message.content = "!"

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await router.handle_admin_command(admin_message)

            assert result is True
            mock_send.assert_called_once()


class TestAdminCommandRouterErrorHandling:
    """Test class for error handling functionality."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    @pytest.fixture
    def admin_message(self):
        """Create a mock admin message."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        message.content = "!admin stop"
        return message

    async def test_handler_exception_handling(self, router, admin_message):
        """Test exception handling in command handlers."""
        with patch.object(router.command_map["stop"], "handle_command") as mock_handle:
            mock_handle.side_effect = Exception("Test exception")

            with patch.object(
                router.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                result = await router.handle_admin_command(admin_message)

                assert result is False
                mock_send.assert_called_once()
                args = mock_send.call_args[0]
                assert "error occurred" in args[1].lower()

    async def test_handler_returns_false(self, router, admin_message):
        """Test when handler returns False."""
        with patch.object(router.command_map["stop"], "handle_command") as mock_handle:
            mock_handle.return_value = False

            result = await router.handle_admin_command(admin_message)
            assert result is False

    async def test_handler_async_exception(self, router, admin_message):
        """Test async exception handling."""

        async def failing_handler(*args, **kwargs):
            raise RuntimeError("Async failure")

        with patch.object(
            router.command_map["stop"], "handle_command", failing_handler
        ):
            with patch.object(
                router.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                result = await router.handle_admin_command(admin_message)

                assert result is False
                mock_send.assert_called_once()

    async def test_discord_rate_limiter_exception(self, router, admin_message):
        """Test current behavior when Discord rate limiter fails."""
        admin_message.content = "!admin unknown"

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.side_effect = Exception("Discord API error")

            # Current behavior: exception propagates
            with pytest.raises(Exception, match="Discord API error"):
                await router.handle_admin_command(admin_message)

    async def test_permission_check_edge_case(self, router):
        """Test permission check with malformed permissions object."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = None  # Edge case: None permissions
        message.content = "!admin stop"

        # Current behavior: AttributeError propagates
        with pytest.raises(AttributeError):
            await router.handle_admin_command(message)

    async def test_message_parsing_edge_cases(self, router, admin_message):
        """Test edge cases in message parsing."""
        test_cases = [
            ("!admin stop", True),  # Normal case
            ("!admin stop extra args", True),  # Extra arguments
            ("!admin unknown", False),  # Unknown command
        ]

        for content, expected_success in test_cases:
            admin_message.content = content

            if "stop" in content:
                with patch.object(
                    router.command_map["stop"], "handle_command"
                ) as mock_handle:
                    mock_handle.return_value = expected_success
                    result = await router.handle_admin_command(admin_message)
                    assert result == expected_success
            else:
                # Unknown command case
                with patch.object(
                    router.discord_rate_limiter, "send_message_with_backoff"
                ):
                    result = await router.handle_admin_command(admin_message)
                    assert result == expected_success


class TestAdminCommandRouterBackwardCompatibility:
    """Test class for backward compatibility methods."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    @pytest.fixture
    def admin_message(self):
        """Create a mock admin message."""
        message = Mock()
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        return message

    async def test_handle_stop_command_backward_compatibility(
        self, router, admin_message
    ):
        """Test backward compatibility for stop command."""
        with patch.object(router.command_map["stop"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_stop_command(admin_message)

            assert result is True
            mock_handle.assert_called_once_with(admin_message, ["stop"])

    async def test_handle_config_command_backward_compatibility(
        self, router, admin_message
    ):
        """Test backward compatibility for config command."""
        admin_message.content = "!config show"

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_config_command(admin_message)

            assert result is True
            # The method parses parts[1:] which excludes the command name
            mock_handle.assert_called_once_with(admin_message, ["show"])

    async def test_handle_queue_command_backward_compatibility(
        self, router, admin_message
    ):
        """Test backward compatibility for queue command."""
        admin_message.content = "!queue status"

        with patch.object(router.command_map["queue"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_queue_command(admin_message)

            assert result is True
            # The method parses parts[1:] which excludes the command name
            mock_handle.assert_called_once_with(admin_message, ["status"])

    async def test_handle_api_command_backward_compatibility(
        self, router, admin_message
    ):
        """Test backward compatibility for api command."""
        admin_message.content = "!api list"

        with patch.object(router.command_map["api"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_api_command(admin_message)

            assert result is True
            # The method parses parts[1:] which excludes the command name
            mock_handle.assert_called_once_with(admin_message, ["list"])

    async def test_handle_cache_command_backward_compatibility(
        self, router, admin_message
    ):
        """Test backward compatibility for cache command."""
        admin_message.content = "!cache show"

        with patch.object(router.command_map["cache"], "handle_command") as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_cache_command(admin_message)

            assert result is True
            # The method parses parts[1:] which excludes the command name
            mock_handle.assert_called_once_with(admin_message, ["show"])

    async def test_backward_compatibility_empty_args(self, router, admin_message):
        """Test backward compatibility with empty arguments."""
        admin_message.content = "!config"

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True
            result = await router.handle_config_command(admin_message)

            assert result is True
            mock_handle.assert_called_once_with(admin_message, ["config"])


class TestAdminCommandRouterHelpSystem:
    """Test class for help system functionality."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    def test_get_admin_help_text(self, router):
        """Test getting admin help text."""
        # Mock handler help text
        for handler in router.handlers:
            handler.get_help_text = Mock(return_value="Test help")

        help_text = router._get_admin_help_text()

        assert "Admin Commands Help" in help_text
        assert "General Information" in help_text
        assert "administrator permissions" in help_text
        assert "case-insensitive" in help_text

    async def test_send_admin_help(self, router):
        """Test sending admin help message."""
        message = Mock()
        message.channel = Mock()

        with patch.object(router, "_get_admin_help_text") as mock_get_help:
            mock_get_help.return_value = "Test help text"

            with patch.object(
                router.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                await router._send_admin_help(message)

                mock_send.assert_called_once()
                args = mock_send.call_args[0]
                assert args[1] == "Test help text"

    async def test_send_error_message(self, router):
        """Test sending error message."""
        message = Mock()
        message.channel = Mock()

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await router._send_error_message(message, "Test error")

            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert args[1] == "❌ Test error"

    async def test_send_unknown_command(self, router):
        """Test sending unknown command message."""
        message = Mock()
        message.channel = Mock()

        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            await router._send_unknown_command(message, "badcommand")

            mock_send.assert_called_once()
            args = mock_send.call_args[0]
            assert "badcommand" in args[1]
            assert "Unknown admin command" in args[1]


class TestAdminCommandRouterIntegration:
    """Test class for integration scenarios."""

    @pytest.fixture
    def router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create a router instance for testing."""
        stop_callback = AsyncMock()
        return AdminCommandRouter(
            mock_client, mock_ip_service, mock_storage, stop_callback, mock_config
        )

    async def test_full_command_workflow_success(self, router):
        """Test complete command workflow from start to finish."""
        message = Mock()
        message.content = "!admin config show"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True

            result = await router.handle_admin_command(message)

            assert result is True
            mock_handle.assert_called_once()
            args = mock_handle.call_args[0]
            assert args[0] is message
            assert args[1] == ["config", "show"]

    async def test_full_command_workflow_failure(self, router):
        """Test complete command workflow with failure."""
        message = Mock()
        message.content = "!admin config show"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = False

            result = await router.handle_admin_command(message)

            assert result is False
            mock_handle.assert_called_once()

    async def test_command_with_multiple_arguments(self, router):
        """Test command with multiple arguments."""
        message = Mock()
        message.content = "!admin config set check_interval 600"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True

            result = await router.handle_admin_command(message)

            assert result is True
            mock_handle.assert_called_once()
            args = mock_handle.call_args[0]
            assert args[1] == ["config", "set", "check_interval", "600"]

    async def test_handler_state_persistence(self, router):
        """Test that handlers maintain state between calls."""
        message = Mock()
        message.content = "!admin config show"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        # First call
        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True
            await router.handle_admin_command(message)

            # Verify same handler instance is used
            first_handler = router.command_map["config"]

        # Second call
        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True
            await router.handle_admin_command(message)

            # Verify same handler instance is used
            second_handler = router.command_map["config"]
            assert first_handler is second_handler

    async def test_concurrent_command_handling(self, router):
        """Test handling multiple concurrent commands."""
        import asyncio

        # Create multiple messages
        messages = []
        for i in range(3):
            message = Mock()
            message.content = f"!admin config show{i}"
            message.author = Mock()
            message.author.guild_permissions = Mock()
            message.author.guild_permissions.administrator = True
            message.channel = Mock()
            messages.append(message)

        # Handle commands concurrently
        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True

            tasks = [router.handle_admin_command(msg) for msg in messages]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(results)
            assert mock_handle.call_count == 3

    async def test_handler_dependency_injection(self, router):
        """Test that handlers receive all required dependencies."""
        # Verify each handler has access to all required services
        for handler in router.handlers:
            assert handler.client is router.client
            assert handler.ip_service is router.ip_service
            assert handler.storage is router.storage
            assert handler.stop_callback is router.stop_callback
            assert handler.config is router.config

    async def test_dynamic_handler_management(self, router):
        """Test adding and removing handlers dynamically."""
        # Create a mock handler
        mock_handler = Mock(spec=BaseHandler)
        mock_handler.handle_command = AsyncMock(return_value=True)

        # Add handler
        router.add_handler("dynamic", mock_handler)

        # Test using the new handler
        message = Mock()
        message.content = "!admin dynamic test"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        result = await router.handle_admin_command(message)

        assert result is True
        mock_handler.handle_command.assert_called_once()

        # Remove handler
        router.remove_handler("dynamic")

        # Test that handler is no longer available
        with patch.object(
            router.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await router.handle_admin_command(message)

            assert result is False
            mock_send.assert_called_once()  # Should send unknown command message

    async def test_error_recovery_after_handler_failure(self, router):
        """Test that router continues working after handler failure."""
        message = Mock()
        message.content = "!admin config show"
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()

        # First call fails
        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.side_effect = Exception("Handler failure")

            with patch.object(router.discord_rate_limiter, "send_message_with_backoff"):
                result = await router.handle_admin_command(message)
                assert result is False

        # Second call should work
        with patch.object(
            router.command_map["config"], "handle_command"
        ) as mock_handle:
            mock_handle.return_value = True

            result = await router.handle_admin_command(message)
            assert result is True
