"""Test data generators for the IP Monitor Bot.

This module provides utilities for generating realistic test data for:
- IP addresses and history
- Discord messages and interactions
- API responses and configurations
- Database records and scenarios
- Performance test datasets
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import Any
from unittest.mock import AsyncMock, Mock
import uuid


@dataclass
class IPRecord:
    """Represents an IP address record with timestamp."""

    ip: str
    timestamp: str
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "ip": self.ip,
            "timestamp": self.timestamp,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class APIEndpoint:
    """Represents an API endpoint configuration."""

    name: str
    url: str
    format: str
    field: str | None = None
    enabled: bool = True
    priority: int = 1
    success_rate: float = 0.95
    avg_response_time: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "name": self.name,
            "url": self.url,
            "format": self.format,
            "field": self.field,
            "enabled": self.enabled,
            "priority": self.priority,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
        }


class IPAddressGenerator:
    """Generates realistic IP addresses for testing."""

    @staticmethod
    def generate_public_ip() -> str:
        """Generate a realistic public IP address."""
        # Avoid private IP ranges
        while True:
            octets = [
                random.randint(1, 255),
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(1, 254),
            ]

            # Check if it's not a private IP
            if not (
                octets[0] == 10  # 10.0.0.0/8
                or (octets[0] == 172 and 16 <= octets[1] <= 31)  # 172.16.0.0/12
                or (octets[0] == 192 and octets[1] == 168)  # 192.168.0.0/16
            ):
                return f"{octets[0]}.{octets[1]}.{octets[2]}.{octets[3]}"

    @staticmethod
    def generate_private_ip() -> str:
        """Generate a private IP address."""
        ip_ranges = [
            (10, 0, 0, 0),  # 10.0.0.0/8
            (172, 16, 0, 0),  # 172.16.0.0/12
            (192, 168, 0, 0),  # 192.168.0.0/16
        ]

        base = random.choice(ip_ranges)

        if base[0] == 10:
            return f"10.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        if base[0] == 172:
            return f"172.{random.randint(16, 31)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        # 192.168
        return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"

    @staticmethod
    def generate_ip_list(count: int, public_only: bool = True) -> list[str]:
        """Generate a list of IP addresses."""
        generator = (
            IPAddressGenerator.generate_public_ip
            if public_only
            else IPAddressGenerator.generate_private_ip
        )
        return [generator() for _ in range(count)]


class IPHistoryGenerator:
    """Generates realistic IP history data."""

    @staticmethod
    def generate_ip_history(
        count: int = 10,
        start_time: datetime | None = None,
        time_interval_minutes: int = 60,
        change_probability: float = 0.3,
    ) -> list[IPRecord]:
        """Generate realistic IP history with configurable change patterns."""

        if start_time is None:
            start_time = datetime.now() - timedelta(days=7)

        history = []
        current_ip = IPAddressGenerator.generate_public_ip()
        current_time = start_time

        for i in range(count):
            # Decide whether to change IP based on probability
            if i > 0 and random.random() < change_probability:
                current_ip = IPAddressGenerator.generate_public_ip()

            record = IPRecord(
                ip=current_ip,
                timestamp=current_time.isoformat(),
                created_at=current_time,
            )
            history.append(record)

            # Advance time with some randomness
            time_variance = random.randint(
                -time_interval_minutes // 2, time_interval_minutes // 2
            )
            current_time += timedelta(minutes=time_interval_minutes + time_variance)

        return history

    @staticmethod
    def generate_frequent_changes(count: int = 20) -> list[IPRecord]:
        """Generate IP history with frequent changes (for testing edge cases)."""
        return IPHistoryGenerator.generate_ip_history(
            count=count, time_interval_minutes=5, change_probability=0.8
        )

    @staticmethod
    def generate_stable_history(count: int = 10) -> list[IPRecord]:
        """Generate IP history with rare changes (stable connection)."""
        return IPHistoryGenerator.generate_ip_history(
            count=count, time_interval_minutes=120, change_probability=0.1
        )


class DiscordDataGenerator:
    """Generates Discord-related test data."""

    @staticmethod
    def generate_user_id() -> int:
        """Generate a realistic Discord user ID."""
        return random.randint(100000000000000000, 999999999999999999)

    @staticmethod
    def generate_channel_id() -> int:
        """Generate a realistic Discord channel ID."""
        return random.randint(100000000000000000, 999999999999999999)

    @staticmethod
    def generate_guild_id() -> int:
        """Generate a realistic Discord guild ID."""
        return random.randint(100000000000000000, 999999999999999999)

    @staticmethod
    def generate_username() -> str:
        """Generate a realistic Discord username."""
        adjectives = [
            "Cool",
            "Fast",
            "Smart",
            "Brave",
            "Lucky",
            "Swift",
            "Bright",
            "Bold",
        ]
        nouns = ["Bot", "User", "Player", "Coder", "Gamer", "Master", "Pro", "Ninja"]

        return f"{random.choice(adjectives)}{random.choice(nouns)}{random.randint(1, 9999)}"

    @staticmethod
    def generate_mock_message(
        content: str = "!test",
        user_id: int | None = None,
        channel_id: int | None = None,
        is_admin: bool = False,
    ) -> Mock:
        """Generate a mock Discord message."""
        message = Mock()
        message.author = Mock()
        message.author.id = user_id or DiscordDataGenerator.generate_user_id()
        message.author.name = DiscordDataGenerator.generate_username()
        message.author.guild_permissions = Mock()
        message.author.guild_permissions.administrator = is_admin

        message.channel = Mock()
        message.channel.id = channel_id or DiscordDataGenerator.generate_channel_id()
        message.channel.send = AsyncMock()

        message.content = content
        message.id = random.randint(100000000000000000, 999999999999999999)

        return message

    @staticmethod
    def generate_mock_interaction(
        command_name: str = "test",
        user_id: int | None = None,
        is_admin: bool = False,
    ) -> Mock:
        """Generate a mock Discord interaction for slash commands."""
        interaction = AsyncMock()

        interaction.user = Mock()
        interaction.user.id = user_id or DiscordDataGenerator.generate_user_id()
        interaction.user.name = DiscordDataGenerator.generate_username()
        interaction.user.guild_permissions = Mock()
        interaction.user.guild_permissions.administrator = is_admin

        interaction.guild_id = DiscordDataGenerator.generate_guild_id()
        interaction.channel_id = DiscordDataGenerator.generate_channel_id()

        interaction.command = Mock()
        interaction.command.name = command_name
        interaction.data = {"name": command_name, "options": []}

        interaction.response = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.followup.send = AsyncMock()

        return interaction


class APIResponseGenerator:
    """Generates realistic API responses for testing."""

    @staticmethod
    def generate_json_response(
        ip: str | None = None, field: str = "ip"
    ) -> dict[str, Any]:
        """Generate a JSON API response."""
        if ip is None:
            ip = IPAddressGenerator.generate_public_ip()

        return {field: ip}

    @staticmethod
    def generate_text_response(ip: str | None = None) -> str:
        """Generate a text API response."""
        if ip is None:
            ip = IPAddressGenerator.generate_public_ip()

        return ip

    @staticmethod
    def generate_complex_json_response(ip: str | None = None) -> dict[str, Any]:
        """Generate a complex JSON response with additional fields."""
        if ip is None:
            ip = IPAddressGenerator.generate_public_ip()

        return {
            "ip": ip,
            "country": random.choice(["US", "GB", "CA", "AU", "DE", "FR"]),
            "region": random.choice(["California", "Texas", "London", "Ontario"]),
            "city": random.choice(["Los Angeles", "New York", "London", "Toronto"]),
            "isp": random.choice(["Comcast", "Verizon", "AT&T", "Charter"]),
            "timezone": random.choice(
                ["America/New_York", "Europe/London", "America/Los_Angeles"]
            ),
            "lat": round(random.uniform(-90, 90), 6),
            "lon": round(random.uniform(-180, 180), 6),
        }

    @staticmethod
    def generate_error_response(
        status_code: int = 500, message: str = "Internal Server Error"
    ) -> dict[str, Any]:
        """Generate an error response."""
        return {"error": {"code": status_code, "message": message}}


class APIConfigGenerator:
    """Generates API configuration data for testing."""

    @staticmethod
    def generate_api_endpoint(
        name: str | None = None,
        url: str | None = None,
        format: str = "json",
        field: str | None = None,
    ) -> APIEndpoint:
        """Generate a single API endpoint configuration."""

        if name is None:
            name = f"Test API {random.randint(1, 1000)}"

        if url is None:
            url = f"https://api.example{random.randint(1, 100)}.com/ip"

        if field is None and format == "json":
            field = random.choice(["ip", "origin", "address", "public_ip"])

        return APIEndpoint(
            name=name,
            url=url,
            format=format,
            field=field,
            enabled=random.choice([True, False]),
            priority=random.randint(1, 10),
            success_rate=round(random.uniform(0.7, 0.99), 2),
            avg_response_time=round(random.uniform(0.1, 2.0), 2),
        )

    @staticmethod
    def generate_api_config(count: int = 5) -> list[APIEndpoint]:
        """Generate multiple API endpoint configurations."""
        configs = []

        for i in range(count):
            format_type = random.choice(["json", "text"])
            endpoint = APIConfigGenerator.generate_api_endpoint(
                name=f"Test API {i + 1}",
                url=f"https://testapi{i + 1}.example.com/ip",
                format=format_type,
            )
            configs.append(endpoint)

        return configs

    @staticmethod
    def generate_default_apis() -> list[APIEndpoint]:
        """Generate the default API configurations used by the bot."""
        return [
            APIEndpoint(
                name="IPify JSON",
                url="https://api.ipify.org?format=json",
                format="json",
                field="ip",
                enabled=True,
                priority=1,
                success_rate=0.99,
                avg_response_time=0.3,
            ),
            APIEndpoint(
                name="IPify Text",
                url="https://api.ipify.org",
                format="text",
                field=None,
                enabled=True,
                priority=2,
                success_rate=0.99,
                avg_response_time=0.3,
            ),
            APIEndpoint(
                name="ifconfig.me",
                url="https://ifconfig.me/ip",
                format="text",
                field=None,
                enabled=True,
                priority=3,
                success_rate=0.95,
                avg_response_time=0.5,
            ),
            APIEndpoint(
                name="icanhazip.com",
                url="https://icanhazip.com",
                format="text",
                field=None,
                enabled=True,
                priority=4,
                success_rate=0.95,
                avg_response_time=0.4,
            ),
            APIEndpoint(
                name="AWS CheckIP",
                url="https://checkip.amazonaws.com",
                format="text",
                field=None,
                enabled=True,
                priority=5,
                success_rate=0.98,
                avg_response_time=0.2,
            ),
        ]


class DatabaseRecordGenerator:
    """Generates database records for testing."""

    @staticmethod
    def generate_current_ip_record(ip: str | None = None) -> tuple[str, str]:
        """Generate a current IP record for database insertion."""
        if ip is None:
            ip = IPAddressGenerator.generate_public_ip()

        timestamp = datetime.now().isoformat()
        return ip, timestamp

    @staticmethod
    def generate_ip_history_records(count: int = 10) -> list[tuple[str, str]]:
        """Generate IP history records for database insertion."""
        history = IPHistoryGenerator.generate_ip_history(count)
        return [(record.ip, record.timestamp) for record in history]

    @staticmethod
    def generate_bulk_test_data(
        current_ip_count: int = 1, history_count: int = 100
    ) -> dict[str, list[tuple[str, str]]]:
        """Generate bulk test data for database performance testing."""

        return {
            "current_ip": [
                DatabaseRecordGenerator.generate_current_ip_record()
                for _ in range(current_ip_count)
            ],
            "ip_history": DatabaseRecordGenerator.generate_ip_history_records(
                history_count
            ),
        }


class ConfigurationGenerator:
    """Generates configuration data for testing."""

    @staticmethod
    def generate_bot_config(
        custom_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate bot configuration with realistic values."""

        default_config = {
            "check_interval": random.randint(60, 1440),
            "max_retries": random.randint(1, 10),
            "retry_delay": random.randint(1, 300),
            "concurrent_api_checks": random.choice([True, False]),
            "circuit_breaker_enabled": random.choice([True, False]),
            "circuit_breaker_failure_threshold": random.randint(1, 20),
            "circuit_breaker_recovery_timeout": random.randint(10, 3600),
            "rate_limit_period": random.randint(60, 3600),
            "max_checks_per_period": random.randint(1, 100),
            "ip_history_size": random.randint(1, 100),
            "startup_message_enabled": random.choice([True, False]),
            "custom_apis_enabled": random.choice([True, False]),
            "message_queue_enabled": random.choice([True, False]),
            "message_queue_max_size": random.randint(10, 10000),
            "message_queue_max_age_hours": random.randint(1, 168),
            "message_queue_batch_size": random.randint(1, 50),
            "message_queue_process_interval": round(random.uniform(0.1, 60.0), 1),
            "connection_pool_size": random.randint(1, 100),
            "connection_pool_max_keepalive": random.randint(1, 50),
            "connection_timeout": round(random.uniform(1.0, 60.0), 1),
            "read_timeout": round(random.uniform(1.0, 300.0), 1),
            "cache_enabled": random.choice([True, False]),
            "cache_ttl": random.randint(30, 3600),
            "cache_max_memory_size": random.randint(100, 10000),
            "cache_stale_threshold": round(random.uniform(0.1, 0.9), 1),
            "cache_cleanup_interval": random.randint(60, 3600),
        }

        if custom_values:
            default_config.update(custom_values)

        return default_config


