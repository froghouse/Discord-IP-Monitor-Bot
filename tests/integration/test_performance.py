"""
Performance tests for Discord IP Monitor Bot.

This module contains comprehensive performance tests for the bot's core functionality
under load conditions, including concurrent operations, cache efficiency, rate limiting,
and database performance.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.async_rate_limiter import AsyncRateLimiter
from ip_monitor.utils.cache import CacheType, IntelligentCache


class TestPerformanceLoadTesting:
    """Test system performance under load conditions."""

    @pytest.fixture
    def performance_config(self, mock_config):
        """Create configuration optimized for performance testing."""
        mock_config.check_interval = 1  # 1 minute for faster testing
        mock_config.max_retries = 3
        mock_config.retry_delay = 1
        mock_config.concurrent_api_checks = True
        mock_config.cache_enabled = True
        mock_config.cache_ttl = 300  # 5 minutes
        mock_config.rate_limit_period = 60
        mock_config.max_checks_per_period = 100  # High limit for load testing

        # Add missing required attributes
        mock_config.db_file = ":memory:"
        mock_config.discord_token = "test_token"
        mock_config.cache_file = "/tmp/test_performance_cache.json"
        mock_config.cache_stale_threshold = 0.8
        mock_config.cache_cleanup_interval = 300

        # Additional config attributes that might be needed
        mock_config.bot_token = "test_token"
        mock_config.ip_file = "/tmp/test_ip.json"
        mock_config.ip_history_file = "/tmp/test_history.json"
        mock_config.circuit_breaker_failure_threshold = 3
        mock_config.circuit_breaker_recovery_timeout = 120
        mock_config.message_queue_batch_size = 5
        mock_config.message_queue_process_interval = 1.0
        mock_config.api_config_file = "/tmp/test_api_config.json"

        return mock_config

    @pytest.fixture
    def performance_ip_service(self, performance_config):
        """Create IP service for performance testing."""
        return IPService(performance_config)

    @pytest.fixture
    def performance_storage(self):
        """Create storage for performance testing."""
        storage = SQLiteIPStorage(":memory:", history_size=10)  # In-memory for performance
        yield storage
        storage.close()

    @pytest.fixture
    def performance_bot(self, performance_config):
        """Create bot for performance testing."""
        bot = IPMonitorBot(config=performance_config)

        # Mock the Discord client
        bot.client = MagicMock()
        bot.client.get_channel.return_value = MagicMock()
        bot.client.get_channel.return_value.send = AsyncMock()

        return bot

    @pytest.mark.asyncio
    async def test_concurrent_ip_checks_performance(self, performance_bot):
        """Test performance of concurrent IP checks."""
        # Mock IP service to return consistent results quickly
        mock_responses = [
            "192.168.1.1",
            "192.168.1.2",
            "192.168.1.3",
            "192.168.1.4",
            "192.168.1.5",
        ]

        with patch.object(
            performance_bot.ip_service, "get_public_ip", side_effect=mock_responses
        ) as mock_get_ip:
            # Measure time for 50 concurrent IP checks
            start_time = time.time()
            tasks = []

            for i in range(50):
                task = asyncio.create_task(performance_bot.ip_service.get_public_ip())
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            execution_time = end_time - start_time

            # Performance assertions
            assert execution_time < 10.0, (
                f"Concurrent IP checks took {execution_time:.2f}s (should be < 10s)"
            )
            assert mock_get_ip.call_count == 50, (
                f"Expected 50 calls, got {mock_get_ip.call_count}"
            )

            # Check that all operations completed successfully
            success_count = sum(1 for task in tasks if not task.exception())
            assert success_count >= 45, f"Only {success_count}/50 operations succeeded"

    @pytest.mark.asyncio
    async def test_high_frequency_ip_monitoring(self, performance_bot):
        """Test high frequency IP monitoring performance."""
        # Mock IP service with varying responses
        ip_responses = [f"192.168.1.{i % 10}" for i in range(100)]

        with patch.object(
            performance_bot.ip_service, "get_public_ip", side_effect=ip_responses
        ) as mock_get_ip:
            # Measure time for 100 IP checks in rapid succession
            start_time = time.time()

            for i in range(100):
                await performance_bot.check_ip_change()
                if i % 10 == 0:  # Brief pause every 10 checks
                    await asyncio.sleep(0.01)

            end_time = time.time()
            execution_time = end_time - start_time

            # Performance assertions
            assert execution_time < 30.0, (
                f"High frequency monitoring took {execution_time:.2f}s (should be < 30s)"
            )
            assert mock_get_ip.call_count == 100, (
                f"Expected 100 calls, got {mock_get_ip.call_count}"
            )

            # Check average time per check
            avg_time_per_check = execution_time / 100
            assert avg_time_per_check < 0.3, (
                f"Average time per check: {avg_time_per_check:.3f}s (should be < 0.3s)"
            )

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_bot):
        """Test memory usage remains stable under load."""
        # Mock IP service to simulate varying load
        with patch.object(
            performance_bot.ip_service, "get_public_ip", return_value="192.168.1.100"
        ) as mock_get_ip:
            # Perform 200 operations to test memory stability
            for batch in range(10):  # 10 batches of 20 operations each
                tasks = []
                for i in range(20):
                    task = asyncio.create_task(performance_bot.check_ip_change())
                    tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

                # Brief pause between batches
                await asyncio.sleep(0.1)

            # Verify all operations completed
            assert mock_get_ip.call_count == 200, (
                f"Expected 200 calls, got {mock_get_ip.call_count}"
            )

            # Check that storage operations completed successfully
            current_ip = performance_bot.storage.load_last_ip()
            assert current_ip == "192.168.1.100", "Storage should contain the last IP"

    @pytest.mark.asyncio
    async def test_error_handling_under_load(self, performance_bot):
        """Test error handling performance under load conditions."""

        # Mock IP service to simulate intermittent failures
        def mock_get_ip_with_failures():
            """Mock that fails 20% of the time."""
            import random

            if random.random() < 0.2:  # 20% failure rate
                raise ConnectionError("Simulated network error")
            return "192.168.1.200"

        with patch.object(
            performance_bot.ip_service,
            "get_public_ip",
            side_effect=mock_get_ip_with_failures,
        ) as mock_get_ip:
            start_time = time.time()

            # Run 100 operations with 20% failure rate
            tasks = []
            for i in range(100):
                task = asyncio.create_task(performance_bot.check_ip_change())
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()

            execution_time = end_time - start_time

            # Performance assertions
            assert execution_time < 60.0, (
                f"Error handling under load took {execution_time:.2f}s (should be < 60s)"
            )
            assert mock_get_ip.call_count == 100, (
                f"Expected 100 calls, got {mock_get_ip.call_count}"
            )

            # Check that most operations completed (allowing for failures)
            success_count = sum(
                1 for result in results if not isinstance(result, Exception)
            )
            assert success_count >= 70, f"Only {success_count}/100 operations succeeded"


class TestPerformanceCacheEfficiency:
    """Test cache performance and efficiency under load."""

    @pytest.fixture
    def cache_instance(self):
        """Create cache instance for performance testing."""
        cache = IntelligentCache(
            cache_file="/tmp/test_cache_performance.json",
            max_memory_size=1000,
        )
        yield cache
        # Cleanup
        cache.clear()

    @pytest.mark.asyncio
    async def test_cache_hit_ratio_performance(self, cache_instance):
        """Test cache hit ratio under high load."""
        # Pre-populate cache with test data
        for i in range(100):
            cache_instance.set(
                "test_namespace", f"key_{i}", f"value_{i}", CacheType.IP_RESULT
            )

        # Perform 1000 get operations with 80% cache hits
        start_time = time.time()
        hit_count = 0
        miss_count = 0

        for i in range(1000):
            key = f"key_{i % 120}"  # 100 keys exist, 20 don't (83% hit rate)
            result = cache_instance.get("test_namespace", key, CacheType.IP_RESULT)

            if result is not None:
                hit_count += 1
            else:
                miss_count += 1

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 1.0, (
            f"Cache operations took {execution_time:.3f}s (should be < 1s)"
        )

        hit_ratio = hit_count / (hit_count + miss_count)
        assert hit_ratio > 0.8, f"Cache hit ratio: {hit_ratio:.2f} (should be > 0.8)"

        # Check average operation time
        avg_time_per_op = execution_time / 1000
        assert avg_time_per_op < 0.001, (
            f"Average time per operation: {avg_time_per_op:.6f}s (should be < 0.001s)"
        )

    @pytest.mark.asyncio
    async def test_cache_concurrent_access_performance(self, cache_instance):
        """Test cache performance under concurrent access."""

        # Define concurrent operations
        async def cache_reader(reader_id: int):
            """Read from cache concurrently."""
            results = []
            for i in range(50):
                key = f"concurrent_key_{i % 10}"
                result = cache_instance.get("concurrent_test", key, CacheType.IP_RESULT)
                results.append(result)
                await asyncio.sleep(0.001)  # Small delay to simulate real usage
            return results

        async def cache_writer(writer_id: int):
            """Write to cache concurrently."""
            for i in range(25):
                key = f"concurrent_key_{i % 10}"
                value = f"writer_{writer_id}_value_{i}"
                cache_instance.set("concurrent_test", key, value, CacheType.IP_RESULT)
                await asyncio.sleep(0.002)  # Small delay to simulate real usage

        # Run concurrent readers and writers
        start_time = time.time()

        tasks = []
        # 5 readers, 3 writers
        for i in range(5):
            tasks.append(asyncio.create_task(cache_reader(i)))
        for i in range(3):
            tasks.append(asyncio.create_task(cache_writer(i)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 5.0, (
            f"Concurrent cache operations took {execution_time:.2f}s (should be < 5s)"
        )

        # Check that all operations completed successfully
        success_count = sum(
            1 for result in results if not isinstance(result, Exception)
        )
        assert success_count == 8, (
            f"Only {success_count}/8 concurrent operations succeeded"
        )

    @pytest.mark.asyncio
    async def test_cache_memory_efficiency(self, cache_instance):
        """Test cache memory usage efficiency."""
        # Fill cache to capacity
        for i in range(1000):
            cache_instance.set(
                "memory_test",
                f"large_key_{i}",
                f"large_value_{i}" * 10,
                CacheType.IP_RESULT,
            )

        # Get initial statistics
        initial_stats = cache_instance.get_statistics()
        initial_memory_usage = initial_stats.get("memory_usage", 0)

        # Perform operations that should trigger eviction
        for i in range(200):
            cache_instance.set(
                "memory_test",
                f"new_key_{i}",
                f"new_value_{i}" * 10,
                CacheType.IP_RESULT,
            )

        # Get final statistics
        final_stats = cache_instance.get_statistics()
        final_memory_usage = final_stats.get("memory_usage", 0)

        # Memory efficiency assertions
        assert final_memory_usage <= 1000, (
            f"Cache exceeded memory limit: {final_memory_usage} entries"
        )
        assert final_stats.get("evictions", 0) > 0, (
            "Cache should have performed evictions"
        )

        # Check that eviction maintained reasonable hit ratio
        hit_ratio = final_stats.get("hit_ratio", 0)
        assert hit_ratio > 0.5, (
            f"Hit ratio after eviction: {hit_ratio:.2f} (should be > 0.5)"
        )

    @pytest.mark.asyncio
    async def test_cache_cleanup_performance(self, cache_instance):
        """Test cache cleanup performance."""
        # Add entries with short TTL
        for i in range(500):
            cache_instance.set(
                "cleanup_test",
                f"short_ttl_key_{i}",
                f"value_{i}",
                CacheType.IP_RESULT,
                ttl=1,
            )

        # Add entries with long TTL
        for i in range(500):
            cache_instance.set(
                "cleanup_test",
                f"long_ttl_key_{i}",
                f"value_{i}",
                CacheType.IP_RESULT,
                ttl=3600,
            )

        # Wait for short TTL entries to expire
        await asyncio.sleep(1.5)

        # Measure cleanup performance
        start_time = time.time()
        cache_instance.cleanup()
        end_time = time.time()

        cleanup_time = end_time - start_time

        # Performance assertions
        assert cleanup_time < 1.0, (
            f"Cache cleanup took {cleanup_time:.3f}s (should be < 1s)"
        )

        # Check that expired entries were removed
        stats = cache_instance.get_statistics()
        remaining_entries = stats.get("memory_usage", 0)
        assert remaining_entries <= 500, (
            f"Too many entries remaining after cleanup: {remaining_entries}"
        )


class TestPerformanceRateLimiting:
    """Test rate limiting performance under high frequency requests."""

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for performance testing."""
        return AsyncRateLimiter(max_calls=100, period=60)  # 100 calls per minute

    @pytest.mark.asyncio
    async def test_rate_limiter_throughput(self, rate_limiter):
        """Test rate limiter throughput under high load."""
        # Test maximum throughput
        start_time = time.time()
        successful_calls = 0

        # Attempt 150 calls (50 more than limit)
        for i in range(150):
            is_limited, wait_time = await rate_limiter.is_limited()
            if not is_limited:
                await rate_limiter.record_call()
                successful_calls += 1

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 5.0, (
            f"Rate limiter check took {execution_time:.2f}s (should be < 5s)"
        )
        assert successful_calls <= 100, (
            f"Rate limiter allowed {successful_calls} calls (should be <= 100)"
        )
        assert successful_calls >= 95, (
            f"Rate limiter allowed only {successful_calls} calls (should be >= 95)"
        )

        # Check average time per operation
        avg_time_per_op = execution_time / 150
        assert avg_time_per_op < 0.05, (
            f"Average time per operation: {avg_time_per_op:.4f}s (should be < 0.05s)"
        )

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrent_access(self, rate_limiter):
        """Test rate limiter performance under concurrent access."""

        async def worker(worker_id: int, calls_per_worker: int):
            """Worker function for concurrent testing."""
            successful = 0
            for i in range(calls_per_worker):
                is_limited, wait_time = await rate_limiter.is_limited()
                if not is_limited:
                    await rate_limiter.record_call()
                    successful += 1
                await asyncio.sleep(0.001)  # Small delay
            return successful

        # Run 10 workers, each making 20 calls
        start_time = time.time()

        tasks = []
        for i in range(10):
            task = asyncio.create_task(worker(i, 20))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        execution_time = end_time - start_time
        total_successful = sum(result for result in results if isinstance(result, int))

        # Performance assertions
        assert execution_time < 10.0, (
            f"Concurrent rate limiting took {execution_time:.2f}s (should be < 10s)"
        )
        assert total_successful <= 100, (
            f"Rate limiter allowed {total_successful} calls (should be <= 100)"
        )
        assert total_successful >= 90, (
            f"Rate limiter allowed only {total_successful} calls (should be >= 90)"
        )

        # Check that all workers completed successfully
        success_count = sum(1 for result in results if isinstance(result, int))
        assert success_count == 10, (
            f"Only {success_count}/10 workers completed successfully"
        )

    @pytest.mark.asyncio
    async def test_rate_limiter_recovery_performance(self, rate_limiter):
        """Test rate limiter recovery performance."""
        # Fill the rate limiter to capacity
        for i in range(100):
            await rate_limiter.record_call()

        # Verify rate limiter is at capacity
        is_limited, wait_time = await rate_limiter.is_limited()
        assert is_limited, "Rate limiter should be at capacity"

        # Measure recovery time (simulate passage of time)
        start_time = time.time()

        # Simulate 30 seconds passing (half the period)
        with patch("time.time", return_value=time.time() + 30):
            # Check if some calls are available
            is_limited, wait_time = await rate_limiter.is_limited()
            remaining_calls = await rate_limiter.get_remaining_calls()

        end_time = time.time()
        check_time = end_time - start_time

        # Performance assertions
        assert check_time < 0.1, (
            f"Recovery check took {check_time:.3f}s (should be < 0.1s)"
        )
        assert remaining_calls > 0, (
            f"Should have some calls available after 30s, got {remaining_calls}"
        )

    @pytest.mark.asyncio
    async def test_rate_limiter_status_performance(self, rate_limiter):
        """Test rate limiter status reporting performance."""
        # Add some calls to the rate limiter
        for i in range(50):
            await rate_limiter.record_call()

        # Measure status reporting performance
        start_time = time.time()

        # Get status 100 times
        for i in range(100):
            status = await rate_limiter.get_status()
            assert isinstance(status, dict), "Status should be a dictionary"
            assert "active_calls" in status, "Status should contain active_calls"
            assert "remaining_calls" in status, "Status should contain remaining_calls"

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 0.5, (
            f"Status reporting took {execution_time:.3f}s (should be < 0.5s)"
        )

        # Check average time per status check
        avg_time_per_status = execution_time / 100
        assert avg_time_per_status < 0.005, (
            f"Average time per status: {avg_time_per_status:.5f}s (should be < 0.005s)"
        )


