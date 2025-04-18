"""
Configuration management for the IP Monitor Bot.
"""

import logging
import os
from dataclasses import dataclass
from typing import ClassVar

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration settings with validation."""

    # Discord settings
    discord_token: str
    channel_id: int

    # IP check settings
    check_interval: int  # minutes
    max_retries: int
    retry_delay: int  # seconds
    concurrent_api_checks: bool

    # Rate limiting
    rate_limit_period: int  # seconds
    max_checks_per_period: int

    # Storage settings
    ip_file: str
    ip_history_file: str
    ip_history_size: int

    # Application behavior
    startup_message_enabled: bool
    testing_mode: bool
    log_level: str

    # Class constants
    DEFAULT_MAX_RETRIES: ClassVar[int] = 3
    DEFAULT_RETRY_DELAY: ClassVar[int] = 5
    DEFAULT_CHECK_INTERVAL: ClassVar[int] = 30
    DEFAULT_IP_HISTORY_SIZE: ClassVar[int] = 10
    DEFAULT_RATE_LIMIT_PERIOD: ClassVar[int] = 300
    DEFAULT_MAX_CHECKS: ClassVar[int] = 10

    @classmethod
    def load_from_env(cls) -> "AppConfig":
        """
        Load configuration from environment variables.

        Returns:
            AppConfig: Validated configuration object

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Load environment variables from .env file
        load_dotenv()

        # Required settings
        token = os.getenv("DISCORD_BOT_TOKEN")
        if not token:
            raise ValueError("DISCORD_BOT_TOKEN not set")

        # Channel ID with validation
        channel_id_str = os.getenv("CHANNEL_ID", "0")
        try:
            channel_id = int(channel_id_str)
            if channel_id <= 0:
                raise ValueError("CHANNEL_ID must be a positive integer")
        except ValueError:
            raise ValueError(f"Invalid CHANNEL_ID: {channel_id_str}")

        # Check interval with validation
        check_interval_str = os.getenv(
            "CHECK_INTERVAL", str(cls.DEFAULT_CHECK_INTERVAL)
        )
        try:
            check_interval = int(check_interval_str)
            if check_interval <= 0:
                raise ValueError("CHECK_INTERVAL must be positive")
        except ValueError:
            raise ValueError(f"Invalid CHECK_INTERVAL: {check_interval_str}")

        # Build and return config object
        config = cls(
            discord_token=token,
            channel_id=channel_id,
            check_interval=check_interval,
            max_retries=int(os.getenv("MAX_RETRIES", str(cls.DEFAULT_MAX_RETRIES))),
            retry_delay=int(os.getenv("RETRY_DELAY", str(cls.DEFAULT_RETRY_DELAY))),
            concurrent_api_checks=os.getenv("CONCURRENT_API_CHECKS", "true").lower()
            == "true",
            rate_limit_period=int(
                os.getenv("RATE_LIMIT_PERIOD", str(cls.DEFAULT_RATE_LIMIT_PERIOD))
            ),
            max_checks_per_period=int(
                os.getenv("MAX_CHECKS_PER_PERIOD", str(cls.DEFAULT_MAX_CHECKS))
            ),
            ip_file=os.getenv("IP_FILE", "last_ip.json"),
            ip_history_file=os.getenv("IP_HISTORY_FILE", "ip_history.json"),
            ip_history_size=int(
                os.getenv("IP_HISTORY_SIZE", str(cls.DEFAULT_IP_HISTORY_SIZE))
            ),
            startup_message_enabled=os.getenv("STARTUP_MESSAGE_ENABLED", "true").lower()
            == "true",
            testing_mode=os.getenv("TESTING_MODE", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

        # Validate file paths
        for file_path in [config.ip_file, config.ip_history_file]:
            directory = os.path.dirname(file_path) or "."
            if directory != "." and not os.path.exists(directory):
                logger.warning(f"Directory does not exist: {directory}")

        return config
