# CODEX-Arbeitsauftrag: Roland D-50 Patch Librarian für Windows

**Dokumentversion:** 1.1  
**Zielplattform:** Windows 11, 64 Bit  
**Zielausgabe:** lauffähige Windows-App (`.exe`) mit übersichtlicher GUI  
**Arbeitstitel:** `D-50 Patch Librarian`  
**Sprache der GUI:** zunächst Deutsch; Texte zentral halten, damit spätere Übersetzung möglich bleibt

---

## 1. Ziel und Abgrenzung

Entwickle eine eigenständige Windows-Anwendung zur Verwaltung, Prüfung, Zusammenstellung und MIDI-Übertragung von Roland-D-50-Patches und vollständigen Patchbanken.

Die Anwendung ist:

- ein **Librarian**,
- ein **Bank-Editor**,
- ein **SysEx-Import-/Exportwerkzeug**,
- ein **MIDI-Dump- und Vorhörwerkzeug**.

Die Anwendung ist **kein Klangparameter-Editor**. Es werden außer Patchnamen, Slotposition und Reverb-Zuordnung keine Syntheseparameter grafisch editiert.

Wichtige Klarstellung:

> Der Roland D-50 besitzt in seiner normalen Bedienoberfläche keinen komfortablen Einzelpreset-Dateiimport.  
> Die Anwendung darf dennoch einzelne Patches als standardkonforme Roland-D-50-SysEx-Dateien ablegen, indem sie die sieben Patchblöcke auf den temporären Editierbereich adressiert. Diese Dateien werden von der Anwendung importiert, in Banken kombiniert und zum Vorhören in den D-50-Buffer gesendet.

---

## 2. Technische D-50-Grundlage

### 2.1 SysEx-Erkennung

Nur eindeutig erkannte Roland-D-50-Daten dürfen importiert werden.

Mindestens prüfen:

- Startbyte `F0`
- Endbyte `F7`
- Roland Manufacturer ID `41`
- D-50 Model ID `14`
- zulässige Command IDs:
  - `12` = DT1 / Data Set 1
  - optional später Handshake-Nachrichten, sofern sauber implementiert
- Device ID im erlaubten Bereich
- ausschließlich 7-Bit-Datenbytes innerhalb von SysEx
- korrekte Roland-Prüfsumme
- gültige D-50-Adressbereiche
- keine überlappenden Daten mit widersprüchlichem Inhalt
- keine abgeschnittenen Frames
- keine Fremdbytes außerhalb erlaubter MIDI-Realtime-Bytes

Fremdformate, andere Roland-Modelle und beschädigte Dateien sind abzulehnen. Die Fehlermeldung soll konkret sein, zum Beispiel:

- „Keine SysEx-Datei“
- „Roland-SysEx erkannt, aber nicht D-50“
- „Ungültige D-50-Prüfsumme in Nachricht 17“
- „Unvollständiger Patch: Lower Common fehlt“
- „Bank enthält widersprüchliche Daten an Adresse …“
- „Datei enthält nur einen Teil einer Bank“
- „Datei enthält nicht unterstützte Handshake-Daten“

Keine stillen Reparaturen im normalen Benutzermodus.

### 2.2 Patchstruktur

Ein vollständiger D-50-Patch umfasst sieben Blöcke mit zusammen **448 Byte**:

1. Upper Partial 1 – 64 Byte  
2. Upper Partial 2 – 64 Byte  
3. Upper Common – 64 Byte  
4. Lower Partial 1 – 64 Byte  
5. Lower Partial 2 – 64 Byte  
6. Lower Common – 64 Byte  
7. Patch – 64 Byte

Temporäre D-50-Adressen:

```text
00 00 00  Upper Partial 1 temporary
00 00 40  Upper Partial 2 temporary
00 01 00  Upper Common temporary
00 01 40  Lower Partial 1 temporary
00 02 00  Lower Partial 2 temporary
00 02 40  Lower Common temporary
00 03 00  Patch temporary
```

Die Anwendung muss Roland-7-Bit-Adressarithmetik korrekt implementieren. Keine normale 8-Bit-Integerarithmetik auf den drei Adressbytes verwenden.

### 2.3 Patchnamen

- Patchname: maximal **18 Zeichen**
- Tone-Namen: jeweils maximal **10 Zeichen**
- In Version 1 wird nur der Patchname bearbeitet.
- Zulässiger D-50-Zeichensatz:

```text
Leerzeichen
A–Z
a–z
0–9
-
```

Andere Zeichen dürfen nicht in die D-50-Daten geschrieben werden.

GUI-Verhalten bei ungültigen Zeichen:

- Zeichen beim Tippen sichtbar ablehnen oder markieren.
- Keine automatische Transliteration ohne Bestätigung.
- Optionaler Button „Ungültige Zeichen ersetzen“.
- Dateinamen dürfen Windows-konform zusätzlich bereinigt werden; der Patchname innerhalb der SysEx-Datei bleibt davon getrennt.

### 2.4 Exakter Aufbau eines vollständigen D-50-Bankdumps

Dieser Abschnitt ist verbindlich. Codex darf die Bankstruktur nicht erneut erraten oder nur aus Dateigrößen ableiten.

#### 2.4.1 Adressmodell

Alle D-50-Adressen bestehen aus drei 7-Bit-Bytes:

```text
AA BB CC
linear = AA * 128 * 128 + BB * 128 + CC
```

Addition und Subtraktion müssen im linearen Adressraum erfolgen und anschließend wieder in drei 7-Bit-Bytes zerlegt werden:

