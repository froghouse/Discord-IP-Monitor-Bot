"""
Tests for logging setup utility.

This module tests the logging configuration functionality including:
- Basic logging configuration
- Log level handling (valid and invalid)
- Handler setup (file and console)
- File rotation configuration
- Environment variable integration
- Error handling for invalid log levels
- Format and datetime configuration
"""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from ip_monitor.utils.logging_setup import setup_logging


class TestLoggingSetup:
    """Test cases for basic logging setup functionality."""

    def test_setup_logging_default_config(self):
        """Test logging setup with default configuration."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called with correct parameters
            mock_basic_config.assert_called_once()
            call_args = mock_basic_config.call_args

            # Check basic configuration
            assert call_args[1]["level"] == logging.INFO
            assert (
                call_args[1]["format"]
                == "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )
            assert call_args[1]["datefmt"] == "%Y-%m-%d %H:%M:%S"

            # Check handlers
            handlers = call_args[1]["handlers"]
            assert len(handlers) == 2
            assert isinstance(handlers[0], RotatingFileHandler)
            assert isinstance(handlers[1], logging.StreamHandler)

            # Verify root logger level was set
            mock_logger.setLevel.assert_called_once()

    def test_setup_logging_with_explicit_level(self):
        """Test logging setup with explicit log level."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("DEBUG")

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to DEBUG
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_setup_logging_reads_environment_variable(self):
        """Test logging setup reads LOG_LEVEL from environment."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to WARNING
            mock_logger.setLevel.assert_called_once_with(logging.WARNING)

    def test_setup_logging_case_insensitive_level_from_environment(self):
        """Test logging setup handles case-insensitive log levels from environment variables."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "debug"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to DEBUG (environment case converted)
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_setup_logging_invalid_level_fallback(self):
        """Test logging setup falls back to INFO for invalid log levels."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.warning") as mock_warning,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("INVALID_LEVEL")

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (fallback)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

            # Verify warning was logged
            mock_warning.assert_called_once_with(
                "Invalid LOG_LEVEL: INVALID_LEVEL. Using INFO instead."
            )

    def test_setup_logging_environment_invalid_level(self):
        """Test logging setup handles invalid environment LOG_LEVEL."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.warning") as mock_warning,
            patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (fallback)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

            # Verify warning was logged
            mock_warning.assert_called_once_with(
                "Invalid LOG_LEVEL: INVALID. Using INFO instead."
            )


