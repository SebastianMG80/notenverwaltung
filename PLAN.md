# Notenverwaltung – Etappenplan

Grundlage: [LASTENHEFT.md](LASTENHEFT.md), Stand 12.11.2026.

**Aufwandsangabe:** in Arbeitssitzungen (AS). Eine AS ist ein zusammenhängender Arbeitsblock von mir (etwa 2–4 Stunden), einschließlich Tests. Dazu kommen deine Testrunden. Die Werte sind grobe Schätzungen mit etwa ±30 %.

Jede Etappe endet mit einem lauffähigen Stand, automatischen Tests und einem Eintrag in `FORTSCHRITT.md`.

## Etappen

| # | Etappe | Inhalt | Aufwand |
|---|--------|--------|---------|
| 0 | Fundament | Eigenes privates Repo, Projektgerüst (PySide6, venv mit festen Versionen), Grund-Design dunkel, Test-Rahmen (pytest), automatischer Offline-Test (verbietet Netzwerk-Importe im Code), `.gitignore` für Datenbanken | 1 AS |
| 1 | Verschlüsselte Datenbank | Dateiformat v1 mit Versionsnummer. Startdialog: letzte, andere oder neue Datenbank. Passwortabfrage, Wiederherstellungscode und Notfallblatt-PDF mit QR-Code und Datenschutzhinweis, Passwort ändern, optionale Schlüsseldatei. Sicheres Speichern (erst Zwischendatei, dann ersetzen), automatisches Speichern, Sicherungskopien mit Rotation, Sperre gegen doppeltes Öffnen, Warnung bei Cloud-Ordner | 3 AS |
| 2 | Stammdaten | Schuljahre mit Halbjahren. Fächer und Lerngruppen (Klasse oder Kurs, schriftlich/mündlich, E/G-Vermerk, Jahrgang). Schüler:innen mit Jahrgang und Klasse. Zu- und Abgänge mit Datum. Sortierung: Klasse → Alphabet (Standard), Alphabet, eigene Reihenfolge. Notensystem abstrakt angelegt, damit Sek II später passt | 3 AS |
| 3 | Klassenarbeiten | Aufgaben mit Teilaufgaben (3a, b, c) und Höchstpunkten. Punkteeingabe als Tabelle, schnell per Tastatur wie in der Tabellenkalkulation. Notenschlüssel: Prozenttabelle als Standard, pro Arbeit änderbar, als Vorlage speicherbar. Interne Tendenz (1,7 / 2,3), Ausgabe ohne Tendenz. Notenspiegel, Schnitt, Anteil unter 4 | 3 AS |
| 4 | Druck / PDF, Teil 1 | Punkteliste, Notenspiegel. Notenabschnitte frei skalierbar und als Avery 3424/3425 – mit Startposition auf angebrochenen Bögen und Druckversatz-Kalibrierung. Optionen: leere Zeilen ausblenden, Hervorhebungen | 3 AS |
| 5 | Windows-Build | GitHub Actions baut die `.exe`. Automatischer Kompatibilitätstest: Eine unter Linux erzeugte Datenbank wird unter Windows geöffnet und umgekehrt | 1–2 AS |
| | **Meilenstein A** | **Ersetzt Punkteliste.ods vollständig – Linux und Windows. Erste Testrunde für dich.** | |
| 6 | Import | Assistent mit Spaltenzuordnung und Vorschau: CSV, XLSX, ODS, SchILD-NRW, Untis. Abgleich mit vorhandenen Schüler:innen, Dubletten-Erkennung | 2–3 AS |
| 7 | Mündliche Noten | Zeiträume: Quartal als Standard, frei feiner unterteilbar. Eingaberaster. Nach dem Abgangsdatum ist keine Eingabe mehr möglich, die Daten bleiben erhalten | 2 AS |
| 8 | Notenberechnung und Vorschläge | Gewichtung pro Fach (schriftlich ca. 50 %). 2. Halbjahr mit Anteil des 1. Halbjahres (5–10 %). Sonderfall D/E/M Jahrgang 10: Ganzjahresnote 50 % + ZP10 50 %. Vorschlag mit nachvollziehbarer Herleitung, Festsetzung durch die Lehrkraft. Übersichten pro Klasse/Kurs, halbjährlich und ganzjährig | 3 AS |
| | **Meilenstein B** | **Komplettes Halbjahr im Programm führbar. Zweite Testrunde.** | |
| 9 | Schuljahreswechsel | Übernahme-Assistent: Versetzen (8.4 → 9.4), Abgänge und Zugänge, Kurse neu bilden. Altes Jahr bleibt über das Menü Datei erreichbar | 2 AS |
| 10 | Rückmeldebogen | Eine Seite pro Person: Aufgaben, erreichte Punkte, Kriterien/Erwartungshorizont, Bemerkung, Note ohne Tendenz | 2 AS |
| 11 | KI-Paket | Prompt-Vorlage aus dem Programm. Festes JSON-Format für Aufgaben, Punkte, Musterlösung und Rückmeldetexte. Einlesen mit Prüfung und Vorschau in eine bestehende Lerngruppe | 2 AS |
| 12 | Darstellung und Druckanpassung | Hell/dunkel umschaltbar, Schriftarten. Druckvorlagen mit ein- und ausschaltbaren Bausteinen, Live-Vorschau | 2–3 AS |
| | **Meilenstein C** | **Alles aus dem Lastenheft außer Layout-Editor und Sek II. Dritte Testrunde.** | |

