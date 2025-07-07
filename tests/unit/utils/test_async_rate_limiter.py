"""
Test suite for AsyncRateLimiter and TokenBucketRateLimiter classes.

This module provides comprehensive testing for the async-native rate limiting
functionality used throughout the IP Monitor Bot.
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from ip_monitor.utils.async_rate_limiter import AsyncRateLimiter, TokenBucketRateLimiter


class TestAsyncRateLimiter:
    """Test suite for AsyncRateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        return AsyncRateLimiter(period=10, max_calls=5)

    @pytest.fixture
    def strict_rate_limiter(self):
        """Create a strict rate limiter for testing edge cases."""
        # Reduced period from 5 to 0.2 for faster testing
        return AsyncRateLimiter(period=0.2, max_calls=2)

    async def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.period == 10
        assert rate_limiter.max_calls == 5
        assert rate_limiter.calls == []
        assert rate_limiter.lock is not None
        assert isinstance(rate_limiter.lock, asyncio.Lock)

    async def test_string_representation(self, rate_limiter):
        """Test string representation of rate limiter."""
        expected = "AsyncRateLimiter(period=10s, max_calls=5)"
        assert str(rate_limiter) == expected
        assert repr(rate_limiter) == expected

    async def test_is_limited_empty_calls(self, rate_limiter):
        """Test is_limited with no previous calls."""
        is_limited, wait_time = await rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0

    async def test_is_limited_within_limit(self, rate_limiter):
        """Test is_limited when within rate limit."""
        # Add some calls but stay under limit
        current_time = time.time()
        rate_limiter.calls = [current_time - 1, current_time - 2, current_time - 3]

        is_limited, wait_time = await rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0

    async def test_is_limited_at_limit(self, rate_limiter):
        """Test is_limited when at rate limit."""
        # Add exactly max_calls within period
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(5)]

        is_limited, wait_time = await rate_limiter.is_limited()
        assert is_limited
        assert wait_time >= 1  # Should wait at least 1 second

    async def test_is_limited_over_limit(self, rate_limiter):
        """Test is_limited when over rate limit."""
        # Add more than max_calls within period
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(7)]

        is_limited, wait_time = await rate_limiter.is_limited()
        assert is_limited
        assert wait_time >= 1

    async def test_is_limited_expired_calls(self, rate_limiter):
        """Test is_limited with expired calls."""
        # Add old calls that should be expired
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired (> 10 seconds)
            current_time - 12,  # Expired
            current_time - 2,  # Active
            current_time - 1,  # Active
        ]

        is_limited, wait_time = await rate_limiter.is_limited()
        assert not is_limited
        assert wait_time == 0

    async def test_record_call(self, rate_limiter):
        """Test recording a call."""
        initial_count = len(rate_limiter.calls)
        await rate_limiter.record_call()

        assert len(rate_limiter.calls) == initial_count + 1
        assert rate_limiter.calls[-1] <= time.time()

    async def test_record_call_cleanup(self, rate_limiter):
        """Test automatic cleanup during record_call."""
        # Add 9 calls to trigger cleanup on 10th call
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(9)]

        # Add one more call to trigger cleanup (10 % 10 == 0)
        await rate_limiter.record_call()

        # Should have cleaned up expired calls
        assert len(rate_limiter.calls) == 10

    async def test_get_remaining_calls_empty(self, rate_limiter):
        """Test get_remaining_calls with no calls."""
        remaining = await rate_limiter.get_remaining_calls()
        assert remaining == 5

    async def test_get_remaining_calls_with_active_calls(self, rate_limiter):
        """Test get_remaining_calls with active calls."""
        current_time = time.time()
        rate_limiter.calls = [current_time - 1, current_time - 2]

        remaining = await rate_limiter.get_remaining_calls()
        assert remaining == 3

    async def test_get_remaining_calls_with_expired_calls(self, rate_limiter):
        """Test get_remaining_calls with expired calls."""
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired
            current_time - 12,  # Expired
            current_time - 2,  # Active
        ]

        remaining = await rate_limiter.get_remaining_calls()
        assert remaining == 4

    async def test_get_remaining_calls_at_limit(self, rate_limiter):
        """Test get_remaining_calls when at limit."""
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(5)]

        remaining = await rate_limiter.get_remaining_calls()
        assert remaining == 0

    async def test_wait_if_limited_not_limited(self, rate_limiter):
        """Test wait_if_limited when not limited."""
        waited = await rate_limiter.wait_if_limited()
        assert not waited

    async def test_wait_if_limited_is_limited(self, strict_rate_limiter):
        """Test wait_if_limited when limited."""
        # Fill up the rate limiter with recent calls (within the 0.2 second period)
        current_time = time.time()
        strict_rate_limiter.calls = [current_time - 0.01, current_time - 0.02]

        start_time = time.time()
        waited = await strict_rate_limiter.wait_if_limited()
        end_time = time.time()

        assert waited
        # Should have waited at least 0.1 seconds (reduced from 1.0)
        assert end_time - start_time >= 0.1

    async def test_try_acquire_success(self, rate_limiter):
        """Test try_acquire when not limited."""
        initial_count = len(rate_limiter.calls)

        acquired = await rate_limiter.try_acquire()

        assert acquired
        assert len(rate_limiter.calls) == initial_count + 1

    async def test_try_acquire_failure(self, strict_rate_limiter):
        """Test try_acquire when limited."""
        # Fill up the rate limiter with recent calls (within the 0.2 second period)
        current_time = time.time()
        strict_rate_limiter.calls = [current_time - 0.01, current_time - 0.02]

        acquired = await strict_rate_limiter.try_acquire()

        assert not acquired
        # Should not have recorded a call
        assert len(strict_rate_limiter.calls) == 2

    async def test_acquire_immediate(self, rate_limiter):
        """Test acquire when not limited."""
        initial_count = len(rate_limiter.calls)

        await rate_limiter.acquire()

        assert len(rate_limiter.calls) == initial_count + 1

    async def test_acquire_with_wait(self, strict_rate_limiter):
        """Test acquire when limited (will wait)."""
        # Fill up the rate limiter with recent calls (within the 0.2 second period)
        current_time = time.time()
        strict_rate_limiter.calls = [current_time - 0.01, current_time - 0.02]

        start_time = time.time()
        await strict_rate_limiter.acquire()
        end_time = time.time()

        # Should have waited and then acquired
        assert end_time - start_time >= 0.1  # Reduced from 1.0
        # After waiting, old calls may be expired and cleaned up,
        # but there should be at least one new call
        assert len(strict_rate_limiter.calls) >= 1
        # The newest call should be recent (from the acquire operation)
        assert max(strict_rate_limiter.calls) >= start_time

    async def test_get_status_empty(self, rate_limiter):
        """Test get_status with no calls."""
        status = await rate_limiter.get_status()

        expected = {
            "period": 10,
            "max_calls": 5,
            "active_calls": 0,
            "remaining_calls": 5,
            "is_limited": False,
            "wait_time": 0,
            "utilization_percent": 0.0,
        }

        assert status == expected

    async def test_get_status_with_calls(self, rate_limiter):
        """Test get_status with active calls."""
        current_time = time.time()
        rate_limiter.calls = [current_time - 1, current_time - 2]

        status = await rate_limiter.get_status()

        assert status["period"] == 10
        assert status["max_calls"] == 5
        assert status["active_calls"] == 2
        assert status["remaining_calls"] == 3
        assert not status["is_limited"]
        assert status["wait_time"] == 0
        assert status["utilization_percent"] == 40.0

    async def test_get_status_at_limit(self, rate_limiter):
        """Test get_status when at rate limit."""
        current_time = time.time()
        rate_limiter.calls = [current_time - i for i in range(5)]

        status = await rate_limiter.get_status()

        assert status["period"] == 10
        assert status["max_calls"] == 5
        assert status["active_calls"] == 5
        assert status["remaining_calls"] == 0
        assert status["is_limited"]
        assert status["wait_time"] >= 1
        assert status["utilization_percent"] == 100.0

    async def test_get_status_with_expired_calls(self, rate_limiter):
        """Test get_status with expired calls."""
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired
            current_time - 2,  # Active
            current_time - 1,  # Active
        ]

        status = await rate_limiter.get_status()

        assert status["active_calls"] == 2
        assert status["remaining_calls"] == 3
        assert status["utilization_percent"] == 40.0

    async def test_get_status_zero_max_calls(self):
        """Test get_status with zero max_calls."""
        rate_limiter = AsyncRateLimiter(period=10, max_calls=0)

        status = await rate_limiter.get_status()

        assert status["utilization_percent"] == 0.0

    async def test_concurrent_access(self, rate_limiter):
        """Test concurrent access to rate limiter."""

        async def make_calls():
            tasks = []
            for _ in range(10):
                tasks.append(rate_limiter.record_call())
            await asyncio.gather(*tasks)

        # Run concurrent calls
        await make_calls()

        # Should have recorded all calls
        assert len(rate_limiter.calls) == 10

    async def test_concurrent_acquire(self, strict_rate_limiter):
        """Test concurrent acquire operations."""

        async def try_acquire():
            return await strict_rate_limiter.try_acquire()

        # Try to acquire more than the limit concurrently
        tasks = [try_acquire() for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # Only 2 should succeed (max_calls = 2)
        successful = sum(1 for r in results if r)
        assert successful == 2

    async def test_edge_case_minimum_wait_time(self, rate_limiter):
        """Test minimum wait time calculation."""
        # Set up a scenario where calculated wait time would be < 1
        current_time = time.time()
        rate_limiter.calls = [current_time - 0.1 for _ in range(5)]

        is_limited, wait_time = await rate_limiter.is_limited()

        assert is_limited
        assert wait_time >= 1  # Should enforce minimum 1 second wait

    async def test_cleanup_during_is_limited(self, rate_limiter):
        """Test call cleanup during is_limited check."""
        # Add mix of expired and active calls
        current_time = time.time()
        rate_limiter.calls = [
            current_time - 15,  # Expired
            current_time - 12,  # Expired
            current_time - 2,  # Active
            current_time - 1,  # Active
        ]

        await rate_limiter.is_limited()

        # Should have cleaned up expired calls
        assert len(rate_limiter.calls) == 2
        assert all(call > current_time - 10 for call in rate_limiter.calls)


class TestTokenBucketRateLimiter:
    """Test suite for TokenBucketRateLimiter class."""

    @pytest.fixture
    def token_bucket(self):
        """Create a token bucket rate limiter for testing."""
        return TokenBucketRateLimiter(rate=2.0, capacity=10)

    @pytest.fixture
    def small_bucket(self):
        """Create a small token bucket for testing edge cases."""
        # Increased rate from 1.0 to 10.0 for faster testing
        return TokenBucketRateLimiter(rate=10.0, capacity=3)

    async def test_initialization(self, token_bucket):
        """Test token bucket initialization."""
        assert token_bucket.rate == 2.0
        assert token_bucket.capacity == 10
        assert token_bucket.tokens == 10.0
        assert token_bucket.last_refill <= time.time()
        assert token_bucket.lock is not None
        assert isinstance(token_bucket.lock, asyncio.Lock)

    async def test_string_representation(self, token_bucket):
        """Test string representation of token bucket."""
        expected = "TokenBucketRateLimiter(rate=2.0/s, capacity=10)"
        assert str(token_bucket) == expected
        assert repr(token_bucket) == expected

    async def test_refill_tokens(self, token_bucket):
        """Test token refill mechanism."""
        # Consume some tokens
        token_bucket.tokens = 5.0
        initial_time = 1000.0  # Use a fixed time for predictable results
        token_bucket.last_refill = initial_time

        # Simulate time passing
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time",
            return_value=initial_time + 2.0,
        ):
            await token_bucket._refill_tokens()

        # Should have refilled 4 tokens (2 seconds * 2 tokens/sec)
        assert token_bucket.tokens == 9.0

    async def test_refill_tokens_cap_at_capacity(self, token_bucket):
        """Test token refill doesn't exceed capacity."""
        # Start with some tokens
        token_bucket.tokens = 8.0
        initial_time = 1000.0  # Use a fixed time
        token_bucket.last_refill = initial_time

        # Simulate a lot of time passing
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time",
            return_value=initial_time + 10.0,
        ):
            await token_bucket._refill_tokens()

        # Should be capped at capacity
        assert token_bucket.tokens == 10.0

    async def test_try_acquire_success(self, token_bucket):
        """Test successful token acquisition."""
        # Set predictable time to avoid refill
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        initial_tokens = token_bucket.tokens

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            acquired = await token_bucket.try_acquire(3)

        assert acquired
        assert token_bucket.tokens == initial_tokens - 3

    async def test_try_acquire_insufficient_tokens(self, token_bucket):
        """Test token acquisition with insufficient tokens."""
        # Set tokens to less than requested
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        token_bucket.tokens = 2.0

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            acquired = await token_bucket.try_acquire(5)

        assert not acquired
        assert token_bucket.tokens == 2.0  # Should remain unchanged

    async def test_try_acquire_exact_tokens(self, token_bucket):
        """Test token acquisition with exact token count."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        token_bucket.tokens = 5.0

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            acquired = await token_bucket.try_acquire(5)

        assert acquired
        assert token_bucket.tokens == 0.0

    async def test_try_acquire_default_single_token(self, token_bucket):
        """Test token acquisition with default single token."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        initial_tokens = token_bucket.tokens

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            acquired = await token_bucket.try_acquire()

        assert acquired
        assert token_bucket.tokens == initial_tokens - 1

    async def test_try_acquire_with_refill(self, small_bucket):
        """Test token acquisition with automatic refill."""
        # Consume all tokens
        small_bucket.tokens = 0.0
        initial_time = 1000.0
        small_bucket.last_refill = initial_time

        # Simulate time passing to refill tokens
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time",
            return_value=initial_time + 2.0,
        ):
            acquired = await small_bucket.try_acquire(1)

        assert acquired
        # Should have refilled to capacity (3), then used 1
        assert small_bucket.tokens == 2.0

    async def test_acquire_immediate(self, token_bucket):
        """Test acquire when tokens are available."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        initial_tokens = token_bucket.tokens

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            await token_bucket.acquire(3)

        assert token_bucket.tokens == initial_tokens - 3

    async def test_acquire_with_wait(self, small_bucket):
        """Test acquire when tokens need to be refilled."""
        # Consume all tokens
        small_bucket.tokens = 0.0

        start_time = time.time()
        await small_bucket.acquire(1)
        end_time = time.time()

        # Should have waited for token to be refilled (0.1s at 10 tokens/sec)
        assert end_time - start_time >= 0.1
        assert (
            small_bucket.tokens >= 0.0
        )  # Used the refilled token (allowing for floating point precision)

    async def test_acquire_multiple_tokens_with_wait(self, small_bucket):
        """Test acquire multiple tokens with wait."""
        # Start with no tokens
        small_bucket.tokens = 0.0

        start_time = time.time()
        await small_bucket.acquire(2)
        end_time = time.time()

        # Should have waited for 2 tokens to be refilled (0.2 seconds at 10 tokens/sec)
        assert end_time - start_time >= 0.2
        assert (
            small_bucket.tokens >= 0.0
        )  # Used the refilled tokens (allowing for floating point precision)

    async def test_get_status_full_bucket(self, token_bucket):
        """Test get_status with full bucket."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            status = await token_bucket.get_status()

        expected = {
            "rate": 2.0,
            "capacity": 10,
            "current_tokens": 10.0,
            "utilization_percent": 0.0,
        }

        assert status == expected

    async def test_get_status_partial_bucket(self, token_bucket):
        """Test get_status with partial bucket."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        token_bucket.tokens = 6.0

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            status = await token_bucket.get_status()

        assert status["rate"] == 2.0
        assert status["capacity"] == 10
        assert status["current_tokens"] == 6.0
        assert status["utilization_percent"] == 40.0

    async def test_get_status_empty_bucket(self, token_bucket):
        """Test get_status with empty bucket."""
        fixed_time = 1000.0
        token_bucket.last_refill = fixed_time
        token_bucket.tokens = 0.0

        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=fixed_time
        ):
            status = await token_bucket.get_status()

        assert status["current_tokens"] == 0.0
        assert status["utilization_percent"] == 100.0

    async def test_get_status_with_refill(self, small_bucket):
        """Test get_status with automatic refill."""
        # Consume tokens
        small_bucket.tokens = 1.0
        initial_time = 1000.0
        small_bucket.last_refill = initial_time

        # Simulate time passing
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time",
            return_value=initial_time + 1.0,
        ):
            status = await small_bucket.get_status()

        # Should have refilled to capacity (3 max)
        assert status["current_tokens"] == 3.0

    async def test_concurrent_token_acquisition(self, token_bucket):
        """Test concurrent token acquisition."""

        async def acquire_tokens():
            return await token_bucket.try_acquire(2)

        # Try to acquire more tokens than available concurrently
        tasks = [acquire_tokens() for _ in range(6)]
        results = await asyncio.gather(*tasks)

        # Should only succeed for 5 calls (10 tokens / 2 tokens per call)
        successful = sum(1 for r in results if r)
        assert successful == 5

    async def test_token_refill_time_precision(self, token_bucket):
        """Test token refill time precision."""
        # Set up initial state
        token_bucket.tokens = 0.0
        initial_time = 1000.0
        token_bucket.last_refill = initial_time

        # Simulate partial time passing (0.5 seconds)
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time",
            return_value=initial_time + 0.5,
        ):
            await token_bucket._refill_tokens()

        # Should have refilled 1 token (0.5 seconds * 2 tokens/sec)
        assert token_bucket.tokens == 1.0

    async def test_zero_rate_edge_case(self):
        """Test edge case with zero rate."""
        bucket = TokenBucketRateLimiter(rate=0.0, capacity=5)

        # Should not refill any tokens
        initial_time = time.time()
        with patch("time.time", return_value=initial_time + 10.0):
            await bucket._refill_tokens()

        assert bucket.tokens == 5.0  # Should remain at initial capacity

    async def test_negative_time_edge_case(self, token_bucket):
        """Test edge case with negative time difference."""
        # Set last_refill to future time (simulating clock adjustment)
        current_time = 1000.0
        token_bucket.last_refill = current_time + 100
        token_bucket.tokens = 5.0

        # Should not add negative tokens
        with patch(
            "ip_monitor.utils.async_rate_limiter.time.time", return_value=current_time
        ):
            await token_bucket._refill_tokens()

        assert token_bucket.tokens == 5.0


class TestRateLimiterIntegration:
    """Integration tests for rate limiter components."""

    async def test_async_rate_limiter_realistic_usage(self):
        """Test realistic usage pattern for AsyncRateLimiter."""
        # Create a rate limiter: 5 calls per 2 seconds
        limiter = AsyncRateLimiter(period=2, max_calls=5)

        # Make 5 calls quickly
        for _ in range(5):
            acquired = await limiter.try_acquire()
            assert acquired

        # 6th call should fail
        acquired = await limiter.try_acquire()
        assert not acquired

        # Wait for reset and try again
        await asyncio.sleep(2.1)
        acquired = await limiter.try_acquire()
        assert acquired

    async def test_token_bucket_burst_handling(self):
        """Test token bucket burst handling capability."""
        # Create bucket: 1 token/sec, capacity 5
        bucket = TokenBucketRateLimiter(rate=1.0, capacity=5)

        # Should handle burst of 5 tokens
        for i in range(5):
            acquired = await bucket.try_acquire()
            assert acquired, f"Failed to acquire token {i + 1}"

        # 6th should fail
        acquired = await bucket.try_acquire()
        assert not acquired

        # Wait for refill and try again
        await asyncio.sleep(1.1)
        acquired = await bucket.try_acquire()
        assert acquired

    async def test_rate_limiter_comparison(self):
        """Test comparison between different rate limiter implementations."""
        # Equivalent configurations
        async_limiter = AsyncRateLimiter(period=1, max_calls=2)
        token_bucket = TokenBucketRateLimiter(rate=2.0, capacity=2)

        # Both should allow 2 initial calls
        for _ in range(2):
            assert await async_limiter.try_acquire()
            assert await token_bucket.try_acquire()

        # Both should deny 3rd call
        assert not await async_limiter.try_acquire()
        assert not await token_bucket.try_acquire()
