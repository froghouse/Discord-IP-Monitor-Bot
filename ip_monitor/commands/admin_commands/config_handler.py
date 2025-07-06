"""
Configuration handler for admin commands.
"""

import logging
from collections.abc import Callable, Coroutine
from typing import Any

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.message_queue import message_queue

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class ConfigHandler(BaseHandler):
    """
    Handles configuration-related admin commands.
    """

    def __init__(
        self,
        client: discord.Client,
        ip_service: IPService,
        storage: IPStorage | SQLiteIPStorage,
        stop_callback: Callable[[], Coroutine[Any, Any, None]],
        config: AppConfig,
    ) -> None:
        """
        Initialize the configuration handler.

        Args:
            client: Discord client instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback to stop the bot
            config: Application configuration
        """
        super().__init__(client, ip_service, storage, stop_callback, config)

    async def handle_command(self, message: discord.Message, args: list[str]) -> bool:
        """
        Handle configuration commands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        if not args:
            return False

        command = args[0].lower()

        if command == "config":
            return await self._handle_config_command(message, args[1:])

        return False

    async def _handle_config_command(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !config command and its subcommands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments (excluding 'config')

        Returns:
            bool: True if handled successfully
        """
        # Check admin permissions
        if not self.check_admin_permissions(message):
            await self.send_permission_denied(message)
            return False

        self.log_command_usage(message, "config")

        if not args:
            # Show help for config commands
            help_text = self._get_config_help_text()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        subcommand = args[0].lower()

        try:
            if subcommand == "show":
                field = args[1] if len(args) > 1 else None
                return await self._handle_config_show(message, field)
            if subcommand == "set":
                if len(args) < 3:
                    await self.send_error_message(
                        message, "Usage: !config set <field> <value>"
                    )
                    return False
                field = args[1]
                value = " ".join(args[2:])
                return await self._handle_config_set(message, field, value)
            if subcommand == "list":
                return await self._handle_config_list(message)
            if subcommand == "save":
                return await self._handle_config_save(message)
            if subcommand == "reload":
                return await self._handle_config_reload(message)
            await self.send_error_message(
                message, f"Unknown config subcommand: {subcommand}"
            )
            return False
        except Exception as e:
            await self.handle_command_error(message, e, f"config {subcommand}")
            return False

    async def _handle_config_show(
        self, message: discord.Message, field: str = None
    ) -> bool:
        """
        Handle the !config show [field] command.

        Args:
            message: The Discord message
            field: Optional specific field to show

        Returns:
            bool: True if handled successfully
        """
        if field:
            # Show specific field
            field_info = self.config.get_field_info(field)
            if not field_info:
                await self.send_error_message(
                    message, f"Unknown configuration field: {field}"
                )
                return False

            current_value = getattr(self.config, field, "Not set")

            info_text = f"**Configuration Field: {field}**\n"
            info_text += (
                f"Current Value: {self.format_inline_code(str(current_value))}\n"
            )
            info_text += f"Type: {field_info.get('type', 'Unknown')}\n"
            info_text += (
                f"Description: {field_info.get('description', 'No description')}\n"
            )

            if field_info.get("range"):
                info_text += f"Range: {field_info['range']}\n"
            if field_info.get("unit"):
                info_text += f"Unit: {field_info['unit']}\n"
            if field_info.get("restart_required"):
                info_text += "⚠️ **Restart required** for changes to take effect\n"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, info_text
            )
        else:
            # Show all configuration organized by category
            config_text = self._format_all_configuration()
            # Truncate if too long for Discord
            config_text = self.truncate_message(config_text)
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, config_text
            )

        return True

    async def _handle_config_set(
        self, message: discord.Message, field: str, value: str
    ) -> bool:
        """
        Handle the !config set <field> <value> command.

        Args:
            message: The Discord message
            field: Configuration field to set
            value: New value for the field

        Returns:
            bool: True if handled successfully
        """
        # Validate field and value
        validation_result = self.config.validate_config_value(field, value)
        if not validation_result["valid"]:
            await self.send_error_message(message, validation_result["error"])
            return False

        # Update the configuration
        old_value = getattr(self.config, field, None)
        try:
            self.config.update_field(field, validation_result["converted_value"])

            # Apply the change to running services
            await self._apply_config_change(field, validation_result["converted_value"])

            # Show success message
            field_info = self.config.get_field_info(field)
            restart_warning = ""
            if field_info and field_info.get("restart_required"):
                restart_warning = " ⚠️ **Restart required** for full effect"

            success_msg = f"Configuration updated: {field} = {validation_result['converted_value']}{restart_warning}"
            await self.send_success_message(message, success_msg)

            logger.info(
                f"Config changed by {message.author}: {field} = {old_value} → {validation_result['converted_value']}"
            )

        except Exception as e:
            await self.send_error_message(
                message, f"Failed to update configuration: {e!s}"
            )
            return False

        return True

    async def _handle_config_list(self, message: discord.Message) -> bool:
        """
        Handle the !config list command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        fields = self.config.get_runtime_configurable_fields()

        if not fields:
            await self.send_info_message(message, "No configurable fields available")
            return True

        list_text = "**Available Configuration Fields:**\n\n"
        for field, info in fields.items():
            list_text += f"• **{field}** ({info.get('type', 'unknown')})\n"
            list_text += f"  {info.get('description', 'No description')}\n"
            if info.get("range"):
                list_text += f"  Range: {info['range']}\n"
            if info.get("restart_required"):
                list_text += "  ⚠️ Restart required\n"
            list_text += "\n"

        # Truncate if too long for Discord
        list_text = self.truncate_message(list_text)
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, list_text
        )
        return True

    async def _handle_config_save(self, message: discord.Message) -> bool:
        """
        Handle the !config save command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        try:
            self.config.save_to_file()
            await self.send_success_message(
                message, "Configuration saved to bot_config.json"
            )
            logger.info(f"Configuration saved by {message.author}")
        except Exception as e:
            await self.send_error_message(
                message, f"Failed to save configuration: {e!s}"
            )
            return False

        return True

    async def _handle_config_reload(self, message: discord.Message) -> bool:
        """
        Handle the !config reload command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        await self.send_info_message(
            message,
            "Configuration reload requested. Note: Bot restart is required for most changes to take full effect.",
        )
        logger.info(f"Configuration reload requested by {message.author}")
        return True

    async def _apply_config_change(self, field: str, value: Any) -> None:
        """
        Apply configuration changes to running services.

        Args:
            field: Configuration field that was changed
            value: New value for the field
        """
        # Apply IP service settings
        if field == "max_retries":
            self.ip_service.max_retries = value
        elif field == "retry_delay":
            self.ip_service.retry_delay = value
        elif field == "concurrent_api_checks":
            self.ip_service.concurrent_api_checks = value

        # Apply circuit breaker settings
        elif field == "circuit_breaker_enabled":
            if hasattr(self.ip_service, "circuit_breaker"):
                self.ip_service.circuit_breaker.enabled = value
        elif field == "circuit_breaker_failure_threshold":
            if hasattr(self.ip_service, "circuit_breaker"):
                self.ip_service.circuit_breaker.failure_threshold = value
        elif field == "circuit_breaker_recovery_timeout":
            if hasattr(self.ip_service, "circuit_breaker"):
                self.ip_service.circuit_breaker.recovery_timeout = value

        # Apply message queue settings
        elif field == "message_queue_enabled":
            message_queue.enabled = value
        elif field == "message_queue_max_size":
            message_queue.max_size = value
        elif field == "message_queue_max_age_hours":
            message_queue.max_age_hours = value
        elif field == "message_queue_batch_size":
            message_queue.batch_size = value
        elif field == "message_queue_process_interval":
            message_queue.process_interval = value

        logger.info(f"Applied configuration change: {field} = {value}")

    def _format_all_configuration(self) -> str:
        """
        Format all configuration fields organized by category.

        Returns:
            str: Formatted configuration text
        """
        config_text = "**Current Configuration:**\n\n"

        # IP Monitoring
        config_text += "**IP Monitoring:**\n"
        config_text += f"• Check Interval: {self.config.check_interval} minutes\n"
        config_text += f"• Max Retries: {self.config.max_retries}\n"
        config_text += f"• Retry Delay: {self.config.retry_delay} seconds\n"
        config_text += (
            f"• Concurrent API Checks: {self.config.concurrent_api_checks}\n\n"
        )

        # Circuit Breaker
        config_text += "**Circuit Breaker:**\n"
        config_text += f"• Enabled: {self.config.circuit_breaker_enabled}\n"
        config_text += (
            f"• Failure Threshold: {self.config.circuit_breaker_failure_threshold}\n"
        )
        config_text += f"• Recovery Timeout: {self.config.circuit_breaker_recovery_timeout} seconds\n\n"

        # Rate Limiting
        config_text += "**Rate Limiting:**\n"
        config_text += f"• Rate Limit Period: {self.config.rate_limit_period} seconds\n"
        config_text += (
            f"• Max Checks Per Period: {self.config.max_checks_per_period}\n\n"
        )

        # Storage
        config_text += "**Storage:**\n"
        config_text += f"• IP History Size: {self.config.ip_history_size}\n\n"

        # Messages
        config_text += "**Messages:**\n"
        config_text += (
            f"• Startup Message Enabled: {self.config.startup_message_enabled}\n\n"
        )

        # Message Queue
        config_text += "**Message Queue:**\n"
        config_text += f"• Enabled: {self.config.message_queue_enabled}\n"
        config_text += f"• Max Size: {self.config.message_queue_max_size}\n"
        config_text += f"• Max Age: {self.config.message_queue_max_age_hours} hours\n"
        config_text += f"• Batch Size: {self.config.message_queue_batch_size}\n"
        config_text += f"• Process Interval: {self.config.message_queue_process_interval} seconds\n"

        return config_text

    def _get_config_help_text(self) -> str:
        """
        Get help text for configuration commands.

        Returns:
            str: Help text for config commands
        """
        return """**Configuration Commands:**
• `!config show` - Show all configuration settings
• `!config show <field>` - Show specific configuration field
• `!config set <field> <value>` - Update configuration field
• `!config list` - List all configurable fields with descriptions
• `!config save` - Save current configuration to file
• `!config reload` - Reload configuration from file (requires restart)

**Examples:**
• `!config show max_retries`
• `!config set max_retries 5`
• `!config set circuit_breaker_enabled false`"""

    def get_help_text(self) -> str:
        """
        Get help text for configuration commands.

        Returns:
            str: Help text describing available commands
        """
        return self._get_config_help_text()
