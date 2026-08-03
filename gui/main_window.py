"""Windows-oriented Phase-2 desktop application."""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from app.i18n import tr
from app.version import __version__
from d50.bank_codec import parse_bank
from d50.classifier import classify
from d50.patch_codec import create_init_patch
from domain.enums import DumpType
from domain.project import BankProject
from midi.bank_transfer import (
    BankReceiveReport,
    BankSendReport,
    BankTransferCancelled,
    receive_full_bank_handshake,
    send_full_bank_handshake,
)
from midi.operation_manager import MidiOperation, MidiOperationManager, OperationToken
from midi.temporary_sender import (
    MidiTransferError,
    list_midi_input_ports,
    list_midi_output_ports,
    send_temporary_patch,
    test_midi_input_port,
    test_midi_output_port,
)
from services.bank_editor_service import BankEditorService
from services.bank_file_service import (
    export_selected_patch_files,
    load_bank_file,
    load_single_patch_file,
    save_project_bank_file,
    save_single_patch_file,
)
from services.project_service import load_project, save_project
from services.patch_export_service import safe_filename_component

from .bank_editor_tab import BankEditorTab
from .diagnostics_tab import DiagnosticsTab
from .dialogs.rename_dialog import ask_patch_name
from .midi_transfer_tab import MidiTransferTab
from .widgets.status_bar import StatusBar


