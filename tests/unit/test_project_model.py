from __future__ import annotations

import pytest

from d50.bank_codec import bank_payload, parse_bank
from domain.project import BankProject, ProjectExportError
from services.bank_editor_service import BankEditorService


def test_project_from_bank_and_partial_export_rules(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes, label="Original")
    project = BankProject.from_bank(bank)
    assert project.occupied_count == 64
    assert project.has_complete_reverbs
    assert bank_payload(project.to_bank()) == bank_payload(bank)

    project.clear_slots([0, 1])
    assert project.empty_count == 2
    with pytest.raises(ProjectExportError, match="Füllpatch"):
        project.to_bank()
    filled = project.to_bank(fill_patch=bank.patches[2])
    assert filled.patches[0].raw == bank.patches[2].raw
    assert project.slots[0] is None


def test_empty_project_requires_reverb_basis_and_fill_patch(valid_single_bytes: bytes) -> None:
    from d50.single_patch_codec import parse_single_patch

    patch = parse_single_patch(valid_single_bytes)
    project = BankProject.empty("Singles")
    project.insert_patches([patch])
    with pytest.raises(ProjectExportError, match="Reverb-Basis"):
        project.to_bank(fill_patch=patch)


def test_editor_undo_redo_rename_move_sort_and_clear(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    editor = BankEditorService(BankProject.from_bank(bank))
    original_first = editor.project.slots[0]
    original_second = editor.project.slots[1]

    editor.rename(0, "Renamed")
    assert editor.project.slots[0].patch.name == "Renamed"  # type: ignore[union-attr]
    assert editor.undo()
    assert editor.project.slots[0] == original_first
    assert editor.redo()
    assert editor.project.slots[0].patch.name == "Renamed"  # type: ignore[union-attr]

    editor.move_or_swap(0, 1)
    assert editor.project.slots[0] == original_second
    editor.clear([0])
    assert editor.project.slots[0] is None
    assert editor.undo()
    assert editor.project.slots[0] == original_second

    editor.sort("name", reverse=True)
    names = [slot.patch.name for slot in editor.project.slots if slot is not None]
    assert names == sorted(names, key=str.casefold, reverse=True)


def test_copy_cut_paste_duplicate_and_delete_shift(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    editor = BankEditorService(BankProject.from_bank(bank))
    editor.clear([60, 61, 62, 63])
    assert editor.copy([0, 1]) == 2
    assert editor.paste(60) == [60, 61]
    assert editor.project.slots[60].patch.raw == bank.patches[0].raw  # type: ignore[union-attr]
    editor.duplicate(2, 62)
    assert editor.project.slots[62].patch.raw == bank.patches[2].raw  # type: ignore[union-attr]
    assert editor.cut([3]) == 1
    assert editor.project.slots[3] is None
    editor.delete_and_shift(4)
    assert len(editor.project.slots) == 64

