# Prüfbericht Notenverwaltung 1.0.0 – Bugs und Sicherheit

Stand: 15.11.2026 · geprüft: Commit `dd21d4c` (Tag `v1.0.0`, lokal = GitHub) · Linux- und Windows-Fassung, Repository
`SebastianMG80/notenverwaltung`

## 1 Kurzfassung

Das Programm ist solide gebaut: AES-256-GCM mit Argon2id, atomares Speichern, keine Netzwerkzugriffe, keine
gefährlichen Aufrufe (`eval`, `pickle`, externe Programme), SQL durchgehend mit Parametern, das Repository ist privat
und enthält weder Zugangsdaten noch echte Namen.

Gefunden habe ich trotzdem **zwei schwere Lücken**, beide sind behoben und mit Tests belegt:

1. **Die Sperre ließ sich umgehen.** Das Programm prüfte das Passwort gegen die Datei auf der Platte. Wer die
   `.nvdb`-Datei gegen eine eigene austauschte, kam mit dem eigenen Passwort an die geöffneten Noten.
2. **Namen, Noten und Rückmeldungen landeten unverschlüsselt im Temp-Ordner.** SQLite lagerte das
   Rückgängig-Protokoll nach einigen Änderungen in eine Datei unter `/var/tmp` aus.

Dazu kommen vier mittlere und mehrere kleine Funde (Dateirechte, Sperre nach Ruhezustand, Sicherungen bei
Dateinamen mit `[ ]`, Import beschädigter Tabellen). Alles Eindeutige ist behoben. Die Korrekturen sind
auf deinen Wunsch **committet und gepusht** (Commit `2fa74f3` auf `main`, kein Tag, kein Release). Auf GitHub habe ich zwei Einstellungen
verschärft (Abschnitt 5).

Offen sind Punkte, die deine Entscheidung brauchen (Abschnitt 6), vor allem: Ein Passwortwechsel tauscht den
eigentlichen Schlüssel nicht aus, und der Notenschlüssel verhält sich bei Arbeiten unter 10 Punkten unerwartet.

Die Windows-Fassung konnte ich nicht selbst ausführen; dafür gelten die CI-Ergebnisse (Abschnitt 7).

**Freigabe:** Die Korrekturen sind auf deinen Wunsch als **Version 1.1.0** freigegeben (Tag `v1.1.0`). Die Zips von
v1.0.0 enthalten sie nicht – bitte nur noch 1.1.0 benutzen.

**Nachtrag nach dem Push (15.11.2026):** Der CI-Lauf zu `2fa74f3` ist vollständig grün. Linux: 319 Tests
bestanden. Windows: 315 bestanden, 4 übersprungen (der Sperrdatei-Test wie bisher und drei neue Tests, die es nur
unter Linux geben kann: Temp-Dateien auflisten, Dateirechte, `CLOCK_BOOTTIME`). Selbsttest in beiden gebauten
Programmen bestanden, Dateien in beide Richtungen lesbar. Die engeren Workflow-Rechte (G1) gelten damit.

| Schwere | gefunden | behoben | offen |
|---|---|---|---|
| hoch | 2 | 2 | 0 |
| mittel | 5 | 4 | 1 |
| niedrig / Hinweis | 16 | 5 | 11 |

Tests: vorher 284 bestanden, 1 übersprungen. Jetzt **318 bestanden, 1 übersprungen** (34 neue in
`tests/test_pruefung.py`). Gegenprobe am alten Stand: 28 der neuen Tests schlagen dort fehl, wie sie sollen.

## 2 Behobene Funde

Alle Nachweise stammen aus einer Kopie mit erfundenen Daten. Die Nummern stehen auch an den Tests
(`test_s1_…`).

### Hoch

**S1 – Sperre per Dateitausch umgehbar**
- Nachweis: `Datenbank.pruefe_passwort()` las die Datei neu von der Platte. Nach dem Überschreiben der Datei mit
  einer fremden Datenbank galt deren Passwort (`True`), das echte nicht mehr (`False`).
