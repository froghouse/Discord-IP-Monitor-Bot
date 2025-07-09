"""
Timeout helpers for integration tests.

This module provides standardized timeout utilities for different types of operations
to prevent hanging tests while maintaining reasonable timeouts for each operation type.
"""

import asyncio
import functools
import time
from typing import Any, Awaitable, Callable, Optional, TypeVar

import pytest

T = TypeVar("T")


class TimeoutConfig:
    """Standardized timeout configurations for different operation types."""
    
    # Admin command operations
    ADMIN_COMMAND = 5.0
    
    # Network operations
    IP_CHECK = 30.0
    HTTP_REQUEST = 10.0
    DISCORD_API = 10.0
    
    # Database operations
    DATABASE = 10.0
    
    # Complex workflows
    WORKFLOW = 15.0
    
    # Concurrent operations
    CONCURRENT_LIGHT = 15.0  # 5 or fewer concurrent operations
    CONCURRENT_HEAVY = 30.0  # More than 5 concurrent operations
    
    # Message queue operations
    MESSAGE_QUEUE = 5.0
    
    # Cache operations
    CACHE = 5.0


async def with_timeout(
    operation: Awaitable[T],
    timeout: float,
    operation_name: Optional[str] = None,
) -> T:
    """
    Execute an async operation with timeout and enhanced error reporting.
    
    Args:
        operation: The async operation to execute
        timeout: Timeout in seconds
        operation_name: Optional name for better error reporting
    
    Returns:
        The result of the operation
    
    Raises:
        pytest.fail: If the operation times out with diagnostic information
    """
    start_time = time.time()
    
    try:
        return await asyncio.wait_for(operation, timeout=timeout)
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        name = operation_name or "async operation"
        pytest.fail(
            f"{name} timed out after {elapsed:.1f}s (limit: {timeout:.1f}s). "
            f"This may indicate a hanging async operation or insufficient timeout."
        )


async def with_admin_timeout(operation: Awaitable[T], name: str = "Admin command") -> T:
    """Execute admin command with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.ADMIN_COMMAND, name)


async def with_ip_timeout(operation: Awaitable[T], name: str = "IP check") -> T:
    """Execute IP check operation with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.IP_CHECK, name)


async def with_http_timeout(operation: Awaitable[T], name: str = "HTTP request") -> T:
    """Execute HTTP request with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.HTTP_REQUEST, name)


async def with_discord_timeout(operation: Awaitable[T], name: str = "Discord API") -> T:
    """Execute Discord API operation with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.DISCORD_API, name)


async def with_database_timeout(operation: Awaitable[T], name: str = "Database operation") -> T:
    """Execute database operation with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.DATABASE, name)


async def with_workflow_timeout(operation: Awaitable[T], name: str = "Workflow") -> T:
    """Execute complex workflow with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.WORKFLOW, name)


async def with_concurrent_timeout(
    operation: Awaitable[T], 
    count: int, 
    name: str = "Concurrent operations"
) -> T:
    """
    Execute concurrent operations with appropriate timeout based on count.
    
    Args:
        operation: The async operation to execute
        count: Number of concurrent operations
        name: Operation name for error reporting
    
    Returns:
        The result of the operation
    """
    timeout = TimeoutConfig.CONCURRENT_HEAVY if count > 5 else TimeoutConfig.CONCURRENT_LIGHT
    return await with_timeout(operation, timeout, f"{name} (count: {count})")


async def with_message_queue_timeout(operation: Awaitable[T], name: str = "Message queue") -> T:
    """Execute message queue operation with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.MESSAGE_QUEUE, name)


async def with_cache_timeout(operation: Awaitable[T], name: str = "Cache operation") -> T:
    """Execute cache operation with standardized timeout."""
    return await with_timeout(operation, TimeoutConfig.CACHE, name)


def timeout_wrapper(timeout: float, operation_name: Optional[str] = None):
    """
    Decorator to add timeout protection to async test methods.
    
    Args:
        timeout: Timeout in seconds
        operation_name: Optional name for error reporting
    
    Returns:
        Decorated function with timeout protection
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            name = operation_name or func.__name__
            return await with_timeout(func(*args, **kwargs), timeout, name)
        return wrapper
    return decorator


# Common timeout decorators for test methods
admin_timeout = timeout_wrapper(TimeoutConfig.ADMIN_COMMAND, "Admin command test")
ip_timeout = timeout_wrapper(TimeoutConfig.IP_CHECK, "IP check test")
http_timeout = timeout_wrapper(TimeoutConfig.HTTP_REQUEST, "HTTP request test")
discord_timeout = timeout_wrapper(TimeoutConfig.DISCORD_API, "Discord API test")
database_timeout = timeout_wrapper(TimeoutConfig.DATABASE, "Database test")
workflow_timeout = timeout_wrapper(TimeoutConfig.WORKFLOW, "Workflow test")


class TimeoutTracker:
    """Track timeout statistics for test analysis."""
    
    def __init__(self):
        self.operations = []
        self.timeouts = []
        self.successes = []
    
    def record_operation(self, name: str, duration: float, timeout: float, success: bool):
        """Record an operation for analysis."""
        self.operations.append({
            'name': name,
            'duration': duration,
            'timeout': timeout,
            'success': success,
            'utilization': (duration / timeout) * 100
        })
        
        if success:
            self.successes.append(duration)
        else:
            self.timeouts.append(duration)
    
    def get_stats(self) -> dict:
        """Get timeout statistics."""
        if not self.operations:
            return {'total': 0, 'timeouts': 0, 'avg_duration': 0, 'avg_utilization': 0}
        
        total = len(self.operations)
        timeout_count = len(self.timeouts)
        avg_duration = sum(op['duration'] for op in self.operations) / total
        avg_utilization = sum(op['utilization'] for op in self.operations) / total
        
        return {
            'total': total,
            'timeouts': timeout_count,
            'success_rate': ((total - timeout_count) / total) * 100,
            'avg_duration': avg_duration,
            'avg_utilization': avg_utilization,
            'operations': self.operations
        }


# Global timeout tracker instance
timeout_tracker = TimeoutTracker()


@pytest.fixture
def timeout_stats():
    """Fixture to provide timeout statistics tracking."""
    return timeout_tracker