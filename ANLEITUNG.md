# Notenverwaltung – Kurzanleitung (Stand 0.8.0)

## Starten

- **Windows:** `Notenverwaltung-windows.zip` aus dem GitHub-Release herunterladen, entpacken, `Notenverwaltung.exe` starten.
  Beim ersten Start warnt Windows ggf. vor einer unbekannten App („Weitere Informationen → Trotzdem ausführen“) –
  das Programm ist nicht signiert.
- **Linux (aus dem Quellcode):** `./start.sh` im Ordner `Notenverwaltung`
  (einmalig vorher die Python-Umgebung einrichten, siehe README.md).
- **Linux (gebaut):** `Notenverwaltung-linux.zip` entpacken, `./Notenverwaltung` starten.
- **Selbsttest:** `Notenverwaltung --selbsttest` prüft Verschlüsselung, Datenbank, PDF und Oberfläche
  (Ergebnis auch in `notenverwaltung-selbsttest.txt` im Temp-Ordner).

Beide Fassungen öffnen dieselben `.nvdb`-Dateien. Neue Versionen öffnen auch alle älteren Dateien und stellen sie
um; vorher bleibt die alte Datei im Ordner `<Name>-Sicherungen` erhalten („…_vor-Umstellung-…“). Eine umgestellte
Datei lässt sich mit älteren Programmversionen nicht mehr öffnen.

**Hilfe im Programm:** F1 öffnet überall die Seite zur aktuellen Ansicht; Menü Hilfe → Inhalt, Tastenkürzel,
Häufige Fragen. Die Hilfe ist im Programm enthalten und funktioniert ohne Internet.

## Erste Schritte

1. **Neue Datenbank** anlegen: Datenschutzhinweis lesen, Speicherort wählen (nicht in einem Cloud-Ordner),
   Passwort festlegen, **Notfallblatt drucken** (Wiederherstellungscode).
2. **Schuljahr anlegen** (wird vorgeschlagen). Quartalswechsel: automatisch in der Mitte des Halbjahres oder
   eigene Daten (Schuljahr bearbeiten → „Quartale“).
3. **Schüler:innen** links → „Neu …“ oder „Importieren …“ (CSV, Excel, ODS, Exporte aus SchILD/Untis).
4. **Lerngruppen** anlegen (Datei → Neue Lerngruppe, Strg+L): Klasse in einem Fach oder klassenübergreifender Kurs,
   E/G-Vermerk, schriftlich oder mündlich.
5. **Strg+Z** nimmt jede Änderung zurück (eine Zelle, ein Dialog, auch Löschen oder den Schuljahreswechsel),
   Strg+Y stellt sie wieder her. **Übersichten → Nachschreibliste:** alle mit „fehlt“/„schreibt nach“.
   **Strg+F** sucht Namen, Lerngruppen und Arbeiten und springt hin. Die Seite **Schuljahr** zeigt die
   **offenen Punkte** (Lücken in Arbeiten, Nachschreiber:innen, fehlende mündliche, Quartals- und Halbjahresnoten
   ab drei Wochen vor dem Stichtag). **Sicherheit:** nach 15 Minuten ohne Eingabe sperrt das Programm
   (Strg+Umschalt+L sofort); ein zweiter Sicherungsort (USB-Stick) bekommt beim Schließen eine Kopie –
   beides unter Bearbeiten → Einstellungen.
