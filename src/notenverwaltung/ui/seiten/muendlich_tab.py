"""Reiter „Mündlich“: Noten der Sonstigen Mitarbeit je Zeitraum, mit Halbjahresmittel."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.muendlich import Muendlich, MuendlichFehler, Zeitraum, note_aus_eingabe
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Schuljahr, Stammdaten
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, aktuelle_farben, frage
from notenverwaltung.ui.seiten.arbeiten_tab import EingabeRaster

FEST = 3  # Nr., Name, Klasse


def _schnitt_text(wert: float | None) -> str:
    return f"{wert:.2f}".replace(".", ",") if wert is not None else ""


class MuendlichModell(QAbstractTableModel):
    fehler = Signal(str)
    neu_berechnet = Signal()

    def __init__(self, mu: Muendlich) -> None:
        super().__init__()
        self.mu = mu
        self.gruppe: Lerngruppe | None = None
        self.jahr: Schuljahr | None = None
        self.zeitraeume: list[Zeitraum] = []
        self.mitglieder: list[Mitglied] = []
        self.noten: dict = {}
        self.alle_zeigen = False

    def lade(self, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        self.beginResetModel()
        self.jahr, self.gruppe = jahr, gruppe
        self.zeitraeume = self.mu.zeitraeume(gruppe.id)
        alle = self.mu.sd.mitglieder(gruppe.id)
        self.mitglieder = [m for m in alle if self.alle_zeigen or any(z.erfasst(m) for z in self.zeitraeume)
                           and (m.ende is None or m.ende >= self.jahr.beginn)]
        self.noten = self.mu.noten(gruppe.id)
        self.endResetModel()
        self.neu_berechnet.emit()

    def aktualisiere(self) -> None:
        self.noten = self.mu.noten(self.gruppe.id)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1))
        self.neu_berechnet.emit()

    # ---- Struktur
    def eingabe_bereich(self) -> tuple[int, int, int]:
        return FEST, FEST + len(self.zeitraeume) - 1, len(self.mitglieder)

    def ist_zeitraum(self, spalte: int) -> bool:
        return FEST <= spalte < FEST + len(self.zeitraeume)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.mitglieder)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() or self.gruppe is None else FEST + len(self.zeitraeume) + 2

    def headerData(self, abschnitt, ausrichtung, rolle=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if ausrichtung != Qt.Orientation.Horizontal:
            return None
        if rolle == Qt.ItemDataRole.DisplayRole:
            if abschnitt < FEST:
                return ["Nr.", "Name", "Kl."][abschnitt]
            if self.ist_zeitraum(abschnitt):
                z = self.zeitraeume[abschnitt - FEST]
                return f"{z.bezeichnung}\n{z.beginn:%d.%m.}–{z.ende:%d.%m.}"
            return ["Ø 1. Hj.", "Ø 2. Hj."][abschnitt - FEST - len(self.zeitraeume)]
        if rolle == Qt.ItemDataRole.ToolTipRole and self.ist_zeitraum(abschnitt):
            z = self.zeitraeume[abschnitt - FEST]
            return f"{z.bezeichnung}: {z.beginn:%d.%m.%Y} bis {z.ende:%d.%m.%Y} ({self.jahr.halbjahr(z.beginn)}. Halbjahr)"
        return None

    def _erlaubt(self, index) -> bool:
        return (0 <= index.row() < len(self.mitglieder) and self.ist_zeitraum(index.column())
                and self.zeitraeume[index.column() - FEST].erfasst(self.mitglieder[index.row()]))

    def flags(self, index):
        f = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if self._erlaubt(index):
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def schnitt(self, m: Mitglied, halbjahr: int) -> float | None:
        werte = [self.noten[(z.id, m.schueler.id)][0].wert for z in self.zeitraeume
                 if self.jahr.halbjahr(z.beginn) == halbjahr and (z.id, m.schueler.id) in self.noten]
        return sum(werte) / len(werte) if werte else None

    def data(self, index, rolle=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        m = self.mitglieder[index.row()]
        s = index.column()
        farben = aktuelle_farben()
        eintrag = self.noten.get((self.zeitraeume[s - FEST].id, m.schueler.id)) if self.ist_zeitraum(s) else None
        if rolle in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if s == 0:
                return str(m.nummer)
            if s == 1:
                return f"{m.schueler.nachname}, {m.schueler.vorname}"
            if s == 2:
                return m.klasse
            if self.ist_zeitraum(s):
                if eintrag:
                    return eintrag[0].kurz + (" ✎" if eintrag[1] and rolle == Qt.ItemDataRole.DisplayRole else "")
                return "" if self._erlaubt(index) or rolle == Qt.ItemDataRole.EditRole else "—"
            return _schnitt_text(self.schnitt(m, s - FEST - len(self.zeitraeume) + 1))
        if rolle == Qt.ItemDataRole.TextAlignmentRole and s != 1:
            return int(Qt.AlignmentFlag.AlignCenter)
        if rolle == Qt.ItemDataRole.ForegroundRole and self.ist_zeitraum(s) and not self._erlaubt(index):
            return QBrush(QColor(farben.text_leise))
        if rolle == Qt.ItemDataRole.BackgroundRole:
            if s >= FEST + len(self.zeitraeume):
                return QBrush(QColor(farben.flaeche_hoch))
            if self.ist_zeitraum(s) and not self._erlaubt(index):
                c = QColor(farben.rand)
                c.setAlpha(90)
                return QBrush(c)
        if rolle == Qt.ItemDataRole.FontRole and s >= FEST + len(self.zeitraeume):
            f = QFont()
            f.setBold(True)
            return f
        if rolle == Qt.ItemDataRole.ToolTipRole and self.ist_zeitraum(s):
            if not self._erlaubt(index):
                return "In diesem Zeitraum nicht in der Lerngruppe – keine Note nötig."
            if eintrag:
                return eintrag[0].wort_mit_tendenz + (f"\n{eintrag[1]}" if eintrag[1] else "")
        return None

    def setData(self, index, wert, rolle=Qt.ItemDataRole.EditRole):  # noqa: N802
        if rolle != Qt.ItemDataRole.EditRole or not self._erlaubt(index):
            return False
        try:
            note = note_aus_eingabe(str(wert))
            self.mu.setze_note(self.zeitraeume[index.column() - FEST].id, self.mitglieder[index.row()].schueler.id, note)
        except MuendlichFehler as e:
            self.fehler.emit(str(e))
            return False
        self.fehler.emit("")
        self.aktualisiere()
        return True

    def leere(self, indizes) -> None:
        for i in indizes:
            if self._erlaubt(i):
                self.mu.setze_note(self.zeitraeume[i.column() - FEST].id, self.mitglieder[i.row()].schueler.id, None)
        self.aktualisiere()


class ZeitraeumeDialog(QDialog):
    """Zeiträume bearbeiten: umbenennen, Grenzen verschieben, teilen, entfernen, auf Quartale zurücksetzen."""

    def __init__(self, mu: Muendlich, jahr: Schuljahr, gruppe: Lerngruppe, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mu, self.jahr, self.gruppe = mu, jahr, gruppe
        self.setWindowTitle(f"Zeiträume – {gruppe.bezeichnung}")
        self.setMinimumSize(560, 420)
        self.tabelle = QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["Bezeichnung", "von", "bis"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        knoepfe = QHBoxLayout()
        for text, slot in (("Teilen …", self._teilen), ("Entfernen", self._entfernen),
                           ("Auf Quartale zurücksetzen", self._quartale)):
            k = QPushButton(text)
            k.clicked.connect(slot)
            knoepfe.addWidget(k)
        knoepfe.addStretch(1)
        self.meldung = Hinweis()
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        hinweis = QLabel("Ein Zeitraum darf nicht über den Halbjahreswechsel "
                         f"({jahr.halbjahreswechsel:%d.%m.%Y}) gehen. Beim Entfernen gehen die Noten des "
                         "Zeitraums verloren.", objectName="leise")
        hinweis.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle, 1)
        lay.addLayout(knoepfe)
        lay.addWidget(hinweis)
        lay.addWidget(self.meldung)
        lay.addWidget(box)
        self._setze([(z.id, z.bezeichnung, z.beginn, z.ende) for z in mu.zeitraeume(gruppe.id)])

    def _setze(self, liste) -> None:
        self.tabelle.setRowCount(0)
        for zid, bez, a, b in sorted(liste, key=lambda x: x[2]):
            r = self.tabelle.rowCount()
            self.tabelle.insertRow(r)
            item = QTableWidgetItem(bez)
            item.setData(Qt.ItemDataRole.UserRole, zid)
            self.tabelle.setItem(r, 0, item)
            for c, d in ((1, a), (2, b)):
                feld = Datumsfeld(d)
                feld.begrenze(self.jahr.beginn, self.jahr.ende)
                self.tabelle.setCellWidget(r, c, feld)

    def liste(self) -> list[tuple]:
        return [(self.tabelle.item(r, 0).data(Qt.ItemDataRole.UserRole), self.tabelle.item(r, 0).text(),
                 self.tabelle.cellWidget(r, 1).wert(), self.tabelle.cellWidget(r, 2).wert())
                for r in range(self.tabelle.rowCount())]

    def _teilen(self) -> None:
        r = self.tabelle.currentRow()
        if r < 0:
            self.meldung.setze("Bitte zuerst einen Zeitraum auswählen.", "info")
            return
        zid, bez, a, b = self.liste()[r]
        if (b - a).days < 1:
            self.meldung.setze("Dieser Zeitraum ist zu kurz zum Teilen.", "fehler")
            return
        teile, ok = QInputDialog.getInt(self, "Teilen", f"„{bez}“ in wie viele gleich lange Abschnitte teilen?", 2, 2, 8)
        if not ok:
            return
        tage = (b - a).days + 1
        neu = []
        for i in range(teile):
            von = a + timedelta(days=tage * i // teile)
            bis = a + timedelta(days=tage * (i + 1) // teile - 1)
            neu.append((zid if i == 0 else None, f"{bez} ({i + 1})", von, bis))
        liste = self.liste()
        liste[r:r + 1] = neu
        self._setze(liste)

    def _entfernen(self) -> None:
        r = self.tabelle.currentRow()
        if r >= 0:
            self.tabelle.removeRow(r)

    def _quartale(self) -> None:
        from notenverwaltung.modell.muendlich import standard_zeitraeume

        alt = self.liste()
        neu = [(alt[i][0] if i < len(alt) else None, *z) for i, z in enumerate(standard_zeitraeume(self.jahr))]
        self._setze(neu)

    def _ok(self) -> None:
        liste = self.liste()
        try:
            self.mu.pruefe_zeitraeume(self.jahr, liste)
        except MuendlichFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        weg = {z.id for z in self.mu.zeitraeume(self.gruppe.id)} - {x[0] for x in liste if x[0] is not None}
        noten = self.mu.noten(self.gruppe.id)
        verloren = sum(1 for (zid, _) in noten if zid in weg)
        if verloren and not frage(self, "Noten gehen verloren",
                                  f"Durch das Entfernen von Zeiträumen gehen {verloren} mündliche Note(n) verloren. "
                                  "Fortfahren?", ja="Fortfahren", warnung=True):
            return
        self.mu.setze_zeitraeume(self.gruppe.id, liste)
        self.accept()


class MuendlichTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.mu: Muendlich | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self.modell: MuendlichModell | None = None

        self.richtung = QComboBox()
        self.richtung.addItem("Enter springt nach unten (Zeitraum für Zeitraum)", False)
        self.richtung.addItem("Enter springt nach rechts (Person für Person)", True)
        self.richtung.currentIndexChanged.connect(lambda: setattr(self.raster, "nach_rechts", self.richtung.currentData()))
        self.alle = QCheckBox("Auch Ausgetretene zeigen")
        self.alle.toggled.connect(self._alle)
        zr = QPushButton("Zeiträume …")
        zr.clicked.connect(self._zeitraeume)
        oben = QHBoxLayout()
        oben.addWidget(self.richtung)
        oben.addWidget(self.alle)
        oben.addStretch(1)
        oben.addWidget(zr)
        self.raster = EingabeRaster()
        self.raster.nach_rechts = False
        self.raster.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.raster.customContextMenuRequested.connect(self._kontextmenue)
        self.meldung = Hinweis()
        hilfe = QLabel("Eingabe: 2, 2+, 2- oder als Zahl (1,7 → 2+). Graue Felder: in diesem Zeitraum nicht in der "
                       "Gruppe. Rechtsklick: Bemerkung.", objectName="leise")
        hilfe.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(oben)
        lay.addWidget(self.raster, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(hilfe)

    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        if self.sd is not sd or self.modell is None:
            self.sd = sd
            self.mu = Muendlich(sd.v)
            self.modell = MuendlichModell(self.mu)
            self.modell.fehler.connect(lambda t: self.meldung.setze(t, "fehler"))
            self.raster.setModel(self.modell)
        self.jahr, self.gruppe = jahr, gruppe
        self.meldung.setze("")
        self.modell.lade(jahr, gruppe)
        k = self.raster.horizontalHeader()
        k.setMinimumHeight(44)
        k.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.raster.setColumnWidth(0, 34)
        self.raster.setColumnWidth(1, 200)
        self.raster.setColumnWidth(2, 42)
        for s in range(FEST, self.modell.columnCount()):
            self.raster.setColumnWidth(s, 92)
        # Cursor in den aktuellen Zeitraum setzen
        heute = date.today()
        spalte = next((FEST + i for i, z in enumerate(self.modell.zeitraeume) if z.beginn <= heute <= z.ende), FEST)
        self.raster.setCurrentIndex(self.modell.index(0, spalte))

    def _alle(self, an: bool) -> None:
        self.modell.alle_zeigen = an
        self.modell.lade(self.jahr, self.gruppe)

    def _zeitraeume(self) -> None:
        if ZeitraeumeDialog(self.mu, self.jahr, self.gruppe, self).exec():
            self.zeige(self.sd, self.jahr, self.gruppe)
            self.geaendert.emit()

    def _kontextmenue(self, pos) -> None:
        index = self.raster.indexAt(pos)
        if not self.modell._erlaubt(index):
            return
        m = self.modell.mitglieder[index.row()]
        z = self.modell.zeitraeume[index.column() - FEST]
        eintrag = self.modell.noten.get((z.id, m.schueler.id))
        menue = QMenu(self)
        bem = menue.addAction("Bemerkung …")
        bem.setEnabled(eintrag is not None)
        if eintrag is None:
            bem.setToolTip("Erst eine Note eintragen")
        aktion = menue.exec(self.raster.viewport().mapToGlobal(pos))
        if aktion is bem and eintrag:
            text, ok = QInputDialog.getMultiLineText(self, "Bemerkung",
                                                     f"{m.schueler.vorname} {m.schueler.nachname}, {z.bezeichnung}:",
                                                     eintrag[1])
            if ok:
                self.mu.setze_note(z.id, m.schueler.id, eintrag[0], text.strip())
                self.modell.aktualisiere()

