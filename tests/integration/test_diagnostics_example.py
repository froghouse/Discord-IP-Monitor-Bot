"""
Example integration test showing how to use the enhanced error diagnostics.

This demonstrates practical usage of the diagnostic utilities with
existing test patterns.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.cache import CacheType
from tests.utils.diagnostic_helpers import (
    DiagnosticContext,
    assert_with_context,
    collect_test_metrics,
    log_test_checkpoint,
    log_test_start,
    monitor_async_operations,
    track_concurrent_operations,
    track_service_state,
    with_diagnostics,
)


class TestDiagnosticsIntegration:
    """Example tests showing diagnostic integration patterns."""

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_ip_check_with_full_diagnostics(
        self, isolated_test_config, isolated_cache
    ):
        """Example test with comprehensive diagnostics."""
        log_test_start("test_ip_check_with_full_diagnostics")

        # Create services with mocked dependencies
        mock_storage = AsyncMock(spec=SQLiteIPStorage)
        mock_storage.get_current_ip.return_value = "192.168.1.1"
        mock_storage.save_current_ip.return_value = None

        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        log_test_checkpoint("Services initialized")

        # Test IP retrieval with diagnostic context
        async with DiagnosticContext("ip_retrieval_test") as ctx:
            # Mock the HTTP response
            with patch("aiohttp.ClientSession.get") as mock_get:
                mock_response = AsyncMock()
                mock_response.text.return_value = "203.0.113.1"
                mock_response.status = 200
                mock_get.return_value.__aenter__.return_value = mock_response

                ctx.record_checkpoint("HTTP mock configured")

                # Perform IP check
                result = await ip_service.get_current_ip()

                ctx.record_checkpoint("IP check completed", {"result": result})

                # Enhanced assertion with context
                assert_with_context(
                    result == "203.0.113.1",
                    "IP check returned unexpected result",
                    expected="203.0.113.1",
                    actual=result,
                    service_state={"cache_hits": isolated_cache.get_stats()["hits"]},
                    http_calls=mock_get.call_count,
                )

        log_test_checkpoint("Test completed successfully")

    @pytest.mark.asyncio
    @track_service_state("ip_service")
    @monitor_async_operations("concurrent_ip_checks", timeout=15.0)
    async def test_concurrent_operations_with_diagnostics(
        self, isolated_test_config, isolated_cache
    ):
        """Example test with concurrent operation monitoring."""
        log_test_start("test_concurrent_operations_with_diagnostics")

        # Create IP service
        mock_storage = AsyncMock(spec=SQLiteIPStorage)
        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        # Store reference for service state tracking
        self.ip_service = ip_service

        # Mock HTTP responses
        mock_responses = [f"192.168.1.{i}" for i in range(1, 11)]

        async def mock_get_ip():
            # Simulate some processing time
            await asyncio.sleep(0.1)
            return mock_responses.pop(0) if mock_responses else "192.168.1.1"

        with patch.object(ip_service, "get_current_ip", side_effect=mock_get_ip):
            # Create concurrent operations
            operations = [
                lambda: ip_service.get_current_ip(),
                lambda: ip_service.get_current_ip(),
                lambda: ip_service.get_current_ip(),
                lambda: ip_service.get_current_ip(),
                lambda: ip_service.get_current_ip(),
            ]

            operation_names = [f"ip_check_{i}" for i in range(5)]

            log_test_checkpoint("Starting concurrent operations")

            # Execute with diagnostic tracking
            results = await track_concurrent_operations(
                operations, operation_names, timeout=10.0
            )

            log_test_checkpoint("Concurrent operations completed")

            # Analyze results with enhanced assertions
            successful_results = [r for r in results if not isinstance(r, Exception)]
            failed_results = [r for r in results if isinstance(r, Exception)]

            assert_with_context(
                len(successful_results) >= 4,
                "Too many concurrent operations failed",
                successful_count=len(successful_results),
                failed_count=len(failed_results),
                total_operations=len(operations),
                failed_operations=failed_results,
            )

    @pytest.mark.asyncio
    @collect_test_metrics("database_performance")
    async def test_database_performance_with_metrics(self, isolated_sqlite_storage):
        """Example test collecting performance metrics."""
        log_test_start("test_database_performance_with_metrics")

        # Perform multiple database operations
        test_ips = [f"192.168.1.{i}" for i in range(1, 21)]

        async with DiagnosticContext("database_operations") as ctx:
            for i, ip in enumerate(test_ips):
                ctx.record_checkpoint(f"saving_ip_{i}", {"ip": ip})

                # Save IP with timing
                start_time = time.time()
                await isolated_sqlite_storage.save_current_ip(ip)
                save_duration = time.time() - start_time

                # Retrieve IP with timing
                start_time = time.time()
                retrieved_ip = await isolated_sqlite_storage.get_current_ip()
                retrieve_duration = time.time() - start_time

                # Verify and record metrics
                assert_with_context(
                    retrieved_ip == ip,
                    f"Database round-trip failed for IP {ip}",
                    expected=ip,
                    actual=retrieved_ip,
                    save_duration=save_duration,
                    retrieve_duration=retrieve_duration,
                    operation_number=i,
                )

                ctx.record_checkpoint(
                    f"verified_ip_{i}",
                    {
                        "save_duration": save_duration,
                        "retrieve_duration": retrieve_duration,
                    },
                )

        log_test_checkpoint("Database performance test completed")

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_error_handling_with_diagnostics(
        self, isolated_test_config, isolated_cache
    ):
        """Example test showing error diagnostic capabilities."""
        log_test_start("test_error_handling_with_diagnostics")

        # Create IP service with failing storage
        mock_storage = AsyncMock(spec=SQLiteIPStorage)
        mock_storage.get_current_ip.side_effect = Exception(
            "Database connection failed"
        )

        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        log_test_checkpoint("Services with failing storage initialized")

        # Test error handling
        async with DiagnosticContext("error_handling_test") as ctx:
            try:
                # This should fail due to storage error
                result = await ip_service.get_current_ip()

                # This should not be reached
                assert_with_context(
                    False,
                    "Expected storage error but operation succeeded",
                    unexpected_result=result,
                )

            except Exception as e:
                ctx.record_checkpoint(
                    "Expected error caught",
                    {"error_type": type(e).__name__, "error_message": str(e)},
                )

                # Verify it's the expected error
                assert_with_context(
                    "Database connection failed" in str(e),
                    "Got unexpected error type",
                    expected_error="Database connection failed",
                    actual_error=str(e),
                    error_type=type(e).__name__,
                )

        log_test_checkpoint("Error handling test completed")

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_timeout_scenario_with_diagnostics(
        self, isolated_test_config, isolated_cache
    ):
        """Example test showing timeout diagnostic capabilities."""
        log_test_start("test_timeout_scenario_with_diagnostics")

        # Create IP service with slow operations
        mock_storage = AsyncMock(spec=SQLiteIPStorage)

        async def slow_get_ip():
            await asyncio.sleep(2.0)  # Simulate slow operation
            return "192.168.1.1"

        mock_storage.get_current_ip.side_effect = slow_get_ip

        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        log_test_checkpoint("Services with slow operations initialized")

        # Test with timeout
        async with DiagnosticContext("timeout_test") as ctx:
            try:
                # This should timeout
                result = await asyncio.wait_for(
                    ip_service.get_current_ip(), timeout=1.0
                )

                # This should not be reached
                assert_with_context(
                    False,
                    "Expected timeout but operation succeeded",
                    unexpected_result=result,
                )

            except TimeoutError:
                ctx.record_checkpoint("Expected timeout occurred")

                # Verify timeout was handled correctly
                assert_with_context(
                    True,
                    "Timeout handled correctly",
                    timeout_duration=1.0,
                    operation_duration=2.0,
                )

        log_test_checkpoint("Timeout scenario test completed")


class TestDiagnosticPatterns:
    """Test different diagnostic patterns and use cases."""

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_service_interaction_diagnostics(
        self, isolated_test_config, isolated_cache
    ):
        """Test diagnostics for complex service interactions."""
        log_test_start("test_service_interaction_diagnostics")

        # Create multiple services
        mock_storage = AsyncMock(spec=SQLiteIPStorage)
        mock_storage.get_current_ip.return_value = "192.168.1.1"
        mock_storage.save_current_ip.return_value = None

        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        # Simulate complex interaction
        async with DiagnosticContext("service_interaction") as ctx:
            # Step 1: Get current IP
            ctx.record_checkpoint("getting_current_ip")
            current_ip = await ip_service.get_current_ip()

            # Step 2: Check cache
            ctx.record_checkpoint("checking_cache")
            cache_key = "test_key"
            cached_value = isolated_cache.get(
                "test_namespace", cache_key, CacheType.IP_RESULT
            )

            # Step 3: Perform operation
            ctx.record_checkpoint("performing_operation")
            if cached_value is None:
                isolated_cache.set(
                    "test_namespace", cache_key, current_ip, CacheType.IP_RESULT
                )

            # Step 4: Verify state
            ctx.record_checkpoint("verifying_state")
            final_cached_value = isolated_cache.get(
                "test_namespace", cache_key, CacheType.IP_RESULT
            )

            assert_with_context(
                final_cached_value == current_ip,
                "Service interaction failed",
                current_ip=current_ip,
                cached_value=cached_value,
                final_cached_value=final_cached_value,
                cache_stats=isolated_cache.get_stats(),
            )

        log_test_checkpoint("Service interaction test completed")

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_resource_leak_detection(self, isolated_test_config):
        """Test resource leak detection capabilities."""
        log_test_start("test_resource_leak_detection")

        # Create resources that might leak
        resources = []

        async with DiagnosticContext("resource_management") as ctx:
            # Create multiple resources
            for i in range(10):
                ctx.record_checkpoint(f"creating_resource_{i}")

                # Simulate resource creation
                resource = AsyncMock()
                resource.cleanup = AsyncMock()
                resources.append(resource)

                # Simulate some work
                await asyncio.sleep(0.01)

            ctx.record_checkpoint("all_resources_created")

            # Cleanup most resources (simulate partial cleanup)
            for resource in resources[:8]:  # Only cleanup 8 out of 10
                await resource.cleanup()

            ctx.record_checkpoint("partial_cleanup_completed")

            # The diagnostic system should detect the remaining resources
            # This would be caught by the resource monitoring

        log_test_checkpoint("Resource leak detection test completed")

    @pytest.mark.asyncio
    @with_diagnostics
    async def test_performance_regression_detection(
        self, isolated_test_config, isolated_cache
    ):
        """Test performance regression detection."""
        log_test_start("test_performance_regression_detection")

        # Simulate operations with varying performance
        mock_storage = AsyncMock(spec=SQLiteIPStorage)

        async def variable_performance_get_ip():
            # Simulate variable performance
            delay = (
                0.1 if len(mock_storage.get_current_ip.call_args_list) % 2 == 0 else 0.5
            )
            await asyncio.sleep(delay)
            return "192.168.1.1"

        mock_storage.get_current_ip.side_effect = variable_performance_get_ip

        ip_service = IPService(
            config=isolated_test_config, storage=mock_storage, cache=isolated_cache
        )

        # Perform multiple operations and measure performance
        async with DiagnosticContext("performance_measurement") as ctx:
            for i in range(10):
                ctx.record_checkpoint(f"operation_{i}")

                await ip_service.get_current_ip()
                # The diagnostic system will collect these metrics
                # and detect performance variations

        log_test_checkpoint("Performance regression detection test completed")
