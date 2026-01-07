"""Main Textual application for Claude Orchestra."""

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..session.manager import SessionManager
from .screens.dashboard import DashboardScreen
from .screens.session import SessionScreen


class NewSessionScreen(ModalScreen):
    """Modal for creating a new session."""

    DEFAULT_CSS = """
    NewSessionScreen {
        align: center middle;
    }

    #new-session-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    #new-session-dialog Label {
        margin-bottom: 1;
    }

    #new-session-dialog Input {
        margin-bottom: 1;
    }

    #button-row {
        margin-top: 1;
        height: 3;
    }

    #button-row Button {
        margin-right: 1;
    }
    """

    def __init__(self, manager: SessionManager) -> None:
        super().__init__()
        self.manager = manager

    def compose(self):
        with Vertical(id="new-session-dialog"):
            yield Label("[bold]New Session[/]")
            yield Label("Project path:")
            yield Input(placeholder="~/Workspace/my-project", id="project-path")
            yield Label("Task description:")
            yield Input(placeholder="What are you working on?", id="task-desc")
            with Horizontal(id="button-row"):
                yield Button("Create", variant="primary", id="create-btn")
                yield Button("Cancel", id="cancel-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.pop_screen()
        elif event.button.id == "create-btn":
            project = self.query_one("#project-path", Input).value
            task = self.query_one("#task-desc", Input).value

            if not project:
                self.notify("Project path is required", severity="error")
                return

            try:
                self.manager.create_session(project, task or "(no description)")
                self.app.pop_screen()
                # Refresh dashboard - use get_screen since it's an installed screen
                dashboard = self.app.get_screen("dashboard")
                if isinstance(dashboard, DashboardScreen):
                    await dashboard.refresh_session_list()
                self.app.notify(f"Created session for {project}")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")


class ConfirmDeleteScreen(ModalScreen):
    """Modal for confirming session deletion."""

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }

    #delete-dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $error;
    }

    #button-row {
        margin-top: 1;
        height: 3;
    }

    #button-row Button {
        margin-right: 1;
    }
    """

    def __init__(self, manager: SessionManager, session_id: str) -> None:
        super().__init__()
        self.manager = manager
        self.session_id = session_id
        self.session = manager.get_session(session_id)

    def compose(self):
        with Vertical(id="delete-dialog"):
            yield Label("[bold red]Delete Session?[/]")
            if self.session:
                yield Static(f"Project: {self.session.display_name}")
                yield Static(f"Task: {self.session.task_description}")
            yield Static("\nThis will kill the tmux session.")
            with Horizontal(id="button-row"):
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", id="cancel-btn")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.app.pop_screen()
        elif event.button.id == "delete-btn":
            self.manager.delete_session(self.session_id)
            self.app.pop_screen()
            # Refresh dashboard - use get_screen since it's an installed screen
            dashboard = self.app.get_screen("dashboard")
            if isinstance(dashboard, DashboardScreen):
                await dashboard.refresh_session_list()
            self.app.notify("Session deleted")


class OrchestraApp(App):
    """Main Claude Orchestra application."""

    TITLE = "Claude Orchestra"
    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.manager = SessionManager()

    def on_mount(self) -> None:
        """Set up the application."""
        # Try to reconnect any orphaned sessions
        reconnected = self.manager.reconnect_orphaned_sessions()
        if reconnected:
            self.notify(f"Reconnected {reconnected} orphaned session(s)")

        # Install screens
        self.install_screen(DashboardScreen(self.manager), name="dashboard")

        # Push dashboard as initial screen
        self.push_screen("dashboard")

    def push_screen(self, screen, callback=None, **kwargs) -> None:
        """Override to handle screen creation with arguments."""
        if screen == "session":
            session_id = kwargs.get("session_id")
            if session_id:
                screen_instance = SessionScreen(self.manager, session_id)
                super().push_screen(screen_instance, callback)
                return
        elif screen == "new_session":
            screen_instance = NewSessionScreen(self.manager)
            super().push_screen(screen_instance, callback)
            return
        elif screen == "confirm_delete":
            session_id = kwargs.get("session_id")
            if session_id:
                screen_instance = ConfirmDeleteScreen(self.manager, session_id)
                super().push_screen(screen_instance, callback)
                return

        super().push_screen(screen, callback)
