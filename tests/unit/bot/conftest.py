"""
Bot-specific test fixtures for IPMonitorBot tests.
"""

from unittest.mock import AsyncMock, Mock

import discord
import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig


@pytest.fixture
def mock_bot_config():
    """Enhanced bot configuration mock with comprehensive settings."""
    config = Mock(spec=AppConfig)

    # Discord settings
    config.discord_token = "test_token"
    config.channel_id = 12345

    # IP monitoring settings
    config.check_interval = 5
    config.max_retries = 3
    config.retry_delay = 1
    config.concurrent_api_checks = True

    # Circuit breaker settings
    config.circuit_breaker_enabled = True
    config.circuit_breaker_failure_threshold = 3
    config.circuit_breaker_recovery_timeout = 60

    # Rate limiting settings
    config.rate_limit_period = 300
    config.max_checks_per_period = 10

    # Storage settings
    config.db_file = "test.db"
    config.ip_history_size = 10
    config.ip_file = "test_ip.json"
    config.ip_history_file = "test_history.json"

    # HTTP connection settings
    config.connection_pool_size = 10
    config.connection_pool_max_keepalive = 5
    config.connection_timeout = 10.0
    config.read_timeout = 30.0

    # Message queue settings
    config.message_queue_enabled = True
    config.message_queue_max_size = 1000
    config.message_queue_max_age_hours = 24
    config.message_queue_batch_size = 5
    config.message_queue_process_interval = 1.0

    # Cache settings
    config.cache_enabled = True
    config.cache_ttl = 300
    config.cache_max_memory_size = 1000
    config.cache_stale_threshold = 0.8
    config.cache_cleanup_interval = 300

    # API settings
    config.custom_apis_enabled = True
    config.api_config_file = "test_apis.json"

    # Feature flags
    config.startup_message_enabled = True
    config.testing_mode = False

    return config


@pytest.fixture
def mock_discord_client():
    """Enhanced Discord client mock with full bot functionality."""
    client = AsyncMock()

    # Bot identity
    client.user = Mock()
    client.user.id = 123456789
    client.user.name = "TestBot"
    client.user.discriminator = "0001"
    client.user.mention = "<@123456789>"

    # Connection status
    client.is_ready = Mock(return_value=True)
    client.is_closed = Mock(return_value=False)
    client.latency = 0.1
    client.loop = Mock()

    # Guild and channel setup
    guild = Mock()
    guild.id = 987654321
    guild.name = "Test Guild"
    guild.member_count = 100

    channel = AsyncMock()
    channel.id = 12345
    channel.name = "test-channel"
    channel.guild = guild
    channel.send = AsyncMock()
    channel.typing = AsyncMock()

    client.get_guild = Mock(return_value=guild)
    client.get_channel = Mock(return_value=channel)
    client.guilds = [guild]

    # Command tree for slash commands
    client.tree = Mock()
    client.tree.sync = AsyncMock()
    client.tree.add_command = Mock()
    client.tree.remove_command = Mock()
    client.tree.clear_commands = Mock()

    # Event handling
    client.wait_for = AsyncMock()
    client.dispatch = Mock()

    # Connection methods
    client.login = AsyncMock()
    client.connect = AsyncMock()
    client.close = AsyncMock()
    client.run = AsyncMock()

    # HTTP session
    client.http = Mock()
    client.http.close = AsyncMock()
    client.http.session = Mock()
    client.http.session.close = AsyncMock()

    return client


@pytest.fixture
def mock_bot_storage():
    """Enhanced storage mock for bot testing."""
    storage = Mock()

    # Basic IP operations
    storage.get_current_ip = Mock(return_value="192.168.1.1")
    storage.save_current_ip = Mock()
    storage.get_ip_history = Mock(return_value=[])
    storage.add_ip_to_history = Mock()

    # Migration support
    storage.migrate_from_json = Mock()
    storage.is_migration_needed = Mock(return_value=False)

    # Database operations
    storage.close = Mock()
    storage.cleanup = Mock()

    return storage


@pytest.fixture
def mock_bot_ip_service():
    """Enhanced IP service mock for bot testing."""
    service = Mock()

    # Primary IP fetching
    service.get_current_ip = AsyncMock(return_value="192.168.1.1")
    service.check_ip_change = AsyncMock(return_value=(False, "192.168.1.1"))

    # Cache operations
    service.get_cache_info = Mock(
        return_value={
            "enabled": True,
            "cache_ttl": 300,
            "stale_threshold": 0.8,
            "stale_entries_count": 0,
            "stats": {
                "memory_entries": 0,
                "hits": 0,
                "misses": 0,
                "evictions": 0,
                "invalidations": 0,
                "refreshes": 0,
                "saves": 0,
                "loads": 0,
            },
        }
    )
    service.invalidate_cache = Mock(return_value=0)
    service.refresh_stale_cache_entries = AsyncMock(return_value=0)

    # API management
    service.get_api_stats = Mock(return_value={})
    service.test_api = AsyncMock(return_value={"success": True, "ip": "192.168.1.1"})

    # Cleanup
    service.cleanup = AsyncMock()
    service.close = AsyncMock()

    return service


