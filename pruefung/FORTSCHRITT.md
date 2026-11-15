# Fortschritt der Prüfung (Bugs und Sicherheit)

Auftrag (15.11.2026): Notenverwaltung in der Linux- und Windows-Fassung – auch den Stand auf GitHub – auf Bugs
und vor allem auf Sicherheitslücken prüfen. Ergebnis: `pruefung/BERICHT.md`. „weiter“ setzt hier fort.

## Antworten von Sebastian (15.11.2026, Anfangsrunde)
- Eindeutige Fehler und Lücken **gleich beheben** (lokal, mit Test). Strittiges und alles, was das Dateiformat
  ändert, nur berichten.
- GitHub-Einstellungen: **lesen und anpassen** (eindeutig sinnvolle Sicherheitseinstellungen direkt ändern, im
  Bericht aufführen).
- Herunterladen erlaubt: Release-Zips v1.0.0, `pip-audit` (Wegwerf-Umgebung), CI-Protokolle – alles in einen
  Wegwerf-Ordner außerhalb des Projekts.
- **Nichts committen**, nichts pushen, kein Tag, kein Release.

## Regeln für diese Prüfung
- Getestet wird nur an einer Kopie mit erfundenen Daten (Wegwerf-Ordner). Echte `.nvdb`-Dateien, die echte
  `Notenverwaltung.ini` und der zweite Klon `~/Notenverwaltung` werden nicht angefasst.
- Notenlogik und Dateiformat werden nicht verändert.

## Schritte
- [x] 1 Gedächtnis, Projektregeln, Ordner gesichtet (Stand: `main` = `origin/main` = dd21d4c, Version 1.0.0)
- [x] 2 Rückfragen gestellt und beantwortet
- [x] 3 Quelltext gelesen (Speicherung, Sperre, Import, Notenlogik vollständig; Oberfläche und Ausgaben nach
      riskanten Mustern durchsucht)
- [x] 4 GitHub: Einstellungen, Workflow, Läufe, Releases, Versionsgeschichte geprüft (nur gelesen)
- [x] 5 Tests an einer Kopie (284 bestanden, 1 übersprungen), Funde nachgestellt, `pip-audit` ohne Befund,
      Release-Zips v1.0.0 geprüft, Linux-Fassung: Selbsttest bestanden
- [x] 6 Korrekturen eingebaut: `speicher/tresor.py`, `speicher/datenbank.py`,
      `ui/hauptfenster.py`, `ui/startdialog.py`, `ui/stammdaten_dialoge.py`, `ausgabe/notfallblatt.py`,
      `modell/tabellen.py`, `modell/importieren.py`, `modell/ki.py`, `.github/workflows/build.yml`;
      neue Tests `tests/test_pruefung.py` (34, bestanden), `tests/test_sperre.py` auf neue Uhr umgestellt
- [x] 6b Gegenprobe: neue Tests gegen den alten Stand – 28 scheitern wie erwartet, 5 bestehen (Kontrolltests).
      **Nur mit Speichergrenze (`ulimit -v 3000000`) und `-k "not riesige"` starten**: Der Fall „riesige-spalte“
      füllt am alten Stand den Arbeitsspeicher (hat am 15.11. den Rechner in Speichernot gebracht).
- [x] 6c ganze Testreihe am neuen Stand: 318 bestanden, 1 übersprungen; Selbsttest aus dem Quelltext bestanden
- [x] 6d GitHub: Dependabot-Warnungen eingeschaltet (0 Warnungen), erlaubte Actions auf GitHub-eigene beschränkt
- [x] 7 `BERICHT.md` geschrieben, Prüfwerkzeuge in `pruefung/werkzeuge/`

## Stand
**Die Prüfung ist abgeschlossen.** Auf Sebastians Wunsch (15.11.2026) lokal committet – ein Commit auf `main`,
**nicht gepusht**, kein Tag. Bei „weiter“: Sebastians Entscheidungen zu
Abschnitt 6 des Berichts abwarten bzw. umsetzen (O1 Hauptschlüssel erneuern, O2 Notenschlüssel, O4–O12), danach
auf seinen Wunsch committen und pushen – dann laufen die neuen Tests erstmals unter Windows.

## Wegwerf-Ordner (kann fehlen, dann neu anlegen)
Wegwerf-Ordner der Claude-Sitzung (außerhalb des Projekts, wird beim Neustart geleert):
`kopie` (alter Stand), `kopie2` (neuer Stand), `probe` (Prüfskripte), `release`, `logs`, `audit`.

## Ergebnisse der Nachstellung (Kurzform, Einzelheiten im Bericht)
- Sperre per Dateitausch umgehbar: bestätigt, behoben.
- Klartext im Temp-Ordner (`/var/tmp/etilqs_*`) nach ~17 Änderungen einer Arbeit mit großer Musterlösung:
  bestätigt, behoben (`PRAGMA temp_store = MEMORY`).
- Dateirechte 0664 für Datenbank, Schlüsseldatei, Notfallblatt-PDF: bestätigt, behoben (0600).
- Namen mit `[ ]`: Sicherungen nicht gefunden, nicht rotiert, nach Passwortwechsel nicht neu verpackt:
  bestätigt, behoben.
- Veränderter Kopf: AttributeError/ValueError statt „beschädigt“: bestätigt, behoben.
- Import: Hänger bei Spalte „ZZZZZZZ1“, mehrere unbehandelte Ausnahmen, Zip-Bombe: bestätigt, behoben.
- Speichern ist atomar (Abbruch lässt das Original stehen): bestätigt, kein Fund.
- GitHub: privat, keine Secrets, Standardrecht des Tokens „read“, Geschichte ohne Zugangsdaten oder echte
  Namen; Workflow gab allen Jobs Schreibrecht (behoben, lokal); Actions nur per Tag gepinnt (offen).
- Abhängigkeiten: `pip-audit` ohne Befund. Release-Zips: keine fremden Dateien; enthalten ungenutzte
  Netzwerk-Bausteine von Qt/Python (offen).
