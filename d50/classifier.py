"""Classify untrusted input by reconstructed D-50 address content."""

from __future__ import annotations

from dataclasses import dataclass

from domain.enums import DumpType
from domain.errors import D50ValidationError

from .addresses import address_to_linear
from .constants import (
    D50_MODEL_ID,
    DT1_COMMAND_ID,
    FULL_BANK_END,
    FULL_BANK_PAYLOAD_SIZE,
    FULL_BANK_START,
    PATCH_MEMORY_END,
    PATCH_MEMORY_START,
    PATCH_SIZE,
    ROLAND_MANUFACTURER_ID,
    TEMP_PATCH_END,
    TEMP_PATCH_START,
)
from .sysex_frames import parse_sysex_stream
from .validator import ReconstructedMemory, reconstruct_messages


@dataclass(frozen=True, slots=True)
class Classification:
    dump_type: DumpType
    message_count: int
    data_byte_count: int = 0
    device_id: int | None = None
    issues: tuple[str, ...] = ()
    memory: ReconstructedMemory | None = None

    @property
    def is_supported(self) -> bool:
        return self.dump_type in {
            DumpType.D50_FULL_BANK,
            DumpType.D50_SINGLE_PATCH_TEMP,
            DumpType.D50_SINGLE_PATCH_MEMORY,
        }


def _range(start: tuple[int, int, int], end: tuple[int, int, int]) -> frozenset[int]:
    return frozenset(range(address_to_linear(start), address_to_linear(end) + 1))


TEMP_ADDRESSES = _range(TEMP_PATCH_START, TEMP_PATCH_END)
FULL_BANK_ADDRESSES = _range(FULL_BANK_START, FULL_BANK_END)
PATCH_MEMORY_ADDRESSES = _range(PATCH_MEMORY_START, PATCH_MEMORY_END)


def _classify_memory(memory: ReconstructedMemory) -> DumpType:
    addresses = memory.addresses
    if addresses == TEMP_ADDRESSES:
        return DumpType.D50_SINGLE_PATCH_TEMP
    if addresses == FULL_BANK_ADDRESSES and len(addresses) == FULL_BANK_PAYLOAD_SIZE:
        return DumpType.D50_FULL_BANK
    if len(addresses) == PATCH_SIZE and addresses <= PATCH_MEMORY_ADDRESSES:
        first = min(addresses)
        expected = frozenset(range(first, first + PATCH_SIZE))
        slot_offset = first - address_to_linear(PATCH_MEMORY_START)
        if addresses == expected and slot_offset % PATCH_SIZE == 0:
            return DumpType.D50_SINGLE_PATCH_MEMORY
    if addresses & FULL_BANK_ADDRESSES:
        return DumpType.D50_PARTIAL_BANK
    return DumpType.D50_VALID_OTHER


def classify(data: bytes) -> Classification:
    stream = parse_sysex_stream(data)
    if not stream.frames:
        return Classification(
            DumpType.NOT_SYSEX,
            0,
            issues=tuple(issue.message for issue in stream.issues) or ("Keine SysEx-Datei",),
        )

    raw_frames = [frame.raw for frame in stream.frames]
    manufacturers = {frame[1] for frame in raw_frames if len(frame) > 1}
    if not manufacturers or manufacturers != {ROLAND_MANUFACTURER_ID}:
        return Classification(
            DumpType.FOREIGN_SYSEX,
            len(raw_frames),
            issues=tuple(issue.message for issue in stream.issues),
        )

    models = {frame[3] for frame in raw_frames if len(frame) > 3}
    if not models or models != {D50_MODEL_ID}:
        return Classification(
            DumpType.ROLAND_OTHER_MODEL,
            len(raw_frames),
            issues=("Roland-SysEx erkannt, aber nicht D-50",),
        )

    if stream.issues:
        return Classification(
            DumpType.D50_CORRUPT,
            len(raw_frames),
            issues=tuple(issue.message for issue in stream.issues),
        )

    commands = {frame[4] for frame in raw_frames if len(frame) > 4}
    if commands != {DT1_COMMAND_ID}:
        return Classification(
            DumpType.D50_VALID_OTHER,
            len(raw_frames),
            issues=("Datei enthält nicht unterstützte D-50-Handshake- oder Command-Daten",),
        )

    try:
        memory = reconstruct_messages(stream.frames)
    except D50ValidationError as exc:
        return Classification(
            DumpType.D50_CORRUPT,
            len(raw_frames),
            issues=(str(exc),),
        )
    return Classification(
        _classify_memory(memory),
        len(raw_frames),
        memory.data_byte_count,
        memory.device_id,
        memory=memory,
    )

