"""Session lifecycle management."""

import json
import uuid
from pathlib import Path

from ..config import SESSIONS_DIR, STATUS_DIR, TMUX_SESSION_PREFIX, ensure_dirs
from ..logging_config import SessionError, get_logger
from ..tmux.controller import TmuxController
from .models import Session, SessionState, SessionStatus

logger = get_logger(__name__)


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
                logger.debug(f"Loaded session {session.id} from {path}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in session file {path}: {e}")
            except Exception as e:
                logger.error(f"Failed to load session from {path}: {e}")

    def _save_session(self, session: Session) -> None:
        """Persist session metadata to disk."""
        path = session.get_session_file()
        try:
            path.write_text(session.model_dump_json(indent=2))
            logger.debug(f"Saved session {session.id} to {path}")
        except Exception as e:
            logger.error(f"Failed to save session {session.id}: {e}")
            raise SessionError(f"Failed to save session: {e}") from e

    def _delete_session_file(self, session_id: str) -> None:
        """Remove session file from disk."""
        path = SESSIONS_DIR / f"{session_id}.json"
        if path.exists():
            try:
                path.unlink()
                logger.debug(f"Deleted session file {path}")
            except Exception as e:
                logger.error(f"Failed to delete session file {path}: {e}")

        status_path = STATUS_DIR / f"{session_id}.json"
        if status_path.exists():
            try:
                status_path.unlink()
                logger.debug(f"Deleted status file {status_path}")
            except Exception as e:
                logger.error(f"Failed to delete status file {status_path}: {e}")

    def create_session(
        self,
        project_path: str | Path,
        task_description: str,
        git_branch: str = "",
    ) -> Session:
        """Create a new Claude Code session."""
        project_path = Path(project_path).expanduser().resolve()

        if not project_path.exists():
            raise SessionError(f"Project path does not exist: {project_path}")

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
        logger.info(f"Created session {session_id} for {project_path}")
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and kill its tmux session."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Cannot delete: session {session_id} not found")
            return False

        # Kill tmux session
        self.tmux.kill_session(session.tmux_session)

        # Remove from memory and disk
        del self._sessions[session_id]
        self._delete_session_file(session_id)
        logger.info(f"Deleted session {session_id}")
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
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in status file for {session_id}: {e}")
            return SessionStatus(state=SessionState.UNKNOWN)
        except Exception as e:
            logger.error(f"Failed to read status for {session_id}: {e}")
            return SessionStatus(state=SessionState.UNKNOWN)

    def send_input(self, session_id: str, text: str) -> bool:
        """Send input to a session."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Cannot send input: session {session_id} not found")
            return False
        return self.tmux.send_keys(session.tmux_session, text)

    def send_raw_key(self, session_id: str, key: str) -> bool:
        """Send a special key to a session (C-c, Up, Down, Tab, etc)."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Cannot send raw key: session {session_id} not found")
            return False
        return self.tmux.send_raw_key(session.tmux_session, key)

    def send_text_literal(self, session_id: str, text: str) -> bool:
        """Send text literally without interpreting special characters."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Cannot send text: session {session_id} not found")
            return False
        return self.tmux.send_text_literal(session.tmux_session, text)

    def get_output(self, session_id: str, lines: int = 50) -> str:
        """Get recent output from a session."""
        session = self._sessions.get(session_id)
        if not session:
            logger.warning(f"Cannot get output: session {session_id} not found")
            return ""
        return self.tmux.capture_pane(session.tmux_session, lines)

    def reconnect_orphaned_sessions(self) -> int:
        """Find tmux sessions without metadata and reconnect them.

        Queries the actual pane CWD from tmux instead of using cwd().
        """
        count = 0
        for tmux_session in self.tmux.list_sessions(TMUX_SESSION_PREFIX):
            # Extract session ID from tmux name
            session_id = tmux_session.replace(TMUX_SESSION_PREFIX, "")
            if session_id not in self._sessions:
                # Get the actual working directory from the tmux pane
                pane_cwd = self.tmux.get_pane_cwd(tmux_session)
                if pane_cwd:
                    project_path = Path(pane_cwd)
                    project_name = project_path.name
                else:
                    # Fallback if we can't get the CWD
                    logger.warning(
                        f"Could not get CWD for orphaned session {session_id}, using home"
                    )
                    project_path = Path.home()
                    project_name = "unknown"

                # Try to detect git branch
                git_branch = self._detect_git_branch(project_path)

                session = Session(
                    id=session_id,
                    project_path=project_path,
                    project_name=project_name,
                    task_description="(reconnected session)",
                    git_branch=git_branch,
                    tmux_session=tmux_session,
                )
                self._sessions[session_id] = session
                self._save_session(session)
                logger.info(f"Reconnected orphaned session {session_id} at {project_path}")
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
        except subprocess.TimeoutExpired:
            logger.warning(f"Git branch detection timed out for {project_path}")
        except Exception as e:
            logger.debug(f"Could not detect git branch for {project_path}: {e}")
        return ""

    def _build_wrapper_command(self, session: Session) -> str:
        """Build the command to run in tmux."""
        # Use the installed wrapper script
        return f"cc-wrapper --session-id {session.id}"