```python
def address_to_linear(a: int, b: int, c: int) -> int:
    return a * 16384 + b * 128 + c

def linear_to_address(value: int) -> tuple[int, int, int]:
    if value < 0 or value > 0x1FFFFF:
        raise ValueError("D-50 address outside three-byte 7-bit range")
    return (value // 16384, (value // 128) % 128, value % 128)
```

Keine normale hexadezimale 24-Bit-Adressarithmetik verwenden.

#### 2.4.2 Patch-Memory der vollständigen Bank

Der interne Patchspeicher beginnt bei:

```text
02 00 00
```

Er enthält 64 Patches mit je 448 Byte:

```text
64 × 448 = 28 672 Byte
```

Adressbereich:

```text
02 00 00 – 03 5F 7F
```

Slotindex:

```python
slot_index = (bank_number - 1) * 8 + (patch_number - 1)  # 0..63
slot_base_linear = address_to_linear(0x02, 0x00, 0x00) + slot_index * 448
slot_base = linear_to_address(slot_base_linear)
```

Beispiele:

```text
1-1  → 02 00 00
1-2  → 02 03 40
1-3  → 02 07 00
...
8-8  → 03 5C 40
```

Ein Patch belegt relativ zu seiner Slotbasis:

```text
dezimal  D-50-Offset  Länge  Inhalt
0        00 00        64     Upper Partial 1
64       00 40        64     Upper Partial 2
128      01 00        64     Upper Common
192      01 40        64     Lower Partial 1
256      02 00        64     Lower Partial 2
320      02 40        64     Lower Common
384      03 00        64     Patchblock
```

Der Patchblock enthält unter anderem:

```text
Offset 0–17   Patchname, exakt 18 Zeichen
Offset 18     Key Mode
Offset 30     Reverb Type, gespeicherter Wert 0–31 entspricht Anzeige 1–32
Offset 31     Reverb Balance
```

Die Common-Blöcke enthalten jeweils:

```text
Offset 0–9    Tone-Name, exakt 10 Zeichen
```

Die App muss alle 448 Bytes eines Patches erhalten. Beim Verschieben, Sortieren oder Exportieren darf niemals nur der 64-Byte-Patchblock verschoben werden.

#### 2.4.3 Reverb-Memory 17–32

Direkt nach dem Patchspeicher folgen 16 veränderbare Reverbprogramme:

```text
Reverb 17–32
16 × 376 Byte = 6 016 Byte
```

Adressbereich:

```text
03 60 00 – 04 0E 7F
```

Basisadresse eines Reverbprogramms:

```python
reverb_index = reverb_number - 17  # 0..15
reverb_base_linear = address_to_linear(0x03, 0x60, 0x00) + reverb_index * 376
reverb_base = linear_to_address(reverb_base_linear)
```

Beispiele:

```text
Reverb 17 → 03 60 00
Reverb 18 → 03 62 78
Reverb 32 → 04 0C 08
```

Jeder Block umfasst 376 Byte. Die Reverbblöcke sind global für die Bank und nicht Bestandteil der einzelnen 448-Byte-Patches.

#### 2.4.4 Gesamter adressierter Speicher einer vollständigen Bank

```text
Patch-Memory:   28 672 Byte
Reverb-Memory:   6 016 Byte
Gesamt:         34 688 Byte
```

Gesamtadressbereich:

```text
02 00 00 – 04 0E 7F
```

Eine vollständige Bank ist inhaltlich genau dann vollständig, wenn dieser gesamte adressierte Bereich ohne Lücken und ohne widersprüchliche Überlappungen rekonstruiert werden kann.

Wichtig:

- Die SysEx-Nachrichten dürfen in anderer Reihenfolge vorliegen.
- Die Segmentgrößen dürfen von Datei zu Datei abweichen.
- Mehrere Nachrichten dürfen benachbarte Bereiche unterschiedlich aufteilen.
- Deshalb immer den adressierten Speicher rekonstruieren.
- Die Zahl der Nachrichten und die Dateigröße sind nur Plausibilitätsmerkmale.

#### 2.4.5 Kanonische Bankserialisierung der untersuchten Archive

Die bereits analysierten gültigen Bankdateien verwenden folgende kanonische DT1-Aufteilung:

```text
136 DT1-Nachrichten
135 Nachrichten × 256 Datenbytes
1 letzte Nachricht × 128 Datenbytes
```

Startadresse:

```text
02 00 00
```

Adressschritt der 256-Byte-Nachrichten:

```text
00 02 00   # 256 dezimal im 7-Bit-Adressraum
```

Letzte Nachricht:

```text
Start 04 0E 00
Länge 128 Byte
Ende  04 0E 7F
```

DT1-Rahmen:

```text
F0
41             Roland
DEV            Device ID
14             D-50 Model ID
12             DT1
AA BB CC       Startadresse
DATA...        1 bis 256 Datenbytes
CHECKSUM
F7
```

Roland-Prüfsumme:

```python
checksum = (128 - ((sum(address_bytes) + sum(data_bytes)) % 128)) % 128
```

Bei der kanonischen Aufteilung ergibt sich:

```text
34 688 Byte Nutzdaten
1 360 Byte SysEx-Overhead
36 048 Byte Gesamtdateigröße
```

Diese Größe ist ein nützliches Testfixture, aber kein alleiniges Erkennungskriterium.

#### 2.4.6 Kanonischer Einzelpatch-Export

Ein app-erzeugtes Einzelpatch-SysEx verwendet sieben DT1-Nachrichten mit je 64 Datenbytes:

