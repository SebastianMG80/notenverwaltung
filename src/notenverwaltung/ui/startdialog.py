"""Startdialog: Datenbank auswählen und entsperren. Die zuletzt benutzte ist vorausgewählt."""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.einstellungen import merke_geoeffnet, vergiss_geoeffnet, zuletzt_geoeffnet
from notenverwaltung.speicher.datenbank import ENDUNG, SCHLUESSELDATEI_ENDUNG, Datenbank, GesperrtFehler, sicherungsordner
from notenverwaltung.speicher.krypto import EntschluesselungsFehler, normalisiere_code
from notenverwaltung.speicher.schema import SchemaFehler
from notenverwaltung.speicher.tresor import PASSWORT, SCHLUESSELDATEI, WIEDERHERSTELLUNG, FormatFehler, Tresor
from notenverwaltung.ui.bausteine import Hinweis, Passwortfeld, fehler, frage
from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent, passwort_bewertung

DATEIFILTER = f"Notenverwaltung (*{ENDUNG});;Alle Dateien (*)"


def oeffne_mit_rueckfrage(parent: QWidget, pfad: Path, art: str, wert) -> Datenbank | None:
    """Öffnet die Datenbank; fragt bei Sperre nach. Wirft EntschluesselungsFehler bei falschem Zugang."""
    QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        try:
            return Datenbank.oeffnen(pfad, art, wert)
        except GesperrtFehler as e:
            QGuiApplication.restoreOverrideCursor()
            if not frage(
                parent, "Datenbank ist schon geöffnet",
                f"Die Datenbank ist laut Sperrvermerk bereits geöffnet:\n\nRechner: {e.info.rechner}\n"
                f"Seit: {e.info.seit}\n\nWenn sie dort wirklich noch offen ist, gehen beim gleichzeitigen "
                "Bearbeiten Änderungen verloren. Ist das Programm dort abgestürzt oder längst beendet, "
                "kannst du gefahrlos fortfahren.",
                ja="Trotzdem öffnen", nein="Abbrechen", warnung=True,
            ):
                return None
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            return Datenbank.oeffnen(pfad, art, wert, sperre_ignorieren=True)
        except (FormatFehler, SchemaFehler) as e:
            QGuiApplication.restoreOverrideCursor()
            sicherung = sicherungsordner(pfad)
            zusatz = (f"\n\nSicherungen dieser Datenbank liegen im Ordner:\n{sicherung}"
                      if sicherung.is_dir() else "")
            fehler(parent, "Datenbank öffnen", f"{e}{zusatz}")
            return None
        except OSError as e:
            QGuiApplication.restoreOverrideCursor()
            fehler(parent, "Datenbank öffnen", f"Die Datei kann nicht gelesen werden:\n{e}")
            return None
    finally:
        while QGuiApplication.overrideCursor() is not None:
            QGuiApplication.restoreOverrideCursor()


class StartDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Datenbank öffnen")
        self.setMinimumSize(560, 440)
        self.datenbank: Datenbank | None = None

        titel = QLabel("Welche Datenbank möchtest du öffnen?", objectName="titel")
        titel.setStyleSheet("font-size: 15pt;")
        self.liste = QListWidget()
        self.liste.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.setWordWrap(False)
        self.liste.currentItemChanged.connect(self._auswahl_geaendert)
        self.liste.itemDoubleClicked.connect(lambda _: self.passwort.setFocus())

        self.passwort = Passwortfeld("Passwort")
        self.passwort.returnPressed.connect(self._oeffnen)
        self.meldung = Hinweis()
        self.vergessen = QPushButton("Passwort vergessen?", objectName="link")
        self.vergessen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.vergessen.clicked.connect(self._wiederherstellen)

        self.oeffnen_knopf = QPushButton("Öffnen", objectName="primaer")
        self.oeffnen_knopf.setDefault(True)
        self.oeffnen_knopf.clicked.connect(self._oeffnen)
        andere = QPushButton("Andere Datenbank …")
        andere.clicked.connect(self._andere)
        neu = QPushButton("Neue Datenbank …")
        neu.clicked.connect(self._neu)
        abbrechen = QPushButton("Abbrechen")
        abbrechen.clicked.connect(self.reject)

        pw_zeile = QHBoxLayout()
        pw_zeile.addWidget(self.passwort, 1)
        pw_zeile.addWidget(self.oeffnen_knopf)

        unten = QHBoxLayout()
        unten.addWidget(andere)
        unten.addWidget(neu)
        unten.addStretch(1)
        unten.addWidget(abbrechen)

        lay = QVBoxLayout(self)
        lay.addWidget(titel)
        lay.addWidget(self.liste, 1)
        lay.addLayout(pw_zeile)
        zeile2 = QHBoxLayout()
        zeile2.addWidget(self.meldung, 1)
        zeile2.addWidget(self.vergessen, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        lay.addLayout(zeile2)
        lay.addSpacing(8)
        lay.addLayout(unten)

        self._liste_fuellen()

    # ---- Liste -------------------------------------------------------------------------------
    def _liste_fuellen(self, auswahl: str | None = None) -> None:
        self.liste.clear()
        for pfad in zuletzt_geoeffnet():
            p = Path(pfad)
            eintrag = QListWidgetItem(f"{p.stem}\n{p.parent}")
            eintrag.setData(Qt.ItemDataRole.UserRole, pfad)
            eintrag.setToolTip(pfad)
            if not p.exists():
                eintrag.setText(f"{p.stem}  (nicht gefunden)\n{p.parent}")
                eintrag.setFlags(eintrag.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.liste.addItem(eintrag)
        ziel = 0
        for i in range(self.liste.count()):
            if self.liste.item(i).data(Qt.ItemDataRole.UserRole) == auswahl:
                ziel = i
                break
        else:
            ziel = next((i for i in range(self.liste.count())
                         if self.liste.item(i).flags() & Qt.ItemFlag.ItemIsEnabled), -1)
        if ziel >= 0:
            self.liste.setCurrentRow(ziel)
        self._auswahl_geaendert()

    def ausgewaehlt(self) -> Path | None:
        eintrag = self.liste.currentItem()
        if eintrag is None or not (eintrag.flags() & Qt.ItemFlag.ItemIsEnabled):
            return None
        return Path(eintrag.data(Qt.ItemDataRole.UserRole))

    def _auswahl_geaendert(self, *_) -> None:
        da = self.ausgewaehlt() is not None
        for w in (self.passwort, self.oeffnen_knopf, self.vergessen):
            w.setEnabled(da)
        self.meldung.setze("" if da or self.liste.count() else
                           "Noch keine Datenbank vorhanden. Lege mit „Neue Datenbank …“ eine an.", "info")
        if da:
            self.passwort.setFocus()

    # ---- Aktionen ----------------------------------------------------------------------------
    def _andere(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "Datenbank öffnen", "", DATEIFILTER)
        if pfad:
            merke_geoeffnet(str(Path(pfad)))
            self._liste_fuellen(str(Path(pfad)))

    def _neu(self) -> None:
        assistent = NeueDatenbankAssistent(self)
        if assistent.exec() and assistent.datenbank is not None:
            self.datenbank = assistent.datenbank
            merke_geoeffnet(str(self.datenbank.pfad))
            self.accept()

    def _oeffnen(self) -> None:
        pfad = self.ausgewaehlt()
        if pfad is None:
            return
        if not self.passwort.text():
            self.meldung.setze("Bitte das Passwort eingeben.", "fehler")
            return
        try:
            db = oeffne_mit_rueckfrage(self, pfad, PASSWORT, self.passwort.text())
        except EntschluesselungsFehler:
            self.meldung.setze("Das Passwort ist falsch.", "fehler")
            self.passwort.selectAll()
            self.passwort.setFocus()
            return
        if db is None:
            return
        self.passwort.clear()
        self.datenbank = db
        merke_geoeffnet(str(pfad))
        self.accept()

    def _wiederherstellen(self) -> None:
        pfad = self.ausgewaehlt()
        if pfad is None:
            return
        dialog = WiederherstellenDialog(pfad, self)
        if dialog.exec() and dialog.datenbank is not None:
            self.datenbank = dialog.datenbank
            merke_geoeffnet(str(pfad))
            self.accept()

    def entferne_aus_liste(self, pfad: str) -> None:
        vergiss_geoeffnet(pfad)
        self._liste_fuellen()


class WiederherstellenDialog(QDialog):
    """Entsperren mit Wiederherstellungscode oder Schlüsseldatei, danach neues Passwort."""

    def __init__(self, pfad: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.pfad = Path(pfad)
        self.datenbank: Datenbank | None = None
        self._schluesseldatei: bytes | None = None
        self.setWindowTitle("Passwort vergessen")
        self.setMinimumWidth(560)

        try:
            vorhanden = Tresor.vorhandene_zugaenge(self.pfad.read_bytes())
        except (OSError, FormatFehler):
            vorhanden = [WIEDERHERSTELLUNG]

        einleitung = QLabel(f"Datenbank <b>{html.escape(self.pfad.stem)}</b> mit dem Notfallblatt oder einer Schlüsseldatei "
                            "entsperren und ein neues Passwort festlegen.")
        einleitung.setWordWrap(True)

        self.mit_code = QRadioButton("Wiederherstellungscode vom Notfallblatt")
        self.mit_datei = QRadioButton("Schlüsseldatei")
        self.mit_datei.setEnabled(SCHLUESSELDATEI in vorhanden)
        if SCHLUESSELDATEI not in vorhanden:
            self.mit_datei.setToolTip("Für diese Datenbank wurde keine Schlüsseldatei angelegt.")
        gruppe = QButtonGroup(self)
        gruppe.addButton(self.mit_code)
        gruppe.addButton(self.mit_datei)
        self.mit_code.setChecked(True)

        self.code = QLineEdit()
        self.code.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.code.setStyleSheet("font-family: monospace; font-size: 13pt;")
        self.datei_knopf = QPushButton("Schlüsseldatei wählen …")
        self.datei_knopf.clicked.connect(self._datei_waehlen)
        self.datei_label = QLabel(objectName="leise")

        self.pw1 = Passwortfeld("Neues Passwort")
        self.pw2 = Passwortfeld("Neues Passwort wiederholen")
        self.bewertung = Hinweis()
        self.meldung = Hinweis()

        form = QFormLayout()
        form.addRow(self.mit_code)
        form.addRow("Code:", self.code)
        form.addRow(self.mit_datei)
        datei_zeile = QHBoxLayout()
        datei_zeile.addWidget(self.datei_knopf)
        datei_zeile.addWidget(self.datei_label, 1)
        form.addRow("", datei_zeile)
        form.addRow(QLabel(""))
        form.addRow("Neues Passwort:", self.pw1)
        form.addRow("", self.bewertung)
        form.addRow("Wiederholung:", self.pw2)

        self.knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Entsperren")
        self.knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._entsperren)
        self.knoepfe.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(einleitung)
        lay.addLayout(form)
        lay.addWidget(self.meldung)
        lay.addWidget(self.knoepfe)

        for w in (self.code, self.pw1, self.pw2):
            w.textChanged.connect(self._pruefen)
        self.mit_code.toggled.connect(self._pruefen)
        self._pruefen()

    def _datei_waehlen(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "Schlüsseldatei wählen", "",
                                              f"Schlüsseldatei (*{SCHLUESSELDATEI_ENDUNG});;Alle Dateien (*)")
        if not pfad:
            return
        try:
            self._schluesseldatei = Path(pfad).read_bytes()[:4096]
            self.datei_label.setText(Path(pfad).name)
            self.mit_datei.setChecked(True)
        except OSError as e:
            fehler(self, "Schlüsseldatei", f"Die Datei kann nicht gelesen werden:\n{e}")
        self._pruefen()

    def _pruefen(self) -> None:
        mit_code = self.mit_code.isChecked()
        self.code.setEnabled(mit_code)
        self.datei_knopf.setEnabled(not mit_code)
        ok_pw, text, art = passwort_bewertung(self.pw1.text())
        self.bewertung.setze(text, art)
        zugang_ok = self._schluesseldatei is not None
        if mit_code:
            try:
                normalisiere_code(self.code.text())
                zugang_ok = True
            except ValueError as e:
                zugang_ok = False
                self.meldung.setze(str(e) if self.code.text() else "", "info")
        if zugang_ok:
            if self.pw2.text() and self.pw1.text() != self.pw2.text():
                self.meldung.setze("Die Passwörter stimmen nicht überein.", "fehler")
            else:
                self.meldung.setze("")
        bereit = zugang_ok and ok_pw and self.pw1.text() == self.pw2.text()
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bereit)

    def _entsperren(self) -> None:
        if self.mit_code.isChecked():
            art, wert = WIEDERHERSTELLUNG, self.code.text()
        else:
            art, wert = SCHLUESSELDATEI, self._schluesseldatei or b""
        try:
            db = oeffne_mit_rueckfrage(self, self.pfad, art, wert)
        except EntschluesselungsFehler:
            self.meldung.setze("Der Code bzw. die Schlüsseldatei passt nicht zu dieser Datenbank."
                               if art == WIEDERHERSTELLUNG else
                               "Die Schlüsseldatei passt nicht zu dieser Datenbank.", "fehler")
            return
        if db is None:
            return
        try:
            db.aendere_passwort(self.pw1.text())
        except (OSError, ValueError) as e:
            fehler(self, "Neues Passwort", f"Das neue Passwort konnte nicht gespeichert werden:\n{e}")
            db.schliessen(speichern=False)
            return
        self.pw1.clear()
        self.pw2.clear()
        self.datenbank = db
        self.accept()

