"""Tests for TmuxController."""

from unittest.mock import MagicMock, patch

import pytest

from claude_orchestra.logging_config import TmuxError
from claude_orchestra.tmux.controller import TmuxController


@pytest.fixture
def mock_server():
    """Create a mock libtmux Server."""
    mock = MagicMock()
    return mock


@pytest.fixture
def controller(mock_server):
    """Create a TmuxController with mocked server."""
    ctrl = TmuxController()
    ctrl._server = mock_server
    return ctrl


class TestServerConnection:
    """Tests for server connection handling."""

    def test_server_lazy_init(self):
        """Server should be lazily initialized."""
        ctrl = TmuxController()
        assert ctrl._server is None

    def test_server_connection_failure(self):
        """Should raise TmuxError when server connection fails."""
        ctrl = TmuxController()

        with patch("libtmux.Server", side_effect=Exception("Connection failed")):
            with pytest.raises(TmuxError, match="Cannot connect to tmux server"):
                _ = ctrl.server


class TestSessionCreation:
    """Tests for session creation."""

    def test_create_session_success(self, controller, mock_server):
        """Should create a new session."""
        mock_session = MagicMock()
        mock_pane = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.new_session.return_value = mock_session
        mock_server.sessions.get.return_value = None  # No existing session

        result = controller.create_session("test-session", "echo hello", "/tmp")

        mock_server.new_session.assert_called_once_with(
            session_name="test-session",
            start_directory="/tmp",
            attach=False,
        )
        mock_pane.send_keys.assert_called_once_with("echo hello")

    def test_create_session_kills_existing(self, controller, mock_server):
        """Should kill existing session with same name."""
        existing_session = MagicMock()
        mock_server.sessions.get.return_value = existing_session

        mock_new_session = MagicMock()
        mock_server.new_session.return_value = mock_new_session

        controller.create_session("test-session", "cmd", "/tmp")

        existing_session.kill.assert_called_once()

    def test_create_session_failure(self, controller, mock_server):
        """Should raise TmuxError on failure."""
        mock_server.sessions.get.return_value = None
        mock_server.new_session.side_effect = Exception("Failed")

        with pytest.raises(TmuxError, match="Failed to create session"):
            controller.create_session("test", "cmd", "/tmp")


class TestSessionKilling:
    """Tests for session killing."""

    def test_kill_existing_session(self, controller, mock_server):
        """Should kill an existing session."""
        mock_session = MagicMock()
        mock_server.sessions.get.return_value = mock_session

        result = controller.kill_session("test-session")

        assert result is True
        mock_session.kill.assert_called_once()

    def test_kill_nonexistent_session(self, controller, mock_server):
        """Should return False for nonexistent session."""
        mock_server.sessions.get.return_value = None

        result = controller.kill_session("nonexistent")

        assert result is False


class TestSendKeys:
    """Tests for sending keys to sessions."""

    def test_send_keys_success(self, controller, mock_server):
        """Should send keys to session."""
        mock_pane = MagicMock()
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.send_keys("test-session", "hello", enter=True)

        assert result is True
        mock_pane.send_keys.assert_called_once_with("hello", enter=True)

    def test_send_keys_no_enter(self, controller, mock_server):
        """Should send keys without enter."""
        mock_pane = MagicMock()
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        controller.send_keys("test-session", "hello", enter=False)

        mock_pane.send_keys.assert_called_once_with("hello", enter=False)

    def test_send_keys_session_not_found(self, controller, mock_server):
        """Should return False when session not found."""
        mock_server.sessions.get.return_value = None

        result = controller.send_keys("nonexistent", "hello")

        assert result is False


class TestSendRawKey:
    """Tests for sending raw/special keys."""

    def test_send_raw_key_ctrl_c(self, controller, mock_server):
        """Should send Ctrl+C to session."""
        mock_pane = MagicMock()
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.send_raw_key("test-session", "C-c")

        assert result is True
        mock_pane.send_keys.assert_called_once_with(
            "C-c", enter=False, suppress_history=False
        )

    def test_send_raw_key_arrow(self, controller, mock_server):
        """Should send arrow keys."""
        mock_pane = MagicMock()
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        controller.send_raw_key("test-session", "Up")

        mock_pane.send_keys.assert_called_once_with(
            "Up", enter=False, suppress_history=False
        )


