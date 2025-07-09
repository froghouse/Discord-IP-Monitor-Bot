"""
Resource monitoring utilities for integration tests.

This module provides comprehensive resource monitoring and tracking capabilities
to detect resource leaks, enforce usage limits, and provide detailed diagnostics
for test failures.
"""

import asyncio
import gc
import os
import psutil
import sqlite3
import threading
import time
import weakref
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from unittest.mock import Mock

import pytest


@dataclass
class ResourceSnapshot:
    """Snapshot of resource usage at a specific point in time."""
    
    timestamp: float
    memory_mb: float
    cpu_percent: float
    open_files: int
    threads: int
    database_connections: int
    http_connections: int
    mock_objects: int
    async_tasks: int
    
    def __post_init__(self):
        """Initialize computed fields."""
        pass


@dataclass
class ResourceLimits:
    """Resource usage limits for tests."""
    
    memory_mb: float = 100.0  # Maximum memory usage in MB
    open_files: int = 50      # Maximum open file descriptors
    threads: int = 20         # Maximum thread count
    database_connections: int = 10  # Maximum database connections
    http_connections: int = 20      # Maximum HTTP connections
    mock_objects: int = 100         # Maximum mock objects
    async_tasks: int = 50          # Maximum async tasks
    
    def check_limits(self, snapshot: ResourceSnapshot) -> List[str]:
        """Check if resource snapshot exceeds limits."""
        violations = []
        
        if snapshot.memory_mb > self.memory_mb:
            violations.append(f"Memory usage ({snapshot.memory_mb:.1f}MB) exceeds limit ({self.memory_mb:.1f}MB)")
        
        if snapshot.open_files > self.open_files:
            violations.append(f"Open files ({snapshot.open_files}) exceeds limit ({self.open_files})")
        
        if snapshot.threads > self.threads:
            violations.append(f"Thread count ({snapshot.threads}) exceeds limit ({self.threads})")
        
        if snapshot.database_connections > self.database_connections:
            violations.append(f"Database connections ({snapshot.database_connections}) exceeds limit ({self.database_connections})")
        
        if snapshot.http_connections > self.http_connections:
            violations.append(f"HTTP connections ({snapshot.http_connections}) exceeds limit ({self.http_connections})")
        
        if snapshot.mock_objects > self.mock_objects:
            violations.append(f"Mock objects ({snapshot.mock_objects}) exceeds limit ({self.mock_objects})")
        
        if snapshot.async_tasks > self.async_tasks:
            violations.append(f"Async tasks ({snapshot.async_tasks}) exceeds limit ({self.async_tasks})")
        
        return violations


class ResourceTracker:
    """Track specific resource types during test execution."""
    
    def __init__(self):
        self._database_connections: Set[weakref.ref] = set()
        self._http_connections: Set[weakref.ref] = set()
        self._mock_objects: Set[weakref.ref] = set()
        self._async_tasks: Set[weakref.ref] = set()
        self._lock = threading.Lock()
    
    def track_database_connection(self, connection: sqlite3.Connection):
        """Track a database connection."""
        with self._lock:
            self._database_connections.add(weakref.ref(connection))
    
    def track_http_connection(self, connection: Any):
        """Track an HTTP connection."""
        with self._lock:
            self._http_connections.add(weakref.ref(connection))
    
    def track_mock_object(self, mock: Mock):
        """Track a mock object."""
        with self._lock:
            self._mock_objects.add(weakref.ref(mock))
    
    def track_async_task(self, task: asyncio.Task):
        """Track an async task."""
        with self._lock:
            self._async_tasks.add(weakref.ref(task))
    
    def get_active_counts(self) -> Dict[str, int]:
        """Get current active resource counts."""
        with self._lock:
            # Clean up dead references
            self._database_connections = {ref for ref in self._database_connections if ref() is not None}
            self._http_connections = {ref for ref in self._http_connections if ref() is not None}
            self._mock_objects = {ref for ref in self._mock_objects if ref() is not None}
            self._async_tasks = {ref for ref in self._async_tasks if ref() is not None}
            
            return {
                'database_connections': len(self._database_connections),
                'http_connections': len(self._http_connections),
                'mock_objects': len(self._mock_objects),
                'async_tasks': len(self._async_tasks)
            }
    
    def cleanup_all(self):
        """Clean up all tracked resources."""
        with self._lock:
            # Cancel async tasks
            for task_ref in self._async_tasks:
                task = task_ref()
                if task and not task.done():
                    task.cancel()
            
            # Clear all references
            self._database_connections.clear()
            self._http_connections.clear()
            self._mock_objects.clear()
            self._async_tasks.clear()


