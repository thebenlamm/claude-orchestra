"""Session focus screen for interacting with a single session."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static, TextArea

from ...session.manager import SessionManager

# Map Textual key names to tmux key names
SPECIAL_KEY_MAP = {
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "tab": "Tab",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "delete": "DC",  # tmux name for Delete
    "backspace": "BSpace",
}


class SessionInput(TextArea):
    """Custom TextArea that handles special key forwarding to tmux."""

    def __init__(self, session_screen: "SessionScreen", **kwargs) -> None:
        super().__init__(**kwargs)
        self.session_screen = session_screen

    def on_key(self, event: Key) -> None:
        """Intercept keys before TextArea processes them."""
        # Ctrl+C - send interrupt to tmux
        if event.key == "ctrl+c":
            self.session_screen.send_raw_key("C-c")
            event.prevent_default()
            event.stop()
            return

        # Ctrl+D - send EOF
        if event.key == "ctrl+d":
            self.session_screen.send_raw_key("C-d")
            event.prevent_default()
            event.stop()
            return

        # Ctrl+Z - send suspend
        if event.key == "ctrl+z":
            self.session_screen.send_raw_key("C-z")
            event.prevent_default()
            event.stop()
            return

        # Ctrl+L - send clear screen
        if event.key == "ctrl+l":
            self.session_screen.send_raw_key("C-l")
            event.prevent_default()
            event.stop()
            return

        # Tab - send Tab to tmux for autocomplete
        if event.key == "tab":
            self.session_screen.send_raw_key("Tab")
            event.prevent_default()
            event.stop()
            return

        # Arrow keys - forward to tmux for history/navigation
        if event.key in SPECIAL_KEY_MAP:
            self.session_screen.send_raw_key(SPECIAL_KEY_MAP[event.key])
            event.prevent_default()
            event.stop()
            return

        # Enter - submit input (unless Shift+Enter for literal newline)
        if event.key == "enter":
            self.session_screen.submit_input()
            event.prevent_default()
            event.stop()
            return

        # Shift+Enter - insert literal newline in the input
        if event.key == "shift+enter":
            # Let TextArea handle this normally (inserts newline)
            return


class SessionScreen(Screen):
    """Focus mode for a single Claude Code session."""

    BINDINGS = [
        Binding("escape", "back", "Dashboard", priority=True),
    ]

    DEFAULT_CSS = """
    SessionScreen {
        background: $surface;
    }

    #session-header {
        height: 3;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }

    #mode-indicator {
        background: $success;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    #session-output {
        height: 1fr;
        border: solid $primary-background;
        margin: 0 1;
        padding: 0 1;
        scrollbar-gutter: stable;
    }

    #input-container {
        height: auto;
        min-height: 3;
        max-height: 8;
        margin: 0 1 1 1;
        border: solid $accent;
    }

    #session-input {
        height: auto;
        min-height: 1;
        max-height: 6;
        padding: 0 1;
        border: none;
    }

    #input-hint {
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    """

    def __init__(self, manager: SessionManager, session_id: str) -> None:
        super().__init__()
        self.manager = manager
        self.session_id = session_id
        self.session = manager.get_session(session_id)
        self._last_output_hash = ""  # Track output changes for incremental updates
        self._output_lines: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical():
            # Header with mode indicator
            header_text = ""
            if self.session:
                header_text = (
                    f"[bold cyan]◉ FOCUS[/] │ "
                    f"[bold]{self.session.display_name}[/] │ "
                    f"[dim]{self.session.git_branch or 'no branch'}[/] │ "
                    f"{self.session.task_description}"
                )
            yield Static(header_text, id="session-header")
            yield RichLog(id="session-output", highlight=True, markup=True, auto_scroll=True)
            with Vertical(id="input-container"):
                yield SessionInput(self, id="session-input")
                yield Static(
                    "[dim]Enter[/] send │ [dim]Shift+Enter[/] newline │ "
                    "[dim]↑↓[/] history │ [dim]Tab[/] complete │ "
                    "[dim]Ctrl+C[/] interrupt │ [dim]Esc[/] dashboard",
                    id="input-hint",
                )
            yield Footer()

    def on_mount(self) -> None:
        """Initialize the session view."""
        self.query_one(SessionInput).focus()
        self._load_output()
        # Faster polling for more responsive feel
        self.set_interval(0.25, self._refresh_output)

    def _load_output(self) -> None:
        """Load initial output from the session."""
        if not self.session:
            return
        output = self.manager.get_output(self.session_id, lines=200)
        log = self.query_one(RichLog)
        log.clear()
        if output:
            self._output_lines = output.split("\n")
            self._last_output_hash = hash(output)
            log.write(output)

    def _refresh_output(self) -> None:
        """Refresh output from the session - only updates if changed."""
        if not self.session:
            return

        # Get latest output
        output = self.manager.get_output(self.session_id, lines=200)
        output_hash = hash(output)

        # Skip if nothing changed
        if output_hash == self._last_output_hash:
            return

        self._last_output_hash = output_hash
        log = self.query_one(RichLog)

        # Full refresh - simpler and avoids partial line issues
        log.clear()
        if output:
            log.write(output)

    def submit_input(self) -> None:
        """Submit the current input to the session."""
        input_widget = self.query_one(SessionInput)
        text = input_widget.text.strip()

        if not text:
            # Send just Enter if empty (useful for confirming prompts)
            self.send_raw_key("Enter")
            return

        # For multi-line input, send as literal text then Enter
        if "\n" in text:
            self.manager.send_text_literal(self.session_id, text)
            self.send_raw_key("Enter")
        else:
            # Single line - use regular send
            self.manager.send_input(self.session_id, text)

        # Clear input
        input_widget.clear()

        # Trigger refresh soon
        self.set_timer(0.1, self._refresh_output)

    def send_raw_key(self, key: str) -> None:
        """Send a special key to the tmux session."""
        self.manager.send_raw_key(self.session_id, key)
        # Refresh output after key
        self.set_timer(0.1, self._refresh_output)

    def action_back(self) -> None:
        """Return to dashboard."""
        self.app.pop_screen()
