# Notenverwaltung

Offline-Notenverwaltung für Lehrer:innen: Klassenarbeiten korrigieren, Noten verwalten, Notenvorschläge, Ausdrucke.
Läuft unter Linux (KDE) und Windows mit identischem Dateiformat. Das Programm sendet von sich aus nie Daten nach außen.

- **Handbuch:** [handbuch/HANDBUCH.md](handbuch/HANDBUCH.md), als PDF [handbuch/Handbuch.pdf](handbuch/Handbuch.pdf) (liegt auch jedem Release bei)
- Kurzanleitung: [ANLEITUNG.md](ANLEITUNG.md)
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

Handbuch neu bebildern und setzen (nach Programmänderungen):

```bash
~/.venvs/notenverwaltung/bin/python werkzeuge/handbuch_bilder.py
~/.venvs/notenverwaltung/bin/python werkzeuge/handbuch_pdf.py
```

Tests:

```bash
~/.venvs/notenverwaltung/bin/python -m pytest -q
```

## Lizenz

Copyright © 2026 SebastianMG80. Die Notenverwaltung ist freie Software unter der
[GNU General Public License, Version 3 oder später](LICENSE) – ohne jede Gewährleistung.
Verwendete Software anderer und ihre Lizenzen: [lizenzen/README.md](lizenzen/README.md).

Fehler gefunden oder eine Idee? Gern als [Issue](https://github.com/SebastianMG80/notenverwaltung/issues) melden –
bitte **ohne echte Schülerdaten** (keine Namen, keine Datenbankdateien, keine Bildschirmfotos mit Noten).
