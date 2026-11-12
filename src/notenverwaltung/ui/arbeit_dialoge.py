"""Dialoge für Klassenarbeiten: Arbeit anlegen/bearbeiten mit Aufgaben, Notenschlüssel."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from PySide6.QtCore import Qt
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
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.arbeiten import Arbeit, ArbeitFehler, Arbeiten
from notenverwaltung.modell.noten import ALLE_NOTEN, Note, Notenschluessel, zahl, zahl_text
from notenverwaltung.modell.stammdaten import Lerngruppe, Schuljahr
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, OptionalesDatum, frage


# ---- Aufgaben-Editor -----------------------------------------------------------------------------

class AufgabenEditor(QWidget):
    """Tabelle der Aufgaben: Bezeichnung, Höchstpunkte, Thema. Schnelle Knöpfe für Aufgabe/Teilaufgabe."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tabelle = QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["Aufgabe", "Punkte", "Thema (für den Rückmeldebogen)"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabelle.setColumnWidth(0, 80)
        self.tabelle.setColumnWidth(1, 70)
        self.tabelle.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabelle.itemChanged.connect(self._summe)
        knoepfe = QHBoxLayout()
        for text, slot in (("＋ Aufgabe", self.neue_aufgabe), ("＋ Teilaufgabe", self.neue_teilaufgabe),
                           ("▲", lambda: self._schiebe(-1)), ("▼", lambda: self._schiebe(1)),
                           ("Entfernen", self._entfernen)):
            k = QPushButton(text)
            k.clicked.connect(slot)
            knoepfe.addWidget(k)
        knoepfe.addStretch(1)
        self.gesamt = QLabel(objectName="leise")
        knoepfe.addWidget(self.gesamt)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(knoepfe)
        lay.addWidget(self.tabelle, 1)

    # Zeilendaten: (id oder None, bezeichnung, punkte, thema, erwartung)
    def setze(self, zeilen: list[tuple]) -> None:
        self.tabelle.blockSignals(True)
        self.tabelle.setRowCount(0)
        for z in zeilen:
            self._zeile(*z)
        self.tabelle.blockSignals(False)
        self._summe()

    def _zeile(self, aid, bez, punkte, thema="", erwartung="", zeile: int | None = None) -> None:
        r = self.tabelle.rowCount() if zeile is None else zeile
        self.tabelle.insertRow(r)
        a = QTableWidgetItem(str(bez))
        a.setData(Qt.ItemDataRole.UserRole, (aid, erwartung))
        self.tabelle.setItem(r, 0, a)
        p = QTableWidgetItem(zahl_text(punkte))
        p.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tabelle.setItem(r, 1, p)
        self.tabelle.setItem(r, 2, QTableWidgetItem(thema))

    def zeilen(self) -> list[tuple]:
        """Liest die Tabelle; wirft ArbeitFehler bei ungültigen Punkten."""
        ergebnis = []
        for r in range(self.tabelle.rowCount()):
            bez = (self.tabelle.item(r, 0).text() if self.tabelle.item(r, 0) else "").strip()
            aid, erwartung = self.tabelle.item(r, 0).data(Qt.ItemDataRole.UserRole) or (None, "")
            text = self.tabelle.item(r, 1).text() if self.tabelle.item(r, 1) else ""
            try:
                punkte = zahl(text)
            except ValueError:
                raise ArbeitFehler(f"Aufgabe {bez or r + 1}: „{text}“ ist keine Punktzahl.") from None
            if punkte is None:
                raise ArbeitFehler(f"Aufgabe {bez or r + 1}: Bitte die Höchstpunktzahl angeben.")
            thema = self.tabelle.item(r, 2).text() if self.tabelle.item(r, 2) else ""
            ergebnis.append((aid, bez, punkte, thema, erwartung))
        return ergebnis

    def _summe(self, *_) -> None:
        summe = 0.0
        for r in range(self.tabelle.rowCount()):
            try:
                summe += zahl(self.tabelle.item(r, 1).text() if self.tabelle.item(r, 1) else "") or 0
            except ValueError:
                pass
        self.gesamt.setText(f"Gesamt: {zahl_text(summe)} Punkte")

    def _bezeichnungen(self) -> list[str]:
        return [self.tabelle.item(r, 0).text() for r in range(self.tabelle.rowCount()) if self.tabelle.item(r, 0)]

    def neue_aufgabe(self) -> None:
        nummern = [int(m.group(1)) for b in self._bezeichnungen() if (m := re.match(r"(\d+)", b))]
        self._zeile(None, str(max(nummern, default=0) + 1), 1)
        self._summe()
        self.tabelle.setCurrentCell(self.tabelle.rowCount() - 1, 1)

    def neue_teilaufgabe(self) -> None:
        """„3“ → „3a“ + „b“; „3a“/„b“ → nächster Buchstabe (Schreibweise wie in der Punkteliste)."""
        if self.tabelle.rowCount() == 0:
            self._zeile(None, "1a", 1)
            self._summe()
            return
        letzte = self.tabelle.item(self.tabelle.rowCount() - 1, 0)
        text = letzte.text().strip()
        m = re.fullmatch(r"(\d*)([a-z]?)", text)
        if m and m.group(1) and not m.group(2):
            letzte.setText(text + "a")
            neu = "b"
        elif m and m.group(2):
            neu = chr(ord(m.group(2)) + 1) if m.group(2) < "z" else "z"
        else:
            neu = text + "'"
        self._zeile(None, neu, 1)
        self._summe()
        self.tabelle.setCurrentCell(self.tabelle.rowCount() - 1, 1)

    def _schiebe(self, schritt: int) -> None:
        r = self.tabelle.currentRow()
        ziel = r + schritt
        if r < 0 or not 0 <= ziel < self.tabelle.rowCount():
            return
        werte = [self.tabelle.takeItem(r, c) for c in range(3)]
        self.tabelle.removeRow(r)
        self.tabelle.insertRow(ziel)
        for c, item in enumerate(werte):
            self.tabelle.setItem(ziel, c, item)
        self.tabelle.setCurrentCell(ziel, 0)

    def _entfernen(self) -> None:
        r = self.tabelle.currentRow()
        if r >= 0:
            self.tabelle.removeRow(r)
            self._summe()


