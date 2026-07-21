"""Helpers for global reverb blocks 17 through 32."""

from __future__ import annotations

from domain.reverb import D50Reverb

from .constants import REVERB_SIZE


def decode_reverb(number: int, raw: bytes) -> D50Reverb:
    if len(raw) != REVERB_SIZE:
        raise ValueError(f"Reverbblock muss {REVERB_SIZE} Byte lang sein")
    return D50Reverb(number, bytes(raw))