class TestLoggingHandlers:
    """Test cases for logging handler configuration."""

    def test_rotating_file_handler_configuration(self):
        """Test RotatingFileHandler is configured correctly."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Get the handlers from the call
            handlers = mock_basic_config.call_args[1]["handlers"]
            rotating_handler = handlers[0]

            # Verify it's a RotatingFileHandler
            assert isinstance(rotating_handler, RotatingFileHandler)

            # Verify file handler configuration
            assert rotating_handler.baseFilename.endswith("bot.log")
            assert rotating_handler.maxBytes == 1024 * 1024  # 1MB
            assert rotating_handler.backupCount == 3

    def test_stream_handler_configuration(self):
        """Test StreamHandler is configured correctly."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Get the handlers from the call
            handlers = mock_basic_config.call_args[1]["handlers"]
            stream_handler = handlers[1]

            # Verify it's a StreamHandler
            assert isinstance(stream_handler, logging.StreamHandler)

    def test_handler_count_and_order(self):
        """Test correct number and order of handlers."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Get the handlers from the call
            handlers = mock_basic_config.call_args[1]["handlers"]

            # Verify handler count
            assert len(handlers) == 2

            # Verify handler order (file handler first, then stream handler)
            assert isinstance(handlers[0], RotatingFileHandler)
            assert isinstance(handlers[1], logging.StreamHandler)


class TestLoggingLevels:
    """Test cases for log level handling."""

    @pytest.mark.parametrize(
        "level_name,expected_level",
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_valid_log_levels(self, level_name: str, expected_level: int):
        """Test all valid log levels are handled correctly."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging(level_name)

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set correctly
            mock_logger.setLevel.assert_called_once_with(expected_level)

    @pytest.mark.parametrize(
        "level_name",
        [
            "debug",
            "info",
            "warning",
            "error",
            "critical",
        ],
    )
    def test_lowercase_log_levels_cause_error(self, level_name: str):
        """Test lowercase log levels cause TypeError when setLevel is called with logging function."""
        with patch("logging.basicConfig") as mock_basic_config:
            # The actual code will raise TypeError because getattr(logging, 'debug') returns a function
            # and setLevel doesn't accept functions - test with real logger
            with pytest.raises(
                TypeError, match="Level not an integer or a valid string"
            ):
                setup_logging(level_name)

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

    @pytest.mark.parametrize(
        "invalid_level",
        [
            "INVALID",
            "TRACE",
            "VERBOSE",
            "",
            "123",
            "None",
            "null",
        ],
    )
    def test_invalid_log_levels_fallback(self, invalid_level: str):
        """Test invalid log levels fall back to INFO."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.warning") as mock_warning,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging(invalid_level)

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (fallback)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

            # Verify warning was logged
            mock_warning.assert_called_once_with(
                f"Invalid LOG_LEVEL: {invalid_level}. Using INFO instead."
            )


class TestEnvironmentIntegration:
    """Test cases for environment variable integration."""

    def test_default_log_level_when_env_not_set(self):
        """Test default log level is INFO when environment variable is not set."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {}, clear=True),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (default)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

    def test_environment_variable_override(self):
        """Test environment variable overrides default log level."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to ERROR
            mock_logger.setLevel.assert_called_once_with(logging.ERROR)

    def test_explicit_parameter_overrides_environment(self):
        """Test explicit parameter overrides environment variable."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("DEBUG")

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to DEBUG (explicit parameter)
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_environment_variable_case_handling(self):
        """Test environment variable case handling."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "warning"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to WARNING (case converted)
            mock_logger.setLevel.assert_called_once_with(logging.WARNING)


class TestFormatAndDateTime:
    """Test cases for logging format and datetime configuration."""

    def test_log_format_configuration(self):
        """Test log format is configured correctly."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called with correct format
            call_args = mock_basic_config.call_args
            expected_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            assert call_args[1]["format"] == expected_format

    def test_datetime_format_configuration(self):
        """Test datetime format is configured correctly."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called with correct datefmt
            call_args = mock_basic_config.call_args
            expected_datefmt = "%Y-%m-%d %H:%M:%S"
            assert call_args[1]["datefmt"] == expected_datefmt

    def test_basic_config_level_parameter(self):
        """Test basicConfig is called with INFO level parameter."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify basicConfig was called with level=INFO
            call_args = mock_basic_config.call_args
            assert call_args[1]["level"] == logging.INFO


class TestErrorHandling:
    """Test cases for error handling in logging setup."""

    def test_attribute_error_handling(self):
        """Test handling of AttributeError when setting invalid log level."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.warning") as mock_warning,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Test with a level that doesn't exist - this will naturally raise AttributeError
            setup_logging("INVALID_LEVEL")

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (fallback)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

            # Verify warning was logged
            mock_warning.assert_called_once_with(
                "Invalid LOG_LEVEL: INVALID_LEVEL. Using INFO instead."
            )

    def test_none_log_level_handling(self):
        """Test handling of None log level parameter."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging(None)

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to DEBUG (from environment)
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_empty_string_log_level_handling(self):
        """Test handling of empty string log level."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch("logging.warning") as mock_warning,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("")

            # Verify basicConfig was called
            mock_basic_config.assert_called_once()

            # Verify root logger level was set to INFO (fallback)
            mock_logger.setLevel.assert_called_once_with(logging.INFO)

            # Verify warning was logged
            mock_warning.assert_called_once_with(
                "Invalid LOG_LEVEL: . Using INFO instead."
            )


class TestIntegrationScenarios:
    """Test cases for integration scenarios."""

    def test_complete_logging_setup_workflow(self):
        """Test complete logging setup workflow with realistic configuration."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify all components are configured
            mock_basic_config.assert_called_once()
            call_args = mock_basic_config.call_args

            # Check complete configuration
            assert call_args[1]["level"] == logging.INFO
            assert (
                call_args[1]["format"]
                == "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
            )
            assert call_args[1]["datefmt"] == "%Y-%m-%d %H:%M:%S"
            assert len(call_args[1]["handlers"]) == 2

            # Verify root logger level was set from environment
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_production_logging_setup(self):
        """Test logging setup for production environment."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
            patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}),
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging()

            # Verify production-appropriate configuration
            mock_basic_config.assert_called_once()
            mock_logger.setLevel.assert_called_once_with(logging.WARNING)

    def test_development_logging_setup(self):
        """Test logging setup for development environment."""
        with (
            patch("logging.basicConfig") as mock_basic_config,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            setup_logging("DEBUG")

            # Verify development-appropriate configuration
            mock_basic_config.assert_called_once()
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)