- Folge: Der Rechner ist während der Sperre ja angemeldet. Jemand am Pult kopiert eine vorbereitete `.nvdb` über
  deine, tippt sein Passwort ein und sieht alle Noten; beim nächsten Speichern liegt deine Datei wieder da.
  Betroffen war auch „Passwort ändern“.
- Behoben: Geprüft wird gegen den geöffneten Tresor im Arbeitsspeicher (`Tresor.pruefe_zugang`), die Datei
  spielt keine Rolle mehr.

**S2 – Unverschlüsselte Daten im Temp-Ordner**
- Nachweis: Nach 17 Änderungen an einer Arbeit mit langer Musterlösung lag eine 1,8 MB große Datei
  `/var/tmp/etilqs_…` vor, darin im Klartext der Schülername und die Rückmeldungen.
- Folge: Widerspricht der Zusage „unverschlüsselte Daten berühren nie die Festplatte“. Die Datei wird zwar sofort
  als gelöscht markiert, ihr Inhalt bleibt aber auf dem Datenträger wiederherstellbar.
- Behoben: `PRAGMA temp_store = MEMORY` beim Anlegen jeder Verbindung.
- Nicht geprüft: das Verhalten des alten Stands unter Windows (dort wäre es `%TEMP%`).

### Mittel

**S3 – Dateien für andere Benutzer lesbar**
- Nachweis: Datenbank, Schlüsseldatei, Sperrdatei und Notfallblatt-PDF entstanden mit `-rw-rw-r--`.
- Folge: Auf einem Rechner mit mehreren Konten kann jedes Konto die Schlüsseldatei oder das Notfallblatt-PDF
  lesen – beides öffnet die Datenbank ohne Passwort.
- Behoben: Diese Dateien bekommen unter Linux `600`, der Sicherungsordner `700`. Unter Windows gelten weiter die
  Rechte des Ordners.

**S4 – Keine Sperre nach dem Ruhezustand (Linux)**
- Nachweis: Die Sperr-Uhr nutzte `time.monotonic()`; die steht unter Linux still, solange der Rechner schläft.
- Folge: Laptop zuklappen, Stunden später aufklappen: Die Notenverwaltung ist noch offen, obwohl 15 Minuten längst
  vorbei sind.
- Behoben: Uhr `CLOCK_BOOTTIME`, die den Ruhezustand mitzählt.

**S7 – Sicherungen bei Dateinamen mit `[ ]`, `*` oder `?`**
- Nachweis: Datenbank „Noten [2026]“: eine Sicherung im Ordner, `sicherungen()` findet 0; am zweiten
  Sicherungsort blieben 3 statt 1 Kopie.
- Folge: Sicherungen werden nie aufgeräumt und – schwerer – nach einem Passwortwechsel nicht umgestellt: Das
  alte Passwort öffnet sie weiter.
- Behoben: `glob.escape` an beiden Stellen.

**S8 – Import beschädigter oder präparierter Tabellen**
- Nachweis: Eine `.xlsx` mit Zellbezug `ZZZZZZZ1` ließ das Programm hängen und füllte den Arbeitsspeicher. Fünf
  weitere Fälle endeten in unbehandelten Fehlern (fehlender Textverweis, Stil ohne Zahl, CSV-Feld über 128 kB,
  ODS mit unsinniger Wiederholung, Jahrgang „²“). Der Assistent arbeitete dann mit den Zeilen der vorigen Datei
  weiter.
- Behoben: Spaltenzahl begrenzt, entpackte Größe je Archivteil höchstens 100 MB, alle Lesefehler ergeben eine
  verständliche Meldung.
- In Ordnung waren schon vorher: Entitäten-Bombe und externe Entitäten (werden abgelehnt).

### Niedrig

