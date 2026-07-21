"""Keyboard- and mouse-operable 8×8 D-50 patch matrix."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from domain.project import BankProject

from .reverb_display import present_reverb_status

SelectionCallback = Callable[[set[int]], None]
IndexCallback = Callable[[int], None]
MoveCallback = Callable[[int, int], None]


class BankMatrix(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_selection: SelectionCallback,
        on_activate: IndexCallback,
        on_context: Callable[[int, int, int], None],
        on_move: MoveCallback,
    ) -> None:
        super().__init__(master, padding=4, takefocus=True)
        self.on_selection = on_selection
        self.on_activate = on_activate
        self.on_context = on_context
        self.on_move = on_move
        self.selected: set[int] = {0}
        self.anchor = 0
        self.drag_source: int | None = None
        self.buttons: list[tk.Button] = []
        self._widget_indices: dict[tk.Misc, int] = {}

        for row in range(8):
            self.rowconfigure(row, weight=1, uniform="slots")
            self.columnconfigure(row, weight=1, uniform="slots")
            for column in range(8):
                index = row * 8 + column
                button = tk.Button(
                    self,
                    text="",
                    font=("Segoe UI", 9),
                    anchor="nw",
                    justify="left",
                    wraplength=88,
                    relief=tk.RAISED,
                    borderwidth=1,
                    padx=7,
                    pady=6,
                    takefocus=True,
                )
                button.grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
                button.bind("<ButtonPress-1>", lambda event, i=index: self._press(event, i))
                button.bind("<ButtonRelease-1>", lambda event, i=index: self._release(event, i))
                button.bind("<Double-Button-1>", lambda _event, i=index: self.on_activate(i))
                button.bind("<Button-3>", lambda event, i=index: self._context(event, i))
                self.buttons.append(button)
                self._widget_indices[button] = index

    def set_selection(self, indices: set[int] | list[int] | tuple[int, ...], *, notify: bool = True) -> None:
        normalized = {index for index in indices if 0 <= index < 64}
        self.selected = normalized or {0}
        self.anchor = min(self.selected)
        if notify:
            self.on_selection(set(self.selected))

    def select_all(self) -> None:
        self.selected = set(range(64))
        self.on_selection(set(self.selected))

    def _press(self, event: tk.Event, index: int) -> str:
        self.focus_set()
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        if shift:
            start, end = sorted((self.anchor, index))
            self.selected = set(range(start, end + 1))
        elif ctrl:
            if index in self.selected and len(self.selected) > 1:
                self.selected.remove(index)
            else:
                self.selected.add(index)
            self.anchor = index
        else:
            self.selected = {index}
            self.anchor = index
        self.drag_source = index
        self.on_selection(set(self.selected))
        return "break"

    def _release(self, event: tk.Event, index: int) -> str:
        target_widget = self.winfo_containing(event.x_root, event.y_root)
        target = self._index_for_widget(target_widget)
        source = self.drag_source
        self.drag_source = None
        if source is not None and target is not None and source != target:
            self.on_move(source, target)
            self.selected = {target}
            self.anchor = target
            self.on_selection(set(self.selected))
        return "break"

    def _index_for_widget(self, widget: tk.Misc | None) -> int | None:
        current = widget
        while current is not None:
            if current in self._widget_indices:
                return self._widget_indices[current]
            if current == self:
                break
            current = getattr(current, "master", None)
        return None

    def _context(self, event: tk.Event, index: int) -> str:
        if index not in self.selected:
            self.selected = {index}
            self.anchor = index
            self.on_selection(set(self.selected))
        self.on_context(index, event.x_root, event.y_root)
        return "break"

    def refresh(self, project: BankProject) -> None:
        for index, button in enumerate(self.buttons):
            slot = project.slots[index]
            row, column = divmod(index, 8)
            slot_label = f"{row + 1}-{column + 1}"
            if slot is None:
                text = f"{slot_label}\n— leer —"
                background = "#f1f1f1"
                foreground = "#777777"
            else:
                presentation = present_reverb_status(slot.patch.reverb_status)
                text = (
                    f"{slot_label}  R{slot.patch.reverb_type:02d}{presentation.marker}\n"
                    f"{slot.patch.name or '(ohne Namen)'}"
                )
                background = presentation.background
                foreground = "#202020"
            if index in self.selected:
                background = "#cfe2ff"
                relief = tk.SUNKEN
                borderwidth = 2
            else:
                relief = tk.RAISED
                borderwidth = 1
            button.configure(
                text=text,
                background=background,
                activebackground="#b6d4fe",
                foreground=foreground,
                relief=relief,
                borderwidth=borderwidth,
            )
