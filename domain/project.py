"""Editable Phase-2 working bank with empty slots and librarian metadata."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from d50.patch_codec import decode_patch

from .bank import D50Bank
from .enums import ReverbStatus
from .patch import D50Patch
from .reverb import D50Reverb


class ProjectExportError(ValueError):
    """Raised when a working project cannot form a complete hardware bank."""


@dataclass(frozen=True, slots=True)
class PatchSlot:
    patch: D50Patch
    category: str = ""
    rating: int = 1
    notes: str = ""
    original_position: int | None = None
    sequence: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.rating <= 6:
            raise ValueError("Bewertung muss zwischen 1 und 6 liegen")
        if self.original_position is not None and not 0 <= self.original_position < 64:
            raise ValueError("Originalposition muss zwischen 0 und 63 liegen")
        if self.sequence < 0:
            raise ValueError("Sequenznummer darf nicht negativ sein")


@dataclass(frozen=True, slots=True)
class ProjectState:
    label: str
    slots: tuple[PatchSlot | None, ...]
    reverbs: tuple[D50Reverb, ...]
    device_id: int
    source_bank_path: str | None
    project_path: str | None
    next_sequence: int


@dataclass(slots=True)
class BankProject:
    label: str = "Neue Bank"
    slots: list[PatchSlot | None] = field(default_factory=lambda: [None] * 64)
    reverbs: dict[int, D50Reverb] = field(default_factory=dict)
    device_id: int = 0x00
    source_bank_path: str | None = None
    project_path: str | None = None
    next_sequence: int = 0

    def __post_init__(self) -> None:
        if len(self.slots) != 64:
            raise ValueError("Eine Arbeitsbank muss genau 64 Slots enthalten")
        if not 0 <= self.device_id <= 0x1F:
            raise ValueError("Device ID muss zwischen 00h und 1Fh liegen")
        if any(number != reverb.number for number, reverb in self.reverbs.items()):
            raise ValueError("Reverbnummer und Reverbobjekt stimmen nicht überein")
        if any(not 17 <= number <= 32 for number in self.reverbs):
            raise ValueError("Nur Reverbblöcke 17 bis 32 sind zulässig")

    @classmethod
    def empty(cls, label: str = "Neue Bank") -> "BankProject":
        return cls(label=label or "Neue Bank")

    @classmethod
    def from_bank(cls, bank: D50Bank, *, source_path: str | Path | None = None) -> "BankProject":
        slots = [
            PatchSlot(patch=patch, original_position=index, sequence=index)
            for index, patch in enumerate(bank.patches)
        ]
        return cls(
            label=bank.label,
            slots=slots,
            reverbs={reverb.number: reverb for reverb in bank.reverbs},
            device_id=bank.device_id,
            source_bank_path=str(Path(source_path).resolve()) if source_path is not None else None,
            next_sequence=64,
        )

    @property
    def occupied_count(self) -> int:
        return sum(slot is not None for slot in self.slots)

    @property
    def empty_count(self) -> int:
        return 64 - self.occupied_count

    @property
    def has_complete_reverbs(self) -> bool:
        return set(self.reverbs) == set(range(17, 33))

    @property
    def reverb_conflict_count(self) -> int:
        return sum(
            slot is not None and slot.patch.reverb_status == ReverbStatus.CONFLICT
            for slot in self.slots
        )

    @property
    def reverb_missing_count(self) -> int:
        return sum(
            slot is not None and slot.patch.reverb_status == ReverbStatus.SOURCE_MISSING
            for slot in self.slots
        )

    @property
    def dirty_title(self) -> str:
        return self.label or "Neue Bank"

    def occupied_indices(self) -> list[int]:
        return [index for index, slot in enumerate(self.slots) if slot is not None]

    def free_indices(self) -> list[int]:
        return [index for index, slot in enumerate(self.slots) if slot is None]

    def snapshot(self) -> ProjectState:
        return ProjectState(
            label=self.label,
            slots=tuple(self.slots),
            reverbs=tuple(self.reverbs[number] for number in sorted(self.reverbs)),
            device_id=self.device_id,
            source_bank_path=self.source_bank_path,
            project_path=self.project_path,
            next_sequence=self.next_sequence,
        )

    def restore(self, state: ProjectState) -> None:
        self.label = state.label
        self.slots = list(state.slots)
        self.reverbs = {reverb.number: reverb for reverb in state.reverbs}
        self.device_id = state.device_id
        self.source_bank_path = state.source_bank_path
        self.project_path = state.project_path
        self.next_sequence = state.next_sequence

    def new_entry(self, patch: D50Patch, *, original_position: int | None = None) -> PatchSlot:
        entry = PatchSlot(
            patch=self.with_reverb_context(patch),
            original_position=original_position,
            sequence=self.next_sequence,
        )
        self.next_sequence += 1
        return entry

    def with_reverb_context(self, patch: D50Patch) -> D50Patch:
        refreshed = decode_patch(
            patch.raw,
            source_device_id=patch.source_device_id,
            source_bank=patch.source_bank,
            source_slot=patch.source_slot,
        )
        if refreshed.reverb_type <= 16:
            return refreshed
        source_hash = patch.reverb_dependency_hash
        target_reverb = self.reverbs.get(refreshed.reverb_type)
        if source_hash is None or target_reverb is None:
            return replace(
                refreshed,
                reverb_dependency_hash=source_hash,
                reverb_status=ReverbStatus.SOURCE_MISSING,
            )
        status = (
            ReverbStatus.RESOLVED
            if source_hash == target_reverb.sha256
            else ReverbStatus.CONFLICT
        )
        return replace(
            refreshed,
            reverb_dependency_hash=source_hash,
            reverb_status=status,
        )

    def refresh_all_reverb_context(self) -> None:
        self.slots = [
            replace(slot, patch=self.with_reverb_context(slot.patch)) if slot is not None else None
            for slot in self.slots
        ]

    def set_reverbs(self, reverbs: tuple[D50Reverb, ...] | list[D50Reverb]) -> None:
        mapping = {reverb.number: reverb for reverb in reverbs}
        if set(mapping) != set(range(17, 33)):
            raise ValueError("Eine Reverb-Basis muss alle Programme 17 bis 32 enthalten")
        self.reverbs = mapping
        self.refresh_all_reverb_context()

    def insert_patches(self, patches: list[D50Patch], *, start_index: int | None = None) -> list[int]:
        if not patches:
            return []
        available = self.free_indices()
        if start_index is not None:
            if not 0 <= start_index < 64:
                raise ValueError("Zielslot muss zwischen 0 und 63 liegen")
            available = [index for index in range(start_index, 64) if self.slots[index] is None] + [
                index for index in range(0, start_index) if self.slots[index] is None
            ]
        if len(available) < len(patches):
            raise ValueError(f"Nicht genügend freie Slots: benötigt {len(patches)}, frei {len(available)}")
        written: list[int] = []
        for patch, index in zip(patches, available):
            self.slots[index] = self.new_entry(patch, original_position=patch.source_slot)
            written.append(index)
        return written

    def move_or_swap(self, source: int, target: int) -> None:
        self._validate_slot_index(source)
        self._validate_slot_index(target)
        if source == target or self.slots[source] is None:
            return
        self.slots[source], self.slots[target] = self.slots[target], self.slots[source]

    def clear_slots(self, indices: list[int] | set[int] | tuple[int, ...]) -> None:
        for index in indices:
            self._validate_slot_index(index)
            self.slots[index] = None

    def initialize_slots(
        self,
        indices: list[int] | set[int] | tuple[int, ...],
        patch: D50Patch,
    ) -> None:
        """Replace selected positions with fresh canonical patch entries."""
        for index in sorted(set(indices)):
            self._validate_slot_index(index)
            self.slots[index] = self.new_entry(patch)

    def delete_and_shift(self, index: int) -> None:
        self._validate_slot_index(index)
        del self.slots[index]
        self.slots.append(None)

    def sort_slots(self, key: str, *, reverse: bool = False) -> None:
        occupied = [slot for slot in self.slots if slot is not None]
        key_functions: dict[str, Callable[[PatchSlot], object]] = {
            "name": lambda slot: slot.patch.name.casefold(),
            "reverb": lambda slot: slot.patch.reverb_type,
            "category": lambda slot: slot.category.casefold(),
            "original": lambda slot: (
                slot.original_position is None,
                slot.original_position if slot.original_position is not None else slot.sequence,
            ),
        }
        if key not in key_functions:
            raise ValueError(f"Unbekannter Sortierschlüssel: {key}")
        occupied.sort(key=key_functions[key], reverse=reverse)
        self.slots = [*occupied, *([None] * (64 - len(occupied)))]

    def update_metadata(self, index: int, *, category: str, rating: int, notes: str) -> None:
        self._validate_slot_index(index)
        slot = self.slots[index]
        if slot is None:
            raise ValueError("Leerer Slot besitzt keine Patchdetails")
        self.slots[index] = replace(slot, category=category.strip(), rating=rating, notes=notes)

    def replace_patch(self, index: int, patch: D50Patch) -> None:
        self._validate_slot_index(index)
        slot = self.slots[index]
        if slot is None:
            self.slots[index] = self.new_entry(patch, original_position=patch.source_slot)
        else:
            self.slots[index] = replace(slot, patch=self.with_reverb_context(patch))

    def to_bank(self, *, fill_patch: D50Patch | None = None) -> D50Bank:
        if not self.has_complete_reverbs:
            raise ProjectExportError(
                "Reverb-Basis 17–32 fehlt. Bitte zuerst 'Reverbs aus Bank übernehmen' verwenden."
            )
        if self.empty_count and fill_patch is None:
            raise ProjectExportError(
                f"Die Arbeitsbank enthält {self.empty_count} leere Slots; ein expliziter Füllpatch ist erforderlich."
            )
        patches = tuple(
            slot.patch if slot is not None else fill_patch
            for slot in self.slots
        )
        if any(patch is None for patch in patches):
            raise ProjectExportError("Bankexport enthält weiterhin leere Slots")
        return D50Bank(
            patches=patches,  # type: ignore[arg-type]
            reverbs=tuple(self.reverbs[number] for number in range(17, 33)),
            device_id=self.device_id,
            label=self.label,
        )

    @staticmethod
    def _validate_slot_index(index: int) -> None:
        if not 0 <= index < 64:
            raise ValueError("Slotindex muss zwischen 0 und 63 liegen")
