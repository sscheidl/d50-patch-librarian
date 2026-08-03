# Changelog

## 0.4.2 – 2026-07-22

- Alle MIDI-Aktionen verwenden einen gemeinsamen threadsicheren Operationsmanager mit eindeutiger Job-ID; Preview, Banktransfer, Porttest und Portrefresh können sich nicht mehr überschneiden.
- Patch-Vorschau läuft in einem Worker und übergibt Fortschritt und Abschluss über eine Queue ausschließlich an den Tkinter-Hauptthread.
- Preview- und Bankaktionen werden während eines MIDI-Jobs konsistent deaktiviert; Mehrfachaufrufe und veraltete Abschlussereignisse werden abgelehnt.
- Die Preview-Statusmeldung unterscheidet nun korrekt zwischen gesendeten Daten und einem nicht bestätigten Empfang durch den D-50.
- Portabschluss und Fehlerpriorität des Preview-Senders wurden gehärtet; Diagnoseeinträge enthalten Job, Port, Device-ID, Timing, Frameadressen und Datenlängen.
- Der Bank-Handshake leert veraltete Eingangsnachrichten nur vor Transferbeginn, filtert zustandsabhängig erlaubte Befehle und ignoriert eigene Echo-Frames sowie fremde SysEx-Daten.
- Der Bankempfang besitzt ein Gesamtzeitlimit, toleriert begrenzte identische DAT-Wiederholungen und protokolliert Nachrichten, eindeutige Blöcke, Dubletten und Nutzbytes getrennt.
- Kombinierter Patch-/Reverbimport ist atomar und genau einmal rückgängig zu machen; ein Reverbimport verändert die Projekt-Device-ID nicht mehr.
- Undo/Redo in Eingabefeldern, Drag-Schwelle und Zielmarkierung, Matrixspalten, Kontextauswahl, Reverbstatus und sichere Einzelpatch-Dateinamen wurden korrigiert.
- Read-only-CLI `diagnose-preview-roundtrip` und 64-Patch-Regressionstests bestätigen die byteidentische Erhaltung aller bekannten, unbekannten und reservierten Patchbytes.
- Temporary-Buffer-Vorhören bleibt bis zu weiterem Hardwaretest ausdrücklich experimentell.

## 0.4.1 – 2026-07-21

- Temporary-Buffer-Vorhören ist nach Hardwaretests ausdrücklich als experimentell/buggy markiert.
- Beobachtet wurden sporadisch fehlende Partials oder Layer, unerwartete Keyboard-Splits und abweichende Klangbereiche gegenüber einem vollständigen Bankimport.
- Die Oberfläche stellt klar, dass vollständiger Banktransfer und anschließender Patchwechsel derzeit die verlässlichere Klangreferenz sind.

## 0.4.0 – 2026-07-21

- Vollständige Banken mit 64 Patches und Reverbs 17–32 können über Rolands bidirektionalen Handshake gesendet und empfangen werden.
- Bankübertragung verwendet WSD/DAT/EOD/ACK, prüft jeden Block, unterstützt Fortschritt und einen protokollgerechten Abbruch.
- Der MIDI-Tab besitzt getrennte Ein- und Ausgangsports sowie klare B.Load-/B.Dump-Anweisungen.
- Das redundante Feld für ausgewählte Patches und der GUI-Dry-Run wurden entfernt; Patch-Vorschau bleibt in Matrix und Patchdetails.
- Temporary-Buffer-Senden wartet vor dem Schließen des Windows-MIDI-Ports und verwendet standardmäßig 50 ms Abstand.

## 0.3.2 – 2026-07-21

- Neue Projekte, der MIDI-Tab und Exporte ohne bekannte Quell-ID verwenden standardmäßig Device ID `00h` statt `10h`.

## 0.3.1 – 2026-07-21

- Vorhören in den Temporary Buffer erfolgt ohne störende Reverb-Rückfrage; Reverbprogramme 17–32 werden weiterhin nicht gesendet.

