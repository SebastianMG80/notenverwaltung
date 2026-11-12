"""Das Programm darf von sich aus nie etwas nach außen senden.

Prüfung 1 (statisch): Kein Quelltext importiert Netzwerk-Module.
Prüfung 2 (Laufzeit): Ein echter Programmstart in einem frischen Prozess lädt keine
                      Netzwerk-Module und versucht keinen Verbindungsaufbau.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

QUELLEN = Path(__file__).resolve().parent.parent / "src" / "notenverwaltung"

VERBOTEN = {
    "socket", "ssl", "http", "urllib", "ftplib", "smtplib", "poplib", "imaplib",
    "telnetlib", "xmlrpc", "webbrowser", "requests", "httpx", "aiohttp",
    "websocket", "websockets", "urllib3",
}
VERBOTEN_QT = ("QtNetwork", "QtWebEngine", "QtWebSockets", "QtWebChannel", "QtWebView", "QtHttpServer")


def _importe(datei: Path) -> list[str]:
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    namen = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            namen += [a.name for a in knoten.names]
        elif isinstance(knoten, ast.ImportFrom) and knoten.module:
            namen.append(knoten.module)
            namen += [f"{knoten.module}.{a.name}" for a in knoten.names]
    return namen


def test_keine_netzwerk_importe_im_quelltext():
    verstoesse = []
    dateien = sorted(QUELLEN.rglob("*.py"))
    assert dateien, "Keine Quelltexte gefunden"
    for datei in dateien:
        for name in _importe(datei):
            teile = name.split(".")
            if teile[0] in VERBOTEN or any(t.startswith(VERBOTEN_QT) for t in teile):
                verstoesse.append(f"{datei.relative_to(QUELLEN)}: {name}")
        quelltext = datei.read_text(encoding="utf-8")
        if "__import__" in quelltext or "importlib" in quelltext:
            verstoesse.append(f"{datei.relative_to(QUELLEN)}: dynamischer Import")
    assert not verstoesse, "Netzwerkzugriff im Code:\n" + "\n".join(verstoesse)


PRUEFPROGRAMM = r"""
import os, socket, sys
versuche = []
def blockiert(self, *a, **k):
    versuche.append(a)
    raise OSError("Netzwerk verboten")
for name in ("connect", "connect_ex", "sendto", "sendmsg"):
    setattr(socket.socket, name, blockiert)

from PySide6.QtCore import QSettings, QTimer
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, sys.argv[1])
from notenverwaltung.app import erzeuge_anwendung
from notenverwaltung.ui.hauptfenster import Hauptfenster
app = erzeuge_anwendung([])
fenster = Hauptfenster()
fenster.show()
QTimer.singleShot(500, app.quit)
app.exec()
fenster.close()

netz = sorted(m for m in sys.modules
              if m.split(".")[0] in {"ssl", "http", "urllib3", "requests", "httpx", "aiohttp", "webbrowser"}
              or any(q in m for q in VERBOTEN_QT))
print("VERSUCHE", len(versuche))
print("MODULE", ",".join(netz))
"""


def test_start_ohne_netzwerk(tmp_path):
    """Läuft in einem frischen Prozess, damit Module der Test-Umgebung nicht mitzählen."""
    programm = f"VERBOTEN_QT = {VERBOTEN_QT!r}\n" + PRUEFPROGRAMM
    umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(QUELLEN.parent))
    erg = subprocess.run(
        [sys.executable, "-c", programm, str(tmp_path / "config")],
        capture_output=True, text=True, env=umgebung, timeout=60,
    )
    assert erg.returncode == 0, erg.stderr
    zeilen = dict(z.split(" ", 1) if " " in z else (z, "") for z in erg.stdout.strip().splitlines())
    assert zeilen.get("VERSUCHE") == "0", erg.stdout
    assert zeilen.get("MODULE", "") == "", f"Netzwerk-Module geladen: {zeilen.get('MODULE')}"


NOTFALL_PROGRAMM = r"""
import socket, sys
versuche = []
def blockiert(self, *a, **k):
    versuche.append(a)
    raise OSError("Netzwerk verboten")
for name in ("connect", "connect_ex", "sendto", "sendmsg"):
    setattr(socket.socket, name, blockiert)
from PySide6.QtWidgets import QApplication
app = QApplication([])
from notenverwaltung.ausgabe import notfallblatt
notfallblatt.als_pdf(sys.argv[1], "Test", "ABCD-EFGH-JKMN-PQRS-TVWX-YZ23")
print("VERSUCHE", len(versuche))
"""


def test_notfallblatt_ohne_netzwerk(tmp_path):
    """segno (QR-Code) lädt urllib mit – es darf aber keinen Verbindungsversuch geben."""
    umgebung = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(QUELLEN.parent))
    erg = subprocess.run([sys.executable, "-c", NOTFALL_PROGRAMM, str(tmp_path / "n.pdf")],
                         capture_output=True, text=True, env=umgebung, timeout=60)
    assert erg.returncode == 0, erg.stderr
    assert "VERSUCHE 0" in erg.stdout
    assert (tmp_path / "n.pdf").read_bytes()[:4] == b"%PDF"
