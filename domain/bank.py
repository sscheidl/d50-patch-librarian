"""Complete D-50 bank domain model."""

from __future__ import annotations

from dataclasses import dataclass

from .patch import D50Patch
from .reverb import D50Reverb


@dataclass(frozen=True, slots=True)
class D50Bank:
    patches: tuple[D50Patch, ...]
    reverbs: tuple[D50Reverb, ...]
    device_id: int = 0x10
    label: str = "Unbenannte Bank"
    raw_source: bytes | None = None

    def __post_init__(self) -> None:
        if len(self.patches) != 64:
            raise ValueError(f"Eine vollständige D-50-Bank benötigt 64 Patches, erhalten: {len(self.patches)}")
        if len(self.reverbs) != 16:
            raise ValueError(f"Eine vollständige D-50-Bank benötigt 16 Reverbblöcke, erhalten: {len(self.reverbs)}")
        if not 0 <= self.device_id <= 0x1F:
            raise ValueError("Device ID muss zwischen 00h und 1Fh liegen")
        if tuple(reverb.number for reverb in self.reverbs) != tuple(range(17, 33)):
            raise ValueError("Reverbblöcke müssen lückenlos in der Reihenfolge 17 bis 32 vorliegen")