```text
00 00 00  Upper Partial 1
00 00 40  Upper Partial 2
00 01 00  Upper Common
00 01 40  Lower Partial 1
00 02 00  Lower Partial 2
00 02 40  Lower Common
00 03 00  Patchblock
```

Gesamt:

```text
7 × 64 = 448 Datenbytes
7 × 10 = 70 Byte SysEx-Overhead
518 Byte kanonische Einzelpatch-Datei
```

Der Patchblock wird beim Live-Senden zuletzt übertragen.

Der Parser darf alternativ segmentierte, aber adressinhaltlich gleichwertige D-50-Einzelpatchdateien akzeptieren, sofern exakt der Temporary-Area-Bereich `00 00 00 – 00 03 3F` vollständig und widerspruchsfrei rekonstruiert wird.

#### 2.4.7 Bankname ist kein D-50-Datenfeld

Eine D-50-Bank besitzt innerhalb des SysEx-Dumps keinen eigenen Banknamen.

Der in der App angezeigte Bankname stammt aus:

1. Projektmetadaten,
2. Dateiname,
3. gegebenenfalls Ordnername.

Er darf nicht in die D-50-Speicherdaten hineingeschrieben werden.

#### 2.4.8 Verbindliche Golden Tests

Codex muss mindestens folgende bereits aufgeklärte Strukturen als Golden Tests festschreiben:

```text
slot 1-1 base == 02 00 00
slot 1-2 base == 02 03 40
slot 8-8 base == 03 5C 40
slot 8-8 end  == 03 5F 7F

reverb 17 base == 03 60 00
reverb 18 base == 03 62 78
reverb 32 base == 04 0C 08
reverb 32 end  == 04 0E 7F

full addressed payload == 34 688 bytes
canonical bank file    == 36 048 bytes
canonical bank frames  == 136
canonical single file  == 518 bytes
```

Zusätzlicher Roundtrip-Test:

```text
gültige Bank
→ adressierten Speicher rekonstruieren
→ 64 Patches + 16 Reverbs dekodieren
→ kanonisch serialisieren
→ erneut parsen
→ adressierter Speicher byteidentisch
```

### 2.4 Reverbprogramme

Der Patch enthält unter anderem:

- Reverb Type `1–32`
- Reverb Balance

Dabei gilt:

- Reverb `1–16`: fest im D-50
- Reverb `17–32`: veränderbare globale Reverbprogramme außerhalb des 448-Byte-Patchblocks

Daraus folgt:

> Ein Einzelpatch mit Reverb 17–32 ist ohne das dazugehörige Reverbprogramm nicht vollständig reproduzierbar.

Die Anwendung muss solche Patches klar markieren.

Anzeigevorschlag:

```text
Reverb 08  [intern/fest]
Reverb 23  [bankabhängig]
Reverb 23  [Quelle vorhanden]
Reverb 23  [Quelle fehlt]
```

Standardmäßig darf „Dump into Buffer“ **keine globalen Reverbprogramme 17–32 überschreiben**.

---

## 3. Unterstützte Dateitypen

### 3.1 Vollständige D-50-Bank

Eine Bank enthält:

- 64 vollständige Patchblöcke
- optional bzw. normalerweise die Reverb-Daten 17–32
- gültige adressierte Roland-D-50-SysEx-Nachrichten

Die Klassifizierung darf nicht nur über Dateigröße erfolgen. Ausschlaggebend ist der vollständig rekonstruierte D-50-Adressraum.

Erwartete Klassifizierung:

```python
D50_FULL_BANK
D50_PARTIAL_BANK
D50_SINGLE_PATCH_TEMP
D50_SINGLE_PATCH_MEMORY
D50_VALID_OTHER
D50_CORRUPT
ROLAND_OTHER_MODEL
FOREIGN_SYSEX
NOT_SYSEX
```

### 3.2 Einzelpatch-SysEx der Anwendung

Ein exportierter Einzelpatch ist eine normale `.syx`-Datei mit sieben D-50-DT1-Nachrichten für die Temporary Area.

Vorgaben:

- exakt die sieben benötigten Patchblöcke
- Patchblock zuletzt senden/speichern
- jede Nachricht eigene gültige Roland-Prüfsumme
- keine proprietären Bytes vor `F0` oder nach `F7`
- kein JSON im SysEx-Strom
- Standard-Dateiendung `.syx`

Empfohlener Dateiname:

```text
01-1_Patch_Name.syx
08-8_Patch_Name.syx
```

Bei Export aus einer Bank in einen Ordner:

```text
Bankname/
  01-1_Patch_Name.syx
  01-2_Another_Patch.syx
  ...
```

Optional darf die Anwendung zusätzlich eine Metadatei erzeugen:

```text
01-1_Patch_Name.d50meta.json
```

Diese kann enthalten:

- ursprüngliche Bank
- ursprünglicher Slot
- Patch-SHA256
- Reverb Type
- Reverb-Abhängigkeit 17–32
- Hash des zugehörigen Reverbblocks
- Notizen/Kategorie

Die `.syx`-Datei muss unabhängig von der Metadatei eine gültige D-50-SysEx-Datei bleiben.

### 3.3 Projektdatei

Empfohlen ist ein eigenes Arbeitsformat:

```text
*.d50proj
```

Technisch als ZIP-Container oder JSON mit binären Daten in separaten Einträgen.

Die Projektdatei speichert:

- bis zu 64 belegte oder leere Slots
- rohe 448-Byte-Patchdaten
- Banklabel
- Quellbank und Ursprungsslot
- Reverb-Daten 17–32
- ungelöste Reverb-Abhängigkeiten
- Kategorien, Bewertungen und Notizen
- App-Version und Schema-Version

