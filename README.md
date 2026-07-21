# D-50 Patch Librarian

Windows-Patch-Librarian für den Roland D-50. Version `0.2.1` implementiert die im Bauplan
definierten **Phasen 1 und 2**: einen strikt validierenden SysEx-Codec sowie einen grafischen
8×8-Bankeditor mit Projekt-, Import-, Export- und Undo/Redo-Workflow.

Die Anwendung ist ein Librarian und Bankwerkzeug, **kein Soundparameter-Editor**. MIDI-Senden
und -Empfangen folgen in Phase 3/4.

## Grafischer Bankeditor in Phase 2

- vollständige D-50-Banken öffnen und alle 64 Patches anzeigen
- neue Arbeitsbanken mit echten leeren App-Slots erstellen
- Einzelpatchdateien, ganze Patchordner und Patches aus einer zweiten Bank importieren
- Patches per Mausziehen oder `Alt+Pfeil` verschieben/tauschen
- Rename, Sort A–Z/Z–A, Kategorie, Reverb und Originalreihenfolge
- Copy/Cut/Paste, Duplicate, Clear sowie Löschen und Nachrücken
- mindestens 100 Undo-/Redo-Schritte
- Kategorien, Bewertungen und Notizen pro Patch
- Projekte als `.d50proj` atomar speichern und laden
- ausgewählte oder alle belegten Patches als Einzel-SysEx exportieren
- vollständige Bank-SysEx exportieren; leere Slots werden nach ausdrücklicher Bestätigung mit
  einem ausgewählten vorhandenen Patch gefüllt
- Reverbs 17–32 aus einer vollständigen Quellbank übernehmen
- integrierter Diagnose-Tab

Start:

```powershell
python main.py
```

Eine `.syx`- oder `.d50proj`-Datei kann auch auf `D50PatchLibrarian.exe` gezogen werden.

## Fertiger Funktionsumfang in Phase 1

- striktes Trennen vollständiger `F0 … F7`-Frames; MIDI-Realtime-Bytes werden erlaubt
- Prüfung von Roland-ID `41`, D-50-Modell `14`, DT1-Command `12` und Device ID `00h–1Fh`
- Prüfung aller 7-Bit-Datenbytes, der Roland-Prüfsumme und der maximalen DT1-Nutzlast
- konfliktfreie Rekonstruktion des adressierten Speichers, unabhängig von Reihenfolge und Segmentierung
- Klassifikation als vollständige Bank, Teilbank, Temporary-Area-Einzelpatch,
  Memory-Einzelpatch, sonstige D-50-Daten, beschädigte Daten oder Fremdformat
- Import und kanonischer Export vollständiger Banken mit 64 Patches und Reverbs 17–32
- Import und kanonischer Export einzelner 448-Byte-Patches als sieben Temporary-Area-DT1-Frames
- Patch-, Tone- und Reverb-Metadaten sowie SHA-256-Hashes
- D-50-Zeichensatzprüfung mit korrekter kompakter 6-Bit-Codierung und sicheres Umbenennen des 18-Zeichen-Patchnamens
- atomischer Datei-Export; bestehende Ziele werden ohne `--force` nicht ersetzt
- CLI zum Prüfen, Kanonisieren und Exportieren aller Bankpatches

## Unterstützte Formate

Eine vollständige Bank wird anhand ihres rekonstruierten Adressraums `02 00 00` bis
`04 0E 7F` erkannt – nicht nur anhand der Dateigröße. Sie enthält 34.688 adressierte
Nutzdatenbytes. Die kanonische Ausgabe enthält 136 DT1-Nachrichten und ist 36.048 Byte groß.

Ein app-kompatibler Einzelpatch enthält exakt 448 Nutzdatenbytes in sieben DT1-Nachrichten:

```text
00 00 00  Upper Partial 1
00 00 40  Upper Partial 2
00 01 00  Upper Common
00 01 40  Lower Partial 1
00 02 00  Lower Partial 2
00 02 40  Lower Common
00 03 00  Patch (zuletzt)
```

Die kanonische Einzeldatei ist 518 Byte groß. Gleichwertig segmentierte Temporary-Area-Daten
und genau ein vollständiger, slot-ausgerichteter Memory-Patch werden ebenfalls importiert.

Reverbtypen 1–16 sind fest im D-50. Bei Reverb 17–32 markiert das Domainmodell, ob der
zugehörige globale Reverbblock aus einer vollständigen Quellbank vorhanden ist. Ein
Einzelpatch allein erhält in diesem Fall den Status `SOURCE_MISSING`.

## Installation aus dem Quellcode

Voraussetzung ist Python 3.11 oder 3.12 (64 Bit).

