"""
Cache handler for admin commands.
"""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

import discord

from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage, SQLiteIPStorage

from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class CacheHandler(BaseHandler):
    """
    Handles cache-related admin commands.
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
        Initialize the cache handler.

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
        Handle cache commands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments

        Returns:
            bool: True if command was handled successfully, False otherwise
        """
        if not args:
            return False

        command = args[0].lower()

        if command == "cache":
            return await self._handle_cache_command(message, args[1:])

        return False

    async def _handle_cache_command(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache command and its subcommands.

        Args:
            message: The Discord message containing the command
            args: List of command arguments (excluding 'cache')

        Returns:
            bool: True if handled successfully
        """
        # Check admin permissions
        if not self.check_admin_permissions(message):
            await self.send_permission_denied(message)
            return False

        self.log_command_usage(message, "cache")

        if not args:
            # Show cache help text
            help_text = self._get_cache_help_text()
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, help_text
            )
            return True

        subcommand = args[0].lower()

        try:
            if subcommand == "show":
                return await self._handle_cache_show(message, args)
            if subcommand == "clear":
                return await self._handle_cache_clear(message, args)
            if subcommand == "stats":
                return await self._handle_cache_stats(message, args)
            if subcommand == "cleanup":
                return await self._handle_cache_cleanup(message, args)
            if subcommand == "refresh":
                return await self._handle_cache_refresh(message, args)
            await self.send_error_message(
                message, f"Unknown cache subcommand: {subcommand}"
            )
            return False
        except Exception as e:
            await self.handle_command_error(message, e, f"cache {subcommand}")
            return False

    async def _handle_cache_show(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache show command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.send_info_message(message, "Cache Status: Disabled")
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
            await self.send_error_message(message, f"Error getting cache status: {e}")
            logger.error(f"Error handling cache show command: {e}")
            return False

    async def _handle_cache_clear(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache clear [namespace] command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.send_error_message(message, "Cache is disabled")
                return True

            namespace = None
            if len(args) > 1:
                namespace = args[1]

            cleared_count = self.ip_service.invalidate_cache(namespace)

            if namespace:
                success_msg = (
                    f"Cleared {cleared_count} entries from namespace '{namespace}'"
                )
            else:
                success_msg = f"Cleared all {cleared_count} cache entries"

            await self.send_success_message(message, success_msg)

            logger.info(
                f"Admin {message.author} cleared cache (namespace: {namespace})"
            )
            return True

        except Exception as e:
            await self.send_error_message(message, f"Error clearing cache: {e}")
            logger.error(f"Error handling cache clear command: {e}")
            return False

    async def _handle_cache_stats(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache stats command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.send_error_message(message, "Cache is disabled")
                return True

            stats = cache_info["stats"]

            # Get cache instance for detailed stats
            try:
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

                max_memory_size = cache.max_memory_size
            except Exception:
                type_breakdown = "  Unable to retrieve entry types"
                max_memory_size = "Unknown"

            total_requests = stats["hits"] + stats["misses"]
            hit_rate = stats["hit_rate"] * 100 if "hit_rate" in stats else 0
            miss_rate = 100 - hit_rate if total_requests > 0 else 0

            # Determine efficiency rating
            if hit_rate > 80:
                efficiency = "Excellent"
            elif hit_rate > 60:
                efficiency = "Good"
            elif hit_rate > 40:
                efficiency = "Fair"
            else:
                efficiency = "Poor"

            response = (
                "📊 **Detailed Cache Statistics**\n"
                f"```\n"
                f"Cache Configuration:\n"
                f"  TTL:              {cache_info['cache_ttl']} seconds\n"
                f"  Stale Threshold:  {cache_info['stale_threshold']:.1f}\n"
                f"  Max Memory Size:  {max_memory_size} entries\n"
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
                f"  Efficiency:       {efficiency}\n"
                f"\n"
                f"Maintenance Operations:\n"
                f"  Evictions:        {stats['evictions']}\n"
                f"  Invalidations:    {stats['invalidations']}\n"
                f"  Refreshes:        {stats['refreshes']}\n"
                f"  Disk Saves:       {stats['saves']}\n"
                f"  Disk Loads:       {stats['loads']}\n"
                f"```"
            )

            # Truncate if too long for Discord
            response = self.truncate_message(response)
            await self.discord_rate_limiter.send_message_with_backoff(
                message.channel, response
            )

            logger.info(f"Admin {message.author} viewed cache statistics")
            return True

        except Exception as e:
            await self.send_error_message(
                message, f"Error getting cache statistics: {e}"
            )
            logger.error(f"Error handling cache stats command: {e}")
            return False

    async def _handle_cache_cleanup(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache cleanup command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.send_error_message(message, "Cache is disabled")
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
            await self.send_error_message(
                message, f"Error performing cache cleanup: {e}"
            )
            logger.error(f"Error handling cache cleanup command: {e}")
            return False

    async def _handle_cache_refresh(
        self, message: discord.Message, args: list[str]
    ) -> bool:
        """
        Handle the !cache refresh command.

        Args:
            message: The Discord message
            args: Command arguments

        Returns:
            bool: True if handled successfully
        """
        try:
            cache_info = self.ip_service.get_cache_info()

            if not cache_info["enabled"]:
                await self.send_error_message(message, "Cache is disabled")
                return True

            # Send initial message
            await self.send_info_message(
                message, "Refreshing stale cache entries... Please wait."
            )

            refreshed_count = await self.ip_service.refresh_stale_cache_entries()

            if refreshed_count > 0:
                success_msg = (
                    f"Successfully refreshed {refreshed_count} stale cache entries"
                )
            else:
                success_msg = "No stale cache entries found to refresh"

            await self.send_success_message(message, success_msg)

            logger.info(
                f"Admin {message.author} refreshed {refreshed_count} cache entries"
            )
            return True

        except Exception as e:
            await self.send_error_message(
                message, f"Error refreshing cache entries: {e}"
            )
            logger.error(f"Error handling cache refresh command: {e}")
            return False

    def _get_cache_help_text(self) -> str:
        """
        Get help text for cache commands.

        Returns:
            str: Help text for cache commands
        """
        return """**🗄️ Cache Management Commands**
• `!cache show` - Show cache status and statistics
• `!cache clear` - Clear all cache entries
• `!cache clear <namespace>` - Clear specific namespace (ip_check, global)
• `!cache stats` - Show detailed cache statistics
• `!cache cleanup` - Force cleanup of expired entries
• `!cache refresh` - Refresh stale cache entries

**Cache Information:**
• View current cache status and performance metrics
• Monitor hit rates and efficiency ratings
• Clear cache entries to force fresh data retrieval
• Maintain cache health with cleanup operations
• Proactively refresh stale entries"""

    def get_help_text(self) -> str:
        """
        Get help text for cache commands.

        Returns:
            str: Help text describing available commands
        """
        return self._get_cache_help_text()
