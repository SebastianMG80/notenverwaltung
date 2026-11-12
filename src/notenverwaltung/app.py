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
    if app.property("systemschrift") is None:
        app.setProperty("systemschrift", app.font().toString())
    schrift = ui_schrift()
    if schrift:
        from PySide6.QtGui import QFont

        f = QFont()
        if f.fromString(schrift):
            app.setFont(f)
    return app


def main(argv: list[str] | None = None) -> int:
    argumente = sys.argv if argv is None else argv
    if "--selbsttest" in argumente:
        from notenverwaltung.selbsttest import selbsttest

        return selbsttest()
    app = erzeuge_anwendung(argv)
    fenster = Hauptfenster()
    fenster.show()
    QTimer.singleShot(0, fenster.zeige_startdialog)  # Lastenheft: beim Start Auswahl der Datenbank
    return app.exec()