Die Projektdatei ist kein SysEx-Format und wird nie direkt an den D-50 gesendet.

---

## 4. Kernfunktion 1: Bank laden und Einzelpatches exportieren

### 4.1 Bank laden

Datei öffnen per:

- Menü
- Toolbar
- Drag-and-drop auf das Fenster
- Drag-and-drop auf die Bankliste

Nach dem Laden:

- Datei vollständig validieren
- Dump-Typ anzeigen
- 64 Slots rekonstruieren
- Patchnamen und Tone-Namen anzeigen
- Reverb Type pro Patch anzeigen
- Reverb 17–32 aus der Bank erfassen
- Prüfsummenstatus anzeigen
- Ursprungsdatei niemals verändern

### 4.2 Export aller Patches

Button:

```text
Alle Patches als Einzel-SysEx exportieren
```

Ablauf:

1. Zielordner wählen.
2. Unterordner mit Banknamen anlegen.
3. Alle belegten Patches als einzelne `.syx` speichern.
4. Optional Metadateien erzeugen.
5. Ergebnisdialog mit Anzahl, Warnungen und Zielpfad.

### 4.3 Selektiver Export

Mehrfachauswahl in der Matrix:

- `Strg` für einzelne Auswahl
- `Shift` für Bereiche
- `Strg+A` für alle
- Checkbox-Auswahl optional

Aktion:

```text
Ausgewählte Patches exportieren
```

### 4.4 Kontextmenü

Rechte Maustaste auf einen belegten Slot:

```text
Vorhören: Dump into Buffer
Als Einzel-SysEx speichern…
Umbenennen…
Kopieren
Ausschneiden
Einfügen
Duplizieren nach…
Verschieben nach…
Mit anderem Slot tauschen…
Slot leeren
Mit Initial-Patch ersetzen
Patchdetails…
```

**„Als Einzel-SysEx speichern…“ ist eine zentrale Pflichtfunktion.**

---

## 5. Kernfunktion 2: Neue Bank aus Einzelpatches bauen

### 5.1 Neue Bank

Dialog:

```text
Neue Bank
- Bankname / Projektname
- Leere Slots zunächst:
  [wirklich leer in der App]
  [mit Initial-Patch vorbelegen]
- Reverb-Basis:
  [Factory/Standard]
  [aus vorhandener Bank übernehmen]
  [später auswählen]
```

Die interne Matrix darf echte leere Slots enthalten.

### 5.2 Import von Einzelpatches

Importmöglichkeiten:

- einzelne `.syx`
- Mehrfachauswahl mehrerer `.syx`
- kompletter Ordner
- Drag-and-drop
- aus einer zweiten geöffneten Bank
- Copy/Paste zwischen Bankfenstern

Beim Import:

- Datei strikt klassifizieren
- nur vollständige D-50-Einzelpatches akzeptieren
- Patchname lesen
- Zielslot wählen oder automatisch nächsten freien Slot verwenden
- Konflikt bei belegtem Slot abfragen:
  - ersetzen
  - tauschen
  - nächsten freien Slot
  - abbrechen

### 5.3 Import aus einer vollständigen Bank

Optional zweigeteilte Ansicht:

- linke Seite: Quellbank
- rechte Seite: Zielbank

Patches per Drag-and-drop von links nach rechts.

### 5.4 Export einer neuen Bank

Der D-50 benötigt eine vollständige, gültige Bankstruktur.

Wenn die Arbeitsbank weniger als 64 belegte Slots enthält:

- leere Slots beim SysEx-Export mit einem definierten Initial-Patch auffüllen
- Benutzer vorher informieren
- Arbeitsprojekt selbst behält die Slots als leer

Exportoptionen:

```text
Bank als D-50-SysEx exportieren
Belegte Slots als Einzel-SysEx exportieren
Projekt speichern
```

Die Anwendung muss die vollständige Patch- und Reverb-Datenstruktur neu adressieren, fragmentieren und mit korrekten Prüfsummen schreiben.

DT1-Nutzdaten pro Nachricht dürfen die D-50-Grenze nicht überschreiten. Für Bankexport einen kanonischen, reproduzierbaren Nachrichtenschnitt verwenden.

---

## 6. Kernfunktion 3: Bankbearbeitung

### 6.1 Matrix

Zentrale 8×8-Matrix:

```text
1-1  1-2 ... 1-8
2-1  2-2 ... 2-8
...
8-1  8-2 ... 8-8
```

Optional zusätzlich Anzeige der Roland-Schreibweise:

```text
I11, I12 … I88
```

Jede Kachel zeigt:

- Slotnummer
- Patchname
- Reverbnummer
- Warnsymbol bei Reverb 17–32
- Markierung „geändert“
- Markierung „leer“
- optional Kategorie/Favorit

### 6.2 Umbenennen

- `F2`
- Doppelklick auf Namen
- Kontextmenü

Live-Anzeige:

```text
12 / 18 Zeichen
```

Keine unzulässigen D-50-Zeichen akzeptieren.

### 6.3 Sortieren

Aktionen:

- A–Z
- Z–A
- nach Kategorie
- nach Reverb Type
- Originalreihenfolge wiederherstellen, solange Ursprung bekannt ist

Sortierregeln:

- stabile Sortierung
- leere Slots ans Ende
- vollständige Patchdaten verschieben, nicht nur Namen
- Reverb-Abhängigkeiten mit dem Patch verschieben

### 6.4 Verschieben und Tauschen

- Drag-and-drop
- Tastatur `Alt+Pfeil`
- Kontextmenü „Verschieben nach“
- Kontextmenü „Tauschen mit“

