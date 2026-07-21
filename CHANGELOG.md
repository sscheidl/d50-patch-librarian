# Changelog

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
