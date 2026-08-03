from __future__ import annotations

import json

import pytest

from d50.bank_codec import parse_bank
from domain.enums import ReverbStatus
from services.project_service import parse_project, serialize_project
from domain.project import BankProject
from services.bank_editor_service import BankEditorService


def test_project_json_roundtrip_preserves_slots_reverbs_and_metadata(valid_bank_bytes: bytes) -> None:
    project = BankProject.from_bank(parse_bank(valid_bank_bytes, label="Golden"))
    project.clear_slots([5, 6])
    project.update_metadata(0, category="Pad", rating=6, notes="Favorit")
    reparsed = parse_project(serialize_project(project))
    assert reparsed.label == "Golden"
    assert reparsed.slots[5] is None
    assert reparsed.slots[0].category == "Pad"  # type: ignore[union-attr]
    assert reparsed.slots[0].rating == 6  # type: ignore[union-attr]
    assert reparsed.slots[0].notes == "Favorit"  # type: ignore[union-attr]
    assert reparsed.slots[0].patch.raw == project.slots[0].patch.raw  # type: ignore[union-attr]
    assert reparsed.reverbs[23].raw == project.reverbs[23].raw
    assert reparsed.slots[22].patch.reverb_dependency_hash == project.slots[22].patch.reverb_dependency_hash  # type: ignore[union-attr]
    assert reparsed.slots[22].patch.reverb_status == ReverbStatus.RESOLVED  # type: ignore[union-attr]


def test_project_parser_migrates_legacy_zero_rating(valid_bank_bytes: bytes) -> None:
    project = BankProject.from_bank(parse_bank(valid_bank_bytes, label="Legacy"))
    payload = json.loads(serialize_project(project))
    payload["slots"][0]["rating"] = 0

    reparsed = parse_project(json.dumps(payload).encode("utf-8"))

    assert reparsed.slots[0].rating == 1  # type: ignore[union-attr]


def test_project_parser_rejects_wrong_schema_and_slot_count() -> None:
    payload = {
        "format": "d50proj",
        "schema_version": 99,
        "label": "Bad",
        "device_id": 16,
        "reverbs": [],
        "slots": [],
    }
    with pytest.raises(ValueError, match="schema-Version"):
        parse_project(json.dumps(payload).encode())


def test_reverb_import_does_not_change_project_device_id(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    project = BankProject.empty()
    project.device_id = 7
    editor = BankEditorService(project)

    editor.set_reverbs(bank.reverbs)

    assert project.device_id == 7
    assert project.has_complete_reverbs


def test_combined_patch_and_reverb_import_is_one_undo_step(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    project = BankProject.empty()
    project.device_id = 5
    editor = BankEditorService(project)

    written = editor.import_bank_content(list(bank.patches[:2]), start_index=3, reverbs=bank.reverbs)

    assert written == [3, 4]
    assert project.occupied_count == 2
    assert project.has_complete_reverbs
    assert project.device_id == 5
    assert editor.undo()
    assert project.occupied_count == 0
    assert not project.reverbs
    assert project.device_id == 5
    assert not editor.undo()


def test_failed_combined_import_restores_complete_previous_state(valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes)
    project = BankProject.empty()
    project.device_id = 9
    editor = BankEditorService(project)
    before = project.snapshot()

    with pytest.raises(ValueError, match="alle Programme"):
        editor.import_bank_content(list(bank.patches[:2]), reverbs=bank.reverbs[:-1])

    assert project.snapshot() == before
    assert not editor.dirty
    assert not editor.undo_stack.can_undo


def test_replace_project_can_mark_received_bank_dirty(valid_bank_bytes: bytes) -> None:
    editor = BankEditorService()
    project = BankProject.from_bank(parse_bank(valid_bank_bytes))

    editor.replace_project(project, mark_dirty=True)

    assert editor.project is project
    assert editor.dirty
