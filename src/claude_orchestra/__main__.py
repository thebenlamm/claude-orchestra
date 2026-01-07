"""Entry point for Claude Orchestra."""

from .tui import OrchestraApp


def main() -> None:
    """Run the Claude Orchestra TUI."""
    app = OrchestraApp()
    app.run()


if __name__ == "__main__":
    main()
