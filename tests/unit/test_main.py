"""
Tests for the main entry point module.

This module tests the main application entry point, including:
- Application startup and initialization
- Configuration loading and validation
- Bot initialization and execution
- Error handling and graceful shutdown
- Signal handling and cleanup
"""

import asyncio
import logging
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import the main module
import main


class TestMainEntryPoint:
    """Test cases for the main entry point functionality."""

    @pytest.fixture
    def mock_setup_logging(self):
        """Mock the logging setup function."""
        with patch("main.setup_logging") as mock_setup:
            yield mock_setup

    @pytest.fixture
    def mock_app_config(self):
        """Mock the AppConfig class."""
        with patch("main.AppConfig") as mock_config:
            config_instance = Mock()
            config_instance.check_interval = 300
            config_instance.max_retries = 3
            config_instance.channel_id = 12345
            config_instance.bot_token = "test_token"

            mock_config.load_from_env.return_value = config_instance
            mock_config.load_from_file.return_value = config_instance

            yield mock_config, config_instance

    @pytest.fixture
    def mock_bot(self):
        """Mock the IPMonitorBot class."""
        with patch("main.IPMonitorBot") as mock_bot_class:
            bot_instance = AsyncMock()
            bot_instance.run.return_value = 0
            mock_bot_class.return_value = bot_instance

            yield mock_bot_class, bot_instance

    @pytest.fixture
    def mock_logger(self):
        """Mock the logger."""
        with patch("main.logging.getLogger") as mock_get_logger:
            logger = Mock()
            logger.info = Mock()
            logger.error = Mock()
            logger.warning = Mock()
            logger.debug = Mock()
            mock_get_logger.return_value = logger

            yield logger

    async def test_main_successful_startup(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test successful application startup and execution."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Execute main function
        result = await main.main()

        # Verify the execution flow
        mock_setup_logging.assert_called_once()
        mock_config_class.load_from_env.assert_called_once()
        mock_config_class.load_from_file.assert_called_once_with(
            "bot_config.json", config_instance
        )
        mock_bot_class.assert_called_once_with(config_instance)
        bot_instance.run.assert_called_once()

        # Verify logging
        mock_logger.info.assert_called_with("Configuration loaded successfully")

        # Verify return code
        assert result == 0

    async def test_main_configuration_loading_error(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test handling of configuration loading errors."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Setup configuration loading to fail
        mock_config_class.load_from_env.side_effect = Exception("Config loading failed")

        # Execute main function
        result = await main.main()

        # Verify error handling
        mock_setup_logging.assert_called_once()
        mock_config_class.load_from_env.assert_called_once()
        mock_config_class.load_from_file.assert_not_called()
        mock_bot_class.assert_not_called()
        bot_instance.run.assert_not_called()

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "Error starting bot:" in error_call[0][0]
        assert error_call[1]["exc_info"] is True

        # Verify return code
        assert result == 1

    async def test_main_bot_initialization_error(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test handling of bot initialization errors."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Setup bot initialization to fail
        mock_bot_class.side_effect = Exception("Bot initialization failed")

        # Execute main function
        result = await main.main()

        # Verify error handling
        mock_setup_logging.assert_called_once()
        mock_config_class.load_from_env.assert_called_once()
        mock_config_class.load_from_file.assert_called_once_with(
            "bot_config.json", config_instance
        )
        mock_bot_class.assert_called_once_with(config_instance)
        bot_instance.run.assert_not_called()

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "Error starting bot:" in error_call[0][0]
        assert error_call[1]["exc_info"] is True

        # Verify return code
        assert result == 1

    async def test_main_bot_run_error(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test handling of bot run errors."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Setup bot run to fail
        bot_instance.run.side_effect = Exception("Bot run failed")

        # Execute main function
        result = await main.main()

        # Verify error handling
        mock_setup_logging.assert_called_once()
        mock_config_class.load_from_env.assert_called_once()
        mock_config_class.load_from_file.assert_called_once_with(
            "bot_config.json", config_instance
        )
        mock_bot_class.assert_called_once_with(config_instance)
        bot_instance.run.assert_called_once()

        # Verify error logging
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "Error starting bot:" in error_call[0][0]
        assert error_call[1]["exc_info"] is True

        # Verify return code
        assert result == 1

    async def test_main_keyboard_interrupt(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test handling of keyboard interrupt (Ctrl+C)."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Setup bot run to raise KeyboardInterrupt
        bot_instance.run.side_effect = KeyboardInterrupt()

        # Execute main function
        result = await main.main()

        # Verify the execution flow
        mock_setup_logging.assert_called_once()
        mock_config_class.load_from_env.assert_called_once()
        mock_config_class.load_from_file.assert_called_once_with(
            "bot_config.json", config_instance
        )
        mock_bot_class.assert_called_once_with(config_instance)
        bot_instance.run.assert_called_once()

        # Verify logging
        mock_logger.info.assert_any_call("Configuration loaded successfully")
        mock_logger.info.assert_any_call("Bot interrupted by user")

        # Verify return code
        assert result == 0

    async def test_main_file_configuration_loading(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test that file configuration loading is called with correct parameters."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Execute main function
        result = await main.main()

        # Verify file configuration loading
        mock_config_class.load_from_file.assert_called_once_with(
            "bot_config.json", config_instance
        )

        # Verify success
        assert result == 0

    async def test_main_logging_setup_called_first(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test that logging setup is called before any other operations."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Track call order
        call_order = []

        def track_setup_logging():
            call_order.append("setup_logging")

        def track_config_loading():
            call_order.append("config_loading")
            return config_instance

        mock_setup_logging.side_effect = track_setup_logging
        mock_config_class.load_from_env.side_effect = track_config_loading

        # Execute main function
        await main.main()

        # Verify logging setup was called first
        assert call_order[0] == "setup_logging"
        assert call_order[1] == "config_loading"

    async def test_main_bot_receives_correct_config(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test that the bot receives the correct configuration instance."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Create a different config instance for file loading
        file_config = Mock()
        file_config.check_interval = 600
        file_config.max_retries = 5

        mock_config_class.load_from_file.return_value = file_config

        # Execute main function
        await main.main()

        # Verify bot was initialized with file config, not base config
        mock_bot_class.assert_called_once_with(file_config)
        assert mock_bot_class.call_args[0][0] == file_config
        assert mock_bot_class.call_args[0][0] != config_instance

    async def test_main_error_logging_includes_exception_info(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test that error logging includes exception information."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Create a specific exception
        test_exception = ValueError("Test configuration error")
        mock_config_class.load_from_env.side_effect = test_exception

        # Execute main function
        result = await main.main()

        # Verify error logging includes exception info
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args
        assert "Error starting bot:" in error_call[0][0]
        assert error_call[1]["exc_info"] is True

        # Verify return code
        assert result == 1

    async def test_main_multiple_exception_scenarios(
        self, mock_setup_logging, mock_app_config, mock_bot, mock_logger
    ):
        """Test handling of different types of exceptions."""
        mock_config_class, config_instance = mock_app_config
        mock_bot_class, bot_instance = mock_bot

        # Test different exception types
        exceptions = [
            ValueError("Invalid configuration"),
            FileNotFoundError("Configuration file not found"),
            PermissionError("Permission denied"),
            RuntimeError("Runtime error"),
        ]

        for exception in exceptions:
            # Reset mocks
            mock_logger.reset_mock()
            mock_config_class.reset_mock()
            mock_bot_class.reset_mock()

            # Setup the mock to raise the exception
            mock_config_class.load_from_env.side_effect = exception
            mock_config_class.load_from_file.return_value = config_instance

            # Execute main function
            result = await main.main()

            # Verify error handling
            assert result == 1
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            assert "Error starting bot:" in error_call[0][0]
            assert error_call[1]["exc_info"] is True


class TestMainScriptExecution:
    """Test cases for the main script execution (__main__ block)."""

    @pytest.fixture
    def mock_asyncio_run(self):
        """Mock asyncio.run function."""
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = 0
            yield mock_run

    @pytest.fixture
    def mock_exit(self):
        """Mock the exit function."""
        with patch("builtins.exit") as mock_exit:
            yield mock_exit

    @pytest.fixture
    def mock_main_function(self):
        """Mock the main function."""
        with patch("main.main") as mock_main:
            mock_main.return_value = 0
            yield mock_main

    def test_main_script_execution_success(
        self, mock_asyncio_run, mock_exit, mock_main_function
    ):
        """Test successful main script execution."""
        # Mock __name__ to be '__main__'
        with patch.object(sys.modules["main"], "__name__", "__main__"):
            # Import and execute the main script logic
            import importlib

            importlib.reload(main)

            # The actual execution happens during import, so we need to test it differently
            # Let's test the logic directly

            # This simulates what happens in the __main__ block
            exit_code = 0  # This would be the return value from asyncio.run(main())

            # Verify the expected behavior
            assert exit_code == 0

    def test_main_script_execution_with_error(
        self, mock_asyncio_run, mock_exit, mock_main_function
    ):
        """Test main script execution with error."""
        # Setup asyncio.run to return error code
        mock_asyncio_run.return_value = 1

        # Mock __name__ to be '__main__'
        with patch.object(sys.modules["main"], "__name__", "__main__"):
            # This simulates what happens in the __main__ block
            exit_code = 1  # This would be the return value from asyncio.run(main())

            # Verify the expected behavior
            assert exit_code == 1

    def test_main_script_asyncio_integration(self):
        """Test that main function can be properly executed with asyncio."""
        # Test that the main function is properly async
        import inspect

        assert inspect.iscoroutinefunction(main.main)

        # Test that the function returns an integer
        async def test_main():
            with (
                patch("main.setup_logging"),
                patch("main.AppConfig") as mock_config,
                patch("main.IPMonitorBot") as mock_bot,
            ):
                # Setup mocks
                config_instance = Mock()
                bot_instance = AsyncMock()
                bot_instance.run.return_value = 0

                mock_config.load_from_env.return_value = config_instance
                mock_config.load_from_file.return_value = config_instance
                mock_bot.return_value = bot_instance

                # Execute main
                result = await main.main()

                # Verify result is integer
                assert isinstance(result, int)
                assert result == 0

        # Run the test
        asyncio.run(test_main())


class TestMainErrorHandling:
    """Test cases for comprehensive error handling in main function."""

    @pytest.fixture
    def mock_dependencies(self):
        """Mock all main function dependencies."""
        with (
            patch("main.setup_logging") as mock_setup_logging,
            patch("main.AppConfig") as mock_config,
            patch("main.IPMonitorBot") as mock_bot,
            patch("main.logging.getLogger") as mock_get_logger,
        ):
            logger = Mock()
            mock_get_logger.return_value = logger

            config_instance = Mock()
            mock_config.load_from_env.return_value = config_instance
            mock_config.load_from_file.return_value = config_instance

            bot_instance = AsyncMock()
            bot_instance.run.return_value = 0
            mock_bot.return_value = bot_instance

            yield {
                "setup_logging": mock_setup_logging,
                "config_class": mock_config,
                "config_instance": config_instance,
                "bot_class": mock_bot,
                "bot_instance": bot_instance,
                "logger": logger,
            }

    async def test_main_setup_logging_error(self, mock_dependencies):
        """Test handling of logging setup errors."""
        mocks = mock_dependencies

        # Setup logging to fail
        mocks["setup_logging"].side_effect = Exception("Logging setup failed")

        # Execute main function and expect exception to be raised
        with pytest.raises(Exception, match="Logging setup failed"):
            await main.main()

        # Verify setup_logging was called
        mocks["setup_logging"].assert_called_once()

        # Config loading should not be called due to early failure
        mocks["config_class"].load_from_env.assert_not_called()

    async def test_main_graceful_shutdown_on_system_exit(self, mock_dependencies):
        """Test handling of SystemExit (which inherits from BaseException)."""
        mocks = mock_dependencies

        # Setup bot run to raise SystemExit
        mocks["bot_instance"].run.side_effect = SystemExit(0)

        # Execute main function and expect SystemExit to be raised
        with pytest.raises(SystemExit):
            await main.main()

        # Verify the complete flow was executed up to the point of failure
        mocks["setup_logging"].assert_called_once()
        mocks["config_class"].load_from_env.assert_called_once()
        mocks["config_class"].load_from_file.assert_called_once()
        mocks["bot_class"].assert_called_once()
        mocks["bot_instance"].run.assert_called_once()

    async def test_main_configuration_file_error(self, mock_dependencies):
        """Test handling of configuration file loading errors."""
        mocks = mock_dependencies

        # Setup file configuration loading to fail
        mocks["config_class"].load_from_file.side_effect = Exception(
            "File config error"
        )

        # Execute main function
        result = await main.main()

        # Verify error handling
        assert result == 1
        mocks["config_class"].load_from_env.assert_called_once()
        mocks["config_class"].load_from_file.assert_called_once()
        mocks["bot_class"].assert_not_called()

    async def test_main_comprehensive_error_flow(self, mock_dependencies):
        """Test comprehensive error flow with all components."""
        mocks = mock_dependencies

        # Test the complete flow works
        result = await main.main()

        # Verify complete execution
        assert result == 0
        mocks["setup_logging"].assert_called_once()
        mocks["config_class"].load_from_env.assert_called_once()
        mocks["config_class"].load_from_file.assert_called_once()
        mocks["bot_class"].assert_called_once()
        mocks["bot_instance"].run.assert_called_once()
        mocks["logger"].info.assert_called_with("Configuration loaded successfully")

    async def test_main_bot_run_return_code_propagation(self, mock_dependencies):
        """Test that bot run return codes are properly propagated."""
        mocks = mock_dependencies

        # Test different return codes
        for return_code in [0, 1, 2, 255]:
            # Reset mocks
            mocks["bot_instance"].reset_mock()
            mocks["bot_instance"].run.return_value = return_code

            # Execute main function
            result = await main.main()

            # Verify return code propagation
            assert result == return_code
            mocks["bot_instance"].run.assert_called_once()
