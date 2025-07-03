"""
Configuration management for the IP Monitor Bot.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, ClassVar, Dict, Union

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

    # Circuit breaker settings
    circuit_breaker_enabled: bool
    circuit_breaker_failure_threshold: int
    circuit_breaker_recovery_timeout: float

    # Rate limiting
    rate_limit_period: int  # seconds
    max_checks_per_period: int

    # Storage settings
    db_file: str
    ip_file: str  # Keep for migration
    ip_history_file: str  # Keep for migration
    ip_history_size: int

    # Application behavior
    startup_message_enabled: bool
    testing_mode: bool
    log_level: str

    # Message queue settings
    message_queue_enabled: bool
    message_queue_max_size: int
    message_queue_max_age_hours: int
    message_queue_batch_size: int
    message_queue_process_interval: float

    # Class constants
    DEFAULT_MAX_RETRIES: ClassVar[int] = 3
    DEFAULT_RETRY_DELAY: ClassVar[int] = 5
    DEFAULT_CHECK_INTERVAL: ClassVar[int] = 30
    DEFAULT_IP_HISTORY_SIZE: ClassVar[int] = 10
    DEFAULT_RATE_LIMIT_PERIOD: ClassVar[int] = 300
    DEFAULT_MAX_CHECKS: ClassVar[int] = 10
    DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD: ClassVar[int] = 3
    DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT: ClassVar[float] = 120.0
    DEFAULT_MESSAGE_QUEUE_MAX_SIZE: ClassVar[int] = 1000
    DEFAULT_MESSAGE_QUEUE_MAX_AGE_HOURS: ClassVar[int] = 24
    DEFAULT_MESSAGE_QUEUE_BATCH_SIZE: ClassVar[int] = 5
    DEFAULT_MESSAGE_QUEUE_PROCESS_INTERVAL: ClassVar[float] = 1.0

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
            circuit_breaker_enabled=os.getenv("CIRCUIT_BREAKER_ENABLED", "true").lower()
            == "true",
            circuit_breaker_failure_threshold=int(
                os.getenv(
                    "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
                    str(cls.DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD),
                )
            ),
            circuit_breaker_recovery_timeout=float(
                os.getenv(
                    "CIRCUIT_BREAKER_RECOVERY_TIMEOUT",
                    str(cls.DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT),
                )
            ),
            rate_limit_period=int(
                os.getenv("RATE_LIMIT_PERIOD", str(cls.DEFAULT_RATE_LIMIT_PERIOD))
            ),
            max_checks_per_period=int(
                os.getenv("MAX_CHECKS_PER_PERIOD", str(cls.DEFAULT_MAX_CHECKS))
            ),
            db_file=os.getenv("DB_FILE", "ip_monitor.db"),
            ip_file=os.getenv("IP_FILE", "last_ip.json"),
            ip_history_file=os.getenv("IP_HISTORY_FILE", "ip_history.json"),
            ip_history_size=int(
                os.getenv("IP_HISTORY_SIZE", str(cls.DEFAULT_IP_HISTORY_SIZE))
            ),
            startup_message_enabled=os.getenv("STARTUP_MESSAGE_ENABLED", "true").lower()
            == "true",
            testing_mode=os.getenv("TESTING_MODE", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            message_queue_enabled=os.getenv("MESSAGE_QUEUE_ENABLED", "true").lower()
            == "true",
            message_queue_max_size=int(
                os.getenv(
                    "MESSAGE_QUEUE_MAX_SIZE", str(cls.DEFAULT_MESSAGE_QUEUE_MAX_SIZE)
                )
            ),
            message_queue_max_age_hours=int(
                os.getenv(
                    "MESSAGE_QUEUE_MAX_AGE_HOURS",
                    str(cls.DEFAULT_MESSAGE_QUEUE_MAX_AGE_HOURS),
                )
            ),
            message_queue_batch_size=int(
                os.getenv(
                    "MESSAGE_QUEUE_BATCH_SIZE",
                    str(cls.DEFAULT_MESSAGE_QUEUE_BATCH_SIZE),
                )
            ),
            message_queue_process_interval=float(
                os.getenv(
                    "MESSAGE_QUEUE_PROCESS_INTERVAL",
                    str(cls.DEFAULT_MESSAGE_QUEUE_PROCESS_INTERVAL),
                )
            ),
        )

        # Validate file paths
        for file_path in [config.ip_file, config.ip_history_file]:
            directory = os.path.dirname(file_path) or "."
            if directory != "." and not os.path.exists(directory):
                logger.warning(f"Directory does not exist: {directory}")

        return config

    def get_runtime_configurable_fields(self) -> Dict[str, Dict[str, Any]]:
        """
        Get fields that can be modified at runtime.

        Returns:
            Dict mapping field names to their metadata
        """
        configurable_fields = {
            "check_interval": {
                "type": "int",
                "min_value": 1,
                "max_value": 1440,  # 24 hours
                "description": "IP check interval in minutes",
                "unit": "minutes",
                "restart_required": True,
            },
            "max_retries": {
                "type": "int",
                "min_value": 1,
                "max_value": 10,
                "description": "Maximum retry attempts for IP checks",
                "restart_required": False,
            },
            "retry_delay": {
                "type": "int",
                "min_value": 1,
                "max_value": 300,
                "description": "Delay between retries in seconds",
                "unit": "seconds",
                "restart_required": False,
            },
            "concurrent_api_checks": {
                "type": "bool",
                "description": "Enable concurrent API checks",
                "restart_required": False,
            },
            "circuit_breaker_enabled": {
                "type": "bool",
                "description": "Enable circuit breaker pattern",
                "restart_required": False,
            },
            "circuit_breaker_failure_threshold": {
                "type": "int",
                "min_value": 1,
                "max_value": 20,
                "description": "Failures before circuit breaker opens",
                "restart_required": False,
            },
            "circuit_breaker_recovery_timeout": {
                "type": "float",
                "min_value": 10.0,
                "max_value": 3600.0,
                "description": "Circuit breaker recovery timeout in seconds",
                "unit": "seconds",
                "restart_required": False,
            },
            "rate_limit_period": {
                "type": "int",
                "min_value": 60,
                "max_value": 3600,
                "description": "Rate limit period in seconds",
                "unit": "seconds",
                "restart_required": False,
            },
            "max_checks_per_period": {
                "type": "int",
                "min_value": 1,
                "max_value": 100,
                "description": "Maximum checks per rate limit period",
                "restart_required": False,
            },
            "ip_history_size": {
                "type": "int",
                "min_value": 1,
                "max_value": 100,
                "description": "Maximum IP history entries to store",
                "restart_required": False,
            },
            "startup_message_enabled": {
                "type": "bool",
                "description": "Enable startup notification message",
                "restart_required": False,
            },
            "message_queue_enabled": {
                "type": "bool",
                "description": "Enable async message queue",
                "restart_required": False,
            },
            "message_queue_max_size": {
                "type": "int",
                "min_value": 10,
                "max_value": 10000,
                "description": "Maximum messages in queue",
                "restart_required": False,
            },
            "message_queue_max_age_hours": {
                "type": "int",
                "min_value": 1,
                "max_value": 168,  # 1 week
                "description": "Maximum message age in hours",
                "unit": "hours",
                "restart_required": False,
            },
            "message_queue_batch_size": {
                "type": "int",
                "min_value": 1,
                "max_value": 50,
                "description": "Messages processed per batch",
                "restart_required": False,
            },
            "message_queue_process_interval": {
                "type": "float",
                "min_value": 0.1,
                "max_value": 60.0,
                "description": "Interval between processing batches",
                "unit": "seconds",
                "restart_required": False,
            },
        }
        return configurable_fields

    def validate_config_value(
        self, field_name: str, value: str
    ) -> tuple[bool, Union[Any, str]]:
        """
        Validate a configuration value.

        Args:
            field_name: Name of the configuration field
            value: String value to validate and convert

        Returns:
            Tuple of (is_valid, converted_value_or_error_message)
        """
        configurable_fields = self.get_runtime_configurable_fields()

        if field_name not in configurable_fields:
            return False, f"Field '{field_name}' is not configurable at runtime"

        field_info = configurable_fields[field_name]
        field_type = field_info["type"]

        try:
            # Convert value to appropriate type
            if field_type == "int":
                converted_value = int(value)
            elif field_type == "float":
                converted_value = float(value)
            elif field_type == "bool":
                if value.lower() in ["true", "yes", "1", "on", "enabled"]:
                    converted_value = True
                elif value.lower() in ["false", "no", "0", "off", "disabled"]:
                    converted_value = False
                else:
                    return (
                        False,
                        f"Invalid boolean value: '{value}'. Use true/false, yes/no, 1/0, on/off, or enabled/disabled",
                    )
            else:
                return False, f"Unsupported field type: {field_type}"

            # Validate ranges for numeric values
            if field_type in ["int", "float"]:
                if (
                    "min_value" in field_info
                    and converted_value < field_info["min_value"]
                ):
                    return (
                        False,
                        f"Value {converted_value} is below minimum {field_info['min_value']}",
                    )
                if (
                    "max_value" in field_info
                    and converted_value > field_info["max_value"]
                ):
                    return (
                        False,
                        f"Value {converted_value} is above maximum {field_info['max_value']}",
                    )

            return True, converted_value

        except ValueError as e:
            return False, f"Invalid {field_type} value: '{value}' ({str(e)})"

    def update_field(self, field_name: str, value: Any) -> bool:
        """
        Update a configuration field value.

        Args:
            field_name: Name of the field to update
            value: New value for the field

        Returns:
            bool: True if update was successful
        """
        if hasattr(self, field_name):
            setattr(self, field_name, value)
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.

        Returns:
            Dict representation of configuration
        """
        return asdict(self)

    def save_to_file(self, file_path: str) -> bool:
        """
        Save configuration to JSON file.

        Args:
            file_path: Path to save configuration file

        Returns:
            bool: True if save was successful
        """
        try:
            config_dict = self.to_dict()
            # Remove sensitive data
            config_dict.pop("discord_token", None)

            with open(file_path, "w") as f:
                json.dump(config_dict, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config to {file_path}: {e}")
            return False

    @classmethod
    def load_from_file(cls, file_path: str, base_config: "AppConfig") -> "AppConfig":
        """
        Load configuration overrides from JSON file.

        Args:
            file_path: Path to configuration file
            base_config: Base configuration to override

        Returns:
            AppConfig with overrides applied
        """
        if not os.path.exists(file_path):
            return base_config

        try:
            with open(file_path, "r") as f:
                overrides = json.load(f)

            # Apply overrides to base config
            config_dict = asdict(base_config)
            config_dict.update(overrides)

            # Create new config instance
            # We need to handle this manually since we can't use dataclass constructor directly
            new_config = cls(**config_dict)
            return new_config

        except Exception as e:
            logger.error(f"Failed to load config from {file_path}: {e}")
            return base_config
