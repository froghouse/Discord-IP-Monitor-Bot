"""
Integration tests for AdminCommandRouter.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.commands.admin_commands.admin_command_router import AdminCommandRouter
from ip_monitor.commands.admin_commands.base_handler import BaseHandler


class TestAdminCommandRouterIntegration:
    """Integration test cases for AdminCommandRouter."""

    @pytest.fixture
    def admin_router(
        self,
        mock_client,
        mock_ip_service,
        mock_storage,
        mock_stop_callback,
        mock_config,
    ):
        """Create an AdminCommandRouter instance for testing."""
        return AdminCommandRouter(
            client=mock_client,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=mock_stop_callback,
            config=mock_config,
        )

    def test_initialization(self, admin_router):
        """Test that AdminCommandRouter initializes correctly."""
        assert len(admin_router.handlers) == 5
        assert len(admin_router.command_map) == 5
        assert "stop" in admin_router.command_map
        assert "config" in admin_router.command_map
        assert "queue" in admin_router.command_map
        assert "api" in admin_router.command_map
        assert "cache" in admin_router.command_map

    def test_check_admin_permissions(
        self, admin_router, mock_admin_message, mock_non_admin_message
    ):
        """Test admin permission checking."""
        assert admin_router.check_admin_permissions(mock_admin_message) is True
        assert admin_router.check_admin_permissions(mock_non_admin_message) is False

    async def test_handle_admin_command_no_permissions(
        self, admin_router, mock_non_admin_message
    ):
        """Test handling admin command without permissions."""
        mock_non_admin_message.content = "!admin stop"

        result = await admin_router.handle_admin_command(mock_non_admin_message)
        assert result is False

    async def test_handle_admin_command_no_args(self, admin_router, mock_admin_message):
        """Test handling admin command with no arguments shows help."""
        mock_admin_message.content = "!admin"

        result = await admin_router.handle_admin_command(mock_admin_message)
        assert result is True

    async def test_handle_admin_command_unknown_command(
        self, admin_router, mock_admin_message
    ):
        """Test handling unknown admin command."""
        mock_admin_message.content = "!admin unknown"

        result = await admin_router.handle_admin_command(mock_admin_message)
        assert result is False

    async def test_handle_admin_command_stop(self, admin_router, mock_admin_message):
        """Test handling stop command through router."""
        mock_admin_message.content = "!admin stop"

        with patch.object(
            admin_router.command_map["stop"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["stop"])

    async def test_handle_admin_command_config(self, admin_router, mock_admin_message):
        """Test handling config command through router."""
        mock_admin_message.content = "!admin config show"

        with patch.object(
            admin_router.command_map["config"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["config", "show"])

    async def test_handle_admin_command_queue(self, admin_router, mock_admin_message):
        """Test handling queue command through router."""
        mock_admin_message.content = "!admin queue clear"

        with patch.object(
            admin_router.command_map["queue"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["queue", "clear"])

    async def test_handle_admin_command_api(self, admin_router, mock_admin_message):
        """Test handling api command through router."""
        mock_admin_message.content = "!admin api list"

        with patch.object(
            admin_router.command_map["api"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["api", "list"])

    async def test_handle_admin_command_cache(self, admin_router, mock_admin_message):
        """Test handling cache command through router."""
        mock_admin_message.content = "!admin cache show"

        with patch.object(
            admin_router.command_map["cache"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["cache", "show"])

    async def test_handle_admin_command_handler_exception(
        self, admin_router, mock_admin_message
    ):
        """Test handling admin command when handler raises exception."""
        mock_admin_message.content = "!admin stop"

        with patch.object(
            admin_router.command_map["stop"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.side_effect = Exception("Handler error")

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is False

    async def test_handle_stop_command_backward_compatibility(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility stop command method."""
        with patch.object(
            admin_router.command_map["stop"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_stop_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["stop"])

    async def test_handle_config_command_backward_compatibility(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility config command method."""
        mock_admin_message.content = "!config show field"

        with patch.object(
            admin_router.command_map["config"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_config_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(
                mock_admin_message, ["show", "field"]
            )

    async def test_handle_config_command_no_args(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility config command with no args."""
        mock_admin_message.content = "!config"

        with patch.object(
            admin_router.command_map["config"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_config_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["config"])

    async def test_handle_queue_command_backward_compatibility(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility queue command method."""
        mock_admin_message.content = "!queue status"

        with patch.object(
            admin_router.command_map["queue"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_queue_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(mock_admin_message, ["status"])

    async def test_handle_api_command_backward_compatibility(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility api command method."""
        mock_admin_message.content = "!api test endpoint"

        with patch.object(
            admin_router.command_map["api"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_api_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(
                mock_admin_message, ["test", "endpoint"]
            )

    async def test_handle_cache_command_backward_compatibility(
        self, admin_router, mock_admin_message
    ):
        """Test backward compatibility cache command method."""
        mock_admin_message.content = "!cache clear namespace"

        with patch.object(
            admin_router.command_map["cache"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.return_value = True

            result = await admin_router.handle_cache_command(mock_admin_message)
            assert result is True
            mock_handle.assert_called_once_with(
                mock_admin_message, ["clear", "namespace"]
            )

    def test_get_admin_help_text(self, admin_router):
        """Test generation of comprehensive admin help text."""
        help_text = admin_router._get_admin_help_text()
        assert "Admin Commands Help" in help_text
        assert "General Information:" in help_text
        assert "administrator permissions" in help_text

    def test_get_available_commands(self, admin_router):
        """Test getting list of available commands."""
        commands = admin_router.get_available_commands()
        assert "stop" in commands
        assert "config" in commands
        assert "queue" in commands
        assert "api" in commands
        assert "cache" in commands
        assert len(commands) == 5

    def test_get_handler_for_command(self, admin_router):
        """Test getting handler for specific command."""
        stop_handler = admin_router.get_handler_for_command("stop")
        assert stop_handler is not None
        assert stop_handler == admin_router.command_map["stop"]

        unknown_handler = admin_router.get_handler_for_command("unknown")
        assert unknown_handler is None

    def test_add_handler(self, admin_router):
        """Test adding new command handler."""
        mock_handler = MagicMock(spec=BaseHandler)
        mock_handler.get_help_text.return_value = "Test command help"

        admin_router.add_handler("test", mock_handler)

        assert "test" in admin_router.command_map
        assert admin_router.command_map["test"] == mock_handler
        assert mock_handler in admin_router.handlers

    def test_add_handler_existing_handler(self, admin_router):
        """Test adding handler that already exists in handlers list."""
        existing_handler = admin_router.command_map["stop"]

        admin_router.add_handler("test", existing_handler)

        assert "test" in admin_router.command_map
        assert admin_router.command_map["test"] == existing_handler
        # Should not duplicate in handlers list
        assert admin_router.handlers.count(existing_handler) == 1

    def test_remove_handler(self, admin_router):
        """Test removing command handler."""
        # Add a test handler first
        mock_handler = MagicMock(spec=BaseHandler)
        admin_router.add_handler("test", mock_handler)

        # Verify it was added
        assert "test" in admin_router.command_map
        assert mock_handler in admin_router.handlers

        # Remove it
        result = admin_router.remove_handler("test")
        assert result is True
        assert "test" not in admin_router.command_map
        assert mock_handler not in admin_router.handlers

    def test_remove_handler_nonexistent(self, admin_router):
        """Test removing handler that doesn't exist."""
        result = admin_router.remove_handler("nonexistent")
        assert result is False

    def test_remove_handler_shared_handler(self, admin_router):
        """Test removing handler that is shared by multiple commands."""
        existing_handler = admin_router.command_map["stop"]

        # Add same handler with different command
        admin_router.add_handler("shutdown", existing_handler)

        # Remove one command
        result = admin_router.remove_handler("shutdown")
        assert result is True
        assert "shutdown" not in admin_router.command_map
        assert "stop" in admin_router.command_map
        # Handler should still be in handlers list
        assert existing_handler in admin_router.handlers

    async def test_end_to_end_command_flow(self, admin_router, mock_admin_message):
        """Test complete end-to-end command flow."""
        # Test a complete config command flow
        mock_admin_message.content = "!admin config show check_interval"

        # Mock the config handler's response
        with patch.object(
            admin_router.command_map["config"], "handle_command", new_callable=AsyncMock
        ) as mock_config_handle:
            mock_config_handle.return_value = True

            # Route the command
            result = await admin_router.handle_admin_command(mock_admin_message)

            # Verify the flow
            assert result is True
            mock_config_handle.assert_called_once_with(
                mock_admin_message, ["config", "show", "check_interval"]
            )

    async def test_command_routing_case_insensitive(
        self, admin_router, mock_admin_message
    ):
        """Test that command routing is case insensitive."""
        test_cases = [
            "!admin STOP",
            "!admin Stop",
            "!admin sToP",
            "!admin CONFIG show",
            "!admin Config Show",
            "!admin QUEUE clear",
            "!admin API list",
            "!admin CACHE show",
        ]

        for content in test_cases:
            mock_admin_message.content = content
            command = content.split()[1].lower()

            with patch.object(
                admin_router.command_map[command],
                "handle_command",
                new_callable=AsyncMock,
            ) as mock_handle:
                mock_handle.return_value = True

                result = await admin_router.handle_admin_command(mock_admin_message)
                assert result is True
                mock_handle.assert_called_once()

    async def test_error_handling_in_routing(self, admin_router, mock_admin_message):
        """Test error handling during command routing."""
        mock_admin_message.content = "!admin config show"

        # Make the config handler raise an exception
        with patch.object(
            admin_router.command_map["config"], "handle_command", new_callable=AsyncMock
        ) as mock_handle:
            mock_handle.side_effect = ValueError("Test error")

            result = await admin_router.handle_admin_command(mock_admin_message)
            assert result is False

    def test_handler_initialization_integrity(self, admin_router):
        """Test that all handlers are properly initialized and accessible."""
        # Verify handler types
        from ip_monitor.commands.admin_commands.api_handler import ApiHandler
        from ip_monitor.commands.admin_commands.bot_lifecycle_handler import (
            BotLifecycleHandler,
        )
        from ip_monitor.commands.admin_commands.cache_handler import CacheHandler
        from ip_monitor.commands.admin_commands.config_handler import ConfigHandler
        from ip_monitor.commands.admin_commands.queue_handler import QueueHandler

        assert isinstance(admin_router.command_map["stop"], BotLifecycleHandler)
        assert isinstance(admin_router.command_map["config"], ConfigHandler)
        assert isinstance(admin_router.command_map["queue"], QueueHandler)
        assert isinstance(admin_router.command_map["api"], ApiHandler)
        assert isinstance(admin_router.command_map["cache"], CacheHandler)

        # Verify all handlers have required dependencies
        for handler in admin_router.handlers:
            assert handler.client == admin_router.client
            assert handler.ip_service == admin_router.ip_service
            assert handler.storage == admin_router.storage
            assert handler.stop_callback == admin_router.stop_callback
            assert handler.config == admin_router.config
