"""
Unit tests for ApiHandler.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ip_monitor.commands.admin_commands.api_handler import ApiHandler
from ip_monitor.ip_api_config import IPAPIEndpoint, ResponseFormat


class TestApiHandler:
    """Test cases for ApiHandler."""

    @pytest.fixture
    def api_handler(
        self,
        mock_client,
        mock_ip_service,
        mock_storage,
        mock_stop_callback,
        mock_config,
    ):
        """Create an ApiHandler instance for testing."""
        return ApiHandler(
            client=mock_client,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=mock_stop_callback,
            config=mock_config,
        )

    @pytest.fixture
    def mock_api_endpoint(self):
        """Create a mock API endpoint."""
        api = MagicMock(spec=IPAPIEndpoint)
        api.id = "test_api"
        api.name = "Test API"
        api.url = "https://api.example.com/ip"
        api.enabled = True
        api.priority = 1
        api.response_format = ResponseFormat.JSON
        api.json_field = "ip"
        api.success_count = 10
        api.failure_count = 2
        api.avg_response_time = 0.5
        api.timeout = 10
        api.headers = {}
        api.last_success = datetime.now()
        api.last_failure = datetime.now()
        api.get_success_rate.return_value = 83.3
        api.get_performance_score.return_value = 85.5
        api.record_success = MagicMock()
        api.record_failure = MagicMock()
        return api

    @pytest.fixture
    def mock_api_manager(self):
        """Mock IP API manager."""
        with patch(
            "ip_monitor.commands.admin_commands.api_handler.ip_api_manager"
        ) as mock_manager:
            mock_manager.list_apis.return_value = []
            mock_manager.get_api.return_value = None
            mock_manager.add_api.return_value = True
            mock_manager.remove_api.return_value = True
            mock_manager.enable_api.return_value = True
            mock_manager.disable_api.return_value = True
            mock_manager.set_api_priority.return_value = True
            mock_manager.endpoints = []
            yield mock_manager

    async def test_handle_command_no_args(self, api_handler, mock_message):
        """Test handle_command with no arguments."""
        result = await api_handler.handle_command(mock_message, [])
        assert result is False

    async def test_handle_command_api_command(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test handle_command with api command."""
        mock_message.author.guild_permissions.administrator = True

        result = await api_handler.handle_command(mock_message, ["api"])
        assert result is True

    async def test_handle_command_non_api_command(self, api_handler, mock_message):
        """Test handle_command with non-api command."""
        result = await api_handler.handle_command(mock_message, ["other"])
        assert result is False

    async def test_handle_api_command_no_permissions(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api command without admin permissions."""
        mock_message.author.guild_permissions.administrator = False

        result = await api_handler._handle_api_command(mock_message, [])
        assert result is False

    async def test_handle_api_command_no_args_shows_help(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api command with no args shows help."""
        mock_message.author.guild_permissions.administrator = True

        result = await api_handler._handle_api_command(mock_message, [])
        assert result is True

    async def test_handle_api_command_list_subcommand(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api list subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await api_handler._handle_api_command(mock_message, ["list"])
        assert result is True
        mock_api_manager.list_apis.assert_called_once()

    async def test_handle_api_command_add_subcommand(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api add subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await api_handler._handle_api_command(
            mock_message, ["add", "TestAPI", "https://api.test.com"]
        )
        assert result is True

    async def test_handle_api_command_invalid_subcommand(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api command with invalid subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await api_handler._handle_api_command(mock_message, ["invalid"])
        assert result is False

    async def test_handle_api_command_exception(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api command with exception."""
        mock_message.author.guild_permissions.administrator = True
        mock_api_manager.list_apis.side_effect = Exception("API error")

        result = await api_handler._handle_api_command(mock_message, ["list"])
        assert result is False

    async def test_handle_api_list_no_apis(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api list with no APIs configured."""
        mock_api_manager.list_apis.return_value = []

        result = await api_handler._handle_api_list(mock_message)
        assert result is True

    async def test_handle_api_list_with_apis(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test api list with APIs configured."""
        mock_api_manager.list_apis.return_value = [mock_api_endpoint]

        result = await api_handler._handle_api_list(mock_message)
        assert result is True

    async def test_handle_api_add_insufficient_args(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api add with insufficient arguments."""
        result = await api_handler._handle_api_add(mock_message, ["add", "name"])
        assert result is True

    async def test_handle_api_add_success(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test successful api add."""
        mock_api_manager.get_api.return_value = None  # API doesn't exist
        mock_api_manager.add_api.return_value = True

        result = await api_handler._handle_api_add(
            mock_message, ["add", "TestAPI", "https://api.test.com"]
        )
        assert result is True
        mock_api_manager.add_api.assert_called_once()

    async def test_handle_api_add_with_format_and_field(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api add with format and field."""
        mock_api_manager.get_api.return_value = None
        mock_api_manager.add_api.return_value = True

        result = await api_handler._handle_api_add(
            mock_message, ["add", "TestAPI", "https://api.test.com", "json", "ip"]
        )
        assert result is True

    async def test_handle_api_add_invalid_format(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api add with invalid format."""
        result = await api_handler._handle_api_add(
            mock_message, ["add", "TestAPI", "https://api.test.com", "invalid"]
        )
        assert result is True

    async def test_handle_api_add_already_exists(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test api add when API already exists."""
        mock_api_manager.get_api.return_value = mock_api_endpoint

        result = await api_handler._handle_api_add(
            mock_message, ["add", "TestAPI", "https://api.test.com"]
        )
        assert result is True

    async def test_handle_api_add_exception(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api add with exception."""
        mock_api_manager.get_api.return_value = None
        mock_api_manager.add_api.side_effect = Exception("Add error")

        result = await api_handler._handle_api_add(
            mock_message, ["add", "TestAPI", "https://api.test.com"]
        )
        assert result is False

    async def test_handle_api_remove_insufficient_args(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api remove with insufficient arguments."""
        result = await api_handler._handle_api_remove(mock_message, ["remove"])
        assert result is True

    async def test_handle_api_remove_success(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test successful api remove."""
        mock_api_manager.get_api.return_value = mock_api_endpoint
        mock_api_manager.remove_api.return_value = True

        result = await api_handler._handle_api_remove(
            mock_message, ["remove", "test_api"]
        )
        assert result is True
        mock_api_manager.remove_api.assert_called_once_with("test_api")

    async def test_handle_api_remove_not_found(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api remove when API not found."""
        mock_api_manager.get_api.return_value = None

        result = await api_handler._handle_api_remove(
            mock_message, ["remove", "nonexistent"]
        )
        assert result is True

    async def test_handle_api_enable_success(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test successful api enable."""
        mock_api_manager.get_api.return_value = mock_api_endpoint
        mock_api_manager.enable_api.return_value = True

        result = await api_handler._handle_api_enable(
            mock_message, ["enable", "test_api"]
        )
        assert result is True
        mock_api_manager.enable_api.assert_called_once_with("test_api")

    async def test_handle_api_disable_success(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test successful api disable."""
        mock_api_manager.get_api.return_value = mock_api_endpoint
        mock_api_manager.disable_api.return_value = True

        result = await api_handler._handle_api_disable(
            mock_message, ["disable", "test_api"]
        )
        assert result is True
        mock_api_manager.disable_api.assert_called_once_with("test_api")

    async def test_handle_api_test_insufficient_args(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api test with insufficient arguments."""
        result = await api_handler._handle_api_test(mock_message, ["test"])
        assert result is True

    async def test_handle_api_test_success(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test successful api test."""
        mock_api_manager.get_api.return_value = mock_api_endpoint

        with patch.object(api_handler, "_test_single_api") as mock_test:
            mock_test.return_value = {
                "success": True,
                "ip": "192.168.1.1",
                "response_time": 0.5,
                "error": None,
            }

            result = await api_handler._handle_api_test(
                mock_message, ["test", "test_api"]
            )
            assert result is True
            mock_test.assert_called_once_with(mock_api_endpoint)

    async def test_handle_api_test_failure(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test api test with failure."""
        mock_api_manager.get_api.return_value = mock_api_endpoint

        with patch.object(api_handler, "_test_single_api") as mock_test:
            mock_test.return_value = {
                "success": False,
                "ip": None,
                "response_time": 0.5,
                "error": "Connection timeout",
            }

            result = await api_handler._handle_api_test(
                mock_message, ["test", "test_api"]
            )
            assert result is True

    async def test_handle_api_priority_insufficient_args(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api priority with insufficient arguments."""
        result = await api_handler._handle_api_priority(
            mock_message, ["priority", "test_api"]
        )
        assert result is True

    async def test_handle_api_priority_invalid_number(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api priority with invalid number."""
        result = await api_handler._handle_api_priority(
            mock_message, ["priority", "test_api", "invalid"]
        )
        assert result is True

    async def test_handle_api_priority_success(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test successful api priority."""
        mock_api_manager.get_api.return_value = mock_api_endpoint
        mock_api_manager.set_api_priority.return_value = True

        result = await api_handler._handle_api_priority(
            mock_message, ["priority", "test_api", "5"]
        )
        assert result is True
        mock_api_manager.set_api_priority.assert_called_once_with("test_api", 5)

    async def test_handle_api_stats_no_stats(
        self, api_handler, mock_message, mock_api_manager
    ):
        """Test api stats with no statistics."""
        mock_api_manager.list_apis.return_value = []

        result = await api_handler._handle_api_stats(mock_message)
        assert result is True

    async def test_handle_api_stats_with_stats(
        self, api_handler, mock_message, mock_api_manager, mock_api_endpoint
    ):
        """Test api stats with statistics."""
        mock_api_manager.list_apis.return_value = [mock_api_endpoint]

        result = await api_handler._handle_api_stats(mock_message)
        assert result is True

    async def test_test_single_api_json_success(self, api_handler, mock_api_endpoint):
        """Test _test_single_api with JSON response success."""
        mock_api_endpoint.response_format = ResponseFormat.JSON
        mock_api_endpoint.json_field = "ip"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"ip": "192.168.1.1"}
            mock_response.headers = {"content-type": "application/json"}
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await api_handler._test_single_api(mock_api_endpoint)
            assert result["success"] is True
            assert result["ip"] == "192.168.1.1"

    async def test_test_single_api_text_success(self, api_handler, mock_api_endpoint):
        """Test _test_single_api with text response success."""
        mock_api_endpoint.response_format = ResponseFormat.PLAIN_TEXT

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.text = "192.168.1.1"
            mock_response.headers = {"content-type": "text/plain"}
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await api_handler._test_single_api(mock_api_endpoint)
            assert result["success"] is True
            assert result["ip"] == "192.168.1.1"

    async def test_test_single_api_auto_detect_json(
        self, api_handler, mock_api_endpoint
    ):
        """Test _test_single_api with auto-detect JSON response."""
        mock_api_endpoint.response_format = ResponseFormat.AUTO
        mock_api_endpoint.json_field = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"ip": "192.168.1.1"}
            mock_response.headers = {"content-type": "application/json"}
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await api_handler._test_single_api(mock_api_endpoint)
            assert result["success"] is True
            assert result["ip"] == "192.168.1.1"

    async def test_test_single_api_no_ip_found(self, api_handler, mock_api_endpoint):
        """Test _test_single_api with no IP found."""
        mock_api_endpoint.response_format = ResponseFormat.JSON
        mock_api_endpoint.json_field = "ip"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "ok"}
            mock_response.headers = {"content-type": "application/json"}
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await api_handler._test_single_api(mock_api_endpoint)
            assert result["success"] is False
            assert "No IP address found" in result["error"]

    async def test_test_single_api_exception(self, api_handler, mock_api_endpoint):
        """Test _test_single_api with exception."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                Exception("Connection error")
            )

            result = await api_handler._test_single_api(mock_api_endpoint)
            assert result["success"] is False
            assert "Connection error" in result["error"]
            mock_api_endpoint.record_failure.assert_called_once()

    def test_get_api_help_text(self, api_handler):
        """Test _get_api_help_text returns proper help text."""
        help_text = api_handler._get_api_help_text()
        assert "IP API Management Commands:" in help_text
        assert "!api list" in help_text
        assert "!api add" in help_text
        assert "!api remove" in help_text
        assert "!api enable" in help_text
        assert "!api disable" in help_text
        assert "!api test" in help_text
        assert "!api priority" in help_text
        assert "!api stats" in help_text

    def test_get_help_text(self, api_handler):
        """Test get_help_text returns API help text."""
        help_text = api_handler.get_help_text()
        assert "IP API Management Commands:" in help_text
        assert "!api list" in help_text
