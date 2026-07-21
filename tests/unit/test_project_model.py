from __future__ import annotations

import pytest

from d50.bank_codec import bank_payload, parse_bank
from d50.patch_codec import create_init_patch
from d50.single_patch_codec import parse_single_patch
from domain.enums import ReverbStatus
from domain.project import BankProject, ProjectExportError
from domain.reverb import D50Reverb
from services.bank_editor_service import BankEditorService


def test_empty_project_uses_device_id_zero_by_default() -> None:
    assert BankProject.empty().device_id == 0x00


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
    init_patch = create_init_patch(source_device_id=project.device_id)
    filled = project.to_bank(fill_patch=init_patch)
    assert filled.patches[0].raw == init_patch.raw
    assert filled.patches[1].name == "INIT SAW"
    assert project.slots[0] is None


def test_built_in_init_saw_is_audible_neutral_and_uses_one_partial() -> None:
    patch = create_init_patch(source_device_id=0x10)
    assert patch.name == "INIT SAW"
    assert patch.upper_tone_name == "INIT SAW"
    assert patch.lower_tone_name == "INIT OFF"
    assert patch.source_bank == "Built-in INIT SAW"

    assert patch.raw[0x00] == 24  # normal coarse pitch
    assert patch.raw[0x01] == 50  # fine tune 0
    assert patch.raw[0x02] == 11  # pitch keyfollow 1:1
    assert patch.raw[0x06] == 1  # sawtooth
    assert patch.raw[0x0D] == 100  # filter fully open
    assert patch.raw[0x0E] == 0  # resonance off
    assert patch.raw[0x12] == 0  # no TVF envelope modulation
    assert patch.raw[0x23] == 100  # audible TVA level
    assert patch.raw[0x27] == 0  # immediate attack
    assert patch.raw[0x30] == 0  # envelope end level
    assert patch.raw[0x34] == 0  # no TVA LFO modulation

    assert patch.raw[0x80 + 0x2D] == 0  # Upper chorus dry/off
    assert patch.raw[0x80 + 0x2E] == 1  # only Upper Partial 1 active
    assert patch.raw[0x80 + 0x2F] == 50  # neutral Partial balance
    assert patch.raw[0x140 + 0x2D] == 0  # Lower chorus dry/off
    assert patch.raw[0x140 + 0x2E] == 0  # both Lower Partials inactive

    assert patch.raw[0x180 + 0x12] == 0  # Whole mode
    assert patch.raw[0x180 + 0x16] == 24  # neutral Upper key shift
    assert patch.raw[0x180 + 0x18] == 50  # neutral Upper fine tune
    assert patch.raw[0x180 + 0x1A] == 0  # pitch bender off
    assert patch.raw[0x180 + 0x1B] == 12  # neutral aftertouch pitch
    assert patch.reverb_type == 1
    assert patch.reverb_balance == 0
    assert patch.raw[0x180 + 0x20] == 100  # normal total volume
    assert patch.raw[0x180 + 0x21] == 50  # neutral tone balance


def test_initialize_slots_uses_fresh_init_entries_and_is_undoable(valid_bank_bytes: bytes) -> None:
    editor = BankEditorService(BankProject.from_bank(parse_bank(valid_bank_bytes)))
    original = editor.project.slots[0]
    init_patch = create_init_patch(source_device_id=editor.project.device_id)

    editor.initialize([0, 63], init_patch)
    assert editor.project.slots[0].patch.name == "INIT SAW"  # type: ignore[union-attr]
    assert editor.project.slots[63].patch.raw == init_patch.raw  # type: ignore[union-attr]
    assert editor.project.slots[0].original_position is None  # type: ignore[union-attr]
    assert editor.undo()
    assert editor.project.slots[0] == original


def test_empty_project_requires_reverb_basis_and_fill_patch(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    project = BankProject.empty("Singles")
    project.insert_patches([patch])
    with pytest.raises(ProjectExportError, match="Reverb-Basis"):
        project.to_bank(fill_patch=patch)


def test_reverb_context_detects_matching_missing_and_conflicting_sources(
    valid_bank_bytes: bytes,
    fixture_dir,
) -> None:
    bank = parse_bank(valid_bank_bytes)
    project = BankProject.from_bank(bank)
    project.clear_slots([0, 1])

    changed_raw = bytearray(project.reverbs[23].raw)
    changed_raw[0] ^= 0x01
    project.reverbs[23] = D50Reverb(23, bytes(changed_raw))
    project.insert_patches([bank.patches[22]], start_index=0)
    assert project.slots[0].patch.reverb_status == ReverbStatus.CONFLICT  # type: ignore[union-attr]
    assert project.reverb_conflict_count == 1

    unknown_source = parse_single_patch((fixture_dir / "d50_patch_reverb_23.syx").read_bytes())
    project.insert_patches([unknown_source], start_index=1)
    assert project.slots[1].patch.reverb_status == ReverbStatus.SOURCE_MISSING  # type: ignore[union-attr]
    assert project.reverb_missing_count == 1

    project.set_reverbs(bank.reverbs)
    assert project.slots[0].patch.reverb_status == ReverbStatus.RESOLVED  # type: ignore[union-attr]
    assert project.slots[1].patch.reverb_status == ReverbStatus.SOURCE_MISSING  # type: ignore[union-attr]
    assert project.reverb_conflict_count == 0


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
