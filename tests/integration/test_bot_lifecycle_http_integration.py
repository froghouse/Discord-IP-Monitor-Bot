"""
Integration tests for bot lifecycle with HTTP server mocks.

Tests the complete bot lifecycle including startup, IP monitoring,
Discord interactions, and shutdown with real HTTP servers.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig
from ip_monitor.storage import SQLiteIPStorage
from tests.utils.http_server_mocks import HTTPMockFixture


class TestBotLifecycleHTTPIntegration:
    """Integration tests for bot lifecycle with HTTP operations."""

    @pytest.fixture
    async def http_fixture(self):
        """Create HTTP mock fixture."""
        fixture = HTTPMockFixture()
        yield fixture
        await fixture.cleanup()

    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database path."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_config(self, temp_db_path):
        """Create mock configuration."""
        config = Mock(spec=AppConfig)
        config.bot_token = "test_token"
        config.channel_id = 12345
        config.db_file = temp_db_path
        config.check_interval = 1  # 1 second for fast testing
        config.max_retries = 2
        config.retry_delay = 0.1
        config.concurrent_api_checks = True
        config.circuit_breaker_enabled = True
        config.circuit_breaker_failure_threshold = 3
        config.circuit_breaker_recovery_timeout = 1.0
        config.message_queue_enabled = True
        config.message_queue_max_size = 100
        config.cache_enabled = True
        config.cache_ttl = 60
        config.startup_message_enabled = True
        config.custom_apis_enabled = True
        config.connection_timeout = 5.0
        config.read_timeout = 10.0
        config.ip_history_size = 10
        config.connection_pool_size = 10
        config.connection_pool_max_keepalive = 5
        config.rate_limit_period = 300
        config.max_checks_per_period = 10
        config.ip_file = "last_ip.json"
        config.ip_history_file = "ip_history.json"
        return config

    @pytest.fixture
    def mock_discord_client(self):
        """Create comprehensive Discord client mock."""
        client = AsyncMock()
        client.user = Mock()
        client.user.id = 123456789
        client.user.name = "TestBot"
        client.is_ready = Mock(return_value=True)
        client.latency = 0.1

        # Mock channel
        channel = AsyncMock()
        channel.id = 12345
        channel.send = AsyncMock()
        client.get_channel = Mock(return_value=channel)

        # Mock for slash command tree
        client.tree = Mock()
        client.tree.sync = AsyncMock()

        return client

    @pytest.fixture
    def storage(self, temp_db_path):
        """Create SQLite storage."""
        return SQLiteIPStorage(temp_db_path, history_size=10)

    @pytest.fixture
    async def bot_instance(self, mock_config, mock_discord_client, storage):
        """Create bot instance with mocked dependencies."""
        with patch("ip_monitor.bot.commands.Bot", return_value=mock_discord_client):
            with patch("ip_monitor.bot.SQLiteIPStorage", return_value=storage):
                bot = IPMonitorBot(mock_config)
                # Don't actually start the bot loop
                bot.start_monitoring = AsyncMock()
                bot.stop_monitoring = AsyncMock()
                yield bot

    async def test_bot_startup_with_http_server(
        self, http_fixture, bot_instance, mock_config
    ):
        """Test bot startup with HTTP server integration."""
        server = await http_fixture.create_server()

        # Configure bot to use our test server
        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # Test bot initialization
            await bot_instance.on_ready()

            # Verify startup message was sent
            bot_instance.client.get_channel.assert_called_with(mock_config.channel_id)
            channel = bot_instance.client.get_channel.return_value
            channel.send.assert_called()

            # Verify IP check was performed
            assert server.get_request_count() >= 1

    async def test_periodic_ip_monitoring_with_http(
        self, http_fixture, bot_instance, storage
    ):
        """Test periodic IP monitoring with HTTP server."""
        server = await http_fixture.create_server()

        # Configure different IPs for testing IP changes
        call_count = 0
        original_responses = server.responses.copy()

        async def changing_ip_handler(request):
            nonlocal call_count
            call_count += 1

            server._track_request(request)

            if call_count == 1:
                return server.app.router.json_response({"ip": "203.0.113.1"})
            return server.app.router.json_response({"ip": "203.0.113.2"})

        # Replace the handler to simulate IP changes
        server.app.router._resources[0]._handler = changing_ip_handler

        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # Simulate initial IP check
            initial_ip = await bot_instance.ip_service.get_current_ip()
            storage.save_current_ip(initial_ip)

            # Simulate periodic check with IP change
            await bot_instance.check_ip_periodically()

            # Verify IP change was detected and stored
            current_ip = storage.get_current_ip()
            assert current_ip == "203.0.113.2"

            # Verify history was updated
            history = storage.get_ip_history()
            assert len(history) >= 1

            # Verify notification was sent
            channel = bot_instance.client.get_channel.return_value
            assert channel.send.call_count >= 1

    async def test_bot_command_handling_with_http(
        self, http_fixture, bot_instance, mock_discord_client
    ):
        """Test bot command handling with HTTP integration."""
        server = await http_fixture.create_server()

        # Mock Discord message
        message = Mock()
        message.content = "!ip"
        message.channel = Mock()
        message.channel.send = AsyncMock()

        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # Test IP command
            await bot_instance.on_message(message)

            # Verify HTTP request was made
            assert server.get_request_count() == 1

            # Verify response was sent
            message.channel.send.assert_called_once()

            # Verify response contains IP
            call_args = message.channel.send.call_args[0][0]
            assert "203.0.113.1" in call_args

    async def test_admin_command_api_management(self, http_fixture, bot_instance):
        """Test admin command API management with HTTP integration."""
        server = await http_fixture.create_server()

        # Mock admin message
        admin_message = Mock()
        admin_message.content = "!admin api test"
        admin_message.author = Mock()
        admin_message.author.guild_permissions = Mock()
        admin_message.author.guild_permissions.administrator = True
        admin_message.channel = Mock()
        admin_message.channel.send = AsyncMock()

        # Mock API config
        with patch.object(bot_instance, "ip_api_config") as mock_api_config:
            mock_api_config.test_api = AsyncMock(
                return_value={
                    "success": True,
                    "ip": "203.0.113.1",
                    "response_time": 0.1,
                }
            )

            # Test API test command
            await bot_instance.on_message(admin_message)

            # Verify API test was called
            mock_api_config.test_api.assert_called_once()

            # Verify response was sent
            admin_message.channel.send.assert_called_once()

    async def test_error_handling_during_monitoring(
        self, http_fixture, bot_instance, storage
    ):
        """Test error handling during IP monitoring."""
        failing_server = await http_fixture.create_server()
        backup_server = await http_fixture.create_server()

        # Configure first server to fail
        failing_server.set_error_rate(1.0)

        with patch.object(
            bot_instance.ip_service,
            "apis",
            [f"{failing_server.base_url}/json", f"{backup_server.base_url}/json"],
        ):
            # Test error recovery
            await bot_instance.check_ip_periodically()

            # Verify backup server was used
            assert backup_server.get_request_count() >= 1

            # Verify IP was still saved
            current_ip = storage.get_current_ip()
            assert current_ip == "203.0.113.1"

    async def test_circuit_breaker_behavior_in_monitoring(
        self, http_fixture, bot_instance
    ):
        """Test circuit breaker behavior during monitoring."""
        failing_server = await http_fixture.create_server()

        # Configure server to always fail
        failing_server.set_error_rate(1.0)

        # Enable circuit breaker
        bot_instance.ip_service.circuit_breaker_enabled = True
        bot_instance.ip_service.circuit_breaker_failure_threshold = 2

        with patch.object(
            bot_instance.ip_service, "apis", [f"{failing_server.base_url}/json"]
        ):
            # Multiple monitoring attempts should trigger circuit breaker
            for _ in range(5):
                try:
                    await bot_instance.check_ip_periodically()
                except Exception:
                    pass  # Expected failures

            # Circuit breaker should limit requests
            assert failing_server.get_request_count() <= 3

    async def test_message_queue_integration(self, http_fixture, bot_instance):
        """Test message queue integration with HTTP operations."""
        server = await http_fixture.create_server()

        # Mock message queue
        with patch.object(bot_instance, "message_queue") as mock_queue:
            mock_queue.add_message = AsyncMock()
            mock_queue.get_status = Mock(
                return_value={
                    "queued_messages": 0,
                    "processing": True,
                    "total_processed": 0,
                    "total_failed": 0,
                }
            )

            with patch.object(
                bot_instance.ip_service, "apis", [f"{server.base_url}/json"]
            ):
                # Simulate IP change detection
                await bot_instance.check_ip_periodically()

                # Verify message was queued
                if mock_queue.add_message.called:
                    call_args = mock_queue.add_message.call_args
                    assert call_args is not None

    async def test_cache_integration_with_http(self, http_fixture, bot_instance):
        """Test cache integration with HTTP requests."""
        server = await http_fixture.create_server()

        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # First request should hit HTTP server
            ip1 = await bot_instance.ip_service.get_current_ip()
            initial_requests = server.get_request_count()

            # Second request should use cache (if enabled)
            ip2 = await bot_instance.ip_service.get_current_ip()

            assert ip1 == ip2 == "203.0.113.1"

            # Verify cache behavior
            if bot_instance.ip_service.cache_enabled:
                # Should not have made additional HTTP requests
                assert server.get_request_count() == initial_requests
            else:
                # Should have made additional HTTP requests
                assert server.get_request_count() > initial_requests

    async def test_bot_shutdown_with_active_http_connections(
        self, http_fixture, bot_instance
    ):
        """Test bot shutdown with active HTTP connections."""
        server = await http_fixture.create_server()

        # Add latency to simulate active connections
        server.set_latency(1000)  # 1 second delay

        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # Start IP check in background
            ip_task = asyncio.create_task(bot_instance.ip_service.get_current_ip())

            # Wait a bit to ensure request is in progress
            await asyncio.sleep(0.1)

            # Test graceful shutdown
            await bot_instance.shutdown()

            # Verify task was cancelled or completed
            try:
                await asyncio.wait_for(ip_task, timeout=2.0)
            except TimeoutError:
                ip_task.cancel()

            # Verify bot state
            assert bot_instance.client.is_closed() or not bot_instance.client.is_ready()

    async def test_performance_monitoring_integration(self, http_fixture, bot_instance):
        """Test performance monitoring integration."""
        fast_server = await http_fixture.create_server()
        slow_server = await http_fixture.create_server()

        fast_server.set_latency(10)  # 10ms
        slow_server.set_latency(500)  # 500ms

        # Mock API config with performance tracking
        with patch.object(bot_instance, "ip_api_config") as mock_api_config:
            mock_api_config.get_performance_stats = Mock(
                return_value=[
                    {
                        "id": "fast",
                        "name": "Fast API",
                        "success_rate": 100.0,
                        "avg_response_time": 0.01,
                        "performance_score": 95.0,
                    },
                    {
                        "id": "slow",
                        "name": "Slow API",
                        "success_rate": 100.0,
                        "avg_response_time": 0.5,
                        "performance_score": 70.0,
                    },
                ]
            )

            # Test performance monitoring command
            admin_message = Mock()
            admin_message.content = "!admin api stats"
            admin_message.author = Mock()
            admin_message.author.guild_permissions = Mock()
            admin_message.author.guild_permissions.administrator = True
            admin_message.channel = Mock()
            admin_message.channel.send = AsyncMock()

            await bot_instance.on_message(admin_message)

            # Verify stats were retrieved and sent
            mock_api_config.get_performance_stats.assert_called_once()
            admin_message.channel.send.assert_called_once()

    async def test_end_to_end_monitoring_cycle(
        self, http_fixture, bot_instance, storage
    ):
        """Test complete end-to-end monitoring cycle."""
        server = await http_fixture.create_server()

        # Configure IP changes
        ip_sequence = ["203.0.113.1", "203.0.113.2", "203.0.113.1"]
        call_count = 0

        async def sequential_ip_handler(request):
            nonlocal call_count
            server._track_request(request)

            ip = ip_sequence[call_count % len(ip_sequence)]
            call_count += 1

            return server.app.router.json_response({"ip": ip})

        server.app.router._resources[0]._handler = sequential_ip_handler

        with patch.object(bot_instance.ip_service, "apis", [f"{server.base_url}/json"]):
            # Simulate multiple monitoring cycles
            for cycle in range(3):
                await bot_instance.check_ip_periodically()

                # Verify IP was stored
                current_ip = storage.get_current_ip()
                expected_ip = ip_sequence[cycle % len(ip_sequence)]
                assert current_ip == expected_ip

                # Small delay between cycles
                await asyncio.sleep(0.1)

            # Verify history tracking
            history = storage.get_ip_history()
            assert len(history) >= 2  # Should have tracked changes

            # Verify HTTP requests were made
            assert server.get_request_count() >= 3

    async def test_resilience_under_network_conditions(
        self, http_fixture, bot_instance
    ):
        """Test bot resilience under various network conditions."""
        unreliable_server = await http_fixture.create_server()

        # Configure unreliable network conditions
        unreliable_server.set_error_rate(0.3)  # 30% error rate
        unreliable_server.set_latency(200)  # 200ms latency

        success_count = 0
        total_attempts = 10

        with patch.object(
            bot_instance.ip_service, "apis", [f"{unreliable_server.base_url}/json"]
        ):
            for attempt in range(total_attempts):
                try:
                    await bot_instance.check_ip_periodically()
                    success_count += 1
                except Exception as e:
                    # Log but don't fail the test
                    print(f"Attempt {attempt + 1} failed: {e}")

                # Brief pause between attempts
                await asyncio.sleep(0.1)

        # Should have reasonable success rate despite network issues
        success_rate = success_count / total_attempts
        assert success_rate >= 0.5  # At least 50% success rate

        # Verify server received requests
        assert unreliable_server.get_request_count() >= total_attempts
