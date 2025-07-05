"""
Integration tests for IP service with real HTTP server mocks.

These tests use actual HTTP servers to test the IP service's HTTP client behavior,
including error handling, retries, timeouts, and API failover scenarios.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from ip_monitor.ip_service import IPService
from ip_monitor.ip_api_config import IPAPIManager, IPAPIEndpoint, ResponseFormat
from tests.utils.http_server_mocks import MockIPAPIServer, MockAPICluster, HTTPMockFixture


class TestIPServiceHTTPIntegration:
    """Integration tests for IP service HTTP operations."""
    
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
        config.max_retries = 3
        config.retry_delay = 0.1  # Fast retries for testing
        config.connection_timeout = 5.0
        config.read_timeout = 10.0
        config.circuit_breaker_enabled = False  # Disable for focused HTTP testing
        config.cache_enabled = False  # Disable for focused HTTP testing
        return config
    
    @pytest.fixture
    def ip_service(self, mock_config):
        """Create IP service instance."""
        return IPService(
            max_retries=mock_config.max_retries,
            retry_delay=mock_config.retry_delay,
            use_concurrent_checks=False,  # Sequential for predictable testing
            circuit_breaker_enabled=mock_config.circuit_breaker_enabled,
            connection_timeout=mock_config.connection_timeout,
            read_timeout=mock_config.read_timeout,
            cache_enabled=mock_config.cache_enabled,
        )
    
    async def test_successful_json_api_call(self, http_fixture, ip_service):
        """Test successful JSON API call."""
        server = await http_fixture.create_server()
        
        # Configure IP service to use our mock server
        with patch.object(ip_service, 'apis', [f"{server.base_url}/json"]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert server.get_request_count() == 1
        
        # Verify request details
        history = server.get_request_history()
        assert len(history) == 1
        assert history[0]["path"] == "/json"
        assert history[0]["method"] == "GET"
    
    async def test_successful_text_api_call(self, http_fixture, ip_service):
        """Test successful plain text API call."""
        server = await http_fixture.create_server()
        
        # Configure IP service to use our mock server
        with patch.object(ip_service, 'apis', [f"{server.base_url}/text"]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert server.get_request_count() == 1
    
    async def test_custom_json_field_parsing(self, http_fixture, ip_service):
        """Test parsing IP from custom JSON field."""
        server = await http_fixture.create_server()
        
        # Mock IP API config to handle custom field
        mock_api_config = Mock()
        mock_api_config.get_all_apis.return_value = [
            IPAPIEndpoint(
                id="custom",
                name="Custom API",
                url=f"{server.base_url}/custom",
                response_format=ResponseFormat.JSON,
                json_field="origin",
                enabled=True,
                priority=1,
            )
        ]
        
        with patch('ip_monitor.ip_service.ip_api_manager', mock_api_config):
            with patch.object(ip_service, 'use_custom_apis', True):
                ip_address = await ip_service.get_current_ip()
                
        assert ip_address == "203.0.113.1"
        assert server.get_request_count() == 1
    
    async def test_api_failover_on_error(self, http_fixture, ip_service):
        """Test API failover when first server returns error."""
        error_server = await http_fixture.create_server()
        success_server = await http_fixture.create_server()
        
        # Configure first server to always error
        error_server.set_error_rate(1.0)
        
        # Configure IP service to use both servers
        with patch.object(ip_service, 'apis', [
            f"{error_server.base_url}/json",
            f"{success_server.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert error_server.get_request_count() == 1
        assert success_server.get_request_count() == 1
    
    async def test_retry_logic_on_temporary_failure(self, http_fixture, ip_service):
        """Test retry logic with temporary failures."""
        server = await http_fixture.create_server()
        
        # Configure server to fail first 2 requests, then succeed
        server.set_error_rate(0.7)  # 70% error rate
        
        # Mock the requests to fail first 2, succeed on 3rd
        original_handler = server._json_handler
        call_count = 0
        
        async def failing_handler(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                server._track_request(request)
                return server.app.router._resources[0]._handler(request)
            else:
                # Disable errors for success
                server.set_error_rate(0.0)
                return await original_handler(request)
        
        server.app.router._resources[0]._handler = failing_handler
        
        with patch.object(ip_service, 'apis', [f"{server.base_url}/json"]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert server.get_request_count() >= 2  # Should have retried
    
    async def test_timeout_handling(self, http_fixture, ip_service):
        """Test timeout handling with slow server."""
        slow_server = await http_fixture.create_server()
        fast_server = await http_fixture.create_server()
        
        # Configure IP service with short timeout
        ip_service.connection_timeout = 0.5
        ip_service.read_timeout = 0.5
        
        with patch.object(ip_service, 'apis', [
            f"{slow_server.base_url}/slow",  # 2 second delay
            f"{fast_server.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        # Should have failed over to fast server
        assert fast_server.get_request_count() == 1
    
    async def test_malformed_json_handling(self, http_fixture, ip_service):
        """Test handling of malformed JSON responses."""
        malformed_server = await http_fixture.create_server()
        good_server = await http_fixture.create_server()
        
        with patch.object(ip_service, 'apis', [
            f"{malformed_server.base_url}/malformed",
            f"{good_server.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert malformed_server.get_request_count() == 1
        assert good_server.get_request_count() == 1
    
    async def test_empty_response_handling(self, http_fixture, ip_service):
        """Test handling of empty responses."""
        empty_server = await http_fixture.create_server()
        good_server = await http_fixture.create_server()
        
        with patch.object(ip_service, 'apis', [
            f"{empty_server.base_url}/empty",
            f"{good_server.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert empty_server.get_request_count() == 1
        assert good_server.get_request_count() == 1
    
    async def test_invalid_ip_address_handling(self, http_fixture, ip_service):
        """Test handling of invalid IP addresses."""
        invalid_server = await http_fixture.create_server()
        valid_server = await http_fixture.create_server()
        
        with patch.object(ip_service, 'apis', [
            f"{invalid_server.base_url}/invalid_ip",
            f"{valid_server.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        assert ip_address == "203.0.113.1"
        assert invalid_server.get_request_count() == 1
        assert valid_server.get_request_count() == 1
    
    async def test_rate_limiting_handling(self, http_fixture, ip_service):
        """Test handling of rate-limited responses."""
        rate_limited_server = await http_fixture.create_server()
        backup_server = await http_fixture.create_server()
        
        # Configure server to rate limit after 1 request
        rate_limited_server.set_rate_limit(1)
        
        with patch.object(ip_service, 'apis', [
            f"{rate_limited_server.base_url}/rate_limit",
            f"{backup_server.base_url}/json"
        ]):
            # First request should succeed
            ip_address1 = await ip_service.get_current_ip()
            assert ip_address1 == "203.0.113.1"
            
            # Second request should be rate limited, fail over to backup
            ip_address2 = await ip_service.get_current_ip()
            assert ip_address2 == "203.0.113.1"
            
        assert rate_limited_server.get_request_count() >= 1
        assert backup_server.get_request_count() >= 1
    
    async def test_concurrent_api_checks(self, http_fixture):
        """Test concurrent API checking."""
        server1 = await http_fixture.create_server()
        server2 = await http_fixture.create_server()
        server3 = await http_fixture.create_server()
        
        # Create IP service with concurrent checks enabled
        ip_service = IPService(
            use_concurrent_checks=True,
            max_retries=1,
            retry_delay=0.1,
            circuit_breaker_enabled=False,
            cache_enabled=False,
        )
        
        # Add latency to servers to test concurrency
        server1.set_latency(100)  # 100ms
        server2.set_latency(200)  # 200ms
        server3.set_latency(50)   # 50ms (fastest)
        
        start_time = asyncio.get_event_loop().time()
        
        with patch.object(ip_service, 'apis', [
            f"{server1.base_url}/json",
            f"{server2.base_url}/json",
            f"{server3.base_url}/json"
        ]):
            ip_address = await ip_service.get_current_ip()
            
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        assert ip_address == "203.0.113.1"
        # Should be faster than sequential (< 350ms total)
        assert duration < 0.35
        
        # All servers should have been called
        assert server1.get_request_count() == 1
        assert server2.get_request_count() == 1
        assert server3.get_request_count() == 1
    
    async def test_custom_api_management_integration(self, http_fixture, ip_service):
        """Test integration with custom API management."""
        server = await http_fixture.create_server()
        
        # Create API config
        api_config = IPAPIManager()
        api_config.add_api(
            name="Test API",
            url=f"{server.base_url}/json",
            response_format=ResponseFormat.JSON,
            json_field="ip"
        )
        
        with patch('ip_monitor.ip_service.ip_api_manager', api_config):
            with patch.object(ip_service, 'use_custom_apis', True):
                ip_address = await ip_service.get_current_ip()
                
        assert ip_address == "203.0.113.1"
        assert server.get_request_count() == 1
        
        # Test API performance tracking
        stats = api_config.get_performance_stats()
        assert len(stats) == 1
        assert stats[0]["success_count"] > 0
    
    async def test_circuit_breaker_integration(self, http_fixture):
        """Test circuit breaker integration with HTTP failures."""
        failing_server = await http_fixture.create_server()
        backup_server = await http_fixture.create_server()
        
        # Configure server to always fail
        failing_server.set_error_rate(1.0)
        
        # Create IP service with circuit breaker enabled
        ip_service = IPService(
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_recovery_timeout=0.1,
            max_retries=1,
            retry_delay=0.1,
            cache_enabled=False,
        )
        
        with patch.object(ip_service, 'apis', [
            f"{failing_server.base_url}/json",
            f"{backup_server.base_url}/json"
        ]):
            # First few requests should trigger circuit breaker
            for _ in range(3):
                ip_address = await ip_service.get_current_ip()
                assert ip_address == "203.0.113.1"
                
            # Circuit breaker should prevent further calls to failing server
            initial_failing_count = failing_server.get_request_count()
            
            # Additional requests should use backup server only
            for _ in range(2):
                ip_address = await ip_service.get_current_ip()
                assert ip_address == "203.0.113.1"
                
            # Failing server should not receive more requests
            assert failing_server.get_request_count() == initial_failing_count
    
    async def test_cluster_failover_scenario(self, http_fixture, ip_service):
        """Test complete cluster failover scenario."""
        cluster = await http_fixture.create_cluster(server_count=3)
        
        # Configure IP service to use cluster
        urls = cluster.get_server_urls()
        with patch.object(ip_service, 'apis', urls):
            # Initial request should succeed
            ip_address = await ip_service.get_current_ip()
            assert ip_address == "203.0.113.1"
            
            # Fail primary server
            cluster.fail_server(0)
            
            # Should fail over to secondary servers
            ip_address = await ip_service.get_current_ip()
            assert ip_address == "203.0.113.1"
            
            # Fail second server
            cluster.fail_server(1)
            
            # Should still work with third server
            ip_address = await ip_service.get_current_ip()
            assert ip_address == "203.0.113.1"
            
        # Verify requests were distributed
        stats = cluster.get_cluster_stats()
        assert stats["total_requests"] >= 3
    
    async def test_performance_monitoring(self, http_fixture, ip_service):
        """Test performance monitoring during HTTP operations."""
        fast_server = await http_fixture.create_server()
        slow_server = await http_fixture.create_server()
        
        fast_server.set_latency(10)   # 10ms
        slow_server.set_latency(500)  # 500ms
        
        # Create API config with performance tracking
        api_config = IPAPIManager()
        api_config.add_api("Fast API", f"{fast_server.base_url}/json")
        api_config.add_api("Slow API", f"{slow_server.base_url}/json")
        
        with patch('ip_monitor.ip_service.ip_api_manager', api_config):
            with patch.object(ip_service, 'use_custom_apis', True):
                # Make multiple requests to gather performance data
                for _ in range(5):
                    await ip_service.get_current_ip()
                    
        # Check performance statistics
        stats = api_config.get_performance_stats()
        assert len(stats) == 2
        
        # Fast server should have better performance
        fast_stats = next(s for s in stats if "Fast" in s["name"])
        slow_stats = next(s for s in stats if "Slow" in s["name"])
        
        assert fast_stats["avg_response_time"] < slow_stats["avg_response_time"]
    
    async def test_http_connection_pooling(self, http_fixture, ip_service):
        """Test HTTP connection pooling behavior."""
        server = await http_fixture.create_server()
        
        # Configure IP service for connection pooling
        ip_service.connection_pool_size = 5
        ip_service.connection_pool_max_keepalive = 3
        
        with patch.object(ip_service, 'apis', [f"{server.base_url}/json"]):
            # Make multiple requests to test connection reuse
            for _ in range(10):
                ip_address = await ip_service.get_current_ip()
                assert ip_address == "203.0.113.1"
                
        assert server.get_request_count() == 10
        
        # Verify connection headers were set correctly
        history = server.get_request_history()
        for request in history:
            assert "User-Agent" in request["headers"]
    
    async def test_error_recovery_workflow(self, http_fixture, ip_service):
        """Test complete error recovery workflow."""
        unreliable_server = await http_fixture.create_server()
        reliable_server = await http_fixture.create_server()
        
        # Configure unreliable server with intermittent failures
        unreliable_server.set_error_rate(0.5)  # 50% error rate
        
        success_count = 0
        total_attempts = 10
        
        with patch.object(ip_service, 'apis', [
            f"{unreliable_server.base_url}/json",
            f"{reliable_server.base_url}/json"
        ]):
            for _ in range(total_attempts):
                try:
                    ip_address = await ip_service.get_current_ip()
                    if ip_address == "203.0.113.1":
                        success_count += 1
                except Exception:
                    pass  # Expected failures
                    
        # Should have high success rate due to failover
        success_rate = success_count / total_attempts
        assert success_rate >= 0.8  # At least 80% success rate
        
        # Both servers should have received requests
        assert unreliable_server.get_request_count() > 0
        assert reliable_server.get_request_count() > 0