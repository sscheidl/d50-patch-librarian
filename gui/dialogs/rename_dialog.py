"""Patch rename dialog with live D-50 character validation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter.simpledialog import Dialog

from d50.charset import ALLOWED_CHARACTERS, validate_name
from domain.errors import D50ValidationError


class RenameDialog(Dialog):
    def __init__(self, parent: tk.Misc, initial_name: str) -> None:
        self.initial_name = initial_name
        self.value: str | None = None
        self.name_var = tk.StringVar(value=initial_name)
        self.count_var = tk.StringVar()
        self.error_var = tk.StringVar()
        super().__init__(parent, title="Patch umbenennen")

    def body(self, master: tk.Misc) -> tk.Widget:
        ttk.Label(master, text="Neuer Patchname:").grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(master, textvariable=self.name_var, width=30, font=("Segoe UI", 11))
        entry.grid(row=1, column=0, sticky="ew", pady=(4, 2))
        info = ttk.Frame(master)
        info.grid(row=2, column=0, sticky="ew")
        ttk.Label(info, textvariable=self.error_var, foreground="#a00000").pack(side="left")
        ttk.Label(info, textvariable=self.count_var).pack(side="right")
        ttk.Label(
            master,
            text="Zulässig: Leerzeichen, A–Z, a–z, 0–9 und -",
            foreground="#555555",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))
        master.columnconfigure(0, weight=1)
        self.name_var.trace_add("write", self._update_validation)
        self._update_validation()
        entry.selection_range(0, tk.END)
        return entry

    def _update_validation(self, *_args: object) -> None:
        value = self.name_var.get()
        self.count_var.set(f"{len(value)} / 18 Zeichen")
        invalid = [character for character in value if character not in ALLOWED_CHARACTERS]
        if len(value) > 18:
            self.error_var.set("Maximal 18 Zeichen")
        elif invalid:
            self.error_var.set(f"Unzulässig: {invalid[0]!r}")
        else:
            self.error_var.set("")

    def validate(self) -> bool:
        try:
            validate_name(self.name_var.get(), max_length=18, field="Patchname")
        except D50ValidationError as exc:
            self.error_var.set(str(exc))
            return False
        return True

    def apply(self) -> None:
        self.value = self.name_var.get()


def ask_patch_name(parent: tk.Misc, initial_name: str) -> str | None:
    dialog = RenameDialog(parent, initial_name)
    return dialog.value

