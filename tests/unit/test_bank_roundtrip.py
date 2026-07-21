from d50.bank_codec import bank_payload, parse_bank, serialize_bank
from d50.classifier import classify
from d50.constants import CANONICAL_BANK_FILE_SIZE, CANONICAL_BANK_FRAME_COUNT, FULL_BANK_PAYLOAD_SIZE
from d50.single_patch_codec import parse_single_patch, serialize_single_patch
from d50.sysex_frames import parse_sysex_stream
from domain.bank import D50Bank
from domain.enums import DumpType, ReverbStatus


def test_golden_bank_decodes_all_content(valid_bank_bytes: bytes) -> None:
    assert len(valid_bank_bytes) == CANONICAL_BANK_FILE_SIZE == 36_048
    result = classify(valid_bank_bytes)
    assert result.dump_type == DumpType.D50_FULL_BANK
    assert result.message_count == CANONICAL_BANK_FRAME_COUNT == 136
    assert result.data_byte_count == FULL_BANK_PAYLOAD_SIZE == 34_688

    bank = parse_bank(valid_bank_bytes, label="Golden Bank")
    assert len(bank.patches) == 64
    assert len(bank.reverbs) == 16
    assert bank.patches[0].name == "Golden Patch 01"
    assert bank.patches[63].name == "Golden Patch 64"
    assert bank.patches[22].reverb_type == 23
    assert bank.patches[22].reverb_status == ReverbStatus.SOURCE_AVAILABLE
    assert bank.patches[22].reverb_dependency_hash == bank.reverbs[6].sha256


def test_bank_canonical_roundtrip_is_memory_identical(valid_bank_bytes: bytes) -> None:
    original = parse_bank(valid_bank_bytes)
    exported = serialize_bank(original)
    reparsed = parse_bank(exported)
    assert len(exported) == 36_048
    assert len(parse_sysex_stream(exported, strict=True).frames) == 136
    assert bank_payload(reparsed) == bank_payload(original)
    assert exported == valid_bank_bytes


def test_bank_can_be_reconstructed_from_64_exported_singles(valid_bank_bytes: bytes) -> None:
    original = parse_bank(valid_bank_bytes)
    imported_patches = tuple(
        parse_single_patch(serialize_single_patch(patch), source_bank="Singles")
        for patch in original.patches
    )
    rebuilt = D50Bank(imported_patches, original.reverbs, original.device_id, "Rebuilt")
    assert bank_payload(parse_bank(serialize_bank(rebuilt))) == bank_payload(original)

