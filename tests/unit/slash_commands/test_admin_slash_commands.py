"""
Tests for admin slash commands functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord.ext import commands

from ip_monitor.slash_commands.admin_slash_commands import AdminSlashCommands


class TestAdminSlashCommands:
    """Tests for admin slash commands initialization and setup."""

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
        return MagicMock()

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage."""
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        handler = MagicMock()
        handler.get_handler_for_command = MagicMock()
        return handler

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
        )

    def test_initialization(
        self,
        admin_slash_commands,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Test admin slash commands initialization."""
        assert admin_slash_commands.bot == mock_bot
        assert admin_slash_commands.ip_service == mock_ip_service
        assert admin_slash_commands.storage == mock_storage
        assert admin_slash_commands.config == mock_config
        assert (
            admin_slash_commands.admin_commands_handler == mock_admin_commands_handler
        )
        assert callable(admin_slash_commands.stop_callback)

    def test_check_admin_permissions_true(self, admin_slash_commands):
        """Test admin permission check with administrator permissions."""
        interaction = MagicMock()
        interaction.user.guild_permissions.administrator = True

        result = admin_slash_commands.check_admin_permissions(interaction)
        assert result is True

    def test_check_admin_permissions_false(self, admin_slash_commands):
        """Test admin permission check without administrator permissions."""
        interaction = MagicMock()
        interaction.user.guild_permissions.administrator = False

        result = admin_slash_commands.check_admin_permissions(interaction)
        assert result is False


class TestStopSlashCommand:
    """Tests for the /stop slash command."""

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
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
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        return MagicMock()

    @pytest.fixture
    def mock_interaction_admin(self):
        """Create a mock Discord interaction with admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "AdminUser"
        interaction.user.guild_permissions.administrator = True
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_interaction_non_admin(self):
        """Create a mock Discord interaction without admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "NonAdminUser"
        interaction.user.guild_permissions.administrator = False
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_stop_slash_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful bot stop command."""
        await admin_slash_commands.stop_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_admin.response.send_message.call_args[0][0]
        assert "🛑 Shutting down the bot gracefully" in call_args

        # Check that ephemeral is True
        assert (
            mock_interaction_admin.response.send_message.call_args[1]["ephemeral"]
            is True
        )

        # Check that stop callback was called
        admin_slash_commands.stop_callback.assert_called_once()

    async def test_stop_slash_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test stop command with insufficient permissions."""
        await admin_slash_commands.stop_slash.callback(admin_slash_commands, mock_interaction_non_admin)

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

        # Stop callback should not be called
        admin_slash_commands.stop_callback.assert_not_called()

    async def test_stop_slash_exception_handling(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test stop command exception handling."""
        admin_slash_commands.stop_callback.side_effect = Exception("Test error")

        await admin_slash_commands.stop_slash.callback(admin_slash_commands, mock_interaction_admin)

        # Should send error message
        assert mock_interaction_admin.response.send_message.call_count == 2

    async def test_stop_slash_interaction_already_responded(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test stop command when interaction is already responded to."""
        admin_slash_commands.stop_callback.side_effect = Exception("Test error")
        mock_interaction_admin.response.send_message.side_effect = [
            None,  # First call succeeds
            discord.InteractionResponded(mock_interaction_admin),  # Second call fails
        ]

        # Should not raise exception
        await admin_slash_commands.stop_slash.callback(admin_slash_commands, mock_interaction_admin)


class TestConfigSlashCommands:
    """Tests for the /config slash command group."""

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
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
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        handler = MagicMock()
        mock_config_handler = MagicMock()
        mock_config_handler._handle_config_show = AsyncMock(return_value=True)
        mock_config_handler._handle_config_set = AsyncMock(return_value=True)
        mock_config_handler._handle_config_list = AsyncMock(return_value=True)
        mock_config_handler._handle_config_save = AsyncMock(return_value=True)
        mock_config_handler._handle_config_reload = AsyncMock(return_value=True)
        handler.get_handler_for_command.return_value = mock_config_handler
        return handler

    @pytest.fixture
    def mock_interaction_admin(self):
        """Create a mock Discord interaction with admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "AdminUser"
        interaction.user.guild_permissions.administrator = True
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_interaction_non_admin(self):
        """Create a mock Discord interaction without admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "NonAdminUser"
        interaction.user.guild_permissions.administrator = False
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_config_show_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful config show command."""
        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_admin, None)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "Configuration displayed successfully" in call_args

    async def test_config_show_with_field(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config show command with specific field."""
        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "check_interval"
        )

        config_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command(
                "config"
            )
        )
        config_handler._handle_config_show.assert_called_once()

        # Check that the mock message contains the field
        call_args = config_handler._handle_config_show.call_args[0]
        mock_message = call_args[0]
        assert "!config show check_interval" in mock_message.content

    async def test_config_show_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test config show command with insufficient permissions."""
        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_non_admin, None)

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

    async def test_config_show_handler_failure(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config show command when handler fails."""
        config_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command(
                "config"
            )
        )
        config_handler._handle_config_show.return_value = False

        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_admin, None)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display configuration" in call_args

    async def test_config_show_no_handler(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config show command when no handler is found."""
        admin_slash_commands.admin_commands_handler.get_handler_for_command.return_value = None

        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_admin, None)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display configuration" in call_args

    async def test_config_set_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful config set command."""
        await admin_slash_commands.config_set_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "check_interval", "60"
        )

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ Configuration updated: `check_interval` = `60`" in call_args

    async def test_config_set_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test config set command with insufficient permissions."""
        await admin_slash_commands.config_set_slash.callback(admin_slash_commands, 
            mock_interaction_non_admin, "field", "value"
        )

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

    async def test_config_set_handler_failure(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config set command when handler fails."""
        config_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command(
                "config"
            )
        )
        config_handler._handle_config_set.return_value = False

        await admin_slash_commands.config_set_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "field", "value"
        )

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to update configuration field `field`" in call_args

    async def test_config_list_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful config list command."""
        await admin_slash_commands.config_list_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "Configuration fields listed successfully" in call_args

    async def test_config_save_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful config save command."""
        await admin_slash_commands.config_save_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ Configuration saved to file successfully" in call_args

    async def test_config_reload_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful config reload command."""
        await admin_slash_commands.config_reload_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ Configuration reloaded from file successfully" in call_args

    async def test_config_exception_handling(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config command exception handling."""
        config_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command(
                "config"
            )
        )
        config_handler._handle_config_show.side_effect = Exception("Test error")

        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_admin, None)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ An error occurred while showing configuration" in call_args

    async def test_config_interaction_expired(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test config command when interaction expires."""
        config_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command(
                "config"
            )
        )
        config_handler._handle_config_show.side_effect = Exception("Test error")
        mock_interaction_admin.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await admin_slash_commands.config_show_slash.callback(admin_slash_commands, mock_interaction_admin, None)


class TestAPISlashCommands:
    """Tests for the /api slash command group."""

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
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
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        handler = MagicMock()
        mock_api_handler = MagicMock()
        mock_api_handler.handle_command = AsyncMock(return_value=True)
        handler.get_handler_for_command.return_value = mock_api_handler
        return handler

    @pytest.fixture
    def mock_interaction_admin(self):
        """Create a mock Discord interaction with admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "AdminUser"
        interaction.user.guild_permissions.administrator = True
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_interaction_non_admin(self):
        """Create a mock Discord interaction without admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "NonAdminUser"
        interaction.user.guild_permissions.administrator = False
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_api_list_success(self, admin_slash_commands, mock_interaction_admin):
        """Test successful API list command."""
        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "API list displayed successfully" in call_args

    async def test_api_list_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test API list command with insufficient permissions."""
        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_non_admin)

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

    async def test_api_add_success(self, admin_slash_commands, mock_interaction_admin):
        """Test successful API add command."""
        await admin_slash_commands.api_add_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "TestAPI", "https://test.example.com", "json", "ip"
        )

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ API `TestAPI` added successfully" in call_args

        # Check that handler was called with correct arguments
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        api_handler.handle_command.assert_called_once()
        call_args = api_handler.handle_command.call_args[0][1]
        assert call_args == [
            "api",
            "add",
            "TestAPI",
            "https://test.example.com",
            "json",
            "ip",
        ]

    async def test_api_add_auto_format(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test API add command with auto format."""
        await admin_slash_commands.api_add_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "TestAPI", "https://test.example.com", "auto", None
        )

        # Check that handler was called without format when auto
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        call_args = api_handler.handle_command.call_args[0][1]
        assert call_args == ["api", "add", "TestAPI", "https://test.example.com"]

    async def test_api_add_text_format(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test API add command with text format."""
        await admin_slash_commands.api_add_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "TestAPI", "https://test.example.com", "text", None
        )

        # Check that handler was called with text format
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        call_args = api_handler.handle_command.call_args[0][1]
        assert call_args == [
            "api",
            "add",
            "TestAPI",
            "https://test.example.com",
            "text",
        ]

    async def test_api_remove_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful API remove command."""
        await admin_slash_commands.api_remove_slash.callback(admin_slash_commands, mock_interaction_admin, "test_api")

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ API `test_api` removed successfully" in call_args

    async def test_api_toggle_enable_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful API enable command."""
        await admin_slash_commands.api_toggle_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "test_api", "enable"
        )

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ API `test_api` enabled successfully" in call_args

    async def test_api_toggle_disable_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful API disable command."""
        await admin_slash_commands.api_toggle_slash.callback(admin_slash_commands, 
            mock_interaction_admin, "test_api", "disable"
        )

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ API `test_api` disabled successfully" in call_args

    async def test_api_test_success(self, admin_slash_commands, mock_interaction_admin):
        """Test successful API test command."""
        await admin_slash_commands.api_test_slash.callback(admin_slash_commands, mock_interaction_admin, "test_api")

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "API test completed successfully" in call_args

    async def test_api_stats_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful API stats command."""
        await admin_slash_commands.api_stats_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "API statistics displayed successfully" in call_args

    async def test_api_handler_failure(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test API command when handler fails."""
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        api_handler.handle_command.return_value = False

        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display API list" in call_args

    async def test_api_no_handler(self, admin_slash_commands, mock_interaction_admin):
        """Test API command when no handler is found."""
        admin_slash_commands.admin_commands_handler.get_handler_for_command.return_value = None

        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display API list" in call_args

    async def test_api_exception_handling(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test API command exception handling."""
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        api_handler.handle_command.side_effect = Exception("Test error")

        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ An error occurred while listing APIs" in call_args

    async def test_api_interaction_expired(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test API command when interaction expires."""
        api_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("api")
        )
        api_handler.handle_command.side_effect = Exception("Test error")
        mock_interaction_admin.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await admin_slash_commands.api_list_slash.callback(admin_slash_commands, mock_interaction_admin)


class TestCacheSlashCommands:
    """Tests for the /cache slash command group."""

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
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
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        handler = MagicMock()
        mock_cache_handler = MagicMock()
        mock_cache_handler.handle_command = AsyncMock(return_value=True)
        handler.get_handler_for_command.return_value = mock_cache_handler
        return handler

    @pytest.fixture
    def mock_interaction_admin(self):
        """Create a mock Discord interaction with admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "AdminUser"
        interaction.user.guild_permissions.administrator = True
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_interaction_non_admin(self):
        """Create a mock Discord interaction without admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "NonAdminUser"
        interaction.user.guild_permissions.administrator = False
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_cache_show_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful cache show command."""
        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "Cache status displayed successfully" in call_args

    async def test_cache_show_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test cache show command with insufficient permissions."""
        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_non_admin)

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

    async def test_cache_clear_all_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful cache clear all command."""
        await admin_slash_commands.cache_clear_slash.callback(admin_slash_commands, mock_interaction_admin, None)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ All cache entries cleared successfully" in call_args

        # Check that handler was called with correct arguments
        cache_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("cache")
        )
        cache_handler.handle_command.assert_called_once()
        call_args = cache_handler.handle_command.call_args[0][1]
        assert call_args == ["cache", "clear"]

    async def test_cache_clear_namespace_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful cache clear namespace command."""
        await admin_slash_commands.cache_clear_slash.callback(admin_slash_commands, mock_interaction_admin, "ip_check")

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ Cache namespace `ip_check` cleared successfully" in call_args

        # Check that handler was called with correct arguments
        cache_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("cache")
        )
        cache_handler.handle_command.assert_called_once()
        call_args = cache_handler.handle_command.call_args[0][1]
        assert call_args == ["cache", "clear", "ip_check"]

    async def test_cache_handler_failure(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test cache command when handler fails."""
        cache_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("cache")
        )
        cache_handler.handle_command.return_value = False

        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display cache status" in call_args

    async def test_cache_no_handler(self, admin_slash_commands, mock_interaction_admin):
        """Test cache command when no handler is found."""
        admin_slash_commands.admin_commands_handler.get_handler_for_command.return_value = None

        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display cache status" in call_args

    async def test_cache_exception_handling(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test cache command exception handling."""
        cache_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("cache")
        )
        cache_handler.handle_command.side_effect = Exception("Test error")

        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ An error occurred while showing cache status" in call_args

    async def test_cache_interaction_expired(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test cache command when interaction expires."""
        cache_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("cache")
        )
        cache_handler.handle_command.side_effect = Exception("Test error")
        mock_interaction_admin.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await admin_slash_commands.cache_show_slash.callback(admin_slash_commands, mock_interaction_admin)


class TestQueueSlashCommands:
    """Tests for the /queue slash command group."""

    @pytest.fixture
    def admin_slash_commands(
        self,
        mock_bot,
        mock_ip_service,
        mock_storage,
        mock_config,
        mock_admin_commands_handler,
    ):
        """Create an admin slash commands instance."""
        return AdminSlashCommands(
            bot=mock_bot,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=AsyncMock(),
            config=mock_config,
            admin_commands_handler=mock_admin_commands_handler,
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
    def mock_config(self):
        """Create a mock config."""
        return MagicMock()

    @pytest.fixture
    def mock_admin_commands_handler(self):
        """Create a mock admin commands handler."""
        handler = MagicMock()
        mock_queue_handler = MagicMock()
        mock_queue_handler.handle_command = AsyncMock(return_value=True)
        handler.get_handler_for_command.return_value = mock_queue_handler
        return handler

    @pytest.fixture
    def mock_interaction_admin(self):
        """Create a mock Discord interaction with admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "AdminUser"
        interaction.user.guild_permissions.administrator = True
        interaction.channel = MagicMock()
        interaction.response = MagicMock()
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = MagicMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def mock_interaction_non_admin(self):
        """Create a mock Discord interaction without admin permissions."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "NonAdminUser"
        interaction.user.guild_permissions.administrator = False
        interaction.response = MagicMock()
        interaction.response.send_message = AsyncMock()
        return interaction

    async def test_queue_status_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful queue status command."""
        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "Queue status displayed successfully" in call_args

        # Check that handler was called with correct arguments
        queue_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("queue")
        )
        queue_handler.handle_command.assert_called_once()
        call_args = queue_handler.handle_command.call_args[0][1]
        assert call_args == ["queue"]

    async def test_queue_status_permission_denied(
        self, admin_slash_commands, mock_interaction_non_admin
    ):
        """Test queue status command with insufficient permissions."""
        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_non_admin)

        mock_interaction_non_admin.response.send_message.assert_called_once()
        call_args = mock_interaction_non_admin.response.send_message.call_args[0][0]
        assert "❌ You need administrator permissions" in call_args

    async def test_queue_clear_success(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test successful queue clear command."""
        await admin_slash_commands.queue_clear_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.response.defer.assert_called_once_with(ephemeral=True)
        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "✅ Message queue cleared successfully" in call_args

        # Check that handler was called with correct arguments
        queue_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("queue")
        )
        queue_handler.handle_command.assert_called_once()
        call_args = queue_handler.handle_command.call_args[0][1]
        assert call_args == ["queue", "clear"]

    async def test_queue_handler_failure(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test queue command when handler fails."""
        queue_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("queue")
        )
        queue_handler.handle_command.return_value = False

        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display queue status" in call_args

    async def test_queue_no_handler(self, admin_slash_commands, mock_interaction_admin):
        """Test queue command when no handler is found."""
        admin_slash_commands.admin_commands_handler.get_handler_for_command.return_value = None

        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ Failed to display queue status" in call_args

    async def test_queue_exception_handling(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test queue command exception handling."""
        queue_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("queue")
        )
        queue_handler.handle_command.side_effect = Exception("Test error")

        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_admin)

        mock_interaction_admin.followup.send.assert_called_once()
        call_args = mock_interaction_admin.followup.send.call_args[0][0]
        assert "❌ An error occurred while displaying queue status" in call_args

    async def test_queue_interaction_expired(
        self, admin_slash_commands, mock_interaction_admin
    ):
        """Test queue command when interaction expires."""
        queue_handler = (
            admin_slash_commands.admin_commands_handler.get_handler_for_command("queue")
        )
        queue_handler.handle_command.side_effect = Exception("Test error")
        mock_interaction_admin.followup.send.side_effect = discord.NotFound(
            MagicMock(), "Interaction not found"
        )

        # Should not raise exception
        await admin_slash_commands.queue_status_slash.callback(admin_slash_commands, mock_interaction_admin)
