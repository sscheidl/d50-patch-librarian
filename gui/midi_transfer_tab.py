"""Full-bank MIDI transfer controls for the Roland D-50."""

from __future__ import annotations

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from d50.constants import DEFAULT_DEVICE_ID


class MidiTransferTab(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        on_refresh_ports: Callable[[], None],
        on_test_ports: Callable[[], None],
        on_send_bank: Callable[[], None],
        on_receive_bank: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=24)
        self.output_port_var = tk.StringVar()
        self.input_port_var = tk.StringVar()
        self.device_id_var = tk.StringVar(value=f"{DEFAULT_DEVICE_ID:02X}")
        self.preview_delay_var = tk.StringVar(value="50")
        self.bank_var = tk.StringVar(value="Neue Bank · 0/64 Patches · Reverbs fehlen")
        self.status_var = tk.StringVar(value="Noch keine MIDI-Bankübertragung ausgeführt")
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_text_var = tk.StringVar(value="Bereit")

        ttk.Label(self, text="MIDI / vollständige Bank", font=("Segoe UI Semibold", 18)).pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "64 Patches und Reverbs 17–32 zuverlässig per Roland-Handshake senden oder empfangen. "
                "Die Patch-Vorschau in Matrix und Patchdetails ist experimentell und kann am realen "
                "D-50 Partials, Layer oder Splits fehlerhaft initialisieren."
            ),
            foreground="#555555",
            wraplength=900,
        ).pack(anchor="w", pady=(8, 20))

        connection = ttk.LabelFrame(self, text="Bidirektionale MIDI-Verbindung", padding=14)
        connection.pack(fill="x")
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(3, weight=0)
        ttk.Label(connection, text="Ausgang zum D-50:").grid(row=0, column=0, sticky="w")
        self.output_port_box = ttk.Combobox(
            connection,
            textvariable=self.output_port_var,
            state="readonly",
            width=52,
        )
        self.output_port_box.grid(row=0, column=1, sticky="ew", padx=(8, 6))
        self.refresh_button = ttk.Button(connection, text="Aktualisieren", command=on_refresh_ports)
        self.refresh_button.grid(row=0, column=2, padx=3)

        ttk.Label(connection, text="Eingang vom D-50:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.input_port_box = ttk.Combobox(
            connection,
            textvariable=self.input_port_var,
            state="readonly",
            width=52,
        )
        self.input_port_box.grid(row=1, column=1, sticky="ew", padx=(8, 6), pady=(8, 0))
        self.test_button = ttk.Button(connection, text="Beide Ports testen", command=on_test_ports)
        self.test_button.grid(row=1, column=2, padx=3, pady=(8, 0))

        ttk.Label(connection, text="Device ID (hex):").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.device_id_box = ttk.Combobox(
            connection,
            textvariable=self.device_id_var,
            values=tuple(f"{value:02X}" for value in range(0x20)),
            state="readonly",
            width=8,
        )
        self.device_id_box.grid(row=2, column=1, sticky="w", padx=(8, 6), pady=(10, 0))
        ttk.Label(connection, text="Patch-Vorschau-Abstand:").grid(row=2, column=2, sticky="e", pady=(10, 0))
        self.preview_delay_box = ttk.Combobox(
            connection,
            textvariable=self.preview_delay_var,
            values=("30", "40", "50", "60", "75", "100"),
            state="readonly",
            width=6,
        )
        self.preview_delay_box.grid(row=2, column=3, sticky="w", padx=3, pady=(10, 0))

        bank_frame = ttk.LabelFrame(self, text="Aktuelle Arbeitsbank", padding=14)
        bank_frame.pack(fill="x", pady=(14, 0))
        ttk.Label(bank_frame, textvariable=self.bank_var, font=("Segoe UI Semibold", 11)).pack(anchor="w")
        buttons = ttk.Frame(bank_frame)
        buttons.pack(fill="x", pady=(12, 0))
        self.send_button = ttk.Button(buttons, text="Komplette Bank an D-50 senden…", command=on_send_bank)
        self.send_button.pack(side="left")
        self.receive_button = ttk.Button(buttons, text="Komplette Bank vom D-50 empfangen…", command=on_receive_bank)
        self.receive_button.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(buttons, text="Abbrechen", command=on_cancel, state="disabled")
        self.cancel_button.pack(side="right")

        preparation = ttk.LabelFrame(self, text="D-50 vorbereiten", padding=14)
        preparation.pack(fill="x", pady=(14, 0))
        ttk.Label(
            preparation,
            text=(
                "Senden: Bank sichern, Memory Protect ausschalten und den D-50 in DATA TRANSFER → B.Load bereitstellen.\n"
                "Empfangen: zuerst hier den Empfang starten, dann am D-50 DATA TRANSFER → B.Dump auslösen.\n"
                "Für den Handshake müssen MIDI IN und MIDI OUT verbunden sein; Basic Channel und Device ID müssen passen."
            ),
            justify="left",
            wraplength=940,
        ).pack(anchor="w")

        progress_frame = ttk.LabelFrame(self, text="Übertragungsstatus", padding=14)
        progress_frame.pack(fill="x", pady=(14, 0))
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=1)
        self.progress.pack(fill="x")
        ttk.Label(progress_frame, textvariable=self.progress_text_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            progress_frame,
            textvariable=self.status_var,
            wraplength=940,
            justify="left",
            foreground="#444444",
        ).pack(anchor="w", pady=(6, 0))

        self._idle_widgets = (
            self.output_port_box,
            self.input_port_box,
            self.device_id_box,
            self.preview_delay_box,
            self.refresh_button,
            self.test_button,
            self.send_button,
            self.receive_button,
        )

    def set_ports(self, output_names: tuple[str, ...], input_names: tuple[str, ...]) -> None:
        current_output = self.output_port_var.get()
        current_input = self.input_port_var.get()
        self.output_port_box.configure(values=output_names)
        self.input_port_box.configure(values=input_names)
        if current_output not in output_names:
            self.output_port_var.set(output_names[0] if len(output_names) == 1 else "")
        if current_input not in input_names:
            self.input_port_var.set(input_names[0] if len(input_names) == 1 else "")

    def selected_preview_settings(self) -> tuple[str, int, int]:
        return (
            self.output_port_var.get(),
            int(self.device_id_var.get(), 16),
            int(self.preview_delay_var.get()),
        )

    def selected_bank_settings(self) -> tuple[str, str, int]:
        return (
            self.output_port_var.get(),
            self.input_port_var.get(),
            int(self.device_id_var.get(), 16),
        )

    def show_bank(self, *, label: str, occupied: int, empty: int, reverbs_complete: bool) -> None:
        reverb_text = "Reverbs vollständig" if reverbs_complete else "Reverbs fehlen"
        self.bank_var.set(f"{label} · {occupied}/64 Patches · {empty} leer · {reverb_text}")

    def set_transfer_active(self, active: bool) -> None:
        for widget in self._idle_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="disabled" if active else "readonly")
            else:
                widget.configure(state="disabled" if active else "normal")
        self.cancel_button.configure(state="normal" if active else "disabled")

    def set_progress(self, phase: str, current: int, total: int) -> None:
        maximum = max(1, total)
        self.progress.configure(maximum=maximum)
        self.progress_var.set(min(current, maximum))
        self.progress_text_var.set(f"{phase}: {current} / {total}")

    def reset_progress(self, text: str = "Bereit") -> None:
        self.progress.configure(maximum=1)
        self.progress_var.set(0)
        self.progress_text_var.set(text)

    def set_status(self, message: str) -> None:
        self.status_var.set(message)
