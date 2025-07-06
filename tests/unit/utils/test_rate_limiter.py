"""
Test suite for the legacy thread-based RateLimiter class.

This module provides comprehensive testing for the thread-safe rate limiting
functionality used in the IP Monitor Bot.
"""

import pytest
import threading
import time
from unittest.mock import patch

from ip_monitor.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test suite for RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        return RateLimiter(period=10, max_calls=5)

    @pytest.fixture
    def strict_rate_limiter(self):
        """Create a strict rate limiter for testing edge cases."""
        return RateLimiter(period=5, max_calls=2)

    def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.period == 10
        assert rate_limiter.max_calls == 5
        assert rate_limiter.calls == []
        assert rate_limiter.lock is not None
        assert isinstance(rate_limiter.lock, threading.Lock)

    def test_is_limited_empty_calls(self, rate_limiter):
        """Test is_limited with no previous calls."""
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0

    def test_is_limited_within_limit(self, rate_limiter):
        """Test is_limited when within rate limit."""
        # Add some calls but stay under limit
        current_time = time.time()
        rate_limiter.calls = [current_time - 1, current_time - 2, current_time - 3]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0

    def test_is_limited_at_limit(self, rate_limiter):
        """Test is_limited when at rate limit."""
        # Add exactly max_calls within period
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(5)]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert is_limited
        assert wait_time >= 1  # Should wait at least 1 second

    def test_is_limited_over_limit(self, rate_limiter):
        """Test is_limited when over rate limit."""
        # Add more than max_calls within period
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(7)]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert is_limited
        assert wait_time >= 1

    def test_is_limited_expired_calls(self, rate_limiter):
        """Test is_limited with expired calls."""
        # Add old calls that should be expired
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired (> 10 seconds)
            current_time - 12,  # Expired
            current_time - 2,   # Active
            current_time - 1,   # Active
        ]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0
        
        # Should have cleaned up expired calls
        assert len(rate_limiter.calls) == 2

    def test_is_limited_edge_of_period(self, rate_limiter):
        """Test is_limited with calls at edge of time period."""
        current_time = time.time()
        # Add a call exactly at the period boundary
        rate_limiter.calls = [current_time - 10.0]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0
        
        # Call at period boundary should be removed
        assert len(rate_limiter.calls) == 0

    def test_record_call(self, rate_limiter):
        """Test recording a call."""
        initial_count = len(rate_limiter.calls)
        rate_limiter.record_call()
        
        assert len(rate_limiter.calls) == initial_count + 1
        assert rate_limiter.calls[-1] <= time.time()

    def test_record_call_timing(self, rate_limiter):
        """Test that recorded calls have accurate timestamps."""
        before_time = time.time()
        rate_limiter.record_call()
        after_time = time.time()
        
        recorded_time = rate_limiter.calls[-1]
        assert before_time <= recorded_time <= after_time

    def test_get_remaining_calls_empty(self, rate_limiter):
        """Test get_remaining_calls with no calls."""
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 5

    def test_get_remaining_calls_with_active_calls(self, rate_limiter):
        """Test get_remaining_calls with active calls."""
        current_time = time.time()
        rate_limiter.calls = [current_time - 1, current_time - 2]
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 3

    def test_get_remaining_calls_with_expired_calls(self, rate_limiter):
        """Test get_remaining_calls with expired calls."""
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired
            current_time - 12,  # Expired
            current_time - 2,   # Active
        ]
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 4
        
        # Should have cleaned up expired calls
        assert len(rate_limiter.calls) == 1

    def test_get_remaining_calls_at_limit(self, rate_limiter):
        """Test get_remaining_calls when at limit."""
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(5)]
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 0

    def test_get_remaining_calls_over_limit(self, rate_limiter):
        """Test get_remaining_calls when over limit."""
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(7)]
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == -2  # 5 - 7 = -2

    def test_wait_time_calculation(self, strict_rate_limiter):
        """Test wait time calculation accuracy."""
        current_time = time.time()
        # Add calls that will require waiting
        strict_rate_limiter.calls = [current_time - 1, current_time - 2]
        
        is_limited, wait_time = strict_rate_limiter.is_limited()
        
        assert is_limited
        # Wait time should be approximately period - (current_time - oldest_call)
        # oldest_call is current_time - 2, so wait_time should be ~= 5 - 2 = 3
        assert 2 <= wait_time <= 4  # Allow for timing variations

    def test_minimum_wait_time(self, rate_limiter):
        """Test minimum wait time enforcement."""
        current_time = time.time()
        # Add a call very recently to test minimum wait time
        rate_limiter.calls = [current_time - 0.1 for _ in range(5)]
        
        is_limited, wait_time = rate_limiter.is_limited()
        
        assert is_limited
        assert wait_time >= 1  # Should enforce minimum 1 second wait

    def test_thread_safety_record_call(self, rate_limiter):
        """Test thread safety of record_call method."""
        def make_calls():
            for _ in range(10):
                rate_limiter.record_call()
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_calls)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have recorded all calls
        assert len(rate_limiter.calls) == 50

    def test_thread_safety_is_limited(self, rate_limiter):
        """Test thread safety of is_limited method."""
        # Pre-populate with some calls
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(3)]
        
        results = []
        
        def check_limited():
            is_limited, wait_time = rate_limiter.is_limited()
            results.append((is_limited, wait_time))
        
        # Create multiple threads checking limit
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=check_limited)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All threads should return the same result
        assert len(results) == 10
        first_result = results[0]
        assert all(r == first_result for r in results)

    def test_thread_safety_get_remaining_calls(self, rate_limiter):
        """Test thread safety of get_remaining_calls method."""
        # Pre-populate with some calls
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(3)]
        
        results = []
        
        def get_remaining():
            remaining = rate_limiter.get_remaining_calls()
            results.append(remaining)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_remaining)
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All threads should return the same result
        assert len(results) == 10
        first_result = results[0]
        assert all(r == first_result for r in results)

    def test_concurrent_record_and_check(self, strict_rate_limiter):
        """Test concurrent recording and checking operations."""
        check_results = []
        
        def record_calls():
            for _ in range(3):
                strict_rate_limiter.record_call()
                time.sleep(0.01)  # Small delay between calls
        
        def check_limits():
            for _ in range(5):
                is_limited, wait_time = strict_rate_limiter.is_limited()
                check_results.append((is_limited, wait_time))
                time.sleep(0.01)
        
        # Start both operations concurrently
        record_thread = threading.Thread(target=record_calls)
        check_thread = threading.Thread(target=check_limits)
        
        record_thread.start()
        check_thread.start()
        
        record_thread.join()
        check_thread.join()
        
        # Should have recorded 3 calls
        assert len(strict_rate_limiter.calls) == 3
        # Should have multiple check results
        assert len(check_results) == 5

    def test_calls_cleanup_during_operations(self, rate_limiter):
        """Test that expired calls are cleaned up during operations."""
        # Add mix of old and new calls (period is 10 seconds)
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired (15 > 10)
            current_time - 12,  # Expired (12 > 10)
            current_time - 8,   # Active (8 < 10)
            current_time - 2,   # Active (2 < 10)
        ]
        
        # Operations should clean up expired calls
        is_limited, _ = rate_limiter.is_limited()
        assert not is_limited
        assert len(rate_limiter.calls) == 2  # Two active calls should remain
        
        # Add more expired calls
        rate_limiter.calls.extend([current_time - 20, current_time - 25])
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 3  # 5 - 2 active calls
        assert len(rate_limiter.calls) == 2  # Should have cleaned up expired calls, 2 active remain

    def test_edge_case_zero_max_calls(self):
        """Test edge case with zero max calls."""
        limiter = RateLimiter(period=10, max_calls=0)
        
        # Should always be limited
        is_limited, wait_time = limiter.is_limited()
        assert is_limited
        assert wait_time >= 1
        
        # Remaining calls should be 0
        remaining = limiter.get_remaining_calls()
        assert remaining == 0

    def test_edge_case_zero_period(self):
        """Test edge case with zero period."""
        limiter = RateLimiter(period=0, max_calls=5)
        
        # Add a call
        limiter.record_call()
        
        # With zero period, all calls should be considered expired
        is_limited, wait_time = limiter.is_limited()
        assert not is_limited
        assert wait_time == 0
        
        # Calls should be cleaned up
        assert len(limiter.calls) == 0

    def test_large_number_of_calls(self, rate_limiter):
        """Test performance with large number of calls."""
        # Add many calls
        current_time = time.time()
        large_calls = [current_time - i * 0.1 for i in range(1000)]
        rate_limiter.calls = large_calls
        
        # Operations should still work efficiently
        start_time = time.time()
        is_limited, wait_time = rate_limiter.is_limited()
        end_time = time.time()
        
        # Should complete quickly (within reasonable time)
        assert end_time - start_time < 1.0
        
        # Should have cleaned up expired calls
        assert len(rate_limiter.calls) < 1000

    def test_time_precision(self, rate_limiter):
        """Test rate limiter behavior with high time precision."""
        # Record calls with very small time differences
        base_time = time.time()
        rate_limiter.calls = [
            base_time - 0.001,
            base_time - 0.002,
            base_time - 0.003,
        ]
        
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 2  # 5 - 3 = 2

    def test_calls_list_immutability_during_check(self, rate_limiter):
        """Test that calls list is properly managed during concurrent access."""
        # Pre-populate with calls
        current_time = time.time()
        initial_calls = [current_time - i for i in range(3)]
        rate_limiter.calls = initial_calls.copy()
        
        # Check that operations don't interfere with each other
        original_length = len(rate_limiter.calls)
        
        is_limited, _ = rate_limiter.is_limited()
        remaining = rate_limiter.get_remaining_calls()
        
        # Length should be consistent
        assert len(rate_limiter.calls) == original_length
        assert remaining == rate_limiter.max_calls - len(rate_limiter.calls)

    def test_boundary_condition_exact_period(self, rate_limiter):
        """Test boundary condition where call is exactly at period boundary."""
        current_time = time.time()
        
        # Add a call exactly at the period boundary
        rate_limiter.calls = [current_time - rate_limiter.period]
        
        # This call should be considered expired
        is_limited, wait_time = rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0
        
        # Call should be removed
        assert len(rate_limiter.calls) == 0

    def test_realistic_usage_pattern(self, rate_limiter):
        """Test realistic usage pattern over time."""
        # Simulate normal usage: make calls, check limits, wait, repeat
        
        # Make initial calls within limit
        for _ in range(3):
            rate_limiter.record_call()
            time.sleep(0.01)
        
        # Should not be limited yet
        is_limited, _ = rate_limiter.is_limited()
        assert not is_limited
        
        # Make more calls to reach limit
        for _ in range(2):
            rate_limiter.record_call()
        
        # Should now be limited
        is_limited, wait_time = rate_limiter.is_limited()
        assert is_limited
        assert wait_time >= 1
        
        # Check remaining calls
        remaining = rate_limiter.get_remaining_calls()
        assert remaining == 0

    def test_rate_limiter_independence(self):
        """Test that different rate limiter instances are independent."""
        limiter1 = RateLimiter(period=10, max_calls=5)
        limiter2 = RateLimiter(period=5, max_calls=3)
        
        # Add calls to limiter1
        for _ in range(3):
            limiter1.record_call()
        
        # limiter2 should be unaffected
        assert len(limiter1.calls) == 3
        assert len(limiter2.calls) == 0
        
        remaining1 = limiter1.get_remaining_calls()
        remaining2 = limiter2.get_remaining_calls()
        
        assert remaining1 == 2  # 5 - 3
        assert remaining2 == 3  # 3 - 0