"""Phase-2 bank and patch file workflows with atomic output."""

from __future__ import annotations

from pathlib import Path

from d50.bank_codec import parse_bank, serialize_bank
from d50.single_patch_codec import parse_single_patch, serialize_single_patch
from domain.bank import D50Bank
from domain.patch import D50Patch
from domain.project import BankProject

from .file_service import atomic_write_bytes
from .patch_export_service import safe_filename_component


def load_bank_file(path: str | Path) -> D50Bank:
    source = Path(path)
    return parse_bank(source.read_bytes(), source_path=source)


def load_single_patch_file(path: str | Path) -> D50Patch:
    source = Path(path)
    return parse_single_patch(source.read_bytes(), source_bank=source.stem)


def load_single_patch_files(paths: list[str | Path] | tuple[str | Path, ...]) -> list[D50Patch]:
    return [load_single_patch_file(path) for path in paths]


def save_single_patch_file(
    patch: D50Patch,
    path: str | Path,
    *,
    device_id: int | None = None,
    overwrite: bool = False,
) -> Path:
    return atomic_write_bytes(
        path,
        serialize_single_patch(patch, device_id=device_id),
        overwrite=overwrite,
    )


def save_project_bank_file(
    project: BankProject,
    path: str | Path,
    *,
    fill_patch: D50Patch | None = None,
    overwrite: bool = False,
) -> Path:
    bank = project.to_bank(fill_patch=fill_patch)
    return atomic_write_bytes(path, serialize_bank(bank), overwrite=overwrite)


def export_selected_patch_files(
    project: BankProject,
    indices: list[int] | set[int] | tuple[int, ...],
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    directory = Path(destination) / safe_filename_component(project.label, fallback="D50_Bank")
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index in sorted(set(indices)):
        slot = project.slots[index]
        if slot is None:
            continue
        row, column = divmod(index, 8)
        filename = f"{row + 1:02d}-{column + 1}_{safe_filename_component(slot.patch.name)}.syx"
        written.append(
            save_single_patch_file(
                slot.patch,
                directory / filename,
                device_id=project.device_id,
                overwrite=overwrite,
            )
        )
    return tuple(written)

