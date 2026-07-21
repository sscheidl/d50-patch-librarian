"""Strict JSON `.d50proj` persistence for editable Phase-2 projects."""

from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any

from app.version import __version__
from d50.patch_codec import decode_patch
from domain.project import BankProject, PatchSlot
from domain.reverb import D50Reverb

from .file_service import atomic_write_bytes

SCHEMA_VERSION = 1


def _encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode_bytes(value: object, *, field: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{field} muss Base64-Text sein")
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{field} enthält ungültige Base64-Daten") from exc


def project_to_dict(project: BankProject) -> dict[str, Any]:
    slots: list[dict[str, Any] | None] = []
    for slot in project.slots:
        if slot is None:
            slots.append(None)
            continue
        patch = slot.patch
        slots.append(
            {
                "raw": _encode_bytes(patch.raw),
                "source_device_id": patch.source_device_id,
                "source_bank": patch.source_bank,
                "source_slot": patch.source_slot,
                "category": slot.category,
                "rating": slot.rating,
                "notes": slot.notes,
                "original_position": slot.original_position,
                "sequence": slot.sequence,
            }
        )
    return {
        "format": "d50proj",
        "schema_version": SCHEMA_VERSION,
        "app_version": __version__,
        "label": project.label,
        "device_id": project.device_id,
        "source_bank_path": project.source_bank_path,
        "next_sequence": project.next_sequence,
        "reverbs": [
            {"number": number, "raw": _encode_bytes(project.reverbs[number].raw)}
            for number in sorted(project.reverbs)
        ],
        "slots": slots,
    }


def project_from_dict(payload: object, *, project_path: str | Path | None = None) -> BankProject:
    if not isinstance(payload, dict):
        raise ValueError("Projektwurzel muss ein JSON-Objekt sein")
    if payload.get("format") != "d50proj":
        raise ValueError("Datei ist kein D-50-Librarian-Projekt")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Nicht unterstützte Projektschema-Version: {payload.get('schema_version')!r}")

    label = payload.get("label")
    if not isinstance(label, str):
        raise ValueError("Projektlabel fehlt oder ist ungültig")
    device_id = payload.get("device_id")
    if not isinstance(device_id, int) or not 0 <= device_id <= 0x1F:
        raise ValueError("Projekt enthält eine ungültige Device ID")

    reverb_payload = payload.get("reverbs")
    if not isinstance(reverb_payload, list):
        raise ValueError("Projekt-Reverb-Liste fehlt")
    reverbs: dict[int, D50Reverb] = {}
    for item in reverb_payload:
        if not isinstance(item, dict) or not isinstance(item.get("number"), int):
            raise ValueError("Ungültiger Reverb-Eintrag")
        number = item["number"]
        if number in reverbs:
            raise ValueError(f"Reverb {number} ist doppelt vorhanden")
        reverbs[number] = D50Reverb(number, _decode_bytes(item.get("raw"), field=f"Reverb {number}"))

    slot_payload = payload.get("slots")
    if not isinstance(slot_payload, list) or len(slot_payload) != 64:
        raise ValueError("Projekt muss genau 64 Sloteinträge enthalten")
    slots: list[PatchSlot | None] = []
    for index, item in enumerate(slot_payload):
        if item is None:
            slots.append(None)
            continue
        if not isinstance(item, dict):
            raise ValueError(f"Ungültiger Sloteintrag {index + 1}")
        raw = _decode_bytes(item.get("raw"), field=f"Slot {index + 1}")
        patch = decode_patch(
            raw,
            source_device_id=item.get("source_device_id"),
            source_bank=item.get("source_bank"),
            source_slot=item.get("source_slot"),
            reverbs=reverbs,
        )
        category = item.get("category", "")
        rating = item.get("rating", 0)
        notes = item.get("notes", "")
        original_position = item.get("original_position")
        sequence = item.get("sequence", index)
        if not isinstance(category, str) or not isinstance(notes, str):
            raise ValueError(f"Ungültige Metadaten in Slot {index + 1}")
        if not isinstance(rating, int) or not isinstance(sequence, int):
            raise ValueError(f"Ungültige Bewertung/Sequenz in Slot {index + 1}")
        if original_position is not None and not isinstance(original_position, int):
            raise ValueError(f"Ungültige Originalposition in Slot {index + 1}")
        slots.append(
            PatchSlot(
                patch=patch,
                category=category,
                rating=rating,
                notes=notes,
                original_position=original_position,
                sequence=sequence,
            )
        )

    source_bank_path = payload.get("source_bank_path")
    if source_bank_path is not None and not isinstance(source_bank_path, str):
        raise ValueError("source_bank_path muss Text oder null sein")
    next_sequence = payload.get("next_sequence", 0)
    if not isinstance(next_sequence, int) or next_sequence < 0:
        raise ValueError("next_sequence ist ungültig")
    return BankProject(
        label=label,
        slots=slots,
        reverbs=reverbs,
        device_id=device_id,
        source_bank_path=source_bank_path,
        project_path=str(Path(project_path).resolve()) if project_path is not None else None,
        next_sequence=next_sequence,
    )


def serialize_project(project: BankProject) -> bytes:
    return (json.dumps(project_to_dict(project), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def parse_project(data: bytes, *, project_path: str | Path | None = None) -> BankProject:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Projektdatei ist kein gültiges UTF-8-JSON: {exc}") from exc
    return project_from_dict(payload, project_path=project_path)


def save_project(project: BankProject, path: str | Path, *, overwrite: bool = True) -> Path:
    target = atomic_write_bytes(path, serialize_project(project), overwrite=overwrite)
    project.project_path = str(target.resolve())
    return target


def load_project(path: str | Path) -> BankProject:
    source = Path(path)
    return parse_project(source.read_bytes(), project_path=source)

