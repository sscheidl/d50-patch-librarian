"""Transactional editor operations shared by the GUI and tests."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

from app.undo_stack import UndoStack
from d50.patch_codec import rename_patch
from domain.patch import D50Patch
from domain.project import BankProject, PatchSlot


class BankEditorService:
    def __init__(self, project: BankProject | None = None, *, undo_limit: int = 100) -> None:
        self.project = project or BankProject.empty()
        self.undo_stack = UndoStack(undo_limit)
        self.clipboard: tuple[PatchSlot, ...] = ()
        self.dirty = False

    def replace_project(self, project: BankProject) -> None:
        self.project = project
        self.undo_stack.clear()
        self.dirty = False

    def mark_saved(self) -> None:
        self.dirty = False

    def _change(self, operation: Callable[[], None]) -> None:
        before = self.project.snapshot()
        try:
            operation()
        except BaseException:
            self.project.restore(before)
            raise
        if self.project.snapshot() != before:
            self.undo_stack.record_state(before)
            self.dirty = True

    def undo(self) -> bool:
        project_path = self.project.project_path
        if self.undo_stack.undo(self.project):
            self.project.project_path = project_path
            self.dirty = True
            return True
        return False

    def redo(self) -> bool:
        project_path = self.project.project_path
        if self.undo_stack.redo(self.project):
            self.project.project_path = project_path
            self.dirty = True
            return True
        return False

    def rename(self, index: int, new_name: str) -> None:
        def operation() -> None:
            slot = self._occupied(index)
            self.project.slots[index] = replace(slot, patch=rename_patch(slot.patch, new_name))

        self._change(operation)

    def update_metadata(self, index: int, *, category: str, rating: int, notes: str) -> None:
        self._change(lambda: self.project.update_metadata(index, category=category, rating=rating, notes=notes))

    def clear(self, indices: list[int] | set[int] | tuple[int, ...]) -> None:
        normalized = sorted(set(indices))
        self._change(lambda: self.project.clear_slots(normalized))

    def initialize(
        self,
        indices: list[int] | set[int] | tuple[int, ...],
        patch: D50Patch,
    ) -> None:
        normalized = sorted(set(indices))
        self._change(lambda: self.project.initialize_slots(normalized, patch))

    def delete_and_shift(self, index: int) -> None:
        self._change(lambda: self.project.delete_and_shift(index))

    def move_or_swap(self, source: int, target: int) -> None:
        self._change(lambda: self.project.move_or_swap(source, target))

    def sort(self, key: str, *, reverse: bool = False) -> None:
        self._change(lambda: self.project.sort_slots(key, reverse=reverse))

    def import_patches(self, patches: list[D50Patch], *, start_index: int | None = None) -> list[int]:
        written: list[int] = []

        def operation() -> None:
            written.extend(self.project.insert_patches(patches, start_index=start_index))

        self._change(operation)
        return written

    def replace_patch(self, index: int, patch: D50Patch) -> None:
        self._change(lambda: self.project.replace_patch(index, patch))

    def set_reverbs(self, reverbs) -> None:
        self._change(lambda: self.project.set_reverbs(reverbs))

    def copy(self, indices: list[int] | set[int] | tuple[int, ...]) -> int:
        self.clipboard = tuple(
            self.project.slots[index]
            for index in sorted(set(indices))
            if self.project.slots[index] is not None
        )  # type: ignore[assignment]
        return len(self.clipboard)

    def cut(self, indices: list[int] | set[int] | tuple[int, ...]) -> int:
        normalized = sorted(set(indices))
        count = self.copy(normalized)
        if count:
            self.clear(normalized)
        return count

    def paste(self, start_index: int | None = None) -> list[int]:
        if not self.clipboard:
            return []
        written: list[int] = []

        def operation() -> None:
            available = self.project.free_indices()
            if start_index is not None:
                available = [index for index in range(start_index, 64) if self.project.slots[index] is None] + [
                    index for index in range(start_index) if self.project.slots[index] is None
                ]
            if len(available) < len(self.clipboard):
                raise ValueError(
                    f"Nicht genügend freie Slots: benötigt {len(self.clipboard)}, frei {len(available)}"
                )
            for clipboard_slot, index in zip(self.clipboard, available):
                self.project.slots[index] = PatchSlot(
                    patch=self.project.with_reverb_context(clipboard_slot.patch),
                    category=clipboard_slot.category,
                    rating=clipboard_slot.rating,
                    notes=clipboard_slot.notes,
                    original_position=clipboard_slot.original_position,
                    sequence=self.project.next_sequence,
                )
                self.project.next_sequence += 1
                written.append(index)

        self._change(operation)
        return written

    def duplicate(self, source: int, target: int) -> None:
        slot = self._occupied(source)

        def operation() -> None:
            self.project.slots[target] = PatchSlot(
                patch=self.project.with_reverb_context(slot.patch),
                category=slot.category,
                rating=slot.rating,
                notes=slot.notes,
                original_position=slot.original_position,
                sequence=self.project.next_sequence,
            )
            self.project.next_sequence += 1

        self._change(operation)

    def _occupied(self, index: int) -> PatchSlot:
        BankProject._validate_slot_index(index)
        slot = self.project.slots[index]
        if slot is None:
            raise ValueError("Der ausgewählte Slot ist leer")
        return slot
