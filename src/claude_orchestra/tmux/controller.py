"""Tmux session controller using libtmux."""

import libtmux


class TmuxController:
    """Controls tmux sessions for Claude Code instances."""

    def __init__(self):
        self._server: libtmux.Server | None = None

    @property
    def server(self) -> libtmux.Server:
        """Get or create the tmux server connection."""
        if self._server is None:
            self._server = libtmux.Server()
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

        return session

    def kill_session(self, name: str) -> bool:
        """Kill a tmux session by name."""
        try:
            session = self.server.sessions.get(session_name=name)
            if session:
                session.kill()
                return True
        except Exception:
            pass
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
        except Exception:
            pass
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
        except Exception:
            pass
        return ""

    def list_sessions(self, prefix: str = "") -> list[str]:
        """List tmux sessions, optionally filtered by prefix."""
        try:
            sessions = self.server.sessions
            names = [s.name for s in sessions if s.name]
            if prefix:
                names = [n for n in names if n.startswith(prefix)]
            return names
        except Exception:
            return []

    def session_exists(self, name: str) -> bool:
        """Check if a tmux session exists."""
        try:
            session = self.server.sessions.get(session_name=name)
            return session is not None
        except Exception:
            return False
