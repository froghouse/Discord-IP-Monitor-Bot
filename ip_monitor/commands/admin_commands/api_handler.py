"""
API handler for admin commands.
"""

import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

import discord
import httpx

from ip_monitor.config import AppConfig
from ip_monitor.ip_api_config import IPAPIEndpoint, ResponseFormat, ip_api_manager
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class ApiHandler(BaseHandler):
    """
    Handles API-related admin commands.
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
        Initialize the API handler.

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
        Handle API commands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        if not args:
            return False

        command = args[0].lower()

        if command == "api":
            return await self._handle_api_command(message, args[1:])

        return False

    async def _handle_api_command(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !api command and its subcommands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments (excluding 'api')

        Returns:
            bool: True if handled successfully
        """
        # Check admin permissions
        if not self.check_admin_permissions(message):
            await self.send_permission_denied(message)
            return False

        self.log_command_usage(message, "api")

        if not args:
            # Show API help text
            help_text = self._get_api_help_text()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        subcommand = args[0].lower()

        try:
            if subcommand == "list":
                return await self._handle_api_list(message)
            if subcommand == "add":
                return await self._handle_api_add(message, args)
            if subcommand == "remove":
                return await self._handle_api_remove(message, args)
            if subcommand == "enable":
                return await self._handle_api_enable(message, args)
            if subcommand == "disable":
                return await self._handle_api_disable(message, args)
            if subcommand == "test":
                return await self._handle_api_test(message, args)
            if subcommand == "priority":
                return await self._handle_api_priority(message, args)
            if subcommand == "stats":
                return await self._handle_api_stats(message)
            await self.send_error_message(
                message, f"Unknown API subcommand: {subcommand}"
            )
            return False
        except Exception as e:
            await self.handle_command_error(message, e, f"api {subcommand}")
            return False

    async def _handle_api_list(self, message: discord.Message) -> bool:
        """
        Handle the !api list command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        apis = ip_api_manager.list_apis()

        if not apis:
            await self.send_info_message(message, "No IP APIs configured.")
            return True

        list_text = "**Configured IP APIs:**\n\n"

        for api in apis:
            status = "🟢 Enabled" if api.enabled else "🔴 Disabled"
            success_rate = api.get_success_rate()
            perf_score = api.get_performance_score()

            list_text += f"**{api.name}** ({self.format_inline_code(api.id)})\n"
            list_text += f"  URL: {self.format_inline_code(api.url)}\n"
            list_text += f"  Status: {status} | Priority: {api.priority}\n"
            list_text += f"  Format: {api.response_format.value}"

            if api.json_field:
                list_text += f" | Field: {self.format_inline_code(api.json_field)}"

            list_text += "\n"

            if success_rate >= 0:
                list_text += f"  Success Rate: {success_rate:.1f}% | Performance: {perf_score:.1f}/100\n"
            else:
                list_text += "  No usage statistics available\n"

            if api.last_success:
                list_text += f"  Last Success: {api.last_success.strftime('%Y-%m-%d %H:%M:%S')}\n"
            if api.last_failure:
                list_text += f"  Last Failure: {api.last_failure.strftime('%Y-%m-%d %H:%M:%S')}\n"

            list_text += "\n"

        # Truncate if too long for Discord
        list_text = self.truncate_message(list_text)
        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, list_text
        )
        return True

    async def _handle_api_add(self, message: discord.Message, args: list[str]) -> bool:
        """
        Handle the !api add command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 3:
            await self.send_error_message(
                message,
                "Usage: `!api add <name> <url> [format] [field]`\n"
                "Formats: json, text, auto (default)",
            )
            return True

        name = args[1].strip('"')
        url = args[2].strip('"')

        # Parse optional format and field
        response_format = ResponseFormat.AUTO
        json_field = None

        if len(args) > 3:
            format_str = args[3].lower()
            if format_str in ["json", "text", "auto"]:
                response_format = ResponseFormat(format_str)
            else:
                await self.send_error_message(
                    message, f"Invalid format: {format_str}. Use: json, text, or auto"
                )
                return True

        if len(args) > 4:
            json_field = args[4].strip('"')

        # Generate API ID
        api_id = name.lower().replace(" ", "_").replace("-", "_")

        # Check if API already exists
        if ip_api_manager.get_api(api_id):
            await self.send_error_message(
                message, f"API with ID '{api_id}' already exists. Use a different name."
            )
            return True

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
                success_msg = f"Successfully added API '{name}' with ID '{api_id}'"
                await self.send_success_message(message, success_msg)
                logger.info(f"Admin {message.author} added API: {name} ({api_id})")
            else:
                await self.send_error_message(message, f"Failed to add API '{name}'")

        except Exception as e:
            await self.send_error_message(message, f"Error adding API: {e!s}")
            return False

        return True

    async def _handle_api_remove(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !api remove command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 2:
            await self.send_error_message(message, "Usage: `!api remove <api_id>`")
            return True

        api_id = args[1]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.send_error_message(message, f"API with ID '{api_id}' not found")
            return True

        if ip_api_manager.remove_api(api_id):
            await self.send_success_message(
                message, f"Successfully removed API '{api.name}'"
            )
            logger.info(f"Admin {message.author} removed API: {api.name} ({api_id})")
        else:
            await self.send_error_message(message, f"Failed to remove API '{api_id}'")

        return True

    async def _handle_api_enable(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !api enable command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 2:
            await self.send_error_message(message, "Usage: `!api enable <api_id>`")
            return True

        api_id = args[1]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.send_error_message(message, f"API with ID '{api_id}' not found")
            return True

        if ip_api_manager.enable_api(api_id):
            await self.send_success_message(
                message, f"Successfully enabled API '{api.name}'"
            )
            logger.info(f"Admin {message.author} enabled API: {api.name} ({api_id})")
        else:
            await self.send_error_message(message, f"Failed to enable API '{api_id}'")

        return True

    async def _handle_api_disable(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !api disable command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 2:
            await self.send_error_message(message, "Usage: `!api disable <api_id>`")
            return True

        api_id = args[1]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.send_error_message(message, f"API with ID '{api_id}' not found")
            return True

        if ip_api_manager.disable_api(api_id):
            await self.send_success_message(
                message, f"Successfully disabled API '{api.name}'"
            )
            logger.info(f"Admin {message.author} disabled API: {api.name} ({api_id})")
        else:
            await self.send_error_message(message, f"Failed to disable API '{api_id}'")

        return True

    async def _handle_api_test(self, message: discord.Message, args: list[str]) -> bool:
        """
        Handle the !api test command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 2:
            await self.send_error_message(message, "Usage: `!api test <api_id>`")
            return True

        api_id = args[1]
        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.send_error_message(message, f"API with ID '{api_id}' not found")
            return True

        # Show "testing" message
        await self.send_info_message(message, f"Testing API '{api.name}'...")

        test_result = await self._test_single_api(api)

        if test_result["success"]:
            ip = test_result["ip"]
            response_time = test_result["response_time"]
            result_text = f"✅ **{api.name}** test successful!\n"
            result_text += f"Detected IP: {self.format_inline_code(ip)}\n"
            result_text += f"Response time: {response_time:.2f}s"
        else:
            error = test_result["error"]
            result_text = f"❌ **{api.name}** test failed!\n"
            result_text += f"Error: {error}"

        await self.discord_rate_limiter.send_message_with_backoff(
            message.channel, result_text
        )
        return True

    async def _handle_api_priority(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !api priority command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        if len(args) < 3:
            await self.send_error_message(
                message, "Usage: `!api priority <api_id> <priority>`"
            )
            return True

        api_id = args[1]
        try:
            priority = int(args[2])
        except ValueError:
            await self.send_error_message(message, "Priority must be a number")
            return True

        api = ip_api_manager.get_api(api_id)

        if not api:
            await self.send_error_message(message, f"API with ID '{api_id}' not found")
            return True

        if ip_api_manager.set_api_priority(api_id, priority):
            await self.send_success_message(
                message, f"Successfully set priority for API '{api.name}' to {priority}"
            )
            logger.info(
                f"Admin {message.author} set priority for API {api.name} ({api_id}) to {priority}"
            )
        else:
            await self.send_error_message(
                message, f"Failed to set priority for API '{api_id}'"
            )

        return True

    async def _handle_api_stats(self, message: discord.Message) -> bool:
        """
        Handle the !api stats command.

        Args:
            message: The Discord message

        Returns:
            bool: True if handled successfully
        """
        apis = ip_api_manager.list_apis()

        # Filter APIs with usage statistics
        apis_with_stats = [
            api for api in apis if api.success_count > 0 or api.failure_count > 0
        ]

        if not apis_with_stats:
            await self.send_info_message(message, "No API usage statistics available")
            return True

        # Sort by performance score
        apis_with_stats.sort(key=lambda x: x.get_performance_score(), reverse=True)

        stats_text = "**API Performance Statistics:**\n\n"

        for i, api in enumerate(apis_with_stats, 1):
            success_rate = api.get_success_rate()
            perf_score = api.get_performance_score()
            total_calls = api.success_count + api.failure_count

            stats_text += f"**{i}. {api.name}** ({self.format_inline_code(api.id)})\n"
            stats_text += f"  Performance Score: {perf_score:.1f}/100\n"
            stats_text += f"  Success Rate: {success_rate:.1f}% ({api.success_count}/{total_calls})\n"
            stats_text += f"  Avg Response Time: {api.avg_response_time:.2f}s\n"
            stats_text += f"  Priority: {api.priority} | Enabled: {'Yes' if api.enabled else 'No'}\n"
            stats_text += "\n"

        # Truncate if too long for Discord
        stats_text = self.truncate_message(stats_text)
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
            dict: Test results with success status, IP, response time, and error
        """
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
                        "ip": None,
                    }

                # Update API statistics
                api.record_success(response_time)

                return {
                    "success": True,
                    "ip": ip,
                    "response_time": response_time,
                    "error": None,
                }

        except httpx.HTTPStatusError as e:
            response_time = time.time() - start_time
            api.record_failure()

            # Check for rate limiting
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "unknown")
                error_msg = f"Rate limit exceeded (retry after {retry_after}s)"
            else:
                error_msg = f"HTTP {e.response.status_code}: {e.response.text}"

            return {
                "success": False,
                "error": error_msg,
                "response_time": response_time,
                "ip": None,
            }

        except Exception as e:
            response_time = time.time() - start_time
            api.record_failure()

            return {
                "success": False,
                "error": str(e),
                "response_time": response_time,
                "ip": None,
            }

    def _get_api_help_text(self) -> str:
        """
        Get help text for API commands.

        Returns:
            str: Help text for API commands
        """
        return """**IP API Management Commands:**
• `!api list` - List all configured APIs with status
• `!api add <name> <url> [format] [field]` - Add new API endpoint
• `!api remove <api_id>` - Remove API endpoint
• `!api enable <api_id>` - Enable API endpoint
• `!api disable <api_id>` - Disable API endpoint
• `!api test <api_id>` - Test API endpoint
• `!api priority <api_id> <priority>` - Set API priority
• `!api stats` - Show API performance statistics

**Response Formats:**
• `json` - JSON response with IP in specified field
• `text` - Plain text IP response
• `auto` - Auto-detect format (default)

**Examples:**
• `!api add "My API" "https://api.example.com/ip" json ip`
• `!api add "Simple API" "https://text.example.com/" text`
• `!api test my_api`
• `!api priority my_api 1`"""

    def get_help_text(self) -> str:
        """
        Get help text for API commands.

        Returns:
            str: Help text describing available commands
        """
        return self._get_api_help_text()
