from __future__ import annotations

import sys
import tkinter as tk
from types import SimpleNamespace

import pytest

from d50.bank_codec import parse_bank
from domain.project import BankProject
from gui.main_window import MainWindow
from gui.bank_matrix import BankMatrix


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop smoke test")
def test_phase2_window_builds_matrix_and_displays_bank(valid_bank_bytes: bytes, tk_root: tk.Tk) -> None:
    root = tk_root
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
        try:
            root.after_cancel(app._midi_poll_id)
        except (AttributeError, tk.TclError):
            pass
        for child in root.winfo_children():
            child.destroy()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop smoke test")
def test_matrix_drag_threshold_prevents_jitter_and_moves_once(
    valid_bank_bytes: bytes,
    tk_root: tk.Tk,
) -> None:
    root = tk_root
    moves: list[tuple[int, int]] = []
    try:
        matrix = BankMatrix(
            root,
            on_selection=lambda _selection: None,
            on_activate=lambda _index: None,
            on_context=lambda _index, _x, _y: None,
            on_move=lambda source, target: moves.append((source, target)),
        )
        matrix.pack()
        matrix.refresh(BankProject.from_bank(parse_bank(valid_bank_bytes)))
        root.update_idletasks()
        matrix.winfo_containing = lambda _x, _y: matrix.buttons[1]  # type: ignore[method-assign]

        matrix._press(SimpleNamespace(state=0, x_root=10, y_root=10), 0)
        matrix._motion(SimpleNamespace(x_root=13, y_root=12), 0)
        matrix._release(SimpleNamespace(x_root=13, y_root=12), 0)
        assert moves == []

        matrix._press(SimpleNamespace(state=0, x_root=10, y_root=10), 0)
        matrix._motion(SimpleNamespace(x_root=20, y_root=10), 0)
        assert matrix.drag_target == 1
        matrix._release(SimpleNamespace(x_root=20, y_root=10), 0)

        assert moves == [(0, 1)]
        assert matrix.drag_target is None
    finally:
        matrix.destroy()
