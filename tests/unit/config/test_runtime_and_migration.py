"""
Unit tests for runtime configuration updates and migration functionality.
"""

from unittest.mock import mock_open, patch

import pytest

from ip_monitor.config import AppConfig


class TestAppConfigRuntimeUpdates:
    """Test runtime configuration update functionality."""

    @pytest.fixture
    def config(self, base_config):
        """Use the base_config fixture."""
        return base_config

    def test_runtime_config_field_validation_and_update(self, config):
        """Test complete workflow of validating and updating configuration fields."""
        # Test valid update
        validation_result = config.validate_config_value("max_retries", "7")
        assert validation_result["valid"] is True
        assert validation_result["converted_value"] == 7

        update_result = config.update_field(
            "max_retries", validation_result["converted_value"]
        )
        assert update_result is True
        assert config.max_retries == 7

    def test_runtime_config_boolean_field_updates(self, config):
        """Test runtime updates of boolean configuration fields."""
        boolean_fields = [
            "concurrent_api_checks",
            "circuit_breaker_enabled",
            "startup_message_enabled",
            "custom_apis_enabled",
            "message_queue_enabled",
            "cache_enabled",
        ]

        for field in boolean_fields:
            original_value = getattr(config, field)
            new_value = not original_value

            # Validate and update
            validation_result = config.validate_config_value(
                field, str(new_value).lower()
            )
            assert validation_result["valid"] is True
            assert validation_result["converted_value"] == new_value

            update_result = config.update_field(
                field, validation_result["converted_value"]
            )
            assert update_result is True
            assert getattr(config, field) == new_value

            # Restore original value
            config.update_field(field, original_value)

    def test_runtime_config_numeric_field_updates(self, config):
        """Test runtime updates of numeric configuration fields."""
        numeric_test_cases = [
            ("max_retries", 5),
            ("retry_delay", 10),
            ("ip_history_size", 15),
            ("rate_limit_period", 600),
            ("max_checks_per_period", 20),
            ("circuit_breaker_failure_threshold", 5),
            ("message_queue_max_size", 2000),
            ("message_queue_max_age_hours", 48),
            ("message_queue_batch_size", 10),
            ("connection_pool_size", 20),
            ("connection_pool_max_keepalive", 10),
            ("cache_ttl", 600),
            ("cache_max_memory_size", 2000),
            ("cache_cleanup_interval", 600),
        ]

        for field, new_value in numeric_test_cases:
            original_value = getattr(config, field)

            # Validate and update
            validation_result = config.validate_config_value(field, str(new_value))
            assert validation_result["valid"] is True, (
                f"Validation failed for {field} with value {new_value}"
            )
            assert validation_result["converted_value"] == new_value

            update_result = config.update_field(
                field, validation_result["converted_value"]
            )
            assert update_result is True
            assert getattr(config, field) == new_value

            # Restore original value
            config.update_field(field, original_value)

    def test_runtime_config_float_field_updates(self, config):
        """Test runtime updates of float configuration fields."""
        float_test_cases = [
            ("circuit_breaker_recovery_timeout", 180.5),
            ("message_queue_process_interval", 2.5),
            ("connection_timeout", 15.0),
            ("read_timeout", 45.0),
            ("cache_stale_threshold", 0.9),
        ]

        for field, new_value in float_test_cases:
            original_value = getattr(config, field)

            # Validate and update
            validation_result = config.validate_config_value(field, str(new_value))
            assert validation_result["valid"] is True, (
                f"Validation failed for {field} with value {new_value}"
            )
            assert validation_result["converted_value"] == new_value

            update_result = config.update_field(
                field, validation_result["converted_value"]
            )
            assert update_result is True
            assert getattr(config, field) == new_value

            # Restore original value
            config.update_field(field, original_value)

    def test_runtime_config_validation_prevents_invalid_updates(self, config):
        """Test that validation prevents invalid runtime updates."""
        invalid_test_cases = [
            ("max_retries", "0"),  # Below minimum
            ("max_retries", "15"),  # Above maximum
            ("circuit_breaker_recovery_timeout", "5.0"),  # Below minimum
            ("circuit_breaker_recovery_timeout", "4000.0"),  # Above maximum
            ("cache_stale_threshold", "1.5"),  # Above maximum
            ("cache_stale_threshold", "-0.1"),  # Below minimum
            ("concurrent_api_checks", "maybe"),  # Invalid boolean
        ]

        for field, invalid_value in invalid_test_cases:
            original_value = getattr(config, field)

            # Validation should fail
            validation_result = config.validate_config_value(field, invalid_value)
            assert validation_result["valid"] is False, (
                f"Validation should have failed for {field} with value {invalid_value}"
            )
            assert validation_result["converted_value"] is None
            assert validation_result["error"] is not None

            # Original value should be unchanged
            assert getattr(config, field) == original_value

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_runtime_config_persistence_workflow(
        self, mock_json_dump, mock_file, config
    ):
        """Test complete workflow of runtime config changes with persistence."""
        # Make runtime changes
        config.update_field("max_retries", 7)
        config.update_field("concurrent_api_checks", False)
        config.update_field("cache_ttl", 600)

        # Save configuration
        result = config.save_to_file("runtime_config.json")
        assert result is True

        # Verify saved data excludes sensitive information
        saved_data = mock_json_dump.call_args[0][0]
        assert "discord_token" not in saved_data
        assert saved_data["max_retries"] == 7
        assert saved_data["concurrent_api_checks"] is False
        assert saved_data["cache_ttl"] == 600
        assert "cache_info" in saved_data


