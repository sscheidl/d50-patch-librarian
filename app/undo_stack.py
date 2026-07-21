"""Bounded snapshot-based undo/redo for the 64-slot working bank."""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.project import BankProject, ProjectState


@dataclass(slots=True)
class UndoStack:
    limit: int = 100
    _undo: list[ProjectState] = field(default_factory=list)
    _redo: list[ProjectState] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.limit < 1:
            raise ValueError("Undo-Limit muss mindestens 1 sein")

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def record(self, project: BankProject) -> None:
        self.record_state(project.snapshot())

    def record_state(self, state: ProjectState) -> None:
        self._undo.append(state)
        if len(self._undo) > self.limit:
            del self._undo[0 : len(self._undo) - self.limit]
        self._redo.clear()

    def undo(self, project: BankProject) -> bool:
        if not self._undo:
            return False
        self._redo.append(project.snapshot())
        project.restore(self._undo.pop())
        return True

    def redo(self, project: BankProject) -> bool:
        if not self._redo:
            return False
        self._undo.append(project.snapshot())
        project.restore(self._redo.pop())
        return True
