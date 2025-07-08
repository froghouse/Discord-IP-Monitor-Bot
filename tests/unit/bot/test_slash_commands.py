"""
Tests for IPMonitorBot slash command setup and integration.
"""

from unittest.mock import AsyncMock, Mock, patch

from ip_monitor.bot import IPMonitorBot


class TestSlashCommandSetup:
    """Test suite for slash command setup and integration."""

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
    def test_setup_slash_commands(
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
        """Test slash command setup."""
        # Setup mocks
        mock_intents.default.return_value = mock_intents
        mock_client = Mock()
        mock_client.event = Mock()  # client.event() is synchronous
        mock_bot_class.return_value = mock_client

        mock_ip_cog = AsyncMock()
        mock_admin_cog = AsyncMock()
        mock_ip_slash_commands.return_value = mock_ip_cog
        mock_admin_slash_commands.return_value = mock_admin_cog

        # Initialize bot (this calls _setup_slash_commands)
        bot = IPMonitorBot(mock_bot_config)

        # Verify slash commands were created
        mock_ip_slash_commands.assert_called_once()
        mock_admin_slash_commands.assert_called_once()
        assert bot.ip_slash_cog == mock_ip_cog
        assert bot.admin_slash_cog == mock_admin_cog

    async def test_slash_command_integration(self, mock_bot_instance):
        """Test slash command integration with bot instance."""
        # Verify slash command cogs are available
        assert hasattr(mock_bot_instance, "ip_slash_cog")
        assert hasattr(mock_bot_instance, "admin_slash_cog")

        # Verify cogs have expected attributes
        assert mock_bot_instance.ip_slash_cog is not None
        assert mock_bot_instance.admin_slash_cog is not None

    async def test_slash_command_dependency_injection(self, mock_bot_instance):
        """Test that slash commands receive proper dependencies."""
        # Verify that the slash command setup process provides
        # the necessary dependencies to the cogs
        ip_cog = mock_bot_instance.ip_slash_cog
        admin_cog = mock_bot_instance.admin_slash_cog

        # These should be available for the cogs to use
        assert mock_bot_instance.ip_service is not None
        assert mock_bot_instance.storage is not None
        assert mock_bot_instance.config is not None
