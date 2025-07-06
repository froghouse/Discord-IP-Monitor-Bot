"""Performance testing utilities for the IP Monitor Bot.

This module provides utilities for measuring and analyzing performance
of various bot components including:
- IP API response times
- Database operations
- Cache hit/miss rates
- Message queue throughput
- Circuit breaker behavior
- Rate limiter effectiveness
"""

import asyncio
import logging
import statistics
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""

    operation_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    total_duration: float
    average_duration: float
    min_duration: float
    max_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    operations_per_second: float
    success_rate: float
    error_rate: float
    durations: list[float]
    errors: list[Exception]

    def __str__(self) -> str:
        return (
            f"Performance Metrics for {self.operation_name}:\n"
            f"  Total Operations: {self.total_operations}\n"
            f"  Success Rate: {self.success_rate:.2%}\n"
            f"  Operations/Second: {self.operations_per_second:.2f}\n"
            f"  Average Duration: {self.average_duration:.3f}s\n"
            f"  Median Duration: {self.median_duration:.3f}s\n"
            f"  95th Percentile: {self.p95_duration:.3f}s\n"
            f"  99th Percentile: {self.p99_duration:.3f}s\n"
            f"  Min/Max Duration: {self.min_duration:.3f}s / {self.max_duration:.3f}s"
        )


class PerformanceTimer:
    """Context manager for measuring operation performance."""

    def __init__(self, operation_name: str = "operation"):
        self.operation_name = operation_name
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.duration: float | None = None
        self.logger = logging.getLogger(__name__)

    def __enter__(self) -> "PerformanceTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time

        if exc_type is None:
            self.logger.debug(
                f"{self.operation_name} completed in {self.duration:.3f}s"
            )
        else:
            self.logger.debug(
                f"{self.operation_name} failed after {self.duration:.3f}s: {exc_val}"
            )

    @asynccontextmanager
    async def async_timer(self):
        """Async context manager version."""
        self.start_time = time.perf_counter()
        try:
            yield self
        finally:
            self.end_time = time.perf_counter()
            self.duration = self.end_time - self.start_time


