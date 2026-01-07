"""Shared regex patterns for Claude Code status detection.

This module is the single source of truth for status detection patterns.
Used by both the wrapper script and the TUI.
"""

import re
from typing import List, Pattern

# Patterns that indicate Claude is waiting for user input
WAITING_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^>\s*$"),  # Claude Code prompt
    re.compile(r"^\?\s"),  # Question prompt
    re.compile(r"^Do you want to"),
    re.compile(r"^Would you like"),
    re.compile(r"^Press Enter"),
    re.compile(r"\[Y/n\]"),
    re.compile(r"\[y/N\]"),
]

# Patterns that indicate Claude is actively working
WORKING_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^Reading\s"),
    re.compile(r"^Writing\s"),
    re.compile(r"^Editing\s"),
    re.compile(r"^Running\s"),
    re.compile(r"^Searching\s"),
    re.compile(r"^\[.*\]"),  # Tool indicators like [Read], [Write], etc.
]

# Patterns that indicate an error occurred
ERROR_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^Error:", re.IGNORECASE),
    re.compile(r"^Failed:", re.IGNORECASE),
    re.compile(r"^Exception:", re.IGNORECASE),
]


def detect_state(line: str, current_state: str = "unknown") -> str:
    """Detect Claude's state from an output line.

    Args:
        line: A line of output from Claude Code
        current_state: The current state (returned if no pattern matches)

    Returns:
        One of: 'waiting', 'working', 'error', or current_state
    """
    line = line.strip()
    if not line:
        return current_state

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