### 6.5 Leeren und Löschen

Begriffe klar unterscheiden:

- **Slot leeren:** Patch entfernen, leerer App-Slot bleibt
- **Mit Initial-Patch ersetzen:** gültiger neutraler Patch wird eingesetzt
- **Löschen und nachrücken:** optional, alle folgenden belegten Patches rücken auf

Vor destruktiven Aktionen Undo-Zustand anlegen.

### 6.6 Undo/Redo

Pflichtfunktion:

- `Strg+Z`
- `Strg+Y`
- mindestens 100 Schritte
- Rename, Move, Swap, Delete, Import, Sort und Reverb-Neuzuordnung müssen rückgängig sein

---

## 7. Zusatzfunktion: Dump into Buffer / Vorhören

### 7.1 Zweck

Ein Patch soll am D-50 ausprobiert werden können, ohne die interne 64er-Bank zu überschreiben.

Aktionen:

- Kontextmenü `Vorhören: Dump into Buffer`
- Doppelklick optional
- Taste `Leertaste` optional
- Button im Detailbereich

### 7.2 Technischer Ablauf

1. MIDI OUT muss verbunden sein.
2. D-50 Exclusive muss eingeschaltet sein.
3. Die sieben Patchblöcke werden als DT1 an die Temporary Area gesendet.
4. Reihenfolge:
   - Upper Partial 1
   - Upper Partial 2
   - Upper Common
   - Lower Partial 1
   - Lower Partial 2
   - Lower Common
   - Patchblock zuletzt
5. Zwischen Nachrichten standardmäßig mindestens 25–35 ms Pause.
6. Nach erfolgreichem Senden:
   - Status `Patch im D-50-Buffer`
   - Patchname und Slot anzeigen
   - optional kurzer Program-/UI-Refresh, aber keine automatische Note senden

Wichtig:

- kein Schreiben in Patch Memory
- keine Änderung der internen Bank
- kein automatisches Überschreiben globaler Reverbdaten
- kein Senden beim bloßen Anklicken
- immer explizite Benutzeraktion

### 7.3 Reverbwarnung beim Vorhören

Bei Reverb 17–32:

```text
Dieser Patch verwendet Reverb 23.
Das Original-Reverb stammt aus der Quellbank und befindet sich nicht
im temporären Patchbuffer. Der Klang kann mit dem aktuell im D-50
gespeicherten Reverb 23 abweichen.
```

Buttons:

```text
Trotzdem vorhören
Abbrechen
Für diese Sitzung nicht mehr fragen
```

Spätere optionale Funktion:

- Reverb auf einen festen Typ 1–16 für die Vorschau abbilden
- Quelle und Ziel nebeneinander vergleichen
- globale Reverbprogramme nur nach ausdrücklicher Sicherheitsabfrage senden

### 7.4 Rechte Maustaste: Speichern als SysEx

Direkt nach oder unabhängig vom Vorhören:

```text
Rechte Maustaste auf Patch
→ Als Einzel-SysEx speichern…
```

Die erzeugte Datei enthält die sieben Temporary-Area-DT1-Nachrichten und ist wieder in die App importierbar sowie direkt per „Dump into Buffer“ sendbar.

---

## 8. Reverb-Konfliktverwaltung beim Bankbau

### 8.1 Datenmodell

Jeder importierte Patch erhält:

```python
reverb_type: int              # 1..32
reverb_dependency_hash: str | None
reverb_source_bank: str | None
reverb_status:
    FIXED_1_16
    SOURCE_AVAILABLE
    SOURCE_MISSING
    RESOLVED
    CONFLICT
```

### 8.2 Konfliktfall

Beispiel:

- Patch A verwendet Reverb 20 aus Bank X
- Patch B verwendet Reverb 20 aus Bank Y
- die Reverbblöcke sind verschieden

In einer Zielbank kann Reverb 20 nur eine Definition besitzen.

Konfliktassistent:

1. vorhandenen Reverbblock übernehmen
2. Reverbblock auf einen freien Slot 17–32 verschieben und Patch-Reverb-Type anpassen
3. auf festen Reverb 1–16 umstellen
4. Abhängigkeit ungelöst lassen
5. Patch nicht importieren

### 8.3 Exportprüfung

Vor Bankexport:

- alle Reverbkonflikte auflisten
- Export bei ungelösten Konflikten standardmäßig blockieren
- optional „Trotz Warnung exportieren“ nur nach expliziter Bestätigung
- vollständige Zusammenfassung anzeigen

---

## 9. MIDI-Senden und -Empfangen

### 9.1 Wiederverwendung aus τAUREON Synth Tool

Vor Implementierung Repository und vorhandene Module untersuchen:

- Native WinMM / `engine3_native`
- CaptureCore / Sessionlogik
- MIDI-Portauflistung
- Queue-basierte GUI-Kommunikation
- SysEx-Splitting
- Roland-/Herstellererkennung
- Sender mit einstellbarem Delay
- Diagnose-Logging
- PyInstaller-Konfiguration

Wiederverwenden, wenn fachlich und lizenztechnisch geeignet.

Nicht übernehmen:

- die komplette bestehende τAUREON-GUI
- generische Monitoransichten, die den Librarian überladen
- gerätespezifische Korg-Logik
- alte textbasierte Capturepfade als primären D-50-Weg

Der MIDI-Kern bleibt unabhängig von der D-50-Codec-Schicht.

### 9.2 MIDI-Bereich in der App

Eigenes Tab `MIDI / Transfer`:

