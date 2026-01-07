"""Tmux session controller using libtmux."""

import libtmux

from ..logging_config import TmuxError, get_logger

logger = get_logger(__name__)


class TmuxController:
    """Controls tmux sessions for Claude Code instances."""

    def __init__(self):
        self._server: libtmux.Server | None = None

    @property
    def server(self) -> libtmux.Server:
        """Get or create the tmux server connection."""
        if self._server is None:
            try:
                self._server = libtmux.Server()
            except Exception as e:
                logger.error(f"Failed to connect to tmux server: {e}")
                raise TmuxError(f"Cannot connect to tmux server: {e}") from e
        return self._server

    def create_session(
        self,
        name: str,
        command: str,
        working_dir: str | None = None,
    ) -> libtmux.Session:
        """Create a new tmux session running a command."""
        # Kill existing session with same name if it exists
        self.kill_session(name)

        try:
            # Create new session
            session = self.server.new_session(
                session_name=name,
                start_directory=working_dir,
                attach=False,
            )

            # Send the command to run
            window = session.active_window
            pane = window.active_pane
            if pane:
                pane.send_keys(command)

            logger.info(f"Created tmux session '{name}' in {working_dir}")
            return session
        except Exception as e:
            logger.error(f"Failed to create tmux session '{name}': {e}")
            raise TmuxError(f"Failed to create session '{name}': {e}") from e

    def kill_session(self, name: str) -> bool:
        """Kill a tmux session by name."""
        try:
            session = self.server.sessions.get(session_name=name)
            if session:
                session.kill()
                logger.info(f"Killed tmux session '{name}'")
                return True
            return False
        except Exception as e:
            logger.warning(f"Error killing session '{name}': {e}")
            return False

    def send_keys(self, session_name: str, keys: str, enter: bool = True) -> bool:
        """Send keys to a tmux session."""
        try:
            session = self.server.sessions.get(session_name=session_name)
            if session:
                pane = session.active_window.active_pane
                if pane:
                    pane.send_keys(keys, enter=enter)
                    return True
            logger.warning(f"Session '{session_name}' not found for send_keys")
            return False
        except Exception as e:
            logger.error(f"Error sending keys to '{session_name}': {e}")
            return False

    def send_raw_key(self, session_name: str, key: str) -> bool:
        """Send a raw/special key to tmux (C-c, Up, Down, Tab, etc).

        Args:
            session_name: Target tmux session
            key: Tmux key name (e.g., 'C-c', 'Up', 'Down', 'Left', 'Right', 'Tab', 'Enter')
        """
        try:
            session = self.server.sessions.get(session_name=session_name)
            if session:
                pane = session.active_window.active_pane
                if pane:
                    pane.send_keys(key, enter=False, suppress_history=False)
                    return True
            logger.warning(f"Session '{session_name}' not found for send_raw_key")
            return False
        except Exception as e:
            logger.error(f"Error sending raw key to '{session_name}': {e}")
            return False

    def send_text_literal(self, session_name: str, text: str) -> bool:
        """Send text literally without interpreting special characters.

        Use this for pasting code blocks or text that might contain special chars.
        """
        try:
            session = self.server.sessions.get(session_name=session_name)
            if session:
                pane = session.active_window.active_pane
                if pane:
                    pane.send_keys(text, enter=False, literal=True)
                    return True
            logger.warning(f"Session '{session_name}' not found for send_text_literal")
            return False
        except Exception as e:
            logger.error(f"Error sending literal text to '{session_name}': {e}")
            return False

    def capture_pane(self, session_name: str, lines: int = 50) -> str:
        """Capture recent output from a tmux session's pane."""
        try:
            session = self.server.sessions.get(session_name=session_name)
            if session:
                pane = session.active_window.active_pane
                if pane:
                    # Capture last N lines
                    output = pane.capture_pane(start=-lines)
                    return "\n".join(output) if output else ""
            logger.warning(f"Session '{session_name}' not found for capture_pane")
            return ""
        except Exception as e:
            logger.error(f"Error capturing pane from '{session_name}': {e}")
            return ""

    def get_pane_cwd(self, session_name: str) -> str | None:
        """Get the current working directory of a tmux pane.

        Uses tmux's pane_current_path format variable.

        Returns:
            The pane's current working directory, or None if unavailable.
        """
        try:
            session = self.server.sessions.get(session_name=session_name)
            if session:
                pane = session.active_window.active_pane
                if pane:
                    # libtmux pane has pane_current_path attribute
                    cwd = pane.pane_current_path
                    if cwd:
                        logger.debug(f"Pane CWD for '{session_name}': {cwd}")
                        return cwd
            logger.warning(f"Session '{session_name}' not found for get_pane_cwd")
            return None
        except Exception as e:
            logger.error(f"Error getting pane CWD for '{session_name}': {e}")
            return None

    def list_sessions(self, prefix: str = "") -> list[str]:
        """List tmux sessions, optionally filtered by prefix."""
        try:
            sessions = self.server.sessions
            names = [s.name for s in sessions if s.name]
            if prefix:
                names = [n for n in names if n.startswith(prefix)]
            return names
        except Exception as e:
            logger.error(f"Error listing tmux sessions: {e}")
            return []

    def session_exists(self, name: str) -> bool:
        """Check if a tmux session exists."""
        try:
            session = self.server.sessions.get(session_name=name)
            return session is not None
        except Exception as e:
            logger.error(f"Error checking if session '{name}' exists: {e}")
            return False
