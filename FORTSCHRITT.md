# Fortschritt Notenverwaltung

## Auftrag
Sebastian: Lastenheft in `LASTENHEFT.md` prüfen, Plan vorlegen (`PLAN.md`), am 12.11.2026 mit „Ja, starten“ freigegeben.
12.11.2026 abends: „mach einfach weiter, bis du wieder von mir hörst“ – Etappen selbstständig abarbeiten, je Etappe committen und pushen.
Rückfragen sind geklärt (Abschnitt „Klärungen“ im Lastenheft) – ab jetzt selbst entscheiden, Entscheidungen hier festhalten.

## Etappen (Details in PLAN.md)
- [x] 0 Fundament (12.11.2026)
- [x] 1 Verschlüsselte Datenbank (12.11.2026)
- [x] 2 Stammdaten (12.11.2026)
- [x] 3 Klassenarbeiten (12.11.2026)
- [x] 4 Druck / PDF, Teil 1 (12.11.2026)
- [x] 5 Windows-Build → **Meilenstein A** (12.11.2026, Release v0.1.0)
- [x] 6 Import (12.11.2026) – SchILD/Untis noch mit echten Beispiel-Exporten von Sebastian gegenprüfen
- [x] 7 Mündliche Noten (12.11.2026), Druck der mündlichen Noten (12.11.2026, Version 0.3.2)
- [x] 8 Notenberechnung → **Meilenstein B** (12.11.2026, Release v0.2.0)
- [x] 9 Schuljahreswechsel (12.11.2026)
- [x] 10 Rückmeldebogen (12.11.2026)
- [x] 11 KI-Paket (12.11.2026)
- [x] 12 Darstellung → **Meilenstein C** (12.11.2026, Version 0.3.0)

Runde 2 (15.11.2026, nach Sebastians Linux-Test; „Ja, starten“ für Etappen 13 und 14):
- [x] 13 Absicherung der Dateien (15.11.2026) – `tests/daten/version_0_3_2.nvdb/.json`, dauerhafte Sicherung vor Format-Umstellung; nebenbei Fehler im Schuljahreswechsel behoben (Klassengruppe „D 8.4“ bekam keine Mitglieder)
- [ ] 14 Etiketten-Rand, Note ohne Punkte → Version 0.3.3
- [ ] 15 Quartalsnoten (braucht Antworten auf Fragen 1–3)
- [ ] 16 Einzelnoten im Reiter „Noten“ → Version 0.4.0
- [ ] 17 Sek II (braucht Antworten auf Fragen 4–6) → Version 0.5.0
- [ ] 18 Hilfe im Programm → Version 0.6.0

## Nächster Schritt
Etappe 14. Danach auf Antworten zu den Fragen warten (Quartalsnoten, Kompatibilität, Sek II).

**Bei jeder Freigabe (Tag vX.Y.Z):** mit genau diesem Stand `python werkzeuge/versionsdatei.py erzeuge
tests/daten/version_X_Y_Z` ausführen und die beiden Dateien committen – aber nur, wenn sich das Dateiformat
oder die Daten-Arten geändert haben. Bestehende Versionsdateien nie neu erzeugen.

Offen / Rückfragen an Sebastian:
- Beispiel-Exporte aus SchILD-NRW und Untis (erfundene Namen) zum Gegenprüfen des Imports
- Quartalsnoten: Was fließt ein (nur das Quartal?), ganze Noten oder mit Tendenz?
- Arbeitet er mit derselben Datei an Rechnern mit verschiedenen Versionen?
- Sek II: Klausurschlüssel (NRW-Standard?), nur Kursführung ohne Abiturberechnung?, 50/50 als Standard?

Bestätigt von Sebastian (12.11.2026): Standard Anteil 1. Halbjahr 10 %; beim Übernehmen genau ,5 → bessere Note (2,5 → 2).

