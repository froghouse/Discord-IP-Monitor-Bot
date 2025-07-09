"""
HTTP server mocks for integration testing.

This module provides utilities for creating real HTTP servers during testing
to simulate IP API endpoints and test the bot's HTTP client behavior.
"""

import asyncio
import logging
import random
import time
from typing import Any

from aiohttp import web

logger = logging.getLogger(__name__)


class IPAddressPool:
    """Manages a realistic pool of IP addresses for testing."""

    def __init__(self):
        # Common public IP ranges used by cloud providers and ISPs
        self.ip_ranges = {
            "aws": ["203.0.113.0/24", "198.51.100.0/24", "192.0.2.0/24"],  # Test ranges
            "gcp": ["35.235.240.0/24", "35.247.4.0/24"],  # GCP ranges
            "azure": ["52.182.143.0/24", "40.83.178.0/24"],  # Azure ranges
            "residential": ["73.43.0.0/16", "108.23.0.0/16", "24.147.0.0/16"],  # Residential
            "datacenter": ["104.131.0.0/16", "45.55.0.0/16"],  # DigitalOcean
        }

        # Generate pool of realistic IPs
        self.ip_pool = []
        self._generate_ip_pool()

        # Current IP tracking
        self.current_ip = None
        self.ip_change_probability = 0.01  # 1% chance per request

    def _generate_ip_pool(self):
        """Generate a pool of realistic IP addresses."""
        for provider, ranges in self.ip_ranges.items():
            for ip_range in ranges:
                base_ip = ip_range.split("/")[0]
                octets = base_ip.split(".")

                # Generate 10 IPs per range
                for i in range(10):
                    # Vary the last octet
                    new_octets = octets[:-1] + [str(int(octets[-1]) + i + 1)]
                    ip = ".".join(new_octets)
                    self.ip_pool.append({
                        "ip": ip,
                        "provider": provider,
                        "region": self._get_region_for_provider(provider),
                        "asn": self._get_asn_for_provider(provider)
                    })

    def _get_region_for_provider(self, provider: str) -> str:
        """Get realistic region for provider."""
        regions = {
            "aws": ["us-east-1", "us-west-2", "eu-west-1"],
            "gcp": ["us-central1", "us-west1", "europe-west1"],
            "azure": ["eastus", "westus2", "northeurope"],
            "residential": ["New York", "California", "Texas"],
            "datacenter": ["NYC1", "SFO1", "AMS3"]
        }
        return random.choice(regions.get(provider, ["unknown"]))

    def _get_asn_for_provider(self, provider: str) -> int:
        """Get realistic ASN for provider."""
        asns = {
            "aws": [16509, 14618],
            "gcp": [15169, 396982],
            "azure": [8075, 12076],
            "residential": [7922, 20115, 1239],
            "datacenter": [14061, 62567]
        }
        return random.choice(asns.get(provider, [0]))

    def get_current_ip(self) -> str:
        """Get current IP, potentially changing it."""
        if self.current_ip is None or random.random() < self.ip_change_probability:
            self.current_ip = random.choice(self.ip_pool)
        return self.current_ip["ip"]

    def get_random_ip(self) -> str:
        """Get a random IP from the pool."""
        return random.choice(self.ip_pool)["ip"]

    def get_ip_info(self, ip: str) -> dict:
        """Get information about an IP address."""
        for ip_info in self.ip_pool:
            if ip_info["ip"] == ip:
                return ip_info
        return {"ip": ip, "provider": "unknown", "region": "unknown", "asn": 0}


class ResponseTimingSimulator:
    """Simulates realistic response timing patterns."""

    def __init__(self):
        self.base_latency_ms = 50  # Base latency in milliseconds
        self.jitter_factor = 0.3  # 30% jitter
        self.degradation_factor = 1.0  # Performance degradation multiplier
        self.network_conditions = "good"  # good, fair, poor

    def get_response_delay(self, endpoint: str) -> float:
        """Get realistic response delay for an endpoint."""
        # Base delays for different endpoint types
        endpoint_delays = {
            "json": 80,
            "text": 60,
            "custom": 90,
            "nested": 120,
            "array": 150,
            "slow": 2000,
            "timeout": 30000,
            "error": 200,
            "rate_limit": 100,
            "malformed": 300,
            "empty": 40,
            "invalid_ip": 110,
            "multiple_ips": 140
        }

        # Get base delay
        base_delay = endpoint_delays.get(endpoint.lstrip("/"), self.base_latency_ms)

        # Apply network conditions
        network_multipliers = {
            "good": 1.0,
            "fair": 1.5,
            "poor": 3.0
        }
        base_delay *= network_multipliers.get(self.network_conditions, 1.0)

        # Apply jitter
        jitter = random.uniform(-self.jitter_factor, self.jitter_factor)
        delay_with_jitter = base_delay * (1 + jitter)

        # Apply degradation
        final_delay = delay_with_jitter * self.degradation_factor

        return max(0, final_delay / 1000.0)  # Convert to seconds

    def simulate_network_conditions(self, condition: str):
        """Simulate different network conditions."""
        if condition in ["good", "fair", "poor"]:
            self.network_conditions = condition

    def set_degradation_factor(self, factor: float):
        """Set performance degradation factor."""
        self.degradation_factor = max(0.1, factor)