@pytest.fixture
def mock_bot_commands():
    """Mock command handlers for bot testing."""
    commands = Mock()

    # IP commands
    commands.handle_ip_command = AsyncMock()
    commands.handle_history_command = AsyncMock()
    commands.handle_status_command = AsyncMock()
    commands.handle_help_command = AsyncMock()

    return commands


@pytest.fixture
def mock_bot_slash_cogs():
    """Mock slash command cogs for bot testing."""
    ip_cog = Mock()
    ip_cog.qualified_name = "IPSlashCommands"
    ip_cog.description = "IP monitoring slash commands"

    admin_cog = Mock()
    admin_cog.qualified_name = "AdminSlashCommands"
    admin_cog.description = "Admin slash commands"

    return [ip_cog, admin_cog]


@pytest.fixture
def mock_bot_message_queue():
    """Enhanced message queue mock for bot testing."""
    queue = Mock()

    # Core operations
    queue.add_message = AsyncMock()
    queue.process_messages = AsyncMock()
    queue.clear = AsyncMock()
    queue.start_processing = Mock()  # start_processing() is synchronous
    queue.stop_processing = AsyncMock()

    # Status and statistics
    queue.get_status = Mock(
        return_value={
            "enabled": True,
            "processing": False,
            "queued_messages": 0,
            "total_processed": 0,
            "total_failed": 0,
            "last_process_time": None,
            "queue_size": 0,
            "max_size": 1000,
            "oldest_message_age": 0,
            "max_age_hours": 24,
        }
    )

    # Lifecycle
    queue.cleanup = AsyncMock()

    return queue


@pytest.fixture
def mock_bot_service_health():
    """Enhanced service health monitor mock for bot testing."""
    health = Mock()

    # Status reporting
    health.get_status = Mock(
        return_value={
            "level": "NORMAL",
            "score": 100,
            "issues": [],
            "services": {
                "ip_service": {
                    "status": "healthy",
                    "last_check": "2023-01-01T12:00:00Z",
                },
                "discord_api": {
                    "status": "healthy",
                    "last_check": "2023-01-01T12:00:00Z",
                },
                "storage": {"status": "healthy", "last_check": "2023-01-01T12:00:00Z"},
            },
        }
    )

    # Health recording
    health.record_api_success = Mock()
    health.record_api_failure = Mock()
    health.record_discord_success = Mock()
    health.record_discord_failure = Mock()

    # Degradation management
    health.is_degraded = Mock(return_value=False)
    health.get_degradation_level = Mock(return_value=0)
    health.get_adjusted_interval = Mock(return_value=5.0)

    return health


@pytest.fixture
def mock_bot_rate_limiter():
    """Enhanced rate limiter mock for bot testing."""
    limiter = Mock()

    # Rate limiting operations
    limiter.is_limited = AsyncMock(return_value=(False, 0))
    limiter.record_call = AsyncMock()
    limiter.acquire = AsyncMock()
    limiter.try_acquire = AsyncMock(return_value=True)
    limiter.wait_if_limited = AsyncMock(return_value=False)

    # Status reporting
    limiter.get_status = AsyncMock(
        return_value={
            "period": 300,
            "max_calls": 10,
            "active_calls": 0,
            "remaining_calls": 10,
            "is_limited": False,
            "wait_time": 0,
            "utilization_percent": 0.0,
            "next_reset": "2023-01-01T12:05:00Z",
        }
    )

    return limiter


@pytest.fixture
def mock_bot_discord_rate_limiter():
    """Mock Discord API rate limiter for bot testing."""
    limiter = Mock()

    # Discord-specific rate limiting
    limiter.acquire_send_message = AsyncMock()
    limiter.acquire_channel_operation = AsyncMock()
    limiter.acquire_guild_operation = AsyncMock()
    limiter.send_message_with_backoff = AsyncMock()

    # Status reporting
    limiter.get_status = Mock(
        return_value={
            "active_limits": {},
            "recent_429s": 0,
            "total_requests": 0,
            "total_limited": 0,
        }
    )

    return limiter


@pytest.fixture
def mock_discord_intents():
    """Mock Discord intents for bot testing."""
    intents = Mock(spec=discord.Intents)
    intents.default = Mock(return_value=intents)
    intents.message_content = True
    intents.guilds = True
    intents.guild_messages = True
    return intents


@pytest.fixture
def mock_tasks_loop():
    """Mock tasks loop for scheduled operations."""
    loop = Mock()

    # Task control
    loop.start = Mock()  # start() is synchronous for tasks.Loop
    loop.stop = Mock()
    loop.cancel = Mock()
    loop.restart = Mock()

    # Task state
    loop.is_running = Mock(return_value=False)
    loop.is_being_cancelled = Mock(return_value=False)
    loop.failed = Mock(return_value=False)
    loop.get_task = Mock(return_value=None)

    # Task configuration
    loop.change_interval = Mock()
    loop.before_loop = Mock()
    loop.after_loop = Mock()
    loop.error = Mock()

    return loop