class ResourceMonitor:
    """Monitor and track resource usage during tests."""
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self.tracker = ResourceTracker()
        self.snapshots: List[ResourceSnapshot] = []
        self.violations: List[str] = []
        self.start_snapshot: Optional[ResourceSnapshot] = None
        self.process = psutil.Process()
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def _get_current_snapshot(self) -> ResourceSnapshot:
        """Get current resource usage snapshot."""
        try:
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            cpu_percent = self.process.cpu_percent()
            open_files = len(self.process.open_files())
            threads = self.process.num_threads()
            
            active_counts = self.tracker.get_active_counts()
            
            # Count current async tasks
            try:
                current_tasks = len([task for task in asyncio.all_tasks() if not task.done()])
            except RuntimeError:
                current_tasks = 0
            
            return ResourceSnapshot(
                timestamp=time.time(),
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                open_files=open_files,
                threads=threads,
                database_connections=active_counts['database_connections'],
                http_connections=active_counts['http_connections'],
                mock_objects=active_counts['mock_objects'],
                async_tasks=current_tasks
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Return empty snapshot if process monitoring fails
            return ResourceSnapshot(
                timestamp=time.time(),
                memory_mb=0.0,
                cpu_percent=0.0,
                open_files=0,
                threads=0,
                database_connections=0,
                http_connections=0,
                mock_objects=0,
                async_tasks=0
            )
    
    async def start_monitoring(self, interval: float = 0.5):
        """Start continuous resource monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self.start_snapshot = self._get_current_snapshot()
        self.snapshots.clear()
        self.violations.clear()
        
        async def monitor_loop():
            while self._monitoring:
                try:
                    snapshot = self._get_current_snapshot()
                    
                    async with self._lock:
                        self.snapshots.append(snapshot)
                        
                        # Check for limit violations
                        violations = self.limits.check_limits(snapshot)
                        if violations:
                            self.violations.extend(violations)
                            
                            # Log violations for debugging
                            for violation in violations:
                                print(f"Resource violation: {violation}")
                    
                    await asyncio.sleep(interval)
                except Exception as e:
                    print(f"Resource monitoring error: {e}")
                    await asyncio.sleep(interval)
        
        self._monitor_task = asyncio.create_task(monitor_loop())
    
    async def stop_monitoring(self):
        """Stop resource monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    def get_peak_usage(self) -> ResourceSnapshot:
        """Get peak resource usage from monitoring period."""
        if not self.snapshots:
            return self._get_current_snapshot()
        
        # Find peak values across all snapshots
        peak_memory = max(s.memory_mb for s in self.snapshots)
        peak_cpu = max(s.cpu_percent for s in self.snapshots)
        peak_files = max(s.open_files for s in self.snapshots)
        peak_threads = max(s.threads for s in self.snapshots)
        peak_db_conn = max(s.database_connections for s in self.snapshots)
        peak_http_conn = max(s.http_connections for s in self.snapshots)
        peak_mocks = max(s.mock_objects for s in self.snapshots)
        peak_tasks = max(s.async_tasks for s in self.snapshots)
        
        return ResourceSnapshot(
            timestamp=time.time(),
            memory_mb=peak_memory,
            cpu_percent=peak_cpu,
            open_files=peak_files,
            threads=peak_threads,
            database_connections=peak_db_conn,
            http_connections=peak_http_conn,
            mock_objects=peak_mocks,
            async_tasks=peak_tasks
        )
    
    def get_resource_diff(self) -> Dict[str, float]:
        """Get difference between current and start snapshot."""
        if not self.start_snapshot:
            return {}
        
        current = self._get_current_snapshot()
        
        return {
            'memory_mb': current.memory_mb - self.start_snapshot.memory_mb,
            'cpu_percent': current.cpu_percent - self.start_snapshot.cpu_percent,
            'open_files': current.open_files - self.start_snapshot.open_files,
            'threads': current.threads - self.start_snapshot.threads,
            'database_connections': current.database_connections - self.start_snapshot.database_connections,
            'http_connections': current.http_connections - self.start_snapshot.http_connections,
            'mock_objects': current.mock_objects - self.start_snapshot.mock_objects,
            'async_tasks': current.async_tasks - self.start_snapshot.async_tasks
        }
    
    def has_violations(self) -> bool:
        """Check if any resource violations occurred."""
        return bool(self.violations)
    
    def get_violations(self) -> List[str]:
        """Get all resource violations."""
        return self.violations.copy()
    
    def cleanup_resources(self):
        """Clean up tracked resources."""
        self.tracker.cleanup_all()
        gc.collect()  # Force garbage collection
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive resource usage report."""
        current = self._get_current_snapshot()
        peak = self.get_peak_usage()
        diff = self.get_resource_diff()
        
        return {
            'start_snapshot': self.start_snapshot.__dict__ if self.start_snapshot else None,
            'current_snapshot': current.__dict__,
            'peak_usage': peak.__dict__,
            'resource_diff': diff,
            'violations': self.violations,
            'snapshot_count': len(self.snapshots),
            'monitoring_duration': current.timestamp - (self.start_snapshot.timestamp if self.start_snapshot else current.timestamp)
        }


class ResourceExhaustionError(Exception):
    """Raised when resource usage exceeds configured limits."""
    
    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Resource exhaustion detected: {', '.join(violations)}")


@pytest.fixture
def resource_monitor(request):
    """Fixture to provide resource monitoring for tests."""
    # Create monitor with test-specific limits if configured
    limits = getattr(request, 'param', None)
    if limits is None:
        limits = ResourceLimits()
    
    monitor = ResourceMonitor(limits)
    
    # Start monitoring
    loop = asyncio.get_event_loop()
    loop.run_until_complete(monitor.start_monitoring())
    
    yield monitor
    
    # Stop monitoring and cleanup
    loop.run_until_complete(monitor.stop_monitoring())
    monitor.cleanup_resources()
    
    # Check for violations and report
    if monitor.has_violations():
        violations = monitor.get_violations()
        report = monitor.get_report()
        
        # Log resource report for debugging
        print(f"\nResource usage report for {request.node.name}:")
        print(f"Peak memory: {report['peak_usage']['memory_mb']:.1f}MB")
        print(f"Peak database connections: {report['peak_usage']['database_connections']}")
        print(f"Peak HTTP connections: {report['peak_usage']['http_connections']}")
        print(f"Peak async tasks: {report['peak_usage']['async_tasks']}")
        print(f"Violations: {violations}")
        
        # Fail test if violations occurred
        pytest.fail(f"Resource usage violations: {', '.join(violations)}")


@pytest.fixture
def resource_tracker():
    """Fixture to provide resource tracking capabilities."""
    tracker = ResourceTracker()
    yield tracker
    tracker.cleanup_all()


class ResourceContextManager:
    """Context manager for resource monitoring within specific operations."""
    
    def __init__(self, monitor: ResourceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_snapshot: Optional[ResourceSnapshot] = None
        self.end_snapshot: Optional[ResourceSnapshot] = None
    
    async def __aenter__(self):
        self.start_snapshot = self.monitor._get_current_snapshot()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.end_snapshot = self.monitor._get_current_snapshot()
        
        # Check for violations during this operation
        if self.start_snapshot and self.end_snapshot:
            violations = self.monitor.limits.check_limits(self.end_snapshot)
            if violations:
                raise ResourceExhaustionError(violations)
    
    def get_resource_usage(self) -> Dict[str, float]:
        """Get resource usage during this operation."""
        if not self.start_snapshot or not self.end_snapshot:
            return {}
        
        return {
            'memory_mb': self.end_snapshot.memory_mb - self.start_snapshot.memory_mb,
            'cpu_percent': self.end_snapshot.cpu_percent - self.start_snapshot.cpu_percent,
            'open_files': self.end_snapshot.open_files - self.start_snapshot.open_files,
            'threads': self.end_snapshot.threads - self.start_snapshot.threads,
            'database_connections': self.end_snapshot.database_connections - self.start_snapshot.database_connections,
            'http_connections': self.end_snapshot.http_connections - self.start_snapshot.http_connections,
            'mock_objects': self.end_snapshot.mock_objects - self.start_snapshot.mock_objects,
            'async_tasks': self.end_snapshot.async_tasks - self.start_snapshot.async_tasks
        }


def resource_context(monitor: ResourceMonitor, operation_name: str) -> ResourceContextManager:
    """Create a resource monitoring context manager."""
    return ResourceContextManager(monitor, operation_name)


# Global resource tracker instance
global_resource_tracker = ResourceTracker()


def track_database_connection(connection: sqlite3.Connection):
    """Track a database connection globally."""
    global_resource_tracker.track_database_connection(connection)


def track_http_connection(connection: Any):
    """Track an HTTP connection globally."""
    global_resource_tracker.track_http_connection(connection)


def track_mock_object(mock: Mock):
    """Track a mock object globally."""
    global_resource_tracker.track_mock_object(mock)


def track_async_task(task: asyncio.Task):
    """Track an async task globally."""
    global_resource_tracker.track_async_task(task)


def get_global_resource_counts() -> Dict[str, int]:
    """Get global resource counts."""
    return global_resource_tracker.get_active_counts()


def cleanup_global_resources():
    """Clean up all global resources."""
    global_resource_tracker.cleanup_all()