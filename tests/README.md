# Integration Tests with HTTP Server Mocks

This directory contains comprehensive integration tests that use real HTTP servers to test the Discord IP Monitor Bot's behavior under realistic network conditions.

## Overview

The integration test suite provides:

- **Real HTTP Server Mocks**: Actual HTTP servers that simulate IP API endpoints
- **Network Condition Simulation**: Latency, failures, rate limiting, and timeouts
- **End-to-End Testing**: Complete bot lifecycle testing with realistic scenarios
- **Performance Testing**: Load testing and performance monitoring
- **Disaster Recovery Testing**: Multi-tier failover and recovery scenarios

## Test Structure

### Core Integration Tests

#### `test_ip_service_http_integration.py`
Tests IP service HTTP client behavior with real servers:
- JSON and text API response parsing
- Custom JSON field handling
- API failover and retry logic
- Timeout and error handling
- Rate limiting detection
- Circuit breaker integration
- Performance monitoring
- Connection pooling

#### `test_bot_lifecycle_http_integration.py`
Tests complete bot lifecycle with HTTP operations:
- Bot startup with IP checking
- Periodic monitoring with IP changes
- Command handling with HTTP integration
- Error recovery during monitoring
- Message queue integration
- Cache integration
- Graceful shutdown with active connections

#### `test_admin_commands_http_integration.py`
Tests admin command functionality with HTTP integration:
- API management (add, test, remove, stats)
- HTTP server performance monitoring
- Rate limiting detection and handling
- API cluster management
- Security and error handling
- Configuration updates affecting HTTP behavior

#### `test_real_world_scenarios.py`
Comprehensive real-world scenario testing:
- Complete deployment scenarios
- API service outages and recovery
- High-load monitoring
- Network partition recovery
- Production monitoring simulation
- Disaster recovery testing

### Test Utilities

#### `utils/http_server_mocks.py`
HTTP server mock utilities providing:
- `MockIPAPIServer`: Single configurable HTTP server
- `MockAPICluster`: Cluster of servers for failover testing
- `HTTPMockFixture`: Test fixture for server lifecycle management
- `MockServerContext`: Context manager for easy server usage

## Running the Tests

### Prerequisites

Install test dependencies:
```bash
./.venv/bin/pip install pytest pytest-asyncio pytest-mock pytest-cov aiohttp
```

### Running All Integration Tests

```bash
# Run all integration tests
./.venv/bin/python -m pytest tests/integration/ -v

# Run with coverage
./.venv/bin/python -m pytest tests/integration/ --cov=ip_monitor --cov-report=html

# Run specific test file
./.venv/bin/python -m pytest tests/integration/test_ip_service_http_integration.py -v
```

### Running Specific Test Categories

```bash
# IP service HTTP tests
./.venv/bin/python -m pytest tests/integration/test_ip_service_http_integration.py -v

# Bot lifecycle tests
./.venv/bin/python -m pytest tests/integration/test_bot_lifecycle_http_integration.py -v

# Admin command tests
./.venv/bin/python -m pytest tests/integration/test_admin_commands_http_integration.py -v

# Real-world scenario tests
./.venv/bin/python -m pytest tests/integration/test_real_world_scenarios.py -v
```

### Running Performance Tests

```bash
# High-load scenarios
./.venv/bin/python -m pytest tests/integration/test_real_world_scenarios.py::TestRealWorldScenarios::test_high_load_monitoring_scenario -v

# Performance monitoring
./.venv/bin/python -m pytest tests/integration/test_ip_service_http_integration.py -k "performance" -v
```

## Test Features

### HTTP Server Mock Capabilities

The HTTP server mocks provide realistic simulation of:

- **Response Types**: JSON, plain text, custom formats
- **Network Conditions**: Configurable latency (10ms to 5000ms)
- **Failure Scenarios**: Error rates, timeouts, connection failures
- **Rate Limiting**: Configurable requests per minute
- **Performance Monitoring**: Request tracking and statistics

