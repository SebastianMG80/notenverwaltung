"""Eine unter Linux erzeugte Datenbank muss auf jedem System (auch Windows) identisch lesbar sein."""

import importlib.util
import shutil
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEI = WURZEL / "tests" / "daten" / "kompatibilitaet_linux.nvdb"


def _werkzeug():
    spec = importlib.util.spec_from_file_location("kompatibilitaet", WURZEL / "werkzeuge" / "kompatibilitaet.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_linux_datei_ist_lesbar(app, tmp_path):
    kopie = tmp_path / "k.nvdb"
    shutil.copy(DATEI, kopie)  # Original nicht verändern (Sperrdatei, Migrationen)
    assert _werkzeug().pruefe(kopie) == "linux"


def test_selbst_erzeugt_und_geprueft(app, tmp_path):
    w = _werkzeug()
    w.erzeuge(tmp_path / "neu.nvdb")
    assert w.pruefe(tmp_path / "neu.nvdb") == sys.platform
