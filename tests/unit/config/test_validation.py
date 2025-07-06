"""
Unit tests for configuration validation functionality.
"""

import pytest

from ip_monitor.config import AppConfig


class TestAppConfigValidation:
    """Test configuration validation functionality."""

    @pytest.fixture
    def config(self, base_config):
        """Use the base_config fixture."""
        return base_config

    def test_validate_config_value_valid_integer(self, config):
        """Test validating a valid integer value."""
        result = config.validate_config_value("max_retries", "5")

        assert result["valid"] is True
        assert result["converted_value"] == 5
        assert result["error"] is None

    def test_validate_config_value_invalid_integer(self, config):
        """Test validating an invalid integer value."""
        result = config.validate_config_value("max_retries", "not_a_number")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid int value" in result["error"]

    def test_validate_config_value_integer_below_minimum(self, config):
        """Test validating an integer below minimum."""
        result = config.validate_config_value("max_retries", "0")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "below minimum" in result["error"]

    def test_validate_config_value_integer_above_maximum(self, config):
        """Test validating an integer above maximum."""
        result = config.validate_config_value("max_retries", "15")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "above maximum" in result["error"]

    def test_validate_config_value_valid_float(self, config):
        """Test validating a valid float value."""
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "180.5"
        )

        assert result["valid"] is True
        assert result["converted_value"] == 180.5
        assert result["error"] is None

    def test_validate_config_value_invalid_float(self, config):
        """Test validating an invalid float value."""
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "not_a_float"
        )

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid float value" in result["error"]

    def test_validate_config_value_float_below_minimum(self, config):
        """Test validating a float below minimum."""
        result = config.validate_config_value("circuit_breaker_recovery_timeout", "5.0")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "below minimum" in result["error"]

    def test_validate_config_value_float_above_maximum(self, config):
        """Test validating a float above maximum."""
        result = config.validate_config_value(
            "circuit_breaker_recovery_timeout", "4000.0"
        )

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "above maximum" in result["error"]

    def test_validate_config_value_valid_boolean_true_variations(self, config):
        """Test validating various true boolean values."""
        true_values = [
            "true",
            "yes",
            "1",
            "on",
            "enabled",
            "TRUE",
            "YES",
            "ON",
            "ENABLED",
        ]

        for value in true_values:
            result = config.validate_config_value("concurrent_api_checks", value)
            assert result["valid"] is True
            assert result["converted_value"] is True
            assert result["error"] is None

    def test_validate_config_value_valid_boolean_false_variations(self, config):
        """Test validating various false boolean values."""
        false_values = [
            "false",
            "no",
            "0",
            "off",
            "disabled",
            "FALSE",
            "NO",
            "OFF",
            "DISABLED",
        ]

        for value in false_values:
            result = config.validate_config_value("concurrent_api_checks", value)
            assert result["valid"] is True
            assert result["converted_value"] is False
            assert result["error"] is None

    def test_validate_config_value_invalid_boolean(self, config):
        """Test validating an invalid boolean value."""
        result = config.validate_config_value("concurrent_api_checks", "maybe")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "Invalid boolean value" in result["error"]

    def test_validate_config_value_non_configurable_field(self, config):
        """Test validating a non-configurable field."""
        result = config.validate_config_value("discord_token", "new_token")

        assert result["valid"] is False
        assert result["converted_value"] is None
        assert "not configurable at runtime" in result["error"]

    def test_get_field_info_existing_field(self, config):
        """Test getting field information for an existing field."""
        field_info = config.get_field_info("max_retries")

        assert field_info["type"] == "int"
        assert field_info["min_value"] == 1
        assert field_info["max_value"] == 10
        assert "Maximum retry attempts" in field_info["description"]

    def test_get_field_info_non_existing_field(self, config):
        """Test getting field information for a non-existing field."""
        field_info = config.get_field_info("non_existing_field")

        assert field_info == {}

    def test_update_field_existing_field(self, config):
        """Test updating an existing field."""
        result = config.update_field("max_retries", 7)

        assert result is True
        assert config.max_retries == 7

    def test_update_field_non_existing_field(self, config):
        """Test updating a non-existing field."""
        result = config.update_field("non_existing_field", "value")

        assert result is False

    def test_to_dict(self, config):
        """Test converting configuration to dictionary."""
        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict["discord_token"] == "test_token"
        assert config_dict["channel_id"] == 123456789
        assert config_dict["max_retries"] == 3
