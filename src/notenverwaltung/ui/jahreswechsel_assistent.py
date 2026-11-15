"""Assistent „Neues Schuljahr übernehmen“: Jahr → Klassen → Schüler:innen → Lerngruppen."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from notenverwaltung.modell.jahreswechsel import AKTIONEN, Wechselplan, fuehre_aus, klasse_endet, klasse_hoch, plane
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten, StammdatenFehler, natuerlich, schuljahr_vorschlag
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, fehler, info


def _tabelle(koepfe: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(koepfe))
    t.setHorizontalHeaderLabels(koepfe)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    return t


def _fest(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


class SeiteJahr(QWizardPage):
    def __init__(self, sd: Stammdaten, quelle: Schuljahr) -> None:
        super().__init__()
        self.sd = sd
        self.setTitle("Neues Schuljahr")
        self.setSubTitle("Aus welchem Schuljahr wird übernommen, und wie heißt das neue?")
        self.quelle = QComboBox()
        for sj in sd.schuljahre():
            self.quelle.addItem(sj.bezeichnung, sj)
        self.quelle.setCurrentIndex(max(0, self.quelle.findText(quelle.bezeichnung)))
        self.bezeichnung = QLineEdit()
        self.beginn = Datumsfeld()
        self.wechsel = Datumsfeld()
        self.ende = Datumsfeld()
        self.meldung = Hinweis()
        form = QFormLayout(self)
        form.addRow("Übernehmen aus:", self.quelle)
        form.addRow(QLabel(""))
        form.addRow("Neues Schuljahr:", self.bezeichnung)
        form.addRow("Beginn:", self.beginn)
        form.addRow("2. Halbjahr ab:", self.wechsel)
        form.addRow("Ende:", self.ende)
        erkl = QLabel("Das bisherige Schuljahr bleibt mit allen Noten unverändert erhalten und ist weiter über "
                      "Datei → Schuljahr erreichbar. Neue Schüler:innen nimmst du danach per Import oder von Hand auf.",
                      objectName="leise")
        erkl.setWordWrap(True)
        form.addRow(erkl)
        form.addRow(self.meldung)
        self.quelle.currentIndexChanged.connect(self._vorschlagen)
        self._vorschlagen()

    def alt(self) -> Schuljahr:
        return self.quelle.currentData()

    def _vorschlagen(self, *_) -> None:
        a = self.alt()
        b, beginn, wechsel, ende = schuljahr_vorschlag(date(a.beginn.year + 1, 9, 1))
        vorhanden = next((s for s in self.sd.schuljahre() if s.bezeichnung == b), None)
        if vorhanden:
            beginn, wechsel, ende = vorhanden.beginn, vorhanden.halbjahreswechsel, vorhanden.ende
        self.bezeichnung.setText(b)
        self.beginn.setze(beginn)
        self.wechsel.setze(wechsel)
        self.ende.setze(ende)
        self.meldung.setze("Dieses Schuljahr gibt es schon – die Übernahme ergänzt es." if vorhanden else "", "info")

    def neues_jahr(self) -> Schuljahr:
        """Legt das neue Schuljahr an oder liefert das vorhandene gleichen Namens."""
        vorhanden = next((s for s in self.sd.schuljahre() if s.bezeichnung == self.bezeichnung.text().strip()), None)
        if vorhanden:
            return vorhanden
        return self.sd.lege_schuljahr_an(self.bezeichnung.text(), self.beginn.wert(), self.wechsel.wert(),
                                         self.ende.wert())

    def validatePage(self) -> bool:  # noqa: N802
        if self.bezeichnung.text().strip() == self.alt().bezeichnung:
            self.meldung.setze("Das neue Schuljahr muss anders heißen als das bisherige.", "fehler")
            return False
        if not (self.beginn.wert() < self.wechsel.wert() <= self.ende.wert()):
            self.meldung.setze("Der Halbjahreswechsel muss zwischen Beginn und Ende liegen.", "fehler")
            return False
        if self.beginn.wert() <= self.alt().beginn:
            self.meldung.setze("Das neue Schuljahr muss nach dem bisherigen beginnen.", "fehler")
            return False
        return True


class SeiteKlassen(QWizardPage):
    def __init__(self, sd: Stammdaten) -> None:
        super().__init__()
        self.sd = sd
        self.setTitle("Klassen")
        self.setSubTitle("So werden die Klassen hochgesetzt. Endet eine Klasse (z. B. nach dem Abschluss), Haken setzen.")
        self.tabelle = _tabelle(["Bisher", "Schüler:innen", "Neue Klasse", "Klasse endet"])
        self.tabelle.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle)

    def initializePage(self) -> None:  # noqa: N802
        alt = self.wizard().seite_jahr.alt()
        klassen = self.sd.klassen(alt.id)
        aktiv = {}
        for e in self.sd.schueler_im_jahr(alt.id):
            if e.abgang is None:
                aktiv[e.klasse] = aktiv.get(e.klasse, 0) + 1
        self.tabelle.setRowCount(len(klassen))
        for r, k in enumerate(klassen):
            self.tabelle.setItem(r, 0, _fest(k))
            self.tabelle.setItem(r, 1, _fest(str(aktiv.get(k, 0))))
            self.tabelle.setItem(r, 2, QTableWidgetItem(klasse_hoch(k)))
            endet = QCheckBox()
            endet.setChecked(klasse_endet(k))      # Q2: Abitur
            self.tabelle.setCellWidget(r, 3, endet)

    def zuordnung(self) -> dict[str, str | None]:
        return {self.tabelle.item(r, 0).text(): (None if self.tabelle.cellWidget(r, 3).isChecked()
                                                  else self.tabelle.item(r, 2).text().strip())
                for r in range(self.tabelle.rowCount())}


class SeitePersonen(QWizardPage):
    def __init__(self, sd: Stammdaten) -> None:
        super().__init__()
        self.sd = sd
        self.plan: Wechselplan | None = None
        self.setTitle("Schüler:innen")
        self.setSubTitle("Einzelne Ausnahmen festlegen: Wiederholung, Abgang oder eine andere Klasse.")
        self.tabelle = _tabelle(["Name", "Bisher", "Aktion", "Neue Klasse"])
        self.tabelle.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.zusammenfassung = QLabel(objectName="leise")
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(self.zusammenfassung)

    def initializePage(self) -> None:  # noqa: N802
        a = self.wizard()
        self.plan = plane(self.sd, a.seite_jahr.alt().id, a.seite_klassen.zuordnung())
        self.plan.personen.sort(key=lambda p: (natuerlich(p.eintrag.klasse), p.eintrag.schueler.nachname))
        self.tabelle.setRowCount(len(self.plan.personen))
        for r, p in enumerate(self.plan.personen):
            s = p.eintrag.schueler
            self.tabelle.setItem(r, 0, _fest(f"{s.nachname}, {s.vorname}"))
            self.tabelle.setItem(r, 1, _fest(p.eintrag.klasse))
            combo = QComboBox()
            for k, text in AKTIONEN.items():
                combo.addItem(text, k)
            combo.setCurrentIndex(combo.findData(p.aktion))
            combo.currentIndexChanged.connect(lambda _=0, zeile=r: self._aktion(zeile))
            self.tabelle.setCellWidget(r, 2, combo)
            self.tabelle.setItem(r, 3, QTableWidgetItem(p.neue_klasse))
        self.tabelle.resizeColumnsToContents()
        self._zusammenfassen()

    def _aktion(self, r: int) -> None:
        p = self.plan.personen[r]
        aktion = self.tabelle.cellWidget(r, 2).currentData()
        if aktion == "wiederholen":
            self.tabelle.item(r, 3).setText(p.eintrag.klasse)
        elif aktion == "versetzen" and self.tabelle.item(r, 3).text() in ("", p.eintrag.klasse):
            self.tabelle.item(r, 3).setText(klasse_hoch(p.eintrag.klasse))
        elif aktion == "abgang":
            self.tabelle.item(r, 3).setText("")
        self._zusammenfassen()

    def uebernimm(self) -> None:
        for r, p in enumerate(self.plan.personen):
            p.aktion = self.tabelle.cellWidget(r, 2).currentData()
            p.neue_klasse = self.tabelle.item(r, 3).text().strip()

    def _zusammenfassen(self) -> None:
        z = {}
        for r in range(self.tabelle.rowCount()):
            k = self.tabelle.cellWidget(r, 2).currentData()
            z[k] = z.get(k, 0) + 1
        self.zusammenfassung.setText(" · ".join(f"{AKTIONEN[k]}: {v}" for k, v in z.items()))


class SeiteGruppen(QWizardPage):
    def __init__(self, sd: Stammdaten) -> None:
        super().__init__()
        self.sd = sd
        self.setTitle("Lerngruppen")
        self.setSubTitle("Welche Lerngruppen gehen weiter? Bezeichnung und Jahrgang lassen sich anpassen.")
        self.tabelle = _tabelle(["Übernehmen", "Bisher", "Neue Bezeichnung", "Jahrgang", "Mitglieder übernehmen"])
        self.tabelle.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        erkl = QLabel("Übernommen werden Fach, Art, Kursniveau, Gewichtung und Sortierung. Klassenarbeiten und "
                      "Noten bleiben im alten Schuljahr.", objectName="leise")
        erkl.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.addWidget(self.tabelle, 1)
        lay.addWidget(erkl)

    def initializePage(self) -> None:  # noqa: N802
        plan = self.wizard().seite_personen.plan
        self.tabelle.setRowCount(len(plan.gruppen))
        for r, gp in enumerate(plan.gruppen):
            an = QCheckBox()
            an.setChecked(gp.uebernehmen)
            self.tabelle.setCellWidget(r, 0, an)
            self.tabelle.setItem(r, 1, _fest(gp.gruppe.bezeichnung))
            self.tabelle.setItem(r, 2, QTableWidgetItem(gp.neue_bezeichnung))
            jg = QSpinBox()
            jg.setRange(1, 13)
            jg.setValue(gp.neuer_jahrgang)
            self.tabelle.setCellWidget(r, 3, jg)
            mit = QCheckBox()
            mit.setChecked(True)
            self.tabelle.setCellWidget(r, 4, mit)
        self.tabelle.resizeColumnsToContents()

    def uebernimm(self) -> None:
        for r, gp in enumerate(self.wizard().seite_personen.plan.gruppen):
            gp.uebernehmen = self.tabelle.cellWidget(r, 0).isChecked()
            gp.neue_bezeichnung = self.tabelle.item(r, 2).text().strip()
            gp.neuer_jahrgang = self.tabelle.cellWidget(r, 3).value()
            gp.mitglieder = self.tabelle.cellWidget(r, 4).isChecked()


class JahreswechselAssistent(QWizard):
    def __init__(self, sd: Stammdaten, quelle: Schuljahr, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sd = sd
        self.neues_jahr: Schuljahr | None = None
        self.setWindowTitle("Neues Schuljahr übernehmen")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(760, 600)
        self.seite_jahr = SeiteJahr(sd, quelle)
        self.seite_klassen = SeiteKlassen(sd)
        self.seite_personen = SeitePersonen(sd)
        self.seite_gruppen = SeiteGruppen(sd)
        for s in (self.seite_jahr, self.seite_klassen, self.seite_personen, self.seite_gruppen):
            self.addPage(s)
        self.setButtonText(QWizard.WizardButton.NextButton, "Weiter")
        self.setButtonText(QWizard.WizardButton.BackButton, "Zurück")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Übernehmen")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Abbrechen")

    def accept(self) -> None:
        self.seite_personen.uebernimm()
        self.seite_gruppen.uebernimm()
        plan = self.seite_personen.plan
        v = self.sd.v
        vorher = v.serialize()
        try:
            neu = self.seite_jahr.neues_jahr()
            e = fuehre_aus(self.sd, plan, neu)
        except StammdatenFehler as fehlertext:
            v.deserialize(vorher)
            v.execute("PRAGMA foreign_keys = ON")
            fehler(self, "Übernahme", f"Es wurde nichts verändert.\n\n{fehlertext}")
            return
        self.neues_jahr = neu
        info(self, "Schuljahr übernommen",
             f"Schuljahr {neu.bezeichnung}:\n{e.versetzt} versetzt, {e.wiederholt} Wiederholung(en), "
             f"{e.abgaenge} Abgang/Abgänge\n{e.gruppen} Lerngruppe(n) mit {e.mitglieder} Mitgliedschaften übernommen.")
        super().accept()
