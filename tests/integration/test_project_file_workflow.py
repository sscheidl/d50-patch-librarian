from pathlib import Path

from d50.bank_codec import parse_bank
from services.project_service import load_project, save_project
from domain.project import BankProject


def test_project_file_save_load_is_atomic(tmp_path: Path, valid_bank_bytes: bytes) -> None:
    project = BankProject.from_bank(parse_bank(valid_bank_bytes, label="File Test"))
    target = tmp_path / "test.d50proj"
    save_project(project, target)
    loaded = load_project(target)
    assert loaded.label == "File Test"
    assert loaded.project_path == str(target.resolve())
    assert loaded.slots[63].patch.raw == project.slots[63].patch.raw  # type: ignore[union-attr]

