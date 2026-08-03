"""Import and canonical seven-frame export of individual D-50 patches."""

from __future__ import annotations

from dataclasses import dataclass

from domain.enums import DumpType
from domain.errors import UnsupportedDumpError, ValidationIssue
from domain.patch import D50Patch

from .addresses import address_to_linear
from .classifier import classify
from .constants import (
    DEFAULT_DEVICE_ID,
    PATCH_BLOCK_SIZE,
    PATCH_MEMORY_START,
    PATCH_SIZE,
    TEMP_PATCH_BLOCK_ADDRESSES,
    TEMP_PATCH_START,
)
from .patch_codec import decode_patch
from .sysex_frames import build_dt1_frame, parse_dt1_frame, parse_sysex_stream


PREVIEW_BLOCK_NAMES = (
    "Upper Partial 1",
    "Upper Partial 2",
    "Upper Common",
    "Lower Partial 1",
    "Lower Partial 2",
    "Lower Common",
    "Patch",
)


@dataclass(frozen=True, slots=True)
class PreviewBlock:
    name: str
    address: tuple[int, int, int]
    device_id: int
    data: bytes
    checksum: int


def parse_single_patch(data: bytes, *, source_bank: str | None = None) -> D50Patch:
    result = classify(data)
    if result.dump_type not in {
        DumpType.D50_SINGLE_PATCH_TEMP,
        DumpType.D50_SINGLE_PATCH_MEMORY,
    }:
        detail = result.issues[0] if result.issues else result.dump_type.value
        raise UnsupportedDumpError(
            ValidationIssue("not_complete_single", f"Kein vollständiger D-50-Einzelpatch: {detail}")
        )
    assert result.memory is not None
    first = min(result.memory.addresses)
    raw = result.memory.read(first, PATCH_SIZE)
    source_slot: int | None = None
    if result.dump_type == DumpType.D50_SINGLE_PATCH_MEMORY:
        source_slot = (first - address_to_linear(PATCH_MEMORY_START)) // PATCH_SIZE
    return decode_patch(
        raw,
        source_device_id=result.device_id,
        source_bank=source_bank,
        source_slot=source_slot,
    )


def serialize_single_patch(patch: D50Patch, *, device_id: int | None = None) -> bytes:
    selected_device_id = (
        device_id
        if device_id is not None
        else patch.source_device_id
        if patch.source_device_id is not None
        else DEFAULT_DEVICE_ID
    )
    frames = []
    for block_index, address in enumerate(TEMP_PATCH_BLOCK_ADDRESSES):
        start = block_index * PATCH_BLOCK_SIZE
        frames.append(
            build_dt1_frame(
                address,
                patch.raw[start : start + PATCH_BLOCK_SIZE],
                device_id=selected_device_id,
            )
        )
    return b"".join(frames)


def extract_preview_blocks(stream: bytes) -> tuple[PreviewBlock, ...]:
    """Return and validate the seven logical Temporary-Area blocks."""
    result = parse_sysex_stream(stream, strict=True)
    if len(result.frames) != len(TEMP_PATCH_BLOCK_ADDRESSES):
        raise ValueError(
            f"Preview-SysEx muss genau sieben DT1-Nachrichten enthalten, erhalten: {len(result.frames)}"
        )
    blocks: list[PreviewBlock] = []
    for index, (frame, name, expected_address) in enumerate(
        zip(result.frames, PREVIEW_BLOCK_NAMES, TEMP_PATCH_BLOCK_ADDRESSES, strict=True),
        start=1,
    ):
        message = parse_dt1_frame(frame, index=index)
        if message.address != expected_address:
            raise ValueError(
                f"Preview-Block {index} hat Adresse {message.address}, erwartet {expected_address}"
            )
        if len(message.data) != PATCH_BLOCK_SIZE:
            raise ValueError(
                f"Preview-Block {index} enthält {len(message.data)} statt {PATCH_BLOCK_SIZE} Datenbytes"
            )
        blocks.append(
            PreviewBlock(
                name=name,
                address=message.address,
                device_id=message.device_id,
                data=message.data,
                checksum=message.checksum,
            )
        )
    if sum(len(block.data) for block in blocks) != PATCH_SIZE:
        raise AssertionError("Preview-Blöcke enthalten nicht exakt 448 Patchbytes")
    return tuple(blocks)
