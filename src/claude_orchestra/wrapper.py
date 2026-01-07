#!/usr/bin/env python3
"""Wrapper script that runs Claude Code and monitors its status.

This script:
1. Launches Claude Code as a subprocess
2. Monitors stdout/stderr for activity patterns
3. Writes status updates to a JSON file for the orchestrator to read
4. Passes through all I/O transparently
"""

import argparse
import json
import os
import pty
import re
import select
import signal
import sys
from datetime import datetime
from pathlib import Path

# Status patterns
WAITING_PATTERNS = [
    re.compile(r"^>\s*$"),  # Claude Code prompt
    re.compile(r"^\?\s"),  # Question prompt
    re.compile(r"^Do you want to"),
    re.compile(r"^Would you like"),
    re.compile(r"^Press Enter"),
    re.compile(r"\[Y/n\]"),
    re.compile(r"\[y/N\]"),
]

WORKING_PATTERNS = [
    re.compile(r"^Reading\s"),
    re.compile(r"^Writing\s"),
    re.compile(r"^Editing\s"),
    re.compile(r"^Running\s"),
    re.compile(r"^Searching\s"),
    re.compile(r"^\[.*\]"),  # Tool indicators
]

ERROR_PATTERNS = [
    re.compile(r"^Error:", re.IGNORECASE),
    re.compile(r"^Failed:", re.IGNORECASE),
    re.compile(r"^Exception:", re.IGNORECASE),
]


class StatusWriter:
    """Writes status updates to a JSON file."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status_dir = Path.home() / ".claude-orchestra" / "status"
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.status_dir / f"{session_id}.json"
        self.last_output = ""
        self.last_update = datetime.now()
        self.state = "unknown"

    def update(self, state: str, last_output: str = "") -> None:
        """Write status update to file."""
        self.state = state
        if last_output:
            # Keep last meaningful line
            self.last_output = last_output.strip()[:200]
        self.last_update = datetime.now()

        status = {
            "state": self.state,
            "last_output": self.last_output,
            "updated_at": self.last_update.isoformat(),
        }

        try:
            self.status_file.write_text(json.dumps(status, indent=2))
        except Exception:
            pass  # Don't crash on status write failures

    def detect_state(self, line: str) -> str:
        """Detect state from an output line."""
        line = line.strip()
        if not line:
            return self.state

        for pattern in WAITING_PATTERNS:
            if pattern.search(line):
                return "waiting"

        for pattern in ERROR_PATTERNS:
            if pattern.search(line):
                return "error"

        for pattern in WORKING_PATTERNS:
            if pattern.search(line):
                return "working"

        # If we're getting output, we're working
        return "working"


def run_wrapper(session_id: str, command: str = "claude") -> int:
    """Run Claude Code with status monitoring."""
    status = StatusWriter(session_id)
    status.update("working", "Starting Claude Code...")

    # Use pty for proper terminal handling
    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # Child process
        os.close(master_fd)
        os.setsid()
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(slave_fd)

        # Exec claude
        os.execlp(command, command)
        sys.exit(1)

    # Parent process
    os.close(slave_fd)

    # Set up signal handling
    def handle_signal(signum: int, frame) -> None:
        os.kill(pid, signum)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Make stdin non-blocking for select
    stdin_fd = sys.stdin.fileno()

    try:
        while True:
            # Wait for input from either stdin or the pty
            rlist, _, _ = select.select([stdin_fd, master_fd], [], [], 1.0)

            if not rlist:
                # Timeout - check if child is still running
                result = os.waitpid(pid, os.WNOHANG)
                if result[0] != 0:
                    break
                continue

            if stdin_fd in rlist:
                # Forward stdin to claude
                try:
                    data = os.read(stdin_fd, 1024)
                    if data:
                        os.write(master_fd, data)
                except OSError:
                    break

            if master_fd in rlist:
                # Read and forward claude output
                try:
                    data = os.read(master_fd, 1024)
                    if data:
                        # Write to stdout
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()

                        # Update status based on output
                        text = data.decode("utf-8", errors="replace")
                        for line in text.split("\n"):
                            if line.strip():
                                new_state = status.detect_state(line)
                                status.update(new_state, line)
                    else:
                        break
                except OSError:
                    break

    except KeyboardInterrupt:
        pass
    finally:
        os.close(master_fd)

    # Wait for child and get exit code
    _, exit_status = os.waitpid(pid, 0)
    exit_code = os.WEXITSTATUS(exit_status) if os.WIFEXITED(exit_status) else 1

    status.update("idle", "Session ended")
    return exit_code


def main() -> None:
    """Entry point for the wrapper script."""
    parser = argparse.ArgumentParser(description="Claude Code session wrapper")
    parser.add_argument(
        "--session-id",
        required=True,
        help="Session ID for status file naming",
    )
    parser.add_argument(
        "--command",
        default="claude",
        help="Command to run (default: claude)",
    )

    args = parser.parse_args()
    sys.exit(run_wrapper(args.session_id, args.command))


if __name__ == "__main__":
    main()
