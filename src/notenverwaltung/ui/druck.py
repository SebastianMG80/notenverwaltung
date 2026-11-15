"""Druckdialog für eine Arbeit: Punkteliste oder Notenabschnitte, mit Vorschau, PDF und Drucker."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QFont, QPageLayout, QPixmap
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.ausgabe.abschnitte import AVERY_3424, AVERY_3425, BLATTRAND, Notenabschnitte, freies_format
from notenverwaltung.ausgabe.punkteliste import ListenOptionen, Punkteliste
from notenverwaltung.ausgabe.rueckmeldebogen import Rueckmeldebogen
from notenverwaltung.ausgabe.seite import Ausgabe, als_pdf, drucke, kopfzeile_aus, vorschau
from notenverwaltung.einstellungen import druck_schrift, einstellungen, setze_druck_schrift
from notenverwaltung.modell.arbeiten import Arbeit, Arbeiten
from notenverwaltung.ui.bausteine import Hinweis, OptionalesDatum, fehler


def _wert(schluessel: str, standard, typ=float):
    try:
        return typ(einstellungen().value(schluessel, standard))
    except (TypeError, ValueError):
        return standard


def _bool(schluessel: str, standard: bool) -> bool:
    w = einstellungen().value(schluessel, standard)
    return w if isinstance(w, bool) else str(w).lower() == "true"


class DruckDialog(QDialog):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar, self.arbeit = ar, arbeit
        self.setWindowTitle(f"Drucken – {arbeit.titel}")
        self.resize(1100, 760)
        self._seite = 0
        self.ausgabe: Ausgabe | None = None

        # ---- Art der Ausgabe
        self.art_liste = QRadioButton("Punkteliste (für dich)")
        self.art_abschnitte = QRadioButton("Notenabschnitte (für die Schüler:innen)")
        self.art_bogen = QRadioButton("Rückmeldebögen (ein Bogen pro Person)")
        gruppe = QButtonGroup(self)
        for k in (self.art_liste, self.art_abschnitte, self.art_bogen):
            gruppe.addButton(k)
        {"abschnitte": self.art_abschnitte, "bogen": self.art_bogen}.get(
            einstellungen().value("druck/art", "liste"), self.art_liste).setChecked(True)

        # ---- Optionen Rückmeldebogen
        self.box_bogen = QGroupBox("Rückmeldebögen")
        fb = QVBoxLayout(self.box_bogen)
        self.bogen_erwartung = QCheckBox("Erwartungshorizont je Aufgabe (falls eingetragen)")
        self.bogen_erwartung.setChecked(_bool("druck/bogen/erwartung", True))
        self.bogen_unterschrift = QCheckBox("Unterschriftszeilen")
        self.bogen_unterschrift.setChecked(_bool("druck/bogen/unterschrift", True))
        self.bogen_nur_note = QCheckBox("Nur Schüler:innen mit Note")
        self.bogen_nur_note.setChecked(True)
        self.bogen_beidseitig = QCheckBox("Beidseitiger Druck: jeder Bogen beginnt auf einem neuen Blatt")
        self.bogen_beidseitig.setToolTip("Fügt leere Rückseiten ein, damit ein Bogen mit Folgeseite nicht auf der "
                                         "Rückseite des vorigen beginnt.")
        self.bogen_beidseitig.setChecked(_bool("druck/bogen/beidseitig", False))
        for c in (self.bogen_erwartung, self.bogen_unterschrift, self.bogen_nur_note, self.bogen_beidseitig):
            c.toggled.connect(self._aktualisieren)
            fb.addWidget(c)

        # ---- Optionen Punkteliste
        self.box_liste = QGroupBox("Punkteliste")
        fl = QVBoxLayout(self.box_liste)
        o = ListenOptionen()
        self.opt = {}
        for feld, text in (("leere_ausblenden", "Leere Zeilen ausblenden"), ("mit_tendenz", "Noten mit Tendenz (2+, 2-)"),
                           ("schwache_hervorheben", "Noten 5 und 6 hervorheben"),
                           ("luecken_hervorheben", "Fehlende Einträge hervorheben"),
                           ("zebra", "Zeilen abwechselnd tönen"), ("durchschnitt", "Durchschnitt je Aufgabe"),
                           ("notenspiegel", "Notenspiegel und Notenschlüssel")):
            c = QCheckBox(text)
            c.setChecked(_bool(f"druck/liste/{feld}", getattr(o, feld)))
            c.toggled.connect(self._aktualisieren)
            fl.addWidget(c)
            self.opt[feld] = c

        # ---- Optionen Abschnitte
        self.box_abschnitte = QGroupBox("Notenabschnitte")
        fa = QFormLayout(self.box_abschnitte)
        self.format = QComboBox()
        self.format.addItem(AVERY_3424.name, "3424")
        self.format.addItem(AVERY_3425.name, "3425")
        self.format.addItem("Frei (Normalpapier zum Ausschneiden)", "frei")
        self.format.setCurrentIndex(max(0, self.format.findData(einstellungen().value("druck/format", "3424"))))
        self.frei_b = QDoubleSpinBox()
        self.frei_b.setRange(60, 190)
        self.frei_b.setSuffix(" mm")
        self.frei_b.setValue(_wert("druck/frei_b", 100.0))
        self.frei_h = QDoubleSpinBox()
        self.frei_h.setRange(30, 140)
        self.frei_h.setSuffix(" mm")
        self.frei_h.setValue(_wert("druck/frei_h", 50.0))
        groesse = QHBoxLayout()
        groesse.addWidget(self.frei_b)
        groesse.addWidget(QLabel("×"))
        groesse.addWidget(self.frei_h)
        self.startplatz = QSpinBox()
        self.startplatz.setRange(1, 12)
        self.startplatz.setToolTip("Bei einem angebrochenen Etikettenbogen: erstes freies Etikett (zeilenweise gezählt)")
        self.nur_mit_note = QCheckBox("Nur Schüler:innen mit Note")
        self.nur_mit_note.setChecked(True)
        self.rahmen = QCheckBox("Schneidelinien drucken")
        self.datum = OptionalesDatum("anderes Datum:", vorgabe=arbeit.rueckgabe or date.today())
        self.versatz_x = QDoubleSpinBox()
        self.versatz_y = QDoubleSpinBox()
        for sp, schluessel in ((self.versatz_x, "druck/versatz_x"), (self.versatz_y, "druck/versatz_y")):
            sp.setRange(-10, 10)
            sp.setSingleStep(0.5)
            sp.setSuffix(" mm")
            sp.setValue(_wert(schluessel, 0.0))
        self.blattrand = QDoubleSpinBox()
        self.blattrand.setRange(0, 15)
        self.blattrand.setSingleStep(0.5)
        self.blattrand.setSuffix(" mm")
        self.blattrand.setValue(_wert("druck/blattrand", BLATTRAND))
        self.blattrand.setToolTip("So weit bleibt der Text mindestens vom Papierrand entfernt. Wird rechts oder links "
                                  "etwas abgeschnitten, diesen Wert erhöhen.")
        versatz = QHBoxLayout()
        versatz.addWidget(QLabel("→"))
        versatz.addWidget(self.versatz_x)
        versatz.addWidget(QLabel("↓"))
        versatz.addWidget(self.versatz_y)
        fa.addRow("Format:", self.format)
        fa.addRow("Größe:", groesse)
        fa.addRow("Start bei Etikett:", self.startplatz)
        fa.addRow(self.nur_mit_note)
        fa.addRow(self.rahmen)
        fa.addRow("Datum:", self.datum)
        fa.addRow("Druckversatz:", versatz)
        fa.addRow("Abstand zum Blattrand:", self.blattrand)
        hinweis = QLabel("Druckversatz: verschiebt den Druck, falls dein Drucker die Etiketten nicht genau trifft "
                         "(positiv = nach rechts bzw. unten). Abstand zum Blattrand: erhöhen, wenn am Rand etwas "
                         "abgeschnitten wird.", objectName="leise")
        hinweis.setWordWrap(True)
        fa.addRow(hinweis)
        self.format.currentIndexChanged.connect(self._aktualisieren)
        self.startplatz.valueChanged.connect(self._aktualisieren)
        for w in (self.frei_b, self.frei_h, self.versatz_x, self.versatz_y, self.blattrand):
            w.valueChanged.connect(self._aktualisieren)
        for w in (self.nur_mit_note, self.rahmen, self.datum.an):
            w.toggled.connect(self._aktualisieren)
        self.datum.datum.dateChanged.connect(self._aktualisieren)
        self.art_liste.toggled.connect(self._aktualisieren)
        self.art_bogen.toggled.connect(self._aktualisieren)

        # ---- Schrift
        self.schrift = QFontComboBox()
        self.schrift.setFontFilters(QFontComboBox.FontFilter.ScalableFonts)
        gespeichert = druck_schrift()
        if gespeichert:
            self.schrift.setCurrentFont(QFont(gespeichert))
        else:
            self.schrift.setCurrentText("")
        self.schrift.currentFontChanged.connect(self._aktualisieren)
        self.schrift_standard = QPushButton("Standard")
        self.schrift_standard.setToolTip("Noto Sans / DejaVu Sans / Segoe UI / Arial – je nachdem, was vorhanden ist")
        self.schrift_standard.clicked.connect(self._schrift_standard)
        self._schrift_gesetzt = bool(gespeichert)
        self.schrift.activated.connect(lambda _: setattr(self, "_schrift_gesetzt", True))

        # ---- Vorschau
        self.bild = QLabel()
        self.bild.setAlignment(Qt.AlignmentFlag.AlignCenter)
        flaeche = QScrollArea()
        flaeche.setWidget(self.bild)
        flaeche.setWidgetResizable(True)
        self.zurueck = QPushButton("◀")
        self.vor = QPushButton("▶")
        self.seiteninfo = QLabel()
        self.zurueck.clicked.connect(lambda: self._blaettern(-1))
        self.vor.clicked.connect(lambda: self._blaettern(1))
        nav = QHBoxLayout()
        nav.addStretch(1)
        nav.addWidget(self.zurueck)
        nav.addWidget(self.seiteninfo)
        nav.addWidget(self.vor)
        nav.addStretch(1)

        # ---- Knöpfe
        self.meldung = Hinweis()
        pdf = QPushButton("Als PDF speichern …")
        pdf.clicked.connect(self.als_pdf)
        drucken = QPushButton("Drucken …", objectName="primaer")
        drucken.clicked.connect(self.drucken)
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.accept)

        links = QVBoxLayout()
        links.addWidget(self.art_liste)
        links.addWidget(self.art_abschnitte)
        links.addWidget(self.art_bogen)
        links.addWidget(self.box_liste)
        links.addWidget(self.box_abschnitte)
        links.addWidget(self.box_bogen)
        sz = QHBoxLayout()
        sz.addWidget(QLabel("Schrift:"))
        sz.addWidget(self.schrift, 1)
        sz.addWidget(self.schrift_standard)
        links.addLayout(sz)
        links.addStretch(1)
        links.addWidget(self.meldung)
        lw = QWidget()
        lw.setLayout(links)
        lw.setFixedWidth(380)
        rechts = QVBoxLayout()
        rechts.addWidget(flaeche, 1)
        rechts.addLayout(nav)
        oben = QHBoxLayout()
        oben.addWidget(lw)
        oben.addLayout(rechts, 1)
        unten = QHBoxLayout()
        unten.addStretch(1)
        unten.addWidget(pdf)
        unten.addWidget(drucken)
        unten.addWidget(schliessen)
        lay = QVBoxLayout(self)
        lay.addLayout(oben, 1)
        lay.addLayout(unten)
        self._aktualisieren()

    # ---- Ausgabe zusammenstellen ---------------------------------------------------------------
    def baue_ausgabe(self) -> Ausgabe:
        if self.art_liste.isChecked():
            o = ListenOptionen(**{k: c.isChecked() for k, c in self.opt.items()})
            return Punkteliste(self.ar, self.arbeit, o)
        if self.art_bogen.isChecked():
            return Rueckmeldebogen(self.ar, self.arbeit, nur_mit_note=self.bogen_nur_note.isChecked(),
                                   erwartung=self.bogen_erwartung.isChecked(),
                                   unterschrift=self.bogen_unterschrift.isChecked(),
                                   beidseitig=self.bogen_beidseitig.isChecked())
        art = self.format.currentData()
        fmt = {"3424": AVERY_3424, "3425": AVERY_3425}.get(art) or freies_format(self.frei_b.value(), self.frei_h.value())
        a = Notenabschnitte(self.ar, self.arbeit, fmt, startplatz=self.startplatz.value() - 1,
                            nur_mit_note=self.nur_mit_note.isChecked(), rahmen=self.rahmen.isChecked(),
                            datum=self.datum.wert(), blattrand=self.blattrand.value())
        a.versatz_x, a.versatz_y = self.versatz_x.value(), self.versatz_y.value()
        return a

    def _schrift_standard(self) -> None:
        self._schrift_gesetzt = False
        self.schrift.blockSignals(True)
        self.schrift.setCurrentText("")
        self.schrift.blockSignals(False)
        self._aktualisieren()

    def _mit_einstellungen(self, ausgabe: Ausgabe) -> Ausgabe:
        ausgabe.schrift = self.schrift.currentFont().family() if self._schrift_gesetzt else None
        ausgabe.kopfzeile = kopfzeile_aus(self.ar.v)
        return ausgabe

    def _aktualisieren(self, *_) -> None:
        liste = self.art_liste.isChecked()
        self.box_liste.setVisible(liste)
        self.box_abschnitte.setVisible(self.art_abschnitte.isChecked())
        self.box_bogen.setVisible(self.art_bogen.isChecked())
        frei = self.format.currentData() == "frei"
        self.frei_b.setEnabled(frei)
        self.frei_h.setEnabled(frei)
        if self.sender() is self.format:
            self.rahmen.setChecked(frei)
        try:
            je_seite = (AVERY_3424.je_seite if self.format.currentData() == "3424" else AVERY_3425.je_seite
                        if self.format.currentData() == "3425" else
                        freies_format(self.frei_b.value(), self.frei_h.value()).je_seite)
            self.startplatz.blockSignals(True)
            self.startplatz.setMaximum(je_seite)
            self.startplatz.blockSignals(False)
            self.ausgabe = self._mit_einstellungen(self.baue_ausgabe())
        except ValueError as e:
            self.meldung.setze(str(e), "fehler")
            return
        if isinstance(self.ausgabe, (Notenabschnitte, Rueckmeldebogen)) and not self.ausgabe.ergebnisse:
            self.meldung.setze("Noch keine Noten – es gibt nichts zu drucken.", "info")
        elif isinstance(self.ausgabe, Rueckmeldebogen) and self.ausgabe.mehrseitig:
            n = sum(1 for k in self.ausgabe.seiten_je_bogen if k > 1)
            self.meldung.setze(f"{n} {'Bogen braucht' if n == 1 else 'Bögen brauchen'} eine Folgeseite (lange "
                               "Erwartungshorizonte oder Rückmeldungen). Für beidseitigen Druck die Option "
                               "„jeder Bogen beginnt auf einem neuen Blatt“ wählen.", "info")
        else:
            self.meldung.setze("", "info")
        self._seite = min(self._seite, self.ausgabe.seitenzahl() - 1)
        self._merken()
        self._vorschau()

    def _merken(self) -> None:
        s = einstellungen()
        s.setValue("druck/art", "liste" if self.art_liste.isChecked() else
                   "bogen" if self.art_bogen.isChecked() else "abschnitte")
        s.setValue("druck/bogen/erwartung", self.bogen_erwartung.isChecked())
        s.setValue("druck/bogen/unterschrift", self.bogen_unterschrift.isChecked())
        s.setValue("druck/bogen/beidseitig", self.bogen_beidseitig.isChecked())
        for k, c in self.opt.items():
            s.setValue(f"druck/liste/{k}", c.isChecked())
        s.setValue("druck/format", self.format.currentData())
        s.setValue("druck/frei_b", self.frei_b.value())
        s.setValue("druck/frei_h", self.frei_h.value())
        s.setValue("druck/versatz_x", self.versatz_x.value())
        s.setValue("druck/versatz_y", self.versatz_y.value())
        s.setValue("druck/blattrand", self.blattrand.value())
        setze_druck_schrift(self.schrift.currentFont().family() if self._schrift_gesetzt else "")

    def _vorschau(self) -> None:
        if self.ausgabe is None:
            return
        bild = vorschau(self.ausgabe, self._seite, dpi=80)
        self.bild.setPixmap(QPixmap.fromImage(bild))
        n = self.ausgabe.seitenzahl()
        self.seiteninfo.setText(f"Seite {self._seite + 1} von {n}")
        self.zurueck.setEnabled(self._seite > 0)
        self.vor.setEnabled(self._seite < n - 1)

    def _blaettern(self, schritt: int) -> None:
        self._seite = max(0, min(self.ausgabe.seitenzahl() - 1, self._seite + schritt))
        self._vorschau()

    # ---- Ausgeben ----------------------------------------------------------------------------
    def _dateiname(self) -> str:
        g = self.ar.sd.lerngruppe(self.arbeit.lerngruppe_id)
        art = ("Punkteliste" if self.art_liste.isChecked() else
               "Rückmeldebögen" if self.art_bogen.isChecked() else "Notenabschnitte")
        roh = f"{art} {g.bezeichnung} {self.arbeit.titel}"
        return "".join(z if z not in '\\/:*?"<>|' else "_" for z in roh) + ".pdf"

    def als_pdf(self) -> None:
        if self.ausgabe is None:
            return
        ordner = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        pfad, _ = QFileDialog.getSaveFileName(self, "Als PDF speichern", str(Path(ordner) / self._dateiname()),
                                              "PDF-Dateien (*.pdf)")
        if not pfad:
            return
        if not pfad.lower().endswith(".pdf"):
            pfad += ".pdf"
        try:
            als_pdf(self.ausgabe, Path(pfad))
        except OSError as e:
            fehler(self, "PDF speichern", f"Die Datei konnte nicht geschrieben werden:\n{e}")
            return
        self.meldung.setze(f"Gespeichert: {pfad}\nDie PDF enthält Noten – bitte nicht in einer Cloud ablegen.", "ok")

    def drucken(self) -> None:
        if self.ausgabe is None:
            return
        drucker = QPrinter(QPrinter.PrinterMode.HighResolution)
        drucker.setFullPage(True)
        drucker.setDocName(self.ausgabe.titel)
        drucker.setPageOrientation(QPageLayout.Orientation.Landscape if self.ausgabe.quer
                                   else QPageLayout.Orientation.Portrait)
        dialog = QPrintDialog(drucker, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            drucke(self.ausgabe, drucker)
        except OSError as e:
            fehler(self, "Drucken", str(e))
            return
        self.meldung.setze("An den Drucker geschickt. Etiketten: Druckeinstellung „Tatsächliche Größe“ / "
                           "„100 %“ verwenden, nicht „An Seite anpassen“.", "ok")
