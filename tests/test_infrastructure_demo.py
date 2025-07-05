"""Demonstration of the new test infrastructure utilities.

This test file shows how to use the new performance testing utilities,
test data generators, and database cleanup functionality.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from tests.utils import (  # Test data generators; Performance testing; Database cleanup
    APIResponseGenerator,
    DatabaseTestManager,
    DiscordDataGenerator,
    IPAddressGenerator,
    IPHistoryGenerator,
    PerformanceBenchmark,
    PerformanceTestSuite,
    PerformanceTimer,
    TestScenarioGenerator,
    benchmark_ip_api_performance,
    default_fixture_manager,
    isolated_database_test,
    performance_test_database,
)


class TestPerformanceUtilities:
    """Test the performance testing utilities."""

    def test_performance_timer_sync(self):
        """Test synchronous performance timer."""

        with PerformanceTimer("test_operation") as timer:
            # Simulate some work
            sum(range(1000))

        assert timer.duration > 0
        assert timer.duration < 1.0  # Should be very fast

    async def test_performance_timer_async(self):
        """Test asynchronous performance timer."""

        timer = PerformanceTimer("async_test_operation")

        async with timer.async_timer():
            # Simulate async work
            await asyncio.sleep(0.01)

        assert timer.duration > 0.01
        assert timer.duration < 0.1

    async def test_performance_benchmark_async(self):
        """Test async performance benchmarking."""

        benchmark = PerformanceBenchmark("async_operation_test")

        async def test_operation():
            await asyncio.sleep(0.001)  # 1ms operation
            return "success"

        metrics = await benchmark.benchmark_async_operation(
            test_operation, iterations=10, concurrent_operations=2
        )

        assert metrics.total_operations == 10
        assert metrics.successful_operations == 10
        assert metrics.failed_operations == 0
        assert metrics.success_rate == 1.0
        assert metrics.average_duration > 0.001
        assert metrics.operations_per_second > 0

    def test_performance_benchmark_sync(self):
        """Test synchronous performance benchmarking."""

        benchmark = PerformanceBenchmark("sync_operation_test")

        def test_operation():
            return sum(range(100))

        metrics = benchmark.benchmark_sync_operation(test_operation, iterations=50)

        assert metrics.total_operations == 50
        assert metrics.successful_operations == 50
        assert metrics.success_rate == 1.0
        assert metrics.operations_per_second > 0

    async def test_ip_api_performance_benchmark(self):
        """Test IP API performance benchmarking."""

        # Create mock IP service
        mock_ip_service = Mock()
        mock_ip_service.get_current_ip = AsyncMock(return_value="192.168.1.1")

        metrics = await benchmark_ip_api_performance(
            mock_ip_service, iterations=20, concurrent_requests=3
        )

        assert metrics.total_operations == 20
        assert metrics.successful_operations == 20
        assert mock_ip_service.get_current_ip.call_count == 20


class TestDataGenerators:
    """Test the test data generators."""

    def test_ip_address_generator(self):
        """Test IP address generation."""

        # Test public IP generation
        public_ip = IPAddressGenerator.generate_public_ip()
        assert self._is_valid_ip(public_ip)
        assert not self._is_private_ip(public_ip)

        # Test private IP generation
        private_ip = IPAddressGenerator.generate_private_ip()
        assert self._is_valid_ip(private_ip)
        assert self._is_private_ip(private_ip)

        # Test IP list generation
        ip_list = IPAddressGenerator.generate_ip_list(5)
        assert len(ip_list) == 5
        assert all(self._is_valid_ip(ip) for ip in ip_list)

    def test_ip_history_generator(self):
        """Test IP history generation."""

        # Test normal history
        history = IPHistoryGenerator.generate_ip_history(count=5)
        assert len(history) == 5

        # Check that all records have required fields
        for record in history:
            assert hasattr(record, "ip")
            assert hasattr(record, "timestamp")
            assert hasattr(record, "created_at")
            assert self._is_valid_ip(record.ip)

        # Test frequent changes
        frequent_history = IPHistoryGenerator.generate_frequent_changes(count=10)
        assert len(frequent_history) == 10

        # Test stable history
        stable_history = IPHistoryGenerator.generate_stable_history(count=5)
        assert len(stable_history) == 5

    def test_discord_data_generator(self):
        """Test Discord data generation."""

        # Test user ID generation
        user_id = DiscordDataGenerator.generate_user_id()
        assert isinstance(user_id, int)
        assert user_id > 100000000000000000  # Valid Discord ID range

        # Test mock message generation
        message = DiscordDataGenerator.generate_mock_message(
            content="!test command", is_admin=True
        )

        assert message.content == "!test command"
        assert message.author.guild_permissions.administrator is True
        assert hasattr(message.channel, "send")

        # Test mock interaction generation
        interaction = DiscordDataGenerator.generate_mock_interaction(
            command_name="test_command", is_admin=False
        )

        assert interaction.command.name == "test_command"
        assert interaction.user.guild_permissions.administrator is False
        assert hasattr(interaction.response, "send_message")

    def test_api_response_generator(self):
        """Test API response generation."""

        # Test JSON response
        json_response = APIResponseGenerator.generate_json_response(
            ip="1.2.3.4", field="ip_address"
        )

        assert json_response["ip_address"] == "1.2.3.4"

        # Test text response
        text_response = APIResponseGenerator.generate_text_response(ip="5.6.7.8")
        assert text_response == "5.6.7.8"

        # Test complex JSON response
        complex_response = APIResponseGenerator.generate_complex_json_response()
        assert "ip" in complex_response
        assert "country" in complex_response
        assert "city" in complex_response

    def test_test_scenario_generator(self):
        """Test complete test scenario generation."""

        # Test IP change scenario
        ip_scenario = TestScenarioGenerator.generate_ip_change_scenario(changes=3)

        assert ip_scenario["total_changes"] == 3
        assert len(ip_scenario["ip_changes"]) == 3
        assert "initial_ip" in ip_scenario
        assert "final_ip" in ip_scenario
        assert "timeline" in ip_scenario

        # Test performance scenario
        perf_scenario = TestScenarioGenerator.generate_performance_test_scenario(
            operations=100, concurrent_users=10
        )

        assert perf_scenario["operations"] == 100
        assert perf_scenario["concurrent_users"] == 10
        assert "test_ips" in perf_scenario
        assert "api_endpoints" in perf_scenario

    def _is_valid_ip(self, ip: str) -> bool:
        """Check if string is a valid IP address."""
        parts = ip.split(".")
        if len(parts) != 4:
            return False

        try:
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
            return True
        except ValueError:
            return False

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is in private range."""
        parts = [int(x) for x in ip.split(".")]

        return (
            parts[0] == 10
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
            or (parts[0] == 192 and parts[1] == 168)
        )


