"""
Helper functions and fixtures for integrating error diagnostics into tests.

This module provides easy-to-use decorators and fixtures that can be
added to existing tests without major refactoring.
"""

import asyncio
from collections.abc import Callable
import functools
import inspect
import time
from typing import Any

import pytest

from .error_diagnostics import (
    diagnostic_context,
    enhanced_assert,
    get_diagnostics,
    measure_performance,
)
from .test_reporting import TestReporter

# Global test reporter instance
_test_reporter = TestReporter()


def get_test_reporter() -> TestReporter:
    """Get the global test reporter instance."""
    return _test_reporter


@pytest.fixture
def diagnostics():
    """Pytest fixture providing error diagnostics."""
    return get_diagnostics()


@pytest.fixture
def test_reporter():
    """Pytest fixture providing test reporter."""
    return get_test_reporter()


@pytest.fixture
async def diagnostic_test_context(request):
    """
    Pytest fixture that automatically provides diagnostic context for tests.

    Usage:
        async def test_something(diagnostic_test_context):
            # Test code here - diagnostics are automatically tracked
            pass
    """
    test_name = request.node.name
    test_file = request.node.fspath.basename

    async with diagnostic_context(test_name, test_file) as diagnostics:
        yield diagnostics


def with_diagnostics(func: Callable) -> Callable:
    """
    Decorator that adds comprehensive diagnostics to a test function.

    Usage:
        @with_diagnostics
        async def test_something():
            # Test code here
            pass
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract test information
        test_name = func.__name__
        test_file = inspect.getfile(func)

        async with diagnostic_context(test_name, test_file) as diagnostics:
            # Track the main test execution
            task = asyncio.current_task()
            if task:
                diagnostics.register_task(task, f"test_{test_name}")

            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Generate and store diagnostic report
                report = diagnostics.create_diagnostic_report(test_name, test_file, e)
                get_test_reporter().add_report(report)
                raise

    return wrapper


def track_service_state(service_name: str):
    """
    Decorator that tracks service state throughout test execution.

    Usage:
        @track_service_state("ip_service")
        async def test_ip_service():
            # Service state changes will be tracked
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            diagnostics = get_diagnostics()

            # Record initial state if service is available
            if hasattr(args[0], service_name):
                service = getattr(args[0], service_name)
                initial_state = extract_service_state(service)
                diagnostics.record_service_state(service_name, initial_state)

            try:
                return await func(*args, **kwargs)
            finally:
                # Record final state
                if hasattr(args[0], service_name):
                    service = getattr(args[0], service_name)
                    final_state = extract_service_state(service)
                    diagnostics.record_service_state(
                        f"{service_name}_final", final_state
                    )

        return wrapper

    return decorator


def extract_service_state(service: Any) -> dict[str, Any]:
    """Extract relevant state information from a service object."""
    state = {}

    # Common service state attributes
    state_attrs = [
        "is_healthy",
        "is_degraded",
        "current_health",
        "health_level",
        "is_circuit_breaker_open",
        "circuit_breaker_state",
        "failure_count",
        "last_success_time",
        "last_failure_time",
        "success_rate",
        "response_time",
        "active_connections",
        "queue_size",
        "cache_hit_rate",
        "cache_size",
        "pending_operations",
    ]

    for attr in state_attrs:
        if hasattr(service, attr):
            try:
                value = getattr(service, attr)
                if callable(value):
                    try:
                        state[attr] = value()
                    except Exception:
                        state[attr] = "error_calling_method"
                else:
                    state[attr] = value
            except Exception:
                state[attr] = "error_accessing_attribute"

    return state