| Nr. | Fund | Korrektur |
|---|---|---|
| S5 | Beim Schließen wurde die Sperre aufgehoben, bevor das Speichern gelungen war. Scheiterte es, lag die Datenbank nach „Abbrechen“ entsperrt da. | Sperre fällt erst nach gelungenem Schließen; sonst bleibt gesperrt. |
| S6 | Veränderter Dateikopf (Zugang kein Objekt, Salz oder Nonce falscher Länge) führte zu einem Programmfehler ohne Meldung. | Wird als „Datei ist beschädigt“ gemeldet. |
| S9 | Namen standen ungeschützt in drei formatierten Beschriftungen (`<b>Name</b>`); ein importierter Name mit `<…>` wurde als HTML gedeutet. | `html.escape`. |
| S10 | Sehr tief verschachtelte KI-Antwort brach mit `RecursionError` ab. | Verständliche Fehlermeldung. |
| G1 | Der Workflow gab allen Jobs Schreibrecht auf das Repository. | Standard `contents: read`, nur der Job `release` darf schreiben. Wirkt erst nach einem Push. |

## 3 Was in Ordnung ist

- **Verschlüsselung:** Zufälliger Hauptschlüssel, je Zugang neu verpackt, Kopf als Zusatzdaten geschützt,
  Nonce bei jedem Speichern neu. Falsches Passwort und veränderte Datei werden sauber unterschieden.
- **Speichern:** Zwischendatei, Leseprobe, dann Ersetzen. Simulierter Abbruch („Platte voll“): Original
  unverändert, das Programm weiß, dass noch nicht gespeichert ist. Abgeschnittene und leere Dateien werden
  abgelehnt.
- **Kein Netz, keine Updates, kein Autostart:** keine entsprechenden Aufrufe im Quelltext; der vorhandene
  Offline-Test besteht. Einziger Aufruf nach außen: der Dateimanager für den Sicherungsordner.
- **Exporte:** nur PDF und Druck, kein CSV-Export – also keine Formel-Einschleusung.
- **Textbausteine:** Platzhalter werden per Muster ersetzt, nicht per `str.format`.
- **Abhängigkeiten:** `pip-audit` meldet für die festgelegten Versionen keine bekannten Lücken.
- **Versionsgeschichte:** 44 Commits, alle mit der GitHub-noreply-Adresse; keine Schlüssel, Token,
  E-Mail-Adressen oder Heimatpfade; nie eine Datei gelöscht. `Punkteliste.ods` enthält keine Namen und keine
  Autorenangabe. Testdaten tragen erfundene Namen.

## 4 Linux und Windows im Vergleich

| Thema | Linux | Windows |
|---|---|---|
| Tests in CI (v1.0.0) | 285 bestanden | 284 bestanden, 1 übersprungen (Sperrdatei-Test, absichtlich) |
| Selbsttest im gebauten Programm | bestanden (CI und hier aus dem Release-Zip) | bestanden (nur CI) |
| Gegenprobe Dateiformat | Windows-Datei unter Linux lesbar | Linux-Datei unter Windows lesbar |
| Einstellungen | `~/.config/Notenverwaltung/Notenverwaltung.ini` | `%APPDATA%\Notenverwaltung\Notenverwaltung.ini` |
| Dateirechte | jetzt `600` (S3) | Rechte des Ordners; nicht geprüft |
| Verwaiste Sperrdatei | wird über die Prozessnummer erkannt | es wird immer nachgefragt |
| Sperr-Uhr im Ruhezustand | behoben (S4) | `monotonic` zählt dort laut Dokumentation mit; nicht geprüft |
| Paket | Zip, 122 MB, Python 3.13.18, OpenSSL 3.5.5 | Zip, 51 MB, unsignierte `.exe` |
| Installer, Autostart | keiner | keiner |

## 5 GitHub

Gelesen: Repository privat, nur du als Mitwirkender, keine Secrets, Variablen, Deploy-Schlüssel oder Webhooks,
Standardrecht des Workflow-Tokens „read“, 12 Releases (v0.3.0 bis v1.0.0), jeweils zwei Zips, angelegt vom
Actions-Bot. Die Zips enthalten nur das Programm, keine Datenbanken, Einstellungen oder Quelltexte.

Geändert (von dir erlaubt, beides mit einem Klick rückgängig zu machen):

| Einstellung | vorher | jetzt |
|---|---|---|
| Dependabot-Warnungen | aus | an (derzeit 0 Warnungen) |
| Erlaubte Actions | alle | nur GitHub-eigene (`actions/*`) – mehr benutzt der Workflow nicht |

