from __future__ import annotations

import json
from pathlib import Path
import sys

from app.cli import main


def test_cli_without_arguments_shows_help_instead_of_error(capsys) -> None:
    result = main([])
    output = capsys.readouterr()
    assert result == 0
    assert "Phase 1 ist ein Diagnoseprogramm" in output.out
    assert output.err == ""


def test_interactive_no_argument_start_waits_for_enter(monkeypatch, capsys) -> None:
    class InteractiveInput:
        @staticmethod
        def isatty() -> bool:
            return True

    prompts: list[str] = []
    monkeypatch.setattr(sys, "argv", ["D50PatchLibrarian.exe"])
    monkeypatch.setattr(sys, "stdin", InteractiveInput())
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt))
    assert main() == 0
    assert prompts == ["\nZum Schließen Eingabetaste drücken ..."]
    assert "Phase 1 ist ein Diagnoseprogramm" in capsys.readouterr().out


def test_cli_inspect_json(fixture_dir: Path, capsys) -> None:
    result = main(["inspect", str(fixture_dir / "valid_generated_single.syx"), "--json"])
    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["classification"] == "D50_SINGLE_PATCH_TEMP"
    assert output["patch"]["name"] == "Golden Patch 01"


def test_cli_returns_nonzero_for_corrupt_file(fixture_dir: Path, capsys) -> None:
    result = main(["inspect", str(fixture_dir / "corrupt_checksum.syx")])
    output = capsys.readouterr().out
    assert result == 2
    assert "D50_CORRUPT" in output


def test_cli_canonicalize_refuses_implicit_overwrite(tmp_path: Path, fixture_dir: Path, capsys) -> None:
    source = fixture_dir / "valid_generated_single.syx"
    target = tmp_path / "single.syx"
    assert main(["canonicalize", str(source), str(target)]) == 0
    assert target.stat().st_size == 518
    assert main(["canonicalize", str(source), str(target)]) == 2
    assert "existiert bereits" in capsys.readouterr().err


def test_cli_diagnoses_all_64_preview_roundtrips(fixture_dir: Path, capsys) -> None:
    result = main(["diagnose-preview-roundtrip", str(fixture_dir / "valid_full_bank.syx")])
    output = capsys.readouterr()

    assert result == 0
    assert "Patches geprüft: 64" in output.out
    assert "Mit Differenz: 0" in output.out
    assert "Ungültig: 0" in output.out
    assert "64 von 64 Patches ohne Roundtrip-Differenz." in output.out
    assert output.err == ""
