"""Test stability utilities for measuring and improving test reliability."""
import time
from typing import Any, Dict, List, Optional
import pytest
import asyncio
from dataclasses import dataclass
from collections import defaultdict
import json
import os

@dataclass
class TestResult:
    """Represents a single test execution result."""
    test_name: str
    passed: bool
    duration: float
    error: Optional[str] = None
    retry_count: int = 0

@dataclass
class TestStabilityMetrics:
    """Stability metrics for a test suite."""
    total_tests: int
    passed_tests: int
    failed_tests: int
    average_duration: float
    flaky_tests: List[str]
    stability_score: float
    retry_rate: float

class TestStabilityTracker:
    """Tracks test stability metrics across runs."""
    
    def __init__(self, results_file: str = "test_stability_results.json"):
        self.results_file = results_file
        self.current_run_results: List[TestResult] = []
        self.historical_results: Dict[str, List[TestResult]] = defaultdict(list)
        self.load_historical_results()
    
    def load_historical_results(self) -> None:
        """Load historical test results from file."""
        if os.path.exists(self.results_file):
            try:
                with open(self.results_file, 'r') as f:
                    data = json.load(f)
                    for test_name, results in data.items():
                        self.historical_results[test_name] = [
                            TestResult(
                                test_name=r['test_name'],
                                passed=r['passed'],
                                duration=r['duration'],
                                error=r.get('error'),
                                retry_count=r.get('retry_count', 0)
                            )
                            for r in results
                        ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load historical results: {e}")
    
    def save_results(self) -> None:
        """Save current and historical results to file."""
        # Merge current results with historical
        for result in self.current_run_results:
            self.historical_results[result.test_name].append(result)
            # Keep only last 20 results per test
            if len(self.historical_results[result.test_name]) > 20:
                self.historical_results[result.test_name] = self.historical_results[result.test_name][-20:]
        
        # Convert to JSON-serializable format
        data = {}
        for test_name, results in self.historical_results.items():
            data[test_name] = [
                {
                    'test_name': r.test_name,
                    'passed': r.passed,
                    'duration': r.duration,
                    'error': r.error,
                    'retry_count': r.retry_count
                }
                for r in results
            ]
        
        with open(self.results_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_test_result(self, test_name: str, passed: bool, duration: float, 
                          error: Optional[str] = None, retry_count: int = 0) -> None:
        """Record a test result."""
        result = TestResult(
            test_name=test_name,
            passed=passed,
            duration=duration,
            error=error,
            retry_count=retry_count
        )
        self.current_run_results.append(result)
    
    def get_test_stability_score(self, test_name: str) -> float:
        """Calculate stability score for a specific test (0-100)."""
        results = self.historical_results.get(test_name, [])
        if not results:
            return 100.0  # New test, assume stable
        
        pass_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        
        return (pass_count / total_count) * 100.0
    
    def get_flaky_tests(self, threshold: float = 80.0) -> List[str]:
        """Get list of tests with stability score below threshold."""
        flaky_tests = []
        for test_name in self.historical_results:
            if self.get_test_stability_score(test_name) < threshold:
                flaky_tests.append(test_name)
        return flaky_tests
    
    def get_current_run_metrics(self) -> TestStabilityMetrics:
        """Get stability metrics for current test run."""
        if not self.current_run_results:
            return TestStabilityMetrics(0, 0, 0, 0.0, [], 100.0, 0.0)
        
        total_tests = len(self.current_run_results)
        passed_tests = sum(1 for r in self.current_run_results if r.passed)
        failed_tests = total_tests - passed_tests
        
        average_duration = sum(r.duration for r in self.current_run_results) / total_tests
        
        flaky_tests = self.get_flaky_tests()
        
        stability_score = (passed_tests / total_tests) * 100.0
        
        retry_count = sum(r.retry_count for r in self.current_run_results)
        retry_rate = retry_count / total_tests if total_tests > 0 else 0.0
        
        return TestStabilityMetrics(
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            average_duration=average_duration,
            flaky_tests=flaky_tests,
            stability_score=stability_score,
            retry_rate=retry_rate
        )
    
    def print_stability_report(self) -> None:
        """Print a stability report for the current run."""
        metrics = self.get_current_run_metrics()
        
        print("\n" + "="*60)
        print("TEST STABILITY REPORT")
        print("="*60)
        print(f"Total Tests: {metrics.total_tests}")
        print(f"Passed: {metrics.passed_tests}")
        print(f"Failed: {metrics.failed_tests}")
        print(f"Average Duration: {metrics.average_duration:.2f}s")
        print(f"Stability Score: {metrics.stability_score:.1f}%")
        print(f"Retry Rate: {metrics.retry_rate:.2f}")
        
        if metrics.flaky_tests:
            print(f"\nFlaky Tests ({len(metrics.flaky_tests)}):")
            for test in metrics.flaky_tests[:10]:  # Show top 10
                score = self.get_test_stability_score(test)
                print(f"  - {test}: {score:.1f}%")
        
        print("="*60)

# Global tracker instance
_stability_tracker = TestStabilityTracker()

def get_stability_tracker() -> TestStabilityTracker:
    """Get the global stability tracker instance."""
    return _stability_tracker

# Pytest fixtures for stability tracking
@pytest.fixture(scope="session", autouse=True)
def stability_tracker():
    """Provide stability tracker for tests."""
    return _stability_tracker

@pytest.fixture(autouse=True)
def track_test_stability(request, stability_tracker):
    """Automatically track test stability."""
    start_time = time.time()
    test_name = request.node.nodeid
    
    yield
    
    duration = time.time() - start_time
    passed = not hasattr(request.node, 'rep_call') or request.node.rep_call.passed
    error = None
    retry_count = 0
    
    if hasattr(request.node, 'rep_call') and request.node.rep_call.failed:
        error = str(request.node.rep_call.longrepr)
    
    # Check if test was retried (if pytest-rerunfailures is used)
    if hasattr(request.node, 'execution_count'):
        retry_count = request.node.execution_count - 1
    
    stability_tracker.record_test_result(test_name, passed, duration, error, retry_count)

@pytest.fixture(scope="session", autouse=True)
def save_stability_results(stability_tracker):
    """Save stability results at the end of test session."""
    yield
    stability_tracker.save_results()
    stability_tracker.print_stability_report()

# Utility functions for test marking
def mark_flaky_test(test_func):
    """Mark a test as flaky and configure appropriate retries."""
    return pytest.mark.flaky(
        pytest.mark.timeout(60),
        test_func
    )

def mark_stability_test(test_func):
    """Mark a test as a stability test."""
    return pytest.mark.stability(test_func)

def mark_critical_test(test_func):
    """Mark a test as critical (should not be skipped)."""
    return pytest.mark.critical(test_func)

# Async utilities for test stability
async def retry_async_operation(operation, max_retries: int = 3, delay: float = 1.0):
    """Retry an async operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(delay * (2 ** attempt))
    
def timeout_async_test(timeout_seconds: int = 30):
    """Decorator to add timeout to async tests."""
    def decorator(test_func):
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(test_func(*args, **kwargs), timeout=timeout_seconds)
        return wrapper
    return decorator