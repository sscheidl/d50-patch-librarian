from __future__ import annotations

from threading import Event, get_ident
import sys
import time
import tkinter as tk

import pytest

from d50.bank_codec import parse_bank
from domain.project import BankProject
from gui.main_window import MainWindow
from midi.operation_manager import MidiOperation
from midi.temporary_sender import TemporaryPatchTransferReport


def _window(monkeypatch, valid_bank_bytes: bytes, root: tk.Tk) -> tuple[tk.Tk, MainWindow]:
    monkeypatch.setattr("gui.main_window.list_midi_output_ports", lambda: ("D-50 OUT",))
    monkeypatch.setattr("gui.main_window.list_midi_input_ports", lambda: ("D-50 IN",))
    app = MainWindow(root)
    app.editor.replace_project(BankProject.from_bank(parse_bank(valid_bank_bytes, label="MIDI GUI")))
    app.selection = {0}
    app.bank_tab.matrix.set_selection({0}, notify=False)
    app.refresh("Test")
    app.midi_tab.output_port_var.set("D-50 OUT")
    app.midi_tab.input_port_var.set("D-50 IN")
    return root, app


def _close_window(root: tk.Tk, app: MainWindow) -> None:
    try:
        root.after_cancel(app._midi_poll_id)
    except (AttributeError, tk.TclError):
        pass
    for child in root.winfo_children():
        child.destroy()


def _pump_until(root: tk.Tk, predicate, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        root.update()
        time.sleep(0.005)
    assert predicate()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop operation test")
def test_preview_worker_rejects_double_start_and_updates_tk_only_on_main_thread(
    monkeypatch,
    valid_bank_bytes: bytes,
    tk_root: tk.Tk,
) -> None:
    root, app = _window(monkeypatch, valid_bank_bytes, tk_root)
    started = Event()
    release = Event()
    calls: list[int] = []
    ui_threads: list[int] = []
    main_thread = get_ident()
    original_set_status = app.midi_tab.set_status

    def checked_set_status(message: str) -> None:
        ui_threads.append(get_ident())
        original_set_status(message)

    app.midi_tab.set_status = checked_set_status  # type: ignore[method-assign]

    def fake_send(patch, *, port_name, device_id, delay_ms, progress, job_id, diagnostic):
        calls.append(get_ident())
        progress(1, 7)
        diagnostic(f"[TX PREVIEW #{job_id}] test")
        started.set()
        assert release.wait(2)
        progress(7, 7)
        return TemporaryPatchTransferReport(port_name, patch.name, device_id, 7, 448, 50)

    monkeypatch.setattr("gui.main_window.send_temporary_patch", fake_send)
    port_test_calls: list[str] = []
    monkeypatch.setattr("gui.main_window.test_midi_output_port", port_test_calls.append)
    monkeypatch.setattr("gui.main_window.test_midi_input_port", port_test_calls.append)
    try:
        app.send_selected_to_buffer()
        assert started.wait(1)
        assert app.midi_operations.active_operation is MidiOperation.PREVIEW
        assert str(app.bank_tab.details.preview_button.cget("state")) == "disabled"
        assert str(app.midi_tab.send_button.cget("state")) == "disabled"

        app.send_selected_to_buffer()
        app.send_bank_to_d50()
        app.receive_bank_from_d50()
        app.test_selected_midi_ports()
        app.refresh_midi_ports()
        assert len(calls) == 1
        assert port_test_calls == []
        assert app.midi_operations.active_operation is MidiOperation.PREVIEW

        release.set()
        _pump_until(root, lambda: not app.midi_operations.is_busy)
        assert len(calls) == 1
        assert calls[0] != main_thread
        assert ui_threads and set(ui_threads) == {main_thread}
        assert "nicht bestätigt" in app.midi_tab.status_var.get()
        assert str(app.bank_tab.details.preview_button.cget("state")) == "normal"
    finally:
        _close_window(root, app)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop operation test")
def test_preview_failure_releases_operation_and_controls(
    monkeypatch,
    valid_bank_bytes: bytes,
    tk_root: tk.Tk,
) -> None:
    root, app = _window(monkeypatch, valid_bank_bytes, tk_root)
    errors: list[str] = []
    monkeypatch.setattr("gui.main_window.messagebox.showerror", lambda title, message, parent: errors.append(message))

    def fail_send(*args, **kwargs):
        raise RuntimeError("preview worker failed")

    monkeypatch.setattr("gui.main_window.send_temporary_patch", fail_send)
    try:
        app.send_selected_to_buffer()
        _pump_until(root, lambda: not app.midi_operations.is_busy)

        assert errors == ["preview worker failed"]
        assert str(app.bank_tab.details.preview_button.cget("state")) == "normal"
        assert str(app.midi_tab.send_button.cget("state")) == "normal"
        assert app.midi_tab.activity_var.get() == "MIDI bereit"
    finally:
        _close_window(root, app)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows desktop operation test")
def test_port_refresh_and_preview_are_rejected_during_bank_receive(
    monkeypatch,
    valid_bank_bytes: bytes,
    tk_root: tk.Tk,
) -> None:
    root, app = _window(monkeypatch, valid_bank_bytes, tk_root)
    refresh_calls = 0

    def count_outputs() -> tuple[str, ...]:
        nonlocal refresh_calls
        refresh_calls += 1
        return ("CHANGED",)

    monkeypatch.setattr("gui.main_window.list_midi_output_ports", count_outputs)
    preview_calls: list[object] = []
    monkeypatch.setattr("gui.main_window.send_temporary_patch", lambda *args, **kwargs: preview_calls.append(args))
    token = app.midi_operations.try_begin(MidiOperation.BANK_RECEIVE)
    assert token is not None
    try:
        app.refresh_midi_ports()
        app.send_selected_to_buffer()
        assert refresh_calls == 0
        assert preview_calls == []
        assert app.midi_tab.output_port_var.get() == "D-50 OUT"
        assert app.midi_operations.active_token == token
    finally:
        app.midi_operations.finish(token)
        _close_window(root, app)