Nicht möglich im kostenlosen Tarif bei privatem Repository: Schutzregeln für `main`, Secret-Scanning.

## 6 Offen – braucht deine Entscheidung

### Mittel

**O1 – Passwortwechsel tauscht den Hauptschlüssel nicht**
- Ein neues Passwort verpackt nur denselben Hauptschlüssel neu. Wer das alte Passwort kannte *und* eine alte
  Kopie der Datei hat (Cloud-Verlauf, USB-Stick), kann damit auch alle späteren Fassungen entschlüsseln.
- Dazu passt: Kopien am zweiten Sicherungsort (USB-Stick) behalten das alte Passwort, weil das Programm sie
  beim Passwortwechsel nicht umstellt. Die Sicherungen im Ordner neben der Datenbank werden umgestellt.
- Vorschlag: bei „Passwort ändern“ wahlweise „Schlüssel erneuern“ anbieten. Das verlangt ein neues Notfallblatt
  und eine neue Schlüsseldatei, deshalb habe ich es nicht selbst eingebaut. Das Dateiformat bliebe gleich.

### Niedrig und Hinweise

| Nr. | Punkt | Vorschlag |
|---|---|---|
| O2 | **Notenschlüssel bei kleinen Arbeiten:** Unter 10 Höchstpunkten ergibt die volle Punktzahl „1+“ statt „1“; bei 1–2 Höchstpunkten ergeben 0 Punkte eine 4 bzw. 5 (Sek II bei 1 Höchstpunkt: 5 Punkte). Ursache ist die Rundung der Prozentgrenzen wie in der ODS. | Entscheiden: so lassen (wie die Vorlage) oder „1+“ erst über 100 % und 0 Punkte immer schlechteste Note. Notenlogik habe ich nicht angefasst. |
| O3 | **Grenzen der Sperre** (aus dem Quelltext abgeleitet, nicht nachgestellt): Ein offener Datei- oder Druckdialog des Betriebssystems wird nicht abgedeckt; fragt ein Dialog beim Schließen nach, während gesperrt ist, kann die Rückfrage das Entsperren blockieren. Grundsätzlich schützt die Sperre nur vor dem Blick auf den Bildschirm, nicht vor jemandem mit Zugriff auf dein angemeldetes Konto. | Zusätzlich die Bildschirmsperre des Betriebssystems nutzen; in der Anleitung so benennen. |
| O4 | **Hinweise in Infofeldern:** Themen und Bemerkungen (auch aus der KI-Antwort) erscheinen in Tooltips; beginnt ein Text mit `<…>`, deutet Qt ihn als HTML. Nur Darstellung, kein Skript, kein Netz. | Tooltips einheitlich maskieren. |
| O5 | **Actions nur per Versionsnummer festgelegt** (`@v4`, `@v5`), nicht per Prüfsumme; CI warnt, dass diese Fassungen auf dem veralteten Node 20 beruhen. `pip install` ohne Hash-Prüfung, PyInstaller-Zubehör ohne feste Version. | Actions auf aktuelle Hauptversion heben und per Commit-Prüfsumme festlegen; `requirements` mit Hashes. |
| O6 | **Release-Zips:** unsigniert, ohne Prüfsummen; Windows zeigt die SmartScreen-Warnung. Gebündelte Bibliotheken (OpenSSL, SQLite, Qt, Python) bekommen nur mit einem neuen Release Sicherheitsupdates. | Prüfsummen ins Release schreiben; alle paar Monate neu bauen. |
| O7 | **Ungenutzte Netzwerk-Bausteine im Paket:** QtNetwork, `_ssl`, `_socket` werden mit eingepackt, aber nie geladen. | Beim Bauen ausschließen – stärkt die Offline-Zusage und spart Platz. |
| O8 | **Linux-Paket ohne xcb-Bibliotheken:** Der Build meldet fehlende `libxcb-cursor` usw. Unter Wayland egal; unter X11 startet das Programm nur, wenn sie installiert sind. | `libxcb-cursor0` und Verwandte im Build-Schritt installieren. |
| O9 | **Selbsttest-Protokoll** mit festem Namen im Temp-Ordner (`notenverwaltung-selbsttest.txt`); auf einem Mehrbenutzer-Linux könnte ein anderes Konto dort eine Verknüpfung ablegen. Betrifft nur `--selbsttest`. | Protokoll in den eigenen Wegwerf-Ordner schreiben. |
| O10 | **Zweiter Klon `~/Notenverwaltung`** auf Stand 0.6.1 – ohne automatische Sperre und ohne diese Korrekturen. | Löschen oder aktualisieren, damit du nicht versehentlich die alte Fassung startest. |
| O11 | **Was Verschlüsselung der Datei nicht abdeckt:** Auslagerungsdatei und Ruhezustand können Klartext aus dem Arbeitsspeicher enthalten; PDF-Ausgaben und Druckaufträge sind unverschlüsselt; die Sperrdatei nennt den Rechnernamen, die `.ini` die Pfade der zuletzt geöffneten Datenbanken. | Festplatte verschlüsseln (LUKS, BitLocker); PDFs nach dem Drucken löschen. |
| O12 | **Präparierte Datei kann den Rechner bremsen:** Der Kopf darf bis 4 GiB Speicher × 50 Durchläufe für Argon2 verlangen. Nur beim Öffnen einer fremden Datei. | Obergrenze auf 1 GiB × 10 senken. |