# ---- Notenschlüssel ------------------------------------------------------------------------------

class SchluesselDialog(QDialog):
    """Prozenttabelle bearbeiten, Punktgrenzen live sehen, Vorlagen laden/speichern."""

    def __init__(self, ar: Arbeiten, schluessel: Notenschluessel, hoechstpunkte: float,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar = ar
        self.hoechstpunkte = hoechstpunkte
        self.ergebnis: Notenschluessel | None = None
        self.setWindowTitle("Notenschlüssel")
        self.setMinimumSize(520, 620)

        self.vorlage = QComboBox()
        self._vorlagen_fuellen()
        laden = QPushButton("Laden")
        laden.clicked.connect(self._laden)
        oben = QHBoxLayout()
        oben.addWidget(QLabel("Vorlage:"))
        oben.addWidget(self.vorlage, 1)
        oben.addWidget(laden)

        self.tabelle = QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["ab Prozent", "Note", f"ab Punkten (von {zahl_text(hoechstpunkte)})"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.raster = QComboBox()
        for r, text in ((1.0, "ganze Punkte"), (0.5, "halbe Punkte"), (0.25, "Viertelpunkte")):
            self.raster.addItem(text, r)
        self.raster.currentIndexChanged.connect(self._vorschau)
        zeile_knoepfe = QHBoxLayout()
        plus = QPushButton("＋ Stufe")
        plus.clicked.connect(lambda: self._zeile(50, Note.aus_kurz("4")))
        minus = QPushButton("Stufe entfernen")
        minus.clicked.connect(lambda: self.tabelle.removeRow(self.tabelle.currentRow()))
        zeile_knoepfe.addWidget(plus)
        zeile_knoepfe.addWidget(minus)
        zeile_knoepfe.addStretch(1)
        zeile_knoepfe.addWidget(QLabel("Punktgrenzen runden auf:"))
        zeile_knoepfe.addWidget(self.raster)

        self.meldung = Hinweis()
        speichern = QPushButton("Als Vorlage speichern …")
        speichern.clicked.connect(self._als_vorlage)
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Übernehmen")
        knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        knoepfe.addButton(speichern, QDialogButtonBox.ButtonRole.ActionRole)
        knoepfe.accepted.connect(self._ok)
        knoepfe.rejected.connect(self.reject)

        erklaerung = QLabel("Wer mindestens den angegebenen Anteil der Punkte erreicht, bekommt die Note. "
                            "Die Punktgrenzen werden wie in der Punkteliste gerundet.", objectName="leise")
        erklaerung.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addLayout(oben)
        lay.addWidget(erklaerung)
        lay.addWidget(self.tabelle, 1)
        lay.addLayout(zeile_knoepfe)
        lay.addWidget(self.meldung)
        lay.addWidget(knoepfe)
        self._setze(schluessel)

    def _vorlagen_fuellen(self) -> None:
        self.vorlage.clear()
        for v in self.ar.vorlagen():
            self.vorlage.addItem(v.name + ("  (Standard)" if v.standard else ""), v.schluessel)

    def _laden(self) -> None:
        if self.vorlage.currentData():
            self._setze(self.vorlage.currentData())

    def _setze(self, k: Notenschluessel) -> None:
        self.tabelle.setRowCount(0)
        for s in k.stufen:
            self._zeile(s.prozent, s.note)
        self.raster.setCurrentIndex(max(0, self.raster.findData(k.raster)))
        self._vorschau()

    def _zeile(self, prozent: float, note: Note) -> None:
        r = self.tabelle.rowCount()
        self.tabelle.insertRow(r)
        spin = QDoubleSpinBox()
        spin.setRange(0, 200)
        spin.setDecimals(1)
        spin.setSuffix(" %")
        spin.setValue(prozent)
        spin.valueChanged.connect(self._vorschau)
        self.tabelle.setCellWidget(r, 0, spin)
        combo = QComboBox()
        for n in ALLE_NOTEN:
            combo.addItem(f"{n.kurz}  ({n.wort_mit_tendenz})", n.kurz)
        combo.setCurrentIndex(combo.findData(note.kurz))
        combo.currentIndexChanged.connect(self._vorschau)
        self.tabelle.setCellWidget(r, 1, combo)
        punkte = QTableWidgetItem()
        punkte.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.tabelle.setItem(r, 2, punkte)

    def schluessel(self) -> Notenschluessel:
        paare = [(self.tabelle.cellWidget(r, 0).value(), self.tabelle.cellWidget(r, 1).currentData())
                 for r in range(self.tabelle.rowCount())]
        return Notenschluessel.aus_liste(paare, self.raster.currentData())

    def _vorschau(self, *_) -> None:
        try:
            k = self.schluessel()
        except ValueError as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.meldung.setze("")
        grenzen = {s.prozent: g for s, (g, _) in zip(k.stufen, k.grenzen(self.hoechstpunkte))}
        for r in range(self.tabelle.rowCount()):
            p = self.tabelle.cellWidget(r, 0).value()
            g = grenzen.get(p)
            text = "—" if g is None else (zahl_text(g) if g <= self.hoechstpunkte else f"{zahl_text(g)} (nicht erreichbar)")
            self.tabelle.item(r, 2).setText(text)

    def _als_vorlage(self) -> None:
        try:
            k = self.schluessel()
        except ValueError as e:
            self.meldung.setze(str(e), "fehler")
            return
        name, ok = QInputDialog.getText(self, "Als Vorlage speichern", "Name der Vorlage:")
        if not ok or not name.strip():
            return
        standard = frage(self, "Standard", f"Soll „{name}“ der Standard für neue Arbeiten werden?",
                         ja="Ja, als Standard", nein="Nein")
        try:
            self.ar.speichere_vorlage(name, k, standard)
        except ArbeitFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self._vorlagen_fuellen()
        self.meldung.setze(f"Vorlage „{name}“ gespeichert.", "ok")

    def _ok(self) -> None:
        try:
            self.ergebnis = self.schluessel()
        except ValueError as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.accept()


# ---- Arbeit anlegen / bearbeiten -----------------------------------------------------------------

class ArbeitDialog(QDialog):
    def __init__(self, ar: Arbeiten, jahr: Schuljahr, gruppe: Lerngruppe, arbeit: Arbeit | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar, self.jahr, self.gruppe, self.alt = ar, jahr, gruppe, arbeit
        self.ergebnis: Arbeit | None = None
        self.setWindowTitle("Arbeit bearbeiten" if arbeit else "Neue Klassenarbeit")
        self.setMinimumSize(620, 640)
        self.schluessel = arbeit.schluessel if arbeit else ar.standard_schluessel()

        heute = date.today() if jahr.enthaelt(date.today()) else jahr.beginn
        self.titel = QLineEdit(arbeit.titel if arbeit else ar.titel_vorschlag(gruppe.id))
        self.datum = Datumsfeld(arbeit.datum if arbeit else heute)
        self.datum.begrenze(jahr.beginn, jahr.ende)
        self.rueckgabe = OptionalesDatum("Datum für die Notenabschnitte:", arbeit.rueckgabe if arbeit else None,
                                         vorgabe=heute)
        self.rueckgabe.datum.begrenze(jahr.beginn, jahr.ende)
        self.thema = QLineEdit(arbeit.thema if arbeit else "")
        self.thema.setPlaceholderText("z. B. Lineare Funktionen")
        self.zaehlt = QCheckBox("zählt zur Note (sonst z. B. Übungsarbeit)")
        self.zaehlt.setChecked(arbeit.zaehlt if arbeit else True)
        self.schluessel_text = QLabel(objectName="leise")
        schluessel_knopf = QPushButton("Notenschlüssel …")
        schluessel_knopf.clicked.connect(self._schluessel)
        sz = QHBoxLayout()
        sz.addWidget(self.schluessel_text, 1)
        sz.addWidget(schluessel_knopf)

        form = QFormLayout()
        form.addRow("Titel:", self.titel)
        form.addRow("Geschrieben am:", self.datum)
        form.addRow("", self.rueckgabe)
        form.addRow("Thema:", self.thema)
        form.addRow("", self.zaehlt)
        form.addRow("Notenschlüssel:", sz)

        self.aufgaben = AufgabenEditor()
        if arbeit:
            self.aufgaben.setze([(a.id, a.bezeichnung, a.max_punkte, a.thema, a.erwartung)
                                 for a in ar.aufgaben(arbeit.id)])
        else:
            self.aufgaben.setze([(None, str(i), 5, "", "") for i in range(1, 5)])

        self.meldung = Hinweis()
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Speichern" if arbeit else "Anlegen")
        knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        knoepfe.accepted.connect(self._ok)
        knoepfe.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(QLabel("<b>Aufgaben</b>"))
        lay.addWidget(self.aufgaben, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(knoepfe)
        self._schluessel_anzeigen()

    def _schluessel_anzeigen(self) -> None:
        vorlage = next((v.name for v in self.ar.vorlagen() if v.schluessel == self.schluessel), None)
        self.schluessel_text.setText(vorlage or "angepasst")

    def _schluessel(self) -> None:
        try:
            maximum = sum(z[2] for z in self.aufgaben.zeilen())
        except ArbeitFehler:
            maximum = 0
        d = SchluesselDialog(self.ar, self.schluessel, maximum or 100, self)
        if d.exec() and d.ergebnis:
            self.schluessel = d.ergebnis
            self._schluessel_anzeigen()

    def _ok(self) -> None:
        try:
            zeilen = self.aufgaben.zeilen()
            if not zeilen:
                raise ArbeitFehler("Bitte mindestens eine Aufgabe anlegen.")
            for _, bez, punkte, _, _ in zeilen:
                if not bez:
                    raise ArbeitFehler("Jede Aufgabe braucht eine Bezeichnung.")
                if punkte < 0:
                    raise ArbeitFehler(f"Aufgabe {bez}: Die Höchstpunktzahl darf nicht negativ sein.")
            if self.alt is None:
                a = self.ar.lege_arbeit_an(self.gruppe.id, self.titel.text(), self.datum.wert(),
                                           schluessel=self.schluessel, rueckgabe=self.rueckgabe.wert(),
                                           thema=self.thema.text().strip())
                if not self.zaehlt.isChecked():
                    self.ar.aendere_arbeit(replace(a, zaehlt=False))
            else:
                a = replace(self.alt, titel=self.titel.text(), datum=self.datum.wert(), rueckgabe=self.rueckgabe.wert(),
                            thema=self.thema.text().strip(), zaehlt=self.zaehlt.isChecked(), schluessel=self.schluessel)
                self.ar.setze_aufgaben(a.id, zeilen)  # zuerst: prüft auch vorhandene Punkte gegen neue Höchstwerte
                self.ar.aendere_arbeit(a)
            if self.alt is None:
                self.ar.setze_aufgaben(a.id, zeilen)
        except ArbeitFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.ergebnis = self.ar.arbeit(a.id)
        self.accept()