def monitor_async_operations(operation_name: str, timeout: float = 30.0):
    """
    Decorator that monitors async operations with enhanced diagnostics.

    Usage:
        @monitor_async_operations("ip_check", timeout=10.0)
        async def test_ip_check():
            # Operation will be monitored for performance and failures
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            diagnostics = get_diagnostics()
            start_time = time.time()

            # Register operation tracking
            diagnostics.record_interaction(f"Started {operation_name}")

            try:
                # Execute with timeout and performance tracking
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)

                # Record success metrics
                duration = time.time() - start_time
                diagnostics.add_performance_sample(
                    operation_name, duration, {"success": True, "timeout": timeout}
                )
                diagnostics.record_interaction(
                    f"Completed {operation_name} in {duration:.3f}s"
                )

                return result

            except TimeoutError:
                duration = time.time() - start_time
                diagnostics.add_performance_sample(
                    f"{operation_name}_timeout",
                    duration,
                    {"success": False, "timeout": timeout, "error": "timeout"},
                )
                diagnostics.record_interaction(
                    f"Timeout in {operation_name} after {duration:.3f}s"
                )
                raise

            except Exception as e:
                duration = time.time() - start_time
                diagnostics.add_performance_sample(
                    f"{operation_name}_error",
                    duration,
                    {"success": False, "error": str(e), "error_type": type(e).__name__},
                )
                diagnostics.record_interaction(
                    f"Error in {operation_name} after {duration:.3f}s: {e}"
                )
                raise

        return wrapper

    return decorator


def assert_with_context(condition: bool, message: str, **context):
    """
    Enhanced assertion that includes diagnostic context.

    Usage:
        assert_with_context(
            result == expected,
            "IP check failed",
            actual_ip=result,
            expected_ip=expected,
            service_state=service.get_state()
        )
    """
    enhanced_assert(condition, message, context)


def collect_test_metrics(metrics_name: str):
    """
    Decorator that collects test metrics for performance analysis.

    Usage:
        @collect_test_metrics("database_operations")
        async def test_database_performance():
            # Metrics will be collected automatically
            pass
    """

    def decorator(func: Callable) -> Callable:
        @measure_performance(metrics_name)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def track_concurrent_operations(
    operations: list[Callable], operation_names: list[str] = None, timeout: float = 30.0
) -> list[Any]:
    """
    Track multiple concurrent operations with enhanced diagnostics.

    Usage:
        results = await track_concurrent_operations([
            lambda: service.get_ip(),
            lambda: service.check_health(),
            lambda: service.get_metrics()
        ], ["get_ip", "check_health", "get_metrics"])
    """
    diagnostics = get_diagnostics()

    if operation_names is None:
        operation_names = [f"operation_{i}" for i in range(len(operations))]

    # Create tasks with tracking
    tasks = []
    for i, operation in enumerate(operations):
        task = asyncio.create_task(operation())
        diagnostics.register_task(
            task,
            operation_names[i],
            {"operation_index": i, "total_operations": len(operations)},
        )
        tasks.append(task)

    try:
        # Execute with timeout
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
        )

        # Analyze results
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]

        diagnostics.record_interaction(
            f"Concurrent operations completed: {len(successful)}/{len(operations)} succeeded"
        )

        return results

    except TimeoutError:
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation
        await asyncio.gather(*tasks, return_exceptions=True)

        diagnostics.record_interaction(
            f"Concurrent operations timed out after {timeout}s"
        )
        raise


class DiagnosticContext:
    """Context manager for manual diagnostic tracking."""

    def __init__(self, operation_name: str, context: dict[str, Any] = None):
        self.operation_name = operation_name
        self.context = context or {}
        self.start_time = None
        self.diagnostics = get_diagnostics()

    async def __aenter__(self):
        self.start_time = time.time()
        self.diagnostics.record_interaction(f"Started {self.operation_name}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time

        if exc_type is None:
            self.diagnostics.add_performance_sample(
                self.operation_name, duration, {**self.context, "success": True}
            )
            self.diagnostics.record_interaction(
                f"Completed {self.operation_name} in {duration:.3f}s"
            )
        else:
            self.diagnostics.add_performance_sample(
                f"{self.operation_name}_error",
                duration,
                {
                    **self.context,
                    "success": False,
                    "error": str(exc_val),
                    "error_type": exc_type.__name__,
                },
            )
            self.diagnostics.record_interaction(
                f"Failed {self.operation_name} after {duration:.3f}s: {exc_val}"
            )

    def record_checkpoint(self, checkpoint_name: str, data: dict[str, Any] = None):
        """Record a checkpoint during operation execution."""
        checkpoint_time = time.time() - self.start_time
        self.diagnostics.record_interaction(
            f"Checkpoint '{checkpoint_name}' in {self.operation_name} at {checkpoint_time:.3f}s"
        )
        if data:
            self.diagnostics.add_performance_sample(
                f"{self.operation_name}_{checkpoint_name}", checkpoint_time, data
            )


def create_test_fixtures_with_diagnostics():
    """Create enhanced test fixtures with built-in diagnostics."""

    @pytest.fixture
    async def diagnostic_ip_service(mock_ip_service):
        """IP service with diagnostic tracking."""
        diagnostics = get_diagnostics()

        # Wrap service methods with diagnostics
        original_get_ip = mock_ip_service.get_current_ip

        async def tracked_get_ip():
            async with DiagnosticContext("get_current_ip"):
                return await original_get_ip()

        mock_ip_service.get_current_ip = tracked_get_ip

        # Record initial state
        diagnostics.record_service_state(
            "ip_service", extract_service_state(mock_ip_service)
        )

        yield mock_ip_service

        # Record final state
        diagnostics.record_service_state(
            "ip_service_final", extract_service_state(mock_ip_service)
        )

    @pytest.fixture
    async def diagnostic_storage(mock_storage):
        """Storage with diagnostic tracking."""
        diagnostics = get_diagnostics()

        # Wrap storage methods with diagnostics
        original_save_ip = mock_storage.save_current_ip
        original_get_ip = mock_storage.get_current_ip

        async def tracked_save_ip(ip: str):
            async with DiagnosticContext("save_current_ip", {"ip": ip}):
                return await original_save_ip(ip)

        async def tracked_get_ip():
            async with DiagnosticContext("get_current_ip"):
                return await original_get_ip()

        mock_storage.save_current_ip = tracked_save_ip
        mock_storage.get_current_ip = tracked_get_ip

        # Record initial state
        diagnostics.record_service_state("storage", extract_service_state(mock_storage))

        yield mock_storage

        # Record final state
        diagnostics.record_service_state(
            "storage_final", extract_service_state(mock_storage)
        )

    return {
        "diagnostic_ip_service": diagnostic_ip_service,
        "diagnostic_storage": diagnostic_storage,
    }


# Convenience functions for common diagnostic patterns
def log_test_start(test_name: str):
    """Log test start with diagnostic context."""
    get_diagnostics().record_interaction(f"Test started: {test_name}")


def log_test_checkpoint(checkpoint_name: str, data: dict[str, Any] = None):
    """Log a test checkpoint with optional data."""
    get_diagnostics().record_interaction(f"Test checkpoint: {checkpoint_name}")
    if data:
        get_diagnostics().add_performance_sample(
            f"checkpoint_{checkpoint_name}", 0, data
        )


def log_test_completion(test_name: str, duration: float = None):
    """Log test completion with diagnostic context."""
    message = f"Test completed: {test_name}"
    if duration is not None:
        message += f" in {duration:.3f}s"
    get_diagnostics().record_interaction(message)


def generate_test_report(test_suite: str, format: str = "summary") -> str:
    """Generate a test report in the specified format."""
    reporter = get_test_reporter()

    if format == "html":
        return reporter.generate_html_report(test_suite)
    if format == "json":
        return reporter.generate_json_report(test_suite)
    return reporter.generate_summary_report(test_suite)
