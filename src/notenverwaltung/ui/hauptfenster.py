"""Hauptfenster: links die Navigation (Schuljahr → Fächer/Lerngruppen), rechts der Arbeitsbereich."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung import APP_NAME, __version__
from notenverwaltung.einstellungen import design_name, einstellungen, merke_geoeffnet, setze_design_name
from notenverwaltung.speicher.datenbank import SCHLUESSELDATEI_ENDUNG, Datenbank, sicherungsordner
from notenverwaltung.ui.bausteine import fehler, frage, info
from notenverwaltung.ui.design import wende_design_an
from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent
from notenverwaltung.ui.notfall import NotfallDialog
from notenverwaltung.ui.sicherheit import PasswortAendernDialog
from notenverwaltung.ui.startdialog import StartDialog

OFFLINE_HINWEIS = "Offline – dieses Programm sendet keine Daten."
AUTOSPEICHERN_MS = 120_000


def _karte(titel: str) -> tuple[QFrame, QVBoxLayout]:
    karte = QFrame(objectName="karte")
    karte.setMaximumWidth(600)
    innen = QVBoxLayout(karte)
    innen.setContentsMargins(32, 28, 32, 28)
    innen.setSpacing(12)
    innen.addWidget(QLabel(titel, objectName="titel"))
    return karte, innen


def _zentriert(karte: QWidget) -> QWidget:
    seite = QWidget()
    aussen = QVBoxLayout(seite)
    aussen.setContentsMargins(40, 40, 40, 40)
    aussen.addStretch(1)
    zeile = QHBoxLayout()
    zeile.addStretch(1)
    zeile.addWidget(karte, 3)
    zeile.addStretch(1)
    aussen.addLayout(zeile)
    aussen.addStretch(2)
    return seite


class Willkommen(QWidget):
    """Startseite, solange keine Datenbank geöffnet ist."""

    def __init__(self) -> None:
        super().__init__()
        karte, innen = _karte("Willkommen")
        text = QLabel("Noch ist keine Datenbank geöffnet.\n"
                      "Lege eine neue Datenbank an oder öffne eine vorhandene.", objectName="leise")
        text.setWordWrap(True)
        knoepfe = QHBoxLayout()
        self.neu = QPushButton("Neue Datenbank …", objectName="primaer")
        self.oeffnen = QPushButton("Datenbank öffnen …")
        knoepfe.addWidget(self.neu)
        knoepfe.addWidget(self.oeffnen)
        knoepfe.addStretch(1)
        innen.addWidget(text)
        innen.addSpacing(8)
        innen.addLayout(knoepfe)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(_zentriert(karte))


class DatenbankUebersicht(QWidget):
    """Übersicht der geöffneten Datenbank (wird in Etappe 2 um Schuljahre ergänzt)."""

    def __init__(self) -> None:
        super().__init__()
        karte, innen = _karte("")
        self.titel = karte.findChild(QLabel, "titel")
        self.angaben = QLabel(objectName="leise")
        self.angaben.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.angaben.setWordWrap(True)
        innen.addWidget(self.angaben)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(_zentriert(karte))

    def zeige(self, db: Datenbank) -> None:
        self.titel.setText(db.name)
        erstellt = db.meta("erstellt", "")
        try:
            erstellt = datetime.fromisoformat(erstellt).strftime("%d.%m.%Y")
        except ValueError:
            pass
        zeilen = [
            f"Datei: {db.pfad}",
            f"Angelegt am: {erstellt}",
            f"Sicherungen: {len(db.sicherungen())} (im Ordner „{sicherungsordner(db.pfad).name}“)",
            "Schlüsseldatei: " + ("eingerichtet" if db.tresor.hat_schluesseldatei else "keine"),
        ]
        self.angaben.setText("\n".join(zeilen))


class Hauptfenster(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.db: Datenbank | None = None
        self.setMinimumSize(900, 600)

        self.navigation = QTreeWidget(objectName="navigation")
        self.navigation.setHeaderHidden(True)
        self.navigation.setMinimumWidth(200)

        self.willkommen = Willkommen()
        self.willkommen.neu.clicked.connect(self.neue_datenbank)
        self.willkommen.oeffnen.clicked.connect(self.zeige_startdialog)
        self.uebersicht = DatenbankUebersicht()
        self.stapel = QStackedWidget()
        self.stapel.addWidget(self.willkommen)
        self.stapel.addWidget(self.uebersicht)

        teiler = QSplitter(Qt.Orientation.Horizontal)
        teiler.setHandleWidth(1)
        teiler.addWidget(self.navigation)
        teiler.addWidget(self.stapel)
        teiler.setStretchFactor(1, 1)
        teiler.setSizes([240, 760])
        self.setCentralWidget(teiler)

        self.statusBar().showMessage(OFFLINE_HINWEIS)
        self.autospeichern = QTimer(self)
        self.autospeichern.setInterval(AUTOSPEICHERN_MS)
        self.autospeichern.timeout.connect(self._autospeichern)

        self._menues()
        self._fenster_wiederherstellen()
        self._zustand_aktualisieren()

    # ---- Menüs ---------------------------------------------------------------------------------
    def _aktion(self, text: str, slot, kuerzel=None) -> QAction:
        a = QAction(text, self)
        if kuerzel is not None:
            a.setShortcut(kuerzel)
        a.triggered.connect(slot)
        return a

    def _menues(self) -> None:
        datei = self.menuBar().addMenu("&Datei")
        self.a_neu = self._aktion("&Neue Datenbank …", self.neue_datenbank, QKeySequence.StandardKey.New)
        self.a_oeffnen = self._aktion("Datenbank ö&ffnen …", self.zeige_startdialog, QKeySequence.StandardKey.Open)
        self.a_speichern = self._aktion("&Speichern", self.speichern, QKeySequence.StandardKey.Save)
        self.a_schliessen = self._aktion("Datenbank s&chließen", self.schliesse_datenbank,
                                         QKeySequence.StandardKey.Close)
        for a in (self.a_neu, self.a_oeffnen, self.a_speichern, self.a_schliessen):
            datei.addAction(a)
        datei.addSeparator()

        self.m_sicherheit = datei.addMenu("S&icherheit")
        self.a_passwort = self._aktion("&Passwort ändern …", self.passwort_aendern)
        self.a_notfall = self._aktion("Neues &Notfallblatt …", self.neues_notfallblatt)
        self.a_schluesseldatei = self._aktion("&Schlüsseldatei anlegen …", self.schluesseldatei_anlegen)
        self.a_schluesseldatei_weg = self._aktion("Schlüsseldatei &entfernen", self.schluesseldatei_entfernen)
        self.a_sicherungen = self._aktion("Ordner mit Si&cherungen anzeigen", self.sicherungen_zeigen)
        for a in (self.a_passwort, self.a_notfall, self.a_schluesseldatei, self.a_schluesseldatei_weg):
            self.m_sicherheit.addAction(a)
        self.m_sicherheit.addSeparator()
        self.m_sicherheit.addAction(self.a_sicherungen)

        datei.addSeparator()
        datei.addAction(self._aktion("&Beenden", self.close, QKeySequence.StandardKey.Quit))

        ansicht = self.menuBar().addMenu("&Ansicht")
        design_menue = ansicht.addMenu("&Design")
        self.design_gruppe = QActionGroup(self)
        aktuell = design_name()
        for name, beschriftung in (("dunkel", "&Dunkel"), ("hell", "&Hell")):
            a = QAction(beschriftung, self, checkable=True)
            a.setData(name)
            a.setChecked(name == aktuell)
            a.triggered.connect(lambda _=False, n=name: self.setze_design(n))
            self.design_gruppe.addAction(a)
            design_menue.addAction(a)

        hilfe = self.menuBar().addMenu("&Hilfe")
        hilfe.addAction(self._aktion("Ü&ber …", self._ueber))

    def _zustand_aktualisieren(self) -> None:
        offen = self.db is not None
        for a in (self.a_speichern, self.a_schliessen, self.a_passwort, self.a_notfall,
                  self.a_schluesseldatei, self.a_sicherungen):
            a.setEnabled(offen)
        self.a_schluesseldatei_weg.setEnabled(offen and self.db.tresor.hat_schluesseldatei)
        self.setWindowTitle(f"{self.db.name} – {APP_NAME}" if offen else APP_NAME)
        if offen:
            self.uebersicht.zeige(self.db)
            self.stapel.setCurrentWidget(self.uebersicht)
            self.autospeichern.start()
        else:
            self.stapel.setCurrentWidget(self.willkommen)
            self.autospeichern.stop()

    # ---- Datenbank öffnen / schließen ---------------------------------------------------------
    def zeige_startdialog(self) -> None:
        dialog = StartDialog(self)
        if dialog.exec() and dialog.datenbank is not None:
            self.setze_datenbank(dialog.datenbank)

    def neue_datenbank(self) -> None:
        assistent = NeueDatenbankAssistent(self)
        if assistent.exec() and assistent.datenbank is not None:
            merke_geoeffnet(str(assistent.datenbank.pfad))
            self.setze_datenbank(assistent.datenbank)

    def setze_datenbank(self, db: Datenbank) -> None:
        if self.db is not None and self.db is not db and not self.schliesse_datenbank():
            db.schliessen(speichern=False)
            return
        self.db = db
        self._zustand_aktualisieren()
        self.statusBar().showMessage(f"Datenbank „{db.name}“ geöffnet. {OFFLINE_HINWEIS}", 8000)

    def schliesse_datenbank(self) -> bool:
        """Speichert und schließt. Gibt False zurück, wenn das Schließen abgebrochen wurde."""
        if self.db is None:
            return True
        try:
            self.db.schliessen(speichern=True)
        except OSError as e:
            if not frage(self, "Speichern fehlgeschlagen",
                         f"Die Datenbank konnte nicht gespeichert werden:\n{e}\n\n"
                         "Ohne Speichern schließen? Ungespeicherte Änderungen gehen verloren.",
                         ja="Ohne Speichern schließen", nein="Abbrechen", warnung=True):
                return False
            self.db.schliessen(speichern=False)
        self.db = None
        self._zustand_aktualisieren()
        return True

    def speichern(self) -> None:
        if self.db is None:
            return
        try:
            self.db.speichern()
        except OSError as e:
            fehler(self, "Speichern", f"Die Datenbank konnte nicht gespeichert werden:\n{e}")
            return
        self.statusBar().showMessage(f"Gespeichert um {datetime.now():%H:%M} Uhr. {OFFLINE_HINWEIS}", 8000)
        self.uebersicht.zeige(self.db)

    def _autospeichern(self) -> None:
        if self.db is not None and self.db.geaendert:
            try:
                self.db.speichern()
                self.statusBar().showMessage(
                    f"Automatisch gespeichert um {datetime.now():%H:%M} Uhr. {OFFLINE_HINWEIS}", 8000)
            except OSError as e:
                self.statusBar().showMessage(f"Automatisches Speichern fehlgeschlagen: {e}")

    # ---- Sicherheit ---------------------------------------------------------------------------
    def passwort_aendern(self) -> None:
        if self.db and PasswortAendernDialog(self.db, self).exec():
            info(self, "Passwort ändern", "Das Passwort wurde geändert.")

    def neues_notfallblatt(self) -> None:
        if self.db is None:
            return
        if not frage(self, "Neues Notfallblatt",
                     "Es wird ein neuer Wiederherstellungscode erzeugt. Der bisherige Code und alte "
                     "Notfallblätter werden damit ungültig.\n\nFortfahren?", ja="Neuen Code erzeugen"):
            return
        try:
            code = self.db.neuer_wiederherstellungscode()
        except OSError as e:
            fehler(self, "Neues Notfallblatt", f"Der neue Code konnte nicht gespeichert werden:\n{e}")
            return
        NotfallDialog(self.db.name, code, self).exec()

    def schluesseldatei_anlegen(self) -> None:
        if self.db is None:
            return
        if not frage(
            self, "Schlüsseldatei anlegen",
            "Eine Schlüsseldatei öffnet die Datenbank ohne Passwort – wie ein Ersatzschlüssel. "
            "Speichere sie auf einem USB-Stick und bewahre ihn getrennt vom Rechner auf.\n\n"
            + ("Eine bereits vorhandene Schlüsseldatei wird dabei ungültig.\n\n"
               if self.db.tresor.hat_schluesseldatei else "")
            + "Fortfahren?", ja="Schlüsseldatei anlegen",
        ):
            return
        pfad, _ = QFileDialog.getSaveFileName(
            self, "Schlüsseldatei speichern", f"{self.db.name}{SCHLUESSELDATEI_ENDUNG}",
            f"Schlüsseldatei (*{SCHLUESSELDATEI_ENDUNG})")
        if not pfad:
            return
        try:
            ziel = self.db.neue_schluesseldatei(Path(pfad))
        except OSError as e:
            fehler(self, "Schlüsseldatei", f"Die Schlüsseldatei konnte nicht angelegt werden:\n{e}")
            return
        self._zustand_aktualisieren()
        info(self, "Schlüsseldatei", f"Die Schlüsseldatei wurde gespeichert:\n{ziel}")

    def schluesseldatei_entfernen(self) -> None:
        if self.db is None or not frage(self, "Schlüsseldatei entfernen",
                                        "Die Schlüsseldatei kann die Datenbank danach nicht mehr öffnen. Fortfahren?",
                                        ja="Entfernen"):
            return
        try:
            self.db.entferne_schluesseldatei()
        except OSError as e:
            fehler(self, "Schlüsseldatei", str(e))
        self._zustand_aktualisieren()

    def sicherungen_zeigen(self) -> None:
        if self.db is None:
            return
        ordner = sicherungsordner(self.db.pfad)
        if not ordner.is_dir():
            info(self, "Sicherungen", "Es gibt noch keine Sicherungen. Sie entstehen beim ersten Speichern "
                                      "nach dem Öffnen der Datenbank.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ordner)))

    # ---- Ansicht / Hilfe ----------------------------------------------------------------------
    def setze_design(self, name: str) -> None:
        setze_design_name(name)
        wende_design_an(QApplication.instance(), name)

    def _ueber(self) -> None:
        QMessageBox.about(
            self,
            f"Über {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Notenverwaltung für Lehrer:innen.<br>"
            "Alle Daten bleiben auf diesem Rechner. Das Programm stellt keine "
            "Verbindung ins Internet her.",
        )

    # ---- Fenster ------------------------------------------------------------------------------
    def _fenster_wiederherstellen(self) -> None:
        geo = einstellungen().value("fenster/geometrie")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 760)

    def closeEvent(self, ereignis) -> None:  # noqa: N802 (Qt-Name)
        if not self.schliesse_datenbank():
            ereignis.ignore()
            return
        s = einstellungen()
        s.setValue("fenster/geometrie", self.saveGeometry())
        s.sync()
        super().closeEvent(ereignis)
