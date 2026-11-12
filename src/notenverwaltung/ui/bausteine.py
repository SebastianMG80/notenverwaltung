"""Kleine wiederverwendbare Bausteine für Dialoge."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMessageBox, QWidget

from notenverwaltung.ui.design import farben


def aktuelle_farben():
    app = QApplication.instance()
    return farben(app.property("design") if app else "dunkel")


class Passwortfeld(QLineEdit):
    """Passwortfeld mit „Anzeigen“-Schalter."""

    def __init__(self, platzhalter: str = "Passwort", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setPlaceholderText(platzhalter)
        self._zeigen = QAction("Anzeigen", self)
        self._zeigen.setCheckable(True)
        self._zeigen.setIcon(QIcon.fromTheme("view-visible"))
        self._zeigen.setToolTip("Passwort anzeigen")
        self._zeigen.toggled.connect(self._umschalten)
        self.addAction(self._zeigen, QLineEdit.ActionPosition.TrailingPosition)

    def _umschalten(self, an: bool) -> None:
        self.setEchoMode(QLineEdit.EchoMode.Normal if an else QLineEdit.EchoMode.Password)


class Hinweis(QLabel):
    """Farbiger Hinweistext: art = "info", "warnung" oder "fehler"."""

    def __init__(self, text: str = "", art: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setze(text, art)

    def setze(self, text: str, art: str = "info") -> None:
        f = aktuelle_farben()
        farbe = {"info": f.text_leise, "warnung": f.warnung, "fehler": f.fehler, "ok": f.akzent}[art]
        self.setStyleSheet(f"color: {farbe};")
        self.setText(text)
        self.setVisible(bool(text))


def frage(parent: QWidget, titel: str, text: str, ja: str = "Ja", nein: str = "Abbrechen",
          warnung: bool = False) -> bool:
    box = QMessageBox(QMessageBox.Icon.Warning if warnung else QMessageBox.Icon.Question, titel, text,
                      parent=parent)
    ja_knopf = box.addButton(ja, QMessageBox.ButtonRole.AcceptRole)
    nein_knopf = box.addButton(nein, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(nein_knopf)
    box.exec()
    return box.clickedButton() is ja_knopf


def fehler(parent: QWidget, titel: str, text: str) -> None:
    QMessageBox.critical(parent, titel, text)


def info(parent: QWidget, titel: str, text: str) -> None:
    QMessageBox.information(parent, titel, text)
