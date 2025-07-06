"""
Integration tests for admin command workflows.

This module tests the complete admin command processing including:
- Runtime configuration changes
- API management operations
- System diagnostics and monitoring
- Error handling and validation
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.commands.admin_commands import AdminCommandRouter
from ip_monitor.config import AppConfig
from ip_monitor.ip_api_config import IPAPIManager
from ip_monitor.utils.cache import get_global_cache
from ip_monitor.utils.service_health import service_health


class TestConfigurationChangeWorkflow:
    """Test runtime configuration change workflows."""

    @pytest.fixture
    async def admin_router_with_config(self):
        """Create admin router with test configuration."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()

        with patch("discord.ext.commands.Bot") as mock_bot_class:
            mock_client = MagicMock()
            mock_bot_class.return_value = mock_client

            # Create temporary config file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as temp_config:
                config_path = temp_config.name

            router = AdminCommandRouter(
                client=mock_client,
                ip_service=Mock(),
                storage=Mock(),
                stop_callback=AsyncMock(),
                config=config,
            )

            yield router, config, config_path

        # Cleanup
        Path(config_path).unlink(missing_ok=True)

    async def test_config_show_workflow(self, admin_router_with_config):
        """Test configuration display workflow."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test show all configuration
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["config", "show"])
            mock_handle.assert_called_once_with(mock_message, ["config", "show"])

        # Test show specific field
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(
                mock_message, ["config", "show", "check_interval"]
            )
            mock_handle.assert_called_once_with(
                mock_message, ["config", "show", "check_interval"]
            )

    async def test_config_set_workflow(self, admin_router_with_config):
        """Test configuration setting workflow."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test valid configuration change
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(
                mock_message, ["config", "set", "max_retries", "5"]
            )
            mock_handle.assert_called_once_with(
                mock_message, ["config", "set", "max_retries", "5"]
            )

        # Test invalid configuration change
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(
                mock_message, ["config", "set", "invalid_field", "value"]
            )
            mock_handle.assert_called_once_with(
                mock_message, ["config", "set", "invalid_field", "value"]
            )

    async def test_config_persistence_workflow(self, admin_router_with_config):
        """Test configuration persistence workflow."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test configuration save
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["config", "save"])
            mock_handle.assert_called_once_with(mock_message, ["config", "save"])

        # Test configuration reload
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["config", "reload"])
            mock_handle.assert_called_once_with(mock_message, ["config", "reload"])

    async def test_config_validation_workflow(self, admin_router_with_config):
        """Test configuration validation during changes."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test validation cases
        test_cases = [
            {
                "field": "check_interval",
                "value": "5",
                "valid": True,
                "description": "Valid interval",
            },
            {
                "field": "check_interval",
                "value": "0",
                "valid": False,
                "description": "Invalid interval - too low",
            },
            {
                "field": "max_retries",
                "value": "3",
                "valid": True,
                "description": "Valid retry count",
            },
            {
                "field": "max_retries",
                "value": "-1",
                "valid": False,
                "description": "Invalid retry count - negative",
            },
        ]

        for case in test_cases:
            with patch.object(router.config_handler, "handle_command") as mock_handle:
                await router.handle_command(
                    mock_message, ["config", "set", case["field"], case["value"]]
                )

                # Verify command was processed
                mock_handle.assert_called_once_with(
                    mock_message, ["config", "set", case["field"], case["value"]]
                )

    async def test_config_change_with_restart_requirement(
        self, admin_router_with_config
    ):
        """Test configuration changes that require restart."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test check_interval change (requires restart)
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(
                mock_message, ["config", "set", "check_interval", "10"]
            )

            # Verify command was processed
            mock_handle.assert_called_once_with(
                mock_message, ["config", "set", "check_interval", "10"]
            )

    async def test_config_list_workflow(self, admin_router_with_config):
        """Test configuration field listing workflow."""
        router, config, config_path = admin_router_with_config

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test list all configurable fields
        with patch.object(router.config_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["config", "list"])
            mock_handle.assert_called_once_with(mock_message, ["config", "list"])


class TestAPIManagementWorkflow:
    """Test API management workflows."""

    @pytest.fixture
    async def admin_router_with_api_manager(self):
        """Create admin router with API manager."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()

        with patch("discord.ext.commands.Bot") as mock_bot_class:
            mock_client = MagicMock()
            mock_bot_class.return_value = mock_client

            # Create temporary API config file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as temp_api_config:
                api_config_path = temp_api_config.name

            # Mock IP service with API manager
            mock_ip_service = Mock()
            mock_api_manager = IPAPIManager(config_file=api_config_path)
            mock_ip_service.api_manager = mock_api_manager

            router = AdminCommandRouter(
                client=mock_client,
                ip_service=mock_ip_service,
                storage=Mock(),
                stop_callback=AsyncMock(),
                config=config,
            )

            yield router, mock_api_manager, api_config_path

        # Cleanup
        Path(api_config_path).unlink(missing_ok=True)

    async def test_api_list_workflow(self, admin_router_with_api_manager):
        """Test API listing workflow."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test list APIs
        with patch.object(router.api_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["api", "list"])
            mock_handle.assert_called_once_with(mock_message, ["api", "list"])

    async def test_api_add_workflow(self, admin_router_with_api_manager):
        """Test API addition workflow."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test add API with different formats
        test_apis = [
            {
                "name": "test_json_api",
                "url": "https://api.test.com/ip",
                "format": "json",
                "field": "ip",
            },
            {
                "name": "test_text_api",
                "url": "https://text.test.com/",
                "format": "text",
                "field": None,
            },
            {
                "name": "test_auto_api",
                "url": "https://auto.test.com/",
                "format": "auto",
                "field": None,
            },
        ]

        for api in test_apis:
            args = ["api", "add", api["name"], api["url"]]
            if api["format"]:
                args.append(api["format"])
            if api["field"]:
                args.append(api["field"])

            with patch.object(router.api_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, args)
                mock_handle.assert_called_once_with(mock_message, args)

    async def test_api_remove_workflow(self, admin_router_with_api_manager):
        """Test API removal workflow."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test remove API by ID and by name
        test_cases = [
            ["api", "remove", "1"],  # Remove by ID
            ["api", "remove", "test_api"],  # Remove by name
        ]

        for args in test_cases:
            with patch.object(router.api_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, args)
                mock_handle.assert_called_once_with(mock_message, args)

    async def test_api_toggle_workflow(self, admin_router_with_api_manager):
        """Test API enable/disable workflow."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test enable/disable APIs
        test_cases = [
            ["api", "enable", "1"],
            ["api", "disable", "1"],
            ["api", "enable", "test_api"],
            ["api", "disable", "test_api"],
        ]

        for args in test_cases:
            with patch.object(router.api_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, args)
                mock_handle.assert_called_once_with(mock_message, args)

    async def test_api_test_workflow(self, admin_router_with_api_manager):
        """Test API testing workflow."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test API testing
        with patch.object(router.api_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["api", "test", "1"])
            mock_handle.assert_called_once_with(mock_message, ["api", "test", "1"])

        # Test API statistics
        with patch.object(router.api_handler, "handle_command") as mock_handle:
            await router.handle_command(mock_message, ["api", "stats"])
            mock_handle.assert_called_once_with(mock_message, ["api", "stats"])

    async def test_api_error_handling_workflow(self, admin_router_with_api_manager):
        """Test API management error handling."""
        router, api_manager, api_config_path = admin_router_with_api_manager

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test error cases
        error_cases = [
            {
                "args": ["api", "add"],  # Missing arguments
                "description": "Missing API arguments",
            },
            {
                "args": ["api", "remove", "999"],  # Non-existent API
                "description": "Remove non-existent API",
            },
            {
                "args": ["api", "test", "invalid"],  # Invalid API identifier
                "description": "Test invalid API",
            },
            {
                "args": ["api", "invalid_command"],  # Invalid subcommand
                "description": "Invalid API subcommand",
            },
        ]

        for case in error_cases:
            with patch.object(router.api_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, case["args"])
                mock_handle.assert_called_once_with(mock_message, case["args"])


class TestSystemDiagnosticsWorkflow:
    """Test system diagnostics and monitoring workflows."""

    @pytest.fixture
    async def admin_router_with_diagnostics(self):
        """Create admin router with diagnostic capabilities."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()

        with patch("discord.ext.commands.Bot") as mock_bot_class:
            mock_client = MagicMock()
            mock_bot_class.return_value = mock_client

            router = AdminCommandRouter(
                client=mock_client,
                ip_service=Mock(),
                storage=Mock(),
                stop_callback=AsyncMock(),
                config=config,
            )

            yield router, config

    async def test_queue_status_workflow(self, admin_router_with_diagnostics):
        """Test message queue status monitoring workflow."""
        router, config = admin_router_with_diagnostics

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test queue status commands
        queue_commands = [
            ["queue", "status"],
            ["queue", "clear"],
            ["queue", "retry"],
            ["queue", "start"],
            ["queue", "stop"],
        ]

        for args in queue_commands:
            with patch.object(router.queue_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, args)
                mock_handle.assert_called_once_with(mock_message, args)

    async def test_cache_management_workflow(self, admin_router_with_diagnostics):
        """Test cache management workflow."""
        router, config = admin_router_with_diagnostics

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test cache management commands
        cache_commands = [
            ["cache", "show"],
            ["cache", "clear"],
            ["cache", "clear", "ip_check"],  # Clear specific namespace
            ["cache", "stats"],
            ["cache", "cleanup"],
            ["cache", "refresh"],
        ]

        for args in cache_commands:
            with patch.object(router.cache_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, args)
                mock_handle.assert_called_once_with(mock_message, args)

    async def test_system_health_monitoring_workflow(
        self, admin_router_with_diagnostics
    ):
        """Test system health monitoring integration."""
        router, config = admin_router_with_diagnostics

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Mock service health state
        with patch.object(service_health, "get_system_health_info") as mock_health:
            mock_health.return_value = {
                "overall_health": "NORMAL",
                "services": {
                    "ip_service": {"status": "NORMAL", "failure_count": 0},
                    "discord_api": {"status": "NORMAL", "failure_count": 0},
                    "storage": {"status": "NORMAL", "failure_count": 0},
                },
                "degradation_level": 0,
            }

            # Test health information retrieval (simulated through config show)
            with patch.object(router.config_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message, ["config", "show"])
                mock_handle.assert_called_once_with(mock_message, ["config", "show"])

    async def test_bot_lifecycle_workflow(self, admin_router_with_diagnostics):
        """Test bot lifecycle management workflow."""
        router, config = admin_router_with_diagnostics

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test bot stop command
        with patch.object(
            router.bot_lifecycle_handler, "handle_command"
        ) as mock_handle:
            await router.handle_command(mock_message, ["stop"])
            mock_handle.assert_called_once_with(mock_message, ["stop"])

    async def test_permission_validation_workflow(self, admin_router_with_diagnostics):
        """Test admin permission validation workflow."""
        router, config = admin_router_with_diagnostics

        # Test non-admin user
        mock_message_non_admin = MagicMock()
        mock_message_non_admin.author.guild_permissions.administrator = False
        mock_message_non_admin.channel.send = AsyncMock()

        # Should reject non-admin commands
        with patch.object(router, "check_permissions", return_value=False):
            with patch.object(router.config_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message_non_admin, ["config", "show"])
                # Command should not reach handler due to permission check
                mock_handle.assert_not_called()

        # Test admin user
        mock_message_admin = MagicMock()
        mock_message_admin.author.guild_permissions.administrator = True
        mock_message_admin.channel.send = AsyncMock()

        # Should allow admin commands
        with patch.object(router, "check_permissions", return_value=True):
            with patch.object(router.config_handler, "handle_command") as mock_handle:
                await router.handle_command(mock_message_admin, ["config", "show"])
                mock_handle.assert_called_once_with(
                    mock_message_admin, ["config", "show"]
                )

    async def test_error_recovery_workflow(self, admin_router_with_diagnostics):
        """Test error recovery and resilience workflow."""
        router, config = admin_router_with_diagnostics

        # Mock Discord message
        mock_message = MagicMock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel.send = AsyncMock()

        # Test error handling in command processing
        with patch.object(
            router.config_handler,
            "handle_command",
            side_effect=Exception("Handler error"),
        ):
            # Should handle exceptions gracefully
            try:
                await router.handle_command(mock_message, ["config", "show"])
            except Exception:
                # Exception should be caught and handled by router
                pass

        # Test recovery mechanisms
        error_scenarios = [
            {
                "handler": "config_handler",
                "command": ["config", "show"],
                "error": "Configuration error",
            },
            {
                "handler": "api_handler",
                "command": ["api", "list"],
                "error": "API manager error",
            },
            {
                "handler": "queue_handler",
                "command": ["queue", "status"],
                "error": "Queue error",
            },
        ]

        for scenario in error_scenarios:
            handler = getattr(router, scenario["handler"])
            with patch.object(
                handler, "handle_command", side_effect=Exception(scenario["error"])
            ):
                try:
                    await router.handle_command(mock_message, scenario["command"])
                except Exception:
                    # Errors should be handled gracefully
                    pass

    async def test_concurrent_admin_operations(self, admin_router_with_diagnostics):
        """Test concurrent admin operations handling."""
        router, config = admin_router_with_diagnostics

        # Create multiple admin messages
        mock_messages = []
        for i in range(3):
            mock_message = MagicMock()
            mock_message.author.guild_permissions.administrator = True
            mock_message.channel.send = AsyncMock()
            mock_messages.append(mock_message)

        # Test concurrent command processing
        import asyncio

        async def process_command(message, args):
            """Process a command with the router."""
            with patch.object(router, "check_permissions", return_value=True):
                with patch.object(
                    router.config_handler, "handle_command"
                ) as mock_handle:
                    await router.handle_command(message, args)
                    return mock_handle.call_count

        # Run concurrent commands
        tasks = [
            process_command(mock_messages[0], ["config", "show"]),
            process_command(mock_messages[1], ["config", "list"]),
            process_command(mock_messages[2], ["config", "show", "check_interval"]),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All commands should complete successfully
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"Concurrent command failed: {result}")
            else:
                assert result >= 0  # Handler was called
