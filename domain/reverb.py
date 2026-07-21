"""Global, mutable D-50 reverb programs 17 through 32."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class D50Reverb:
    number: int
    raw: bytes

    def __post_init__(self) -> None:
        if not 17 <= self.number <= 32:
            raise ValueError("Reverbnummer muss zwischen 17 und 32 liegen")
        if len(self.raw) != 376:
            raise ValueError(f"Ein D-50-Reverbblock muss 376 Byte enthalten, erhalten: {len(self.raw)}")
        if any(value > 0x7F for value in self.raw):
            raise ValueError("Reverbdaten enthalten ein Byte außerhalb des 7-Bit-Bereichs")

    @property
    def sha256(self) -> str:
        return sha256(self.raw).hexdigest()

