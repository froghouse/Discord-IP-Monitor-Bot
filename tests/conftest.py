import os
import sys
import sqlite3
import tempfile
from unittest.mock import AsyncMock, Mock
from pathlib import Path

import pytest
import aiohttp
from aiohttp import web

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


@pytest.fixture
def mock_admin_message():
    """Create a mock Discord message with admin permissions."""
    message = Mock()
    message.author = Mock()
    message.author.id = 987654321
    message.author.name = "AdminUser"
    message.author.guild_permissions = Mock()
    message.author.guild_permissions.administrator = True
    message.channel = Mock()
    message.channel.id = 12345
    message.channel.send = AsyncMock()
    message.content = "!admin"
    return message


@pytest.fixture
def mock_non_admin_message():
    """Create a mock Discord message without admin permissions."""
    message = Mock()
    message.author = Mock()
    message.author.id = 987654322
    message.author.name = "RegularUser"
    message.author.guild_permissions = Mock()
    message.author.guild_permissions.administrator = False
    message.channel = Mock()
    message.channel.id = 12345
    message.channel.send = AsyncMock()
    message.content = "!user"
    return message


# Database Test Fixtures
@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database file path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        temp_path = temp_file.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_db_connection(temp_db_path):
    """Create a temporary SQLite database connection with test schema."""
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    
    # Create test schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS current_ip (
            id INTEGER PRIMARY KEY,
            ip TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ip_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_ip_history_timestamp 
        ON ip_history(timestamp)
    """)
    
    conn.commit()
    
    yield conn
    
    conn.close()


@pytest.fixture
def sqlite_storage(temp_db_path):
    """Create a SQLiteIPStorage instance with temporary database."""
    from ip_monitor.storage import SQLiteIPStorage
    return SQLiteIPStorage(temp_db_path, history_size=10)


@pytest.fixture
def sqlite_storage_with_data(sqlite_storage):
    """Create a SQLiteIPStorage instance with test data."""
    # Insert test data
    test_ips = [
        ("192.168.1.1", "2023-01-01T12:00:00Z"),
        ("192.168.1.2", "2023-01-01T13:00:00Z"),
        ("192.168.1.3", "2023-01-01T14:00:00Z"),
    ]
    
    with sqlite3.connect(sqlite_storage.db_file) as conn:
        cursor = conn.cursor()
        
        # Add current IP
        cursor.execute(
            "INSERT INTO current_ip (ip, timestamp) VALUES (?, ?)",
            test_ips[-1]
        )
        
        # Add history in reverse order so chronological order is correct
        for ip, timestamp in reversed(test_ips):
            cursor.execute(
                "INSERT INTO ip_history (ip, timestamp) VALUES (?, ?)",
                (ip, timestamp)
            )
        
        conn.commit()
    
    return sqlite_storage


# HTTP Mock Server Fixtures
@pytest.fixture
async def mock_ip_api_server():
    """Create a mock HTTP server for IP API testing."""
    import asyncio
    responses = {
        "/json": {"ip": "203.0.113.1"},
        "/text": "203.0.113.1",
        "/custom": {"origin": "203.0.113.1"},
        "/slow": {"ip": "203.0.113.1"},  # Will add delay
        "/error": None,  # Will return 500 error
    }
    
    async def json_handler(request):
        return web.json_response(responses["/json"])
    
    async def text_handler(request):
        return web.Response(text=responses["/text"])
    
    async def custom_handler(request):
        return web.json_response(responses["/custom"])
    
    async def slow_handler(request):
        await asyncio.sleep(2)  # Simulate slow response
        return web.json_response(responses["/slow"])
    
    async def error_handler(request):
        return web.Response(status=500, text="Internal Server Error")
    
    app = web.Application()
    app.router.add_get("/json", json_handler)
    app.router.add_get("/text", text_handler)
    app.router.add_get("/custom", custom_handler)
    app.router.add_get("/slow", slow_handler)
    app.router.add_get("/error", error_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    
    port = site._server.sockets[0].getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    
    yield {
        "base_url": base_url,
        "port": port,
        "responses": responses,
        "endpoints": {
            "json": f"{base_url}/json",
            "text": f"{base_url}/text",
            "custom": f"{base_url}/custom",
            "slow": f"{base_url}/slow",
            "error": f"{base_url}/error",
        }
    }
    
    await runner.cleanup()


# Enhanced HTTP Mock Fixtures
@pytest.fixture
async def http_mock_fixture():
    """Create enhanced HTTP mock fixture for integration testing."""
    from tests.utils.http_server_mocks import HTTPMockFixture
    
    fixture = HTTPMockFixture()
    yield fixture
    await fixture.cleanup()


@pytest.fixture
async def mock_api_server():
    """Create a single mock API server for testing."""
    from tests.utils.http_server_mocks import MockIPAPIServer
    
    server = MockIPAPIServer()
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def mock_api_cluster():
    """Create a cluster of mock API servers for testing."""
    from tests.utils.http_server_mocks import MockAPICluster
    
    cluster = MockAPICluster(server_count=3)
    await cluster.start()
    yield cluster
    await cluster.stop()


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx client for testing."""
    client = Mock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    
    # Default successful response
    response = Mock()
    response.status_code = 200
    response.text = "203.0.113.1"
    response.json.return_value = {"ip": "203.0.113.1"}
    response.raise_for_status = Mock()
    
    client.get.return_value = response
    
    return client


@pytest.fixture
def mock_httpx_responses():
    """Create configurable mock HTTP responses."""
    class MockResponse:
        def __init__(self, status_code=200, text="", json_data=None):
            self.status_code = status_code
            self.text = text
            self._json_data = json_data or {}
        
        def json(self):
            return self._json_data
        
        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPError(f"HTTP {self.status_code}")
    
    return MockResponse


# Enhanced Discord Bot Mock Fixtures
@pytest.fixture
def mock_discord_client():
    """Enhanced Discord client mock with comprehensive API coverage."""
    client = AsyncMock()
    
    # Bot user
    client.user = Mock()
    client.user.id = 123456789
    client.user.name = "TestBot"
    client.user.discriminator = "0001"
    client.user.mention = "<@123456789>"
    
    # Connection status
    client.is_ready = Mock(return_value=True)
    client.is_closed = Mock(return_value=False)
    client.latency = 0.1
    
    # Guild and channel mocks
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
    
    return client


@pytest.fixture
def mock_discord_interaction():
    """Create a mock Discord interaction for slash commands."""
    interaction = AsyncMock()
    
    # User info
    interaction.user = Mock()
    interaction.user.id = 987654321
    interaction.user.name = "TestUser"
    interaction.user.discriminator = "0001"
    interaction.user.guild_permissions = Mock()
    interaction.user.guild_permissions.administrator = True
    
    # Guild and channel info
    interaction.guild_id = 987654321
    interaction.channel_id = 12345
    interaction.guild = Mock()
    interaction.guild.id = 987654321
    interaction.channel = Mock()
    interaction.channel.id = 12345
    
    # Response methods
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    # Command info
    interaction.command = Mock()
    interaction.command.name = "test"
    interaction.data = {"name": "test", "options": []}
    
    return interaction


@pytest.fixture
def mock_discord_cog():
    """Create a mock Discord cog for testing."""
    from discord.ext import commands
    
    cog = Mock(spec=commands.Cog)
    cog.qualified_name = "TestCog"
    cog.description = "Test cog for testing"
    cog.get_commands.return_value = []
    
    return cog
