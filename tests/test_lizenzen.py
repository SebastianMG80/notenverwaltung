"""Lizenz: GPL-3.0 für das Programm, Texte aller mitgelieferten Bestandteile im Repo und im Paket."""

import re
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent


def test_gpl_und_dateien_der_uebersicht():
    lizenz = (WURZEL / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in lizenz and "Version 3, 29 June 2007" in lizenz
    uebersicht = (WURZEL / "lizenzen" / "README.md").read_text(encoding="utf-8")
    for datei in set(re.findall(r"`([\w.\-]+\.txt)`", uebersicht)) - {"Python-LICENSE.txt"}:
        assert (WURZEL / "lizenzen" / datei).is_file(), datei
    for datei in (WURZEL / "lizenzen").glob("*.txt"):
        assert datei.name in uebersicht or datei.name.startswith("cryptography-"), f"{datei.name} fehlt in der Übersicht"
    import tomllib

    assert tomllib.loads((WURZEL / "pyproject.toml").read_text())["project"]["license"] == "GPL-3.0-or-later"


def test_lizenzen_sammeln(tmp_path):
    paket = tmp_path / "Notenverwaltung"
    (paket / "_internal").mkdir(parents=True)
    r = subprocess.run([sys.executable, str(WURZEL / "werkzeuge" / "lizenzen_sammeln.py"), str(paket)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert (paket / "LICENSE.txt").read_text(encoding="utf-8").startswith(
        (WURZEL / "LICENSE").read_text(encoding="utf-8")[:200])
    assert (paket / "lizenzen" / "LGPL-3.0.txt").is_file() and (paket / "lizenzen" / "README.md").is_file()
    assert (paket / "lizenzen" / "Python-LICENSE.txt").is_file()
    r2 = subprocess.run([sys.executable, str(WURZEL / "werkzeuge" / "lizenzen_sammeln.py"), str(paket)],
                        capture_output=True, text=True, timeout=120)
    assert r2.returncode == 0                                     # zweimal ausführen geht
