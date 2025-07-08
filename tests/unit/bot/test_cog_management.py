"""
Tests for IPMonitorBot cog management functionality.
"""

from unittest.mock import AsyncMock, Mock, patch

import discord
from discord.ext import commands

from ip_monitor.bot import IPMonitorBot


class TestCogManagement:
    """Test suite for Discord cog management operations."""

    @patch("ip_monitor.bot.commands.Bot")
    @patch("ip_monitor.bot.discord.Intents")
    @patch("ip_monitor.bot.IPService")
    @patch("ip_monitor.bot.SQLiteIPStorage")
    @patch("ip_monitor.bot.AsyncRateLimiter")
    @patch("ip_monitor.bot.DiscordRateLimiter")
    @patch("ip_monitor.bot.IPCommands")
    @patch("ip_monitor.bot.AdminCommandRouter")
    @patch("ip_monitor.slash_commands.ip_slash_commands.IPSlashCommands")
    @patch("ip_monitor.slash_commands.admin_slash_commands.AdminSlashCommands")
    def test_cog_initialization(
        self,
        mock_admin_slash_commands,
        mock_ip_slash_commands,
        mock_admin_router,
        mock_ip_commands,
        mock_discord_rate_limiter,
        mock_async_rate_limiter,
        mock_storage,
        mock_ip_service,
        mock_intents,
        mock_bot_class,
        mock_bot_config,
    ):
        """Test that cogs are properly initialized during bot setup."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client

        mock_ip_cog = AsyncMock()
        mock_admin_cog = AsyncMock()
        mock_ip_slash_commands.return_value = mock_ip_cog
        mock_admin_slash_commands.return_value = mock_admin_cog

        # Initialize bot
        bot = IPMonitorBot(mock_bot_config)

        # Verify cogs were created with correct parameters
        mock_ip_slash_commands.assert_called_once_with(
            bot=mock_client,
            channel_id=mock_bot_config.channel_id,
            ip_service=mock_ip_service.return_value,
            storage=mock_storage.return_value,
            rate_limiter=mock_async_rate_limiter.return_value,
            ip_commands_handler=mock_ip_commands.return_value,
        )

        mock_admin_slash_commands.assert_called_once_with(
            bot=mock_client,
            ip_service=mock_ip_service.return_value,
            storage=mock_storage.return_value,
            stop_callback=bot._stop_bot,
            config=mock_bot_config,
            admin_commands_handler=mock_admin_router.return_value,
        )

        # Verify cogs are stored for later registration
        assert bot.ip_slash_cog == mock_ip_cog
        assert bot.admin_slash_cog == mock_admin_cog

    async def test_cog_registration_success(self, mock_bot_instance):
        """Test successful cog registration during on_ready."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify cogs were registered
        assert mock_bot_instance.client.add_cog.call_count == 2
        mock_bot_instance.client.add_cog.assert_any_call(mock_bot_instance.ip_slash_cog)
        mock_bot_instance.client.add_cog.assert_any_call(
            mock_bot_instance.admin_slash_cog
        )

    async def test_cog_registration_failure(self, mock_bot_instance, caplog):
        """Test handling of cog registration failures."""
        # Setup mocks to simulate registration failure
        mock_bot_instance.client.add_cog = AsyncMock(
            side_effect=Exception("Failed to register cog")
        )
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged but bot continued
        assert "Failed to register slash command cogs" in caplog.text
        # Only the first add_cog call is made before the exception
        assert mock_bot_instance.client.add_cog.call_count == 1

    async def test_slash_command_sync_success(self, mock_bot_instance):
        """Test successful slash command synchronization."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_commands = [Mock(), Mock(), Mock()]
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=mock_commands)

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify commands were synced
        mock_bot_instance.client.tree.sync.assert_called_once()

    async def test_slash_command_sync_failure(self, mock_bot_instance, caplog):
        """Test handling of slash command sync failures."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(
            side_effect=Exception("Failed to sync commands")
        )

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged but bot continued
        assert "Failed to sync slash commands" in caplog.text
        mock_bot_instance.client.tree.sync.assert_called_once()

    async def test_cog_dependencies_injection(self, mock_bot_instance):
        """Test that cogs receive proper dependency injection."""
        # Verify IP slash commands cog has access to necessary services
        ip_cog = mock_bot_instance.ip_slash_cog
        admin_cog = mock_bot_instance.admin_slash_cog

        # Check that both cogs are available
        assert ip_cog is not None
        assert admin_cog is not None

        # Verify bot instance has all required services for cog initialization
        assert mock_bot_instance.ip_service is not None
        assert mock_bot_instance.storage is not None
        assert mock_bot_instance.config is not None
        assert mock_bot_instance.rate_limiter is not None
        assert mock_bot_instance.ip_commands is not None
        assert mock_bot_instance.admin_commands is not None

    async def test_cog_cleanup_on_bot_stop(self, mock_bot_instance):
        """Test that cogs are properly cleaned up when bot stops."""
        # Setup mocks
        mock_bot_instance.client.remove_cog = AsyncMock()
        mock_bot_instance.client.close = AsyncMock()
        mock_bot_instance.client.http = Mock()
        mock_bot_instance.client.http.session = Mock()
        mock_bot_instance.client.http.session.close = AsyncMock()

        # Mock the ip_service close method
        mock_bot_instance.ip_service.close = AsyncMock()

        # Mock the check_ip_task
        mock_bot_instance.check_ip_task = Mock()
        mock_bot_instance.check_ip_task.is_running = Mock(return_value=False)

        # Mock the message queue and service health which are global imports
        from unittest.mock import patch

        with patch("ip_monitor.bot.message_queue") as mock_message_queue:
            mock_message_queue.stop_processing = AsyncMock()

            # Call cleanup
            await mock_bot_instance.cleanup()

            # Verify message queue was stopped
            mock_message_queue.stop_processing.assert_called_once()

            # Verify ip_service was closed
            mock_bot_instance.ip_service.close.assert_called_once()

            # Verify client was closed (which handles cog cleanup)
            mock_bot_instance.client.close.assert_called_once()


