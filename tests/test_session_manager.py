"""Tests for SessionManager."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_orchestra.logging_config import SessionError
from claude_orchestra.session.manager import SessionManager
from claude_orchestra.session.models import Session, SessionState, SessionStatus


@pytest.fixture
def temp_dirs(tmp_path):
    """Create temporary directories for testing."""
    sessions_dir = tmp_path / "sessions"
    status_dir = tmp_path / "status"
    sessions_dir.mkdir()
    status_dir.mkdir()
    return sessions_dir, status_dir


@pytest.fixture
def mock_tmux():
    """Create a mock TmuxController."""
    mock = MagicMock()
    mock.create_session.return_value = MagicMock()
    mock.kill_session.return_value = True
    mock.list_sessions.return_value = []
    mock.get_pane_cwd.return_value = "/home/user/project"
    return mock


@pytest.fixture
def manager(temp_dirs, mock_tmux):
    """Create a SessionManager with mocked dependencies."""
    sessions_dir, status_dir = temp_dirs

    with patch("claude_orchestra.session.manager.SESSIONS_DIR", sessions_dir):
        with patch("claude_orchestra.session.manager.STATUS_DIR", status_dir):
            with patch("claude_orchestra.session.manager.ensure_dirs"):
                manager = SessionManager(tmux=mock_tmux)
                return manager


class TestSessionCreation:
    """Tests for session creation."""

    def test_create_session_success(self, manager, tmp_path):
        """Should create a session with valid project path."""
        project_path = tmp_path / "my_project"
        project_path.mkdir()

        session = manager.create_session(project_path, "Test task")

        assert session.project_path == project_path
        assert session.task_description == "Test task"
        assert session.id is not None
        assert len(session.id) == 8

    def test_create_session_expands_home(self, manager, mock_tmux):
        """Should expand ~ in project path."""
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "expanduser") as mock_expand:
                mock_expand.return_value = Path("/home/user/project")
                with patch.object(Path, "resolve", return_value=Path("/home/user/project")):
                    # This will fail because path doesn't exist, but we're testing expansion
                    try:
                        manager.create_session("~/project", "Test")
                    except SessionError:
                        pass
                    mock_expand.assert_called()

    def test_create_session_nonexistent_path(self, manager):
        """Should raise error for nonexistent project path."""
        with pytest.raises(SessionError, match="does not exist"):
            manager.create_session("/nonexistent/path", "Test task")

    def test_create_session_calls_tmux(self, manager, mock_tmux, tmp_path):
        """Should create a tmux session."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        manager.create_session(project_path, "Test")

        mock_tmux.create_session.assert_called_once()


