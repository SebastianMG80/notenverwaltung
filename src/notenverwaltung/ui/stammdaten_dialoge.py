"""Dialoge für Schuljahre, Schüler:innen und Lerngruppen."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.stammdaten import (
    FAECHER,
    Lerngruppe,
    Schueler,
    SchuelerImJahr,
    Schuljahr,
    Stammdaten,
    StammdatenFehler,
    jahrgang_aus_klasse,
    natuerlich,
    schuljahr_vorschlag,
)
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, OptionalesDatum, Tabelle


class _Dialog(QDialog):
    """Grundgerüst: Formular, Meldungszeile, OK/Abbrechen. Unterklassen setzen `speichern()` um."""

    def __init__(self, titel: str, ok_text: str = "Speichern", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(titel)
        self.setMinimumWidth(460)
        self.form = QFormLayout()
        self.meldung = Hinweis()
        self.knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText(ok_text)
        self.knoepfe.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        self.knoepfe.accepted.connect(self._ok)
        self.knoepfe.rejected.connect(self.reject)
        self.lay = QVBoxLayout(self)
        self.lay.addLayout(self.form)
        self.lay.addWidget(self.meldung)
        self.lay.addWidget(self.knoepfe)

    def _ok(self) -> None:
        try:
            self.speichern()
        except StammdatenFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.accept()

    def speichern(self) -> None:  # pragma: no cover - abstrakt
        raise NotImplementedError


# ---- Schuljahr ----------------------------------------------------------------------------------

class SchuljahrDialog(_Dialog):
    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr | None = None, parent: QWidget | None = None) -> None:
        super().__init__("Schuljahr bearbeiten" if schuljahr else "Neues Schuljahr",
                         "Speichern" if schuljahr else "Anlegen", parent)
        self.sd = sd
        self.alt = schuljahr
        self.ergebnis: Schuljahr | None = None
        if schuljahr:
            b, beginn, wechsel, ende = (schuljahr.bezeichnung, schuljahr.beginn, schuljahr.halbjahreswechsel,
                                        schuljahr.ende)
        else:
            vorhanden = {s.bezeichnung for s in sd.schuljahre()}
            stichtag = date.today()
            b, beginn, wechsel, ende = schuljahr_vorschlag(stichtag)
            while b in vorhanden:  # nächstes freies Jahr vorschlagen
                stichtag = date(stichtag.year + 1, 9, 1)
                b, beginn, wechsel, ende = schuljahr_vorschlag(stichtag)
        self.bezeichnung = QLineEdit(b)
        self.beginn = Datumsfeld(beginn)
        self.wechsel = Datumsfeld(wechsel)
        self.ende = Datumsfeld(ende)
        self.form.addRow("Bezeichnung:", self.bezeichnung)
        self.form.addRow("Beginn:", self.beginn)
        self.form.addRow("2. Halbjahr ab:", self.wechsel)
        self.form.addRow("Ende:", self.ende)
        hinweis = QLabel("Der Halbjahreswechsel bestimmt, welche Noten zum 1. und welche zum 2. Halbjahr zählen.",
                         objectName="leise")
        hinweis.setWordWrap(True)
        self.form.addRow(hinweis)

    def speichern(self) -> None:
        werte = (self.bezeichnung.text(), self.beginn.wert(), self.wechsel.wert(), self.ende.wert())
        if self.alt:
            neu = Schuljahr(self.alt.id, *werte)
            self.sd.aendere_schuljahr(neu)
            self.ergebnis = self.sd.schuljahr(self.alt.id)
        else:
            self.ergebnis = self.sd.lege_schuljahr_an(*werte)


# ---- Schüler:in -----------------------------------------------------------------------------------

class SchuelerDialog(_Dialog):
    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr, eintrag: SchuelerImJahr | None = None,
                 klasse_vorschlag: str = "", parent: QWidget | None = None) -> None:
        super().__init__("Schüler:in bearbeiten" if eintrag else "Neue:r Schüler:in",
                         "Speichern" if eintrag else "Anlegen", parent)
        self.sd = sd
        self.jahr = schuljahr
        self.eintrag = eintrag
        self.ergebnis: Schueler | None = None
        s = eintrag.schueler if eintrag else None
        self.nachname = QLineEdit(s.nachname if s else "")
        self.vorname = QLineEdit(s.vorname if s else "")
        self.klasse = QComboBox()
        self.klasse.setEditable(True)
        self.klasse.addItems(sd.klassen(schuljahr.id))
        self.klasse.setCurrentText(eintrag.klasse if eintrag else klasse_vorschlag)
        self.jahrgang = QSpinBox()
        self.jahrgang.setRange(1, 13)
        self.jahrgang.setValue(eintrag.jahrgang if eintrag else (jahrgang_aus_klasse(klasse_vorschlag) or 5))
        self.klasse.currentTextChanged.connect(self._jahrgang_vorschlagen)
        self.zugang = OptionalesDatum("Zugang im laufenden Schuljahr am", eintrag.zugang if eintrag else None,
                                      vorgabe=date.today() if schuljahr.enthaelt(date.today()) else schuljahr.beginn)
        self.zugang.datum.begrenze(schuljahr.beginn, schuljahr.ende)
        self.geburtsdatum = OptionalesDatum("bekannt:", s.geburtsdatum if s else None, vorgabe=date(2012, 1, 1))
        self.bemerkung = QLineEdit(s.bemerkung if s else "")
        self.bemerkung.setPlaceholderText("z. B. Nachteilsausgleich")
        self.form.addRow("Nachname:", self.nachname)
        self.form.addRow("Vorname:", self.vorname)
        self.form.addRow("Klasse:", self.klasse)
        self.form.addRow("Jahrgang:", self.jahrgang)
        self.form.addRow("", self.zugang)
        self.form.addRow("Geburtsdatum:", self.geburtsdatum)
        self.form.addRow("Bemerkung:", self.bemerkung)
        self.nachname.setFocus()

    def _jahrgang_vorschlagen(self, text: str) -> None:
        j = jahrgang_aus_klasse(text)
        if j:
            self.jahrgang.setValue(j)

    def speichern(self) -> None:
        if self.eintrag is None:
            neu = self.sd.lege_schueler_an(self.jahr.id, self.nachname.text(), self.vorname.text(),
                                           self.klasse.currentText(), self.jahrgang.value(), self.zugang.wert(),
                                           self.geburtsdatum.wert())
            if self.bemerkung.text().strip():
                self.sd.aendere_schueler(replace(neu, bemerkung=self.bemerkung.text().strip()))
            self.ergebnis = self.sd.schueler(neu.id)
        else:
            s = replace(self.eintrag.schueler, nachname=self.nachname.text(), vorname=self.vorname.text(),
                        geburtsdatum=self.geburtsdatum.wert(), bemerkung=self.bemerkung.text().strip())
            self.sd.aendere_schueler(s)
            self.sd.setze_klasse(s.id, self.jahr.id, self.klasse.currentText(), self.jahrgang.value(),
                                 self.zugang.wert())
            self.ergebnis = self.sd.schueler(s.id)


class AbgangDialog(_Dialog):
    """Abgang von der Schule im laufenden Schuljahr."""

    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr, eintrag: SchuelerImJahr,
                 parent: QWidget | None = None) -> None:
        super().__init__("Abgang", "Speichern", parent)
        self.sd, self.jahr, self.eintrag = sd, schuljahr, eintrag
        erklaerung = QLabel(
            f"<b>{eintrag.schueler.vorname} {eintrag.schueler.nachname}</b> ({eintrag.klasse}) verlässt die Schule. "
            "Alle Noten bleiben erhalten; für Leistungen nach dem Abgangstag wird keine Eingabe mehr erwartet.")
        erklaerung.setWordWrap(True)
        self.form.addRow(erklaerung)
        vorgabe = eintrag.abgang or (date.today() if schuljahr.enthaelt(date.today()) else schuljahr.ende)
        self.datum = Datumsfeld(vorgabe)
        self.datum.begrenze(schuljahr.beginn, schuljahr.ende)
        self.form.addRow("Letzter Schultag:", self.datum)
        self.zuruecknehmen = QCheckBox("Abgang zurücknehmen (bleibt doch)")
        self.zuruecknehmen.setVisible(eintrag.abgang is not None)
        self.zuruecknehmen.toggled.connect(lambda an: self.datum.setEnabled(not an))
        self.form.addRow(self.zuruecknehmen)

    def speichern(self) -> None:
        datum = None if self.zuruecknehmen.isChecked() else self.datum.wert()
        self.sd.abgang(self.eintrag.schueler.id, self.jahr.id, datum)


# ---- Lerngruppe -----------------------------------------------------------------------------------

class LerngruppeDialog(_Dialog):
    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr, gruppe: Lerngruppe | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__("Lerngruppe bearbeiten" if gruppe else "Neue Lerngruppe",
                         "Speichern" if gruppe else "Anlegen", parent)
        self.sd, self.jahr, self.alt = sd, schuljahr, gruppe
        self.ergebnis: Lerngruppe | None = None

        self.ist_klasse = QRadioButton("Klasse in einem Fach (z. B. „8.4 Deutsch“)")
        self.ist_kurs = QRadioButton("Kurs, klassenübergreifend (z. B. „M9.3E“)")
        (self.ist_klasse if gruppe and gruppe.art == "klasse" else self.ist_kurs).setChecked(True)
        if gruppe is None:
            self.ist_klasse.setChecked(True)
        self._art_gruppe = QButtonGroup(self)
        self._art_gruppe.addButton(self.ist_klasse)
        self._art_gruppe.addButton(self.ist_kurs)
        art = QVBoxLayout()
        art.addWidget(self.ist_klasse)
        art.addWidget(self.ist_kurs)
        self.form.addRow("Art:", art)

        self.klasse = QComboBox()
        self.klasse.setEditable(True)
        self.klasse.addItems(sd.klassen(schuljahr.id))
        self.fach = QComboBox()
        self.fach.setEditable(True)
        self.fach.addItems([f for f, _ in FAECHER])
        self.fach.setCurrentText(gruppe.fach if gruppe else "")
        self.kuerzel = QLineEdit(gruppe.fach_kuerzel if gruppe else "")
        self.kuerzel.setMaximumWidth(80)
        self.bezeichnung = QLineEdit(gruppe.bezeichnung if gruppe else "")
        self.bezeichnung.setPlaceholderText("wird vorgeschlagen")
        self._bezeichnung_von_hand = gruppe is not None
        self.bezeichnung.textEdited.connect(lambda _: setattr(self, "_bezeichnung_von_hand", True))
        self.jahrgang = QSpinBox()
        self.jahrgang.setRange(1, 13)
        self.jahrgang.setValue(gruppe.jahrgang if gruppe else 5)
        self.niveau = QComboBox()
        self.niveau.addItem("—", "")
        self.niveau.addItem("E-Kurs (Erweiterung)", "E")
        self.niveau.addItem("G-Kurs (Grundlage)", "G")
        self.niveau.setCurrentIndex(max(0, self.niveau.findData(gruppe.niveau if gruppe else "")))
        self.schriftlich = QRadioButton("schriftlich (mit Klassenarbeiten)")
        self.muendlich = QRadioButton("nur mündlich")
        self._schr_gruppe = QButtonGroup(self)
        self._schr_gruppe.addButton(self.schriftlich)
        self._schr_gruppe.addButton(self.muendlich)
        (self.schriftlich if (gruppe is None or gruppe.schriftlich) else self.muendlich).setChecked(True)
        schr = QHBoxLayout()
        schr.addWidget(self.schriftlich)
        schr.addWidget(self.muendlich)
        schr.addStretch(1)
        self.notensystem = QComboBox()
        self.notensystem.addItem("Sekundarstufe I (Noten 1–6)", "sek1")
        self.notensystem.addItem("Sekundarstufe II (0–15 Punkte) – folgt später", "sek2")
        self.notensystem.model().item(1).setEnabled(False)

        fach_zeile = QHBoxLayout()
        fach_zeile.addWidget(self.fach, 1)
        fach_zeile.addWidget(QLabel("Kürzel:"))
        fach_zeile.addWidget(self.kuerzel)
        self.form.addRow("Klasse:", self.klasse)
        self.form.addRow("Fach:", fach_zeile)
        self.form.addRow("Jahrgang:", self.jahrgang)
        self.form.addRow("Kursniveau:", self.niveau)
        self.form.addRow("Bezeichnung:", self.bezeichnung)
        self.form.addRow("Fachart:", schr)
        self.form.addRow("Notensystem:", self.notensystem)
        self.uebernehmen = QCheckBox("Alle Schüler:innen der Klasse aufnehmen")
        self.uebernehmen.setChecked(True)
        self.uebernehmen.setVisible(gruppe is None)
        self.form.addRow(self.uebernehmen)

        if gruppe and gruppe.art == "klasse":
            self.klasse.setCurrentText(gruppe.bezeichnung.split(" ")[0])
        for sig in (self.ist_klasse.toggled, self.klasse.currentTextChanged, self.fach.currentTextChanged,
                    self.niveau.currentIndexChanged, self.jahrgang.valueChanged):
            sig.connect(self._aktualisieren)
        self._aktualisieren()

    def _aktualisieren(self, *_) -> None:
        klasse = self.ist_klasse.isChecked()
        self.form.setRowVisible(self.klasse, klasse)
        self.uebernehmen.setVisible(klasse and self.alt is None)
        fach = self.fach.currentText().strip()
        kuerzel = dict(FAECHER).get(fach)
        if kuerzel and (not self.kuerzel.text() or self.kuerzel.text() in dict(FAECHER).values()):
            self.kuerzel.setText(kuerzel)
        if klasse:
            j = jahrgang_aus_klasse(self.klasse.currentText())
            if j and self.sender() is self.klasse:
                self.jahrgang.setValue(j)
        if not self._bezeichnung_von_hand:
            if klasse:
                vorschlag = f"{self.klasse.currentText().strip()} {fach}".strip()
            else:
                vorschlag = f"{self.kuerzel.text() or fach}{self.jahrgang.value()}{self.niveau.currentData()}"
            self.bezeichnung.setText(vorschlag)

    def speichern(self) -> None:
        art = "klasse" if self.ist_klasse.isChecked() else "kurs"
        if art == "klasse" and not self.klasse.currentText().strip():
            raise StammdatenFehler("Bitte die Klasse angeben.")
        werte = dict(bezeichnung=self.bezeichnung.text(), fach=self.fach.currentText(), art=art,
                     jahrgang=self.jahrgang.value(), fach_kuerzel=self.kuerzel.text(),
                     niveau=self.niveau.currentData(), schriftlich=self.schriftlich.isChecked(),
                     notensystem=self.notensystem.currentData())
        if self.alt:
            self.sd.aendere_lerngruppe(replace(self.alt, **werte))
            self.ergebnis = self.sd.lerngruppe(self.alt.id)
        else:
            self.ergebnis = self.sd.lege_lerngruppe_an(Lerngruppe(id=0, schuljahr_id=self.jahr.id, **werte))
            if art == "klasse" and self.uebernehmen.isChecked():
                self.sd.uebernimm_klasse(self.ergebnis.id, self.klasse.currentText().strip())


class MitgliederDialog(_Dialog):
    """Schüler:innen des Schuljahres zu einer Lerngruppe hinzufügen."""

    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr, gruppe: Lerngruppe,
                 parent: QWidget | None = None) -> None:
        super().__init__(f"Schüler:innen zu „{gruppe.bezeichnung}“ hinzufügen", "Hinzufügen", parent)
        self.setMinimumSize(560, 520)
        self.sd, self.jahr, self.gruppe = sd, schuljahr, gruppe
        self.hinzugefuegt = 0
        vorhanden = {m.schueler.id for m in sd.mitglieder(gruppe.id)}
        self.kandidaten = [e for e in sd.schueler_im_jahr(schuljahr.id) if e.schueler.id not in vorhanden]

        self.filter_klasse = QComboBox()
        self.filter_klasse.addItem("Alle Klassen", None)
        for k in sorted({e.klasse for e in self.kandidaten}, key=natuerlich):
            self.filter_klasse.addItem(k, k)
        self.suche = QLineEdit()
        self.suche.setPlaceholderText("Name suchen …")
        filter_zeile = QHBoxLayout()
        filter_zeile.addWidget(self.filter_klasse)
        filter_zeile.addWidget(self.suche, 1)
        self.form.addRow(filter_zeile)
        self.tabelle = Tabelle(["Nachname", "Vorname", "Klasse"], mehrfach=True)
        self.form.addRow(self.tabelle)
        self.von = OptionalesDatum("Eintritt erst am",
                                   vorgabe=date.today() if schuljahr.enthaelt(date.today()) else schuljahr.beginn)
        self.von.datum.begrenze(schuljahr.beginn, schuljahr.ende)
        self.form.addRow(self.von)
        if gruppe.art == "klasse":  # „8.4 Deutsch“ → Klasse 8.4 vorauswählen
            idx = self.filter_klasse.findData(gruppe.bezeichnung.split(" ")[0])
            self.filter_klasse.setCurrentIndex(max(0, idx))
        self.filter_klasse.currentIndexChanged.connect(self._filtern)
        self.suche.textChanged.connect(self._filtern)
        self._filtern()

    def _filtern(self, *_) -> None:
        klasse = self.filter_klasse.currentData()
        text = self.suche.text().strip().lower()
        # Ohne Klassenwahl und Suche: nur der Jahrgang der Lerngruppe (Kurse sind klassenübergreifend)
        nur_jahrgang = klasse is None and not text
        treffer = [e for e in self.kandidaten
                   if (klasse is None or e.klasse == klasse)
                   and (not text or text in f"{e.schueler.nachname} {e.schueler.vorname}".lower())
                   and (not nur_jahrgang or e.jahrgang == self.gruppe.jahrgang)]
        self.tabelle.fuelle([[e.schueler.nachname, e.schueler.vorname, e.klasse] for e in treffer],
                            [e.schueler.id for e in treffer])
        if not treffer:
            self.meldung.setze("Keine passenden Schüler:innen. Neue legst du unter „Schüler:innen“ an.", "info")
        else:
            self.meldung.setze("Mehrere auswählen mit Strg oder Umschalt. Strg+A wählt alle.", "info")

    def speichern(self) -> None:
        ids = self.tabelle.ausgewaehlte_daten()
        if not ids:
            raise StammdatenFehler("Bitte mindestens eine:n Schüler:in auswählen.")
        self.hinzugefuegt = self.sd.fuege_hinzu(self.gruppe.id, ids, self.von.wert())


class ZeitraumDialog(_Dialog):
    """Eintritt und Austritt einer Person in einer Lerngruppe."""

    def __init__(self, sd: Stammdaten, schuljahr: Schuljahr, gruppe: Lerngruppe, mitglied,
                 parent: QWidget | None = None) -> None:
        super().__init__("Eintritt / Austritt", "Speichern", parent)
        self.sd, self.gruppe, self.mitglied = sd, gruppe, mitglied
        s = mitglied.schueler
        text = QLabel(f"<b>{s.vorname} {s.nachname}</b> in „{gruppe.bezeichnung}“. Nach dem Austritt bleiben alle "
                      "Noten erhalten; für spätere Leistungen wird keine Eingabe mehr erwartet.")
        text.setWordWrap(True)
        self.form.addRow(text)
        heute = date.today() if schuljahr.enthaelt(date.today()) else schuljahr.beginn
        self.von = OptionalesDatum("Eintritt am", mitglied.von, heute)
        self.bis = OptionalesDatum("Austritt am (letzter Tag)", mitglied.bis, heute)
        for f in (self.von, self.bis):
            f.datum.begrenze(schuljahr.beginn, schuljahr.ende)
        self.form.addRow(self.von)
        self.form.addRow(self.bis)
        if mitglied.abgang:
            self.form.addRow(Hinweis(f"Abgang von der Schule am {mitglied.abgang:%d.%m.%Y} "
                                     "(änderbar unter „Schüler:innen“).", "info"))

    def speichern(self) -> None:
        self.sd.setze_zeitraum(self.gruppe.id, self.mitglied.schueler.id, self.von.wert(), self.bis.wert())

