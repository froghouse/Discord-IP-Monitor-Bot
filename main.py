import asyncio
import ipaddress
import json
import logging
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import discord
import httpx
from discord.ext import tasks
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", mode="a"),  # Append mode to preserve old logs
        logging.StreamHandler(),
    ],
    datefmt="%Y-%m-%d %H:%M:%S",  # More readable timestamp format
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Additional configuration options with defaults
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))  # seconds
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
IP_HISTORY_SIZE = int(
    os.getenv("IP_HISTORY_SIZE", "10")
)  # number of IPs to store in history
STARTUP_MESSAGE_ENABLED = os.getenv("STARTUP_MESSAGE_ENABLED", "true").lower() == "true"
TESTING_MODE = os.getenv("TESTING_MODE", "false").lower() == "true"
CONCURRENT_API_CHECKS = os.getenv("CONCURRENT_API_CHECKS", "true").lower() == "true"
RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "300"))  # seconds
MAX_CHECKS_PER_PERIOD = int(
    os.getenv("MAX_CHECKS_PER_PERIOD", "10")
)  # number of checks allowed per period

# Initialize IP check lock
ip_check_lock = asyncio.Lock()

# Set log level from environment variable
try:
    logger.setLevel(getattr(logging, LOG_LEVEL))
except AttributeError:
    logger.setLevel(logging.INFO)
    logger.warning(f"Invalid LOG_LEVEL: {LOG_LEVEL}. Using INFO instead.")

# Bot configuration with validation
try:
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN not set")

    CHANNEL_ID = os.getenv("CHANNEL_ID", "0")
    CHANNEL_ID = int(CHANNEL_ID)
    if CHANNEL_ID <= 0:
        raise ValueError("CHANNEL_ID must be a positive integer")

    CHECK_INTERVAL = os.getenv("CHECK_INTERVAL", "30")
    CHECK_INTERVAL = int(CHECK_INTERVAL)
    if CHECK_INTERVAL <= 0:
        raise ValueError("CHECK_INTERVAL must be positive")

    # Add validation for file paths
    IP_FILE = os.getenv("IP_FILE", "last_ip.json")
    IP_HISTORY_FILE = os.getenv("IP_HISTORY_FILE", "ip_history.json")

    # Optional: Validate that the directories exist and are writable
    ip_file_dir = os.path.dirname(IP_FILE) or "."
    history_file_dir = os.path.dirname(IP_HISTORY_FILE) or "."

    if not os.path.exists(ip_file_dir):
        logger.warning(f"Directory for IP_FILE does not exist: {ip_file_dir}")
    if not os.path.exists(history_file_dir):
        logger.warning(
            f"Directory for IP_HISTORY_FILE does not exist: {history_file_dir}"
        )

except ValueError as e:
    logger.error(f"Configuration error: {e}")
    exit(1)


# Thread-safe rate limiter class
class RateLimiter:
    def __init__(self, period: int, max_calls: int):
        """
        Initialize a thread-safe rate limiter.

        Args:
            period: Time window in seconds
            max_calls: Maximum number of calls allowed in the time window
        """
        self.period = period
        self.max_calls = max_calls
        self.calls = []  # List of timestamps
        self.lock = threading.Lock()  # Reentrant lock for thread safety

    def is_limited(self) -> Tuple[bool, int]:
        """
        Check if the rate limit is reached.

        Returns:
            Tuple of (is_limited, seconds_to_wait)
        """
        with self.lock:
            current_time = time.time()

            # Remove timestamps older than the rate limit period
            self.calls = [t for t in self.calls if current_time - t < self.period]

            # Check if we've reached the maximum number of calls
            if len(self.calls) >= self.max_calls:
                # Calculate when the oldest call will expire
                oldest_call = min(self.calls)
                seconds_to_wait = int(self.period - (current_time - oldest_call))
                return True, max(1, seconds_to_wait)  # Ensure at least 1 second wait

            return False, 0

    def record_call(self):
        """Record a timestamp for a call."""
        with self.lock:
            self.calls.append(time.time())

    def get_remaining_calls(self) -> int:
        """Get the number of remaining calls allowed in the current period."""
        with self.lock:
            # Clean up expired calls first
            current_time = time.time()
            self.calls = [t for t in self.calls if current_time - t < self.period]
            return self.max_calls - len(self.calls)


