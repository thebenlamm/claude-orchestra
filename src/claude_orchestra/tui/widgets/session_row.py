"""Session row widget for the dashboard."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from ...session.models import Session, SessionState, SessionStatus


STATUS_ICONS = {
    SessionState.WORKING: "[bold yellow]...[/]",
    SessionState.WAITING: "[bold red]?[/]",
    SessionState.IDLE: "[bold green]OK[/]",
    SessionState.ERROR: "[bold red]!![/]",
    SessionState.UNKNOWN: "[dim]--[/]",
}


class SessionRow(Widget):
    """A single row in the session list."""

    DEFAULT_CSS = """
    SessionRow {
        height: 3;
        padding: 0 1;
        border: solid $primary-background;
    }

    SessionRow:hover {
        background: $boost;
    }

    SessionRow.-selected {
        background: $accent;
        border: solid $accent;
    }

    SessionRow .session-number {
        width: 4;
        text-style: bold;
        color: $text-muted;
    }

    SessionRow .session-project {
        width: 20;
        text-style: bold;
    }

    SessionRow .session-branch {
        width: 15;
        color: $text-muted;
    }

    SessionRow .session-task {
        width: 1fr;
    }

    SessionRow .session-status {
        width: 4;
        text-align: center;
    }

    SessionRow .session-output {
        width: 40;
        color: $text-muted;
    }
    """

    selected: reactive[bool] = reactive(False)

    def __init__(
        self,
        session: Session,
        index: int,
        status: SessionStatus | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.session = session
        self.index = index
        self.status = status or SessionStatus()

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(f"[{self.index + 1}]", classes="session-number")
            yield Static(self.session.display_name, classes="session-project")
            yield Static(
                self.session.git_branch[:12] if self.session.git_branch else "",
                classes="session-branch",
            )
            yield Static(
                self._truncate(self.session.task_description, 30),
                classes="session-task",
            )
            yield Static(STATUS_ICONS[self.status.state], classes="session-status")
            yield Static(
                self._truncate(self.status.last_output, 35),
                classes="session-output",
            )

    def watch_selected(self, selected: bool) -> None:
        self.set_class(selected, "-selected")

    def update_status(self, status: SessionStatus) -> None:
        """Update the displayed status."""
        self.status = status
        # Update status icon
        status_widget = self.query_one(".session-status", Static)
        status_widget.update(STATUS_ICONS[status.state])
        # Update last output
        output_widget = self.query_one(".session-output", Static)
        output_widget.update(self._truncate(status.last_output, 35))

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "..."
