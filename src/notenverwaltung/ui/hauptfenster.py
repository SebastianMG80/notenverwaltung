"""Hauptfenster: links die Navigation (Schuljahr → Fächer/Lerngruppen), rechts der Arbeitsbereich."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung import APP_NAME, __version__
from notenverwaltung.einstellungen import design_name, einstellungen, setze_design_name
from notenverwaltung.ui.design import wende_design_an

OFFLINE_HINWEIS = "Offline – dieses Programm sendet keine Daten."


class Willkommen(QWidget):
    """Startseite, solange keine Datenbank geöffnet ist."""

    def __init__(self) -> None:
        super().__init__()
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(40, 40, 40, 40)
        aussen.addStretch(1)

        karte = QFrame(objectName="karte")
        karte.setMaximumWidth(560)
        innen = QVBoxLayout(karte)
        innen.setContentsMargins(32, 28, 32, 28)
        innen.setSpacing(12)

        titel = QLabel("Willkommen", objectName="titel")
        text = QLabel(
            "Noch ist keine Datenbank geöffnet.\n"
            "Lege eine neue Datenbank an oder öffne eine vorhandene.",
            objectName="leise",
        )
        text.setWordWrap(True)

        knoepfe = QHBoxLayout()
        self.neu = QPushButton("Neue Datenbank …", objectName="primaer")
        self.oeffnen = QPushButton("Datenbank öffnen …")
        for k in (self.neu, self.oeffnen):
            k.setEnabled(False)
            k.setToolTip("Folgt mit der verschlüsselten Datenbank (Etappe 1).")
            knoepfe.addWidget(k)
        knoepfe.addStretch(1)

        innen.addWidget(titel)
        innen.addWidget(text)
        innen.addSpacing(8)
        innen.addLayout(knoepfe)

        zeile = QHBoxLayout()
        zeile.addStretch(1)
        zeile.addWidget(karte, 3)
        zeile.addStretch(1)
        aussen.addLayout(zeile)
        aussen.addStretch(2)


class Hauptfenster(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)

        self.navigation = QTreeWidget(objectName="navigation")
        self.navigation.setHeaderHidden(True)
        self.navigation.setMinimumWidth(200)

        self.willkommen = Willkommen()

        teiler = QSplitter(Qt.Orientation.Horizontal)
        teiler.setHandleWidth(1)
        teiler.addWidget(self.navigation)
        teiler.addWidget(self.willkommen)
        teiler.setStretchFactor(1, 1)
        teiler.setSizes([240, 760])
        self.setCentralWidget(teiler)

        self.statusBar().showMessage(OFFLINE_HINWEIS)
        self._menues()
        self._fenster_wiederherstellen()

    # ---- Menüs ---------------------------------------------------------------
    def _menues(self) -> None:
        datei = self.menuBar().addMenu("&Datei")
        beenden = QAction("&Beenden", self)
        beenden.setShortcut(QKeySequence.StandardKey.Quit)
        beenden.triggered.connect(self.close)
        datei.addAction(beenden)

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
        ueber = QAction("Ü&ber …", self)
        ueber.triggered.connect(self._ueber)
        hilfe.addAction(ueber)

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

    # ---- Fenstergröße merken ------------------------------------------------
    def _fenster_wiederherstellen(self) -> None:
        geo = einstellungen().value("fenster/geometrie")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 760)

    def closeEvent(self, ereignis) -> None:  # noqa: N802 (Qt-Name)
        s = einstellungen()
        s.setValue("fenster/geometrie", self.saveGeometry())
        s.sync()
        super().closeEvent(ereignis)
