"""Session lifecycle management."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from ..config import SESSIONS_DIR, STATUS_DIR, TMUX_SESSION_PREFIX, ensure_dirs
from ..tmux.controller import TmuxController
from .models import Session, SessionState, SessionStatus


class SessionManager:
    """Manages Claude Code session lifecycle."""

    def __init__(self, tmux: TmuxController | None = None):
        ensure_dirs()
        self.tmux = tmux or TmuxController()
        self._sessions: dict[str, Session] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load persisted sessions from disk."""
        for path in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                session = Session.model_validate(data)
                self._sessions[session.id] = session
            except Exception:
                # Skip invalid session files
                pass

    def _save_session(self, session: Session) -> None:
        """Persist session metadata to disk."""
        path = session.get_session_file()
        path.write_text(session.model_dump_json(indent=2))

    def _delete_session_file(self, session_id: str) -> None:
        """Remove session file from disk."""
        path = SESSIONS_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()
        status_path = STATUS_DIR / f"{session_id}.json"
        if status_path.exists():
            status_path.unlink()

    def create_session(
        self,
        project_path: str | Path,
        task_description: str,
        git_branch: str = "",
    ) -> Session:
        """Create a new Claude Code session."""
        project_path = Path(project_path).expanduser().resolve()
        session_id = str(uuid.uuid4())[:8]
        tmux_name = f"{TMUX_SESSION_PREFIX}{session_id}"

        session = Session(
            id=session_id,
            project_path=project_path,
            project_name=project_path.name,
            task_description=task_description,
            git_branch=git_branch or self._detect_git_branch(project_path),
            tmux_session=tmux_name,
        )

        # Create tmux session running the wrapper
        wrapper_cmd = self._build_wrapper_command(session)
        self.tmux.create_session(tmux_name, wrapper_cmd, working_dir=str(project_path))

        self._sessions[session_id] = session
        self._save_session(session)
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and kill its tmux session."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        # Kill tmux session
        self.tmux.kill_session(session.tmux_session)

        # Remove from memory and disk
        del self._sessions[session_id]
        self._delete_session_file(session_id)
        return True

    def list_sessions(self) -> list[Session]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> Session | None:
        """Get a specific session."""
        return self._sessions.get(session_id)

    def get_session_status(self, session_id: str) -> SessionStatus:
        """Read current status from the session's status file."""
        status_path = STATUS_DIR / f"{session_id}.json"
        if not status_path.exists():
            return SessionStatus(state=SessionState.UNKNOWN)

        try:
            data = json.loads(status_path.read_text())
            return SessionStatus.model_validate(data)
        except Exception:
            return SessionStatus(state=SessionState.UNKNOWN)

    def send_input(self, session_id: str, text: str) -> bool:
        """Send input to a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        self.tmux.send_keys(session.tmux_session, text)
        return True

    def get_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session."""
        session = self._sessions.get(session_id)
        if not session:
            return ""
        return self.tmux.capture_pane(session.tmux_session, lines)

    def reconnect_orphaned_sessions(self) -> int:
        """Find tmux sessions without metadata and reconnect them."""
        count = 0
        for tmux_session in self.tmux.list_sessions(TMUX_SESSION_PREFIX):
            # Extract session ID from tmux name
            session_id = tmux_session.replace(TMUX_SESSION_PREFIX, "")
            if session_id not in self._sessions:
                # Create minimal session metadata
                session = Session(
                    id=session_id,
                    project_path=Path.cwd(),
                    project_name="unknown",
                    task_description="(reconnected session)",
                    tmux_session=tmux_session,
                )
                self._sessions[session_id] = session
                self._save_session(session)
                count += 1
        return count

    def _detect_git_branch(self, project_path: Path) -> str:
        """Detect current git branch in project."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return ""

    def _build_wrapper_command(self, session: Session) -> str:
        """Build the command to run in tmux."""
        # Use the installed wrapper script
        return f"cc-wrapper --session-id {session.id}"
