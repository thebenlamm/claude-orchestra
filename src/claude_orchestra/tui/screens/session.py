"""Session focus screen for interacting with a single session."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

from ...session.manager import SessionManager


class SessionScreen(Screen):
    """Focus mode for a single Claude Code session."""

    BINDINGS = [
        Binding("escape", "back", "Back to Dashboard"),
    ]

    DEFAULT_CSS = """
    SessionScreen {
        background: $surface;
    }

    #session-header {
        height: 3;
        padding: 0 1;
        background: $panel;
    }

    #session-output {
        height: 1fr;
        border: solid $primary-background;
        margin: 0 1;
        padding: 1;
    }

    #session-input {
        height: 3;
        margin: 0 1 1 1;
    }
    """

    def __init__(self, manager: SessionManager, session_id: str) -> None:
        super().__init__()
        self.manager = manager
        self.session_id = session_id
        self.session = manager.get_session(session_id)

    def compose(self) -> ComposeResult:
        yield Header()
        if self.session:
            yield Static(
                f"[bold]{self.session.display_name}[/] | "
                f"[dim]{self.session.git_branch}[/] | "
                f"{self.session.task_description}",
                id="session-header",
            )
        yield RichLog(id="session-output", highlight=True, markup=True)
        yield Input(placeholder="Type message and press Enter...", id="session-input")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the session view."""
        self.query_one(Input).focus()
        self._load_output()
        self.set_interval(1.0, self._refresh_output)

    def _load_output(self) -> None:
        """Load initial output from the session."""
        if not self.session:
            return
        output = self.manager.get_output(self.session_id, lines=100)
        log = self.query_one(RichLog)
        log.clear()
        if output:
            log.write(output)

    def _refresh_output(self) -> None:
        """Refresh output from the session."""
        if not self.session:
            return
        # Get latest output
        output = self.manager.get_output(self.session_id, lines=50)
        log = self.query_one(RichLog)
        log.clear()
        if output:
            log.write(output)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if not event.value:
            return

        # Send to session
        self.manager.send_input(self.session_id, event.value)

        # Clear input
        event.input.value = ""

        # Refresh output after a brief delay
        self.set_timer(0.5, self._refresh_output)

    def action_back(self) -> None:
        """Return to dashboard."""
        self.app.pop_screen()
