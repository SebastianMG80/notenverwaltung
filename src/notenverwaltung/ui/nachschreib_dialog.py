"""Nachschreibliste: alle mit „fehlt“ oder „schreibt nach“ aus allen Lerngruppen; Doppelklick öffnet die Arbeit."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.ausgabe.nachschreibliste import Nachschreibliste
from notenverwaltung.modell.arbeiten import STATUS, Arbeiten, Nachschreiber
from notenverwaltung.modell.stammdaten import Schuljahr
from notenverwaltung.ui.vorschau_dialog import VorschauDialog


class NachschreibDialog(QDialog):
    def __init__(self, ar: Arbeiten, jahr: Schuljahr, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar, self.jahr = ar, jahr
        self.ziel: tuple[int, int] | None = None        # (Lerngruppe, Arbeit) nach Doppelklick
        self.setWindowTitle(f"Nachschreibliste – Schuljahr {jahr.bezeichnung}")
        self.resize(820, 520)
        self.erledigte = QCheckBox("Auch schon Nachgeschriebene zeigen")
        self.erledigte.toggled.connect(self.laden)
        self.tabelle = QTableWidget(0, 6)
        self.tabelle.setHorizontalHeaderLabels(["Lerngruppe", "Arbeit", "geschrieben am", "Name", "Klasse", "Stand"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tabelle.horizontalHeader().setStretchLastSection(True)
        self.tabelle.cellDoubleClicked.connect(self._oeffnen)
        self.hinweis = QLabel("Doppelklick öffnet die Arbeit. Erledigt ist, wer Punkte oder eine Note hat.",
                              objectName="leise")
        drucken = QPushButton("Drucken / PDF …")
        drucken.clicked.connect(self.drucken)
        zu = QPushButton("Schließen")
        zu.clicked.connect(self.reject)
        unten = QHBoxLayout()
        unten.addWidget(self.hinweis, 1)
        unten.addWidget(drucken)
        unten.addWidget(zu)
        lay = QVBoxLayout(self)
        lay.addWidget(self.erledigte)
        lay.addWidget(self.tabelle, 1)
        lay.addLayout(unten)
        self.eintraege: list[Nachschreiber] = []
        self.laden()

    def laden(self, *_) -> None:
        self.eintraege = self.ar.nachschreibliste(self.jahr.id, auch_erledigte=self.erledigte.isChecked())
        self.tabelle.setRowCount(len(self.eintraege))
        for r, n in enumerate(self.eintraege):
            e = n.ergebnis
            stand = "erledigt" if n.erledigt else STATUS.get(e.status, e.status)
            for c, text in enumerate((n.gruppe.bezeichnung, n.arbeit.titel, f"{n.arbeit.datum:%d.%m.%Y}",
                                      f"{e.mitglied.schueler.nachname}, {e.mitglied.schueler.vorname}",
                                      e.mitglied.klasse, stand)):
                item = QTableWidgetItem(text)
                if c == 5 and n.erledigt:
                    item.setForeground(Qt.GlobalColor.darkGreen)
                self.tabelle.setItem(r, c, item)
        if not self.eintraege:
            self.hinweis.setText("Niemand muss etwas nachschreiben.")

    def _oeffnen(self, zeile: int, _spalte: int = 0) -> None:
        n = self.eintraege[zeile]
        self.ziel = (n.gruppe.id, n.arbeit.id)
        self.accept()

    def drucken(self) -> None:
        optionen = QLabel("Ohne Noten – die Liste kann der Aufsicht beim Nachschreibtermin mitgegeben werden.\n\n"
                          "Termin, Raum und „erledigt“ trägst du von Hand ein.")
        optionen.setWordWrap(True)
        d = VorschauDialog("Nachschreibliste", lambda: Nachschreibliste(self.eintraege, self.jahr.bezeichnung),
                           optionen, self.ar.v, f"Nachschreibliste {self.jahr.bezeichnung.replace('/', '-')}.pdf", self)
        d.aktualisieren()
        self._druckdialog = d    # für Tests erreichbar
        d.exec()
