"""Assistent „Schüler:innen importieren“: Datei → Spalten zuordnen → Abgleich prüfen → übernehmen."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from notenverwaltung.modell.importieren import (
    AKTIONEN,
    FELDER,
    Abgleich,
    ImportFehler,
    Zuordnung,
    datensaetze,
    erkenne,
    fuehre_aus,
    gleiche_ab,
)
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten
from notenverwaltung.modell.tabellen import TabellenFehler, blaetter, lies_tabelle
from notenverwaltung.ui.bausteine import Hinweis, OptionalesDatum, fehler, info

DATEIFILTER = ("Tabellen (*.csv *.txt *.xlsx *.ods);;CSV/Text (*.csv *.txt);;Excel (*.xlsx);;"
               "OpenDocument (*.ods);;Alle Dateien (*)")


def _fuelle_tabelle(t: QTableWidget, zeilen: list[list[str]], kopf: list[str] | None = None, max_zeilen: int = 200):
    zeilen = zeilen[:max_zeilen]
    breite = max((len(z) for z in zeilen), default=0)
    t.clear()
    t.setRowCount(len(zeilen))
    t.setColumnCount(len(kopf) if kopf else breite)
    if kopf:
        t.setHorizontalHeaderLabels(kopf)
    else:
        t.setHorizontalHeaderLabels([f"Spalte {i + 1}" for i in range(breite)])
    for r, z in enumerate(zeilen):
        for c, w in enumerate(z):
            t.setItem(r, c, QTableWidgetItem(w))
    t.resizeColumnsToContents()


def _vorschau_tabelle() -> QTableWidget:
    t = QTableWidget()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    return t


class SeiteDatei(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Datei wählen")
        self.setSubTitle("CSV-, Excel- (.xlsx) oder OpenDocument-Tabelle (.ods), z. B. ein Export aus SchILD-NRW oder Untis.")
        self.pfad: Path | None = None
        self.zeilen: list[list[str]] = []
        waehlen = QPushButton("Datei wählen …", objectName="primaer")
        waehlen.clicked.connect(self._waehlen)
        self.name = QLabel(objectName="leise")
        self.blatt = QComboBox()
        self.blatt.currentIndexChanged.connect(self._laden)
        self.blatt_label = QLabel("Tabellenblatt:")
        oben = QHBoxLayout()
        oben.addWidget(waehlen)
        oben.addWidget(self.name, 1)
        oben.addWidget(self.blatt_label)
        oben.addWidget(self.blatt)
        self.tabelle = _vorschau_tabelle()
        self.meldung = Hinweis()
        lay = QVBoxLayout(self)
        lay.addLayout(oben)
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(self.meldung)
        self.blatt_label.setVisible(False)
        self.blatt.setVisible(False)

    def _waehlen(self) -> None:
        pfad, _ = QFileDialog.getOpenFileName(self, "Schülerliste öffnen", "", DATEIFILTER)
        if pfad:
            self.lade_datei(Path(pfad))

    def lade_datei(self, pfad: Path) -> None:
        self.pfad = Path(pfad)
        self.name.setText(self.pfad.name)
        namen = blaetter(self.pfad)
        self.blatt.blockSignals(True)
        self.blatt.clear()
        self.blatt.addItems(namen)
        self.blatt.blockSignals(False)
        self.blatt.setVisible(len(namen) > 1)
        self.blatt_label.setVisible(len(namen) > 1)
        self._laden()

    def _laden(self, *_) -> None:
        if self.pfad is None:
            return
        try:
            self.zeilen = lies_tabelle(self.pfad, max(0, self.blatt.currentIndex()))
        except (TabellenFehler, OSError) as e:
            self.zeilen = []
            self.meldung.setze(str(e), "fehler")
        else:
            self.meldung.setze(f"{len(self.zeilen)} Zeilen gelesen." if self.zeilen else "Die Tabelle ist leer.",
                               "info" if self.zeilen else "fehler")
        _fuelle_tabelle(self.tabelle, self.zeilen)
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        return bool(self.zeilen)


class SeiteSpalten(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Spalten zuordnen")
        self.setSubTitle("Die Zuordnung wurde vorgeschlagen. Bitte prüfen und bei Bedarf ändern.")
        self.zuordnung = Zuordnung()
        self.combos: dict[str, QComboBox] = {}
        raster = QGridLayout()
        for i, (feld, text) in enumerate(FELDER.items()):
            c = QComboBox()
            c.currentIndexChanged.connect(self._geaendert)
            self.combos[feld] = c
            raster.addWidget(QLabel(text + ":"), i // 2, (i % 2) * 2)
            raster.addWidget(c, i // 2, (i % 2) * 2 + 1)
        self.kopfzeile = QCheckBox("Erste Zeile enthält Überschriften")
        self.kopfzeile.toggled.connect(self._geaendert)
        self.feste_klasse = QLineEdit()
        self.feste_klasse.setPlaceholderText("z. B. 9.3 – nur nötig, wenn die Datei keine Klassenspalte hat")
        self.feste_klasse.textChanged.connect(self._geaendert)
        form = QFormLayout()
        form.addRow(self.kopfzeile)
        form.addRow("Klasse für alle:", self.feste_klasse)
        self.tabelle = _vorschau_tabelle()
        self.meldung = Hinweis()
        lay = QVBoxLayout(self)
        lay.addLayout(raster)
        lay.addLayout(form)
        lay.addWidget(QLabel("<b>Vorschau</b>"))
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(self.meldung)

    def initializePage(self) -> None:  # noqa: N802
        zeilen = self.wizard().seite_datei.zeilen
        self.zuordnung = erkenne(zeilen)
        breite = max((len(z) for z in zeilen), default=0)
        kopf = zeilen[0] if zeilen else []
        for feld, c in self.combos.items():
            c.blockSignals(True)
            c.clear()
            c.addItem("— nicht vorhanden —", None)
            for i in range(breite):
                beispiel = kopf[i] if i < len(kopf) else ""
                c.addItem(f"Spalte {i + 1}: {beispiel[:24]}", i)
            c.setCurrentIndex(max(0, c.findData(self.zuordnung.spalten.get(feld))))
            c.blockSignals(False)
        self.kopfzeile.blockSignals(True)
        self.kopfzeile.setChecked(self.zuordnung.kopfzeile)
        self.kopfzeile.blockSignals(False)
        self._geaendert()

    def _geaendert(self, *_) -> None:
        z = Zuordnung({f: c.currentData() for f, c in self.combos.items()}, self.kopfzeile.isChecked(),
                      self.feste_klasse.text())
        self.zuordnung = z
        try:
            saetze = datensaetze(self.wizard().seite_datei.zeilen if self.wizard() else [], z)
        except ImportFehler as e:
            self.meldung.setze(str(e), "warnung")
            self.tabelle.setRowCount(0)
            self.completeChanged.emit()
            return
        fehlerhaft = sum(1 for s in saetze if s.fehler)
        self.meldung.setze(f"{len(saetze)} Einträge" + (f", davon {fehlerhaft} mit Fehlern (werden übersprungen)"
                                                        if fehlerhaft else ""), "warnung" if fehlerhaft else "ok")
        _fuelle_tabelle(self.tabelle, [[s.nachname, s.vorname, s.klasse, str(s.jahrgang or ""),
                                        s.geburtsdatum.strftime("%d.%m.%Y") if s.geburtsdatum else "",
                                        s.extern_id or "", s.fehler] for s in saetze],
                        ["Nachname", "Vorname", "Klasse", "Jg.", "Geburtsdatum", "ID", "Problem"])
        self.completeChanged.emit()

    def isComplete(self) -> bool:  # noqa: N802
        try:
            self.zuordnung.pruefe()
            return True
        except ImportFehler:
            return False


class SeiteAbgleich(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Abgleich prüfen")
        self.setSubTitle("So werden die Einträge übernommen. Die Aktion lässt sich je Zeile ändern.")
        self.abgleich: list[Abgleich] = []
        self.tabelle = QTableWidget()
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setAlternatingRowColors(True)
        self.tabelle.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.zugang = OptionalesDatum("Zugang im laufenden Schuljahr am")
        self.lerngruppe = QComboBox()
        self.zusammenfassung = QLabel()
        form = QFormLayout()
        form.addRow("", self.zugang)
        form.addRow("Zusätzlich aufnehmen in:", self.lerngruppe)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle, 1)
        lay.addLayout(form)
        lay.addWidget(self.zusammenfassung)

    def initializePage(self) -> None:  # noqa: N802
        a: ImportAssistent = self.wizard()
        saetze = datensaetze(a.seite_datei.zeilen, a.seite_spalten.zuordnung)
        self.abgleich = gleiche_ab(a.sd, a.jahr.id, saetze)
        heute = date.today() if a.jahr.enthaelt(date.today()) else a.jahr.beginn
        self.zugang.datum.setze(heute)
        self.zugang.datum.begrenze(a.jahr.beginn, a.jahr.ende)
        self.lerngruppe.clear()
        self.lerngruppe.addItem("— keine —", None)
        for g in a.sd.lerngruppen(a.jahr.id):
            self.lerngruppe.addItem(g.bezeichnung, g.id)
        self.lerngruppe.setCurrentIndex(max(0, self.lerngruppe.findData(a.lerngruppe_id)))

        kopf = ["Zeile", "Nachname", "Vorname", "Klasse", "Geburtsdatum", "Aktion", "Hinweis"]
        self.tabelle.clear()
        self.tabelle.setColumnCount(len(kopf))
        self.tabelle.setHorizontalHeaderLabels(kopf)
        self.tabelle.setRowCount(len(self.abgleich))
        for r, x in enumerate(self.abgleich):
            s = x.satz
            for c, w in enumerate([str(s.zeile), s.nachname, s.vorname, s.klasse,
                                   s.geburtsdatum.strftime("%d.%m.%Y") if s.geburtsdatum else ""]):
                self.tabelle.setItem(r, c, QTableWidgetItem(w))
            combo = QComboBox()
            for aktion in x.moegliche_aktionen:
                combo.addItem(AKTIONEN[aktion], aktion)
            combo.setCurrentIndex(max(0, combo.findData(x.aktion)))
            combo.currentIndexChanged.connect(self._zusammenfassen)
            self.tabelle.setCellWidget(r, 5, combo)
            self.tabelle.setItem(r, 6, QTableWidgetItem(x.hinweis))
        self.tabelle.resizeColumnsToContents()
        self.tabelle.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._zusammenfassen()

    def gewaehlt(self) -> list[Abgleich]:
        return [replace(x, aktion=self.tabelle.cellWidget(r, 5).currentData()) for r, x in enumerate(self.abgleich)]

    def _zusammenfassen(self, *_) -> None:
        zaehler: dict[str, int] = {}
        for x in self.gewaehlt():
            zaehler[x.aktion] = zaehler.get(x.aktion, 0) + 1
        self.zusammenfassung.setText(" · ".join(f"{AKTIONEN[k]}: {v}" for k, v in zaehler.items()))


class ImportAssistent(QWizard):
    def __init__(self, sd: Stammdaten, jahr: Schuljahr, lerngruppe_id: int | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sd, self.jahr, self.lerngruppe_id = sd, jahr, lerngruppe_id
        self.ergebnis = None
        self.setWindowTitle(f"Schüler:innen importieren – Schuljahr {jahr.bezeichnung}")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(860, 620)
        self.seite_datei = SeiteDatei()
        self.seite_spalten = SeiteSpalten()
        self.seite_abgleich = SeiteAbgleich()
        for s in (self.seite_datei, self.seite_spalten, self.seite_abgleich):
            self.addPage(s)
        self.setButtonText(QWizard.WizardButton.NextButton, "Weiter")
        self.setButtonText(QWizard.WizardButton.BackButton, "Zurück")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Importieren")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Abbrechen")

    def accept(self) -> None:
        try:
            self.ergebnis = fuehre_aus(self.sd, self.jahr.id, self.seite_abgleich.gewaehlt(),
                                       self.seite_abgleich.lerngruppe.currentData(), self.seite_abgleich.zugang.wert())
        except ValueError as e:
            fehler(self, "Import", f"Der Import wurde nicht ausgeführt – es wurde nichts verändert.\n\n{e}")
            return
        e = self.ergebnis
        teile = [f"{e.neu} neu angelegt", f"{e.aktualisiert} aktualisiert", f"{e.uebernommen} aus früheren Jahren",
                 f"{e.unveraendert} unverändert", f"{e.uebersprungen} übersprungen"]
        if self.seite_abgleich.lerngruppe.currentData() is not None:
            teile.append(f"{e.in_lerngruppe} neu in „{self.seite_abgleich.lerngruppe.currentText()}“")
        info(self, "Import abgeschlossen", "\n".join(teile))
        super().accept()

