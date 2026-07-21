import pytest

from d50.classifier import classify
from d50.patch_codec import rename_patch
from d50.single_patch_codec import parse_single_patch, serialize_single_patch
from d50.sysex_frames import build_dt1_frame, parse_dt1_frame, parse_sysex_stream
from domain.enums import DumpType, ReverbStatus
from domain.errors import D50ValidationError


def test_single_patch_golden_and_roundtrip(valid_single_bytes: bytes) -> None:
    assert len(valid_single_bytes) == 518
    patch = parse_single_patch(valid_single_bytes)
    assert patch.name == "Golden Patch 01"
    assert patch.upper_tone_name == "UP01"
    assert patch.lower_tone_name == "LOW01"
    assert patch.reverb_type == 1
    assert patch.reverb_status == ReverbStatus.FIXED_1_16

    exported = serialize_single_patch(patch)
    assert len(exported) == 518
    assert classify(exported).dump_type == DumpType.D50_SINGLE_PATCH_TEMP
    assert parse_single_patch(exported).raw == patch.raw

    frames = parse_sysex_stream(exported, strict=True).frames
    assert len(frames) == 7
    assert parse_dt1_frame(frames[-1], index=7).address == (0, 3, 0)


def test_reverb_dependency_without_source_is_marked(fixture_dir) -> None:
    patch = parse_single_patch((fixture_dir / "d50_patch_reverb_23.syx").read_bytes())
    assert patch.reverb_type == 23
    assert patch.reverb_status == ReverbStatus.SOURCE_MISSING
    assert patch.reverb_dependency_hash is None


def test_rename_changes_only_name_bytes(valid_single_bytes: bytes) -> None:
    patch = parse_single_patch(valid_single_bytes)
    renamed = rename_patch(patch, "New Name")
    assert renamed.name == "New Name"
    assert renamed.raw[:384] == patch.raw[:384]
    assert renamed.raw[402:] == patch.raw[402:]
    with pytest.raises(D50ValidationError):
        rename_patch(patch, "Not_valid")


def test_rename_preserves_reverb_dependency_metadata(fixture_dir) -> None:
    patch = parse_single_patch((fixture_dir / "d50_patch_reverb_23.syx").read_bytes())
    renamed = rename_patch(patch, "Reverb Patch")
    assert renamed.reverb_status == patch.reverb_status
    assert renamed.reverb_dependency_hash == patch.reverb_dependency_hash


def test_single_roundtrip_preserves_source_device_id(valid_single_bytes: bytes) -> None:
    source = parse_single_patch(valid_single_bytes)
    custom = b"".join(
        build_dt1_frame(
            parse_dt1_frame(frame, index=index).address,
            parse_dt1_frame(frame, index=index).data,
            device_id=0x03,
        )
        for index, frame in enumerate(parse_sysex_stream(valid_single_bytes, strict=True).frames, start=1)
    )
    parsed = parse_single_patch(custom)
    assert parsed.source_device_id == 0x03
    exported_frames = parse_sysex_stream(serialize_single_patch(parsed), strict=True).frames
    assert {parse_dt1_frame(frame, index=index).device_id for index, frame in enumerate(exported_frames, 1)} == {0x03}