- MIDI IN Dropdown
- MIDI OUT Dropdown
- Ports aktualisieren
- Verbinden / Trennen
- Device ID / Basic Channel
- Send Delay
- Empfang starten
- Empfang stoppen
- aktuelle Bytezahl
- SysEx-Nachrichtenzahl
- Status
- Diagnose-Log

### 9.3 Bank empfangen

Zuverlässiger erster Workflow:

1. App auf Empfang schalten.
2. Benutzer löst am D-50 Bulk Dump aus.
3. App speichert rohe empfangene Bytes.
4. Capture nach Quiet-Time sauber finalisieren.
5. D-50-Validator ausführen.
6. Nur bei vollständiger gültiger Bank Import anbieten.

Status:

```text
WAITING
RECEIVING
VALIDATING
COMPLETE
INCOMPLETE
CORRUPT
FOREIGN
ERROR
```

Rohdump bei Fehler optional als Diagnose-Datei speichern, aber nicht als gültige Bank importieren.

### 9.4 Bank senden

Vor dem Senden:

```text
Achtung: Das Laden einer Bank überschreibt die 64 internen Patches des D-50.
Bitte vorher ein Backup erstellen und Memory Protect ausschalten.
```

Optionen:

- Bank senden
- abbrechen
- vorher D-50-Backup empfangen

Während Sendung:

- Fortschrittsbalken
- Nachricht X von Y
- gesendete Bytes
- Stop-Button
- GUI bleibt responsiv
- keine parallele zweite Sendung

### 9.5 Einzelpatch senden

`Dump into Buffer` verwendet denselben Sender, aber:

- nur sieben DT1-Nachrichten
- Temporary-Area-Adressen
- keine Warnung vor Banküberschreibung
- Reverbhinweis nach Abschnitt 7

### 9.6 Optional: Request Data

Ein automatischer RQ1-Request darf erst aktiviert werden, wenn er am realen D-50 verifiziert wurde.

Bis dahin:

- Button sichtbar als `Bank vom D-50 anfordern (experimentell)` oder gar nicht anzeigen
- Standardweg bleibt manueller Bulk Dump vom Gerät
- keine unbelegte Behauptung, dass Request/Handshake vollständig funktioniert

---

## 10. GUI-Konzept

### 10.1 Designgrundsätze

Die Oberfläche darf nicht wie ein vollgestopfter Ein-Fenster-Editor wirken.

Vorgaben:

- Windows-native `ttk`-Optik
- helle und dunkle Darstellung optional
- keine braune Retro-Farbgebung
- Mindestschriftgröße 11 pt
- DPI-aware
- für 1920×1080 sinnvoll nutzbar
- klare Abstände
- keine winzigen Beschriftungen
- zentrale Aktionen als gut erkennbare Buttons
- Details in Tabs oder Seitenpanel, nicht alles gleichzeitig

### 10.2 Hauptfenster

Tabs:

```text
1. Bank Editor
2. MIDI / Transfer
3. Diagnose
```

`Bank Editor`:

- oben Toolbar
- links Quellen/Geöffnete Banken
- Mitte 8×8-Matrix
- rechts Patchdetails und Aktionen
- unten Statusleiste

Toolbar:

```text
Neue Bank
Bank öffnen
Projekt öffnen
Projekt speichern
Bank exportieren
Patches exportieren
Undo
Redo
MIDI verbinden
```

### 10.3 Patchdetails

Rechtes Panel:

```text
Slot
Patchname
Upper Tone
Lower Tone
Reverb Type
Reverbstatus
Quelle
Originalslot
SHA256
Kategorie
Bewertung
Notizen
```

Buttons:

```text
Vorhören
Als SysEx speichern
Umbenennen
In Zielbank kopieren
```

### 10.4 Kontextmenü

Kontextmenü muss auf belegten und leeren Slots sinnvoll reagieren.

Belegter Slot:

```text
Vorhören: Dump into Buffer
Als Einzel-SysEx speichern…
Umbenennen…
Kopieren
Ausschneiden
Duplizieren
Verschieben
Tauschen
Details
Slot leeren
Mit Initial-Patch ersetzen
```

Leerer Slot:

```text
Einzelpatch importieren…
Einfügen
Initial-Patch einsetzen
```

---

## 11. Empfohlene Programmstruktur

```text
d50_patch_librarian/
  main.py
  pyproject.toml
  requirements.txt
  README.md
  CHANGELOG.md
  ROADMAP.md
  LICENSE
  .gitignore

  app/
    __init__.py
    version.py
    paths.py
    settings.py
    logging_setup.py
    commands.py
    undo_stack.py

  domain/
    __init__.py
    patch.py
    bank.py
    reverb.py
    project.py
    enums.py
    errors.py

  d50/
    __init__.py
    constants.py
    addresses.py
    charset.py
    checksum.py
    sysex_frames.py
    parser.py
    classifier.py
    validator.py
    patch_codec.py
    bank_codec.py
    single_patch_codec.py
    reverb_codec.py
    init_patch.py

  services/
    __init__.py
    bank_service.py
    patch_export_service.py
    patch_import_service.py
    reverb_resolution_service.py
    project_service.py
    file_service.py
    hash_service.py

  midi/
    __init__.py
    backend.py
    ports.py
    sender.py
    receiver.py
    capture_session.py
    transfer_service.py
    taureon_adapter.py
    diagnostics.py

  gui/
    __init__.py
    main_window.py
    bank_editor_tab.py
    midi_transfer_tab.py
    diagnostics_tab.py
    bank_matrix.py
    patch_details.py
    source_bank_panel.py
    dialogs/
      rename_dialog.py
      export_dialog.py
      import_conflict_dialog.py
      reverb_conflict_dialog.py
      receive_dialog.py
      send_warning_dialog.py
    widgets/
      status_bar.py
      log_view.py
      progress_dialog.py

  resources/
    init_patch.bin
    app.ico

  tests/
    unit/
      test_addresses.py
      test_checksum.py
      test_charset.py
      test_frame_parser.py
      test_classifier.py
      test_patch_codec.py
      test_single_patch_roundtrip.py
      test_bank_roundtrip.py
      test_reverb_resolution.py
      test_sort_move_rename.py
      test_invalid_files.py
    integration/
      test_import_export_bank.py
      test_export_import_singles.py
      test_capture_validation.py
    fixtures/
      valid_full_bank.syx
      valid_partial_bank.syx
      valid_generated_single.syx
      corrupt_checksum.syx
      corrupt_truncated.syx
      foreign_sysex.syx
      d50_patch_reverb_23.syx

  packaging/
    pyinstaller/
      d50_patch_librarian.spec

  scripts/
    build_windows_debug.bat
    build_windows.bat
    run_tests.bat
    run_from_source.bat
```

