"""Assistent „Neue Datenbank“: Datenschutz → Speicherort → Passwort → Notfallblatt."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from notenverwaltung import texte
from notenverwaltung.speicher.datenbank import ENDUNG, Datenbank, cloud_hinweis
from notenverwaltung.ui.bausteine import Hinweis, Passwortfeld, fehler, frage
from notenverwaltung.ui.notfall import NotfallAnzeige


def standardordner() -> Path:
    dokumente = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    return Path(dokumente or Path.home()) / "Notenverwaltung"


def passwort_bewertung(pw: str) -> tuple[bool, str, str]:
    """(ausreichend, text, art) für die Anzeige unter dem Passwortfeld."""
    n = texte.PASSWORT_MINDESTLAENGE
    if not pw:
        return False, f"Mindestens {n} Zeichen. Ein ganzer Satz lässt sich gut merken.", "info"
    if len(pw) < n:
        return False, f"Noch {n - len(pw)} Zeichen bis zur Mindestlänge.", "warnung"
    arten = sum([any(c.islower() for c in pw), any(c.isupper() for c in pw),
                 any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)])
    if len(pw) >= 16 or (len(pw) >= 12 and arten >= 3):
        return True, "Gutes Passwort.", "ok"
    return True, "Ausreichend. Länger ist sicherer.", "info"


class SeiteDatenschutz(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle(texte.DATENSCHUTZ_TITEL)
        self.setSubTitle("Bitte vor dem Anlegen der Datenbank lesen.")
        lay = QVBoxLayout(self)
        text = QLabel(texte.DATENSCHUTZ)
        text.setWordWrap(True)
        self.gelesen = QCheckBox("Ich habe den Hinweis gelesen.")
        lay.addWidget(text)
        lay.addStretch(1)
        lay.addWidget(Hinweis("Der Hinweis steht auch auf dem Notfallblatt.", "info"))
        lay.addWidget(self.gelesen)
        self.registerField("datenschutz*", self.gelesen)


class SeiteSpeicherort(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Name und Speicherort")
        self.setSubTitle("Die Datenbank ist eine einzelne Datei. Du kannst sie später auf einen anderen Rechner kopieren.")
        form = QFormLayout()
        self.name = QLineEdit("Noten")
        self.ordner = QLineEdit(str(standardordner()))
        waehlen = QPushButton("Ordner wählen …")
        waehlen.clicked.connect(self._waehlen)
        zeile = QHBoxLayout()
        zeile.addWidget(self.ordner, 1)
        zeile.addWidget(waehlen)
        form.addRow("Name:", self.name)
        form.addRow("Ordner:", zeile)
        self.ziel = QLabel(objectName="leise")
        self.ziel.setWordWrap(True)
        self.hinweis = Hinweis()
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.ziel)
        lay.addWidget(self.hinweis)
        lay.addStretch(1)
        self.name.textChanged.connect(self._pruefen)
        self.ordner.textChanged.connect(self._pruefen)
        self._pruefen()

    def _waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(self, "Ordner für die Datenbank", self.ordner.text())
        if ordner:
            self.ordner.setText(ordner)

    def pfad(self) -> Path | None:
        name = self.name.text().strip()
        if not name or any(z in name for z in '\\/:*?"<>|'):
            return None
        if name.lower().endswith(ENDUNG):
            name = name[: -len(ENDUNG)]
        return Path(self.ordner.text().strip()).expanduser() / (name + ENDUNG)

    def _pruefen(self) -> None:
        pfad = self.pfad()
        if pfad is None:
            self.ziel.setText("")
            self.hinweis.setze("Bitte einen Namen ohne die Zeichen \\ / : * ? \" < > | eingeben.", "fehler")
        elif pfad.exists():
            self.ziel.setText(f"Datei: {pfad}")
            self.hinweis.setze("Diese Datei gibt es schon. Bitte einen anderen Namen wählen.", "fehler")
        else:
            self.ziel.setText(f"Datei: {pfad}")
            warnung = cloud_hinweis(pfad)
            self.hinweis.setze(warnung or "", "warnung")
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        pfad = self.pfad()
        return pfad is not None and not pfad.exists()

    def validatePage(self) -> bool:  # noqa: N802
        pfad = self.pfad()
        if pfad is None:
            return False
        if cloud_hinweis(pfad) and not frage(
            self, "Cloud-Ordner", cloud_hinweis(pfad) + "\n\nTrotzdem hier speichern?",
            ja="Trotzdem hier speichern", nein="Anderen Ordner wählen", warnung=True,
        ):
            return False
        try:
            pfad.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            fehler(self, "Ordner", f"Der Ordner kann nicht angelegt werden:\n{e}")
            return False
        return True


class SeitePasswort(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Passwort festlegen")
        self.setSubTitle("Das Passwort wird bei jedem Öffnen der Datenbank abgefragt.")
        self.pw1 = Passwortfeld("Passwort")
        self.pw2 = Passwortfeld("Passwort wiederholen")
        self.bewertung = Hinweis()
        self.gleich = Hinweis()
        lay = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Passwort:", self.pw1)
        form.addRow("", self.bewertung)
        form.addRow("Wiederholung:", self.pw2)
        form.addRow("", self.gleich)
        lay.addLayout(form)
        lay.addStretch(1)
        lay.addWidget(Hinweis(
            "Im nächsten Schritt bekommst du ein Notfallblatt für den Fall, dass du das Passwort vergisst.", "info"))
        self.pw1.textChanged.connect(self._pruefen)
        self.pw2.textChanged.connect(self._pruefen)
        self.setCommitPage(True)
        self.setButtonText(QWizard.WizardButton.CommitButton, "Datenbank anlegen")
        self._pruefen()

    def _pruefen(self) -> None:
        ok, text, art = passwort_bewertung(self.pw1.text())
        self.bewertung.setze(text, art)
        if self.pw2.text() and self.pw2.text() != self.pw1.text():
            self.gleich.setze("Die Passwörter stimmen nicht überein.", "fehler")
        else:
            self.gleich.setze("")
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        return passwort_bewertung(self.pw1.text())[0] and self.pw1.text() == self.pw2.text()

    def validatePage(self) -> bool:  # noqa: N802
        assistent: NeueDatenbankAssistent = self.wizard()
        pfad = assistent.seite_ort.pfad()
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            db, code = Datenbank.neu(pfad, self.pw1.text())
        except (OSError, ValueError) as e:
            QGuiApplication.restoreOverrideCursor()
            fehler(self, "Datenbank anlegen", f"Die Datenbank konnte nicht angelegt werden:\n{e}")
            return False
        QGuiApplication.restoreOverrideCursor()
        assistent.datenbank = db
        assistent.seite_notfall.anzeige.setze(db.name, code)
        self.pw1.clear()
        self.pw2.clear()
        return True


class SeiteNotfall(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Notfallblatt")
        self.setSubTitle("Die Datenbank ist angelegt. Sichere jetzt den Wiederherstellungscode.")
        lay = QVBoxLayout(self)
        self.anzeige = NotfallAnzeige()
        self.anzeige.bestaetigt_geaendert.connect(lambda _: self.completeChanged.emit())
        lay.addWidget(self.anzeige)

    def isComplete(self) -> bool:  # noqa: N802
        return self.anzeige.bestaetigt


class NeueDatenbankAssistent(QWizard):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Neue Datenbank")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage, True)
        self.setMinimumSize(640, 520)
        self.datenbank: Datenbank | None = None
        self.seite_datenschutz = SeiteDatenschutz()
        self.seite_ort = SeiteSpeicherort()
        self.seite_passwort = SeitePasswort()
        self.seite_notfall = SeiteNotfall()
        for s in (self.seite_datenschutz, self.seite_ort, self.seite_passwort, self.seite_notfall):
            self.addPage(s)
        self.setButtonText(QWizard.WizardButton.NextButton, "Weiter")
        self.setButtonText(QWizard.WizardButton.BackButton, "Zurück")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Fertig")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Abbrechen")

    def reject(self) -> None:
        if self.datenbank is not None and not self.seite_notfall.anzeige.bestaetigt:
            if not frage(
                self, "Notfallblatt nicht gesichert",
                "Die Datenbank ist schon angelegt, aber das Notfallblatt ist noch nicht gesichert. "
                "Ohne Notfallblatt gibt es bei vergessenem Passwort keinen Weg zurück an die Daten.\n\n"
                "Du kannst später unter Datei → Sicherheit ein neues Notfallblatt erzeugen.",
                ja="Ohne Notfallblatt weiter", nein="Zurück", warnung=True,
            ):
                return
            self.accept()  # Datenbank ist angelegt und wird geöffnet
            return
        super().reject()
