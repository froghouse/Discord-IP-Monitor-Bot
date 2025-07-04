"""
Tests for the ConfigHandler class.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import discord

from ip_monitor.commands.admin_commands.config_handler import ConfigHandler
from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage


class TestConfigHandler:
    """Test cases for ConfigHandler class."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for ConfigHandler."""
        client = Mock(spec=discord.Client)
        ip_service = Mock(spec=IPService)
        ip_service.max_retries = 3
        ip_service.retry_delay = 30
        ip_service.concurrent_api_checks = True
        ip_service.circuit_breaker = Mock()
        ip_service.circuit_breaker.enabled = True
        ip_service.circuit_breaker.failure_threshold = 3
        ip_service.circuit_breaker.recovery_timeout = 120

        storage = Mock(spec=IPStorage)
        stop_callback = AsyncMock()

        config = Mock(spec=AppConfig)
        config.check_interval = 300
        config.max_retries = 3
        config.retry_delay = 30
        config.concurrent_api_checks = True
        config.circuit_breaker_enabled = True
        config.circuit_breaker_failure_threshold = 3
        config.circuit_breaker_recovery_timeout = 120
        config.rate_limit_period = 300
        config.max_checks_per_period = 10
        config.ip_history_size = 10
        config.startup_message_enabled = True
        config.message_queue_enabled = True
        config.message_queue_max_size = 1000
        config.message_queue_max_age_hours = 24
        config.message_queue_batch_size = 5
        config.message_queue_process_interval = 1.0

        # Mock config methods
        config.get_field_info = Mock()
        config.validate_config_value = Mock()
        config.update_field = Mock()
        config.get_runtime_configurable_fields = Mock()
        config.save_to_file = Mock()

        return {
            "client": client,
            "ip_service": ip_service,
            "storage": storage,
            "stop_callback": stop_callback,
            "config": config,
        }

    @pytest.fixture
    def handler(self, mock_dependencies):
        """Create a ConfigHandler instance."""
        return ConfigHandler(**mock_dependencies)

    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.author.__str__ = Mock(return_value="TestUser")
        message.channel = Mock()
        return message

    @pytest.fixture
    def mock_non_admin_message(self):
        """Create a mock Discord message from non-admin user."""
        message = Mock(spec=discord.Message)
        message.author = Mock()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = False
        message.channel = Mock()
        return message

    def test_init(self, mock_dependencies):
        """Test ConfigHandler initialization."""
        handler = ConfigHandler(**mock_dependencies)

        assert handler.client == mock_dependencies["client"]
        assert handler.ip_service == mock_dependencies["ip_service"]
        assert handler.storage == mock_dependencies["storage"]
        assert handler.stop_callback == mock_dependencies["stop_callback"]
        assert handler.config == mock_dependencies["config"]

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
    async def test_handle_command_config(self, handler, mock_message):
        """Test handle_command with config command."""
        with patch.object(
            handler, "_handle_config_command", return_value=True
        ) as mock_config:
            result = await handler.handle_command(mock_message, ["config", "show"])

            assert result is True
            mock_config.assert_called_once_with(mock_message, ["show"])

    @pytest.mark.asyncio
    async def test_handle_config_command_no_permissions(
        self, handler, mock_non_admin_message
    ):
        """Test _handle_config_command when user doesn't have permissions."""
        with patch.object(handler, "send_permission_denied") as mock_send_denied:
            result = await handler._handle_config_command(mock_non_admin_message, [])

            assert result is False
            mock_send_denied.assert_called_once_with(mock_non_admin_message)

    @pytest.mark.asyncio
    async def test_handle_config_command_no_args_shows_help(
        self, handler, mock_message
    ):
        """Test _handle_config_command with no arguments shows help."""
        with patch.object(
            handler, "_get_config_help_text", return_value="Help text"
        ) as mock_help:
            with patch.object(
                handler.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                result = await handler._handle_config_command(mock_message, [])

                assert result is True
                mock_help.assert_called_once()
                mock_send.assert_called_once_with(mock_message.channel, "Help text")

    @pytest.mark.asyncio
    async def test_handle_config_show_all(self, handler, mock_message):
        """Test _handle_config_show without specific field."""
        with patch.object(
            handler, "_format_all_configuration", return_value="Config text"
        ) as mock_format:
            with patch.object(
                handler, "truncate_message", return_value="Config text"
            ) as mock_truncate:
                with patch.object(
                    handler.discord_rate_limiter, "send_message_with_backoff"
                ) as mock_send:
                    result = await handler._handle_config_show(mock_message, None)

                    assert result is True
                    mock_format.assert_called_once()
                    mock_truncate.assert_called_once_with("Config text")
                    mock_send.assert_called_once_with(
                        mock_message.channel, "Config text"
                    )

    @pytest.mark.asyncio
    async def test_handle_config_show_specific_field(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_show with specific field."""
        field_info = {
            "type": "int",
            "description": "Test field",
            "range": "1-100",
            "unit": "seconds",
            "restart_required": True,
        }
        mock_dependencies["config"].get_field_info.return_value = field_info

        with patch.object(
            handler.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            result = await handler._handle_config_show(mock_message, "test_field")

            assert result is True
            mock_dependencies["config"].get_field_info.assert_called_once_with(
                "test_field"
            )
            mock_send.assert_called_once()

            # Verify the sent message contains field information
            sent_message = mock_send.call_args[0][1]
            assert "Configuration Field: test_field" in sent_message
            assert "Type: int" in sent_message
            assert "Description: Test field" in sent_message
            assert "Range: 1-100" in sent_message
            assert "Unit: seconds" in sent_message
            assert "Restart required" in sent_message

    @pytest.mark.asyncio
    async def test_handle_config_show_unknown_field(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_show with unknown field."""
        mock_dependencies["config"].get_field_info.return_value = None

        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_show(mock_message, "unknown_field")

            assert result is False
            mock_send_error.assert_called_once_with(
                mock_message, "Unknown configuration field: unknown_field"
            )

    @pytest.mark.asyncio
    async def test_handle_config_set_invalid_args(self, handler, mock_message):
        """Test _handle_config_command set with invalid arguments."""
        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_command(
                mock_message, ["set", "field"]
            )

            assert result is False
            mock_send_error.assert_called_once_with(
                mock_message, "Usage: !config set <field> <value>"
            )

    @pytest.mark.asyncio
    async def test_handle_config_set_validation_failed(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_set with validation failure."""
        mock_dependencies["config"].validate_config_value.return_value = {
            "valid": False,
            "error": "Invalid value",
        }

        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_set(mock_message, "field", "value")

            assert result is False
            mock_send_error.assert_called_once_with(mock_message, "Invalid value")

    @pytest.mark.asyncio
    async def test_handle_config_set_success(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_set with successful update."""
        mock_dependencies["config"].validate_config_value.return_value = {
            "valid": True,
            "converted_value": 5,
        }
        mock_dependencies["config"].get_field_info.return_value = {
            "restart_required": False
        }

        with patch.object(handler, "_apply_config_change") as mock_apply:
            with patch.object(handler, "send_success_message") as mock_send_success:
                result = await handler._handle_config_set(
                    mock_message, "max_retries", "5"
                )

                assert result is True
                mock_dependencies[
                    "config"
                ].validate_config_value.assert_called_once_with("max_retries", "5")
                mock_dependencies["config"].update_field.assert_called_once_with(
                    "max_retries", 5
                )
                mock_apply.assert_called_once_with("max_retries", 5)
                mock_send_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_config_set_restart_required(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_set with restart required warning."""
        mock_dependencies["config"].validate_config_value.return_value = {
            "valid": True,
            "converted_value": 600,
        }
        mock_dependencies["config"].get_field_info.return_value = {
            "restart_required": True
        }

        with patch.object(handler, "_apply_config_change"):
            with patch.object(handler, "send_success_message") as mock_send_success:
                result = await handler._handle_config_set(
                    mock_message, "check_interval", "600"
                )

                assert result is True
                success_message = mock_send_success.call_args[0][1]
                assert "Restart required" in success_message

    @pytest.mark.asyncio
    async def test_handle_config_set_exception(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_set with exception during update."""
        mock_dependencies["config"].validate_config_value.return_value = {
            "valid": True,
            "converted_value": 5,
        }
        mock_dependencies["config"].update_field.side_effect = Exception(
            "Update failed"
        )

        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_set(mock_message, "field", "value")

            assert result is False
            mock_send_error.assert_called_once()
            error_message = mock_send_error.call_args[0][1]
            assert "Failed to update configuration" in error_message

    @pytest.mark.asyncio
    async def test_handle_config_list_no_fields(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_list with no configurable fields."""
        mock_dependencies["config"].get_runtime_configurable_fields.return_value = {}

        with patch.object(handler, "send_info_message") as mock_send_info:
            result = await handler._handle_config_list(mock_message)

            assert result is True
            mock_send_info.assert_called_once_with(
                mock_message, "No configurable fields available"
            )

    @pytest.mark.asyncio
    async def test_handle_config_list_success(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_list with configurable fields."""
        fields = {
            "max_retries": {
                "type": "int",
                "description": "Maximum retry attempts",
                "range": "1-10",
                "restart_required": False,
            },
            "check_interval": {
                "type": "int",
                "description": "Check interval in minutes",
                "restart_required": True,
            },
        }
        mock_dependencies[
            "config"
        ].get_runtime_configurable_fields.return_value = fields

        with patch.object(
            handler, "truncate_message", return_value="List text"
        ) as mock_truncate:
            with patch.object(
                handler.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                result = await handler._handle_config_list(mock_message)

                assert result is True
                mock_truncate.assert_called_once()
                mock_send.assert_called_once_with(mock_message.channel, "List text")

    @pytest.mark.asyncio
    async def test_handle_config_save_success(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_save successful save."""
        with patch.object(handler, "send_success_message") as mock_send_success:
            result = await handler._handle_config_save(mock_message)

            assert result is True
            mock_dependencies["config"].save_to_file.assert_called_once()
            mock_send_success.assert_called_once_with(
                mock_message, "Configuration saved to bot_config.json"
            )

    @pytest.mark.asyncio
    async def test_handle_config_save_exception(
        self, handler, mock_message, mock_dependencies
    ):
        """Test _handle_config_save with exception."""
        mock_dependencies["config"].save_to_file.side_effect = Exception("Save failed")

        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_save(mock_message)

            assert result is False
            mock_send_error.assert_called_once()
            error_message = mock_send_error.call_args[0][1]
            assert "Failed to save configuration" in error_message

    @pytest.mark.asyncio
    async def test_handle_config_reload(self, handler, mock_message):
        """Test _handle_config_reload."""
        with patch.object(handler, "send_info_message") as mock_send_info:
            result = await handler._handle_config_reload(mock_message)

            assert result is True
            mock_send_info.assert_called_once()
            info_message = mock_send_info.call_args[0][1]
            assert "Configuration reload requested" in info_message

    @pytest.mark.asyncio
    async def test_handle_config_command_unknown_subcommand(
        self, handler, mock_message
    ):
        """Test _handle_config_command with unknown subcommand."""
        with patch.object(handler, "send_error_message") as mock_send_error:
            result = await handler._handle_config_command(mock_message, ["unknown"])

            assert result is False
            mock_send_error.assert_called_once_with(
                mock_message, "Unknown config subcommand: unknown"
            )

    @pytest.mark.asyncio
    async def test_handle_config_command_exception(self, handler, mock_message):
        """Test _handle_config_command with exception."""
        with patch.object(
            handler, "_handle_config_show", side_effect=Exception("Test error")
        ):
            with patch.object(handler, "handle_command_error") as mock_handle_error:
                result = await handler._handle_config_command(mock_message, ["show"])

                assert result is False
                mock_handle_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_config_change_ip_service_fields(
        self, handler, mock_dependencies
    ):
        """Test _apply_config_change for IP service fields."""
        # Test max_retries
        await handler._apply_config_change("max_retries", 5)
        assert mock_dependencies["ip_service"].max_retries == 5

        # Test retry_delay
        await handler._apply_config_change("retry_delay", 60)
        assert mock_dependencies["ip_service"].retry_delay == 60

        # Test concurrent_api_checks
        await handler._apply_config_change("concurrent_api_checks", False)
        assert mock_dependencies["ip_service"].concurrent_api_checks is False

    @pytest.mark.asyncio
    async def test_apply_config_change_circuit_breaker_fields(
        self, handler, mock_dependencies
    ):
        """Test _apply_config_change for circuit breaker fields."""
        # Test circuit_breaker_enabled
        await handler._apply_config_change("circuit_breaker_enabled", False)
        assert mock_dependencies["ip_service"].circuit_breaker.enabled is False

        # Test circuit_breaker_failure_threshold
        await handler._apply_config_change("circuit_breaker_failure_threshold", 5)
        assert mock_dependencies["ip_service"].circuit_breaker.failure_threshold == 5

        # Test circuit_breaker_recovery_timeout
        await handler._apply_config_change("circuit_breaker_recovery_timeout", 300)
        assert mock_dependencies["ip_service"].circuit_breaker.recovery_timeout == 300

    @pytest.mark.asyncio
    async def test_apply_config_change_message_queue_fields(self, handler):
        """Test _apply_config_change for message queue fields."""
        with patch(
            "ip_monitor.commands.admin_commands.config_handler.message_queue"
        ) as mock_queue:
            # Test message_queue_enabled
            await handler._apply_config_change("message_queue_enabled", False)
            assert mock_queue.enabled is False

            # Test message_queue_max_size
            await handler._apply_config_change("message_queue_max_size", 2000)
            assert mock_queue.max_size == 2000

    def test_format_all_configuration(self, handler, mock_dependencies):
        """Test _format_all_configuration method."""
        result = handler._format_all_configuration()

        assert "Current Configuration:" in result
        assert "IP Monitoring:" in result
        assert "Circuit Breaker:" in result
        assert "Rate Limiting:" in result
        assert "Storage:" in result
        assert "Messages:" in result
        assert "Message Queue:" in result
        assert str(mock_dependencies["config"].check_interval) in result

    def test_get_config_help_text(self, handler):
        """Test _get_config_help_text method."""
        result = handler._get_config_help_text()

        assert "Configuration Commands:" in result
        assert "!config show" in result
        assert "!config set" in result
        assert "!config list" in result
        assert "!config save" in result
        assert "!config reload" in result
        assert "Examples:" in result

    def test_get_help_text(self, handler):
        """Test get_help_text method."""
        result = handler.get_help_text()

        assert "Configuration Commands:" in result
        assert "!config show" in result