```powershell
cd "D:\Eigene Dateien\Eigene Dokumente\Playground\d50_sysex_editor"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Der Phase-1-Codec selbst verwendet nur die Python-Standardbibliothek. `pytest` und
`PyInstaller` werden nur für Tests beziehungsweise Builds benötigt.

## Diagnose-CLI

Datei prüfen und lesbar anzeigen:

```powershell
python main.py inspect tests\fixtures\valid_full_bank.syx
```

Maschinenlesbare Diagnose:

```powershell
python main.py inspect patch.syx --json
```

Bank oder Einzelpatch mit reproduzierbarer DT1-Aufteilung neu schreiben:

```powershell
python main.py canonicalize input.syx output.syx
```

Alle 64 Patches einer Bank in einen Unterordner exportieren:

```powershell
python main.py export-singles bank.syx export
```

Vorhandene Zieldateien werden nicht still überschrieben. Nur die explizite Option `--force`
erlaubt ein Ersetzen.

## Tests

```powershell
python tests\fixtures\generate_fixtures.py
python -m pytest
```

Die Binärfixtures werden von einem kleinen, vom Produktionscodec unabhängigen Generator
erstellt. Abgedeckt sind unter anderem:

- alle verbindlichen Golden-Adressen für Slot 1-1, 1-2, 8-8 und Reverb 17, 18, 32
- 34.688 Byte Banknutzdaten, 136 Frames und 36.048 Byte Bankdatei
- sieben Frames und 518 Byte Einzelpatchdatei
- Bank → Speicher → Modelle → kanonische Bank → Speicher, byteidentisch
- Einzelpatch- und 64-Einzelpatch-Roundtrips
- falsche Prüfsumme, abgeschnittener Frame, Fremdhersteller und anderes Roland-Modell
- Fremdbytes, falsche Device ID, gemischte Device IDs und widersprüchliche Überlappung
- ungültige Namen und unvollständige Banken

Die Fixtures sind synthetische Protokollfixtures und keine Werkspresets.

## Windows-Build

Debug-Build:

```powershell
scripts\build_windows_debug.bat
```

Kanonischer onedir-Build:

```powershell
scripts\build_windows.bat
```

Der Release-Build ist eine Windows-GUI ohne Konsolenfenster. Ein Doppelklick auf
`D50PatchLibrarian.exe` öffnet direkt den Bankeditor. Die App startet und arbeitet ohne
angeschlossenen D-50 und ohne MIDI-Pakete. Die Diagnose-CLI bleibt über Quellstart oder den
Debug-Build mit Unterbefehlen verfügbar.

## Architektur

```text
app/       CLI und Version
domain/    unveränderliche Patch-, Bank- und Reverbmodelle
d50/       Adressen, Frames, Prüfsumme, Validator, Klassifikator und Codecs
services/  atomare Datei- und Exportoperationen
midi/      reservierte, derzeit leere Grenze für Phase 3
gui/       Hauptfenster, Bankmatrix, Details, Dialoge und Diagnose
tests/     Unit-, Integrations- und Golden-Tests
```

Der D-50-Codec importiert weder GUI- noch MIDI-Module. Aus dem vorhandenen TAUREON Synth Tool
wurden nach Prüfung nur Architekturprinzipien übernommen. Quellcode wurde nicht kopiert,
da dort keine Lizenzdatei vorliegt und Phase 1 keinen MIDI-Backend-Code benötigt.

## Datenintegrität

- Eingaben gelten als nicht vertrauenswürdig.
- Beschädigte, fremde und unvollständige Dateien werden mit konkretem Grund abgelehnt.
- Identische Adressüberlappungen sind erlaubt; widersprüchliche Überlappungen werden abgelehnt.
- Originalbytes bleiben im Bankmodell als `raw_source` erhalten.
- Prüfsummen werden nur bei explizitem Export neu erzeugt.
- Dateischreibvorgänge erfolgen über eine temporäre Datei und atomare Umbenennung.
- Es gibt keine stille Reparatur und kein automatisches Senden.

## Bekannte Grenzen

- Noch kein verifizierter Initial-Patch. Beim Export einer teilgefüllten Bank muss deshalb ein
  bereits vorhandener Patch nach ausdrücklicher Bestätigung als Füllpatch dienen.
- Noch kein MIDI-Senden oder -Empfangen (Phasen 3 und 4).
- D-50-Handshake-/RQ1-Nachrichten werden erkannt, aber nicht importiert.
- Der Validator akzeptiert den von Roland für dieses Exclusive-Format dokumentierten
  Device-ID-Bereich `00h–1Fh`; die Quell-ID bleibt bei kanonischen Roundtrips erhalten.
- Die Tests wurden ohne realen Roland D-50 ausgeführt. Es wird kein Hardwaretest als bestanden behauptet.

## MIDI-Voraussetzungen für spätere Phasen

Für Phase 3 sind `mido` und `python-rtmidi` als optionale Abhängigkeiten vorgesehen. Am D-50
muss Exclusive aktiviert sein. Eine vollständige Bank darf später nur nach deutlicher
Überschreibwarnung und bei deaktiviertem Memory Protect gesendet werden. `Dump into Buffer`
wird ausschließlich die Temporary Area beschreiben und Reverb 17–32 nicht automatisch überschreiben.

Protokollreferenz: [Roland D-05 Parameter Guide / D-50 MIDI Implementation](https://static.roland.com/assets/media/pdf/D-05_ParameterGuide_eng02_W.pdf)

## Lizenz

`TBD` – es wurde bewusst noch keine Lizenz ausgewählt.
