"""Tests for Claude Code status detection patterns."""

import pytest

from claude_orchestra.patterns import (
    ERROR_PATTERNS,
    WAITING_PATTERNS,
    WORKING_PATTERNS,
    detect_state,
)


class TestWaitingPatterns:
    """Tests for patterns that detect Claude waiting for input."""

    def test_prompt_detection(self):
        """Should detect the standard Claude Code prompt."""
        assert detect_state("> ") == "waiting"
        assert detect_state(">  ") == "waiting"
        assert detect_state(">") == "waiting"  # Matches ^>\s*$ (zero or more spaces)

    def test_question_prompt(self):
        """Should detect question prompts."""
        assert detect_state("? Do something") == "waiting"
        # Note: "? " alone doesn't match because ^\?\s requires char after space
        assert detect_state("? x") == "waiting"

    def test_confirmation_prompts(self):
        """Should detect confirmation prompts."""
        assert detect_state("Do you want to continue?") == "waiting"
        assert detect_state("Would you like me to proceed?") == "waiting"
        assert detect_state("Press Enter to continue") == "waiting"

    def test_yes_no_prompts(self):
        """Should detect [Y/n] style prompts."""
        assert detect_state("Continue? [Y/n]") == "waiting"
        assert detect_state("Delete file? [y/N]") == "waiting"


class TestWorkingPatterns:
    """Tests for patterns that detect Claude actively working."""

    def test_file_operations(self):
        """Should detect file operation messages."""
        assert detect_state("Reading src/main.py") == "working"
        assert detect_state("Writing output.txt") == "working"
        assert detect_state("Editing config.json") == "working"

    def test_command_execution(self):
        """Should detect command execution."""
        assert detect_state("Running npm install") == "working"
        assert detect_state("Searching for files") == "working"

    def test_tool_indicators(self):
        """Should detect tool usage indicators."""
        assert detect_state("[Read] src/main.py") == "working"
        assert detect_state("[Write] output.txt") == "working"
        assert detect_state("[Bash] npm install") == "working"


class TestErrorPatterns:
    """Tests for patterns that detect errors."""

    def test_error_prefix(self):
        """Should detect error messages."""
        assert detect_state("Error: File not found") == "error"
        assert detect_state("ERROR: Something went wrong") == "error"

    def test_failed_prefix(self):
        """Should detect failure messages."""
        assert detect_state("Failed: Could not connect") == "error"
        assert detect_state("FAILED: Test assertion") == "error"

    def test_exception_prefix(self):
        """Should detect exception messages."""
        assert detect_state("Exception: ValueError") == "error"


class TestDetectState:
    """Tests for the detect_state function."""

    def test_empty_line_keeps_state(self):
        """Empty lines should preserve current state."""
        assert detect_state("", "working") == "working"
        assert detect_state("   ", "waiting") == "waiting"

    def test_whitespace_stripped(self):
        """Should handle lines with leading/trailing whitespace."""
        assert detect_state("  > ") == "waiting"
        assert detect_state("\tReading file\n") == "working"

    def test_default_to_working(self):
        """Unknown output should default to working."""
        assert detect_state("Some random output") == "working"
        assert detect_state("Installing dependencies...") == "working"

    def test_priority_waiting_over_working(self):
        """Waiting patterns should take priority if both match."""
        # A line that could match both should be detected as waiting
        assert detect_state("> ") == "waiting"

    def test_error_detection(self):
        """Error patterns should be detected."""
        assert detect_state("Error: Connection refused") == "error"


class TestPatternCompilation:
    """Tests to ensure patterns are properly compiled."""

    def test_waiting_patterns_compiled(self):
        """All waiting patterns should be compiled regex objects."""
        for pattern in WAITING_PATTERNS:
            assert hasattr(pattern, "search"), f"Pattern {pattern} is not compiled"

    def test_working_patterns_compiled(self):
        """All working patterns should be compiled regex objects."""
        for pattern in WORKING_PATTERNS:
            assert hasattr(pattern, "search"), f"Pattern {pattern} is not compiled"

    def test_error_patterns_compiled(self):
        """All error patterns should be compiled regex objects."""
        for pattern in ERROR_PATTERNS:
            assert hasattr(pattern, "search"), f"Pattern {pattern} is not compiled"
