"""GUI by default; Phase-1 diagnostic CLI when arguments are supplied."""

from __future__ import annotations

import sys
from pathlib import Path

from app.cli import main as cli_main
from gui.main_window import run_gui


def main() -> int:
    arguments = sys.argv[1:]
    if len(arguments) == 1:
        candidate = Path(arguments[0])
        if candidate.is_file() and candidate.suffix.casefold() in {".syx", ".d50proj"}:
            return run_gui(candidate)
    if arguments:
        return cli_main()
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
