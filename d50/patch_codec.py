"""Decode and safely rename complete D-50 patches."""

from __future__ import annotations

from dataclasses import replace

from domain.enums import ReverbStatus
from domain.patch import D50Patch
from domain.reverb import D50Reverb

from .charset import decode_name, encode_name
from .constants import (
    LOWER_TONE_NAME_OFFSET,
    PATCH_NAME_LENGTH,
    PATCH_NAME_OFFSET,
    PATCH_SIZE,
    REVERB_BALANCE_OFFSET,
    REVERB_TYPE_OFFSET,
    TONE_NAME_LENGTH,
    UPPER_TONE_NAME_OFFSET,
)


def decode_patch(
    raw: bytes,
    *,
    source_device_id: int | None = None,
    source_bank: str | None = None,
    source_slot: int | None = None,
    reverbs: dict[int, D50Reverb] | None = None,
) -> D50Patch:
    if len(raw) != PATCH_SIZE:
        raise ValueError(f"Ein D-50-Patch muss {PATCH_SIZE} Byte enthalten")
    name = decode_name(raw[PATCH_NAME_OFFSET : PATCH_NAME_OFFSET + PATCH_NAME_LENGTH], field="Patchname")
    upper = decode_name(
        raw[UPPER_TONE_NAME_OFFSET : UPPER_TONE_NAME_OFFSET + TONE_NAME_LENGTH],
        field="Upper Tone-Name",
    )
    lower = decode_name(
        raw[LOWER_TONE_NAME_OFFSET : LOWER_TONE_NAME_OFFSET + TONE_NAME_LENGTH],
        field="Lower Tone-Name",
    )
    reverb_type = raw[REVERB_TYPE_OFFSET] + 1
    if not 1 <= reverb_type <= 32:
        raise ValueError(f"Ungültiger gespeicherter Reverb Type {raw[REVERB_TYPE_OFFSET]}")

    dependency_hash: str | None = None
    if reverb_type <= 16:
        status = ReverbStatus.FIXED_1_16
    elif reverbs and reverb_type in reverbs:
        status = ReverbStatus.SOURCE_AVAILABLE
        dependency_hash = reverbs[reverb_type].sha256
    else:
        status = ReverbStatus.SOURCE_MISSING

    return D50Patch(
        raw=bytes(raw),
        name=name,
        upper_tone_name=upper,
        lower_tone_name=lower,
        reverb_type=reverb_type,
        reverb_balance=raw[REVERB_BALANCE_OFFSET],
        source_device_id=source_device_id,
        source_bank=source_bank,
        source_slot=source_slot,
        reverb_dependency_hash=dependency_hash,
        reverb_status=status,
    )


def rename_patch(patch: D50Patch, new_name: str) -> D50Patch:
    updated = bytearray(patch.raw)
    updated[PATCH_NAME_OFFSET : PATCH_NAME_OFFSET + PATCH_NAME_LENGTH] = encode_name(
        new_name,
        length=PATCH_NAME_LENGTH,
        field="Patchname",
    )
    decoded = decode_patch(
        bytes(updated),
        source_device_id=patch.source_device_id,
        source_bank=patch.source_bank,
        source_slot=patch.source_slot,
    )
    return replace(
        decoded,
        reverb_dependency_hash=patch.reverb_dependency_hash,
        reverb_status=patch.reverb_status,
    )
