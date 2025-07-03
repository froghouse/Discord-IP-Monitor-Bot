"""
Slash command implementations for IP-related commands.
"""

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage
from ip_monitor.utils.async_rate_limiter import AsyncRateLimiter
from ip_monitor.utils.message_queue import MessagePriority
from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class IPSlashCommands(commands.Cog):
    """
    Slash command implementations for IP monitoring functionality.
    """

    def __init__(
        self,
        bot: commands.Bot,
        channel_id: int,
        ip_service: IPService,
        storage: SQLiteIPStorage,
        rate_limiter: AsyncRateLimiter,
        ip_commands_handler,
    ) -> None:
        """
        Initialize the IP slash commands.

        Args:
            bot: Discord bot instance
            channel_id: Discord channel ID for bot messages
            ip_service: Service for IP address operations
            storage: Storage for IP data
            rate_limiter: Rate limiter for IP checks
            ip_commands_handler: Existing IP commands handler for reusing logic
        """
        self.bot = bot
        self.channel_id = channel_id
        self.ip_service = ip_service
        self.storage = storage
        self.rate_limiter = rate_limiter
        self.ip_commands_handler = ip_commands_handler

    @app_commands.command(name="ip", description="Check the current public IP address")
    async def ip_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command to manually check the current IP address.
        """
        try:
            await interaction.response.defer()

            logger.info(f"IP check requested by {interaction.user} via slash command")

            # Check if we're rate limited
            is_limited, wait_time = await self.rate_limiter.is_limited()
            if is_limited:
                logger.warning(f"Rate limit reached. Need to wait {wait_time} seconds.")
                await interaction.followup.send(
                    f"⚠️ Rate limit reached. Please wait {wait_time} seconds before checking again.",
                    ephemeral=True,
                )
                return

            # Get the current IP
            current_ip = await self.ip_service.get_public_ip()
            if not current_ip:
                logger.error("Failed to get current IP address")
                await interaction.followup.send(
                    "❌ Failed to retrieve the current IP address. Please try again later.",
                    ephemeral=True,
                )
                return

            # Get the last known IP
            last_ip = self.storage.load_last_ip()

            # Save the current IP (skip if in read-only mode)
            if not service_health.is_fallback_active("read_only_mode"):
                if not self.storage.save_current_ip(current_ip):
                    logger.error("Failed to save current IP address")
                    await interaction.followup.send(
                        "❌ Failed to save the current IP address. Please try again later.",
                        ephemeral=True,
                    )
                    return
            else:
                logger.debug("Skipping IP save due to read-only mode")

            # Send response with current IP information
            message = "✅ IP address check complete.\\n\\n"
            message += f"**Current IP:** `{current_ip}`\\n"
            message += f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            if last_ip:
                if last_ip != current_ip:
                    message += f"\\n\\n🔄 **IP has changed** from previous: `{last_ip}`"
                else:
                    message += f"\\n\\nNo change from previous IP: `{last_ip}`"

            await interaction.followup.send(message)

        except Exception as e:
            logger.error(f"Error in IP slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while checking the IP address.",
                    ephemeral=True,
                )
            except discord.NotFound:
                # Interaction has already been responded to or expired
                pass

    @app_commands.command(name="history", description="View IP address change history")
    async def history_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command to show IP address history.
        """
        try:
            await interaction.response.defer()

            logger.info(f"IP history requested by {interaction.user} via slash command")
            history = self.storage.load_ip_history()

            if not history:
                await interaction.followup.send(
                    "No IP history available.", ephemeral=True
                )
                return

            history_text = "📜 **IP Address History**\\n"
            for idx, entry in enumerate(reversed(history), 1):
                ip = entry.get("ip", "Unknown")
                timestamp_str = entry.get("timestamp", "Unknown time")
                try:
                    # Convert ISO timestamp to more readable format
                    dt = datetime.fromisoformat(timestamp_str)
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

                history_text += f"{idx}. IP: `{ip}` - {timestamp_str}\\n"

                # Discord message limit is 2000 chars, be safe and break if needed
                if len(history_text) > 1800 and idx < len(history):
                    history_text += f"... and {len(history) - idx} more entries"
                    break

            await interaction.followup.send(history_text)

        except Exception as e:
            logger.error(f"Error in history slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while retrieving IP history.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="status", description="View bot status and configuration")
    async def status_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command to show bot status.
        """
        try:
            await interaction.response.defer()

            logger.info(f"Status check requested by {interaction.user} via slash command")

            # Format status info
            is_limited, wait_time = await self.rate_limiter.is_limited()
            remaining_calls = await self.rate_limiter.get_remaining_calls()
            check_interval = getattr(self.ip_commands_handler, "check_interval", 30)
            max_retries = self.ip_service.max_retries
            concurrent_api_checking = self.ip_service.use_concurrent_checks

            status_text = "📊 **IP Monitor Bot Status**\\n"
            status_text += f"⏱️ Checking interval: Every {check_interval} minutes\\n"
            status_text += f"🔄 IP API retry attempts: {max_retries}\\n"
            status_text += f"⚡ Concurrent API checking: {'Enabled' if concurrent_api_checking else 'Disabled'}\\n"
            status_text += f"⏳ Rate limit status: {'Limited (wait ' + str(wait_time) + ' seconds)' if is_limited else 'Not limited'}\\n"
            status_text += f"📝 Checks remaining in current period: {remaining_calls}/{self.rate_limiter.max_calls}\\n"

            # Add circuit breaker info
            cb_info = self.ip_service.get_circuit_breaker_info()
            if cb_info["enabled"]:
                cb_state = cb_info["state"]
                if cb_state == "closed":
                    status_text += "🟢 Circuit breaker: CLOSED (normal operation)\\n"
                elif cb_state == "open":
                    time_until_half_open = cb_info.get("time_until_half_open", 0)
                    status_text += (
                        f"🔴 Circuit breaker: OPEN (retry in {time_until_half_open:.0f}s)\\n"
                    )
                elif cb_state == "half_open":
                    status_text += "🟡 Circuit breaker: HALF-OPEN (testing recovery)\\n"

                if cb_info.get("last_known_ip"):
                    status_text += f"💾 Cached IP: `{cb_info['last_known_ip']}`\\n"
            else:
                status_text += "⚪ Circuit breaker: Disabled\\n"

            # Add cache information
            cache_info = self.ip_service.get_cache_info()
            if cache_info["enabled"]:
                stats = cache_info["stats"]
                hit_rate = stats.get("hit_rate", 0) * 100
                memory_entries = stats.get("memory_entries", 0)
                memory_usage = stats.get("memory_usage_mb", 0)
                stale_entries = cache_info.get("stale_entries_count", 0)

                if memory_entries > 0:
                    status_text += f"🗄️ Cache: Enabled ({hit_rate:.1f}% hit rate)\\n"
                    status_text += (
                        f"   ↳ Entries: {memory_entries}, Memory: {memory_usage:.1f} MB"
                    )
                    if stale_entries > 0:
                        status_text += f", Stale: {stale_entries}"
                    status_text += "\\n"
                else:
                    status_text += "🗄️ Cache: Enabled (no entries yet)\\n"
            else:
                status_text += "⚪ Cache: Disabled\\n"

            # Add current IP info
            current_ip = self.storage.load_last_ip()
            if current_ip:
                status_text += f"🌐 Current IP: `{current_ip}`\\n"

            # Add service health information
            system_health = service_health.get_system_health()
            degradation_level = system_health["degradation_level"]

            if degradation_level == "normal":
                status_text += "✅ System Health: NORMAL\\n"
            elif degradation_level == "minor":
                status_text += "🟡 System Health: MINOR ISSUES\\n"
            elif degradation_level == "moderate":
                status_text += "🟠 System Health: DEGRADED\\n"
            elif degradation_level == "severe":
                status_text += "🔴 System Health: SEVERE DEGRADATION\\n"
            elif degradation_level == "critical":
                status_text += "💀 System Health: CRITICAL\\n"

            # Show failed/degraded services
            failed_services = [
                name
                for name, info in system_health["services"].items()
                if info["status"] == "failed"
            ]
            degraded_services = [
                name
                for name, info in system_health["services"].items()
                if info["status"] == "degraded"
            ]

            if failed_services:
                status_text += f"❌ Failed: {', '.join(failed_services)}\\n"
            if degraded_services:
                status_text += f"⚠️ Degraded: {', '.join(degraded_services)}\\n"

            # Show active fallbacks
            active_fallbacks = system_health["system_capabilities"]["active_fallbacks"]
            if active_fallbacks:
                status_text += f"🔄 Active Fallbacks: {', '.join(active_fallbacks)}\\n"

            # Add message queue status if available
            try:
                from ip_monitor.utils.message_queue import message_queue
                queue_status = message_queue.get_queue_status()
                status_text += f"📥 Message Queue: {queue_status['queue_size']}/{queue_status['max_queue_size']} messages\\n"

                if queue_status["queue_size"] > 0:
                    status_text += f"   ↳ Ready: {queue_status['ready_to_process']}, Scheduled: {queue_status['scheduled_for_later']}\\n"

                queue_stats = queue_status["statistics"]
                status_text += f"📊 Queue Stats: {queue_stats['total_delivered']} sent, {queue_stats['total_failed']} failed\\n"
            except Exception as e:
                logger.debug(f"Could not get message queue status: {e}")

            await interaction.followup.send(status_text)

        except Exception as e:
            logger.error(f"Error in status slash command: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while retrieving bot status.",
                    ephemeral=True,
                )
            except discord.NotFound:
                pass

    @app_commands.command(name="help", description="Display available commands and their usage")
    async def help_slash(self, interaction: discord.Interaction) -> None:
        """
        Slash command to show available commands.
        """
        try:
            help_text = (
                "**IP Monitor Bot Commands**\\n"
                "**User Commands:**\\n"
                "- `/ip` - Manually check the current IP address\\n"
                "- `/history` - View IP address history\\n"
                "- `/status` - View bot status and configuration\\n"
                "- `/help` - Show this help message\\n"
                "\\n**Admin Commands:**\\n"
                "- `/config` - Manage bot configuration\\n"
                "- `/api` - Manage IP detection APIs\\n"
                "- `/cache` - Manage intelligent caching\\n"
                "- `/queue` - Manage message queue\\n"
                "- `/stop` - Stop the bot\\n"
                "\\n*Note: Admin commands require administrator permissions.*"
            )
            await interaction.response.send_message(help_text, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in help slash command: {e}")
            try:
                await interaction.response.send_message(
                    "❌ An error occurred while displaying help.",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                pass


async def setup(bot: commands.Bot) -> None:
    """Setup function to add this cog to the bot."""
    # This will be called when the cog is loaded
    pass