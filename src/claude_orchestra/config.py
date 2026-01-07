"""Configuration constants and paths."""

from pathlib import Path

# Base directory for all claude-orchestra data
DATA_DIR = Path.home() / ".claude-orchestra"
SESSIONS_DIR = DATA_DIR / "sessions"
STATUS_DIR = DATA_DIR / "status"

# Tmux session naming
TMUX_SESSION_PREFIX = "claude-orchestra-"

# Status detection patterns
WAITING_PATTERNS = [
    r"^> $",  # Claude Code prompt
    r"^\? ",  # Question prompt
    r"^Do you want to",  # Confirmation
    r"^Would you like",  # Question
]

WORKING_PATTERNS = [
    r"^Reading ",
    r"^Writing ",
    r"^Editing ",
    r"^Running ",
    r"^\[",  # Tool indicators
]

# Time thresholds
IDLE_THRESHOLD_SECONDS = 30  # No output for this long = idle


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
