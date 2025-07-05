"""
Unit tests for configuration environment variable loading.
"""

import os
import pytest
from unittest.mock import patch

from ip_monitor.config import AppConfig
from .conftest import assert_config_defaults, assert_config_boolean_defaults, assert_config_string_defaults


class TestAppConfigEnvironmentVariableLoading:
    """Test environment variable loading functionality."""

    @pytest.fixture(autouse=True)
    def setup_method(self, env_cleanup):
        """Use the env_cleanup fixture automatically for all tests."""
        pass

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_required_fields_present(self, mock_load_dotenv, minimal_env_config):
        """Test successful loading with all required fields present."""
        config = AppConfig.load_from_env()
        
        assert config.discord_token == 'test_token_123'
        assert config.channel_id == 123456789
        assert config.check_interval == AppConfig.DEFAULT_CHECK_INTERVAL
        assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES
        mock_load_dotenv.assert_called_once()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_missing_discord_token(self, mock_load_dotenv):
        """Test failure when DISCORD_BOT_TOKEN is missing."""
        os.environ['CHANNEL_ID'] = '123456789'
        
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN not set"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_empty_discord_token(self, mock_load_dotenv):
        """Test failure when DISCORD_BOT_TOKEN is empty."""
        os.environ['DISCORD_BOT_TOKEN'] = ''
        os.environ['CHANNEL_ID'] = '123456789'
        
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN not set"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_channel_id_non_numeric(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is not numeric."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = 'not_a_number'
        
        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: not_a_number"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_channel_id_negative(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is negative."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '-123'
        
        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: -123"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_channel_id_zero(self, mock_load_dotenv):
        """Test failure when CHANNEL_ID is zero."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '0'
        
        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: 0"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_default_channel_id(self, mock_load_dotenv):
        """Test behavior when CHANNEL_ID is not provided (uses default 0)."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        
        with pytest.raises(ValueError, match="Invalid CHANNEL_ID: 0"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_custom_check_interval(self, mock_load_dotenv):
        """Test loading with custom check interval."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CHECK_INTERVAL'] = '60'
        
        config = AppConfig.load_from_env()
        
        assert config.check_interval == 60

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_check_interval_non_numeric(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is not numeric."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CHECK_INTERVAL'] = 'not_a_number'
        
        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: not_a_number"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_check_interval_negative(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is negative."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CHECK_INTERVAL'] = '-10'
        
        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: -10"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_invalid_check_interval_zero(self, mock_load_dotenv):
        """Test failure when CHECK_INTERVAL is zero."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CHECK_INTERVAL'] = '0'
        
        with pytest.raises(ValueError, match="Invalid CHECK_INTERVAL: 0"):
            AppConfig.load_from_env()

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_integer_fields(self, mock_load_dotenv):
        """Test loading various integer fields."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['MAX_RETRIES'] = '5'
        os.environ['RETRY_DELAY'] = '10'
        os.environ['IP_HISTORY_SIZE'] = '20'
        os.environ['RATE_LIMIT_PERIOD'] = '600'
        os.environ['MAX_CHECKS_PER_PERIOD'] = '15'
        
        config = AppConfig.load_from_env()
        
        assert config.max_retries == 5
        assert config.retry_delay == 10
        assert config.ip_history_size == 20
        assert config.rate_limit_period == 600
        assert config.max_checks_per_period == 15

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_boolean_fields_true_variations(self, mock_load_dotenv):
        """Test loading boolean fields with various true values."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CONCURRENT_API_CHECKS'] = 'true'
        os.environ['CIRCUIT_BREAKER_ENABLED'] = 'TRUE'
        os.environ['STARTUP_MESSAGE_ENABLED'] = 'True'
        os.environ['TESTING_MODE'] = 'true'
        os.environ['CUSTOM_APIS_ENABLED'] = 'true'
        os.environ['MESSAGE_QUEUE_ENABLED'] = 'true'
        os.environ['CACHE_ENABLED'] = 'true'
        
        config = AppConfig.load_from_env()
        
        assert config.concurrent_api_checks is True
        assert config.circuit_breaker_enabled is True
        assert config.startup_message_enabled is True
        assert config.testing_mode is True
        assert config.custom_apis_enabled is True
        assert config.message_queue_enabled is True
        assert config.cache_enabled is True

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_boolean_fields_false_variations(self, mock_load_dotenv):
        """Test loading boolean fields with various false values."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CONCURRENT_API_CHECKS'] = 'false'
        os.environ['CIRCUIT_BREAKER_ENABLED'] = 'FALSE'
        os.environ['STARTUP_MESSAGE_ENABLED'] = 'False'
        os.environ['TESTING_MODE'] = 'false'
        os.environ['CUSTOM_APIS_ENABLED'] = 'false'
        os.environ['MESSAGE_QUEUE_ENABLED'] = 'false'
        os.environ['CACHE_ENABLED'] = 'false'
        
        config = AppConfig.load_from_env()
        
        assert config.concurrent_api_checks is False
        assert config.circuit_breaker_enabled is False
        assert config.startup_message_enabled is False
        assert config.testing_mode is False
        assert config.custom_apis_enabled is False
        assert config.message_queue_enabled is False
        assert config.cache_enabled is False

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_float_fields(self, mock_load_dotenv):
        """Test loading float fields."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['CIRCUIT_BREAKER_RECOVERY_TIMEOUT'] = '180.5'
        os.environ['MESSAGE_QUEUE_PROCESS_INTERVAL'] = '2.5'
        os.environ['CONNECTION_TIMEOUT'] = '15.0'
        os.environ['READ_TIMEOUT'] = '45.0'
        os.environ['CACHE_STALE_THRESHOLD'] = '0.75'
        
        config = AppConfig.load_from_env()
        
        assert config.circuit_breaker_recovery_timeout == 180.5
        assert config.message_queue_process_interval == 2.5
        assert config.connection_timeout == 15.0
        assert config.read_timeout == 45.0
        assert config.cache_stale_threshold == 0.75

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_string_fields(self, mock_load_dotenv):
        """Test loading string fields."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['DB_FILE'] = 'test.db'
        os.environ['IP_FILE'] = 'test_ip.json'
        os.environ['IP_HISTORY_FILE'] = 'test_history.json'
        os.environ['LOG_LEVEL'] = 'DEBUG'
        os.environ['API_CONFIG_FILE'] = 'test_apis.json'
        os.environ['CACHE_FILE'] = 'test_cache.json'
        
        config = AppConfig.load_from_env()
        
        assert config.db_file == 'test.db'
        assert config.ip_file == 'test_ip.json'
        assert config.ip_history_file == 'test_history.json'
        assert config.log_level == 'DEBUG'
        assert config.api_config_file == 'test_apis.json'
        assert config.cache_file == 'test_cache.json'

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_log_level_case_conversion(self, mock_load_dotenv):
        """Test that log level is converted to uppercase."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['LOG_LEVEL'] = 'debug'
        
        config = AppConfig.load_from_env()
        
        assert config.log_level == 'DEBUG'

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_all_defaults(self, mock_load_dotenv, minimal_env_config):
        """Test loading with only required fields, all others use defaults."""
        config = AppConfig.load_from_env()
        
        # Check that defaults are used
        assert_config_defaults(config)
        assert_config_boolean_defaults(config)
        assert_config_string_defaults(config)

    @patch('ip_monitor.config.load_dotenv')
    @patch('os.path.exists')
    @patch('ip_monitor.config.logger')
    def test_load_from_env_file_path_validation_warning(self, mock_logger, mock_exists, mock_load_dotenv):
        """Test that warnings are logged for non-existent directories."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['IP_FILE'] = '/nonexistent/path/ip.json'
        os.environ['IP_HISTORY_FILE'] = '/nonexistent/path/history.json'
        os.environ['CACHE_FILE'] = '/nonexistent/path/cache.json'
        
        # Mock path existence checks
        mock_exists.return_value = False
        
        config = AppConfig.load_from_env()
        
        # Check that warnings were logged for non-existent directories
        assert mock_logger.warning.call_count == 3
        mock_logger.warning.assert_any_call("Directory does not exist: /nonexistent/path")

    @patch('ip_monitor.config.load_dotenv')
    @patch('os.path.exists')
    def test_load_from_env_file_path_validation_no_warning_for_current_dir(self, mock_exists, mock_load_dotenv):
        """Test that no warnings are logged for files in current directory."""
        os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
        os.environ['CHANNEL_ID'] = '123456789'
        os.environ['IP_FILE'] = 'ip.json'
        os.environ['IP_HISTORY_FILE'] = 'history.json'
        os.environ['CACHE_FILE'] = 'cache.json'
        
        # Mock path existence checks
        mock_exists.return_value = True
        
        config = AppConfig.load_from_env()
        
        # Should not raise any warnings for current directory files
        assert config.ip_file == 'ip.json'
        assert config.ip_history_file == 'history.json'
        assert config.cache_file == 'cache.json'

    @patch('ip_monitor.config.load_dotenv')
    def test_load_from_env_comprehensive_all_fields(self, mock_load_dotenv, comprehensive_env_config):
        """Test loading with all possible environment variables set."""
        config = AppConfig.load_from_env()
        
        # Verify all fields are set correctly
        assert config.discord_token == 'comprehensive_test_token'
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
        assert config.db_file == 'comprehensive.db'
        assert config.ip_file == 'comprehensive_ip.json'
        assert config.ip_history_file == 'comprehensive_history.json'
        assert config.ip_history_size == 25
        assert config.startup_message_enabled is False
        assert config.testing_mode is True
        assert config.log_level == 'WARNING'
        assert config.custom_apis_enabled is False
        assert config.api_config_file == 'comprehensive_apis.json'
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
        assert config.cache_file == 'comprehensive_cache.json'
        assert config.cache_cleanup_interval == 600