## Entscheidungen
| Punkt | Entscheidung |
|---|---|
| Oberfläche | PySide6-Essentials 6.12 (LGPL), Stil „Fusion“ – sieht unter KDE und Windows gleich aus |
| Python-Umgebung | `~/.venvs/notenverwaltung` (außerhalb des Cloud-Ordners, PySide6 ist groß) |
| Einstellungen | `QSettings` im INI-Format im Benutzerprofil – nur Bedienkomfort, nie Schülerdaten |
| Dateiendung Datenbank | `.nvdb` (in `.gitignore`) |
| Offline-Garantie | `tests/test_offline.py`: statische Prüfung aller Importe + echter Programmstart in frischem Prozess mit gesperrtem Netzwerk |
| Dateiformat | `NVDB` + Version + ASCII-JSON-Kopf + AES-256-GCM(zlib(SQLite)); Kopf ist AAD. Hauptschlüssel verpackt je Zugang (Passwort/Code: Argon2id 64 MiB×3×4; Schlüsseldatei: HKDF) |
| Wiederherstellungscode | 24 Zeichen Crockford-Base32 (120 Bit), Gruppen à 4, O→0, I/L→1 beim Eintippen |
| Sicherungen | Ordner `<Name>-Sicherungen` neben der Datenbank, einmal pro Sitzung vor dem ersten Speichern, max. 20; bei Zugangsänderung werden sie neu verpackt (altes Passwort gilt dort nicht mehr) |
| Sperre | `<Datei>.sperre` (Rechnername, PID); verwaiste eigene Sperre wird übernommen; unter Windows keine PID-Prüfung → Nachfrage |
| Anrede in der Oberfläche | „du“ (freundlich, wie in den übrigen Projekten) |
| Notfallblatt | Drucken direkt oder als PDF (mit Hinweis: PDF enthält den Code, nach dem Drucken löschen); Bestätigung „gesichert“ ist Pflicht, Abbruch nur nach Warnung |
| Passwort | mindestens 10 Zeichen, Unicode-NFC-normalisiert |
| Autospeichern | alle 2 Minuten bei Änderungen, außerdem beim Schließen |
| Navigation | links: Schuljahr, Schüler:innen, Lerngruppen (+ Neue Lerngruppe); Wechsel des Schuljahres unter Datei → Schuljahr |
| Zu-/Abgang | Schulabgang an der Klassenzuordnung, Kurswechsel per Ein-/Austritt an der Mitgliedschaft; wirksames Ende = früheres Datum |
| Eigene Reihenfolge | startet mit der aktuell angezeigten; später Hinzugekommene ans Ende |
| Punkteraster | Spalten Nr., Name, Kl., Summe, Note vorne (immer sichtbar), dann Aufgaben, Vermerk; Enter springt nach rechts (umschaltbar: nach unten), Tab seitlich, Entf leert; Punkte in Viertelschritten; unvollständige Zeilen gelb |
| Notenspiegel | wie ODS ohne Tendenz gezählt; Schnitt ganze Noten + Schnitt mit Tendenz; Anteil unter 4 |
| Festgesetzte Note | per Rechtsklick, Anzeige mit * |
| Avery-Etiketten | 3424: 105×48, 2×6, oben/unten 4,5 mm; 3425: 105×57, 2×5, oben/unten 6 mm (Grundmaße laut Hersteller/Händlern, Ränder rechnerisch, seitlich randlos) + Druckversatz X/Y in den Einstellungen |
| Notenabschnitte | Note ohne Tendenz; Schrift 9…6 pt nach Platz, sonst zweizeilig; Datum = Rückgabedatum der Arbeit oder heute; Startplatz für angebrochene Bögen |
| Punkteliste | A4 quer, Note mit Tendenz (abschaltbar), Hervorhebungen 5/6 und Lücken, Zebra, Durchschnitt je Aufgabe, Notenspiegel + Notenschlüssel |
| Import | ohne Zusatzbibliotheken (XLSX/ODS per ZIP+XML), Synonyme für Spaltennamen, Abgleich ID → Name+Klasse → früheres Jahr; gleichnamig in anderer Klasse wird nicht geraten; alles oder nichts über Speicher-Schnappschuss |
| Mündliche Noten | Zeiträume je Lerngruppe, Standard vier Quartale (Halbjahre in der Mitte geteilt), teilbar, nie über den Halbjahreswechsel; Noten mit Tendenz, Zahl wird zur nächsten Stufe (Gleichstand → bessere); gesperrt außerhalb der Mitgliedschaft |
| Druck mündlich | Hochformat, solange Spalten ≥ 16 mm breit sind, sonst quer; Restbreite ≥ 20 mm wird Spalte „Notizen“; Bemerkungen mit * markiert und unter der Tabelle (Umbruch über Seiten); „Liste zum Eintragen“ ohne Noten mit 8-mm-Zeilen |
| Windows-Build | GitHub Actions, PyInstaller onedir als Zip, Selbsttest `--selbsttest`, Tests unter Windows mit QT_QPA_PLATFORM=windows (offscreen kennt dort keine Schriften) |
| Notenvorschlag | nächstgelegene Note mit Tendenz (Gleichstand → bessere), Herleitung als Tooltip; „Vorschläge übernehmen“ setzt ganze Noten (Zeugnis ohne Tendenz), genau ,5 → bessere |
| Gewichtung | je Lerngruppe: Anteil schriftlich (automatisch 50 %/0 %), Anteil 1. Hj. an 2. Hj. (Standard 10 %), ZP10 automatisch für D/E/M Jahrgang 10 (abschaltbar) |
| ZP10 | Vornote = Ganzjahresnote aus allen Leistungen, Endnote = 50 % Vornote (festgesetzt oder Vorschlag) + 50 % ZP10 |
| Schuljahreswechsel | Assistent unter Datei → Schuljahr; Klassen hochsetzen (erste Jahrgangszahl +1), je Klasse „endet“, je Person versetzen/wiederholen/Abgang; Klassen-Lerngruppen bekommen alle der neuen Klasse, Kurse nur versetzte bisherige Mitglieder; Gewichtung/Sortierung/eigene Reihenfolge werden übernommen; altes Jahr bleibt unverändert |
| Rückmeldebogen | dritte Ausgabe im Druckdialog; eine Seite pro Person: Aufgabe/Thema/möglich/erreicht/Anteil, Erwartungshorizont kursiv (abschaltbar), Note ohne Tendenz, Rückmeldung (Rechtsklick im Raster), Unterschriftszeilen (abschaltbar) |
| KI-Paket | Programm bleibt offline: Prompt-Vorlage (ohne Schülerdaten) zum Kopieren, Antwort als JSON (Format `notenverwaltung-arbeit-1`) wird eingefügt – auch mit Text/Code-Zaun drumherum; neue Arbeit oder Übernahme in vorhandene (Aufgaben der Reihe nach weiterverwendet, Punkte bleiben); Musterlösung als Feld der Arbeit (Migration 6) |
| Darstellung | Ansicht: dunkel/hell, Schrift wählen, größer/kleiner (Strg+Plus/Minus), Standard; Druckschrift im Druckdialog; Kopfzeile „Schule · Lehrkraft“ aus Datei → Angaben für Ausdrucke (in der Datenbank) |
| Notenübersicht | Reiter „Noten“ → Drucken / PDF: A4 quer, Zeitraum 1./2. Halbjahr oder ganzes Jahr, Vorschläge abschaltbar, Notenspiegel der festgesetzten Noten je Halbjahr (2. Hj. = Jahresnote); allgemeiner `VorschauDialog` für weitere Listen |
| Repo | eigenes privates Repo `SebastianMG80/notenverwaltung`; im Repo `lernspiele-it` per `.gitignore` ausgeschlossen |

