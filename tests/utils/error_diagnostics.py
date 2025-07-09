"""
Enhanced error diagnostics utilities for integration tests.

This module provides comprehensive error reporting and diagnostic capabilities
to improve debugging of integration test failures.
"""

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import functools
import inspect
import logging
import sys
import time
import traceback
from typing import Any

import psutil


@dataclass
class TaskFailureInfo:
    """Information about a failed async task."""

    task_name: str
    task_id: str
    exception: Exception
    start_time: float
    failure_time: float
    duration: float
    stack_trace: str
    task_state: str
    resource_usage: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceLeakInfo:
    """Information about a resource leak."""

    resource_type: str
    resource_id: str
    creation_location: str
    current_count: int
    expected_count: int
    leak_size: int
    stack_trace: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceInteractionFailure:
    """Information about service interaction failures."""

    service_name: str
    operation: str
    failure_reason: str
    service_state: dict[str, Any]
    interaction_history: list[str]
    recovery_suggestions: list[str]
    timestamp: float


@dataclass
class TestDiagnosticReport:
    """Comprehensive diagnostic report for test failures."""

    test_name: str
    test_file: str
    test_duration: float
    failure_type: str
    primary_error: Exception
    task_failures: list[TaskFailureInfo] = field(default_factory=list)
    resource_leaks: list[ResourceLeakInfo] = field(default_factory=list)
    service_failures: list[ServiceInteractionFailure] = field(default_factory=list)
    performance_metrics: dict[str, Any] = field(default_factory=dict)
    system_state: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class ErrorDiagnostics:
    """Enhanced error diagnostics for integration tests."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_tasks: dict[str, dict[str, Any]] = {}
        self.resource_baselines: dict[str, int] = {}
        self.service_states: dict[str, dict[str, Any]] = {}
        self.interaction_history: list[str] = []
        self.performance_samples: list[dict[str, Any]] = []
        self.start_time: float | None = None

    def start_tracking(self, test_name: str) -> None:
        """Start tracking for a test."""
        self.start_time = time.time()
        self.active_tasks.clear()
        self.resource_baselines.clear()
        self.service_states.clear()
        self.interaction_history.clear()
        self.performance_samples.clear()

        # Capture initial system state
        process = psutil.Process()
        self.resource_baselines = {
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "open_files": len(process.open_files()),
            "threads": process.num_threads(),
            "connections": len(process.connections()),
        }

        self.logger.info(f"Started error diagnostics tracking for {test_name}")

    def register_task(
        self, task: asyncio.Task, name: str, context: dict[str, Any] = None
    ) -> None:
        """Register an async task for monitoring."""
        task_id = f"{name}_{id(task)}"
        self.active_tasks[task_id] = {
            "task": task,
            "name": name,
            "start_time": time.time(),
            "context": context or {},
            "registered_location": self._get_caller_location(),
        }

    def record_service_state(self, service_name: str, state: dict[str, Any]) -> None:
        """Record current state of a service."""
        self.service_states[service_name] = {
            "state": state.copy(),
            "timestamp": time.time(),
            "location": self._get_caller_location(),
        }

    def record_interaction(self, description: str) -> None:
        """Record a service interaction."""
        timestamp = time.time()
        location = self._get_caller_location()
        self.interaction_history.append(
            f"{timestamp:.3f}: {description} (at {location})"
        )

    def add_performance_sample(
        self, metric_name: str, value: float, context: dict[str, Any] = None
    ) -> None:
        """Add a performance measurement sample."""
        self.performance_samples.append(
            {
                "metric": metric_name,
                "value": value,
                "timestamp": time.time(),
                "context": context or {},
                "location": self._get_caller_location(),
            }
        )

    def create_diagnostic_report(
        self, test_name: str, test_file: str, primary_error: Exception
    ) -> TestDiagnosticReport:
        """Create a comprehensive diagnostic report."""
        test_duration = time.time() - (self.start_time or time.time())

        # Analyze task failures
        task_failures = self._analyze_task_failures()

        # Detect resource leaks
        resource_leaks = self._detect_resource_leaks()

        # Analyze service failures
        service_failures = self._analyze_service_failures()

        # Collect performance metrics
        performance_metrics = self._collect_performance_metrics()

        # Capture current system state
        system_state = self._capture_system_state()

        # Generate recommendations
        recommendations = self._generate_recommendations(
            primary_error, task_failures, resource_leaks, service_failures
        )

        return TestDiagnosticReport(
            test_name=test_name,
            test_file=test_file,
            test_duration=test_duration,
            failure_type=type(primary_error).__name__,
            primary_error=primary_error,
            task_failures=task_failures,
            resource_leaks=resource_leaks,
            service_failures=service_failures,
            performance_metrics=performance_metrics,
            system_state=system_state,
            recommendations=recommendations,
        )

    def _analyze_task_failures(self) -> list[TaskFailureInfo]:
        """Analyze failures in tracked async tasks."""
        failures = []

        for task_id, task_info in self.active_tasks.items():
            task = task_info["task"]

            if task.done():
                try:
                    task.result()
                except Exception as e:
                    failure_time = time.time()
                    duration = failure_time - task_info["start_time"]

                    failures.append(
                        TaskFailureInfo(
                            task_name=task_info["name"],
                            task_id=task_id,
                            exception=e,
                            start_time=task_info["start_time"],
                            failure_time=failure_time,
                            duration=duration,
                            stack_trace=traceback.format_exc(),
                            task_state=str(task._state),
                            resource_usage=self._get_task_resource_usage(task),
                            context=task_info["context"],
                        )
                    )

        return failures

    def _detect_resource_leaks(self) -> list[ResourceLeakInfo]:
        """Detect resource leaks by comparing current vs baseline."""
        leaks = []

        try:
            process = psutil.Process()
            current_resources = {
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "open_files": len(process.open_files()),
                "threads": process.num_threads(),
                "connections": len(process.connections()),
            }

            for resource_type, current_count in current_resources.items():
                baseline = self.resource_baselines.get(resource_type, 0)
                if current_count > baseline + 5:  # Threshold for leak detection
                    leaks.append(
                        ResourceLeakInfo(
                            resource_type=resource_type,
                            resource_id=f"{resource_type}_leak",
                            creation_location=self._get_caller_location(),
                            current_count=current_count,
                            expected_count=baseline,
                            leak_size=current_count - baseline,
                            stack_trace=traceback.format_stack()[-3],
                            context={"baseline": baseline, "current": current_count},
                        )
                    )

        except Exception as e:
            self.logger.warning(f"Failed to detect resource leaks: {e}")

        return leaks

    def _analyze_service_failures(self) -> list[ServiceInteractionFailure]:
        """Analyze service interaction failures."""
        failures = []

        for service_name, service_info in self.service_states.items():
            state = service_info["state"]

            # Check for common failure indicators
            if state.get("is_degraded", False):
                failures.append(
                    ServiceInteractionFailure(
                        service_name=service_name,
                        operation="health_check",
                        failure_reason=state.get("degradation_reason", "Unknown"),
                        service_state=state,
                        interaction_history=self.interaction_history[
                            -10:
                        ],  # Last 10 interactions
                        recovery_suggestions=self._get_recovery_suggestions(
                            service_name, state
                        ),
                        timestamp=service_info["timestamp"],
                    )
                )

            if state.get("circuit_breaker_open", False):
                failures.append(
                    ServiceInteractionFailure(
                        service_name=service_name,
                        operation="circuit_breaker",
                        failure_reason="Circuit breaker is open",
                        service_state=state,
                        interaction_history=self.interaction_history[-10:],
                        recovery_suggestions=[
                            "Wait for circuit breaker recovery",
                            "Check underlying service health",
                        ],
                        timestamp=service_info["timestamp"],
                    )
                )

        return failures

    def _collect_performance_metrics(self) -> dict[str, Any]:
        """Collect and analyze performance metrics."""
        metrics = {
            "sample_count": len(self.performance_samples),
            "by_metric": {},
            "trends": {},
            "outliers": [],
        }

        # Group samples by metric
        by_metric = {}
        for sample in self.performance_samples:
            metric_name = sample["metric"]
            if metric_name not in by_metric:
                by_metric[metric_name] = []
            by_metric[metric_name].append(sample)

        # Calculate statistics for each metric
        for metric_name, samples in by_metric.items():
            values = [s["value"] for s in samples]
            if values:
                metrics["by_metric"][metric_name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "samples": samples,
                }

        return metrics

    def _capture_system_state(self) -> dict[str, Any]:
        """Capture current system state."""
        try:
            process = psutil.Process()
            return {
                "cpu_percent": process.cpu_percent(),
                "memory_info": process.memory_info()._asdict(),
                "open_files_count": len(process.open_files()),
                "threads_count": process.num_threads(),
                "connections_count": len(process.connections()),
                "active_tasks_count": len(self.active_tasks),
                "python_version": sys.version,
                "platform": sys.platform,
            }
        except Exception as e:
            return {"error": f"Failed to capture system state: {e}"}

    def _generate_recommendations(
        self,
        primary_error: Exception,
        task_failures: list[TaskFailureInfo],
        resource_leaks: list[ResourceLeakInfo],
        service_failures: list[ServiceInteractionFailure],
    ) -> list[str]:
        """Generate actionable recommendations based on diagnostics."""
        recommendations = []

        # Analyze primary error
        if isinstance(primary_error, asyncio.TimeoutError):
            recommendations.append(
                "Consider increasing timeout values for async operations"
            )
            recommendations.append("Check for blocking operations in async contexts")

        if isinstance(primary_error, ConnectionError):
            recommendations.append(
                "Verify network connectivity and service availability"
            )
            recommendations.append("Check HTTP mock server configuration")

        # Analyze task failures
        if task_failures:
            recommendations.append(f"Review {len(task_failures)} failed async tasks")
            for failure in task_failures[:3]:  # Top 3 failures
                recommendations.append(f"- {failure.task_name}: {failure.exception}")

        # Analyze resource leaks
        if resource_leaks:
            recommendations.append(f"Address {len(resource_leaks)} resource leaks")
            for leak in resource_leaks[:3]:  # Top 3 leaks
                recommendations.append(
                    f"- {leak.resource_type}: {leak.leak_size} units leaked"
                )

        # Analyze service failures
        if service_failures:
            recommendations.append(
                f"Investigate {len(service_failures)} service failures"
            )
            for failure in service_failures[:3]:  # Top 3 failures
                recommendations.extend(failure.recovery_suggestions)

        return recommendations

    def _get_task_resource_usage(self, task: asyncio.Task) -> dict[str, Any]:
        """Get resource usage information for a task."""
        try:
            return {
                "state": str(task._state),
                "callbacks": len(task._callbacks) if hasattr(task, "_callbacks") else 0,
                "done": task.done(),
                "cancelled": task.cancelled(),
            }
        except Exception:
            return {}

    def _get_recovery_suggestions(
        self, service_name: str, state: dict[str, Any]
    ) -> list[str]:
        """Get recovery suggestions for a service."""
        suggestions = []

        if service_name == "circuit_breaker":
            suggestions.append("Wait for circuit breaker recovery timeout")
            suggestions.append("Check underlying service health")

        if service_name == "ip_service":
            suggestions.append("Verify IP API endpoints are accessible")
            suggestions.append("Check network connectivity")

        if service_name == "storage":
            suggestions.append("Verify database file permissions")
            suggestions.append("Check for database lock contention")

        return suggestions

    def _get_caller_location(self) -> str:
        """Get the location of the caller for context."""
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back.f_back
            filename = caller_frame.f_code.co_filename
            line_number = caller_frame.f_lineno
            function_name = caller_frame.f_code.co_name
            return f"{filename}:{line_number} in {function_name}"
        except Exception:
            return "unknown location"
        finally:
            del frame


# Global diagnostics instance
_diagnostics = ErrorDiagnostics()


def get_diagnostics() -> ErrorDiagnostics:
    """Get the global diagnostics instance."""
    return _diagnostics


@asynccontextmanager
async def diagnostic_context(test_name: str, test_file: str):
    """Context manager for test diagnostics."""
    diagnostics = get_diagnostics()
    diagnostics.start_tracking(test_name)

    try:
        yield diagnostics
    except Exception as e:
        # Generate diagnostic report
        report = diagnostics.create_diagnostic_report(test_name, test_file, e)

        # Log detailed diagnostic information
        logger = logging.getLogger(__name__)
        logger.error(f"Test failure diagnostic report for {test_name}:")
        logger.error(f"  Primary error: {report.failure_type}: {report.primary_error}")
        logger.error(f"  Duration: {report.test_duration:.2f}s")

        if report.task_failures:
            logger.error(f"  Task failures ({len(report.task_failures)}):")
            for failure in report.task_failures[:3]:
                logger.error(f"    - {failure.task_name}: {failure.exception}")

        if report.resource_leaks:
            logger.error(f"  Resource leaks ({len(report.resource_leaks)}):")
            for leak in report.resource_leaks[:3]:
                logger.error(f"    - {leak.resource_type}: {leak.leak_size} units")

        if report.service_failures:
            logger.error(f"  Service failures ({len(report.service_failures)}):")
            for failure in report.service_failures[:3]:
                logger.error(f"    - {failure.service_name}: {failure.failure_reason}")

        if report.recommendations:
            logger.error("  Recommendations:")
            for rec in report.recommendations[:5]:
                logger.error(f"    - {rec}")

        # Re-raise the original exception with enhanced context
        raise e


def enhanced_assert(
    condition: bool, message: str, context: dict[str, Any] = None
) -> None:
    """Enhanced assertion with diagnostic context."""
    if not condition:
        diagnostics = get_diagnostics()

        # Add context to interaction history
        diagnostics.record_interaction(f"Assertion failed: {message}")

        # Create enhanced error message
        enhanced_message = f"Assertion failed: {message}"
        if context:
            enhanced_message += f"\nContext: {context}"

        # Add recent interactions
        if diagnostics.interaction_history:
            enhanced_message += "\nRecent interactions:"
            for interaction in diagnostics.interaction_history[-5:]:
                enhanced_message += f"\n  {interaction}"

        raise AssertionError(enhanced_message)


def track_async_task(name: str, context: dict[str, Any] = None):
    """Decorator to track async tasks for diagnostics."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            task = asyncio.current_task()
            if task:
                get_diagnostics().register_task(task, name, context)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def measure_performance(metric_name: str, context: dict[str, Any] = None):
    """Decorator to measure performance of a function."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                get_diagnostics().add_performance_sample(metric_name, duration, context)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_context = dict(context or {})
                error_context["error"] = str(e)
                get_diagnostics().add_performance_sample(
                    f"{metric_name}_error", duration, error_context
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                get_diagnostics().add_performance_sample(metric_name, duration, context)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_context = dict(context or {})
                error_context["error"] = str(e)
                get_diagnostics().add_performance_sample(
                    f"{metric_name}_error", duration, error_context
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator
