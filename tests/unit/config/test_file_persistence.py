"""
Unit tests for configuration file persistence functionality.
"""

import json
import pytest
from unittest.mock import mock_open, patch

from ip_monitor.config import AppConfig


class TestAppConfigFilePersistence:
    """Test configuration file persistence functionality."""

    @pytest.fixture
    def config(self, base_config):
        """Use the base_config fixture."""
        return base_config

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_to_file_success(self, mock_json_dump, mock_file, config):
        """Test successful configuration save to file."""
        result = config.save_to_file('test_config.json')
        
        assert result is True
        mock_file.assert_called_once_with('test_config.json', 'w')
        mock_json_dump.assert_called_once()
        
        # Check that discord_token was removed from saved data
        saved_data = mock_json_dump.call_args[0][0]
        assert 'discord_token' not in saved_data
        assert 'cache_info' in saved_data

    @patch('builtins.open', side_effect=IOError("Permission denied"))
    @patch('ip_monitor.config.logger')
    def test_save_to_file_failure(self, mock_logger, mock_file, config):
        """Test configuration save failure."""
        result = config.save_to_file('test_config.json')
        
        assert result is False
        mock_logger.error.assert_called_once()
        assert 'Failed to save config' in mock_logger.error.call_args[0][0]

    @patch('os.path.exists', return_value=False)
    def test_load_from_file_file_not_exists(self, mock_exists, config):
        """Test loading from non-existent file returns base config."""
        result = AppConfig.load_from_file('non_existent.json', config)
        
        assert result == config

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{"max_retries": 7, "retry_delay": 15}')
    @patch('json.load')
    def test_load_from_file_success(self, mock_json_load, mock_file, mock_exists, config):
        """Test successful configuration load from file."""
        mock_json_load.return_value = {'max_retries': 7, 'retry_delay': 15}
        
        result = AppConfig.load_from_file('test_config.json', config)
        
        assert result.max_retries == 7
        assert result.retry_delay == 15
        assert result.discord_token == config.discord_token  # Base config values preserved

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    @patch('ip_monitor.config.logger')
    def test_load_from_file_failure(self, mock_logger, mock_file, mock_exists, config):
        """Test configuration load failure returns base config."""
        result = AppConfig.load_from_file('test_config.json', config)
        
        assert result == config
        mock_logger.error.assert_called_once()
        assert 'Failed to load config' in mock_logger.error.call_args[0][0]

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    @patch('json.load', side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0))
    @patch('ip_monitor.config.logger')
    def test_load_from_file_invalid_json(self, mock_logger, mock_json_load, mock_file, mock_exists, config):
        """Test configuration load with invalid JSON returns base config."""
        result = AppConfig.load_from_file('test_config.json', config)
        
        assert result == config
        mock_logger.error.assert_called_once()
        assert 'Failed to load config' in mock_logger.error.call_args[0][0]