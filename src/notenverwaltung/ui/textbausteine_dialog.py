"""Textbausteine verwalten: Kürzel, Text mit Platzhaltern, optional nur für ein Fach."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.rueckmeldung import PLATZHALTER, TextbausteinFehler, Textbausteine
from notenverwaltung.ui.bausteine import Hinweis


class TextbausteineDialog(QDialog):
    def __init__(self, tb: Textbausteine, fach: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tb, self.fach = tb, fach
        self.setWindowTitle("Textbausteine")
        self.resize(860, 520)
        self.tabelle = QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["Kürzel", "Text", "Nur für Fach"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.setWordWrap(True)
        k = self.tabelle.horizontalHeader()
        k.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        k.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        k.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for b in tb.alle():
            self._zeile(b.id, b.kuerzel, b.text, b.fach)
        self.tabelle.resizeRowsToContents()

        neu = QPushButton("Neuer Baustein")
        neu.clicked.connect(lambda: self._zeile(None, "", "", ""))
        weg = QPushButton("Löschen")
        weg.clicked.connect(self._loeschen)
        hoch, runter = QPushButton("▲"), QPushButton("▼")
        hoch.setToolTip("Nach oben")
        runter.setToolTip("Nach unten")
        hoch.clicked.connect(lambda: self._verschieben(-1))
        runter.clicked.connect(lambda: self._verschieben(1))
        reihe = QHBoxLayout()
        for w in (neu, weg, hoch, runter):
            reihe.addWidget(w)
        reihe.addStretch(1)
        platz = ", ".join("{" + p + "}" for p in PLATZHALTER)
        hilfe = QLabel(f"Platzhalter: {platz}.<br>{{Stärken}} und {{Übungsbedarf}} nennen die Themen der Aufgaben "
                       "mit vielen bzw. wenigen Punkten (Grenzen unter Bearbeiten → Einstellungen). "
                       "Ein Kürzel ohne Leerzeichen; „Nur für Fach“ leer = alle Fächer.", objectName="leise")
        hilfe.setWordWrap(True)
        self.meldung = Hinweis()
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle, 1)
        lay.addLayout(reihe)
        lay.addWidget(hilfe)
        lay.addWidget(self.meldung)
        lay.addWidget(knoepfe)

    def _zeile(self, bid, kuerzel: str, text: str, fach: str) -> None:
        r = self.tabelle.rowCount()
        self.tabelle.insertRow(r)
        k = QTableWidgetItem(kuerzel)
        k.setData(Qt.ItemDataRole.UserRole, bid)
        self.tabelle.setItem(r, 0, k)
        self.tabelle.setItem(r, 1, QTableWidgetItem(text))
        self.tabelle.setItem(r, 2, QTableWidgetItem(fach))
        if bid is None:
            self.tabelle.setCurrentCell(r, 1)
            self.tabelle.editItem(self.tabelle.item(r, 1))

    def _loeschen(self) -> None:
        for r in sorted({i.row() for i in self.tabelle.selectedIndexes()}, reverse=True):
            self.tabelle.removeRow(r)

    def _verschieben(self, schritt: int) -> None:
        r = self.tabelle.currentRow()
        ziel = r + schritt
        if r < 0 or not 0 <= ziel < self.tabelle.rowCount():
            return
        for c in range(3):
            a, b = self.tabelle.takeItem(r, c), self.tabelle.takeItem(ziel, c)
            self.tabelle.setItem(r, c, b)
            self.tabelle.setItem(ziel, c, a)
        self.tabelle.setCurrentCell(ziel, self.tabelle.currentColumn())

    def liste(self) -> list[tuple[int | None, str, str, str]]:
        ergebnis = []
        for r in range(self.tabelle.rowCount()):
            werte = [(self.tabelle.item(r, c).text() if self.tabelle.item(r, c) else "") for c in range(3)]
            bid = self.tabelle.item(r, 0).data(Qt.ItemDataRole.UserRole) if self.tabelle.item(r, 0) else None
            ergebnis.append((bid, *werte))
        return ergebnis

    def accept(self) -> None:
        try:
            self.tb.setze(self.liste())
        except TextbausteinFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        super().accept()