class TestAppConfigMigration:
    """Test configuration migration functionality and legacy format handling."""

    @pytest.fixture
    def base_config(self):
        """Create a base configuration for migration testing."""
        return AppConfig(
            discord_token="test_token",
            channel_id=123456789,
            check_interval=30,
            max_retries=3,
            retry_delay=5,
            concurrent_api_checks=True,
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=120.0,
            rate_limit_period=300,
            max_checks_per_period=10,
            db_file="test.db",
            ip_file="test_ip.json",
            ip_history_file="test_history.json",
            ip_history_size=10,
            startup_message_enabled=True,
            testing_mode=False,
            log_level="INFO",
            custom_apis_enabled=True,
            api_config_file="test_apis.json",
            message_queue_enabled=True,
            message_queue_max_size=1000,
            message_queue_max_age_hours=24,
            message_queue_batch_size=5,
            message_queue_process_interval=1.0,
            connection_pool_size=10,
            connection_pool_max_keepalive=5,
            connection_timeout=10.0,
            read_timeout=30.0,
            cache_enabled=True,
            cache_ttl=300,
            cache_max_memory_size=1000,
            cache_stale_threshold=0.8,
            cache_file="test_cache.json",
            cache_cleanup_interval=300,
        )

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"check_interval": 45, "max_retries": 5}',
    )
    @patch("json.load")
    def test_migration_with_partial_config_override(
        self, mock_json_load, mock_file, mock_exists, base_config
    ):
        """Test migration with partial configuration override."""
        partial_config_data = {"check_interval": 45, "max_retries": 5}
        mock_json_load.return_value = partial_config_data

        result = AppConfig.load_from_file("partial_config.json", base_config)

        # Changed values should be updated
        assert result.check_interval == 45
        assert result.max_retries == 5

        # Unchanged values should remain from base config
        assert result.discord_token == base_config.discord_token
        assert result.channel_id == base_config.channel_id
        assert result.retry_delay == base_config.retry_delay

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_migration_with_new_fields_added(
        self, mock_json_load, mock_file, mock_exists, base_config
    ):
        """Test migration when new fields are added to the configuration."""
        # Simulate old config missing new fields
        old_config_data = {
            "check_interval": 45,
            "max_retries": 5,
            "retry_delay": 8,
            # Missing newer fields like cache_* and message_queue_*
        }
        mock_json_load.return_value = old_config_data

        result = AppConfig.load_from_file("old_format_config.json", base_config)

        # Old fields should be updated
        assert result.check_interval == 45
        assert result.max_retries == 5
        assert result.retry_delay == 8

        # New fields should use base config defaults
        assert result.cache_enabled == base_config.cache_enabled
        assert result.cache_ttl == base_config.cache_ttl
        assert result.message_queue_enabled == base_config.message_queue_enabled

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.load")
    def test_migration_preserves_data_types(
        self, mock_json_load, mock_file, mock_exists, base_config
    ):
        """Test that migration preserves correct data types."""
        config_data = {
            "check_interval": 45,  # int
            "max_retries": 5,  # int
            "circuit_breaker_recovery_timeout": 180.5,  # float
            "concurrent_api_checks": False,  # bool
            "cache_stale_threshold": 0.9,  # float
        }
        mock_json_load.return_value = config_data

        result = AppConfig.load_from_file("typed_config.json", base_config)

        # Verify types are preserved
        assert isinstance(result.check_interval, int)
        assert isinstance(result.max_retries, int)
        assert isinstance(result.circuit_breaker_recovery_timeout, float)
        assert isinstance(result.concurrent_api_checks, bool)
        assert isinstance(result.cache_stale_threshold, float)

        # Verify values
        assert result.check_interval == 45
        assert result.max_retries == 5
        assert result.circuit_breaker_recovery_timeout == 180.5
        assert result.concurrent_api_checks is False
        assert result.cache_stale_threshold == 0.9

    def test_migration_validation_after_load(self, base_config):
        """Test that loaded configuration values are valid after migration."""
        # Test that a migrated config passes validation
        fields_to_validate = [
            "check_interval",
            "max_retries",
            "retry_delay",
            "concurrent_api_checks",
            "circuit_breaker_enabled",
            "circuit_breaker_failure_threshold",
            "circuit_breaker_recovery_timeout",
            "rate_limit_period",
            "max_checks_per_period",
            "ip_history_size",
            "startup_message_enabled",
            "custom_apis_enabled",
            "cache_enabled",
            "cache_ttl",
            "cache_stale_threshold",
        ]

        for field in fields_to_validate:
            current_value = getattr(base_config, field)
            validation_result = base_config.validate_config_value(
                field, str(current_value)
            )

            assert validation_result["valid"] is True, (
                f"Field {field} with value {current_value} failed validation after migration"
            )
            assert validation_result["error"] is None
