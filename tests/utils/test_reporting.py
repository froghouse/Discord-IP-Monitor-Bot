"""
Enhanced test reporting utilities for better failure analysis.

This module provides tools for generating detailed test reports,
analyzing test patterns, and providing actionable insights.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any

from .error_diagnostics import TestDiagnosticReport


@dataclass
class TestRunSummary:
    """Summary of a test run with enhanced diagnostics."""

    test_suite: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    total_duration: float
    start_time: float
    end_time: float
    failure_reports: list[TestDiagnosticReport]
    performance_summary: dict[str, Any]
    resource_usage_summary: dict[str, Any]
    recommendations: list[str]


class TestReporter:
    """Enhanced test reporter with diagnostic capabilities."""

    def __init__(self, output_dir: str = "test_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.reports: list[TestDiagnosticReport] = []
        self.start_time = time.time()

    def add_report(self, report: TestDiagnosticReport) -> None:
        """Add a diagnostic report to the collection."""
        self.reports.append(report)

    def generate_html_report(self, test_suite: str) -> str:
        """Generate an HTML report with enhanced diagnostics."""
        html_content = self._generate_html_template(test_suite)

        report_file = self.output_dir / f"{test_suite}_report.html"
        with open(report_file, "w") as f:
            f.write(html_content)

        return str(report_file)

    def generate_json_report(self, test_suite: str) -> str:
        """Generate a JSON report for programmatic analysis."""
        summary = self._create_test_summary(test_suite)

        # Convert to JSON-serializable format
        json_data = {
            "test_suite": summary.test_suite,
            "total_tests": summary.total_tests,
            "passed_tests": summary.passed_tests,
            "failed_tests": summary.failed_tests,
            "skipped_tests": summary.skipped_tests,
            "total_duration": summary.total_duration,
            "start_time": summary.start_time,
            "end_time": summary.end_time,
            "failure_reports": [
                self._serialize_report(report) for report in summary.failure_reports
            ],
            "performance_summary": summary.performance_summary,
            "resource_usage_summary": summary.resource_usage_summary,
            "recommendations": summary.recommendations,
        }

        report_file = self.output_dir / f"{test_suite}_report.json"
        with open(report_file, "w") as f:
            json.dump(json_data, f, indent=2, default=str)

        return str(report_file)

    def generate_summary_report(self, test_suite: str) -> str:
        """Generate a concise summary report."""
        summary = self._create_test_summary(test_suite)

        report_content = f"""
# Test Run Summary: {test_suite}

## Overview
- **Total Tests**: {summary.total_tests}
- **Passed**: {summary.passed_tests}
- **Failed**: {summary.failed_tests}
- **Skipped**: {summary.skipped_tests}
- **Duration**: {summary.total_duration:.2f}s
- **Success Rate**: {(summary.passed_tests / summary.total_tests * 100):.1f}%

## Performance Summary
{self._format_performance_summary(summary.performance_summary)}

## Resource Usage Summary
{self._format_resource_summary(summary.resource_usage_summary)}

## Failure Analysis
{self._format_failure_analysis(summary.failure_reports)}