**Summe Etappen 0–12: etwa 29–34 AS**, dazu drei Testrunden.

## Später (nicht im ersten Durchgang)

| Vorhaben | Aufwand |
|----------|---------|
| Freier Layout-Editor für alle Ausgaben | 5–8 AS |
| Sek II (0–15 Punkte, Q-Phase, Kursarten) | 4–6 AS |

## Runde 2 – nach Sebastians Linux-Test (15.11.2026)

| # | Etappe | Inhalt | Aufwand |
|---|--------|--------|---------|
| 13 ✔ | Absicherung der Dateien | Je freigegebener Version eine Beispiel-Datenbank als Testdatei; jede neue Version muss sie öffnen, umstellen und alle Noten unverändert zeigen. Vor jeder Umstellung des Dateiformats eine eigene Sicherung („vor Umstellung auf 0.4“) | 0,5 AS |
| 14 ✔ | Schnelle Korrekturen | Etiketten: größerer Innenabstand zum Blattrand, einstellbar. Klassenarbeiten: Note direkt in die Notenspalte tippen, auch ohne Punkte; Abschnitt und Rückmeldebogen zeigen dann nur die Note | 1 AS |
| | **Version 0.3.3** | **Testrunde: Etiketten und Nachschreiber** | |
| 15 ✔ | Quartalsnoten | Quartalsgrenze je Halbjahr im Schuljahr. Vorschlag aus den Arbeiten und mündlichen Noten des Quartals. Festsetzen in der Reihenfolge Q1 – 1. Hj. – Q3 – 2. Hj., auch im Druck der Notenübersicht. Dafür ändert sich das Dateiformat (Umstellung 7) | 2 AS |
| 16 ✔ | Einzelnoten im Reiter „Noten“ | Umschalter: zusammengefasst (wie bisher) oder einzeln (jede Arbeit, jeder mündliche Zeitraum) | 1–1,5 AS |
| | **Version 0.4.0** | **Testrunde: Notenabgabe** | |
| 17 ✔ | Sek II | Notensystem 0–15 Punkte. EF/Q1/Q2 (Jg. 11–13), GK/LK, schriftlich/mündlich belegt. Klausuren mit Punkteschlüssel, Sonstige Mitarbeit, Quartals- und Halbjahresnoten in Punkten, Abschnitte/Bogen/Übersichten in Punkten. Schuljahreswechsel EF → Q1 → Q2 | 4–6 AS |
| | **Version 0.5.0** | **Testrunde: Oberstufe** | |
| 18 ✔ | Hilfe im Programm | Menü Hilfe und F1: Hilfefenster mit Inhaltsverzeichnis und Suche, F1 öffnet die Seite zur aktuellen Ansicht, offline mitgeliefert | 1,5–2 AS |
| | **Version 0.6.0** | | |

**Summe Runde 2: etwa 10–13 AS.**

