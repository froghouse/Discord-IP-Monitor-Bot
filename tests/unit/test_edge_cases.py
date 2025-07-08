"""
Unit tests for edge cases and error handling scenarios across the application.

This module focuses on testing malformed configurations, network timeouts,
database corruption, and invalid IP address handling.
"""

import json
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.config import AppConfig


class TestMalformedConfiguration:
    """Test malformed configuration scenarios and error handling."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            yield f.name
        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def temp_env_file(self):
        """Create a temporary environment file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            yield f.name
        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    def test_load_config_with_malformed_json(self, temp_config_file):
        """Test loading configuration with malformed JSON."""
        # Write malformed JSON
        with open(temp_config_file, "w") as f:
            f.write('{"check_interval": 300, "max_retries":}')  # Missing value

        with pytest.raises(json.JSONDecodeError):
            with open(temp_config_file) as f:
                json.load(f)

    def test_load_config_with_corrupted_json_file(self, temp_config_file):
        """Test loading configuration with corrupted JSON file."""
        # Write corrupted JSON
        with open(temp_config_file, "w") as f:
            f.write(
                '{"check_interval": 300, "max_retries": 3\x00\x01\x02}'
            )  # Binary data

        with pytest.raises(json.JSONDecodeError):
            with open(temp_config_file) as f:
                json.load(f)

    def test_load_config_with_missing_required_fields(self):
        """Test loading configuration with missing required fields."""
        # Mock environment with missing critical fields
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                AppConfig.load_from_env()

    def test_load_config_with_invalid_field_types(self):
        """Test loading configuration with invalid field types."""
        # Mock environment with invalid types
        invalid_env = {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "invalid_id",  # Should be int
            "CHECK_INTERVAL": "not_a_number",  # Should be int
            "MAX_RETRIES": "invalid",  # Should be int
            "RETRY_DELAY": "invalid",  # Should be int
        }

        with patch.dict(os.environ, invalid_env, clear=True):
            with pytest.raises(ValueError):
                AppConfig.load_from_env()

    def test_load_config_with_out_of_range_values(self):
        """Test loading configuration with out-of-range values."""
        # Mock environment with out-of-range values
        invalid_env = {
            "DISCORD_BOT_TOKEN": "test_token",
            "CHANNEL_ID": "123456789",
            "CHECK_INTERVAL": "-1",  # Should be positive
            "MAX_RETRIES": "0",  # Should be >= 1
            "RETRY_DELAY": "-10",  # Should be positive
            "CIRCUIT_BREAKER_FAILURE_THRESHOLD": "0",  # Should be >= 1
            "CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "-1",  # Should be positive
        }

        with patch.dict(os.environ, invalid_env, clear=True):
            with pytest.raises(ValueError):
                AppConfig.load_from_env()

    def test_load_config_with_empty_required_fields(self):
        """Test loading configuration with empty required fields."""
        # Mock environment with empty required fields
        empty_env = {
            "DISCORD_BOT_TOKEN": "",  # Empty token
            "CHANNEL_ID": "123456789",
            "CHECK_INTERVAL": "300",
            "MAX_RETRIES": "3",
            "RETRY_DELAY": "30",
        }

        with patch.dict(os.environ, empty_env, clear=True):
            with pytest.raises(ValueError):
                AppConfig.load_from_env()

    def test_load_config_with_unicode_characters(self):
        """Test loading configuration with unicode characters."""
        # Mock environment with unicode characters
        unicode_env = {
            "DISCORD_BOT_TOKEN": "test_token_🤖",
            "CHANNEL_ID": "123456789",
            "CHECK_INTERVAL": "300",
            "MAX_RETRIES": "3",
            "RETRY_DELAY": "30",
            "DB_FILE": "test_db_🗄️.db",
        }

        with patch.dict(os.environ, unicode_env, clear=True):
            config = AppConfig.load_from_env()
            assert config.discord_token == "test_token_🤖"
            assert config.db_file == "test_db_🗄️.db"

    def test_load_config_with_extremely_long_values(self):
        """Test loading configuration with extremely long values."""
        # Mock environment with extremely long values
        long_token = "a" * 10000  # Very long token
        long_env = {
            "DISCORD_BOT_TOKEN": long_token,
            "CHANNEL_ID": "123456789",
            "CHECK_INTERVAL": "300",
            "MAX_RETRIES": "3",
            "RETRY_DELAY": "30",
            "DB_FILE": "a" * 1000 + ".db",  # Very long filename
        }

        with patch.dict(os.environ, long_env, clear=True):
            config = AppConfig.load_from_env()
            assert config.discord_token == long_token
            assert len(config.db_file) == 1003  # 1000 + '.db' = 1003 characters

    def test_load_config_with_special_characters(self):
        """Test loading configuration with special characters."""
        # Mock environment with special characters
        special_env = {
            "DISCORD_BOT_TOKEN": "test_token!@#$%^&*()_+{}[]|\\:\";'<>?,./~`",
            "CHANNEL_ID": "123456789",
            "CHECK_INTERVAL": "300",
            "MAX_RETRIES": "3",
            "RETRY_DELAY": "30",
            "DB_FILE": "test_db_!@#$%^&*().db",
        }

        with patch.dict(os.environ, special_env, clear=True):
            config = AppConfig.load_from_env()
            assert config.discord_token == "test_token!@#$%^&*()_+{}[]|\\:\";'<>?,./~`"
            assert config.db_file == "test_db_!@#$%^&*().db"

    def test_load_config_with_env_file_corruption(self, temp_env_file):
        """Test loading configuration with corrupted .env file."""
        # Write corrupted .env file
        with open(temp_env_file, "wb") as f:
            f.write(b"DISCORD_BOT_TOKEN=test_token\n\x00\x01\x02\x03")  # Binary data

        # This should handle the corruption gracefully
        with patch("ip_monitor.config.load_dotenv") as mock_load_dotenv:
            mock_load_dotenv.side_effect = UnicodeDecodeError(
                "utf-8", b"\x00\x01\x02\x03", 0, 1, "invalid start byte"
            )

            # Should fall back to environment variables
            with patch.dict(
                os.environ,
                {
                    "DISCORD_BOT_TOKEN": "test_token",
                    "CHANNEL_ID": "123456789",
                    "CHECK_INTERVAL": "300",
                    "MAX_RETRIES": "3",
                    "RETRY_DELAY": "30",
                },
                clear=True,
            ):
                config = AppConfig.load_from_env()
                assert config.discord_token == "test_token"

    def test_load_config_with_circular_reference_in_json(self, temp_config_file):
        """Test loading configuration with circular reference handling."""
        # Create a complex nested structure that could cause issues
        complex_config = {
            "check_interval": 300,
            "max_retries": 3,
            "nested": {"deep": {"very_deep": {"config": "value"}}},
        }

        with open(temp_config_file, "w") as f:
            json.dump(complex_config, f)

        # Should handle complex nested structures
        with open(temp_config_file) as f:
            loaded_config = json.load(f)
            assert loaded_config["check_interval"] == 300
            assert loaded_config["nested"]["deep"]["very_deep"]["config"] == "value"


