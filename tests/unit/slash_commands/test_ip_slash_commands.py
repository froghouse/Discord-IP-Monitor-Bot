"""
Tests for IP slash commands functionality.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from ip_monitor.slash_commands.ip_slash_commands import IPSlashCommands


class TestIPSlashCommands:
    """Tests for IP slash commands initialization and setup."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.user = MagicMock()
        bot.user.id = 12345
        return bot

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        service = MagicMock()
        service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        service.max_retries = 3
        service.use_concurrent_checks = True
        service.get_circuit_breaker_info = MagicMock(
            return_value={
                "enabled": True,
                "state": "closed",
                "last_known_ip": "203.0.113.1",
            }
        )
        service.get_cache_info = MagicMock(
            return_value={
                "enabled": True,
                "stats": {
                    "hit_rate": 0.75,
                    "memory_entries": 10,
                    "memory_usage_mb": 0.5,
                },
                "stale_entries_count": 2,
            }
        )
        return service

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        storage = MagicMock()
        storage.load_last_ip = MagicMock(return_value="203.0.113.0")
        storage.save_current_ip = MagicMock(return_value=True)
        storage.load_ip_history = MagicMock(
            return_value=[
                {"ip": "203.0.113.0", "timestamp": "2024-01-01T12:00:00"},
                {"ip": "203.0.113.1", "timestamp": "2024-01-01T13:00:00"},
            ]
        )
        return storage

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.is_limited = AsyncMock(return_value=(False, 0))
        limiter.get_remaining_calls = AsyncMock(return_value=8)
        limiter.max_calls = 10
        return limiter

    @pytest.fixture
    def mock_ip_commands_handler(self):
        """Create a mock IP commands handler."""
        handler = MagicMock()
        handler.check_interval = 30
        return handler

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.id = 98765
        interaction.user.name = "TestUser"
        interaction.channel = MagicMock()
        interaction.channel.id = 123456789
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def ip_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Create an IP slash commands instance."""
        return IPSlashCommands(
            bot=mock_bot,
            channel_id=123456789,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
            ip_commands_handler=mock_ip_commands_handler,
        )

    def test_initialization(
        self,
        ip_slash_commands,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Test IP slash commands initialization."""
        assert ip_slash_commands.bot == mock_bot
        assert ip_slash_commands.channel_id == 123456789
        assert ip_slash_commands.ip_service == mock_ip_service
        assert ip_slash_commands.storage == mock_storage
        assert ip_slash_commands.rate_limiter == mock_rate_limiter
        assert ip_slash_commands.ip_commands_handler == mock_ip_commands_handler


