"""Dialoge unter Datei → Sicherheit."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.ui.bausteine import Hinweis, Passwortfeld, fehler
from notenverwaltung.ui.neue_datenbank import passwort_bewertung


class PasswortAendernDialog(QDialog):
    def __init__(self, db: Datenbank, parent: QWidget | None = None, weitere_ordner: list | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.weitere_ordner = weitere_ordner or []
        self.ergebnis = None          # Passwortwechsel nach Erfolg
        self.setWindowTitle("Passwort ändern")
        self.setMinimumWidth(480)
        self.alt = Passwortfeld("Bisheriges Passwort")
        self.pw1 = Passwortfeld("Neues Passwort")
        self.pw2 = Passwortfeld("Neues Passwort wiederholen")
        self.bewertung = Hinweis()
        self.meldung = Hinweis()
        form = QFormLayout()
        form.addRow("Bisheriges Passwort:", self.alt)
        form.addRow("Neues Passwort:", self.pw1)
        form.addRow("", self.bewertung)
        form.addRow("Wiederholung:", self.pw2)
        hinweis = QLabel("Die Datenbank bekommt dabei einen neuen inneren Schlüssel. Danach erscheint ein neues "
                         "Notfallblatt – der bisherige Wiederherstellungscode wird ungültig, eine Schlüsseldatei "
                         "muss neu angelegt werden. Alle Sicherungen (auch auf dem zweiten Sicherungsort) werden "
                         "umgestellt.", objectName="leise")
        hinweis.setWordWrap(True)
        self.knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Passwort ändern")
        self.knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._aendern)
        self.knoepfe.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(hinweis)
        lay.addWidget(self.meldung)
        lay.addWidget(self.knoepfe)
        for w in (self.alt, self.pw1, self.pw2):
            w.textChanged.connect(self._pruefen)
        self._pruefen()

    def _pruefen(self) -> None:
        ok, text, art = passwort_bewertung(self.pw1.text())
        self.bewertung.setze(text, art)
        if self.pw2.text() and self.pw1.text() != self.pw2.text():
            self.meldung.setze("Die neuen Passwörter stimmen nicht überein.", "fehler")
        else:
            self.meldung.setze("")
        bereit = bool(self.alt.text()) and ok and self.pw1.text() == self.pw2.text()
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bereit)

    def _aendern(self) -> None:
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            richtig = self.db.pruefe_passwort(self.alt.text())
        finally:
            QGuiApplication.restoreOverrideCursor()
        if not richtig:
            self.meldung.setze("Das bisherige Passwort ist falsch.", "fehler")
            self.alt.selectAll()
            self.alt.setFocus()
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.ergebnis = self.db.aendere_passwort(self.pw1.text(), self.weitere_ordner)
        except (OSError, ValueError) as e:
            QGuiApplication.restoreOverrideCursor()
            fehler(self, "Passwort ändern", f"Das neue Passwort konnte nicht gespeichert werden:\n{e}")
            return
        QGuiApplication.restoreOverrideCursor()
        for w in (self.alt, self.pw1, self.pw2):
            w.clear()
        self.accept()
