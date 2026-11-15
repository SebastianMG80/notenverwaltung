"""Automatisch sperren: Nach einer Weile ohne Eingabe deckt ein Schirm alle Fenster ab; weiter geht es nur mit
dem Passwort der Datenbank.

Die Daten bleiben geöffnet, nichts geht verloren – auch nicht ein halb ausgefüllter Dialog. Vor dem Sperren wird
gespeichert. Solange gesperrt ist, lässt der Ereignisfilter des Hauptfensters (siehe `Hauptfenster`) Tasten und
Mausklicks nur zum Entsperr-Feld durch; Tastenkürzel greifen nicht.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.ui.bausteine import Hinweis, Passwortfeld


class Schirm(QFrame):
    """Undurchsichtige Abdeckung über einem Fenster; auf dem obersten Fenster mit Passwortfeld."""

    def __init__(self, fenster: QWidget, mit_eingabe: bool, grund: str) -> None:
        super().__init__(fenster)
        self.setObjectName("sperrschirm")
        self.setAutoFillBackground(True)
        self.setStyleSheet("#sperrschirm { background: palette(window); }")
        self.passwort: Passwortfeld | None = None
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        titel = QLabel("🔒  Notenverwaltung gesperrt" if mit_eingabe else "🔒  Gesperrt")
        titel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titel.setStyleSheet("font-size: 20px; font-weight: bold;")
        lay.addWidget(titel)
        if mit_eingabe:
            text = QLabel(f"{grund}\nDeine Eingaben sind gespeichert. Zum Weiterarbeiten das Passwort der Datenbank "
                          "eingeben.")
            text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            text.setWordWrap(True)
            lay.addWidget(text)
            self.passwort = Passwortfeld("Passwort")
            self.passwort.setMaximumWidth(340)
            self.knopf = QPushButton("Entsperren", objectName="primaer")
            self.meldung = Hinweis()
            self.meldung.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for w in (self.passwort, self.knopf):
                lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(self.meldung)
        lay.addStretch(2)
        self.setGeometry(fenster.rect())
        fenster.installEventFilter(self)
        self.show()
        self.raise_()

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        if objekt is self.parentWidget() and ereignis.type() == QEvent.Type.Resize:
            self.setGeometry(objekt.rect())
            self.raise_()
        return False


class Sperre(QObject):
    """Verwaltet die Schirme. `pruefe(passwort)` entscheidet, ob entsperrt wird."""

    entsperrt = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.schirme: list[Schirm] = []
        self.eingabe: Schirm | None = None
        self.pruefe = lambda passwort: False

    @property
    def aktiv(self) -> bool:
        return bool(self.schirme)

    def sperren(self, hauptfenster: QWidget, grund: str) -> None:
        if self.aktiv:
            return
        popup = QApplication.activePopupWidget()
        while popup is not None:                 # offene Menüs schließen
            popup.close()
            nxt = QApplication.activePopupWidget()
            popup = None if nxt is popup else nxt
        modal = [w for w in QApplication.topLevelWidgets()
                 if w.isVisible() and isinstance(w, QDialog) and w.isModal()]
        oben = QApplication.activeModalWidget() or (modal[-1] if modal else hauptfenster)
        for w in QApplication.topLevelWidgets():
            if (w.isVisible() and not isinstance(w, QMenu)
                    and w.windowType() not in (Qt.WindowType.ToolTip, Qt.WindowType.Popup)):
                s = Schirm(w, w is oben, grund)
                self.schirme.append(s)
                if w is oben:
                    self.eingabe = s
        if self.eingabe is None:                 # z. B. Hauptfenster gerade unsichtbar
            self.eingabe = Schirm(hauptfenster, True, grund)
            self.schirme.append(self.eingabe)
        self.eingabe.knopf.clicked.connect(self._versuchen)
        self.eingabe.passwort.returnPressed.connect(self._versuchen)
        self.eingabe.passwort.setFocus()

    def erlaubt(self, objekt) -> bool:
        """Darf dieses Widget während der Sperre Eingaben bekommen?"""
        return self.eingabe is not None and isinstance(objekt, QWidget) and (
            objekt is self.eingabe or self.eingabe.isAncestorOf(objekt))

    def _versuchen(self) -> None:
        if self.eingabe is None:
            return
        pw = self.eingabe.passwort.text()
        if not pw:
            self.eingabe.meldung.setze("Bitte das Passwort eingeben.", "warnung")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            richtig = self.pruefe(pw)
        finally:
            QApplication.restoreOverrideCursor()
        if not richtig:
            self.eingabe.passwort.clear()
            self.eingabe.meldung.setze("Das Passwort stimmt nicht.", "fehler")
            return
        self.aufheben()
        self.entsperrt.emit()

    def aufheben(self) -> None:
        for s in self.schirme:
            try:
                s.parentWidget().removeEventFilter(s)
                s.deleteLater()
                s.hide()
            except RuntimeError:                 # Fenster inzwischen geschlossen
                pass
        self.schirme.clear()
        self.eingabe = None
