"""
Centralized Logging Configuration
=================================

This module configures application-wide logging using dictConfig.
It supports console and file handlers, environment-driven log levels,
and a structured, readable log format suitable for production.

Design decisions:
- Use dictConfig for explicit, reproducible logging setup
- Provide both console and rotating file handlers
- Keep JSON-style fields in a readable line format for simplicity
"""

import logging
import logging.config
from typing import Optional


def configure_logging(
    log_level: str = "INFO",
    log_file: str = "insightfinance.log",
    enable_file: bool = True,
) -> None:
    """
    Configure Python logging for the application.

    Args:
        log_level: Minimum level for handlers (DEBUG/INFO/WARNING/ERROR)
        log_file: Path to log file
        enable_file: Whether to enable file handler
    """
    handlers = ["console"] + (["file"] if enable_file else [])

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "standard",
                "filename": log_file,
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 3,
                "encoding": "utf-8",
            },
        },
        "root": {
            "level": log_level,
            "handlers": handlers,
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a named logger (or the root logger).

    Args:
        name: Logger name; None returns root logger

    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)



