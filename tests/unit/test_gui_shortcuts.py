from __future__ import annotations

from types import SimpleNamespace

from gui.main_window import MainWindow


class _Widget:
    def __init__(self, widget_class: str) -> None:
        self.widget_class = widget_class

    def winfo_class(self) -> str:
        return self.widget_class


def test_bank_undo_shortcut_is_not_used_inside_input_widgets() -> None:
    app = MainWindow.__new__(MainWindow)
    calls: list[str] = []

    for widget_class in ("Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"):
        event = SimpleNamespace(widget=_Widget(widget_class))
        assert app._shortcut(event, lambda: calls.append(widget_class)) is None

    assert calls == []


def test_bank_shortcut_runs_outside_input_widgets() -> None:
    app = MainWindow.__new__(MainWindow)
    calls: list[str] = []

    result = app._shortcut(SimpleNamespace(widget=_Widget("TButton")), lambda: calls.append("undo"))

    assert result == "break"
    assert calls == ["undo"]
