"""Windows-oriented Phase-2 desktop application."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from app.i18n import tr
from app.version import __version__
from d50.bank_codec import parse_bank
from d50.classifier import classify
from domain.enums import DumpType
from domain.project import BankProject
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


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.editor = BankEditorService()
        self.selection: set[int] = {0}
        self._configure_root()
        self._build_menu()
        self._build_toolbar()
        self._build_content()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh("Neue leere Arbeitsbank")

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
        edit_menu.add_command(label="Umbenennen", accelerator="F2", command=self.rename_selected)
        edit_menu.add_command(label="Slot leeren", accelerator="Entf", command=self.clear_selected)
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
        )
        for label, command in actions:
            ttk.Button(toolbar, text=label, command=command, style="Toolbar.TButton").pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8)
        self.undo_button = ttk.Button(toolbar, text="Undo", command=self.undo, style="Toolbar.TButton")
        self.undo_button.pack(side="left", padx=2)
        self.redo_button = ttk.Button(toolbar, text="Redo", command=self.redo, style="Toolbar.TButton")
        self.redo_button.pack(side="left", padx=2)
        ttk.Label(toolbar, text="MIDI: Phase 3", foreground="#666666").pack(side="right", padx=8)

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
            on_import_singles=self.import_singles,
            on_import_bank=self.import_from_bank,
            on_take_reverbs=self.take_reverbs_from_bank,
        )
        self.midi_tab = MidiTransferTab(self.notebook)
        self.diagnostics_tab = DiagnosticsTab(self.notebook)
        self.notebook.add(self.bank_tab, text=tr("tab_bank"))
        self.notebook.add(self.midi_tab, text=tr("tab_midi"))
        self.notebook.add(self.diagnostics_tab, text=tr("tab_diagnostics"))
        ttk.Separator(self.root).pack(fill="x")
        self.status = StatusBar(self.root)
        self.status.pack(fill="x")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda _event: self.new_project())
        self.root.bind("<Control-o>", lambda _event: self.open_bank())
        self.root.bind("<Control-s>", lambda _event: self.save_project())
        self.root.bind("<Control-z>", lambda _event: self.undo())
        self.root.bind("<Control-y>", lambda _event: self.redo())
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
        if widget_class in {"Entry", "TEntry", "Text", "TCombobox", "Spinbox"}:
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
        reverb = "Reverbs vollständig" if self.project.has_complete_reverbs else "Reverbs fehlen"
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
            written = self.editor.import_patches(list(bank.patches[:count]), start_index=min(self.selection))
            if not self.project.has_complete_reverbs and messagebox.askyesno(
                "Reverb-Basis übernehmen",
                "Die Arbeitsbank besitzt keine vollständige Reverb-Basis. Reverbs 17–32 aus der Quellbank übernehmen?",
                parent=self.root,
            ):
                self.editor.set_reverbs(bank.reverbs)
                self.project.device_id = bank.device_id
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
            self.project.device_id = bank.device_id
            self.refresh(f"Reverbs 17–32 aus {bank.label} übernommen")
        except Exception as exc:
            self._show_error("Reverb-Basis konnte nicht übernommen werden", exc, path)

    def export_bank(self) -> None:
        fill_patch = None
        if not self.project.has_complete_reverbs:
            messagebox.showerror(
                "Bankexport blockiert",
                "Reverb-Basis 17–32 fehlt. Verwende zuerst 'Import → Reverbs 17–32 aus Bank'.",
                parent=self.root,
            )
            return
        if self.project.empty_count:
            occupied = [index for index in sorted(self.selection) if self.project.slots[index] is not None]
            if not occupied:
                occupied = self.project.occupied_indices()[:1]
            if not occupied:
                messagebox.showerror("Bankexport blockiert", "Die Arbeitsbank enthält keinen Patch.", parent=self.root)
                return
            fill_index = occupied[0]
            fill_patch = self.project.slots[fill_index].patch  # type: ignore[union-attr]
            row, column = divmod(fill_index, 8)
            if not messagebox.askyesno(
                "Leere Slots auffüllen",
                f"{self.project.empty_count} leere Slots werden im SysEx-Export mit "
                f"'{fill_patch.name}' aus Slot {row + 1}-{column + 1} gefüllt.\n\n"
                "Das Arbeitsprojekt behält seine leeren Slots. Fortfahren?",
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
            self.refresh(f"Bank exportiert: {target.name}")
            messagebox.showinfo(
                "Bank exportiert",
                f"Vollständige D-50-Bank gespeichert:\n{target}\n\n64 Patches + Reverbs 17–32",
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
            initialfile=f"{row + 1:02d}-{column + 1}_{patch.name.replace(' ', '_')}.syx",
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
        occupied = [index for index in self.selection if self.project.slots[index] is not None]
        if not occupied:
            return
        if not messagebox.askyesno(
            "Slots leeren",
            f"{len(occupied)} belegte(n) Slot(s) leeren?",
            parent=self.root,
        ):
            return
        self.editor.clear(occupied)
        self.refresh(f"{len(occupied)} Slot(s) geleert")

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

    def show_context_menu(self, index: int, x: int, y: int) -> None:
        occupied = self.project.slots[index] is not None
        menu = tk.Menu(self.root, tearoff=False)
        if occupied:
            menu.add_command(label="Vorhören: Dump into Buffer (Phase 3)", state="disabled")
            menu.add_command(label=tr("save_single"), command=self.save_selected_single)
            menu.add_command(label=tr("rename"), command=self.rename_selected)
            menu.add_separator()
            menu.add_command(label=tr("copy"), command=self.copy)
            menu.add_command(label=tr("cut"), command=self.cut)
            menu.add_command(label=tr("paste"), command=self.paste)
            menu.add_command(label=tr("duplicate"), command=self.duplicate_to)
            menu.add_command(label=tr("move"), command=self.move_dialog)
            menu.add_separator()
            menu.add_command(label=tr("clear"), command=self.clear_selected)
            menu.add_command(label=tr("delete_shift"), command=self.delete_and_shift)
        else:
            menu.add_command(label=tr("import_patches"), command=self.import_singles)
            menu.add_command(label=tr("paste"), command=self.paste)
        menu.tk_popup(x, y)

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
            "Phase 2: Bankeditor und Dateiworkflows\n"
            "Kein Klangparameter-Editor\n\n"
            "MIDI-Senden/Empfangen folgt in Phase 3/4.",
            parent=self.root,
        )

    def close(self) -> None:
        if self._ask_save_if_dirty():
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
