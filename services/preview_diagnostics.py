"""Read-only diagnostics for D-50 Temporary-Area serialization."""

from __future__ import annotations

from dataclasses import dataclass

from d50.constants import PATCH_BLOCK_SIZE
from d50.single_patch_codec import (
    PREVIEW_BLOCK_NAMES,
    extract_preview_blocks,
    parse_single_patch,
    serialize_single_patch,
)
from domain.bank import D50Bank
from domain.patch import D50Patch


@dataclass(frozen=True, slots=True)
class PreviewDifference:
    block: str
    offset: int
    expected: int
    actual: int


@dataclass(frozen=True, slots=True)
class PatchPreviewDiagnostic:
    slot: str
    patch_name: str
    differences: tuple[PreviewDifference, ...]
    issues: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.differences and not self.issues


@dataclass(frozen=True, slots=True)
class BankPreviewDiagnostic:
    bank_label: str
    patches: tuple[PatchPreviewDiagnostic, ...]

    @property
    def ok_count(self) -> int:
        return sum(patch.ok for patch in self.patches)

    @property
    def difference_count(self) -> int:
        return sum(bool(patch.differences) for patch in self.patches)

    @property
    def invalid_count(self) -> int:
        return sum(bool(patch.issues) for patch in self.patches)

    @property
    def ok(self) -> bool:
        return self.difference_count == 0 and self.invalid_count == 0


def diagnose_patch_preview(
    patch: D50Patch,
    *,
    slot: str,
    device_id: int,
) -> PatchPreviewDiagnostic:
    first = serialize_single_patch(patch, device_id=device_id)
    second = serialize_single_patch(patch, device_id=device_id)
    issues: list[str] = []
    if first != second:
        issues.append("Serialisierung ist bei identischen Eingaben nicht deterministisch")

    blocks = extract_preview_blocks(first)
    if tuple(block.name for block in blocks) != PREVIEW_BLOCK_NAMES:
        issues.append("Preview-Blöcke stehen nicht in der erwarteten Reihenfolge")
    if {block.device_id for block in blocks} != {device_id}:
        issues.append("Preview-Blöcke enthalten eine abweichende Device-ID")

    serialized_raw = b"".join(block.data for block in blocks)
    reparsed_raw = parse_single_patch(first).raw
    actual = reparsed_raw if reparsed_raw != patch.raw else serialized_raw
    differences = tuple(
        PreviewDifference(
            block=PREVIEW_BLOCK_NAMES[offset // PATCH_BLOCK_SIZE],
            offset=offset % PATCH_BLOCK_SIZE,
            expected=expected,
            actual=received,
        )
        for offset, (expected, received) in enumerate(zip(patch.raw, actual, strict=True))
        if expected != received
    )
    return PatchPreviewDiagnostic(slot, patch.name, differences, tuple(issues))


def diagnose_bank_preview(bank: D50Bank, *, device_id: int | None = None) -> BankPreviewDiagnostic:
    selected_device_id = bank.device_id if device_id is None else device_id
    patches = tuple(
        diagnose_patch_preview(
            patch,
            slot=f"I{index // 8 + 1}{index % 8 + 1}",
            device_id=selected_device_id,
        )
        for index, patch in enumerate(bank.patches)
    )
    return BankPreviewDiagnostic(bank.label, patches)
