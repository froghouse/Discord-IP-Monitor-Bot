"""
Unit tests for configuration edge cases and error handling scenarios.
"""

import os
from unittest.mock import mock_open, patch

import pytest

from ip_monitor.config import AppConfig


class TestAppConfigValidationErrorHandling:
    """Test configuration validation and error handling edge cases."""

    @pytest.fixture
    def config(self, base_config):
        """Use the base_config fixture."""
        return base_config

    def test_validate_config_value_empty_string(self, config):
        """Test validation with empty string values."""
        result = config.validate_config_value("max_retries", "")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid int value" in result["error"]

    def test_validate_config_value_whitespace_only(self, config):
        """Test validation with whitespace-only values."""
        result = config.validate_config_value("max_retries", "   ")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid int value" in result["error"]

    def test_validate_config_value_float_with_scientific_notation(self, config):
        """Test validation of float values with scientific notation."""
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "1.5e2"
        )

        assert result["valid"] is True
        assert result["converted_value"] == 150.0
        assert result["error"] is None

    def test_validate_config_value_integer_with_decimal(self, config):
        """Test validation of integer field with decimal value."""
        result = config.validate_config_value("max_retries", "3.0")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid int value" in result["error"]

    def test_validate_config_value_boolean_mixed_case(self, config):
        """Test validation of boolean values with mixed case."""
        mixed_case_values = ["True", "FALSE", "Yes", "NO", "On", "oFF"]
        expected_results = [True, False, True, False, True, False]

        for value, expected in zip(mixed_case_values, expected_results, strict=False):
            result = config.validate_config_value("concurrent_api_checks", value)
            assert result["valid"] is True
            assert result["converted_value"] is expected
            assert result["error"] is None

    def test_validate_config_value_boolean_numeric_string(self, config):
        """Test validation of boolean values with numeric strings."""
        result_true = config.validate_config_value("concurrent_api_checks", "1")
        result_false = config.validate_config_value("concurrent_api_checks", "0")

        assert result_true["valid"] is True
        assert result_true["converted_value"] is True

        assert result_false["valid"] is True
        assert result_false["converted_value"] is False

    def test_validate_config_value_boolean_invalid_numeric(self, config):
        """Test validation of boolean values with invalid numeric strings."""
        invalid_values = ["2", "-1", "10", "0.5"]

        for value in invalid_values:
            result = config.validate_config_value("concurrent_api_checks", value)
            assert result["valid"] is False
            assert result["converted_value"] is None
            assert "Invalid boolean value" in result["error"]

    def test_validate_config_value_extreme_values(self, config):
        """Test validation with extreme boundary values."""
        # Test maximum integer value
        result = config.validate_config_value("max_retries", "10")
        assert result["valid"] is True
        assert result["converted_value"] == 10

        # Test minimum integer value
        result = config.validate_config_value("max_retries", "1")
        assert result["valid"] is True
        assert result["converted_value"] == 1

        # Test maximum float value
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "3600.0"
        )
        assert result["valid"] is True
        assert result["converted_value"] == 3600.0

        # Test minimum float value
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "10.0"
        )
        assert result["valid"] is True
        assert result["converted_value"] == 10.0

    def test_validate_config_value_precision_float(self, config):
        """Test validation of float values with high precision."""
        result = config.validate_config_value("cache_stale_threshold", "0.123456789")

        assert result["valid"] is True
        assert abs(result["converted_value"] - 0.123456789) < 1e-9
        assert result["error"] is None

    def test_validate_config_value_unsupported_field_type(self, config):
        """Test validation handling of unsupported field types."""
        # Mock a field with unsupported type
        with patch.object(config, "get_runtime_configurable_fields") as mock_fields:
            mock_fields.return_value = {
                "unsupported_field": {
                    "type": "list",
                    "description": "Unsupported type for testing",
                }
            }

            result = config.validate_config_value("unsupported_field", "value")

            assert result["valid"] is False
            assert result["converted_value"] is None
            assert "Unsupported field type" in result["error"]

    def test_update_field_with_invalid_field_name(self, config):
        """Test updating field with non-existent field name."""
        result = config.update_field("non_existent_field", "value")

        assert result is False
        assert not hasattr(config, "non_existent_field")

    def test_update_field_with_none_value(self, config):
        """Test updating field with None value."""
        original_value = config.max_retries
        result = config.update_field("max_retries", None)

        assert result is True
        assert config.max_retries is None

        # Restore original value
        config.max_retries = original_value

    def test_get_field_info_case_sensitivity(self, config):
        """Test that field info lookup is case sensitive."""
        # Correct case
        field_info = config.get_field_info("max_retries")
        assert field_info != {}

        # Wrong case
        field_info_wrong = config.get_field_info("MAX_RETRIES")
        assert field_info_wrong == {}

        field_info_mixed = config.get_field_info("Max_Retries")
        assert field_info_mixed == {}

    def test_get_runtime_configurable_fields_completeness(self, config):
        """Test that all expected fields are present in runtime configurable fields."""
        fields = config.get_runtime_configurable_fields()

        expected_fields = [
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
            "message_queue_enabled",
            "message_queue_max_size",
            "message_queue_max_age_hours",
            "message_queue_batch_size",
            "message_queue_process_interval",
            "connection_pool_size",
            "connection_pool_max_keepalive",
            "connection_timeout",
            "read_timeout",
            "cache_enabled",
            "cache_ttl",
            "cache_max_memory_size",
            "cache_stale_threshold",
            "cache_cleanup_interval",
        ]

        for field in expected_fields:
            assert field in fields, (
                f"Field {field} not found in runtime configurable fields"
            )
            assert "type" in fields[field], f"Field {field} missing type information"
            assert "description" in fields[field], f"Field {field} missing description"

    def test_get_runtime_configurable_fields_field_metadata(self, config):
        """Test that runtime configurable fields have proper metadata."""
        fields = config.get_runtime_configurable_fields()

        for field_name, field_info in fields.items():
            # All fields should have type and description
            assert "type" in field_info, f"Field {field_name} missing type"
            assert "description" in field_info, (
                f"Field {field_name} missing description"
            )

            # Numeric fields should have min/max values
            if field_info["type"] in ["int", "float"]:
                assert "min_value" in field_info, (
                    f"Numeric field {field_name} missing min_value"
                )
                assert "max_value" in field_info, (
                    f"Numeric field {field_name} missing max_value"
                )
                assert field_info["min_value"] < field_info["max_value"], (
                    f"Field {field_name} has invalid range"
                )

            # Boolean fields should not have min/max values
            if field_info["type"] == "bool":
                assert "min_value" not in field_info, (
                    f"Boolean field {field_name} should not have min_value"
                )
                assert "max_value" not in field_info, (
                    f"Boolean field {field_name} should not have max_value"
                )

    def test_to_dict_completeness(self, config):
        """Test that to_dict returns all configuration fields."""
        config_dict = config.to_dict()

        # Check that all dataclass fields are present
        expected_fields = [
            "discord_token",
            "channel_id",
            "check_interval",
            "max_retries",
            "retry_delay",
            "concurrent_api_checks",
            "circuit_breaker_enabled",
            "circuit_breaker_failure_threshold",
            "circuit_breaker_recovery_timeout",
            "rate_limit_period",
            "max_checks_per_period",
            "db_file",
            "ip_file",
            "ip_history_file",
            "ip_history_size",
            "startup_message_enabled",
            "testing_mode",
            "log_level",
            "custom_apis_enabled",
            "api_config_file",
            "message_queue_enabled",
            "message_queue_max_size",
            "message_queue_max_age_hours",
            "message_queue_batch_size",
            "message_queue_process_interval",
            "connection_pool_size",
            "connection_pool_max_keepalive",
            "connection_timeout",
            "read_timeout",
            "cache_enabled",
            "cache_ttl",
            "cache_max_memory_size",
            "cache_stale_threshold",
            "cache_file",
            "cache_cleanup_interval",
        ]

        for field in expected_fields:
            assert field in config_dict, f"Field {field} not found in to_dict output"

        # Check that values match
        assert config_dict["discord_token"] == config.discord_token
        assert config_dict["channel_id"] == config.channel_id
        assert config_dict["max_retries"] == config.max_retries
        assert config_dict["cache_enabled"] == config.cache_enabled

    def test_to_dict_immutability(self, config):
        """Test that modifying to_dict result doesn't affect original config."""
        config_dict = config.to_dict()
        original_max_retries = config.max_retries

        # Modify the dictionary
        config_dict["max_retries"] = 999

        # Original config should be unchanged
        assert config.max_retries == original_max_retries
        assert config.max_retries != 999


