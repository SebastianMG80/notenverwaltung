# Fortschritt Notenverwaltung

## Auftrag
Sebastian: Lastenheft in `LASTENHEFT.md` prüfen, Plan vorlegen (`PLAN.md`), am 12.11.2026 mit „Ja, starten“ freigegeben.
Rückfragen sind geklärt (Abschnitt „Klärungen“ im Lastenheft) – ab jetzt selbst entscheiden, Entscheidungen hier festhalten.

## Etappen (Details in PLAN.md)
- [x] 0 Fundament (12.11.2026)
- [ ] 1 Verschlüsselte Datenbank
- [ ] 2 Stammdaten
- [ ] 3 Klassenarbeiten
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
Etappe 1 – verschlüsselte Datenbank. Geplanter Aufbau:
1. `src/notenverwaltung/speicher/datei.py`: Dateiformat v1 = Kopf (Magic `NVDB`, Formatversion, Argon2id-Parameter, Salze,
   zwei verpackte Hauptschlüssel: Passwort + Wiederherstellungscode, optional Schlüsseldatei) + AES-256-GCM-verschlüsselte
   SQLite-Datenbank (im Speicher geöffnet, `sqlite3.serialize/deserialize`). Kopf als zusätzliche authentifizierte Daten (AAD).
2. Sicheres Speichern: Zwischendatei → `os.replace`, Sicherungen mit Rotation, Sperrdatei gegen doppeltes Öffnen.
3. Tests zuerst (falsches Passwort, manipulierte Datei, Wiederherstellung, Passwortwechsel), dann Dialoge
   (Startdialog, Neue Datenbank mit Datenschutzhinweis, Notfallblatt-PDF mit QR-Code via `segno`).

## Entscheidungen
| Punkt | Entscheidung |
|---|---|
| Oberfläche | PySide6-Essentials 6.12 (LGPL), Stil „Fusion“ – sieht unter KDE und Windows gleich aus |
| Python-Umgebung | `~/.venvs/notenverwaltung` (außerhalb des Cloud-Ordners, PySide6 ist groß) |
| Einstellungen | `QSettings` im INI-Format im Benutzerprofil – nur Bedienkomfort, nie Schülerdaten |
| Dateiendung Datenbank | `.nvdb` (in `.gitignore`) |
| Offline-Garantie | `tests/test_offline.py`: statische Prüfung aller Importe + echter Programmstart in frischem Prozess mit gesperrtem Netzwerk |
| Repo | eigenes privates Repo `SebastianMG80/notenverwaltung`; im Repo `lernspiele-it` per `.gitignore` ausgeschlossen |

## Fallstricke
- Netzwerk-Laufzeittest muss in eigenem Prozess laufen: pytest selbst lädt `ssl`.
- Tests setzen `QSettings.setPath` auf einen Wegwerf-Ordner – nie die echten Einstellungen benutzen.
