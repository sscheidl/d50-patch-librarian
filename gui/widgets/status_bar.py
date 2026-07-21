from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class StatusBar(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=(8, 4))
        self.message_var = tk.StringVar(value="Bereit")
        self.summary_var = tk.StringVar(value="0 / 64 Patches")
        ttk.Label(self, textvariable=self.message_var).pack(side="left")
        ttk.Label(self, textvariable=self.summary_var).pack(side="right")

    def set(self, message: str, summary: str | None = None) -> None:
        self.message_var.set(message)
        if summary is not None:
            self.summary_var.set(summary)

