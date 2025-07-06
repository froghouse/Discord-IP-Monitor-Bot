"""
Test suite for DiscordRateLimiter class.

This module provides comprehensive testing for Discord API rate limiting
functionality with exponential backoff and jitter.
"""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from ip_monitor.utils.discord_rate_limiter import DiscordRateLimiter


class TestDiscordRateLimiter:
    """Test suite for DiscordRateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a Discord rate limiter for testing."""
        return DiscordRateLimiter(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            backoff_factor=2.0,
            jitter=True,
        )

    @pytest.fixture
    def no_jitter_limiter(self):
        """Create a rate limiter without jitter for predictable testing."""
        return DiscordRateLimiter(
            max_retries=2,
            base_delay=2.0,
            max_delay=10.0,
            backoff_factor=2.0,
            jitter=False,
        )

    @pytest.fixture
    def mock_channel(self):
        """Create a mock Discord channel."""
        channel = Mock(spec=discord.TextChannel)
        channel.id = 123456789
        channel.send = AsyncMock()
        return channel

    @pytest.fixture
    def mock_message(self):
        """Create a mock Discord message."""
        message = Mock(spec=discord.Message)
        message.id = 987654321
        message.channel = Mock()
        message.channel.id = 123456789
        message.edit = AsyncMock()
        message.delete = AsyncMock()
        return message

    def test_initialization(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.max_retries == 3
        assert rate_limiter.base_delay == 1.0
        assert rate_limiter.max_delay == 30.0
        assert rate_limiter.backoff_factor == 2.0
        assert rate_limiter.jitter is True
        assert rate_limiter.rate_limit_buckets == {}
        assert rate_limiter.global_rate_limit_reset is None

    def test_calculate_delay_no_retry_after(self, no_jitter_limiter):
        """Test delay calculation without retry-after header."""
        # Test exponential backoff
        assert no_jitter_limiter._calculate_delay(0) == 2.0  # base_delay
        assert no_jitter_limiter._calculate_delay(1) == 4.0  # base_delay * 2^1
        assert no_jitter_limiter._calculate_delay(2) == 8.0  # base_delay * 2^2
        assert no_jitter_limiter._calculate_delay(3) == 10.0  # capped at max_delay

    def test_calculate_delay_with_retry_after(self, no_jitter_limiter):
        """Test delay calculation with retry-after header."""
        delay = no_jitter_limiter._calculate_delay(0, retry_after=5.5)
        assert delay == 5.5

    def test_calculate_delay_with_jitter(self, rate_limiter):
        """Test delay calculation with jitter."""
        with patch("secrets.SystemRandom.uniform", return_value=0.75):
            delay = rate_limiter._calculate_delay(0)
            # Should be base_delay (1.0) * jitter (0.75) = 0.75
            assert delay == 0.75

    def test_get_bucket_key(self, rate_limiter):
        """Test bucket key generation."""
        assert rate_limiter._get_bucket_key("messages", "POST") == "POST:messages"
        assert rate_limiter._get_bucket_key("channels/123", "GET") == "GET:channels/123"

    def test_is_rate_limited_no_limits(self, rate_limiter):
        """Test is_rate_limited with no active limits."""
        assert not rate_limiter._is_rate_limited("POST:messages")

    def test_is_rate_limited_global_limit(self, rate_limiter):
        """Test is_rate_limited with global rate limit."""
        # Set global rate limit to future time
        rate_limiter.global_rate_limit_reset = time.time() + 10

        assert rate_limiter._is_rate_limited("POST:messages")

    def test_is_rate_limited_bucket_limit(self, rate_limiter):
        """Test is_rate_limited with bucket-specific limit."""
        bucket_key = "POST:messages"
        # Set bucket rate limit to future time
        rate_limiter.rate_limit_buckets[bucket_key] = time.time() + 5

        assert rate_limiter._is_rate_limited(bucket_key)

    def test_is_rate_limited_expired_global_limit(self, rate_limiter):
        """Test is_rate_limited with expired global limit."""
        # Set global rate limit to past time
        rate_limiter.global_rate_limit_reset = time.time() - 1

        assert not rate_limiter._is_rate_limited("POST:messages")

    def test_is_rate_limited_expired_bucket_limit(self, rate_limiter):
        """Test is_rate_limited with expired bucket limit."""
        bucket_key = "POST:messages"
        # Set bucket rate limit to past time
        rate_limiter.rate_limit_buckets[bucket_key] = time.time() - 1

        assert not rate_limiter._is_rate_limited(bucket_key)

    def test_update_rate_limits_global(self, rate_limiter):
        """Test updating rate limits with global rate limit."""
        headers = {
            "x-ratelimit-global": "true",
            "retry-after": "60.5",
        }

        rate_limiter._update_rate_limits(headers, "POST:messages")

        assert rate_limiter.global_rate_limit_reset is not None
        assert rate_limiter.global_rate_limit_reset > time.time() + 60

    def test_update_rate_limits_bucket_exhausted(self, rate_limiter):
        """Test updating rate limits with exhausted bucket."""
        bucket_key = "POST:messages"
        headers = {
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "30.0",
        }

        rate_limiter._update_rate_limits(headers, bucket_key)

        assert bucket_key in rate_limiter.rate_limit_buckets
        assert rate_limiter.rate_limit_buckets[bucket_key] > time.time() + 29

    def test_update_rate_limits_bucket_not_exhausted(self, rate_limiter):
        """Test updating rate limits with non-exhausted bucket."""
        bucket_key = "POST:messages"
        headers = {
            "x-ratelimit-remaining": "5",
            "x-ratelimit-reset-after": "30.0",
        }

        rate_limiter._update_rate_limits(headers, bucket_key)

        # Should not add bucket to rate limits since remaining > 0
        assert bucket_key not in rate_limiter.rate_limit_buckets

    async def test_execute_with_backoff_success_immediate(self, rate_limiter):
        """Test execute_with_backoff with immediate success."""
        mock_func = AsyncMock(return_value="success")

        result = await rate_limiter.execute_with_backoff(mock_func, "messages")

        assert result == "success"
        mock_func.assert_called_once()

    async def test_execute_with_backoff_rate_limited_then_success(self, rate_limiter):
        """Test execute_with_backoff with initial rate limit then success."""
        bucket_key = "POST:messages"
        # Set initial rate limit
        rate_limiter.rate_limit_buckets[bucket_key] = time.time() + 0.1

        mock_func = AsyncMock(return_value="success")

        start_time = time.time()
        result = await rate_limiter.execute_with_backoff(mock_func, "messages")
        end_time = time.time()

        assert result == "success"
        assert end_time - start_time >= 0.1  # Should have waited
        mock_func.assert_called_once()

    async def test_execute_with_backoff_429_retry_success(self, rate_limiter):
        """Test execute_with_backoff with 429 error then success."""
        # Create a 429 exception
        mock_response = Mock()
        mock_response.status = 429
        mock_response.headers = {}  # Mock headers as empty dict
        http_exception = discord.HTTPException(mock_response, "Rate limited")
        http_exception.retry_after = 0.1
        http_exception.response = mock_response

        mock_func = AsyncMock(side_effect=[http_exception, "success"])

        start_time = time.time()
        result = await rate_limiter.execute_with_backoff(mock_func, "messages")
        end_time = time.time()

        assert result == "success"
        assert (
            end_time - start_time >= 0.05
        )  # Should have waited (accounting for jitter)
        assert mock_func.call_count == 2

    async def test_execute_with_backoff_429_max_retries(self, rate_limiter):
        """Test execute_with_backoff with 429 exceeding max retries."""
        # Create a 429 exception that keeps happening
        mock_response = Mock()
        mock_response.status = 429
        mock_response.headers = {}
        http_exception = discord.HTTPException(mock_response, "Rate limited")
        http_exception.retry_after = 0.01
        http_exception.response = mock_response

        mock_func = AsyncMock(side_effect=http_exception)

        with pytest.raises(discord.HTTPException):
            await rate_limiter.execute_with_backoff(mock_func, "messages")

        # Should have tried max_retries + 1 times
        assert mock_func.call_count == rate_limiter.max_retries + 1

    async def test_execute_with_backoff_server_error_retry(self, rate_limiter):
        """Test execute_with_backoff with server error retry."""
        # Create a 500 server error
        mock_response = Mock()
        mock_response.status = 500
        mock_response.headers = {}
        server_error = discord.HTTPException(mock_response, "Internal server error")
        server_error.response = mock_response

        mock_func = AsyncMock(side_effect=[server_error, "success"])

        result = await rate_limiter.execute_with_backoff(mock_func, "messages")

        assert result == "success"
        assert mock_func.call_count == 2

    async def test_execute_with_backoff_server_error_max_retries(self, rate_limiter):
        """Test execute_with_backoff with server error exceeding max retries."""
        # Create a 500 server error that keeps happening
        mock_response = Mock()
        mock_response.status = 500
        mock_response.headers = {}
        server_error = discord.HTTPException(mock_response, "Internal server error")
        server_error.response = mock_response

        mock_func = AsyncMock(side_effect=server_error)

        with pytest.raises(discord.HTTPException):
            await rate_limiter.execute_with_backoff(mock_func, "messages")

        assert mock_func.call_count == rate_limiter.max_retries + 1

    async def test_execute_with_backoff_client_error_no_retry(self, rate_limiter):
        """Test execute_with_backoff with client error (no retry)."""
        # Create a 400 client error
        mock_response = Mock()
        mock_response.status = 400
        mock_response.headers = {}
        client_error = discord.HTTPException(mock_response, "Bad request")
        client_error.response = mock_response

        mock_func = AsyncMock(side_effect=client_error)

        with pytest.raises(discord.HTTPException):
            await rate_limiter.execute_with_backoff(mock_func, "messages")

        # Should not retry client errors
        mock_func.assert_called_once()

    async def test_execute_with_backoff_discord_exception_retry(self, rate_limiter):
        """Test execute_with_backoff with Discord exception retry."""
        discord_error = discord.DiscordException("Connection error")

        mock_func = AsyncMock(side_effect=[discord_error, "success"])

        result = await rate_limiter.execute_with_backoff(mock_func, "messages")

        assert result == "success"
        assert mock_func.call_count == 2

    async def test_execute_with_backoff_unexpected_error_no_retry(self, rate_limiter):
        """Test execute_with_backoff with unexpected error (no retry)."""
        unexpected_error = ValueError("Something went wrong")

        mock_func = AsyncMock(side_effect=unexpected_error)

        with pytest.raises(ValueError):
            await rate_limiter.execute_with_backoff(mock_func, "messages")

        # Should not retry unexpected errors
        mock_func.assert_called_once()

    async def test_execute_with_backoff_all_retries_failed(self, rate_limiter):
        """Test execute_with_backoff when all retries fail."""
        discord_error = discord.DiscordException("Persistent error")

        mock_func = AsyncMock(side_effect=discord_error)

        with pytest.raises(discord.DiscordException):
            await rate_limiter.execute_with_backoff(mock_func, "messages")

        assert mock_func.call_count == rate_limiter.max_retries + 1

    async def test_send_message_with_backoff_success(self, rate_limiter, mock_channel):
        """Test send_message_with_backoff with success."""
        expected_message = Mock(spec=discord.Message)
        mock_channel.send.return_value = expected_message

        result = await rate_limiter.send_message_with_backoff(
            mock_channel, "test message", embed=None
        )

        assert result == expected_message
        mock_channel.send.assert_called_once_with("test message", embed=None)

    async def test_send_message_with_backoff_failure(self, rate_limiter, mock_channel):
        """Test send_message_with_backoff with failure."""
        mock_response = Mock()
        mock_response.status = 400
        mock_response.headers = {}
        http_error = discord.HTTPException(mock_response, "Bad request")
        http_error.response = mock_response
        mock_channel.send.side_effect = http_error

        with pytest.raises(discord.HTTPException):
            await rate_limiter.send_message_with_backoff(mock_channel, "test message")

    async def test_edit_message_with_backoff_success(self, rate_limiter, mock_message):
        """Test edit_message_with_backoff with success."""
        mock_message.edit.return_value = mock_message

        result = await rate_limiter.edit_message_with_backoff(
            mock_message, "edited content", embed=None
        )

        assert result == mock_message
        mock_message.edit.assert_called_once_with(content="edited content", embed=None)

    async def test_edit_message_with_backoff_failure(self, rate_limiter, mock_message):
        """Test edit_message_with_backoff with failure."""
        mock_response = Mock()
        mock_response.status = 403
        mock_response.headers = {}
        http_error = discord.HTTPException(mock_response, "Forbidden")
        http_error.response = mock_response
        mock_message.edit.side_effect = http_error

        with pytest.raises(discord.HTTPException):
            await rate_limiter.edit_message_with_backoff(mock_message, "new content")

    async def test_delete_message_with_backoff_success(
        self, rate_limiter, mock_message
    ):
        """Test delete_message_with_backoff with success."""
        # Set up the async mock to return None (normal behavior for delete)
        mock_message.delete.return_value = None

        result = await rate_limiter.delete_message_with_backoff(mock_message)

        assert result is True
        mock_message.delete.assert_called_once()

    async def test_delete_message_with_backoff_failure(
        self, rate_limiter, mock_message
    ):
        """Test delete_message_with_backoff with failure."""
        mock_response = Mock()
        mock_response.status = 404
        mock_response.headers = {}
        http_error = discord.HTTPException(mock_response, "Not found")
        http_error.response = mock_response
        mock_message.delete.side_effect = http_error

        result = await rate_limiter.delete_message_with_backoff(mock_message)

        assert result is False

    def test_get_rate_limit_info_no_limits(self, rate_limiter):
        """Test get_rate_limit_info with no active limits."""
        info = rate_limiter.get_rate_limit_info()

        expected = {
            "global_rate_limited": False,
            "global_reset_in": 0,
            "bucket_rate_limits": 0,
            "active_buckets": [],
        }

        assert info == expected

    def test_get_rate_limit_info_with_global_limit(self, rate_limiter):
        """Test get_rate_limit_info with global rate limit."""
        rate_limiter.global_rate_limit_reset = time.time() + 30

        info = rate_limiter.get_rate_limit_info()

        assert info["global_rate_limited"] is True
        assert 25 <= info["global_reset_in"] <= 30  # Allow for small timing differences

    def test_get_rate_limit_info_with_bucket_limits(self, rate_limiter):
        """Test get_rate_limit_info with bucket rate limits."""
        rate_limiter.rate_limit_buckets = {
            "POST:messages": time.time() + 10,
            "GET:channels": time.time() + 5,
        }

        info = rate_limiter.get_rate_limit_info()

        assert info["bucket_rate_limits"] == 2
        assert set(info["active_buckets"]) == {"POST:messages", "GET:channels"}

    def test_get_rate_limit_info_cleanup_expired(self, rate_limiter):
        """Test get_rate_limit_info cleans up expired limits."""
        # Add mix of active and expired limits
        current_time = time.time()
        rate_limiter.rate_limit_buckets = {
            "POST:messages": current_time + 10,  # Active
            "GET:channels": current_time - 5,  # Expired
        }
        rate_limiter.global_rate_limit_reset = current_time - 10  # Expired

        info = rate_limiter.get_rate_limit_info()

        assert info["global_rate_limited"] is False
        assert info["global_reset_in"] == 0
        assert info["bucket_rate_limits"] == 1
        assert info["active_buckets"] == ["POST:messages"]

        # Check that expired limits were cleaned up
        assert "GET:channels" not in rate_limiter.rate_limit_buckets
        assert rate_limiter.global_rate_limit_reset is None

    async def test_rate_limit_header_parsing_with_response(self, rate_limiter):
        """Test rate limit header parsing from Discord response."""
        # Create a mock 429 exception with response headers
        response = Mock()
        response.status = 429
        response.headers = {
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "45.0",
        }

        http_exception = discord.HTTPException(response, "Rate limited")
        http_exception.retry_after = 45.0
        http_exception.response = response

        mock_func = AsyncMock(side_effect=[http_exception, "success"])

        # This should update the bucket rate limits
        await rate_limiter.execute_with_backoff(mock_func, "messages")

        bucket_key = "POST:messages"
        assert bucket_key in rate_limiter.rate_limit_buckets

    async def test_global_rate_limit_precedence(self, rate_limiter):
        """Test that global rate limit takes precedence over bucket limits."""
        # Set both global and bucket rate limits
        bucket_key = "POST:messages"
        current_time = time.time()
        rate_limiter.global_rate_limit_reset = current_time + 10
        rate_limiter.rate_limit_buckets[bucket_key] = current_time + 5

        mock_func = AsyncMock(return_value="success")

        start_time = time.time()
        # Use a very short global limit for testing
        rate_limiter.global_rate_limit_reset = start_time + 0.1

        result = await rate_limiter.execute_with_backoff(mock_func, "messages")
        end_time = time.time()

        assert result == "success"
        # Should have waited for global limit (longer than bucket limit would have been)
        assert end_time - start_time >= 0.1

    async def test_concurrent_api_calls(self, rate_limiter):
        """Test concurrent API calls through rate limiter."""
        call_count = 0

        async def mock_api_call():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # Make multiple concurrent calls
        tasks = [
            rate_limiter.execute_with_backoff(mock_api_call, f"endpoint_{i}")
            for i in range(5)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert call_count == 5
        # All results should be unique
        assert len(set(results)) == 5

    async def test_backoff_timing_progression(self, no_jitter_limiter):
        """Test exponential backoff timing progression."""
        call_times = []

        async def failing_func():
            call_times.append(time.time())
            raise discord.DiscordException("Persistent failure")

        start_time = time.time()

        with pytest.raises(discord.DiscordException):
            await no_jitter_limiter.execute_with_backoff(failing_func, "test")

        # Should have made 3 attempts (max_retries=2 + initial)
        assert len(call_times) == 3

        # Check timing between calls (allowing for small variations)
        if len(call_times) >= 2:
            # First retry should be after ~2 seconds (base_delay)
            first_gap = call_times[1] - call_times[0]
            assert 1.8 <= first_gap <= 2.2

        if len(call_times) >= 3:
            # Second retry should be after ~4 seconds (base_delay * 2)
            second_gap = call_times[2] - call_times[1]
            assert 3.8 <= second_gap <= 4.2

    async def test_jitter_randomization(self, rate_limiter):
        """Test that jitter adds randomization to delays."""
        delays = []

        # Mock the jitter to return different values
        with patch("secrets.SystemRandom.uniform") as mock_uniform:
            mock_uniform.side_effect = [0.5, 0.8, 1.0]

            for attempt in range(3):
                delay = rate_limiter._calculate_delay(attempt)
                delays.append(delay)

        # All delays should be different due to jitter
        assert len(set(delays)) == 3
        # All delays should be within expected range
        assert all(0.5 <= d <= 4.0 for d in delays)

    async def test_max_delay_cap(self, rate_limiter):
        """Test that delays are capped at max_delay."""
        # Test with high attempt number
        delay = rate_limiter._calculate_delay(10)  # Would be very high without cap

        # Should be capped at max_delay (30.0) even with jitter
        assert delay <= 30.0

    async def test_rate_limiter_state_isolation(self):
        """Test that different rate limiter instances maintain separate state."""
        limiter1 = DiscordRateLimiter()
        limiter2 = DiscordRateLimiter()

        # Set rate limits on limiter1
        limiter1.rate_limit_buckets["test"] = time.time() + 10
        limiter1.global_rate_limit_reset = time.time() + 10

        # limiter2 should not be affected
        assert limiter2.rate_limit_buckets == {}
        assert limiter2.global_rate_limit_reset is None
