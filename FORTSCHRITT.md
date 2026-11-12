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
- [ ] 4 Druck / PDF, Teil 1
- [ ] 5 Windows-Build → **Meilenstein A**
- [ ] 6 Import (braucht Beispiel-Exporte SchILD-NRW + Untis von Sebastian)
- [ ] 7 Mündliche Noten
- [ ] 8 Notenberechnung → **Meilenstein B**
- [ ] 9 Schuljahreswechsel
- [ ] 10 Rückmeldebogen
- [ ] 11 KI-Paket
- [ ] 12 Darstellung → **Meilenstein C**

## Nächster Schritt
Etappe 4 – Druck / PDF. Plan:
1. `ausgabe/punkteliste.py`: Punkteliste einer Arbeit (A4 quer, wie Punkteliste.ods: Kopf Kurs/Datum, Aufgaben mit Höchstpunkten,
   Zeilen je Schüler:in, Summe, Note) – Optionen: leere Zeilen ausblenden, Hervorhebung (z. B. Noten 5/6, unvollständig), Notenspiegel
   und Notenschlüssel unten.
2. `ausgabe/abschnitte.py`: Notenabschnitte (wie unterer Teil der ODS: Name, Aufgabe/max/erreicht, Summe, Datum, Note **ohne Tendenz**).
   Formate: frei (Breite/Höhe in mm, Spalten/Zeilen, Ränder) und feste Vorlagen Avery Zweckform 3424 (105×48, 2×6) und 3425 (105×57, 2×5)
   – Maße vor Umsetzung gegenprüfen! Startposition auf angebrochenem Bogen, Druckversatz X/Y (in Einstellungen gespeichert).
   Spaltenbreite passt sich der Aufgabenzahl an, Mindestschrift ~6 pt, sonst zweizeilig.
3. `ausgabe/notenspiegel.py` für eine Arbeit (ggf. in Punkteliste integriert).
4. UI: Knopf „Drucken / PDF …“ im Reiter Klassenarbeiten → Druckdialog mit Vorschau (QPrintPreviewDialog oder eigene Vorschau
   über QPdfWriter → Bild), Auswahl Ausgabe + Optionen.

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
| Repo | eigenes privates Repo `SebastianMG80/notenverwaltung`; im Repo `lernspiele-it` per `.gitignore` ausgeschlossen |

## Fallstricke
- Qt übernimmt Enter im Zelleneditor verzögert (QueuedConnection): in Tests `QApplication.processEvents()` nach Enter; geschlossene Editoren existieren bis zum nächsten Event-Durchlauf weiter (sichtbaren nehmen).
- `segno` (QR) lädt über `xml.sax.saxutils` das ungenutzte `urllib.request` – deshalb erst in `notfallblatt._qr` importieren.
- UI-Tests: `schnelle_kdf`-Fixture benutzen (Argon2id sonst 0,3 s pro Öffnen); Meldungsfenster sind in `conftest.py` stummgeschaltet, `frage` per monkeypatch im jeweiligen Modul setzen.
- Netzwerk-Laufzeittest muss in eigenem Prozess laufen: pytest selbst lädt `ssl`.
- Tests setzen `QSettings.setPath` auf einen Wegwerf-Ordner – nie die echten Einstellungen benutzen.