class ErrorSimulator:
    """Simulates realistic error patterns."""

    def __init__(self):
        self.error_patterns = {
            "server_overload": {"rate": 0.1, "codes": [503, 502, 504]},
            "rate_limiting": {"rate": 0.05, "codes": [429]},
            "client_errors": {"rate": 0.02, "codes": [400, 401, 403, 404]},
            "network_errors": {"rate": 0.03, "codes": [500, 502, 503, 504]},
            "timeout_errors": {"rate": 0.01, "codes": [408, 504]}
        }

        self.current_error_state = "normal"
        self.error_burst_probability = 0.05  # 5% chance of error burst
        self.error_burst_duration = 0

    def should_error(self, base_error_rate: float = 0.0) -> bool:
        """Determine if request should error."""
        # Check for error burst
        if self.error_burst_duration > 0:
            self.error_burst_duration -= 1
            return random.random() < 0.8  # 80% error rate during burst

        # Check if we should start an error burst
        if random.random() < self.error_burst_probability:
            self.error_burst_duration = random.randint(3, 8)
            return True

        # Normal error checking
        total_error_rate = base_error_rate
        for pattern in self.error_patterns.values():
            total_error_rate += pattern["rate"]

        return random.random() < total_error_rate

    def get_error_response(self) -> tuple[int, str]:
        """Get a realistic error response."""
        if self.error_burst_duration > 0:
            # During error burst, favor server errors
            codes = [503, 502, 504]
            code = random.choice(codes)
            messages = {
                503: "Service Temporarily Unavailable",
                502: "Bad Gateway",
                504: "Gateway Timeout"
            }
            return code, messages.get(code, "Server Error")

        # Normal error selection
        pattern = random.choice(list(self.error_patterns.values()))
        code = random.choice(pattern["codes"])

        messages = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            408: "Request Timeout",
            429: "Too Many Requests",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }

        return code, messages.get(code, "Error")


class PerformanceDegradationSimulator:
    """Simulates gradual performance degradation."""

    def __init__(self):
        self.degradation_rate = 0.01  # 1% degradation per request
        self.current_degradation = 1.0
        self.max_degradation = 5.0
        self.recovery_rate = 0.005  # 0.5% recovery per request
        self.degradation_enabled = False

    def apply_degradation(self):
        """Apply performance degradation."""
        if self.degradation_enabled:
            # Increase degradation
            self.current_degradation = min(
                self.max_degradation,
                self.current_degradation + self.degradation_rate
            )
        else:
            # Gradual recovery
            self.current_degradation = max(
                1.0,
                self.current_degradation - self.recovery_rate
            )

    def get_degradation_factor(self) -> float:
        """Get current degradation factor."""
        return self.current_degradation

    def enable_degradation(self):
        """Enable performance degradation."""
        self.degradation_enabled = True

    def disable_degradation(self):
        """Disable performance degradation."""
        self.degradation_enabled = False


