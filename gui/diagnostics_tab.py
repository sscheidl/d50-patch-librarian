"""Human-readable strict file diagnostics inside the desktop app."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from d50.bank_codec import parse_bank
from d50.classifier import classify
from d50.single_patch_codec import parse_single_patch
from domain.enums import DumpType


class DiagnosticsTab(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=12)
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="SysEx-Datei prüfen…", command=self.choose_file).pack(side="left")
        ttk.Button(toolbar, text="Log leeren", command=self.clear).pack(side="left", padx=6)
        self.text = tk.Text(self, wrap="word", font=("Consolas", 10), state="disabled")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.pack(side="left", fill="both", expand=True, pady=(10, 0))
        scrollbar.pack(side="right", fill="y", pady=(10, 0))
        self.append("Diagnose bereit. Dateien werden ausschließlich gelesen.\n")

    def clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.configure(state="disabled")

    def append(self, message: str) -> None:
        self.text.configure(state="normal")
        self.text.insert(tk.END, message.rstrip() + "\n")
        self.text.see(tk.END)
        self.text.configure(state="disabled")

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="SysEx-Datei prüfen",
            filetypes=(("SysEx-Dateien", "*.syx"), ("Alle Dateien", "*.*")),
        )
        if path:
            self.analyze(Path(path))

    def analyze(self, path: Path) -> None:
        try:
            data = path.read_bytes()
            result = classify(data)
            lines = [
                "",
                f"Datei: {path}",
                f"Klassifikation: {result.dump_type.value}",
                f"Dateigröße: {len(data)} Byte",
                f"Nachrichten: {result.message_count}",
                f"Adressierte Daten: {result.data_byte_count} Byte",
                f"Device ID: {result.device_id if result.device_id is not None else '—'}",
            ]
            lines.extend(f"Fehler: {issue}" for issue in result.issues)
            if result.dump_type == DumpType.D50_FULL_BANK:
                bank = parse_bank(data, source_path=path)
                lines.append(f"Bank: {bank.label}; 64 Patches; 16 Reverbs")
                lines.extend(
                    f"  {patch.slot_label}: {patch.name} / Reverb {patch.reverb_type:02d}"
                    for patch in bank.patches
                )
            elif result.dump_type in {
                DumpType.D50_SINGLE_PATCH_TEMP,
                DumpType.D50_SINGLE_PATCH_MEMORY,
            }:
                patch = parse_single_patch(data, source_bank=path.stem)
                lines.append(
                    f"Patch: {patch.name}; Upper {patch.upper_tone_name}; "
                    f"Lower {patch.lower_tone_name}; Reverb {patch.reverb_type:02d}"
                )
            self.append("\n".join(lines))
        except Exception as exc:
            self.append(f"\nDatei: {path}\nDiagnosefehler: {exc}")