class MessageQueueDataGenerator:
    """Generates message queue data for testing."""

    @staticmethod
    def generate_queued_message(
        priority: str = "NORMAL",
        content: str | None = None,
        channel_id: int | None = None,
    ) -> dict[str, Any]:
        """Generate a queued message."""

        if content is None:
            content = f"Test message {random.randint(1, 1000)}"

        if channel_id is None:
            channel_id = DiscordDataGenerator.generate_channel_id()

        return {
            "id": str(uuid.uuid4()),
            "priority": priority,
            "content": content,
            "channel_id": channel_id,
            "timestamp": datetime.now().isoformat(),
            "attempts": 0,
            "max_attempts": 3,
        }

    @staticmethod
    def generate_message_queue_batch(
        count: int = 10, priority_distribution: dict[str, float] | None = None
    ) -> list[dict[str, Any]]:
        """Generate a batch of queued messages."""

        if priority_distribution is None:
            priority_distribution = {
                "CRITICAL": 0.1,
                "HIGH": 0.2,
                "NORMAL": 0.6,
                "LOW": 0.1,
            }

        messages = []
        priorities = list(priority_distribution.keys())
        weights = list(priority_distribution.values())

        for _ in range(count):
            priority = random.choices(priorities, weights=weights)[0]
            message = MessageQueueDataGenerator.generate_queued_message(
                priority=priority
            )
            messages.append(message)

        return messages


