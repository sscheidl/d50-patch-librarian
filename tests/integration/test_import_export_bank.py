from pathlib import Path

from d50.bank_codec import parse_bank, serialize_bank


def test_file_level_bank_roundtrip(tmp_path: Path, valid_bank_bytes: bytes) -> None:
    source = tmp_path / "source.syx"
    target = tmp_path / "canonical.syx"
    source.write_bytes(valid_bank_bytes)
    target.write_bytes(serialize_bank(parse_bank(source.read_bytes(), source_path=source)))
    assert target.read_bytes() == valid_bank_bytes