6. In der Lerngruppe:
   - **Klassenarbeiten:** „Neue Arbeit …“ (Aufgaben wie 1, 2, 3a, b, c), Punkte eintippen – Enter springt weiter,
     Summe und Note erscheinen sofort. Rechtsklick: fehlt / schreibt nach / Note festsetzen / Rückmeldung.
     **Note ohne Punkte** (z. B. Nachschreiber:innen): Note direkt in die Spalte „Note“ tippen (2, 3+, 4-);
     * markiert eine festgesetzte Note, Entf hebt die Festsetzung auf. Abschnitt und Rückmeldebogen zeigen
     dann nur die Note.
     „Drucken / PDF …“: Punkteliste, Notenabschnitte (Avery 3424/3425 oder frei), Rückmeldebögen.
     Wird bei Etiketten am Rand etwas abgeschnitten: „Abstand zum Blattrand“ erhöhen (Standard 7 mm).
     Rückmeldebögen mit langem Erwartungshorizont: erst kleinere Schrift (bis 7 pt, für alle gleich), sonst eine
     Folgeseite; für beidseitigen Druck „jeder Bogen beginnt auf einem neuen Blatt“ wählen.
     „KI-Vorlage …“: Prompt kopieren, Antwort der KI einfügen → Aufgaben, Punkte, Erwartungshorizont, Musterlösung.
     **Aufgabe für Aufgabe korrigieren:** „Enter springt nach unten“ – nach der letzten Person geht es mit der
     nächsten Aufgabe weiter; daneben steht, wie viele schon eingetragen sind.
     **Rückmeldungen …:** Person für Person schreiben (Strg+Bild auf/ab), Textbausteine per Doppelklick oder
     Kürzel + Strg+Leertaste, Platzhalter wie {Vorname}, {Stärken}, {Übungsbedarf}. Optional (Bearbeiten →
     Einstellungen): Vorschlag aus den Punkten und Aufgabenanalyse (Lösungsquote je Aufgabe, auch als Ausdruck).
   - **Mündlich:** Noten je Quartal (feiner unterteilbar unter „Zeiträume …“), Eingabe 2, 2+, 2- oder 1,7.
     „Drucken / PDF …“: Liste der mündlichen Noten (mit/ohne Tendenz, Halbjahresmittel, Bemerkungen)
     oder leere Liste zum Eintragen von Hand. Bei vielen Zeiträumen automatisch im Querformat.
   - **Noten:** in der Reihenfolge der Abgabe – 1. Quartal, 1. Halbjahr, 3. Quartal, 2. Halbjahr. Vorschläge mit
     Herleitung (Maus über den Vorschlag), Noten festsetzen, Gewichtung einstellen.
     Quartalsnoten zählen nur die Leistungen des Quartals und werden mit Tendenz festgesetzt (2+, 2-),
     Halbjahresnoten ganz. „Zeitraum“: ganzes Jahr oder ein Halbjahr. „Ansicht: mit Einzelnoten“ zeigt jede
     Arbeit und jeden mündlichen Zeitraum vor der Note, zu der sie zählen.
     Bei Deutsch/Englisch/Mathematik in Jahrgang 10: Vornote, ZP10 und Endnote.
     „Drucken / PDF …“: Notenübersicht mit Quartalen und Notenspiegeln.
   - **Schüler:innen:** Mitglieder, Sortierung (Klasse → Alphabet, Alphabet, eigene Reihenfolge), Ein-/Austritt.
6. **Neues Schuljahr:** Datei → Schuljahr → „Neues Schuljahr aus bisherigem übernehmen …“.
   Oberstufe: aus allen 10. Klassen wird die EF, dann Q1 und Q2; die Q2 endet (Abitur) – alles im Assistenten änderbar.

## Oberstufe (EF, Q1, Q2)

- Schüler:innen bekommen als Klasse „EF“, „Q1“ oder „Q2“ (Jahrgang 11, 12, 13).
- Lerngruppe mit Jahrgang 11–13 anlegen: Notensystem **Punkte 0–15**, Kursart GK oder LK, schriftlich oder mündlich.
- **Klausuren** wie Klassenarbeiten; Schlüssel nach NRW-Tabelle (ab 95 % 15 Punkte, je 5 % weniger ein Punkt bis
  50 % = 6 Punkte, dann 45/39/33/27/20 % = 5/4/3/2/1 Punkt) – pro Klausur änderbar, eigene Vorlagen möglich.
  Punkte ohne Klausurpunkte direkt in die Spalte „Notenpunkte“ tippen (ganze Punkte).
- **Sonstige Mitarbeit** im Reiter „Mündlich“: Punkte 0–15 (Kommazahlen werden gerundet, 10,5 → 11).
- **Noten:** Quartals- und Halbjahresnoten in Punkten; schriftliche Kurse standardmäßig 50 % Klausuren / 50 %
  Sonstige Mitarbeit; die Halbjahre werden getrennt bewertet. Schnitte werden auf ganze Punkte gerundet (,5 → besser).
- Ausdrucke (Punkteliste, Abschnitte, Rückmeldebogen, Übersichten) zeigen Punkte; der Notenspiegel zählt Punkte
  und den Anteil unter 5 Punkten. Nicht enthalten: Abiturzulassung und Abiturprüfungen.

## Sicherheit

- Datei → Sicherheit: Passwort ändern, neues Notfallblatt, Schlüsseldatei (z. B. USB-Stick), Ordner mit Sicherungen.
- Passwort vergessen? Im Startdialog „Passwort vergessen?“ → Wiederherstellungscode oder Schlüsseldatei.
- Das Programm speichert automatisch (alle 2 Minuten und beim Schließen) und legt pro Sitzung eine Sicherung an.

## Darstellung

Ansicht → Design (dunkel/hell), Schrift, Strg+Plus/Minus. Datei → Angaben für Ausdrucke (Schule, Lehrkraft).
