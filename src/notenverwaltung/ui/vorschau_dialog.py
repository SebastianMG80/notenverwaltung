"""Allgemeiner Druckdialog: Optionen links, Vorschau rechts, PDF und Drucker."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QPageLayout, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.ausgabe.seite import Ausgabe, als_pdf, drucke, kopfzeile_aus, vorschau
from notenverwaltung.einstellungen import druck_schrift
from notenverwaltung.ui.bausteine import Hinweis, fehler


class VorschauDialog(QDialog):
    def __init__(self, titel: str, baue: Callable[[], Ausgabe], optionen: QWidget, verbindung,
                 dateiname: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.baue, self.verbindung, self.dateiname = baue, verbindung, dateiname
        self.ausgabe: Ausgabe | None = None
        self._seite = 0
        self.setWindowTitle(titel)
        self.resize(1100, 720)
        self.bild = QLabel()
        self.bild.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flaeche = QScrollArea()
        flaeche.setWidget(self.bild)
        flaeche.setWidgetResizable(True)
        self.zurueck, self.vor, self.info = QPushButton("◀"), QPushButton("▶"), QLabel()
        self.zurueck.clicked.connect(lambda: self._blaettern(-1))
        self.vor.clicked.connect(lambda: self._blaettern(1))
        nav = QHBoxLayout()
        nav.addStretch(1)
        for w in (self.zurueck, self.info, self.vor):
            nav.addWidget(w)
        nav.addStretch(1)
        self.meldung = Hinweis()
        links = QVBoxLayout()
        links.addWidget(optionen)
        links.addStretch(1)
        links.addWidget(self.meldung)
        lw = QWidget()
        lw.setLayout(links)
        lw.setFixedWidth(340)
        rechts = QVBoxLayout()
        rechts.addWidget(flaeche, 1)
        rechts.addLayout(nav)
        oben = QHBoxLayout()
        oben.addWidget(lw)
        oben.addLayout(rechts, 1)
        pdf = QPushButton("Als PDF speichern …")
        pdf.clicked.connect(self.als_pdf)
        drucken = QPushButton("Drucken …", objectName="primaer")
        drucken.clicked.connect(self.drucken)
        zu = QPushButton("Schließen")
        zu.clicked.connect(self.accept)
        unten = QHBoxLayout()
        unten.addStretch(1)
        for k in (pdf, drucken, zu):
            unten.addWidget(k)
        lay = QVBoxLayout(self)
        lay.addLayout(oben, 1)
        lay.addLayout(unten)

    def aktualisieren(self, *_) -> None:
        self.ausgabe = self.baue()
        self.ausgabe.schrift = druck_schrift() or None
        self.ausgabe.kopfzeile = kopfzeile_aus(self.verbindung)
        self._seite = min(self._seite, self.ausgabe.seitenzahl() - 1)
        self.bild.setPixmap(QPixmap.fromImage(vorschau(self.ausgabe, self._seite, dpi=80)))
        n = self.ausgabe.seitenzahl()
        self.info.setText(f"Seite {self._seite + 1} von {n}")
        self.zurueck.setEnabled(self._seite > 0)
        self.vor.setEnabled(self._seite < n - 1)

    def _blaettern(self, schritt: int) -> None:
        self._seite = max(0, min(self.ausgabe.seitenzahl() - 1, self._seite + schritt))
        self.aktualisieren()

    def als_pdf(self) -> None:
        ordner = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        name = "".join(z if z not in '\\/:*?"<>|' else "_" for z in self.dateiname)
        pfad, _ = QFileDialog.getSaveFileName(self, "Als PDF speichern", str(Path(ordner) / name), "PDF-Dateien (*.pdf)")
        if not pfad:
            return
        if not pfad.lower().endswith(".pdf"):
            pfad += ".pdf"
        try:
            als_pdf(self.ausgabe, Path(pfad))
        except OSError as e:
            fehler(self, "PDF speichern", str(e))
            return
        self.meldung.setze(f"Gespeichert: {pfad}\nDie PDF enthält Noten – bitte nicht in einer Cloud ablegen.", "ok")

    def drucken(self) -> None:
        drucker = QPrinter(QPrinter.PrinterMode.HighResolution)
        drucker.setFullPage(True)
        drucker.setDocName(self.ausgabe.titel)
        drucker.setPageOrientation(QPageLayout.Orientation.Landscape if self.ausgabe.quer
                                   else QPageLayout.Orientation.Portrait)
        if QPrintDialog(drucker, self).exec() != QDialog.DialogCode.Accepted:
            return
        try:
            drucke(self.ausgabe, drucker)
        except OSError as e:
            fehler(self, "Drucken", str(e))
            return
        self.meldung.setze("An den Drucker geschickt.", "ok")
