"""Reiter „Schnellerfassung“: je Stunde ++ / + / o / – / –– für einzelne Personen, sporadisch.

Spalten = Stunden (Tage) im gewählten Zeitraum, dazu der Durchschnitt. „Ø als mündliche Note übernehmen“ setzt
für alle ohne mündliche Note in diesem Zeitraum den Vorschlag – festgesetzte Noten bleiben unberührt.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.muendlich import Muendlich, Zeitraum
from notenverwaltung.modell.noten import Notensystem
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Schuljahr, Stammdaten
from notenverwaltung.modell.stunden import SYMBOLE, Stunden, StundenFehler, vorschlag, wert_aus_eingabe
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, aktuelle_farben, frage
from notenverwaltung.ui.seiten.arbeiten_tab import EingabeRaster

FEST = 4   # Nr., Name, Kl., Ø


class StundenModell(QAbstractTableModel):
    fehler = Signal(str)
    neu_berechnet = Signal()

    def __init__(self, st: Stunden, sd: Stammdaten) -> None:
        super().__init__()
        self.st, self.sd = st, sd
        self.gruppe: Lerngruppe | None = None
        self.von = self.bis = date.today()
        self.tage: list[date] = []
        self.extra: set[date] = set()          # neu angelegte Stunden ohne Eintrag
        self.mitglieder: list[Mitglied] = []
        self.eintraege: dict = {}

    def lade(self, gruppe: Lerngruppe, von: date, bis: date) -> None:
        self.beginResetModel()
        self.gruppe, self.von, self.bis = gruppe, von, bis
        self.eintraege = self.st.eintraege(gruppe.id)
        tage = {d for (_, d) in self.eintraege} | self.extra
        self.tage = sorted(d for d in tage if von <= d <= bis)
        alle = self.sd.mitglieder(gruppe.id)
        self.mitglieder = [m for m in alle if (m.ende is None or m.ende >= von) and (m.beginn is None or m.beginn <= bis)]
        self.endResetModel()
        self.neu_berechnet.emit()

    def aktualisiere(self) -> None:
        self.eintraege = self.st.eintraege(self.gruppe.id)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        self.neu_berechnet.emit()

    def eingabe_bereich(self) -> tuple[int, int, int]:
        return FEST, FEST + len(self.tage) - 1, len(self.mitglieder)

    def tag(self, spalte: int) -> date | None:
        return self.tage[spalte - FEST] if FEST <= spalte < FEST + len(self.tage) else None

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.mitglieder)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() or self.gruppe is None else FEST + len(self.tage)

    def headerData(self, abschnitt, ausrichtung, rolle=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if ausrichtung != Qt.Orientation.Horizontal or rolle != Qt.ItemDataRole.DisplayRole:
            return None
        if abschnitt < FEST:
            return ["Nr.", "Name", "Kl.", "Ø"][abschnitt]
        d = self.tag(abschnitt)
        return f"{('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')[d.weekday()]}\n{d:%d.%m.}"

    def _erlaubt(self, index) -> bool:
        d = self.tag(index.column())
        return d is not None and 0 <= index.row() < len(self.mitglieder) and self.mitglieder[index.row()].aktiv_am(d)

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._erlaubt(index):
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def schnitt(self, m: Mitglied):
        return self.st.schnitt(self.gruppe.id, m.schueler.id, self.von, self.bis, self.eintraege)

    def data(self, index, rolle=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        m = self.mitglieder[index.row()]
        s = index.column()
        d = self.tag(s)
        b = self.eintraege.get((m.schueler.id, d)) if d else None
        farben = aktuelle_farben()
        if rolle in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if s == 0:
                return str(m.nummer)
            if s == 1:
                return f"{m.schueler.nachname}, {m.schueler.vorname}"
            if s == 2:
                return m.klasse
            if s == 3:
                sch = self.schnitt(m)
                if sch.wert is None:
                    return ""
                note = vorschlag(sch, Notensystem.von(self.gruppe.notensystem))
                return f"{sch.wert:.1f}".replace(".", ",") + f" → {note.kurz}"
            if b is None:
                return "" if self._erlaubt(index) or rolle == Qt.ItemDataRole.EditRole else "—"
            return b.symbol + (" ✎" if b.notiz and rolle == Qt.ItemDataRole.DisplayRole else "")
        if rolle == Qt.ItemDataRole.TextAlignmentRole and s != 1:
            return int(Qt.AlignmentFlag.AlignCenter)
        if rolle == Qt.ItemDataRole.ForegroundRole:
            if b is not None:
                return QBrush(QColor(farben.akzent if b.wert <= 2 else farben.fehler if b.wert >= 4 else farben.text))
            if d is not None and not self._erlaubt(index):
                return QBrush(QColor(farben.text_leise))
        if rolle == Qt.ItemDataRole.FontRole and (b is not None or s == 3):
            f = QFont()
            f.setBold(True)
            return f
        if rolle == Qt.ItemDataRole.BackgroundRole and s == 3:
            return QBrush(QColor(farben.flaeche_hoch))
        if rolle == Qt.ItemDataRole.ToolTipRole:
            if s == 3:
                sch = self.schnitt(m)
                return (sch.text() + " – Vorschlag für die mündliche Note") if sch.wert is not None else None
            if b is not None:
                return f"{b.symbol} am {b.datum:%d.%m.%Y}" + (f"\n{b.notiz}" if b.notiz else "")
            if d is not None and not self._erlaubt(index):
                return "An diesem Tag nicht in der Lerngruppe."
        return None

    def setData(self, index, wert, rolle=Qt.ItemDataRole.EditRole):  # noqa: N802
        if rolle != Qt.ItemDataRole.EditRole or not self._erlaubt(index):
            return False
        try:
            w = wert_aus_eingabe(str(wert))
            self.st.setze(self.gruppe.id, self.mitglieder[index.row()].schueler.id, self.tag(index.column()), w)
        except StundenFehler as e:
            self.fehler.emit(str(e))
            return False
        self.fehler.emit("")
        self.aktualisiere()
        return True

    def leere(self, indizes) -> None:
        for i in indizes:
            if self._erlaubt(i):
                self.st.setze(self.gruppe.id, self.mitglieder[i.row()].schueler.id, self.tag(i.column()), None)
        self.aktualisiere()


class StundenTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self.modell: StundenModell | None = None
        self.zeitraum = QComboBox()
        self.zeitraum.setMinimumWidth(220)
        self.zeitraum.currentIndexChanged.connect(self._laden)
        self.datum = Datumsfeld()
        neu = QPushButton("Stunde hinzufügen")
        neu.setToolTip("Legt eine Spalte für diesen Tag an – Einträge folgen per Tastatur.")
        neu.clicked.connect(self.stunde_hinzufuegen)
        self.k_uebernehmen = QPushButton("Ø als mündliche Note übernehmen …")
        self.k_uebernehmen.setToolTip("Für alle ohne mündliche Note in diesem Zeitraum den Vorschlag aus der "
                                      "Schnellerfassung eintragen. Vorhandene Noten bleiben.")
        self.k_uebernehmen.clicked.connect(self.uebernehmen)
        oben = QHBoxLayout()
        oben.addWidget(QLabel("Zeitraum:"))
        oben.addWidget(self.zeitraum)
        oben.addSpacing(16)
        oben.addWidget(self.datum)
        oben.addWidget(neu)
        oben.addStretch(1)
        oben.addWidget(self.k_uebernehmen)
        self.raster = EingabeRaster()
        self.raster.nach_rechts = False
        self.raster.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.raster.customContextMenuRequested.connect(self._kontextmenue)
        self.meldung = Hinweis()
        self.hilfe = QLabel("Eingabe: ++  +  o  -  --  (oder 1 bis 5) · Entf löscht · Rechtsklick: Notiz · "
                            "Ø → Vorschlag für die mündliche Note (++ = 1 … –– = 5)", objectName="leise")
        self.hilfe.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(oben)
        lay.addWidget(self.raster, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(self.hilfe)

    # ---- Anzeige ---------------------------------------------------------------------------------
    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        if self.sd is not sd or self.modell is None:
            self.sd = sd
            self.mu = Muendlich(sd.v)
            self.st = Stunden(sd.v)
            self.modell = StundenModell(self.st, sd)
            self.modell.fehler.connect(lambda t: self.meldung.setze(t, "fehler"))
            self.raster.setModel(self.modell)
        if self.gruppe is None or self.gruppe.id != gruppe.id:
            self.modell.extra.clear()
        self.jahr, self.gruppe = jahr, gruppe
        self.datum.begrenze(jahr.beginn, jahr.ende)
        heute = date.today()
        self.datum.setze(min(max(heute, jahr.beginn), jahr.ende))
        bisher = self.zeitraum.currentData()
        self.zeitraum.blockSignals(True)
        self.zeitraum.clear()
        self.zeitraeume: list[Zeitraum] = self.mu.zeitraeume(gruppe.id)
        for z in self.zeitraeume:
            self.zeitraum.addItem(f"{z.bezeichnung} ({z.beginn:%d.%m.}–{z.ende:%d.%m.})", z.id)
        self.zeitraum.addItem("ganzes Schuljahr", None)
        idx = self.zeitraum.findData(bisher) if bisher is not None else -1
        if idx < 0:
            idx = next((i for i, z in enumerate(self.zeitraeume) if z.beginn <= heute <= z.ende), 0)
        self.zeitraum.setCurrentIndex(idx)
        self.zeitraum.blockSignals(False)
        self._laden()

    def aktueller_zeitraum(self) -> Zeitraum | None:
        zid = self.zeitraum.currentData()
        return next((z for z in self.zeitraeume if z.id == zid), None)

    def _laden(self, *_) -> None:
        if self.gruppe is None:
            return
        z = self.aktueller_zeitraum()
        von, bis = (z.beginn, z.ende) if z else (self.jahr.beginn, self.jahr.ende)
        self.modell.lade(self.gruppe, von, bis)
        self.k_uebernehmen.setEnabled(z is not None)
        k = self.raster.horizontalHeader()
        k.setMinimumHeight(44)
        k.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for s, b in ((0, 34), (1, 200), (2, 42), (3, 84)):
            self.raster.setColumnWidth(s, b)
        for s in range(FEST, self.modell.columnCount()):
            self.raster.setColumnWidth(s, 52)
        self.meldung.setze("" if self.modell.tage else
                           "Noch keine Stunde in diesem Zeitraum – Datum wählen und „Stunde hinzufügen“.", "info")
        if self.modell.tage:      # zur neuesten Stunde
            self.raster.setCurrentIndex(self.modell.index(0, FEST + len(self.modell.tage) - 1))

    def stunde_hinzufuegen(self) -> None:
        d = self.datum.wert()
        self.modell.extra.add(d)
        z = self.aktueller_zeitraum()
        if z is not None and not z.beginn <= d <= z.ende:     # Tag liegt woanders: passenden Zeitraum zeigen
            passend = next((i for i, x in enumerate(self.zeitraeume) if x.beginn <= d <= x.ende), None)
            self.zeitraum.setCurrentIndex(passend if passend is not None else self.zeitraum.count() - 1)
        else:
            self._laden()
        if d in self.modell.tage:
            spalte = FEST + self.modell.tage.index(d)
            self.raster.setCurrentIndex(self.modell.index(0, spalte))
            self.raster.setFocus()

    def markiere_person(self, sid: int) -> None:
        ids = [m.schueler.id for m in self.modell.mitglieder] if self.modell else []
        if sid in ids:
            spalte = max(FEST, self.raster.currentIndex().column())
            self.raster.setCurrentIndex(self.modell.index(ids.index(sid), spalte))
            self.raster.setFocus()

    # ---- Aktionen --------------------------------------------------------------------------------
    def _kontextmenue(self, pos) -> None:
        index = self.raster.indexAt(pos)
        if not self.modell._erlaubt(index):
            return
        m = self.modell.mitglieder[index.row()]
        d = self.modell.tag(index.column())
        b = self.modell.eintraege.get((m.schueler.id, d))
        menue = QMenu(self)
        for w, symbol in SYMBOLE.items():
            a = menue.addAction(symbol)
            a.setCheckable(True)
            a.setChecked(b is not None and b.wert == w)
            a.triggered.connect(lambda _=False, w=w: self._setze(m, d, w))
        menue.addSeparator()
        notiz = menue.addAction("Notiz …")
        notiz.setEnabled(b is not None)
        loeschen = menue.addAction("Löschen")
        loeschen.setEnabled(b is not None)
        loeschen.triggered.connect(lambda: self._setze(m, d, None))
        aktion = menue.exec(self.raster.viewport().mapToGlobal(pos))
        if aktion is notiz and b is not None:
            text, ok = QInputDialog.getText(self, "Notiz", f"{m.schueler.vorname} {m.schueler.nachname}, "
                                                           f"{d:%d.%m.%Y}:", text=b.notiz)
            if ok:
                self.st.setze_notiz(self.gruppe.id, m.schueler.id, d, text)
                self.modell.aktualisiere()

    def _setze(self, m: Mitglied, d: date, wert: int | None) -> None:
        self.st.setze(self.gruppe.id, m.schueler.id, d, wert)
        self.modell.aktualisiere()

    def vorschlaege(self) -> list[tuple[Mitglied, object]]:
        """(Person, Note) für alle ohne mündliche Note im gewählten Zeitraum, die Einträge haben."""
        z = self.aktueller_zeitraum()
        if z is None:
            return []
        noten = self.mu.noten(self.gruppe.id)
        system = Notensystem.von(self.gruppe.notensystem)
        liste = []
        for m in self.modell.mitglieder:
            if not z.erfasst(m) or (z.id, m.schueler.id) in noten:
                continue
            note = vorschlag(self.modell.schnitt(m), system)
            if note is not None:
                liste.append((m, note))
        return liste

    def uebernehmen(self) -> None:
        z = self.aktueller_zeitraum()
        liste = self.vorschlaege()
        if z is None:
            return
        if not liste:
            self.meldung.setze("Niemand ohne mündliche Note hat in diesem Zeitraum Einträge.", "info")
            return
        namen = ", ".join(f"{m.schueler.vorname} {m.schueler.nachname[:1]}. {n.kurz}" for m, n in liste[:8])
        if not frage(self, "Vorschläge übernehmen",
                     f"Für {len(liste)} {'Person' if len(liste) == 1 else 'Personen'} ohne mündliche Note in "
                     f"„{z.bezeichnung}“ den Durchschnitt der Schnellerfassung als Note eintragen?\n\n{namen}"
                     + (" …" if len(liste) > 8 else "") + "\n\nVorhandene Noten bleiben unverändert.",
                     ja="Übernehmen"):
            return
        for m, note in liste:
            self.mu.setze_note(z.id, m.schueler.id, note)
        self.meldung.setze(f"{len(liste)} mündliche Noten übernommen.", "ok")
        self.geaendert.emit()