class TestSessionDeletion:
    """Tests for session deletion."""

    def test_delete_existing_session(self, manager, mock_tmux, tmp_path):
        """Should delete an existing session."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        session = manager.create_session(project_path, "Test")
        result = manager.delete_session(session.id)

        assert result is True
        assert manager.get_session(session.id) is None
        mock_tmux.kill_session.assert_called()

    def test_delete_nonexistent_session(self, manager):
        """Should return False for nonexistent session."""
        result = manager.delete_session("nonexistent")
        assert result is False


class TestSessionRetrieval:
    """Tests for session retrieval."""

    def test_list_sessions_empty(self, manager):
        """Should return empty list when no sessions."""
        sessions = manager.list_sessions()
        assert sessions == []

    def test_list_sessions_with_data(self, manager, tmp_path):
        """Should return all sessions."""
        project1 = tmp_path / "project1"
        project2 = tmp_path / "project2"
        project1.mkdir()
        project2.mkdir()

        manager.create_session(project1, "Task 1")
        manager.create_session(project2, "Task 2")

        sessions = manager.list_sessions()
        assert len(sessions) == 2

    def test_get_session_exists(self, manager, tmp_path):
        """Should return session by ID."""
        project = tmp_path / "project"
        project.mkdir()

        session = manager.create_session(project, "Test")
        retrieved = manager.get_session(session.id)

        assert retrieved is not None
        assert retrieved.id == session.id

    def test_get_session_not_found(self, manager):
        """Should return None for unknown ID."""
        result = manager.get_session("unknown")
        assert result is None


class TestSessionStatus:
    """Tests for session status reading."""

    def test_get_status_no_file(self, manager):
        """Should return UNKNOWN state when no status file."""
        status = manager.get_session_status("unknown")
        assert status.state == SessionState.UNKNOWN

    def test_get_status_valid_file(self, manager, temp_dirs):
        """Should read status from file."""
        sessions_dir, status_dir = temp_dirs

        # Write a status file
        status_file = status_dir / "test123.json"
        status_data = {
            "state": "working",
            "last_output": "Reading file",
            "updated_at": "2024-01-01T00:00:00",
        }
        status_file.write_text(json.dumps(status_data))

        with patch("claude_orchestra.session.manager.STATUS_DIR", status_dir):
            status = manager.get_session_status("test123")

        assert status.state == SessionState.WORKING
        assert status.last_output == "Reading file"

    def test_get_status_invalid_json(self, manager, temp_dirs):
        """Should return UNKNOWN for invalid JSON."""
        sessions_dir, status_dir = temp_dirs

        status_file = status_dir / "bad.json"
        status_file.write_text("not valid json")

        with patch("claude_orchestra.session.manager.STATUS_DIR", status_dir):
            status = manager.get_session_status("bad")

        assert status.state == SessionState.UNKNOWN


class TestSessionReconnection:
    """Tests for orphaned session reconnection."""

    def test_reconnect_orphaned_sessions(self, manager, mock_tmux):
        """Should reconnect sessions found in tmux."""
        mock_tmux.list_sessions.return_value = ["claude-orchestra-abc123"]
        mock_tmux.get_pane_cwd.return_value = "/home/user/project"

        with patch("claude_orchestra.session.manager.TMUX_SESSION_PREFIX", "claude-orchestra-"):
            count = manager.reconnect_orphaned_sessions()

        assert count == 1
        session = manager.get_session("abc123")
        assert session is not None
        assert session.project_path == Path("/home/user/project")

    def test_reconnect_uses_pane_cwd(self, manager, mock_tmux):
        """Should use tmux pane CWD instead of cwd()."""
        mock_tmux.list_sessions.return_value = ["claude-orchestra-test99"]
        mock_tmux.get_pane_cwd.return_value = "/specific/project/path"

        with patch("claude_orchestra.session.manager.TMUX_SESSION_PREFIX", "claude-orchestra-"):
            manager.reconnect_orphaned_sessions()

        session = manager.get_session("test99")
        assert session.project_path == Path("/specific/project/path")

    def test_reconnect_fallback_when_no_cwd(self, manager, mock_tmux):
        """Should fall back to home when CWD unavailable."""
        mock_tmux.list_sessions.return_value = ["claude-orchestra-nocwd"]
        mock_tmux.get_pane_cwd.return_value = None

        with patch("claude_orchestra.session.manager.TMUX_SESSION_PREFIX", "claude-orchestra-"):
            manager.reconnect_orphaned_sessions()

        session = manager.get_session("nocwd")
        assert session.project_path == Path.home()
        assert session.project_name == "unknown"

    def test_skip_already_known_sessions(self, manager, mock_tmux, tmp_path):
        """Should not reconnect sessions already in memory."""
        project = tmp_path / "project"
        project.mkdir()

        session = manager.create_session(project, "Test")
        mock_tmux.list_sessions.return_value = [session.tmux_session]

        with patch("claude_orchestra.session.manager.TMUX_SESSION_PREFIX", "claude-orchestra-"):
            count = manager.reconnect_orphaned_sessions()

        assert count == 0  # Should not reconnect existing session
