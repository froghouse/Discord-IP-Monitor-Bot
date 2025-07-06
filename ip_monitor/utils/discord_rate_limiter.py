"""
Discord API rate limiting with exponential backoff implementation.
"""

import asyncio
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import discord

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DiscordRateLimiter:
    """
    Discord API rate limiter with exponential backoff and jitter.

    Handles Discord's rate limiting by:
    1. Respecting Discord's rate limit headers
    2. Implementing exponential backoff with jitter
    3. Managing different rate limit buckets
    4. Automatic retry on 429 responses
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize the Discord rate limiter.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay in seconds
            backoff_factor: Factor for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        # Track rate limit buckets and their reset times
        self.rate_limit_buckets: dict[str, float] = {}
        self.global_rate_limit_reset: float | None = None

    def _calculate_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """
        Calculate delay for exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
            retry_after: Retry-After header value from Discord

        Returns:
            Delay in seconds
        """
        if retry_after is not None:
            # Use Discord's suggested retry time
            delay = retry_after
        else:
            # Calculate exponential backoff
            delay = min(
                self.base_delay * (self.backoff_factor**attempt), self.max_delay
            )

        # Add jitter to prevent thundering herd
        if self.jitter:
            jitter = secrets.SystemRandom().uniform(0.5, 1.0)
            delay *= jitter  # 50-100% of calculated delay

        return delay

    def _get_bucket_key(self, endpoint: str, method: str = "POST") -> str:
        """
        Generate a bucket key for rate limiting.

        Args:
            endpoint: API endpoint
            method: HTTP method

        Returns:
            Bucket key for rate limiting
        """
        # Simplified bucket key - in practice, Discord uses more complex bucketing
        return f"{method}:{endpoint}"

    def _is_rate_limited(self, bucket_key: str) -> bool:
        """
        Check if a bucket is currently rate limited.

        Args:
            bucket_key: The bucket key to check

        Returns:
            True if rate limited, False otherwise
        """
        current_time = time.time()

        # Check global rate limit
        if self.global_rate_limit_reset and current_time < self.global_rate_limit_reset:
            return True

        # Check bucket-specific rate limit
        if bucket_key in self.rate_limit_buckets:
            return current_time < self.rate_limit_buckets[bucket_key]

        return False

    def _update_rate_limits(
        self, response_headers: dict[str, str], bucket_key: str
    ) -> None:
        """
        Update rate limit information from Discord response headers.

        Args:
            response_headers: HTTP response headers from Discord
            bucket_key: The bucket key for this request
        """
        # Handle global rate limit
        if "x-ratelimit-global" in response_headers:
            retry_after = float(response_headers.get("retry-after", 0))
            self.global_rate_limit_reset = time.time() + retry_after
            logger.warning(f"Global rate limit hit. Reset in {retry_after} seconds")

        # Handle bucket-specific rate limit
        if "x-ratelimit-remaining" in response_headers:
            remaining = int(response_headers.get("x-ratelimit-remaining", 0))
            reset_after = float(response_headers.get("x-ratelimit-reset-after", 0))

            if remaining == 0:
                self.rate_limit_buckets[bucket_key] = time.time() + reset_after
                logger.debug(
                    f"Rate limit bucket {bucket_key} exhausted. Reset in {reset_after} seconds"
                )

    async def execute_with_backoff(
        self,
        func: Callable[[], Awaitable[T]],
        endpoint: str = "unknown",
        method: str = "POST",
    ) -> T | None:
        """
        Execute a Discord API call with exponential backoff.

        Args:
            func: Async function to execute
            endpoint: API endpoint name for bucket tracking
            method: HTTP method

        Returns:
            Result of the function or None if all retries failed
        """
        bucket_key = self._get_bucket_key(endpoint, method)

        for attempt in range(self.max_retries + 1):
            try:
                # Check if we're currently rate limited
                if self._is_rate_limited(bucket_key):
                    current_time = time.time()

                    # Calculate wait time
                    global_wait = (
                        (self.global_rate_limit_reset - current_time)
                        if self.global_rate_limit_reset
                        else 0
                    )
                    bucket_wait = (
                        self.rate_limit_buckets.get(bucket_key, 0) - current_time
                    )
                    wait_time = max(global_wait, bucket_wait, 0)

                    if wait_time > 0:
                        logger.info(
                            f"Rate limited, waiting {wait_time:.2f} seconds before retry"
                        )
                        await asyncio.sleep(wait_time)

                # Execute the function
                result = await func()

                # If we get here, the call succeeded
                logger.debug(f"Discord API call succeeded on attempt {attempt + 1}")
                return result

            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = e.retry_after if hasattr(e, "retry_after") else None

                    # Update rate limit tracking
                    if hasattr(e, "response") and hasattr(e.response, "headers"):
                        self._update_rate_limits(dict(e.response.headers), bucket_key)

                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt, retry_after)
                        logger.warning(
                            f"Rate limited (429), retrying in {delay:.2f} seconds "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        f"Rate limited and max retries ({self.max_retries}) exceeded"
                    )
                    raise

                if e.status >= 500:  # Server errors
                    if attempt < self.max_retries:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"Server error ({e.status}), retrying in {delay:.2f} seconds "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(delay)
                        continue
                    logger.error(
                        f"Server error and max retries ({self.max_retries}) exceeded"
                    )
                    raise
                # Other HTTP errors (4xx) - don't retry
                logger.error(f"HTTP error {e.status}: {e}")
                raise

            except discord.DiscordException as e:
                # Other Discord exceptions
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        f"Discord exception: {e}, retrying in {delay:.2f} seconds "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error(
                    f"Discord exception and max retries ({self.max_retries}) exceeded: {e}"
                )
                raise

            except Exception as e:
                # Unexpected errors - don't retry
                logger.error(f"Unexpected error in Discord API call: {e}")
                raise

        # If we get here, all retries failed
        logger.error(f"All {self.max_retries} retries failed for Discord API call")
        return None

    async def send_message_with_backoff(
        self, channel: discord.TextChannel, content: str, **kwargs: Any
    ) -> discord.Message | None:
        """
        Send a message to a Discord channel with rate limiting and backoff.

        Args:
            channel: The Discord channel to send to
            content: Message content
            **kwargs: Additional arguments for channel.send()

        Returns:
            The sent message or None if failed
        """

        async def send_func() -> discord.Message:
            return await channel.send(content, **kwargs)

        return await self.execute_with_backoff(
            send_func, endpoint=f"channels/{channel.id}/messages", method="POST"
        )

    async def edit_message_with_backoff(
        self, message: discord.Message, content: str, **kwargs: Any
    ) -> discord.Message | None:
        """
        Edit a Discord message with rate limiting and backoff.

        Args:
            message: The message to edit
            content: New message content
            **kwargs: Additional arguments for message.edit()

        Returns:
            The edited message or None if failed
        """

        async def edit_func() -> discord.Message:
            return await message.edit(content=content, **kwargs)

        return await self.execute_with_backoff(
            edit_func,
            endpoint=f"channels/{message.channel.id}/messages/{message.id}",
            method="PATCH",
        )

    async def delete_message_with_backoff(self, message: discord.Message) -> bool:
        """
        Delete a Discord message with rate limiting and backoff.

        Args:
            message: The message to delete

        Returns:
            True if successful, False otherwise
        """

        async def delete_func() -> None:
            await message.delete()

        try:
            await self.execute_with_backoff(
                delete_func,
                endpoint=f"channels/{message.channel.id}/messages/{message.id}",
                method="DELETE",
            )
            return True
        except Exception:
            return False

    def get_rate_limit_info(self) -> dict[str, Any]:
        """
        Get current rate limit information.

        Returns:
            Dictionary with rate limit status
        """
        current_time = time.time()

        # Clean up expired rate limits
        self.rate_limit_buckets = {
            k: v for k, v in self.rate_limit_buckets.items() if v > current_time
        }

        if (
            self.global_rate_limit_reset
            and self.global_rate_limit_reset <= current_time
        ):
            self.global_rate_limit_reset = None

        return {
            "global_rate_limited": self.global_rate_limit_reset is not None,
            "global_reset_in": max(0, self.global_rate_limit_reset - current_time)
            if self.global_rate_limit_reset
            else 0,
            "bucket_rate_limits": len(self.rate_limit_buckets),
            "active_buckets": list(self.rate_limit_buckets.keys()),
        }
