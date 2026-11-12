"""Schutz vor zu breiten .gitignore-Regeln: Kein Quelltext darf versehentlich ignoriert werden."""

import shutil
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("git") or not (WURZEL / ".git").exists(), reason="kein Git-Arbeitsverzeichnis")
def test_kein_quelltext_ignoriert():
    dateien = [str(p.relative_to(WURZEL)) for ordner in ("src", "tests", "werkzeuge", "packaging")
               for p in (WURZEL / ordner).rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    erg = subprocess.run(["git", "check-ignore", "--no-index", *dateien], cwd=WURZEL, capture_output=True, text=True)
    ignoriert = [z for z in erg.stdout.splitlines() if z.strip()]
    assert not ignoriert, "Von .gitignore ausgeschlossen:\n" + "\n".join(ignoriert)