@pytest.fixture
def mock_bot_dependencies(
    mock_bot_config,
    mock_bot_storage,
    mock_bot_ip_service,
    mock_bot_commands,
    mock_bot_slash_cogs,
    mock_bot_message_queue,
    mock_bot_service_health,
    mock_bot_rate_limiter,
    mock_bot_discord_rate_limiter,
    mock_discord_intents,
    mock_tasks_loop,
):
    """Bundle of all bot dependencies for testing."""
    return {
        "config": mock_bot_config,
        "storage": mock_bot_storage,
        "ip_service": mock_bot_ip_service,
        "commands": mock_bot_commands,
        "slash_cogs": mock_bot_slash_cogs,
        "message_queue": mock_bot_message_queue,
        "service_health": mock_bot_service_health,
        "rate_limiter": mock_bot_rate_limiter,
        "discord_rate_limiter": mock_bot_discord_rate_limiter,
        "intents": mock_discord_intents,
        "tasks_loop": mock_tasks_loop,
    }


@pytest.fixture
def mock_bot_message():
    """Enhanced Discord message mock for bot testing."""
    message = Mock()

    # Message author
    message.author = Mock()
    message.author.id = 987654321
    message.author.name = "TestUser"
    message.author.discriminator = "0001"
    message.author.mention = "<@987654321>"
    message.author.bot = False
    message.author.guild_permissions = Mock()
    message.author.guild_permissions.administrator = False

    # Message content and metadata
    message.content = "!test"
    message.clean_content = "!test"
    message.id = 1234567890
    message.created_at = Mock()
    message.edited_at = None

    # Channel and guild info
    message.channel = Mock()
    message.channel.id = 12345
    message.channel.name = "test-channel"
    message.channel.send = AsyncMock()
    message.channel.typing = AsyncMock()

    message.guild = Mock()
    message.guild.id = 987654321
    message.guild.name = "Test Guild"

    # Message operations
    message.reply = AsyncMock()
    message.edit = AsyncMock()
    message.delete = AsyncMock()
    message.add_reaction = AsyncMock()

    return message


@pytest.fixture
def mock_bot_admin_message(mock_bot_message):
    """Enhanced admin message mock for bot testing."""
    message = mock_bot_message
    message.author.name = "AdminUser"
    message.author.guild_permissions.administrator = True
    message.content = "!admin test"
    return message


@pytest.fixture
def mock_bot_instance(
    mock_discord_client,
    mock_bot_config,
    mock_bot_storage,
    mock_bot_ip_service,
    mock_bot_commands,
    mock_bot_slash_cogs,
    mock_bot_message_queue,
    mock_bot_service_health,
    mock_bot_rate_limiter,
    mock_bot_discord_rate_limiter,
    mock_discord_intents,
    mock_tasks_loop,
):
    """Pre-configured IPMonitorBot instance for testing."""
    from unittest.mock import patch

    with patch("ip_monitor.bot.commands.Bot", return_value=mock_discord_client):
        with patch(
            "ip_monitor.bot.discord.Intents.default", return_value=mock_discord_intents
        ):
            with patch("ip_monitor.bot.IPService", return_value=mock_bot_ip_service):
                with patch(
                    "ip_monitor.bot.SQLiteIPStorage", return_value=mock_bot_storage
                ):
                    with patch(
                        "ip_monitor.bot.AsyncRateLimiter",
                        return_value=mock_bot_rate_limiter,
                    ):
                        with patch(
                            "ip_monitor.bot.DiscordRateLimiter",
                            return_value=mock_bot_discord_rate_limiter,
                        ):
                            with patch(
                                "ip_monitor.bot.IPCommands",
                                return_value=mock_bot_commands,
                            ):
                                with patch(
                                    "ip_monitor.bot.AdminCommandRouter",
                                    return_value=mock_bot_commands,
                                ):
                                    with patch(
                                        "ip_monitor.bot.message_queue",
                                        mock_bot_message_queue,
                                    ):
                                        with patch(
                                            "ip_monitor.bot.service_health",
                                            mock_bot_service_health,
                                        ):
                                            bot = IPMonitorBot(config=mock_bot_config)

                                            # Override created services with our mocks
                                            bot.storage = mock_bot_storage
                                            bot.ip_service = mock_bot_ip_service
                                            bot.commands = mock_bot_commands
                                            bot.admin_commands = mock_bot_commands
                                            bot.message_queue = mock_bot_message_queue
                                            bot.service_health = mock_bot_service_health
                                            bot.rate_limiter = mock_bot_rate_limiter
                                            bot.discord_rate_limiter = (
                                                mock_bot_discord_rate_limiter
                                            )
                                            bot.ip_slash_cog = mock_bot_slash_cogs[0]
                                            bot.admin_slash_cog = mock_bot_slash_cogs[1]

                                            return bot
