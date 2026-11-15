"""Arbeitsseiten rechts im Hauptfenster: Schuljahr, Schüler:innen, Lerngruppe."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.stammdaten import SORTIERUNGEN, Lerngruppe, Schuljahr, Stammdaten
from notenverwaltung.ui.bausteine import Tabelle, aktuelle_farben, frage, info
from notenverwaltung.ui.stammdaten_dialoge import (
    AbgangDialog,
    LerngruppeDialog,
    MitgliederDialog,
    SchuelerDialog,
    SchuljahrDialog,
    ZeitraumDialog,
)


def _stichtag(jahr: Schuljahr) -> date:
    heute = date.today()
    return heute if jahr.enthaelt(heute) else (jahr.ende if heute > jahr.ende else jahr.beginn)


class Seite(QWidget):
    """Grundgerüst: Überschrift, Unterzeile, Knopfleiste, Inhalt."""

    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.titel = QLabel(objectName="titel")
        self.unterzeile = QLabel(objectName="leise")
        self.unterzeile.setWordWrap(True)
        self.leiste = QHBoxLayout()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 20, 24, 16)
        kopf = QHBoxLayout()
        texte = QVBoxLayout()
        texte.addWidget(self.titel)
        texte.addWidget(self.unterzeile)
        kopf.addLayout(texte, 1)
        self.kopf_knoepfe = QHBoxLayout()
        kopf.addLayout(self.kopf_knoepfe)
        self.lay.addLayout(kopf)
        self.lay.addSpacing(8)
        self.lay.addLayout(self.leiste)

    def knopf(self, text: str, slot, leiste: QHBoxLayout | None = None, primaer: bool = False) -> QPushButton:
        k = QPushButton(text, objectName="primaer" if primaer else None)
        k.clicked.connect(slot)
        (leiste if leiste is not None else self.leiste).addWidget(k)
        return k


# ---- Schuljahr -------------------------------------------------------------------------------------

class SchuljahrSeite(Seite):
    offen_gewaehlt = Signal(object)          # OffenerPunkt – das Hauptfenster springt dorthin

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.knopf("Bearbeiten …", self._bearbeiten, self.kopf_knoepfe)
        self.angaben = QLabel()
        self.angaben.setWordWrap(True)
        self.lay.addWidget(self.angaben)
        self.leiste.addStretch(1)
        self.lay.addSpacing(16)
        self.offen_titel = QLabel("<b>Offene Punkte</b>")
        self.offen = QListWidget()
        self.offen.setWordWrap(True)
        self.offen.itemActivated.connect(self._offen_gewaehlt)
        self.offen.itemDoubleClicked.connect(self._offen_gewaehlt)
        self.offen_hinweis = QLabel("Doppelklick oder Enter springt zur Stelle. Quartals- und Halbjahresnoten "
                                    "erscheinen drei Wochen vor dem Ende des Zeitraums.", objectName="leise")
        self.offen_hinweis.setWordWrap(True)
        self.lay.addWidget(self.offen_titel)
        self.lay.addWidget(self.offen, 1)
        self.lay.addWidget(self.offen_hinweis)

    def zeige(self, sd: Stammdaten, jahr: Schuljahr) -> None:
        self.sd, self.jahr = sd, jahr
        self.titel.setText(f"Schuljahr {jahr.bezeichnung}")
        self.unterzeile.setText(f"{jahr.beginn:%d.%m.%Y} bis {jahr.ende:%d.%m.%Y} · "
                                f"2. Halbjahr ab {jahr.halbjahreswechsel:%d.%m.%Y}")
        schueler = sd.schueler_im_jahr(jahr.id)
        gruppen = sd.lerngruppen(jahr.id)
        zeilen = [f"<b>{len(schueler)}</b> Schüler:innen in <b>{len(sd.klassen(jahr.id))}</b> Klassen",
                  f"<b>{len(gruppen)}</b> Lerngruppen"]
        if not schueler:
            zeilen.append("<br>Als Nächstes: Schüler:innen anlegen (links „Schüler:innen“), danach Lerngruppen.")
        elif not gruppen:
            zeilen.append("<br>Als Nächstes: Lerngruppen anlegen (Datei-Menü oder links „Neue Lerngruppe …“).")
        self.angaben.setText("<br>".join(zeilen))
        self.offene_punkte_laden()

    def offene_punkte_laden(self, heute: date | None = None) -> None:
        from notenverwaltung.modell.offen import offene_punkte

        self.offen.clear()
        punkte = offene_punkte(self.sd.v, self.jahr, heute) if self.sd and self.jahr else []
        f = aktuelle_farben()
        for p in punkte:
            item = QListWidgetItem(("⚠ " if p.dringend else "• ") + p.text)
            item.setData(Qt.ItemDataRole.UserRole, p)
            if p.dringend:
                item.setForeground(QColor(f.warnung))
            self.offen.addItem(item)
        if not punkte:
            item = QListWidgetItem("✓ Nichts offen.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.offen.addItem(item)
        self.offen_titel.setText(f"<b>Offene Punkte</b> ({len(punkte)})" if punkte else "<b>Offene Punkte</b>")

    def _offen_gewaehlt(self, item: QListWidgetItem) -> None:
        p = item.data(Qt.ItemDataRole.UserRole)
        if p is not None:
            self.offen_gewaehlt.emit(p)

    def _bearbeiten(self) -> None:
        if self.sd and self.jahr and SchuljahrDialog(self.sd, self.jahr, self).exec():
            self.geaendert.emit()


# ---- Schüler:innen des Jahres ----------------------------------------------------------------------

class SchuelerSeite(Seite):
    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.titel.setText("Schüler:innen")
        self.filter_klasse = QComboBox()
        self.filter_klasse.setMinimumWidth(130)
        self.suche = QLineEdit()
        self.suche.setPlaceholderText("Name suchen …")
        self.leiste.addWidget(self.filter_klasse)
        self.leiste.addWidget(self.suche, 1)
        self.knopf("Neu …", self.neu, primaer=True)
        self.knopf("Importieren …", self.importieren)
        self.k_bearbeiten = self.knopf("Bearbeiten …", self.bearbeiten)
        self.k_abgang = self.knopf("Abgang …", self.abgang)
        self.k_loeschen = self.knopf("Löschen", self.loeschen)
        self.k_bogen = self.knopf("Schüler:innen-Bogen …", self.bogen)
        self.k_bogen.setToolTip("Alle Noten dieser Person aus allen deinen Gruppen, mit Verlauf (Strg+B)")
        self.tabelle = Tabelle(["Nachname", "Vorname", "Klasse", "Jahrgang", "Status", "Bemerkung"])
        self.tabelle.itemDoubleClicked.connect(lambda _: self.bearbeiten())
        self.tabelle.itemSelectionChanged.connect(self._knoepfe)
        self.lay.addWidget(self.tabelle, 1)
        self.filter_klasse.currentIndexChanged.connect(self._fuellen)
        self.suche.textChanged.connect(self._fuellen)
        self._eintraege = []

    def zeige(self, sd: Stammdaten, jahr: Schuljahr) -> None:
        self.sd, self.jahr = sd, jahr
        auswahl = self.filter_klasse.currentData()
        self.filter_klasse.blockSignals(True)
        self.filter_klasse.clear()
        self.filter_klasse.addItem("Alle Klassen", None)
        for k in sd.klassen(jahr.id):
            self.filter_klasse.addItem(f"Klasse {k}", k)
        self.filter_klasse.setCurrentIndex(max(0, self.filter_klasse.findData(auswahl)))
        self.filter_klasse.blockSignals(False)
        self._fuellen()

    def _fuellen(self, *_) -> None:
        if not self.sd:
            return
        alle = self.sd.schueler_im_jahr(self.jahr.id, self.filter_klasse.currentData())
        text = self.suche.text().strip().lower()
        self._eintraege = [e for e in alle
                           if not text or text in f"{e.schueler.nachname} {e.schueler.vorname}".lower()]
        stichtag = _stichtag(self.jahr)
        zeilen, gedimmt = [], []
        for e in self._eintraege:
            status = (f"Abgang am {e.abgang:%d.%m.%Y}" if e.abgang else
                      f"Zugang am {e.zugang:%d.%m.%Y}" if e.zugang else "")
            zeilen.append([e.schueler.nachname, e.schueler.vorname, e.klasse, str(e.jahrgang), status,
                           e.schueler.bemerkung])
            gedimmt.append(not e.aktiv_am(stichtag))
        self.tabelle.fuelle(zeilen, [e.schueler.id for e in self._eintraege], gedimmt)
        self.unterzeile.setText(f"Schuljahr {self.jahr.bezeichnung} · {len(alle)} Schüler:innen"
                                + (f" in Klasse {self.filter_klasse.currentData()}"
                                   if self.filter_klasse.currentData() else ""))
        self._knoepfe()

    def _knoepfe(self) -> None:
        da = self._aktuell() is not None
        for k in (self.k_bearbeiten, self.k_abgang, self.k_loeschen, self.k_bogen):
            k.setEnabled(da)

    def aktuelle_person(self) -> int | None:
        return self.tabelle.aktuelle_daten()

    def bogen(self) -> None:
        from notenverwaltung.ui.personenbogen_dialog import personenbogen_dialog

        sid = self.aktuelle_person()
        if sid is not None:
            d = personenbogen_dialog(self.sd.v, sid, self)
            self._bogendialog = d          # für Tests
            d.exec()

    def markiere_person(self, sid: int) -> None:
        """Für die Schnellsuche: Filter zurücksetzen und die Person auswählen."""
        self.filter_klasse.setCurrentIndex(0)
        self.suche.clear()
        self._fuellen()
        if sid in self.tabelle.zeilen_daten:
            self.tabelle.selectRow(self.tabelle.zeilen_daten.index(sid))
            self.tabelle.setFocus()

    def _aktuell(self):
        sid = self.tabelle.aktuelle_daten()
        return next((e for e in self._eintraege if e.schueler.id == sid), None)

    def neu(self) -> None:
        if SchuelerDialog(self.sd, self.jahr, klasse_vorschlag=self.filter_klasse.currentData() or "",
                          parent=self).exec():
            self.geaendert.emit()

    def importieren(self) -> None:
        from notenverwaltung.ui.import_assistent import ImportAssistent

        if self.sd and ImportAssistent(self.sd, self.jahr, parent=self).exec():
            self.geaendert.emit()

    def bearbeiten(self) -> None:
        e = self._aktuell()
        if e and SchuelerDialog(self.sd, self.jahr, e, parent=self).exec():
            self.geaendert.emit()

    def abgang(self) -> None:
        e = self._aktuell()
        if e and AbgangDialog(self.sd, self.jahr, e, self).exec():
            self.geaendert.emit()

    def loeschen(self) -> None:
        e = self._aktuell()
        if e is None:
            return
        gruppen = self.sd.lerngruppen_von(e.schueler.id, self.jahr.id)
        if not frage(self, "Schüler:in löschen",
                     f"„{e.schueler.vorname} {e.schueler.nachname}“ mit allen Daten aus allen Schuljahren endgültig "
                     f"löschen?\n\nMitglied in {len(gruppen)} Lerngruppe(n) dieses Jahres.\n\n"
                     "Wer die Schule verlässt, bekommt besser einen Abgang – dann bleiben die Noten erhalten.",
                     ja="Endgültig löschen", warnung=True):
            return
        self.sd.loesche_schueler(e.schueler.id)
        self.geaendert.emit()


# ---- Lerngruppe ------------------------------------------------------------------------------------

class MitgliederTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self._mitglieder = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        leiste = QHBoxLayout()
        leiste.addWidget(QLabel("Sortierung:"))
        self.sortierung = QComboBox()
        for schluessel, text in SORTIERUNGEN.items():
            self.sortierung.addItem(text, schluessel)
        self.sortierung.currentIndexChanged.connect(self._sortierung_geaendert)
        leiste.addWidget(self.sortierung)
        self.hoch = QPushButton("▲")
        self.runter = QPushButton("▼")
        self.hoch.setToolTip("In der eigenen Reihenfolge nach oben")
        self.runter.setToolTip("In der eigenen Reihenfolge nach unten")
        self.hoch.clicked.connect(lambda: self._verschieben(-1))
        self.runter.clicked.connect(lambda: self._verschieben(1))
        leiste.addWidget(self.hoch)
        leiste.addWidget(self.runter)
        leiste.addStretch(1)
        self.k_hinzu = QPushButton("Hinzufügen …", objectName="primaer")
        self.k_hinzu.clicked.connect(self._hinzufuegen)
        self.k_import = QPushButton("Liste importieren …")
        self.k_import.setToolTip("Kursliste aus einer Datei: legt fehlende Schüler:innen an und nimmt alle auf")
        self.k_import.clicked.connect(self._importieren)
        self.k_klasse = QPushButton("Klasse vervollständigen")
        self.k_klasse.setToolTip("Fehlende Schüler:innen der Klasse aufnehmen (z. B. nach Zugängen)")
        self.k_klasse.clicked.connect(self._klasse)
        self.k_zeitraum = QPushButton("Eintritt / Austritt …")
        self.k_zeitraum.clicked.connect(self._zeitraum)
        self.k_entfernen = QPushButton("Entfernen")
        self.k_entfernen.clicked.connect(self._entfernen)
        for k in (self.k_hinzu, self.k_import, self.k_klasse, self.k_zeitraum, self.k_entfernen):
            leiste.addWidget(k)
        lay.addLayout(leiste)
        self.tabelle = Tabelle(["Nr.", "Nachname", "Vorname", "Klasse", "Status"])
        self.tabelle.itemSelectionChanged.connect(self._knoepfe)
        self.tabelle.itemDoubleClicked.connect(lambda _: self._zeitraum())
        lay.addWidget(self.tabelle, 1)
        self.zusammenfassung = QLabel(objectName="leise")
        lay.addWidget(self.zusammenfassung)

    def markiere_person(self, sid: int) -> None:
        if sid in self.tabelle.zeilen_daten:
            self.tabelle.selectRow(self.tabelle.zeilen_daten.index(sid))
            self.tabelle.setFocus()

    def aktuelle_person(self) -> int | None:
        return self.tabelle.aktuelle_daten()

    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        self.sd, self.jahr, self.gruppe = sd, jahr, gruppe
        self.sortierung.blockSignals(True)
        self.sortierung.setCurrentIndex(self.sortierung.findData(gruppe.sortierung))
        self.sortierung.blockSignals(False)
        self.k_klasse.setVisible(gruppe.art == "klasse")
        self._fuellen()

    def _fuellen(self) -> None:
        self._mitglieder = self.sd.mitglieder(self.gruppe.id)
        stichtag = _stichtag(self.jahr)
        self.tabelle.fuelle(
            [[str(m.nummer), m.schueler.nachname, m.schueler.vorname, m.klasse, m.status] for m in self._mitglieder],
            [m.schueler.id for m in self._mitglieder],
            [not m.aktiv_am(stichtag) for m in self._mitglieder])
        aktiv = sum(m.aktiv_am(stichtag) for m in self._mitglieder)
        self.zusammenfassung.setText(f"{aktiv} aktiv" + (f", {len(self._mitglieder) - aktiv} ausgetreten bzw. "
                                                         "noch nicht eingetreten (grau)"
                                                         if aktiv != len(self._mitglieder) else ""))
        self._knoepfe()

    def _knoepfe(self) -> None:
        da = self.tabelle.aktuelle_daten() is not None
        eigene = self.sortierung.currentData() == "eigene"
        self.hoch.setEnabled(da and eigene)
        self.runter.setEnabled(da and eigene)
        self.k_zeitraum.setEnabled(da)
        self.k_entfernen.setEnabled(da)

    def _aktuell(self):
        sid = self.tabelle.aktuelle_daten()
        return next((m for m in self._mitglieder if m.schueler.id == sid), None)

    def _sortierung_geaendert(self) -> None:
        self.sd.setze_sortierung(self.gruppe.id, self.sortierung.currentData())
        self.gruppe = self.sd.lerngruppe(self.gruppe.id)
        self._fuellen()

    def _verschieben(self, schritt: int) -> None:
        m = self._aktuell()
        if m:
            self.sd.verschiebe(self.gruppe.id, m.schueler.id, schritt)
            self._fuellen()
            self.tabelle.selectRow(self.tabelle.zeilen_daten.index(m.schueler.id))

    def _hinzufuegen(self) -> None:
        d = MitgliederDialog(self.sd, self.jahr, self.gruppe, self)
        if d.exec():
            self._fuellen()
            self.geaendert.emit()

    def _importieren(self) -> None:
        from notenverwaltung.ui.import_assistent import ImportAssistent

        if ImportAssistent(self.sd, self.jahr, self.gruppe.id, self).exec():
            self._fuellen()
            self.geaendert.emit()

    def _klasse(self) -> None:
        klasse = self.gruppe.bezeichnung.split(" ")[0]
        neu = self.sd.uebernimm_klasse(self.gruppe.id, klasse, _stichtag(self.jahr))
        info(self, "Klasse vervollständigen",
             f"{neu} Schüler:in(nen) aus Klasse {klasse} aufgenommen." if neu else
             f"Alle Schüler:innen der Klasse {klasse} sind bereits in der Lerngruppe.")
        self._fuellen()
        self.geaendert.emit()

    def _zeitraum(self) -> None:
        m = self._aktuell()
        if m and ZeitraumDialog(self.sd, self.jahr, self.gruppe, m, self).exec():
            self._fuellen()
            self.geaendert.emit()

    def _entfernen(self) -> None:
        m = self._aktuell()
        if m is None or not frage(
            self, "Aus Lerngruppe entfernen",
            f"„{m.schueler.vorname} {m.schueler.nachname}“ aus „{self.gruppe.bezeichnung}“ entfernen?\n\n"
            "Das ist für versehentlich Hinzugefügte gedacht. Bei einem Kurswechsel besser "
            "„Eintritt / Austritt …“ verwenden – dann bleiben die Noten erhalten.", ja="Entfernen"):
            return
        self.sd.entferne_mitglied(self.gruppe.id, m.schueler.id)
        self._fuellen()
        self.geaendert.emit()


class LerngruppeSeite(Seite):
    """Eine Lerngruppe mit Reitern; spätere Etappen fügen Klassenarbeiten, mündliche Noten usw. hinzu."""

    geloescht = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self.knopf("Bearbeiten …", self._bearbeiten, self.kopf_knoepfe)
        self.knopf("Löschen", self._loeschen, self.kopf_knoepfe)
        self.reiter = QTabWidget()
        self.mitglieder = MitgliederTab()
        self.mitglieder.geaendert.connect(self.geaendert)
        from notenverwaltung.ui.seiten.arbeiten_tab import ArbeitenTab

        self.arbeiten = ArbeitenTab()
        self.arbeiten.geaendert.connect(self.geaendert)
        from notenverwaltung.ui.seiten.muendlich_tab import MuendlichTab

        self.muendlich = MuendlichTab()
        self.muendlich.geaendert.connect(self.geaendert)
        from notenverwaltung.ui.seiten.stunden_tab import StundenTab

        self.stunden = StundenTab()
        self.stunden.geaendert.connect(self.geaendert)
        from notenverwaltung.ui.seiten.sitzplan_tab import SitzplanTab

        self.sitzplan = SitzplanTab()
        self.sitzplan.geaendert.connect(self.geaendert)
        from notenverwaltung.ui.seiten.noten_tab import NotenTab

        self.noten = NotenTab()
        self.noten.geaendert.connect(self.geaendert)
        self.reiter.addTab(self.arbeiten, "Klassenarbeiten")
        self.reiter.addTab(self.muendlich, "Mündlich")
        self.reiter.addTab(self.stunden, "Schnellerfassung")
        self.reiter.addTab(self.sitzplan, "Sitzplan")
        self.reiter.addTab(self.noten, "Noten")
        self.reiter.addTab(self.mitglieder, "Schüler:innen")
        self.lay.addWidget(self.reiter, 1)

    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        self.sd, self.jahr = sd, jahr
        self.titel.setText(gruppe.bezeichnung)
        self.unterzeile.setText(f"{gruppe.beschreibung} · Schuljahr {jahr.bezeichnung}")
        neu = self.gruppe is None or self.gruppe.id != gruppe.id
        self.gruppe = gruppe
        self.reiter.setTabVisible(self.reiter.indexOf(self.arbeiten), gruppe.schriftlich)
        for i in range(self.reiter.count()):
            w = self.reiter.widget(i)
            if hasattr(w, "zeige") and self.reiter.isTabVisible(i):
                w.zeige(sd, jahr, gruppe)
        if neu:  # beim Wechsel der Lerngruppe den ersten sichtbaren Reiter zeigen
            erster = next(i for i in range(self.reiter.count()) if self.reiter.isTabVisible(i))
            self.reiter.setCurrentIndex(erster)

    def aktuelle_person(self) -> int | None:
        reiter = self.reiter.currentWidget()
        return reiter.aktuelle_person() if hasattr(reiter, "aktuelle_person") else None

    def markiere_person(self, sid: int) -> None:
        """Markiert die Person im gerade sichtbaren Reiter (Schnellsuche)."""
        reiter = self.reiter.currentWidget()
        if hasattr(reiter, "markiere_person"):
            reiter.markiere_person(sid)

    def _bearbeiten(self) -> None:
        if self.gruppe and LerngruppeDialog(self.sd, self.jahr, self.gruppe, self).exec():
            self.geaendert.emit()

    def _loeschen(self) -> None:
        if self.gruppe is None or not frage(
            self, "Lerngruppe löschen",
            f"„{self.gruppe.bezeichnung}“ mit allen zugehörigen Daten endgültig löschen?\n\n"
            "Die Schüler:innen selbst bleiben erhalten.", ja="Endgültig löschen", warnung=True):
            return
        self.sd.loesche_lerngruppe(self.gruppe.id)
        self.gruppe = None
        self.geloescht.emit()
