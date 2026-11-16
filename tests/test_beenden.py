"""Beenden ohne Absturz: Seit 1.0 stürzte das Programm beim Schließen manchmal ab (PySide löschte Widgets doppelt).
`abbauen()` räumt jetzt vorher geordnet auf. Der Ablauf läuft in eigenen Prozessen – ein Absturz träfe sonst die
ganze Testsitzung."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SKRIPT = Path(__file__).resolve().parent / "beenden_skript.py"
SRC = Path(__file__).resolve().parent.parent / "src"


@pytest.mark.parametrize("lauf", range(3))
def test_beenden_ohne_absturz(lauf):
    umgebung = dict(os.environ, PYTHONPATH=str(SRC) + os.pathsep + os.environ.get("PYTHONPATH", ""),
                    QT_QPA_PLATFORM="offscreen")
    r = subprocess.run([sys.executable, "-X", "faulthandler", str(SKRIPT)], capture_output=True, text=True,
                       timeout=120, env=umgebung)
    assert r.returncode == 0, f"Code {r.returncode}\n{r.stdout}\n{r.stderr[-3000:]}"
    assert r.stdout.strip().startswith("OK"), r.stdout


def test_hauptfenster_schliesst_hilfe(app, tmp_path, schnelle_kdf):
    from notenverwaltung.hilfe.fenster import zeige_hilfe
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    f = Hauptfenster()
    f.show()
    hilfe = zeige_hilfe("start")
    assert hilfe.isVisible()
    f.close()
    assert not hilfe.isVisible()
