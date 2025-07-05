"""
Example usage of enhanced test fixtures for the Discord IP Monitor Bot.

This file demonstrates how to use the comprehensive test fixtures for:
1. Database testing with temporary SQLite databases
2. HTTP API testing with mock servers
3. Discord bot testing with comprehensive mocks

These examples show best practices for writing robust tests.
"""

from unittest.mock import patch

import pytest

from ip_monitor.ip_service import IPService
from ip_monitor.storage import SQLiteIPStorage


class TestDatabaseFixtures:
    """Examples of database testing with temporary SQLite databases."""

    def test_basic_sqlite_storage(self, sqlite_storage):
        """Test basic SQLite storage operations."""
        # Test saving and loading current IP
        test_ip = "203.0.113.1"
        assert sqlite_storage.save_current_ip(test_ip) is True
        assert sqlite_storage.load_last_ip() == test_ip

        # Test IP validation
        assert sqlite_storage.is_valid_ip("192.168.1.1") is True
        assert sqlite_storage.is_valid_ip("invalid") is False

    def test_sqlite_storage_with_history(self, sqlite_storage_with_data):
        """Test SQLite storage with pre-populated history."""
        # Verify current IP
        current_ip = sqlite_storage_with_data.load_last_ip()
        assert current_ip == "192.168.1.3"

        # Verify history
        history = sqlite_storage_with_data.load_ip_history()
        assert len(history) == 3
        assert history[0]["ip"] == "192.168.1.1"
        assert history[1]["ip"] == "192.168.1.2"
        assert history[2]["ip"] == "192.168.1.3"

        # Test adding new IP
        new_ip = "203.0.113.5"
        assert sqlite_storage_with_data.save_current_ip(new_ip) is True
        assert sqlite_storage_with_data.load_last_ip() == new_ip

        # History should now have 4 entries
        updated_history = sqlite_storage_with_data.load_ip_history()
        assert len(updated_history) == 4
        assert updated_history[-1]["ip"] == new_ip

    def test_database_migration(self, temp_db_path):
        """Test database migration functionality."""
        storage = SQLiteIPStorage(temp_db_path, history_size=5)

        # Test migration from non-existent files (should handle gracefully)
        result = storage.migrate_from_json(
            "nonexistent.json", "nonexistent_history.json"
        )
        assert result is False

        # Create temporary JSON files to test migration
        import json
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as ip_file:
            json.dump({"ip": "10.0.0.1", "timestamp": "2023-01-01T00:00:00Z"}, ip_file)
            ip_file_path = ip_file.name

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as history_file:
            json.dump(
                [
                    {"ip": "10.0.0.1", "timestamp": "2023-01-01T00:00:00Z"},
                    {"ip": "10.0.0.2", "timestamp": "2023-01-01T01:00:00Z"},
                ],
                history_file,
            )
            history_file_path = history_file.name

        try:
            # Test migration
            result = storage.migrate_from_json(ip_file_path, history_file_path)
            assert result is True

            # Verify migrated data
            assert storage.load_last_ip() == "10.0.0.1"
            history = storage.load_ip_history()
            assert len(history) == 2
            assert history[0]["ip"] == "10.0.0.1"
            assert history[1]["ip"] == "10.0.0.2"

        finally:
            # Cleanup
            os.unlink(ip_file_path)
            os.unlink(history_file_path)


class TestHTTPMockFixtures:
    """Examples of HTTP API testing with mock servers."""

    @pytest.mark.asyncio
    async def test_mock_server_json_endpoint(self, mock_ip_api_server):
        """Test JSON API endpoint with mock server."""
        import httpx

        json_url = mock_ip_api_server["endpoints"]["json"]

        async with httpx.AsyncClient() as client:
            response = await client.get(json_url)
            assert response.status_code == 200

            data = response.json()
            assert "ip" in data
            assert data["ip"] == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_mock_server_text_endpoint(self, mock_ip_api_server):
        """Test text API endpoint with mock server."""
        import httpx

        text_url = mock_ip_api_server["endpoints"]["text"]

        async with httpx.AsyncClient() as client:
            response = await client.get(text_url)
            assert response.status_code == 200
            assert response.text == "203.0.113.1"

    @pytest.mark.asyncio
    async def test_mock_server_error_handling(self, mock_ip_api_server):
        """Test error handling with mock server."""
        import httpx

        error_url = mock_ip_api_server["endpoints"]["error"]

        async with httpx.AsyncClient() as client:
            response = await client.get(error_url)
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_mock_server_timeout_simulation(self, mock_ip_api_server):
        """Test timeout simulation with mock server."""
        import httpx

        slow_url = mock_ip_api_server["endpoints"]["slow"]

        async with httpx.AsyncClient(timeout=1.0) as client:
            with pytest.raises(httpx.TimeoutException):
                await client.get(slow_url)

    def test_configurable_mock_responses(self, mock_httpx_responses):
        """Test configurable mock HTTP responses."""
        # Test successful response
        success_response = mock_httpx_responses(
            status_code=200, text="192.168.1.1", json_data={"ip": "192.168.1.1"}
        )

        assert success_response.status_code == 200
        assert success_response.text == "192.168.1.1"
        assert success_response.json()["ip"] == "192.168.1.1"

        # Test error response
        error_response = mock_httpx_responses(status_code=404, text="Not Found")
        assert error_response.status_code == 404
        assert error_response.text == "Not Found"

        # Test raise_for_status
        with pytest.raises(Exception):
            error_response.raise_for_status()


