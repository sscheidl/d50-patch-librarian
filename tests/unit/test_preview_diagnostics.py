from __future__ import annotations

from d50.bank_codec import parse_bank
from d50.checksum import roland_checksum
from d50.constants import PATCH_BLOCK_SIZE, PATCH_SIZE, TEMP_PATCH_BLOCK_ADDRESSES
from d50.single_patch_codec import (
    PREVIEW_BLOCK_NAMES,
    extract_preview_blocks,
    serialize_single_patch,
)
from services.preview_diagnostics import diagnose_bank_preview


def test_preview_blocks_keep_payload_address_device_and_checksum(valid_bank_bytes: bytes) -> None:
    patch = parse_bank(valid_bank_bytes).patches[0]
    stream = serialize_single_patch(patch, device_id=0)
    blocks = extract_preview_blocks(stream)

    assert tuple(block.name for block in blocks) == PREVIEW_BLOCK_NAMES
    assert tuple(block.address for block in blocks) == TEMP_PATCH_BLOCK_ADDRESSES
    assert {block.device_id for block in blocks} == {0}
    assert all(len(block.data) == PATCH_BLOCK_SIZE for block in blocks)
    assert all(0 <= block.checksum <= 0x7F for block in blocks)
    assert all(roland_checksum(block.address, block.data) == block.checksum for block in blocks)
    assert b"".join(block.data for block in blocks) == patch.raw
    assert sum(len(block.data) for block in blocks) == PATCH_SIZE


def test_complete_bank_has_64_lossless_deterministic_preview_roundtrips(valid_bank_bytes: bytes) -> None:
    report = diagnose_bank_preview(parse_bank(valid_bank_bytes, label="64er Diagnose"), device_id=0)

    assert len(report.patches) == 64
    assert report.ok
    assert report.ok_count == 64
    assert report.difference_count == 0
    assert all(patch.ok for patch in report.patches)
    assert report.invalid_count == 0


def test_temporary_serialization_is_byte_deterministic(valid_bank_bytes: bytes) -> None:
    patch = parse_bank(valid_bank_bytes).patches[17]

    first = serialize_single_patch(patch, device_id=0)
    second = serialize_single_patch(patch, device_id=0)

    assert first == second