class NetworkSimulator:
    """Simulates network-level effects."""

    def __init__(self):
        self.dns_delay_ms = 20  # DNS resolution delay
        self.connection_timeout_probability = 0.01  # 1% chance
        self.packet_loss_probability = 0.005  # 0.5% chance
        self.bandwidth_limit_kbps = None  # No limit by default

    def get_dns_delay(self) -> float:
        """Get DNS resolution delay."""
        # Simulate DNS lookup time with jitter
        jitter = random.uniform(-0.5, 0.5)
        delay = self.dns_delay_ms * (1 + jitter)
        return max(0, delay / 1000.0)

    def should_connection_timeout(self) -> bool:
        """Check if connection should timeout."""
        return random.random() < self.connection_timeout_probability

    def should_packet_loss(self) -> bool:
        """Check if packet loss should occur."""
        return random.random() < self.packet_loss_probability

    def get_bandwidth_delay(self, content_size: int) -> float:
        """Get delay based on bandwidth limits."""
        if self.bandwidth_limit_kbps is None:
            return 0.0

        # Calculate transmission time
        transmission_time = (content_size * 8) / (self.bandwidth_limit_kbps * 1000)
        return transmission_time

    def set_bandwidth_limit(self, kbps: int):
        """Set bandwidth limit in kbps."""
        self.bandwidth_limit_kbps = kbps


