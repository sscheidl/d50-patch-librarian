from d50.addresses import add_to_address, slot_base
from d50.classifier import classify
from d50.sysex_frames import build_dt1_frame
from domain.enums import DumpType


def test_classifies_golden_files(fixture_dir) -> None:
    expectations = {
        "valid_full_bank.syx": DumpType.D50_FULL_BANK,
        "valid_partial_bank.syx": DumpType.D50_PARTIAL_BANK,
        "valid_generated_single.syx": DumpType.D50_SINGLE_PATCH_TEMP,
        "corrupt_checksum.syx": DumpType.D50_CORRUPT,
        "corrupt_truncated.syx": DumpType.D50_CORRUPT,
        "foreign_sysex.syx": DumpType.FOREIGN_SYSEX,
    }
    for filename, expected in expectations.items():
        assert classify((fixture_dir / filename).read_bytes()).dump_type == expected


def test_classifies_memory_single() -> None:
    raw = bytes(448)
    base = slot_base(7)
    frames = b"".join(
        build_dt1_frame(
            # Split at 256 while keeping correct 7-bit address arithmetic.
            add_to_address(base, offset),
            raw[offset : offset + 256],
        )
        for offset in (0, 256)
    )
    assert classify(frames).dump_type == DumpType.D50_SINGLE_PATCH_MEMORY


def test_classifies_other_roland_model_and_not_sysex() -> None:
    frame = bytearray(build_dt1_frame((0, 0, 0), bytes(64)))
    frame[3] = 0x15
    assert classify(bytes(frame)).dump_type == DumpType.ROLAND_OTHER_MODEL
    assert classify(b"plain text").dump_type == DumpType.NOT_SYSEX


def test_valid_unknown_d50_command_is_not_imported_as_dt1() -> None:
    raw = bytes([0xF0, 0x41, 0x10, 0x14, 0x11, 0, 0, 0, 0, 0xF7])
    result = classify(raw)
    assert result.dump_type == DumpType.D50_VALID_OTHER
    assert "nicht unterstützte" in result.issues[0]