class TestIPSlashCommand:
    """Tests for the /ip slash command."""

    @pytest.fixture
    def ip_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Create an IP slash commands instance."""
        return IPSlashCommands(
            bot=mock_bot,
            channel_id=123456789,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
            ip_commands_handler=mock_ip_commands_handler,
        )

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        service = MagicMock()
        service.get_public_ip = AsyncMock(return_value="203.0.113.1")
        return service

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        storage = MagicMock()
        storage.load_last_ip = MagicMock(return_value="203.0.113.0")
        storage.save_current_ip = MagicMock(return_value=True)
        return storage

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.is_limited = AsyncMock(return_value=(False, 0))
        return limiter

    @pytest.fixture
    def mock_ip_commands_handler(self):
        """Create a mock IP commands handler."""
        return MagicMock()

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "TestUser"
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_ip_slash_success_with_ip_change(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test successful IP check with IP change."""
        mock_service_health.is_fallback_active.return_value = False

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.response.defer.assert_called_once()
        ip_slash_commands.rate_limiter.is_limited.assert_called_once()
        ip_slash_commands.ip_service.get_public_ip.assert_called_once()
        ip_slash_commands.storage.save_current_ip.assert_called_once_with("203.0.113.1")

        # Check that the success message was sent
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "✅ IP address check complete" in call_args
        assert "203.0.113.1" in call_args
        assert "🔄 **IP has changed**" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_ip_slash_success_no_ip_change(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test successful IP check with no IP change."""
        mock_service_health.is_fallback_active.return_value = False
        ip_slash_commands.ip_service.get_public_ip.return_value = "203.0.113.0"

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "✅ IP address check complete" in call_args
        assert "203.0.113.0" in call_args
        assert "No change from previous IP" in call_args

    async def test_ip_slash_rate_limited(self, ip_slash_commands, mock_interaction):
        """Test IP slash command when rate limited."""
        ip_slash_commands.rate_limiter.is_limited.return_value = (True, 30)

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "⚠️ Rate limit reached" in call_args
        assert "30 seconds" in call_args

        # Should not call IP service when rate limited
        ip_slash_commands.ip_service.get_public_ip.assert_not_called()

    async def test_ip_slash_service_failure(self, ip_slash_commands, mock_interaction):
        """Test IP slash command when service fails."""
        ip_slash_commands.ip_service.get_public_ip.return_value = None

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ Failed to retrieve the current IP address" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_ip_slash_storage_failure(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test IP slash command when storage fails."""
        mock_service_health.is_fallback_active.return_value = False
        ip_slash_commands.storage.save_current_ip.return_value = False

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ Failed to save the current IP address" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_ip_slash_readonly_mode(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test IP slash command in read-only mode."""
        mock_service_health.is_fallback_active.return_value = True

        await ip_slash_commands.ip_slash(mock_interaction)

        # Should not save IP in read-only mode
        ip_slash_commands.storage.save_current_ip.assert_not_called()

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "✅ IP address check complete" in call_args

    async def test_ip_slash_exception_handling(
        self, ip_slash_commands, mock_interaction
    ):
        """Test IP slash command exception handling."""
        ip_slash_commands.rate_limiter.is_limited.side_effect = Exception("Test error")

        await ip_slash_commands.ip_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ An error occurred while checking the IP address" in call_args

    async def test_ip_slash_interaction_expired(
        self, ip_slash_commands, mock_interaction
    ):
        """Test IP slash command when interaction expires."""
        ip_slash_commands.rate_limiter.is_limited.side_effect = Exception("Test error")
        mock_interaction.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await ip_slash_commands.ip_slash(mock_interaction)


class TestHistorySlashCommand:
    """Tests for the /history slash command."""

    @pytest.fixture
    def ip_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Create an IP slash commands instance."""
        return IPSlashCommands(
            bot=mock_bot,
            channel_id=123456789,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
            ip_commands_handler=mock_ip_commands_handler,
        )

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        return MagicMock()

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        storage = MagicMock()
        storage.load_ip_history = MagicMock(
            return_value=[
                {"ip": "203.0.113.0", "timestamp": "2024-01-01T12:00:00"},
                {"ip": "203.0.113.1", "timestamp": "2024-01-01T13:00:00"},
            ]
        )
        return storage

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        return MagicMock()

    @pytest.fixture
    def mock_ip_commands_handler(self):
        """Create a mock IP commands handler."""
        return MagicMock()

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "TestUser"
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    async def test_history_slash_success(self, ip_slash_commands, mock_interaction):
        """Test successful history retrieval."""
        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.response.defer.assert_called_once()
        ip_slash_commands.storage.load_ip_history.assert_called_once()

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "📜 **IP Address History**" in call_args
        assert "203.0.113.0" in call_args
        assert "203.0.113.1" in call_args

    async def test_history_slash_no_history(self, ip_slash_commands, mock_interaction):
        """Test history slash command with no history."""
        ip_slash_commands.storage.load_ip_history.return_value = []

        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "No IP history available" in call_args

    async def test_history_slash_large_history(
        self, ip_slash_commands, mock_interaction
    ):
        """Test history slash command with large history (truncation)."""
        # Create a large history that will exceed message length
        large_history = []
        for i in range(50):
            large_history.append(
                {"ip": f"203.0.113.{i}", "timestamp": f"2024-01-{i + 1:02d}T12:00:00"}
            )

        ip_slash_commands.storage.load_ip_history.return_value = large_history

        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "📜 **IP Address History**" in call_args
        assert "... and" in call_args and "more entries" in call_args

    async def test_history_slash_invalid_timestamp(
        self, ip_slash_commands, mock_interaction
    ):
        """Test history slash command with invalid timestamp."""
        ip_slash_commands.storage.load_ip_history.return_value = [
            {"ip": "203.0.113.0", "timestamp": "invalid-timestamp"}
        ]

        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "203.0.113.0" in call_args
        assert "invalid-timestamp" in call_args

    async def test_history_slash_missing_fields(
        self, ip_slash_commands, mock_interaction
    ):
        """Test history slash command with missing fields."""
        ip_slash_commands.storage.load_ip_history.return_value = [
            {"ip": "203.0.113.0"},  # Missing timestamp
            {"timestamp": "2024-01-01T12:00:00"},  # Missing IP
        ]

        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "Unknown" in call_args

    async def test_history_slash_exception_handling(
        self, ip_slash_commands, mock_interaction
    ):
        """Test history slash command exception handling."""
        ip_slash_commands.storage.load_ip_history.side_effect = Exception("Test error")

        await ip_slash_commands.history_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ An error occurred while retrieving IP history" in call_args

    async def test_history_slash_interaction_expired(
        self, ip_slash_commands, mock_interaction
    ):
        """Test history slash command when interaction expires."""
        ip_slash_commands.storage.load_ip_history.side_effect = Exception("Test error")
        mock_interaction.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await ip_slash_commands.history_slash(mock_interaction)


class TestStatusSlashCommand:
    """Tests for the /status slash command."""

    @pytest.fixture
    def ip_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Create an IP slash commands instance."""
        return IPSlashCommands(
            bot=mock_bot,
            channel_id=123456789,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
            ip_commands_handler=mock_ip_commands_handler,
        )

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        service = MagicMock()
        service.max_retries = 3
        service.use_concurrent_checks = True
        service.get_circuit_breaker_info = MagicMock(
            return_value={
                "enabled": True,
                "state": "closed",
                "last_known_ip": "203.0.113.1",
            }
        )
        service.get_cache_info = MagicMock(
            return_value={
                "enabled": True,
                "stats": {
                    "hit_rate": 0.75,
                    "memory_entries": 10,
                    "memory_usage_mb": 0.5,
                },
                "stale_entries_count": 2,
            }
        )
        return service

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        storage = MagicMock()
        storage.load_last_ip = MagicMock(return_value="203.0.113.1")
        return storage

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        limiter = MagicMock()
        limiter.is_limited = AsyncMock(return_value=(False, 0))
        limiter.get_remaining_calls = AsyncMock(return_value=8)
        limiter.max_calls = 10
        return limiter

    @pytest.fixture
    def mock_ip_commands_handler(self):
        """Create a mock IP commands handler."""
        handler = MagicMock()
        handler.check_interval = 30
        return handler

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "TestUser"
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_success(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test successful status retrieval."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {"ip_service": {"status": "healthy"}},
            "system_capabilities": {"active_fallbacks": []},
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "📊 **IP Monitor Bot Status**" in call_args
        assert "Every 30 minutes" in call_args
        assert "3" in call_args  # max_retries
        assert "Enabled" in call_args  # concurrent checking
        assert "8/10" in call_args  # rate limit
        assert "🟢 Circuit breaker: CLOSED" in call_args
        assert "🗄️ Cache: Enabled" in call_args
        assert "75.0% hit rate" in call_args
        assert "203.0.113.1" in call_args  # current IP
        assert "✅ System Health: NORMAL" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_degraded_system(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status with degraded system health."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "severe",
            "services": {
                "ip_service": {"status": "failed"},
                "discord_api": {"status": "degraded"},
            },
            "system_capabilities": {"active_fallbacks": ["read_only_mode"]},
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "🔴 System Health: SEVERE DEGRADATION" in call_args
        assert "❌ Failed: ip_service" in call_args
        assert "⚠️ Degraded: discord_api" in call_args
        assert "🔄 Active Fallbacks: read_only_mode" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_circuit_breaker_open(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status with circuit breaker open."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {},
            "system_capabilities": {"active_fallbacks": []},
        }

        ip_slash_commands.ip_service.get_circuit_breaker_info.return_value = {
            "enabled": True,
            "state": "open",
            "time_until_half_open": 45,
            "last_known_ip": "203.0.113.1",
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "🔴 Circuit breaker: OPEN" in call_args
        assert "retry in 45s" in call_args
        assert "💾 Cached IP: `203.0.113.1`" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_circuit_breaker_disabled(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status with circuit breaker disabled."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {},
            "system_capabilities": {"active_fallbacks": []},
        }

        ip_slash_commands.ip_service.get_circuit_breaker_info.return_value = {
            "enabled": False,
            "state": "closed",
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "⚪ Circuit breaker: Disabled" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_cache_disabled(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status with cache disabled."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {},
            "system_capabilities": {"active_fallbacks": []},
        }

        ip_slash_commands.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "⚪ Cache: Disabled" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_rate_limited(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status when rate limited."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {},
            "system_capabilities": {"active_fallbacks": []},
        }

        ip_slash_commands.rate_limiter.is_limited.return_value = (True, 25)

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "Limited (wait 25 seconds)" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    @patch("ip_monitor.slash_commands.ip_slash_commands.message_queue")
    async def test_status_slash_with_message_queue(
        self,
        mock_message_queue,
        mock_service_health,
        ip_slash_commands,
        mock_interaction,
    ):
        """Test status with message queue information."""
        mock_service_health.get_system_health.return_value = {
            "degradation_level": "normal",
            "services": {},
            "system_capabilities": {"active_fallbacks": []},
        }

        mock_message_queue.get_queue_status.return_value = {
            "queue_size": 5,
            "max_queue_size": 100,
            "ready_to_process": 3,
            "scheduled_for_later": 2,
            "statistics": {"total_delivered": 50, "total_failed": 2},
        }

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "📥 Message Queue: 5/100 messages" in call_args
        assert "Ready: 3, Scheduled: 2" in call_args
        assert "📊 Queue Stats: 50 sent, 2 failed" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_exception_handling(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status slash command exception handling."""
        mock_service_health.get_system_health.side_effect = Exception("Test error")

        await ip_slash_commands.status_slash(mock_interaction)

        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args[0][0]
        assert "❌ An error occurred while retrieving bot status" in call_args

    @patch("ip_monitor.slash_commands.ip_slash_commands.service_health")
    async def test_status_slash_interaction_expired(
        self, mock_service_health, ip_slash_commands, mock_interaction
    ):
        """Test status slash command when interaction expires."""
        mock_service_health.get_system_health.side_effect = Exception("Test error")
        mock_interaction.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await ip_slash_commands.status_slash(mock_interaction)


class TestHelpSlashCommand:
    """Tests for the /help slash command."""

    @pytest.fixture
    def ip_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_rate_limiter,
        mock_ip_commands_handler,
    ):
        """Create an IP slash commands instance."""
        return IPSlashCommands(
            bot=mock_bot,
            channel_id=123456789,
            ip_service=mock_ip_service,
            storage=mock_storage,
            rate_limiter=mock_rate_limiter,
            ip_commands_handler=mock_ip_commands_handler,
        )

    @pytest.fixture
    def mock_bot(self):
        """Create a mock Discord bot."""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        return MagicMock()

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        return MagicMock()

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create a mock rate limiter."""
        return MagicMock()

    @pytest.fixture
    def mock_ip_commands_handler(self):
        """Create a mock IP commands handler."""
        return MagicMock()

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "TestUser"
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_help_slash_success(self, ip_slash_commands, mock_interaction):
        """Test successful help display."""
        await ip_slash_commands.help_slash(mock_interaction)

        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args[0][0]
        assert "**IP Monitor Bot Commands**" in call_args
        assert "**User Commands:**" in call_args
        assert "/ip" in call_args
        assert "/history" in call_args
        assert "/status" in call_args
        assert "/help" in call_args
        assert "**Admin Commands:**" in call_args
        assert "/config" in call_args
        assert "/api" in call_args
        assert "/stop" in call_args

        # Check that it's sent as ephemeral
        assert mock_interaction.response.send_message.call_args[1]["ephemeral"] is True

    async def test_help_slash_exception_handling(
        self, ip_slash_commands, mock_interaction
    ):
        """Test help slash command exception handling."""
        mock_interaction.response.send_message.side_effect = Exception("Test error")

        await ip_slash_commands.help_slash(mock_interaction)

        # Should call response.send_message twice (once for help, once for error)
        assert mock_interaction.response.send_message.call_count == 2

    async def test_help_slash_interaction_already_responded(
        self, ip_slash_commands, mock_interaction
    ):
        """Test help slash command when interaction is already responded to."""
        mock_interaction.response.send_message.side_effect = [
            Exception("Test error"),
            discord.InteractionResponded(),
        ]

        # Should not raise exception
        await ip_slash_commands.help_slash(mock_interaction)