class PerformanceBenchmark:
    """Advanced performance benchmarking utility."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.durations: list[float] = []
        self.errors: list[Exception] = []
        self.successful_operations = 0
        self.failed_operations = 0
        self.logger = logging.getLogger(__name__)

    async def benchmark_async_operation(
        self,
        operation: Callable[..., Any],
        iterations: int = 100,
        concurrent_operations: int = 1,
        *args,
        **kwargs,
    ) -> PerformanceMetrics:
        """Benchmark an async operation with configurable concurrency."""

        self.logger.info(f"Starting benchmark: {self.operation_name}")
        self.logger.info(
            f"Iterations: {iterations}, Concurrency: {concurrent_operations}"
        )

        start_time = time.perf_counter()

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrent_operations)

        async def run_single_operation():
            async with semaphore:
                timer = PerformanceTimer(f"{self.operation_name}_single")
                try:
                    async with timer.async_timer():
                        await operation(*args, **kwargs)

                    self.durations.append(timer.duration)
                    self.successful_operations += 1

                except Exception as e:
                    self.errors.append(e)
                    self.failed_operations += 1
                    if timer.duration:
                        self.durations.append(timer.duration)

        # Run all operations concurrently
        tasks = [run_single_operation() for _ in range(iterations)]
        await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.perf_counter() - start_time

        return self._calculate_metrics(total_duration)

    def benchmark_sync_operation(
        self, operation: Callable[..., Any], iterations: int = 100, *args, **kwargs
    ) -> PerformanceMetrics:
        """Benchmark a synchronous operation."""

        self.logger.info(f"Starting sync benchmark: {self.operation_name}")
        self.logger.info(f"Iterations: {iterations}")

        start_time = time.perf_counter()

        for _ in range(iterations):
            with PerformanceTimer(f"{self.operation_name}_single") as timer:
                try:
                    operation(*args, **kwargs)
                    self.successful_operations += 1
                except Exception as e:
                    self.errors.append(e)
                    self.failed_operations += 1
                finally:
                    if timer.duration:
                        self.durations.append(timer.duration)

        total_duration = time.perf_counter() - start_time

        return self._calculate_metrics(total_duration)

    def _calculate_metrics(self, total_duration: float) -> PerformanceMetrics:
        """Calculate performance metrics from collected data."""

        total_operations = self.successful_operations + self.failed_operations

        if not self.durations:
            # Handle case where no operations completed
            return PerformanceMetrics(
                operation_name=self.operation_name,
                total_operations=total_operations,
                successful_operations=self.successful_operations,
                failed_operations=self.failed_operations,
                total_duration=total_duration,
                average_duration=0.0,
                min_duration=0.0,
                max_duration=0.0,
                median_duration=0.0,
                p95_duration=0.0,
                p99_duration=0.0,
                operations_per_second=0.0,
                success_rate=0.0,
                error_rate=1.0,
                durations=self.durations,
                errors=self.errors,
            )

        # Calculate statistics
        average_duration = statistics.mean(self.durations)
        min_duration = min(self.durations)
        max_duration = max(self.durations)
        median_duration = statistics.median(self.durations)

        # Calculate percentiles
        sorted_durations = sorted(self.durations)
        p95_duration = sorted_durations[int(len(sorted_durations) * 0.95)]
        p99_duration = sorted_durations[int(len(sorted_durations) * 0.99)]

        # Calculate rates
        operations_per_second = (
            total_operations / total_duration if total_duration > 0 else 0
        )
        success_rate = (
            self.successful_operations / total_operations if total_operations > 0 else 0
        )
        error_rate = (
            self.failed_operations / total_operations if total_operations > 0 else 0
        )

        return PerformanceMetrics(
            operation_name=self.operation_name,
            total_operations=total_operations,
            successful_operations=self.successful_operations,
            failed_operations=self.failed_operations,
            total_duration=total_duration,
            average_duration=average_duration,
            min_duration=min_duration,
            max_duration=max_duration,
            median_duration=median_duration,
            p95_duration=p95_duration,
            p99_duration=p99_duration,
            operations_per_second=operations_per_second,
            success_rate=success_rate,
            error_rate=error_rate,
            durations=self.durations,
            errors=self.errors,
        )


class LoadTestScenario:
    """Defines a load testing scenario with ramp-up and sustained load."""

    def __init__(
        self,
        name: str,
        operation: Callable[..., Any],
        ramp_up_duration: float = 10.0,
        sustained_duration: float = 30.0,
        max_concurrent_users: int = 10,
        target_ops_per_second: float | None = None,
    ):
        self.name = name
        self.operation = operation
        self.ramp_up_duration = ramp_up_duration
        self.sustained_duration = sustained_duration
        self.max_concurrent_users = max_concurrent_users
        self.target_ops_per_second = target_ops_per_second
        self.logger = logging.getLogger(__name__)

    async def run_load_test(self, *args, **kwargs) -> dict[str, PerformanceMetrics]:
        """Run a complete load test scenario."""

        self.logger.info(f"Starting load test: {self.name}")
        self.logger.info(
            f"Ramp-up: {self.ramp_up_duration}s, Sustained: {self.sustained_duration}s"
        )
        self.logger.info(f"Max concurrent users: {self.max_concurrent_users}")

        results = {}

        # Ramp-up phase
        ramp_up_benchmark = PerformanceBenchmark(f"{self.name}_ramp_up")
        ramp_up_iterations = int(
            self.ramp_up_duration * (self.target_ops_per_second or 1)
        )

        results["ramp_up"] = await ramp_up_benchmark.benchmark_async_operation(
            self.operation,
            iterations=ramp_up_iterations,
            concurrent_operations=self.max_concurrent_users // 2,
            *args,
            **kwargs,
        )

        # Sustained load phase
        sustained_benchmark = PerformanceBenchmark(f"{self.name}_sustained")
        sustained_iterations = int(
            self.sustained_duration * (self.target_ops_per_second or 1)
        )

        results["sustained"] = await sustained_benchmark.benchmark_async_operation(
            self.operation,
            iterations=sustained_iterations,
            concurrent_operations=self.max_concurrent_users,
            *args,
            **kwargs,
        )

        self.logger.info(f"Load test completed: {self.name}")
        return results


class MemoryProfiler:
    """Simple memory profiling for performance tests."""

    def __init__(self):
        self.initial_memory = 0
        self.peak_memory = 0
        self.final_memory = 0
        self.memory_samples = []
        self.logger = logging.getLogger(__name__)

    def start_profiling(self):
        """Start memory profiling."""
        try:
            import psutil

            process = psutil.Process()
            self.initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = self.initial_memory
            self.logger.info(
                f"Memory profiling started. Initial memory: {self.initial_memory:.2f} MB"
            )
        except ImportError:
            self.logger.warning("psutil not available, memory profiling disabled")

    def sample_memory(self):
        """Take a memory sample."""
        try:
            import psutil

            process = psutil.Process()
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            self.memory_samples.append(current_memory)
            self.peak_memory = max(self.peak_memory, current_memory)
        except ImportError:
            pass

    def stop_profiling(self) -> dict[str, float]:
        """Stop profiling and return memory statistics."""
        try:
            import psutil

            process = psutil.Process()
            self.final_memory = process.memory_info().rss / 1024 / 1024  # MB

            memory_stats = {
                "initial_memory_mb": self.initial_memory,
                "final_memory_mb": self.final_memory,
                "peak_memory_mb": self.peak_memory,
                "memory_increase_mb": self.final_memory - self.initial_memory,
                "peak_increase_mb": self.peak_memory - self.initial_memory,
                "average_memory_mb": statistics.mean(self.memory_samples)
                if self.memory_samples
                else 0,
            }

            self.logger.info(
                f"Memory profiling completed. Peak memory: {self.peak_memory:.2f} MB"
            )
            return memory_stats

        except ImportError:
            self.logger.warning("psutil not available, returning empty memory stats")
            return {}


async def benchmark_ip_api_performance(
    ip_service, iterations: int = 50, concurrent_requests: int = 5
) -> PerformanceMetrics:
    """Benchmark IP API performance with realistic load."""

    benchmark = PerformanceBenchmark("IP_API_Performance")

    async def single_ip_check():
        """Single IP check operation."""
        return await ip_service.get_current_ip()

    return await benchmark.benchmark_async_operation(
        single_ip_check,
        iterations=iterations,
        concurrent_operations=concurrent_requests,
    )


async def benchmark_database_performance(
    storage, iterations: int = 100, concurrent_operations: int = 10
) -> dict[str, PerformanceMetrics]:
    """Benchmark database operations performance."""

    results = {}

    # Benchmark IP retrieval
    read_benchmark = PerformanceBenchmark("Database_Read")
    results["read"] = await read_benchmark.benchmark_async_operation(
        lambda: storage.get_current_ip(),
        iterations=iterations,
        concurrent_operations=concurrent_operations,
    )

    # Benchmark IP storage
    write_benchmark = PerformanceBenchmark("Database_Write")
    results["write"] = await write_benchmark.benchmark_async_operation(
        lambda: storage.save_current_ip("192.168.1.100"),
        iterations=iterations,
        concurrent_operations=concurrent_operations,
    )

    # Benchmark history retrieval
    history_benchmark = PerformanceBenchmark("Database_History")
    results["history"] = await history_benchmark.benchmark_async_operation(
        lambda: storage.get_ip_history(),
        iterations=iterations,
        concurrent_operations=concurrent_operations,
    )

    return results


async def benchmark_cache_performance(
    cache, iterations: int = 1000, concurrent_operations: int = 20
) -> dict[str, PerformanceMetrics]:
    """Benchmark cache performance."""

    results = {}

    # Benchmark cache writes
    write_benchmark = PerformanceBenchmark("Cache_Write")
    results["write"] = await write_benchmark.benchmark_async_operation(
        lambda: cache.set("test_namespace", "test_key", "test_value"),
        iterations=iterations,
        concurrent_operations=concurrent_operations,
    )

    # Benchmark cache reads (should be much faster)
    read_benchmark = PerformanceBenchmark("Cache_Read")
    results["read"] = await read_benchmark.benchmark_async_operation(
        lambda: cache.get("test_namespace", "test_key"),
        iterations=iterations,
        concurrent_operations=concurrent_operations,
    )

    return results


class PerformanceTestSuite:
    """Complete performance test suite for the IP Monitor Bot."""

    def __init__(self, ip_service, storage, cache, message_queue):
        self.ip_service = ip_service
        self.storage = storage
        self.cache = cache
        self.message_queue = message_queue
        self.logger = logging.getLogger(__name__)

    async def run_complete_suite(self) -> dict[str, Any]:
        """Run all performance tests and return comprehensive results."""

        self.logger.info("Starting complete performance test suite")

        results = {
            "test_timestamp": time.time(),
            "test_duration": 0,
            "memory_profile": {},
            "performance_metrics": {},
        }

        # Start memory profiling
        profiler = MemoryProfiler()
        profiler.start_profiling()

        suite_start_time = time.perf_counter()

        try:
            # IP API Performance Tests
            self.logger.info("Running IP API performance tests")
            results["performance_metrics"][
                "ip_api"
            ] = await benchmark_ip_api_performance(
                self.ip_service, iterations=25, concurrent_requests=3
            )
            profiler.sample_memory()

            # Database Performance Tests
            self.logger.info("Running database performance tests")
            results["performance_metrics"][
                "database"
            ] = await benchmark_database_performance(
                self.storage, iterations=50, concurrent_operations=5
            )
            profiler.sample_memory()

            # Cache Performance Tests
            self.logger.info("Running cache performance tests")
            results["performance_metrics"]["cache"] = await benchmark_cache_performance(
                self.cache, iterations=500, concurrent_operations=10
            )
            profiler.sample_memory()

        except Exception as e:
            self.logger.error(f"Performance test suite failed: {e}")
            results["error"] = str(e)

        finally:
            # Stop profiling and calculate final metrics
            results["test_duration"] = time.perf_counter() - suite_start_time
            results["memory_profile"] = profiler.stop_profiling()

            self.logger.info(
                f"Performance test suite completed in {results['test_duration']:.2f}s"
            )

        return results

    def generate_performance_report(self, results: dict[str, Any]) -> str:
        """Generate a human-readable performance report."""

        report = ["=" * 60]
        report.append("IP MONITOR BOT PERFORMANCE REPORT")
        report.append("=" * 60)
        report.append(f"Test Duration: {results['test_duration']:.2f}s")
        report.append(f"Test Timestamp: {time.ctime(results['test_timestamp'])}")
        report.append("")

        # Memory profile
        if results.get("memory_profile"):
            memory = results["memory_profile"]
            report.append("MEMORY PROFILE:")
            report.append(
                f"  Initial Memory: {memory.get('initial_memory_mb', 0):.2f} MB"
            )
            report.append(f"  Peak Memory: {memory.get('peak_memory_mb', 0):.2f} MB")
            report.append(f"  Final Memory: {memory.get('final_memory_mb', 0):.2f} MB")
            report.append(
                f"  Memory Increase: {memory.get('memory_increase_mb', 0):.2f} MB"
            )
            report.append("")

        # Performance metrics
        if results.get("performance_metrics"):
            for category, metrics in results["performance_metrics"].items():
                report.append(f"{category.upper()} PERFORMANCE:")

                if isinstance(metrics, dict):
                    # Multiple metrics in category
                    for subcategory, metric in metrics.items():
                        report.append(f"  {subcategory}:")
                        report.extend(
                            [f"    {line}" for line in str(metric).split("\n")]
                        )
                else:
                    # Single metric
                    report.extend([f"  {line}" for line in str(metrics).split("\n")])

                report.append("")

        if results.get("error"):
            report.append(f"ERROR: {results['error']}")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)
