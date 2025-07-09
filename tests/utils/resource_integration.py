"""
Resource monitoring integration utilities for tests.

This module provides utilities to integrate resource monitoring with existing
test infrastructure and common test patterns.
"""

import asyncio
import functools
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar
from unittest.mock import patch

import pytest

from .resource_monitor import ResourceMonitor, ResourceLimits, resource_context

T = TypeVar("T")


class ResourceMonitoringDecorator:
    """Decorator to add resource monitoring to test functions."""
    
    def __init__(self, limits: Optional[ResourceLimits] = None, fail_on_violations: bool = True):
        self.limits = limits or ResourceLimits()
        self.fail_on_violations = fail_on_violations
    
    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Extract resource_monitor from kwargs if present
            resource_monitor = kwargs.get('resource_monitor')
            if not resource_monitor:
                # Create a temporary monitor if not provided
                resource_monitor = ResourceMonitor(self.limits)
                await resource_monitor.start_monitoring()
                
                try:
                    async with resource_context(resource_monitor, func.__name__) as ctx:
                        result = await func(*args, **kwargs)
                        
                        # Check for violations
                        if self.fail_on_violations and resource_monitor.has_violations():
                            violations = resource_monitor.get_violations()
                            pytest.fail(f"Resource violations in {func.__name__}: {violations}")
                        
                        return result
                finally:
                    await resource_monitor.stop_monitoring()
            else:
                # Use existing monitor
                async with resource_context(resource_monitor, func.__name__) as ctx:
                    result = await func(*args, **kwargs)
                    
                    # Check for violations
                    if self.fail_on_violations and resource_monitor.has_violations():
                        violations = resource_monitor.get_violations()
                        pytest.fail(f"Resource violations in {func.__name__}: {violations}")
                    
                    return result
        
        return wrapper


def monitor_resources(limits: Optional[ResourceLimits] = None, fail_on_violations: bool = True):
    """
    Decorator to monitor resource usage in test functions.
    
    Args:
        limits: Resource limits to enforce
        fail_on_violations: Whether to fail test on resource violations
    
    Returns:
        Decorated function with resource monitoring
    """
    return ResourceMonitoringDecorator(limits, fail_on_violations)


class ResourceProfiler:
    """Profile resource usage patterns across multiple test runs."""
    
    def __init__(self):
        self.profiles: Dict[str, List[Dict[str, Any]]] = {}
        self.baseline_profile: Optional[Dict[str, Any]] = None
    
    def profile_test(self, test_name: str, resource_monitor: ResourceMonitor):
        """Profile a test's resource usage."""
        if test_name not in self.profiles:
            self.profiles[test_name] = []
        
        report = resource_monitor.get_report()
        self.profiles[test_name].append(report)
    
    def get_profile_summary(self, test_name: str) -> Dict[str, Any]:
        """Get summary statistics for a test's resource usage."""
        if test_name not in self.profiles:
            return {}
        
        profiles = self.profiles[test_name]
        if not profiles:
            return {}
        
        # Calculate averages and maximums
        avg_memory = sum(p['peak_usage']['memory_mb'] for p in profiles) / len(profiles)
        max_memory = max(p['peak_usage']['memory_mb'] for p in profiles)
        
        avg_tasks = sum(p['peak_usage']['async_tasks'] for p in profiles) / len(profiles)
        max_tasks = max(p['peak_usage']['async_tasks'] for p in profiles)
        
        avg_db_conn = sum(p['peak_usage']['database_connections'] for p in profiles) / len(profiles)
        max_db_conn = max(p['peak_usage']['database_connections'] for p in profiles)
        
        total_violations = sum(len(p['violations']) for p in profiles)
        
        return {
            'test_name': test_name,
            'run_count': len(profiles),
            'memory': {
                'average_mb': avg_memory,
                'peak_mb': max_memory
            },
            'async_tasks': {
                'average': avg_tasks,
                'peak': max_tasks
            },
            'database_connections': {
                'average': avg_db_conn,
                'peak': max_db_conn
            },
            'violations': {
                'total': total_violations,
                'rate': total_violations / len(profiles)
            }
        }
    
    def compare_to_baseline(self, test_name: str) -> Dict[str, Any]:
        """Compare test resource usage to baseline."""
        if not self.baseline_profile:
            return {}
        
        current_summary = self.get_profile_summary(test_name)
        if not current_summary:
            return {}
        
        baseline_memory = self.baseline_profile['memory']['peak_mb']
        current_memory = current_summary['memory']['peak_mb']
        
        baseline_tasks = self.baseline_profile['async_tasks']['peak']
        current_tasks = current_summary['async_tasks']['peak']
        
        return {
            'memory_change_percent': ((current_memory - baseline_memory) / baseline_memory) * 100,
            'task_change_percent': ((current_tasks - baseline_tasks) / baseline_tasks) * 100,
            'performance_regression': current_memory > baseline_memory * 1.2,  # 20% threshold
            'stability_regression': current_summary['violations']['rate'] > 0.1  # 10% violation rate
        }
    
    def set_baseline(self, test_name: str):
        """Set a test's resource usage as baseline."""
        summary = self.get_profile_summary(test_name)
        if summary:
            self.baseline_profile = summary