## 7 Nicht geprüft

- **Windows-Programm ausgeführt:** nein, hier steht kein Windows-Rechner. Belege sind die CI-Läufe zu v1.0.0.
  Meine Korrekturen und die neuen Tests liefen unter Windows nur in der CI (siehe Nachtrag in Abschnitt 1).
- **Bedienung von Hand:** Ich habe das Fenster nicht durchgeklickt. Die Oberfläche ist über die vorhandenen und
  neuen Tests geprüft.
- **Quelltext Zeile für Zeile:** vollständig gelesen habe ich Speicherung, Verschlüsselung, Sperre,
  Sicherheitsdialoge, Start, Import, KI-Einlesen, Notenlogik, Zeugnisberechnung, Arbeiten, mündliche Noten,
  Stammdaten, Schema, Rückmeldungen. Die Reiter der Oberfläche, die Druckausgaben, die Hilfetexte und die
  Modelle Jahreswechsel, Schnellerfassung, Sitzplan, Offene Punkte und Schüler:innen-Bogen habe ich nur nach
  riskanten Mustern durchsucht. Dort können Bedienfehler stecken, die ich nicht gesehen habe.
- **Sehr große Datenbestände:** nur bis 6000 Personen in einer Probe; keine Zeitmessung der Oberfläche.
- **Echte Daten:** nicht geöffnet. Die echte `Notenverwaltung.ini` und `~/Notenverwaltung` habe ich nicht gelesen
  (nur festgestellt, dass es sie gibt).
- **Ältere Releases** (v0.3.0 bis v0.9.0): nur aufgelistet, nicht heruntergeladen.

## 8 Geänderte Dateien (Commit `2fa74f3`)

| Datei | Änderung |
|---|---|
| `src/notenverwaltung/speicher/tresor.py` | S1, S6 |
| `src/notenverwaltung/speicher/datenbank.py` | S1, S2, S3, S7 |
| `src/notenverwaltung/ui/hauptfenster.py` | S4, S5 |
| `src/notenverwaltung/ausgabe/notfallblatt.py` | S3 |
| `src/notenverwaltung/modell/tabellen.py`, `importieren.py` | S8 |
| `src/notenverwaltung/modell/ki.py` | S10 |
| `src/notenverwaltung/ui/startdialog.py`, `stammdaten_dialoge.py` | S9 |
| `.github/workflows/build.yml` | G1 |
| `tests/test_pruefung.py` (neu) | 34 Tests zu S1–S10 und zum Speichern |
| `tests/test_sperre.py` | nutzt die neue Uhr `betriebszeit()` |
| `pruefung/` (neu) | dieser Bericht, `FORTSCHRITT.md`, Prüfwerkzeuge |