class TestDiscordBotFixtures:
    """Examples of Discord bot testing with comprehensive mocks."""

    def test_discord_client_basic_properties(self, mock_discord_client):
        """Test basic Discord client properties."""
        # Test user information
        assert mock_discord_client.user.id == 123456789
        assert mock_discord_client.user.name == "TestBot"
        assert mock_discord_client.user.discriminator == "0001"
        assert mock_discord_client.user.mention == "<@123456789>"

        # Test connection status
        assert mock_discord_client.is_ready() is True
        assert mock_discord_client.is_closed() is False
        assert mock_discord_client.latency == 0.1

    def test_discord_client_guild_and_channel(self, mock_discord_client):
        """Test Discord client guild and channel mocking."""
        # Test guild
        guild = mock_discord_client.get_guild(987654321)
        assert guild.id == 987654321
        assert guild.name == "Test Guild"
        assert guild.member_count == 100

        # Test channel
        channel = mock_discord_client.get_channel(12345)
        assert channel.id == 12345
        assert channel.name == "test-channel"
        assert channel.guild == guild

    @pytest.mark.asyncio
    async def test_discord_client_message_sending(self, mock_discord_client):
        """Test Discord client message sending."""
        channel = mock_discord_client.get_channel(12345)

        # Test sending a message
        await channel.send("Test message")
        channel.send.assert_called_once_with("Test message")

        # Test typing indicator
        await channel.typing()
        channel.typing.assert_called_once()

    def test_discord_interaction_slash_commands(self, mock_discord_interaction):
        """Test Discord interaction for slash commands."""
        # Test user permissions
        assert mock_discord_interaction.user.guild_permissions.administrator is True

        # Test guild and channel info
        assert mock_discord_interaction.guild_id == 987654321
        assert mock_discord_interaction.channel_id == 12345

        # Test command info
        assert mock_discord_interaction.command.name == "test"
        assert mock_discord_interaction.data["name"] == "test"

    @pytest.mark.asyncio
    async def test_discord_interaction_responses(self, mock_discord_interaction):
        """Test Discord interaction response methods."""
        # Test initial response
        await mock_discord_interaction.response.send_message("Test response")
        mock_discord_interaction.response.send_message.assert_called_once_with(
            "Test response"
        )

        # Test follow-up response
        await mock_discord_interaction.followup.send("Follow-up message")
        mock_discord_interaction.followup.send.assert_called_once_with(
            "Follow-up message"
        )

        # Test defer response
        await mock_discord_interaction.response.defer()
        mock_discord_interaction.response.defer.assert_called_once()

    def test_discord_message_permissions(
        self, mock_admin_message, mock_non_admin_message
    ):
        """Test Discord message permission checking."""
        # Test admin message
        assert mock_admin_message.author.guild_permissions.administrator is True
        assert mock_admin_message.author.name == "AdminUser"

        # Test non-admin message
        assert mock_non_admin_message.author.guild_permissions.administrator is False
        assert mock_non_admin_message.author.name == "RegularUser"

    @pytest.mark.asyncio
    async def test_discord_message_sending(self, mock_admin_message):
        """Test Discord message sending."""
        await mock_admin_message.channel.send("Admin command response")
        mock_admin_message.channel.send.assert_called_once_with(
            "Admin command response"
        )


class TestIntegratedFixtures:
    """Examples of using multiple fixtures together for integration testing."""

    @pytest.mark.asyncio
    async def test_ip_service_with_mock_server_and_database(
        self, mock_ip_api_server, sqlite_storage, mock_config
    ):
        """Test IP service with mock server and database integration."""
        # Create IP service with mock server endpoints
        json_url = mock_ip_api_server["endpoints"]["json"]
        text_url = mock_ip_api_server["endpoints"]["text"]

        # Mock the IP service to use our test endpoints
        with patch(
            "ip_monitor.ip_service.IPService.DEFAULT_IP_APIS", [json_url, text_url]
        ):
            ip_service = IPService(
                max_retries=1,
                retry_delay=0,
                use_concurrent_checks=False,
                circuit_breaker_enabled=False,
            )

            # Test IP retrieval
            ip = await ip_service.get_current_ip()
            assert ip == "203.0.113.1"

            # Test saving to database
            success = sqlite_storage.save_current_ip(ip)
            assert success is True

            # Verify database storage
            stored_ip = sqlite_storage.load_last_ip()
            assert stored_ip == ip

    @pytest.mark.asyncio
    async def test_admin_command_with_database_and_discord(
        self, mock_admin_message, sqlite_storage_with_data, mock_config
    ):
        """Test admin command with database and Discord integration."""
        # Simulate an admin command that queries IP history
        history = sqlite_storage_with_data.load_ip_history()

        # Format history for Discord response
        if history:
            history_text = "IP History:\\n"
            for i, record in enumerate(history[-3:], 1):  # Last 3 records
                history_text += f"{i}. {record['ip']} ({record['timestamp']})\\n"
        else:
            history_text = "No IP history found."

        # Send response
        await mock_admin_message.channel.send(history_text)

        # Verify the response was sent
        mock_admin_message.channel.send.assert_called_once_with(history_text)

        # Verify response contains expected data
        call_args = mock_admin_message.channel.send.call_args[0][0]
        assert "192.168.1.1" in call_args
        assert "192.168.1.2" in call_args
        assert "192.168.1.3" in call_args

    def test_configuration_with_multiple_fixtures(
        self, mock_config, sqlite_storage, mock_discord_client
    ):
        """Test configuration management with multiple fixtures."""
        # Test configuration values
        assert mock_config.check_interval == 300
        assert mock_config.max_retries == 3
        assert mock_config.channel_id == 12345

        # Test that database respects configuration
        assert sqlite_storage.history_size == 10

        # Test that Discord client can use configuration
        channel = mock_discord_client.get_channel(mock_config.channel_id)
        assert channel.id == mock_config.channel_id

        # Test updating configuration
        mock_config.check_interval = 600
        assert mock_config.check_interval == 600
