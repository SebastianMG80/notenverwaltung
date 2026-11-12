"""Anzeige des Wiederherstellungscodes mit Drucken / PDF – im Assistenten und für „Neues Notfallblatt“."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.ausgabe import notfallblatt
from notenverwaltung.ui.bausteine import Hinweis, fehler, frage


class NotfallAnzeige(QWidget):
    """Zeigt den Code, bietet Drucken/PDF und verlangt die Bestätigung „gesichert“."""

    bestaetigt_geaendert = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.datenbankname = ""
        self.code = ""
        self.erstellt = datetime.now()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        erklaerung = QLabel(
            "Das ist der <b>Wiederherstellungscode</b> deiner Datenbank. Mit ihm kommst du wieder an deine Daten, "
            "falls du das Passwort vergisst. Er wird nur jetzt angezeigt."
        )
        erklaerung.setWordWrap(True)
        self.code_label = QLabel(objectName="code")
        self.code_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        knoepfe = QHBoxLayout()
        self.drucken = QPushButton("Notfallblatt drucken …", objectName="primaer")
        self.pdf = QPushButton("Als PDF speichern …")
        self.drucken.clicked.connect(self._drucken)
        self.pdf.clicked.connect(self._pdf)
        knoepfe.addWidget(self.drucken)
        knoepfe.addWidget(self.pdf)
        knoepfe.addStretch(1)

        self.pdf_hinweis = Hinweis(
            "Die PDF-Datei enthält den Code. Drucke sie aus und lösche sie danach – oder bewahre sie nur auf "
            "einem eigenen USB-Stick auf, nicht auf diesem Rechner und nicht in einer Cloud.", "info")
        self.status = Hinweis("", "ok")
        self.bestaetigung = QCheckBox("Ich habe das Notfallblatt gedruckt oder sicher gespeichert.")
        self.bestaetigung.toggled.connect(self.bestaetigt_geaendert)

        lay.addWidget(erklaerung)
        lay.addSpacing(6)
        lay.addWidget(self.code_label)
        lay.addSpacing(6)
        lay.addLayout(knoepfe)
        lay.addWidget(self.status)
        lay.addWidget(self.pdf_hinweis)
        lay.addStretch(1)
        lay.addWidget(self.bestaetigung)

    def setze(self, datenbankname: str, code: str) -> None:
        self.datenbankname = datenbankname
        self.code = code
        self.erstellt = datetime.now()
        gruppen = code.split("-")
        self.code_label.setText("-".join(gruppen[:3]) + "\n" + "-".join(gruppen[3:]))
        self.bestaetigung.setChecked(False)
        self.status.setze("")

    @property
    def bestaetigt(self) -> bool:
        return self.bestaetigung.isChecked()

    def _drucken(self) -> None:
        drucker = QPrinter(QPrinter.PrinterMode.HighResolution)
        drucker.setFullPage(True)
        drucker.setDocName(f"Notfallblatt {self.datenbankname}")
        dialog = QPrintDialog(drucker, self)
        dialog.setWindowTitle("Notfallblatt drucken")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        painter = QPainter()
        if not painter.begin(drucker):
            fehler(self, "Drucken", "Der Drucker konnte nicht angesprochen werden.")
            return
        try:
            notfallblatt.zeichne(painter, self.datenbankname, self.code, self.erstellt)
        finally:
            painter.end()
        self.status.setze("Notfallblatt wurde an den Drucker geschickt.", "ok")

    def _pdf(self) -> None:
        ordner = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        vorschlag = str(Path(ordner) / f"Notfallblatt {self.datenbankname}.pdf")
        pfad, _ = QFileDialog.getSaveFileName(self, "Notfallblatt speichern", vorschlag, "PDF-Dateien (*.pdf)")
        if not pfad:
            return
        if not pfad.lower().endswith(".pdf"):
            pfad += ".pdf"
        try:
            notfallblatt.als_pdf(Path(pfad), self.datenbankname, self.code, self.erstellt)
        except OSError as e:
            fehler(self, "PDF speichern", f"Die Datei konnte nicht geschrieben werden:\n{e}")
            return
        self.status.setze(f"Gespeichert: {pfad}", "ok")


class NotfallDialog(QDialog):
    """Eigenständiger Dialog für „Neues Notfallblatt“."""

    def __init__(self, datenbankname: str, code: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neues Notfallblatt")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        self.anzeige = NotfallAnzeige()
        self.anzeige.setze(datenbankname, code)
        hinweis = Hinweis("Der bisherige Wiederherstellungscode ist ab sofort ungültig. "
                          "Alte Notfallblätter kannst du vernichten.", "warnung")
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Fertig")
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.anzeige.bestaetigt_geaendert.connect(knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled)
        knoepfe.accepted.connect(self.accept)
        lay.addWidget(hinweis)
        lay.addWidget(self.anzeige)
        lay.addWidget(knoepfe)

    def reject(self) -> None:
        if self.anzeige.bestaetigt or frage(
            self, "Notfallblatt nicht gesichert",
            "Du hast das neue Notfallblatt noch nicht gesichert. Der alte Code ist bereits ungültig.\n\n"
            "Trotzdem schließen? (Du kannst jederzeit ein weiteres neues Notfallblatt erzeugen.)",
            ja="Trotzdem schließen", nein="Zurück", warnung=True,
        ):
            super().reject()
