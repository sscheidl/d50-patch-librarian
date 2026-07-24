"""Three-pane Phase-2 bank editor composition."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from domain.project import BankProject

from .bank_matrix import BankMatrix
from .patch_details import PatchDetails


class BankEditorTab(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_selection,
        on_activate,
        on_context,
        on_move,
        on_metadata,
        on_rename,
        on_save_single,
        on_preview,
        on_new_patch: Callable[[], None],
        on_import_singles: Callable[[], None],
        on_import_bank: Callable[[], None],
        on_take_reverbs: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=8)
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)

        source = ttk.LabelFrame(self, text="Arbeitsbank / Quellen", padding=10, width=230)
        source.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        source.grid_propagate(False)
        self.project_name_var = tk.StringVar(value="Neue Bank")
        self.patch_count_var = tk.StringVar(value="0 belegt / 64")
        self.reverb_var = tk.StringVar(value="Reverb-Basis fehlt")
        self.source_var = tk.StringVar(value="Keine Quelldatei")
        ttk.Label(source, textvariable=self.project_name_var, font=("Segoe UI Semibold", 13), wraplength=205).pack(
            anchor="w"
        )
        ttk.Label(source, textvariable=self.patch_count_var).pack(anchor="w", pady=(8, 0))
        ttk.Label(source, textvariable=self.reverb_var, wraplength=205).pack(anchor="w", pady=(4, 0))
        ttk.Label(source, textvariable=self.source_var, foreground="#555555", wraplength=205).pack(
            anchor="w", pady=(4, 14)
        )
        ttk.Separator(source).pack(fill="x", pady=4)
        ttk.Button(source, text="Einzelpatches importieren…", command=on_import_singles).pack(fill="x", pady=3)
        ttk.Button(source, text="Patches aus Bank…", command=on_import_bank).pack(fill="x", pady=3)
        ttk.Button(source, text="Reverbs aus Bank…", command=on_take_reverbs).pack(fill="x", pady=3)
        ttk.Button(source, text="INIT SAW einsetzen", command=on_new_patch).pack(fill="x", pady=(10, 3))
        ttk.Separator(source).pack(fill="x", pady=10)
        ttk.Label(source, text="Reverbstatus", font=("Segoe UI Semibold", 10)).pack(anchor="w")
        legend = (
            ("#ffffff", "Weiß: Reverb 1–16 fest"),
            ("#e2f0d9", "Grün: Bank-Reverb vorhanden"),
            ("#fff3cd", "Gelb: Bank-Reverb fehlt"),
            ("#f8d7da", "Rot: Reverbkonflikt"),
        )
        for color, text in legend:
            row = ttk.Frame(source)
            row.pack(fill="x", pady=1)
            tk.Label(row, background=color, width=2, relief="solid", borderwidth=1).pack(side="left")
            ttk.Label(row, text=text).pack(side="left", padx=(6, 0))
        ttk.Separator(source).pack(fill="x", pady=10)
        ttk.Label(
            source,
            text=(
                "Tipp:\nStrg/Shift = Mehrfachauswahl\n"
                "Ziehen = Verschieben/Tauschen\nF2 = Umbenennen\nEntf = auf INIT SAW setzen"
            ),
            foreground="#555555",
            justify="left",
        ).pack(anchor="w")

        matrix_container = ttk.LabelFrame(self, text="64 Patchslots", padding=4)
        matrix_container.grid(row=0, column=1, sticky="nsew")
        matrix_container.rowconfigure(0, weight=1)
        matrix_container.columnconfigure(0, weight=1)
        self.matrix = BankMatrix(
            matrix_container,
            on_selection=on_selection,
            on_activate=on_activate,
            on_context=on_context,
            on_move=on_move,
        )
        self.matrix.grid(row=0, column=0, sticky="nsew")

        self.details = PatchDetails(
            self,
            on_apply=on_metadata,
            on_rename=on_rename,
            on_save_single=on_save_single,
            on_preview=on_preview,
        )
        self.details.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self.details.configure(width=330)
        self.details.grid_propagate(False)

    def refresh_summary(self, project: BankProject) -> None:
        self.project_name_var.set(project.label)
        self.patch_count_var.set(f"{project.occupied_count} belegt / {project.empty_count} leer")
        reverb_summary = (
            "Reverb-Basis 17–32 vollständig" if project.has_complete_reverbs else "Reverb-Basis 17–32 fehlt"
        )
        if project.reverb_conflict_count:
            reverb_summary += f" · {project.reverb_conflict_count} Konflikt(e)"
        if project.reverb_missing_count:
            reverb_summary += f" · {project.reverb_missing_count} Quelle(n) unbekannt"
        self.reverb_var.set(reverb_summary)
        self.source_var.set(project.source_bank_path or project.project_path or "Keine Quelldatei")

    def set_midi_busy(self, busy: bool) -> None:
        self.details.set_midi_busy(busy)
