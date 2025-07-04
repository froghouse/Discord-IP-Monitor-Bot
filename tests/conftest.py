import asyncio
import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_config():
    """Create a mock configuration object."""
    config = Mock()
    config.check_interval = 300
    config.max_retries = 3
    config.retry_delay = 30
    config.channel_id = 12345
    config.bot_token = "test_token"
    config.circuit_breaker_enabled = True
    config.circuit_breaker_failure_threshold = 3
    config.circuit_breaker_recovery_timeout = 120
    config.message_queue_enabled = True
    config.message_queue_max_size = 1000
    config.message_queue_max_age_hours = 24
    config.cache_enabled = True
    config.cache_ttl = 300
    config.cache_max_memory_size = 1000
    config.rate_limit_period = 300
    config.max_checks_per_period = 10
    config.ip_history_size = 10
    config.startup_message_enabled = True
    config.custom_apis_enabled = True
    config.connection_pool_size = 10
    config.connection_timeout = 10.0
    config.read_timeout = 30.0
    return config


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = AsyncMock()
    bot.user = Mock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.latency = 0.1
    bot.is_ready.return_value = True

    # Mock channel
    channel = AsyncMock()
    channel.send = AsyncMock()
    bot.get_channel.return_value = channel

    return bot


@pytest.fixture
def mock_ctx():
    """Create a mock Discord context."""
    ctx = AsyncMock()
    ctx.author = Mock()
    ctx.author.id = 987654321
    ctx.author.name = "TestUser"
    ctx.author.guild_permissions = Mock()
    ctx.author.guild_permissions.administrator = True
    ctx.channel = Mock()
    ctx.channel.id = 12345
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()
    return ctx


@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = Mock()
    cache.get = Mock(return_value=None)
    cache.set = Mock()
    cache.invalidate = Mock()
    cache.clear = Mock()
    cache.get_status = Mock(
        return_value={
            "memory_entries": 0,
            "hit_rate": 0.0,
            "operations": {"hits": 0, "misses": 0, "sets": 0},
        }
    )
    return cache


@pytest.fixture
def mock_message_queue():
    """Create a mock message queue."""
    queue = Mock()
    queue.add_message = AsyncMock()
    queue.get_status = Mock(
        return_value={
            "queued_messages": 0,
            "processing": False,
            "total_processed": 0,
            "total_failed": 0,
        }
    )
    queue.clear = AsyncMock()
    queue.start_processing = AsyncMock()
    queue.stop_processing = AsyncMock()
    return queue


@pytest.fixture
def mock_service_health():
    """Create a mock service health monitor."""
    health = Mock()
    health.get_status = Mock(
        return_value={"level": "NORMAL", "score": 100, "issues": []}
    )
    health.record_api_success = Mock()
    health.record_api_failure = Mock()
    return health


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter."""
    limiter = Mock()
    limiter.is_limited = AsyncMock(return_value=(False, 0))
    limiter.record_call = AsyncMock()
    limiter.get_status = AsyncMock(
        return_value={
            "is_limited": False,
            "remaining_calls": 10,
            "period": 300,
            "max_calls": 10,
        }
    )
    return limiter


@pytest.fixture
def mock_circuit_breaker():
    """Create a mock circuit breaker."""
    breaker = Mock()
    breaker.is_open = False
    breaker.call = AsyncMock()
    breaker.get_status = Mock(
        return_value={"state": "CLOSED", "failure_count": 0, "success_count": 0}
    )
    return breaker


@pytest.fixture
def mock_ip_api_config():
    """Create a mock IP API configuration."""
    config = Mock()
    config.get_all_apis = Mock(return_value=[])
    config.add_api = Mock(return_value=True)
    config.remove_api = Mock(return_value=True)
    config.enable_api = Mock(return_value=True)
    config.disable_api = Mock(return_value=True)
    config.get_performance_stats = Mock(return_value={})
    config.test_api = AsyncMock(return_value={"success": True, "ip": "1.2.3.4"})
    return config


@pytest.fixture
def sample_ip_address():
    """Sample IP address for testing."""
    return "192.168.1.1"


@pytest.fixture
def sample_ip_history():
    """Sample IP history for testing."""
    return [
        {"ip": "192.168.1.1", "timestamp": "2023-01-01T12:00:00Z"},
        {"ip": "192.168.1.2", "timestamp": "2023-01-01T13:00:00Z"},
        {"ip": "192.168.1.3", "timestamp": "2023-01-01T14:00:00Z"},
    ]


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_client():
    """Create a mock Discord client."""
    client = Mock()
    client.user = Mock()
    client.user.id = 123456789
    client.user.name = "TestBot"
    return client


@pytest.fixture
def mock_ip_service():
    """Create a mock IP service."""
    service = Mock()
    service.get_current_ip = AsyncMock(return_value="192.168.1.1")
    service.get_cache_info = Mock(return_value={
        'enabled': True,
        'cache_ttl': 300,
        'stale_threshold': 0.8,
        'stale_entries_count': 0,
        'stats': {
            'memory_entries': 0,
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'invalidations': 0,
            'refreshes': 0,
            'saves': 0,
            'loads': 0,
        }
    })
    service.invalidate_cache = Mock(return_value=0)
    service.refresh_stale_cache_entries = AsyncMock(return_value=0)
    return service


@pytest.fixture
def mock_storage():
    """Create a mock storage."""
    storage = Mock()
    storage.get_current_ip = Mock(return_value="192.168.1.1")
    storage.save_current_ip = Mock()
    storage.get_ip_history = Mock(return_value=[])
    return storage


@pytest.fixture
def mock_stop_callback():
    """Create a mock stop callback."""
    return AsyncMock()


@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    message = Mock()
    message.author = Mock()
    message.author.id = 987654321
    message.author.name = "TestUser"
    message.author.guild_permissions = Mock()
    message.author.guild_permissions.administrator = False
    message.channel = Mock()
    message.channel.id = 12345
    message.channel.send = AsyncMock()
    message.content = "!test"
    return message
