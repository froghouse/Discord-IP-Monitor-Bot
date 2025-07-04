"""
IP address operations for the IP Monitor Bot.
"""

import asyncio
import ipaddress
import json
import logging
import time
from typing import List, Optional

import httpx

from ip_monitor.ip_api_config import ResponseFormat, ip_api_manager
from ip_monitor.utils.cache import CacheType, get_cache
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
        use_custom_apis: bool = True,
        connection_pool_size: int = 10,
        connection_pool_max_keepalive: int = 5,
        connection_timeout: float = 10.0,
        read_timeout: float = 30.0,
        cache_enabled: bool = True,
        cache_ttl: int = 300,
        cache_stale_threshold: float = 0.8,
    ) -> None:
        """
        Initialize the IP service.

        Args:
            max_retries: Maximum number of retries for failed API calls
            retry_delay: Delay between retries in seconds
            use_concurrent_checks: Whether to check APIs concurrently
            apis: List of IP API endpoints to use (optional, legacy)
            circuit_breaker_enabled: Whether to use circuit breaker pattern
            circuit_breaker_failure_threshold: Number of failures before opening circuit
            circuit_breaker_recovery_timeout: Time to wait before testing recovery
            use_custom_apis: Whether to use custom configured APIs
            connection_pool_size: Maximum number of connections in the pool
            connection_pool_max_keepalive: Maximum number of keep-alive connections
            connection_timeout: Timeout for establishing connections
            read_timeout: Timeout for reading responses
            cache_enabled: Whether to enable intelligent caching
            cache_ttl: Default cache TTL in seconds
            cache_stale_threshold: Threshold for considering cache entries stale (0.0-1.0)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_concurrent_checks = use_concurrent_checks
        self.use_custom_apis = use_custom_apis
        self.legacy_apis = apis or self.DEFAULT_IP_APIS

        # Connection pooling configuration
        self.connection_pool_size = connection_pool_size
        self.connection_pool_max_keepalive = connection_pool_max_keepalive
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout

        # HTTP client with connection pooling
        self.client = None  # Will be initialized when needed
        self._client_initialized = False

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

        # Caching configuration
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.cache_stale_threshold = cache_stale_threshold
        self.cache = get_cache() if cache_enabled else None

        # Configure cache TTL for different types
        if self.cache:
            self.cache.set_ttl(CacheType.IP_RESULT, cache_ttl)
            self.cache.set_ttl(
                CacheType.API_RESPONSE, cache_ttl // 2
            )  # Shorter TTL for API responses
            self.cache.set_ttl(CacheType.DNS_LOOKUP, 3600)  # 1 hour for DNS
            self.cache.set_ttl(
                CacheType.PERFORMANCE_DATA, 600
            )  # 10 minutes for performance data

        logger.debug(
            f"IP service initialized with connection pool size: {self.connection_pool_size}, "
            f"max keepalive: {self.connection_pool_max_keepalive}, "
            f"connection timeout: {self.connection_timeout}s, "
            f"read timeout: {self.read_timeout}s, "
            f"cache enabled: {self.cache_enabled}, cache TTL: {self.cache_ttl}s"
        )

    def get_apis_to_use(self) -> List[str]:
        """
        Get list of API URLs to use for IP detection.

        Returns:
            List of API URLs
        """
        if self.use_custom_apis:
            # Use custom configured APIs
            custom_urls = ip_api_manager.get_api_urls(enabled_only=True)
            if custom_urls:
                return custom_urls
            else:
                logger.warning(
                    "No custom APIs configured, falling back to default APIs"
                )

        # Fall back to legacy/default APIs
        return self.legacy_apis

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

    async def fetch_ip_from_custom_api(self, api_config) -> Optional[str]:
        """
        Fetch IP from a custom API endpoint with specific configuration.

        Args:
            api_config: IPAPIEndpoint configuration object

        Returns:
            IP address string or None if unsuccessful
        """
        start_time = time.time()

        try:
            client = await self.get_client()

            # Merge custom headers with defaults
            headers = api_config.headers or {}

            # Create timeout for this specific request
            request_timeout = httpx.Timeout(
                connect=self.connection_timeout,
                read=api_config.timeout,
                write=30.0,
                pool=60.0,
            )

            response = await client.get(
                api_config.url, headers=headers, timeout=request_timeout
            )
            response.raise_for_status()

            response_time = time.time() - start_time

            # Parse response based on format
            if api_config.response_format == ResponseFormat.JSON or (
                api_config.response_format == ResponseFormat.AUTO
                and response.headers.get("content-type", "").startswith(
                    "application/json"
                )
            ):
                try:
                    data = response.json()
                    if api_config.json_field:
                        ip = data.get(api_config.json_field)
                    else:
                        # Try common field names
                        ip = data.get("ip") or data.get("origin") or data.get("address")
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON response from {api_config.url}")
                    return None
            else:
                # Plain text response
                ip = response.text.strip()

            if not ip:
                logger.warning(f"No IP found in response from {api_config.url}")
                api_config.record_failure()
                return None

            if not self.is_valid_ip(ip):
                logger.warning(f"Invalid IP '{ip}' from {api_config.url}")
                api_config.record_failure()
                return None

            # Record success
            api_config.record_success(response_time)
            logger.debug(
                f"Successfully got IP '{ip}' from {api_config.name} in {response_time:.2f}s"
            )

            return ip

        except Exception as e:
            response_time = time.time() - start_time
            api_config.record_failure()
            logger.debug(f"Error fetching IP from {api_config.name}: {e}")
            return None

    async def fetch_ip_from_api(self, api: str) -> Optional[str]:
        """
        Fetch IP from a single API endpoint.

        Args:
            api: URL of the API to query

        Returns:
            IP address string or None if unsuccessful
        """
        try:
            logger.debug(f"Trying to get IP from {api}")
            client = await self.get_client()
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
            await self._initialize_client()

        try:
            for attempt in range(self.max_retries):
                # Get APIs to use (custom or legacy)
                if self.use_custom_apis:
                    api_configs = ip_api_manager.list_apis(enabled_only=True)
                    if not api_configs:
                        logger.warning("No custom APIs available, using legacy APIs")
                        api_configs = None
                else:
                    api_configs = None

                # If we should check APIs concurrently
                if self.use_concurrent_checks:
                    if api_configs:
                        # Use custom API configurations
                        tasks = [
                            self.fetch_ip_from_custom_api(api_config)
                            for api_config in api_configs
                        ]
                    else:
                        # Use legacy API URLs
                        tasks = [
                            self.fetch_ip_from_api(api)
                            for api in self.get_apis_to_use()
                        ]

                    # Wait for first successful result
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Process results
                    for result in results:
                        if isinstance(result, str) and self.is_valid_ip(result):
                            # Save API configuration changes if using custom APIs
                            if api_configs:
                                ip_api_manager.save_apis()

                            # Cache the global IP result
                            if self.cache_enabled and self.cache:
                                self.cache.set(
                                    "global",
                                    "current_ip",
                                    result,
                                    CacheType.IP_RESULT,
                                    ttl=self.cache_ttl,
                                    metadata={
                                        "source": "concurrent",
                                        "timestamp": time.time(),
                                    },
                                )

                            return result

                    # If we get here, all concurrent checks failed
                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"All IP APIs failed concurrently, retrying in {self.retry_delay} seconds..."
                        )
                        await asyncio.sleep(self.retry_delay)
                    continue

                # Sequential API checking (fallback approach)
                if api_configs:
                    # Use custom API configurations
                    for api_config in api_configs:
                        ip = await self.fetch_ip_from_custom_api(api_config)
                        if ip:
                            # Save API configuration changes
                            ip_api_manager.save_apis()
                            return ip
                else:
                    # Use legacy API URLs
                    for api in self.get_apis_to_use():
                        ip = await self.fetch_ip_from_api(api)
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

    async def _initialize_client(self) -> None:
        """
        Initialize the HTTP client with connection pooling configuration.
        """
        if self._client_initialized:
            return

        logger.info("Initializing HTTP client with connection pooling")

        # Configure connection limits and timeouts
        limits = httpx.Limits(
            max_connections=self.connection_pool_size,
            max_keepalive_connections=self.connection_pool_max_keepalive,
            keepalive_expiry=300.0,  # 5 minutes keepalive
        )

        timeout = httpx.Timeout(
            connect=self.connection_timeout,
            read=self.read_timeout,
            write=30.0,
            pool=60.0,
        )

        # Create client with connection pooling
        # Try to enable HTTP/2 if available, fall back to HTTP/1.1 if not
        try:
            self.client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                headers={
                    "User-Agent": "IP-Monitor-Bot/1.0",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                },
                http2=True,  # Enable HTTP/2 support for better performance
                follow_redirects=True,
            )
            logger.debug("HTTP/2 support enabled")
        except ImportError:
            # Fall back to HTTP/1.1 if h2 package is not installed
            logger.info("HTTP/2 not available, using HTTP/1.1")
            self.client = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                headers={
                    "User-Agent": "IP-Monitor-Bot/1.0",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate",
                    "Connection": "keep-alive",
                },
                follow_redirects=True,
            )

        self._client_initialized = True
        logger.info(
            f"HTTP client initialized with pool size: {self.connection_pool_size}, "
            f"keepalive connections: {self.connection_pool_max_keepalive}"
        )

    async def get_client(self) -> httpx.AsyncClient:
        """
        Get the HTTP client, initializing it if necessary.

        Returns:
            Configured httpx.AsyncClient instance
        """
        if self.client is None or not self._client_initialized:
            await self._initialize_client()
        return self.client

    async def close(self) -> None:
        """
        Close any pending HTTP connections.
        This should be called when shutting down the bot.
        """
        logger.info("Closing IP service connections")
        if self.client is not None:
            try:
                # Get connection pool statistics before closing
                if hasattr(self.client, "_pool"):
                    pool = self.client._pool
                    logger.info(
                        f"Closing connection pool - Active connections: {len(pool._pool)}, "
                        f"Keepalive connections: {len(pool._keepalive_connections)}"
                    )

                await self.client.aclose()
                logger.info("HTTP client closed successfully")
            except Exception as e:
                logger.warning(f"Error closing HTTP client: {e}")
            finally:
                self.client = None
                self._client_initialized = False

        # Save cache to disk
        if self.cache_enabled and self.cache:
            try:
                self.cache.save()
                logger.debug("Cache saved during IP service shutdown")
            except Exception as e:
                logger.warning(f"Failed to save cache during shutdown: {e}")

    def get_cache_info(self) -> dict:
        """
        Get information about the cache state and statistics.

        Returns:
            Dictionary with cache information
        """
        if not self.cache_enabled or self.cache is None:
            return {"enabled": False, "stats": {}}

        stats = self.cache.get_stats()
        stale_entries = self.cache.get_stale_entries("ip_check")

        return {
            "enabled": True,
            "stats": stats,
            "stale_entries_count": len(stale_entries),
            "cache_ttl": self.cache_ttl,
            "stale_threshold": self.cache_stale_threshold,
        }

    def invalidate_cache(self, namespace: Optional[str] = None) -> int:
        """
        Invalidate cache entries.

        Args:
            namespace: Optional namespace to invalidate (None for all)

        Returns:
            Number of entries invalidated
        """
        if not self.cache_enabled or self.cache is None:
            return 0

        if namespace:
            return self.cache.invalidate(namespace)
        else:
            return self.cache.clear()

    async def refresh_stale_cache_entries(self) -> int:
        """
        Refresh stale cache entries proactively.

        Returns:
            Number of entries refreshed
        """
        if not self.cache_enabled or self.cache is None:
            return 0

        stale_entries = self.cache.get_stale_entries("ip_check")
        refreshed = 0

        for entry in stale_entries:
            try:
                # Parse the cache key to determine API type
                if entry.metadata and "api_name" in entry.metadata:
                    # Custom API entry
                    api_config = ip_api_manager.get_api_by_name(
                        entry.metadata["api_name"]
                    )
                    if api_config:
                        fresh_ip = await self.fetch_ip_from_custom_api(api_config)
                        if fresh_ip:
                            refreshed += 1
                elif entry.metadata and "api_url" in entry.metadata:
                    # Legacy API entry
                    api_url = entry.metadata["api_url"]
                    fresh_ip = await self.fetch_ip_from_api(api_url)
                    if fresh_ip:
                        refreshed += 1
            except Exception as e:
                logger.debug(f"Failed to refresh cache entry: {e}")

        return refreshed
