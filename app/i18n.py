"""Central German UI strings; later languages can provide another catalog."""

from __future__ import annotations

STRINGS: dict[str, str] = {
    "app_title": "D-50 Patch Librarian",
    "tab_bank": "Bank Editor",
    "tab_midi": "MIDI / Transfer",
    "tab_diagnostics": "Diagnose",
    "new_bank": "Neue Bank",
    "open_bank": "Bank öffnen",
    "open_project": "Projekt öffnen",
    "save_project": "Projekt speichern",
    "export_bank": "Bank exportieren",
    "export_patches": "Patches exportieren",
    "undo": "Undo",
    "redo": "Redo",
    "import_patches": "Einzelpatches importieren",
    "import_folder": "Patchordner importieren",
    "import_bank_patches": "Patches aus Bank importieren",
    "take_reverbs": "Reverbs aus Bank übernehmen",
    "rename": "Umbenennen",
    "save_single": "Als Einzel-SysEx speichern…",
    "copy": "Kopieren",
    "cut": "Ausschneiden",
    "paste": "Einfügen",
    "duplicate": "Duplizieren nach…",
    "move": "Verschieben/Tauschen nach…",
    "clear": "Slot leeren",
    "delete_shift": "Löschen und nachrücken",
    "empty": "leer",
    "ready": "Bereit",
    "phase3": "MIDI-Senden und -Empfangen wird in Phase 3/4 aktiviert.",
}


def tr(key: str, **values: object) -> str:
    return STRINGS.get(key, key).format(**values)

