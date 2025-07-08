"""
Unit tests for configuration management module.
"""

import json
import os
from unittest.mock import mock_open, patch

import pytest

from ip_monitor.config import AppConfig


class TestAppConfigEnvironmentVariableLoading:
    """Test environment variable loading functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Clear any existing environment variables
        self.env_vars_to_clear = [
            "DISCORD_BOT_TOKEN",
            "CHANNEL_ID",
            "CHECK_INTERVAL",
            "MAX_RETRIES",
            "RETRY_DELAY",
            "CONCURRENT_API_CHECKS",
            "CIRCUIT_BREAKER_ENABLED",
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            "CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
            "RATE_LIMIT_PERIOD",
            "MAX_CHECKS_PER_PERIOD",
            "DB_FILE",
            "IP_FILE",
            "IP_HISTORY_FILE",
            "IP_HISTORY_SIZE",
            "STARTUP_MESSAGE_ENABLED",
            "TESTING_MODE",
            "LOG_LEVEL",
            "CUSTOM_APIS_ENABLED",
            "API_CONFIG_FILE",
            "MESSAGE_QUEUE_ENABLED",
            "MESSAGE_QUEUE_MAX_SIZE",
            "MESSAGE_QUEUE_MAX_AGE_HOURS",
            "MESSAGE_QUEUE_BATCH_SIZE",
            "MESSAGE_QUEUE_PROCESS_INTERVAL",
            "CONNECTION_POOL_SIZE",
            "CONNECTION_POOL_MAX_KEEPALIVE",
            "CONNECTION_TIMEOUT",
            "READ_TIMEOUT",
            "CACHE_ENABLED",
            "CACHE_TTL",
            "CACHE_MAX_MEMORY_SIZE",
            "CACHE_STALE_THRESHOLD",
            "CACHE_FILE",
            "CACHE_CLEANUP_INTERVAL",
        ]

        # Store original values
        self.original_env_values = {}
        for var in self.env_vars_to_clear:
            self.original_env_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
            if self.original_env_values[var] is not None:
                os.environ[var] = self.original_env_values[var]

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_required_fields_present(self, mock_load_dotenv):
        """Test successful loading with all required fields present."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"

        config = AppConfig.load_from_env()

        assert config.discord_token == "test_token_123"
        assert config.channel_id == 123456789
        assert config.check_interval == AppConfig.DEFAULT_CHECK_INTERVAL
        assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES
        mock_load_dotenv.assert_called_once()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_missing_discord_token(self, mock_load_dotenv):
        """Test failure when DISCORD_BOT_TOKEN is missing."""
        os.environ["CHANNEL_ID"] = "123456789"

        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN not set"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_empty_discord_token(self, mock_load_dotenv):
        """Test failure when DISCORD_BOT_TOKEN is empty."""
        os.environ["DISCORD_BOT_TOKEN"] = ""
        os.environ["CHANNEL_ID"] = "123456789"

        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN not set"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_channel_id_non_numeric(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is not numeric."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "not_a_number"

        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: not_a_number"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_channel_id_negative(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is negative."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "-123"

        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: -123"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_channel_id_zero(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is zero."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "0"

        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: 0"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_default_channel_id(self, mock_load_dotenv):
        """Test behavior when CHANNEL_ID is not provided (uses default 0)."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"

        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: 0"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_custom_check_interval(self, mock_load_dotenv):
        """Test loading with custom check interval."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CHECK_INTERVAL"] = "60"

        config = AppConfig.load_from_env()

        assert config.check_interval == 60

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_check_interval_non_numeric(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is not numeric."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CHECK_INTERVAL"] = "not_a_number"

        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: not_a_number"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_check_interval_negative(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is negative."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CHECK_INTERVAL"] = "-10"

        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: -10"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_invalid_check_interval_zero(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is zero."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CHECK_INTERVAL"] = "0"

        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: 0"):
            AppConfig.load_from_env()

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_integer_fields(self, mock_load_dotenv):
        """Test loading various integer fields."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["MAX_RETRIES"] = "5"
        os.environ["RETRY_DELAY"] = "10"
        os.environ["IP_HISTORY_SIZE"] = "20"
        os.environ["RATE_LIMIT_PERIOD"] = "600"
        os.environ["MAX_CHECKS_PER_PERIOD"] = "15"

        config = AppConfig.load_from_env()

        assert config.max_retries == 5
        assert config.retry_delay == 10
        assert config.ip_history_size == 20
        assert config.rate_limit_period == 600
        assert config.max_checks_per_period == 15

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_boolean_fields_true_variations(self, mock_load_dotenv):
        """Test loading boolean fields with various true values."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CONCURRENT_API_CHECKS"] = "true"
        os.environ["CIRCUIT_BREAKER_ENABLED"] = "TRUE"
        os.environ["STARTUP_MESSAGE_ENABLED"] = "True"
        os.environ["TESTING_MODE"] = "true"
        os.environ["CUSTOM_APIS_ENABLED"] = "true"
        os.environ["MESSAGE_QUEUE_ENABLED"] = "true"
        os.environ["CACHE_ENABLED"] = "true"

        config = AppConfig.load_from_env()

        assert config.concurrent_api_checks is True
        assert config.circuit_breaker_enabled is True
        assert config.startup_message_enabled is True
        assert config.testing_mode is True
        assert config.custom_apis_enabled is True
        assert config.message_queue_enabled is True
        assert config.cache_enabled is True

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_boolean_fields_false_variations(self, mock_load_dotenv):
        """Test loading boolean fields with various false values."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CONCURRENT_API_CHECKS"] = "false"
        os.environ["CIRCUIT_BREAKER_ENABLED"] = "FALSE"
        os.environ["STARTUP_MESSAGE_ENABLED"] = "False"
        os.environ["TESTING_MODE"] = "false"
        os.environ["CUSTOM_APIS_ENABLED"] = "false"
        os.environ["MESSAGE_QUEUE_ENABLED"] = "false"
        os.environ["CACHE_ENABLED"] = "false"

        config = AppConfig.load_from_env()

        assert config.concurrent_api_checks is False
        assert config.circuit_breaker_enabled is False
        assert config.startup_message_enabled is False
        assert config.testing_mode is False
        assert config.custom_apis_enabled is False
        assert config.message_queue_enabled is False
        assert config.cache_enabled is False

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_float_fields(self, mock_load_dotenv):
        """Test loading float fields."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["CIRCUIT_BREAKER_RECOVERY_TIMEOUT"] = "180.5"
        os.environ["MESSAGE_QUEUE_PROCESS_INTERVAL"] = "2.5"
        os.environ["CONNECTION_TIMEOUT"] = "15.0"
        os.environ["READ_TIMEOUT"] = "45.0"
        os.environ["CACHE_STALE_THRESHOLD"] = "0.75"

        config = AppConfig.load_from_env()

        assert config.circuit_breaker_recovery_timeout == 180.5
        assert config.message_queue_process_interval == 2.5
        assert config.connection_timeout == 15.0
        assert config.read_timeout == 45.0
        assert config.cache_stale_threshold == 0.75

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_string_fields(self, mock_load_dotenv):
        """Test loading string fields."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["DB_FILE"] = "test.db"
        os.environ["IP_FILE"] = "test_ip.json"
        os.environ["IP_HISTORY_FILE"] = "test_history.json"
        os.environ["LOG_LEVEL"] = "DEBUG"
        os.environ["API_CONFIG_FILE"] = "test_apis.json"
        os.environ["CACHE_FILE"] = "test_cache.json"

        config = AppConfig.load_from_env()

        assert config.db_file == "test.db"
        assert config.ip_file == "test_ip.json"
        assert config.ip_history_file == "test_history.json"
        assert config.log_level == "DEBUG"
        assert config.api_config_file == "test_apis.json"
        assert config.cache_file == "test_cache.json"

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_log_level_case_conversion(self, mock_load_dotenv):
        """Test that log level is converted to uppercase."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["LOG_LEVEL"] = "debug"

        config = AppConfig.load_from_env()

        assert config.log_level == "DEBUG"

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_all_defaults(self, mock_load_dotenv):
        """Test loading with only required fields, all others use defaults."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"

        config = AppConfig.load_from_env()

        # Check that defaults are used
        assert config.check_interval == AppConfig.DEFAULT_CHECK_INTERVAL
        assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES
        assert config.retry_delay == AppConfig.DEFAULT_RETRY_DELAY
        assert config.ip_history_size == AppConfig.DEFAULT_IP_HISTORY_SIZE
        assert config.rate_limit_period == AppConfig.DEFAULT_RATE_LIMIT_PERIOD
        assert config.max_checks_per_period == AppConfig.DEFAULT_MAX_CHECKS
        assert (
            config.circuit_breaker_failure_threshold
            == AppConfig.DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD
        )
        assert (
            config.circuit_breaker_recovery_timeout
            == AppConfig.DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT
        )
        assert config.message_queue_max_size == AppConfig.DEFAULT_MESSAGE_QUEUE_MAX_SIZE
        assert (
            config.message_queue_max_age_hours
            == AppConfig.DEFAULT_MESSAGE_QUEUE_MAX_AGE_HOURS
        )
        assert (
            config.message_queue_batch_size
            == AppConfig.DEFAULT_MESSAGE_QUEUE_BATCH_SIZE
        )
        assert (
            config.message_queue_process_interval
            == AppConfig.DEFAULT_MESSAGE_QUEUE_PROCESS_INTERVAL
        )
        assert config.connection_pool_size == AppConfig.DEFAULT_CONNECTION_POOL_SIZE
        assert (
            config.connection_pool_max_keepalive
            == AppConfig.DEFAULT_CONNECTION_POOL_MAX_KEEPALIVE
        )
        assert config.connection_timeout == AppConfig.DEFAULT_CONNECTION_TIMEOUT
        assert config.read_timeout == AppConfig.DEFAULT_READ_TIMEOUT
        assert config.cache_ttl == AppConfig.DEFAULT_CACHE_TTL
        assert config.cache_max_memory_size == AppConfig.DEFAULT_CACHE_MAX_MEMORY_SIZE
        assert config.cache_stale_threshold == AppConfig.DEFAULT_CACHE_STALE_THRESHOLD
        assert config.cache_cleanup_interval == AppConfig.DEFAULT_CACHE_CLEANUP_INTERVAL

        # Check default boolean values
        assert config.concurrent_api_checks is True
        assert config.circuit_breaker_enabled is True
        assert config.startup_message_enabled is True
        assert config.testing_mode is False
        assert config.custom_apis_enabled is True
        assert config.message_queue_enabled is True
        assert config.cache_enabled is True

        # Check default string values
        assert config.db_file == "ip_monitor.db"
        assert config.ip_file == "last_ip.json"
        assert config.ip_history_file == "ip_history.json"
        assert config.log_level == "INFO"
        assert config.api_config_file == "ip_apis.json"
        assert config.cache_file == "cache.json"

    @patch("ip_monitor.config.load_dotenv")
    @patch("os.path.exists")
    @patch("ip_monitor.config.logger")
    def test_load_from_env_file_path_validation_warning(
        self, mock_logger, mock_exists, mock_load_dotenv
    ):
        """Test that warnings are logged for non-existent directories."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["IP_FILE"] = "/nonexistent/path/ip.json"
        os.environ["IP_HISTORY_FILE"] = "/nonexistent/path/history.json"
        os.environ["CACHE_FILE"] = "/nonexistent/path/cache.json"

        # Mock path existence checks
        mock_exists.return_value = False

        config = AppConfig.load_from_env()

        # Check that warnings were logged for non-existent directories
        assert mock_logger.warning.call_count == 3
        mock_logger.warning.assert_any_call(
            "Directory does not exist: /nonexistent/path"
        )

    @patch("ip_monitor.config.load_dotenv")
    @patch("os.path.exists")
    def test_load_from_env_file_path_validation_no_warning_for_current_dir(
        self, mock_exists, mock_load_dotenv
    ):
        """Test that no warnings are logged for files in current directory."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
        os.environ["CHANNEL_ID"] = "123456789"
        os.environ["IP_FILE"] = "ip.json"
        os.environ["IP_HISTORY_FILE"] = "history.json"
        os.environ["CACHE_FILE"] = "cache.json"

        # Mock path existence checks
        mock_exists.return_value = True

        config = AppConfig.load_from_env()

        # Should not raise any warnings for current directory files
        assert config.ip_file == "ip.json"
        assert config.ip_history_file == "history.json"
        assert config.cache_file == "cache.json"

    @patch("ip_monitor.config.load_dotenv")
    def test_load_from_env_comprehensive_all_fields(self, mock_load_dotenv):
        """Test loading with all possible environment variables set."""
        # Set all environment variables
        env_vars = {
            "DISCORD_BOT_TOKEN": "comprehensive_test_token",
            "CHANNEL_ID": "987654321",
            "CHECK_INTERVAL": "45",
            "MAX_RETRIES": "7",
            "RETRY_DELAY": "8",
            "CONCURRENT_API_CHECKS": "false",
            "CIRCUIT_BREAKER_ENABLED": "false",
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "5",
            "CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "200.5",
            "RATE_LIMIT_PERIOD": "900",
            "MAX_CHECKS_PER_PERIOD": "25",
            "DB_FILE": "comprehensive.db",
            "IP_FILE": "comprehensive_ip.json",
            "IP_HISTORY_FILE": "comprehensive_history.json",
            "IP_HISTORY_SIZE": "25",
            "STARTUP_MESSAGE_ENABLED": "false",
            "TESTING_MODE": "true",
            "LOG_LEVEL": "warning",
            "CUSTOM_APIS_ENABLED": "false",
            "API_CONFIG_FILE": "comprehensive_apis.json",
            "MESSAGE_QUEUE_ENABLED": "false",
            "MESSAGE_QUEUE_MAX_SIZE": "2000",
            "MESSAGE_QUEUE_MAX_AGE_HOURS": "48",
            "MESSAGE_QUEUE_BATCH_SIZE": "10",
            "MESSAGE_QUEUE_PROCESS_INTERVAL": "5.0",
            "CONNECTION_POOL_SIZE": "20",
            "CONNECTION_POOL_MAX_KEEPALIVE": "15",
            "CONNECTION_TIMEOUT": "20.0",
            "READ_TIMEOUT": "60.0",
            "CACHE_ENABLED": "false",
            "CACHE_TTL": "600",
            "CACHE_MAX_MEMORY_SIZE": "2000",
            "CACHE_STALE_THRESHOLD": "0.9",
            "CACHE_FILE": "comprehensive_cache.json",
            "CACHE_CLEANUP_INTERVAL": "600",
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        config = AppConfig.load_from_env()

        # Verify all fields are set correctly
        assert config.discord_token == "comprehensive_test_token"
        assert config.channel_id == 987654321
        assert config.check_interval == 45
        assert config.max_retries == 7
        assert config.retry_delay == 8
        assert config.concurrent_api_checks is False
        assert config.circuit_breaker_enabled is False
        assert config.circuit_breaker_failure_threshold == 5
        assert config.circuit_breaker_recovery_timeout == 200.5
        assert config.rate_limit_period == 900
        assert config.max_checks_per_period == 25
        assert config.db_file == "comprehensive.db"
        assert config.ip_file == "comprehensive_ip.json"
        assert config.ip_history_file == "comprehensive_history.json"
        assert config.ip_history_size == 25
        assert config.startup_message_enabled is False
        assert config.testing_mode is True
        assert config.log_level == "WARNING"
        assert config.custom_apis_enabled is False
        assert config.api_config_file == "comprehensive_apis.json"
        assert config.message_queue_enabled is False
        assert config.message_queue_max_size == 2000
        assert config.message_queue_max_age_hours == 48
        assert config.message_queue_batch_size == 10
        assert config.message_queue_process_interval == 5.0
        assert config.connection_pool_size == 20
        assert config.connection_pool_max_keepalive == 15
        assert config.connection_timeout == 20.0
        assert config.read_timeout == 60.0
        assert config.cache_enabled is False
        assert config.cache_ttl == 600
        assert config.cache_max_memory_size == 2000
        assert config.cache_stale_threshold == 0.9
        assert config.cache_file == "comprehensive_cache.json"
        assert config.cache_cleanup_interval == 600


class TestAppConfigValidation:
    """Test configuration validation functionality."""

    @pytest.fixture
    def config(self):
        """Create a test configuration instance."""
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


class TestAppConfigFilePersistence:
    """Test configuration file persistence functionality."""

    @pytest.fixture
    def config(self):
        """Create a test configuration instance."""
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

    @patch("builtins.open", new_callable=mock_open)
    @patch("json.dump")
    def test_save_to_file_success(self, mock_json_dump, mock_file, config):
        """Test successful configuration save to file."""
        result = config.save_to_file("test_config.json")

        assert result is True
        mock_file.assert_called_once_with("test_config.json", "w")
        mock_json_dump.assert_called_once()

        # Check that discord_token was removed from saved data
        saved_data = mock_json_dump.call_args[0][0]
        assert "discord_token" not in saved_data
        assert "cache_info" in saved_data

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    @patch("ip_monitor.config.logger")
    def test_save_to_file_failure(self, mock_logger, mock_file, config):
        """Test configuration save failure."""
        result = config.save_to_file("test_config.json")

        assert result is False
        mock_logger.error.assert_called_once()
        assert "Failed to save config" in mock_logger.error.call_args[0][0]

    @patch("os.path.exists", return_value=False)
    def test_load_from_file_file_not_exists(self, mock_exists, config):
        """Test loading from non-existent file returns base config."""
        result = AppConfig.load_from_file("non_existent.json", config)

        assert result == config

    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"max_retries": 7, "retry_delay": 15}',
    )
    @patch("json.load")
    def test_load_from_file_success(
        self, mock_json_load, mock_file, mock_exists, config
    ):
        """Test successful configuration load from file."""
        mock_json_load.return_value = {"max_retries": 7, "retry_delay": 15}

        result = AppConfig.load_from_file("test_config.json", config)

        assert result.max_retries == 7
        assert result.retry_delay == 15
        assert (
            result.discord_token == config.discord_token
        )  # Base config values preserved

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=OSError("Permission denied"))
    @patch("ip_monitor.config.logger")
    def test_load_from_file_failure(self, mock_logger, mock_file, mock_exists, config):
        """Test configuration load failure returns base config."""
        result = AppConfig.load_from_file("test_config.json", config)

        assert result == config
        mock_logger.error.assert_called_once()
        assert "Failed to load config" in mock_logger.error.call_args[0][0]

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data="invalid json")
    @patch("json.load", side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0))
    @patch("ip_monitor.config.logger")
    def test_load_from_file_invalid_json(
        self, mock_logger, mock_json_load, mock_file, mock_exists, config
    ):
        """Test configuration load with invalid JSON returns base config."""
        result = AppConfig.load_from_file("test_config.json", config)

        assert result == config
        mock_logger.error.assert_called_once()
        assert "Failed to load config" in mock_logger.error.call_args[0][0]


class TestAppConfigValidationErrorHandling:
    """Test configuration validation and error handling edge cases."""

    @pytest.fixture
    def config(self):
        """Create a test configuration instance."""
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

    def setup_method(self):
        """Set up test fixtures."""
        # Clear any existing environment variables
        self.env_vars_to_clear = [
            "DISCORD_BOT_TOKEN",
            "CHANNEL_ID",
            "CHECK_INTERVAL",
            "MAX_RETRIES",
            "RETRY_DELAY",
            "CONCURRENT_API_CHECKS",
            "CIRCUIT_BREAKER_ENABLED",
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
            "CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
            "RATE_LIMIT_PERIOD",
            "MAX_CHECKS_PER_PERIOD",
            "DB_FILE",
            "IP_FILE",
            "IP_HISTORY_FILE",
            "IP_HISTORY_SIZE",
            "STARTUP_MESSAGE_ENABLED",
            "TESTING_MODE",
            "LOG_LEVEL",
            "CUSTOM_APIS_ENABLED",
            "API_CONFIG_FILE",
            "MESSAGE_QUEUE_ENABLED",
            "MESSAGE_QUEUE_MAX_SIZE",
            "MESSAGE_QUEUE_MAX_AGE_HOURS",
            "MESSAGE_QUEUE_BATCH_SIZE",
            "MESSAGE_QUEUE_PROCESS_INTERVAL",
            "CONNECTION_POOL_SIZE",
            "CONNECTION_POOL_MAX_KEEPALIVE",
            "CONNECTION_TIMEOUT",
            "READ_TIMEOUT",
            "CACHE_ENABLED",
            "CACHE_TTL",
            "CACHE_MAX_MEMORY_SIZE",
            "CACHE_STALE_THRESHOLD",
            "CACHE_FILE",
            "CACHE_CLEANUP_INTERVAL",
        ]

        # Store original values
        self.original_env_values = {}
        for var in self.env_vars_to_clear:
            self.original_env_values[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        for var in self.env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]
            if self.original_env_values[var] is not None:
                os.environ[var] = self.original_env_values[var]

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

        # Should still work even if dotenv fails
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
    def config(self):
        """Create a test configuration instance."""
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


class TestAppConfigRuntimeUpdates:
    """Test runtime configuration update functionality."""

    @pytest.fixture
    def config(self):
        """Create a test configuration instance."""
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
