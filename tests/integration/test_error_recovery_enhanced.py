"""
Enhanced error recovery tests with comprehensive diagnostics.

This demonstrates how to integrate the error diagnostic system
with existing integration tests for better failure analysis.
"""

import asyncio
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.circuit_breaker import CircuitBreakerError
from ip_monitor.utils.service_health import service_health
from tests.utils.diagnostic_helpers import (
    DiagnosticContext,
    assert_with_context,
    log_test_checkpoint,
    log_test_start,
    monitor_async_operations,
    track_service_state,
    with_diagnostics,
)


class TestNetworkFailureRecoveryEnhanced:
    """Test network failure handling and recovery with enhanced diagnostics."""

    @pytest.fixture
    async def bot_with_network_mocking(self):
        """Create bot with network operation mocking."""
        with patch.dict(
            os.environ, {"DISCORD_BOT_TOKEN": "test_token", "CHANNEL_ID": "123456789"}
        ):
            config = AppConfig.load_from_env()
            config.testing_mode = True

        with patch("discord.ext.commands.Bot"):
            bot = IPMonitorBot(config)
            yield bot

    @pytest.mark.asyncio
    @with_diagnostics
    @track_service_state("ip_service")
    @monitor_async_operations("api_timeout_recovery", timeout=45.0)
    async def test_api_timeout_recovery_enhanced(self, bot_with_network_mocking):
        """Test recovery from API timeout errors with comprehensive diagnostics."""
        log_test_start("test_api_timeout_recovery_enhanced")

        bot = bot_with_network_mocking
        # Store for service state tracking
        self.ip_service = bot.ip_service

        # Mock timeout errors
        timeout_error = TimeoutError("Request timeout")

        async with DiagnosticContext("timeout_recovery_test") as ctx:
            with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
                # First call fails with timeout
                mock_get_ip.side_effect = [timeout_error, "192.168.1.100"]

                ctx.record_checkpoint("Mock configured for timeout scenario")

                # First attempt should fail
                try:
                    log_test_checkpoint("Attempting first IP check (should fail)")
                    await asyncio.wait_for(bot.ip_service.get_public_ip(), timeout=30.0)

                    assert_with_context(
                        False,
                        "Expected timeout error but operation succeeded",
                        expected_error="TimeoutError",
                        actual_result="success",
                    )

                except TimeoutError as e:
                    log_test_checkpoint("First attempt failed as expected")
                    ctx.record_checkpoint(
                        "First timeout handled",
                        {
                            "error": str(e),
                            "service_health_before": service_health.get_current_health(),  # noqa: E501
                        },
                    )

                    # Record the failure
                    service_health.record_failure(
                        "ip_service", "Timeout error", "api_check"
                    )

                    ctx.record_checkpoint("Service health updated after failure")

                # Second attempt should succeed (recovery)
                log_test_checkpoint("Attempting second IP check (should succeed)")
                ip = await asyncio.wait_for(
                    bot.ip_service.get_public_ip(), timeout=30.0
                )

                ctx.record_checkpoint(
                    "Second attempt succeeded",
                    {
                        "ip": ip,
                        "service_health_after": service_health.get_current_health(),
                    },
                )

                assert_with_context(
                    ip == "192.168.1.100",
                    "IP check recovery failed",
                    expected_ip="192.168.1.100",
                    actual_ip=ip,
                    mock_call_count=mock_get_ip.call_count,
                    service_health=service_health.get_current_health(),
                )

                # Record recovery
                service_health.record_success("ip_service", "api_check")
                log_test_checkpoint("Recovery successful and recorded")

    @pytest.mark.asyncio
    @with_diagnostics
    @track_service_state("ip_service")
    @monitor_async_operations("connection_error_recovery", timeout=60.0)
    async def test_connection_error_recovery_enhanced(self, bot_with_network_mocking):
        """Test recovery from connection errors with enhanced diagnostics."""
        log_test_start("test_connection_error_recovery_enhanced")

        bot = bot_with_network_mocking
        # Store for service state tracking
        self.ip_service = bot.ip_service

        connection_error = ConnectionError("Connection refused")

        async with DiagnosticContext("connection_recovery_test") as ctx:
            with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
                # Multiple failures followed by success
                mock_get_ip.side_effect = [
                    connection_error,
                    connection_error,
                    "192.168.1.101",
                ]

                ctx.record_checkpoint("Mock configured for connection error scenario")

                # First two attempts should fail
                for attempt in range(2):
                    log_test_checkpoint(
                        f"Attempting connection {attempt + 1} (should fail)"
                    )

                    try:
                        await asyncio.wait_for(
                            bot.ip_service.get_public_ip(), timeout=30.0
                        )

                        assert_with_context(
                            False,
                            f"Expected connection error on attempt {attempt + 1}",
                            attempt=attempt + 1,
                            expected_error="ConnectionError",
                        )

                    except ConnectionError as e:
                        log_test_checkpoint(
                            f"Connection attempt {attempt + 1} failed as expected"
                        )
                        ctx.record_checkpoint(
                            f"Connection failure {attempt + 1}",
                            {
                                "error": str(e),
                                "attempt": attempt + 1,
                                "service_health": service_health.get_current_health(),
                            },
                        )

                        service_health.record_failure(
                            "ip_service", "Connection error", "api_check"
                        )

                # Third attempt should succeed
                log_test_checkpoint("Attempting final connection (should succeed)")
                ip = await asyncio.wait_for(
                    bot.ip_service.get_public_ip(), timeout=30.0
                )

                ctx.record_checkpoint(
                    "Final attempt succeeded",
                    {
                        "ip": ip,
                        "total_attempts": 3,
                        "service_health": service_health.get_current_health(),
                    },
                )

                assert_with_context(
                    ip == "192.168.1.101",
                    "Connection recovery failed",
                    expected_ip="192.168.1.101",
                    actual_ip=ip,
                    total_attempts=3,
                    mock_call_count=mock_get_ip.call_count,
                )

                service_health.record_success("ip_service", "api_check")
                log_test_checkpoint("Connection recovery successful")

    @pytest.mark.asyncio
    @with_diagnostics
    @track_service_state("circuit_breaker")
    @monitor_async_operations("circuit_breaker_recovery", timeout=90.0)
    async def test_circuit_breaker_recovery_enhanced(self, bot_with_network_mocking):
        """Test circuit breaker recovery with enhanced diagnostics."""
        log_test_start("test_circuit_breaker_recovery_enhanced")

        bot = bot_with_network_mocking

        async with DiagnosticContext("circuit_breaker_test") as ctx:
            with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
                # Configure circuit breaker to trip after 3 failures
                circuit_breaker_error = CircuitBreakerError("Circuit breaker is open")

                # First 3 calls fail, triggering circuit breaker
                mock_get_ip.side_effect = [
                    ConnectionError("Connection failed"),
                    ConnectionError("Connection failed"),
                    ConnectionError("Connection failed"),
                    circuit_breaker_error,  # Circuit breaker now open
                    "192.168.1.102",  # Recovery after circuit breaker closes
                ]

                ctx.record_checkpoint("Mock configured for circuit breaker scenario")

                # First 3 attempts should fail with connection errors
                for attempt in range(3):
                    log_test_checkpoint(
                        f"Attempting call {attempt + 1} (connection failure)"
                    )

                    try:
                        await asyncio.wait_for(
                            bot.ip_service.get_public_ip(), timeout=30.0
                        )

                        assert_with_context(
                            False,
                            f"Expected connection error on attempt {attempt + 1}",
                            attempt=attempt + 1,
                        )

                    except ConnectionError as e:
                        ctx.record_checkpoint(
                            f"Connection failure {attempt + 1}",
                            {"error": str(e), "attempt": attempt + 1},
                        )

                        service_health.record_failure(
                            "ip_service", "Connection error", "api_check"
                        )

                # Fourth attempt should trigger circuit breaker
                log_test_checkpoint(
                    "Attempting call 4 (circuit breaker should be open)"
                )

                try:
                    await asyncio.wait_for(bot.ip_service.get_public_ip(), timeout=30.0)

                    assert_with_context(
                        False,
                        "Expected circuit breaker error",
                        expected_error="CircuitBreakerError",
                    )

                except CircuitBreakerError as e:
                    log_test_checkpoint("Circuit breaker triggered as expected")
                    ctx.record_checkpoint(
                        "Circuit breaker opened",
                        {
                            "error": str(e),
                            "service_health": service_health.get_current_health(),
                        },
                    )

                # Wait for circuit breaker to close (simulate time passage)
                await asyncio.sleep(0.1)  # Simulate timeout

                # Fifth attempt should succeed after circuit breaker recovery
                log_test_checkpoint(
                    "Attempting call 5 (circuit breaker should be closed)"
                )
                ip = await asyncio.wait_for(
                    bot.ip_service.get_public_ip(), timeout=30.0
                )

                ctx.record_checkpoint(
                    "Circuit breaker recovery successful",
                    {"ip": ip, "service_health": service_health.get_current_health()},
                )

                assert_with_context(
                    ip == "192.168.1.102",
                    "Circuit breaker recovery failed",
                    expected_ip="192.168.1.102",
                    actual_ip=ip,
                    total_attempts=5,
                    circuit_breaker_state="closed",
                )

                service_health.record_success("ip_service", "api_check")
                log_test_checkpoint("Circuit breaker recovery test completed")