class ResourceAwareTestCase:
    """Base class for test cases that need resource monitoring."""
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self.resource_monitor: Optional[ResourceMonitor] = None
        self.profiler = ResourceProfiler()
    
    async def setup_resource_monitoring(self):
        """Set up resource monitoring for test case."""
        if self.resource_monitor:
            return
        
        self.resource_monitor = ResourceMonitor(self.limits)
        await self.resource_monitor.start_monitoring()
    
    async def teardown_resource_monitoring(self):
        """Tear down resource monitoring for test case."""
        if self.resource_monitor:
            await self.resource_monitor.stop_monitoring()
            self.resource_monitor.cleanup_resources()
            self.resource_monitor = None
    
    async def run_with_monitoring(self, test_func: Callable, test_name: str, *args, **kwargs):
        """Run a test function with resource monitoring."""
        await self.setup_resource_monitoring()
        
        try:
            async with resource_context(self.resource_monitor, test_name) as ctx:
                result = await test_func(*args, **kwargs)
                
                # Profile the test
                self.profiler.profile_test(test_name, self.resource_monitor)
                
                # Check for violations
                if self.resource_monitor.has_violations():
                    violations = self.resource_monitor.get_violations()
                    print(f"Resource violations in {test_name}: {violations}")
                
                return result
        finally:
            await self.teardown_resource_monitoring()
    
    def get_test_profile(self, test_name: str) -> Dict[str, Any]:
        """Get resource profile for a test."""
        return self.profiler.get_profile_summary(test_name)


def patch_with_resource_tracking(target: str, resource_monitor: ResourceMonitor):
    """
    Patch context manager that tracks resource usage of patched objects.
    
    Args:
        target: The target to patch
        resource_monitor: Resource monitor to track with
    
    Returns:
        Context manager for patching with resource tracking
    """
    def tracking_patch(*args, **kwargs):
        mock_obj = patch(target, *args, **kwargs)
        
        # Track the mock object
        if hasattr(mock_obj, 'start'):
            original_start = mock_obj.start
            
            def tracked_start():
                result = original_start()
                if hasattr(resource_monitor, 'tracker'):
                    resource_monitor.tracker.track_mock_object(result)
                return result
            
            mock_obj.start = tracked_start
        
        return mock_obj
    
    return tracking_patch


@pytest.fixture
def resource_profiler():
    """Fixture to provide resource profiling capabilities."""
    return ResourceProfiler()


@pytest.fixture
def resource_aware_test_case(resource_limits):
    """Fixture to provide resource-aware test case."""
    test_case = ResourceAwareTestCase(resource_limits)
    yield test_case
    
    # Cleanup
    if test_case.resource_monitor:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_case.teardown_resource_monitoring())


class ResourceBenchmark:
    """Benchmark resource usage for performance comparison."""
    
    def __init__(self, name: str, resource_monitor: ResourceMonitor):
        self.name = name
        self.resource_monitor = resource_monitor
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.start_snapshot = None
        self.end_snapshot = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        self.start_snapshot = self.resource_monitor._get_current_snapshot()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.end_snapshot = self.resource_monitor._get_current_snapshot()
    
    def get_benchmark_results(self) -> Dict[str, Any]:
        """Get benchmark results."""
        if not self.start_time or not self.end_time:
            return {}
        
        duration = self.end_time - self.start_time
        
        if not self.start_snapshot or not self.end_snapshot:
            return {'duration': duration}
        
        memory_delta = self.end_snapshot.memory_mb - self.start_snapshot.memory_mb
        task_delta = self.end_snapshot.async_tasks - self.start_snapshot.async_tasks
        
        return {
            'name': self.name,
            'duration': duration,
            'memory_delta_mb': memory_delta,
            'task_delta': task_delta,
            'memory_rate_mb_per_sec': memory_delta / duration if duration > 0 else 0,
            'task_rate_per_sec': task_delta / duration if duration > 0 else 0
        }


def resource_benchmark(name: str, resource_monitor: ResourceMonitor) -> ResourceBenchmark:
    """Create a resource benchmark context manager."""
    return ResourceBenchmark(name, resource_monitor)