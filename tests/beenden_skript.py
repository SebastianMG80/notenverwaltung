"""Wird von test_beenden.py in einem eigenen Prozess gestartet: Programm öffnen, echte Dialoge zeigen, Hilfe offen
lassen, Hauptfenster schließen und so enden wie `notenverwaltung.app.main`. Ausgabe „OK …“ und Code 0 – oder ein
Absturz beim Beenden (vor 1.1.1: SIGABRT/SIGSEGV in PySide::destroyQCoreApplication)."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QSettings, QTimer  # noqa: E402

QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

from notenverwaltung.app import abbauen, erzeuge_anwendung  # noqa: E402
from notenverwaltung.speicher.datenbank import Datenbank  # noqa: E402
from notenverwaltung.ui.hauptfenster import Hauptfenster  # noqa: E402

QUELLE = Path(__file__).resolve().parent / "daten" / "version_0_9_0.nvdb"


def main() -> int:
    from PySide6.QtWidgets import QApplication

    app = erzeuge_anwendung([])
    fenster = Hauptfenster()
    fenster.show()

    def zu_bald():
        w = QApplication.activeModalWidget()
        if w is not None:
            w.reject()
        else:
            QTimer.singleShot(30, zu_bald)

    def los():
        ziel = Path(tempfile.mkdtemp()) / QUELLE.name
        shutil.copy2(QUELLE, ziel)
        fenster.setze_datenbank(Datenbank.oeffnen(ziel, "passwort", "Versionsprüfung 2026 – Ärger vermeiden"))
        g = fenster.sd.lerngruppen(fenster.jahr.id)[0]
        fenster.oeffne_gruppe(g.id, "arbeiten")
        for oeffnen in (fenster.seite_gruppe.arbeiten.drucken, fenster.seite_gruppe.muendlich.drucken,
                        fenster.einstellungen_zeigen, fenster.nachschreibliste):
            QTimer.singleShot(50, zu_bald)
            oeffnen()                                        # echtes exec(), per Timer geschlossen
        from notenverwaltung.hilfe.fenster import zeige_hilfe

        zeige_hilfe("start")                                 # Hilfe bleibt offen
        QTimer.singleShot(50, fenster.close)

    QTimer.singleShot(0, los)
    code = app.exec()
    del fenster
    abbauen(app)

    import shiboken6
    from PySide6.QtCore import QObject

    rest = [type(w).__name__ for w in shiboken6.getAllValidWrappers()
            if isinstance(w, QObject) and shiboken6.ownedByPython(w) and w.parent() is not None]
    if rest or QApplication.topLevelWidgets():
        print("REST", rest, [type(w).__name__ for w in QApplication.topLevelWidgets()])
        return 3
    print("OK", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
