from pathlib import Path

from d50.bank_codec import parse_bank
from d50.classifier import classify
from domain.enums import DumpType
from domain.project import BankProject
from services.bank_file_service import export_selected_patch_files, save_project_bank_file


def test_partial_project_exports_complete_bank_with_explicit_fill(tmp_path: Path, valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes, label="Partial")
    project = BankProject.from_bank(bank)
    project.clear_slots([0, 1, 2])
    target = tmp_path / "partial-export.syx"
    save_project_bank_file(project, target, fill_patch=bank.patches[3])
    result = classify(target.read_bytes())
    assert result.dump_type == DumpType.D50_FULL_BANK
    exported = parse_bank(target.read_bytes())
    assert all(exported.patches[index].raw == bank.patches[3].raw for index in (0, 1, 2))
    assert project.empty_count == 3


def test_selected_patch_export_uses_matrix_slot_names(tmp_path: Path, valid_bank_bytes: bytes) -> None:
    project = BankProject.from_bank(parse_bank(valid_bank_bytes, label="Selection"))
    written = export_selected_patch_files(project, [0, 9, 63], tmp_path)
    assert [path.name for path in written] == [
        "01-1_Golden_Patch_01.syx",
        "02-2_Golden_Patch_10.syx",
        "08-8_Golden_Patch_64.syx",
    ]
    assert all(classify(path.read_bytes()).dump_type == DumpType.D50_SINGLE_PATCH_TEMP for path in written)

