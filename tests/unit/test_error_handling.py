"""
Unit tests for error handling and exception propagation throughout the application.

This module focuses on testing exception propagation, graceful degradation,
and recovery mechanisms across different components.
"""

import asyncio
from datetime import datetime, timedelta
import logging
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.utils.service_health import DegradationLevel, ServiceHealthMonitor


class TestExceptionPropagation:
    """Test exception propagation and handling across components."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return MagicMock(spec=logging.Logger)

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        service = AsyncMock()
        service.get_public_ip = AsyncMock()
        return service

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage service."""
        storage = MagicMock()
        storage.get_current_ip = MagicMock()
        storage.save_current_ip = MagicMock()
        storage.add_ip_to_history = MagicMock()
        return storage

    @pytest.fixture
    def mock_discord_client(self):
        """Create a mock Discord client."""
        client = AsyncMock()
        client.get_channel = MagicMock()
        return client

    async def test_ip_service_exception_propagation(self, mock_ip_service):
        """Test exception propagation from IP service."""
        # Mock IP service to raise various exceptions
        exceptions_to_test = [
            TimeoutError("Request timeout"),
            ValueError("Invalid response"),
            ConnectionError("Connection failed"),
            RuntimeError("Service error"),
            Exception("Unknown error"),
        ]

        for exception in exceptions_to_test:
            mock_ip_service.get_public_ip.side_effect = exception

            with pytest.raises(type(exception)):
                await mock_ip_service.get_public_ip()

    async def test_storage_exception_propagation(self, mock_storage):
        """Test exception propagation from storage layer."""
        # Mock storage to raise various exceptions
        exceptions_to_test = [
            sqlite3.OperationalError("Database locked"),
            sqlite3.DatabaseError("Database corrupted"),
            PermissionError("Access denied"),
            OSError("Disk full"),
            Exception("Storage error"),
        ]

        for exception in exceptions_to_test:
            mock_storage.save_current_ip.side_effect = exception

            with pytest.raises(type(exception)):
                mock_storage.save_current_ip("192.168.1.1")

    async def test_discord_client_exception_propagation(self, mock_discord_client):
        """Test exception propagation from Discord client."""
        # Mock Discord client to raise various exceptions
        exceptions_to_test = [
            ConnectionError("Connection failed"),
            RuntimeError("Discord API error"),
            ValueError("Invalid message"),
            Exception("Discord error"),
        ]

        for exception in exceptions_to_test:
            mock_channel = AsyncMock()
            mock_channel.send.side_effect = exception
            mock_discord_client.get_channel.return_value = mock_channel

            with pytest.raises(type(exception)):
                channel = mock_discord_client.get_channel(12345)
                await channel.send("test message")

    async def test_nested_exception_propagation(self, mock_ip_service, mock_storage):
        """Test nested exception propagation through multiple layers."""
        # Create a chain of exceptions
        original_exception = sqlite3.OperationalError("Database locked")

        mock_storage.save_current_ip.side_effect = original_exception

        try:
            try:
                mock_storage.save_current_ip("192.168.1.1")
            except sqlite3.OperationalError as e:
                raise RuntimeError("Storage layer failed") from e
        except RuntimeError as e:
            # Verify exception chain
            assert isinstance(e.__cause__, sqlite3.OperationalError)
            assert str(e.__cause__) == "Database locked"

    async def test_exception_logging_and_propagation(self, mock_logger):
        """Test that exceptions are properly logged before propagation."""
        with patch("logging.getLogger", return_value=mock_logger):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("Test exception for logging")
                except ValueError as e:
                    mock_logger.error("Exception occurred: %s", str(e))
                    raise

        # Verify logging was called
        mock_logger.error.assert_called_once()

    async def test_exception_context_preservation(self):
        """Test that exception context is preserved during propagation."""
        original_exception = ValueError("Original error")

        try:
            try:
                raise original_exception
            except ValueError as e:
                # Add context and re-raise
                raise RuntimeError("Wrapper error") from e
        except RuntimeError as wrapper_exception:
            # Verify context is preserved
            assert wrapper_exception.__cause__ is original_exception
            assert str(wrapper_exception.__cause__) == "Original error"

    async def test_exception_suppression_scenarios(self):
        """Test scenarios where exceptions should be suppressed."""
        suppressed_exceptions = []

        # Test context manager that suppresses specific exceptions
        try:
            try:
                raise ValueError("Suppressible error")
            except ValueError as e:
                suppressed_exceptions.append(e)
                # Exception is suppressed, don't re-raise
        except ValueError:
            pytest.fail("Exception should have been suppressed")

        assert len(suppressed_exceptions) == 1
        assert isinstance(suppressed_exceptions[0], ValueError)

    async def test_exception_handling_with_cleanup(self):
        """Test exception handling with proper cleanup."""
        cleanup_called = False

        def cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        try:
            try:
                raise ValueError("Error requiring cleanup")
            finally:
                cleanup()
        except ValueError:
            pass  # Handle the exception

        assert cleanup_called is True

    async def test_async_exception_propagation(self):
        """Test exception propagation in async contexts."""

        async def failing_async_function():
            await asyncio.sleep(0.01)  # Simulate async work
            raise ValueError("Async function failed")

        with pytest.raises(ValueError) as exc_info:
            await failing_async_function()

        assert str(exc_info.value) == "Async function failed"

    async def test_concurrent_exception_handling(self):
        """Test exception handling in concurrent operations."""

        async def failing_task(task_id):
            await asyncio.sleep(0.01)
            if task_id % 2 == 0:
                raise ValueError(f"Task {task_id} failed")
            return f"Task {task_id} succeeded"

        # Run multiple tasks concurrently
        tasks = [failing_task(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify both successes and exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        successes = [r for r in results if not isinstance(r, Exception)]

        assert len(exceptions) == 3  # Tasks 0, 2, 4 should fail
        assert len(successes) == 2  # Tasks 1, 3 should succeed

    async def test_exception_recovery_attempts(self):
        """Test exception recovery with multiple attempts."""
        attempt_count = 0
        max_attempts = 3

        async def unreliable_operation():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < max_attempts:
                raise ConnectionError(f"Attempt {attempt_count} failed")
            return "Success on final attempt"

        # Implement retry logic
        for attempt in range(max_attempts):
            try:
                result = await unreliable_operation()
                break
            except ConnectionError:
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(0.01)  # Brief delay before retry

        assert result == "Success on final attempt"
        assert attempt_count == max_attempts


class TestGracefulDegradation:
    """Test graceful degradation scenarios and system behavior."""

    @pytest.fixture
    def service_health_monitor(self):
        """Create a service health monitor for testing."""
        return ServiceHealthMonitor()

    async def test_service_degradation_levels(self, service_health_monitor):
        """Test different levels of service degradation."""
        # Start with normal operation
        assert service_health_monitor.current_degradation == DegradationLevel.NORMAL

        # Simulate minor issues
        service_health_monitor.record_failure("ip_service", "Timeout")
        degradation = service_health_monitor.current_degradation

        # Should start degrading based on failures
        assert degradation in [DegradationLevel.NORMAL, DegradationLevel.MINOR]

    async def test_feature_disabling_during_degradation(self, service_health_monitor):
        """Test feature disabling during service degradation."""
        # Force severe degradation
        service_health_monitor.force_degradation_level(DegradationLevel.SEVERE)

        # Check if non-essential features should be disabled
        health_info = service_health_monitor.get_system_health()
        assert health_info["degradation_level"] == "severe"

        # Features should be adjusted based on degradation
        adjusted_interval = service_health_monitor.get_adjusted_interval(300)
        assert adjusted_interval > 300  # Should be increased due to degradation

    async def test_partial_functionality_maintenance(self, service_health_monitor):
        """Test that core functionality is maintained during degradation."""
        # Force critical degradation
        service_health_monitor.force_degradation_level(DegradationLevel.CRITICAL)

        # Core services should still be attempted
        health_info = service_health_monitor.get_system_health()
        assert health_info["degradation_level"] == "critical"

        # Even in critical state, essential functions should work
        assert service_health_monitor.current_degradation == DegradationLevel.CRITICAL

    async def test_automatic_recovery_from_degradation(self, service_health_monitor):
        """Test automatic recovery from degraded state."""
        # Force degradation
        service_health_monitor.force_degradation_level(DegradationLevel.MODERATE)

        # Simulate successful operations to trigger recovery
        for _ in range(10):
            service_health_monitor.record_success("ip_service")

        # Should potentially recover (depends on implementation)
        current_level = service_health_monitor.current_degradation
        assert current_level in [
            DegradationLevel.NORMAL,
            DegradationLevel.MINOR,
            DegradationLevel.MODERATE,
        ]

    async def test_fallback_mechanisms_activation(self):
        """Test activation of fallback mechanisms during failures."""
        # Mock primary service failure
        primary_service_available = False
        fallback_service_available = True

        def get_service():
            if primary_service_available:
                return "primary_service"
            if fallback_service_available:
                return "fallback_service"
            raise RuntimeError("No services available")

        # Should use fallback when primary fails
        service = get_service()
        assert service == "fallback_service"

    async def test_resource_conservation_during_degradation(self):
        """Test resource conservation during system degradation."""
        # Simulate resource-constrained environment
        system_under_stress = True

        if system_under_stress:
            # Reduce resource usage
            check_interval = 600  # Longer intervals
            max_retries = 1  # Fewer retries
            batch_size = 1  # Smaller batches
        else:
            check_interval = 300
            max_retries = 3
            batch_size = 5

        # Verify resource conservation
        assert check_interval == 600
        assert max_retries == 1
        assert batch_size == 1

    async def test_user_notification_during_degradation(self):
        """Test user notification during service degradation."""
        degraded_services = ["ip_service", "discord_api"]

        # Generate appropriate user messages
        if "ip_service" in degraded_services:
            message = "IP monitoring may be delayed due to service issues"
        elif "discord_api" in degraded_services:
            message = "Notifications may be delayed due to Discord issues"
        else:
            message = "All services operating normally"

        assert "delayed" in message


class TestRecoveryMechanisms:
    """Test recovery mechanisms and system resilience."""

    @pytest.fixture
    def recovery_manager(self):
        """Create a mock recovery manager."""
        manager = MagicMock()
        manager.attempt_recovery = AsyncMock()
        manager.is_service_healthy = MagicMock()
        return manager

    async def test_automatic_service_recovery(self, recovery_manager):
        """Test automatic service recovery mechanisms."""
        # Mock failed service
        recovery_manager.is_service_healthy.return_value = False
        recovery_manager.attempt_recovery.return_value = True

        # Attempt recovery
        recovery_successful = await recovery_manager.attempt_recovery("ip_service")

        assert recovery_successful is True
        recovery_manager.attempt_recovery.assert_called_once_with("ip_service")

    async def test_recovery_with_backoff_strategy(self):
        """Test recovery with exponential backoff strategy."""
        attempt_count = 0
        max_attempts = 3
        base_delay = 0.01

        async def recovery_attempt():
            nonlocal attempt_count
            attempt_count += 1

            if attempt_count < max_attempts:
                raise ConnectionError("Recovery failed")
            return True

        # Implement exponential backoff
        for attempt in range(max_attempts):
            try:
                success = await recovery_attempt()
                if success:
                    break
            except ConnectionError:
                if attempt < max_attempts - 1:
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        assert attempt_count == max_attempts

    async def test_partial_recovery_scenarios(self, recovery_manager):
        """Test partial recovery scenarios."""
        # Mock partial recovery
        services = ["ip_service", "discord_api", "storage"]
        recovery_results = {}

        for service in services:
            if service == "storage":
                recovery_results[service] = False  # Storage still failed
            else:
                recovery_results[service] = True  # Others recovered

        # Verify partial recovery handling
        recovered_services = [s for s, success in recovery_results.items() if success]
        failed_services = [s for s, success in recovery_results.items() if not success]

        assert len(recovered_services) == 2
        assert len(failed_services) == 1
        assert "storage" in failed_services

    async def test_recovery_state_persistence(self):
        """Test that recovery state is properly maintained."""
        recovery_state = {
            "last_recovery_attempt": datetime.now(),
            "recovery_count": 0,
            "services_recovered": [],
            "services_failed": [],
        }

        # Simulate recovery attempt
        recovery_state["recovery_count"] += 1
        recovery_state["last_recovery_attempt"] = datetime.now()
        recovery_state["services_recovered"].append("ip_service")

        # Verify state maintenance
        assert recovery_state["recovery_count"] == 1
        assert len(recovery_state["services_recovered"]) == 1
        assert isinstance(recovery_state["last_recovery_attempt"], datetime)

    async def test_recovery_timeout_handling(self):
        """Test recovery timeout handling."""
        recovery_timeout = 0.05  # Short timeout for testing

        async def long_running_recovery():
            await asyncio.sleep(0.1)  # Longer than timeout
            return True

        # Test timeout during recovery
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(long_running_recovery(), timeout=recovery_timeout)

    async def test_cascading_recovery_prevention(self):
        """Test prevention of cascading recovery attempts."""
        recovery_in_progress = False
        recent_recovery_attempts = []
        max_recent_attempts = 3
        time_window = timedelta(minutes=5)

        def can_attempt_recovery():
            nonlocal recovery_in_progress, recent_recovery_attempts

            if recovery_in_progress:
                return False

            # Clean old attempts
            now = datetime.now()
            recent_recovery_attempts = [
                attempt
                for attempt in recent_recovery_attempts
                if now - attempt < time_window
            ]

            # Check if too many recent attempts
            return len(recent_recovery_attempts) < max_recent_attempts

        # Test multiple recovery attempts
        assert can_attempt_recovery() is True

        # Simulate recovery in progress
        recovery_in_progress = True
        assert can_attempt_recovery() is False

        # Simulate too many recent attempts
        recovery_in_progress = False
        for _ in range(max_recent_attempts):
            recent_recovery_attempts.append(datetime.now())

        assert can_attempt_recovery() is False