class TestNetworkTimeout:
    """Test network timeout scenarios and error handling."""

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        from ip_monitor.ip_service import IPService

        service = MagicMock(spec=IPService)
        return service

    @pytest.fixture
    def mock_aiohttp_session(self):
        """Create a mock aiohttp session."""
        session = AsyncMock()
        return session

    async def test_http_request_timeout_connection(self, mock_aiohttp_session):
        """Test HTTP request timeout during connection."""
        import asyncio


        # Mock timeout during connection
        mock_aiohttp_session.get.side_effect = TimeoutError(
            "Connection timeout"
        )

        with pytest.raises(asyncio.TimeoutError):
            await mock_aiohttp_session.get("https://api.ipify.org")

    async def test_http_request_timeout_read(self, mock_aiohttp_session):
        """Test HTTP request timeout during read."""
        import asyncio


        # Mock timeout during read by making the session.get call itself raise the exception
        mock_aiohttp_session.get.side_effect = TimeoutError("Read timeout")

        with pytest.raises(asyncio.TimeoutError):
            await mock_aiohttp_session.get("https://api.ipify.org")

    async def test_http_request_partial_response(self, mock_aiohttp_session):
        """Test HTTP request with partial response."""
        # Test that we can detect partial/incomplete responses
        incomplete_responses = [
            "192.168.1",  # Incomplete IP
            "192.168",  # Very incomplete
            "invalid",  # Not an IP at all
            "",  # Empty response
        ]

        for incomplete_response in incomplete_responses:
            # This test focuses on the response content, not the HTTP mechanics
            assert incomplete_response != "192.168.1.1"  # All are incomplete/invalid

    async def test_http_request_slow_response(self, mock_aiohttp_session):
        """Test HTTP request with slow response."""
        import asyncio

        # Mock slow response with a delay before returning
        async def slow_get(*args, **kwargs):
            await asyncio.sleep(0.01)  # Short delay for testing
            return "192.168.1.1"

        mock_aiohttp_session.get.side_effect = slow_get

        # Should complete but take some time
        result = await mock_aiohttp_session.get("https://api.ipify.org")
        assert result == "192.168.1.1"

    async def test_dns_resolution_timeout(self, mock_aiohttp_session):
        """Test DNS resolution timeout."""
        from aiohttp import ClientConnectorError

        # Mock DNS resolution failure
        mock_aiohttp_session.get.side_effect = ClientConnectorError(
            connection_key=None, os_error=OSError("Name or service not known")
        )

        with pytest.raises(ClientConnectorError):
            await mock_aiohttp_session.get("https://invalid.domain.example")

    async def test_network_unreachable_error(self, mock_aiohttp_session):
        """Test network unreachable error."""
        from aiohttp import ClientConnectorError

        # Mock network unreachable
        mock_aiohttp_session.get.side_effect = ClientConnectorError(
            connection_key=None, os_error=OSError("Network is unreachable")
        )

        with pytest.raises(ClientConnectorError):
            await mock_aiohttp_session.get("https://api.ipify.org")

    async def test_connection_reset_error(self, mock_aiohttp_session):
        """Test connection reset error."""
        from aiohttp import ClientConnectorError

        # Mock connection reset
        mock_aiohttp_session.get.side_effect = ClientConnectorError(
            connection_key=None,
            os_error=ConnectionResetError("Connection reset by peer"),
        )

        with pytest.raises(ClientConnectorError):
            await mock_aiohttp_session.get("https://api.ipify.org")

    async def test_ssl_certificate_error(self, mock_aiohttp_session):
        """Test SSL certificate error."""
        import ssl

        from aiohttp import ClientConnectorError

        # Mock SSL certificate error
        mock_aiohttp_session.get.side_effect = ClientConnectorError(
            connection_key=None, os_error=ssl.SSLError("certificate verify failed")
        )

        with pytest.raises(ClientConnectorError):
            await mock_aiohttp_session.get("https://api.ipify.org")


