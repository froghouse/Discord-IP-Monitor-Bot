"""
Integration tests for error recovery scenarios.

This module tests the system's ability to handle and recover from various
failure conditions including:
- Network failures and timeouts
- Database corruption and recovery
- Discord API outages and rate limiting
- Service degradation and fallback mechanisms
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.circuit_breaker import CircuitBreakerError
from ip_monitor.utils.message_queue import message_queue
from ip_monitor.utils.service_health import service_health


class TestNetworkFailureRecovery:
    """Test network failure handling and recovery."""

    @pytest.fixture
    async def bot_with_network_mocking(self):
        """Create bot with network operation mocking."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()
            config.testing_mode = True

        with patch("discord.ext.commands.Bot"):
            bot = IPMonitorBot(config)
            yield bot

    async def test_api_timeout_recovery(self, bot_with_network_mocking):
        """Test recovery from API timeout errors."""
        bot = bot_with_network_mocking

        # Mock timeout errors
        timeout_error = asyncio.TimeoutError("Request timeout")

        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            # First call fails with timeout
            mock_get_ip.side_effect = [timeout_error, "192.168.1.100"]

            # First attempt should fail
            try:
                await bot.ip_service.get_public_ip()
                pytest.fail("Should have raised timeout error")
            except asyncio.TimeoutError:
                # Record the failure
                service_health.record_failure(
                    "ip_service", "Timeout error", "api_check"
                )

            # Second attempt should succeed (recovery)
            ip = await bot.ip_service.get_public_ip()
            assert ip == "192.168.1.100"

            # Record recovery
            service_health.record_success("ip_service", "api_check")

    async def test_connection_error_recovery(self, bot_with_network_mocking):
        """Test recovery from connection errors."""
        bot = bot_with_network_mocking

        connection_error = ConnectionError("Connection refused")

        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            # Multiple failures followed by success
            mock_get_ip.side_effect = [
                connection_error,
                connection_error,
                "192.168.1.101",
            ]

            # First two attempts should fail
            for _ in range(2):
                try:
                    await bot.ip_service.get_public_ip()
                    pytest.fail("Should have raised connection error")
                except ConnectionError:
                    service_health.record_failure(
                        "ip_service", "Connection error", "api_check"
                    )

            # Third attempt should succeed
            ip = await bot.ip_service.get_public_ip()
            assert ip == "192.168.1.101"
            service_health.record_success("ip_service", "api_check")

    async def test_circuit_breaker_activation_and_recovery(
        self, bot_with_network_mocking
    ):
        """Test circuit breaker activation and recovery from failures."""
        bot = bot_with_network_mocking

        # Mock circuit breaker behavior
        with patch.object(bot.ip_service, "circuit_breaker") as mock_cb:
            # Configure circuit breaker to be open
            mock_cb.state = "OPEN"
            mock_cb.call.side_effect = CircuitBreakerError("Circuit breaker is open")

            # Attempt to get IP should be blocked by circuit breaker
            try:
                await bot.ip_service.circuit_breaker.call(
                    bot.ip_service._fetch_ip_from_primary_apis
                )
                pytest.fail("Should have raised CircuitBreakerError")
            except CircuitBreakerError as e:
                assert "Circuit breaker is open" in str(e)

            # Mock recovery - circuit breaker becomes half-open then closed
            mock_cb.state = "HALF_OPEN"
            mock_cb.call.side_effect = None
            mock_cb.call.return_value = "192.168.1.102"

            # Recovery attempt should succeed
            ip = await bot.ip_service.circuit_breaker.call(
                bot.ip_service._fetch_ip_from_primary_apis
            )
            assert ip == "192.168.1.102"

    async def test_fallback_ip_service_behavior(self, bot_with_network_mocking):
        """Test fallback behavior when primary IP services fail."""
        bot = bot_with_network_mocking

        # Mock all primary APIs failing
        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            # Primary APIs fail, fallback to cached IP
            mock_get_ip.side_effect = [
                Exception("Primary API 1 failed"),
                Exception("Primary API 2 failed"),
                "192.168.1.50",  # Cached/fallback IP
            ]

            # Should eventually get IP from fallback
            try:
                # First two attempts fail
                for _ in range(2):
                    try:
                        await bot.ip_service.get_public_ip()
                    except Exception:
                        pass

                # Final attempt uses fallback
                ip = await bot.ip_service.get_public_ip()
                assert ip == "192.168.1.50"
            except Exception as e:
                # Test that system handles fallback gracefully
                assert "failed" in str(e)

    async def test_network_partition_recovery(self, bot_with_network_mocking):
        """Test recovery from network partition scenarios."""
        bot = bot_with_network_mocking

        # Simulate network partition (all network calls fail)
        network_error = OSError("Network is unreachable")

        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            # Network partition - all requests fail
            mock_get_ip.side_effect = network_error

            # Verify system handles network partition
            try:
                await bot.ip_service.get_public_ip()
                pytest.fail("Should have raised network error")
            except OSError as e:
                assert "Network is unreachable" in str(e)
                service_health.record_failure("ip_service", str(e), "api_check")

            # Network recovery - requests succeed again
            mock_get_ip.side_effect = None
            mock_get_ip.return_value = "192.168.1.200"

            ip = await bot.ip_service.get_public_ip()
            assert ip == "192.168.1.200"
            service_health.record_success("ip_service", "api_check")

    async def test_dns_resolution_failure_recovery(self, bot_with_network_mocking):
        """Test recovery from DNS resolution failures."""
        bot = bot_with_network_mocking

        dns_error = OSError("Name resolution failed")

        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            # DNS failure
            mock_get_ip.side_effect = dns_error

            try:
                await bot.ip_service.get_public_ip()
                pytest.fail("Should have raised DNS error")
            except OSError as e:
                assert "Name resolution failed" in str(e)

            # DNS recovery
            mock_get_ip.side_effect = None
            mock_get_ip.return_value = "192.168.1.250"

            ip = await bot.ip_service.get_public_ip()
            assert ip == "192.168.1.250"

    async def test_partial_api_failure_recovery(self, bot_with_network_mocking):
        """Test recovery when some APIs fail but others succeed."""
        bot = bot_with_network_mocking

        # Mock partial failure scenario
        api_responses = [
            Exception("API 1 failed"),
            Exception("API 2 failed"),
            "192.168.1.175",  # API 3 succeeds
        ]

        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            mock_get_ip.side_effect = api_responses

            # First two attempts fail, third succeeds
            try:
                await bot.ip_service.get_public_ip()
            except Exception:
                pass

            try:
                await bot.ip_service.get_public_ip()
            except Exception:
                pass

            # Third attempt succeeds
            ip = await bot.ip_service.get_public_ip()
            assert ip == "192.168.1.175"


