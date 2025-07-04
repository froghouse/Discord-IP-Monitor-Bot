"""
Slash command implementations for admin commands.
"""

import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage

logger = logging.getLogger(__name__)


class AdminSlashCommands(commands.Cog):
    """
    Admin slash command implementations.
    """

    def __init__(
        self,
        bot: commands.Bot,
        ip_service: IPService,
        storage: SQLiteIPStorage,
        stop_callback,
        config: AppConfig,
        admin_commands_handler,
    ) -> None:
        """
        Initialize the admin slash commands.

        Args:
            bot: Discord bot instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback function to stop the bot
            config: Application configuration
            admin_commands_handler: Existing admin commands handler for reusing logic
        """
        self.bot = bot
        self.ip_service = ip_service
        self.storage = storage
        self.stop_callback = stop_callback
        self.config = config
        self.admin_commands_handler = admin_commands_handler

    def check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """
        Check if the user has administrator permissions.

        Args:
            interaction: Discord interaction object

        Returns:
            bool: True if user has admin permissions
        """
        return interaction.user.guild_permissions.administrator

    @app_commands.command(name="stop", description="Gracefully shutdown the bot")
    async def stop_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command to stop the bot (admin only).
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                "🛑 Shutting down the bot gracefully...",
                ephemeral=True,
            )

            logger.info(
                f"Bot shutdown requested by {interaction.user} via slash command"
            )
            await self.stop_callback()

        except Exception as e:
            logger.error(f"Error in stop slash command: {e}")
            try:
                await interaction.response.send_message(
                    "❌ An error occurred while stopping the bot.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                pass

    # Config command group
    config_group = app_commands.Group(
        name="config", description="Manage bot configuration"
    )

    @config_group.command(name="show", description="Show current configuration")
    @app_commands.describe(field="Specific configuration field to show (optional)")
    async def config_show_slash(
        self, interaction: discord.Interaction, field: str | None = None
    ) -> None:
        """
        Show current configuration.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    if field:
                        self.content = f"!config show {field}"
                    else:
                        self.content = "!config show"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            config_handler = self.admin_commands_handler.get_handler_for_command(
                "config"
            )
            if config_handler:
                result = await config_handler._handle_config_show(mock_message, field)
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "Configuration displayed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to display configuration.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in config show slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while showing configuration.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @config_group.command(name="set", description="Update a configuration field")
    @app_commands.describe(
        field="Configuration field to update",
        value="New value for the configuration field",
    )
    async def config_set_slash(
        self, interaction: discord.Interaction, field: str, value: str
    ) -> None:
        """
        Update a configuration field.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, field, value):
                    self.author = user
                    self.channel = channel
                    self.content = f"!config set {field} {value}"

            mock_message = MockMessage(
                interaction.user, interaction.channel, field, value
            )

            # Use existing logic through the router
            config_handler = self.admin_commands_handler.get_handler_for_command(
                "config"
            )
            if config_handler:
                result = await config_handler._handle_config_set(
                    mock_message, field, value
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    f"✅ Configuration updated: `{field}` = `{value}`", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to update configuration field `{field}`.",
                    ephemeral=True,
                )

        except Exception as e:
            logger.error(f"Error in config set slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while updating configuration.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @config_group.command(name="list", description="List all configurable fields")
    async def config_list_slash(self, interaction: discord.Interaction) -> None:
        """
        List all configurable fields.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!config list"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            config_handler = self.admin_commands_handler.get_handler_for_command(
                "config"
            )
            if config_handler:
                result = await config_handler._handle_config_list(mock_message)
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "Configuration fields listed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to list configuration fields.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in config list slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while listing configuration fields.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @config_group.command(name="save", description="Save current configuration to file")
    async def config_save_slash(self, interaction: discord.Interaction) -> None:
        """
        Save current configuration to file.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!config save"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            config_handler = self.admin_commands_handler.get_handler_for_command(
                "config"
            )
            if config_handler:
                result = await config_handler._handle_config_save(mock_message)
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "✅ Configuration saved to file successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to save configuration to file.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in config save slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while saving configuration.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @config_group.command(name="reload", description="Reload configuration from file")
    async def config_reload_slash(self, interaction: discord.Interaction) -> None:
        """
        Reload configuration from file.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!config reload"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            config_handler = self.admin_commands_handler.get_handler_for_command(
                "config"
            )
            if config_handler:
                result = await config_handler._handle_config_reload(mock_message)
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "✅ Configuration reloaded from file successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to reload configuration from file.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in config reload slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while reloading configuration.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    # API command group
    api_group = app_commands.Group(name="api", description="Manage IP detection APIs")

    @api_group.command(name="list", description="List all configured IP APIs")
    async def api_list_slash(self, interaction: discord.Interaction) -> None:
        """
        List all configured IP APIs.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!api list"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                result = await api_handler.handle_command(mock_message, ["api", "list"])
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "API list displayed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to display API list.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in api list slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while listing APIs.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @api_group.command(name="add", description="Add a new IP detection API")
    @app_commands.describe(
        name="Name for the API",
        url="URL of the API endpoint",
        format="Response format (json, text, auto)",
        field="JSON field name for IP (if format is json)",
    )
    async def api_add_slash(
        self,
        interaction: discord.Interaction,
        name: str,
        url: str,
        format: Literal["json", "text", "auto"] | None = "auto",
        field: str | None = None,
    ) -> None:
        """
        Add a new IP detection API.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, name, url, format_type, field):
                    self.author = user
                    self.channel = channel
                    content_parts = [f"!api add {name} {url}"]
                    if format_type and format_type != "auto":
                        content_parts.append(format_type)
                    if field:
                        content_parts.append(field)
                    self.content = " ".join(content_parts)

            mock_message = MockMessage(
                interaction.user, interaction.channel, name, url, format, field
            )

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                args = ["api", "add", name, url]
                if format and format != "auto":
                    args.append(format)
                if field:
                    args.append(field)
                result = await api_handler.handle_command(mock_message, args)
            else:
                result = False

            if result:
                await interaction.followup.send(
                    f"✅ API `{name}` added successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to add API `{name}`.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in api add slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while adding the API.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @api_group.command(name="remove", description="Remove an IP detection API")
    @app_commands.describe(api_id="ID or name of the API to remove")
    async def api_remove_slash(
        self, interaction: discord.Interaction, api_id: str
    ) -> None:
        """
        Remove an IP detection API.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, api_id):
                    self.author = user
                    self.channel = channel
                    self.content = f"!api remove {api_id}"

            mock_message = MockMessage(interaction.user, interaction.channel, api_id)

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                result = await api_handler.handle_command(
                    mock_message, ["api", "remove", api_id]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    f"✅ API `{api_id}` removed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to remove API `{api_id}`.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in api remove slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while removing the API.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @api_group.command(
        name="toggle", description="Enable or disable an IP detection API"
    )
    @app_commands.describe(
        api_id="ID or name of the API to toggle",
        action="Whether to enable or disable the API",
    )
    async def api_toggle_slash(
        self,
        interaction: discord.Interaction,
        api_id: str,
        action: Literal["enable", "disable"],
    ) -> None:
        """
        Enable or disable an IP detection API.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, action, api_id):
                    self.author = user
                    self.channel = channel
                    self.content = f"!api {action} {api_id}"

            mock_message = MockMessage(
                interaction.user, interaction.channel, action, api_id
            )

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                result = await api_handler.handle_command(
                    mock_message, ["api", action, api_id]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    f"✅ API `{api_id}` {action}d successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ Failed to {action} API `{api_id}`.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in api toggle slash command: {e}")
            try:
                await interaction.followup.send(
                    f"❌ An error occurred while {action}ing the API.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @api_group.command(name="test", description="Test an IP detection API")
    @app_commands.describe(api_id="ID or name of the API to test")
    async def api_test_slash(
        self, interaction: discord.Interaction, api_id: str
    ) -> None:
        """
        Test an IP detection API.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, api_id):
                    self.author = user
                    self.channel = channel
                    self.content = f"!api test {api_id}"

            mock_message = MockMessage(interaction.user, interaction.channel, api_id)

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                result = await api_handler.handle_command(
                    mock_message, ["api", "test", api_id]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "API test completed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send("❌ API test failed.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in api test slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while testing the API.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @api_group.command(name="stats", description="Show API performance statistics")
    async def api_stats_slash(self, interaction: discord.Interaction) -> None:
        """
        Show API performance statistics.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!api stats"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            api_handler = self.admin_commands_handler.get_handler_for_command("api")
            if api_handler:
                result = await api_handler.handle_command(
                    mock_message, ["api", "stats"]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "API statistics displayed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to display API statistics.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in api stats slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while displaying API statistics.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    # Cache command group
    cache_group = app_commands.Group(
        name="cache", description="Manage intelligent caching"
    )

    @cache_group.command(name="show", description="Show cache status and statistics")
    async def cache_show_slash(self, interaction: discord.Interaction) -> None:
        """
        Show cache status and statistics.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!cache show"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            cache_handler = self.admin_commands_handler.get_handler_for_command("cache")
            if cache_handler:
                result = await cache_handler.handle_command(
                    mock_message, ["cache", "show"]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "Cache status displayed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to display cache status.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in cache show slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while showing cache status.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @cache_group.command(name="clear", description="Clear cache entries")
    @app_commands.describe(namespace="Specific namespace to clear (optional)")
    async def cache_clear_slash(
        self, interaction: discord.Interaction, namespace: str | None = None
    ) -> None:
        """
        Clear cache entries.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel, namespace):
                    self.author = user
                    self.channel = channel
                    if namespace:
                        self.content = f"!cache clear {namespace}"
                    else:
                        self.content = "!cache clear"

            mock_message = MockMessage(interaction.user, interaction.channel, namespace)

            # Use existing logic through the router
            cache_handler = self.admin_commands_handler.get_handler_for_command("cache")
            if cache_handler:
                args = ["cache", "clear"]
                if namespace:
                    args.append(namespace)
                result = await cache_handler.handle_command(mock_message, args)
            else:
                result = False

            if result:
                if namespace:
                    await interaction.followup.send(
                        f"✅ Cache namespace `{namespace}` cleared successfully.",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        "✅ All cache entries cleared successfully.", ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "❌ Failed to clear cache entries.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in cache clear slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while clearing cache entries.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    # Queue command group
    queue_group = app_commands.Group(name="queue", description="Manage message queue")

    @queue_group.command(name="status", description="Show message queue status")
    async def queue_status_slash(self, interaction: discord.Interaction) -> None:
        """
        Show message queue status.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!queue"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            queue_handler = self.admin_commands_handler.get_handler_for_command("queue")
            if queue_handler:
                result = await queue_handler.handle_command(mock_message, ["queue"])
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "Queue status displayed successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to display queue status.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in queue status slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while displaying queue status.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @queue_group.command(name="clear", description="Clear all queued messages")
    async def queue_clear_slash(self, interaction: discord.Interaction) -> None:
        """
        Clear all queued messages.
        """
        try:
            if not self.check_admin_permissions(interaction):
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Create a mock message object for the existing handler
            class MockMessage:
                def __init__(self, user, channel):
                    self.author = user
                    self.channel = channel
                    self.content = "!queue clear"

            mock_message = MockMessage(interaction.user, interaction.channel)

            # Use existing logic through the router
            queue_handler = self.admin_commands_handler.get_handler_for_command("queue")
            if queue_handler:
                result = await queue_handler.handle_command(
                    mock_message, ["queue", "clear"]
                )
            else:
                result = False

            if result:
                await interaction.followup.send(
                    "✅ Message queue cleared successfully.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Failed to clear message queue.", ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in queue clear slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while clearing the message queue.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass


async def setup(bot: commands.Bot) -> None:
    """Setup function to add this cog to the bot."""
    # This will be called when the cog is loaded