## 0.3.0 – 2026-07-21

- Die Librarian-Bewertung verwendet durchgehend die Skala 1–6; alte Projektwerte `0` werden beim Laden als `1` übernommen.
- Eine kanonische, hörbare Vorlage `INIT SAW` mit einem aktiven Sägezahn-Partial, offenem Filter und neutraler Modulation ersetzt den bisherigen stillen Füllpatch.
- `Neuer Patch`, `Platz leeren` und freie Slots beim Vollbankexport verwenden durchgehend dieselbe `INIT SAW`-Vorlage.
- Freie Slots werden beim Vollbank-SysEx-Export automatisch gefüllt; der separate Auswahl-Dialog entfällt.
- Das Arbeitsprojekt behält seine tatsächlich leeren Slots unverändert.
- Reverbstatus wird in Matrix, Legende und Patchdetails als fest, vorhanden, fehlend oder konfliktbehaftet dargestellt.
- Phase-3-MIDI-Ausgang mit Porttest, Device ID, DT1-Dry-Run und sicherem Temporary-Buffer-Senden ergänzt.
- Automatisierte Fake-Port-Tests und manueller Hardwaretestplan ergänzt; Bank-, RQ1- und Reverb-Senden bleiben deaktiviert.

## 0.2.1 – 2026-07-21

- D-50-Patch- und Tonenamen werden nun mit der tatsächlichen kompakten 6-Bit-Zeichentabelle statt als ASCII gelesen und geschrieben.
- Reale D-50-Banken mit Namensbytes wie `0x06`, `0x0E` oder `0x02` lassen sich wieder öffnen.
- Regressionstests mit bekannten Namenscodierungen aus realen Banken ergänzt.

## 0.2.0 – 2026-07-21

- Windows-GUI mit drei Tabs, Toolbar, Statusleiste und 8×8-Patchmatrix implementiert.
- Vollständige D-50-Banken sowie einzelne Patches und Patchordner importierbar.
- Einzelne/ausgewählte/alle Patches als kanonische Einzel-SysEx exportierbar.
- Arbeitsbanken mit leeren Slots und explizitem Füllpatch als vollständige Bank exportierbar.
- Rename, Move/Swap per Maus und Tastatur, Sort, Clear, Delete-and-shift, Copy/Cut/Paste und Duplicate ergänzt.
- Undo/Redo mit 100 Schritten für alle Editoroperationen ergänzt.
- `.d50proj`-Projektformat mit rohen Patchdaten, Reverbs und Librarian-Metadaten ergänzt.
- Reverb-Basis 17–32 kann aus einer vollständigen Bank übernommen werden.
- Diagnose-Tab und Dateiübergabe per Drag auf die EXE/Dateiargument ergänzt.
- Release-Build auf GUI ohne Konsolenfenster umgestellt.

## 0.1.1 – 2026-07-20

- Start ohne CLI-Argumente beendet sich nicht mehr mit Fehlercode 2.
- Beim Doppelklick werden Hilfe und Phase-1-Hinweis angezeigt; das Konsolenfenster wartet auf Enter.
- Python-, Tkinter-, Paket- und PyInstaller-Laufzeitabhängigkeiten geprüft.

## 0.1.0 – 2026-07-20

- Phase-1-Projektgerüst angelegt.
- Strikten SysEx-Streamparser und Roland-D-50-DT1-Validator implementiert.
- 7-Bit-Adressarithmetik, Prüfsumme und D-50-Zeichensatz implementiert.
- Adressbasierte Klassifikation für Bank-, Einzelpatch-, Teil-, Fremd- und Fehlerdaten ergänzt.
- Vollbank- und Einzelpatch-Codecs mit kanonischer Serialisierung ergänzt.
- Patch-, Bank- und Reverb-Domainmodelle ergänzt.
- Deterministische Golden-Fixtures und automatisierte Tests ergänzt.
- Diagnose-CLI und PyInstaller-Buildgerüst ergänzt.
