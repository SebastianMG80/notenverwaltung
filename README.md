# Notenverwaltung

Offline-Notenverwaltung für Lehrer:innen: Klassenarbeiten korrigieren, Noten verwalten, Notenvorschläge, Ausdrucke.
Läuft unter Linux (KDE) und Windows mit identischem Dateiformat. Das Programm sendet von sich aus nie Daten nach außen.

- Bedienung: [ANLEITUNG.md](ANLEITUNG.md)
- Anforderungen: [LASTENHEFT.md](LASTENHEFT.md)
- Etappenplan: [PLAN.md](PLAN.md)
- Stand: [FORTSCHRITT.md](FORTSCHRITT.md)

## Entwicklung (Linux)

Die Python-Umgebung liegt bewusst außerhalb des Cloud-Ordners:

```bash
python3 -m venv ~/.venvs/notenverwaltung
~/.venvs/notenverwaltung/bin/pip install -r requirements-dev.txt
```

Starten:

```bash
./start.sh
```

Tests:

```bash
~/.venvs/notenverwaltung/bin/python -m pytest -q
```