class TestDatabaseCleanup:
    """Test the database cleanup utilities."""

    def test_isolated_database_test(self):
        """Test isolated database testing."""

        with isolated_database_test("test_isolation") as db_path:
            # Database should exist and be empty
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check that tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert "current_ip" in tables
            assert "ip_history" in tables

            # Check that tables are empty
            cursor.execute("SELECT COUNT(*) FROM current_ip")
            assert cursor.fetchone()[0] == 0

            cursor.execute("SELECT COUNT(*) FROM ip_history")
            assert cursor.fetchone()[0] == 0

            conn.close()

        # Database should be cleaned up after context
        import os

        assert not os.path.exists(db_path)

    def test_database_fixture_application(self):
        """Test applying database fixtures."""

        with isolated_database_test("test_fixtures", fixture="single_ip") as db_path:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check that current IP was set
            cursor.execute("SELECT COUNT(*) FROM current_ip")
            assert cursor.fetchone()[0] == 1

            cursor.execute("SELECT ip FROM current_ip")
            ip = cursor.fetchone()[0]
            assert ip  # Should have an IP

            conn.close()

    def test_database_manager_backup_restore(self):
        """Test database backup and restore functionality."""

        manager = DatabaseTestManager()
        db_path = manager.create_temp_database("backup_test")

        try:
            # Seed some initial data
            manager.seed_test_data(current_ip="1.2.3.4")

            # Create backup
            backup = manager.backup_database("backup_test")
            assert backup is not None

            # Modify database
            manager.seed_test_data(current_ip="5.6.7.8")

            # Restore from backup
            success = manager.restore_database()
            assert success

            # Verify restoration
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT ip FROM current_ip")
            restored_ip = cursor.fetchone()[0]
            assert restored_ip == "1.2.3.4"
            conn.close()

        finally:
            manager.cleanup_all()

    def test_performance_database_cleanup(self):
        """Test performance database cleanup."""

        with performance_test_database(
            "perf_cleanup_test", initial_records=50
        ) as db_path:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check initial records
            cursor.execute("SELECT COUNT(*) FROM ip_history")
            initial_count = cursor.fetchone()[0]
            assert initial_count == 50

            # Simulate adding performance test data
            cursor.execute(
                "INSERT INTO ip_history (ip, timestamp) VALUES (?, ?)",
                ("192.168.1.100", "2023-01-01T15:00:00Z"),
            )
            conn.commit()

            # Check increased count
            cursor.execute("SELECT COUNT(*) FROM ip_history")
            increased_count = cursor.fetchone()[0]
            assert increased_count == 51

            conn.close()

        # After context, cleanup should have occurred
        # (Can't verify since database is deleted, but no exceptions should occur)

    def test_fixture_manager(self):
        """Test the fixture manager."""

        fixtures = default_fixture_manager.list_fixtures()
        assert "empty" in fixtures
        assert "single_ip" in fixtures
        assert "ip_history" in fixtures
        assert "large_dataset" in fixtures

        # Test applying fixture
        manager = DatabaseTestManager()
        db_path = manager.create_temp_database("fixture_test")

        try:
            success = default_fixture_manager.apply_fixture(
                "ip_history", db_path, history_count=5
            )
            assert success

            # Verify fixture was applied
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM ip_history")
            count = cursor.fetchone()[0]
            assert count == 5

            conn.close()

        finally:
            manager.cleanup_all()


