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
- [x] 14 Etiketten-Rand, Note ohne Punkte → Version 0.3.3 (15.11.2026)
- [x] 15 Quartalsnoten (15.11.2026) – Schema 7: Quartalswechsel je Schuljahr, Notenarten q1/q3
- [x] 16 Einzelnoten im Reiter „Noten“ → Version 0.4.0 (15.11.2026)
- [x] 17 Sek II → Version 0.5.0 (15.11.2026) – Schema 8: Kursart GK/LK, Klausurschlüssel Sek II; Punkte als „11P“
- [x] 18 Hilfe im Programm → Version 0.6.0 (15.11.2026)

Nach Runde 2:
- [x] Rückmeldebögen liefen bei langen Erwartungshorizonten (KI-Antwort) über Note und Unterschriften → Version 0.6.1 (15.11.2026)

Runde 3 (15.11.2026, Plan in PLAN.md; Sebastian: alle Etappen am Stück, letzte Version 1.0.0):
- [x] 19 Rückgängig / Wiederholen (15.11.2026)
- [x] 20 Aufgabenweise korrigieren, Nachschreibliste (15.11.2026)
- [x] 21 Textbausteine, Rückmeldungs-Vorschlag, Aufgabenanalyse → Version 0.7.0 (15.11.2026) – Schema 9: Tabelle textbaustein
- [x] 22 Automatisch sperren, zweiter Sicherungsort (15.11.2026)
- [x] 23 Schnellsuche, Übersicht „Offene Punkte“ → Version 0.8.0 (15.11.2026)
- [x] 24 Schnellerfassung je Stunde (15.11.2026) – Schema 10: Tabelle beobachtung
- [x] 25 Sitzplan → Version 0.9.0 (15.11.2026) – Schema 11: Tabellen sitzplan, sitzplatz
- [x] 26 Schüler:innen-Bogen → Version 1.0.0 (15.11.2026)

## Prüfung auf Bugs und Sicherheit (15.11.2026)
Bericht: `pruefung/BERICHT.md`, Stand der Prüfung: `pruefung/FORTSCHRITT.md`. Zwei schwere Lücken (Sperre per
Dateitausch umgehbar, Klartext im Temp-Ordner) und weitere Funde sind behoben, Tests in `tests/test_pruefung.py`.
Die Korrekturen sind committet und gepusht (`2fa74f3`), CI unter Linux und Windows grün; noch kein neues Release. Offene Entscheidungen stehen in
Abschnitt 6 des Berichts (u. a. Hauptschlüssel beim Passwortwechsel erneuern, Notenschlüssel unter 10 Punkten).

## Nächster Schritt
Runde 3 ist abgeschlossen (Etappen 19–26, Version 1.0.0). Warten auf Sebastians Testrunde.
Später: freier Layout-Editor.

**Bei jeder Freigabe (Tag vX.Y.Z):** mit genau diesem Stand `python werkzeuge/versionsdatei.py erzeuge
tests/daten/version_X_Y_Z` ausführen und die beiden Dateien committen – aber nur, wenn sich das Dateiformat
oder die Daten-Arten geändert haben. Bestehende Versionsdateien nie neu erzeugen.

Offen / Rückfragen an Sebastian:
- Beispiel-Exporte aus SchILD-NRW und Untis (erfundene Namen) zum Gegenprüfen des Imports

