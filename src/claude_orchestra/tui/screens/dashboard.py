"""Dashboard screen showing all sessions."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...session.manager import SessionManager
from ..widgets.session_row import SessionRow


class DashboardScreen(Screen):
    """Main dashboard showing all Claude Code sessions."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down"),
        Binding("up", "cursor_up", "Up"),
        Binding("enter", "focus_session", "Focus"),
        Binding("n", "new_session", "New Session"),
        Binding("d", "delete_session", "Delete"),
        Binding("e", "edit_task", "Edit Task"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    DashboardScreen {
        background: $surface;
    }

    #dashboard-header {
        height: 3;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }

    #session-list {
        height: 1fr;
        border: solid $primary-background;
        margin: 0 1 1 1;
    }

    #empty-message {
        text-align: center;
        padding: 2;
        color: $text-muted;
    }
    """

    def __init__(self, manager: SessionManager) -> None:
        super().__init__()
        self.manager = manager
        self.selected_index = 0
        self._session_rows: list[SessionRow] = []

    def compose(self) -> ComposeResult:
        yield Header()
        # Mode indicator header
        session_count = len(self.manager.list_sessions())
        yield Static(
            f"[bold green]◉ DASHBOARD[/] │ {session_count} session(s) │ "
            f"[dim]j/k[/] navigate │ [dim]Enter[/] focus │ [dim]n[/] new │ [dim]d[/] delete",
            id="dashboard-header",
        )
        with VerticalScroll(id="session-list"):
            sessions = self.manager.list_sessions()
            if not sessions:
                yield Static(
                    "No sessions. Press [bold]n[/] to create one.",
                    id="empty-message",
                )
            else:
                for i, session in enumerate(sessions):
                    status = self.manager.get_session_status(session.id)
                    row = SessionRow(session, i, status, id=f"session-{session.id}")
                    if i == 0:
                        row.selected = True
                    self._session_rows.append(row)
                    yield row
        yield Footer()

    def on_mount(self) -> None:
        """Set up periodic status refresh."""
        self.set_interval(2.0, self._refresh_statuses)

    def _refresh_statuses(self) -> None:
        """Refresh status for all sessions."""
        for row in self._session_rows:
            status = self.manager.get_session_status(row.session.id)
            row.update_status(status)

    def action_cursor_down(self) -> None:
        """Move selection down."""
        if not self._session_rows:
            return
        self._session_rows[self.selected_index].selected = False
        self.selected_index = min(self.selected_index + 1, len(self._session_rows) - 1)
        self._session_rows[self.selected_index].selected = True
        self._session_rows[self.selected_index].scroll_visible()

    def action_cursor_up(self) -> None:
        """Move selection up."""
        if not self._session_rows:
            return
        self._session_rows[self.selected_index].selected = False
        self.selected_index = max(self.selected_index - 1, 0)
        self._session_rows[self.selected_index].selected = True
        self._session_rows[self.selected_index].scroll_visible()

    def action_focus_session(self) -> None:
        """Enter focus mode for selected session."""
        if not self._session_rows:
            return
        session = self._session_rows[self.selected_index].session
        self.app.push_screen("session", session_id=session.id)

    def action_new_session(self) -> None:
        """Create a new session."""
        self.app.push_screen("new_session")

    def action_delete_session(self) -> None:
        """Delete the selected session."""
        if not self._session_rows:
            return
        session = self._session_rows[self.selected_index].session
        self.app.push_screen("confirm_delete", session_id=session.id)

    def action_edit_task(self) -> None:
        """Edit the selected session's task description."""
        if not self._session_rows:
            return
        session = self._session_rows[self.selected_index].session
        self.app.push_screen("edit_task", session_id=session.id)

    def action_refresh(self) -> None:
        """Force refresh of all sessions."""
        self._refresh_statuses()
        self.notify("Refreshed")

    def action_quit(self) -> None:
        """Quit the orchestrator (sessions continue in tmux)."""
        self.app.exit()

    async def refresh_session_list(self) -> None:
        """Rebuild the session list after changes."""
        # Clear existing rows
        self._session_rows.clear()
        container = self.query_one("#session-list", VerticalScroll)
        await container.remove_children()  # Await ensures widgets removed before mounting

        # Update header with new count
        sessions = self.manager.list_sessions()
        header = self.query_one("#dashboard-header", Static)
        header.update(
            f"[bold green]◉ DASHBOARD[/] │ {len(sessions)} session(s) │ "
            f"[dim]j/k[/] navigate │ [dim]Enter[/] focus │ [dim]n[/] new │ [dim]d[/] delete"
        )

        # Rebuild
        if not sessions:
            container.mount(
                Static(
                    "No sessions. Press [bold]n[/] to create one.",
                    id="empty-message",
                )
            )
        else:
            for i, session in enumerate(sessions):
                status = self.manager.get_session_status(session.id)
                row = SessionRow(session, i, status, id=f"session-{session.id}")
                if i == self.selected_index:
                    row.selected = True
                self._session_rows.append(row)
                container.mount(row)

        # Fix selection if needed
        if self._session_rows:
            self.selected_index = min(self.selected_index, len(self._session_rows) - 1)
