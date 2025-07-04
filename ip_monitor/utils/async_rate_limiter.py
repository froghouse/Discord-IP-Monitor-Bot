"""
Async-native rate limiting implementation for the IP Monitor Bot.

This module provides an async-native rate limiter that replaces the threading-based
implementation, offering better performance and compatibility with asyncio applications.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class AsyncRateLimiter:
    """
    Async-native rate limiter to prevent excessive API calls.

    This implementation uses asyncio locks instead of threading locks,
    providing better performance and compatibility with async/await patterns.
    """

    def __init__(self, period: int, max_calls: int) -> None:
        """
        Initialize an async-native rate limiter.

        Args:
            period: Time window in seconds
            max_calls: Maximum number of calls allowed in the time window
        """
        self.period = period
        self.max_calls = max_calls
        self.calls: list[float] = []  # List of timestamps
        self.lock = asyncio.Lock()  # Async lock for coroutine safety

        logger.debug(
            f"AsyncRateLimiter initialized: {max_calls} calls per {period} seconds"
        )

    async def is_limited(self) -> tuple[bool, int]:
        """
        Check if the rate limit is reached.

        Returns:
            Tuple of (is_limited, seconds_to_wait)
        """
        async with self.lock:
            current_time = time.time()

            # Remove timestamps older than the rate limit period
            cutoff_time = current_time - self.period
            self.calls = [t for t in self.calls if t > cutoff_time]

            # Check if we've reached the maximum number of calls
            if len(self.calls) >= self.max_calls:
                # Calculate when the oldest call will expire
                oldest_call = min(self.calls)
                seconds_to_wait = int(self.period - (current_time - oldest_call))
                wait_time = max(1, seconds_to_wait)  # Ensure at least 1 second wait

                logger.debug(
                    f"Rate limit reached: {len(self.calls)}/{self.max_calls} calls, wait {wait_time}s"
                )
                return True, wait_time

            return False, 0

    async def record_call(self) -> None:
        """Record a timestamp for a call."""
        async with self.lock:
            current_time = time.time()
            self.calls.append(current_time)

            # Clean up old calls periodically to prevent memory bloat
            if len(self.calls) % 10 == 0:
                cutoff_time = current_time - self.period
                self.calls = [t for t in self.calls if t > cutoff_time]

            logger.debug(
                f"Call recorded: {len(self.calls)}/{self.max_calls} calls in period"
            )

    async def get_remaining_calls(self) -> int:
        """Get the number of remaining calls allowed in the current period."""
        async with self.lock:
            # Clean up expired calls first
            current_time = time.time()
            cutoff_time = current_time - self.period
            self.calls = [t for t in self.calls if t > cutoff_time]

            remaining = self.max_calls - len(self.calls)
            return max(0, remaining)

    async def wait_if_limited(self) -> bool:
        """
        Check if rate limited and wait if necessary.

        Returns:
            True if had to wait, False if not limited
        """
        is_limited, wait_time = await self.is_limited()
        if is_limited:
            logger.info(f"Rate limited, waiting {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return True
        return False

    async def acquire(self) -> None:
        """
        Acquire a rate limit slot, waiting if necessary.

        This method will block until a slot becomes available,
        automatically waiting for the rate limit to reset.
        """
        while True:
            is_limited, wait_time = await self.is_limited()
            if not is_limited:
                await self.record_call()
                break

            logger.debug(f"Rate limit acquired, waiting {wait_time} seconds")
            await asyncio.sleep(wait_time)

    async def try_acquire(self) -> bool:
        """
        Try to acquire a rate limit slot without waiting.

        Returns:
            True if slot was acquired, False if rate limited
        """
        is_limited, _ = await self.is_limited()
        if not is_limited:
            await self.record_call()
            return True
        return False

    async def get_status(self) -> dict:
        """
        Get detailed status information about the rate limiter.

        Returns:
            Dictionary containing rate limiter status
        """
        async with self.lock:
            current_time = time.time()
            cutoff_time = current_time - self.period
            active_calls = [t for t in self.calls if t > cutoff_time]

            is_limited, wait_time = False, 0
            if len(active_calls) >= self.max_calls:
                oldest_call = min(active_calls)
                wait_time = int(self.period - (current_time - oldest_call))
                is_limited = True

            return {
                "period": self.period,
                "max_calls": self.max_calls,
                "active_calls": len(active_calls),
                "remaining_calls": max(0, self.max_calls - len(active_calls)),
                "is_limited": is_limited,
                "wait_time": max(1, wait_time) if is_limited else 0,
                "utilization_percent": (len(active_calls) / self.max_calls) * 100
                if self.max_calls > 0
                else 0,
            }

    def __repr__(self) -> str:
        """String representation of the rate limiter."""
        return f"AsyncRateLimiter(period={self.period}s, max_calls={self.max_calls})"


class TokenBucketRateLimiter:
    """
    Token bucket implementation of async rate limiter.

    This alternative implementation uses the token bucket algorithm,
    which allows for burst traffic up to the bucket capacity while
    maintaining the overall rate limit.
    """

    def __init__(self, rate: float, capacity: int) -> None:
        """
        Initialize a token bucket rate limiter.

        Args:
            rate: Tokens per second refill rate
            capacity: Maximum number of tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = asyncio.Lock()

        logger.debug(
            f"TokenBucketRateLimiter initialized: {rate} tokens/sec, capacity {capacity}"
        )

    async def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        current_time = time.time()
        elapsed = current_time - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = current_time

    async def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False if insufficient tokens
        """
        async with self.lock:
            await self._refill_tokens()

            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} tokens, {self.tokens:.1f} remaining")
                return True

            logger.debug(f"Insufficient tokens: need {tokens}, have {self.tokens:.1f}")
            return False

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire
        """
        while True:
            if await self.try_acquire(tokens):
                break

            # Calculate wait time for tokens to become available
            async with self.lock:
                await self._refill_tokens()
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.rate

            logger.debug(f"Waiting {wait_time:.1f}s for {tokens} tokens")
            await asyncio.sleep(wait_time)

    async def get_status(self) -> dict:
        """Get token bucket status."""
        async with self.lock:
            await self._refill_tokens()

            return {
                "rate": self.rate,
                "capacity": self.capacity,
                "current_tokens": self.tokens,
                "utilization_percent": ((self.capacity - self.tokens) / self.capacity)
                * 100,
            }

    def __repr__(self) -> str:
        """String representation of the token bucket rate limiter."""
        return f"TokenBucketRateLimiter(rate={self.rate}/s, capacity={self.capacity})"