### Configuration Options

Mock servers can be configured with:

```python
server.set_latency(100)        # 100ms response time
server.set_error_rate(0.2)     # 20% error rate
server.set_rate_limit(30)      # 30 requests per minute
server.configure_endpoint(     # Custom endpoint
    "/custom", 
    {"custom_field": "203.0.113.1"}
)
```

### Cluster Testing

Test failover scenarios with server clusters:

```python
cluster = MockAPICluster(server_count=5)
cluster.fail_server(0)        # Simulate server failure
cluster.recover_server(0)     # Simulate server recovery
```

## Test Scenarios Covered

### Network Resilience
- API server failures and recovery
- Network partitions and timeouts
- Rate limiting and throttling
- DNS resolution failures
- Connection pool exhaustion

### Performance Testing
- Concurrent request handling
- Cache effectiveness
- Circuit breaker behavior
- Load balancing across APIs
- Response time monitoring

### Real-World Conditions
- Multi-datacenter failover
- Maintenance window simulation
- Peak load handling
- Disaster recovery procedures
- Gradual degradation scenarios

### Security Testing
- Malicious URL rejection
- Input validation
- Error message sanitization
- Rate limiting enforcement

## Best Practices

### Writing Integration Tests

1. **Use Fixtures**: Leverage shared fixtures for consistent setup
2. **Mock External Dependencies**: Only test HTTP behavior, mock Discord/storage
3. **Test Error Conditions**: Include failure scenarios and edge cases
4. **Verify Cleanup**: Ensure servers are properly stopped after tests
5. **Use Realistic Data**: Test with actual IP addresses and response formats

### Performance Considerations

1. **Parallel Execution**: Tests can run in parallel using pytest-xdist
2. **Resource Management**: Servers automatically clean up after tests
3. **Timeouts**: Configure appropriate timeouts for test scenarios
4. **Port Management**: Servers use random available ports

### Debugging Failed Tests

1. **Enable Verbose Output**: Use `-v` flag for detailed test output
2. **Check Server Logs**: Mock servers track all requests and responses
3. **Inspect Statistics**: Use server statistics for debugging
4. **Isolate Tests**: Run individual tests to isolate issues

## Example Usage

### Basic HTTP Server Test

```python
async def test_api_call(http_fixture):
    server = await http_fixture.create_server()
    
    # Configure server behavior
    server.set_latency(50)  # 50ms latency
    
    # Test your code against the server
    response = await your_http_client.get(f"{server.base_url}/json")
    
    # Verify results
    assert response.json()["ip"] == "203.0.113.1"
    assert server.get_request_count() == 1
```

### Failover Testing

```python
async def test_failover(http_fixture):
    cluster = await http_fixture.create_cluster(server_count=3)
    
    # Fail primary server
    cluster.fail_server(0)
    
    # Test failover behavior
    result = await your_service.get_ip()
    
    # Verify backup servers were used
    stats = cluster.get_cluster_stats()
    assert stats["total_requests"] >= 1
```

## Continuous Integration

These tests are designed to run in CI environments:

- **Fast Execution**: Most tests complete in under 30 seconds
- **Deterministic**: Tests use controlled timing and conditions
- **Resource Efficient**: Automatic cleanup prevents resource leaks
- **Parallelizable**: Tests can run concurrently without conflicts

## Troubleshooting

### Common Issues

1. **Port Conflicts**: Tests use random ports to avoid conflicts
2. **Timing Issues**: Tests include appropriate delays and timeouts
3. **Resource Cleanup**: Use fixtures to ensure proper cleanup
4. **Network Dependencies**: Tests are fully self-contained

### Environment Variables

Set these for enhanced testing:

```bash
export PYTEST_TIMEOUT=60        # Test timeout in seconds
export PYTEST_WORKERS=4         # Parallel test workers
export LOG_LEVEL=DEBUG          # Enable debug logging
```