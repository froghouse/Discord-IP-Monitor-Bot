"""
Core bot implementation for the IP Monitor Bot.
"""

import logging

import discord
from discord.ext import tasks

from ip_monitor.commands.admin_commands import AdminCommands
from ip_monitor.commands.ip_commands import IPCommands
from ip_monitor.config import AppConfig
from ip_monitor.ip_service import IPService
from ip_monitor.storage import IPStorage
from ip_monitor.utils.rate_limiter import RateLimiter
from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter
from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class IPMonitorBot:
    """
    Discord bot for monitoring IP address changes.
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initialize the IP Monitor Bot.

        Args:
            config: Application configuration
        """
        self.config = config

        # Set up Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        # Configure services
        self.ip_service = IPService(
            max_retries=config.max_retries,
            retry_delay=config.retry_delay,
            use_concurrent_checks=config.concurrent_api_checks,
            circuit_breaker_enabled=config.circuit_breaker_enabled,
            circuit_breaker_failure_threshold=config.circuit_breaker_failure_threshold,
            circuit_breaker_recovery_timeout=config.circuit_breaker_recovery_timeout,
        )

        self.storage = IPStorage(
            ip_file=config.ip_file,
            history_file=config.ip_history_file,
            history_size=config.ip_history_size,
        )

        self.rate_limiter = RateLimiter(
            period=config.rate_limit_period, max_calls=config.max_checks_per_period
        )

        self.discord_rate_limiter = DiscordRateLimiter()

        # Set up command handlers
        self.ip_commands = IPCommands(
            channel_id=config.channel_id,
            ip_service=self.ip_service,
            storage=self.storage,
            rate_limiter=self.rate_limiter,
        )

        self.admin_commands = AdminCommands(
            client=self.client,
            ip_service=self.ip_service,
            storage=self.storage,
            stop_callback=self._stop_bot,
        )

        # Configure client event handlers
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        # IP check task reference
        self.check_ip_task = None

        # Store original check interval for degradation adjustments
        self.base_check_interval = config.check_interval

    async def run(self) -> int:
        """
        Run the bot.

        Returns:
            int: Exit code (0 for success, non-zero for errors)
        """
        try:
            if self.config.testing_mode:
                logger.info("Starting in TESTING mode - will check IP once and exit")
                ip = await self.ip_service.get_public_ip()
                if ip:
                    logger.info(f"Test completed successfully. Current IP: {ip}")
                    return 0
                else:
                    logger.error("Test failed - could not retrieve IP")
                    return 1

            await self.client.start(self.config.discord_token)
            return 0
        except discord.LoginFailure:
            logger.error("Invalid Discord token. Please check your bot token.")
            return 1
        finally:
            # Ensure all resources are properly closed
            await self.cleanup()

    async def cleanup(self) -> None:
        """
        Clean up all resources used by the bot.
        This should be called when the bot is stopped.
        """
        logger.info("Cleaning up bot resources")

        # Cancel the background task properly
        if self.check_ip_task and self.check_ip_task.is_running():
            logger.info("Stopping scheduled IP check task")
            self.check_ip_task.cancel()
            logger.info("IP check task cancelled")

        # Close any pending HTTP connections in the IP service
        logger.info("Closing HTTP connections")
        if hasattr(self.ip_service, "close"):
            await self.ip_service.close()

        # Close the client connection
        logger.info("Closing client connection")

        # Properly close the discord.py client's HTTP session
        if hasattr(self.client, "http") and hasattr(self.client.http, "session"):
            logger.info("Closing discord.py HTTP session")
            await self.client.http.session.close()

        await self.client.close()

    async def on_ready(self) -> None:
        """
        Called when the bot is ready and connected to Discord.
        """
        try:
            logger.info(f"Logged in as {self.client.user} (ID: {self.client.user.id})")

            channel = self.client.get_channel(self.config.channel_id)
            if not channel:
                logger.error(
                    f"Could not find channel with ID {self.config.channel_id}. Stopping bot."
                )
                await self.client.close()
                return

            # Initialize circuit breaker with last known IP if available
            last_ip = self.storage.load_last_ip()
            if last_ip:
                self.ip_service.set_last_known_ip(last_ip)
                logger.info(
                    f"Initialized circuit breaker with last known IP: {last_ip}"
                )

            if self.config.startup_message_enabled:
                try:
                    await self.discord_rate_limiter.send_message_with_backoff(
                        channel,
                        f"🟢 IP Monitor Bot started! Will check IP every {self.config.check_interval} minutes.",
                    )
                except Exception as e:
                    logger.error(f"Failed to send startup message: {e}")
                    # Continue running even if startup message fails

            # Start the scheduled task - this will handle the initial check
            self.check_ip_task = self._create_check_ip_task()
            self.check_ip_task.start()
        except discord.DiscordException as e:
            logger.error(f"Discord error in on_ready handler: {e}")
            # Try to gracefully shut down if we can't initialize properly
            await self.client.close()
        except Exception as e:
            logger.error(f"Unexpected error in on_ready handler: {e}", exc_info=True)
            # Try to gracefully shut down if we can't initialize properly
            await self.client.close()

    def _create_check_ip_task(self) -> tasks.Loop:
        """
        Create the scheduled IP check task.

        Returns:
            The discord.ext.tasks.Loop instance
        """

        # Calculate adjusted interval based on service health
        adjusted_interval = service_health.get_adjusted_interval(
            self.base_check_interval
        )
        logger.info(
            f"Creating IP check task with {adjusted_interval:.1f} minute interval"
        )

        @tasks.loop(minutes=adjusted_interval)
        async def check_ip_changes() -> None:
            """
            Periodic task to check for IP changes with graceful degradation.
            """
            try:
                # Check if we should perform the operation in current degradation mode
                if service_health.is_fallback_active("silent_monitoring"):
                    logger.debug(
                        "Silent monitoring mode - skipping IP check notification"
                    )
                    # Still check IP but don't send notifications
                    current_ip = await self.ip_service.get_public_ip()
                    if current_ip:
                        # Save IP silently if storage is working
                        if not service_health.is_fallback_active("read_only_mode"):
                            self.storage.save_current_ip(current_ip)
                    return

                await self.ip_commands.check_ip_once(self.client, user_requested=False)
                service_health.record_success("discord_api", "scheduled_task")

            except discord.DiscordException as e:
                logger.error(f"Discord error in scheduled IP check: {e}")
                service_health.record_failure(
                    "discord_api",
                    f"Discord error in scheduled task: {e}",
                    "scheduled_task",
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error in scheduled IP check: {e}", exc_info=True
                )
                service_health.record_failure(
                    "discord_api",
                    f"Unexpected error in scheduled task: {e}",
                    "scheduled_task",
                )

        @check_ip_changes.before_loop
        async def before_check_ip() -> None:
            """
            Wait until the bot is ready before starting the loop.
            """
            try:
                await self.client.wait_until_ready()
            except Exception as e:
                logger.error(f"Error in before_check_ip: {e}", exc_info=True)
                # If this fails, we might need to restart the bot
                try:
                    await self.client.close()
                except Exception as close_error:
                    logger.error(f"Error while trying to close client: {close_error}")

        @check_ip_changes.error
        async def on_check_ip_error(error: Exception) -> None:
            """
            Handle errors in the scheduled task.
            """
            logger.error(f"Error in scheduled IP check task: {error}", exc_info=True)

            # Try to send a notification if possible
            try:
                channel = self.client.get_channel(self.config.channel_id)
                if channel:
                    await self.discord_rate_limiter.send_message_with_backoff(
                        channel,
                        "⚠️ An error occurred during scheduled IP check. Check logs for details.",
                    )
            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")

            # Restart the task
            if check_ip_changes.is_running():
                check_ip_changes.restart()
            else:
                check_ip_changes.start()

        return check_ip_changes

    def _adjust_check_interval_for_degradation(self) -> None:
        """Adjust the IP check interval based on current service health."""
        if self.check_ip_task and self.check_ip_task.is_running():
            current_interval = self.check_ip_task.minutes
            adjusted_interval = service_health.get_adjusted_interval(
                self.base_check_interval
            )

            if abs(current_interval - adjusted_interval) > 0.1:  # Significant change
                logger.info(
                    f"Adjusting IP check interval: {current_interval:.1f} → {adjusted_interval:.1f} minutes"
                )

                # Restart the task with new interval
                self.check_ip_task.cancel()
                self.check_ip_task = self._create_check_ip_task()
                self.check_ip_task.start()

    async def on_message(self, message: discord.Message) -> None:
        """
        Handle incoming messages for bot commands.

        Args:
            message: The message object from Discord
        """
        try:
            # Skip messages from the bot itself
            if message.author == self.client.user:
                return

            # Only process commands in the designated channel or from admins
            if (
                message.channel.id != self.config.channel_id
                and not message.author.guild_permissions.administrator
            ):
                return

            # Process commands
            if message.content.startswith("!ip"):
                await self.ip_commands.handle_ip_command(message, self.client)
            elif message.content.startswith("!history"):
                await self.ip_commands.handle_history_command(message)
            elif message.content.startswith("!status"):
                await self.ip_commands.handle_status_command(message)
            elif message.content.startswith("!help"):
                await self.ip_commands.handle_help_command(message)
            elif message.content.startswith("!stop"):
                await self.admin_commands.handle_stop_command(message)

        except discord.DiscordException as e:
            # Handle Discord-specific exceptions
            logger.error(f"Discord error in on_message handler: {e}")
            try:
                # Attempt to notify about the error
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel,
                    f"❌ An error occurred while processing your command: {type(e).__name__}",
                )
            except Exception as notification_error:
                # If we can't even send an error message, just log it
                logger.error(f"Failed to send error notification: {notification_error}")
        except Exception as e:
            # Handle any other unexpected exceptions
            logger.error(f"Unexpected error in on_message handler: {e}", exc_info=True)
            try:
                # Attempt to notify about the error
                await self.discord_rate_limiter.send_message_with_backoff(
                    message.channel,
                    "❌ An unexpected error occurred while processing your command",
                )
            except Exception as notification_error:
                # If we can't even send an error message, just log it
                logger.error(f"Failed to send error notification: {notification_error}")

    async def _stop_bot(self) -> None:
        """
        Stop the bot gracefully.
        """
        # Use the cleanup method to ensure all resources are properly closed
        await self.cleanup()