class TestDatabaseFailureRecoveryEnhanced:
    """Test database failure recovery with enhanced diagnostics."""

    @pytest.mark.asyncio
    @with_diagnostics
    @track_service_state("storage")
    @monitor_async_operations("database_corruption_recovery", timeout=60.0)
    async def test_database_corruption_recovery_enhanced(self, isolated_test_config):
        """Test recovery from database corruption with enhanced diagnostics."""
        log_test_start("test_database_corruption_recovery_enhanced")

        async with DiagnosticContext("database_corruption_test") as ctx:
            # Create temporary database file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
                temp_db_path = temp_db.name

            try:
                # Store for service state tracking
                self.storage = SQLiteIPStorage(temp_db_path)

                ctx.record_checkpoint(
                    "Database initialized",
                    {
                        "db_path": temp_db_path,
                        "db_exists": Path(temp_db_path).exists(),
                    },
                )

                # Test normal operation first
                log_test_checkpoint("Testing normal database operation")
                await self.storage.save_current_ip("192.168.1.1")
                ip = await self.storage.get_current_ip()

                assert_with_context(
                    ip == "192.168.1.1",
                    "Normal database operation failed",
                    expected_ip="192.168.1.1",
                    actual_ip=ip,
                )

                ctx.record_checkpoint("Normal operation verified")

                # Simulate database corruption by deleting file
                log_test_checkpoint("Simulating database corruption")
                await self.storage.close()
                Path(temp_db_path).unlink()

                ctx.record_checkpoint(
                    "Database file deleted", {"db_exists": Path(temp_db_path).exists()}
                )

                # Attempt to recreate storage (should handle corruption)
                log_test_checkpoint("Attempting to recreate storage")
                self.storage = SQLiteIPStorage(temp_db_path)

                # Test recovery operation
                await self.storage.save_current_ip("192.168.1.2")
                recovered_ip = await self.storage.get_current_ip()

                ctx.record_checkpoint(
                    "Recovery successful",
                    {
                        "recovered_ip": recovered_ip,
                        "db_exists": Path(temp_db_path).exists(),
                    },
                )

                assert_with_context(
                    recovered_ip == "192.168.1.2",
                    "Database recovery failed",
                    expected_ip="192.168.1.2",
                    actual_ip=recovered_ip,
                    db_path=temp_db_path,
                )

                log_test_checkpoint("Database corruption recovery successful")

            finally:
                # Cleanup
                if hasattr(self, "storage"):
                    await self.storage.close()
                if Path(temp_db_path).exists():
                    Path(temp_db_path).unlink()

                ctx.record_checkpoint("Cleanup completed")


