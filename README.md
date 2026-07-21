# D-50 Patch Librarian

Windows-Patch-Librarian für den Roland D-50. Version `0.4.1` implementiert einen strikt
validierenden SysEx-Codec, den grafischen 8×8-Bankeditor und die vollständige bidirektionale
MIDI-Bankübertragung.

Die Anwendung ist ein Librarian und Bankwerkzeug, **kein Soundparameter-Editor**.

## Grafischer Bankeditor in Phase 2

- vollständige D-50-Banken öffnen und alle 64 Patches anzeigen
- neue Arbeitsbanken mit echten leeren App-Slots erstellen
- Einzelpatchdateien, ganze Patchordner und Patches aus einer zweiten Bank importieren
- Patches per Mausziehen oder `Alt+Pfeil` verschieben/tauschen
- Rename, Sort A–Z/Z–A, Kategorie, Reverb und Originalreihenfolge
- Copy/Cut/Paste, Duplicate, `Neuer Patch`/`Platz leeren` mit kanonischem `INIT SAW` sowie Löschen und Nachrücken
- mindestens 100 Undo-/Redo-Schritte
- Kategorien, Bewertungen von 1–6 und Notizen pro Patch
- Projekte als `.d50proj` atomar speichern und laden
- ausgewählte oder alle belegten Patches als Einzel-SysEx exportieren
- vollständige Bank-SysEx exportieren; leere Slots werden automatisch mit dem eingebauten,
  hörbaren `INIT SAW` gefüllt, ohne die leeren App-Slots im Arbeitsprojekt zu verändern
- Reverbs 17–32 aus einer vollständigen Quellbank übernehmen
- integrierter Diagnose-Tab
- einen Patch über Matrix oder Patchdetails experimentell in den Temporary Buffer senden
- vollständige Banken mit 64 Patches und Reverbs 17–32 per bestätigtem Roland-Handshake senden
  und empfangen
- verständliche Reverbfarben: fest, vorhanden, fehlend oder Konflikt

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

Der Codec selbst verwendet nur die Python-Standardbibliothek. Die Desktopanwendung
benötigt für MIDI zusätzlich `mido` und `python-rtmidi`; `pytest` und `PyInstaller` werden nur
für Tests beziehungsweise Builds benötigt.

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
midi/      Temporary-Preview und bidirektionaler WSD/DAT/EOD/ACK-Bank-Handshake
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

- Der kanonische `INIT SAW` ist strukturell getestet; sein Klang und alle neutralen Parameterwerte
  werden beim nächsten Gerätetest noch einmal am realen D-50 geprüft.
- **Temporary-Buffer-Vorhören ist derzeit buggy:** Obwohl die DT1-Daten angenommen werden, klingt
  ein Patch am realen D-50 nicht immer wie nach einem vollständigen Bankimport. Beobachtet wurden
  fehlende Partials/Layer, unerwartete Keyboard-Splits sowie sehr tiefe Klanganteile unterhalb einer
  Split-Grenze. Das Phänomen ist nicht deterministisch; der vollständige Bankimport gilt als Referenz.
- Der vollständige Bank-Handshake ist automatisiert simuliert, muss aber vor produktiver Nutzung
  noch mit gesicherter Bank am realen D-50 geprüft werden.
- RQ1-Read-back für einzelne Diagnosezwecke ist noch nicht Teil der Oberfläche.
- Der Validator akzeptiert den von Roland für dieses Exclusive-Format dokumentierten
  Device-ID-Bereich `00h–1Fh`; die Quell-ID bleibt bei kanonischen Roundtrips erhalten.
- Die automatisierten Tests ersetzen keine vollständige Prüfung aller Funktionen am realen Roland D-50.

## MIDI / Temporary Buffer und vollständige Banken

MIDI verwendet `mido` und `python-rtmidi`. Am D-50 muss Exclusive aktiviert sein. Der Benutzer
muss Port und Device ID ausdrücklich auswählen; beim bloßen Anklicken eines Patches wird nichts
gesendet. `Dump into Buffer` schreibt ausschließlich sieben Temporary-Area-DT1-Nachrichten mit
standardmäßig 50 ms Abstand und einer zusätzlichen Abschlusswartezeit. Reverb 17–32 wird beim
Vorhören nicht automatisch überschrieben. Der D-50 initialisiert dabei nach Hardwarebeobachtung
nicht immer alle Partials, Layer und Key-Mode/Split-Zustände zuverlässig; diese Funktion ist daher
ausdrücklich experimentell.

Komplette Banken verwenden zwei MIDI-Kabel und Rolands bidirektionalen Handshake. Beim Senden
bestätigt der D-50 jeden der 136 DAT-Blöcke, bevor die Anwendung fortfährt. Beim Empfang wird jeder
Block geprüft und bestätigt; die Arbeitsbank wird erst nach vollständigen 34.688 Nutzdatenbytes
ersetzt. Bank-Senden überschreibt die 64 internen Patchplätze und Reverbs 17–32 und verlangt daher
Backup, ausgeschalteten Memory Protect und die ausdrückliche B.Load-Bestätigung am Gerät.

Die manuellen Prüfabläufe stehen in [`HARDWARE_TEST.md`](HARDWARE_TEST.md) und
[`BANK_TRANSFER_TEST.md`](BANK_TRANSFER_TEST.md).

Protokollreferenz: [Roland D-05 Parameter Guide / D-50 MIDI Implementation](https://static.roland.com/assets/media/pdf/D-05_ParameterGuide_eng02_W.pdf)

## Lizenz

`TBD` – es wurde bewusst noch keine Lizenz ausgewählt.
