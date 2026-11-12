"""Reiter „Noten“: schriftlicher und mündlicher Schnitt, Vorschlag mit Herleitung, festgesetzte Zeugnisnote."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.muendlich import MuendlichFehler, note_aus_eingabe
from notenverwaltung.modell.noten import Notenspiegel
from notenverwaltung.modell.stammdaten import Lerngruppe, Schuljahr, Stammdaten
from notenverwaltung.modell.zeugnis import Teilnote, Vorschlag, Zeile, Zeugnis, ZeugnisFehler
from notenverwaltung.ui.bausteine import Hinweis, aktuelle_farben, info

ROLLE_ART = Qt.ItemDataRole.UserRole + 1
ROLLE_SID = Qt.ItemDataRole.UserRole + 2


def _z(wert: float | None) -> str:
    return "" if wert is None else f"{wert:.2f}".replace(".", ",")


class GewichtungDialog(QDialog):
    def __init__(self, zg: Zeugnis, gruppe: Lerngruppe, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zg, self.gruppe = zg, gruppe
        gw = zg.gewichtung(gruppe)
        self.setWindowTitle(f"Gewichtung – {gruppe.bezeichnung}")
        self.automatisch = QCheckBox("automatisch (schriftliche Fächer 50 %, mündliche 0 %)")
        self.automatisch.setChecked(gw.schriftlich_automatisch)
        self.schriftlich = QDoubleSpinBox()
        self.schriftlich.setRange(0, 100)
        self.schriftlich.setSuffix(" %")
        self.schriftlich.setValue(gw.anteil_schriftlich)
        self.automatisch.toggled.connect(lambda an: self.schriftlich.setEnabled(not an))
        self.schriftlich.setEnabled(not gw.schriftlich_automatisch)
        self.hj1 = QDoubleSpinBox()
        self.hj1.setRange(0, 50)
        self.hj1.setSuffix(" %")
        self.hj1.setValue(gw.anteil_hj1)
        self.zp10 = QComboBox()
        self.zp10.addItem("automatisch (Deutsch, Englisch, Mathematik in Jahrgang 10)", None)
        self.zp10.addItem("ja – Ganzjahresnote + ZP10", True)
        self.zp10.addItem("nein", False)
        self.zp10.setCurrentIndex(0 if gw.zp10_automatisch else (1 if gw.zp10 else 2))
        form = QFormLayout(self)
        form.addRow("Anteil schriftlich:", self.schriftlich)
        form.addRow("", self.automatisch)
        form.addRow("Anteil des 1. Halbjahres an der Note des 2. Halbjahres:", self.hj1)
        form.addRow("ZP10-Fach:", self.zp10)
        erkl = QLabel("Die Arbeiten eines Halbjahres zählen mit ihrem Gewicht (Einstellungen der Arbeit). "
                      "Mündliche Zeiträume zählen gleich. Vorschläge sind die nächstgelegene Note; "
                      "festgesetzt wird von dir.", objectName="leise")
        erkl.setWordWrap(True)
        form.addRow(erkl)
        self.meldung = Hinweis()
        form.addRow(self.meldung)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Speichern")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        form.addRow(box)

    def _ok(self) -> None:
        try:
            self.zg.setze_gewichtung(self.gruppe.id, None if self.automatisch.isChecked() else self.schriftlich.value(),
                                     self.hj1.value(), self.zp10.currentData())
        except ZeugnisFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.accept()


class NotenTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.zg: Zeugnis | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self.zeilen: list[Zeile] = []
        self._fuellt = False

        self.gewichtung_text = QLabel(objectName="leise")
        gewichtung = QPushButton("Gewichtung …")
        gewichtung.clicked.connect(self._gewichtung)
        self.uebernehmen = QToolButton()
        self.uebernehmen.setText("Vorschläge übernehmen ▾")
        self.uebernehmen.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.uebernehmen_menue = QMenu(self)
        self.uebernehmen.setMenu(self.uebernehmen_menue)
        oben = QHBoxLayout()
        oben.addWidget(self.gewichtung_text, 1)
        oben.addWidget(gewichtung)
        oben.addWidget(self.uebernehmen)

        self.tabelle = QTableWidget()
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setAlternatingRowColors(True)
        self.tabelle.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tabelle.setEditTriggers(QAbstractItemView.EditTrigger.AnyKeyPressed
                                     | QAbstractItemView.EditTrigger.DoubleClicked
                                     | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.tabelle.itemChanged.connect(self._geaendert)
        self.tabelle.horizontalHeader().setMinimumHeight(44)
        self.meldung = Hinweis()
        self.spiegel = QLabel()
        self.spiegel.setWordWrap(True)
        hilfe = QLabel("Fahre über einen Vorschlag, um die Herleitung zu sehen. In die fett gedruckten Spalten trägst "
                       "du die festgesetzte Note ein (z. B. 2 oder 2-); Entf löscht.", objectName="leise")
        hilfe.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(oben)
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(self.spiegel)
        lay.addWidget(hilfe)

    # ---- Anzeige ---------------------------------------------------------------------------------
    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        if self.sd is not sd or self.zg is None:
            self.sd, self.zg = sd, Zeugnis(sd.v)
        self.jahr, self.gruppe = jahr, sd.lerngruppe(gruppe.id)
        self.meldung.setze("")
        self._fuellen()

    def _spalten(self, zp10: bool) -> list[tuple[str, str, str | None]]:
        """(Überschrift, Inhalt, Art zum Festsetzen oder None)."""
        s = [("Nr.", "nr", None), ("Name", "name", None), ("Kl.", "klasse", None),
             ("1. Hj.\nschriftl.", "s1", None), ("1. Hj.\nmündl.", "m1", None), ("1. Hj.\nVorschlag", "v:hj1", None),
             ("1. Hj.\nZeugnis", "f:hj1", "hj1")]
        if zp10:
            s += [("Vornote\nVorschlag", "v:vornote", None), ("Vornote", "f:vornote", "vornote"),
                  ("ZP10", "f:zp10", "zp10"), ("Endnote\nVorschlag", "v:hj2", None), ("Endnote\nZeugnis", "f:hj2", "hj2")]
        else:
            s += [("2. Hj.\nschriftl.", "s2", None), ("2. Hj.\nmündl.", "m2", None),
                  ("2. Hj.\nVorschlag", "v:hj2", None), ("2. Hj.\nZeugnis", "f:hj2", "hj2")]
        return s

    def _fuellen(self) -> None:
        gw = self.zg.gewichtung(self.gruppe)
        self.zeilen = self.zg.zeilen(self.gruppe.id)
        teile = [f"schriftlich {gw.anteil_schriftlich:g} % / mündlich {100 - gw.anteil_schriftlich:g} %"]
        if gw.zp10:
            teile.append("ZP10-Fach: Vornote aus dem ganzen Jahr, Endnote = 50 % Vornote + 50 % ZP10")
        else:
            teile.append(f"1. Halbjahr zählt {gw.anteil_hj1:g} % zur Note des 2. Halbjahres")
        self.gewichtung_text.setText(" · ".join(teile))
        self._menue(gw.zp10)

        spalten = self._spalten(gw.zp10)
        farben = aktuelle_farben()
        fett = QFont()
        fett.setBold(True)
        self._fuellt = True
        self.tabelle.clear()
        self.tabelle.setColumnCount(len(spalten))
        self.tabelle.setHorizontalHeaderLabels([s[0] for s in spalten])
        self.tabelle.setRowCount(len(self.zeilen))
        for r, z in enumerate(self.zeilen):
            m = z.mitglied
            for c, (_, inhalt, art) in enumerate(spalten):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if inhalt != "name" else
                                      Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if inhalt == "nr":
                    item.setText(str(m.nummer))
                elif inhalt == "name":
                    item.setText(f"{m.schueler.nachname}, {m.schueler.vorname}")
                elif inhalt == "klasse":
                    item.setText(m.klasse)
                elif inhalt[0] in "sm" and inhalt[1:].isdigit():
                    t: Teilnote = (z.schriftlich if inhalt[0] == "s" else z.muendlich)[int(inhalt[1])]
                    item.setText(_z(t.wert))
                    item.setToolTip(t.herleitung)
                    item.setForeground(QBrush(QColor(farben.text_leise)))
                elif inhalt.startswith("v:"):
                    v: Vorschlag | None = z.vorschlag.get(inhalt[2:])
                    if v and v.note:
                        item.setText(f"{v.note.kurz}  ({_z(v.wert)})")
                    item.setToolTip("\n".join(v.herleitung) if v else "")
                elif inhalt.startswith("f:"):
                    n = z.fest.get(art)
                    item.setText(n.kurz if n else "")
                    item.setFont(fett)
                    item.setBackground(QBrush(QColor(farben.flaeche_hoch)))
                    item.setData(ROLLE_ART, art)
                    item.setData(ROLLE_SID, m.schueler.id)
                    v = z.vorschlag.get(art)
                    if n and v and v.wert is not None and abs(n.wert - v.wert) >= 1.0:
                        item.setForeground(QBrush(QColor(farben.warnung)))
                        item.setToolTip(f"Weicht deutlich vom Vorschlag ({v.note.kurz}) ab.")
                if not inhalt.startswith("f:"):
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tabelle.setItem(r, c, item)
        self._fuellt = False
        k = self.tabelle.horizontalHeader()
        k.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.tabelle.setColumnWidth(0, 34)
        self.tabelle.setColumnWidth(1, 190)
        self.tabelle.setColumnWidth(2, 42)
        for c in range(3, len(spalten)):
            self.tabelle.setColumnWidth(c, 84)
        self._spiegel(gw.zp10)

    def _spiegel(self, zp10: bool) -> None:
        teile = []
        for art, text in (("hj1", "1. Halbjahr"), ("hj2", "Endnote" if zp10 else "2. Halbjahr")):
            noten = [z.fest[art] for z in self.zeilen if art in z.fest]
            if noten:
                s = Notenspiegel.aus(noten)
                stufen = "  ".join(f"{k}: {v}" for k, v in s.anzahl.items())
                teile.append(f"<b>{text}</b> ({s.gesamt} festgesetzt): {stufen} · Schnitt {_z(s.schnitt)}"
                             f" · unter 4: {s.anteil_unter_4:.0f} %")
        self.spiegel.setText("<br>".join(teile) if teile else "Noch keine Zeugnisnoten festgesetzt.")

    def _menue(self, zp10: bool) -> None:
        self.uebernehmen_menue.clear()
        arten = [("hj1", "1. Halbjahr")] + ([("vornote", "Vornote"), ("hj2", "Endnote")] if zp10
                                            else [("hj2", "2. Halbjahr")])
        for art, text in arten:
            a = self.uebernehmen_menue.addAction(f"{text}: nur leere Felder")
            a.triggered.connect(lambda _=False, x=art: self._uebernehmen(x, True))
            b = self.uebernehmen_menue.addAction(f"{text}: alle (überschreibt Festgesetztes)")
            b.triggered.connect(lambda _=False, x=art: self._uebernehmen(x, False))
            self.uebernehmen_menue.addSeparator()

    # ---- Aktionen --------------------------------------------------------------------------------
    def _geaendert(self, item: QTableWidgetItem) -> None:
        if self._fuellt or item.data(ROLLE_ART) is None:
            return
        try:
            note = note_aus_eingabe(item.text())
        except MuendlichFehler as e:
            self.meldung.setze(str(e), "fehler")
            self._fuellen()
            return
        self.zg.setze(self.gruppe.id, item.data(ROLLE_SID), item.data(ROLLE_ART), note)
        self.meldung.setze("")
        zeile, spalte = item.row(), item.column()
        self._fuellen()
        self.tabelle.setCurrentCell(min(zeile + 1, self.tabelle.rowCount() - 1), spalte)
        self.geaendert.emit()

    def keyPressEvent(self, ereignis) -> None:  # noqa: N802
        if ereignis.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            item = self.tabelle.currentItem()
            if item is not None and item.data(ROLLE_ART) is not None:
                self.zg.setze(self.gruppe.id, item.data(ROLLE_SID), item.data(ROLLE_ART), None)
                self._fuellen()
                self.geaendert.emit()
                return
        super().keyPressEvent(ereignis)

    def _uebernehmen(self, art: str, nur_leere: bool) -> None:
        n = self.zg.uebernimm_vorschlaege(self.gruppe.id, art, nur_leere)
        self._fuellen()
        self.geaendert.emit()
        info(self, "Vorschläge übernommen", f"{n} Note(n) als ganze Noten festgesetzt. Du kannst jede einzeln ändern.")

    def _gewichtung(self) -> None:
        if GewichtungDialog(self.zg, self.gruppe, self).exec():
            self._fuellen()
            self.geaendert.emit()
