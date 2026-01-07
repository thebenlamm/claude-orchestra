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
import select
import signal
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .logging_config import get_logger
from .patterns import detect_state

logger = get_logger(__name__)


class StatusWriter:
    """Writes status updates to a JSON file with atomic writes."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status_dir = Path.home() / ".claude-orchestra" / "status"
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.status_dir / f"{session_id}.json"
        self.last_output = ""
        self.last_update = datetime.now()
        self.state = "unknown"

    def update(self, state: str, last_output: str = "") -> None:
        """Write status update to file atomically.

        Uses write-to-temp-then-rename pattern to prevent race conditions.
        """
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
            # Write to temp file first, then atomic rename
            fd, temp_path = tempfile.mkstemp(
                dir=self.status_dir,
                prefix=f".{self.session_id}.",
                suffix=".tmp",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(status, f, indent=2)
                # Atomic rename
                os.rename(temp_path, self.status_file)
            except Exception:
                # Clean up temp file if rename fails
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception as e:
            logger.error(f"Failed to write status for session {self.session_id}: {e}")
            # Don't crash on status write failures, but log them

    def detect_state(self, line: str) -> str:
        """Detect state from an output line using shared patterns."""
        return detect_state(line, self.state)


def run_wrapper(session_id: str, command: str = "claude") -> int:
    """Run Claude Code with status monitoring."""
    logger.info(f"Starting wrapper for session {session_id}, command: {command}")
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
    logger.info(f"Claude process started with PID {pid}")

    # Set up signal handling
    def handle_signal(signum: int, frame) -> None:
        logger.debug(f"Received signal {signum}, forwarding to child {pid}")
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
                    logger.info(f"Child process {pid} exited")
                    break
                continue

            if stdin_fd in rlist:
                # Forward stdin to claude
                try:
                    data = os.read(stdin_fd, 1024)
                    if data:
                        os.write(master_fd, data)
                except OSError as e:
                    logger.error(f"Error reading stdin: {e}")
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
                        logger.debug("EOF from master_fd")
                        break
                except OSError as e:
                    logger.error(f"Error reading from pty: {e}")
                    break

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt")
    finally:
        os.close(master_fd)

    # Wait for child and get exit code
    _, exit_status = os.waitpid(pid, 0)
    exit_code = os.WEXITSTATUS(exit_status) if os.WIFEXITED(exit_status) else 1
    logger.info(f"Wrapper finished with exit code {exit_code}")

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
