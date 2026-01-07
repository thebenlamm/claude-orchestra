"""Configuration constants and paths."""

from pathlib import Path

# Base directory for all claude-orchestra data
DATA_DIR = Path.home() / ".claude-orchestra"
SESSIONS_DIR = DATA_DIR / "sessions"
STATUS_DIR = DATA_DIR / "status"

# Tmux session naming
TMUX_SESSION_PREFIX = "claude-orchestra-"

# Time thresholds
IDLE_THRESHOLD_SECONDS = 30  # No output for this long = idle

# Re-export patterns from the shared module for convenience
from .patterns import (  # noqa: E402, F401
    ERROR_PATTERNS,
    WAITING_PATTERNS,
    WORKING_PATTERNS,
    detect_state,
)


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
