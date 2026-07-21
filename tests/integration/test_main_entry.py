from __future__ import annotations

import sys

import main as app_main


def test_file_argument_routes_to_gui(monkeypatch, fixture_dir) -> None:
    source = fixture_dir / "valid_full_bank.syx"
    opened = []
    monkeypatch.setattr(sys, "argv", ["D50PatchLibrarian.exe", str(source)])
    monkeypatch.setattr(app_main, "run_gui", lambda path=None: opened.append(path) or 0)
    assert app_main.main() == 0
    assert opened == [source]


def test_cli_subcommand_still_routes_to_cli(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["D50PatchLibrarian.exe", "--version"])
    monkeypatch.setattr(app_main, "cli_main", lambda: 7)
    assert app_main.main() == 7

