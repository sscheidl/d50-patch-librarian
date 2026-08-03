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


def create_init_patch(*, source_device_id: int | None = None) -> D50Patch:
    """Create the canonical, audible INIT SAW used throughout the librarian."""
    raw = bytearray(PATCH_SIZE)

    # All four Partial blocks contain a valid, neutral saw. The tone-level mute
    # flags below make only Upper Partial 1 audible. Keeping inactive blocks valid
    # also makes later sound editing predictable.
    partial = _create_init_saw_partial()
    raw[0:64] = partial
    raw[64:128] = partial
    raw[192:256] = partial
    raw[256:320] = partial

    raw[128:192] = _create_init_tone_common("INIT SAW", partial_mute=1)
    raw[320:384] = _create_init_tone_common("INIT OFF", partial_mute=0)
    raw[384:448] = _create_init_patch_common()

    return decode_patch(
        bytes(raw),
        source_device_id=source_device_id,
        source_bank="Built-in INIT SAW",
    )


def _create_init_saw_partial() -> bytes:
    """Return one neutral 64-byte synth Partial using the saw waveform."""
    data = bytearray(64)
    data[0x00] = 24  # normal oscillator octave (Roland factory Init Saw baseline)
    data[0x01] = 50  # fine tune 0
    data[0x02] = 11  # pitch keyfollow 1:1
    data[0x06] = 1  # synthesizer sawtooth
    data[0x09] = 7  # neutral pulse-width velocity modulation
    data[0x0A] = 50  # neutral pulse width (irrelevant for saw)
    data[0x0C] = 7  # neutral pulse-width aftertouch modulation

    data[0x0D] = 100  # TVF cutoff fully open
    data[0x0E] = 0  # resonance off
    data[0x0F] = 11  # TVF keyfollow 1:1
    data[0x10] = 27  # centered TVF bias point
    data[0x11] = 7  # neutral TVF bias level
    data[0x12] = 0  # TVF envelope depth off
    data[0x22] = 7  # neutral TVF aftertouch modulation

    data[0x23] = 100  # TVA level
    data[0x24] = 50  # neutral velocity range
    data[0x25] = 27  # centered TVA bias point
    data[0x26] = 12  # neutral TVA bias level
    data[0x27:0x2C] = bytes((0, 50, 50, 50, 20))  # immediate attack, moderate release
    data[0x2C:0x31] = bytes((100, 100, 100, 100, 0))
    data[0x31] = 0  # envelope velocity follow off
    data[0x32] = 0  # envelope time keyfollow off
    data[0x34] = 0  # TVA LFO depth off
    data[0x35] = 7  # neutral TVA aftertouch modulation
    return bytes(data)


def _create_init_tone_common(name: str, *, partial_mute: int) -> bytes:
    """Return neutral tone-common data with an explicit Partial activation mask."""
    data = bytearray(64)
    data[0:10] = encode_name(name, length=TONE_NAME_LENGTH, field="Tone-Name")
    data[0x0A] = 0  # Structure 1
    data[0x11:0x16] = bytes((50, 50, 50, 50, 50))  # neutral pitch-envelope levels
    data[0x16] = 0  # pitch LFO depth off
    data[0x17] = 0  # lever modulation off
    data[0x18] = 0  # pitch aftertouch modulation off
    data[0x26] = 12  # neutral low EQ gain
    data[0x29] = 12  # neutral high EQ gain
    data[0x2D] = 0  # chorus dry/off
    data[0x2E] = partial_mute
    data[0x2F] = 50  # centered Partial balance
    return bytes(data)


def _create_init_patch_common() -> bytes:
    """Return neutral patch-common data for a Whole-mode, dry INIT SAW."""
    data = bytearray(64)
    data[0:PATCH_NAME_LENGTH] = encode_name(
        "INIT SAW",
        length=PATCH_NAME_LENGTH,
        field="Patchname",
    )
    data[0x12] = 0  # Whole mode: Upper Tone only
    data[0x13] = 24  # neutral split point (unused in Whole mode)
    data[0x16] = 24  # Upper key shift 0
    data[0x17] = 24  # Lower key shift 0
    data[0x18] = 50  # Upper fine tune 0
    data[0x19] = 50  # Lower fine tune 0
    data[0x1A] = 0  # bender range off
    data[0x1B] = 12  # neutral aftertouch pitch
    data[0x1C] = 0  # portamento time 0
    data[0x1D] = 0  # output mode 1
    data[0x1E] = 0  # Reverb Type 1
    data[0x1F] = 0  # reverb dry/off
    data[0x20] = 100  # normal total volume
    data[0x21] = 50  # centered Upper/Lower balance
    return bytes(data)


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
