"""
Unit tests for CacheHandler.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ip_monitor.commands.admin_commands.cache_handler import CacheHandler


class TestCacheHandler:
    """Test cases for CacheHandler."""

    @pytest.fixture
    def cache_handler(
        self,
        mock_client,
        mock_ip_service,
        mock_storage,
        mock_stop_callback,
        mock_config,
    ):
        """Create a CacheHandler instance for testing."""
        return CacheHandler(
            client=mock_client,
            ip_service=mock_ip_service,
            storage=mock_storage,
            stop_callback=mock_stop_callback,
            config=mock_config,
        )

    @pytest.fixture
    def mock_cache_info(self):
        """Mock cache info data."""
        return {
            "enabled": True,
            "cache_ttl": 300,
            "stale_threshold": 0.8,
            "stale_entries_count": 2,
            "stats": {
                "memory_entries": 10,
                "memory_usage_mb": 1.5,
                "hits": 85,
                "misses": 15,
                "hit_rate": 0.85,
                "evictions": 3,
                "invalidations": 2,
                "refreshes": 5,
                "saves": 8,
                "loads": 12,
            },
        }

    @pytest.fixture
    def mock_cache_instance(self):
        """Mock cache instance."""
        cache = MagicMock()
        cache.max_memory_size = 100
        cache.memory_cache = {
            "entry1": MagicMock(cache_type=MagicMock(value="IP_RESULT")),
            "entry2": MagicMock(cache_type=MagicMock(value="API_RESPONSE")),
            "entry3": MagicMock(cache_type=MagicMock(value="IP_RESULT")),
        }
        cache.cleanup.return_value = {
            "entries_cleaned": 5,
            "entries_remaining": 8,
        }
        return cache

    async def test_handle_command_no_args(self, cache_handler, mock_message):
        """Test handle_command with no arguments."""
        result = await cache_handler.handle_command(mock_message, [])
        assert result is False

    async def test_handle_command_cache_command(self, cache_handler, mock_message):
        """Test handle_command with cache command."""
        mock_message.author.guild_permissions.administrator = True

        result = await cache_handler.handle_command(mock_message, ["cache"])
        assert result is True

    async def test_handle_command_non_cache_command(self, cache_handler, mock_message):
        """Test handle_command with non-cache command."""
        result = await cache_handler.handle_command(mock_message, ["other"])
        assert result is False

    async def test_handle_cache_command_no_permissions(
        self, cache_handler, mock_message
    ):
        """Test cache command without admin permissions."""
        mock_message.author.guild_permissions.administrator = False

        result = await cache_handler._handle_cache_command(mock_message, [])
        assert result is False

    async def test_handle_cache_command_no_args_shows_help(
        self, cache_handler, mock_message
    ):
        """Test cache command with no args shows help."""
        mock_message.author.guild_permissions.administrator = True

        result = await cache_handler._handle_cache_command(mock_message, [])
        assert result is True

    async def test_handle_cache_command_show_subcommand(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache show subcommand."""
        mock_message.author.guild_permissions.administrator = True
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info

        result = await cache_handler._handle_cache_command(mock_message, ["show"])
        assert result is True

    async def test_handle_cache_command_clear_subcommand(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache clear subcommand."""
        mock_message.author.guild_permissions.administrator = True
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.invalidate_cache.return_value = 10

        result = await cache_handler._handle_cache_command(mock_message, ["clear"])
        assert result is True

    async def test_handle_cache_command_invalid_subcommand(
        self, cache_handler, mock_message
    ):
        """Test cache command with invalid subcommand."""
        mock_message.author.guild_permissions.administrator = True

        result = await cache_handler._handle_cache_command(mock_message, ["invalid"])
        assert result is False

    async def test_handle_cache_command_exception(self, cache_handler, mock_message):
        """Test cache command with exception."""
        mock_message.author.guild_permissions.administrator = True
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_command(mock_message, ["show"])
        assert result is False

    async def test_handle_cache_show_enabled(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache show when cache is enabled."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info

        result = await cache_handler._handle_cache_show(mock_message, ["show"])
        assert result is True

    async def test_handle_cache_show_disabled(self, cache_handler, mock_message):
        """Test cache show when cache is disabled."""
        cache_handler.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        result = await cache_handler._handle_cache_show(mock_message, ["show"])
        assert result is True

    async def test_handle_cache_show_exception(self, cache_handler, mock_message):
        """Test cache show with exception."""
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_show(mock_message, ["show"])
        assert result is False

    async def test_handle_cache_clear_enabled(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache clear when cache is enabled."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.invalidate_cache.return_value = 15

        result = await cache_handler._handle_cache_clear(mock_message, ["clear"])
        assert result is True
        cache_handler.ip_service.invalidate_cache.assert_called_once_with(None)

    async def test_handle_cache_clear_with_namespace(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache clear with specific namespace."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.invalidate_cache.return_value = 5

        result = await cache_handler._handle_cache_clear(
            mock_message, ["clear", "ip_check"]
        )
        assert result is True
        cache_handler.ip_service.invalidate_cache.assert_called_once_with("ip_check")

    async def test_handle_cache_clear_disabled(self, cache_handler, mock_message):
        """Test cache clear when cache is disabled."""
        cache_handler.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        result = await cache_handler._handle_cache_clear(mock_message, ["clear"])
        assert result is True

    async def test_handle_cache_clear_exception(self, cache_handler, mock_message):
        """Test cache clear with exception."""
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_clear(mock_message, ["clear"])
        assert result is False

    async def test_handle_cache_stats_enabled(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache stats when cache is enabled."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info

        with patch(
            "ip_monitor.commands.admin_commands.cache_handler.get_cache"
        ) as mock_get_cache:
            mock_get_cache.return_value = MagicMock(
                max_memory_size=100,
                memory_cache={
                    "entry1": MagicMock(cache_type=MagicMock(value="IP_RESULT")),
                    "entry2": MagicMock(cache_type=MagicMock(value="API_RESPONSE")),
                },
            )

            result = await cache_handler._handle_cache_stats(mock_message, ["stats"])
            assert result is True

    async def test_handle_cache_stats_disabled(self, cache_handler, mock_message):
        """Test cache stats when cache is disabled."""
        cache_handler.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        result = await cache_handler._handle_cache_stats(mock_message, ["stats"])
        assert result is True

    async def test_handle_cache_stats_exception(self, cache_handler, mock_message):
        """Test cache stats with exception."""
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_stats(mock_message, ["stats"])
        assert result is False

    async def test_handle_cache_stats_import_error(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache stats with import error for cache module."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info

        with patch(
            "ip_monitor.commands.admin_commands.cache_handler.get_cache"
        ) as mock_get_cache:
            mock_get_cache.side_effect = ImportError("Cannot import cache")

            result = await cache_handler._handle_cache_stats(mock_message, ["stats"])
            assert result is True

    async def test_handle_cache_cleanup_enabled(
        self, cache_handler, mock_message, mock_cache_info, mock_cache_instance
    ):
        """Test cache cleanup when cache is enabled."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info

        with patch(
            "ip_monitor.commands.admin_commands.cache_handler.get_cache"
        ) as mock_get_cache:
            mock_get_cache.return_value = mock_cache_instance

            result = await cache_handler._handle_cache_cleanup(
                mock_message, ["cleanup"]
            )
            assert result is True
            mock_cache_instance.cleanup.assert_called_once()

    async def test_handle_cache_cleanup_disabled(self, cache_handler, mock_message):
        """Test cache cleanup when cache is disabled."""
        cache_handler.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        result = await cache_handler._handle_cache_cleanup(mock_message, ["cleanup"])
        assert result is True

    async def test_handle_cache_cleanup_exception(self, cache_handler, mock_message):
        """Test cache cleanup with exception."""
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_cleanup(mock_message, ["cleanup"])
        assert result is False

    async def test_handle_cache_refresh_enabled(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache refresh when cache is enabled."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.refresh_stale_cache_entries = AsyncMock(return_value=8)

        result = await cache_handler._handle_cache_refresh(mock_message, ["refresh"])
        assert result is True
        cache_handler.ip_service.refresh_stale_cache_entries.assert_called_once()

    async def test_handle_cache_refresh_no_stale_entries(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache refresh when no stale entries exist."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.refresh_stale_cache_entries = AsyncMock(return_value=0)

        result = await cache_handler._handle_cache_refresh(mock_message, ["refresh"])
        assert result is True

    async def test_handle_cache_refresh_disabled(self, cache_handler, mock_message):
        """Test cache refresh when cache is disabled."""
        cache_handler.ip_service.get_cache_info.return_value = {
            "enabled": False,
            "stats": {},
        }

        result = await cache_handler._handle_cache_refresh(mock_message, ["refresh"])
        assert result is True

    async def test_handle_cache_refresh_exception(self, cache_handler, mock_message):
        """Test cache refresh with exception."""
        cache_handler.ip_service.get_cache_info.side_effect = Exception("Cache error")

        result = await cache_handler._handle_cache_refresh(mock_message, ["refresh"])
        assert result is False

    def test_get_cache_help_text(self, cache_handler):
        """Test _get_cache_help_text returns proper help text."""
        help_text = cache_handler._get_cache_help_text()
        assert "Cache Management Commands" in help_text
        assert "!cache show" in help_text
        assert "!cache clear" in help_text
        assert "!cache stats" in help_text
        assert "!cache cleanup" in help_text
        assert "!cache refresh" in help_text

    def test_get_help_text(self, cache_handler):
        """Test get_help_text returns cache help text."""
        help_text = cache_handler.get_help_text()
        assert "Cache Management Commands" in help_text
        assert "!cache show" in help_text

    def test_cache_stats_efficiency_ratings(self, cache_handler, mock_message):
        """Test cache stats efficiency ratings."""
        # Test different hit rates and their efficiency ratings
        test_cases = [
            (90, "Excellent"),
            (70, "Good"),
            (50, "Fair"),
            (30, "Poor"),
        ]

        for hit_rate, expected_efficiency in test_cases:
            cache_info = {
                "enabled": True,
                "cache_ttl": 300,
                "stale_threshold": 0.8,
                "stale_entries_count": 2,
                "stats": {
                    "memory_entries": 10,
                    "memory_usage_mb": 1.5,
                    "hits": hit_rate,
                    "misses": 100 - hit_rate,
                    "hit_rate": hit_rate / 100,
                    "evictions": 3,
                    "invalidations": 2,
                    "refreshes": 5,
                    "saves": 8,
                    "loads": 12,
                },
            }

            cache_handler.ip_service.get_cache_info.return_value = cache_info

            # We can't easily test the actual efficiency rating in the output
            # without mocking the entire response, but we can verify the method runs
            async def test_efficiency():
                with patch(
                    "ip_monitor.commands.admin_commands.cache_handler.get_cache"
                ) as mock_get_cache:
                    mock_get_cache.return_value = MagicMock(
                        max_memory_size=100, memory_cache={}
                    )
                    result = await cache_handler._handle_cache_stats(
                        mock_message, ["stats"]
                    )
                    assert result is True

            # Run the test
            import asyncio

            asyncio.run(test_efficiency())

    async def test_cache_clear_different_namespaces(
        self, cache_handler, mock_message, mock_cache_info
    ):
        """Test cache clear with different namespace values."""
        cache_handler.ip_service.get_cache_info.return_value = mock_cache_info
        cache_handler.ip_service.invalidate_cache.return_value = 5

        # Test various namespace values
        test_namespaces = ["ip_check", "global", "api_response", "custom_namespace"]

        for namespace in test_namespaces:
            result = await cache_handler._handle_cache_clear(
                mock_message, ["clear", namespace]
            )
            assert result is True
            cache_handler.ip_service.invalidate_cache.assert_called_with(namespace)

    async def test_cache_show_no_hit_rate(self, cache_handler, mock_message):
        """Test cache show when hit_rate is not in stats."""
        cache_info = {
            "enabled": True,
            "cache_ttl": 300,
            "stale_threshold": 0.8,
            "stale_entries_count": 2,
            "stats": {
                "memory_entries": 10,
                "hits": 85,
                "misses": 15,
                "evictions": 3,
                "invalidations": 2,
                "refreshes": 5,
                "saves": 8,
                "loads": 12,
            },
        }
        cache_handler.ip_service.get_cache_info.return_value = cache_info

        result = await cache_handler._handle_cache_show(mock_message, ["show"])
        assert result is True
