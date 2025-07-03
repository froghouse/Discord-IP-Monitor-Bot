"""
Administrative commands for the IP Monitor Bot.
"""

import logging
from typing import Any, Callable, Coroutine, Union

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter
from ip_monitor.utils.message_queue import message_queue

logger = logging.getLogger(__name__)


class AdminCommands:
    """
    Handles administrative bot commands.
    """

    def __init__(
        self,
        client: discord.Client,
        ip_service: IPService,
        storage: Union[IPStorage, SQLiteIPStorage],
        stop_callback: Callable[[], Coroutine[Any, Any, None]],
        config: AppConfig,
    ) -> None:
        """
        Initialize the admin commands handler.

        Args:
            client: Discord client instance
            ip_service: Service for IP address operations
            storage: Storage for IP data
            stop_callback: Callback to stop the bot
            config: Application configuration
        """
        self.client = client
        self.ip_service = ip_service
        self.storage = storage
        self.stop_callback = stop_callback
        self.config = config
        self.discord_rate_limiter = DiscordRateLimiter()

    async def handle_stop_command(self, message: discord.Message) -> bool:
        """
        Handle the !stop command to stop the bot.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can stop the bot
        if not message.author.guild_permissions.administrator:
            return False

        logger.info(f"Stop command received from {message.author}")
        await message.add_reaction("🛑")

        try:
            # First save the current IP one last time
            current_ip = await self.ip_service.get_public_ip()
            if current_ip:
                self.storage.save_current_ip(current_ip)

            # Send the goodbye message
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "🛑 Stopping bot. Goodbye!"
            )

            # Execute the stop callback
            await self.stop_callback()

            return True
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                "⚠️ Error during shutdown. The bot may not stop cleanly.",
            )
            # Try to force close even if there was an error
            await self.client.close()
            return True

    async def handle_queue_command(self, message: discord.Message) -> bool:
        """
        Handle the !queue command to manage message queue.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can manage the queue
        if not message.author.guild_permissions.administrator:
            return False

        parts = message.content.split()
        if len(parts) < 2:
            # Show queue status
            queue_status = message_queue.get_queue_status()
            status_text = "📥 **Message Queue Status**\n"
            status_text += f"Queue Size: {queue_status['queue_size']}/{queue_status['max_queue_size']}\n"
            status_text += (
                f"Processing: {'Yes' if queue_status['is_processing'] else 'No'}\n"
            )
            status_text += f"Ready to Process: {queue_status['ready_to_process']}\n"
            status_text += (
                f"Scheduled for Later: {queue_status['scheduled_for_later']}\n"
            )

            # Statistics
            stats = queue_status["statistics"]
            status_text += "\n📊 **Statistics**\n"
            status_text += f"Total Queued: {stats['total_queued']}\n"
            status_text += f"Total Delivered: {stats['total_delivered']}\n"
            status_text += f"Total Failed: {stats['total_failed']}\n"
            status_text += f"Total Expired: {stats['total_expired']}\n"
            status_text += f"Deduplicated: {stats['total_deduplicated']}\n"

            # Breakdowns
            if queue_status["status_breakdown"]:
                status_text += (
                    f"\n**Status Breakdown**: {queue_status['status_breakdown']}\n"
                )
            if queue_status["priority_breakdown"]:
                status_text += (
                    f"**Priority Breakdown**: {queue_status['priority_breakdown']}\n"
                )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, status_text
            )
            return True

        command = parts[1].lower()

        if command == "clear":
            # Clear the queue
            cleared = message_queue.clear_queue()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Cleared {cleared} messages from queue"
            )
            logger.info(
                f"Admin {message.author} cleared message queue ({cleared} messages)"
            )
            return True

        elif command == "retry":
            # Retry failed messages
            retried = message_queue.retry_failed_messages()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"🔄 Scheduled {retried} failed messages for retry"
            )
            logger.info(
                f"Admin {message.author} retried failed messages ({retried} messages)"
            )
            return True

        elif command == "start":
            # Start queue processing
            if not message_queue.is_processing:
                message_queue.start_processing()
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "▶️ Message queue processing started"
                )
                logger.info(f"Admin {message.author} started message queue processing")
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "ℹ️ Message queue is already processing"
                )
            return True

        elif command == "stop":
            # Stop queue processing
            if message_queue.is_processing:
                await message_queue.stop_processing()
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "⏹️ Message queue processing stopped"
                )
                logger.info(f"Admin {message.author} stopped message queue processing")
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "ℹ️ Message queue is not processing"
                )
            return True

        else:
            # Unknown command
            help_text = "**Queue Commands:**\n"
            help_text += "`!queue` - Show queue status\n"
            help_text += "`!queue clear` - Clear all queued messages\n"
            help_text += "`!queue retry` - Retry all failed messages\n"
            help_text += "`!queue start` - Start queue processing\n"
            help_text += "`!queue stop` - Stop queue processing\n"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

    async def handle_config_command(self, message: discord.Message) -> bool:
        """
        Handle the !config command to manage bot configuration.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can manage configuration
        if not message.author.guild_permissions.administrator:
            return False

        parts = message.content.split()
        if len(parts) < 2:
            # Show config help
            help_text = "**Configuration Commands:**\n"
            help_text += "`!config show` - Show current configuration\n"
            help_text += "`!config show <field>` - Show specific field value\n"
            help_text += "`!config set <field> <value>` - Update configuration field\n"
            help_text += "`!config list` - List all configurable fields\n"
            help_text += "`!config save` - Save current config to file\n"
            help_text += "`!config reload` - Reload config from file\n"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        command = parts[1].lower()

        if command == "show":
            return await self._handle_config_show(message, parts)
        elif command == "set":
            return await self._handle_config_set(message, parts)
        elif command == "list":
            return await self._handle_config_list(message)
        elif command == "save":
            return await self._handle_config_save(message)
        elif command == "reload":
            return await self._handle_config_reload(message)
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Unknown config command. Use `!config` for help."
            )
            return True

    async def _handle_config_show(self, message: discord.Message, parts: list) -> bool:
        """
        Handle config show command.
        """
        if len(parts) >= 3:
            # Show specific field
            field_name = parts[2]
            if hasattr(self.config, field_name):
                value = getattr(self.config, field_name)
                configurable = self.config.get_runtime_configurable_fields()

                if field_name in configurable:
                    field_info = configurable[field_name]
                    unit = field_info.get("unit", "")
                    restart_req = field_info.get("restart_required", False)
                    description = field_info.get("description", "")

                    config_text = f"**Configuration Field: {field_name}**\n"
                    config_text += (
                        f"Current Value: `{value}`{' ' + unit if unit else ''}\n"
                    )
                    config_text += f"Description: {description}\n"
                    config_text += (
                        f"Restart Required: {'Yes' if restart_req else 'No'}\n"
                    )
                else:
                    config_text = f"**{field_name}**: `{value}` (read-only)"
            else:
                config_text = f"❌ Configuration field '{field_name}' not found."
        else:
            # Show all configuration
            config_text = "**Current Bot Configuration**\n\n"

            # Get configurable fields info
            configurable = self.config.get_runtime_configurable_fields()

            # Group fields by category
            categories = {
                "IP Monitoring": [
                    "check_interval",
                    "max_retries",
                    "retry_delay",
                    "concurrent_api_checks",
                ],
                "Circuit Breaker": [
                    "circuit_breaker_enabled",
                    "circuit_breaker_failure_threshold",
                    "circuit_breaker_recovery_timeout",
                ],
                "Rate Limiting": ["rate_limit_period", "max_checks_per_period"],
                "Storage": ["ip_history_size"],
                "Messages": ["startup_message_enabled"],
                "Message Queue": [
                    "message_queue_enabled",
                    "message_queue_max_size",
                    "message_queue_max_age_hours",
                    "message_queue_batch_size",
                    "message_queue_process_interval",
                ],
            }

            for category, fields in categories.items():
                config_text += f"**{category}:**\n"
                for field in fields:
                    if field in configurable and hasattr(self.config, field):
                        value = getattr(self.config, field)
                        unit = configurable[field].get("unit", "")
                        config_text += (
                            f"  {field}: `{value}`{' ' + unit if unit else ''}\n"
                        )
                config_text += "\n"

            # Add read-only fields
            config_text += "**Read-Only:**\n"
            readonly_fields = [
                "discord_token",
                "channel_id",
                "db_file",
                "testing_mode",
                "log_level",
            ]
            for field in readonly_fields:
                if hasattr(self.config, field):
                    value = getattr(self.config, field)
                    if field == "discord_token":
                        value = "[HIDDEN]"
                    config_text += f"  {field}: `{value}`\n"

        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, config_text
        )
        return True

    async def _handle_config_set(self, message: discord.Message, parts: list) -> bool:
        """
        Handle config set command.
        """
        if len(parts) < 4:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!config set <field> <value>`"
            )
            return True

        field_name = parts[2]
        value_str = " ".join(parts[3:])  # Join in case value has spaces

        # Validate the field and value
        is_valid, result = self.config.validate_config_value(field_name, value_str)

        if not is_valid:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Validation failed: {result}"
            )
            return True

        # Get old value for comparison
        old_value = getattr(self.config, field_name, None)

        # Update the configuration
        if self.config.update_field(field_name, result):
            # Apply the change to relevant services
            await self._apply_config_change(field_name, result, old_value)

            configurable = self.config.get_runtime_configurable_fields()
            restart_required = configurable.get(field_name, {}).get(
                "restart_required", False
            )

            success_text = f"✅ Updated `{field_name}` from `{old_value}` to `{result}`"
            if restart_required:
                success_text += (
                    "\n⚠️ **Restart required** for this change to take full effect."
                )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, success_text
            )

            logger.info(
                f"Admin {message.author} updated config: {field_name} = {result}"
            )
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                f"❌ Failed to update configuration field '{field_name}'",
            )

        return True

    async def _handle_config_list(self, message: discord.Message) -> bool:
        """
        Handle config list command.
        """
        configurable = self.config.get_runtime_configurable_fields()

        list_text = "**Configurable Fields:**\n\n"

        for field_name, field_info in configurable.items():
            field_type = field_info["type"]
            description = field_info["description"]
            restart_req = field_info.get("restart_required", False)

            list_text += f"**{field_name}** ({field_type})\n"
            list_text += f"  {description}\n"

            if field_type in ["int", "float"]:
                min_val = field_info.get("min_value")
                max_val = field_info.get("max_value")
                if min_val is not None and max_val is not None:
                    list_text += f"  Range: {min_val} - {max_val}\n"

            if restart_req:
                list_text += "  ⚠️ Restart required\n"

            list_text += "\n"

        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, list_text
        )
        return True

    async def _handle_config_save(self, message: discord.Message) -> bool:
        """
        Handle config save command.
        """
        config_file = "bot_config.json"
        if self.config.save_to_file(config_file):
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Configuration saved to `{config_file}`"
            )
            logger.info(f"Admin {message.author} saved configuration to {config_file}")
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to save configuration to `{config_file}`"
            )
        return True

    async def _handle_config_reload(self, message: discord.Message) -> bool:
        """
        Handle config reload command.
        """
        try:
            # This would require bot restart to fully take effect
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                "ℹ️ Config reload requires bot restart to take full effect.\n"
                "Current session will continue with existing configuration.",
            )
            logger.info(f"Admin {message.author} requested config reload")
        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to reload configuration: {e}"
            )
        return True

    async def _apply_config_change(
        self, field_name: str, new_value: Any, old_value: Any
    ) -> None:
        """
        Apply configuration changes to running services.

        Args:
            field_name: Name of the changed field
            new_value: New value
            old_value: Previous value
        """
        try:
            # Apply changes to IP service
            if field_name == "max_retries":
                self.ip_service.max_retries = new_value
            elif field_name == "retry_delay":
                self.ip_service.retry_delay = new_value
            elif field_name == "concurrent_api_checks":
                self.ip_service.use_concurrent_checks = new_value
            elif field_name.startswith("circuit_breaker_"):
                # Update circuit breaker settings
                if field_name == "circuit_breaker_enabled":
                    self.ip_service.circuit_breaker_enabled = new_value
                elif (
                    field_name == "circuit_breaker_failure_threshold"
                    and hasattr(self.ip_service, "circuit_breaker")
                    and self.ip_service.circuit_breaker
                ):
                    self.ip_service.circuit_breaker.failure_threshold = new_value
                elif (
                    field_name == "circuit_breaker_recovery_timeout"
                    and hasattr(self.ip_service, "circuit_breaker")
                    and self.ip_service.circuit_breaker
                ):
                    self.ip_service.circuit_breaker.recovery_timeout = new_value

            # Apply changes to message queue
            elif field_name.startswith("message_queue_"):
                if field_name == "message_queue_max_size":
                    message_queue.max_queue_size = new_value
                elif field_name == "message_queue_max_age_hours":
                    message_queue.max_message_age_hours = new_value
                elif field_name == "message_queue_batch_size":
                    message_queue.batch_size = new_value
                elif field_name == "message_queue_process_interval":
                    message_queue.process_interval = new_value

            logger.info(f"Applied config change: {field_name} = {new_value}")

        except Exception as e:
            logger.error(f"Failed to apply config change {field_name}: {e}")