# Integration test showing how to use all utilities together
class TestIntegratedExample:
    """Example of using all test infrastructure utilities together."""

    async def test_comprehensive_performance_scenario(self):
        """Comprehensive test using all utilities together."""

        # Generate test scenario
        scenario = TestScenarioGenerator.generate_performance_test_scenario(
            operations=20, concurrent_users=5, duration_minutes=1
        )

        # Use performance database
        with performance_test_database(
            "comprehensive_test", initial_records=10
        ) as db_path:
            # Create mock services with generated data
            mock_ip_service = Mock()
            mock_storage = Mock()
            mock_cache = Mock()
            mock_queue = Mock()

            # Configure mocks with generated test data
            test_ips = scenario["test_ips"]
            mock_ip_service.get_current_ip = AsyncMock(
                side_effect=test_ips[:5]  # First 5 IPs for testing
            )

            # Create performance test suite
            suite = PerformanceTestSuite(
                mock_ip_service, mock_storage, mock_cache, mock_queue
            )

            # Run performance benchmark
            benchmark = PerformanceBenchmark("comprehensive_test")

            async def test_operation():
                return await mock_ip_service.get_current_ip()

            metrics = await benchmark.benchmark_async_operation(
                test_operation, iterations=10, concurrent_operations=3
            )

            # Verify results
            assert metrics.total_operations == 10
            assert metrics.successful_operations == 10
            assert metrics.operations_per_second > 0

            # Verify mock was called correctly
            assert mock_ip_service.get_current_ip.call_count == 10

            logging.info(f"Comprehensive performance test completed:\n{metrics}")


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
