"""Reiter „Klassenarbeiten“: Auswahl der Arbeit, Punkteraster, Notenspiegel und Notenschlüssel."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.einstellungen import einstellungen
from notenverwaltung.modell.arbeiten import STATUS, Arbeit, ArbeitFehler, Arbeiten, Ergebnis
from notenverwaltung.modell.noten import Notensystem, zahl, zahl_text
from notenverwaltung.modell.stammdaten import Lerngruppe, Schuljahr, Stammdaten
from notenverwaltung.ui.arbeit_dialoge import ArbeitDialog
from notenverwaltung.ui.bausteine import Hinweis, aktuelle_farben, frage

SP_SUMME, SP_NOTE = 3, 4
FESTE_SPALTEN = 5  # Nr., Name, Klasse, Summe, Note – immer sichtbar, Aufgaben danach


class QuotenBalken(QStyledItemDelegate):
    """Zeichnet die Lösungsquote als schmalen Balken unter den Text (Wert in UserRole, 0–100)."""

    def paint(self, painter, option, index) -> None:
        super().paint(painter, option, index)
        quote = index.data(Qt.ItemDataRole.UserRole)
        if quote is None:
            return
        r = option.rect.adjusted(4, option.rect.height() - 5, -4, -2)
        painter.save()
        painter.fillRect(r, QColor(128, 128, 128, 60))
        r.setWidth(int(r.width() * max(0.0, min(100.0, quote)) / 100))
        farbe = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.fillRect(r, farbe.color() if isinstance(farbe, QBrush) else QColor(128, 128, 128))
        painter.restore()


class PunkteModell(QAbstractTableModel):
    """Zeilen = Schüler:innen (+ Durchschnittszeile), Spalten = Nr., Name, Klasse, Summe, Note, Aufgaben…, Vermerk."""

    fehler = Signal(str)
    neu_berechnet = Signal()

    def __init__(self, ar: Arbeiten) -> None:
        super().__init__()
        self.ar = ar
        self.arbeit: Arbeit | None = None
        self.aufgaben = []
        self.ergebnisse: list[Ergebnis] = []
        self.alle_zeigen = False
        self.statistik = []

    # ---- Laden
    def lade(self, arbeit: Arbeit | None) -> None:
        self.beginResetModel()
        self.arbeit = arbeit
        self.aufgaben = self.ar.aufgaben(arbeit.id) if arbeit else []
        self._ergebnisse_laden()
        self.endResetModel()
        self.neu_berechnet.emit()

    def _ergebnisse_laden(self) -> None:
        if self.arbeit is None:
            self.ergebnisse, self.statistik = [], []
            return
        alle = self.ar.ergebnisse(self.arbeit.id)
        self.ergebnisse = [e for e in alle if self.alle_zeigen or e.erwartet or e.summe is not None]
        self.statistik = self.ar.aufgaben_statistik(self.arbeit.id, alle)

    def aktualisiere(self) -> None:
        self._ergebnisse_laden()
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        self.neu_berechnet.emit()

    # ---- Spalten
    @property
    def spalte_vermerk(self) -> int:
        return FESTE_SPALTEN + len(self.aufgaben)

    def ist_punktespalte(self, spalte: int) -> bool:
        return FESTE_SPALTEN <= spalte < self.spalte_vermerk

    def ist_schuelerzeile(self, zeile: int) -> bool:
        return 0 <= zeile < len(self.ergebnisse)

    def eingabe_bereich(self) -> tuple[int, int, int]:
        """(erste Spalte, letzte Spalte, Anzahl Zeilen) der Eingabefelder – für die Tastatursteuerung."""
        return FESTE_SPALTEN, self.spalte_vermerk - 1, len(self.ergebnisse)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() or self.arbeit is None else len(self.ergebnisse) + 1

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else FESTE_SPALTEN + len(self.aufgaben) + 1

    def headerData(self, abschnitt, ausrichtung, rolle=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if ausrichtung != Qt.Orientation.Horizontal:
            return None
        if rolle == Qt.ItemDataRole.DisplayRole:
            if abschnitt == SP_SUMME:
                return f"Summe\n({zahl_text(sum(a.max_punkte for a in self.aufgaben))})"
            if abschnitt < FESTE_SPALTEN:
                sek2 = self.arbeit is not None and self.arbeit.schluessel.system == "sek2"
                return ["Nr.", "Name", "Kl.", "", "Noten-\npunkte" if sek2 else "Note"][abschnitt]
            if self.ist_punktespalte(abschnitt):
                a = self.aufgaben[abschnitt - FESTE_SPALTEN]
                return f"{a.bezeichnung}\n({zahl_text(a.max_punkte)})"
            return "Vermerk"
        if rolle == Qt.ItemDataRole.ToolTipRole and abschnitt == SP_NOTE:
            return ("Note direkt eintippen (z. B. 2, 3+ oder 4-) – auch ohne Punkte, etwa bei Nachschreiber:innen.\n"
                    "* = festgesetzt statt aus den Punkten berechnet. Entf hebt die Festsetzung auf.")
        if rolle == Qt.ItemDataRole.ToolTipRole and self.ist_punktespalte(abschnitt):
            a = self.aufgaben[abschnitt - FESTE_SPALTEN]
            return f"Aufgabe {a.bezeichnung}: höchstens {zahl_text(a.max_punkte)} Punkte" + (
                f"\n{a.thema}" if a.thema else "")
        return None

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self.ist_schuelerzeile(index.row()) and (self.ist_punktespalte(index.column()) or index.column() == SP_NOTE):
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def data(self, index, rolle=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        z, s = index.row(), index.column()
        if not self.ist_schuelerzeile(z):
            return self._durchschnitt(s, rolle)
        e = self.ergebnisse[z]
        farben = aktuelle_farben()
        if rolle in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if s == 0:
                return str(e.mitglied.nummer)
            if s == 1:
                return f"{e.mitglied.schueler.nachname}, {e.mitglied.schueler.vorname}"
            if s == 2:
                return e.mitglied.klasse
            if self.ist_punktespalte(s):
                return zahl_text(e.punkte.get(self.aufgaben[s - FESTE_SPALTEN].id))
            if s == SP_SUMME:
                return zahl_text(e.summe)
            if s == SP_NOTE:
                if rolle == Qt.ItemDataRole.EditRole:
                    return e.note_manuell.kurz if e.note_manuell else ""
                return (e.note.kurz + ("*" if e.note_manuell else "")) if e.note else ""
            if s == self.spalte_vermerk:
                teile = [STATUS[e.status]] if e.status else []
                if not e.erwartet:
                    teile.append("nicht in der Gruppe")
                if e.kommentar:
                    teile.append("✎")
                return " · ".join(teile)
        if rolle == Qt.ItemDataRole.TextAlignmentRole and s != 1 and s != self.spalte_vermerk:
            return int(Qt.AlignmentFlag.AlignCenter)
        if rolle == Qt.ItemDataRole.ForegroundRole:
            if not e.erwartet or e.status in ("fehlt", "befreit"):
                return QBrush(QColor(farben.text_leise))
        if rolle == Qt.ItemDataRole.BackgroundRole:
            if self.ist_punktespalte(s) and e.unvollstaendig and e.punkte.get(self.aufgaben[s - FESTE_SPALTEN].id) is None:
                c = QColor(farben.warnung)
                c.setAlpha(60)
                return QBrush(c)
            if s in (SP_SUMME, SP_NOTE):
                return QBrush(QColor(farben.flaeche_hoch))
        if rolle == Qt.ItemDataRole.FontRole and s == SP_NOTE:
            f = QFont()
            f.setBold(True)
            return f
        if rolle == Qt.ItemDataRole.ToolTipRole:
            if s == SP_NOTE and e.note:
                text = e.note.wort_mit_tendenz + f" ({zahl_text(e.note.wert)})"
                if e.note_manuell:
                    text += "\nfestgesetzt" + (f", berechnet wäre {e.note_berechnet.kurz}" if e.note_berechnet else "")
                return text + f"\nfür Schüler:innen: {e.note.wort}"
            if s == self.spalte_vermerk and e.kommentar:
                return e.kommentar
            if e.unvollstaendig and self.ist_punktespalte(s):
                return "Noch nicht alle Aufgaben eingetragen"
        return None

    def _durchschnitt(self, s: int, rolle):
        farben = aktuelle_farben()
        if rolle == Qt.ItemDataRole.DisplayRole:
            if s == 1:
                return "Durchschnitt"
            if self.ist_punktespalte(s):
                st = self.statistik[s - FESTE_SPALTEN] if s - FESTE_SPALTEN < len(self.statistik) else None
                return f"{st.anteil:.0f} %" if st and st.anteil is not None else ""
            if s == SP_SUMME:
                summen = [e.summe for e in self.ergebnisse if e.summe is not None]
                return zahl_text(round(sum(summen) / len(summen), 1)) if summen else ""
        if rolle == Qt.ItemDataRole.ForegroundRole:
            return QBrush(QColor(farben.text_leise))
        if rolle == Qt.ItemDataRole.TextAlignmentRole and s != 1:
            return int(Qt.AlignmentFlag.AlignCenter)
        if rolle == Qt.ItemDataRole.ToolTipRole and self.ist_punktespalte(s):
            st = self.statistik[s - FESTE_SPALTEN]
            return (f"Im Mittel {zahl_text(round(st.mittel, 2))} von {zahl_text(st.aufgabe.max_punkte)} Punkten"
                    if st.mittel is not None else "")
        return None

    def setData(self, index, wert, rolle=Qt.ItemDataRole.EditRole):  # noqa: N802
        if rolle != Qt.ItemDataRole.EditRole or not (self.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return False
        e = self.ergebnisse[index.row()]
        if index.column() == SP_NOTE:
            return self._setze_note(e, str(wert))
        aufgabe = self.aufgaben[index.column() - FESTE_SPALTEN]
        try:
            punkte = zahl(str(wert))
            self.ar.setze_punkte(aufgabe.id, e.mitglied.schueler.id, punkte)
        except ValueError as fehler:
            self.fehler.emit(str(fehler) if isinstance(fehler, ArbeitFehler) else f"„{wert}“ ist keine Punktzahl.")
            return False
        self.fehler.emit("")
        self.aktualisiere()
        return True

    def _setze_note(self, e: Ergebnis, text: str) -> bool:
        """Note direkt eintragen: setzt sie fest (auch ohne Punkte). Leer hebt die Festsetzung auf.
        Eine eingetragene Note ersetzt den Vermerk „fehlt“/„schreibt nach“/„befreit“."""
        system = Notensystem.von(self.arbeit.schluessel.system)
        try:
            note = system.eingabe(text)
            if note is not None and system.sek2 and abs(float(text.replace(",", ".").replace("*", "")) % 1) > 0:
                raise ValueError("Bitte ganze Punkte (0–15) eingeben.")
        except ValueError as e:
            self.fehler.emit(str(e) if system.sek2 else f"„{text}“ ist keine Note. Beispiele: 2, 3+, 4-")
            return False
        werte: dict = {"note_manuell": note}
        if note is not None and e.note_berechnet == note:
            werte["note_manuell"] = None          # gleich der berechneten Note: keine Festsetzung nötig
        if note is not None and e.status:
            werte["status"] = ""
        self.ar.setze_teilnahme(self.arbeit.id, e.mitglied.schueler.id, **werte)
        self.fehler.emit("")
        self.aktualisiere()
        return True

    def leere(self, indizes) -> None:
        for i in indizes:
            if self.flags(i) & Qt.ItemFlag.ItemIsEditable:
                e = self.ergebnisse[i.row()]
                if i.column() == SP_NOTE:
                    if e.note_manuell is not None:
                        self.ar.setze_teilnahme(self.arbeit.id, e.mitglied.schueler.id, note_manuell=None)
                    continue
                self.ar.setze_punkte(self.aufgaben[i.column() - FESTE_SPALTEN].id, e.mitglied.schueler.id, None)
        self.aktualisiere()


class EingabeRaster(QTableView):
    """Tabelle mit Eingabe wie in einer Tabellenkalkulation.

    Zahl tippen startet die Eingabe; Enter übernimmt und springt weiter (nach rechts oder nach unten),
    Tab/Umschalt+Tab springen seitlich, Entf leert die markierten Felder.
    """

    def __init__(self) -> None:
        super().__init__()
        self.nach_rechts = True
        self._fehler = False
        self.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed | QAbstractItemView.EditTrigger.DoubleClicked
                             | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

    def setModel(self, modell) -> None:  # noqa: N802
        super().setModel(modell)
        modell.fehler.connect(lambda t: setattr(self, "_fehler", bool(t)))
        if hasattr(self, "_spaltenbreiten"):
            modell.modelReset.connect(self._spaltenbreiten)

    def naechste_zelle(self, index: QModelIndex, schritt: int, seitlich: bool) -> QModelIndex:
        """Nächstes Eingabefeld. Seitlich: am Zeilenende in die nächste Zeile. Nach unten (aufgabenweise):
        nach der letzten Person zur ersten Person der nächsten Spalte. Gesperrte Felder werden übersprungen;
        am Ende des Rasters bleibt der Zeiger stehen."""
        m = self.model()
        erste, letzte, anzahl = m.eingabe_bereich()
        z, s = index.row(), index.column()
        if not erste <= s <= letzte:   # Sonderspalte (z. B. Note): Enter/Tab geht in derselben Spalte nach unten
            return m.index(max(0, min(anzahl - 1, z + schritt)), s)
        for _ in range(anzahl * (letzte - erste + 1) + 1):
            if seitlich:
                s += schritt
                if s > letzte:
                    s, z = erste, z + 1
                elif s < erste:
                    s, z = letzte, z - 1
            else:
                z += schritt
                if z >= anzahl:
                    z, s = 0, s + 1
                elif z < 0:
                    z, s = anzahl - 1, s - 1
            if not (0 <= z < anzahl and erste <= s <= letzte):
                return index
            kandidat = m.index(z, s)
            if m.flags(kandidat) & Qt.ItemFlag.ItemIsEditable:
                return kandidat
        return index

    def closeEditor(self, editor, hinweis):  # noqa: N802
        index = self.currentIndex()
        super().closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
        if self._fehler:  # ungültige Eingabe: stehen bleiben
            self._fehler = False
            return
        if hinweis == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            ziel = self.naechste_zelle(index, 1, seitlich=self.nach_rechts)
        elif hinweis == QAbstractItemDelegate.EndEditHint.EditNextItem:
            ziel = self.naechste_zelle(index, 1, seitlich=True)
        elif hinweis == QAbstractItemDelegate.EndEditHint.EditPreviousItem:
            ziel = self.naechste_zelle(index, -1, seitlich=True)
        else:
            return
        self.setCurrentIndex(ziel)

    def keyPressEvent(self, ereignis) -> None:  # noqa: N802
        if ereignis.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.state() != QAbstractItemView.State.EditingState:
            self.model().leere(self.selectedIndexes())
            return
        if ereignis.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.state() != QAbstractItemView.State.EditingState:
            self.setCurrentIndex(self.naechste_zelle(self.currentIndex(), 1, seitlich=self.nach_rechts))
            return
        super().keyPressEvent(ereignis)


class PunkteRaster(EingabeRaster):
    def _spaltenbreiten(self) -> None:
        m: PunkteModell = self.model()
        k = self.horizontalHeader()
        k.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 34)
        k.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.resizeColumnToContents(1)
        self.setColumnWidth(1, max(130, min(220, self.columnWidth(1) + 8)))
        self.setColumnWidth(2, 42)
        self.setColumnWidth(SP_SUMME, 58)
        self.setColumnWidth(SP_NOTE, 48)
        for s in range(FESTE_SPALTEN, m.spalte_vermerk):
            self.setColumnWidth(s, 42)
        k.setSectionResizeMode(m.spalte_vermerk, QHeaderView.ResizeMode.Stretch)
        k.setMinimumHeight(44)


class ArbeitenTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.ar: Arbeiten | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None

        self.auswahl = QComboBox()
        self.auswahl.setMinimumWidth(260)
        self.auswahl.currentIndexChanged.connect(self._arbeit_gewaehlt)
        self.k_neu = QPushButton("Neue Arbeit …", objectName="primaer")
        self.k_neu.clicked.connect(self.neue_arbeit)
        self.k_ki = QPushButton("KI-Vorlage …")
        self.k_ki.setToolTip("Bepunktung, Erwartungshorizont und Musterlösung mit einem KI-Werkzeug deiner Wahl vorbereiten")
        self.k_ki.clicked.connect(self.ki_vorlage)
        self.k_bearbeiten = QPushButton("Aufgaben und Einstellungen …")
        self.k_bearbeiten.clicked.connect(self.bearbeiten)
        self.k_loeschen = QPushButton("Löschen")
        self.k_loeschen.clicked.connect(self.loeschen)
        self.k_drucken = QPushButton("Drucken / PDF …")
        self.k_drucken.clicked.connect(self.drucken)
        self.k_rueckmeldung = QPushButton("Rückmeldungen …")
        self.k_rueckmeldung.setToolTip("Rückmeldungen an die Schüler:innen schreiben – mit Textbausteinen, "
                                       "Person für Person")
        self.k_rueckmeldung.clicked.connect(lambda: self._kommentar())
        oben = QHBoxLayout()
        oben.addWidget(QLabel("Arbeit:"))
        oben.addWidget(self.auswahl)
        oben.addWidget(self.k_bearbeiten)
        oben.addWidget(self.k_loeschen)
        oben.addWidget(self.k_drucken)
        oben.addWidget(self.k_rueckmeldung)
        oben.addStretch(1)
        oben.addWidget(self.k_ki)
        oben.addWidget(self.k_neu)

        self.richtung = QComboBox()
        self.richtung.addItem("Enter springt nach rechts (Arbeit für Arbeit)", True)
        self.richtung.addItem("Enter springt nach unten (Aufgabe für Aufgabe)", False)
        self.richtung.setToolTip("Aufgabe für Aufgabe: Nach der letzten Person geht es mit der ersten Person der "
                                 "nächsten Aufgabe weiter. Die Wahl wird gemerkt.")
        self.fortschritt = QLabel(objectName="leise")
        self.alle = QCheckBox("Auch Ausgetretene zeigen")
        self.alle.toggled.connect(self._alle_zeigen)
        zeile2 = QHBoxLayout()
        zeile2.addWidget(self.richtung)
        zeile2.addWidget(self.alle)
        zeile2.addSpacing(12)
        zeile2.addWidget(self.fortschritt)
        zeile2.addStretch(1)
        self.info = QLabel(objectName="leise")
        zeile2.addWidget(self.info)

        self.modell: PunkteModell | None = None
        self.raster = PunkteRaster()
        rechts_merken = einstellungen().value("eingabe/arbeiten_nach_rechts", True) not in (False, "false")
        self.richtung.setCurrentIndex(0 if rechts_merken else 1)
        self.raster.nach_rechts = rechts_merken
        self.richtung.currentIndexChanged.connect(self._richtung)
        self.raster.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.raster.customContextMenuRequested.connect(self._kontextmenue)
        self.meldung = Hinweis()

        self.spiegel = QTableWidget(0, 3)
        self.spiegel.setHorizontalHeaderLabels(["Note", "Punkte", "Anzahl"])
        self.spiegel.verticalHeader().setVisible(False)
        self.spiegel.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.spiegel.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.spiegel.setMinimumWidth(190)
        self.spiegel.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.spiegel.verticalHeader().setDefaultSectionSize(20)
        self.spiegel.setShowGrid(False)
        self.zusammenfassung = QLabel()
        self.zusammenfassung.setWordWrap(True)
        rechts = QWidget()
        rl = QVBoxLayout(rechts)
        rl.setContentsMargins(8, 0, 0, 0)
        rl.addWidget(QLabel("<b>Notenspiegel</b>"))
        rl.addWidget(self.spiegel, 1)
        rl.addWidget(self.zusammenfassung)
        self.analyse_titel = QLabel("<b>Aufgabenanalyse</b>")
        self.analyse_titel.setToolTip("Lösungsquote = mittlerer Anteil der Höchstpunkte. "
                                      "Ein- und ausschalten unter Bearbeiten → Einstellungen.")
        self.analyse = QTableWidget(0, 4)
        self.analyse.setHorizontalHeaderLabels(["Aufg.", "Quote", "voll", "0"])
        self.analyse.verticalHeader().setVisible(False)
        self.analyse.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.analyse.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.analyse.verticalHeader().setDefaultSectionSize(20)
        self.analyse.setShowGrid(False)
        ka = self.analyse.horizontalHeader()
        ka.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        ka.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.analyse.setItemDelegateForColumn(1, QuotenBalken(self.analyse))
        rl.addWidget(self.analyse_titel)
        rl.addWidget(self.analyse, 1)

        teiler = QSplitter(Qt.Orientation.Horizontal)
        teiler.addWidget(self.raster)
        teiler.addWidget(rechts)
        teiler.setStretchFactor(0, 1)
        teiler.setSizes([960, 200])

        self.leer = QLabel("Noch keine Arbeit angelegt. Mit „Neue Arbeit …“ geht es los.", objectName="leise")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(oben)
        lay.addLayout(zeile2)
        lay.addWidget(self.leer)
        lay.addWidget(teiler, 1)
        lay.addWidget(self.meldung)
        self._teiler = teiler

    # ---- Anzeige ---------------------------------------------------------------------------------
    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe, arbeit_id: int | None = None) -> None:
        neu_db = self.sd is not sd
        self.sd, self.jahr, self.gruppe = sd, jahr, gruppe
        if neu_db or self.ar is None:
            self.ar = Arbeiten(sd.v)
            self.modell = PunkteModell(self.ar)
            self.modell.fehler.connect(lambda t: self.meldung.setze(t, "fehler"))
            self.modell.neu_berechnet.connect(self._spiegel)
            self.modell.neu_berechnet.connect(self._fortschritt)
            self.raster.setModel(self.modell)
            self.raster.selectionModel().currentChanged.connect(self._fortschritt)
        bisher = arbeit_id if arbeit_id is not None else self.auswahl.currentData()
        self.auswahl.blockSignals(True)
        self.auswahl.clear()
        for a in self.ar.arbeiten(gruppe.id):
            self.auswahl.addItem(f"{a.titel} – {a.datum:%d.%m.%Y}" + ("" if a.zaehlt else " (zählt nicht)"), a.id)
        idx = self.auswahl.findData(bisher)
        self.auswahl.setCurrentIndex(idx if idx >= 0 else self.auswahl.count() - 1)
        self.auswahl.blockSignals(False)
        self._arbeit_gewaehlt()

    def aktuelle_arbeit(self) -> Arbeit | None:
        aid = self.auswahl.currentData()
        return self.ar.arbeit(aid) if aid is not None else None

    def _arbeit_gewaehlt(self, *_) -> None:
        a = self.aktuelle_arbeit()
        da = a is not None
        for w in (self.k_bearbeiten, self.k_loeschen, self.k_drucken, self.k_rueckmeldung, self.auswahl,
                  self.richtung, self.alle):
            w.setEnabled(da)
        self.leer.setVisible(not da)
        self._teiler.setVisible(da)
        self.meldung.setze("")
        self.modell.lade(a)
        if da:
            halbjahr = self.jahr.halbjahr(a.datum)
            self.info.setText(f"{halbjahr}. Halbjahr" + (f" · {a.thema}" if a.thema else ""))
            erste = self.modell.index(0, FESTE_SPALTEN)
            self.raster.setCurrentIndex(erste)

    def _richtung(self, *_) -> None:
        self.raster.nach_rechts = self.richtung.currentData()
        einstellungen().setValue("eingabe/arbeiten_nach_rechts", self.raster.nach_rechts)

    def _fortschritt(self, *_) -> None:
        """„Aufgabe 3a: 17 von 28 eingetragen“ – hilft beim aufgabenweisen Korrigieren."""
        m = self.modell
        s = self.raster.currentIndex().column()
        if m is None or m.arbeit is None or not m.ist_punktespalte(s):
            self.fortschritt.setText("")
            return
        a = m.aufgaben[s - FESTE_SPALTEN]
        dabei = [e for e in m.ergebnisse if e.erwartet and not e.status]
        fertig = sum(1 for e in dabei if e.punkte.get(a.id) is not None)
        self.fortschritt.setText(f"Aufgabe {a.bezeichnung}: " + (
            f"alle {fertig} eingetragen ✓" if dabei and fertig == len(dabei) else f"{fertig} von {len(dabei)} eingetragen"))

    def _alle_zeigen(self, an: bool) -> None:
        self.modell.alle_zeigen = an
        self.modell.lade(self.modell.arbeit)

    def _spiegel(self) -> None:
        a = self.modell.arbeit
        if a is None:
            self.spiegel.setRowCount(0)
            self.zusammenfassung.setText("")
            return
        maximum = sum(x.max_punkte for x in self.modell.aufgaben)
        noten = [e.note for e in self.modell.ergebnisse if e.note is not None]
        bereiche = list(reversed(a.schluessel.bereiche(maximum))) if maximum else []
        self.spiegel.setRowCount(len(bereiche))
        for r, (von, bis, note) in enumerate(bereiche):
            anzahl = sum(1 for n in noten if n == note)
            werte = [note.kurz, zahl_text(von) if von == bis else f"{zahl_text(von)}–{zahl_text(bis)}",
                     str(anzahl) if anzahl else ""]
            for c, text in enumerate(werte):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(note.wort_mit_tendenz)
                self.spiegel.setItem(r, c, item)
        s = self.ar.notenspiegel(a.id, self.modell.ergebnisse)
        if s.gesamt and s.sek2:
            self.zusammenfassung.setText(
                f"Schnitt <b>{s.schnitt:.1f} Punkte</b>".replace(".", ",")
                + f"<br>Unter 5 Punkten: <b>{s.anteil_unter_4:.0f} %</b> · {s.gesamt} Klausuren")
        elif s.gesamt:
            stufen = "  ".join(f"{k}: {v}" for k, v in s.anzahl.items())
            self.zusammenfassung.setText(
                f"{stufen}<br>Schnitt <b>{s.schnitt:.2f}</b>".replace(".", ",")
                + f" (mit Tendenz {s.schnitt_mit_tendenz:.2f})".replace(".", ",")
                + f"<br>Unter 4: <b>{s.anteil_unter_4:.0f} %</b> · {s.gesamt} Noten")
        else:
            self.zusammenfassung.setText("Noch keine Noten.")
        self._analyse()

    def _analyse(self) -> None:
        """Lösungsquote je Aufgabe (opt-in): niedrige Quoten fallen farbig auf."""
        from notenverwaltung.einstellungen import aufgabenanalyse_an, schwellen
        from notenverwaltung.modell.rueckmeldung import aufgabenanalyse

        an = aufgabenanalyse_an() and self.modell.arbeit is not None
        self.analyse_titel.setVisible(an)
        self.analyse.setVisible(an)
        if not an:
            return
        stark, schwach = schwellen()
        f = aktuelle_farben()
        zeilen = aufgabenanalyse(self.modell.ergebnisse, self.modell.aufgaben)
        self.analyse.setRowCount(len(zeilen))
        for r, z in enumerate(zeilen):
            werte = [z.aufgabe.bezeichnung, "–" if z.quote is None else f"{z.quote:.0f} %",
                     str(z.voll) if z.bearbeitet else "", str(z.null) if z.bearbeitet else ""]
            for c, text in enumerate(werte):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if c == 1:
                    item.setData(Qt.ItemDataRole.UserRole, z.quote)
                item.setToolTip(f"Aufgabe {z.aufgabe.bezeichnung}" + (f": {z.aufgabe.thema}" if z.aufgabe.thema else "")
                                + f"\n{z.bearbeitet} bearbeitet · {z.voll}× volle Punktzahl · {z.null}× 0 Punkte")
                if c == 1 and z.quote is not None and z.quote < schwach:
                    item.setForeground(QColor(f.fehler))
                elif c == 1 and z.quote is not None and z.quote >= stark:
                    item.setForeground(QColor(f.akzent))
                self.analyse.setItem(r, c, item)

    # ---- Aktionen --------------------------------------------------------------------------------
    def neue_arbeit(self) -> None:
        d = ArbeitDialog(self.ar, self.jahr, self.gruppe, parent=self)
        if d.exec() and d.ergebnis:
            self.zeige(self.sd, self.jahr, self.gruppe, d.ergebnis.id)
            self.geaendert.emit()

    def bearbeiten(self) -> None:
        a = self.aktuelle_arbeit()
        if a and ArbeitDialog(self.ar, self.jahr, self.gruppe, a, self).exec():
            self.zeige(self.sd, self.jahr, self.gruppe, a.id)
            self.geaendert.emit()

    def ki_vorlage(self) -> None:
        from notenverwaltung.ui.ki_dialog import KiDialog

        d = KiDialog(self.ar, self.jahr, self.gruppe, self.aktuelle_arbeit(), self)
        if d.exec() and d.ergebnis:
            self.zeige(self.sd, self.jahr, self.gruppe, d.ergebnis.id)
            self.geaendert.emit()

    def drucken(self) -> None:
        from notenverwaltung.ui.druck import DruckDialog

        a = self.aktuelle_arbeit()
        if a:
            DruckDialog(self.ar, a, self).exec()

    def loeschen(self) -> None:
        a = self.aktuelle_arbeit()
        if a is None or not frage(self, "Arbeit löschen",
                                  f"„{a.titel}“ vom {a.datum:%d.%m.%Y} mit allen eingetragenen Punkten endgültig "
                                  "löschen?", ja="Endgültig löschen", warnung=True):
            return
        self.ar.loesche_arbeit(a.id)
        self.zeige(self.sd, self.jahr, self.gruppe)
        self.geaendert.emit()

    def _kontextmenue(self, pos) -> None:
        index = self.raster.indexAt(pos)
        if not self.modell.ist_schuelerzeile(index.row()):
            return
        e = self.modell.ergebnisse[index.row()]
        sid, aid = e.mitglied.schueler.id, self.modell.arbeit.id
        menue = QMenu(self)
        menue.addSection(f"{e.mitglied.schueler.vorname} {e.mitglied.schueler.nachname}")
        for schluessel, text in (("", "Kein Vermerk"), ("fehlt", "Fehlt"), ("nachschreiben", "Schreibt nach"),
                                 ("befreit", "Befreit")):
            a = menue.addAction(text)
            a.setCheckable(True)
            a.setChecked(e.status == schluessel)
            a.triggered.connect(lambda _=False, s=schluessel: self._teilnahme(sid, aid, status=s))
        menue.addSeparator()
        noten = menue.addMenu("Note festsetzen")
        for n in Notensystem.von(self.modell.arbeit.schluessel.system).alle:
            a = noten.addAction(f"{n.kurz}  ({n.wort_mit_tendenz})")
            a.triggered.connect(lambda _=False, n=n: self._teilnahme(sid, aid, note_manuell=n))
        aufheben = menue.addAction("Festsetzung aufheben")
        aufheben.setEnabled(e.note_manuell is not None)
        aufheben.triggered.connect(lambda: self._teilnahme(sid, aid, note_manuell=None))
        menue.addSeparator()
        kommentar = menue.addAction("Rückmeldung an die Person …")
        kommentar.triggered.connect(lambda: self._kommentar(e))
        leeren = menue.addAction("Markierte Felder leeren")
        leeren.triggered.connect(lambda: self.modell.leere(self.raster.selectedIndexes()))
        menue.exec(self.raster.viewport().mapToGlobal(pos))

    def _teilnahme(self, sid: int, aid: int, **werte) -> None:
        self.ar.setze_teilnahme(aid, sid, **werte)
        self.modell.aktualisiere()

    def _kommentar(self, e: Ergebnis | None = None) -> None:
        """Rückmeldungen schreiben – ab der gewählten Person, mit Blättern durch alle in der Tabelle."""
        from notenverwaltung.ui.rueckmeldung_dialog import RueckmeldungDialog

        if self.modell.arbeit is None or not self.modell.ergebnisse:
            return
        ids = [x.mitglied.schueler.id for x in self.modell.ergebnisse]
        if e is None:
            zeile = self.raster.currentIndex().row()
            start = zeile if self.modell.ist_schuelerzeile(zeile) else 0
        else:
            start = ids.index(e.mitglied.schueler.id)
        d = RueckmeldungDialog(self.ar, self.modell.arbeit, self.gruppe, ids, start, self)
        self._rueckmeldungsdialog = d    # für Tests erreichbar
        d.exec()
        self.modell.aktualisiere()

