# Notenverwaltung – Arbeitsregeln

- Anforderungen: [LASTENHEFT.md](LASTENHEFT.md) (inkl. Abschnitt „Klärungen“). Reihenfolge und Stand: [PLAN.md](PLAN.md), `FORTSCHRITT.md`.
- Sprache in Oberfläche, Ausgaben und Doku: Deutsch, gegendert mit Doppelpunkt (Schüler:innen, Lehrer:innen).
- Das Programm sendet nie etwas nach außen: keine Netzwerk-Module, keine Update-Prüfung, keine Telemetrie. Ein Test prüft das.
- Echte Schülerdaten und Datenbankdateien kommen nie ins Repo. Testdaten nur mit erfundenen Namen.
- Dateiformat versioniert. Jede Änderung braucht eine Migration und muss auf Linux und Windows identisch lesbar bleiben.
- Notenlogik nur mit Tests ändern (Notenschlüssel, Tendenz ±0,3, Gewichtungen, Jahrgang-10-Sonderfall).
- Unterbrechungssicher arbeiten: nach jedem Teilschritt `FORTSCHRITT.md` aktualisieren. „weiter“ setzt dort fort.
- Python-Umgebung: `~/.venvs/notenverwaltung`. Tests: `~/.venvs/notenverwaltung/bin/python -m pytest -q`. Start: `./start.sh`.
- `Punkteliste.ods` ist die Vorlage für Punkteliste und Notenabschnitte (Layout und Notenschlüssel).
