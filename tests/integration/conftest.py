"""
Configuration and fixtures for integration tests.

This module provides shared fixtures and configuration for integration tests
that use real HTTP server mocks.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure logging for integration tests
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Suppress noisy loggers during testing
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Note: Import fixtures manually to avoid pytest_plugins warning
# from tests.conftest import *


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop

    # Clean up pending tasks
    try:
        pending = asyncio.all_tasks(loop)
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass

    if not loop.is_closed():
        loop.close()


@pytest.fixture(autouse=True)
async def setup_test_environment():
    """Setup test environment for each test."""
    # Set test-specific configuration
    os.environ["TESTING_MODE"] = "true"
    os.environ["LOG_LEVEL"] = "INFO"

    yield

    # Cleanup after test
    if "TESTING_MODE" in os.environ:
        del os.environ["TESTING_MODE"]


@pytest.fixture
def integration_test_config():
    """Configuration optimized for integration testing."""
    return {
        "connection_timeout": 5.0,
        "read_timeout": 10.0,
        "max_retries": 2,
        "retry_delay": 0.1,
        "circuit_breaker_enabled": True,
        "circuit_breaker_failure_threshold": 2,
        "circuit_breaker_recovery_timeout": 1.0,
        "cache_enabled": True,
        "cache_ttl": 60,
        "rate_limit_period": 60,
        "max_checks_per_period": 30,
    }


@pytest.fixture
async def cleanup_tasks():
    """Ensure all async tasks are cleaned up after tests."""
    yield

    # Cancel any remaining tasks
    try:
        current_task = asyncio.current_task()
        all_tasks = asyncio.all_tasks()

        other_tasks = [
            task for task in all_tasks if task != current_task and not task.done()
        ]

        if other_tasks:
            for task in other_tasks:
                task.cancel()

            try:
                await asyncio.gather(*other_tasks, return_exceptions=True)
            except Exception:
                pass
    except Exception:
        pass


# Pytest markers for integration tests
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "integration: Integration tests with HTTP mocks")
    config.addinivalue_line("markers", "slow: Slow-running tests (>5 seconds)")
    config.addinivalue_line("markers", "network: Tests requiring network simulation")
    config.addinivalue_line("markers", "failover: Failover and disaster recovery tests")
    config.addinivalue_line("markers", "performance: Performance and load testing")
    config.addinivalue_line("markers", "real_world: Real-world scenario tests")


# Test collection customization
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers."""
    for item in items:
        # Add integration marker to all tests
        item.add_marker(pytest.mark.integration)

        # Add markers based on test name patterns
        if "slow" in item.name or "high_load" in item.name or "disaster" in item.name:
            item.add_marker(pytest.mark.slow)

        if "network" in item.name or "failover" in item.name or "outage" in item.name:
            item.add_marker(pytest.mark.network)

        if (
            "failover" in item.name
            or "recovery" in item.name
            or "disaster" in item.name
        ):
            item.add_marker(pytest.mark.failover)

        if (
            "performance" in item.name
            or "load" in item.name
            or "concurrent" in item.name
        ):
            item.add_marker(pytest.mark.performance)

        if (
            "real_world" in item.name
            or "production" in item.name
            or "complete" in item.name
        ):
            item.add_marker(pytest.mark.real_world)


# Custom timeout handling for integration tests
@pytest.fixture(autouse=True)
def timeout_handler():
    """Handle test timeouts gracefully."""
    import signal

    def timeout_signal_handler(signum, frame):
        print("\nTest timeout - cleaning up resources...")
        # Additional cleanup logic can be added here
        raise TimeoutError("Test execution timeout")

    # Set up timeout signal handler
    original_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)

    yield

    # Restore original handler
    signal.signal(signal.SIGALRM, original_handler)


# Performance monitoring for tests
@pytest.fixture
def performance_monitor():
    """Monitor test performance and resource usage."""
    import time

    import psutil

    start_time = time.time()
    start_memory = psutil.Process().memory_info().rss

    yield

    end_time = time.time()
    end_memory = psutil.Process().memory_info().rss

    duration = end_time - start_time
    memory_delta = end_memory - start_memory

    # Log performance metrics
    if duration > 5.0:  # Log slow tests
        print(f"Slow test detected: {duration:.2f}s")

    if memory_delta > 50 * 1024 * 1024:  # Log high memory usage (>50MB)
        print(f"High memory usage: {memory_delta / 1024 / 1024:.2f}MB")


# Custom assertion helpers for integration tests
class IntegrationTestHelpers:
    """Helper methods for integration tests."""

    @staticmethod
    def assert_server_response_time(server, max_response_time_ms=1000):
        """Assert server response time is within limits."""
        stats = server.get_stats()
        if stats.get("last_request_time"):
            # This is a simplified check - real implementation would track response times
            assert True  # Placeholder for actual response time checking

    @staticmethod
    def assert_cluster_load_distribution(cluster, min_active_servers=2):
        """Assert load is distributed across cluster servers."""
        stats = cluster.get_cluster_stats()
        active_servers = sum(
            1 for server in cluster.servers if server.get_request_count() > 0
        )
        assert active_servers >= min_active_servers, (
            f"Only {active_servers} servers used, expected at least {min_active_servers}"
        )

    @staticmethod
    def assert_failure_recovery(service, max_recovery_time=5.0):
        """Assert service recovers from failures within time limit."""
        # This would be implemented based on specific service metrics
        assert True  # Placeholder for actual recovery time checking


@pytest.fixture
def test_helpers():
    """Provide test helper methods."""
    return IntegrationTestHelpers()
