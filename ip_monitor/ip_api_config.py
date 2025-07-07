"""
Configuration and management for custom IP detection APIs.
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ResponseFormat(Enum):
    """Supported API response formats."""

    JSON = "json"  # JSON response with IP in specified field
    PLAIN_TEXT = "text"  # Plain text IP response
    AUTO = "auto"  # Auto-detect format


@dataclass
class IPAPIEndpoint:
    """Configuration for a custom IP API endpoint."""

    id: str  # Unique identifier
    name: str  # Human-readable name
    url: str  # API endpoint URL
    response_format: ResponseFormat = ResponseFormat.AUTO
    json_field: str | None = (
        None  # Field name for JSON responses (e.g., "ip", "origin")
    )
    headers: dict[str, str] | None = None  # Custom headers
    timeout: float = 10.0  # Request timeout in seconds
    enabled: bool = True  # Whether this API is enabled
    priority: int = 1  # Priority (1=highest, higher numbers = lower priority)

    # Performance tracking
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    last_success: float | None = None
    last_failure: float | None = None

    def __post_init__(self):
        """Validate the endpoint configuration."""
        if not self.url:
            raise ValueError("URL cannot be empty")

        # Validate URL format
        try:
            parsed = urlparse(self.url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            raise ValueError(f"Invalid URL: {e}")

        # Validate JSON field requirement
        if self.response_format == ResponseFormat.JSON and not self.json_field:
            raise ValueError("json_field is required for JSON format")

    def get_success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100

    def record_success(self, response_time: float) -> None:
        """Record a successful API call."""
        self.success_count += 1
        self.last_success = time.time()

        # Update average response time using moving average
        if self.avg_response_time == 0.0:
            self.avg_response_time = response_time
        else:
            # Simple moving average with more weight on recent measurements
            self.avg_response_time = (self.avg_response_time * 0.8) + (
                response_time * 0.2
            )

    def record_failure(self) -> None:
        """Record a failed API call."""
        self.failure_count += 1
        self.last_failure = time.time()

    def get_performance_score(self) -> float:
        """Calculate a performance score for API ranking."""
        success_rate = self.get_success_rate()

        # Base score from success rate
        score = success_rate

        # Penalty for slow response times (anything over 2 seconds)
        if self.avg_response_time > 2.0:
            time_penalty = min(20, (self.avg_response_time - 2.0) * 5)
            score -= time_penalty

        # Bonus for fast response times (under 1 second)
        elif self.avg_response_time > 0 and self.avg_response_time < 1.0:
            time_bonus = min(10, (1.0 - self.avg_response_time) * 10)
            score += time_bonus

        # Recent failure penalty
        if self.last_failure and time.time() - self.last_failure < 300:  # 5 minutes
            score -= 15

        return max(0, score)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["response_format"] = self.response_format.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IPAPIEndpoint":
        """Create from dictionary after JSON deserialization."""
        data["response_format"] = ResponseFormat(data["response_format"])
        return cls(**data)


class IPAPIManager:
    """Manager for custom IP API endpoints."""

    def __init__(self, config_file: str = "ip_apis.json"):
        """
        Initialize the API manager.

        Args:
            config_file: Path to the API configuration file
        """
        self.config_file = config_file
        self.endpoints: dict[str, IPAPIEndpoint] = {}
        self.load_apis()

    def add_api(self, endpoint: IPAPIEndpoint) -> bool:
        """
        Add a new API endpoint.

        Args:
            endpoint: The API endpoint to add

        Returns:
            bool: True if added successfully, False if ID already exists
        """
        if endpoint.id in self.endpoints:
            return False

        self.endpoints[endpoint.id] = endpoint
        self.save_apis()
        logger.info(f"Added custom IP API: {endpoint.name} ({endpoint.id})")
        return True

    def remove_api(self, api_id: str) -> bool:
        """
        Remove an API endpoint.

        Args:
            api_id: ID of the API to remove

        Returns:
            bool: True if removed successfully, False if not found
        """
        if api_id not in self.endpoints:
            return False

        endpoint = self.endpoints.pop(api_id)
        self.save_apis()
        logger.info(f"Removed custom IP API: {endpoint.name} ({api_id})")
        return True

    def get_api(self, api_id: str) -> IPAPIEndpoint | None:
        """Get an API endpoint by ID."""
        return self.endpoints.get(api_id)

    def list_apis(self, enabled_only: bool = False) -> list[IPAPIEndpoint]:
        """
        List all API endpoints.

        Args:
            enabled_only: If True, only return enabled APIs

        Returns:
            List of API endpoints sorted by priority and performance
        """
        apis = list(self.endpoints.values())

        if enabled_only:
            apis = [api for api in apis if api.enabled]

        # Sort by priority first, then by performance score
        apis.sort(key=lambda x: (x.priority, -x.get_performance_score()))
        return apis

    def enable_api(self, api_id: str) -> bool:
        """Enable an API endpoint."""
        if api_id not in self.endpoints:
            return False

        self.endpoints[api_id].enabled = True
        self.save_apis()
        return True

    def disable_api(self, api_id: str) -> bool:
        """Disable an API endpoint."""
        if api_id not in self.endpoints:
            return False

        self.endpoints[api_id].enabled = False
        self.save_apis()
        return True

    def update_api_priority(self, api_id: str, priority: int) -> bool:
        """Update API priority."""
        if api_id not in self.endpoints:
            return False

        self.endpoints[api_id].priority = priority
        self.save_apis()
        return True

    def get_api_by_name(self, name: str) -> IPAPIEndpoint | None:
        """
        Get an API endpoint by name.

        Args:
            name: Name of the API to find

        Returns:
            API endpoint if found, None otherwise
        """
        for endpoint in self.endpoints.values():
            if endpoint.name == name:
                return endpoint
        return None

    def get_all_apis(self) -> list[IPAPIEndpoint]:
        """
        Get all API endpoints (alias for list_apis for backward compatibility).

        Returns:
            List of all API endpoints
        """
        return self.list_apis()

    def get_api_urls(self, enabled_only: bool = True) -> list[str]:
        """
        Get list of API URLs for use by IPService.

        Args:
            enabled_only: If True, only return enabled APIs

        Returns:
            List of API URLs sorted by priority and performance
        """
        apis = self.list_apis(enabled_only=enabled_only)
        return [api.url for api in apis]

    def save_apis(self) -> bool:
        """Save API configuration to file."""
        try:
            data = {
                "endpoints": {
                    api_id: endpoint.to_dict()
                    for api_id, endpoint in self.endpoints.items()
                },
                "saved_at": time.time(),
            }

            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)

            return True
        except Exception as e:
            logger.error(f"Failed to save API configuration: {e}")
            return False

    def load_apis(self) -> bool:
        """Load API configuration from file."""
        try:
            try:
                with open(self.config_file) as f:
                    data = json.load(f)
            except FileNotFoundError:
                # Initialize with default APIs
                self._initialize_default_apis()
                return True

            endpoints_data = data.get("endpoints", {})
            self.endpoints = {}

            for api_id, endpoint_data in endpoints_data.items():
                try:
                    endpoint = IPAPIEndpoint.from_dict(endpoint_data)
                    self.endpoints[api_id] = endpoint
                except Exception as e:
                    logger.warning(f"Failed to load API endpoint {api_id}: {e}")

            logger.info(f"Loaded {len(self.endpoints)} custom IP APIs")
            return True

        except Exception as e:
            logger.error(f"Failed to load API configuration: {e}")
            # Initialize with defaults on error
            self._initialize_default_apis()
            return False

    def _initialize_default_apis(self) -> None:
        """Initialize with default API endpoints."""
        default_apis = [
            IPAPIEndpoint(
                id="ipify_json",
                name="IPify JSON",
                url="https://api.ipify.org?format=json",
                response_format=ResponseFormat.JSON,
                json_field="ip",
                priority=1,
            ),
            IPAPIEndpoint(
                id="ipify_text",
                name="IPify Text",
                url="https://api.ipify.org",
                response_format=ResponseFormat.PLAIN_TEXT,
                priority=2,
            ),
            IPAPIEndpoint(
                id="ifconfig_me",
                name="ifconfig.me",
                url="https://ifconfig.me/ip",
                response_format=ResponseFormat.PLAIN_TEXT,
                priority=3,
            ),
            IPAPIEndpoint(
                id="icanhazip",
                name="icanhazip.com",
                url="https://icanhazip.com/",
                response_format=ResponseFormat.PLAIN_TEXT,
                priority=4,
            ),
            IPAPIEndpoint(
                id="aws_checkip",
                name="AWS CheckIP",
                url="https://checkip.amazonaws.com/",
                response_format=ResponseFormat.PLAIN_TEXT,
                priority=5,
            ),
        ]

        for api in default_apis:
            self.endpoints[api.id] = api

        self.save_apis()
        logger.info("Initialized with default IP API endpoints")


# Global API manager instance
ip_api_manager = IPAPIManager()
