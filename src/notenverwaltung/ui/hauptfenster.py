"""Hauptfenster: links die Navigation (Schuljahr → Fächer/Lerngruppen), rechts der Arbeitsbereich."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung import APP_NAME, __version__
from notenverwaltung.einstellungen import (
    design_name,
    einstellungen,
    merke_geoeffnet,
    setze_design_name,
    setze_ui_schrift,
    sperre_minuten,
    zweiter_ort,
    zweiter_ort_anzahl,
)
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten
from notenverwaltung.speicher.datenbank import SCHLUESSELDATEI_ENDUNG, Datenbank, sichere_nach, sicherungsordner
from notenverwaltung.speicher.verlauf import VerlaufFehler
from notenverwaltung.ui.bausteine import fehler, frage, info
from notenverwaltung.ui.design import wende_design_an
from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent
from notenverwaltung.ui.notfall import NotfallDialog
from notenverwaltung.ui.seiten.stammdaten_seiten import LerngruppeSeite, SchuelerSeite, SchuljahrSeite
from notenverwaltung.ui.sicherheit import PasswortAendernDialog
from notenverwaltung.ui.sperre import Sperre
from notenverwaltung.hilfe.fenster import zeige_hilfe
from notenverwaltung.hilfe.texte import JE_KLASSE
from notenverwaltung.ui.stammdaten_dialoge import LerngruppeDialog, SchuljahrDialog
from notenverwaltung.ui.startdialog import StartDialog

OFFLINE_HINWEIS = "Offline – dieses Programm sendet keine Daten."


def betriebszeit() -> float:
    """Sekunden seit dem Systemstart – einschließlich der Zeit im Ruhezustand.

    `time.monotonic()` bleibt unter Linux stehen, solange der Rechner schläft: Ein zugeklappter Laptop wäre
    nach dem Aufwachen sonst noch stundenlang entsperrt. Wo es die Uhr `CLOCK_BOOTTIME` nicht gibt (Windows,
    dort zählt `monotonic` den Ruhezustand mit), bleibt es bei `time.monotonic()`.
    """
    uhr = getattr(time, "CLOCK_BOOTTIME", None)
    if uhr is not None:
        try:
            return time.clock_gettime(uhr)
        except OSError:
            pass
    return time.monotonic()


class EingabeGrenze(QObject):
    """Sieht jede Eingabe der Anwendung:

    - Jede Taste / jeder Mausklick beendet den laufenden Schritt für „Rückgängig“: Was zwischen zwei Eingaben
      geändert wurde – eine Zelle, ein „OK“ im Dialog –, wird in einem Schritt zurückgenommen.
    - Merkt sich die Zeit der letzten Eingabe (automatisch sperren).
    - Während der Sperre kommen Eingaben nur beim Entsperr-Feld an; Tastenkürzel greifen nicht.
    """

    ARTEN = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.ShortcutOverride)
    EINGABEN = (QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.ShortcutOverride,
                QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
                QEvent.Type.Wheel, QEvent.Type.ContextMenu)

    def __init__(self, fenster: "Hauptfenster") -> None:
        super().__init__(fenster)
        self.fenster = fenster

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        art = ereignis.type()
        if art not in self.EINGABEN:
            return False
        sperre = self.fenster.sperre
        if sperre.aktiv:
            if not isinstance(objekt, QWidget):
                return False                       # Fensterereignisse: Qt leitet sie an die Widgets weiter
            if art == QEvent.Type.ShortcutOverride:
                ereignis.accept()                  # kein Tastenkürzel löst etwas aus
            return not sperre.erlaubt(objekt)
        if art in (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            self.fenster.letzte_eingabe = betriebszeit()
        if art in self.ARTEN and self.fenster.db is not None:
            self.fenster.db.verlauf.abschliessen()
        return False
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
    """Übersicht der geöffneten Datenbank; erscheint, solange es noch kein Schuljahr gibt."""

    schuljahr_anlegen = Signal()

    def __init__(self) -> None:
        super().__init__()
        karte, innen = _karte("")
        self.titel = karte.findChild(QLabel, "titel")
        self.angaben = QLabel(objectName="leise")
        self.angaben.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.angaben.setWordWrap(True)
        innen.addWidget(self.angaben)
        self.hinweis = QLabel("Lege als Erstes ein Schuljahr an.")
        self.anlegen = QPushButton("Schuljahr anlegen …", objectName="primaer")
        self.anlegen.clicked.connect(self.schuljahr_anlegen)
        zeile = QHBoxLayout()
        zeile.addWidget(self.anlegen)
        zeile.addStretch(1)
        innen.addSpacing(8)
        innen.addWidget(self.hinweis)
        innen.addLayout(zeile)
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
        self.uebersicht.schuljahr_anlegen.connect(self.neues_schuljahr)
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self._letzte_auswahl: tuple = ("jahr", None)
        self.seite_jahr = SchuljahrSeite()
        self.seite_schueler = SchuelerSeite()
        self.seite_gruppe = LerngruppeSeite()
        for s in (self.seite_jahr, self.seite_schueler, self.seite_gruppe):
            s.geaendert.connect(self._nach_aenderung)
        self.seite_gruppe.geloescht.connect(self._gruppe_geloescht)
        self.seite_jahr.offen_gewaehlt.connect(self.offenen_punkt_oeffnen)
        self.stapel = QStackedWidget()
        for w in (self.willkommen, self.uebersicht, self.seite_jahr, self.seite_schueler, self.seite_gruppe):
            self.stapel.addWidget(w)
        self.navigation.currentItemChanged.connect(self._navigation_gewaehlt)

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

        self.sperre = Sperre(self)
        self.sperre.pruefe = lambda pw: self.db is not None and self.db.pruefe_passwort(pw)
        self.sperre.entsperrt.connect(lambda: self.statusBar().showMessage(f"Entsperrt. {OFFLINE_HINWEIS}", 5000))
        self.letzte_eingabe = betriebszeit()
        self.sperruhr = QTimer(self)
        self.sperruhr.setInterval(10_000)
        self.sperruhr.timeout.connect(self.sperre_pruefen)
        self.sperruhr.start()
        self._menues()
        self._eingabegrenze = EingabeGrenze(self)
        QApplication.instance().installEventFilter(self._eingabegrenze)
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
        self.m_schuljahr = datei.addMenu("Sch&uljahr")
        self.m_schuljahr.aboutToShow.connect(self._schuljahr_menue_fuellen)
        self.a_neue_lerngruppe = self._aktion("Neue &Lerngruppe …", self.neue_lerngruppe, QKeySequence("Ctrl+L"))
        datei.addAction(self.a_neue_lerngruppe)
        self.a_angaben = self._aktion("&Angaben für Ausdrucke …", self.angaben_fuer_ausdrucke)
        datei.addAction(self.a_angaben)
        datei.addSeparator()

        self.m_sicherheit = datei.addMenu("S&icherheit")
        self.a_passwort = self._aktion("&Passwort ändern …", self.passwort_aendern)
        self.a_notfall = self._aktion("Neues &Notfallblatt …", self.neues_notfallblatt)
        self.a_schluesseldatei = self._aktion("&Schlüsseldatei anlegen …", self.schluesseldatei_anlegen)
        self.a_schluesseldatei_weg = self._aktion("Schlüsseldatei &entfernen", self.schluesseldatei_entfernen)
        self.a_sicherungen = self._aktion("Ordner mit Si&cherungen anzeigen", self.sicherungen_zeigen)
        self.a_zweiter_ort = self._aktion("Jetzt auf den &zweiten Sicherungsort kopieren", self.zweiten_ort_sichern)
        self.a_sperren = self._aktion("Jetzt sp&erren", lambda: self.sperren("Von Hand gesperrt."),
                                      QKeySequence("Ctrl+Shift+L"))
        for a in (self.a_passwort, self.a_notfall, self.a_schluesseldatei, self.a_schluesseldatei_weg):
            self.m_sicherheit.addAction(a)
        self.m_sicherheit.addSeparator()
        self.m_sicherheit.addAction(self.a_sicherungen)
        self.m_sicherheit.addAction(self.a_zweiter_ort)
        self.m_sicherheit.addSeparator()
        self.m_sicherheit.addAction(self.a_sperren)

        datei.addSeparator()
        datei.addAction(self._aktion("&Beenden", self.close, QKeySequence.StandardKey.Quit))

        self.m_bearbeiten = self.menuBar().addMenu("&Bearbeiten")
        self.a_rueckgaengig = self._aktion("&Rückgängig", self.rueckgaengig, QKeySequence.StandardKey.Undo)
        self.a_wiederholen = self._aktion("&Wiederholen", self.wiederholen)
        kuerzel = QKeySequence.keyBindings(QKeySequence.StandardKey.Redo)
        for k in (QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")):
            if k not in kuerzel:
                kuerzel.append(k)
        self.a_wiederholen.setShortcuts(kuerzel)
        self.m_bearbeiten.addAction(self.a_rueckgaengig)
        self.m_bearbeiten.addAction(self.a_wiederholen)
        self.m_bearbeiten.addSeparator()
        self.a_textbausteine = self._aktion("&Textbausteine …", self.textbausteine)
        self.m_bearbeiten.addAction(self.a_textbausteine)
        self.m_bearbeiten.addAction(self._aktion("&Einstellungen …", self.einstellungen_zeigen,
                                                 QKeySequence.StandardKey.Preferences))
        self.m_bearbeiten.aboutToShow.connect(self._bearbeiten_menue)

        self.m_uebersichten = self.menuBar().addMenu("Ü&bersichten")
        self.a_suche = self._aktion("&Schnellsuche …", self.schnellsuche, QKeySequence.StandardKey.Find)
        self.a_offen = self._aktion("&Offene Punkte", self.offene_punkte)
        self.a_nachschreiben = self._aktion("&Nachschreibliste …", self.nachschreibliste)
        self.a_bogen = self._aktion("Schüler:innen-&Bogen …", self.personenbogen, QKeySequence("Ctrl+B"))
        for a in (self.a_suche, self.a_offen, self.a_nachschreiben, self.a_bogen):
            self.m_uebersichten.addAction(a)

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

        ansicht.addSeparator()
        ansicht.addAction(self._aktion("&Schrift …", self.schrift_waehlen))
        ansicht.addAction(self._aktion("Schrift &größer", lambda: self.schrift_groesse(1), QKeySequence.StandardKey.ZoomIn))
        ansicht.addAction(self._aktion("Schrift &kleiner", lambda: self.schrift_groesse(-1),
                                       QKeySequence.StandardKey.ZoomOut))
        ansicht.addAction(self._aktion("Standardschrift", self.schrift_standard))

        hilfe = self.menuBar().addMenu("&Hilfe")
        # F1 selbst fängt die Anwendung ab (hilfe.fenster.F1Filter); hier steht es nur zur Information
        hilfe.addAction(self._aktion("&Hilfe zu dieser Ansicht\tF1", lambda: zeige_hilfe(self.hilfe_thema())))
        hilfe.addAction(self._aktion("&Inhalt", lambda: zeige_hilfe("start")))
        hilfe.addAction(self._aktion("&Tastenkürzel", lambda: zeige_hilfe("tasten")))
        hilfe.addAction(self._aktion("Häufige &Fragen", lambda: zeige_hilfe("probleme")))
        hilfe.addSeparator()
        hilfe.addAction(self._aktion("Ü&ber …", self._ueber))

    def hilfe_thema(self) -> str:
        """Hilfeseite zur gerade sichtbaren Ansicht (auch wenn der Fokus in der Navigation liegt)."""
        seite = self.stapel.currentWidget()
        if seite is self.seite_gruppe:
            seite = self.seite_gruppe.reiter.currentWidget() or seite
        return JE_KLASSE.get(type(seite).__name__, "start")

    def _zustand_aktualisieren(self) -> None:
        offen = self.db is not None
        for a in (self.a_speichern, self.a_schliessen, self.a_passwort, self.a_notfall,
                  self.a_schluesseldatei, self.a_sicherungen, self.a_rueckgaengig, self.a_wiederholen,
                  self.a_textbausteine, self.a_sperren, self.a_zweiter_ort):
            a.setEnabled(offen)
        self.m_schuljahr.setEnabled(offen)
        self.a_angaben.setEnabled(offen)
        self.a_neue_lerngruppe.setEnabled(offen and self.jahr is not None)
        self.m_uebersichten.setEnabled(offen and self.jahr is not None)
        self.a_schluesseldatei_weg.setEnabled(offen and self.db.tresor.hat_schluesseldatei)
        self.setWindowTitle(f"{self.db.name} – {APP_NAME}" if offen else APP_NAME)
        if offen:
            self.autospeichern.start()
            if self.jahr is None:
                self.uebersicht.zeige(self.db)
                self.stapel.setCurrentWidget(self.uebersicht)
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
        self.letzte_eingabe = betriebszeit()
        self.sd = Stammdaten(db.verbindung)
        self.jahr = self.sd.aktuelles_schuljahr()
        self._zustand_aktualisieren()
        self._navigation_fuellen()
        self.statusBar().showMessage(f"Datenbank „{db.name}“ geöffnet. {OFFLINE_HINWEIS}", 8000)

    def schliesse_datenbank(self) -> bool:
        """Speichert und schließt. Gibt False zurück, wenn das Schließen abgebrochen wurde."""
        if self.db is None:
            return True
        pfad = self.db.pfad
        try:
            self.db.schliessen(speichern=True)
        except OSError as e:
            if self.sperre.aktiv:
                # Gesperrt bleibt gesperrt: Sonst läge nach „Abbrechen“ die offene Datenbank ohne Passwort da.
                self.statusBar().showMessage(f"Speichern fehlgeschlagen: {e} – bitte erst entsperren.")
                return False
            if not frage(self, "Speichern fehlgeschlagen",
                         f"Die Datenbank konnte nicht gespeichert werden:\n{e}\n\n"
                         "Ohne Speichern schließen? Ungespeicherte Änderungen gehen verloren.",
                         ja="Ohne Speichern schließen", nein="Abbrechen", warnung=True):
                return False
            self.db.schliessen(speichern=False)
        else:
            self._zweiter_ort(pfad, still=True)
        self.sperre.aufheben()
        self.db = None
        self.sd = None
        self.jahr = None
        self._navigation_fuellen()
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

    # ---- Übersichten ---------------------------------------------------------------------------
    def nachschreibliste(self) -> None:
        if self.db is None or self.jahr is None:
            return
        from notenverwaltung.modell.arbeiten import Arbeiten
        from notenverwaltung.ui.nachschreib_dialog import NachschreibDialog

        d = NachschreibDialog(Arbeiten(self.db.verbindung), self.jahr, self)
        if d.exec() and d.ziel:
            self.oeffne_arbeit(*d.ziel)

    def textbausteine(self) -> None:
        if self.db is None:
            return
        from notenverwaltung.modell.rueckmeldung import Textbausteine
        from notenverwaltung.ui.textbausteine_dialog import TextbausteineDialog

        TextbausteineDialog(Textbausteine(self.db.verbindung), parent=self).exec()

    def einstellungen_zeigen(self) -> None:
        from notenverwaltung.ui.einstellungen_dialog import EinstellungenDialog

        if EinstellungenDialog(self).exec() and self.db is not None:
            self._navigation_fuellen(self._letzte_auswahl)      # z. B. Aufgabenanalyse ein-/ausblenden

    def oeffne_arbeit(self, gruppe_id: int, arbeit_id: int) -> None:
        """Springt zur Lerngruppe, Reiter Klassenarbeiten, und wählt die Arbeit."""
        self.oeffne_gruppe(gruppe_id, "arbeiten", arbeit_id)

    def oeffne_gruppe(self, gruppe_id: int, reiter: str | None = None, arbeit_id: int | None = None,
                      schueler_id: int | None = None) -> None:
        self._navigation_fuellen(("gruppe", gruppe_id))
        seite = self.seite_gruppe
        ziel = {"arbeiten": seite.arbeiten, "muendlich": seite.muendlich, "noten": seite.noten,
                "mitglieder": seite.mitglieder}.get(reiter or "")
        if ziel is not None and seite.reiter.isTabVisible(seite.reiter.indexOf(ziel)):
            seite.reiter.setCurrentWidget(ziel)
        if arbeit_id is not None:
            seite.arbeiten.zeige(self.sd, self.jahr, seite.gruppe, arbeit_id)
        if schueler_id is not None:
            seite.markiere_person(schueler_id)

    def schnellsuche(self) -> None:
        if self.db is None or self.jahr is None:
            return
        from notenverwaltung.ui.schnellsuche import SchnellsucheDialog

        d = SchnellsucheDialog(self.sd, self.jahr, self)
        if not d.exec() or d.gewaehlt is None:
            return
        t = d.gewaehlt
        if t.art == "person":
            self._navigation_fuellen(("schueler", None))
            self.seite_schueler.markiere_person(t.schueler_id)
        elif t.art == "person_gruppe":
            self.oeffne_gruppe(t.gruppe_id, schueler_id=t.schueler_id)
        elif t.art == "arbeit":
            self.oeffne_gruppe(t.gruppe_id, "arbeiten", t.arbeit_id)
        else:
            self.oeffne_gruppe(t.gruppe_id)

    def personenbogen(self) -> None:
        """Bogen der gerade gewählten Person – sonst erst eine Person suchen."""
        if self.db is None or self.jahr is None:
            return
        seite = self.stapel.currentWidget()
        sid = seite.aktuelle_person() if hasattr(seite, "aktuelle_person") else None
        if sid is None:
            from notenverwaltung.ui.schnellsuche import SchnellsucheDialog

            d = SchnellsucheDialog(self.sd, self.jahr, self)
            d.setWindowTitle("Schüler:innen-Bogen – Person wählen")
            if not d.exec() or d.gewaehlt is None or d.gewaehlt.schueler_id is None:
                return
            sid = d.gewaehlt.schueler_id
        from notenverwaltung.ui.personenbogen_dialog import personenbogen_dialog

        d = personenbogen_dialog(self.db.verbindung, sid, self)
        self._bogendialog = d              # für Tests
        d.exec()

    def offene_punkte(self) -> None:
        if self.db is not None and self.jahr is not None:
            self._navigation_fuellen(("jahr", None))
            self.seite_jahr.offen.setFocus()

    def offenen_punkt_oeffnen(self, p) -> None:
        if p.art == "nachschreiben":
            self.nachschreibliste()
        elif p.gruppe_id is not None:
            self.oeffne_gruppe(p.gruppe_id, p.reiter, p.arbeit_id)

    # ---- Sperre und zweiter Sicherungsort -----------------------------------------------------
    def sperre_pruefen(self) -> None:
        minuten = sperre_minuten()
        if (self.db is not None and minuten and not self.sperre.aktiv
                and betriebszeit() - self.letzte_eingabe >= minuten * 60):
            self.sperren(f"Nach {minuten} Minuten ohne Eingabe automatisch gesperrt.")

    def sperren(self, grund: str) -> None:
        if self.db is None or self.sperre.aktiv:
            return
        try:
            if self.db.geaendert:
                self.db.speichern()
        except OSError as e:
            self.statusBar().showMessage(f"Speichern vor dem Sperren fehlgeschlagen: {e}")
        self.sperre.sperren(self, grund)

    def zweiten_ort_sichern(self) -> None:
        if self.db is None:
            return
        if not zweiter_ort():
            info(self, "Zweiter Sicherungsort", "Es ist noch kein zweiter Sicherungsort eingestellt.\n\n"
                 "Bearbeiten → Einstellungen → Sicherheit, z. B. einen Ordner auf einem USB-Stick.")
            return
        try:
            self.db.speichern()
        except OSError as e:
            fehler(self, "Speichern", f"Die Datenbank konnte nicht gespeichert werden:\n{e}")
            return
        self._zweiter_ort(self.db.pfad, still=False)

    def _zweiter_ort(self, pfad: Path, still: bool) -> None:
        """Kopiert die verschlüsselte Datei auf den zweiten Sicherungsort (falls eingestellt). Ist er nicht
        erreichbar (Stick nicht eingesteckt), gibt es nur einen Hinweis – Schließen geht trotzdem."""
        ort = zweiter_ort()
        if not ort:
            return
        try:
            ziel = sichere_nach(pfad, Path(ort), zweiter_ort_anzahl())
        except OSError as e:
            text = f"Zweiter Sicherungsort: {e} Die Sicherung dort wurde übersprungen."
            if still:
                self.statusBar().showMessage(text, 15000)
            else:
                fehler(self, "Zweiter Sicherungsort", text)
            return
        self.statusBar().showMessage(f"Kopie gesichert: {ziel}", 10000)

    # ---- Rückgängig / Wiederholen --------------------------------------------------------------
    def _bearbeiten_menue(self) -> None:
        v = self.db.verlauf if self.db else None
        r = v.text_rueckgaengig() if v else ""
        w = v.text_wiederholen() if v else ""
        self.a_rueckgaengig.setText(f"&Rückgängig: {r}" if r else "&Rückgängig")
        self.a_wiederholen.setText(f"&Wiederholen: {w}" if w else "&Wiederholen")

    def rueckgaengig(self) -> None:
        self._verlauf_schritt(rueck=True)

    def wiederholen(self) -> None:
        self._verlauf_schritt(rueck=False)

    def _verlauf_schritt(self, rueck: bool) -> None:
        if self.db is None:
            return
        try:
            text = self.db.verlauf.rueckgaengig() if rueck else self.db.verlauf.wiederholen()
        except VerlaufFehler as e:
            fehler(self, "Rückgängig", str(e))
            return
        if text is None:
            self.statusBar().showMessage("Nichts rückgängig zu machen." if rueck else "Nichts zu wiederholen.", 5000)
            return
        ansicht = self._ansicht_merken()
        if self.jahr is not None:
            ids = {sj.id for sj in self.sd.schuljahre()}
            self.jahr = self.sd.schuljahr(self.jahr.id) if self.jahr.id in ids else self.sd.aktuelles_schuljahr()
        else:
            self.jahr = self.sd.aktuelles_schuljahr()
        self._zustand_aktualisieren()
        self._navigation_fuellen(self._letzte_auswahl)
        self._ansicht_wiederherstellen(ansicht)
        self.statusBar().showMessage(f"{'Rückgängig gemacht' if rueck else 'Wiederholt'}: {text}", 6000)

    def _ansicht_merken(self) -> list:
        """Aktuelle Zelle und Bildlauf aller Tabellen der sichtbaren Seite – nach dem Neuladen geht es dort weiter."""
        seite = self.stapel.currentWidget()
        return [(t, t.currentIndex().row(), t.currentIndex().column(), t.verticalScrollBar().value(),
                 t.horizontalScrollBar().value()) for t in seite.findChildren(QAbstractItemView) if t.isVisible()]

    def _ansicht_wiederherstellen(self, ansicht: list) -> None:
        for t, zeile, spalte, v, h in ansicht:
            m = t.model()
            if m is not None and 0 <= zeile < m.rowCount() and 0 <= spalte < m.columnCount():
                t.setCurrentIndex(m.index(zeile, spalte))
            t.verticalScrollBar().setValue(v)
            t.horizontalScrollBar().setValue(h)

    # ---- Schuljahr und Navigation -------------------------------------------------------------
    def _schuljahr_menue_fuellen(self) -> None:
        self.m_schuljahr.clear()
        if self.sd is None:
            return
        gruppe = QActionGroup(self.m_schuljahr)
        for sj in self.sd.schuljahre():
            a = QAction(sj.bezeichnung, self.m_schuljahr, checkable=True)
            a.setChecked(self.jahr is not None and sj.id == self.jahr.id)
            a.triggered.connect(lambda _=False, s=sj: self.wechsle_schuljahr(s))
            gruppe.addAction(a)
            self.m_schuljahr.addAction(a)
        if self.sd.schuljahre():
            self.m_schuljahr.addSeparator()
        self.m_schuljahr.addAction(self._aktion("Neues Schuljahr …", self.neues_schuljahr))
        uebernehmen = self._aktion("Neues Schuljahr aus bisherigem übernehmen …", self.schuljahr_uebernehmen)
        uebernehmen.setEnabled(self.jahr is not None)
        self.m_schuljahr.addAction(uebernehmen)
        bearbeiten = self._aktion("Schuljahr bearbeiten …", self._schuljahr_bearbeiten)
        bearbeiten.setEnabled(self.jahr is not None)
        self.m_schuljahr.addAction(bearbeiten)

    def wechsle_schuljahr(self, sj: Schuljahr) -> None:
        self.jahr = sj
        self._navigation_fuellen()
        self._zustand_aktualisieren()
        self.statusBar().showMessage(f"Schuljahr {sj.bezeichnung}. {OFFLINE_HINWEIS}", 6000)

    def neues_schuljahr(self) -> None:
        if self.sd is None:
            return
        d = SchuljahrDialog(self.sd, parent=self)
        if d.exec() and d.ergebnis:
            self.wechsle_schuljahr(d.ergebnis)

    def schuljahr_uebernehmen(self) -> None:
        if self.sd is None or self.jahr is None:
            return
        from notenverwaltung.ui.jahreswechsel_assistent import JahreswechselAssistent

        a = JahreswechselAssistent(self.sd, self.jahr, self)
        if a.exec() and a.neues_jahr:
            self.wechsle_schuljahr(a.neues_jahr)

    def _schuljahr_bearbeiten(self) -> None:
        if self.sd and self.jahr and SchuljahrDialog(self.sd, self.jahr, self).exec():
            self._nach_aenderung()

    def neue_lerngruppe(self) -> None:
        if self.sd is None or self.jahr is None:
            return
        d = LerngruppeDialog(self.sd, self.jahr, parent=self)
        if d.exec() and d.ergebnis:
            self._navigation_fuellen(("gruppe", d.ergebnis.id))
        else:
            self._navigation_fuellen(self._letzte_auswahl)

    def _nach_aenderung(self) -> None:
        if self.sd and self.jahr:
            self.jahr = self.sd.schuljahr(self.jahr.id)
        self._navigation_fuellen()

    def _gruppe_geloescht(self) -> None:
        self._navigation_fuellen(("jahr", None))

    def _navigation_fuellen(self, auswahl: tuple | None = None) -> None:
        aktuell = self.navigation.currentItem()
        ziel = auswahl or (aktuell.data(0, Qt.ItemDataRole.UserRole) if aktuell else ("jahr", None))
        self.navigation.blockSignals(True)
        self.navigation.clear()
        if self.sd is None or self.jahr is None:
            self.navigation.blockSignals(False)
            if self.db is not None:
                self.uebersicht.zeige(self.db)
                self.stapel.setCurrentWidget(self.uebersicht)
            return

        def eintrag(eltern, text, daten, fett=False):
            item = QTreeWidgetItem(eltern, [text])
            item.setData(0, Qt.ItemDataRole.UserRole, daten)
            if fett:
                f = item.font(0)
                f.setBold(True)
                item.setFont(0, f)
            return item

        eintrag(self.navigation, f"Schuljahr {self.jahr.bezeichnung}", ("jahr", None), fett=True)
        eintrag(self.navigation, "Schüler:innen", ("schueler", None))
        kopf = eintrag(self.navigation, "Lerngruppen", ("lerngruppen", None), fett=True)
        kopf.setFlags(kopf.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        for g in self.sd.lerngruppen(self.jahr.id):
            text = g.bezeichnung + ("" if g.schriftlich else "  (mündlich)")
            eintrag(kopf, text, ("gruppe", g.id))
        eintrag(kopf, "＋ Neue Lerngruppe …", ("neue_gruppe", None))
        kopf.setExpanded(True)

        gefunden = None
        for i in range(self.navigation.topLevelItemCount()):
            oben = self.navigation.topLevelItem(i)
            for item in [oben] + [oben.child(j) for j in range(oben.childCount())]:
                if item.data(0, Qt.ItemDataRole.UserRole) == ziel:
                    gefunden = item
        self.navigation.blockSignals(False)
        self.navigation.setCurrentItem(gefunden or self.navigation.topLevelItem(0))
        self._navigation_gewaehlt(self.navigation.currentItem())

    def _navigation_gewaehlt(self, item, *_) -> None:
        if item is None or self.sd is None or self.jahr is None:
            return
        art, wert = item.data(0, Qt.ItemDataRole.UserRole)
        if art != "neue_gruppe":
            self._letzte_auswahl = (art, wert)
        if art == "jahr":
            self.seite_jahr.zeige(self.sd, self.jahr)
            self.stapel.setCurrentWidget(self.seite_jahr)
        elif art == "schueler":
            self.seite_schueler.zeige(self.sd, self.jahr)
            self.stapel.setCurrentWidget(self.seite_schueler)
        elif art == "gruppe":
            self.seite_gruppe.zeige(self.sd, self.jahr, self.sd.lerngruppe(wert))
            self.stapel.setCurrentWidget(self.seite_gruppe)
        elif art == "neue_gruppe":
            QTimer.singleShot(0, self.neue_lerngruppe)

    # ---- Sicherheit ---------------------------------------------------------------------------
    def passwort_aendern(self) -> None:
        if self.db is None:
            return
        d = PasswortAendernDialog(self.db, self, [zweiter_ort()] if zweiter_ort() else [])
        if d.exec() and d.ergebnis is not None:
            self.nach_passwortwechsel(self.db.name, d.ergebnis, self)
            self._zustand_aktualisieren()
        d.deleteLater()

    @staticmethod
    def nach_passwortwechsel(name: str, ergebnis, parent: QWidget) -> None:
        """Neues Notfallblatt zeigen und sagen, was sich sonst geändert hat."""
        NotfallDialog(name, ergebnis.code, parent).exec()
        zeilen = ["Das Passwort wurde geändert, die Datenbank hat einen neuen Schlüssel."]
        if ergebnis.schluesseldatei_verfallen:
            zeilen.append("Die bisherige Schlüsseldatei gilt nicht mehr – bei Bedarf unter Datei → Sicherheit eine "
                          "neue anlegen.")
        if ergebnis.nicht_umgestellt:
            zeilen.append("Nicht umgestellt (öffnen sich weiter mit dem alten Passwort – am besten löschen oder "
                          "später erneut das Passwort ändern):\n" + "\n".join(ergebnis.nicht_umgestellt[:8]))
        info(parent, "Passwort ändern", "\n\n".join(zeilen))

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

    def angaben_fuer_ausdrucke(self) -> None:
        if self.db is None:
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit

        d = QDialog(self)
        d.setWindowTitle("Angaben für Ausdrucke")
        schule = QLineEdit(self.db.meta("druck_schule", ""))
        schule.setPlaceholderText("z. B. Gesamtschule Musterstadt")
        lehrkraft = QLineEdit(self.db.meta("druck_lehrkraft", ""))
        lehrkraft.setPlaceholderText("z. B. Herr Muster (MU)")
        form = QFormLayout(d)
        form.addRow("Schule:", schule)
        form.addRow("Lehrkraft:", lehrkraft)
        form.addRow(QLabel("Erscheint oben auf Punktelisten und Rückmeldebögen.", objectName="leise"))
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(d.accept)
        box.rejected.connect(d.reject)
        form.addRow(box)
        if d.exec():
            self.db.setze_meta("druck_schule", schule.text().strip())
            self.db.setze_meta("druck_lehrkraft", lehrkraft.text().strip())

    # ---- Ansicht / Hilfe ----------------------------------------------------------------------
    def schrift_waehlen(self) -> None:
        from PySide6.QtWidgets import QFontDialog

        ok, schrift = QFontDialog.getFont(QApplication.font(), self, "Schrift der Oberfläche")
        if ok:
            self._setze_schrift(schrift)

    def schrift_groesse(self, schritt: int) -> None:
        f = QApplication.font()
        f.setPointSizeF(max(7.0, min(20.0, f.pointSizeF() + schritt)))
        self._setze_schrift(f)

    def schrift_standard(self) -> None:
        from PySide6.QtGui import QFont

        setze_ui_schrift("")
        f = QFont()
        gemerkt = QApplication.instance().property("systemschrift")
        if not gemerkt or not f.fromString(gemerkt):
            f = QFont()
        QApplication.setFont(f)
        wende_design_an(QApplication.instance(), design_name())

    def _setze_schrift(self, f) -> None:
        setze_ui_schrift(f.toString())
        QApplication.setFont(f)
        wende_design_an(QApplication.instance(), design_name())
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
            "Verbindung ins Internet her.<br><br>"
            "Freie Software unter der GNU GPL, Version 3 oder später – ohne jede Gewährleistung.<br>"
            "Quelltext: github.com/SebastianMG80/notenverwaltung<br><br>"
            "Verwendet: Qt for Python (PySide6, LGPL v3), cryptography (Apache 2.0/BSD), "
            "segno (BSD) und Python (PSF-Lizenz). Die Lizenztexte liegen im Ordner „lizenzen“ "
            "neben dem Programm.<br>F1 öffnet die Hilfe.",
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
        # Offene Nebenfenster (z. B. die Hilfe) halten das Programm sonst unsichtbar am Laufen
        for w in QApplication.topLevelWidgets():
            if w is not self and w.isVisible():
                w.close()