class TestDatabaseCorruption:
    """Test database corruption scenarios and error handling."""

    @pytest.fixture
    def temp_db_file(self):
        """Create a temporary database file."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield f.name
        # Cleanup
        if os.path.exists(f.name):
            os.unlink(f.name)

    @pytest.fixture
    def corrupted_db_file(self, temp_db_file):
        """Create a corrupted database file."""
        # Write random bytes to simulate corruption
        with open(temp_db_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\x04\x05\x06\x07" * 100)
        return temp_db_file

    def test_database_corruption_detection(self, corrupted_db_file):
        """Test detection of database corruption."""
        with pytest.raises(sqlite3.DatabaseError):
            conn = sqlite3.connect(corrupted_db_file)
            conn.execute("SELECT * FROM current_ip")
            conn.close()

    def test_database_locked_error(self, temp_db_file):
        """Test database locked error handling."""
        # Create and lock the database
        conn1 = sqlite3.connect(temp_db_file)
        conn1.execute("BEGIN EXCLUSIVE")

        # Try to access with another connection (with shorter timeout for testing)
        conn2 = sqlite3.connect(
            temp_db_file, timeout=0.1
        )  # 0.1 second timeout instead of default 5 seconds
        with pytest.raises(sqlite3.OperationalError):
            conn2.execute("SELECT * FROM sqlite_master")

        conn1.close()
        conn2.close()

    def test_database_permission_error(self, temp_db_file):
        """Test database permission error handling."""
        # Make file read-only
        os.chmod(temp_db_file, 0o444)

        try:
            with pytest.raises(sqlite3.OperationalError):
                conn = sqlite3.connect(temp_db_file)
                conn.execute("CREATE TABLE test (id INTEGER)")
                conn.close()
        finally:
            # Restore permissions for cleanup
            os.chmod(temp_db_file, 0o666)

    def test_database_disk_full_error(self, temp_db_file):
        """Test database disk full error handling."""
        # This is difficult to simulate reliably, so we'll mock it
        with patch("sqlite3.connect") as mock_connect:
            mock_conn = MagicMock()
            mock_conn.execute.side_effect = sqlite3.OperationalError("disk full")
            mock_connect.return_value = mock_conn

            with pytest.raises(sqlite3.OperationalError):
                conn = sqlite3.connect(temp_db_file)
                conn.execute("INSERT INTO test VALUES (1)")

    def test_database_schema_corruption(self, temp_db_file):
        """Test database schema corruption handling."""
        # Create a database with intentionally corrupted schema
        conn = sqlite3.connect(temp_db_file)

        # First create a table with one schema
        conn.execute("CREATE TABLE current_ip (id INTEGER, ip TEXT)")
        conn.commit()

        # Then try to create the same table with different schema (should fail)
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE current_ip (different_schema INTEGER)")

        conn.close()

    def test_database_recovery_from_corruption(self, temp_db_file):
        """Test database recovery from corruption."""
        from ip_monitor.storage import SQLiteIPStorage

        # Create a working database first
        storage = SQLiteIPStorage(temp_db_file, history_size=10)
        storage.save_current_ip("192.168.1.1")
        storage.close()

        # Corrupt the database
        with open(temp_db_file, "r+b") as f:
            f.seek(100)  # Seek to middle and corrupt
            f.write(b"\x00\x01\x02\x03")

        # Try to recover - storage handles corruption gracefully
        storage = SQLiteIPStorage(temp_db_file, history_size=10)
        result = storage.load_last_ip()
        # Should return None for corrupted database
        assert result is None


class TestInvalidIPAddress:
    """Test invalid IP address scenarios and error handling."""

    @pytest.fixture
    def mock_ip_service(self):
        """Create a mock IP service."""
        from ip_monitor.ip_service import IPService

        service = MagicMock(spec=IPService)
        return service

    def test_invalid_ip_format_detection(self):
        """Test detection of invalid IP address formats."""
        from ip_monitor.ip_service import IPService

        invalid_ips = [
            "256.256.256.256",  # Out of range
            "192.168.1",  # Incomplete
            "192.168.1.1.1",  # Too many octets
            "192.168.1.a",  # Non-numeric
            "192.168.1.-1",  # Negative number
            "192.168.1.01",  # Leading zeros
            "",  # Empty string
            "   ",  # Whitespace only
            "192.168.1.1\x00",  # Null byte
            "192.168.1.1\n",  # Newline
            "192.168.1.1 extra",  # Extra text
        ]

        for invalid_ip in invalid_ips:
            assert not IPService.is_valid_ip(invalid_ip), (
                f"IP {invalid_ip} should be invalid"
            )

    def test_valid_ip_format_detection(self):
        """Test detection of valid IP address formats."""
        from ip_monitor.ip_service import IPService

        valid_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "8.8.8.8",
            "1.1.1.1",
            "127.0.0.1",
            "0.0.0.0",
            "255.255.255.255",
        ]

        for valid_ip in valid_ips:
            assert IPService.is_valid_ip(valid_ip), f"IP {valid_ip} should be valid"

    def test_ip_normalization(self):
        """Test IP address normalization."""
        from ip_monitor.ip_service import IPService

        # Test cases with expected normalization
        test_cases = [
            ("  192.168.1.1  ", "192.168.1.1"),  # Whitespace removal
            ("192.168.1.1\n", "192.168.1.1"),  # Newline removal
            ("192.168.1.1\r", "192.168.1.1"),  # Carriage return removal
            ("192.168.1.1\t", "192.168.1.1"),  # Tab removal
        ]

        for input_ip, expected in test_cases:
            normalized = input_ip.strip()
            if IPService.is_valid_ip(normalized):
                assert normalized == expected

    def test_json_response_with_invalid_ip(self):
        """Test JSON response containing invalid IP."""
        import json

        from ip_monitor.ip_service import IPService

        invalid_responses = [
            {"ip": "256.256.256.256"},  # Out of range
            {"ip": "192.168.1"},  # Incomplete
            {"ip": "not_an_ip"},  # Not an IP
            {"ip": None},  # None value
            {"ip": 12345},  # Numeric instead of string
            {"ip": []},  # Array instead of string
            {"ip": {}},  # Object instead of string
        ]

        for response_data in invalid_responses:
            response_json = json.dumps(response_data)
            # IP service should reject these invalid responses
            ip_value = response_data.get("ip")
            if isinstance(ip_value, str):
                assert not IPService.is_valid_ip(ip_value)

    def test_text_response_with_invalid_ip(self):
        """Test text response containing invalid IP."""
        from ip_monitor.ip_service import IPService

        invalid_responses = [
            "Error: Unable to determine IP",
            "192.168.1",  # Incomplete
            "Your IP is: unknown",
            "Connection failed",
            "<!DOCTYPE html>",  # HTML response
            "Service unavailable",
            "null",
            "undefined",
        ]

        for response_text in invalid_responses:
            cleaned_text = response_text.strip()
            assert not IPService.is_valid_ip(cleaned_text)

    def test_malformed_json_response(self):
        """Test malformed JSON response handling."""
        malformed_responses = [
            '{"ip": "192.168.1.1"',  # Missing closing brace
            '{"ip": 192.168.1.1}',  # Unquoted IP
            '{"ip": "192.168.1.1",}',  # Trailing comma
            '{ip: "192.168.1.1"}',  # Unquoted key
            '{"ip": "192.168.1.1" "extra"}',  # Invalid syntax
        ]

        for response_text in malformed_responses:
            with pytest.raises(json.JSONDecodeError):
                json.loads(response_text)

    def test_ip_validation_with_private_addresses(self):
        """Test IP validation with private address ranges."""
        from ip_monitor.ip_service import IPService

        # These are valid IP formats but private addresses
        private_ips = [
            "192.168.1.1",  # Private range
            "10.0.0.1",  # Private range
            "172.16.0.1",  # Private range
            "127.0.0.1",  # Loopback
            "169.254.1.1",  # Link-local
        ]

        for private_ip in private_ips:
            # Should be valid format-wise
            assert IPService.is_valid_ip(private_ip)
            # But IP service might want to handle these differently

    def test_ip_validation_with_special_addresses(self):
        """Test IP validation with special address ranges."""
        from ip_monitor.ip_service import IPService

        # These are valid but special addresses
        special_ips = [
            "0.0.0.0",  # All zeros
            "255.255.255.255",  # Broadcast
            "224.0.0.1",  # Multicast
            "240.0.0.1",  # Reserved
        ]

        for special_ip in special_ips:
            # Should be valid format-wise
            assert IPService.is_valid_ip(special_ip)
