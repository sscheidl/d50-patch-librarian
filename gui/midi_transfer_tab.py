"""Visible Phase-3 boundary without pretending hardware support exists."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.i18n import tr


class MidiTransferTab(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=24)
        ttk.Label(self, text="MIDI / Transfer", font=("Segoe UI Semibold", 18)).pack(anchor="w")
        ttk.Label(
            self,
            text=tr("phase3"),
            font=("Segoe UI", 11),
            foreground="#555555",
        ).pack(anchor="w", pady=(8, 20))
        box = ttk.LabelFrame(self, text="Geplanter sicherer Workflow", padding=16)
        box.pack(fill="x")
        ttk.Label(
            box,
            text=(
                "• Dump into Buffer: sieben Temporary-Area-DT1-Nachrichten\n"
                "• Warnung bei Reverb 17–32\n"
                "• Bankempfang mit Quiet-Time und strikter Validierung\n"
                "• Banksenden nur nach Überschreibwarnung"
            ),
            justify="left",
        ).pack(anchor="w")

