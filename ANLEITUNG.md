# Notenverwaltung – Kurzanleitung (Stand 0.3.3)

## Starten

- **Windows:** `Notenverwaltung-windows.zip` aus dem GitHub-Release herunterladen, entpacken, `Notenverwaltung.exe` starten.
  Beim ersten Start warnt Windows ggf. vor einer unbekannten App („Weitere Informationen → Trotzdem ausführen“) –
  das Programm ist nicht signiert.
- **Linux (aus dem Quellcode):** `./start.sh` im Ordner `Notenverwaltung`
  (einmalig vorher die Python-Umgebung einrichten, siehe README.md).
- **Linux (gebaut):** `Notenverwaltung-linux.zip` entpacken, `./Notenverwaltung` starten.
- **Selbsttest:** `Notenverwaltung --selbsttest` prüft Verschlüsselung, Datenbank, PDF und Oberfläche
  (Ergebnis auch in `notenverwaltung-selbsttest.txt` im Temp-Ordner).

Beide Fassungen öffnen dieselben `.nvdb`-Dateien.

## Erste Schritte

1. **Neue Datenbank** anlegen: Datenschutzhinweis lesen, Speicherort wählen (nicht in einem Cloud-Ordner),
   Passwort festlegen, **Notfallblatt drucken** (Wiederherstellungscode).
2. **Schuljahr anlegen** (wird vorgeschlagen).
3. **Schüler:innen** links → „Neu …“ oder „Importieren …“ (CSV, Excel, ODS, Exporte aus SchILD/Untis).
4. **Lerngruppen** anlegen (Datei → Neue Lerngruppe, Strg+L): Klasse in einem Fach oder klassenübergreifender Kurs,
   E/G-Vermerk, schriftlich oder mündlich.
5. In der Lerngruppe:
   - **Klassenarbeiten:** „Neue Arbeit …“ (Aufgaben wie 1, 2, 3a, b, c), Punkte eintippen – Enter springt weiter,
     Summe und Note erscheinen sofort. Rechtsklick: fehlt / schreibt nach / Note festsetzen / Rückmeldung.
     **Note ohne Punkte** (z. B. Nachschreiber:innen): Note direkt in die Spalte „Note“ tippen (2, 3+, 4-);
     * markiert eine festgesetzte Note, Entf hebt die Festsetzung auf. Abschnitt und Rückmeldebogen zeigen
     dann nur die Note.
     „Drucken / PDF …“: Punkteliste, Notenabschnitte (Avery 3424/3425 oder frei), Rückmeldebögen.
     Wird bei Etiketten am Rand etwas abgeschnitten: „Abstand zum Blattrand“ erhöhen (Standard 7 mm).
     „KI-Vorlage …“: Prompt kopieren, Antwort der KI einfügen → Aufgaben, Punkte, Erwartungshorizont, Musterlösung.
   - **Mündlich:** Noten je Quartal (feiner unterteilbar unter „Zeiträume …“), Eingabe 2, 2+, 2- oder 1,7.
     „Drucken / PDF …“: Liste der mündlichen Noten (mit/ohne Tendenz, Halbjahresmittel, Bemerkungen)
     oder leere Liste zum Eintragen von Hand. Bei vielen Zeiträumen automatisch im Querformat.
   - **Noten:** Vorschläge mit Herleitung (Maus über den Vorschlag), Zeugnisnoten festsetzen, Gewichtung einstellen.
     Bei Deutsch/Englisch/Mathematik in Jahrgang 10: Vornote, ZP10 und Endnote.
   - **Schüler:innen:** Mitglieder, Sortierung (Klasse → Alphabet, Alphabet, eigene Reihenfolge), Ein-/Austritt.
6. **Neues Schuljahr:** Datei → Schuljahr → „Neues Schuljahr aus bisherigem übernehmen …“.

## Sicherheit

- Datei → Sicherheit: Passwort ändern, neues Notfallblatt, Schlüsseldatei (z. B. USB-Stick), Ordner mit Sicherungen.
- Passwort vergessen? Im Startdialog „Passwort vergessen?“ → Wiederherstellungscode oder Schlüsseldatei.
- Das Programm speichert automatisch (alle 2 Minuten und beim Schließen) und legt pro Sitzung eine Sicherung an.

## Darstellung

Ansicht → Design (dunkel/hell), Schrift, Strg+Plus/Minus. Datei → Angaben für Ausdrucke (Schule, Lehrkraft).
