"""Einstellungen des Programms auf diesem Rechner (keine Notendaten): Klassenarbeiten und Sicherheit."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
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
    setze_sicherheit,
    sperre_minuten,
    zweiter_ort,
    zweiter_ort_anzahl,
)
from notenverwaltung.speicher.datenbank import cloud_hinweis
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

        box = QGroupBox("Sicherheit")
        f = QFormLayout(box)
        self.sperre = QSpinBox(minimum=0, maximum=240, value=sperre_minuten())
        self.sperre.setSuffix(" Minuten")
        self.sperre.setSpecialValueText("nie")
        self.sperre.setToolTip("Nach so vielen Minuten ohne Eingabe deckt das Programm alles ab; weiter geht es mit "
                               "dem Passwort. 0 = nie. Sofort sperren: Strg+Umschalt+L.")
        f.addRow("Automatisch sperren nach:", self.sperre)
        self.ort = QLineEdit(zweiter_ort())
        self.ort.setPlaceholderText("kein zweiter Sicherungsort")
        self.ort.setClearButtonEnabled(True)
        self.ort.textChanged.connect(self._ort_pruefen)
        waehlen = QPushButton("Wählen …")
        waehlen.clicked.connect(self._ort_waehlen)
        reihe = QHBoxLayout()
        reihe.addWidget(self.ort, 1)
        reihe.addWidget(waehlen)
        f.addRow("Zweiter Sicherungsort:", reihe)
        self.anzahl = QSpinBox(minimum=1, maximum=100, value=zweiter_ort_anzahl())
        f.addRow("Kopien dort behalten:", self.anzahl)
        erkl = QLabel("Beim Schließen der Datenbank legt das Programm dort eine verschlüsselte Kopie ab, z. B. auf "
                      "einem USB-Stick. Ist der Stick nicht eingesteckt, wird die Kopie übersprungen. "
                      "Von Hand: Datei → Sicherheit → „Jetzt auf den zweiten Sicherungsort kopieren“.",
                      objectName="leise")
        erkl.setWordWrap(True)
        f.addRow(erkl)
        self.ort_hinweis = Hinweis()
        f.addRow(self.ort_hinweis)
        lay.addWidget(box)
        self._ort_pruefen()

        self.meldung = Hinweis()
        lay.addWidget(self.meldung)
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay.addWidget(knoepfe)

    def _ort_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(self, "Zweiter Sicherungsort", self.ort.text() or str(Path.home()))
        if ordner:
            self.ort.setText(ordner)

    def _ort_pruefen(self, *_) -> None:
        ort = self.ort.text().strip()
        if not ort:
            self.ort_hinweis.setze("")
        elif not Path(ort).is_dir():
            self.ort_hinweis.setze("Der Ordner ist gerade nicht erreichbar (Stick eingesteckt?).", "warnung")
        else:
            self.ort_hinweis.setze(cloud_hinweis(Path(ort) / "x.nvdb") or "", "warnung")

    def accept(self) -> None:
        if self.schwach.value() >= self.stark.value():
            self.meldung.setze("„Übungsbedarf unter“ muss kleiner sein als „Stärke ab“.", "fehler")
            return
        setze_arbeiten_optionen(self.vorschlag.isChecked(), self.analyse.isChecked(),
                                float(self.stark.value()), float(self.schwach.value()))
        setze_sicherheit(self.sperre.value(), self.ort.text().strip(), self.anzahl.value())
        super().accept()
