"""
Entry point for the IP Monitor Bot application.
"""

import asyncio
import logging

from ip_monitor.bot import IPMonitorBot
from ip_monitor.config import AppConfig
from ip_monitor.utils.logging_setup import setup_logging


async def main() -> int:
    """
    Main application entry point.

    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    # Setup logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Load base configuration from environment
        base_config = AppConfig.load_from_env()

        # Load any saved configuration overrides
        config = AppConfig.load_from_file("bot_config.json", base_config)

        logger.info("Configuration loaded successfully")

        # Initialize and run the bot
        bot = IPMonitorBot(config)
        return await bot.run()

    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
