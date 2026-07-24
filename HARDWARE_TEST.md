# D-50 Hardwaretest – Temporary Buffer

Status: Temporary-Buffer-Transfer wird angenommen, ist klanglich aber nicht zuverlässig. Beobachtet
wurden fehlende Partials/Layer, unerwartete Keyboard-Splits und abweichende Klangbereiche. Dieser
Testplan dient der Reproduktion; die Funktion bleibt bis zur Ursachenklärung experimentell/buggy.

Dieser Testplan gilt ausschließlich für den Patchtransfer in die Temporary Area. Der separate
Vollbanktest steht in `BANK_TRANSFER_TEST.md`.

## Zielgerät dokumentieren

- Gerät: Roland D-50 / D-550 (genauen Typ bestätigen)
- Firmware: 2.0.0 (Angabe am Gerät bestätigen)
- MIDI-Interface und Port: noch auswählen
- D-50 Basic Channel beziehungsweise Device ID: noch bestätigen

## Vorbereitung

1. Aktuelle D-50-Bank vollständig sichern.
2. D-50 Exclusive einschalten.
3. MIDI OUT des Computers mit MIDI IN des D-50 verbinden.
4. Im MIDI-Tab den tatsächlich verbundenen Ausgang und Device ID `00h` wählen.
5. `Beide Ports testen` ausführen. Dabei werden keine MIDI-Daten gesendet.
6. Einen Patch mit Reverb 1–16 auswählen und alle Tasten sowie Sustain loslassen.

## Erster Sendetest

1. Einen unkritischen Patch mit Reverb 1–16 auswählen.
2. `Im D-50 vorhören (experimentell)` genau einmal betätigen.
3. Prüfen, ob Patchname und Klang am D-50 wechseln.
4. Keine automatische Note erwarten; auf dem D-50 manuell spielen.
5. Einen internen Speicherplatz wechseln und zurückkehren. Es darf kein Patch Memory überschrieben sein.
6. Die gespeicherte 64er-Bank erneut auslesen und mit dem Backup vergleichen.

## Software-Härtung ab 0.4.2

- Während der Vorschau dürfen Bank-Senden, Bank-Empfang, Porttest und Portrefresh nicht starten.
- Ein zweiter Preview-Aufruf muss mit einem Busy-Hinweis abgelehnt werden.
- Nach Erfolg oder Fehler muss die Anzeige wieder `MIDI bereit` melden.
- `Gesendet` ist ohne RQ1-Readback keine Empfangsbestätigung des D-50.
- Zur Dateidiagnose kann vorab `python main.py diagnose-preview-roundtrip bank.syx` ausgeführt werden.

## Reverb-Test

Ein Patch mit Reverb 17–32 wird ohne zusätzliche Rückfrage zum flüssigen Vorhören gesendet. Das
Reverbprogramm selbst wird nicht mitgesendet. Abweichender Klang ist deshalb möglich und kein
Patchtransferfehler; der MIDI-Status weist weiterhin darauf hin, dass keine Reverbs adressiert wurden.

## Abbruchkriterien

- unerwartete Speicheränderung
- kein klar zuzuordnender MIDI-Port
- fehlerhafte oder hängende Anzeige am D-50
- anderer Zieladressbereich als die sieben Temporary-Adressen
- DT1-Abstand unter 20 ms

Ein Hardwaretest gilt erst nach dokumentiertem Ergebnis am realen Gerät als bestanden.
