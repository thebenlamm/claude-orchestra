"""Logging configuration for Claude Orchestra.

Provides a configured logger that writes to ~/.claude-orchestra/orchestra.log
"""

import logging
from pathlib import Path

# Log file location
LOG_DIR = Path.home() / ".claude-orchestra"
LOG_FILE = LOG_DIR / "orchestra.log"


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger that writes to file and optionally stderr
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Ensure log directory exists
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # File handler - captures everything for debugging
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


class OrchestraError(Exception):
    """Base exception for Claude Orchestra errors."""

    pass


class TmuxError(OrchestraError):
    """Error related to tmux operations."""

    pass


class SessionError(OrchestraError):
    """Error related to session management."""

    pass
