"""Immutable representation of one complete 448-byte D-50 patch."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .enums import ReverbStatus


@dataclass(frozen=True, slots=True)
class D50Patch:
    raw: bytes
    name: str
    upper_tone_name: str
    lower_tone_name: str
    reverb_type: int
    reverb_balance: int
    source_device_id: int | None = None
    source_bank: str | None = None
    source_slot: int | None = None
    reverb_dependency_hash: str | None = None
    reverb_status: ReverbStatus = ReverbStatus.FIXED_1_16

    def __post_init__(self) -> None:
        if len(self.raw) != 448:
            raise ValueError(f"Ein D-50-Patch muss 448 Byte enthalten, erhalten: {len(self.raw)}")
        if any(value > 0x7F for value in self.raw):
            raise ValueError("Patchdaten enthalten ein Byte außerhalb des 7-Bit-Bereichs")
        if not 1 <= self.reverb_type <= 32:
            raise ValueError("Reverb Type muss zwischen 1 und 32 liegen")
        if self.source_device_id is not None and not 0 <= self.source_device_id <= 0x1F:
            raise ValueError("source_device_id muss zwischen 00h und 1Fh liegen")
        if self.source_slot is not None and not 0 <= self.source_slot < 64:
            raise ValueError("source_slot muss zwischen 0 und 63 liegen")

    @property
    def sha256(self) -> str:
        return sha256(self.raw).hexdigest()

    @property
    def slot_label(self) -> str | None:
        if self.source_slot is None:
            return None
        return f"{self.source_slot // 8 + 1}-{self.source_slot % 8 + 1}"