---

## 12. Abhängigkeiten

Empfohlene Basis:

```text
Python 3.11 oder 3.12, 64 Bit
Tkinter / ttk
mido
python-rtmidi
pytest
pyinstaller
```

Optional:

```text
platformdirs
```

Keine unnötigen GUI-Frameworks einführen. Kein Electron. Kein Browser-Frontend. Kein Cloudzwang.

Falls der native τAUREON-WinMM-Capturekern wiederverwendet wird, die dafür notwendigen Windows-Abhängigkeiten sauber kapseln und dokumentieren.

Die App muss auch ohne angeschlossenen D-50 starten und alle Dateioperationen ermöglichen.

---

## 13. Datenintegrität und Sicherheitsregeln

1. Originaldatei nie überschreiben.
2. Importierte rohe Bytes unverändert speichern.
3. Änderungen nur an explizit bearbeiteten Feldern.
4. Export immer in neue Datei oder nach klarer Überschreibabfrage.
5. Prüfsummen bei jedem Export neu berechnen.
6. Vor Bankübertragung Warnung.
7. Vor globaler Reverbübertragung zusätzliche Warnung.
8. Einzelpatch-Vorhören schreibt nur Temporary Area.
9. Kein automatisches Senden beim Öffnen oder Anklicken.
10. Keine „Reparatur“ beschädigter Dateien ohne separaten Expertenmodus.
11. Alle Fehler mit Dateiname, Nachrichtennummer und Grund protokollieren.
12. App-Absturz darf keine halbfertige Datei als gültig erscheinen lassen; atomar in temporäre Datei schreiben und erst am Ende umbenennen.

---

## 14. Tests und Akzeptanzkriterien

### 14.1 Codec

- gültige Bank wird erkannt
- 64 Patches werden korrekt extrahiert
- Namen und Tone-Namen stimmen
- Import und Export ergeben denselben rekonstruierten Speicher
- Einzelpatch-Export enthält genau sieben gültige D-50-DT1-Nachrichten
- exportiertes Einzelpatch lässt sich wieder importieren
- Bank aus 64 exportierten Singles lässt sich rekonstruieren
- Prüfsummen stimmen
- 7-Bit-Adressen stimmen
- ungültige Zeichen werden abgelehnt
- Patchname wird auf 18 Zeichen begrenzt

### 14.2 Fehlerfälle

- falscher Hersteller
- falsches Roland-Modell
- fehlendes `F7`
- falsche Prüfsumme
- fehlender Patchblock
- doppelte widersprüchliche Adresse
- unvollständige Bank
- Datei mit Zusatzmüll
- beschädigtes Schlusssegment
- Reverbabhängigkeit fehlt

### 14.3 Bankeditor

- Import
- Rename
- Drag-and-drop
- Move
- Swap
- Sort A–Z
- Sort Z–A
- Clear
- Delete and shift
- Undo/Redo
- Save/Load Project

### 14.4 MIDI-Hardwaretest

Mit realem D-50:

1. gültigen Einzelpatch in Buffer senden
2. Patch sofort spielbar
3. Wechsel auf anderen D-50-Patch verwirft Bufferzustand erwartungsgemäß
4. interne Bank wurde durch Audition nicht überschrieben
5. Patch mit Reverb 1–16 klingt reproduzierbar
6. Patch mit Reverb 17–32 zeigt Warnung
7. Bulk Dump empfangen
8. empfangene Bank validieren
9. unveränderte Bank zurücksenden
10. Redump vergleichen
11. abgebrochene Übertragung wird nicht als vollständig gemeldet

Codex darf Hardwaretests nicht als bestanden behaupten, wenn kein realer D-50 verfügbar war.

---

## 15. Entwicklungsphasen

### Phase 1 – D-50-Codec und Tests

Implementieren:

- SysEx-Frameparser
- Roland-Prüfsumme
- 7-Bit-Adressarithmetik
- D-50-Klassifikator
- vollständiger Bankparser
- Einzelpatchparser
- Einzelpatchserializer
- Bankserializer
- Zeichenvalidierung
- Unit Tests

Noch keine MIDI-Übertragung und nur minimale CLI.

**Gate:** Golden-File-Tests vollständig grün.

### Phase 2 – Bankeditor ohne MIDI

Implementieren:

- GUI
- 8×8-Matrix
- Bank laden
- neue Bank
- Singles exportieren
- Singles importieren
- Rename
- Sort
- Move/Swap
- Clear/Delete
- Undo/Redo
- Projektdatei

**Gate:** Dateiworkflow vollständig ohne Synthesizer nutzbar.