class TestCogErrorHandling:
    """Test error handling in cog management operations."""

    async def test_cog_registration_with_discord_exception(
        self, mock_bot_instance, caplog
    ):
        """Test handling of Discord-specific exceptions during cog registration."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock(
            side_effect=discord.HTTPException(Mock(), "HTTP error")
        )
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged
        assert "Failed to register slash command cogs" in caplog.text

    async def test_cog_registration_with_command_registration_error(
        self, mock_bot_instance, caplog
    ):
        """Test handling of command registration errors."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock(
            side_effect=commands.CommandRegistrationError("Command already exists")
        )
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged
        assert "Failed to register slash command cogs" in caplog.text

    async def test_slash_command_sync_with_forbidden_error(
        self, mock_bot_instance, caplog
    ):
        """Test handling of permission errors during command sync."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(
            side_effect=discord.Forbidden(Mock(), "Insufficient permissions")
        )

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged
        assert "Failed to sync slash commands" in caplog.text

    async def test_slash_command_sync_with_rate_limit_error(
        self, mock_bot_instance, caplog
    ):
        """Test handling of rate limit errors during command sync."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(
            side_effect=discord.HTTPException(Mock(), "Rate limited")
        )

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify error was logged
        assert "Failed to sync slash commands" in caplog.text


class TestCogLifecycle:
    """Test cog lifecycle management."""

    async def test_cog_availability_after_initialization(self, mock_bot_instance):
        """Test that cogs are available after bot initialization."""
        # Verify cogs are accessible
        assert hasattr(mock_bot_instance, "ip_slash_cog")
        assert hasattr(mock_bot_instance, "admin_slash_cog")
        assert mock_bot_instance.ip_slash_cog is not None
        assert mock_bot_instance.admin_slash_cog is not None

    async def test_cog_state_during_registration(self, mock_bot_instance):
        """Test cog state during the registration process."""
        # Setup mocks
        registration_calls = []

        def track_registration(cog):
            registration_calls.append(cog)
            return AsyncMock()

        mock_bot_instance.client.add_cog = AsyncMock(side_effect=track_registration)
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify both cogs were registered
        assert len(registration_calls) == 2
        assert mock_bot_instance.ip_slash_cog in registration_calls
        assert mock_bot_instance.admin_slash_cog in registration_calls

    async def test_cog_persistence_across_operations(self, mock_bot_instance):
        """Test that cog references persist across different operations."""
        # Get initial cog references
        initial_ip_cog = mock_bot_instance.ip_slash_cog
        initial_admin_cog = mock_bot_instance.admin_slash_cog

        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify cog references are unchanged
        assert mock_bot_instance.ip_slash_cog is initial_ip_cog
        assert mock_bot_instance.admin_slash_cog is initial_admin_cog

    async def test_cog_registration_order(self, mock_bot_instance):
        """Test that cogs are registered in the correct order."""
        # Setup mocks to track registration order
        registration_order = []

        def track_order(cog):
            if cog == mock_bot_instance.ip_slash_cog:
                registration_order.append("ip")
            elif cog == mock_bot_instance.admin_slash_cog:
                registration_order.append("admin")
            return AsyncMock()

        mock_bot_instance.client.add_cog = AsyncMock(side_effect=track_order)
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify registration order (IP commands first, then admin commands)
        assert registration_order == ["ip", "admin"]


class TestCogIntegration:
    """Test integration between cogs and bot services."""

    async def test_cog_service_integration(self, mock_bot_instance):
        """Test that cogs can access bot services properly."""
        # Verify that the bot has all necessary services for cog operations
        required_services = [
            "ip_service",
            "storage",
            "config",
            "rate_limiter",
            "ip_commands",
            "admin_commands",
        ]

        for service in required_services:
            assert hasattr(mock_bot_instance, service)
            assert getattr(mock_bot_instance, service) is not None

    async def test_cog_discord_client_integration(self, mock_bot_instance):
        """Test that cogs have proper access to Discord client."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=[])

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify that the Discord client was used for cog operations
        assert mock_bot_instance.client.add_cog.called
        assert mock_bot_instance.client.tree.sync.called

    async def test_cog_command_tree_integration(self, mock_bot_instance):
        """Test integration with Discord's command tree."""
        # Setup mocks
        mock_bot_instance.client.add_cog = AsyncMock()
        mock_commands = [Mock(name="ip"), Mock(name="history"), Mock(name="status")]
        mock_bot_instance.client.tree.sync = AsyncMock(return_value=mock_commands)

        # Call on_ready
        await mock_bot_instance.on_ready()

        # Verify command tree was synced after cog registration
        mock_bot_instance.client.tree.sync.assert_called_once()
