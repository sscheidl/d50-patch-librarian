from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def valid_bank_bytes(fixture_dir: Path) -> bytes:
    return (fixture_dir / "valid_full_bank.syx").read_bytes()


@pytest.fixture(scope="session")
def valid_single_bytes(fixture_dir: Path) -> bytes:
    return (fixture_dir / "valid_generated_single.syx").read_bytes()


@pytest.fixture(scope="session")
def tk_root():
    """Reuse one Tcl interpreter; repeated Tk() creation is flaky on Windows."""
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except tk.TclError:
        pass
