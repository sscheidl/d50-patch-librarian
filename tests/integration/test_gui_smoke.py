from __future__ import annotations

import sys
import tkinter as tk

import pytest

from d50.bank_codec import parse_bank
from domain.project import BankProject
from gui.main_window import MainWindow


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop smoke test")
def test_phase2_window_builds_matrix_and_displays_bank(valid_bank_bytes: bytes) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk display unavailable: {exc}")
    root.withdraw()
    try:
        app = MainWindow(root)
        app.editor.replace_project(BankProject.from_bank(parse_bank(valid_bank_bytes, label="GUI Golden")))
        app.refresh("Test")
        root.update_idletasks()
        assert len(app.bank_tab.matrix.buttons) == 64
        assert "Golden Patch 01" in app.bank_tab.matrix.buttons[0].cget("text")
        assert app.bank_tab.project_name_var.get() == "GUI Golden"
        assert app.bank_tab.patch_count_var.get() == "64 belegt / 0 leer"
        assert app.bank_tab.reverb_var.get() == "Reverb-Basis 17–32 vollständig"
        assert app.bank_tab.matrix.buttons[0].cget("background") == "#cfe2ff"
        assert app.bank_tab.matrix.buttons[16].cget("background") == "#e2f0d9"
        assert "Fest im D-50" in app.bank_tab.details.variables["status"].get()
        assert app.midi_tab.device_id_var.get() == "00"
        assert "GUI Golden" in app.midi_tab.bank_var.get()
        assert not hasattr(app.midi_tab, "selection_var")
    finally:
        root.destroy()
