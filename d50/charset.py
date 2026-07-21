"""D-50 name encoding restricted by the specification."""

from __future__ import annotations

from domain.errors import D50ValidationError, ValidationIssue

ALLOWED_CHARACTERS = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890-"
CHAR_TO_BYTE = {character: index for index, character in enumerate(ALLOWED_CHARACTERS)}
BYTE_TO_CHAR = {index: character for character, index in CHAR_TO_BYTE.items()}
ALLOWED_BYTES = frozenset(BYTE_TO_CHAR)


def validate_name(name: str, *, max_length: int = 18, field: str = "Patchname") -> None:
    if len(name) > max_length:
        raise D50ValidationError(
            ValidationIssue("name_too_long", f"{field} ist länger als {max_length} Zeichen")
        )
    invalid = sorted(set(name) - set(ALLOWED_CHARACTERS))
    if invalid:
        shown = " ".join(repr(character) for character in invalid)
        raise D50ValidationError(
            ValidationIssue("invalid_character", f"{field} enthält unzulässige Zeichen: {shown}")
        )


def encode_name(name: str, *, length: int, field: str) -> bytes:
    validate_name(name, max_length=length, field=field)
    encoded = bytes(CHAR_TO_BYTE[character] for character in name)
    return encoded.ljust(length, b"\x00")


def decode_name(data: bytes, *, field: str) -> str:
    invalid = [(index, value) for index, value in enumerate(data) if value not in ALLOWED_BYTES]
    if invalid:
        index, value = invalid[0]
        raise D50ValidationError(
            ValidationIssue(
                "invalid_name_byte",
                f"{field} enthält ungültiges D-50-Zeichen 0x{value:02X} an Position {index + 1}",
            )
        )
    return "".join(BYTE_TO_CHAR[value] for value in data).rstrip(" ")


def replace_invalid_characters(name: str, replacement: str = "-") -> str:
    if replacement not in ALLOWED_CHARACTERS:
        raise ValueError("Das Ersatzzeichen ist im D-50-Zeichensatz nicht zulässig")
    return "".join(character if character in ALLOWED_CHARACTERS else replacement for character in name)
