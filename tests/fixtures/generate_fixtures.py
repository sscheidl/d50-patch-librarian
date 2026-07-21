"""Generate deterministic binary golden fixtures without using production codec code."""

from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent
DEVICE_ID = 0x10
PATCH_SIZE = 448
REVERB_SIZE = 376
BANK_START = (0x02, 0x00, 0x00)
TEMP_ADDRESSES = (
    (0x00, 0x00, 0x00),
    (0x00, 0x00, 0x40),
    (0x00, 0x01, 0x00),
    (0x00, 0x01, 0x40),
    (0x00, 0x02, 0x00),
    (0x00, 0x02, 0x40),
    (0x00, 0x03, 0x00),
)
D50_CHARACTERS = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890-"


def linear(address: tuple[int, int, int]) -> int:
    return address[0] * 16384 + address[1] * 128 + address[2]


def address(value: int) -> tuple[int, int, int]:
    return (value // 16384, (value // 128) % 128, value % 128)


def frame(start: tuple[int, int, int], data: bytes, *, manufacturer: int = 0x41, model: int = 0x14) -> bytes:
    checksum = (128 - ((sum(start) + sum(data)) % 128)) % 128
    return bytes([0xF0, manufacturer, DEVICE_ID, model, 0x12, *start, *data, checksum, 0xF7])


def padded(text: str, length: int) -> bytes:
    encoded = bytes(D50_CHARACTERS.index(character) for character in text)
    return encoded.ljust(length, b"\x00")


def patch_raw(slot: int, *, reverb_type: int | None = None) -> bytes:
    data = bytearray(((slot * 7 + offset * 3) % 128 for offset in range(PATCH_SIZE)))
    data[128:138] = padded(f"UP{slot + 1:02d}", 10)
    data[320:330] = padded(f"LOW{slot + 1:02d}", 10)
    data[384:402] = padded(f"Golden Patch {slot + 1:02d}", 18)
    data[402] = slot % 4
    selected_reverb = reverb_type if reverb_type is not None else slot % 32 + 1
    data[414] = selected_reverb - 1
    data[415] = slot % 101
    return bytes(data)


def bank_payload() -> bytes:
    patches = b"".join(patch_raw(slot, reverb_type=23 if slot == 22 else None) for slot in range(64))
    reverbs = b"".join(
        bytes(((number * 5 + offset) % 128 for offset in range(REVERB_SIZE)))
        for number in range(17, 33)
    )
    result = patches + reverbs
    assert len(result) == 34_688
    return result


def canonical_bank(payload: bytes) -> bytes:
    start = linear(BANK_START)
    return b"".join(
        frame(address(start + offset), payload[offset : offset + 256])
        for offset in range(0, len(payload), 256)
    )


def canonical_single(raw: bytes) -> bytes:
    return b"".join(
        frame(start, raw[index * 64 : index * 64 + 64])
        for index, start in enumerate(TEMP_ADDRESSES)
    )


def main() -> None:
    payload = bank_payload()
    valid_bank = canonical_bank(payload)
    valid_single = canonical_single(patch_raw(0))
    reverb_23_single = canonical_single(patch_raw(22, reverb_type=23))

    assert len(valid_bank) == 36_048
    assert len(valid_single) == 518

    (FIXTURE_DIR / "valid_full_bank.syx").write_bytes(valid_bank)
    (FIXTURE_DIR / "valid_partial_bank.syx").write_bytes(valid_bank[:266])
    (FIXTURE_DIR / "valid_generated_single.syx").write_bytes(valid_single)
    (FIXTURE_DIR / "d50_patch_reverb_23.syx").write_bytes(reverb_23_single)

    corrupt_checksum = bytearray(valid_single)
    corrupt_checksum[72] ^= 0x01
    (FIXTURE_DIR / "corrupt_checksum.syx").write_bytes(corrupt_checksum)
    (FIXTURE_DIR / "corrupt_truncated.syx").write_bytes(valid_single[:-1])
    (FIXTURE_DIR / "foreign_sysex.syx").write_bytes(frame((0, 0, 0), bytes(64), manufacturer=0x43))


if __name__ == "__main__":
    main()
