"""
Tests for IPMonitorBot scheduled tasks and IP checking.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ip_monitor.bot import IPMonitorBot


class TestScheduledIPCheck:
    """Test suite for scheduled IP checking functionality."""

    async def test_scheduled_task_creation(self, mock_bot_instance):
        """Test that scheduled IP check task can be created."""
        # Execute
        task = mock_bot_instance._create_check_ip_task()

        # Verify
        assert task is not None
        # The task is a discord.ext.tasks.Loop object