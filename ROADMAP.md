# Roadmap

## Phase 1 – Codec (fertig)

Dateibasierter Codec, strikte Validierung, CLI, Tests und Buildgerüst.

## Phase 2 – Bankeditor ohne MIDI (fertig)

- Windows-native Tkinter/ttk-GUI mit 8×8-Matrix
- neue und teilgefüllte Arbeitsbanken
- Import, Rename, Sort, Move, Swap, Clear und Undo/Redo
- `.d50proj`-Projektformat
- kanonischer, hörbarer `INIT SAW` für neue, geleerte und automatisch aufgefüllte Exportslots

## Phase 3 – Dump into Buffer (experimentell, Hardwarefehler offen)

MIDI OUT, Device ID und explizite Preview-Aktion sind implementiert. Am realen D-50 treten jedoch
sporadisch falsche Partials/Layer und unerwartete Splits gegenüber dem vollständigen Bankimport auf.
Die genaue Initialisierungsursache ist noch offen; Vorschau bleibt als experimentell markiert.

## Phase 4 – Bank Send/Receive (Quellcode und Simulation fertig, Hardwaretest offen)

Bidirektionaler Roland-Handshake, getrennte Ein-/Ausgangsports, Blockvalidierung, Fortschritt,
Abbruch und sichere Übernahme empfangener Banken sind implementiert. Der Test am realen D-50
mit gesicherter Bank steht noch aus.

## Phase 5 – Reverbkonflikte und Packaging

Konfliktassistent und finale Windows-Builds.
