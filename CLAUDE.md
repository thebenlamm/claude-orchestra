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

---

# LLM Conclave MCP Server - Beta Testing

You have access to the `llm-conclave` MCP server (beta). **Act as a beta tester.**

## Your Testing Mission
1. **USE IT PROACTIVELY** - When facing technical decisions, architecture choices, security questions, or any task that could benefit from multiple expert perspectives, invoke the conclave tools
2. **REPORT ALL FEEDBACK** - After each use, note:
   - What worked well
   - What was confusing or unexpected
   - Error messages (exact text)
   - Missing features you wished existed
   - UX friction points
   - Whether the output was actionable

## Available Tools
- `mcp__llm-conclave__llm_conclave_consult` - Fast 4-round expert debate with fixed panel (Security Expert, Architect, Pragmatist). Good for quick decisions.
- `mcp__llm-conclave__llm_conclave_discuss` - **RECOMMENDED** for complex decisions. Supports custom personas and deeper analysis.

## Custom Personas (New!)
`discuss` supports 10 built-in personas: `security`, `performance`, `architect`, `creative`, `skeptic`, `pragmatic`, `qa`, `devops`, `accessibility`, `documentation`

For domain-specific experts, create `~/.llm-conclave/config.json`:
```json
{
  "custom_personas": {
    "healthCoach": {
      "name": "Health Coach",
      "model": "claude-sonnet-4-5",
      "systemPrompt": "You are a certified health coach..."
    }
  },
  "persona_sets": {
    "health": ["healthCoach", "nutritionist", "psychologist"]
  }
}
Use: personas="healthCoach,nutritionist" or personas="@health" (@ expands sets)

When to Test

- Quick architecture decisions → use consult (fixed experts, faster)
- Complex decisions needing specific expertise → use discuss with personas
- Security-sensitive code → use discuss with personas="security,architect,skeptic"
- Non-engineering domains (health, legal, finance) → use discuss with custom personas
- Any "should I do X or Y?" question → either tool works

Feedback Format

After using a tool, report:
Conclave Beta Feedback
- Tool used: [which one]
- Personas (if discuss): [which ones]
- Task: [what you asked]
- Result quality: [1-5 stars + why]
- Response time: [fast/acceptable/slow]
- Issues: [any errors, confusion, missing info]
- Suggestions: [what would make it better]

Be brutally honest - this is how we improve it.
