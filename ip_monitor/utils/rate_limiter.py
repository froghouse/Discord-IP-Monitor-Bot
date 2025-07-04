"""
Rate limiting implementation for the IP Monitor Bot.
"""

import threading
import time


class RateLimiter:
    """
    Thread-safe rate limiter to prevent excessive API calls.
    """

    def __init__(self, period: int, max_calls: int) -> None:
        """
        Initialize a thread-safe rate limiter.

        Args:
            period: Time window in seconds
            max_calls: Maximum number of calls allowed in the time window
        """
        self.period = period
        self.max_calls = max_calls
        self.calls: list[float] = []  # List of timestamps
        self.lock = threading.Lock()  # Reentrant lock for thread safety

    def is_limited(self) -> tuple[bool, int]:
        """
        Check if the rate limit is reached.

        Returns:
            Tuple of (is_limited, seconds_to_wait)
        """
        with self.lock:
            current_time = time.time()

            # Remove timestamps older than the rate limit period
            self.calls = [t for t in self.calls if current_time - t < self.period]

            # Check if we've reached the maximum number of calls
            if len(self.calls) >= self.max_calls:
                # Calculate when the oldest call will expire
                oldest_call = min(self.calls)
                seconds_to_wait = int(self.period - (current_time - oldest_call))
                return True, max(1, seconds_to_wait)  # Ensure at least 1 second wait

            return False, 0

    def record_call(self) -> None:
        """Record a timestamp for a call."""
        with self.lock:
            self.calls.append(time.time())

    def get_remaining_calls(self) -> int:
        """Get the number of remaining calls allowed in the current period."""
        with self.lock:
            # Clean up expired calls first
            current_time = time.time()
            self.calls = [t for t in self.calls if current_time - t < self.period]
            return self.max_calls - len(self.calls)