class MockIPAPIServer:
    """Mock IP API server for testing HTTP interactions."""

    def __init__(self, port: int = 0):
        """Initialize the mock server.

        Args:
            port: Port to bind to (0 for random available port)
        """
        self.port = port
        self.app = None
        self.runner = None
        self.site = None
        self.base_url = None
        self.actual_port = None
        self._is_running = False
        self._shutdown_timeout = 5.0
        self._pending_requests = set()

        # Response configuration
        self.ip_pool = IPAddressPool()
        self.response_templates = {
            "/json": lambda ip: {"ip": ip},
            "/text": lambda ip: ip,
            "/custom": lambda ip: {"origin": ip},
            "/nested": lambda ip: {"data": {"client": {"ip": ip}}},
            "/array": lambda ip: [{"ip": ip}],
            "/slow": lambda ip: {"ip": ip},
            "/timeout": lambda ip: {"ip": ip},
            "/error": lambda ip: None,
            "/rate_limit": lambda ip: {"ip": ip},
            "/malformed": lambda ip: "not json",
            "/empty": lambda ip: "",
            "/invalid_ip": lambda ip: {"ip": "invalid.ip.address"},
            "/multiple_ips": lambda ip: {"ip": ip, "alt_ip": self.ip_pool.get_random_ip()},
        }

        # Server behavior configuration
        self.latency_ms = 0
        self.error_rate = 0.0
        self.rate_limit_requests = 0
        self.max_requests_per_minute = 60
        self.request_counts = {}

        # Enhanced realism features
        self.response_timing = ResponseTimingSimulator()
        self.error_simulator = ErrorSimulator()
        self.performance_degradation = PerformanceDegradationSimulator()
        self.network_simulator = NetworkSimulator()

        # Request tracking
        self.request_history = []
        self.last_request_time = None
        self.session_start_time = time.time()
        self.total_bytes_sent = 0

    async def start(self):
        """Start the mock server."""
        if self._is_running:
            return

        self.app = web.Application()
        self._setup_routes()

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "127.0.0.1", self.port)
        await self.site.start()

        # Get actual port if using port 0
        self.actual_port = self.site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.actual_port}"
        self._is_running = True

        logger.info(f"Mock IP API server started on {self.base_url}")

    async def stop(self):
        """Stop the mock server with proper cleanup."""
        if not self._is_running:
            return

        self._is_running = False

        try:
            # Cancel any pending requests
            if self._pending_requests:
                for request_task in self._pending_requests.copy():
                    if not request_task.done():
                        request_task.cancel()

                # Wait for request cancellation with timeout
                if self._pending_requests:
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*self._pending_requests, return_exceptions=True),
                            timeout=1.0
                        )
                    except TimeoutError:
                        logger.warning("Some pending requests did not cancel within timeout")

                self._pending_requests.clear()

            # Stop the site first
            if self.site:
                await self.site.stop()
                self.site = None

            # Then cleanup the runner
            if self.runner:
                await asyncio.wait_for(self.runner.cleanup(), timeout=self._shutdown_timeout)
                self.runner = None

            # Clear references
            self.app = None
            self.base_url = None

            logger.info("Mock IP API server stopped")

        except TimeoutError:
            logger.error(f"Server shutdown timed out after {self._shutdown_timeout}s")
            raise
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")
            raise

    def _setup_routes(self):
        """Setup server routes."""
        self.app.router.add_get("/json", self._json_handler)
        self.app.router.add_get("/text", self._text_handler)
        self.app.router.add_get("/custom", self._custom_handler)
        self.app.router.add_get("/nested", self._nested_handler)
        self.app.router.add_get("/array", self._array_handler)
        self.app.router.add_get("/slow", self._slow_handler)
        self.app.router.add_get("/timeout", self._timeout_handler)
        self.app.router.add_get("/error", self._error_handler)
        self.app.router.add_get("/rate_limit", self._rate_limit_handler)
        self.app.router.add_get("/malformed", self._malformed_handler)
        self.app.router.add_get("/empty", self._empty_handler)
        self.app.router.add_get("/invalid_ip", self._invalid_ip_handler)
        self.app.router.add_get("/multiple_ips", self._multiple_ips_handler)

        # Dynamic endpoints
        self.app.router.add_get("/dynamic/{endpoint}", self._dynamic_handler)

    def _track_request(self, request: web.Request):
        """Track request for analytics."""
        self.request_history.append(
            {
                "path": request.path,
                "method": request.method,
                "headers": dict(request.headers),
                "timestamp": time.time(),
                "remote": request.remote,
            }
        )
        self.last_request_time = time.time()

    async def _apply_latency(self, endpoint: str = "default"):
        """Apply configured latency with realistic timing patterns."""
        # Apply performance degradation
        self.performance_degradation.apply_degradation()

        # Calculate realistic delay
        realistic_delay = self.response_timing.get_response_delay(endpoint)

        # Apply degradation factor
        degradation_factor = self.performance_degradation.get_degradation_factor()
        total_delay = realistic_delay * degradation_factor

        # Add legacy latency support
        if self.latency_ms > 0:
            total_delay += self.latency_ms / 1000.0

        # Apply network simulation
        dns_delay = self.network_simulator.get_dns_delay()
        total_delay += dns_delay

        # Simulate connection timeout
        if self.network_simulator.should_connection_timeout():
            await asyncio.sleep(30.0)  # Long timeout
            raise web.HTTPRequestTimeout(text="Connection timeout")

        # Simulate packet loss (causes retransmission delay)
        if self.network_simulator.should_packet_loss():
            total_delay += random.uniform(0.1, 0.5)  # Retransmission delay

        await asyncio.sleep(total_delay)

    def _should_error(self):
        """Check if response should error based on error rate."""
        return self.error_simulator.should_error(self.error_rate)

    def _get_error_response(self):
        """Get a realistic error response."""
        status_code, message = self.error_simulator.get_error_response()
        return web.Response(status=status_code, text=message)

    def _generate_response_content(self, endpoint: str) -> Any:
        """Generate realistic response content for an endpoint."""
        current_ip = self.ip_pool.get_current_ip()

        if endpoint in self.response_templates:
            return self.response_templates[endpoint](current_ip)

        # Default response
        return {"ip": current_ip}

    def _track_response_size(self, content: str):
        """Track response size for bandwidth simulation."""
        self.total_bytes_sent += len(content.encode("utf-8"))

    async def _json_handler(self, request: web.Request):
        """Handle JSON IP response."""
        self._track_request(request)
        await self._apply_latency("json")

        if self._should_error():
            return self._get_error_response()

        response_content = self._generate_response_content("/json")
        response = web.json_response(response_content)

        # Track response size for bandwidth simulation
        self._track_response_size(str(response_content))

        return response

    async def _text_handler(self, request: web.Request):
        """Handle plain text IP response."""
        self._track_request(request)
        await self._apply_latency("text")

        if self._should_error():
            return self._get_error_response()

        response_content = self._generate_response_content("/text")
        response = web.Response(text=str(response_content))

        # Track response size for bandwidth simulation
        self._track_response_size(str(response_content))

        return response

    async def _custom_handler(self, request: web.Request):
        """Handle custom JSON field response."""
        self._track_request(request)
        await self._apply_latency("custom")

        if self._should_error():
            return self._get_error_response()

        response_content = self._generate_response_content("/custom")
        response = web.json_response(response_content)

        # Track response size for bandwidth simulation
        self._track_response_size(str(response_content))

        return response

    async def _nested_handler(self, request: web.Request):
        """Handle nested JSON response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/nested"])

    async def _array_handler(self, request: web.Request):
        """Handle array JSON response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/array"])

    async def _slow_handler(self, request: web.Request):
        """Handle slow response (2 second delay)."""
        self._track_request(request)
        await self._apply_latency("slow")
        await asyncio.sleep(2.0)  # Additional intentional delay

        if self._should_error():
            return self._get_error_response()

        response_content = self._generate_response_content("/slow")
        response = web.json_response(response_content)

        # Track response size for bandwidth simulation
        self._track_response_size(str(response_content))

        return response

    async def _timeout_handler(self, request: web.Request):
        """Handle timeout response (never responds)."""
        self._track_request(request)

        # Create a task to track this long-running request
        async def timeout_task():
            try:
                # Wait indefinitely to simulate timeout
                await asyncio.sleep(60)
                return web.json_response(self.responses["/timeout"])
            except asyncio.CancelledError:
                # Return a cancellation response
                return web.Response(status=499, text="Request cancelled")

        task = asyncio.create_task(timeout_task())
        self._pending_requests.add(task)

        try:
            result = await task
            return result
        finally:
            self._pending_requests.discard(task)

    async def _error_handler(self, request: web.Request):
        """Handle error response (500 status)."""
        self._track_request(request)
        await self._apply_latency()
        return web.Response(status=500, text="Internal Server Error")

    async def _rate_limit_handler(self, request: web.Request):
        """Handle rate limited response with realistic rate limiting behavior."""
        self._track_request(request)

        # Track requests per minute with sliding window
        now = time.time()
        current_minute = int(now // 60)

        # Clean old minute buckets (keep last 2 minutes for sliding window)
        self.request_counts = {
            minute: count
            for minute, count in self.request_counts.items()
            if minute >= current_minute - 1
        }

        # Count current minute
        self.request_counts[current_minute] = (
            self.request_counts.get(current_minute, 0) + 1
        )

        total_requests = sum(self.request_counts.values())

        # Implement progressive rate limiting
        if total_requests > self.max_requests_per_minute:
            # Calculate how much over the limit we are
            over_limit = total_requests - self.max_requests_per_minute

            # Progressive retry-after values
            if over_limit <= 5:
                retry_after = "60"
            elif over_limit <= 10:
                retry_after = "120"
            else:
                retry_after = "300"  # 5 minutes for severe violations

            headers = {
                "Retry-After": retry_after,
                "X-RateLimit-Limit": str(self.max_requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int((current_minute + 1) * 60))
            }

            return web.Response(
                status=429,
                text="Rate limit exceeded. Please try again later.",
                headers=headers
            )

        # Add rate limit headers to successful responses
        remaining = max(0, self.max_requests_per_minute - total_requests)
        headers = {
            "X-RateLimit-Limit": str(self.max_requests_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int((current_minute + 1) * 60))
        }

        await self._apply_latency("rate_limit")

        if self._should_error():
            return self._get_error_response()

        response_content = self._generate_response_content("/rate_limit")
        response = web.json_response(response_content, headers=headers)

        # Track response size for bandwidth simulation
        self._track_response_size(str(response_content))

        return response

    async def _malformed_handler(self, request: web.Request):
        """Handle malformed JSON response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.Response(text=self.responses["/malformed"])

    async def _empty_handler(self, request: web.Request):
        """Handle empty response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.Response(text=self.responses["/empty"])

    async def _invalid_ip_handler(self, request: web.Request):
        """Handle invalid IP response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/invalid_ip"])

    async def _multiple_ips_handler(self, request: web.Request):
        """Handle multiple IP fields response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/multiple_ips"])

    async def _dynamic_handler(self, request: web.Request):
        """Handle dynamic endpoint responses."""
        self._track_request(request)
        await self._apply_latency()

        endpoint = request.match_info["endpoint"]

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        # Generate dynamic response
        response_data = {
            "ip": "203.0.113.1",
            "endpoint": endpoint,
            "timestamp": time.time(),
            "random": random.randint(1, 1000),
        }

        return web.json_response(response_data)

    def configure_endpoint(self, path: str, response: Any, status: int = 200):
        """Configure a custom endpoint response.

        Args:
            path: Endpoint path
            response: Response data
            status: HTTP status code
        """
        self.responses[path] = response

        async def custom_handler(request: web.Request):
            self._track_request(request)
            await self._apply_latency()

            if self._should_error():
                return web.Response(status=500, text="Simulated error")

            if isinstance(response, dict):
                return web.json_response(response, status=status)
            return web.Response(text=str(response), status=status)

        self.app.router.add_get(path, custom_handler)

    def set_latency(self, ms: int):
        """Set response latency in milliseconds."""
        self.latency_ms = ms

    def set_error_rate(self, rate: float):
        """Set error rate (0.0 to 1.0)."""
        self.error_rate = max(0.0, min(1.0, rate))

    def set_rate_limit(self, requests_per_minute: int):
        """Set rate limiting."""
        self.max_requests_per_minute = requests_per_minute

    # Enhanced realism configuration methods
    def set_network_conditions(self, condition: str):
        """Set network conditions: 'good', 'fair', or 'poor'."""
        self.response_timing.simulate_network_conditions(condition)

    def enable_performance_degradation(self):
        """Enable gradual performance degradation."""
        self.performance_degradation.enable_degradation()

    def disable_performance_degradation(self):
        """Disable gradual performance degradation."""
        self.performance_degradation.disable_degradation()

    def set_bandwidth_limit(self, kbps: int):
        """Set bandwidth limit in kilobits per second."""
        self.network_simulator.set_bandwidth_limit(kbps)

    def set_ip_change_probability(self, probability: float):
        """Set probability of IP address changes (0.0 to 1.0)."""
        self.ip_pool.ip_change_probability = max(0.0, min(1.0, probability))

    def trigger_error_burst(self, duration: int = 5):
        """Trigger an error burst for specified duration."""
        self.error_simulator.error_burst_duration = duration

    def get_current_ip_info(self) -> dict:
        """Get information about the current IP address."""
        current_ip = self.ip_pool.get_current_ip()
        return self.ip_pool.get_ip_info(current_ip)

    def get_performance_metrics(self) -> dict:
        """Get detailed performance metrics."""
        return {
            "session_duration": time.time() - self.session_start_time,
            "total_requests": len(self.request_history),
            "total_bytes_sent": self.total_bytes_sent,
            "current_degradation_factor": self.performance_degradation.get_degradation_factor(),
            "error_burst_active": self.error_simulator.error_burst_duration > 0,
            "network_conditions": self.response_timing.network_conditions,
            "ip_pool_size": len(self.ip_pool.ip_pool),
            "current_ip": self.ip_pool.get_current_ip(),
            "bandwidth_limit_kbps": self.network_simulator.bandwidth_limit_kbps
        }

    def get_request_count(self) -> int:
        """Get total request count."""
        return len(self.request_history)

    def get_request_history(self) -> list[dict]:
        """Get complete request history."""
        return self.request_history.copy()

    def clear_request_history(self):
        """Clear request history."""
        self.request_history.clear()
        self.request_counts.clear()

    def get_stats(self) -> dict:
        """Get server statistics."""
        now = time.time()
        recent_requests = [
            req
            for req in self.request_history
            if now - req["timestamp"] < 300  # Last 5 minutes
        ]

        return {
            "total_requests": len(self.request_history),
            "recent_requests": len(recent_requests),
            "last_request_time": self.last_request_time,
            "base_url": self.base_url,
            "actual_port": self.actual_port,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "rate_limit": self.max_requests_per_minute,
        }


class MockAPICluster:
    """Cluster of mock API servers for testing failover and load balancing."""

    def __init__(self, server_count: int = 3):
        """Initialize the cluster.

        Args:
            server_count: Number of servers in the cluster
        """
        self.servers = []
        self.server_count = server_count
        self.current_primary = 0
        self._shutdown_timeout = 10.0

    async def start(self):
        """Start all servers in the cluster."""
        for i in range(self.server_count):
            server = MockIPAPIServer()
            await server.start()
            self.servers.append(server)

    async def stop(self):
        """Stop all servers in the cluster with proper cleanup."""
        if not self.servers:
            return

        try:
            # Stop all servers concurrently with timeout
            stop_tasks = [server.stop() for server in self.servers]
            await asyncio.wait_for(
                asyncio.gather(*stop_tasks, return_exceptions=True),
                timeout=self._shutdown_timeout
            )
        except TimeoutError:
            logger.error(f"Cluster shutdown timed out after {self._shutdown_timeout}s")
            raise
        finally:
            self.servers.clear()

    def get_server_urls(self) -> list[str]:
        """Get all server URLs."""
        return [f"{server.base_url}/json" for server in self.servers]

    def get_primary_url(self) -> str:
        """Get primary server URL."""
        return f"{self.servers[self.current_primary].base_url}/json"

    def fail_server(self, index: int):
        """Simulate server failure."""
        if 0 <= index < len(self.servers):
            self.servers[index].set_error_rate(1.0)

    def recover_server(self, index: int):
        """Recover failed server."""
        if 0 <= index < len(self.servers):
            self.servers[index].set_error_rate(0.0)

    def set_primary(self, index: int):
        """Set primary server."""
        if 0 <= index < len(self.servers):
            self.current_primary = index

    def get_cluster_stats(self) -> dict:
        """Get cluster statistics."""
        return {
            "server_count": len(self.servers),
            "primary_server": self.current_primary,
            "servers": [server.get_stats() for server in self.servers],
            "total_requests": sum(
                server.get_request_count() for server in self.servers
            ),
        }


class HTTPMockFixture:
    """Fixture for creating HTTP mock servers in tests."""

    def __init__(self):
        """Initialize the fixture."""
        self.servers = []
        self.clusters = []
        self._cleanup_timeout = 10.0

    async def create_server(self, **kwargs) -> MockIPAPIServer:
        """Create and start a mock server."""
        server = MockIPAPIServer(**kwargs)
        await server.start()
        self.servers.append(server)
        return server

    async def create_cluster(self, server_count: int = 3) -> MockAPICluster:
        """Create and start a mock cluster."""
        cluster = MockAPICluster(server_count)
        await cluster.start()
        self.clusters.append(cluster)
        return cluster

    async def cleanup(self):
        """Cleanup all servers and clusters with proper error handling."""
        cleanup_tasks = []

        # Add server cleanup tasks
        for server in self.servers:
            cleanup_tasks.append(server.stop())

        # Add cluster cleanup tasks
        for cluster in self.clusters:
            cleanup_tasks.append(cluster.stop())

        if cleanup_tasks:
            try:
                # Execute all cleanup tasks concurrently with timeout
                results = await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=self._cleanup_timeout
                )

                # Log any cleanup errors
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Cleanup task {i} failed: {result}")

            except TimeoutError:
                logger.error(f"Fixture cleanup timed out after {self._cleanup_timeout}s")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during fixture cleanup: {e}")
                raise
            finally:
                # Clear references regardless of cleanup success
                self.servers.clear()
                self.clusters.clear()
        else:
            # No cleanup needed
            self.servers.clear()
            self.clusters.clear()


