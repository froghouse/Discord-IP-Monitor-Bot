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

        # Response configuration
        self.responses = {
            "/json": {"ip": "203.0.113.1"},
            "/text": "203.0.113.1",
            "/custom": {"origin": "203.0.113.1"},
            "/nested": {"data": {"client": {"ip": "203.0.113.1"}}},
            "/array": [{"ip": "203.0.113.1"}],
            "/slow": {"ip": "203.0.113.1"},
            "/timeout": {"ip": "203.0.113.1"},
            "/error": None,
            "/rate_limit": {"ip": "203.0.113.1"},
            "/malformed": "not json",
            "/empty": "",
            "/invalid_ip": {"ip": "invalid.ip.address"},
            "/multiple_ips": {"ip": "203.0.113.1", "alt_ip": "203.0.113.2"},
        }

        # Server behavior configuration
        self.latency_ms = 0
        self.error_rate = 0.0
        self.rate_limit_requests = 0
        self.max_requests_per_minute = 60
        self.request_counts = {}

        # Request tracking
        self.request_history = []
        self.last_request_time = None

    async def start(self):
        """Start the mock server."""
        self.app = web.Application()
        self._setup_routes()

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, "127.0.0.1", self.port)
        await self.site.start()

        # Get actual port if using port 0
        self.actual_port = self.site._server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.actual_port}"

        logger.info(f"Mock IP API server started on {self.base_url}")

    async def stop(self):
        """Stop the mock server."""
        if self.runner:
            await self.runner.cleanup()
        logger.info("Mock IP API server stopped")

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

    async def _apply_latency(self):
        """Apply configured latency."""
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

    def _should_error(self):
        """Check if response should error based on error rate."""
        return random.random() < self.error_rate

    async def _json_handler(self, request: web.Request):
        """Handle JSON IP response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/json"])

    async def _text_handler(self, request: web.Request):
        """Handle plain text IP response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.Response(text=self.responses["/text"])

    async def _custom_handler(self, request: web.Request):
        """Handle custom JSON field response."""
        self._track_request(request)
        await self._apply_latency()

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/custom"])

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
        await asyncio.sleep(2.0)

        if self._should_error():
            return web.Response(status=500, text="Simulated error")

        return web.json_response(self.responses["/slow"])

    async def _timeout_handler(self, request: web.Request):
        """Handle timeout response (never responds)."""
        self._track_request(request)
        # Wait indefinitely to simulate timeout
        await asyncio.sleep(60)
        return web.json_response(self.responses["/timeout"])

    async def _error_handler(self, request: web.Request):
        """Handle error response (500 status)."""
        self._track_request(request)
        await self._apply_latency()
        return web.Response(status=500, text="Internal Server Error")

    async def _rate_limit_handler(self, request: web.Request):
        """Handle rate limited response."""
        self._track_request(request)

        # Track requests per minute
        now = time.time()
        minute_ago = now - 60

        # Clean old requests
        self.request_counts = {
            t: count for t, count in self.request_counts.items() if t > minute_ago
        }

        # Count current minute
        current_minute = int(now // 60)
        self.request_counts[current_minute] = (
            self.request_counts.get(current_minute, 0) + 1
        )

        total_requests = sum(self.request_counts.values())

        if total_requests > self.max_requests_per_minute:
            return web.Response(
                status=429, text="Rate limit exceeded", headers={"Retry-After": "60"}
            )

        await self._apply_latency()
        return web.json_response(self.responses["/rate_limit"])

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

    async def start(self):
        """Start all servers in the cluster."""
        for i in range(self.server_count):
            server = MockIPAPIServer()
            await server.start()
            self.servers.append(server)

    async def stop(self):
        """Stop all servers in the cluster."""
        for server in self.servers:
            await server.stop()

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
        """Cleanup all servers and clusters."""
        for server in self.servers:
            await server.stop()
        for cluster in self.clusters:
            await cluster.stop()
        self.servers.clear()
        self.clusters.clear()


# Context manager for easy server management
class MockServerContext:
    """Context manager for mock server lifecycle."""

    def __init__(self, **kwargs):
        """Initialize context manager."""
        self.server = None
        self.server_kwargs = kwargs

    async def __aenter__(self) -> MockIPAPIServer:
        """Enter context and start server."""
        self.server = MockIPAPIServer(**self.server_kwargs)
        await self.server.start()
        return self.server

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context and stop server."""
        if self.server:
            await self.server.stop()