class TestServiceHealthDegradationEnhanced:
    """Test service health degradation with enhanced diagnostics."""

    @pytest.mark.asyncio
    @with_diagnostics
    @track_service_state("service_health")
    @monitor_async_operations("service_degradation", timeout=45.0)
    async def test_service_degradation_recovery_enhanced(
        self, bot_with_network_mocking
    ):
        """Test service health degradation and recovery with diagnostics."""
        log_test_start("test_service_degradation_recovery_enhanced")

        # bot = bot_with_network_mocking  # Not needed for this test

        async with DiagnosticContext("service_degradation_test") as ctx:
            # Reset service health to normal
            service_health.reset()

            ctx.record_checkpoint(
                "Service health reset",
                {"initial_health": service_health.get_current_health()},
            )

            # Record multiple failures to trigger degradation
            log_test_checkpoint("Triggering service degradation")
            for i in range(5):
                service_health.record_failure(
                    "ip_service", f"Failure {i + 1}", "api_check"
                )
                ctx.record_checkpoint(
                    f"Failure {i + 1} recorded",
                    {"current_health": service_health.get_current_health()},
                )

            # Check that service health is degraded
            current_health = service_health.get_current_health()
            log_test_checkpoint("Checking service health degradation")

            assert_with_context(
                current_health != "NORMAL",
                "Service health should be degraded",
                expected_health="degraded",
                actual_health=current_health,
                failure_count=5,
            )

            ctx.record_checkpoint(
                "Service degradation confirmed", {"degraded_health": current_health}
            )

            # Record successes to trigger recovery
            log_test_checkpoint("Triggering service recovery")
            for i in range(10):
                service_health.record_success("ip_service", "api_check")
                ctx.record_checkpoint(
                    f"Success {i + 1} recorded",
                    {"current_health": service_health.get_current_health()},
                )

            # Check that service health is recovered
            recovered_health = service_health.get_current_health()
            log_test_checkpoint("Checking service health recovery")

            ctx.record_checkpoint(
                "Service recovery attempt completed",
                {"recovered_health": recovered_health},
            )

            assert_with_context(
                recovered_health in ["NORMAL", "MINOR"],
                "Service health should be recovered",
                expected_health="NORMAL or MINOR",
                actual_health=recovered_health,
                success_count=10,
            )

            log_test_checkpoint("Service health recovery successful")