# Context manager for easy server management
class MockServerContext:
    """Context manager for mock server lifecycle."""

    def __init__(self, **kwargs):
        """Initialize context manager."""
        self.server = None
        self.server_kwargs = kwargs
        self._cleanup_timeout = 5.0

    async def __aenter__(self) -> MockIPAPIServer:
        """Enter context and start server."""
        self.server = MockIPAPIServer(**self.server_kwargs)
        await self.server.start()
        return self.server

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and stop server with proper cleanup."""
        if self.server:
            try:
                await asyncio.wait_for(
                    self.server.stop(),
                    timeout=self._cleanup_timeout
                )
            except TimeoutError:
                logger.error(f"Server context cleanup timed out after {self._cleanup_timeout}s")
                # Don't re-raise to avoid masking original exceptions
            except Exception as e:
                logger.error(f"Error during server context cleanup: {e}")
                # Don't re-raise to avoid masking original exceptions
            finally:
                self.server = None


class MockServerCluster:
    """Enhanced context manager for server cluster lifecycle."""

    def __init__(self, server_count: int = 3, **server_kwargs):
        """Initialize cluster context manager.
        
        Args:
            server_count: Number of servers in the cluster
            **server_kwargs: Keyword arguments to pass to each server
        """
        self.server_count = server_count
        self.server_kwargs = server_kwargs
        self.cluster = None
        self._cleanup_timeout = 10.0

    async def __aenter__(self) -> MockAPICluster:
        """Enter context and start cluster."""
        self.cluster = MockAPICluster(self.server_count)

        # Override server creation to use custom kwargs
        if self.server_kwargs:
            original_servers = []
            for i in range(self.server_count):
                server = MockIPAPIServer(**self.server_kwargs)
                await server.start()
                original_servers.append(server)
            self.cluster.servers = original_servers
        else:
            await self.cluster.start()

        return self.cluster

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and stop cluster with proper cleanup."""
        if self.cluster:
            try:
                await asyncio.wait_for(
                    self.cluster.stop(),
                    timeout=self._cleanup_timeout
                )
            except TimeoutError:
                logger.error(f"Cluster context cleanup timed out after {self._cleanup_timeout}s")
                # Don't re-raise to avoid masking original exceptions
            except Exception as e:
                logger.error(f"Error during cluster context cleanup: {e}")
                # Don't re-raise to avoid masking original exceptions
            finally:
                self.cluster = None
