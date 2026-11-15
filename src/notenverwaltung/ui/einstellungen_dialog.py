"""Einstellungen des Programms auf diesem Rechner (keine Notendaten): Zusatzfunktionen für Klassenarbeiten."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.einstellungen import (
    aufgabenanalyse_an,
    rueckmeldung_vorschlag_an,
    schwellen,
    setze_arbeiten_optionen,
)
from notenverwaltung.ui.bausteine import Hinweis


class EinstellungenDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)

        box = QGroupBox("Klassenarbeiten")
        f = QFormLayout(box)
        self.vorschlag = QCheckBox("Rückmeldungs-Vorschlag aus den Aufgabenergebnissen anbieten")
        self.vorschlag.setChecked(rueckmeldung_vorschlag_an())
        self.analyse = QCheckBox("Aufgabenanalyse zeigen (Lösungsquote je Aufgabe, auch als Ausdruck)")
        self.analyse.setChecked(aufgabenanalyse_an())
        stark, schwach = schwellen()
        self.stark = QSpinBox(suffix=" %", minimum=50, maximum=100, value=int(stark))
        self.schwach = QSpinBox(suffix=" %", minimum=0, maximum=90, value=int(schwach))
        f.addRow(self.vorschlag)
        f.addRow(self.analyse)
        f.addRow("„Stärke“ ab:", self.stark)
        f.addRow("„Übungsbedarf“ unter:", self.schwach)
        erkl = QLabel("Die Grenzen gelten für den Vorschlag und für die Platzhalter {Stärken} und {Übungsbedarf} "
                      "in Textbausteinen.", objectName="leise")
        erkl.setWordWrap(True)
        f.addRow(erkl)
        lay.addWidget(box)
        self.bereiche = lay              # spätere Abschnitte (Sicherheit) hängen sich hier an

        self.meldung = Hinweis()
        lay.addWidget(self.meldung)
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def accept(self) -> None:
        if self.schwach.value() >= self.stark.value():
            self.meldung.setze("„Übungsbedarf unter“ muss kleiner sein als „Stärke ab“.", "fehler")
            return
        setze_arbeiten_optionen(self.vorschlag.isChecked(), self.analyse.isChecked(),
                                float(self.stark.value()), float(self.schwach.value()))
        super().accept()
