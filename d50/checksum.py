"""Roland checksum calculation and validation."""

from __future__ import annotations

from collections.abc import Iterable


def roland_checksum(address: Iterable[int], data: Iterable[int]) -> int:
    values = [*address, *data]
    if any(not 0 <= value <= 0x7F for value in values):
        raise ValueError("Roland-Prüfsummenwerte müssen 7-Bit-Daten sein")
    return (128 - (sum(values) % 128)) % 128


def checksum_is_valid(address: Iterable[int], data: Iterable[int], checksum: int) -> bool:
    return 0 <= checksum <= 0x7F and roland_checksum(address, data) == checksum

