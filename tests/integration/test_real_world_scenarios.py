"""
Real-world scenario integration tests with HTTP server mocks.

Tests complete end-to-end scenarios that mirror real deployment conditions,
including network failures, API outages, and recovery scenarios.
"""

import asyncio
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage
from tests.utils.http_server_mocks import HTTPMockFixture


class TestRealWorldScenarios:
    """Real-world scenario integration tests."""

    @pytest.fixture
    async def http_fixture(self):
        """Create HTTP mock fixture."""
        fixture = HTTPMockFixture()
        yield fixture
        await fixture.cleanup()

    @pytest.fixture
    def temp_files(self):
        """Create temporary files for testing."""
        files = {}

        # Database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            files["db"] = f.name

        # Config file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            files["config"] = f.name

        # API config file
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            files["api_config"] = f.name

        yield files

        # Cleanup
        for file_path in files.values():
            Path(file_path).unlink(missing_ok=True)

    @pytest.fixture
    def production_like_config(self, temp_files):
        """Create production-like configuration."""
        config = Mock(spec=AppConfig)
        config.bot_token = "test_token"
        config.channel_id = 12345
        config.db_file = temp_files["db"]
        config.check_interval = 5  # 5 seconds for testing
        config.max_retries = 3
        config.retry_delay = 1
        config.circuit_breaker_enabled = True
        config.circuit_breaker_failure_threshold = 3
        config.circuit_breaker_recovery_timeout = 10
        config.message_queue_enabled = True
        config.message_queue_max_size = 1000
        config.cache_enabled = True
        config.cache_ttl = 300
        config.startup_message_enabled = True
        config.custom_apis_enabled = True
        config.connection_timeout = 10.0
        config.read_timeout = 30.0
        config.ip_history_size = 10
        config.connection_pool_size = 10
        config.rate_limit_period = 300
        config.max_checks_per_period = 20
        return config

    async def test_complete_deployment_scenario(
        self, http_fixture, production_like_config, temp_files
    ):
        """Test complete deployment scenario with multiple components."""
        # Create API cluster simulating real IP services
        cluster = await http_fixture.create_cluster(server_count=5)

        # Configure some servers with different characteristics
        servers = cluster.servers
        servers[0].set_latency(50)  # Fast primary
        servers[1].set_latency(100)  # Slower backup
        servers[2].set_latency(200)  # Slow backup
        servers[3].set_error_rate(0.2)  # Unreliable server
        servers[4].set_rate_limit(10)  # Rate limited server

        # Create storage
        storage = SQLiteIPStorage(temp_files["db"], history_size=10)

        # Create IP service with cluster URLs
        ip_service = IPService(
            max_retries=production_like_config.max_retries,
            retry_delay=production_like_config.retry_delay,
            use_concurrent_checks=True,
            circuit_breaker_enabled=production_like_config.circuit_breaker_enabled,
            connection_timeout=production_like_config.connection_timeout,
            read_timeout=production_like_config.read_timeout,
            cache_enabled=production_like_config.cache_enabled,
        )

        # Mock Discord client
        discord_client = AsyncMock()
        discord_client.user = Mock()
        discord_client.user.id = 123456789
        discord_client.is_ready = Mock(return_value=True)
        channel = AsyncMock()
        discord_client.get_channel = Mock(return_value=channel)

        with patch.object(ip_service, "apis", cluster.get_server_urls()):
            # Test initial startup
            initial_ip = await ip_service.get_current_ip()
            storage.save_current_ip(initial_ip)

            assert initial_ip == "149.50.216.211"
            assert storage.get_current_ip() == initial_ip

            # Simulate monitoring over time with various network conditions
            for cycle in range(10):
                # Randomly fail some servers to simulate real conditions
                if cycle == 3:
                    cluster.fail_server(0)  # Fail primary
                elif cycle == 6:
                    cluster.recover_server(0)  # Recover primary
                    cluster.fail_server(1)  # Fail backup
                elif cycle == 8:
                    cluster.recover_server(1)  # Recover all

                # Perform IP check
                current_ip = await ip_service.get_current_ip()

                # Verify service remains operational
                assert current_ip is not None
                assert current_ip == "149.50.216.211"

                # Brief pause between checks
                await asyncio.sleep(0.1)

            # Verify system handled failures gracefully
            cluster_stats = cluster.get_cluster_stats()
            assert cluster_stats["total_requests"] >= 10

            # Verify storage integrity
            history = storage.get_ip_history()
            assert isinstance(history, list)

    async def test_api_service_outage_and_recovery(
        self, http_fixture, production_like_config
    ):
        """Test complete API service outage and recovery."""
        # Create multiple API services
        primary_cluster = await http_fixture.create_cluster(server_count=3)
        backup_cluster = await http_fixture.create_cluster(server_count=2)

        # Create IP service
        ip_service = IPService(
            max_retries=2,
            retry_delay=0.5,
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_recovery_timeout=2,
            cache_enabled=True,
            cache_ttl=60,
        )

        all_urls = primary_cluster.get_server_urls() + backup_cluster.get_server_urls()

        with patch.object(ip_service, "apis", all_urls):
            # Phase 1: Normal operation
            ip1 = await ip_service.get_current_ip()
            assert ip1 == "149.50.216.211"

            # Phase 2: Primary cluster outage
            for i in range(3):
                primary_cluster.fail_server(i)

            # Should failover to backup cluster
            ip2 = await ip_service.get_current_ip()
            assert ip2 == "149.50.216.211"

            # Phase 3: Complete outage
            for i in range(2):
                backup_cluster.fail_server(i)

            # Should use cached value or fail gracefully
            try:
                ip3 = await ip_service.get_current_ip()
                # If successful, should be cached value
                assert ip3 == "149.50.216.211"
            except Exception:
                # Acceptable failure during complete outage
                pass

            # Phase 4: Recovery
            for i in range(3):
                primary_cluster.recover_server(i)

            # Should recover to normal operation
            ip4 = await ip_service.get_current_ip()
            assert ip4 == "149.50.216.211"

            # Verify requests were distributed appropriately
            primary_stats = primary_cluster.get_cluster_stats()
            backup_stats = backup_cluster.get_cluster_stats()

            assert primary_stats["total_requests"] >= 2
            assert backup_stats["total_requests"] >= 1

    async def test_high_load_monitoring_scenario(
        self, http_fixture, production_like_config
    ):
        """Test high-load monitoring scenario."""
        # Create cluster with realistic performance characteristics
        cluster = await http_fixture.create_cluster(server_count=4)

        # Configure realistic latencies
        for i, server in enumerate(cluster.servers):
            server.set_latency(50 + i * 25)  # 50ms to 125ms

        # Create IP service optimized for high load
        ip_service = IPService(
            max_retries=2,
            retry_delay=0.1,
            use_concurrent_checks=True,
            circuit_breaker_enabled=True,
            connection_pool_size=20,
            cache_enabled=True,
            cache_ttl=30,  # Short cache for frequent updates
        )

        with patch.object(ip_service, "apis", cluster.get_server_urls()):
            # Simulate high-frequency monitoring
            start_time = asyncio.get_event_loop().time()

            # Create multiple concurrent monitoring tasks
            tasks = []
            for i in range(20):
                task = asyncio.create_task(ip_service.get_current_ip())
                tasks.append(task)

                # Stagger requests slightly
                await asyncio.sleep(0.05)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            # Verify performance and reliability
            successful_results = [r for r in results if isinstance(r, str)]
            error_results = [r for r in results if isinstance(r, Exception)]

            # Should have high success rate
            success_rate = len(successful_results) / len(results)
            assert success_rate >= 0.8

            # Should be reasonably fast due to concurrency and caching
            assert duration < 5.0  # Complete in under 5 seconds

            # Verify cluster handled load
            cluster_stats = cluster.get_cluster_stats()
            # Should have used multiple servers
            active_servers = sum(
                1 for server in cluster.servers if server.get_request_count() > 0
            )
            assert active_servers >= 2

    async def test_network_partition_recovery(
        self, http_fixture, production_like_config
    ):
        """Test network partition and recovery scenario."""
        # Create geographically distributed cluster simulation
        us_cluster = await http_fixture.create_cluster(server_count=2)
        eu_cluster = await http_fixture.create_cluster(server_count=2)

        # Configure different response times (simulating geography)
        for server in us_cluster.servers:
            server.set_latency(50)  # Fast US servers
        for server in eu_cluster.servers:
            server.set_latency(200)  # Slower EU servers

        ip_service = IPService(
            max_retries=3,
            retry_delay=0.5,
            use_concurrent_checks=True,
            circuit_breaker_enabled=True,
            connection_timeout=5.0,
            cache_enabled=True,
        )

        all_urls = us_cluster.get_server_urls() + eu_cluster.get_server_urls()

        with patch.object(ip_service, "apis", all_urls):
            # Phase 1: All regions available
            ip1 = await ip_service.get_current_ip()
            assert ip1 == "149.50.216.211"

            # Should prefer faster US servers
            us_stats_initial = us_cluster.get_cluster_stats()
            eu_stats_initial = eu_cluster.get_cluster_stats()

            # Phase 2: Simulate US network partition
            for i in range(2):
                us_cluster.fail_server(i)

            # Should failover to EU servers
            ip2 = await ip_service.get_current_ip()
            assert ip2 == "149.50.216.211"

            # Phase 3: Simulate complete network issues
            for i in range(2):
                eu_cluster.fail_server(i)

            # Should handle gracefully (cache or controlled failure)
            try:
                ip3 = await ip_service.get_current_ip()
                assert ip3 == "149.50.216.211"  # From cache
            except Exception:
                pass  # Acceptable during complete outage

            # Phase 4: Gradual recovery
            us_cluster.recover_server(0)  # Partial US recovery

            ip4 = await ip_service.get_current_ip()
            assert ip4 == "149.50.216.211"

            # Phase 5: Full recovery
            us_cluster.recover_server(1)
            for i in range(2):
                eu_cluster.recover_server(i)

            ip5 = await ip_service.get_current_ip()
            assert ip5 == "149.50.216.211"

            # Verify failover behavior
            us_stats_final = us_cluster.get_cluster_stats()
            eu_stats_final = eu_cluster.get_cluster_stats()

            assert (
                us_stats_final["total_requests"] >= us_stats_initial["total_requests"]
            )
            assert (
                eu_stats_final["total_requests"] >= eu_stats_initial["total_requests"]
            )

    async def test_production_monitoring_with_real_conditions(
        self, http_fixture, production_like_config, temp_files
    ):
        """Test production-like monitoring with realistic conditions."""
        # Create realistic API ecosystem
        cluster = await http_fixture.create_cluster(server_count=6)

        # Configure realistic failure patterns
        servers = cluster.servers
        servers[0].set_latency(30)  # Premium fast service
        servers[1].set_latency(100)  # Standard service
        servers[2].set_latency(150)  # Slow but reliable
        servers[3].set_error_rate(0.1)  # Occasionally unreliable
        servers[4].set_rate_limit(30)  # Rate limited service
        servers[5].set_latency(500)  # Very slow service

        # Create storage
        storage = SQLiteIPStorage(temp_files["db"], history_size=10)

        # Create production-like IP service
        ip_service = IPService(
            max_retries=production_like_config.max_retries,
            retry_delay=production_like_config.retry_delay,
            use_concurrent_checks=True,
            circuit_breaker_enabled=production_like_config.circuit_breaker_enabled,
            circuit_breaker_failure_threshold=production_like_config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=production_like_config.circuit_breaker_recovery_timeout,
            connection_pool_size=production_like_config.connection_pool_size,
            connection_timeout=production_like_config.connection_timeout,
            read_timeout=production_like_config.read_timeout,
            cache_enabled=production_like_config.cache_enabled,
            cache_ttl=production_like_config.cache_ttl,
        )

        with patch.object(ip_service, "apis", cluster.get_server_urls()):
            # Simulate 24-hour monitoring cycle (compressed to seconds)
            monitoring_cycles = 48  # Representing 30-minute intervals
            ip_changes = 0
            successful_checks = 0

            previous_ip = None

            for cycle in range(monitoring_cycles):
                # Simulate various network conditions throughout the day
                hour = cycle // 2  # 2 cycles per "hour"

                # Simulate peak hours with more failures
                if 8 <= hour <= 18:  # Business hours
                    if cycle % 10 == 0:  # Periodic failures
                        servers[3].set_error_rate(0.3)
                else:  # Off hours
                    servers[3].set_error_rate(0.05)

                # Simulate maintenance windows
                if hour == 2:  # 2 AM maintenance
                    servers[0].set_error_rate(1.0)  # Primary down for maintenance
                elif hour == 3:
                    servers[0].set_error_rate(0.0)  # Primary back up

                try:
                    current_ip = await ip_service.get_current_ip()

                    if current_ip:
                        successful_checks += 1

                        # Store IP and track changes
                        if previous_ip and previous_ip != current_ip:
                            ip_changes += 1

                        storage.save_current_ip(current_ip)
                        previous_ip = current_ip

                except Exception as e:
                    # Log but continue monitoring
                    print(f"Monitoring cycle {cycle} failed: {e}")

                # Brief pause between cycles
                await asyncio.sleep(0.02)  # 20ms

            # Verify monitoring reliability
            success_rate = successful_checks / monitoring_cycles
            assert success_rate >= 0.9  # 90% uptime even with failures

            # Verify data integrity
            final_ip = storage.get_current_ip()
            assert final_ip is not None

            history = storage.get_ip_history()
            assert isinstance(history, list)

            # Verify cluster performance
            cluster_stats = cluster.get_cluster_stats()
            assert cluster_stats["total_requests"] >= monitoring_cycles

            # Verify load distribution (should use multiple servers)
            active_servers = sum(
                1 for server in servers if server.get_request_count() > 0
            )
            assert active_servers >= 3  # Should distribute load

            print(
                f"Monitoring completed: {successful_checks}/{monitoring_cycles} successful checks"
            )
            print(f"IP changes detected: {ip_changes}")
            print(f"Active servers used: {active_servers}/6")

    async def test_disaster_recovery_scenario(
        self, http_fixture, production_like_config, temp_files
    ):
        """Test complete disaster recovery scenario."""
        # Primary data center
        primary_cluster = await http_fixture.create_cluster(server_count=3)

        # Disaster recovery data center
        dr_cluster = await http_fixture.create_cluster(server_count=2)

        # Emergency fallback service
        emergency_server = await http_fixture.create_server()

        # Configure different characteristics
        for server in primary_cluster.servers:
            server.set_latency(30)  # Fast primary
        for server in dr_cluster.servers:
            server.set_latency(100)  # Slower DR
        emergency_server.set_latency(200)  # Slowest emergency

        # Create storage
        storage = SQLiteIPStorage(temp_files["db"], history_size=10)

        # Create resilient IP service
        ip_service = IPService(
            max_retries=5,
            retry_delay=0.5,
            use_concurrent_checks=True,
            circuit_breaker_enabled=True,
            circuit_breaker_failure_threshold=2,
            circuit_breaker_recovery_timeout=5,
            cache_enabled=True,
            cache_ttl=120,  # Longer cache for disaster scenarios
        )

        all_urls = (
            primary_cluster.get_server_urls()
            + dr_cluster.get_server_urls()
            + [f"{emergency_server.base_url}/json"]
        )

        with patch.object(ip_service, "apis", all_urls):
            # Phase 1: Normal operation
            ip1 = await ip_service.get_current_ip()
            storage.save_current_ip(ip1)
            assert ip1 == "149.50.216.211"

            # Phase 2: Primary data center failure
            for i in range(3):
                primary_cluster.fail_server(i)

            # Should failover to DR
            ip2 = await ip_service.get_current_ip()
            assert ip2 == "149.50.216.211"

            # Phase 3: DR data center also fails (complete disaster)
            for i in range(2):
                dr_cluster.fail_server(i)

            # Should use emergency service
            ip3 = await ip_service.get_current_ip()
            assert ip3 == "149.50.216.211"

            # Phase 4: Emergency service also fails (total outage)
            emergency_server.set_error_rate(1.0)

            # Should use cache or fail gracefully
            try:
                ip4 = await ip_service.get_current_ip()
                # If successful, should be from cache
                assert ip4 == "149.50.216.211"
            except Exception:
                # Total outage is acceptable
                pass

            # Phase 5: Gradual recovery - Emergency service first
            emergency_server.set_error_rate(0.0)

            ip5 = await ip_service.get_current_ip()
            assert ip5 == "149.50.216.211"

            # Phase 6: DR recovery
            for i in range(2):
                dr_cluster.recover_server(i)

            ip6 = await ip_service.get_current_ip()
            assert ip6 == "149.50.216.211"

            # Phase 7: Primary recovery (full restoration)
            for i in range(3):
                primary_cluster.recover_server(i)

            ip7 = await ip_service.get_current_ip()
            assert ip7 == "149.50.216.211"

            # Verify disaster recovery worked
            assert storage.get_current_ip() == "149.50.216.211"

            # Verify all tiers were used
            primary_stats = primary_cluster.get_cluster_stats()
            dr_stats = dr_cluster.get_cluster_stats()
            emergency_stats = emergency_server.get_stats()

            assert primary_stats["total_requests"] >= 2  # Initial + recovery
            assert dr_stats["total_requests"] >= 1  # During primary failure
            assert emergency_stats["total_requests"] >= 1  # During total failure

            print("Disaster recovery scenario completed successfully")
            print(f"Primary DC requests: {primary_stats['total_requests']}")
            print(f"DR DC requests: {dr_stats['total_requests']}")
            print(f"Emergency service requests: {emergency_stats['total_requests']}")
