# Fortschritt Notenverwaltung

## Auftrag
Sebastian: Lastenheft in `LASTENHEFT.md` prüfen, Plan vorlegen (`PLAN.md`), am 12.11.2026 mit „Ja, starten“ freigegeben.
12.11.2026 abends: „mach einfach weiter, bis du wieder von mir hörst“ – Etappen selbstständig abarbeiten, je Etappe committen und pushen.
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
Etappe 1 – Kern ist fertig (`speicher/krypto.py`, `tresor.py`, `datenbank.py`, `schema.py`, Tests `tests/test_speicher.py`).
Jetzt: Dialoge in `ui/`:
1. `ui/startdialog.py`: zuletzt geöffnete Datenbanken (QSettings `datenbank/zuletzt`), Passwortfeld, „Andere öffnen …“, „Neue Datenbank …“,
   „Passwort vergessen?“ → Wiederherstellungscode oder Schlüsseldatei, danach neues Passwort erzwingen. GesperrtFehler → Nachfrage.
2. `ui/neue_datenbank.py`: QWizard – Datenschutzhinweis (Pflicht-Haken), Speicherort (Cloud-Warnung), Passwort ×2 (min. 10 Zeichen),
   Notfallblatt (Code anzeigen, drucken/PDF, Pflicht-Haken „gesichert“).
3. `ausgabe/notfallblatt.py`: PDF/Drucker mit QPainter, QR-Code via segno-Matrix.
4. Hauptfenster: Datei-Menü (Neu, Öffnen, Speichern Strg+S, Schließen), Sicherheit (Passwort ändern, neues Notfallblatt, Schlüsseldatei),
   Autospeichern alle 2 min, Speichern beim Beenden, Titel mit Datenbankname.

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
| Repo | eigenes privates Repo `SebastianMG80/notenverwaltung`; im Repo `lernspiele-it` per `.gitignore` ausgeschlossen |

## Fallstricke
- Netzwerk-Laufzeittest muss in eigenem Prozess laufen: pytest selbst lädt `ssl`.
- Tests setzen `QSettings.setPath` auf einen Wegwerf-Ordner – nie die echten Einstellungen benutzen.
