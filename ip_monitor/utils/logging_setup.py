"""
Logging configuration for the IP Monitor Bot.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(log_level: Optional[str] = None) -> None:
    """
    Configure application logging.

    Args:
        log_level: Optional log level override (default: from environment)
    """
    # Get log level from environment if not provided
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Set up logging handlers and format
    logging.basicConfig(
        level=logging.INFO,  # Default level, will be overridden below
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            RotatingFileHandler("bot.log", maxBytes=1024 * 1024, backupCount=3),
            logging.StreamHandler(),
        ],
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set the actual log level
    root_logger = logging.getLogger()
    try:
        root_logger.setLevel(getattr(logging, log_level))
    except AttributeError:
        root_logger.setLevel(logging.INFO)
        logging.warning(f"Invalid LOG_LEVEL: {log_level}. Using INFO instead.")