## Recommendations
{self._format_recommendations(summary.recommendations)}
"""

        report_file = self.output_dir / f"{test_suite}_summary.md"
        with open(report_file, "w") as f:
            f.write(report_content)

        return str(report_file)

    def _create_test_summary(self, test_suite: str) -> TestRunSummary:
        """Create a comprehensive test summary."""
        total_tests = len(self.reports)
        failed_tests = len([r for r in self.reports if r.primary_error])
        passed_tests = total_tests - failed_tests

        total_duration = sum(r.test_duration for r in self.reports)
        end_time = time.time()

        # Analyze performance metrics
        performance_summary = self._analyze_performance_metrics()

        # Analyze resource usage
        resource_usage_summary = self._analyze_resource_usage()

        # Generate recommendations
        recommendations = self._generate_comprehensive_recommendations()

        return TestRunSummary(
            test_suite=test_suite,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=0,  # Not tracked in current implementation
            total_duration=total_duration,
            start_time=self.start_time,
            end_time=end_time,
            failure_reports=[r for r in self.reports if r.primary_error],
            performance_summary=performance_summary,
            resource_usage_summary=resource_usage_summary,
            recommendations=recommendations,
        )

    def _analyze_performance_metrics(self) -> dict[str, Any]:
        """Analyze performance metrics across all tests."""
        all_metrics = {}

        for report in self.reports:
            for metric_name, metric_data in report.performance_metrics.get(
                "by_metric", {}
            ).items():
                if metric_name not in all_metrics:
                    all_metrics[metric_name] = {"values": [], "contexts": []}
                all_metrics[metric_name]["values"].extend(
                    [s["value"] for s in metric_data["samples"]]
                )
                all_metrics[metric_name]["contexts"].extend(
                    [s["context"] for s in metric_data["samples"]]
                )

        # Calculate aggregated statistics
        summary = {}
        for metric_name, data in all_metrics.items():
            values = data["values"]
            if values:
                summary[metric_name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "p95": sorted(values)[int(len(values) * 0.95)]
                    if len(values) > 20
                    else max(values),
                }

        return summary

    def _analyze_resource_usage(self) -> dict[str, Any]:
        """Analyze resource usage patterns."""
        resource_data = {
            "memory_leaks": [],
            "connection_leaks": [],
            "file_leaks": [],
            "task_failures": [],
            "common_patterns": [],
        }

        for report in self.reports:
            # Collect resource leaks
            for leak in report.resource_leaks:
                leak_type = leak.resource_type
                if "memory" in leak_type.lower():
                    resource_data["memory_leaks"].append(leak)
                elif "connection" in leak_type.lower():
                    resource_data["connection_leaks"].append(leak)
                elif "file" in leak_type.lower():
                    resource_data["file_leaks"].append(leak)

            # Collect task failures
            resource_data["task_failures"].extend(report.task_failures)

        # Analyze common patterns
        resource_data["common_patterns"] = self._identify_common_patterns(resource_data)

        return resource_data

    def _generate_comprehensive_recommendations(self) -> list[str]:
        """Generate comprehensive recommendations based on all reports."""
        recommendations = []

        # Analyze failure patterns
        failure_types = {}
        for report in self.reports:
            failure_type = report.failure_type
            if failure_type not in failure_types:
                failure_types[failure_type] = []
            failure_types[failure_type].append(report)

        # Generate recommendations based on patterns
        if "TimeoutError" in failure_types:
            count = len(failure_types["TimeoutError"])
            recommendations.append(
                f"Address {count} timeout failures - consider increasing timeouts or optimizing async operations"
            )

        if "ConnectionError" in failure_types:
            count = len(failure_types["ConnectionError"])
            recommendations.append(
                f"Fix {count} connection failures - check network setup and mock server configuration"
            )

        # Resource-based recommendations
        resource_leaks = sum(len(r.resource_leaks) for r in self.reports)
        if resource_leaks > 0:
            recommendations.append(
                f"Fix {resource_leaks} resource leaks - implement proper cleanup in test fixtures"
            )

        # Task-based recommendations
        task_failures = sum(len(r.task_failures) for r in self.reports)
        if task_failures > 0:
            recommendations.append(
                f"Address {task_failures} async task failures - improve task management and cancellation"
            )

        # Performance-based recommendations
        slow_tests = [r for r in self.reports if r.test_duration > 10.0]
        if slow_tests:
            recommendations.append(
                f"Optimize {len(slow_tests)} slow tests - consider parallelization or test scope reduction"
            )

        return recommendations

    def _identify_common_patterns(self, resource_data: dict[str, Any]) -> list[str]:
        """Identify common patterns in resource usage."""
        patterns = []

        # Memory leak patterns
        if len(resource_data["memory_leaks"]) > 3:
            patterns.append(
                "Frequent memory leaks detected - likely missing cleanup in fixtures"
            )

        # Connection leak patterns
        if len(resource_data["connection_leaks"]) > 2:
            patterns.append("Connection leaks detected - check HTTP client cleanup")

        # Task failure patterns
        task_failures = resource_data["task_failures"]
        if len(task_failures) > 5:
            patterns.append("High async task failure rate - review task management")

        # Common exception patterns
        exception_types = {}
        for failure in task_failures:
            exc_type = type(failure.exception).__name__
            exception_types[exc_type] = exception_types.get(exc_type, 0) + 1

        for exc_type, count in exception_types.items():
            if count > 3:
                patterns.append(
                    f"Frequent {exc_type} exceptions - investigate root cause"
                )

        return patterns

    def _format_performance_summary(self, summary: dict[str, Any]) -> str:
        """Format performance summary for reporting."""
        if not summary:
            return "No performance metrics collected"

        lines = []
        for metric_name, data in summary.items():
            lines.append(
                f"- **{metric_name}**: avg={data['avg']:.3f}s, max={data['max']:.3f}s, count={data['count']}"
            )

        return "\n".join(lines)

    def _format_resource_summary(self, summary: dict[str, Any]) -> str:
        """Format resource usage summary for reporting."""
        lines = []

        memory_leaks = len(summary.get("memory_leaks", []))
        connection_leaks = len(summary.get("connection_leaks", []))
        file_leaks = len(summary.get("file_leaks", []))
        task_failures = len(summary.get("task_failures", []))

        lines.append(f"- **Memory Leaks**: {memory_leaks}")
        lines.append(f"- **Connection Leaks**: {connection_leaks}")
        lines.append(f"- **File Leaks**: {file_leaks}")
        lines.append(f"- **Task Failures**: {task_failures}")

        patterns = summary.get("common_patterns", [])
        if patterns:
            lines.append("\n**Common Patterns:**")
            for pattern in patterns:
                lines.append(f"- {pattern}")

        return "\n".join(lines)

    def _format_failure_analysis(self, failures: list[TestDiagnosticReport]) -> str:
        """Format failure analysis for reporting."""
        if not failures:
            return "No test failures to analyze"

        lines = []

        # Group by failure type
        by_type = {}
        for failure in failures:
            failure_type = failure.failure_type
            if failure_type not in by_type:
                by_type[failure_type] = []
            by_type[failure_type].append(failure)

        for failure_type, reports in by_type.items():
            lines.append(f"\n### {failure_type} ({len(reports)} tests)")

            for report in reports[:3]:  # Show first 3 of each type
                lines.append(f"- **{report.test_name}**: {report.primary_error}")
                if report.recommendations:
                    lines.append(f"  - Recommendation: {report.recommendations[0]}")

        return "\n".join(lines)

    def _format_recommendations(self, recommendations: list[str]) -> str:
        """Format recommendations for reporting."""
        if not recommendations:
            return "No specific recommendations"

        lines = []
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec}")

        return "\n".join(lines)

    def _serialize_report(self, report: TestDiagnosticReport) -> dict[str, Any]:
        """Serialize a diagnostic report for JSON output."""
        return {
            "test_name": report.test_name,
            "test_file": report.test_file,
            "test_duration": report.test_duration,
            "failure_type": report.failure_type,
            "primary_error": str(report.primary_error),
            "task_failures": [
                {
                    "task_name": tf.task_name,
                    "exception": str(tf.exception),
                    "duration": tf.duration,
                    "context": tf.context,
                }
                for tf in report.task_failures
            ],
            "resource_leaks": [
                {
                    "resource_type": rl.resource_type,
                    "leak_size": rl.leak_size,
                    "context": rl.context,
                }
                for rl in report.resource_leaks
            ],
            "service_failures": [
                {
                    "service_name": sf.service_name,
                    "operation": sf.operation,
                    "failure_reason": sf.failure_reason,
                    "recovery_suggestions": sf.recovery_suggestions,
                }
                for sf in report.service_failures
            ],
            "performance_metrics": report.performance_metrics,
            "system_state": report.system_state,
            "recommendations": report.recommendations,
            "timestamp": report.timestamp,
        }

    def _generate_html_template(self, test_suite: str) -> str:
        """Generate HTML template for test report."""
        summary = self._create_test_summary(test_suite)

        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Report: {test_suite}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .metrics {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .metric {{ text-align: center; padding: 10px; background-color: #e9ecef; border-radius: 5px; }}
        .failures {{ margin-top: 20px; }}
        .failure {{ margin: 10px 0; padding: 10px; background-color: #f8d7da; border-radius: 5px; }}
        .recommendations {{ margin-top: 20px; background-color: #d4edda; padding: 20px; border-radius: 5px; }}
        .performance {{ margin-top: 20px; }}
        .performance table {{ width: 100%; border-collapse: collapse; }}
        .performance th, .performance td {{ padding: 8px; border: 1px solid #ddd; text-align: left; }}
        .performance th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Report: {test_suite}</h1>
        <p>Generated on: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(summary.end_time))}</p>
    </div>
    
    <div class="metrics">
        <div class="metric">
            <h3>Total Tests</h3>
            <p>{summary.total_tests}</p>
        </div>
        <div class="metric">
            <h3>Passed</h3>
            <p>{summary.passed_tests}</p>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <p>{summary.failed_tests}</p>
        </div>
        <div class="metric">
            <h3>Duration</h3>
            <p>{summary.total_duration:.2f}s</p>
        </div>
        <div class="metric">
            <h3>Success Rate</h3>
            <p>{(summary.passed_tests / summary.total_tests * 100):.1f}%</p>
        </div>
    </div>
    
    <div class="performance">
        <h2>Performance Summary</h2>
        <table>
            <tr><th>Metric</th><th>Count</th><th>Average</th><th>Max</th><th>P95</th></tr>
            {self._generate_performance_table_rows(summary.performance_summary)}
        </table>
    </div>
    
    <div class="failures">
        <h2>Test Failures</h2>
        {self._generate_failure_html(summary.failure_reports)}
    </div>
    
    <div class="recommendations">
        <h2>Recommendations</h2>
        <ul>
            {self._generate_recommendations_html(summary.recommendations)}
        </ul>
    </div>
</body>
</html>
"""

    def _generate_performance_table_rows(
        self, performance_summary: dict[str, Any]
    ) -> str:
        """Generate HTML table rows for performance metrics."""
        rows = []
        for metric_name, data in performance_summary.items():
            rows.append(f"""
                <tr>
                    <td>{metric_name}</td>
                    <td>{data["count"]}</td>
                    <td>{data["avg"]:.3f}s</td>
                    <td>{data["max"]:.3f}s</td>
                    <td>{data.get("p95", "N/A")}</td>
                </tr>
            """)
        return "".join(rows)

    def _generate_failure_html(self, failures: list[TestDiagnosticReport]) -> str:
        """Generate HTML for test failures."""
        if not failures:
            return "<p>No test failures to report</p>"

        html_parts = []
        for failure in failures:
            html_parts.append(f"""
                <div class="failure">
                    <h3>{failure.test_name}</h3>
                    <p><strong>Error:</strong> {failure.failure_type}: {failure.primary_error}</p>
                    <p><strong>Duration:</strong> {failure.test_duration:.2f}s</p>
                    {self._generate_failure_details_html(failure)}
                </div>
            """)

        return "".join(html_parts)

    def _generate_failure_details_html(self, failure: TestDiagnosticReport) -> str:
        """Generate HTML for failure details."""
        details = []

        if failure.task_failures:
            details.append(
                f"<p><strong>Task Failures:</strong> {len(failure.task_failures)}</p>"
            )

        if failure.resource_leaks:
            details.append(
                f"<p><strong>Resource Leaks:</strong> {len(failure.resource_leaks)}</p>"
            )

        if failure.service_failures:
            details.append(
                f"<p><strong>Service Failures:</strong> {len(failure.service_failures)}</p>"
            )

        if failure.recommendations:
            details.append(
                f"<p><strong>Recommendations:</strong> {failure.recommendations[0]}</p>"
            )

        return "".join(details)

    def _generate_recommendations_html(self, recommendations: list[str]) -> str:
        """Generate HTML for recommendations."""
        return "".join(f"<li>{rec}</li>" for rec in recommendations)