Bestätigt von Sebastian (12.11.2026): Standard Anteil 1. Halbjahr 10 %; beim Übernehmen genau ,5 → bessere Note (2,5 → 2).
Bestätigt (15.11.2026): Quartalsnote nur aus dem Quartal, mit Tendenz; Dateien dürfen nach Umstellung mit alten Versionen inkompatibel sein.
Bestätigt (15.11.2026): Sek II mit NRW-Klausurschlüssel, nur Kursführung (ohne Abitur), 50/50 als Standard.
Bestätigt (15.11.2026, Runde 3): Schnellerfassung ++ = 1 … –– = 5 als Vorschlag, keine Abwesenheit; Sitzplan mit Tisch-Raster, dann Personen setzen; Schüler:innen-Bogen für die Lehrkraft mit Weglass-Häkchen; Sperre nach 15 min (einstellbar); am Stück, letzte Version 1.0.0.

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
| Etiketten-Rand | Inhalt hält am Papierrand mindestens 7 mm Abstand (einstellbar 0–15 mm, Druckversatz eingerechnet), zur Etikettenmitte weiter 4 mm Innenrand; Grund: Etiketten reichen seitlich bis an den Blattrand, Drucker bedrucken dort 4–6 mm nicht |
| Note ohne Punkte | Note direkt in die Notenspalte tippen = Festsetzung (*); gleich der berechneten Note → keine Festsetzung; eingetippte Note löscht den Vermerk fehlt/schreibt nach/befreit; Entf hebt Festsetzung auf; Abschnitt/Bogen ohne Punkte zeigen „ohne Einzelpunkte bewertet“ statt leerer Tabelle |
| Versionsdateien | Pro Freigabe mit geändertem Format eine Testdatenbank `tests/daten/version_X_Y_Z` (+ JSON); nie neu erzeugen; vor jeder Format-Umstellung bleibt die alte Datei als dauerhafte Sicherung („_vor-Umstellung-Format-a-auf-b“), die nicht rotiert |
| Quartale | Quartalswechsel je Schuljahr (Standard Mitte des Halbjahres = bisherige mündliche Quartale); Arbeit zählt zum Quartal ihres Datums, mündlicher Zeitraum zum Quartal seines Beginns; Quartalsnote = Halbjahresgewichtung nur über das Quartal, ohne Anteil anderer Zeiträume; Übernehmen mit Tendenz |
| Noten-Reiter | Reihenfolge Q1 – 1. Hj. – Q3 – 2. Hj.; Zeitraum-Auswahl (Standard: laufendes Halbjahr); Ansicht „mit Einzelnoten“: Leistungen des 1./3. Quartals vor den Quartalsspalten, des 2./4. vor den Halbjahresspalten |
| Notenübersicht-Druck | wählt die ausführlichste Spaltenauswahl, die passt: erst Quartals-Teilnoten weg, dann Halbjahres-Teilnoten, dann Vorschläge ohne Zahl, zuletzt schmalere Namensspalte; festgesetzte Noten bleiben immer |
| Sek II – Punkte | `Punkte` ist eine Unterart von `Note` (stufe/tendenz = Sek-I-Entsprechung, 11 P = 2), Rechenwert = Punktzahl; Speicherung „11P“; `Notensystem` (sek1/sek2) bündelt Eingabe, Runden (,5 → besser), Liste, Standardschlüssel; Typprüfung beim Speichern (keine Noten in Sek-II-Kursen und umgekehrt) |
| Sek II – Lerngruppe | Notensystem folgt dem Jahrgang (11–13 = Punkte), Wechsel nur ohne vorhandene Noten; Kursart GK/LK (eigene Spalte, E/G nur Sek I); Anteil 1. Hj. = 0 (Halbjahre getrennt); keine ZP10 |
| Sek II – Notenspiegel | Anzahl je Punktzahl 15–0, Schnitt in Punkten, „unter 5 P.“ = Defizite (0–4 Punkte); Notenübersicht bündelt 15–13/12–10/…/0 |
| Sek II – Wechsel | Klassen 10.x → EF, EF → Q1 → Q2; Q2 standardmäßig „endet“ (Abitur); übernommene Lerngruppen mit Jahrgang ≥ 11 werden zu Punkte-Gruppen (ohne E/G, Anteil 1. Hj. 0) |
| Schlüssel-Vorlagen | je Notensystem eigener Standard; Vorlage „Standard Sek II (NRW)“ per Migration 8 |
| Hilfe | Texte als HTML im Python-Modul `hilfe/texte.py` (kein Datei-Nachladen, PyInstaller-sicher, offline); Fenster mit Themenliste, Volltextsuche, internen Verweisen (externe werden ignoriert); F1 anwendungsweit per Ereignisfilter, Thema vom Fokus-Widget aufwärts (`JE_KLASSE`, `hilfe_thema()`); bei modalem Dialog gehört das Hilfefenster zum Dialog; Test: jede Dialog-/Assistentenklasse hat ein Thema, alle Verweise gültig, alle Seiten erreichbar |
| Rückmeldebogen-Umbruch | Bogen wird vorher ausgemessen (600 dpi, Schrift ohne Hinting → Vorschau und Druck brechen gleich um). Erwartungshorizont über die ganze Tabellenbreite, Teilaufgaben „a) … b) …“ als eigene Absätze. Stufen 8,5 → 8 → 7,5 → 7 pt, eine Größe für alle Bögen eines Ausdrucks; reicht 7 pt nicht, Folgeseite mit 8,5 pt, Tabellenkopf wiederholt, Note + Rückmeldung + Unterschriften zusammen am Ende. Unterschriften kompakt in einer Zeile, unterer Rand 14 mm. Option „beidseitig“ fügt leere Rückseiten ein. Titel wird verkleinert statt abgeschnitten |
| Rückgängig | TEMP-Trigger protokollieren je Änderung den Umkehrbefehl (Verfahren von sqlite.org), `speicher/verlauf.py`; kein neues Dateiformat, Verlauf endet beim Schließen; ein Schritt = alles zwischen zwei Eingaben (Ereignisfilter auf Taste/Mausklick), max. 200; Umkehren mit `defer_foreign_keys`; vom Programm selbst angelegte Standard-Zeiträume ohne Verlauf; nach Rückgängig bleiben Ansicht, Arbeit und Zelle erhalten; Strg+Z, Strg+Y und Strg+Umschalt+Z |
| Aufgabenweise | Umschalter „Enter springt nach unten“ gab es schon; neu: am Spaltenende zur ersten Person der nächsten Aufgabe, gesperrte Felder übersprungen, am Rasterende stehen bleiben, Wahl je Reiter gemerkt (QSettings), Fortschritt „Aufgabe 3a: 17 von 28 eingetragen“ (ohne fehlt/schreibt nach/befreit) |
| Nachschreibliste | Menü „Übersichten“; Status fehlt/schreibt nach aus allen Gruppen des Schuljahrs; erledigt = Punkte oder Note; Ausdruck ohne Noten mit Spalten Termin/Raum/erledigt (für die Aufsicht); Doppelklick öffnet die Arbeit |
| Textbausteine | In der Datenbank (Schema 9), damit sie auf allen Rechnern gleich sind; 6 Startbausteine per Migration; Kürzel eindeutig je Fach (fachbezogen vor allgemein); Platzhalter {Vorname} {Nachname} {Note} {Punkte} {Höchstpunkte} {Prozent} {Arbeit} {Fach} {Stärken} {Übungsbedarf}, unbekannte bleiben stehen |
| Rückmeldungsfenster | Ersetzt das einfache Textfeld: Person für Person mit Vorige/Nächste (speichert), Bausteinliste mit Suche, Kürzel + Strg+Leertaste; Knopf „Rückmeldungen …“ im Reiter |
| Vorschlag / Analyse | Opt-in unter Bearbeiten → Einstellungen (QSettings, je Rechner); Stärke ab 80 %, Übungsbedarf unter 50 % (einstellbar); Thema der Aufgabe, sonst „Aufgabe 3a“; Analyse neben dem Notenspiegel (Balken, rot/grün) und als Ausdruck ohne Namen |
| Automatisch sperren | 15 min ohne Taste/Mausklick/Mausrad (einstellbar, 0 = nie), Strg+Umschalt+L; vorher speichern; undurchsichtiger Schirm über jedem sichtbaren Fenster, Passwortfeld auf dem obersten modalen Dialog (sonst Hauptfenster), Dialoginhalte bleiben; Ereignisfilter lässt Eingaben nur zum Schirm durch und nimmt ShortcutOverride an (keine Kürzel); Prüfung mit `pruefe_passwort` (Argon2) |
| Zweiter Sicherungsort | Ordner je Rechner (QSettings); beim Schließen und von Hand eine verschlüsselte Kopie `<name>_<zeit>.nvdb` (über .teil-Datei), neueste 10 bleiben (einstellbar); nicht erreichbar → nur Hinweis; nie die Schlüsseldatei; nicht der Datenbankordner selbst; Cloud-Hinweis im Dialog |
| Schnellsuche | Strg+F: Personen (mit allen Lerngruppen), Lerngruppen, Arbeiten (Titel/Thema) im aktuellen Schuljahr; ohne Akzente und Groß/klein (casefold, ß = ss); Person+Gruppe öffnet die Gruppe im aktuellen Reiter und markiert die Zeile |
| Offene Punkte | Auf der Schuljahrsseite (Startansicht): geschriebene Arbeiten mit Lücken, Nachschreiben (eine Zeile), vorbeie mündliche Zeiträume ohne Note (solange die Quartals-/Halbjahresnote fehlt), Q1/HJ1/Q3/HJ2 ab 21 Tagen vor dem Stichtag (Ende des Zeitraums), ⚠ ab 7 Tagen/überfällig; HJ2 nicht bei ZP10-Gruppen; Personen zählen, wenn sie am Stichtag (bzw. heute) da sind |
| Schnellerfassung | Reiter „Schnellerfassung“ je Lerngruppe; eine Bewertung je Person und Tag (Format 10, PK Gruppe/Person/Datum); Eingabe ++ + o - -- oder 1–5; Spalten = Tage im gewählten mündlichen Zeitraum, „Stunde hinzufügen“ legt eine leere Spalte an; Ø → Note (Sek I nächste mit Tendenz, Gleichstand besser; Sek II 17 − 3·Ø); Vorschlag grau in Klammern in leeren Feldern des Reiters Mündlich, übernehmen per Rechtsklick oder „Ø als mündliche Note übernehmen“ (nur ohne Note); keine Abwesenheit (Sebastian) |
| Sitzplan | Mehrere Pläne je Lerngruppe (Format 11), Raster bis 12 × 12 (Standard 8 × 6: drei 2er-Tische je Reihe), Koordinaten aus Sicht der Klasse, „Sicht vom Pult“ dreht; Modi Tische (Klick/Ziehen, Vorlagen; Besetzte bleiben), Personen (Ziehen aus der Liste, Platz→Platz tauscht, Klick-Name-dann-Platz, Doppelklick macht frei, alphabetisch/zufällig verteilen), Bewerten (Platz antippen → Schnellerfassung am gewählten Tag); Ausdruck quer, nur Namen; gelöschte Person → Platz frei (ON DELETE SET NULL) |
| Schüler:innen-Bogen | Je Person über alle Schuljahre (neueste zuerst) und alle eigenen Lerngruppen: Zeugnisnoten, Arbeiten (Punkte/Note/Vermerk/Rückmeldung), mündliche Noten mit Bemerkung, Schnellerfassung mit Notizen; Ausdruck fließend über Seiten, Überschriften bleiben beim Inhalt; Häkchen: Tendenzen, Punkte, Rückmeldungen, Bemerkungen, Schnellerfassung, frühere Jahre; „Für Eltern“ = ohne Tendenzen, Bemerkungen, Schnellerfassung; Strg+B nimmt die gewählte Person (jeder Reiter kennt `aktuelle_person`), sonst Suche |
| Version 1.0.0 | Sebastian: letzte Version der Runde 3 heißt 1.0 (produktiv einsetzbar); keine neue Versionsdatei, Format seit 0.9.0 (11) unverändert |
| Jahreswechsel-Fehler | Klassengruppen „D 8.4“ bekamen keine Mitglieder (Klasse aus erstem Wort); jetzt aus den Mitgliedern abgeleitet (gefunden in Etappe 13) |
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
