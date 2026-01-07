# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Orchestra is a terminal TUI for orchestrating multiple Claude Code sessions simultaneously. It uses tmux as a backend for session persistence and a custom wrapper script for status detection.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the TUI
claude-orchestra

# Lint
ruff check src/
ruff format src/
```

## Architecture

### Data Flow
```
OrchestraApp (Textual TUI)
    ↓
SessionManager (session lifecycle, persistence)
    ↓
TmuxController (libtmux wrapper)
    ↓
tmux sessions running cc-wrapper → claude
    ↓
Status files (~/.claude-orchestra/status/{id}.json)
```

### Key Components

**TUI Layer** (`tui/`)
- `app.py`: Main `OrchestraApp` with modal screen routing. Overrides `push_screen()` to pass kwargs to screen constructors.
- `screens/dashboard.py`: Grid view of sessions with j/k navigation, live status refresh every 2s
- `screens/session.py`: Focus mode - full-screen view of single session with input forwarding

**Session Layer** (`session/`)
- `manager.py`: `SessionManager` handles create/delete/list, persists to `~/.claude-orchestra/sessions/`, reads status files
- `models.py`: Pydantic models - `Session` (metadata), `SessionStatus` (wrapper output), `SessionState` enum

**Tmux Layer** (`tmux/`)
- `controller.py`: `TmuxController` wraps libtmux for create_session, send_keys, capture_pane, kill_session

**Wrapper** (`wrapper.py`)
- Runs as `cc-wrapper --session-id {id}` inside tmux
- Uses pty to wrap Claude Code, monitors stdout for patterns
- Writes state to `~/.claude-orchestra/status/{id}.json`
- States: `working` (output activity), `waiting` (prompt detected), `idle`, `error`

### Modal Input Routing

Dashboard mode: orchestrator keybindings (j/k navigate, Enter focus, n new, d delete, q quit)
Focus mode: all input forwarded to session via `tmux send-keys`, Esc returns to dashboard

### Session Lifecycle

1. User presses `n` → `NewSessionScreen` modal
2. `SessionManager.create_session()` creates tmux session running `cc-wrapper`
3. Wrapper starts Claude Code, writes status updates
4. Dashboard polls status files every 2s, updates row widgets
5. On TUI quit, tmux sessions persist; on restart, `reconnect_orphaned_sessions()` recovers them

### Persistence Locations

- `~/.claude-orchestra/sessions/{id}.json` - session metadata (project path, task, branch)
- `~/.claude-orchestra/status/{id}.json` - live status from wrapper (state, last_output)
- tmux sessions named `claude-orchestra-{id}`
