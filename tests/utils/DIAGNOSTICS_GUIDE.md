# Integration Test Diagnostics Guide

This guide explains how to use the enhanced error diagnostics system for integration tests.

## Overview

The diagnostics system provides comprehensive error reporting, performance monitoring, and failure analysis for integration tests. It helps identify root causes of test failures and provides actionable recommendations for fixes.

## Key Components

### 1. Error Diagnostics (`error_diagnostics.py`)

The core diagnostic engine that tracks:
- **Async Task Failures**: Detailed information about failed async operations
- **Resource Leaks**: Detection of memory, connection, and file handle leaks
- **Service Interactions**: Tracking of service state changes and interactions
- **Performance Metrics**: Collection of timing and performance data
- **System State**: Capture of system resources and health

### 2. Test Reporting (`test_reporting.py`)

Generates comprehensive reports in multiple formats:
- **HTML Reports**: Interactive web-based failure analysis
- **JSON Reports**: Machine-readable data for automated analysis
- **Summary Reports**: Concise Markdown summaries for quick review

### 3. Diagnostic Helpers (`diagnostic_helpers.py`)

Easy-to-use decorators and utilities for integrating diagnostics into tests:
- **@with_diagnostics**: Automatic diagnostic tracking for test functions
- **@track_service_state**: Monitor service state changes
- **@monitor_async_operations**: Track async operation performance
- **DiagnosticContext**: Manual diagnostic context management

## Quick Start

### Basic Usage

Add diagnostics to any test with a simple decorator:

```python
from tests.utils.diagnostic_helpers import with_diagnostics

@pytest.mark.asyncio
@with_diagnostics
async def test_my_feature():
    # Your test code here
    # Diagnostics are automatically tracked
    pass
```

### Enhanced Assertions

Use `assert_with_context` for better error messages:

```python
from tests.utils.diagnostic_helpers import assert_with_context

async def test_ip_check():
    result = await ip_service.get_current_ip()
    
    assert_with_context(
        result == "192.168.1.1",
        "IP check failed",
        expected="192.168.1.1",
        actual=result,
        service_state=service.get_state()
    )
```

### Performance Monitoring

Track operation performance automatically:

```python
from tests.utils.diagnostic_helpers import monitor_async_operations

@pytest.mark.asyncio
@monitor_async_operations("database_test", timeout=30.0)
async def test_database_performance():
    # Database operations will be monitored
    await storage.save_current_ip("192.168.1.1")
    result = await storage.get_current_ip()
    return result
```

### Service State Tracking

Monitor service state changes throughout tests:

```python
from tests.utils.diagnostic_helpers import track_service_state

@pytest.mark.asyncio
@track_service_state("ip_service")
async def test_ip_service_behavior():
    # Service state changes are automatically tracked
    self.ip_service = ip_service  # Required for state tracking
    await ip_service.get_current_ip()
```

## Advanced Usage

### Manual Diagnostic Context

For fine-grained control over diagnostic tracking:

```python
from tests.utils.diagnostic_helpers import DiagnosticContext

async def test_complex_operation():
    async with DiagnosticContext("complex_test") as ctx:
        # Step 1
        ctx.record_checkpoint("step_1_start")
        result1 = await operation1()
        ctx.record_checkpoint("step_1_complete", {"result": result1})
        
        # Step 2
        ctx.record_checkpoint("step_2_start")
        result2 = await operation2()
        ctx.record_checkpoint("step_2_complete", {"result": result2})
        
        # Final validation
        assert result1 and result2
```

### Concurrent Operation Tracking

Track multiple concurrent operations:

```python
from tests.utils.diagnostic_helpers import track_concurrent_operations

async def test_concurrent_operations():
    operations = [
        lambda: service.get_ip(),
        lambda: service.check_health(),
        lambda: service.get_metrics()
    ]
    
    operation_names = ["get_ip", "check_health", "get_metrics"]
    
    results = await track_concurrent_operations(
        operations, 
        operation_names, 
        timeout=10.0
    )
    
    # Results include success/failure information
    successful = [r for r in results if not isinstance(r, Exception)]
    assert len(successful) >= 2  # At least 2 operations should succeed
```

### Test Checkpoints

Add checkpoints to track test progress:

```python
from tests.utils.diagnostic_helpers import log_test_checkpoint

async def test_with_checkpoints():
    log_test_checkpoint("Starting test")
    
    # Phase 1
    await setup_phase()
    log_test_checkpoint("Setup complete")
    
    # Phase 2
    result = await main_operation()
    log_test_checkpoint("Main operation complete", {"result": result})
    
    # Phase 3
    await verification_phase()
    log_test_checkpoint("Verification complete")
```

## Diagnostic Output

### Error Reports

When tests fail, diagnostic reports include:

