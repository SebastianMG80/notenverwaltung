"""Programmstart."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from notenverwaltung import APP_NAME, ORG_NAME, __version__
from notenverwaltung.einstellungen import design_name
from notenverwaltung.ui.design import wende_design_an
from notenverwaltung.ui.hauptfenster import Hauptfenster


def erzeuge_anwendung(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("notenverwaltung")
    wende_design_an(app, design_name())
    return app


def main(argv: list[str] | None = None) -> int:
    app = erzeuge_anwendung(argv)
    fenster = Hauptfenster()
    fenster.show()
    QTimer.singleShot(0, fenster.zeige_startdialog)  # Lastenheft: beim Start Auswahl der Datenbank
    return app.exec()