Dateiformat und Notenlogik sind unverändert; alte Datenbanken öffnen sich wie bisher (die
Versionsdateien-Tests bestehen).

Prüfwerkzeuge in `pruefung/werkzeuge/` (Aufruf mit Pfad zur Kopie und zu einem leeren Arbeitsordner):
`nachstellen_speicher.py`, `nachstellen_import_temp.py`, `ods_maskiert.py`. **Achtung:** Die Gegenprobe am
alten Stand nur mit Speichergrenze starten (`ulimit -v 3000000`) – der Import-Fall mit der riesigen Spalte
füllt dort den Arbeitsspeicher. Genau das hat während der Prüfung einmal den Rechner in Speichernot gebracht.

## 9 Selbst getroffene Entscheidungen

| Thema | Entscheidung | Begründung |
|---|---|---|
| Testumgebung | Kopie des Stands im Wegwerf-Ordner, eigene Einstellungen und eigenes Heimatverzeichnis | Echte Daten und Einstellungen bleiben unberührt |
| Schwere von S1 und S2 | „hoch“ | Beide heben eine zentrale Zusage auf (Sperre, Verschlüsselung auf der Platte) |
| Passwortprüfung | gegen den Tresor im Arbeitsspeicher, zeitkonstanter Vergleich | Unabhängig von der Datei; kein neues Dateiformat |
| Dateirechte | `600` auch für die verschlüsselte Datenbank und ihre Sicherungen, nicht nur für Schlüsseldatei und Notfallblatt | Schadet nicht, schützt vor Abgreifen zum Durchprobieren von Passwörtern |
| Sperr-Uhr | `CLOCK_BOOTTIME`, sonst `monotonic` | Zählt den Ruhezustand mit; unter Windows unverändert |
| Gesperrt und Speichern scheitert | Fenster bleibt offen und gesperrt, Meldung in der Statuszeile | Keine Rückfrage, die man gesperrt nicht beantworten könnte |
| Import-Grenzen | höchstens 16384 Spalten, 100 MB je Archivteil | Excel-Obergrenze; reicht für jede Schülerliste |
| Jahrgang mit mehr als zwei Ziffern | bleibt ein Fehler („Jahrgang unbekannt“) wie bisher | Verhalten nicht nebenbei ändern |
| Hauptschlüssel-Wechsel (O1) | nur berichtet | Braucht neues Notfallblatt und neue Schlüsseldatei – deine Entscheidung |
| Notenschlüssel (O2) | nur berichtet | Notenlogik folgt deiner Vorlage; Regel im Projekt: nur mit Tests und Absprache ändern |
| Tooltips (O4), Selbsttest-Protokoll (O9), Argon2-Grenze (O12) | nur berichtet | Geringes Risiko, berühren viele Stellen bzw. den CI-Ablauf |
| Workflow | nur die Rechte geändert, Actions nicht auf Prüfsummen umgestellt | Rechte sind risikolos; ein Tippfehler bei Prüfsummen bräche den Build, und ohne Push kann ich ihn nicht testen |
| GitHub-Einstellungen | Dependabot-Warnungen an, nur GitHub-eigene Actions erlaubt | Eindeutig sinnvoll, sofort umkehrbar, stört den Workflow nicht |
| Automatische Dependabot-Korrekturen | aus gelassen | Würden Pull Requests gegen die bewusst festen Versionen öffnen |
| Ältere Releases | nicht heruntergeladen | Erlaubt war v1.0.0; ältere sind überholt |
| `~/Notenverwaltung` und echte `.ini` | nicht gelesen | Könnten auf echte Daten zeigen; für die Prüfung nicht nötig |
| Commit, Push, Tag | zunächst nichts; nach deinem Auftrag ein Commit auf `main` und Push, kein Tag | So von dir festgelegt |
| Projektdoku | nur ein Verweis in `FORTSCHRITT.md`, `ANLEITUNG.md` unverändert | Die Bedienung ändert sich nicht |
