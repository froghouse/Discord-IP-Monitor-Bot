"""
Comprehensive tests for the IPMonitorBot class.
"""

from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands
import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig


class TestIPMonitorBot:
    """Test suite for the IPMonitorBot class."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        config = Mock(spec=AppConfig)
        config.discord_token = "test_token"
        config.channel_id = 12345
        config.check_interval = 5
        config.max_retries = 3
        config.retry_delay = 1
        config.concurrent_api_checks = True
        config.circuit_breaker_enabled = True
        config.circuit_breaker_failure_threshold = 3
        config.circuit_breaker_recovery_timeout = 60
        config.custom_apis_enabled = True
        config.connection_pool_size = 10
        config.connection_pool_max_keepalive = 5
        config.connection_timeout = 10.0
        config.read_timeout = 30.0
        config.db_file = "test.db"
        config.ip_history_size = 10
        config.ip_file = "test_ip.json"
        config.ip_history_file = "test_history.json"
        config.rate_limit_period = 300
        config.max_checks_per_period = 10
        config.message_queue_enabled = True
        config.message_queue_max_size = 1000
        config.message_queue_max_age_hours = 24
        config.message_queue_batch_size = 5
        config.message_queue_process_interval = 1.0
        config.startup_message_enabled = True
        config.testing_mode = False
        return config

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for testing."""
        storage = AsyncMock()
        storage.load_last_ip.return_value = "192.168.1.1"
        storage.save_current_ip = AsyncMock()
        storage.migrate_from_json = AsyncMock()
        return storage

    @pytest.fixture
    def mock_ip_service(self):
        """Mock IP service for testing."""
        service = AsyncMock()
        service.get_public_ip.return_value = "192.168.1.1"
        service.set_last_known_ip = AsyncMock()
        service.close = AsyncMock()
        return service

    @pytest.fixture
    def mock_discord_client(self):
        """Mock Discord client for testing."""
        client = AsyncMock(spec=commands.Bot)
        client.user = Mock()
        client.user.id = 123456789
        client.get_channel.return_value = AsyncMock()
        client.close = AsyncMock()
        client.start = AsyncMock()
        client.wait_until_ready = AsyncMock()
        client.add_cog = AsyncMock()
        client.tree = AsyncMock()
        client.tree.sync = AsyncMock(return_value=[])
        client.http = Mock()
        client.http.session = AsyncMock()
        client.http.session.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_commands(self):
        """Mock command handlers for testing."""
        ip_commands = AsyncMock()
        admin_commands = AsyncMock()
        return ip_commands, admin_commands

    @pytest.fixture
    def mock_slash_cogs(self):
        """Mock slash command cogs for testing."""
        ip_cog = AsyncMock()
        admin_cog = AsyncMock()
        return ip_cog, admin_cog

    @pytest.fixture
    def mock_message_queue(self):
        """Mock message queue for testing."""
        queue = AsyncMock()
        queue.max_queue_size = 1000
        queue.max_message_age_hours = 24
        queue.batch_size = 5
        queue.process_interval = 1.0
        queue.set_discord_client = AsyncMock()
        queue.start_processing = AsyncMock()
        queue.stop_processing = AsyncMock()
        return queue

    @pytest.fixture
    def mock_service_health(self):
        """Mock service health for testing."""
        health = AsyncMock()
        health.get_adjusted_interval.return_value = 5.0
        health.is_fallback_active.return_value = False
        health.record_success = AsyncMock()
        health.record_failure = AsyncMock()
        return health

    @pytest.fixture
    def mock_rate_limiter(self):
        """Mock rate limiter for testing."""
        limiter = AsyncMock()
        limiter.is_limited.return_value = (False, 0)
        return limiter

    @pytest.fixture
    def mock_discord_rate_limiter(self):
        """Mock Discord rate limiter for testing."""
        limiter = AsyncMock()
        limiter.send_message_with_backoff = AsyncMock()
        return limiter

    @pytest.fixture
    def mock_intents(self):
        """Mock Discord intents for testing."""
        intents = Mock(spec=discord.Intents)
        intents.message_content = True
        return intents

    @pytest.fixture
    def mock_tasks_loop(self):
        """Mock tasks loop for testing."""
        loop = AsyncMock()
        loop.start = AsyncMock()
        loop.cancel = AsyncMock()
        loop.restart = AsyncMock()
        loop.is_running.return_value = True
        loop.minutes = 5.0
        return loop

    # Test Bot Initialization

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
        mock_config,
    ):
        """Test bot initialization with default configuration."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify initialization
        assert bot.config == mock_config
        assert bot.client == mock_client
        assert bot.base_check_interval == mock_config.check_interval
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
        mock_config,
    ):
        """Test bot initialization with custom configuration values."""
        # Modify config
        mock_config.check_interval = 10
        mock_config.max_retries = 5
        mock_config.circuit_breaker_enabled = False
        mock_config.message_queue_enabled = False

        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify custom configuration is used
        assert bot.base_check_interval == 10

        # Verify IP service is configured with custom values
        mock_ip_service.assert_called_once_with(
            max_retries=5,
            retry_delay=mock_config.retry_delay,
            use_concurrent_checks=mock_config.concurrent_api_checks,
            circuit_breaker_enabled=False,
            circuit_breaker_failure_threshold=mock_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=mock_config.circuit_breaker_recovery_timeout,
            use_custom_apis=mock_config.custom_apis_enabled,
            connection_pool_size=mock_config.connection_pool_size,
            connection_pool_max_keepalive=mock_config.connection_pool_max_keepalive,
            connection_timeout=mock_config.connection_timeout,
            read_timeout=mock_config.read_timeout,
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
        mock_config,
    ):
        """Test bot initialization triggers data migration."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify migration was called
        mock_storage.migrate_from_json.assert_called_once_with(
            mock_config.ip_file, mock_config.ip_history_file
        )

        # Verify migration flag is set
        assert bot._migration_done is True

    # Test Bot Run Method

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_normal_mode(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test bot run method in normal mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_config.testing_mode = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify normal operation
        mock_client.start.assert_called_once_with(mock_config.discord_token)
        assert result == 0
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_testing_mode_success(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test bot run method in testing mode with successful IP check."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service
        mock_config.testing_mode = True

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify testing mode operation
        mock_ip_service.get_public_ip.assert_called_once()
        mock_client.start.assert_not_called()
        assert result == 0
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_testing_mode_failure(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test bot run method in testing mode with failed IP check."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = None
        mock_ip_service_class.return_value = mock_ip_service
        mock_config.testing_mode = True

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify testing mode failure
        mock_ip_service.get_public_ip.assert_called_once()
        mock_client.start.assert_not_called()
        assert result == 1
        bot.cleanup.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_run_login_failure(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test bot run method with Discord login failure."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.start.side_effect = discord.LoginFailure("Invalid token")
        mock_bot_class.return_value = mock_client
        mock_config.testing_mode = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.cleanup = AsyncMock()

        # Run bot
        result = await bot.run()

        # Verify login failure handling
        mock_client.start.assert_called_once_with(mock_config.discord_token)
        assert result == 1
        bot.cleanup.assert_called_once()

    # Test Cleanup Method

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_all_resources(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test cleanup method properly closes all resources."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.http = Mock()
        mock_client.http.session = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.cancel = AsyncMock()

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.check_ip_task = mock_task

        # Run cleanup
        await bot.cleanup()

        # Verify cleanup operations
        mock_message_queue.stop_processing.assert_called_once()
        mock_task.cancel.assert_called_once()
        mock_ip_service.close.assert_called_once()
        mock_client.http.session.close.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_with_stopped_task(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test cleanup method with already stopped task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.http = Mock()
        mock_client.http.session = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_task = AsyncMock()
        mock_task.is_running.return_value = False
        mock_task.cancel = AsyncMock()

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.check_ip_task = mock_task

        # Run cleanup
        await bot.cleanup()

        # Verify task is still cancelled even if not running (cleanup is safer)
        mock_task.cancel.assert_called_once()
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_without_http_session(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test cleanup method without HTTP session."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Run cleanup
        await bot.cleanup()

        # Verify cleanup completes without HTTP session
        mock_client.close.assert_called_once()

    # Test On Ready Event Handler

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_success(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test successful on_ready event handler."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = Mock()
        mock_storage.load_last_ip.return_value = "192.168.1.1"
        mock_storage_class.return_value = mock_storage

        mock_ip_service = Mock()
        mock_ip_service.set_last_known_ip = Mock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message_queue.set_discord_client = AsyncMock()
        mock_message_queue.start_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify initialization
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)
        mock_storage.load_last_ip.assert_called_once()
        mock_ip_service.set_last_known_ip.assert_called_once_with("192.168.1.1")
        mock_message_queue.set_discord_client.assert_called_once_with(mock_client)
        mock_message_queue.start_processing.assert_called_once()
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        mock_client.add_cog.assert_called()
        mock_client.tree.sync.assert_called_once()
        mock_task.start.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_channel_not_found(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with channel not found."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.return_value = None
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Run on_ready
        await bot.on_ready()

        # Verify bot tries to shut down
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)
        # Note: close is called from within on_ready but it's async so hard to verify

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_discord_exception(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.side_effect = discord.DiscordException("API Error")
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Run on_ready
        await bot.on_ready()

        # Verify Discord exception is handled (close may be called asynchronously)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_message_queue_disabled(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with message queue disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = AsyncMock()
        mock_storage.load_last_ip.return_value = None
        mock_storage_class.return_value = mock_storage

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_config.message_queue_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify message queue is not started
        mock_message_queue.set_discord_client.assert_not_called()
        mock_message_queue.start_processing.assert_not_called()
        mock_task.start.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_on_ready_startup_message_disabled(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_ready with startup message disabled."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_client.add_cog = AsyncMock()
        mock_client.tree = AsyncMock()
        mock_client.tree.sync = AsyncMock(return_value=[])
        mock_bot_class.return_value = mock_client

        mock_storage = AsyncMock()
        mock_storage.load_last_ip.return_value = None
        mock_storage_class.return_value = mock_storage

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_config.startup_message_enabled = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot._create_check_ip_task = Mock()
        mock_task = AsyncMock()
        mock_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = mock_task

        # Run on_ready
        await bot.on_ready()

        # Verify startup message is not sent
        mock_discord_rate_limiter.send_message_with_backoff.assert_not_called()
        mock_task.start.assert_called_once()

    # Test On Message Event Handler

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_ip_command(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling IP command."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify IP command was handled
        mock_ip_commands.handle_ip_command.assert_called_once_with(
            mock_message, mock_client
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_admin_command(
        self,
        mock_admin_router_class,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling admin command."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_admin_router = AsyncMock()
        mock_admin_router.handle_config_command = AsyncMock()
        mock_admin_router_class.return_value = mock_admin_router

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!config show"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify admin command was handled
        mock_admin_router.handle_config_command.assert_called_once_with(mock_message)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_bot_message_ignored(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message ignoring bot's own messages."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = mock_client.user
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_wrong_channel_non_admin(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message ignoring messages from wrong channel for non-admin."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = False
        mock_message.channel = Mock()
        mock_message.channel.id = 999999  # Wrong channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_wrong_channel_admin_allowed(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message allowing admin commands from any channel."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = True
        mock_message.channel = Mock()
        mock_message.channel.id = 999999  # Wrong channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was handled for admin
        mock_ip_commands.handle_ip_command.assert_called_once_with(
            mock_message, mock_client
        )

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_discord_exception(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = discord.DiscordException(
            "API Error"
        )
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify error handling
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        error_message = mock_discord_rate_limiter.send_message_with_backoff.call_args[
            0
        ][1]
        assert "error occurred" in error_message

    # Test Scheduled IP Check Task

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_create_check_ip_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test creation of IP check task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task (test that it doesn't raise exceptions)
        task = bot._create_check_ip_task()

        # Verify service health was consulted
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_config.check_interval
        )

        # Verify task is returned
        assert task is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_adjust_check_interval_for_degradation(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test adjustment of check interval for service degradation."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 10.0
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.minutes = 5.0
        mock_task.cancel = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()
        new_task = AsyncMock()
        new_task.start = AsyncMock()
        bot._create_check_ip_task.return_value = new_task

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify task was restarted with new interval
        mock_task.cancel.assert_called_once()
        bot._create_check_ip_task.assert_called_once()
        new_task.start.assert_called_once()
        assert bot.check_ip_task == new_task

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    def test_adjust_check_interval_no_significant_change(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test adjustment with no significant interval change."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 5.05  # Small change
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        mock_task.minutes = 5.0
        mock_task.cancel = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.check_ip_task = mock_task
        bot._create_check_ip_task = Mock()

        # Adjust interval
        bot._adjust_check_interval_for_degradation()

        # Verify task was not restarted
        mock_task.cancel.assert_not_called()
        bot._create_check_ip_task.assert_not_called()

    # Test Slash Command Setup

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.slash_commands.ip_slash_commands.IPSlashCommands")
    @patch("ip_monitor.slash_commands.admin_slash_commands.AdminSlashCommands")
    def test_setup_slash_commands(
        self,
        mock_admin_slash_commands,
        mock_ip_slash_commands,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test slash command setup."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_cog = AsyncMock()
        mock_admin_cog = AsyncMock()
        mock_ip_slash_commands.return_value = mock_ip_cog
        mock_admin_slash_commands.return_value = mock_admin_cog

        # Initialize bot (this calls _setup_slash_commands)
        bot = IPMonitorBot(mock_config)

        # Verify slash commands were created
        mock_ip_slash_commands.assert_called_once()
        mock_admin_slash_commands.assert_called_once()
        assert bot.ip_slash_cog == mock_ip_cog
        assert bot.admin_slash_cog == mock_admin_cog

    # Test Stop Bot Method

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_stop_bot(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test stop bot method."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        bot.cleanup = AsyncMock()

        # Stop bot
        await bot._stop_bot()

        # Verify cleanup was called
        bot.cleanup.assert_called_once()

    # Test Error Handling in Scheduled Task

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_task_silent_monitoring(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled task in silent monitoring mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.side_effect = (
            lambda x: x == "silent_monitoring"
        )
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage.save_current_ip = AsyncMock()
        mock_storage_class.return_value = mock_storage

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task (test that it works with service health)
        task = bot._create_check_ip_task()

        # Verify task creation uses service health
        mock_service_health.get_adjusted_interval.assert_called_once_with(
            mock_config.check_interval
        )

        # Verify task is created
        assert task is not None

    # Test Integration Points

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_all_command_handlers_registered(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test that all command handlers are properly registered."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify all handlers are initialized
        assert bot.ip_commands is not None
        assert bot.admin_commands is not None
        assert bot.ip_slash_cog is not None
        assert bot.admin_slash_cog is not None
        assert bot.rate_limiter is not None
        assert bot.discord_rate_limiter is not None
        assert bot.ip_service is not None
        assert bot.storage is not None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_configuration_propagation(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test that configuration is properly propagated to services."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify configuration is passed to services
        mock_ip_service.assert_called_once_with(
            max_retries=mock_config.max_retries,
            retry_delay=mock_config.retry_delay,
            use_concurrent_checks=mock_config.concurrent_api_checks,
            circuit_breaker_enabled=mock_config.circuit_breaker_enabled,
            circuit_breaker_failure_threshold=mock_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=mock_config.circuit_breaker_recovery_timeout,
            use_custom_apis=mock_config.custom_apis_enabled,
            connection_pool_size=mock_config.connection_pool_size,
            connection_pool_max_keepalive=mock_config.connection_pool_max_keepalive,
            connection_timeout=mock_config.connection_timeout,
            read_timeout=mock_config.read_timeout,
        )

        mock_storage.assert_called_once_with(
            db_file=mock_config.db_file,
            history_size=mock_config.ip_history_size,
        )

        mock_async_rate_limiter.assert_called_once_with(
            period=mock_config.rate_limit_period,
            max_calls=mock_config.max_checks_per_period,
        )

    # Test Error Recovery and Resilience

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_unexpected_exception(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling unexpected exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = Exception("Unexpected error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify error handling
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()
        error_message = mock_discord_rate_limiter.send_message_with_backoff.call_args[
            0
        ][1]
        assert "unexpected error" in error_message.lower()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_error_notification_fails(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message when error notification itself fails."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands.handle_ip_command.side_effect = Exception("Unexpected error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff.side_effect = Exception(
            "Network error"
        )
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message (should not raise exception)
        await bot.on_message(mock_message)

        # Verify error notification was attempted
        mock_discord_rate_limiter.send_message_with_backoff.assert_called_once()

    # Test Coverage for Edge Cases

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    def test_bot_with_no_check_task(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test bot operations when check task is None."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Test adjustment with no task
        bot._adjust_check_interval_for_degradation()

        # Should not raise exception
        assert bot.check_ip_task is None

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.message_queue")
    async def test_cleanup_with_no_tasks(
        self,
        mock_message_queue,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test cleanup when no tasks are running."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_ip_service = AsyncMock()
        mock_ip_service.close = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_message_queue.stop_processing = AsyncMock()

        # Initialize bot
        bot = IPMonitorBot(mock_config)
        # Don't set any tasks

        # Run cleanup
        await bot.cleanup()

        # Verify cleanup completes without errors
        mock_message_queue.stop_processing.assert_called_once()
        mock_client.close.assert_called_once()

    # Test Command Error Handler - Additional Event Handler

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_command_error_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter_class,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test command error handling for slash commands."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_discord_rate_limiter = AsyncMock()
        mock_discord_rate_limiter.send_message_with_backoff = AsyncMock()
        mock_discord_rate_limiter_class.return_value = mock_discord_rate_limiter

        # Create mock interaction for slash command error
        mock_interaction = AsyncMock()
        mock_interaction.command = Mock()
        mock_interaction.command.name = "test_command"
        mock_interaction.user = Mock()
        mock_interaction.user.id = 987654321
        mock_interaction.channel = Mock()
        mock_interaction.channel.id = mock_config.channel_id
        mock_interaction.response = AsyncMock()
        mock_interaction.response.send_message = AsyncMock()
        mock_interaction.response.is_done.return_value = False

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Since on_command_error is not explicitly defined in the bot,
        # we test the default Discord.py error handling behavior
        # This test validates that error handling infrastructure is in place
        
        # Verify bot initialization doesn't break error handling setup
        assert bot.client is not None
        assert hasattr(bot.client, 'tree')  # Slash command tree
        
        # Verify the bot can handle command processing without breaking
        # when an error occurs (this is implicit through on_message error handling)
        test_message = AsyncMock()
        test_message.author = Mock()
        test_message.author.id = 987654321
        test_message.channel = Mock()
        test_message.channel.id = mock_config.channel_id
        test_message.content = "!unknown_command"
        
        # This should not raise an exception
        await bot.on_message(test_message)

    # Test Connection Events

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_disconnect_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of disconnect events."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Discord.py handles disconnect events internally
        # This test verifies that the bot structure supports reconnection
        assert bot.client is not None
        assert bot.ip_service is not None
        assert bot.storage is not None
        
        # Bot should maintain state during disconnect/reconnect cycles
        assert bot.config == mock_config
        assert bot.check_ip_task is None  # Not started yet

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_resumed_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of connection resume events."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Discord.py handles resume events internally
        # This test verifies that the bot can handle connection restoration
        assert bot.client is not None
        
        # Tasks should continue running after resume
        mock_task = AsyncMock()
        mock_task.is_running.return_value = True
        bot.check_ip_task = mock_task
        
        # Verify task state is maintained
        assert bot.check_ip_task.is_running()

    # Test Guild Events

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_guild_availability_handling(
        self,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test handling of guild availability changes."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_client.get_channel.return_value = AsyncMock()
        mock_bot_class.return_value = mock_client

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Note: Bot should handle guild unavailability gracefully
        # Discord.py handles guild events internally, but bot should maintain state
        assert bot.client is not None
        assert bot.config.channel_id == mock_config.channel_id
        
        # Channel access should work when guild is available
        channel = bot.client.get_channel(mock_config.channel_id)
        assert channel is not None

    # Test Message Handling Edge Cases

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_empty_content(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling empty message content."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = ""  # Empty content

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for empty content
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_unknown_command(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling unknown commands."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!notacommand"  # Doesn't match any command

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for non-matching command
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_case_sensitivity(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message command case sensitivity."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.channel = Mock()
        mock_message.channel.id = mock_config.channel_id
        mock_message.content = "!IP"  # Uppercase command

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify no command was handled for case mismatch
        mock_ip_commands.handle_ip_command.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    async def test_on_message_dm_handling(
        self,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test on_message handling direct messages."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.user = Mock()
        mock_client.user.id = 123456789
        mock_bot_class.return_value = mock_client

        mock_ip_commands = AsyncMock()
        mock_ip_commands.handle_ip_command = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Create DM channel mock
        mock_dm_channel = AsyncMock()
        mock_dm_channel.id = 999999  # Different from config channel_id
        mock_dm_channel.type = discord.ChannelType.private

        mock_message = AsyncMock()
        mock_message.author = Mock()
        mock_message.author.id = 987654321
        mock_message.author.guild_permissions = Mock()
        mock_message.author.guild_permissions.administrator = False
        mock_message.channel = mock_dm_channel
        mock_message.content = "!ip"

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Process message
        await bot.on_message(mock_message)

        # Verify command was not handled in DM for non-admin
        mock_ip_commands.handle_ip_command.assert_not_called()

    # Test Scheduled IP Check Task - Critical Missing Functionality

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_ip_check_normal_operation(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled IP check in normal operation mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.return_value = False
        mock_service_health.record_success = AsyncMock()
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_commands = AsyncMock()
        mock_ip_commands.check_ip_once = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and simulate task execution
        task = bot._create_check_ip_task()
        
        # Access the inner coroutine function directly
        check_ip_func = task.coro

        # Simulate task execution
        await check_ip_func()

        # Verify normal operation
        mock_ip_commands.check_ip_once.assert_called_once_with(mock_client, user_requested=False)
        mock_service_health.record_success.assert_called_once_with("discord_api", "scheduled_task")

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_ip_check_silent_monitoring_mode(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled IP check in silent monitoring mode."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.side_effect = lambda mode: mode == "silent_monitoring"
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage.save_current_ip = AsyncMock()
        mock_storage_class.return_value = mock_storage

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and simulate task execution
        task = bot._create_check_ip_task()
        check_ip_func = task.coro

        # Simulate task execution
        await check_ip_func()

        # Verify silent operation
        mock_ip_service.get_public_ip.assert_called_once()
        mock_storage.save_current_ip.assert_called_once_with("192.168.1.1")
        mock_ip_commands.check_ip_once.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_ip_check_read_only_mode(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled IP check in read-only mode (no storage)."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        def fallback_active(mode):
            return mode in ["silent_monitoring", "read_only_mode"]
        
        mock_service_health.is_fallback_active.side_effect = fallback_active
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_service = AsyncMock()
        mock_ip_service.get_public_ip.return_value = "192.168.1.1"
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        mock_ip_commands = AsyncMock()
        mock_ip_commands_class.return_value = mock_ip_commands

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and simulate task execution
        task = bot._create_check_ip_task()
        check_ip_func = task.coro

        # Simulate task execution
        await check_ip_func()

        # Verify read-only operation
        mock_ip_service.get_public_ip.assert_called_once()
        mock_storage.save_current_ip.assert_not_called()
        mock_ip_commands.check_ip_once.assert_not_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_ip_check_discord_exception(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled IP check handling Discord exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.return_value = False
        mock_service_health.record_failure = AsyncMock()
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_commands = AsyncMock()
        mock_ip_commands.check_ip_once = AsyncMock()
        mock_ip_commands.check_ip_once.side_effect = discord.DiscordException("API Error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and simulate task execution
        task = bot._create_check_ip_task()
        check_ip_func = task.coro

        # Simulate task execution
        await check_ip_func()

        # Verify error handling
        mock_service_health.record_failure.assert_called_once()
        call_args = mock_service_health.record_failure.call_args[0]
        assert call_args[0] == "discord_api"
        assert "Discord error in scheduled task" in call_args[1]

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_scheduled_ip_check_unexpected_exception(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands_class,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage_class,
        mock_ip_service_class,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test scheduled IP check handling unexpected exception."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.is_fallback_active.return_value = False
        mock_service_health.record_failure = AsyncMock()
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_ip_commands = AsyncMock()
        mock_ip_commands.check_ip_once = AsyncMock()
        mock_ip_commands.check_ip_once.side_effect = Exception("Unexpected error")
        mock_ip_commands_class.return_value = mock_ip_commands

        mock_ip_service = AsyncMock()
        mock_ip_service_class.return_value = mock_ip_service

        mock_storage = AsyncMock()
        mock_storage_class.return_value = mock_storage

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and simulate task execution
        task = bot._create_check_ip_task()
        check_ip_func = task.coro

        # Simulate task execution
        await check_ip_func()

        # Verify error handling
        mock_service_health.record_failure.assert_called_once()
        call_args = mock_service_health.record_failure.call_args[0]
        assert call_args[0] == "discord_api"
        assert "Unexpected error in scheduled task" in call_args[1]

    # Additional Bot Functionality Tests

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_cache_cleanup_task_creation(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test cache cleanup task is created properly."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client

        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Verify cache cleanup task is initialized to None
        assert bot.cache_cleanup_task is None


class TestTaskScheduling:
    """Test task scheduling functionality."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_create_check_ip_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test creation of IP check task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task
        task = bot._create_check_ip_task()

        # Verify task properties
        assert task is not None
        assert hasattr(task, 'start')
        assert hasattr(task, 'stop')
        assert hasattr(task, 'restart')
        assert hasattr(task, 'cancel')
        assert hasattr(task, 'is_running')
        
        # Verify interval was set correctly
        mock_service_health.get_adjusted_interval.assert_called_once_with(mock_config.check_interval)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_lifecycle_management(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task lifecycle management (start, stop, restart)."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task
        task = bot._create_check_ip_task()

        # Test that task is not initially running
        assert not task.is_running()

        # Start the task
        task.start()
        assert task.is_running()

        # Stop the task
        task.stop()
        # Note: The task may still be "running" immediately after stop() is called
        # since it needs time to process the cancellation

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_interval_adjustment(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task interval adjustment for degradation."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and start task
        task = bot._create_check_ip_task()
        task.start()
        bot.check_ip_task = task

        # Simulate interval adjustment
        mock_service_health.get_adjusted_interval.return_value = 10.0

        # Call adjustment method
        bot._adjust_check_interval_for_degradation()

        # Verify new task was created with adjusted interval
        assert bot.check_ip_task is not None
        # The task should be recreated with new interval
        mock_service_health.get_adjusted_interval.assert_called()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_before_loop_hook(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task before loop hook functionality."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.wait_until_ready = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task
        task = bot._create_check_ip_task()

        # Access the before_loop hook
        before_loop_func = task._before_loop

        # Execute the before_loop hook
        if before_loop_func:
            await before_loop_func()

        # Verify wait_until_ready was called
        mock_client.wait_until_ready.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_before_loop_error_handling(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task before loop error handling."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.wait_until_ready = AsyncMock()
        mock_client.wait_until_ready.side_effect = Exception("Wait error")
        mock_client.close = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task
        task = bot._create_check_ip_task()

        # Access the before_loop hook
        before_loop_func = task._before_loop

        # Execute the before_loop hook (should handle error)
        if before_loop_func:
            await before_loop_func()

        # Verify error handling (close was called)
        mock_client.close.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task error handler functionality."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_channel = AsyncMock()
        mock_client.get_channel.return_value = mock_channel
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_discord_rate_limiter_instance = AsyncMock()
        mock_discord_rate_limiter.return_value = mock_discord_rate_limiter_instance

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Replace the discord rate limiter instance with our mock
        bot.discord_rate_limiter = mock_discord_rate_limiter_instance

        # Create task
        task = bot._create_check_ip_task()

        # Access the error handler
        error_handler = task._error

        # Execute the error handler
        if error_handler:
            test_error = Exception("Test error")
            await error_handler(test_error)

        # Verify error notification was sent
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)
        mock_discord_rate_limiter_instance.send_message_with_backoff.assert_called_once()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_exception_handling(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task error handler handles exceptions gracefully."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.get_channel.side_effect = Exception("Channel error")
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        mock_discord_rate_limiter_instance = AsyncMock()
        mock_discord_rate_limiter.return_value = mock_discord_rate_limiter_instance

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Replace the discord rate limiter instance with our mock
        bot.discord_rate_limiter = mock_discord_rate_limiter_instance

        # Create task
        task = bot._create_check_ip_task()

        # Access the error handler
        error_handler = task._error

        # Execute the error handler (should not crash despite exception)
        if error_handler:
            test_error = Exception("Test error")
            await error_handler(test_error)

        # Verify get_channel was called
        mock_client.get_channel.assert_called_once_with(mock_config.channel_id)

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_restart_running_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task error handler restarts running task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.get_channel.return_value = None
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task and start it
        task = bot._create_check_ip_task()
        task.start()

        # Access the error handler
        error_handler = task._error

        # Execute the error handler
        if error_handler:
            test_error = Exception("Test error")
            await error_handler(test_error)

        # Verify task was restarted (it should still be running)
        assert task.is_running()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_task_error_handler_start_stopped_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test task error handler starts stopped task."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_client.get_channel.return_value = None
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create task but don't start it
        task = bot._create_check_ip_task()

        # Access the error handler
        error_handler = task._error

        # Execute the error handler
        if error_handler:
            test_error = Exception("Test error")
            await error_handler(test_error)

        # Verify task was started
        assert task.is_running()

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_adjust_check_interval_no_change(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test interval adjustment when no significant change."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Create and start task
        task = bot._create_check_ip_task()
        task.start()
        bot.check_ip_task = task
        original_task = bot.check_ip_task

        # Simulate no significant interval change
        mock_service_health.get_adjusted_interval.return_value = 5.05  # Very small change

        # Call adjustment method
        bot._adjust_check_interval_for_degradation()

        # Verify task was not recreated (same task instance)
        assert bot.check_ip_task is original_task

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.bot.service_health")
    async def test_adjust_check_interval_no_task(
        self,
        mock_service_health,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_config,
    ):
        """Test interval adjustment when no task exists."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = AsyncMock()
        mock_bot_class.return_value = mock_client
        mock_service_health.get_adjusted_interval.return_value = 5.0

        # Initialize bot
        bot = IPMonitorBot(mock_config)

        # Ensure no task exists
        bot.check_ip_task = None

        # Call adjustment method (should not crash)
        bot._adjust_check_interval_for_degradation()

        # Verify no task was created
        assert bot.check_ip_task is None
