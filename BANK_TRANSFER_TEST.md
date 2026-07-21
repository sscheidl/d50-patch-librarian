# D-50 Hardwaretest – vollständige Bank

Status: Der WSD/DAT/EOD/ACK-Handshake ist automatisiert mit einem simulierten D-50 geprüft. Der
erste Test am realen Gerät darf nur mit gesicherter Bank erfolgen.

## Voraussetzungen

- aktuelle interne D-50-Bank als SysEx sichern und Rücklesbarkeit prüfen
- D-50 MIDI OUT mit dem ausgewählten M8U-Eingang verbinden
- ausgewählten M8U-Ausgang mit D-50 MIDI IN verbinden
- Exclusive aktivieren und Basic Channel/Device ID `00h` abgleichen
- für das Senden Memory Protect ausschalten

## Empfang zuerst testen

1. Im MIDI-Tab Ein- und Ausgang wählen und `Beide Ports testen` ausführen.
2. `Komplette Bank vom D-50 empfangen` starten.
3. Erst wenn das Tool wartet, am D-50 DATA TRANSFER → B.Dump auslösen.
4. Erwartet werden 136 bestätigte DAT-Blöcke und 34.688 Nutzdatenbytes.
5. Die empfangene Arbeitsbank sofort als `.d50proj` und `.syx` sichern.
6. Die exportierte SysEx-Datei erneut öffnen und stichprobenartig Patchnamen/Reverbs vergleichen.

## Senden erst nach erfolgreichem Empfang

1. Sicherstellen, dass das ursprüngliche Backup außerhalb des Projektordners vorhanden ist.
2. Am D-50 Memory Protect ausschalten und DATA TRANSFER → B.Load bereitstellen.
3. Im Tool `Komplette Bank an D-50 senden` wählen und die Überschreibwarnung prüfen.
4. Transfer nicht unterbrechen; jeder DAT-Block muss vom D-50 bestätigt werden.
5. Nach Abschluss mehrere Patchplätze einschließlich 1-1, 1-8, 8-1 und 8-8 prüfen.
6. Bank erneut vom D-50 empfangen und bytegenau mit der gesendeten Bank vergleichen.

## Abbruchkriterien

- RJC oder wiederholtes ERR vom D-50
- Timeout auf ACK, WSD, DAT oder EOD
- andere Device ID oder andere angekündigte Adresse/Größe
- weniger als 34.688 eindeutige Nutzdatenbytes
- Memory Protect oder B.Load ist nicht eindeutig vorbereitet

Bei einem Abbruch darf nicht sofort erneut gesendet werden. Zuerst internen Bankzustand und Backup
prüfen, dann den D-50 neu in B.Load/B.Dump versetzen.
