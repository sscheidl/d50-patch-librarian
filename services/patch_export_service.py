"""Export complete bank patches as standard seven-message temporary-area files."""

from __future__ import annotations

from pathlib import Path

from d50.single_patch_codec import serialize_single_patch
from domain.bank import D50Bank

from .file_service import atomic_write_bytes


def safe_filename_component(value: str, *, fallback: str = "Patch") -> str:
    cleaned = "".join(character if character.isalnum() or character in " -" else "-" for character in value)
    cleaned = "_".join(cleaned.strip().split())
    cleaned = cleaned.rstrip(". ")
    return cleaned or fallback


def export_bank_patches(
    bank: D50Bank,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    bank_directory = Path(destination) / safe_filename_component(bank.label, fallback="D50_Bank")
    bank_directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index, patch in enumerate(bank.patches):
        row, column = divmod(index, 8)
        filename = f"{row + 1:02d}-{column + 1}_{safe_filename_component(patch.name)}.syx"
        target = bank_directory / filename
        atomic_write_bytes(
            target,
            serialize_single_patch(patch, device_id=bank.device_id),
            overwrite=overwrite,
        )
        written.append(target)
    return tuple(written)