class TestSendTextLiteral:
    """Tests for sending literal text."""

    def test_send_text_literal(self, controller, mock_server):
        """Should send text with literal flag."""
        mock_pane = MagicMock()
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.send_text_literal("test-session", "code block")

        assert result is True
        mock_pane.send_keys.assert_called_once_with(
            "code block", enter=False, literal=True
        )


class TestCapturePane:
    """Tests for capturing pane output."""

    def test_capture_pane_success(self, controller, mock_server):
        """Should capture pane content."""
        mock_pane = MagicMock()
        mock_pane.capture_pane.return_value = ["line1", "line2", "line3"]
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.capture_pane("test-session", lines=50)

        assert result == "line1\nline2\nline3"
        mock_pane.capture_pane.assert_called_once_with(start=-50)

    def test_capture_pane_empty(self, controller, mock_server):
        """Should handle empty output."""
        mock_pane = MagicMock()
        mock_pane.capture_pane.return_value = []
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.capture_pane("test-session")

        assert result == ""

    def test_capture_pane_session_not_found(self, controller, mock_server):
        """Should return empty string when session not found."""
        mock_server.sessions.get.return_value = None

        result = controller.capture_pane("nonexistent")

        assert result == ""


class TestGetPaneCwd:
    """Tests for getting pane current working directory."""

    def test_get_pane_cwd_success(self, controller, mock_server):
        """Should return pane's CWD."""
        mock_pane = MagicMock()
        mock_pane.pane_current_path = "/home/user/project"
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.get_pane_cwd("test-session")

        assert result == "/home/user/project"

    def test_get_pane_cwd_not_available(self, controller, mock_server):
        """Should return None when CWD not available."""
        mock_pane = MagicMock()
        mock_pane.pane_current_path = None
        mock_session = MagicMock()
        mock_session.active_window.active_pane = mock_pane
        mock_server.sessions.get.return_value = mock_session

        result = controller.get_pane_cwd("test-session")

        assert result is None

    def test_get_pane_cwd_session_not_found(self, controller, mock_server):
        """Should return None when session not found."""
        mock_server.sessions.get.return_value = None

        result = controller.get_pane_cwd("nonexistent")

        assert result is None


class TestListSessions:
    """Tests for listing sessions."""

    def test_list_all_sessions(self, controller, mock_server):
        """Should list all sessions."""
        mock_sessions = [MagicMock(name="session1"), MagicMock(name="session2")]
        mock_sessions[0].name = "session1"
        mock_sessions[1].name = "session2"
        mock_server.sessions = mock_sessions

        result = controller.list_sessions()

        assert result == ["session1", "session2"]

    def test_list_sessions_with_prefix(self, controller, mock_server):
        """Should filter sessions by prefix."""
        mock_sessions = [
            MagicMock(name="claude-orchestra-123"),
            MagicMock(name="other-session"),
        ]
        mock_sessions[0].name = "claude-orchestra-123"
        mock_sessions[1].name = "other-session"
        mock_server.sessions = mock_sessions

        result = controller.list_sessions(prefix="claude-orchestra-")

        assert result == ["claude-orchestra-123"]

    def test_list_sessions_empty(self, controller, mock_server):
        """Should return empty list when no sessions."""
        mock_server.sessions = []

        result = controller.list_sessions()

        assert result == []


class TestSessionExists:
    """Tests for checking session existence."""

    def test_session_exists_true(self, controller, mock_server):
        """Should return True when session exists."""
        mock_server.sessions.get.return_value = MagicMock()

        result = controller.session_exists("test-session")

        assert result is True

    def test_session_exists_false(self, controller, mock_server):
        """Should return False when session doesn't exist."""
        mock_server.sessions.get.return_value = None

        result = controller.session_exists("nonexistent")

        assert result is False