class TestAppConfigEdgeCases:
    """Test configuration edge cases and error scenarios."""

    @pytest.fixture(autouse=True)
    def setup_method(self, env_cleanup):
        """Use the env_cleanup fixture automatically for all tests."""

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_type_conversion_errors(self, mock_load_dotenv):
        """Test handling of type conversion errors during environment loading."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CHECK_INTERVAL"] = "invalid_number"

        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: invalid_number"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_float_conversion_errors(self, mock_load_dotenv):
        """Test handling of float conversion errors during environment loading."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CIRCUIT_BREAKER_RECOVERY_TIMEOUT"] = "not_a_float"

        with pytest.raises(ValueError, match="could not convert string to float"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_overflow_values(self, mock_load_dotenv):
        """Test handling of overflow values during environment loading."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["MAX_RETRIES"] = str(10**20)  # Very large number

        # This should not raise an error - Python handles large integers
        config = AppConfig.load_from_env()
        assert config.max_retries == 10**20

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_negative_values(self, mock_load_dotenv):
        """Test validation of negative values during environment loading."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["MAX_RETRIES"] = "-5"

        # This should not raise an error during loading but will be caught during validation
        config = AppConfig.load_from_env()
        assert config.max_retries == -5

    @patch(
        "ip_monitor.config.load_dotenv", side_effect=Exception("Failed to load .env")
    )
    def test_load_from_env_with_dotenv_failure(self, mock_load_dotenv):
        """Test handling of dotenv loading failure."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"
        os.environ["CHANNEL_ID"] = "123456789"

        # Should still work even if dotenv fails (graceful degradation)
        config = AppConfig.load_from_env()
        assert config.discord_token == "test_token"
        assert config.channel_id == 123456789

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_unicode_values(self, mock_load_dotenv):
        """Test handling of unicode values in environment variables."""
        os.environ["DISCORD_BOT_TOKEN"] = "tëst_tøkén_123"
        os.environ["CHANNEL_ID"] = "123456789"

        config = AppConfig.load_from_env()
        assert config.discord_token == "tëst_tøkén_123"

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_special_characters(self, mock_load_dotenv):
        """Test handling of special characters in environment variables."""
        os.environ["DISCORD_BOT_TOKEN"] = "token_with_!@#$%^&*()_+-=[]{}|;:,.<>?"
        os.environ["CHANNEL_ID"] = "123456789"

        config = AppConfig.load_from_env()
        assert config.discord_token == "token_with_!@#$%^&*()_+-=[]{}|;:,.<>?"

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_with_very_long_values(self, mock_load_dotenv):
        """Test handling of very long environment variable values."""
        long_token = "a" * 10000  # Very long token
        os.environ["DISCORD_BOT_TOKEN"] = long_token
        os.environ["CHANNEL_ID"] = "123456789"

        config = AppConfig.load_from_env()
        assert config.discord_token == long_token
        assert len(config.discord_token) == 10000


class TestAppConfigFileHandlingEdgeCases:
    """Test configuration file handling edge cases and error scenarios."""

    @pytest.fixture
    def config(self, base_config):
        """Use the base_config fixture."""
        return base_config

    @patch("builtins.open", new_callable=mock_open)
    @patch(
        "json.dump", side_effect=TypeError("Object of type X is not JSON serializable")
    )
    @patch("ip_monitor.config.logger")
    def test_save_to_file_json_encode_error(
        self, mock_logger, mock_json_dump, mock_file, config
    ):
        """Test configuration save with JSON encoding error."""
        result = config.save_to_file("test_config.json")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "Failed to save config" in mock_logger.error.call_args[0][0]

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    @patch("ip_monitor.config.logger")
    def test_save_to_file_permission_error(self, mock_logger, mock_file, config):
        """Test configuration save with permission error."""
        result = config.save_to_file("/root/config.json")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "Failed to save config" in mock_logger.error.call_args[0][0]

    @patch("builtins.open", side_effect=OSError("Disk full"))
    @patch("ip_monitor.config.logger")
    def test_save_to_file_disk_full_error(self, mock_logger, mock_file, config):
        """Test configuration save with disk full error."""
        result = config.save_to_file("test_config.json")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "Failed to save config" in mock_logger.error.call_args[0][0]

    @patch("os.path.exists", return_value=True)
    @patch("os.path.getmtime", return_value=1234567890.0)
    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_to_file_with_existing_file_timestamp(
        self, mock_json_dump, mock_file, mock_getmtime, mock_exists, config
    ):
        """Test configuration save with existing file timestamp."""
        result = config.save_to_file("existing_config.json")

        assert result is True
        mock_json_dump.assert_called_once()

        # Check that the saved data includes cache_info with timestamp
        saved_data = mock_json_dump.call_args[0][0]
        assert "cache_info" in saved_data
        assert saved_data["cache_info"]["saved_at"] == 1234567890.0

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"corrupted": true, "max_retries": null}',
    )
    @patch("json.load")
    def test_load_from_file_with_null_values(
        self, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with null values in JSON."""
        mock_json_load.return_value = {"max_retries": None, "retry_delay": 10}

        # Dataclass accepts None values, so this should succeed with modified config
        result = AppConfig.load_from_file("test_config.json", config)
        assert result.max_retries is None
        assert result.retry_delay == 10
        assert result.discord_token == config.discord_token  # Other values preserved

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"unknown_field": "value", "max_retries": 5}',
    )
    @patch("json.load")
    @patch("ip_monitor.config.logger")
    def test_load_from_file_with_unknown_fields(
        self, mock_logger, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with unknown fields in JSON."""
        mock_json_load.return_value = {"unknown_field": "value", "max_retries": 5}

        # This should return base config and log an error
        result = AppConfig.load_from_file("test_config.json", config)
        assert result == config
        mock_logger.error.assert_called_once()
        assert "Failed to load config" in mock_logger.error.call_args[0][0]

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"max_retries": "not_a_number"}',
    )
    @patch("json.load")
    def test_load_from_file_with_wrong_type_values(
        self, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with wrong type values in JSON."""
        mock_json_load.return_value = {"max_retries": "not_a_number"}

        # Dataclass accepts string values even for int fields, so this should succeed
        result = AppConfig.load_from_file("test_config.json", config)
        assert result.max_retries == "not_a_number"
        assert result.discord_token == config.discord_token  # Other values preserved

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "Invalid character"),
    )
    @patch("ip_monitor.config.logger")
    def test_load_from_file_unicode_decode_error(
        self, mock_logger, mock_file, mock_exists, config
    ):
        """Test configuration load with unicode decode error."""
        result = AppConfig.load_from_file("test_config.json", config)

        assert result == config
        mock_logger.error.assert_called_once()
        assert "Failed to load config" in mock_logger.error.call_args[0][0]

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="{}")
    @patch("json.load")
    def test_load_from_file_empty_json_object(
        self, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with empty JSON object."""
        mock_json_load.return_value = {}

        result = AppConfig.load_from_file("test_config.json", config)

        # Should return the base config unchanged
        assert result == config

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="[]")
    @patch("json.load")
    @patch("ip_monitor.config.logger")
    def test_load_from_file_json_array_instead_of_object(
        self, mock_logger, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with JSON array instead of object."""
        mock_json_load.return_value = []

        # Arrays don't work as dict.update() source, so this should work without error
        # as an empty array acts like an empty dict
        result = AppConfig.load_from_file("test_config.json", config)
        assert result == config  # Should still return base config
