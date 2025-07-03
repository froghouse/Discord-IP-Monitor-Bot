"""
IP address operations for the IP Monitor Bot.
"""

import asyncio
import ipaddress
import json
import logging
from typing import List, Optional

import httpx

from ip_monitor.utils.circuit_breaker import IPServiceCircuitBreaker
from ip_monitor.utils.service_health import service_health

logger = logging.getLogger(__name__)


class IPService:
    """
    Service for retrieving and validating IP addresses.
    """

    # Default list of IP APIs to try
    DEFAULT_IP_APIS = [
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/ip",
        "https://api.ipify.org",
        "https://icanhazip.com/",
        "https://checkip.amazonaws.com/",
    ]

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: int = 5,
        use_concurrent_checks: bool = True,
        apis: Optional[List[str]] = None,
        circuit_breaker_enabled: bool = True,
        circuit_breaker_failure_threshold: int = 3,
        circuit_breaker_recovery_timeout: float = 120.0,
    ) -> None:
        """
        Initialize the IP service.

        Args:
            max_retries: Maximum number of retries for failed API calls
            retry_delay: Delay between retries in seconds
            use_concurrent_checks: Whether to check APIs concurrently
            apis: List of IP API endpoints to use (optional)
            circuit_breaker_enabled: Whether to use circuit breaker pattern
            circuit_breaker_failure_threshold: Number of failures before opening circuit
            circuit_breaker_recovery_timeout: Time to wait before testing recovery
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_concurrent_checks = use_concurrent_checks
        self.apis = apis or self.DEFAULT_IP_APIS
        self.client = None  # Will be initialized when needed

        # Circuit breaker setup
        self.circuit_breaker_enabled = circuit_breaker_enabled
        if self.circuit_breaker_enabled:
            self.circuit_breaker = IPServiceCircuitBreaker(
                failure_threshold=circuit_breaker_failure_threshold,
                recovery_timeout=circuit_breaker_recovery_timeout,
            )
        else:
            self.circuit_breaker = None

        # Track last successful IP for fallback
        self._last_known_ip: Optional[str] = None

    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """
        Validate if the given string is a valid IPv4 or IPv6 address.

        Args:
            ip: The IP address to validate

        Returns:
            bool: True if the IP is valid, False otherwise
        """
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    async def fetch_ip_from_api(
        self, client: httpx.AsyncClient, api: str
    ) -> Optional[str]:
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
                    service_health.record_failure(
                        "ip_service", f"JSON parse error from {api}: {e}", "fetch_ip"
                    )
                    return None
            else:
                ip = response.text.strip()

            if self.is_valid_ip(ip):
                logger.debug(f"Successfully got IP {ip} from {api}")
                service_health.record_success("ip_service", "fetch_ip")
                return ip
            else:
                logger.warning(f"Invalid IP address returned by {api}: {ip}")
                service_health.record_failure(
                    "ip_service", f"Invalid IP from {api}: {ip}", "fetch_ip"
                )
                return None

        except httpx.HTTPError as e:
            logger.warning(f"Failed to get IP from {api}: {e}")
            service_health.record_failure(
                "ip_service", f"HTTP error from {api}: {e}", "fetch_ip"
            )
            return None
        except Exception as e:
            logger.warning(f"Unexpected error while fetching from {api}: {e}")
            service_health.record_failure(
                "ip_service", f"Unexpected error from {api}: {e}", "fetch_ip"
            )
            return None

    async def _get_ip_without_circuit_breaker(self) -> Optional[str]:
        """
        Get IP address without circuit breaker (original implementation).

        Returns:
            IP address string or None if unsuccessful
        """
        # Initialize the client if it doesn't exist
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=10.0)

        try:
            for attempt in range(self.max_retries):
                # If we should check APIs concurrently
                if self.use_concurrent_checks:
                    # Create tasks for all APIs
                    tasks = [
                        self.fetch_ip_from_api(self.client, api) for api in self.apis
                    ]
                    # Wait for first successful result
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results
                    for result in results:
                        if isinstance(result, str) and self.is_valid_ip(result):
                            return result

                    # If we get here, all concurrent checks failed
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"All IP APIs failed concurrently, retrying in {self.retry_delay} seconds..."
                        )
                        await asyncio.sleep(self.retry_delay)
                    continue

                # Sequential API checking (fallback approach)
                for api in self.apis:
                    ip = await self.fetch_ip_from_api(self.client, api)
                    if ip:
                        return ip

                # If we get here, all APIs failed in this sequential attempt
                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"All IP APIs failed sequentially, retrying in {self.retry_delay} seconds..."
                    )
                    await asyncio.sleep(self.retry_delay)

            logger.error("All IP APIs failed after maximum retry attempts")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in IP fetch: {e}")
            return None

    async def get_public_ip(self) -> Optional[str]:
        """
        Get the current public IP address with circuit breaker protection.

        Returns:
            IP address string or None if unsuccessful
        """
        if not self.circuit_breaker_enabled or self.circuit_breaker is None:
            # Use original implementation without circuit breaker
            result = await self._get_ip_without_circuit_breaker()
            if result:
                self._last_known_ip = result
            return result

        # Use circuit breaker
        try:
            result = await self.circuit_breaker.get_ip_with_fallback_cache(
                self._get_ip_without_circuit_breaker, self._last_known_ip
            )

            # Update last known IP if we got a fresh result
            if result and result != self._last_known_ip:
                logger.debug(
                    f"Updating last known IP from {self._last_known_ip} to {result}"
                )
                self._last_known_ip = result

            return result

        except Exception as e:
            logger.error(f"Unexpected error in get_public_ip with circuit breaker: {e}")
            # Fallback to cached IP if available
            if self._last_known_ip:
                logger.info(
                    f"Using last known IP as final fallback: {self._last_known_ip}"
                )
                return self._last_known_ip
            return None

    def get_circuit_breaker_info(self) -> dict:
        """
        Get information about the circuit breaker state.

        Returns:
            Dictionary with circuit breaker information
        """
        if not self.circuit_breaker_enabled or self.circuit_breaker is None:
            return {"enabled": False, "state": "disabled"}

        info = self.circuit_breaker.get_state()
        info["enabled"] = True
        info["last_known_ip"] = self._last_known_ip
        return info

    def reset_circuit_breaker(self) -> bool:
        """
        Reset the circuit breaker to initial state.

        Returns:
            True if reset was successful, False if circuit breaker is disabled
        """
        if not self.circuit_breaker_enabled or self.circuit_breaker is None:
            return False

        self.circuit_breaker.reset()
        return True

    def set_last_known_ip(self, ip: str) -> bool:
        """
        Manually set the last known IP (useful for initialization).

        Args:
            ip: IP address to set as last known

        Returns:
            True if IP was valid and set, False otherwise
        """
        if self.is_valid_ip(ip):
            self._last_known_ip = ip
            logger.info(f"Last known IP set to: {ip}")
            return True
        return False

    async def close(self) -> None:
        """
        Close any pending HTTP connections.
        This should be called when shutting down the bot.
        """
        logger.info("Closing IP service connections")
        if self.client is not None:
            await self.client.aclose()
            self.client = None
