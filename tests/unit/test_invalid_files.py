import pytest

from d50.bank_codec import parse_bank
from d50.checksum import roland_checksum
from d50.classifier import classify
from d50.sysex_frames import build_dt1_frame
from domain.enums import DumpType
from domain.errors import UnsupportedDumpError


def test_conflicting_overlap_is_corrupt() -> None:
    first = build_dt1_frame((2, 0, 0), bytes([1, 2, 3]))
    second = build_dt1_frame((2, 0, 1), bytes([99]))
    result = classify(first + second)
    assert result.dump_type == DumpType.D50_CORRUPT
    assert "widersprüchliche Daten" in result.issues[0]


def test_identical_overlap_is_allowed_but_partial() -> None:
    first = build_dt1_frame((2, 0, 0), bytes([1, 2, 3]))
    second = build_dt1_frame((2, 0, 1), bytes([2]))
    assert classify(first + second).dump_type == DumpType.D50_PARTIAL_BANK


def test_partial_bank_has_concrete_error(fixture_dir) -> None:
    with pytest.raises(UnsupportedDumpError, match="nur einen Teil einer Bank"):
        parse_bank((fixture_dir / "valid_partial_bank.syx").read_bytes())


def test_mixed_device_ids_are_rejected() -> None:
    first = build_dt1_frame((2, 0, 0), bytes([1]), device_id=0x10)
    second = build_dt1_frame((2, 0, 1), bytes([2]), device_id=0x11)
    assert classify(first + second).dump_type == DumpType.D50_CORRUPT


def test_address_outside_d50_map_is_rejected() -> None:
    result = classify(build_dt1_frame((1, 0, 0), bytes([1])))
    assert result.dump_type == DumpType.D50_CORRUPT
    assert "außerhalb" in result.issues[0]