## Fallstricke
- `.gitignore`-Regeln für erzeugte Ordner immer mit `/` verankern – `ausgabe/` hatte `src/notenverwaltung/ausgabe/` ausgeschlossen (jetzt durch `tests/test_repo.py` abgesichert).
- Excel speichert Klassen wie „9.10“ gern als Zahl → „9.1“. Beim Import ggf. Klassenspalte prüfen.
- Windows-`pdftotext` gibt Latin-1 aus → in Tests `-enc UTF-8`.
- Qt übernimmt Enter im Zelleneditor verzögert (QueuedConnection): in Tests `QApplication.processEvents()` nach Enter; geschlossene Editoren existieren bis zum nächsten Event-Durchlauf weiter (sichtbaren nehmen).
- `segno` (QR) lädt über `xml.sax.saxutils` das ungenutzte `urllib.request` – deshalb erst in `notfallblatt._qr` importieren.
- UI-Tests: `schnelle_kdf`-Fixture benutzen (Argon2id sonst 0,3 s pro Öffnen); Meldungsfenster sind in `conftest.py` stummgeschaltet, `frage` per monkeypatch im jeweiligen Modul setzen.
- Netzwerk-Laufzeittest muss in eigenem Prozess laufen: pytest selbst lädt `ssl`.
- Tests setzen `QSettings.setPath` auf einen Wegwerf-Ordner – nie die echten Einstellungen benutzen.
