"""
Unit tests for circuit breaker implementation.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    IPServiceCircuitBreaker,
)


class TestCircuitBreaker:
    """Test CircuitBreaker class."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a circuit breaker for testing."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60.0,
            success_threshold=2,
            timeout=0.5,  # Reduced from 10.0 to 0.5 for faster testing
        )

    @pytest.fixture
    def mock_async_func(self):
        """Create a mock async function."""
        return AsyncMock()

    @pytest.fixture
    def mock_failing_func(self):
        """Create a mock async function that raises exceptions."""
        func = AsyncMock()
        func.side_effect = Exception("Test error")
        return func

    @pytest.fixture
    def mock_timeout_func(self):
        """Create a mock async function that times out."""

        async def timeout_func():
            await asyncio.sleep(1.0)  # Will timeout with 0.5s timeout (reduced from 20s)

        return timeout_func

    def test_circuit_breaker_initialization(self, circuit_breaker):
        """Test circuit breaker initialization."""
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 60.0
        assert circuit_breaker.success_threshold == 2
        assert circuit_breaker.timeout == 10.0
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time == 0.0
        assert circuit_breaker.last_success_time == 0.0

    def test_can_execute_closed_state(self, circuit_breaker):
        """Test _can_execute returns True for CLOSED state."""
        circuit_breaker.state = CircuitBreakerState.CLOSED
        assert circuit_breaker._can_execute() is True

    def test_can_execute_open_state_recent_failure(self, circuit_breaker):
        """Test _can_execute returns False for OPEN state with recent failure."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = time.time()
        assert circuit_breaker._can_execute() is False

    def test_can_execute_open_state_old_failure(self, circuit_breaker):
        """Test _can_execute transitions to HALF_OPEN after recovery timeout."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = time.time() - 70.0  # 70 seconds ago

        result = circuit_breaker._can_execute()

        assert result is True
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN
        assert circuit_breaker.success_count == 0

    def test_can_execute_half_open_state(self, circuit_breaker):
        """Test _can_execute returns True for HALF_OPEN state."""
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        assert circuit_breaker._can_execute() is True

    def test_record_success_closed_state(self, circuit_breaker):
        """Test _record_success resets failure count in CLOSED state."""
        circuit_breaker.state = CircuitBreakerState.CLOSED
        circuit_breaker.failure_count = 2

        circuit_breaker._record_success()

        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_success_time > 0

    def test_record_success_half_open_state(self, circuit_breaker):
        """Test _record_success transitions to CLOSED when success threshold is reached."""
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.success_count = 1

        circuit_breaker._record_success()

        # When success threshold (2) is reached, state changes to CLOSED and counts reset
        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.failure_count == 0

    def test_record_success_half_open_insufficient_successes(self, circuit_breaker):
        """Test _record_success doesn't close circuit with insufficient successes."""
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.success_count = 0

        circuit_breaker._record_success()

        assert circuit_breaker.success_count == 1
        assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN

    def test_record_failure_closed_state(self, circuit_breaker):
        """Test _record_failure increments failure count in CLOSED state."""
        circuit_breaker.state = CircuitBreakerState.CLOSED
        circuit_breaker.failure_count = 2

        circuit_breaker._record_failure()

        assert circuit_breaker.failure_count == 3
        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.last_failure_time > 0

    def test_record_failure_closed_state_below_threshold(self, circuit_breaker):
        """Test _record_failure doesn't open circuit below threshold."""
        circuit_breaker.state = CircuitBreakerState.CLOSED
        circuit_breaker.failure_count = 1

        circuit_breaker._record_failure()

        assert circuit_breaker.failure_count == 2
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

    def test_record_failure_half_open_state(self, circuit_breaker):
        """Test _record_failure immediately opens circuit in HALF_OPEN state."""
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        circuit_breaker.success_count = 1

        circuit_breaker._record_failure()

        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.success_count == 0

    async def test_call_success(self, circuit_breaker, mock_async_func):
        """Test successful call execution."""
        mock_async_func.return_value = "success"

        result = await circuit_breaker.call(mock_async_func)

        assert result == "success"
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.last_success_time > 0

    async def test_call_failure(self, circuit_breaker, mock_failing_func):
        """Test call failure handling."""
        with pytest.raises(Exception, match="Test error"):
            await circuit_breaker.call(mock_failing_func)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.last_failure_time > 0

    async def test_call_timeout(self, circuit_breaker, mock_timeout_func):
        """Test call timeout handling."""
        with pytest.raises(TimeoutError):
            await circuit_breaker.call(mock_timeout_func)

        assert circuit_breaker.failure_count == 1
        assert circuit_breaker.last_failure_time > 0

    async def test_call_circuit_open(self, circuit_breaker, mock_async_func):
        """Test call blocked when circuit is open."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = time.time()

        with pytest.raises(CircuitBreakerError, match="Circuit breaker is open"):
            await circuit_breaker.call(mock_async_func)

        mock_async_func.assert_not_called()

    async def test_call_unexpected_exception(self, circuit_breaker):
        """Test call with unexpected exception type."""

        async def unexpected_error_func():
            raise ValueError("Unexpected error")

        circuit_breaker.expected_exception = Exception

        with pytest.raises(ValueError, match="Unexpected error"):
            await circuit_breaker.call(unexpected_error_func)

        # Should record the failure since ValueError is a subclass of Exception
        assert circuit_breaker.failure_count == 1

    async def test_call_truly_unexpected_exception(self, circuit_breaker):
        """Test call with exception not matching expected exception type."""

        async def unexpected_error_func():
            raise RuntimeError("Runtime error")

        # Set expected exception to a specific type
        circuit_breaker.expected_exception = ValueError

        with pytest.raises(RuntimeError, match="Runtime error"):
            await circuit_breaker.call(unexpected_error_func)

        # Should NOT record the failure since RuntimeError != ValueError
        assert circuit_breaker.failure_count == 0

    async def test_call_with_fallback_success(self, circuit_breaker, mock_async_func):
        """Test call_with_fallback with successful primary call."""
        mock_async_func.return_value = "primary_success"
        fallback_func = AsyncMock(return_value="fallback_result")

        result = await circuit_breaker.call_with_fallback(
            mock_async_func, fallback_func
        )

        assert result == "primary_success"
        fallback_func.assert_not_called()

    async def test_call_with_fallback_circuit_open(self, circuit_breaker):
        """Test call_with_fallback uses fallback when circuit is open."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = time.time()

        primary_func = AsyncMock(return_value="primary_result")
        fallback_func = AsyncMock(return_value="fallback_result")

        result = await circuit_breaker.call_with_fallback(primary_func, fallback_func)

        assert result == "fallback_result"
        primary_func.assert_not_called()
        fallback_func.assert_called_once()

    async def test_call_with_fallback_primary_failure(self, circuit_breaker):
        """Test call_with_fallback uses fallback when primary fails."""
        primary_func = AsyncMock(side_effect=Exception("Primary error"))
        fallback_func = AsyncMock(return_value="fallback_result")

        # Make enough failures to open circuit
        for _ in range(3):
            try:
                await circuit_breaker.call(primary_func)
            except Exception:
                pass

        result = await circuit_breaker.call_with_fallback(primary_func, fallback_func)

        assert result == "fallback_result"
        fallback_func.assert_called_once()

    def test_get_state(self, circuit_breaker):
        """Test get_state returns correct state information."""
        circuit_breaker.state = CircuitBreakerState.CLOSED
        circuit_breaker.failure_count = 1
        circuit_breaker.success_count = 0
        circuit_breaker.last_failure_time = time.time() - 30.0
        circuit_breaker.last_success_time = time.time() - 10.0

        state = circuit_breaker.get_state()

        assert state["state"] == "closed"
        assert state["failure_count"] == 1
        assert state["success_count"] == 0
        assert state["failure_threshold"] == 3
        assert state["success_threshold"] == 2
        assert state["time_since_last_failure"] == pytest.approx(30.0, rel=1e-1)
        assert state["time_until_half_open"] == 0

    def test_get_state_open_circuit(self, circuit_breaker):
        """Test get_state with open circuit shows time until half-open."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.last_failure_time = time.time() - 30.0

        state = circuit_breaker.get_state()

        assert state["state"] == "open"
        assert state["time_until_half_open"] == pytest.approx(30.0, rel=1e-1)

    def test_reset(self, circuit_breaker):
        """Test reset functionality."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 5
        circuit_breaker.success_count = 1
        circuit_breaker.last_failure_time = time.time()
        circuit_breaker.last_success_time = time.time()

        circuit_breaker.reset()

        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0
        assert circuit_breaker.last_failure_time == 0.0
        assert circuit_breaker.last_success_time == 0.0

    def test_force_open(self, circuit_breaker):
        """Test force_open functionality."""
        circuit_breaker.state = CircuitBreakerState.CLOSED

        circuit_breaker.force_open()

        assert circuit_breaker.state == CircuitBreakerState.OPEN
        assert circuit_breaker.last_failure_time > 0

    def test_force_close(self, circuit_breaker):
        """Test force_close functionality."""
        circuit_breaker.state = CircuitBreakerState.OPEN
        circuit_breaker.failure_count = 5
        circuit_breaker.success_count = 1

        circuit_breaker.force_close()

        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0
        assert circuit_breaker.success_count == 0

    async def test_concurrent_access(self, circuit_breaker):
        """Test concurrent access to circuit breaker."""

        async def success_func():
            return "success"

        async def failure_func():
            raise Exception("Test error")

        # Create multiple concurrent calls
        tasks = []
        for i in range(10):
            if i % 2 == 0:
                tasks.append(circuit_breaker.call(success_func))
            else:
                tasks.append(circuit_breaker.call(failure_func))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Should have mix of successes and exceptions
        successes = [r for r in results if r == "success"]
        failures = [r for r in results if isinstance(r, Exception)]

        assert len(successes) + len(failures) == 10
        assert len(successes) > 0
        assert len(failures) > 0

    async def test_state_transitions_full_cycle(self, circuit_breaker):
        """Test full state transition cycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""

        async def success_func():
            return "success"

        async def failure_func():
            raise Exception("Test error")

        # 1. Start in CLOSED state
        assert circuit_breaker.state == CircuitBreakerState.CLOSED

        # 2. Generate failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitBreakerState.OPEN

        # 3. Fast-forward time to trigger HALF_OPEN
        with patch("time.time", return_value=time.time() + 70):
            assert circuit_breaker._can_execute() is True
            assert circuit_breaker.state == CircuitBreakerState.HALF_OPEN

        # 4. Generate successes to close circuit
        for _ in range(2):
            await circuit_breaker.call(success_func)

        assert circuit_breaker.state == CircuitBreakerState.CLOSED
        assert circuit_breaker.failure_count == 0

    async def test_multiple_failures_in_half_open(self, circuit_breaker):
        """Test that failure in HALF_OPEN immediately opens circuit."""

        async def failure_func():
            raise Exception("Test error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call(failure_func)

        # Force to HALF_OPEN
        circuit_breaker.state = CircuitBreakerState.HALF_OPEN

        # Single failure should open it again
        with pytest.raises(Exception):
            await circuit_breaker.call(failure_func)

        assert circuit_breaker.state == CircuitBreakerState.OPEN


class TestIPServiceCircuitBreaker:
    """Test IPServiceCircuitBreaker class."""

    @pytest.fixture
    def ip_circuit_breaker(self):
        """Create an IP service circuit breaker for testing."""
        return IPServiceCircuitBreaker(
            failure_threshold=2,
            recovery_timeout=30.0,
            success_threshold=1,
            timeout=5.0,
        )

    @pytest.fixture
    def mock_ip_fetch_func(self):
        """Create a mock IP fetch function."""
        return AsyncMock()

    def test_ip_service_circuit_breaker_initialization(self, ip_circuit_breaker):
        """Test IP service circuit breaker initialization."""
        assert ip_circuit_breaker.failure_threshold == 2
        assert ip_circuit_breaker.recovery_timeout == 30.0
        assert ip_circuit_breaker.success_threshold == 1
        assert ip_circuit_breaker.timeout == 5.0
        assert ip_circuit_breaker.expected_exception == Exception

    async def test_get_ip_with_circuit_breaker_success(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_circuit_breaker with successful IP fetch."""
        mock_ip_fetch_func.return_value = "192.168.1.1"

        result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
            mock_ip_fetch_func
        )

        assert result == "192.168.1.1"
        mock_ip_fetch_func.assert_called_once()

    async def test_get_ip_with_circuit_breaker_none_result(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_circuit_breaker with None result (service responding but no IP)."""
        mock_ip_fetch_func.return_value = None

        result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
            mock_ip_fetch_func
        )

        assert result is None
        mock_ip_fetch_func.assert_called_once()

    async def test_get_ip_with_circuit_breaker_failure(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_circuit_breaker with service failure."""
        mock_ip_fetch_func.side_effect = Exception("Service error")

        result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
            mock_ip_fetch_func
        )

        assert result is None
        assert ip_circuit_breaker.failure_count == 1

    async def test_get_ip_with_circuit_breaker_open_circuit(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_circuit_breaker with open circuit."""
        # Open the circuit
        ip_circuit_breaker.state = CircuitBreakerState.OPEN
        ip_circuit_breaker.last_failure_time = time.time()

        result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
            mock_ip_fetch_func
        )

        assert result is None
        mock_ip_fetch_func.assert_not_called()

    async def test_get_ip_with_fallback_cache_success(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_fallback_cache with successful primary call."""
        mock_ip_fetch_func.return_value = "192.168.1.1"

        result = await ip_circuit_breaker.get_ip_with_fallback_cache(
            mock_ip_fetch_func, cached_ip="10.0.0.1"
        )

        assert result == "192.168.1.1"
        mock_ip_fetch_func.assert_called_once()

    async def test_get_ip_with_fallback_cache_circuit_open(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_fallback_cache uses cached IP when circuit is open."""
        ip_circuit_breaker.state = CircuitBreakerState.OPEN
        ip_circuit_breaker.last_failure_time = time.time()

        result = await ip_circuit_breaker.get_ip_with_fallback_cache(
            mock_ip_fetch_func, cached_ip="10.0.0.1"
        )

        assert result == "10.0.0.1"
        mock_ip_fetch_func.assert_not_called()

    async def test_get_ip_with_fallback_cache_no_cache(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_fallback_cache with no cached IP."""
        ip_circuit_breaker.state = CircuitBreakerState.OPEN
        ip_circuit_breaker.last_failure_time = time.time()

        result = await ip_circuit_breaker.get_ip_with_fallback_cache(
            mock_ip_fetch_func, cached_ip=None
        )

        assert result is None
        mock_ip_fetch_func.assert_not_called()

    async def test_get_ip_with_fallback_cache_exception_handling(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test get_ip_with_fallback_cache handles exceptions gracefully."""
        mock_ip_fetch_func.side_effect = Exception("Service error")

        result = await ip_circuit_breaker.get_ip_with_fallback_cache(
            mock_ip_fetch_func, cached_ip="10.0.0.1"
        )

        assert result == "10.0.0.1"
        assert ip_circuit_breaker.failure_count == 1

    async def test_ip_service_full_workflow(
        self, ip_circuit_breaker, mock_ip_fetch_func
    ):
        """Test full IP service workflow with circuit breaker."""
        # 1. Start with successful calls
        mock_ip_fetch_func.return_value = "192.168.1.1"

        result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
            mock_ip_fetch_func
        )
        assert result == "192.168.1.1"
        assert ip_circuit_breaker.state == CircuitBreakerState.CLOSED

        # 2. Generate failures to open circuit
        mock_ip_fetch_func.side_effect = Exception("Service error")

        for _ in range(2):
            result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
                mock_ip_fetch_func
            )
            assert result is None

        assert ip_circuit_breaker.state == CircuitBreakerState.OPEN

        # 3. Verify circuit blocks calls
        result = await ip_circuit_breaker.get_ip_with_fallback_cache(
            mock_ip_fetch_func, cached_ip="10.0.0.1"
        )
        assert result == "10.0.0.1"

        # 4. Fast-forward time and test recovery
        with patch("time.time", return_value=time.time() + 35):
            mock_ip_fetch_func.side_effect = None
            mock_ip_fetch_func.return_value = "192.168.1.2"

            result = await ip_circuit_breaker.get_ip_with_circuit_breaker(
                mock_ip_fetch_func
            )
            assert result == "192.168.1.2"
            assert ip_circuit_breaker.state == CircuitBreakerState.CLOSED
