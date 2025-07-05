"""
Service health monitoring and graceful degradation for the IP Monitor Bot.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class DegradationLevel(Enum):
    """System degradation levels."""

    NORMAL = "normal"  # All services working
    MINOR = "minor"  # Some non-critical issues
    MODERATE = "moderate"  # Reduced functionality
    SEVERE = "severe"  # Core functionality only
    CRITICAL = "critical"  # Minimal operation


@dataclass
class ServiceHealth:
    """Health information for a service."""

    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_success: float = 0.0
    last_failure: float = 0.0
    failure_count: int = 0
    success_count: int = 0
    error_message: str | None = None
    degraded_since: float | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)


@dataclass
class DegradationMode:
    """Configuration for a degradation mode."""

    level: DegradationLevel
    description: str
    ip_check_interval_multiplier: float = 1.0
    max_retries_multiplier: float = 1.0
    enable_notifications: bool = True
    enable_history_logging: bool = True
    enable_status_commands: bool = True
    fallback_behaviors: list[str] = field(default_factory=list)


class ServiceHealthMonitor:
    """
    Monitors service health and manages graceful degradation.
    """

    def __init__(self):
        """Initialize the service health monitor."""
        self.services: dict[str, ServiceHealth] = {}
        self.current_degradation = DegradationLevel.NORMAL
        self.degradation_history: list[dict[str, Any]] = []

        # Define degradation modes
        self.degradation_modes = {
            DegradationLevel.NORMAL: DegradationMode(
                level=DegradationLevel.NORMAL,
                description="All systems operational",
            ),
            DegradationLevel.MINOR: DegradationMode(
                level=DegradationLevel.MINOR,
                description="Minor issues, full functionality maintained",
                ip_check_interval_multiplier=1.2,
            ),
            DegradationLevel.MODERATE: DegradationMode(
                level=DegradationLevel.MODERATE,
                description="Some services degraded, reduced functionality",
                ip_check_interval_multiplier=1.5,
                max_retries_multiplier=1.5,
                fallback_behaviors=["use_cached_ip", "extended_timeouts"],
            ),
            DegradationLevel.SEVERE: DegradationMode(
                level=DegradationLevel.SEVERE,
                description="Multiple service failures, core functionality only",
                ip_check_interval_multiplier=2.0,
                max_retries_multiplier=2.0,
                enable_notifications=False,
                fallback_behaviors=[
                    "use_cached_ip",
                    "read_only_mode",
                    "silent_monitoring",
                ],
            ),
            DegradationLevel.CRITICAL: DegradationMode(
                level=DegradationLevel.CRITICAL,
                description="Critical system failure, minimal operation",
                ip_check_interval_multiplier=5.0,
                max_retries_multiplier=0.5,
                enable_notifications=False,
                enable_history_logging=False,
                fallback_behaviors=[
                    "use_cached_ip",
                    "read_only_mode",
                    "silent_monitoring",
                    "basic_logging_only",
                ],
            ),
        }

        # Register core services
        self._register_core_services()

    def _register_core_services(self) -> None:
        """Register core services for monitoring."""
        self.register_service(
            "ip_service",
            {
                "fetch_ip": True,
                "circuit_breaker": True,
                "fallback_cache": True,
            },
        )

        self.register_service(
            "discord_api",
            {
                "send_messages": True,
                "receive_commands": True,
                "rate_limiting": True,
            },
        )

        self.register_service(
            "storage",
            {
                "read_files": True,
                "write_files": True,
                "atomic_operations": True,
            },
        )

        self.register_service(
            "rate_limiter",
            {
                "request_limiting": True,
                "backoff": True,
            },
        )

    def register_service(self, name: str, capabilities: dict[str, bool]) -> None:
        """
        Register a service for health monitoring.

        Args:
            name: Service name
            capabilities: Dictionary of service capabilities
        """
        self.services[name] = ServiceHealth(name=name, capabilities=capabilities.copy())
        logger.debug(
            f"Registered service: {name} with capabilities: {list(capabilities.keys())}"
        )

    def record_success(self, service_name: str, operation: str | None = None) -> None:
        """
        Record a successful operation for a service.

        Args:
            service_name: Name of the service
            operation: Specific operation that succeeded (optional)
        """
        if service_name not in self.services:
            logger.warning(f"Unknown service: {service_name}")
            return

        service = self.services[service_name]
        current_time = time.time()

        service.last_success = current_time
        service.success_count += 1
        service.error_message = None

        # Update service status
        if service.status == ServiceStatus.FAILED:
            service.status = ServiceStatus.DEGRADED
            logger.info(f"Service {service_name} recovering from failure")
        elif service.status == ServiceStatus.DEGRADED and service.success_count >= 3:
            service.status = ServiceStatus.HEALTHY
            service.degraded_since = None
            logger.info(f"Service {service_name} fully recovered")
        elif service.status == ServiceStatus.UNKNOWN:
            service.status = ServiceStatus.HEALTHY

        # Reset failure count on successful operations
        if service.success_count % 5 == 0:  # Every 5 successes
            service.failure_count = max(0, service.failure_count - 1)

        self._evaluate_system_health()

    def record_failure(
        self, service_name: str, error: str, operation: str | None = None
    ) -> None:
        """
        Record a failed operation for a service.

        Args:
            service_name: Name of the service
            error: Error message or description
            operation: Specific operation that failed (optional)
        """
        if service_name not in self.services:
            logger.warning(f"Unknown service: {service_name}")
            return

        service = self.services[service_name]
        current_time = time.time()

        service.last_failure = current_time
        service.failure_count += 1
        service.error_message = error

        # Update service status based on failure patterns
        if service.failure_count >= 5:
            if service.status != ServiceStatus.FAILED:
                service.status = ServiceStatus.FAILED
                logger.error(
                    f"Service {service_name} marked as FAILED after {service.failure_count} failures"
                )
        elif service.failure_count >= 2:
            if service.status == ServiceStatus.HEALTHY:
                service.status = ServiceStatus.DEGRADED
                service.degraded_since = current_time
                logger.warning(f"Service {service_name} marked as DEGRADED")

        self._evaluate_system_health()

    def _evaluate_system_health(self) -> None:
        """Evaluate overall system health and adjust degradation level."""
        failed_services = [
            s for s in self.services.values() if s.status == ServiceStatus.FAILED
        ]
        degraded_services = [
            s for s in self.services.values() if s.status == ServiceStatus.DEGRADED
        ]
        healthy_services = [
            s for s in self.services.values() if s.status == ServiceStatus.HEALTHY
        ]

        failed_count = len(failed_services)
        degraded_count = len(degraded_services)
        healthy_count = len(healthy_services)

        previous_level = self.current_degradation

        # Determine degradation level based on service health
        if failed_count == 0 and degraded_count == 0:
            new_level = DegradationLevel.NORMAL
        elif failed_count == 0 and degraded_count <= 1:
            new_level = DegradationLevel.MINOR
        elif failed_count <= 1 or (failed_count == 0 and degraded_count >= 2):
            new_level = DegradationLevel.MODERATE
        elif failed_count >= 2 or healthy_count <= 1:
            new_level = DegradationLevel.SEVERE
        else:
            new_level = DegradationLevel.CRITICAL

        # Check for critical service failures
        critical_services = ["ip_service", "storage"]
        critical_failures = [
            s.name for s in failed_services if s.name in critical_services
        ]

        if critical_failures:
            if len(critical_failures) >= 2:
                new_level = DegradationLevel.CRITICAL
            elif new_level.value < DegradationLevel.SEVERE.value:
                new_level = DegradationLevel.SEVERE

        # Update degradation level
        if new_level != previous_level:
            self.current_degradation = new_level
            self._log_degradation_change(previous_level, new_level)

            # Record degradation history
            self.degradation_history.append(
                {
                    "timestamp": time.time(),
                    "from_level": previous_level.value,
                    "to_level": new_level.value,
                    "failed_services": [s.name for s in failed_services],
                    "degraded_services": [s.name for s in degraded_services],
                    "trigger": "automatic_evaluation",
                }
            )

            # Keep only last 50 degradation events
            if len(self.degradation_history) > 50:
                self.degradation_history = self.degradation_history[-50:]

    def _log_degradation_change(
        self, from_level: DegradationLevel, to_level: DegradationLevel
    ) -> None:
        """Log degradation level changes."""
        if to_level.value > from_level.value:  # Degrading
            logger.warning(
                f"System degradation increased: {from_level.value} → {to_level.value}"
            )
            logger.warning(f"New mode: {self.degradation_modes[to_level].description}")
        else:  # Improving
            logger.info(
                f"System degradation decreased: {from_level.value} → {to_level.value}"
            )
            logger.info(f"New mode: {self.degradation_modes[to_level].description}")

    def get_service_health(self, service_name: str) -> ServiceHealth | None:
        """Get health information for a specific service."""
        return self.services.get(service_name)

    def get_system_health(self) -> dict[str, Any]:
        """Get comprehensive system health information."""
        current_time = time.time()

        services_summary = {}
        for name, service in self.services.items():
            services_summary[name] = {
                "status": service.status.value,
                "failure_count": service.failure_count,
                "success_count": service.success_count,
                "last_success_ago": current_time - service.last_success
                if service.last_success > 0
                else None,
                "last_failure_ago": current_time - service.last_failure
                if service.last_failure > 0
                else None,
                "error_message": service.error_message,
                "degraded_duration": current_time - service.degraded_since
                if service.degraded_since
                else None,
                "capabilities": service.capabilities,
            }

        current_mode = self.degradation_modes[self.current_degradation]

        return {
            "degradation_level": self.current_degradation.value,
            "degradation_description": current_mode.description,
            "services": services_summary,
            "system_capabilities": {
                "ip_check_interval_multiplier": current_mode.ip_check_interval_multiplier,
                "max_retries_multiplier": current_mode.max_retries_multiplier,
                "notifications_enabled": current_mode.enable_notifications,
                "history_logging_enabled": current_mode.enable_history_logging,
                "status_commands_enabled": current_mode.enable_status_commands,
                "active_fallbacks": current_mode.fallback_behaviors,
            },
            "degradation_history": self.degradation_history[-10:],  # Last 10 events
        }

    def should_enable_feature(self, feature: str) -> bool:
        """
        Check if a feature should be enabled in the current degradation mode.

        Args:
            feature: Feature name to check

        Returns:
            True if feature should be enabled
        """
        mode = self.degradation_modes[self.current_degradation]

        feature_map = {
            "notifications": mode.enable_notifications,
            "history_logging": mode.enable_history_logging,
            "status_commands": mode.enable_status_commands,
        }

        return feature_map.get(feature, True)

    def get_adjusted_interval(self, base_interval: float) -> float:
        """
        Get adjusted interval based on current degradation level.

        Args:
            base_interval: Base interval in minutes

        Returns:
            Adjusted interval in minutes
        """
        mode = self.degradation_modes[self.current_degradation]
        return base_interval * mode.ip_check_interval_multiplier

    def get_adjusted_retries(self, base_retries: int) -> int:
        """
        Get adjusted retry count based on current degradation level.

        Args:
            base_retries: Base number of retries

        Returns:
            Adjusted number of retries
        """
        mode = self.degradation_modes[self.current_degradation]
        adjusted = int(base_retries * mode.max_retries_multiplier)
        return max(1, adjusted)  # Always allow at least 1 retry

    def is_fallback_active(self, fallback: str) -> bool:
        """
        Check if a specific fallback behavior is active.

        Args:
            fallback: Fallback behavior name

        Returns:
            True if fallback is active
        """
        mode = self.degradation_modes[self.current_degradation]
        return fallback in mode.fallback_behaviors

    def force_degradation_level(
        self, level: DegradationLevel, reason: str = "manual"
    ) -> None:
        """
        Manually force a degradation level.

        Args:
            level: Degradation level to set
            reason: Reason for manual change
        """
        previous_level = self.current_degradation
        self.current_degradation = level

        # Record in history
        self.degradation_history.append(
            {
                "timestamp": time.time(),
                "from_level": previous_level.value,
                "to_level": level.value,
                "failed_services": [],
                "degraded_services": [],
                "trigger": f"manual_{reason}",
            }
        )

        self._log_degradation_change(previous_level, level)
        logger.info(f"Degradation level manually set to {level.value}: {reason}")

    def reset_service_health(self, service_name: str) -> bool:
        """
        Reset health status for a specific service.

        Args:
            service_name: Name of service to reset

        Returns:
            True if service was reset successfully
        """
        if service_name not in self.services:
            return False

        service = self.services[service_name]
        service.status = ServiceStatus.UNKNOWN
        service.failure_count = 0
        service.success_count = 0
        service.error_message = None
        service.degraded_since = None

        logger.info(f"Reset health status for service: {service_name}")
        self._evaluate_system_health()
        return True

    def get_degradation_summary(self) -> str:
        """Get a human-readable summary of current degradation status."""
        mode = self.degradation_modes[self.current_degradation]

        failed_services = [
            s.name for s in self.services.values() if s.status == ServiceStatus.FAILED
        ]
        degraded_services = [
            s.name for s in self.services.values() if s.status == ServiceStatus.DEGRADED
        ]

        summary = f"System Status: {self.current_degradation.value.upper()}\n"
        summary += f"Description: {mode.description}\n"

        if failed_services:
            summary += f"Failed Services: {', '.join(failed_services)}\n"

        if degraded_services:
            summary += f"Degraded Services: {', '.join(degraded_services)}\n"

        if mode.fallback_behaviors:
            summary += f"Active Fallbacks: {', '.join(mode.fallback_behaviors)}\n"

        return summary.strip()


# Global service health monitor instance
service_health = ServiceHealthMonitor()
