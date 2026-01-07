# Claude Orchestra

A terminal TUI for orchestrating multiple Claude Code sessions simultaneously. Run several Claude instances in parallel, monitor their status in real-time, and switch between them instantly.

## Why?

When working on complex projects, you often need multiple Claude Code sessions:
- One refactoring authentication while another writes tests
- One debugging a bug while another implements a feature
- One researching an approach while another implements an alternative

Claude Orchestra lets you manage all of these from a single dashboard, with persistent sessions that survive restarts.

## Features

- **Multi-session management** - Create, monitor, and switch between multiple Claude Code instances
- **Real-time status** - See at a glance which sessions are working, waiting for input, or idle
- **Session persistence** - Sessions run in tmux and survive application restarts
- **Git-aware** - Automatically detects and displays the git branch for each session
- **Focus mode** - Full-screen view with direct input forwarding to any session
- **Vim-style navigation** - Quick keyboard-driven workflow

## Installation

Requires Python 3.10+ and tmux.

```bash
# Clone the repository
git clone https://github.com/your-username/claude-orchestra.git
cd claude-orchestra

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

## Usage

```bash
claude-orchestra
```

### Dashboard Keybindings

| Key | Action |
|-----|--------|
| `j` / `k` | Navigate up/down |
| `Enter` | Focus selected session (full-screen) |
| `n` | Create new session |
| `d` | Delete selected session |
| `e` | Edit task description |
| `r` | Force refresh |
| `q` | Quit (sessions persist) |

### Focus Mode

When you press `Enter` on a session, you enter focus mode:
- All keyboard input is forwarded directly to Claude Code
- Special keys (Ctrl+C, Tab, arrows) work as expected
- Press `Escape` to return to the dashboard

### Session Status Icons

| Icon | Meaning |
|------|---------|
| `...` | Working - Claude is processing |
| `?` | Waiting - Claude needs input |
| `OK` | Idle - Session is ready |
| `!!` | Error - Something went wrong |
| `--` | Unknown - Status unavailable |

## Architecture

```
┌─────────────────────────────────────────┐
│           Textual TUI                   │
│  (Dashboard, Focus Mode, Modals)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Session Manager                 │
│  (Create, Delete, List, Persist)        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Tmux Controller                 │
│  (libtmux wrapper)                      │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│  tmux sessions running cc-wrapper       │
│         ↓                               │
│     Claude Code                         │
└─────────────────────────────────────────┘
```

Each Claude Code instance runs inside a tmux session via a wrapper script (`cc-wrapper`) that monitors output and writes status to JSON files. The TUI polls these status files to display real-time updates.

### Persistence Locations

| Path | Purpose |
|------|---------|
| `~/.claude-orchestra/sessions/` | Session metadata (project, task, branch) |
| `~/.claude-orchestra/status/` | Live status from each session |
| `~/.claude-orchestra/orchestra.log` | Application logs |

## Development

```bash
# Lint
ruff check src/
ruff format src/

# Test
pytest tests/
```

## Requirements

- Python 3.10+
- tmux
- Claude Code CLI (`claude`)

### Python Dependencies

- `textual>=0.47.0` - TUI framework
- `libtmux>=0.37.0` - tmux Python bindings
- `pydantic>=2.0` - Data validation

## How It Works

1. **Session Creation**: When you create a session, Claude Orchestra spawns a tmux session running the `cc-wrapper` script
2. **Status Detection**: The wrapper monitors Claude Code's output for patterns (prompts, working indicators, errors) and writes status to a JSON file
3. **Dashboard Updates**: The TUI polls status files every 2 seconds and updates the display
4. **Input Forwarding**: In focus mode, keystrokes are sent to tmux via `send-keys`, which forwards them to Claude Code
5. **Persistence**: Since sessions live in tmux, they persist even if you quit the TUI. On restart, orphaned sessions are automatically reconnected

## License

MIT
