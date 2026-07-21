import pytest

from d50.charset import decode_name, encode_name, replace_invalid_characters, validate_name
from domain.errors import D50ValidationError


def test_name_roundtrip_and_padding() -> None:
    encoded = encode_name("D-50 Bass", length=18, field="Patchname")
    assert len(encoded) == 18
    assert decode_name(encoded, field="Patchname") == "D-50 Bass"


def test_known_d50_name_encoding_from_real_banks() -> None:
    fantasia = bytes([0x06, 0x1B, 0x28, 0x2E, 0x1B, 0x2D, 0x23, 0x1B])
    assert encode_name("Fantasia", length=8, field="Patchname") == fantasia
    assert decode_name(fantasia, field="Patchname") == "Fantasia"

    neuromancer = bytes(
        [0x0E, 0x05, 0x15, 0x12, 0x0F, 0x0D, 0x01, 0x0E, 0x03, 0x05, 0x12]
    )
    assert decode_name(neuromancer, field="Patchname") == "NEUROMANCER"

    assert encode_name("D-50", length=4, field="Patchname") == bytes(
        [0x04, 0x3F, 0x39, 0x3E]
    )


@pytest.mark.parametrize("name", ["Umlaut Ä", "Slash/", "Emoji 🎹", "Under_score"])
def test_invalid_characters_are_rejected(name: str) -> None:
    with pytest.raises(D50ValidationError, match="unzulässige Zeichen"):
        validate_name(name)


def test_overlength_is_rejected_and_replacement_is_explicit() -> None:
    with pytest.raises(D50ValidationError, match="länger als 18"):
        validate_name("X" * 19)
    assert replace_invalid_characters("Jörg_1") == "J-rg-1"


def test_invalid_imported_name_byte_is_rejected() -> None:
    with pytest.raises(D50ValidationError, match="ungültiges D-50-Zeichen"):
        decode_name(
            encode_name("VALID", length=5, field="Patchname") + bytes([0x40]),
            field="Patchname",
        )