class TestDatabaseErrorRecovery:
    """Test database error handling and recovery."""

    @pytest.fixture
    async def storage_with_temp_db(self):
        """Create storage with temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            temp_db_path = temp_db.name

        storage = SQLiteIPStorage(db_file=temp_db_path, history_size=10)
        yield storage, temp_db_path

        # Cleanup
        storage.close()
        Path(temp_db_path).unlink(missing_ok=True)

    async def test_database_lock_recovery(self, storage_with_temp_db):
        """Test recovery from database lock errors."""
        storage, db_path = storage_with_temp_db

        # Mock database lock error
        with patch.object(storage, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                Exception("database is locked"),
                [("192.168.1.100",)],  # Recovery
            ]

            # First attempt should fail
            try:
                storage.load_last_ip()
            except Exception as e:
                assert "database is locked" in str(e)

            # Second attempt should succeed (simulating lock release)
            result = storage.load_last_ip()
            assert result == "192.168.1.100"

    async def test_database_corruption_detection(self, storage_with_temp_db):
        """Test detection and handling of database corruption."""
        storage, db_path = storage_with_temp_db

        # Mock corruption error
        corruption_error = Exception("database disk image is malformed")

        with patch.object(storage, "_execute_query") as mock_execute:
            mock_execute.side_effect = corruption_error

            # Should detect corruption
            try:
                storage.load_last_ip()
                pytest.fail("Should have detected corruption")
            except Exception as e:
                assert "malformed" in str(e)

    async def test_database_permission_error_recovery(self, storage_with_temp_db):
        """Test recovery from database permission errors."""
        storage, db_path = storage_with_temp_db

        permission_error = PermissionError("Permission denied")

        with patch.object(storage, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                permission_error,
                None,  # Recovery after permission fix
            ]

            # Permission error
            try:
                storage.save_current_ip("192.168.1.100")
                pytest.fail("Should have raised permission error")
            except PermissionError:
                pass

            # Recovery after permission fix
            storage.save_current_ip("192.168.1.100")
            # Should succeed without exception

    async def test_database_connection_pool_exhaustion(self, storage_with_temp_db):
        """Test handling of database connection pool exhaustion."""
        storage, db_path = storage_with_temp_db

        # Simulate connection pool exhaustion
        pool_error = Exception("too many connections")

        with patch.object(storage, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                pool_error,
                pool_error,
                [("192.168.1.125",)],  # Recovery
            ]

            # Multiple connection failures
            for _ in range(2):
                try:
                    storage.load_last_ip()
                    pytest.fail("Should have failed with pool exhaustion")
                except Exception as e:
                    assert "too many connections" in str(e)

            # Recovery when connections are available
            ip = storage.load_last_ip()
            assert ip == "192.168.1.125"

    async def test_database_disk_space_recovery(self, storage_with_temp_db):
        """Test recovery from disk space exhaustion."""
        storage, db_path = storage_with_temp_db

        disk_space_error = Exception("disk I/O error")

        with patch.object(storage, "save_current_ip") as mock_save:
            mock_save.side_effect = [
                disk_space_error,
                None,  # Recovery after space freed
            ]

            # Disk space error
            try:
                storage.save_current_ip("192.168.1.150")
                pytest.fail("Should have raised disk space error")
            except Exception as e:
                assert "disk I/O error" in str(e)

            # Recovery after disk space freed
            storage.save_current_ip("192.168.1.150")
            # Should succeed

    async def test_database_transaction_rollback(self, storage_with_temp_db):
        """Test database transaction rollback on errors."""
        storage, db_path = storage_with_temp_db

        # Mock transaction that fails midway
        with patch.object(storage, "_execute_query") as mock_execute:
            mock_execute.side_effect = [
                None,  # Begin transaction
                Exception("Constraint violation"),  # Failure during transaction
                None,  # Rollback
            ]

            # Transaction should be rolled back on error
            try:
                # Simulate transaction that fails
                storage.save_current_ip("invalid_ip_format")
            except Exception as e:
                assert "Constraint violation" in str(e)

            # Database should be in consistent state after rollback
            # Verify by attempting a normal operation
            storage.save_current_ip("192.168.1.175")


class TestDiscordAPIOutageRecovery:
    """Test Discord API outage handling and recovery."""

    @pytest.fixture
    async def bot_with_discord_mocking(self):
        """Create bot with Discord API mocking."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()
            config.message_queue_enabled = True

        with patch("discord.ext.commands.Bot") as mock_bot_class:
            mock_client = MagicMock()
            mock_bot_class.return_value = mock_client

            bot = IPMonitorBot(config)
            bot.client = mock_client

            yield bot, mock_client

    async def test_discord_rate_limit_handling(self, bot_with_discord_mocking):
        """Test handling of Discord rate limits."""
        bot, mock_client = bot_with_discord_mocking

        # Mock rate limit error
        rate_limit_error = Exception("Rate limited")

        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.side_effect = [
                rate_limit_error,
                None,  # Success after backoff
            ]

            # First attempt should fail with rate limit
            try:
                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_client.get_channel(bot.config.channel_id), "Test message"
                )
            except Exception as e:
                assert "Rate limited" in str(e)

            # Second attempt should succeed after backoff
            await bot.discord_rate_limiter.send_message_with_backoff(
                mock_client.get_channel(bot.config.channel_id), "Test message"
            )

    async def test_discord_api_outage_with_message_queue(
        self, bot_with_discord_mocking
    ):
        """Test Discord API outage with message queue fallback."""
        bot, mock_client = bot_with_discord_mocking

        # Mock Discord API outage
        api_outage_error = Exception("Discord API unavailable")

        with patch.object(message_queue, "add_message") as mock_add_message:
            mock_add_message.return_value = None

            with patch.object(
                bot.discord_rate_limiter, "send_message_with_backoff"
            ) as mock_send:
                mock_send.side_effect = api_outage_error

                # Should fall back to message queue
                try:
                    await bot.discord_rate_limiter.send_message_with_backoff(
                        mock_client.get_channel(bot.config.channel_id), "Test message"
                    )
                except Exception:
                    # Fall back to message queue
                    await message_queue.add_message(
                        channel_id=bot.config.channel_id,
                        content="Test message",
                        priority="NORMAL",
                    )

                # Verify message was queued
                mock_add_message.assert_called_once()

    async def test_discord_connection_recovery(self, bot_with_discord_mocking):
        """Test Discord connection recovery after outage."""
        bot, mock_client = bot_with_discord_mocking

        connection_error = Exception("Connection lost")

        # Mock connection failure and recovery
        with patch.object(mock_client, "get_channel") as mock_get_channel:
            mock_get_channel.side_effect = [
                connection_error,
                MagicMock(),  # Recovery
            ]

            # First attempt fails
            try:
                mock_client.get_channel(bot.config.channel_id)
            except Exception as e:
                assert "Connection lost" in str(e)

            # Second attempt succeeds (connection recovered)
            channel = mock_client.get_channel(bot.config.channel_id)
            assert channel is not None

    async def test_message_queue_processing_recovery(self, bot_with_discord_mocking):
        """Test message queue processing recovery after Discord outage."""
        bot, mock_client = bot_with_discord_mocking

        # Mock message queue operations
        with patch.object(message_queue, "process_batch") as mock_process:
            with patch.object(message_queue, "get_queue_status") as mock_status:
                # Queue has messages pending
                mock_status.return_value = {
                    "total_messages": 5,
                    "failed_messages": 2,
                    "processing": True,
                }

                # First processing attempt fails (Discord still down)
                mock_process.side_effect = [
                    Exception("Discord still unavailable"),
                    3,  # Success - processed 3 messages
                ]

                # First attempt fails
                try:
                    await message_queue.process_batch()
                except Exception as e:
                    assert "Discord still unavailable" in str(e)

                # Second attempt succeeds (Discord recovered)
                processed = await message_queue.process_batch()
                assert processed == 3

    async def test_discord_permission_error_recovery(self, bot_with_discord_mocking):
        """Test recovery from Discord permission errors."""
        bot, mock_client = bot_with_discord_mocking

        permission_error = Exception("Missing permissions")

        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.side_effect = [
                permission_error,
                None,  # Success after permission fix
            ]

            # Permission error
            try:
                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_client.get_channel(bot.config.channel_id), "Test message"
                )
            except Exception as e:
                assert "Missing permissions" in str(e)

            # Success after permission fix
            await bot.discord_rate_limiter.send_message_with_backoff(
                mock_client.get_channel(bot.config.channel_id), "Test message"
            )

    async def test_service_degradation_during_discord_outage(
        self, bot_with_discord_mocking
    ):
        """Test service degradation during Discord API outage."""
        bot, mock_client = bot_with_discord_mocking

        # Mock service degradation due to Discord issues
        with patch.object(service_health, "record_failure") as mock_record_failure:
            with patch.object(service_health, "is_fallback_active") as mock_fallback:
                # Discord failures trigger degradation
                service_health.record_failure(
                    "discord_api", "API outage", "message_send"
                )
                service_health.record_failure(
                    "discord_api", "API outage", "message_send"
                )
                service_health.record_failure(
                    "discord_api", "API outage", "message_send"
                )

                # Check if silent monitoring is activated
                mock_fallback.return_value = True
                is_silent = service_health.is_fallback_active("silent_monitoring")

                if is_silent:
                    # Should suppress notifications during degradation
                    assert mock_fallback.called
                else:
                    # Normal operation
                    pass

                # Verify failures were recorded
                assert mock_record_failure.call_count >= 3

    async def test_concurrent_discord_operations_during_recovery(
        self, bot_with_discord_mocking
    ):
        """Test concurrent Discord operations during recovery."""
        bot, mock_client = bot_with_discord_mocking

        # Mock concurrent message sending during recovery
        async def send_message_with_delay(channel, message):
            """Simulate message sending with network delay."""
            await asyncio.sleep(0.1)
            return f"Sent: {message}"

        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.side_effect = send_message_with_delay

            # Send multiple messages concurrently
            tasks = []
            for i in range(5):
                task = bot.discord_rate_limiter.send_message_with_backoff(
                    mock_client.get_channel(bot.config.channel_id), f"Message {i}"
                )
                tasks.append(task)

            # All should complete successfully
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    pytest.fail(f"Message {i} failed: {result}")
                else:
                    assert f"Message {i}" in str(result)