Reihenfolge: Erst die Absicherung, weil Etappe 15 das Dateiformat ändert. Dann die kleinen Korrekturen, die sofort im Alltag helfen. Quartalsnoten vor der Einzelansicht, weil beide den Reiter „Noten“ umbauen. Sek II setzt auf Quartalsnoten und Noten-Reiter auf. Die Hilfe zuletzt, damit sie alle Funktionen beschreibt.

## Runde 3 – Komfort und Unterricht (15.11.2026)

| # | Etappe | Inhalt |
|---|--------|--------|
| 19 ✔ | Rückgängig / Wiederholen | Strg+Z / Strg+Y für alle Änderungen der Sitzung, an der Datenbank angesetzt (gilt automatisch für alle späteren Eingaben); kein neues Dateiformat |
| 20 ✔ | Korrektur-Komfort | Aufgabenweise korrigieren (Enter springt nach unten, umschaltbar); Nachschreibliste (alle mit „fehlt“ über alle Gruppen, druckbar) |
| 21 ✔ | Rückmeldungen | Textbausteine mit Platzhaltern ({Vorname} …), in der Datei gespeichert (Format 9); Rückmeldungs-Vorschlag aus den Aufgabenergebnissen (opt-in); Aufgabenanalyse mit Lösungsquote je Aufgabe (opt-in) |
| | **Version 0.7.0** | |
| 22 ✔ | Sicherheit | Automatisch sperren nach 15 Minuten ohne Eingabe (einstellbar, abschaltbar, Passwort zum Entsperren); zweiter Sicherungsort (z. B. USB-Stick) |
| 23 ✔ | Überblick | Schnellsuche Strg+F nach Namen über alle Gruppen; Übersicht „Offene Punkte“ (Lücken in Arbeiten, fehlende Quartals-/Halbjahresnoten vor dem Stichtag, Nachschreiber:innen) |
| | **Version 0.8.0** | |
| 24 ✔ | Schnellerfassung je Stunde | ++ / + / o / – / –– je Person und Stunde, sporadisch; Durchschnitt (++ = 1 … –– = 5) als Vorschlag neben der mündlichen Note, übernehmen per Klick (Format 10) |
| 25 ✔ | Sitzplan | Raster, um Tische schnell zu platzieren; danach Schüler:innen auf Plätze setzen; mehrere Pläne je Lerngruppe; Schnellerfassung per Tippen auf den Platz; Ausdruck für Vertretungskräfte |
| | **Version 0.9.0** | |
| 26 ✔ | Schüler:innen-Bogen | Alles zu einer Person aus allen eigenen Gruppen: Arbeiten, Rückmeldungen, mündliche Noten, Beobachtungen, Zeugnisnoten, Verlauf über die Jahre; Häkchen zum Weglassen für die Weitergabe an Eltern |
| | **Version 1.0.0** | **für den produktiven Einsatz** |

Reihenfolge: Rückgängig zuerst, damit alle späteren Eingaben es automatisch bekommen. Die Korrektur-Funktionen
teilen sich die Auswertung je Aufgabe. Sicherheit und Überblick sind kleine, unabhängige Teile vor den großen.
Der Sitzplan ist vor allem eine Eingabefläche für die Schnellerfassung und folgt ihr. Der Schüler:innen-Bogen
bündelt alles und kommt zuletzt.

## Begründung der Reihenfolge

- **Datenbank zuerst:** Verschlüsselung und Dateiformat sind das Fundament. Ein späterer Umbau würde vorhandene Daten gefährden.
- **Windows vor dem ersten Test:** Plattformprobleme (Pfade, Schriften, Druck) fallen früh auf, solange der Code noch klein ist. Der automatische Kompatibilitätstest sichert die 100-%-Kompatibilität dauerhaft ab.
- **Meilenstein A ist schon im Alltag nutzbar:** Arbeiten korrigieren und Abschnitte drucken ist der häufigste Anwendungsfall.
- **Import nach Meilenstein A:** Für SchILD- und Untis-Exporte brauche ich anonymisierte Beispieldateien von dir. Bis dahin reicht die Eingabe von Hand.

## Was ich von dir brauche

- **Vor Etappe 6:** je eine Beispiel-Exportdatei aus SchILD-NRW und Untis, mit erfundenen Namen
- **Nach jedem Meilenstein:** eine Testrunde und deine Rückmeldung
