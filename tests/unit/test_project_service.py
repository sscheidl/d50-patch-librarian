from __future__ import annotations

import json

import pytest

from d50.bank_codec import parse_bank
from services.project_service import parse_project, serialize_project
from domain.project import BankProject


def test_project_json_roundtrip_preserves_slots_reverbs_and_metadata(valid_bank_bytes: bytes) -> None:
    project = BankProject.from_bank(parse_bank(valid_bank_bytes, label="Golden"))
    project.clear_slots([5, 6])
    project.update_metadata(0, category="Pad", rating=5, notes="Favorit")
    reparsed = parse_project(serialize_project(project))
    assert reparsed.label == "Golden"
    assert reparsed.slots[5] is None
    assert reparsed.slots[0].category == "Pad"  # type: ignore[union-attr]
    assert reparsed.slots[0].rating == 5  # type: ignore[union-attr]
    assert reparsed.slots[0].notes == "Favorit"  # type: ignore[union-attr]
    assert reparsed.slots[0].patch.raw == project.slots[0].patch.raw  # type: ignore[union-attr]
    assert reparsed.reverbs[23].raw == project.reverbs[23].raw


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
