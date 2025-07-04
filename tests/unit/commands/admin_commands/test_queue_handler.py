"""
Unit tests for QueueHandler.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.commands.admin_commands.queue_handler import QueueHandler


class TestQueueHandler:
    """Test cases for QueueHandler."""

    @pytest.fixture
    def queue_handler(
        self,
        mock_client,
        mock_ip_service,
        mock_storage,
        mock_stop_callback,
        mock_config,
    ):
        """Create a QueueHandler instance for testing."""
        return QueueHandler(
            client=mock_client,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=mock_stop_callback,
            config=mock_config,
        )

    @pytest.fixture
    def mock_message_queue(self):
        """Mock message queue with common methods."""
        with patch(
            "ip_monitor.commands.admin_commands.queue_handler.message_queue"
        ) as mock_queue:
            # Default return values
            mock_queue.get_queue_status.return_value = {
                "queue_size": 5,
                "max_queue_size": 100,
                "is_processing": True,
                "ready_to_process": 3,
                "scheduled_for_later": 2,
                "statistics": {
                    "total_queued": 50,
                    "total_delivered": 45,
                    "total_failed": 3,
                    "total_expired": 1,
                    "total_deduplicated": 1,
                },
                "status_breakdown": {"pending": 3, "processing": 2},
                "priority_breakdown": {"high": 2, "normal": 3},
            }
            mock_queue.clear_queue.return_value = 5
            mock_queue.retry_failed_messages.return_value = 3
            mock_queue.is_processing = True
            mock_queue.start_processing = MagicMock()
            mock_queue.stop_processing = AsyncMock()
            yield mock_queue

    @pytest.mark.asyncio
    async def test_handle_command_no_args(self, queue_handler, mock_message):
        """Test handle_command with no arguments."""
        result = await queue_handler.handle_command(mock_message, [])
        assert result is False

    async def test_handle_command_queue_command(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_command with queue command."""
        mock_message.author.guild_permissions.administrator = True

        result = await queue_handler.handle_command(mock_message, ["queue"])
        assert result is True
        mock_message_queue.get_queue_status.assert_called_once()

    async def test_handle_command_non_queue_command(self, queue_handler, mock_message):
        """Test handle_command with non-queue command."""
        result = await queue_handler.handle_command(mock_message, ["other"])
        assert result is False

    async def test_handle_queue_command_no_permissions(
        self, queue_handler, mock_message
    ):
        """Test queue command without admin permissions."""
        mock_message.author.guild_permissions.administrator = False

        result = await queue_handler._handle_queue_command(mock_message, [])
        assert result is False

    async def test_handle_queue_command_no_args_shows_status(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue command with no args shows status."""
        mock_message.author.guild_permissions.administrator = True

        result = await queue_handler._handle_queue_command(mock_message, [])
        assert result is True
        mock_message_queue.get_queue_status.assert_called_once()

    async def test_handle_queue_command_clear_subcommand(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue clear subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await queue_handler._handle_queue_command(mock_message, ["clear"])
        assert result is True
        mock_message_queue.clear_queue.assert_called_once()

    async def test_handle_queue_command_retry_subcommand(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue retry subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await queue_handler._handle_queue_command(mock_message, ["retry"])
        assert result is True
        mock_message_queue.retry_failed_messages.assert_called_once()

    async def test_handle_queue_command_start_subcommand(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue start subcommand."""
        mock_message.author.guild_permissions.administrator = True
        mock_message_queue.is_processing = False

        result = await queue_handler._handle_queue_command(mock_message, ["start"])
        assert result is True
        mock_message_queue.start_processing.assert_called_once()

    async def test_handle_queue_command_stop_subcommand(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue stop subcommand."""
        mock_message.author.guild_permissions.administrator = True
        mock_message_queue.is_processing = True

        result = await queue_handler._handle_queue_command(mock_message, ["stop"])
        assert result is True
        mock_message_queue.stop_processing.assert_called_once()

    async def test_handle_queue_command_invalid_subcommand(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue command with invalid subcommand shows help."""
        mock_message.author.guild_permissions.administrator = True

        result = await queue_handler._handle_queue_command(mock_message, ["invalid"])
        assert result is True
        # Should send help text

    async def test_handle_queue_command_exception(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test queue command with exception."""
        mock_message.author.guild_permissions.administrator = True
        mock_message_queue.clear_queue.side_effect = Exception("Queue error")

        result = await queue_handler._handle_queue_command(mock_message, ["clear"])
        assert result is False

    async def test_show_queue_status_complete_data(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test show_queue_status with complete data."""
        result = await queue_handler._show_queue_status(mock_message)
        assert result is True
        mock_message_queue.get_queue_status.assert_called_once()

    async def test_show_queue_status_minimal_data(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test show_queue_status with minimal data."""
        mock_message_queue.get_queue_status.return_value = {
            "queue_size": 0,
            "max_queue_size": 100,
            "is_processing": False,
            "ready_to_process": 0,
            "scheduled_for_later": 0,
            "statistics": {
                "total_queued": 0,
                "total_delivered": 0,
                "total_failed": 0,
                "total_expired": 0,
                "total_deduplicated": 0,
            },
            "status_breakdown": {},
            "priority_breakdown": {},
        }

        result = await queue_handler._show_queue_status(mock_message)
        assert result is True

    async def test_handle_queue_clear_success(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_clear with successful clear."""
        mock_message_queue.clear_queue.return_value = 10

        result = await queue_handler._handle_queue_clear(mock_message)
        assert result is True
        mock_message_queue.clear_queue.assert_called_once()

    async def test_handle_queue_clear_no_messages(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_clear with no messages to clear."""
        mock_message_queue.clear_queue.return_value = 0

        result = await queue_handler._handle_queue_clear(mock_message)
        assert result is True
        mock_message_queue.clear_queue.assert_called_once()

    async def test_handle_queue_retry_success(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_retry with successful retry."""
        mock_message_queue.retry_failed_messages.return_value = 5

        result = await queue_handler._handle_queue_retry(mock_message)
        assert result is True
        mock_message_queue.retry_failed_messages.assert_called_once()

    async def test_handle_queue_retry_no_failed_messages(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_retry with no failed messages."""
        mock_message_queue.retry_failed_messages.return_value = 0

        result = await queue_handler._handle_queue_retry(mock_message)
        assert result is True
        mock_message_queue.retry_failed_messages.assert_called_once()

    async def test_handle_queue_start_not_processing(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_start when not processing."""
        mock_message_queue.is_processing = False

        result = await queue_handler._handle_queue_start(mock_message)
        assert result is True
        mock_message_queue.start_processing.assert_called_once()

    async def test_handle_queue_start_already_processing(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_start when already processing."""
        mock_message_queue.is_processing = True

        result = await queue_handler._handle_queue_start(mock_message)
        assert result is True
        mock_message_queue.start_processing.assert_not_called()

    async def test_handle_queue_stop_processing(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_stop when processing."""
        mock_message_queue.is_processing = True

        result = await queue_handler._handle_queue_stop(mock_message)
        assert result is True
        mock_message_queue.stop_processing.assert_called_once()

    async def test_handle_queue_stop_not_processing(
        self, queue_handler, mock_message, mock_message_queue
    ):
        """Test handle_queue_stop when not processing."""
        mock_message_queue.is_processing = False

        result = await queue_handler._handle_queue_stop(mock_message)
        assert result is True
        mock_message_queue.stop_processing.assert_not_called()

    def test_get_queue_help_text(self, queue_handler):
        """Test _get_queue_help_text returns proper help text."""
        help_text = queue_handler._get_queue_help_text()
        assert "Queue Commands:" in help_text
        assert "!queue" in help_text
        assert "!queue clear" in help_text
        assert "!queue retry" in help_text
        assert "!queue start" in help_text
        assert "!queue stop" in help_text

    def test_get_help_text(self, queue_handler):
        """Test get_help_text returns queue help text."""
        help_text = queue_handler.get_help_text()
        assert "Queue Commands:" in help_text
        assert "!queue" in help_text