class TestScenarioGenerator:
    """Generates complete test scenarios combining multiple data types."""

    @staticmethod
    def generate_ip_change_scenario(changes: int = 3) -> dict[str, Any]:
        """Generate a complete IP change scenario."""

        history = IPHistoryGenerator.generate_ip_history(changes + 1)

        return {
            "initial_ip": history[0].ip,
            "ip_changes": [
                {
                    "old_ip": history[i].ip,
                    "new_ip": history[i + 1].ip,
                    "timestamp": history[i + 1].timestamp,
                    "change_detected": True,
                }
                for i in range(len(history) - 1)
            ],
            "final_ip": history[-1].ip,
            "total_changes": changes,
            "timeline": [record.to_dict() for record in history],
        }

    @staticmethod
    def generate_performance_test_scenario(
        operations: int = 100, concurrent_users: int = 10, duration_minutes: int = 5
    ) -> dict[str, Any]:
        """Generate a performance test scenario."""

        return {
            "scenario_name": f"Performance Test {random.randint(1, 1000)}",
            "operations": operations,
            "concurrent_users": concurrent_users,
            "duration_minutes": duration_minutes,
            "target_ops_per_second": operations / (duration_minutes * 60),
            "test_ips": IPAddressGenerator.generate_ip_list(operations),
            "api_endpoints": APIConfigGenerator.generate_api_config(5),
            "expected_success_rate": 0.95,
            "expected_avg_response_time": 0.5,
        }

    @staticmethod
    def generate_error_handling_scenario() -> dict[str, Any]:
        """Generate an error handling test scenario."""

        return {
            "scenario_name": "Error Handling Test",
            "error_types": [
                {"type": "network_timeout", "probability": 0.1},
                {"type": "api_down", "probability": 0.05},
                {"type": "invalid_response", "probability": 0.03},
                {"type": "rate_limit", "probability": 0.02},
            ],
            "recovery_strategies": [
                {"strategy": "retry", "max_attempts": 3},
                {"strategy": "fallback_api", "fallback_count": 2},
                {"strategy": "circuit_breaker", "threshold": 3},
            ],
            "test_duration_minutes": 10,
            "expected_uptime": 0.95,
        }
