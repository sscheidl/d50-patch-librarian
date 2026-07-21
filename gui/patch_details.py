"""Patch details and librarian metadata editor."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from domain.project import PatchSlot


class PatchDetails(ttk.LabelFrame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_apply: Callable[[str, int, str], None],
        on_rename: Callable[[], None],
        on_save_single: Callable[[], None],
    ) -> None:
        super().__init__(master, text="Patchdetails", padding=10)
        self.on_apply = on_apply
        self.current_index: int | None = None
        self.variables = {
            "slot": tk.StringVar(value="—"),
            "name": tk.StringVar(value="—"),
            "upper": tk.StringVar(value="—"),
            "lower": tk.StringVar(value="—"),
            "reverb": tk.StringVar(value="—"),
            "status": tk.StringVar(value="—"),
            "source": tk.StringVar(value="—"),
            "original": tk.StringVar(value="—"),
            "hash": tk.StringVar(value="—"),
        }
        labels = (
            ("Slot", "slot"),
            ("Patchname", "name"),
            ("Upper Tone", "upper"),
            ("Lower Tone", "lower"),
            ("Reverb", "reverb"),
            ("Reverbstatus", "status"),
            ("Quelle", "source"),
            ("Originalslot", "original"),
            ("SHA256", "hash"),
        )
        for row, (caption, key) in enumerate(labels):
            ttk.Label(self, text=f"{caption}:").grid(row=row, column=0, sticky="nw", pady=2)
            ttk.Label(
                self,
                textvariable=self.variables[key],
                wraplength=260,
                justify="left",
            ).grid(row=row, column=1, sticky="nw", padx=(8, 0), pady=2)

        separator_row = len(labels)
        ttk.Separator(self).grid(row=separator_row, column=0, columnspan=2, sticky="ew", pady=9)
        ttk.Label(self, text="Kategorie:").grid(row=separator_row + 1, column=0, sticky="w")
        self.category_var = tk.StringVar()
        self.category_entry = ttk.Entry(self, textvariable=self.category_var)
        self.category_entry.grid(row=separator_row + 1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(self, text="Bewertung:").grid(row=separator_row + 2, column=0, sticky="w", pady=5)
        self.rating_var = tk.StringVar(value="0")
        self.rating_box = ttk.Combobox(
            self,
            textvariable=self.rating_var,
            values=("0", "1", "2", "3", "4", "5"),
            state="readonly",
            width=5,
        )
        self.rating_box.grid(row=separator_row + 2, column=1, sticky="w", padx=(8, 0), pady=5)

        ttk.Label(self, text="Notizen:").grid(row=separator_row + 3, column=0, columnspan=2, sticky="w")
        self.notes = tk.Text(self, height=5, width=30, wrap="word", font=("Segoe UI", 10))
        self.notes.grid(row=separator_row + 4, column=0, columnspan=2, sticky="nsew", pady=(3, 6))

        self.apply_button = ttk.Button(self, text="Metadaten übernehmen", command=self._apply)
        self.apply_button.grid(row=separator_row + 5, column=0, columnspan=2, sticky="ew")
        action_frame = ttk.Frame(self)
        action_frame.grid(row=separator_row + 6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.rename_button = ttk.Button(action_frame, text="Umbenennen", command=on_rename)
        self.rename_button.pack(fill="x", pady=2)
        self.save_button = ttk.Button(action_frame, text="Als SysEx speichern", command=on_save_single)
        self.save_button.pack(fill="x", pady=2)
        ttk.Button(action_frame, text="Vorhören (Phase 3)", state="disabled").pack(fill="x", pady=2)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(separator_row + 4, weight=1)
        self.set_empty("Kein Patch ausgewählt")

    def _apply(self) -> None:
        if self.current_index is None:
            return
        self.on_apply(self.category_var.get(), int(self.rating_var.get()), self.notes.get("1.0", "end-1c"))

    def set_empty(self, message: str = "Leerer Slot") -> None:
        self.current_index = None
        for variable in self.variables.values():
            variable.set("—")
        self.variables["name"].set(message)
        self.category_var.set("")
        self.rating_var.set("0")
        self.notes.configure(state="normal")
        self.notes.delete("1.0", tk.END)
        self._set_edit_state(False)

    def show_patch(self, index: int, slot: PatchSlot) -> None:
        self.current_index = index
        row, column = divmod(index, 8)
        patch = slot.patch
        self.variables["slot"].set(f"{row + 1}-{column + 1} / I{row + 1}{column + 1}")
        self.variables["name"].set(patch.name or "(ohne Namen)")
        self.variables["upper"].set(patch.upper_tone_name or "(ohne Namen)")
        self.variables["lower"].set(patch.lower_tone_name or "(ohne Namen)")
        self.variables["reverb"].set(f"{patch.reverb_type:02d}")
        self.variables["status"].set(patch.reverb_status.value)
        self.variables["source"].set(patch.source_bank or "—")
        self.variables["original"].set(patch.slot_label or "—")
        self.variables["hash"].set(patch.sha256)
        self.category_var.set(slot.category)
        self.rating_var.set(str(slot.rating))
        self.notes.configure(state="normal")
        self.notes.delete("1.0", tk.END)
        self.notes.insert("1.0", slot.notes)
        self._set_edit_state(True)

    def _set_edit_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.category_entry.configure(state=state)
        self.rating_box.configure(state="readonly" if enabled else "disabled")
        self.notes.configure(state=state)
        self.apply_button.configure(state=state)
        self.rename_button.configure(state=state)
        self.save_button.configure(state=state)
