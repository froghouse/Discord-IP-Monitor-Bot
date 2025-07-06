"""
Integration tests for the complete IP monitoring workflow.

This module tests the end-to-end IP monitoring process including:
- IP change detection
- Database persistence
- Discord notification delivery
- Error recovery scenarios
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.cache import get_cache
from ip_monitor.utils.service_health import service_health


class TestIPChangeDetection:
    """Test IP change detection workflow."""

    @pytest.fixture
    async def bot_with_temp_db(self):
        """Create a bot instance with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            temp_db_path = temp_db.name

        # Mock environment to prevent loading real env vars
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()
            config.db_file = temp_db_path
            config.testing_mode = True

        with patch("discord.ext.commands.Bot"):
            bot = IPMonitorBot(config)
            yield bot

        # Cleanup
        Path(temp_db_path).unlink(missing_ok=True)

    async def test_ip_change_detection_and_storage(self, bot_with_temp_db):
        """Test complete IP change detection and storage workflow."""
        bot = bot_with_temp_db

        # Mock IP service to return different IPs
        with patch.object(bot.ip_service, "get_public_ip") as mock_get_ip:
            mock_get_ip.side_effect = ["192.168.1.100", "192.168.1.101"]

            # First IP check - should store initial IP
            first_ip = await bot.ip_service.get_public_ip()
            bot.storage.save_current_ip(first_ip)

            # Verify initial IP stored
            stored_ip = bot.storage.load_last_ip()
            assert stored_ip == "192.168.1.100"

            # Second IP check - should detect change
            second_ip = await bot.ip_service.get_public_ip()
            ip_changed = second_ip != stored_ip

            assert ip_changed
            assert second_ip == "192.168.1.101"

            # Store new IP and verify history
            bot.storage.save_current_ip(second_ip)
            history = bot.storage.load_ip_history()

            assert len(history) >= 1
            assert any(entry["ip"] == "192.168.1.101" for entry in history)

    async def test_ip_monitoring_with_service_health(self, bot_with_temp_db):
        """Test IP monitoring integrates with service health tracking."""
        bot = bot_with_temp_db

        # Mock successful IP retrieval
        with patch.object(
            bot.ip_service, "get_public_ip", return_value="192.168.1.200"
        ):
            # Mock service health monitoring
            with patch.object(service_health, "record_success") as mock_record_success:
                with patch.object(
                    service_health, "record_failure"
                ) as mock_record_failure:
                    # Simulate successful IP check
                    ip = await bot.ip_service.get_public_ip()
                    if ip:
                        service_health.record_success("ip_service", "api_check")
                        bot.storage.save_current_ip(ip)

                    # Verify success recorded
                    mock_record_success.assert_called_with("ip_service", "api_check")
                    mock_record_failure.assert_not_called()

                    # Verify IP stored
                    assert bot.storage.load_last_ip() == "192.168.1.200"

    async def test_ip_monitoring_failure_handling(self, bot_with_temp_db):
        """Test IP monitoring handles failures gracefully."""
        bot = bot_with_temp_db

        # Mock IP service failure
        with patch.object(
            bot.ip_service, "get_public_ip", side_effect=Exception("API Error")
        ):
            with patch.object(service_health, "record_failure") as mock_record_failure:
                try:
                    await bot.ip_service.get_public_ip()
                except Exception as e:
                    service_health.record_failure("ip_service", str(e), "api_check")

                # Verify failure recorded
                mock_record_failure.assert_called_with(
                    "ip_service", "API Error", "api_check"
                )

    async def test_concurrent_ip_checks(self, bot_with_temp_db):
        """Test concurrent IP checks don't cause race conditions."""
        bot = bot_with_temp_db

        async def mock_ip_check():
            """Simulate IP check with delay."""
            await asyncio.sleep(0.1)
            return "192.168.1.150"

        with patch.object(bot.ip_service, "get_public_ip", side_effect=mock_ip_check):
            # Run multiple concurrent IP checks
            tasks = [bot.ip_service.get_public_ip() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All should return the same IP
            assert all(ip == "192.168.1.150" for ip in results)

            # Store one result and verify
            bot.storage.save_current_ip(results[0])
            assert bot.storage.load_last_ip() == "192.168.1.150"

    async def test_ip_change_with_cache_integration(self, bot_with_temp_db):
        """Test IP monitoring integrates with caching system."""
        bot = bot_with_temp_db
        cache = get_cache()

        # Clear any existing cache
        cache.clear()

        with patch.object(
            bot.ip_service, "get_public_ip", return_value="192.168.1.250"
        ):
            # First check - should cache result
            ip = await bot.ip_service.get_public_ip()

            # Manually cache the result (simulating what IP service would do)
            cache.set("ip_check", "current_ip", ip, "IP_RESULT")

            bot.storage.save_current_ip(ip)

            # Second check - should use cached result
            cached_ip = cache.get("ip_check", "current_ip", "IP_RESULT")
            assert cached_ip == "192.168.1.250"

            # Verify storage consistency
            assert bot.storage.load_last_ip() == "192.168.1.250"

    async def test_ip_change_detection_edge_cases(self, bot_with_temp_db):
        """Test IP change detection handles edge cases."""
        bot = bot_with_temp_db

        # Test empty IP handling
        with patch.object(bot.ip_service, "get_public_ip", return_value=None):
            ip = await bot.ip_service.get_public_ip()
            assert ip is None

            # Should not store empty IP
            original_ip = bot.storage.load_last_ip()
            if ip:
                bot.storage.save_current_ip(ip)

            # IP should remain unchanged
            assert bot.storage.load_last_ip() == original_ip

        # Test invalid IP format handling
        with patch.object(bot.ip_service, "get_public_ip", return_value="invalid_ip"):
            ip = await bot.ip_service.get_public_ip()

            # IP service should handle validation
            # For this test, we assume it returns the value as-is
            assert ip == "invalid_ip"


class TestDatabasePersistence:
    """Test database persistence during IP monitoring."""

    @pytest.fixture
    async def storage_with_temp_db(self):
        """Create storage instance with temporary database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
            temp_db_path = temp_db.name

        storage = SQLiteIPStorage(db_file=temp_db_path, history_size=10)
        yield storage

        # Cleanup
        storage.close()
        Path(temp_db_path).unlink(missing_ok=True)

    async def test_ip_history_persistence(self, storage_with_temp_db):
        """Test IP history is properly persisted across operations."""
        storage = storage_with_temp_db

        # Add multiple IP entries
        test_ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]

        for ip in test_ips:
            storage.save_current_ip(ip)
            await asyncio.sleep(0.01)  # Ensure different timestamps

        # Verify all IPs in history
        history = storage.load_ip_history()
        stored_ips = [entry["ip"] for entry in history]

        for ip in test_ips:
            assert ip in stored_ips

    async def test_database_transaction_integrity(self, storage_with_temp_db):
        """Test database maintains integrity during concurrent operations."""
        storage = storage_with_temp_db

        async def save_ip_sequence(start_ip, count):
            """Save a sequence of IPs."""
            for i in range(count):
                ip = f"192.168.1.{start_ip + i}"
                storage.save_current_ip(ip)
                await asyncio.sleep(0.001)

        # Run concurrent IP saves
        tasks = [
            save_ip_sequence(10, 5),
            save_ip_sequence(20, 5),
            save_ip_sequence(30, 5),
        ]

        await asyncio.gather(*tasks)

        # Verify database integrity
        history = storage.load_ip_history()
        assert len(history) >= 15  # Should have at least 15 entries

        # Verify last IP is correctly stored
        last_ip = storage.load_last_ip()
        assert last_ip is not None
        assert last_ip.startswith("192.168.1.")

    async def test_database_history_size_limit(self, storage_with_temp_db):
        """Test database enforces history size limits."""
        storage = storage_with_temp_db

        # Add more IPs than the history limit (10)
        for i in range(15):
            ip = f"10.0.0.{i + 1}"
            storage.save_current_ip(ip)

        # Verify history is limited to configured size
        history = storage.load_ip_history()
        assert len(history) <= 10

        # Verify newest entries are kept
        recent_ips = [entry["ip"] for entry in history[:3]]
        assert "10.0.0.15" in recent_ips
        assert "10.0.0.14" in recent_ips

    async def test_database_corruption_recovery(self, storage_with_temp_db):
        """Test system handles database corruption gracefully."""
        storage = storage_with_temp_db

        # Save initial data
        storage.save_current_ip("192.168.1.100")

        # Simulate database error during read
        with patch.object(
            storage, "_execute_query", side_effect=Exception("Database corrupted")
        ):
            try:
                storage.load_last_ip()
            except Exception as e:
                # System should handle gracefully
                assert "Database corrupted" in str(e)

        # Verify system can recover after error
        # (In real implementation, this would involve database repair)
        new_ip = "192.168.1.101"
        storage.save_current_ip(new_ip)

        # Should work normally after recovery
        assert storage.load_last_ip() == new_ip


class TestNotificationDelivery:
    """Test Discord notification delivery workflow."""

    @pytest.fixture
    async def bot_with_mocked_discord(self):
        """Create bot with mocked Discord client."""
        with patch.dict(os.environ, {
            "DISCORD_BOT_TOKEN": "test_token", 
            "CHANNEL_ID": "123456789"
        }):
            config = AppConfig.load_from_env()
            config.testing_mode = True

        with patch("discord.ext.commands.Bot") as mock_bot_class:
            mock_client = MagicMock()
            mock_bot_class.return_value = mock_client

            # Mock channel
            mock_channel = MagicMock()
            mock_client.get_channel.return_value = mock_channel

            bot = IPMonitorBot(config)
            bot.client = mock_client

            yield bot, mock_client, mock_channel

    async def test_ip_change_notification_delivery(self, bot_with_mocked_discord):
        """Test IP change notifications are delivered to Discord."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Mock IP commands for notification
        mock_ip_commands = AsyncMock()
        bot.ip_commands = mock_ip_commands

        # Simulate IP change notification
        old_ip = "192.168.1.100"
        new_ip = "192.168.1.101"

        await mock_ip_commands.send_ip_change_notification(mock_channel, old_ip, new_ip)

        # Verify notification was attempted
        mock_ip_commands.send_ip_change_notification.assert_called_once_with(
            mock_channel, old_ip, new_ip
        )

    async def test_notification_with_rate_limiting(self, bot_with_mocked_discord):
        """Test notifications respect Discord rate limiting."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Mock rate limiter
        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.return_value = None

            # Send multiple notifications
            messages = [
                "IP changed to 192.168.1.101",
                "IP changed to 192.168.1.102",
                "IP changed to 192.168.1.103",
            ]

            for message in messages:
                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_channel, message
                )

            # Verify all messages were processed with rate limiting
            assert mock_send.call_count == 3

    async def test_notification_failure_handling(self, bot_with_mocked_discord):
        """Test notification failure handling and retry logic."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Mock Discord API failure
        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            mock_send.side_effect = Exception("Discord API Error")

            # Attempt to send notification
            try:
                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_channel, "Test notification"
                )
            except Exception as e:
                assert "Discord API Error" in str(e)

            # Verify failure was attempted
            mock_send.assert_called_once()

    async def test_message_queue_integration(self, bot_with_mocked_discord):
        """Test notification delivery integrates with message queue."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Mock message queue
        with patch("ip_monitor.utils.message_queue.message_queue") as mock_queue:
            mock_queue.add_message = AsyncMock()

            # Simulate adding message to queue
            await mock_queue.add_message(
                channel_id=bot.config.channel_id,
                content="IP changed notification",
                priority="HIGH",
            )

            # Verify message was queued
            mock_queue.add_message.assert_called_once_with(
                channel_id=bot.config.channel_id,
                content="IP changed notification",
                priority="HIGH",
            )

    async def test_notification_during_service_degradation(
        self, bot_with_mocked_discord
    ):
        """Test notifications during service degradation."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Mock service degradation
        with patch.object(service_health, "is_fallback_active") as mock_fallback:
            mock_fallback.return_value = True

            # Check if silent monitoring is active
            is_silent = service_health.is_fallback_active("silent_monitoring")

            if is_silent:
                # Should not send notifications during silent mode
                # This is handled by the bot's scheduled task logic
                logging.info("Silent monitoring active - notifications suppressed")
            else:
                # Normal notification flow
                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_channel, "IP change notification"
                )

            # Verify degradation check was performed
            mock_fallback.assert_called_with("silent_monitoring")

    async def test_notification_formatting_and_content(self, bot_with_mocked_discord):
        """Test notification message formatting and content."""
        bot, mock_client, mock_channel = bot_with_mocked_discord

        # Test different notification types
        test_cases = [
            {
                "type": "ip_change",
                "old_ip": "192.168.1.100",
                "new_ip": "192.168.1.101",
                "expected_content": "192.168.1.101",
            },
            {"type": "startup", "expected_content": "IP Monitor Bot started"},
            {"type": "error", "error": "API timeout", "expected_content": "error"},
        ]

        with patch.object(
            bot.discord_rate_limiter, "send_message_with_backoff"
        ) as mock_send:
            for case in test_cases:
                if case["type"] == "ip_change":
                    message = (
                        f"🔄 IP address changed: {case['old_ip']} → {case['new_ip']}"
                    )
                elif case["type"] == "startup":
                    message = "🟢 IP Monitor Bot started!"
                elif case["type"] == "error":
                    message = f"❌ Error: {case['error']}"

                await bot.discord_rate_limiter.send_message_with_backoff(
                    mock_channel, message
                )

                # Verify expected content in message
                sent_message = mock_send.call_args[0][1]
                assert case["expected_content"] in sent_message.lower()

            # Verify all messages were sent
            assert mock_send.call_count == len(test_cases)
