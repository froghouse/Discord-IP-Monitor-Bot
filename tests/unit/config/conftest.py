"""
Shared fixtures and utilities for configuration tests.
"""

import os
import pytest
from unittest.mock import MagicMock, mock_open, patch

from ip_monitor.config import AppConfig


@pytest.fixture
def env_cleanup():
    """Clean up environment variables before and after tests."""
    env_vars_to_clear = [
        'DISCORD_BOT_TOKEN', 'CHANNEL_ID', 'CHECK_INTERVAL', 'MAX_RETRIES',
        'RETRY_DELAY', 'CONCURRENT_API_CHECKS', 'CIRCUIT_BREAKER_ENABLED',
        'CIRCUIT_BREAKER_FAILURE_THRESHOLD', 'CIRCUIT_BREAKER_RECOVERY_TIMEOUT',
        'RATE_LIMIT_PERIOD', 'MAX_CHECKS_PER_PERIOD', 'DB_FILE', 'IP_FILE',
        'IP_HISTORY_FILE', 'IP_HISTORY_SIZE', 'STARTUP_MESSAGE_ENABLED',
        'TESTING_MODE', 'LOG_LEVEL', 'CUSTOM_APIS_ENABLED', 'API_CONFIG_FILE',
        'MESSAGE_QUEUE_ENABLED', 'MESSAGE_QUEUE_MAX_SIZE', 'MESSAGE_QUEUE_MAX_AGE_HOURS',
        'MESSAGE_QUEUE_BATCH_SIZE', 'MESSAGE_QUEUE_PROCESS_INTERVAL',
        'CONNECTION_POOL_SIZE', 'CONNECTION_POOL_MAX_KEEPALIVE',
        'CONNECTION_TIMEOUT', 'READ_TIMEOUT', 'CACHE_ENABLED', 'CACHE_TTL',
        'CACHE_MAX_MEMORY_SIZE', 'CACHE_STALE_THRESHOLD', 'CACHE_FILE',
        'CACHE_CLEANUP_INTERVAL'
    ]
    
    # Store original values
    original_env_values = {}
    for var in env_vars_to_clear:
        original_env_values[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    for var in env_vars_to_clear:
        if var in os.environ:
            del os.environ[var]
        if original_env_values[var] is not None:
            os.environ[var] = original_env_values[var]


@pytest.fixture
def base_config():
    """Create a test configuration instance with standard values."""
    return AppConfig(
        discord_token='test_token',
        channel_id=123456789,
        check_interval=30,
        max_retries=3,
        retry_delay=5,
        concurrent_api_checks=True,
        circuit_breaker_enabled=True,
        circuit_breaker_failure_threshold=3,
        circuit_breaker_recovery_timeout=120.0,
        rate_limit_period=300,
        max_checks_per_period=10,
        db_file='test.db',
        ip_file='test_ip.json',
        ip_history_file='test_history.json',
        ip_history_size=10,
        startup_message_enabled=True,
        testing_mode=False,
        log_level='INFO',
        custom_apis_enabled=True,
        api_config_file='test_apis.json',
        message_queue_enabled=True,
        message_queue_max_size=1000,
        message_queue_max_age_hours=24,
        message_queue_batch_size=5,
        message_queue_process_interval=1.0,
        connection_pool_size=10,
        connection_pool_max_keepalive=5,
        connection_timeout=10.0,
        read_timeout=30.0,
        cache_enabled=True,
        cache_ttl=300,
        cache_max_memory_size=1000,
        cache_stale_threshold=0.8,
        cache_file='test_cache.json',
        cache_cleanup_interval=300,
    )


@pytest.fixture
def minimal_env_config():
    """Set up minimal environment configuration for tests."""
    os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
    os.environ['CHANNEL_ID'] = '123456789'
    yield
    # Cleanup handled by env_cleanup fixture


@pytest.fixture
def comprehensive_env_config():
    """Set up comprehensive environment configuration for tests."""
    env_vars = {
        'DISCORD_BOT_TOKEN': 'comprehensive_test_token',
        'CHANNEL_ID': '987654321',
        'CHECK_INTERVAL': '45',
        'MAX_RETRIES': '7',
        'RETRY_DELAY': '8',
        'CONCURRENT_API_CHECKS': 'false',
        'CIRCUIT_BREAKER_ENABLED': 'false',
        'CIRCUIT_BREAKER_FAILURE_THRESHOLD': '5',
        'CIRCUIT_BREAKER_RECOVERY_TIMEOUT': '200.5',
        'RATE_LIMIT_PERIOD': '900',
        'MAX_CHECKS_PER_PERIOD': '25',
        'DB_FILE': 'comprehensive.db',
        'IP_FILE': 'comprehensive_ip.json',
        'IP_HISTORY_FILE': 'comprehensive_history.json',
        'IP_HISTORY_SIZE': '25',
        'STARTUP_MESSAGE_ENABLED': 'false',
        'TESTING_MODE': 'true',
        'LOG_LEVEL': 'warning',
        'CUSTOM_APIS_ENABLED': 'false',
        'API_CONFIG_FILE': 'comprehensive_apis.json',
        'MESSAGE_QUEUE_ENABLED': 'false',
        'MESSAGE_QUEUE_MAX_SIZE': '2000',
        'MESSAGE_QUEUE_MAX_AGE_HOURS': '48',
        'MESSAGE_QUEUE_BATCH_SIZE': '10',
        'MESSAGE_QUEUE_PROCESS_INTERVAL': '5.0',
        'CONNECTION_POOL_SIZE': '20',
        'CONNECTION_POOL_MAX_KEEPALIVE': '15',
        'CONNECTION_TIMEOUT': '20.0',
        'READ_TIMEOUT': '60.0',
        'CACHE_ENABLED': 'false',
        'CACHE_TTL': '600',
        'CACHE_MAX_MEMORY_SIZE': '2000',
        'CACHE_STALE_THRESHOLD': '0.9',
        'CACHE_FILE': 'comprehensive_cache.json',
        'CACHE_CLEANUP_INTERVAL': '600',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    yield
    # Cleanup handled by env_cleanup fixture


# Helper functions for common test patterns
def assert_config_defaults(config):
    """Assert that configuration has expected default values."""
    assert config.check_interval == AppConfig.DEFAULT_CHECK_INTERVAL
    assert config.max_retries == AppConfig.DEFAULT_MAX_RETRIES
    assert config.retry_delay == AppConfig.DEFAULT_RETRY_DELAY
    assert config.ip_history_size == AppConfig.DEFAULT_IP_HISTORY_SIZE
    assert config.rate_limit_period == AppConfig.DEFAULT_RATE_LIMIT_PERIOD
    assert config.max_checks_per_period == AppConfig.DEFAULT_MAX_CHECKS
    assert config.circuit_breaker_failure_threshold == AppConfig.DEFAULT_CIRCUIT_BREAKER_FAILURE_THRESHOLD
    assert config.circuit_breaker_recovery_timeout == AppConfig.DEFAULT_CIRCUIT_BREAKER_RECOVERY_TIMEOUT
    assert config.message_queue_max_size == AppConfig.DEFAULT_MESSAGE_QUEUE_MAX_SIZE
    assert config.message_queue_max_age_hours == AppConfig.DEFAULT_MESSAGE_QUEUE_MAX_AGE_HOURS
    assert config.message_queue_batch_size == AppConfig.DEFAULT_MESSAGE_QUEUE_BATCH_SIZE
    assert config.message_queue_process_interval == AppConfig.DEFAULT_MESSAGE_QUEUE_PROCESS_INTERVAL
    assert config.connection_pool_size == AppConfig.DEFAULT_CONNECTION_POOL_SIZE
    assert config.connection_pool_max_keepalive == AppConfig.DEFAULT_CONNECTION_POOL_MAX_KEEPALIVE
    assert config.connection_timeout == AppConfig.DEFAULT_CONNECTION_TIMEOUT
    assert config.read_timeout == AppConfig.DEFAULT_READ_TIMEOUT
    assert config.cache_ttl == AppConfig.DEFAULT_CACHE_TTL
    assert config.cache_max_memory_size == AppConfig.DEFAULT_CACHE_MAX_MEMORY_SIZE
    assert config.cache_stale_threshold == AppConfig.DEFAULT_CACHE_STALE_THRESHOLD
    assert config.cache_cleanup_interval == AppConfig.DEFAULT_CACHE_CLEANUP_INTERVAL


def assert_config_boolean_defaults(config):
    """Assert that configuration has expected default boolean values."""
    assert config.concurrent_api_checks is True
    assert config.circuit_breaker_enabled is True
    assert config.startup_message_enabled is True
    assert config.testing_mode is False
    assert config.custom_apis_enabled is True
    assert config.message_queue_enabled is True
    assert config.cache_enabled is True


def assert_config_string_defaults(config):
    """Assert that configuration has expected default string values."""
    assert config.db_file == "ip_monitor.db"
    assert config.ip_file == "last_ip.json"
    assert config.ip_history_file == "ip_history.json"
    assert config.log_level == "INFO"
    assert config.api_config_file == "ip_apis.json"
    assert config.cache_file == "cache.json"