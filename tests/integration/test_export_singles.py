from pathlib import Path

import pytest

from d50.bank_codec import parse_bank
from d50.single_patch_codec import parse_single_patch
from services.patch_export_service import export_bank_patches


def test_export_all_bank_patches_is_atomic_and_reimportable(tmp_path: Path, valid_bank_bytes: bytes) -> None:
    bank = parse_bank(valid_bank_bytes, label="Golden Bank")
    written = export_bank_patches(bank, tmp_path)
    assert len(written) == 64
    assert written[0].name == "01-1_Golden_Patch_01.syx"
    assert all(path.stat().st_size == 518 for path in written)
    assert parse_single_patch(written[22].read_bytes()).raw == bank.patches[22].raw

    with pytest.raises(FileExistsError):
        export_bank_patches(bank, tmp_path)

