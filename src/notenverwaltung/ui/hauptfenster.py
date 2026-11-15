"""Hauptfenster: links die Navigation (Schuljahr → Fächer/Lerngruppen), rechts der Arbeitsbereich."""

from __future__ import annotations

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
)
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten
from notenverwaltung.speicher.datenbank import SCHLUESSELDATEI_ENDUNG, Datenbank, sicherungsordner
from notenverwaltung.speicher.verlauf import VerlaufFehler
from notenverwaltung.ui.bausteine import fehler, frage, info
from notenverwaltung.ui.design import wende_design_an
from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent
from notenverwaltung.ui.notfall import NotfallDialog
from notenverwaltung.ui.seiten.stammdaten_seiten import LerngruppeSeite, SchuelerSeite, SchuljahrSeite
from notenverwaltung.ui.sicherheit import PasswortAendernDialog
from notenverwaltung.hilfe.fenster import zeige_hilfe
from notenverwaltung.hilfe.texte import JE_KLASSE
from notenverwaltung.ui.stammdaten_dialoge import LerngruppeDialog, SchuljahrDialog
from notenverwaltung.ui.startdialog import StartDialog

OFFLINE_HINWEIS = "Offline – dieses Programm sendet keine Daten."


class EingabeGrenze(QObject):
    """Jede Eingabe (Taste, Mausklick) beendet den laufenden Schritt für „Rückgängig“: Was zwischen zwei
    Eingaben geändert wurde – eine Zelle, ein „OK“ im Dialog –, wird in einem Schritt zurückgenommen."""

    ARTEN = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.ShortcutOverride)

    def __init__(self, fenster: "Hauptfenster") -> None:
        super().__init__(fenster)
        self.fenster = fenster

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        if ereignis.type() in self.ARTEN and self.fenster.db is not None:
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
        for a in (self.a_passwort, self.a_notfall, self.a_schluesseldatei, self.a_schluesseldatei_weg):
            self.m_sicherheit.addAction(a)
        self.m_sicherheit.addSeparator()
        self.m_sicherheit.addAction(self.a_sicherungen)

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
        self.m_bearbeiten.aboutToShow.connect(self._bearbeiten_menue)

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
                  self.a_schluesseldatei, self.a_sicherungen, self.a_rueckgaengig, self.a_wiederholen):
            a.setEnabled(offen)
        self.m_schuljahr.setEnabled(offen)
        self.a_angaben.setEnabled(offen)
        self.a_neue_lerngruppe.setEnabled(offen and self.jahr is not None)
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
        self.sd = Stammdaten(db.verbindung)
        self.jahr = self.sd.aktuelles_schuljahr()
        self._zustand_aktualisieren()
        self._navigation_fuellen()
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
            "Verwendet: Qt for Python (PySide6, LGPL v3), cryptography (Apache 2.0/BSD), "
            "segno (BSD) und Python (PSF-Lizenz).<br>F1 öffnet die Hilfe.",
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