_LOGGER = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.editor = BankEditorService()
        self.selection: set[int] = {0}
        self.midi_operations = MidiOperationManager()
        self._midi_thread: threading.Thread | None = None
        self._midi_events: queue.Queue[tuple[str, OperationToken, object]] = queue.Queue()
        self._midi_success = None
        self._midi_error = None
        self._midi_progress = None
        self._bank_cancel_event = threading.Event()
        self._configure_root()
        self._build_menu()
        self._build_toolbar()
        self._build_content()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh("Neue leere Arbeitsbank")
        self._midi_poll_id = self.root.after(25, self._poll_midi_events)

    @property
    def project(self) -> BankProject:
        return self.editor.project

    def _configure_root(self) -> None:
        self.root.title(f"{tr('app_title')} v{__version__}")
        self.root.geometry("1500x880")
        self.root.minsize(1180, 720)
        self.root.option_add("*Font", "{Segoe UI} 11")
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Toolbar.TButton", padding=(10, 6))
        style.configure("TNotebook.Tab", padding=(14, 7))

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Neue Bank", accelerator="Strg+N", command=self.new_project)
        file_menu.add_command(label="D-50-Bank öffnen…", accelerator="Strg+O", command=self.open_bank)
        file_menu.add_command(label="Projekt öffnen…", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Projekt speichern", accelerator="Strg+S", command=self.save_project)
        file_menu.add_command(label="Projekt speichern unter…", command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="Bank als SysEx exportieren…", command=self.export_bank)
        file_menu.add_command(label="Ausgewählte Patches exportieren…", command=self.export_selected)
        file_menu.add_command(label="Alle belegten Patches exportieren…", command=self.export_all)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.close)
        menu.add_cascade(label="Datei", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Rückgängig", accelerator="Strg+Z", command=self.undo)
        edit_menu.add_command(label="Wiederholen", accelerator="Strg+Y", command=self.redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Kopieren", accelerator="Strg+C", command=self.copy)
        edit_menu.add_command(label="Ausschneiden", accelerator="Strg+X", command=self.cut)
        edit_menu.add_command(label="Einfügen", accelerator="Strg+V", command=self.paste)
        edit_menu.add_separator()
        edit_menu.add_command(label="Neuer Patch (INIT SAW)", command=self.initialize_selected)
        edit_menu.add_command(label="Umbenennen", accelerator="F2", command=self.rename_selected)
        edit_menu.add_command(label="Platz leeren (INIT SAW)", accelerator="Entf", command=self.clear_selected)
        edit_menu.add_command(label="Löschen und nachrücken", command=self.delete_and_shift)
        menu.add_cascade(label="Bearbeiten", menu=edit_menu)

        import_menu = tk.Menu(menu, tearoff=False)
        import_menu.add_command(label="Einzelpatches…", command=self.import_singles)
        import_menu.add_command(label="Patchordner…", command=self.import_folder)
        import_menu.add_command(label="Patches aus vollständiger Bank…", command=self.import_from_bank)
        import_menu.add_command(label="Reverbs 17–32 aus Bank…", command=self.take_reverbs_from_bank)
        menu.add_cascade(label="Import", menu=import_menu)

        sort_menu = tk.Menu(menu, tearoff=False)
        sort_menu.add_command(label="Name A–Z", command=lambda: self.sort_slots("name"))
        sort_menu.add_command(label="Name Z–A", command=lambda: self.sort_slots("name", reverse=True))
        sort_menu.add_command(label="Kategorie", command=lambda: self.sort_slots("category"))
        sort_menu.add_command(label="Reverb Type", command=lambda: self.sort_slots("reverb"))
        sort_menu.add_command(label="Originalreihenfolge", command=lambda: self.sort_slots("original"))
        menu.add_cascade(label="Sortieren", menu=sort_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Über D-50 Patch Librarian", command=self.show_about)
        menu.add_cascade(label="Hilfe", menu=help_menu)
        self.root.configure(menu=menu)

    def _build_toolbar(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(8, 6))
        toolbar.pack(fill="x")
        actions = (
            ("Neue Bank", self.new_project),
            ("Bank öffnen", self.open_bank),
            ("Projekt öffnen", self.open_project),
            ("Projekt speichern", self.save_project),
            ("Bank exportieren", self.export_bank),
            ("Patches exportieren", self.export_selected),
            ("INIT SAW", self.initialize_selected),
        )
        for label, command in actions:
            ttk.Button(toolbar, text=label, command=command, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        self.undo_button = ttk.Button(toolbar, text="Undo", command=self.undo, style="Toolbar.TButton")
        self.undo_button.pack(side="left", padx=2)
        self.redo_button = ttk.Button(toolbar, text="Redo", command=self.redo, style="Toolbar.TButton")
        self.redo_button.pack(side="left", padx=2)
        ttk.Label(toolbar, text="MIDI: Temporary Buffer", foreground="#666666").pack(side="right", padx=8)

    def _build_content(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)
        self.bank_tab = BankEditorTab(
            self.notebook,
            on_selection=self.on_selection,
            on_activate=lambda _index: self.rename_selected(),
            on_context=self.show_context_menu,
            on_move=self.move_or_swap,
            on_metadata=self.apply_metadata,
            on_rename=self.rename_selected,
            on_save_single=self.save_selected_single,
            on_preview=self.send_selected_to_buffer,
            on_new_patch=self.initialize_selected,
            on_import_singles=self.import_singles,
            on_import_bank=self.import_from_bank,
            on_take_reverbs=self.take_reverbs_from_bank,
        )
        self.midi_tab = MidiTransferTab(
            self.notebook,
            on_refresh_ports=self.refresh_midi_ports,
            on_test_ports=self.test_selected_midi_ports,
            on_send_bank=self.send_bank_to_d50,
            on_receive_bank=self.receive_bank_from_d50,
            on_cancel=self.cancel_bank_transfer,
        )
        self.diagnostics_tab = DiagnosticsTab(self.notebook)
        self.notebook.add(self.bank_tab, text=tr("tab_bank"))
        self.notebook.add(self.midi_tab, text=tr("tab_midi"))
        self.notebook.add(self.diagnostics_tab, text=tr("tab_diagnostics"))
        ttk.Separator(self.root).pack(fill="x")
        self.status = StatusBar(self.root)
        self.status.pack(fill="x")
        self.refresh_midi_ports(show_errors=False)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _event: self.new_project())
        self.root.bind("<Control-o>", lambda _event: self.open_bank())
        self.root.bind("<Control-s>", lambda _event: self.save_project())
        self.root.bind("<Control-z>", lambda event: self._shortcut(event, self.undo))
        self.root.bind("<Control-y>", lambda event: self._shortcut(event, self.redo))
        self.root.bind("<Control-c>", lambda event: self._shortcut(event, self.copy))
        self.root.bind("<Control-x>", lambda event: self._shortcut(event, self.cut))
        self.root.bind("<Control-v>", lambda event: self._shortcut(event, self.paste))
        self.root.bind("<Control-a>", lambda event: self._shortcut(event, self.select_all))
        self.root.bind("<F2>", lambda event: self._shortcut(event, self.rename_selected))
        self.root.bind("<Delete>", lambda event: self._shortcut(event, self.clear_selected))
        self.root.bind("<Alt-Up>", lambda event: self._shortcut(event, lambda: self.move_selected(-8)))
        self.root.bind("<Alt-Down>", lambda event: self._shortcut(event, lambda: self.move_selected(8)))
        self.root.bind("<Alt-Left>", lambda event: self._shortcut(event, lambda: self.move_selected(-1)))
        self.root.bind("<Alt-Right>", lambda event: self._shortcut(event, lambda: self.move_selected(1)))

    def _shortcut(self, event: tk.Event, command) -> str | None:
        widget_class = event.widget.winfo_class() if event.widget is not None else ""
        if widget_class in {"Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"}:
            return None
        command()
        return "break"

    def refresh(self, message: str = "Bereit") -> None:
        self.bank_tab.matrix.refresh(self.project)
        self.bank_tab.refresh_summary(self.project)
        self._refresh_details()
        dirty = " *" if self.editor.dirty else ""
        self.root.title(f"{tr('app_title')} v{__version__} — {self.project.label}{dirty}")
        self.undo_button.configure(state="normal" if self.editor.undo_stack.can_undo else "disabled")
        self.redo_button.configure(state="normal" if self.editor.undo_stack.can_redo else "disabled")
        self.midi_tab.show_bank(
            label=self.project.label,
            occupied=self.project.occupied_count,
            empty=self.project.empty_count,
            reverbs_complete=self.project.has_complete_reverbs,
        )
        reverb_parts: list[str] = []
        if self.project.reverb_conflict_count:
            reverb_parts.append(f"{self.project.reverb_conflict_count} Reverbkonflikt(e)")
        if self.project.reverb_missing_count:
            reverb_parts.append(f"{self.project.reverb_missing_count} Quelle(n) unbekannt")
        if not reverb_parts:
            reverb_parts.append("Reverbs vollständig" if self.project.has_complete_reverbs else "Reverbs fehlen")
        reverb = " · ".join(reverb_parts)
        self.status.set(message, f"{self.project.occupied_count}/64 Patches · {reverb}")

    def _refresh_details(self) -> None:
        if len(self.selection) != 1:
            self.bank_tab.details.set_empty(f"{len(self.selection)} Slots ausgewählt")
            return
        index = next(iter(self.selection))
        slot = self.project.slots[index]
        if slot is None:
            self.bank_tab.details.set_empty("Leerer Slot")
        else:
            self.bank_tab.details.show_patch(index, slot)

    def on_selection(self, indices: set[int]) -> None:
        self.selection = indices
        self.bank_tab.matrix.selected = set(indices)
        self.bank_tab.matrix.refresh(self.project)
        self._refresh_details()
        self.status.set(f"{len(indices)} Slot(s) ausgewählt")

    def _ask_save_if_dirty(self) -> bool:
        if not self.editor.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Ungespeicherte Änderungen",
            "Das aktuelle Projekt enthält ungespeicherte Änderungen. Jetzt speichern?",
            parent=self.root,
        )
        if answer is None:
            return False
        if answer:
            return self.save_project()
        return True

    def new_project(self) -> bool:
        if not self._ask_save_if_dirty():
            return False
        name = simpledialog.askstring("Neue Bank", "Bank-/Projektname:", initialvalue="Neue Bank", parent=self.root)
        if name is None:
            return False
        self.editor.replace_project(BankProject.empty(name.strip() or "Neue Bank"))
        self.selection = {0}
        self.bank_tab.matrix.set_selection(self.selection, notify=False)
        self.refresh("Neue leere Arbeitsbank erstellt")
        return True

    def load_path(self, path: str | Path) -> bool:
        """Open a project/bank/single supplied by file association or drag-to-EXE."""
        source = Path(path)
        try:
            if source.suffix.casefold() == ".d50proj":
                self.editor.replace_project(load_project(source))
                message = f"Projekt geladen: {source.name}"
            else:
                data = source.read_bytes()
                result = classify(data)
                if result.dump_type == DumpType.D50_FULL_BANK:
                    bank = parse_bank(data, source_path=source)
                    self.editor.replace_project(BankProject.from_bank(bank, source_path=source))
                    message = f"Bank geladen: {source.name}"
                elif result.dump_type in {
                    DumpType.D50_SINGLE_PATCH_TEMP,
                    DumpType.D50_SINGLE_PATCH_MEMORY,
                }:
                    patch = load_single_patch_file(source)
                    project = BankProject.empty(source.stem)
                    project.insert_patches([patch], start_index=0)
                    self.editor.replace_project(project)
                    message = f"Einzelpatch geladen: {patch.name}"
                else:
                    detail = result.issues[0] if result.issues else result.dump_type.value
                    raise ValueError(f"Nicht unterstützte oder beschädigte Datei: {detail}")
            self.selection = {0}
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh(message)
            self.diagnostics_tab.append(f"Datei erfolgreich geladen: {source}")
            return True
        except Exception as exc:
            self._show_error("Datei konnte nicht geöffnet werden", exc, source)
            return False

    def open_bank(self) -> bool:
        if not self._ask_save_if_dirty():
            return False
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Vollständige D-50-Bank öffnen",
            filetypes=(("D-50 SysEx", "*.syx"), ("Alle Dateien", "*.*")),
        )
        if not path:
            return False
        return self.load_path(path)

    def open_project(self) -> bool:
        if not self._ask_save_if_dirty():
            return False
        path = filedialog.askopenfilename(
            parent=self.root,
            title="D-50-Projekt öffnen",
            filetypes=(("D-50-Projekt", "*.d50proj"), ("Alle Dateien", "*.*")),
        )
        if not path:
            return False
        try:
            self.editor.replace_project(load_project(path))
            self.selection = {0}
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh(f"Projekt geladen: {Path(path).name}")
            return True
        except Exception as exc:
            self._show_error("Projekt konnte nicht geöffnet werden", exc, path)
            return False

    def save_project(self) -> bool:
        if not self.project.project_path:
            return self.save_project_as()
        try:
            target = save_project(self.project, self.project.project_path, overwrite=True)
            self.editor.mark_saved()
            self.refresh(f"Projekt gespeichert: {target.name}")
            return True
        except Exception as exc:
            self._show_error("Projekt konnte nicht gespeichert werden", exc, self.project.project_path)
            return False

    def save_project_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Projekt speichern unter",
            defaultextension=".d50proj",
            initialfile=f"{safe_filename_component(self.project.label, fallback='D50_Projekt')}.d50proj",
            filetypes=(("D-50-Projekt", "*.d50proj"),),
        )
        if not path:
            return False
        try:
            target = save_project(self.project, path, overwrite=True)
            self.editor.mark_saved()
            self.refresh(f"Projekt gespeichert: {target.name}")
            return True
        except Exception as exc:
            self._show_error("Projekt konnte nicht gespeichert werden", exc, path)
            return False

    def import_singles(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="D-50-Einzelpatches importieren",
            filetypes=(("D-50 SysEx", "*.syx"), ("Alle Dateien", "*.*")),
        )
        if paths:
            self._import_patch_paths([Path(path) for path in paths])

    def import_folder(self) -> None:
        directory = filedialog.askdirectory(parent=self.root, title="Ordner mit Einzelpatches auswählen")
        if not directory:
            return
        paths = sorted(Path(directory).glob("*.syx"), key=lambda path: path.name.casefold())
        if not paths:
            messagebox.showinfo("Keine Dateien", "Im gewählten Ordner wurden keine .syx-Dateien gefunden.", parent=self.root)
            return
        self._import_patch_paths(paths)

    def _import_patch_paths(self, paths: list[Path]) -> None:
        patches = []
        errors: list[str] = []
        for path in paths:
            try:
                patches.append(load_single_patch_file(path))
            except Exception as exc:
                errors.append(f"{path.name}: {exc}")
        if patches:
            try:
                if len(patches) == 1 and len(self.selection) == 1:
                    target = next(iter(self.selection))
                    if self.project.slots[target] is not None:
                        answer = messagebox.askyesnocancel(
                            "Slot belegt",
                            "Der ausgewählte Slot ist belegt.\n\nJa = ersetzen\nNein = nächsten freien Slot verwenden",
                            parent=self.root,
                        )
                        if answer is None:
                            return
                        if answer:
                            self.editor.replace_patch(target, patches[0])
                            written = [target]
                        else:
                            written = self.editor.import_patches(patches, start_index=target)
                    else:
                        self.editor.replace_patch(target, patches[0])
                        written = [target]
                else:
                    start = min(self.selection) if self.selection else None
                    written = self.editor.import_patches(patches, start_index=start)
                self.selection = set(written)
                self.bank_tab.matrix.set_selection(self.selection, notify=False)
                self.refresh(f"{len(written)} Patch(es) importiert")
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            messagebox.showwarning(
                "Import mit Hinweisen",
                "Folgende Dateien/Aktionen wurden abgelehnt:\n\n" + "\n".join(errors[:12]),
                parent=self.root,
            )
            self.diagnostics_tab.append("Importfehler:\n" + "\n".join(errors))

    def import_from_bank(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Quellbank auswählen",
            filetypes=(("D-50 SysEx", "*.syx"), ("Alle Dateien", "*.*")),
        )
        if not path:
            return
        try:
            bank = load_bank_file(path)
            free = self.project.empty_count
            if free == 0:
                raise ValueError("Die Arbeitsbank besitzt keine freien Slots")
            count = min(free, 64)
            if not messagebox.askyesno(
                "Patches aus Bank importieren",
                f"Die ersten {count} Patches aus '{bank.label}' in freie Slots importieren?",
                parent=self.root,
            ):
                return
            take_reverbs = False
            if not self.project.has_complete_reverbs:
                take_reverbs = messagebox.askyesno(
                    "Reverb-Basis übernehmen",
                    "Die Arbeitsbank besitzt keine vollständige Reverb-Basis. Reverbs 17–32 aus der Quellbank übernehmen?",
                    parent=self.root,
                )
            written = self.editor.import_bank_content(
                list(bank.patches[:count]),
                start_index=min(self.selection),
                reverbs=bank.reverbs if take_reverbs else None,
            )
            self.selection = set(written)
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh(f"{len(written)} Patches aus {bank.label} importiert")
        except Exception as exc:
            self._show_error("Bankpatches konnten nicht importiert werden", exc, path)

    def take_reverbs_from_bank(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Bank mit Reverb-Basis auswählen",
            filetypes=(("D-50 SysEx", "*.syx"), ("Alle Dateien", "*.*")),
        )
        if not path:
            return
        try:
            bank = load_bank_file(path)
            if self.project.has_complete_reverbs and not messagebox.askyesno(
                "Reverb-Basis ersetzen",
                "Die vorhandenen Reverbs 17–32 durch die gewählte Bank ersetzen?",
                parent=self.root,
            ):
                return
            self.editor.set_reverbs(bank.reverbs)
            self.refresh(f"Reverbs 17–32 aus {bank.label} übernommen")
        except Exception as exc:
            self._show_error("Reverb-Basis konnte nicht übernommen werden", exc, path)

    def export_bank(self) -> None:
        filled_count = self.project.empty_count
        fill_patch = (
            create_init_patch(source_device_id=self.project.device_id)
            if filled_count
            else None
        )
        if not self.project.has_complete_reverbs:
            messagebox.showerror(
                "Bankexport blockiert",
                "Reverb-Basis 17–32 fehlt. Verwende zuerst 'Import → Reverbs 17–32 aus Bank'.",
                parent=self.root,
            )
            return
        if (self.project.reverb_conflict_count or self.project.reverb_missing_count) and not messagebox.askyesno(
            "Ungeklärte Reverbabhängigkeiten",
            f"{self.project.reverb_conflict_count} Patch(es) besitzen einen Reverbkonflikt.\n"
            f"{self.project.reverb_missing_count} Patch(es) besitzen keine bekannte Original-Reverbquelle.\n\n"
            "Die Bank ist technisch vollständig, kann bei diesen Patches aber anders klingen. Trotzdem exportieren?",
            parent=self.root,
        ):
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Vollständige D-50-Bank exportieren",
            defaultextension=".syx",
            initialfile=f"{safe_filename_component(self.project.label, fallback='D50_Bank')}.syx",
            filetypes=(("D-50 SysEx", "*.syx"),),
        )
        if not path:
            return
        try:
            target = save_project_bank_file(self.project, path, fill_patch=fill_patch, overwrite=True)
            fill_note = f"\n{filled_count} freie Slots wurden als INIT SAW exportiert." if filled_count else ""
            self.refresh(
                f"Bank exportiert: {target.name}"
                + (f" · {filled_count}× INIT SAW" if filled_count else "")
            )
            messagebox.showinfo(
                "Bank exportiert",
                f"Vollständige D-50-Bank gespeichert:\n{target}\n\n"
                f"64 Patches + Reverbs 17–32{fill_note}",
                parent=self.root,
            )
        except Exception as exc:
            self._show_error("Bank konnte nicht exportiert werden", exc, path)

    def export_selected(self) -> None:
        indices = [index for index in sorted(self.selection) if self.project.slots[index] is not None]
        self._export_patch_indices(indices)

    def export_all(self) -> None:
        self._export_patch_indices(self.project.occupied_indices())

    def _export_patch_indices(self, indices: list[int]) -> None:
        if not indices:
            messagebox.showinfo("Keine Patches", "Es sind keine belegten Slots ausgewählt.", parent=self.root)
            return
        directory = filedialog.askdirectory(parent=self.root, title="Zielordner auswählen")
        if not directory:
            return
        bank_directory = Path(directory) / safe_filename_component(self.project.label, fallback="D50_Bank")
        overwrite = False
        if bank_directory.exists() and any(bank_directory.glob("*.syx")):
            overwrite = messagebox.askyesno(
                "Vorhandene Dateien",
                "Im Zielordner befinden sich bereits SysEx-Dateien. Gleichnamige Dateien ersetzen?",
                parent=self.root,
            )
            if not overwrite:
                return
        try:
            written = export_selected_patch_files(
                self.project,
                indices,
                directory,
                overwrite=overwrite,
            )
            self.refresh(f"{len(written)} Einzelpatches exportiert")
            messagebox.showinfo(
                "Export abgeschlossen",
                f"{len(written)} Einzelpatches gespeichert nach:\n{written[0].parent}",
                parent=self.root,
            )
        except Exception as exc:
            self._show_error("Patches konnten nicht exportiert werden", exc, directory)

    def save_selected_single(self) -> None:
        index = self._single_occupied_index()
        if index is None:
            return
        patch = self.project.slots[index].patch  # type: ignore[union-attr]
        row, column = divmod(index, 8)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Patch als Einzel-SysEx speichern",
            defaultextension=".syx",
            initialfile=(
                f"{row + 1:02d}-{column + 1}_"
                f"{safe_filename_component(patch.name, fallback='D50_Patch')}.syx"
            ),
            filetypes=(("D-50 SysEx", "*.syx"),),
        )
        if not path:
            return
        try:
            save_single_patch_file(patch, path, device_id=self.project.device_id, overwrite=True)
            self.refresh(f"Einzelpatch gespeichert: {Path(path).name}")
        except Exception as exc:
            self._show_error("Einzelpatch konnte nicht gespeichert werden", exc, path)

    def rename_selected(self) -> None:
        index = self._single_occupied_index()
        if index is None:
            return
        patch = self.project.slots[index].patch  # type: ignore[union-attr]
        new_name = ask_patch_name(self.root, patch.name)
        if new_name is None or new_name == patch.name:
            return
        try:
            self.editor.rename(index, new_name)
            self.refresh(f"Patch {index // 8 + 1}-{index % 8 + 1} umbenannt")
        except Exception as exc:
            self._show_error("Patch konnte nicht umbenannt werden", exc)

    def apply_metadata(self, category: str, rating: int, notes: str) -> None:
        index = self._single_occupied_index(show_error=False)
        if index is None:
            return
        try:
            self.editor.update_metadata(index, category=category, rating=rating, notes=notes)
            self.refresh("Patchmetadaten übernommen")
        except Exception as exc:
            self._show_error("Metadaten konnten nicht gespeichert werden", exc)

    def copy(self) -> None:
        count = self.editor.copy(self.selection)
        self.status.set(f"{count} Patch(es) kopiert")

    def cut(self) -> None:
        count = self.editor.cut(self.selection)
        if count:
            self.refresh(f"{count} Patch(es) ausgeschnitten")

    def paste(self) -> None:
        try:
            written = self.editor.paste(min(self.selection) if self.selection else None)
            if not written:
                self.status.set("Zwischenablage ist leer")
                return
            self.selection = set(written)
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh(f"{len(written)} Patch(es) eingefügt")
        except Exception as exc:
            self._show_error("Einfügen nicht möglich", exc)

    def clear_selected(self) -> None:
        selected = sorted(self.selection)
        occupied_count = sum(self.project.slots[index] is not None for index in selected)
        if not messagebox.askyesno(
            "Plätze auf INIT SAW setzen",
            f"{len(selected)} ausgewählte(n) Platz/Plätze auf INIT SAW zurücksetzen?"
            + (f"\n\nDabei werden {occupied_count} vorhandene Patch(es) ersetzt." if occupied_count else ""),
            parent=self.root,
        ):
            return
        self._initialize_indices(selected)

    def initialize_selected(self) -> None:
        selected = sorted(self.selection)
        occupied_count = sum(self.project.slots[index] is not None for index in selected)
        if occupied_count and not messagebox.askyesno(
            "Neuer Patch",
            f"INIT SAW in {len(selected)} ausgewählte(n) Platz/Plätze einsetzen?\n\n"
            f"Dabei werden {occupied_count} vorhandene Patch(es) ersetzt.",
            parent=self.root,
        ):
            return
        self._initialize_indices(selected)

    def _initialize_indices(self, indices: list[int]) -> None:
        init_patch = create_init_patch(source_device_id=self.project.device_id)
        self.editor.initialize(indices, init_patch)
        self.refresh(f"{len(indices)} Platz/Plätze auf INIT SAW gesetzt")

    def delete_and_shift(self) -> None:
        index = self._single_occupied_index()
        if index is None:
            return
        if messagebox.askyesno(
            "Löschen und nachrücken",
            "Patch löschen und alle folgenden Slots um eine Position nachrücken?",
            parent=self.root,
        ):
            self.editor.delete_and_shift(index)
            self.refresh("Patch gelöscht; folgende Slots nachgerückt")

    def duplicate_to(self) -> None:
        source = self._single_occupied_index()
        if source is None:
            return
        target = self._ask_target_slot("Duplizieren nach", source)
        if target is None:
            return
        if self.project.slots[target] is not None and not messagebox.askyesno(
            "Ziel belegt", "Zielpatch ersetzen?", parent=self.root
        ):
            return
        self.editor.duplicate(source, target)
        self.selection = {target}
        self.bank_tab.matrix.set_selection(self.selection, notify=False)
        self.refresh("Patch dupliziert")

    def move_dialog(self) -> None:
        source = self._single_occupied_index()
        if source is None:
            return
        target = self._ask_target_slot("Verschieben/Tauschen nach", source)
        if target is not None:
            self.move_or_swap(source, target)

    def move_or_swap(self, source: int, target: int) -> None:
        try:
            self.editor.move_or_swap(source, target)
            self.selection = {target}
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh(f"Slot {source // 8 + 1}-{source % 8 + 1} → {target // 8 + 1}-{target % 8 + 1}")
        except Exception as exc:
            self._show_error("Patch konnte nicht verschoben werden", exc)

    def move_selected(self, delta: int) -> None:
        if len(self.selection) != 1:
            return
        source = next(iter(self.selection))
        target = source + delta
        if not 0 <= target < 64:
            return
        if delta == -1 and source % 8 == 0 or delta == 1 and source % 8 == 7:
            return
        self.move_or_swap(source, target)

    def sort_slots(self, key: str, *, reverse: bool = False) -> None:
        try:
            self.editor.sort(key, reverse=reverse)
            self.selection = {0}
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.refresh("Bank sortiert")
        except Exception as exc:
            self._show_error("Sortieren nicht möglich", exc)

    def undo(self) -> None:
        if self.editor.undo():
            self.refresh("Änderung rückgängig gemacht")
        else:
            self.status.set("Nichts rückgängig zu machen")

    def redo(self) -> None:
        if self.editor.redo():
            self.refresh("Änderung wiederholt")
        else:
            self.status.set("Nichts zu wiederholen")

    def select_all(self) -> None:
        self.selection = set(range(64))
        self.bank_tab.matrix.set_selection(self.selection, notify=False)
        self.refresh("Alle Slots ausgewählt")

    def _reject_busy_midi_operation(self) -> None:
        message = f"Eine MIDI-Übertragung läuft bereits: {self.midi_operations.active_label}."
        self.midi_tab.set_status(message)
        self.status.set(message)

    def _set_midi_ui_active(
        self,
        active: bool,
        *,
        label: str = "",
        cancellable: bool = False,
    ) -> None:
        self.midi_tab.set_operation_active(active, label=label, cancellable=cancellable)
        self.bank_tab.set_midi_busy(active)

    def _record_midi(self, token: OperationToken, message: str) -> None:
        line = f"[MIDI {token.operation.value.upper()} #{token.job_id}] {message}"
        _LOGGER.info(line)
        self.diagnostics_tab.append(line)

    def _begin_async_midi_operation(
        self,
        operation: MidiOperation,
        *,
        status: str,
        thread_name: str,
        worker_operation,
        success,
        error,
        progress=None,
        cancellable: bool = False,
    ) -> bool:
        token = self.midi_operations.try_begin(operation)
        if token is None:
            self._reject_busy_midi_operation()
            return False

        self._midi_success = success
        self._midi_error = error
        self._midi_progress = progress
        self._set_midi_ui_active(
            True,
            label=self.midi_operations.active_label,
            cancellable=cancellable,
        )
        self.midi_tab.set_status(status)
        self.status.set(status)
        self._record_midi(token, f"Start: {status}")

        def report_progress(value: object) -> None:
            self._midi_events.put(("progress", token, value))

        def run_worker() -> None:
            try:
                result = worker_operation(token, report_progress)
            except BaseException as exc:
                self._midi_events.put(("error", token, exc))
            else:
                self._midi_events.put(("success", token, result))

        thread = threading.Thread(target=run_worker, name=thread_name, daemon=True)
        self._midi_thread = thread
        try:
            thread.start()
        except BaseException:
            self._midi_thread = None
            self._midi_success = None
            self._midi_error = None
            self._midi_progress = None
            self.midi_operations.finish(token)
            self._set_midi_ui_active(False)
            raise
        return True

    def _poll_midi_events(self) -> None:
        while True:
            try:
                kind, token, payload = self._midi_events.get_nowait()
            except queue.Empty:
                break
            if self.midi_operations.active_token != token:
                _LOGGER.warning("Veraltetes MIDI-Ereignis für Job #%d ignoriert", token.job_id)
                continue
            if kind == "progress":
                if self._midi_progress is not None:
                    self._midi_progress(payload)
                continue

            success = self._midi_success
            error = self._midi_error
            self._midi_thread = None
            self._midi_success = None
            self._midi_error = None
            self._midi_progress = None
            if not self.midi_operations.finish(token):
                continue
            self._set_midi_ui_active(False)
            if kind == "success":
                self._record_midi(token, "Abgeschlossen")
                if success is not None:
                    success(payload)
            else:
                self._record_midi(token, f"Fehlgeschlagen: {payload}")
                if error is not None:
                    error(payload)

        try:
            if self.root.winfo_exists():
                self._midi_poll_id = self.root.after(25, self._poll_midi_events)
        except tk.TclError:
            return

    def refresh_midi_ports(self, *, show_errors: bool = True) -> None:
        token = self.midi_operations.try_begin(MidiOperation.PORT_REFRESH)
        if token is None:
            self._reject_busy_midi_operation()
            return
        self._set_midi_ui_active(True, label=self.midi_operations.active_label)
        self._record_midi(token, "MIDI-Ports werden aktualisiert")
        try:
            output_ports = list_midi_output_ports()
            input_ports = list_midi_input_ports()
            self.midi_tab.set_ports(output_ports, input_ports)
            message = (
                f"{len(output_ports)} MIDI-Ausgänge und {len(input_ports)} MIDI-Eingänge gefunden; "
                "bitte die beiden tatsächlich mit dem D-50 verbundenen Ports auswählen."
            )
            if not output_ports or not input_ports:
                message = "Für Bank-Handshake werden ein MIDI-Ausgang und ein MIDI-Eingang benötigt."
            self.midi_tab.set_status(message)
        except Exception as exc:
            self.midi_tab.set_ports((), ())
            self.midi_tab.set_status(f"MIDI nicht verfügbar: {exc}")
            if show_errors:
                self._show_error("MIDI-Ports konnten nicht gelesen werden", exc)
        finally:
            self._record_midi(token, "Portaktualisierung beendet")
            self.midi_operations.finish(token)
            self._set_midi_ui_active(False)

    def test_selected_midi_ports(self) -> None:
        token = self.midi_operations.try_begin(MidiOperation.PORT_TEST)
        if token is None:
            self._reject_busy_midi_operation()
            return
        self._set_midi_ui_active(True, label=self.midi_operations.active_label)
        try:
            output_name, input_name, _device_id = self.midi_tab.selected_bank_settings()
            self._record_midi(token, f"Teste Ausgang '{output_name}' und Eingang '{input_name}'")
            test_midi_output_port(output_name)
            test_midi_input_port(input_name)
            message = (
                f"Ausgang '{output_name}' und Eingang '{input_name}' lassen sich öffnen. "
                "Es wurden keine MIDI-Daten gesendet."
            )
            self.midi_tab.set_status(message)
            self.status.set("MIDI-Ein-/Ausgangstest erfolgreich")
        except Exception as exc:
            self._show_error("MIDI-Ein-/Ausgangstest fehlgeschlagen", exc)
        finally:
            self._record_midi(token, "Porttest beendet")
            self.midi_operations.finish(token)
            self._set_midi_ui_active(False)

    def send_selected_to_buffer(self) -> None:
        if self.midi_operations.is_busy:
            self._reject_busy_midi_operation()
            return
        index = self._single_occupied_index()
        if index is None:
            return
        patch = self.project.slots[index].patch  # type: ignore[union-attr]
        try:
            port_name, device_id, delay_ms = self.midi_tab.selected_preview_settings()
            if not port_name:
                raise MidiTransferError("Bitte zuerst im MIDI-Tab einen Ausgang auswählen")
        except Exception as exc:
            self._show_error("Patch konnte nicht in den Temporary Buffer gesendet werden", exc)
            return

        self._begin_async_midi_operation(
            MidiOperation.PREVIEW,
            status=f"Sende „{patch.name}“ an den D-50 Temporary Buffer …",
            thread_name="D50PatchPreview",
            worker_operation=lambda token, progress: send_temporary_patch(
                patch,
                port_name=port_name,
                device_id=device_id,
                delay_ms=delay_ms,
                progress=lambda current, total: progress(("frame", current, total)),
                job_id=token.job_id,
                diagnostic=lambda message: progress(("log", message)),
            ),
            progress=lambda value: self._show_preview_progress(port_name, value),
            success=self._finish_preview_success,
            error=lambda exc: self._show_error("Patch-Vorschau fehlgeschlagen", exc),
        )

    def _show_preview_progress(self, port_name: str, value: object) -> None:
        kind, *payload = value  # type: ignore[misc]
        if kind == "log":
            self.diagnostics_tab.append(payload[0])
            return
        current, total = payload
        self.midi_tab.set_progress("Patch-Vorschau", current, total)
        self.midi_tab.set_status(f"Sende DT1-Nachricht {current} von {total} an '{port_name}' …")

    def _finish_preview_success(self, report) -> None:
        message = (
            f"„{report.patch_name}“ wurde mit {report.message_count} DT1-Nachrichten "
            f"({report.data_byte_count} Patchbytes) gesendet. Der Empfang wurde vom D-50 nicht bestätigt. "
            "Die Vorschau bleibt experimentell; interne Patchplätze und Reverbs wurden nicht adressiert."
        )
        self.midi_tab.set_status(message)
        self.midi_tab.reset_progress("Patch-Vorschau abgeschlossen")
        self.status.set(f"Patch-Vorschau gesendet: {report.patch_name}")

    @property
    def bank_transfer_active(self) -> bool:
        return self.midi_operations.active_operation in {
            MidiOperation.BANK_SEND,
            MidiOperation.BANK_RECEIVE,
        }

    def send_bank_to_d50(self) -> None:
        if self.midi_operations.is_busy:
            self._reject_busy_midi_operation()
            return
        if not self.project.has_complete_reverbs:
            messagebox.showerror(
                "Bank-Senden blockiert",
                "Die Reverb-Basis 17–32 fehlt. Eine vollständige D-50-Bank kann so nicht gesendet werden.",
                parent=self.root,
            )
            return
        try:
            output_name, input_name, device_id = self.midi_tab.selected_bank_settings()
            if not output_name or not input_name:
                raise MidiTransferError("Bitte MIDI-Ausgang und MIDI-Eingang für den D-50 auswählen")
            filled_count = self.project.empty_count
            fill_patch = create_init_patch(source_device_id=device_id) if filled_count else None
            bank = self.project.to_bank(fill_patch=fill_patch)
        except Exception as exc:
            self._show_error("Bank kann nicht für MIDI vorbereitet werden", exc)
            return

        details = (
            "ACHTUNG: Der folgende Handshake überschreibt die komplette interne D-50-Bank:\n\n"
            "• 64 Patchplätze\n"
            "• Reverbprogramme 17–32\n\n"
            f"Arbeitsbank: {self.project.label}\n"
            f"Device ID: {device_id:02X}h"
        )
        if filled_count:
            details += f"\n{filled_count} leere App-Slots werden als INIT SAW gesendet."
        details += (
            "\n\nVorher Backup erstellen, Memory Protect ausschalten und den D-50 "
            "in DATA TRANSFER → B.Load bereitstellen. Jetzt senden?"
        )
        if not messagebox.askyesno("Komplette Bank an D-50 senden", details, parent=self.root):
            return

        self._begin_bank_transfer(
            MidiOperation.BANK_SEND,
            status="Handshake mit D-50 B.Load wird gestartet…",
            operation=lambda progress, cancelled, job_id: send_full_bank_handshake(
                bank,
                output_port_name=output_name,
                input_port_name=input_name,
                device_id=device_id,
                progress=progress,
                cancelled=cancelled,
                job_id=job_id,
            ),
            success=self._finish_bank_send,
        )

    def receive_bank_from_d50(self) -> None:
        if self.midi_operations.is_busy:
            self._reject_busy_midi_operation()
            return
        if not self._ask_save_if_dirty():
            return
        try:
            output_name, input_name, device_id = self.midi_tab.selected_bank_settings()
            if not output_name or not input_name:
                raise MidiTransferError("Bitte MIDI-Ausgang und MIDI-Eingang für den D-50 auswählen")
        except Exception as exc:
            self._show_error("Bankempfang kann nicht gestartet werden", exc)
            return
        if not messagebox.askokcancel(
            "Komplette Bank vom D-50 empfangen",
            "Die Anwendung öffnet jetzt beide MIDI-Ports und wartet auf den Handshake.\n\n"
            "Danach am D-50 DATA TRANSFER → B.Dump starten. Die empfangene Bank ersetzt erst nach "
            "vollständiger Prüfung die aktuelle Arbeitsbank. Fortfahren?",
            parent=self.root,
        ):
            return

        self._begin_bank_transfer(
            MidiOperation.BANK_RECEIVE,
            status="MIDI-Ports geöffnet; jetzt am D-50 B.Dump starten…",
            operation=lambda progress, cancelled, job_id: receive_full_bank_handshake(
                output_port_name=output_name,
                input_port_name=input_name,
                device_id=device_id,
                label="D-50 MIDI Bank",
                progress=progress,
                cancelled=cancelled,
                job_id=job_id,
            ),
            success=self._finish_bank_receive,
        )

    def _begin_bank_transfer(self, midi_operation: MidiOperation, *, status: str, operation, success) -> None:
        self._bank_cancel_event.clear()
        self.midi_tab.reset_progress("Handshake wird vorbereitet")
        self._begin_async_midi_operation(
            midi_operation,
            status=status,
            thread_name="D50BankTransfer",
            worker_operation=lambda token, progress: operation(
                lambda phase, current, total: progress((phase, current, total)),
                self._bank_cancel_event.is_set,
                token.job_id,
            ),
            progress=lambda value: self.midi_tab.set_progress(*value),
            success=success,
            error=self._finish_bank_transfer_error,
            cancellable=True,
        )

    def _finish_bank_send(self, report: BankSendReport) -> None:
        message = (
            f"Bank '{report.bank_label}' vollständig gesendet: {report.data_message_count} DAT-Blöcke, "
            f"{report.data_byte_count} Byte, jeder Block vom D-50 bestätigt."
        )
        self.midi_tab.set_status(message)
        self.midi_tab.reset_progress("Bank-Senden abgeschlossen")
        self.status.set("D-50-Bank per Handshake gesendet")
        messagebox.showinfo("Bankübertragung abgeschlossen", message, parent=self.root)

    def _finish_bank_receive(self, report: BankReceiveReport) -> None:
        self.editor.replace_project(BankProject.from_bank(report.bank), mark_dirty=True)
        self.selection = {0}
        self.bank_tab.matrix.set_selection(self.selection, notify=False)
        duplicate_note = (
            f" · {report.duplicate_data_message_count} Dublette(n)"
            if report.duplicate_data_message_count
            else ""
        )
        self.refresh(
            f"D-50-Bank empfangen: {report.unique_data_block_count} eindeutige DAT-Blöcke / "
            f"{report.data_byte_count} Byte{duplicate_note}"
        )
        self.midi_tab.set_status(
            "Vollständige D-50-Bank empfangen und geprüft. Bitte als Projekt oder SysEx sichern."
        )
        self.midi_tab.reset_progress("Bank-Empfang abgeschlossen")
        messagebox.showinfo(
            "Bank empfangen",
            "64 Patches und Reverbs 17–32 wurden vollständig empfangen und in die Arbeitsbank übernommen.",
            parent=self.root,
        )

    def _finish_bank_transfer_error(self, exc: BaseException) -> None:
        if isinstance(exc, BankTransferCancelled):
            self.midi_tab.set_status("Bankübertragung wurde abgebrochen.")
            self.midi_tab.reset_progress("Abgebrochen")
            self.status.set("MIDI-Bankübertragung abgebrochen")
            return
        self.midi_tab.reset_progress("Übertragung fehlgeschlagen")
        self._show_error("MIDI-Bankübertragung fehlgeschlagen", exc)

    def cancel_bank_transfer(self) -> None:
        if not self.bank_transfer_active:
            return
        self._bank_cancel_event.set()
        self.midi_tab.set_status("Abbruch angefordert; Handshake wird sicher beendet…")

    def show_context_menu(self, index: int, x: int, y: int) -> None:
        if self.selection != {index}:
            self.selection = {index}
            self.bank_tab.matrix.set_selection(self.selection, notify=False)
            self.bank_tab.matrix.refresh(self.project)
            self._refresh_details()
        occupied = self.project.slots[index] is not None
        menu = tk.Menu(self.root, tearoff=False)
        if occupied:
            menu.add_command(
                label="Vorhören (experimentell): Dump into Buffer",
                command=self.send_selected_to_buffer,
                state="disabled" if self.midi_operations.is_busy else "normal",
            )
            menu.add_command(label=tr("save_single"), command=self.save_selected_single)
            menu.add_command(label=tr("rename"), command=self.rename_selected)
            menu.add_separator()
            menu.add_command(label=tr("copy"), command=self.copy)
            menu.add_command(label=tr("cut"), command=self.cut)
            menu.add_command(label=tr("paste"), command=self.paste)
            menu.add_command(label=tr("duplicate"), command=self.duplicate_to)
            menu.add_command(label=tr("move"), command=self.move_dialog)
            menu.add_separator()
            menu.add_command(label="Platz leeren (INIT SAW)", command=self.clear_selected)
            menu.add_command(label=tr("delete_shift"), command=self.delete_and_shift)
        else:
            menu.add_command(label="Neuer Patch (INIT SAW)", command=self.initialize_selected)
            menu.add_separator()
            menu.add_command(label=tr("import_patches"), command=self.import_singles)
            menu.add_command(label=tr("paste"), command=self.paste)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _ask_target_slot(self, title: str, source: int) -> int | None:
        value = simpledialog.askstring(
            title,
            "Zielslot (z. B. 3-5, I35 oder 21):",
            initialvalue=f"{source // 8 + 1}-{source % 8 + 1}",
            parent=self.root,
        )
        if value is None:
            return None
        try:
            return self._parse_slot(value)
        except ValueError as exc:
            messagebox.showerror("Ungültiger Zielslot", str(exc), parent=self.root)
            return None

    @staticmethod
    def _parse_slot(value: str) -> int:
        normalized = value.strip().upper().removeprefix("I")
        if "-" in normalized:
            parts = normalized.split("-", 1)
        elif len(normalized) == 2 and normalized.isdigit() and all("1" <= part <= "8" for part in normalized):
            parts = [normalized[0], normalized[1]]
        elif normalized.isdigit() and 1 <= int(normalized) <= 64:
            return int(normalized) - 1
        else:
            raise ValueError("Slot als 1-1 bis 8-8, I11 bis I88 oder 1 bis 64 eingeben")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("Ungültiges Slotformat")
        row, column = (int(part) for part in parts)
        if not 1 <= row <= 8 or not 1 <= column <= 8:
            raise ValueError("Bank- und Patchnummer müssen zwischen 1 und 8 liegen")
        return (row - 1) * 8 + column - 1

    def _single_occupied_index(self, *, show_error: bool = True) -> int | None:
        if len(self.selection) != 1:
            if show_error:
                messagebox.showinfo("Auswahl", "Bitte genau einen belegten Slot auswählen.", parent=self.root)
            return None
        index = next(iter(self.selection))
        if self.project.slots[index] is None:
            if show_error:
                messagebox.showinfo("Auswahl", "Der ausgewählte Slot ist leer.", parent=self.root)
            return None
        return index

    def _show_error(self, title: str, exc: BaseException, path: str | Path | None = None) -> None:
        context = f"\n\nDatei: {path}" if path else ""
        messagebox.showerror(title, f"{exc}{context}", parent=self.root)
        self.diagnostics_tab.append(f"FEHLER: {title}: {exc}{context}")
        self.status.set(title)

    def show_about(self) -> None:
        messagebox.showinfo(
            "Über D-50 Patch Librarian",
            f"D-50 Patch Librarian v{__version__}\n\n"
            "Bankeditor, Dateiworkflows und vollständiger MIDI-Bank-Handshake\n"
            "Kein Klangparameter-Editor\n\n"
            "Experimentelle Patch-Vorschau sowie vollständiges Bank-Senden und -Empfangen.",
            parent=self.root,
        )

    def close(self) -> None:
        if self.midi_operations.is_busy:
            messagebox.showwarning(
                "MIDI-Operation läuft",
                f"Bitte zuerst '{self.midi_operations.active_label}' beenden und auf den Abschluss warten.",
                parent=self.root,
            )
            return
        if self._ask_save_if_dirty():
            try:
                self.root.after_cancel(self._midi_poll_id)
            except (AttributeError, tk.TclError):
                pass
            self.root.destroy()


def set_windows_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def run_gui(open_path: str | Path | None = None) -> int:
    set_windows_dpi_awareness()
    root = tk.Tk()
    app = MainWindow(root)
    if open_path is not None:
        app.load_path(open_path)
    auto_close = os.environ.get("D50_TEST_AUTOCLOSE_MS")
    if auto_close:
        root.after(max(1, int(auto_close)), root.destroy)
    root.mainloop()
    return 0
