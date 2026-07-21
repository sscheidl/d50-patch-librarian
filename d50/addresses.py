"""Three-byte Roland 7-bit address arithmetic."""

from __future__ import annotations

from collections.abc import Iterable

from .constants import ADDRESS_SPACE_SIZE, PATCH_MEMORY_START, PATCH_SIZE, REVERB_MEMORY_START, REVERB_SIZE

Address = tuple[int, int, int]


def validate_address(address: Iterable[int]) -> Address:
    values = tuple(address)
    if len(values) != 3:
        raise ValueError("Eine D-50-Adresse muss aus genau drei Bytes bestehen")
    if any(not isinstance(value, int) or not 0 <= value <= 0x7F for value in values):
        raise ValueError("Jedes D-50-Adressbyte muss zwischen 00h und 7Fh liegen")
    return values  # type: ignore[return-value]


def address_to_linear(a: int | Address, b: int | None = None, c: int | None = None) -> int:
    if isinstance(a, tuple):
        aa, bb, cc = validate_address(a)
    else:
        if b is None or c is None:
            raise ValueError("Es werden drei Adressbytes benötigt")
        aa, bb, cc = validate_address((a, b, c))
    return aa * 16384 + bb * 128 + cc


def linear_to_address(value: int) -> Address:
    if not 0 <= value < ADDRESS_SPACE_SIZE:
        raise ValueError("D-50 address outside three-byte 7-bit range")
    return (value // 16384, (value // 128) % 128, value % 128)


def add_to_address(address: Address, amount: int) -> Address:
    return linear_to_address(address_to_linear(address) + amount)


def slot_base(slot_index: int) -> Address:
    if not 0 <= slot_index < 64:
        raise ValueError("Slotindex muss zwischen 0 und 63 liegen")
    return add_to_address(PATCH_MEMORY_START, slot_index * PATCH_SIZE)


def reverb_base(reverb_number: int) -> Address:
    if not 17 <= reverb_number <= 32:
        raise ValueError("Reverbnummer muss zwischen 17 und 32 liegen")
    return add_to_address(REVERB_MEMORY_START, (reverb_number - 17) * REVERB_SIZE)


def format_address(address: Address) -> str:
    return " ".join(f"{value:02X}" for value in validate_address(address))

