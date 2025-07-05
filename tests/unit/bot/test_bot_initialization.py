"""
Tests for IPMonitorBot initialization.
"""

from unittest.mock import AsyncMock, patch
import pytest

from ip_monitor.bot import IPMonitorBot


class TestBotInitialization:
    """Test suite for IPMonitorBot initialization."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_initialization(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test bot initialization with default configuration."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify initialization
        assert bot.config == mock_bot_config
        assert bot.client == mock_client
        assert bot.base_check_interval == mock_bot_config.check_interval
        assert bot.check_ip_task is None
        assert bot.cache_cleanup_task is None

        # Verify service initialization
        mock_ip_service.assert_called_once()
        mock_storage.assert_called_once()
        mock_async_rate_limiter.assert_called_once()
        mock_discord_rate_limiter.assert_called_once()
        mock_ip_commands.assert_called_once()
        mock_admin_router.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_initialization_with_custom_config(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test bot initialization with custom configuration values."""
        # Modify config
        mock_bot_config.check_interval = 10
        mock_bot_config.max_retries = 5
        mock_bot_config.circuit_breaker_enabled = False
        mock_bot_config.message_queue_enabled = False

        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify custom configuration is used
        assert bot.base_check_interval == 10

        # Verify IP service is configured with custom values
        mock_ip_service.assert_called_once_with(
            max_retries=5,
            retry_delay=mock_bot_config.retry_delay,
            use_concurrent_checks=mock_bot_config.concurrent_api_checks,
            circuit_breaker_enabled=False,
            circuit_breaker_failure_threshold=mock_bot_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=mock_bot_config.circuit_breaker_recovery_timeout,
            use_custom_apis=mock_bot_config.custom_apis_enabled,
            connection_pool_size=mock_bot_config.connection_pool_size,
            connection_pool_max_keepalive=mock_bot_config.connection_pool_max_keepalive,
            connection_timeout=mock_bot_config.connection_timeout,
            read_timeout=mock_bot_config.read_timeout,
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_initialization_migration(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test bot initialization triggers data migration."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify migration was called
        mock_storage.migrate_from_json.assert_called_once_with(
            mock_bot_config.ip_file, mock_bot_config.ip_history_file
        )

        # Verify migration flag is set
        assert bot._migration_done is True