# Initialize rate limiter
rate_limiter = RateLimiter(period=RATE_LIMIT_PERIOD, max_calls=MAX_CHECKS_PER_PERIOD)

# Initialize Discord client with intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def atomic_write_json(file_path: str, data: Any) -> bool:
    """
    Write data to a JSON file atomically using a temporary file.

    Args:
        file_path: Path to the target file
        data: Data to write (must be JSON serializable)

    Returns:
        bool: True if successful, False otherwise
    """
    # Create directory if it doesn't exist
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            return False

    # Create a temporary file in the same directory
    try:
        fd, temp_path = tempfile.mkstemp(dir=directory or os.getcwd())

        # Close the file descriptor returned by mkstemp
        os.close(fd)

        # Write the data to the temporary file
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
            # Ensure data is written to disk
            f.flush()
            os.fsync(f.fileno())

        # Rename the temporary file to the target file (atomic operation on most file systems)
        shutil.move(temp_path, file_path)

        return True
    except Exception as e:
        logger.error(f"Error writing to {file_path}: {e}")
        # Clean up the temporary file if it exists
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as remove_error:
                logger.warning(
                    f"Failed to remove temporary file {temp_path}: {remove_error}"
                )
        return False


def is_valid_ip(ip: str) -> bool:
    """Validate if the given string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


async def fetch_ip_from_api(client: httpx.AsyncClient, api: str) -> Optional[str]:
    """
    Fetch IP from a single API endpoint.

    Args:
        client: httpx AsyncClient to use for the request
        api: URL of the API to query

    Returns:
        IP address string or None if unsuccessful
    """
    try:
        logger.debug(f"Trying to get IP from {api}")
        response = await client.get(api)
        response.raise_for_status()

        if "json" in api:
            try:
                ip = response.json()["ip"]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse JSON from {api}: {e}")
                return None
        else:
            ip = response.text.strip()

        if is_valid_ip(ip):
            logger.debug(f"Successfully got IP {ip} from {api}")
            return ip
        else:
            logger.warning(f"Invalid IP address returned by {api}: {ip}")
            return None

    except httpx.HTTPError as e:
        logger.warning(f"Failed to get IP from {api}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Unexpected error while fetching from {api}: {e}")
        return None


async def get_public_ip() -> Optional[str]:
    """Get the current public IP address with fallback APIs and retry logic using async httpx."""
    apis = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/ip",
        "https://api.ipify.org",
        "https://icanhazip.com/",
        "https://checkip.amazonaws.com/",
    ]

    # Check if we're rate limited
    is_limited, wait_time = rate_limiter.is_limited()
    if is_limited:
        logger.warning(
            f"Rate limit reached. Need to wait {wait_time} seconds before next check."
        )
        await asyncio.sleep(wait_time)

    # Record this check attempt
    rate_limiter.record_call()

    # Use an async client for all requests
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES):
            # If we should check APIs concurrently
            if CONCURRENT_API_CHECKS:
                # Create tasks for all APIs
                tasks = [fetch_ip_from_api(client, api) for api in apis]
                # Wait for first successful result
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for result in results:
                    if isinstance(result, str) and is_valid_ip(result):
                        return result

                # If we get here, all concurrent checks failed
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"All IP APIs failed concurrently, retrying in {RETRY_DELAY} seconds..."
                    )
                    await asyncio.sleep(RETRY_DELAY)
                continue

            # Sequential API checking (fallback approach)
            for api in apis:
                ip = await fetch_ip_from_api(client, api)
                if ip:
                    return ip

            # If we get here, all APIs failed in this sequential attempt
            if attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"All IP APIs failed sequentially, retrying in {RETRY_DELAY} seconds..."
                )
                await asyncio.sleep(RETRY_DELAY)

    logger.error("All IP APIs failed after maximum retry attempts")
    return None


def load_ip_history() -> List[Dict[str, Any]]:
    """Load the IP address history from file."""
    if os.path.exists(IP_HISTORY_FILE):
        try:
            with open(IP_HISTORY_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                logger.warning("Invalid format in IP history file")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading IP history: {e}")
    return []


def save_ip_history(history: List[Dict[str, Any]]) -> bool:
    """Save the IP address history to file."""
    try:
        # Limit the history size
        if len(history) > IP_HISTORY_SIZE:
            history = history[-IP_HISTORY_SIZE:]

        return atomic_write_json(IP_HISTORY_FILE, history)
    except Exception as e:
        logger.error(f"Error saving IP history: {e}")
        return False


def load_last_ip() -> Optional[str]:
    """Load the last known IP from file."""
    if os.path.exists(IP_FILE):
        try:
            with open(IP_FILE, "r") as f:
                data = json.load(f)
                ip = data.get("ip")
                if ip and is_valid_ip(ip):
                    return ip
                logger.warning("Invalid or missing IP in last_ip.json")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading last IP: {e}")
    return None


def save_current_ip(ip: str) -> bool:
    """Save the current IP to file and update history."""
    timestamp = datetime.now().isoformat()
    success = True

    # Save to last_ip.json
    if not atomic_write_json(IP_FILE, {"ip": ip, "timestamp": timestamp}):
        success = False

    # Update IP history
    try:
        history = load_ip_history()
        history.append({"ip": ip, "timestamp": timestamp})
        if not save_ip_history(history):
            success = False
    except Exception as e:
        logger.error(f"Error updating IP history: {e}")
        success = False

    return success


async def send_message_with_retry(channel, content: str, max_retries: int = 3) -> bool:
    """Send a message to a Discord channel with retry logic."""
    for attempt in range(max_retries):
        try:
            await channel.send(content)
            return True
        except discord.DiscordException as e:
            logger.warning(
                f"Failed to send message, attempt {attempt + 1}/{max_retries}: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2)  # Wait before retrying

    logger.error(f"Failed to send message after {max_retries} attempts")
    return False


@client.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    try:
        logger.info(f"Logged in as {client.user} (ID: {client.user.id})")

        channel = client.get_channel(CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {CHANNEL_ID}. Stopping bot.")
            await client.close()
            return

        if STARTUP_MESSAGE_ENABLED:
            try:
                await channel.send(
                    f"🟢 IP Monitor Bot started! Will check IP every {CHECK_INTERVAL} minutes."
                )
            except discord.DiscordException as e:
                logger.error(f"Failed to send startup message: {e}")
                # Continue running even if startup message fails

        # Check for IP immediately on startup
        await check_ip_once()

        # Start the scheduled task
        check_ip_changes.start()
    except discord.DiscordException as e:
        logger.error(f"Discord error in on_ready handler: {e}")
        # Try to gracefully shut down if we can't initialize properly
        await client.close()
    except Exception as e:
        logger.error(f"Unexpected error in on_ready handler: {e}", exc_info=True)
        # Try to gracefully shut down if we can't initialize properly
        await client.close()


async def check_ip_once() -> bool:
    """
    Check the IP once (used at startup and for manual checks).

    Returns:
        bool: True if check was successful, False otherwise
    """
    try:
        channel = client.get_channel(CHANNEL_ID)
        if not channel:
            logger.error(f"Could not find channel with ID {CHANNEL_ID}")
            return False

        # Check if we're rate limited
        is_limited, wait_time = rate_limiter.is_limited()
        if is_limited:
            logger.warning(f"Rate limit reached. Need to wait {wait_time} seconds.")
            await send_message_with_retry(
                channel, f"⏳ Rate limit reached. Try again in {wait_time} seconds."
            )
            return False

        # Use lock to prevent race conditions
        async with ip_check_lock:
            current_ip = await get_public_ip()
            if not current_ip:
                logger.warning("Could not retrieve current public IP")
                await send_message_with_retry(
                    channel, "❌ Unable to retrieve current public IP address."
                )
                return False

            last_ip = load_last_ip()

            if last_ip is None:
                await send_message_with_retry(
                    channel, f"📡 Initial IP address detected: `{current_ip}`"
                )
                if not save_current_ip(current_ip):
                    await send_message_with_retry(
                        channel, "⚠️ Warning: Failed to save IP to file"
                    )
            elif last_ip != current_ip:
                await send_message_with_retry(
                    channel,
                    f"🔄 IP address changed!\nOld IP: `{last_ip}`\nNew IP: `{current_ip}`",
                )
                if not save_current_ip(current_ip):
                    await send_message_with_retry(
                        channel, "⚠️ Warning: Failed to save IP to file"
                    )
                logger.info(f"IP changed from {last_ip} to {current_ip}")
            else:
                logger.debug(f"IP unchanged: {current_ip}")

        return True

    except discord.DiscordException as e:
        logger.error(f"Discord error in check_ip_once: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in check_ip_once: {e}", exc_info=True)
        return False


@client.event
async def on_message(message):
    """Handle incoming messages for bot commands."""
    try:
        # Skip messages from the bot itself
        if message.author == client.user:
            return

        # Only process commands in the designated channel or from admins
        if (
            message.channel.id != CHANNEL_ID
            and not message.author.guild_permissions.administrator
        ):
            return

        if message.content.startswith("!ip"):
            # Manual IP check command
            logger.info(f"Manual IP check requested by {message.author}")
            await message.add_reaction("⏳")  # Add reaction to indicate processing

            # Check if we're rate limited
            is_limited, wait_time = rate_limiter.is_limited()
            if is_limited:
                await message.remove_reaction("⏳", client.user)
                await message.add_reaction("🛑")
                await message.reply(
                    f"⏳ Rate limit reached. Try again in {wait_time} seconds."
                )
                return

            success = await check_ip_once()

            await message.remove_reaction("⏳", client.user)
            if success:
                await message.add_reaction("✅")
            else:
                await message.add_reaction("❌")

        elif message.content.startswith("!history"):
            # Show IP history command
            logger.info(f"IP history requested by {message.author}")
            history = load_ip_history()

            if not history:
                await send_message_with_retry(
                    message.channel, "No IP history available."
                )
                return

            # Format the history into a nice message
            history_text = "📜 **IP Address History**\n"
            for idx, entry in enumerate(reversed(history), 1):
                ip = entry.get("ip", "Unknown")
                timestamp_str = entry.get("timestamp", "Unknown time")
                try:
                    # Convert ISO timestamp to more readable format
                    dt = datetime.fromisoformat(timestamp_str)
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    pass

                history_text += f"{idx}. IP: `{ip}` - {timestamp_str}\n"

                # Discord message limit is 2000 chars, be safe and break if needed
                if len(history_text) > 1800 and idx < len(history):
                    history_text += f"... and {len(history) - idx} more entries"
                    break

            await send_message_with_retry(message.channel, history_text)

        elif message.content.startswith("!status"):
            # Show bot status command
            logger.info(f"Status check requested by {message.author}")

            # Format status info
            is_limited, wait_time = rate_limiter.is_limited()
            remaining_calls = rate_limiter.get_remaining_calls()

            status_text = "📊 **IP Monitor Bot Status**\n"
            status_text += f"⏱️ Checking interval: Every {CHECK_INTERVAL} minutes\n"
            status_text += f"🔄 IP API retry attempts: {MAX_RETRIES}\n"
            status_text += f"⚡ Concurrent API checking: {'Enabled' if CONCURRENT_API_CHECKS else 'Disabled'}\n"
            status_text += f"⏳ Rate limit status: {'Limited (wait ' + str(wait_time) + ' seconds)' if is_limited else 'Not limited'}\n"
            status_text += f"📝 Checks remaining in current period: {remaining_calls}/{MAX_CHECKS_PER_PERIOD}\n"
            status_text += f"📈 Current log level: {LOG_LEVEL}\n"

            # Add current IP info
            current_ip = load_last_ip()
            if current_ip:
                status_text += f"🌐 Current IP: `{current_ip}`\n"

            await send_message_with_retry(message.channel, status_text)

        elif message.content.startswith("!help"):
            # Help command
            help_text = (
                "**IP Monitor Bot Commands**\n"
                "- `!ip` - Manually check the current IP address\n"
                "- `!history` - View IP address history\n"
                "- `!status` - View bot status and configuration\n"
                "- `!help` - Show this help message\n"
                "- `!stop` - Stop the bot (admin only)\n"
            )
            await send_message_with_retry(message.channel, help_text)

        elif (
            message.content.startswith("!stop")
            and message.author.guild_permissions.administrator
        ):
            logger.info(f"Stop command received from {message.author}")
            await message.add_reaction("🛑")

            try:
                # First save the current IP one last time
                current_ip = await get_public_ip()
                if current_ip:
                    save_current_ip(current_ip)

                # Cancel the background task properly
                if check_ip_changes.is_running():
                    logger.info("Stopping scheduled IP check task")
                    check_ip_changes.cancel()

                # Send the goodbye message
                await send_message_with_retry(
                    message.channel, "🛑 Stopping bot. Goodbye!"
                )

                # Close the client connection
                logger.info("Closing client connection")
                await client.close()
            except Exception as e:
                logger.error(f"Error during shutdown: {e}", exc_info=True)
                await send_message_with_retry(
                    message.channel,
                    "⚠️ Error during shutdown. The bot may not stop cleanly.",
                )
                # Try to force close even if there was an error
                await client.close()

    except discord.DiscordException as e:
        # Handle Discord-specific exceptions
        logger.error(f"Discord error in on_message handler: {e}")
        try:
            # Attempt to notify about the error
            await message.channel.send(
                f"❌ An error occurred while processing your command: {type(e).__name__}"
            )
        except Exception as notification_error:
            # If we can't even send an error message, just log it
            logger.error(f"Failed to send error notification: {notification_error}")
    except Exception as e:
        # Handle any other unexpected exceptions
        logger.error(f"Unexpected error in on_message handler: {e}", exc_info=True)
        try:
            # Attempt to notify about the error
            await message.channel.send(
                "❌ An unexpected error occurred while processing your command"
            )
        except Exception as notification_error:
            # If we can't even send an error message, just log it
            logger.error(f"Failed to send error notification: {notification_error}")


@tasks.loop(minutes=CHECK_INTERVAL)
async def check_ip_changes():
    """Periodic task to check for IP changes."""
    try:
        await check_ip_once()
    except discord.DiscordException as e:
        logger.error(f"Discord error in scheduled IP check: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in scheduled IP check: {e}", exc_info=True)


@check_ip_changes.before_loop
async def before_check_ip():
    """Wait until the bot is ready before starting the loop."""
    try:
        await client.wait_until_ready()
    except Exception as e:
        logger.error(f"Error in before_check_ip: {e}", exc_info=True)
        # If this fails, we might need to restart the bot
        try:
            await client.close()
        except Exception as close_error:
            logger.error(f"Error while trying to close client: {close_error}")


@check_ip_changes.error
async def on_check_ip_error(error):
    """Handle errors in the scheduled task."""
    logger.error(f"Error in scheduled IP check task: {error}", exc_info=True)

    # Try to send a notification if possible
    try:
        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await send_message_with_retry(
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


if __name__ == "__main__":
    try:
        # Validate that we can write to disk before starting
        with open(IP_FILE, "a+") as f:
            pass  # Just testing write access

        # Use the newer asyncio pattern instead of get_event_loop()
        async def main():
            try:
                if TESTING_MODE:
                    logger.info(
                        "Starting in TESTING mode - will check IP once and exit"
                    )
                    ip = await get_public_ip()
                    if ip:
                        logger.info(f"Test completed successfully. Current IP: {ip}")
                    else:
                        logger.error("Test failed - could not retrieve IP")
                        return 1
                    return 0

                await client.start(TOKEN)
                return 0
            except discord.LoginFailure:
                logger.error("Invalid Discord token. Please check your bot token.")
                return 1
            except KeyboardInterrupt:
                logger.info("Bot interrupted by user")
                # Ensure task is cancelled on keyboard interrupt
                if check_ip_changes.is_running():
                    check_ip_changes.cancel()
                return 0
            except Exception as e:
                logger.error(f"Error starting bot: {e}", exc_info=True)
                return 1
            finally:
                # Ensure all tasks are cancelled
                if check_ip_changes.is_running():
                    logger.info("Stopping scheduled IP check task")
                    check_ip_changes.cancel()

                # Close the client connection if it's still open
                if not client.is_closed():
                    await client.close()

                logger.info("Bot shut down")

        # Use the newer asyncio.run() pattern
        exit_code = asyncio.run(main())
        exit(exit_code)

    except PermissionError:
        logger.critical(
            f"No permission to write to {IP_FILE}. Please check file permissions."
        )
        exit(1)
    except Exception as e:
        logger.critical(f"Fatal error during startup: {e}", exc_info=True)
        exit(1)