class TestPerformanceDatabaseOperations:
    """Test database performance under concurrent access."""

    @pytest.fixture
    def performance_storage(self):
        """Create storage for performance testing."""
        storage = SQLiteIPStorage(":memory:", history_size=10)
        yield storage
        storage.close()

    @pytest.mark.asyncio
    async def test_database_concurrent_writes(self, performance_storage):
        """Test database write performance under concurrent access."""

        async def writer_task(writer_id: int, writes_per_task: int):
            """Writer task for concurrent testing."""
            for i in range(writes_per_task):
                ip = f"192.168.{writer_id}.{i}"
                performance_storage.save_current_ip(ip)
                await asyncio.sleep(0.001)  # Small delay
            return writes_per_task

        # Run 5 writers, each performing 20 writes
        start_time = time.time()

        tasks = []
        for i in range(5):
            task = asyncio.create_task(writer_task(i, 20))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        execution_time = end_time - start_time
        total_writes = sum(result for result in results if isinstance(result, int))

        # Performance assertions
        assert execution_time < 5.0, (
            f"Concurrent database writes took {execution_time:.2f}s (should be < 5s)"
        )
        assert total_writes == 100, f"Expected 100 writes, got {total_writes}"

        # Check that all tasks completed successfully
        success_count = sum(1 for result in results if isinstance(result, int))
        assert success_count == 5, (
            f"Only {success_count}/5 writer tasks completed successfully"
        )

        # Verify final state
        current_ip = performance_storage.load_last_ip()
        assert current_ip is not None, "Database should contain a current IP"

    @pytest.mark.asyncio
    async def test_database_concurrent_reads(self, performance_storage):
        """Test database read performance under concurrent access."""
        # Pre-populate database
        for i in range(10):
            performance_storage.save_current_ip(f"192.168.1.{i}")

        async def reader_task(reader_id: int, reads_per_task: int):
            """Reader task for concurrent testing."""
            results = []
            for i in range(reads_per_task):
                current_ip = performance_storage.load_last_ip()
                history = performance_storage.load_ip_history()
                results.append((current_ip, len(history)))
                await asyncio.sleep(0.001)  # Small delay
            return results

        # Run 10 readers, each performing 30 reads
        start_time = time.time()

        tasks = []
        for i in range(10):
            task = asyncio.create_task(reader_task(i, 30))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 10.0, (
            f"Concurrent database reads took {execution_time:.2f}s (should be < 10s)"
        )

        # Check that all tasks completed successfully
        success_count = sum(1 for result in results if isinstance(result, list))
        assert success_count == 10, (
            f"Only {success_count}/10 reader tasks completed successfully"
        )

        # Verify read results
        for result in results:
            if isinstance(result, list):
                assert len(result) == 30, (
                    f"Expected 30 reads per task, got {len(result)}"
                )
                for current_ip, history_count in result:
                    assert current_ip is not None, "Current IP should not be None"
                    assert history_count >= 0, "History count should be non-negative"

    @pytest.mark.asyncio
    async def test_database_mixed_operations_performance(self, performance_storage):
        """Test database performance with mixed read/write operations."""

        async def mixed_operations_task(task_id: int, operations_count: int):
            """Task with mixed read/write operations."""
            operations_completed = 0

            for i in range(operations_count):
                if i % 3 == 0:  # Write operation
                    performance_storage.save_current_ip(f"192.168.{task_id}.{i}")
                elif i % 2 == 0:
                    performance_storage.load_last_ip()
                else:
                    performance_storage.load_ip_history(limit=3)

                operations_completed += 1
                await asyncio.sleep(0.001)  # Small delay

            return operations_completed

        # Run 8 tasks, each performing 25 mixed operations
        start_time = time.time()

        tasks = []
        for i in range(8):
            task = asyncio.create_task(mixed_operations_task(i, 25))
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        execution_time = end_time - start_time
        total_operations = sum(result for result in results if isinstance(result, int))

        # Performance assertions
        assert execution_time < 15.0, (
            f"Mixed database operations took {execution_time:.2f}s (should be < 15s)"
        )
        assert total_operations == 200, (
            f"Expected 200 operations, got {total_operations}"
        )

        # Check that all tasks completed successfully
        success_count = sum(1 for result in results if isinstance(result, int))
        assert success_count == 8, (
            f"Only {success_count}/8 mixed operation tasks completed successfully"
        )

        # Check average time per operation
        avg_time_per_op = execution_time / 200
        assert avg_time_per_op < 0.075, (
            f"Average time per operation: {avg_time_per_op:.4f}s (should be < 0.075s)"
        )

    @pytest.mark.asyncio
    async def test_database_transaction_performance(self, performance_storage):
        """Test database transaction performance."""
        # Test batch operations that should use transactions
        start_time = time.time()

        # Perform 100 IP updates in sequence (should be efficient due to transactions)
        for i in range(100):
            performance_storage.save_current_ip(f"192.168.100.{i}")

        end_time = time.time()
        execution_time = end_time - start_time

        # Performance assertions
        assert execution_time < 10.0, (
            f"Sequential transactions took {execution_time:.2f}s (should be < 10s)"
        )

        # Check average time per transaction
        avg_time_per_transaction = execution_time / 100
        assert avg_time_per_transaction < 0.1, (
            f"Average time per transaction: {avg_time_per_transaction:.4f}s (should be < 0.1s)"
        )

        # Verify final state
        current_ip = performance_storage.load_last_ip()
        assert current_ip == "192.168.100.99", (
            f"Expected final IP 192.168.100.99, got {current_ip}"
        )

        # Check history size
        history = performance_storage.load_ip_history()
        assert len(history) <= 10, (
            f"History should be limited to 10 entries, got {len(history)}"
        )
