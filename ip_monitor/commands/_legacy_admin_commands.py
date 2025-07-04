"""
Administrative commands for the IP Monitor Bot.
"""

import logging
from typing import Any, Callable, Coroutine, Union

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_api_config import IPAPIEndpoint, ResponseFormat, ip_api_manager
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

    async def handle_api_command(self, message: discord.Message) -> bool:
        """
        Handle the !api command to manage IP detection APIs.

        Args:
            message: The Discord message containing the command

        Returns:
            bool: True if handled successfully
        """
        # Only admins can manage APIs
        if not message.author.guild_permissions.administrator:
            return False

        parts = message.content.split()
        if len(parts) < 2:
            # Show API help
            help_text = "**IP API Management Commands:**\n"
            help_text += "`!api list` - List all configured IP APIs\n"
            help_text += "`!api add <name> <url> [format] [field]` - Add new IP API\n"
            help_text += "`!api remove <id>` - Remove IP API\n"
            help_text += "`!api enable <id>` - Enable IP API\n"
            help_text += "`!api disable <id>` - Disable IP API\n"
            help_text += "`!api test <id>` - Test IP API\n"
            help_text += "`!api priority <id> <priority>` - Set API priority\n"
            help_text += "`!api stats` - Show API performance statistics\n"
            help_text += "\n**Formats:** `json`, `text`, `auto` (default)\n"
            help_text += "**Examples:**\n"
            help_text += '`!api add "My API" "https://api.example.com/ip" json ip`\n'
            help_text += '`!api add "Simple API" "https://text.example.com/" text`'

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        command = parts[1].lower()

        if command == "list":
            return await self._handle_api_list(message)
        elif command == "add":
            return await self._handle_api_add(message, parts)
        elif command == "remove":
            return await self._handle_api_remove(message, parts)
        elif command == "enable":
            return await self._handle_api_enable(message, parts)
        elif command == "disable":
            return await self._handle_api_disable(message, parts)
        elif command == "test":
            return await self._handle_api_test(message, parts)
        elif command == "priority":
            return await self._handle_api_priority(message, parts)
        elif command == "stats":
            return await self._handle_api_stats(message)
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Unknown API command. Use `!api` for help."
            )
            return True

    async def _handle_api_list(self, message: discord.Message) -> bool:
        """Handle api list command."""
        apis = ip_api_manager.list_apis()

        if not apis:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "No IP APIs configured."
            )
            return True

        list_text = "**Configured IP APIs:**\n\n"

        for api in apis:
            status = "🟢 Enabled" if api.enabled else "🔴 Disabled"
            success_rate = api.get_success_rate()
            perf_score = api.get_performance_score()

            list_text += f"**{api.name}** (`{api.id}`)\n"
            list_text += f"  URL: `{api.url}`\n"
            list_text += f"  Status: {status} | Priority: {api.priority}\n"
            list_text += f"  Format: {api.response_format.value}"
            if api.json_field:
                list_text += f" (field: {api.json_field})"
            list_text += "\n"

            if api.success_count > 0 or api.failure_count > 0:
                list_text += f"  Performance: {success_rate:.1f}% success | Score: {perf_score:.1f}\n"
                list_text += f"  Calls: {api.success_count} success, {api.failure_count} failed\n"
                if api.avg_response_time > 0:
                    list_text += f"  Avg Response: {api.avg_response_time:.2f}s\n"

            list_text += "\n"

        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, list_text
        )
        return True

    async def _handle_api_add(self, message: discord.Message, parts: list) -> bool:
        """Handle api add command."""
        if len(parts) < 4:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                "❌ Usage: `!api add <name> <url> [format] [field]`\n"
                "Formats: json, text, auto (default)",
            )
            return True

        name = parts[2].strip('"')
        url = parts[3].strip('"')

        # Parse optional format and field
        response_format = ResponseFormat.AUTO
        json_field = None

        if len(parts) > 4:
            format_str = parts[4].lower()
            if format_str in ["json", "text", "auto"]:
                response_format = ResponseFormat(format_str)
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel,
                    f"❌ Invalid format '{format_str}'. Use: json, text, auto",
                )
                return True

        if len(parts) > 5 and response_format == ResponseFormat.JSON:
            json_field = parts[5]
        elif response_format == ResponseFormat.JSON and not json_field:
            json_field = "ip"  # Default field name

        # Generate unique ID
        api_id = name.lower().replace(" ", "_").replace("-", "_")
        counter = 1
        original_id = api_id
        while ip_api_manager.get_api(api_id):
            api_id = f"{original_id}_{counter}"
            counter += 1

        try:
            # Create new API endpoint
            endpoint = IPAPIEndpoint(
                id=api_id,
                name=name,
                url=url,
                response_format=response_format,
                json_field=json_field,
                priority=len(ip_api_manager.endpoints) + 1,
            )

            if ip_api_manager.add_api(endpoint):
                success_text = f"✅ Added IP API: **{name}** (`{api_id}`)\n"
                success_text += f"URL: `{url}`\n"
                success_text += f"Format: {response_format.value}"
                if json_field:
                    success_text += f" (field: {json_field})"

                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, success_text
                )
                logger.info(f"Admin {message.author} added IP API: {name} ({api_id})")
            else:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, f"❌ Failed to add API (ID conflict: {api_id})"
                )

        except ValueError as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Invalid API configuration: {e}"
            )
        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error adding API: {e}"
            )

        return True

    async def _handle_api_remove(self, message: discord.Message, parts: list) -> bool:
        """Handle api remove command."""
        if len(parts) < 3:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!api remove <id>`"
            )
            return True

        api_id = parts[2]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ API '{api_id}' not found."
            )
            return True

        if ip_api_manager.remove_api(api_id):
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Removed IP API: **{api.name}** (`{api_id}`)"
            )
            logger.info(f"Admin {message.author} removed IP API: {api.name} ({api_id})")
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to remove API '{api_id}'"
            )

        return True

    async def _handle_api_enable(self, message: discord.Message, parts: list) -> bool:
        """Handle api enable command."""
        if len(parts) < 3:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!api enable <id>`"
            )
            return True

        api_id = parts[2]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ API '{api_id}' not found."
            )
            return True

        if ip_api_manager.enable_api(api_id):
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Enabled IP API: **{api.name}** (`{api_id}`)"
            )
            logger.info(f"Admin {message.author} enabled IP API: {api.name} ({api_id})")
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to enable API '{api_id}'"
            )

        return True

    async def _handle_api_disable(self, message: discord.Message, parts: list) -> bool:
        """Handle api disable command."""
        if len(parts) < 3:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!api disable <id>`"
            )
            return True

        api_id = parts[2]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ API '{api_id}' not found."
            )
            return True

        if ip_api_manager.disable_api(api_id):
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"✅ Disabled IP API: **{api.name}** (`{api_id}`)"
            )
            logger.info(
                f"Admin {message.author} disabled IP API: {api.name} ({api_id})"
            )
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to disable API '{api_id}'"
            )

        return True

    async def _handle_api_priority(self, message: discord.Message, parts: list) -> bool:
        """Handle api priority command."""
        if len(parts) < 4:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!api priority <id> <priority>`"
            )
            return True

        api_id = parts[2]
        try:
            priority = int(parts[3])
        except ValueError:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Priority must be a number"
            )
            return True

        api = ip_api_manager.get_api(api_id)
        if not api:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ API '{api_id}' not found."
            )
            return True

        if ip_api_manager.update_api_priority(api_id, priority):
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                f"✅ Updated priority for **{api.name}** (`{api_id}`) to {priority}",
            )
            logger.info(
                f"Admin {message.author} updated API priority: {api.name} -> {priority}"
            )
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Failed to update priority for API '{api_id}'"
            )

        return True

    async def _handle_api_test(self, message: discord.Message, parts: list) -> bool:
        """Handle api test command."""
        if len(parts) < 3:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "❌ Usage: `!api test <id>`"
            )
            return True

        api_id = parts[2]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ API '{api_id}' not found."
            )
            return True

        # Test the API using the IP service
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, f"🔄 Testing **{api.name}** (`{api_id}`)..."
        )

        try:
            # This will be implemented when we update the IP service
            test_result = await self._test_single_api(api)

            if test_result["success"]:
                ip = test_result["ip"]
                response_time = test_result["response_time"]
                result_text = f"✅ **{api.name}** test successful!\n"
                result_text += f"Detected IP: `{ip}`\n"
                result_text += f"Response time: {response_time:.2f}s"
            else:
                error = test_result["error"]
                result_text = f"❌ **{api.name}** test failed!\n"
                result_text += f"Error: {error}"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, result_text
            )

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error testing API: {e}"
            )

        return True

    async def _handle_api_stats(self, message: discord.Message) -> bool:
        """Handle api stats command."""
        apis = ip_api_manager.list_apis()

        if not apis:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "No IP APIs configured."
            )
            return True

        stats_text = "**IP API Performance Statistics:**\n\n"

        # Sort by performance score
        apis_with_stats = [
            api for api in apis if api.success_count > 0 or api.failure_count > 0
        ]
        apis_with_stats.sort(key=lambda x: x.get_performance_score(), reverse=True)

        if not apis_with_stats:
            stats_text += "No performance data available yet."
        else:
            for i, api in enumerate(apis_with_stats, 1):
                success_rate = api.get_success_rate()
                perf_score = api.get_performance_score()
                total_calls = api.success_count + api.failure_count

                stats_text += f"**{i}. {api.name}** (`{api.id}`)\n"
                stats_text += f"  Performance Score: {perf_score:.1f}/100\n"
                stats_text += f"  Success Rate: {success_rate:.1f}% ({api.success_count}/{total_calls})\n"

                if api.avg_response_time > 0:
                    stats_text += f"  Avg Response Time: {api.avg_response_time:.2f}s\n"

                # Recent activity
                import time

                current_time = time.time()
                if api.last_success:
                    last_success_min = (current_time - api.last_success) / 60
                    stats_text += f"  Last Success: {last_success_min:.1f} min ago\n"
                if api.last_failure:
                    last_failure_min = (current_time - api.last_failure) / 60
                    stats_text += f"  Last Failure: {last_failure_min:.1f} min ago\n"

                stats_text += "\n"

        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, stats_text
        )
        return True

    async def _test_single_api(self, api: IPAPIEndpoint) -> dict:
        """
        Test a single API endpoint.

        Args:
            api: The API endpoint to test

        Returns:
            Dict with test results
        """
        import time

        import httpx

        start_time = time.time()

        try:
            headers = api.headers or {}
            headers.setdefault("User-Agent", "IP-Monitor-Bot/1.0")

            async with httpx.AsyncClient(timeout=api.timeout) as client:
                response = await client.get(api.url, headers=headers)
                response.raise_for_status()

                response_time = time.time() - start_time

                # Parse response based on format
                if api.response_format == ResponseFormat.JSON or (
                    api.response_format == ResponseFormat.AUTO
                    and response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                ):
                    data = response.json()
                    if api.json_field:
                        ip = data.get(api.json_field)
                    else:
                        # Try common field names
                        ip = data.get("ip") or data.get("origin") or data.get("address")
                else:
                    # Plain text response
                    ip = response.text.strip()

                if not ip:
                    return {
                        "success": False,
                        "error": "No IP address found in response",
                        "response_time": response_time,
                    }

                # Validate IP
                if not self.ip_service.is_valid_ip(ip):
                    return {
                        "success": False,
                        "error": f"Invalid IP address returned: {ip}",
                        "response_time": response_time,
                    }

                # Update API statistics
                api.record_success(response_time)
                ip_api_manager.save_apis()

                return {"success": True, "ip": ip, "response_time": response_time}

        except Exception as e:
            response_time = time.time() - start_time
            api.record_failure()
            ip_api_manager.save_apis()

            return {"success": False, "error": str(e), "response_time": response_time}

    async def handle_cache_command(self, message: discord.Message) -> bool:
        """
        Handle the !cache command to manage intelligent caching.

        Subcommands:
        - !cache show - Show cache statistics and status
        - !cache clear [namespace] - Clear cache entries (optionally by namespace)
        - !cache stats - Show detailed cache statistics
        - !cache cleanup - Force cleanup of expired entries
        - !cache refresh - Refresh stale cache entries
        """
        # Check if user has admin permissions
        if not message.author.guild_permissions.administrator:
            return False

        parts = message.content.split()
        if len(parts) < 2:
            help_text = (
                "**🗄️ Cache Management Commands**\n"
                "```\n"
                "!cache show        - Show cache status and statistics\n"
                "!cache clear       - Clear all cache entries\n"
                "!cache clear <ns>  - Clear specific namespace (ip_check, global)\n"
                "!cache stats       - Show detailed cache statistics\n"
                "!cache cleanup     - Force cleanup of expired entries\n"
                "!cache refresh     - Refresh stale cache entries\n"
                "```"
            )
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        command = parts[1].lower()

        if command == "show":
            return await self._handle_cache_show(message, parts)
        elif command == "clear":
            return await self._handle_cache_clear(message, parts)
        elif command == "stats":
            return await self._handle_cache_stats(message, parts)
        elif command == "cleanup":
            return await self._handle_cache_cleanup(message, parts)
        elif command == "refresh":
            return await self._handle_cache_refresh(message, parts)
        else:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel,
                f"❌ Unknown cache subcommand: `{command}`. Use `!cache` for help.",
            )
            return True

    async def _handle_cache_show(self, message: discord.Message, parts: list) -> bool:
        """Handle !cache show command."""
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "🗄️ **Cache Status**: Disabled"
                )
                return True

            stats = cache_info["stats"]

            # Calculate additional metrics
            total_requests = stats["hits"] + stats["misses"]
            hit_rate = stats["hit_rate"] * 100 if "hit_rate" in stats else 0

            response = (
                "🗄️ **Intelligent Cache Status**\n"
                f"```\n"
                f"Status:           Enabled\n"
                f"Memory Entries:   {stats['memory_entries']}\n"
                f"Memory Usage:     {stats.get('memory_usage_mb', 0):.1f} MB\n"
                f"Cache TTL:        {cache_info['cache_ttl']} seconds\n"
                f"Stale Threshold:  {cache_info['stale_threshold']:.1f}\n"
                f"Stale Entries:    {cache_info['stale_entries_count']}\n"
                f"\n"
                f"Performance:\n"
                f"  Total Requests: {total_requests}\n"
                f"  Cache Hits:     {stats['hits']}\n"
                f"  Cache Misses:   {stats['misses']}\n"
                f"  Hit Rate:       {hit_rate:.1f}%\n"
                f"\n"
                f"Operations:\n"
                f"  Evictions:      {stats['evictions']}\n"
                f"  Invalidations:  {stats['invalidations']}\n"
                f"  Refreshes:      {stats['refreshes']}\n"
                f"  Saves:          {stats['saves']}\n"
                f"  Loads:          {stats['loads']}\n"
                f"```"
            )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(f"Admin {message.author} viewed cache status")
            return True

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error getting cache status: {e}"
            )
            logger.error(f"Error handling cache show command: {e}")
            return True

    async def _handle_cache_clear(self, message: discord.Message, parts: list) -> bool:
        """Handle !cache clear [namespace] command."""
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "❌ Cache is disabled"
                )
                return True

            namespace = None
            if len(parts) > 2:
                namespace = parts[2]

            cleared_count = self.ip_service.invalidate_cache(namespace)

            if namespace:
                response = (
                    f"✅ Cleared {cleared_count} entries from namespace `{namespace}`"
                )
            else:
                response = f"✅ Cleared all {cleared_count} cache entries"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(
                f"Admin {message.author} cleared cache (namespace: {namespace})"
            )
            return True

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error clearing cache: {e}"
            )
            logger.error(f"Error handling cache clear command: {e}")
            return True

    async def _handle_cache_stats(self, message: discord.Message, parts: list) -> bool:
        """Handle !cache stats command."""
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "❌ Cache is disabled"
                )
                return True

            stats = cache_info["stats"]

            # Get cache instance for detailed stats
            from ip_monitor.utils.cache import get_cache

            cache = get_cache()

            # Count entries by type
            entry_types = {}
            for entry in cache.memory_cache.values():
                cache_type = entry.cache_type.value
                entry_types[cache_type] = entry_types.get(cache_type, 0) + 1

            type_breakdown = (
                "\n".join(
                    [
                        f"  {cache_type}: {count}"
                        for cache_type, count in entry_types.items()
                    ]
                )
                if entry_types
                else "  No entries"
            )

            total_requests = stats["hits"] + stats["misses"]
            hit_rate = stats["hit_rate"] * 100 if "hit_rate" in stats else 0
            miss_rate = 100 - hit_rate if total_requests > 0 else 0

            response = (
                "📊 **Detailed Cache Statistics**\n"
                f"```\n"
                f"Cache Configuration:\n"
                f"  TTL:              {cache_info['cache_ttl']} seconds\n"
                f"  Stale Threshold:  {cache_info['stale_threshold']:.1f}\n"
                f"  Max Memory Size:  {cache.max_memory_size} entries\n"
                f"\n"
                f"Current State:\n"
                f"  Memory Entries:   {stats['memory_entries']}\n"
                f"  Memory Usage:     {stats.get('memory_usage_mb', 0):.1f} MB\n"
                f"  Stale Entries:    {cache_info['stale_entries_count']}\n"
                f"\n"
                f"Entry Types:\n"
                f"{type_breakdown}\n"
                f"\n"
                f"Performance Metrics:\n"
                f"  Total Requests:   {total_requests}\n"
                f"  Cache Hits:       {stats['hits']} ({hit_rate:.1f}%)\n"
                f"  Cache Misses:     {stats['misses']} ({miss_rate:.1f}%)\n"
                f"  Efficiency:       {'Excellent' if hit_rate > 80 else 'Good' if hit_rate > 60 else 'Fair' if hit_rate > 40 else 'Poor'}\n"
                f"\n"
                f"Maintenance Operations:\n"
                f"  Evictions:        {stats['evictions']}\n"
                f"  Invalidations:    {stats['invalidations']}\n"
                f"  Refreshes:        {stats['refreshes']}\n"
                f"  Disk Saves:       {stats['saves']}\n"
                f"  Disk Loads:       {stats['loads']}\n"
                f"```"
            )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(f"Admin {message.author} viewed cache statistics")
            return True

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error getting cache statistics: {e}"
            )
            logger.error(f"Error handling cache stats command: {e}")
            return True

    async def _handle_cache_cleanup(
        self, message: discord.Message, parts: list
    ) -> bool:
        """Handle !cache cleanup command."""
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "❌ Cache is disabled"
                )
                return True

            from ip_monitor.utils.cache import get_cache

            cache = get_cache()

            cleanup_results = cache.cleanup()

            response = (
                f"🧹 **Cache Cleanup Complete**\n"
                f"```\n"
                f"Expired Entries Cleaned: {cleanup_results['entries_cleaned']}\n"
                f"Entries Remaining:       {cleanup_results['entries_remaining']}\n"
                f"Cache Saved to Disk:     Yes\n"
                f"```"
            )

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(f"Admin {message.author} performed cache cleanup")
            return True

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error performing cache cleanup: {e}"
            )
            logger.error(f"Error handling cache cleanup command: {e}")
            return True

    async def _handle_cache_refresh(
        self, message: discord.Message, parts: list
    ) -> bool:
        """Handle !cache refresh command."""
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel, "❌ Cache is disabled"
                )
                return True

            # Send initial message
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, "🔄 Refreshing stale cache entries... Please wait."
            )

            refreshed_count = await self.ip_service.refresh_stale_cache_entries()

            if refreshed_count > 0:
                response = (
                    f"✅ Successfully refreshed {refreshed_count} stale cache entries"
                )
            else:
                response = "ℹ️ No stale cache entries found to refresh"

            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(
                f"Admin {message.author} refreshed {refreshed_count} cache entries"
            )
            return True

        except Exception as e:
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, f"❌ Error refreshing cache entries: {e}"
            )
            logger.error(f"Error handling cache refresh command: {e}")
            return True
