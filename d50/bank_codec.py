"""Full D-50 bank import and deterministic canonical export."""

from __future__ import annotations

from pathlib import Path

from domain.bank import D50Bank
from domain.enums import DumpType
from domain.errors import UnsupportedDumpError, ValidationIssue
from domain.reverb import D50Reverb

from .addresses import add_to_address
from .classifier import classify
from .constants import (
    FULL_BANK_PAYLOAD_SIZE,
    FULL_BANK_START,
    MAX_DT1_DATA_BYTES,
    PATCH_COUNT,
    PATCH_MEMORY_START,
    PATCH_SIZE,
    REVERB_COUNT,
    REVERB_MEMORY_START,
    REVERB_SIZE,
)
from .patch_codec import decode_patch
from .sysex_frames import build_dt1_frame


def parse_bank(data: bytes, *, label: str | None = None, source_path: str | Path | None = None) -> D50Bank:
    result = classify(data)
    if result.dump_type != DumpType.D50_FULL_BANK:
        detail = result.issues[0] if result.issues else result.dump_type.value
        if result.dump_type == DumpType.D50_PARTIAL_BANK:
            detail = "Datei enthält nur einen Teil einer Bank"
        raise UnsupportedDumpError(
            ValidationIssue("not_full_bank", f"Keine vollständige D-50-Bank: {detail}")
        )
    assert result.memory is not None and result.device_id is not None

    reverbs = tuple(
        D50Reverb(
            number=17 + index,
            raw=result.memory.read(
                add_to_address(REVERB_MEMORY_START, index * REVERB_SIZE),
                REVERB_SIZE,
            ),
        )
        for index in range(REVERB_COUNT)
    )
    reverb_map = {reverb.number: reverb for reverb in reverbs}
    bank_label = label
    if bank_label is None and source_path is not None:
        bank_label = Path(source_path).stem
    bank_label = bank_label or "Unbenannte Bank"

    patches = tuple(
        decode_patch(
            result.memory.read(add_to_address(PATCH_MEMORY_START, index * PATCH_SIZE), PATCH_SIZE),
            source_device_id=result.device_id,
            source_bank=bank_label,
            source_slot=index,
            reverbs=reverb_map,
        )
        for index in range(PATCH_COUNT)
    )
    return D50Bank(patches, reverbs, result.device_id, bank_label, bytes(data))


def bank_payload(bank: D50Bank) -> bytes:
    payload = b"".join(patch.raw for patch in bank.patches) + b"".join(reverb.raw for reverb in bank.reverbs)
    if len(payload) != FULL_BANK_PAYLOAD_SIZE:
        raise AssertionError("Interner Fehler: Banknutzdaten haben eine unerwartete Länge")
    return payload


def serialize_bank(bank: D50Bank, *, device_id: int | None = None) -> bytes:
    payload = bank_payload(bank)
    selected_device_id = bank.device_id if device_id is None else device_id
    frames: list[bytes] = []
    for offset in range(0, len(payload), MAX_DT1_DATA_BYTES):
        frames.append(
            build_dt1_frame(
                add_to_address(FULL_BANK_START, offset),
                payload[offset : offset + MAX_DT1_DATA_BYTES],
                device_id=selected_device_id,
            )
        )
    return b"".join(frames)