### Phase 3 – Dump into Buffer

Implementieren:

- MIDI OUT
- Device-ID/Channel
- Sender
- sieben Temporary-Area-DT1-Nachrichten
- Reverbwarnung
- Kontextmenü `Vorhören`
- Kontextmenü `Als Einzel-SysEx speichern`

**Gate:** Ein Patch lässt sich am realen D-50 gefahrlos vorhören.

### Phase 4 – Bank Send/Receive

Implementieren:

- nativer/robuster Empfang
- manuelles Armieren des Bulk-Dump-Empfangs
- Validierung
- Bank senden
- Fortschritt
- Abbruch
- Diagnose

**Gate:** Receive → Save → Send → Redump technisch nachvollziehbar.

### Phase 5 – Reverbkonflikte und Packaging

Implementieren:

- Reverb-Abhängigkeitsverwaltung
- Konfliktassistent
- vollständige Windows-Builds
- Installer optional
- Dokumentation
- Hardwaretestplan

---

## 16. Windows-Build

Erstellen:

```text
scripts/build_windows_debug.bat
scripts/build_windows.bat
packaging/pyinstaller/d50_patch_librarian.spec
```

Zunächst bevorzugt:

```text
PyInstaller onedir
```

Debug-Build:

- Konsole sichtbar
- ausführliches Logging

Release-Build:

- GUI ohne Konsole
- Logdatei unter `%LOCALAPPDATA%`
- App startet ohne MIDI-Gerät
- verständliche Meldung bei fehlenden MIDI-Ports

Optional später Onefile, aber nicht als einzige Buildform.

---

## 17. Dokumentation

README muss enthalten:

- Zweck
- klare Abgrenzung „kein Soundeditor“
- unterstützte Bank- und Einzelpatchformate
- Erklärung des app-definierten Einzelpatch-SysEx
- Reverb-17–32-Hinweis
- Installation aus Source
- Windows-Build
- Bedienung
- MIDI-Voraussetzungen
- D-50 Exclusive/Memory-Protect-Hinweise
- bekannte Grenzen
- Testcheckliste

CHANGELOG mit Versionsnummern pflegen.

Lizenz nicht ungefragt wählen:

```text
License: TBD
```

---

## 18. Direkter Codex-Auftrag

```text
Build a Windows-oriented Roland D-50 Patch Librarian according to the
architecture and acceptance criteria in this document.

Important rules:

1. Inspect the existing TAUREON Synth Tool repository first.
2. Reuse only suitable backend components, especially MIDI port handling,
   queue/thread patterns, native capture, SysEx framing, diagnostics and
   PyInstaller infrastructure.
3. Do not copy the full TAUREON GUI.
4. Keep the D-50 codec completely independent of the MIDI backend and GUI.
5. The application is a librarian, not a sound parameter editor.
6. Treat all imported bytes as untrusted.
7. Reject foreign, malformed, incomplete or checksum-invalid SysEx with
   explicit errors.
8. Implement address-based recognition, not file-size-only recognition.
8a. Use the exact bank memory map, slot formula, reverb map and canonical framing from section 2.4; do not rediscover or approximate them.
9. Preserve original raw data and recompute checksums only during explicit
   export.
10. Implement the work in milestones and keep the application runnable and
    testable after every milestone.
11. Do not claim real-hardware success unless the build was tested with an
    actual Roland D-50.

Mandatory user workflows:

A. Load a valid D-50 bank, display its 64 patches and export all or selected
   patches as seven-message Temporary-Area single-patch .syx files.

B. Right-click any occupied patch slot and choose:
   - Dump into Buffer
   - Save as Single SysEx

C. Create a new empty or partially filled bank, import single-patch .syx
   files, move/swap/sort/rename/clear patches and export a complete valid
   D-50 bank.

D. Receive a D-50 bank dump, validate it, save it and optionally load it into
   the bank editor.

E. Send a complete bank only after a clear overwrite warning.

For the first implementation run, complete Phase 1 only:
- project scaffold
- D-50 constants and address arithmetic
- SysEx parser/classifier/validator
- patch and bank domain models
- single-patch import/export codec
- full-bank import/export codec
- checksum implementation
- charset/name validation
- golden fixtures and pytest tests
- minimal CLI diagnostics
- README and CHANGELOG
- Windows build scaffold

After Phase 1, provide:
- complete file tree
- implemented features
- test results
- unresolved assumptions
- exact next-step recommendation for Phase 2
- statement whether an EXE was actually built
- no invented hardware test claims
```

---

## 19. Definition of Done für die Gesamt-App

Die App gilt als funktionsfähig, wenn:

- eine gültige D-50-Bank eindeutig erkannt wird
- beschädigte oder fremde Dateien abgelehnt werden
- 64 Patches korrekt angezeigt werden
- einzelne oder alle Patches als gültige Einzel-SysEx exportiert werden
- Einzel-SysEx wieder importiert werden
- eine neue Bank aus Einzelpatches aufgebaut werden kann
- Rename/Sort/Move/Swap/Clear und Undo/Redo funktionieren
- eine teilbefüllte Arbeitsbank als vollständige D-50-Bank exportiert wird
- ein Patch per `Dump into Buffer` vorgehört werden kann
- rechte Maustaste → `Als Einzel-SysEx speichern` funktioniert
- Reverb 17–32 korrekt gewarnt und verwaltet wird
- Bank-Dumps empfangen und gesendet werden können
- die Windows-EXE ohne angeschlossenen Synthesizer startet
- alle kritischen Codec- und Dateifehler durch Tests abgesichert sind
