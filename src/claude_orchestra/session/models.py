"""Session data models."""

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    """Possible states for a Claude Code session."""

    WORKING = "working"  # Actively producing output
    WAITING = "waiting"  # Waiting for user input
    IDLE = "idle"  # No activity for a while
    ERROR = "error"  # Error detected
    UNKNOWN = "unknown"  # Can't determine state


class SessionStatus(BaseModel):
    """Current status of a session (from wrapper)."""

    state: SessionState = SessionState.UNKNOWN
    last_output: str = ""
    updated_at: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    """A Claude Code session with metadata."""

    id: str
    project_path: Path
    project_name: str
    task_description: str
    git_branch: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    total_time: timedelta = Field(default_factory=lambda: timedelta())
    tmux_session: str = ""

    @property
    def display_name(self) -> str:
        """Short display name for the session."""
        return self.project_name or self.project_path.name

    def get_status_file(self) -> Path:
        """Path to this session's status file."""
        from ..config import STATUS_DIR

        return STATUS_DIR / f"{self.id}.json"

    def get_session_file(self) -> Path:
        """Path to this session's metadata file."""
        from ..config import SESSIONS_DIR

        return SESSIONS_DIR / f"{self.id}.json"