```
Test failure diagnostic report for test_ip_check:
  Primary error: TimeoutError: Request timeout
  Duration: 15.23s
  Task failures (2):
    - ip_check_task: TimeoutError: Request timeout
    - health_check_task: ConnectionError: Connection refused
  Resource leaks (1):
    - open_files: 3 units
  Service failures (1):
    - ip_service: Circuit breaker is open
  Recommendations:
    - Consider increasing timeout values for async operations
    - Address 2 async task failures
    - Fix 1 resource leaks
```

### Performance Metrics

Performance data is automatically collected:

```python
# Performance metrics are collected for:
# - Operation duration
# - Success/failure rates
# - Resource usage
# - Concurrent operation efficiency
```

### HTML Reports

Generate comprehensive HTML reports:

```python
from tests.utils.diagnostic_helpers import generate_test_report

# Generate HTML report
report_path = generate_test_report("integration_tests", format="html")
print(f"Report generated: {report_path}")
```

## Integration Patterns

### Pattern 1: Basic Test Enhancement

```python
@pytest.mark.asyncio
@with_diagnostics
async def test_basic_feature():
    # Minimal integration - just add the decorator
    result = await my_operation()
    assert result == expected
```

### Pattern 2: Service Monitoring

```python
@pytest.mark.asyncio
@with_diagnostics
@track_service_state("my_service")
@monitor_async_operations("service_test", timeout=30.0)
async def test_service_behavior():
    self.my_service = service  # Required for state tracking
    result = await service.perform_operation()
    assert result is not None
```

### Pattern 3: Complex Multi-Step Test

```python
@pytest.mark.asyncio
@with_diagnostics
async def test_complex_workflow():
    async with DiagnosticContext("workflow_test") as ctx:
        # Step 1: Setup
        ctx.record_checkpoint("setup_start")
        setup_result = await setup_operation()
        ctx.record_checkpoint("setup_complete", {"setup": setup_result})
        
        # Step 2: Main operation
        ctx.record_checkpoint("main_operation_start")
        main_result = await main_operation()
        ctx.record_checkpoint("main_operation_complete", {"result": main_result})
        
        # Step 3: Validation
        ctx.record_checkpoint("validation_start")
        assert_with_context(
            main_result == expected,
            "Main operation failed",
            expected=expected,
            actual=main_result,
            setup_result=setup_result
        )
        ctx.record_checkpoint("validation_complete")
```

## Best Practices

### 1. Use Appropriate Decorators

- **@with_diagnostics**: Essential for all integration tests
- **@track_service_state**: When testing service interactions
- **@monitor_async_operations**: For performance-critical operations

### 2. Provide Context in Assertions

```python
# Good
assert_with_context(
    result == expected,
    "Operation failed",
    expected=expected,
    actual=result,
    context_data=additional_info
)

# Avoid
assert result == expected
```

### 3. Use Checkpoints for Long Tests

```python
# For tests with multiple phases
log_test_checkpoint("Phase 1 complete")
log_test_checkpoint("Phase 2 complete", {"data": phase_result})
```

### 4. Handle Concurrent Operations

```python
# Use the helper for concurrent operations
results = await track_concurrent_operations(operations, names, timeout=30.0)

# Rather than manual asyncio.gather
```

### 5. Generate Reports After Test Runs

```python
# At the end of test suite
report = generate_test_report("my_test_suite", format="summary")
print(f"Test summary: {report}")
```

## Troubleshooting

### Common Issues

1. **Service State Not Tracked**: Ensure you assign the service to `self.service_name` in tests with `@track_service_state`

2. **Missing Context**: Use `DiagnosticContext` for operations that need detailed tracking

3. **Performance Data Not Collected**: Ensure operations are wrapped with `@monitor_async_operations` or `@measure_performance`

4. **Reports Not Generated**: Call `generate_test_report()` after test execution

### Debugging Tips

1. **Check Diagnostic Logs**: Error diagnostics log detailed information about failures

2. **Review Checkpoint Data**: Use checkpoint data to understand test execution flow

3. **Analyze Performance Metrics**: Look for patterns in timing and resource usage

4. **Use HTML Reports**: HTML reports provide interactive analysis of failures

## Examples

See `tests/integration/test_diagnostics_example.py` for comprehensive examples of diagnostic usage patterns.

See `tests/integration/test_error_recovery_enhanced.py` for examples of enhancing existing tests with diagnostics.

## Configuration

### Environment Variables

```bash
# Enable verbose diagnostic logging
DIAGNOSTIC_VERBOSE=true

# Set diagnostic report output directory
DIAGNOSTIC_REPORT_DIR=./test_reports

# Configure diagnostic timeouts
DIAGNOSTIC_DEFAULT_TIMEOUT=30.0
```

### Pytest Configuration

```ini
# In pytest.ini
[tool:pytest]
markers =
    diagnostics: marks tests as using diagnostic features
    
addopts = --tb=short --capture=no
log_cli = true
log_cli_level = INFO
```

This diagnostic system transforms integration test failures from mysterious errors into actionable insights, significantly improving development velocity and test reliability.