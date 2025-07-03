"""
Circuit breaker implementation for IP API calls.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, calls are blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for IP API calls.

    The circuit breaker monitors the success/failure rate of operations and:
    - CLOSED: Normal operation, calls are executed
    - OPEN: Too many failures, calls are blocked and fail fast
    - HALF_OPEN: Testing phase, limited calls allowed to test recovery
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        success_threshold: int = 2,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening the circuit
            recovery_timeout: Time in seconds to wait before trying half-open
            expected_exception: Exception type that counts as a failure
            success_threshold: Number of successes needed to close circuit from half-open
            timeout: Maximum time to wait for an operation
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.timeout = timeout

        # State tracking
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0

        # Protect against concurrent access
        self._lock = asyncio.Lock()

    def _can_execute(self) -> bool:
        """
        Check if the circuit breaker allows execution.

        Returns:
            True if execution is allowed, False otherwise
        """
        current_time = time.time()

        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if we should transition to half-open
            if current_time - self.last_failure_time >= self.recovery_timeout:
                logger.info("Circuit breaker transitioning from OPEN to HALF_OPEN")
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def _record_success(self) -> None:
        """Record a successful operation."""
        current_time = time.time()
        self.last_success_time = current_time

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit breaker success count: {self.success_count}/{self.success_threshold}"
            )

            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker transitioning from HALF_OPEN to CLOSED")
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _record_failure(self) -> None:
        """Record a failed operation."""
        current_time = time.time()
        self.last_failure_time = current_time

        if self.state == CircuitBreakerState.CLOSED:
            self.failure_count += 1
            logger.debug(
                f"Circuit breaker failure count: {self.failure_count}/{self.failure_threshold}"
            )

            if self.failure_count >= self.failure_threshold:
                logger.warning("Circuit breaker opening due to excessive failures")
                self.state = CircuitBreakerState.OPEN
                self.success_count = 0
        elif self.state == CircuitBreakerState.HALF_OPEN:
            logger.warning(
                "Circuit breaker transitioning from HALF_OPEN to OPEN due to failure"
            )
            self.state = CircuitBreakerState.OPEN
            self.success_count = 0

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        """
        Execute a function through the circuit breaker.

        Args:
            func: Async function to execute

        Returns:
            Result of the function

        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception raised by the function
        """
        async with self._lock:
            if not self._can_execute():
                raise CircuitBreakerError(
                    f"Circuit breaker is {self.state.value}, blocking call"
                )

        try:
            # Execute the function with timeout
            result = await asyncio.wait_for(func(), timeout=self.timeout)

            async with self._lock:
                self._record_success()

            return result

        except asyncio.TimeoutError:
            logger.warning(
                f"Circuit breaker call timed out after {self.timeout} seconds"
            )
            async with self._lock:
                self._record_failure()
            raise

        except self.expected_exception as e:
            logger.debug(f"Circuit breaker recording failure: {e}")
            async with self._lock:
                self._record_failure()
            raise

        except Exception as e:
            # Unexpected exceptions don't count as failures for circuit breaker
            logger.error(f"Unexpected exception in circuit breaker call: {e}")
            raise

    async def call_with_fallback(
        self, func: Callable[[], Awaitable[T]], fallback: Callable[[], Awaitable[T]]
    ) -> T:
        """
        Execute a function through the circuit breaker with a fallback.

        Args:
            func: Primary async function to execute
            fallback: Fallback async function to execute if circuit is open

        Returns:
            Result of the function or fallback
        """
        try:
            return await self.call(func)
        except CircuitBreakerError:
            logger.info("Circuit breaker is open, using fallback")
            return await fallback()

    def get_state(self) -> dict[str, Any]:
        """
        Get the current state of the circuit breaker.

        Returns:
            Dictionary with circuit breaker state information
        """
        current_time = time.time()

        state_info = {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "time_since_last_failure": current_time - self.last_failure_time
            if self.last_failure_time > 0
            else 0,
            "time_until_half_open": max(
                0, self.recovery_timeout - (current_time - self.last_failure_time)
            )
            if self.state == CircuitBreakerState.OPEN
            else 0,
        }

        return state_info

    def reset(self) -> None:
        """Reset the circuit breaker to initial state."""
        logger.info("Circuit breaker reset to CLOSED state")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0

    def force_open(self) -> None:
        """Force the circuit breaker to open state."""
        logger.warning("Circuit breaker forced to OPEN state")
        self.state = CircuitBreakerState.OPEN
        self.last_failure_time = time.time()

    def force_close(self) -> None:
        """Force the circuit breaker to closed state."""
        logger.info("Circuit breaker forced to CLOSED state")
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0


class IPServiceCircuitBreaker(CircuitBreaker):
    """
    Specialized circuit breaker for IP service operations.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 120.0,
        success_threshold: int = 2,
        timeout: float = 15.0,
    ) -> None:
        """
        Initialize IP service circuit breaker with appropriate defaults.

        Args:
            failure_threshold: Number of IP service failures before opening
            recovery_timeout: Time to wait before testing IP service recovery
            success_threshold: Number of successful IP checks to close circuit
            timeout: Maximum time to wait for IP service calls
        """
        super().__init__(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=Exception,  # All exceptions count as failures for IP service
            success_threshold=success_threshold,
            timeout=timeout,
        )

    async def get_ip_with_circuit_breaker(
        self, ip_fetch_func: Callable[[], Awaitable[Optional[str]]]
    ) -> Optional[str]:
        """
        Get IP address through circuit breaker with proper error handling.

        Args:
            ip_fetch_func: Function that fetches IP address

        Returns:
            IP address or None if failed/circuit is open
        """
        try:
            result = await self.call(ip_fetch_func)

            # IP service returns None for failures, which we should treat as success
            # if no exception was raised (the service is responding)
            if result is None:
                logger.debug("IP service returned None, but service is responding")
                return None

            return result

        except CircuitBreakerError:
            logger.warning("IP service circuit breaker is open - IP check blocked")
            return None
        except Exception as e:
            logger.error(f"Error in IP service circuit breaker: {e}")
            return None

    async def get_ip_with_fallback_cache(
        self,
        ip_fetch_func: Callable[[], Awaitable[Optional[str]]],
        cached_ip: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get IP address with circuit breaker and fallback to cached IP.

        Args:
            ip_fetch_func: Function that fetches IP address
            cached_ip: Cached IP address to use as fallback

        Returns:
            IP address, cached IP, or None
        """

        async def fallback_func() -> Optional[str]:
            if cached_ip:
                logger.info(f"Using cached IP address as fallback: {cached_ip}")
                return cached_ip
            return None

        try:
            return await self.call_with_fallback(ip_fetch_func, fallback_func)
        except Exception as e:
            logger.error(f"Error in IP service with fallback: {e}")
            return await fallback_func()
