"""Reiter „Noten“: Quartals- und Halbjahresnoten in der Reihenfolge der Abgabe (Q1 – 1. Hj. – Q3 – 2. Hj.).

Je Abschnitt: schriftlicher und mündlicher Schnitt, Vorschlag mit Herleitung, festgesetzte Note.
Ansicht „Einzelnoten“: zusätzlich jede Arbeit und jeder mündliche Zeitraum vor dem Abschnitt, zu dem sie zählen.
"""

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
from notenverwaltung.modell.zeugnis import QUARTALE, Einzelnote, Teilnote, Vorschlag, Zeile, Zeugnis, ZeugnisFehler
from notenverwaltung.ui.bausteine import Hinweis, aktuelle_farben, info

ROLLE_ART = Qt.ItemDataRole.UserRole + 1
ROLLE_SID = Qt.ItemDataRole.UserRole + 2
ROLLE_EINZEL = Qt.ItemDataRole.UserRole + 3
BREITE_EINZEL = 72
BREITE_ABSCHNITT = 84


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
        self._einzel: list = []
        self._einzelwerte: dict = {}
        self._fuellt = False

        self.gewichtung_text = QLabel(objectName="leise")
        gewichtung = QPushButton("Gewichtung …")
        gewichtung.clicked.connect(self._gewichtung)
        self.uebernehmen = QToolButton()
        self.uebernehmen.setText("Vorschläge übernehmen ▾")
        self.uebernehmen.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.uebernehmen_menue = QMenu(self)
        self.uebernehmen.setMenu(self.uebernehmen_menue)
        self.zeitraum = QComboBox()
        self.zeitraum.addItem("ganzes Schuljahr", None)
        self.zeitraum.addItem("1. Halbjahr (Q1 und 1. Hj.)", 1)
        self.zeitraum.addItem("2. Halbjahr (Q3 und 2. Hj.)", 2)
        self.zeitraum.setToolTip("Welche Abschnitte gezeigt werden")
        self._zeitraum_gewaehlt = False
        self.zeitraum.activated.connect(lambda: setattr(self, "_zeitraum_gewaehlt", True))
        self.zeitraum.currentIndexChanged.connect(lambda: self.gruppe and self._fuellen())
        self.ansicht = QComboBox()
        self.ansicht.addItem("zusammengefasst", False)
        self.ansicht.addItem("mit Einzelnoten", True)
        self.ansicht.setToolTip("Mit Einzelnoten: jede Arbeit und jeder mündliche Zeitraum als eigene Spalte, "
                                "jeweils vor der Note, zu der sie zählen")
        self.ansicht.currentIndexChanged.connect(lambda: self.gruppe and self._fuellen())
        auswahl = QHBoxLayout()
        auswahl.addWidget(QLabel("Zeitraum:"))
        auswahl.addWidget(self.zeitraum)
        auswahl.addWidget(QLabel("Ansicht:"))
        auswahl.addWidget(self.ansicht)
        auswahl.addWidget(self.gewichtung_text, 1)
        oben = QHBoxLayout()
        oben.addStretch(1)
        oben.addWidget(gewichtung)
        oben.addWidget(self.uebernehmen)
        drucken = QPushButton("Drucken / PDF …")
        drucken.clicked.connect(self.drucken)
        oben.addWidget(drucken)

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
        lay.addLayout(auswahl)
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
        if not self._zeitraum_gewaehlt:   # Standard: das laufende Halbjahr
            from datetime import date

            heute = date.today()
            h = jahr.halbjahr(heute) if jahr.enthaelt(heute) else None
            self.zeitraum.blockSignals(True)
            self.zeitraum.setCurrentIndex(self.zeitraum.findData(h))
            self.zeitraum.blockSignals(False)
        self._fuellen()

    def _spalten(self, zp10: bool) -> list[tuple[str, str, str | None]]:
        """(Überschrift, Inhalt, Art zum Festsetzen oder None) in der Reihenfolge der Abgabe."""
        s = [("Nr.", "nr", None), ("Name", "name", None), ("Kl.", "klasse", None)]
        halbjahre = (1, 2) if self.zeitraum.currentData() is None else (self.zeitraum.currentData(),)
        einzeln = self.ansicht.currentData()
        for h in halbjahre:
            q = 2 * h - 1   # 1 bzw. 3
            for e in self._einzel if einzeln else []:
                if e.quartal == q:
                    s.append(self._einzelkopf(e))
            s += [(f"Q{q}\nschriftl.", f"sq:{q}", None), (f"Q{q}\nmündl.", f"mq:{q}", None),
                  (f"Q{q}\nVorschlag", f"v:q{q}", None), (f"Q{q}\nNote", f"f:q{q}", f"q{q}")]
            for e in self._einzel if einzeln else []:
                if e.quartal == q + 1:
                    s.append(self._einzelkopf(e))
            if h == 2 and zp10:
                s += [("Vornote\nVorschlag", "v:vornote", None), ("Vornote", "f:vornote", "vornote"),
                      ("ZP10", "f:zp10", "zp10"), ("Endnote\nVorschlag", "v:hj2", None),
                      ("Endnote\nZeugnis", "f:hj2", "hj2")]
            else:
                s += [(f"{h}. Hj.\nschriftl.", f"s{h}", None), (f"{h}. Hj.\nmündl.", f"m{h}", None),
                      (f"{h}. Hj.\nVorschlag", f"v:hj{h}", None), (f"{h}. Hj.\nZeugnis", f"f:hj{h}", f"hj{h}")]
        return s

    @staticmethod
    def _einzelkopf(e) -> tuple[str, str, None]:
        titel = e.titel if len(e.titel) <= 10 else e.titel[:9].rstrip() + "…"
        datum = f"{e.von:%d.%m.}" if e.art == "arbeit" else f"mdl. {e.von:%d.%m.}"
        return (f"{titel}\n{datum}", f"e:{e.schluessel}", None)

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
        self._einzel, self._einzelwerte = (self.zg.einzelnoten(self.gruppe.id) if self.ansicht.currentData()
                                           else ([], {}))
        titel = {f"e:{e.schluessel}": e for e in self._einzel}

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
                elif inhalt[0] in "sm" and (inhalt[1:].isdigit() or inhalt[1:3] == "q:"):
                    if inhalt[1:3] == "q:":
                        t: Teilnote = (z.quartal_s if inhalt[0] == "s" else z.quartal_m)[int(inhalt[3:])]
                    else:
                        t = (z.schriftlich if inhalt[0] == "s" else z.muendlich)[int(inhalt[1])]
                    item.setText(_z(t.wert))
                    item.setToolTip(t.herleitung)
                    item.setForeground(QBrush(QColor(farben.text_leise)))
                elif inhalt.startswith("e:"):
                    e: Einzelnote | None = self._einzelwerte.get((inhalt[2:], m.schueler.id))
                    sp = titel[inhalt]
                    if e:
                        item.setText(e.text)
                        item.setToolTip(f"{sp.titel}: {e.hinweis}" if e.hinweis else sp.titel)
                        if e.leise:
                            item.setForeground(QBrush(QColor(farben.text_leise)))
                    item.setData(ROLLE_EINZEL, True)
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
            self.tabelle.setColumnWidth(c, BREITE_EINZEL if spalten[c][1].startswith("e:") else BREITE_ABSCHNITT)
            if spalten[c][1].startswith("e:"):
                sp = titel[spalten[c][1]]
                kopf = self.tabelle.horizontalHeaderItem(c)
                kopf.setToolTip(f"{sp.titel} ({sp.von:%d.%m.%Y}" + (f"–{sp.bis:%d.%m.%Y}" if sp.bis else "") + ")"
                                + ("" if sp.zaehlt else " – zählt nicht"))
        self._spiegel(gw.zp10)

    def _spiegel(self, zp10: bool) -> None:
        teile = []
        arten = [("q1", "1. Quartal"), ("hj1", "1. Halbjahr"), ("q3", "3. Quartal"),
                 ("hj2", "Endnote" if zp10 else "2. Halbjahr")]
        h = self.zeitraum.currentData()
        if h is not None:
            arten = arten[:2] if h == 1 else arten[2:]
        for art, text in arten:
            noten = [z.fest[art] for z in self.zeilen if art in z.fest]
            if noten:
                s = Notenspiegel.aus(noten)
                stufen = "  ".join(f"{k}: {v}" for k, v in s.anzahl.items())
                teile.append(f"<b>{text}</b> ({s.gesamt} festgesetzt): {stufen} · Schnitt {_z(s.schnitt)}"
                             f" · unter 4: {s.anteil_unter_4:.0f} %")
        self.spiegel.setText("<br>".join(teile) if teile else "Noch keine Zeugnisnoten festgesetzt.")

    def _menue(self, zp10: bool) -> None:
        self.uebernehmen_menue.clear()
        arten = [("q1", "1. Quartal (mit Tendenz)"), ("hj1", "1. Halbjahr"), ("q3", "3. Quartal (mit Tendenz)")] + (
            [("vornote", "Vornote"), ("hj2", "Endnote")] if zp10 else [("hj2", "2. Halbjahr")])
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
        art_text = "mit Tendenz" if art in QUARTALE else "als ganze Noten"
        info(self, "Vorschläge übernommen", f"{n} Note(n) {art_text} festgesetzt. Du kannst jede einzeln ändern.")

    def drucken(self) -> None:
        from notenverwaltung.ausgabe.notenuebersicht import Notenuebersicht, UebersichtOptionen
        from notenverwaltung.ui.vorschau_dialog import VorschauDialog

        optionen = QWidget()
        form = QFormLayout(optionen)
        form.setContentsMargins(0, 0, 0, 0)
        zeitraum = QComboBox()
        zeitraum.addItem("ganzes Schuljahr", None)
        zeitraum.addItem("1. Halbjahr", 1)
        zeitraum.addItem("2. Halbjahr", 2)
        form.addRow("Zeitraum:", zeitraum)
        haken = {}
        zeitraum.setCurrentIndex(zeitraum.findData(self.zeitraum.currentData()))
        for k, text, an in (("quartale", "Quartalsnoten (Q1, Q3)", True), ("vorschlaege", "Vorschläge zeigen", True),
                            ("leere_ausblenden", "Leere Zeilen ausblenden", False),
                            ("zebra", "Zeilen abwechselnd tönen", True), ("notenspiegel", "Notenspiegel", True)):
            c = QCheckBox(text)
            c.setChecked(an)
            form.addRow(c)
            haken[k] = c

        def baue():
            return Notenuebersicht(self.zg, self.gruppe.id, UebersichtOptionen(
                halbjahr=zeitraum.currentData(), **{k: c.isChecked() for k, c in haken.items()}))

        d = VorschauDialog(f"Notenübersicht – {self.gruppe.bezeichnung}", baue, optionen, self.sd.v,
                           f"Notenübersicht {self.gruppe.bezeichnung} {self.jahr.bezeichnung.replace('/', '-')}.pdf",
                           self)
        zeitraum.currentIndexChanged.connect(d.aktualisieren)
        for c in haken.values():
            c.toggled.connect(d.aktualisieren)
        d.aktualisieren()
        self._druckdialog = d  # für Tests erreichbar
        d.exec()

    def _gewichtung(self) -> None:
        if GewichtungDialog(self.zg, self.gruppe, self).exec():
            self._fuellen()
            self.geaendert.emit()
