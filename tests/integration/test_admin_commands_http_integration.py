"""
Integration tests for admin commands with HTTP server mocks.

Tests admin command functionality with real HTTP servers to verify
API management, testing, and performance monitoring capabilities.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.commands.admin_commands.admin_command_router import AdminCommandRouter
from ip_monitor.ip_api_config import IPAPIManager, ResponseFormat
from tests.utils.http_server_mocks import HTTPMockFixture


class TestAdminCommandsHTTPIntegration:
    """Integration tests for admin commands with HTTP operations."""

    @pytest.fixture
    async def http_fixture(self):
        """Create HTTP mock fixture."""
        fixture = HTTPMockFixture()
        yield fixture
        await fixture.cleanup()

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        config = Mock()
        config.check_interval = 300
        config.max_retries = 3
        config.retry_delay = 30
        config.custom_apis_enabled = True
        config.cache_enabled = True
        config.cache_ttl = 300
        config.circuit_breaker_enabled = True
        return config

    @pytest.fixture
    def mock_client(self):
        """Create mock Discord client."""
        client = Mock()
        client.user = Mock()
        client.user.id = 123456789
        client.user.name = "TestBot"
        return client

    @pytest.fixture
    def mock_ip_service(self):
        """Create mock IP service."""
        service = Mock()
        service.get_current_ip = AsyncMock(return_value="203.0.113.1")
        service.get_cache_info = Mock(
            return_value={
                "enabled": True,
                "cache_ttl": 300,
                "stats": {"hits": 10, "misses": 5},
            }
        )
        service.invalidate_cache = Mock(return_value=5)
        return service

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = Mock()
        storage.get_current_ip = Mock(return_value="203.0.113.1")
        storage.get_ip_history = Mock(return_value=[])
        return storage

    @pytest.fixture
    def mock_admin_message(self):
        """Create mock admin message."""
        message = Mock()
        message.author = Mock()
        message.author.id = 987654321
        message.author.name = "AdminUser"
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = True
        message.channel = Mock()
        message.channel.send = AsyncMock()
        return message

    @pytest.fixture
    def admin_router(self, mock_client, mock_ip_service, mock_storage, mock_config):
        """Create admin command router."""
        return AdminCommandRouter(
            client=mock_client,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
        )

    async def test_api_add_command_with_http_server(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test adding API with HTTP server verification."""
        server = await http_fixture.create_server()

        # Mock API config
        api_config = IPAPIManager()

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test adding API
            mock_admin_message.content = (
                f"!admin api add TestAPI {server.base_url}/json json ip"
            )

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify API was added
            apis = api_config.list_apis()
            assert len(apis) == 1
            assert apis[0].name == "TestAPI"
            assert apis[0].url == f"{server.base_url}/json"

            # Verify response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "successfully added" in response.lower()

    async def test_api_test_command_with_http_server(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API testing command with HTTP server."""
        server = await http_fixture.create_server()

        # Create API config with test endpoint
        api_config = IPAPIManager()
        api_config.add_api(
            "TestAPI", f"{server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test API testing command
            mock_admin_message.content = "!admin api test TestAPI"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify HTTP request was made
            assert server.get_request_count() == 1

            # Verify response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "203.0.113.1" in response
            assert "successful" in response.lower()

    async def test_api_test_command_with_failing_server(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API testing command with failing server."""
        server = await http_fixture.create_server()

        # Configure server to fail
        server.set_error_rate(1.0)

        # Create API config with failing endpoint
        api_config = IPAPIManager()
        api_config.add_api(
            "FailingAPI", f"{server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test API testing command
            mock_admin_message.content = "!admin api test FailingAPI"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify HTTP request was made
            assert server.get_request_count() == 1

            # Verify error response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "failed" in response.lower()

    async def test_api_stats_command_with_http_performance(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API stats command with HTTP performance data."""
        fast_server = await http_fixture.create_server()
        slow_server = await http_fixture.create_server()

        # Configure different latencies
        fast_server.set_latency(10)  # 10ms
        slow_server.set_latency(500)  # 500ms

        # Create API config with test endpoints
        api_config = IPAPIManager()
        api_config.add_api(
            "FastAPI", f"{fast_server.base_url}/json", ResponseFormat.JSON, "ip"
        )
        api_config.add_api(
            "SlowAPI", f"{slow_server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test both APIs to generate performance data
            await api_config.test_api("FastAPI")
            await api_config.test_api("SlowAPI")

            # Test API stats command
            mock_admin_message.content = "!admin api stats"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify HTTP requests were made
            assert fast_server.get_request_count() == 1
            assert slow_server.get_request_count() == 1

            # Verify stats response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "FastAPI" in response
            assert "SlowAPI" in response
            assert "performance" in response.lower()

    async def test_api_list_command_with_performance_data(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API list command with performance data."""
        server = await http_fixture.create_server()

        # Create API config with test endpoint
        api_config = IPAPIManager()
        api_config.add_api(
            "TestAPI", f"{server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Generate some performance data
            await api_config.test_api("TestAPI")

            # Test API list command
            mock_admin_message.content = "!admin api list"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "TestAPI" in response
            assert server.base_url in response

    async def test_cache_integration_with_http_apis(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test cache integration with HTTP APIs."""
        server = await http_fixture.create_server()

        # Mock cache system
        mock_cache = Mock()
        mock_cache.get_status = Mock(
            return_value={
                "memory_entries": 5,
                "hit_rate": 0.8,
                "operations": {"hits": 8, "misses": 2, "sets": 3},
            }
        )
        mock_cache.clear = Mock(return_value=5)

        with patch.object(admin_router.cache_handler, "cache", mock_cache):
            # Test cache show command
            mock_admin_message.content = "!admin cache show"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify cache status was retrieved
            mock_cache.get_status.assert_called_once()

            # Verify response was sent
            mock_admin_message.channel.send.assert_called_once()
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "cache" in response.lower()
            assert "hit rate" in response.lower()

    async def test_config_runtime_updates_affecting_http_behavior(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test config updates affecting HTTP behavior."""
        server = await http_fixture.create_server()

        # Test updating HTTP-related configuration
        mock_admin_message.content = "!admin config set connection_timeout 20.0"

        await admin_router.handle_admin_command(mock_admin_message)

        # Verify config was updated
        assert admin_router.config.connection_timeout == 20.0

        # Verify response was sent
        mock_admin_message.channel.send.assert_called_once()
        response = mock_admin_message.channel.send.call_args[0][0]
        assert "updated" in response.lower()
        assert "connection_timeout" in response

    async def test_api_cluster_management(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test managing a cluster of APIs."""
        cluster = await http_fixture.create_cluster(server_count=3)

        # Create API config
        api_config = IPAPIManager()

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Add all cluster servers as APIs
            server_urls = cluster.get_server_urls()
            for i, url in enumerate(server_urls):
                mock_admin_message.content = (
                    f"!admin api add ClusterAPI{i} {url} json ip"
                )
                mock_admin_message.channel.send.reset_mock()

                await admin_router.handle_admin_command(mock_admin_message)

                # Verify API was added
                apis = api_config.list_apis()
                assert len(apis) == i + 1

            # Test all APIs
            for i in range(3):
                mock_admin_message.content = f"!admin api test ClusterAPI{i}"
                mock_admin_message.channel.send.reset_mock()

                await admin_router.handle_admin_command(mock_admin_message)

                # Verify test was performed
                mock_admin_message.channel.send.assert_called_once()

        # Verify cluster received requests
        stats = cluster.get_cluster_stats()
        assert stats["total_requests"] >= 3

    async def test_api_failover_management(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API failover management."""
        primary_server = await http_fixture.create_server()
        backup_server = await http_fixture.create_server()

        # Configure primary server to fail
        primary_server.set_error_rate(1.0)

        # Create API config with primary and backup
        api_config = IPAPIManager()
        api_config.add_api(
            "PrimaryAPI", f"{primary_server.base_url}/json", ResponseFormat.JSON, "ip"
        )
        api_config.add_api(
            "BackupAPI", f"{backup_server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test primary API (should fail)
            mock_admin_message.content = "!admin api test PrimaryAPI"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify primary was tested and failed
            assert primary_server.get_request_count() == 1

            # Test backup API (should succeed)
            mock_admin_message.content = "!admin api test BackupAPI"
            mock_admin_message.channel.send.reset_mock()

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify backup was tested and succeeded
            assert backup_server.get_request_count() == 1

            # Verify success response
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "successful" in response.lower()

    async def test_api_performance_monitoring_over_time(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API performance monitoring over time."""
        server = await http_fixture.create_server()

        # Configure variable latency
        server.set_latency(100)

        # Create API config
        api_config = IPAPIManager()
        api_config.add_api(
            "MonitoredAPI", f"{server.base_url}/json", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Perform multiple tests to build performance history
            for i in range(5):
                mock_admin_message.content = "!admin api test MonitoredAPI"
                mock_admin_message.channel.send.reset_mock()

                await admin_router.handle_admin_command(mock_admin_message)

                # Vary latency
                server.set_latency(50 + i * 25)

                # Brief pause between tests
                await asyncio.sleep(0.1)

            # Check performance stats
            mock_admin_message.content = "!admin api stats"
            mock_admin_message.channel.send.reset_mock()

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify performance data was collected
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "MonitoredAPI" in response
            assert "response time" in response.lower()

        # Verify server received all requests
        assert server.get_request_count() == 5

    async def test_rate_limiting_detection_and_management(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test rate limiting detection and management."""
        server = await http_fixture.create_server()

        # Configure aggressive rate limiting
        server.set_rate_limit(2)  # Only 2 requests per minute

        # Create API config
        api_config = IPAPIManager()
        api_config.add_api(
            "RateLimitedAPI", f"{server.base_url}/rate_limit", ResponseFormat.JSON, "ip"
        )

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test API multiple times to trigger rate limiting
            for i in range(4):
                mock_admin_message.content = "!admin api test RateLimitedAPI"
                mock_admin_message.channel.send.reset_mock()

                await admin_router.handle_admin_command(mock_admin_message)

                # Check response for rate limiting indicators
                response = mock_admin_message.channel.send.call_args[0][0]

                if i >= 2:  # Should be rate limited
                    assert (
                        "rate limit" in response.lower() or "failed" in response.lower()
                    )

        # Verify server received requests
        assert server.get_request_count() >= 2

    async def test_api_security_and_error_handling(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test API security and error handling."""
        server = await http_fixture.create_server()

        # Create API config
        api_config = IPAPIManager()

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Test adding API with invalid URL
            mock_admin_message.content = "!admin api add InvalidAPI invalid-url json ip"

            await admin_router.handle_admin_command(mock_admin_message)

            # Verify error handling
            response = mock_admin_message.channel.send.call_args[0][0]
            assert "error" in response.lower() or "invalid" in response.lower()

            # Test adding API with malicious URL patterns
            malicious_urls = [
                "http://localhost:22/ssh",  # SSH port
                "file:///etc/passwd",  # File protocol
                "ftp://evil.com/",  # FTP protocol
            ]

            for url in malicious_urls:
                mock_admin_message.content = (
                    f"!admin api add MaliciousAPI {url} json ip"
                )
                mock_admin_message.channel.send.reset_mock()

                await admin_router.handle_admin_command(mock_admin_message)

                # Should reject malicious URLs
                apis = api_config.list_apis()
                assert not any(api.url == url for api in apis)

    async def test_comprehensive_admin_workflow(
        self, http_fixture, admin_router, mock_admin_message
    ):
        """Test comprehensive admin workflow with HTTP integration."""
        # Create multiple servers for comprehensive testing
        api_server = await http_fixture.create_server()
        backup_server = await http_fixture.create_server()

        # Configure different behaviors
        api_server.set_latency(50)
        backup_server.set_latency(100)

        # Create API config
        api_config = IPAPIManager()

        with patch.object(admin_router.api_handler, "ip_api_config", api_config):
            # Step 1: Add APIs
            mock_admin_message.content = (
                f"!admin api add MainAPI {api_server.base_url}/json json ip"
            )
            await admin_router.handle_admin_command(mock_admin_message)

            mock_admin_message.content = (
                f"!admin api add BackupAPI {backup_server.base_url}/json json ip"
            )
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            # Step 2: Test APIs
            mock_admin_message.content = "!admin api test MainAPI"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            mock_admin_message.content = "!admin api test BackupAPI"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            # Step 3: Check performance stats
            mock_admin_message.content = "!admin api stats"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            stats_response = mock_admin_message.channel.send.call_args[0][0]
            assert "MainAPI" in stats_response
            assert "BackupAPI" in stats_response

            # Step 4: List all APIs
            mock_admin_message.content = "!admin api list"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            list_response = mock_admin_message.channel.send.call_args[0][0]
            assert "MainAPI" in list_response
            assert "BackupAPI" in list_response

            # Step 5: Update configuration
            mock_admin_message.content = "!admin config set connection_timeout 15.0"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

            # Step 6: Check cache status
            mock_admin_message.content = "!admin cache show"
            mock_admin_message.channel.send.reset_mock()
            await admin_router.handle_admin_command(mock_admin_message)

        # Verify all servers received requests
        assert api_server.get_request_count() >= 1
        assert backup_server.get_request_count() >= 1

        # Verify APIs were properly configured
        apis = api_config.list_apis()
        assert len(apis) == 2
        assert any(api.name == "MainAPI" for api in apis)
        assert any(api.name == "BackupAPI" for api in apis)
