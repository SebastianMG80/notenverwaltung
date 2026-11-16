"""Programmstart."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from notenverwaltung import APP_NAME, ORG_NAME, __version__
from notenverwaltung.einstellungen import design_name, ui_schrift
from notenverwaltung.ui.design import wende_design_an
from notenverwaltung.ui.hauptfenster import Hauptfenster


def erzeuge_anwendung(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("notenverwaltung")
    wende_design_an(app, design_name())
    from notenverwaltung.hilfe.fenster import installiere_f1

    installiere_f1(app)
    if app.property("systemschrift") is None:
        app.setProperty("systemschrift", app.font().toString())
    schrift = ui_schrift()
    if schrift:
        from PySide6.QtGui import QFont

        f = QFont()
        if f.fromString(schrift):
            app.setFont(f)
    return app


def abbauen(app: QApplication) -> None:
    """Baut alle Fenster geordnet ab, solange Qt und Python noch vollständig laufen.

    Hintergrund: Ohne diesen Schritt löscht PySide beim Beenden von Python (`destroyQCoreApplication`) alle
    Objekte, die es noch Python zuordnet – auch Widgets, die längst ein Elternobjekt in Qt haben, etwa einen
    Dialog unter einem Reiter. Ist das Elternobjekt in diesem Moment schon gelöscht, wird das Kind ein zweites
    Mal freigegeben: Absturz beim Schließen (SIGABRT/SIGSEGV), je nach Reihenfolge nur manchmal. Löschen wir
    die Fenster vorher selbst, räumt Qt die Kinder normal auf und PySide hat am Ende nichts mehr zu tun.
    """
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent

    for _ in range(3):                 # Fenster, die beim Löschen eines anderen erst sichtbar „frei“ werden
        fenster = QApplication.topLevelWidgets()
        if not fenster:
            break
        for w in fenster:
            w.hide()
            w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main(argv: list[str] | None = None) -> int:
    argumente = sys.argv if argv is None else argv
    if "--selbsttest" in argumente:
        from notenverwaltung.selbsttest import selbsttest

        return selbsttest()
    app = erzeuge_anwendung(argv)
    fenster = Hauptfenster()
    fenster.show()
    QTimer.singleShot(0, fenster.zeige_startdialog)  # Lastenheft: beim Start Auswahl der Datenbank
    code = app.exec()
    del fenster
    abbauen(app)
    return code
