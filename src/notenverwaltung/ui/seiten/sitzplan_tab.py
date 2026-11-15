"""Reiter „Sitzplan“: Tische im Raster setzen, Schüler:innen auf Plätze setzen, per Antippen bewerten.

Drei Modi:
- **Tische:** Klicken oder Ziehen über das Raster setzt bzw. entfernt Plätze. Vorlagen für Reihen, Gruppentische, U.
- **Personen:** Name aus der Liste auf einen Platz ziehen (oder Name anklicken, dann Platz). Eine Person von Platz
  zu Platz ziehen tauscht. Doppelklick auf einen Platz macht ihn frei. „Verteilen“ füllt die freien Plätze.
- **Bewerten:** Platz antippen → ++ / + / o / – / –– für den gewählten Tag (Schnellerfassung).

Die Tafel ist oben (Sicht der Klasse); „Sicht vom Pult“ dreht den Plan.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.sitzplan import MAX, VORLAGEN, Sitzplaene, Sitzplan, SitzplanFehler
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Schuljahr, Stammdaten
from notenverwaltung.modell.stunden import SYMBOLE, Stunden
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, aktuelle_farben, frage

MIME = "application/x-notenverwaltung-schueler"
MODI = ("tische", "personen", "bewerten")


def kurzname(m: Mitglied) -> str:
    return f"{m.schueler.vorname}\n{m.schueler.nachname}"


class SitzplanFeld(QWidget):
    """Zeichnet das Raster und nimmt Mausaktionen entgegen. Daten kommen von außen (`setze_daten`)."""

    platz_umschalten = Signal(int, int, bool)          # x, y, vorhanden
    person_setzen = Signal(int, int, object)            # x, y, Schüler-ID oder None
    platz_angetippt = Signal(int, int, QPoint)          # Bewerten: x, y, globale Position

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(420, 300)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.modus = "personen"
        self.plan: Sitzplan | None = None
        self.plaetze: dict[tuple[int, int], int | None] = {}
        self.namen: dict[int, Mitglied] = {}
        self.bewertung: dict[int, int] = {}              # Schüler-ID → Wert am gewählten Tag
        self.pult = False                                # Sicht vom Pult: um 180° gedreht
        self.gewaehlt: int | None = None                 # Person aus der Liste, die als Nächstes gesetzt wird
        self._malen: bool | None = None                  # Tische: beim Ziehen setzen (True) oder entfernen
        self._gemalt: set[tuple[int, int]] = set()
        self._ziehen_von: tuple[int, int] | None = None
        self._druck = QPoint()

    def setze_daten(self, plan, plaetze, namen, bewertung) -> None:
        self.plan, self.plaetze, self.namen, self.bewertung = plan, plaetze, namen, bewertung
        self.update()

    # ---- Geometrie ------------------------------------------------------------------------------
    def _zelle(self) -> tuple[float, float, float]:
        """(Größe einer Zelle, Rand links, Rand oben) – Tafel bekommt oben bzw. unten einen Streifen."""
        if self.plan is None:
            return 1.0, 0.0, 0.0
        streifen = 26.0
        b = (self.width() - 8) / self.plan.spalten
        h = (self.height() - streifen - 8) / self.plan.zeilen
        g = min(b, h * 1.4)
        hoehe = g / 1.4
        links = (self.width() - g * self.plan.spalten) / 2
        oben = streifen + 4 if not self.pult else 4
        return g, links, oben + (self.height() - streifen - 8 - hoehe * self.plan.zeilen) / 2

    def rechteck(self, x: int, y: int) -> QRectF:
        g, links, oben = self._zelle()
        h = g / 1.4
        if self.pult:
            x, y = self.plan.spalten - 1 - x, self.plan.zeilen - 1 - y
        return QRectF(links + x * g + 3, oben + y * h + 3, g - 6, h - 6)

    def zelle_bei(self, pos) -> tuple[int, int] | None:
        if self.plan is None:
            return None
        for x in range(self.plan.spalten):
            for y in range(self.plan.zeilen):
                if self.rechteck(x, y).adjusted(-3, -3, 3, 3).contains(pos):
                    return x, y
        return None

    # ---- Zeichnen -------------------------------------------------------------------------------
    def paintEvent(self, _ereignis) -> None:  # noqa: N802
        if self.plan is None:
            return
        f = aktuelle_farben()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g, links, oben = self._zelle()
        breite = g * self.plan.spalten
        # Tafel
        tafel = QRectF(links + breite * 0.25, 2 if not self.pult else self.height() - 24, breite * 0.5, 20)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(f.flaeche_hoch))
        p.drawRoundedRect(tafel, 4, 4)
        p.setPen(QColor(f.text_leise))
        p.drawText(tafel, int(Qt.AlignmentFlag.AlignCenter), "Tafel / vorne")
        schrift = QFont(self.font())
        schrift.setPointSizeF(max(6.5, min(10.0, g / 11)))
        for x in range(self.plan.spalten):
            for y in range(self.plan.zeilen):
                r = self.rechteck(x, y)
                if (x, y) not in self.plaetze:
                    if self.modus == "tische":
                        p.setPen(QPen(QColor(f.rand), 1, Qt.PenStyle.DotLine))
                        p.setBrush(Qt.BrushStyle.NoBrush)
                        p.drawRoundedRect(r, 6, 6)
                    continue
                sid = self.plaetze[(x, y)]
                m = self.namen.get(sid) if sid else None
                p.setPen(QPen(QColor(f.akzent if sid == self.gewaehlt and sid else f.rand), 1.5))
                p.setBrush(QColor(f.flaeche_hoch if m else f.flaeche))
                p.drawRoundedRect(r, 6, 6)
                if sid and m is None:
                    p.setPen(QColor(f.text_leise))
                    p.setFont(schrift)
                    p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), "(nicht mehr\nin der Gruppe)")
                elif m is not None:
                    p.setPen(QColor(f.text))
                    p.setFont(schrift)
                    p.drawText(r.adjusted(2, 2, -2, -2), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                               kurzname(m))
                    wert = self.bewertung.get(sid)
                    if wert is not None and self.modus == "bewerten":
                        marke = QRectF(r.right() - 26, r.top() + 2, 24, 16)
                        p.setPen(Qt.PenStyle.NoPen)
                        p.setBrush(QColor(f.akzent if wert <= 2 else f.fehler if wert >= 4 else f.rand))
                        p.drawRoundedRect(marke, 4, 4)
                        p.setPen(QColor(f.akzent_text))
                        fett = QFont(schrift)
                        fett.setBold(True)
                        p.setFont(fett)
                        p.drawText(marke, int(Qt.AlignmentFlag.AlignCenter), SYMBOLE[wert])
                else:
                    p.setPen(QColor(f.text_leise))
                    p.setFont(schrift)
                    p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), "frei")
        p.end()

    # ---- Maus -----------------------------------------------------------------------------------
    def mousePressEvent(self, ereignis) -> None:  # noqa: N802
        zelle = self.zelle_bei(ereignis.position())
        if zelle is None or ereignis.button() != Qt.MouseButton.LeftButton:
            return
        self._druck = ereignis.position().toPoint()
        if self.modus == "tische":
            self._malen = zelle not in self.plaetze
            self._gemalt = {zelle}
            self.platz_umschalten.emit(*zelle, self._malen)
        elif self.modus == "personen":
            if zelle in self.plaetze and self.gewaehlt is not None:
                self.person_setzen.emit(*zelle, self.gewaehlt)
                self.gewaehlt = None
            elif self.plaetze.get(zelle):
                self._ziehen_von = zelle
        elif self.modus == "bewerten" and self.plaetze.get(zelle) in self.namen:
            self.platz_angetippt.emit(*zelle, ereignis.globalPosition().toPoint())

    def mouseMoveEvent(self, ereignis) -> None:  # noqa: N802
        if self.modus == "tische" and self._malen is not None:
            zelle = self.zelle_bei(ereignis.position())
            if zelle is not None and zelle not in self._gemalt:
                self._gemalt.add(zelle)
                if (zelle in self.plaetze) != self._malen:
                    self.platz_umschalten.emit(*zelle, self._malen)
        elif (self.modus == "personen" and self._ziehen_von is not None
              and (ereignis.position().toPoint() - self._druck).manhattanLength() > 8):
            sid = self.plaetze.get(self._ziehen_von)
            self._ziehen_von = None
            if sid:
                drag = QDrag(self)
                daten = QMimeData()
                daten.setData(MIME, str(sid).encode())
                drag.setMimeData(daten)
                drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, _ereignis) -> None:  # noqa: N802
        self._malen = None
        self._ziehen_von = None

    def mouseDoubleClickEvent(self, ereignis) -> None:  # noqa: N802
        zelle = self.zelle_bei(ereignis.position())
        if self.modus == "personen" and zelle is not None and self.plaetze.get(zelle):
            self.person_setzen.emit(*zelle, None)

    def dragEnterEvent(self, ereignis) -> None:  # noqa: N802
        if ereignis.mimeData().hasFormat(MIME) and self.modus == "personen":
            ereignis.acceptProposedAction()

    def dragMoveEvent(self, ereignis) -> None:  # noqa: N802
        zelle = self.zelle_bei(ereignis.position())
        if zelle in self.plaetze:
            ereignis.acceptProposedAction()
        else:
            ereignis.ignore()

    def dropEvent(self, ereignis) -> None:  # noqa: N802
        zelle = self.zelle_bei(ereignis.position())
        if zelle in self.plaetze:
            sid = int(bytes(ereignis.mimeData().data(MIME)).decode())
            self.person_setzen.emit(*zelle, sid)
            ereignis.acceptProposedAction()


class PersonenListe(QListWidget):
    """Wer noch keinen Platz hat – zum Ziehen auf den Plan."""

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)

    def startDrag(self, _aktionen) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        drag = QDrag(self)
        daten = QMimeData()
        daten.setData(MIME, str(item.data(Qt.ItemDataRole.UserRole)).encode())
        drag.setMimeData(daten)
        drag.exec(Qt.DropAction.MoveAction)


class SitzplanTab(QWidget):
    geaendert = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.sd: Stammdaten | None = None
        self.jahr: Schuljahr | None = None
        self.gruppe: Lerngruppe | None = None
        self.plan: Sitzplan | None = None

        self.auswahl = QComboBox()
        self.auswahl.setMinimumWidth(180)
        self.auswahl.currentIndexChanged.connect(self._plan_gewaehlt)
        neu, umbenennen, loeschen, drucken = (QPushButton(t) for t in ("Neuer Plan …", "Umbenennen …", "Löschen",
                                                                       "Drucken / PDF …"))
        neu.clicked.connect(self.neuer_plan)
        umbenennen.clicked.connect(self.umbenennen)
        loeschen.clicked.connect(self.loeschen)
        drucken.clicked.connect(self.drucken)
        self.k_plan = [umbenennen, loeschen, drucken]
        zeile1 = QHBoxLayout()
        zeile1.addWidget(QLabel("Plan:"))
        zeile1.addWidget(self.auswahl)
        for k in (neu, umbenennen, loeschen):
            zeile1.addWidget(k)
        zeile1.addStretch(1)
        self.pult = QCheckBox("Sicht vom Pult")
        self.pult.setToolTip("Dreht den Plan: die Tafel ist unten, so wie du vorne stehend auf die Klasse schaust.")
        self.pult.toggled.connect(self._pult)
        zeile1.addWidget(self.pult)
        zeile1.addWidget(drucken)

        self.modi = QButtonGroup(self)
        zeile2 = QHBoxLayout()
        for i, (schluessel, text, tipp) in enumerate((
                ("tische", "1  Tische", "Klicken oder Ziehen setzt bzw. entfernt Plätze."),
                ("personen", "2  Personen", "Namen auf Plätze ziehen; Platz zu Platz tauscht; Doppelklick macht frei."),
                ("bewerten", "3  Bewerten", "Platz antippen: ++ + o – –– für den gewählten Tag."))):
            k = QPushButton(text)
            k.setCheckable(True)
            k.setToolTip(tipp)
            k.setProperty("modus", schluessel)
            self.modi.addButton(k, i)
            zeile2.addWidget(k)
        self.modi.idClicked.connect(lambda i: self.setze_modus(MODI[i]))
        zeile2.addSpacing(12)
        self.werkzeuge = QWidget()
        wz = QHBoxLayout(self.werkzeuge)
        wz.setContentsMargins(0, 0, 0, 0)
        self.vorlage = QComboBox()
        for k, text in VORLAGEN.items():
            self.vorlage.addItem(text, k)
        anwenden = QPushButton("Vorlage anwenden")
        anwenden.clicked.connect(self.vorlage_anwenden)
        self.spalten = QSpinBox(minimum=1, maximum=MAX)
        self.zeilen = QSpinBox(minimum=1, maximum=MAX)
        self.spalten.setPrefix("Breite ")
        self.zeilen.setPrefix("Reihen ")
        self.spalten.valueChanged.connect(self._groesse)
        self.zeilen.valueChanged.connect(self._groesse)
        for w in (self.vorlage, anwenden, self.spalten, self.zeilen):
            wz.addWidget(w)
        zeile2.addWidget(self.werkzeuge)
        self.personen_werkzeuge = QWidget()
        pw = QHBoxLayout(self.personen_werkzeuge)
        pw.setContentsMargins(0, 0, 0, 0)
        for text, art in (("Alphabetisch verteilen", "alphabet"), ("Zufällig verteilen", "zufall")):
            k = QPushButton(text)
            k.clicked.connect(lambda _=False, a=art: self.verteilen(a))
            pw.addWidget(k)
        leeren = QPushButton("Alle abräumen")
        leeren.clicked.connect(self.abraeumen)
        pw.addWidget(leeren)
        zeile2.addWidget(self.personen_werkzeuge)
        self.bewerten_werkzeuge = QWidget()
        bw = QHBoxLayout(self.bewerten_werkzeuge)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.addWidget(QLabel("Tag:"))
        self.datum = Datumsfeld()
        self.datum.dateChanged.connect(self._laden)
        bw.addWidget(self.datum)
        zeile2.addWidget(self.bewerten_werkzeuge)
        zeile2.addStretch(1)

        self.feld = SitzplanFeld()
        self.feld.platz_umschalten.connect(self._platz)
        self.feld.person_setzen.connect(self._person)
        self.feld.platz_angetippt.connect(self._bewerten)
        self.liste = PersonenListe()
        self.liste.itemClicked.connect(self._liste_gewaehlt)
        self.liste_titel = QLabel("<b>Ohne Platz</b>")
        rechts = QWidget()
        rl = QVBoxLayout(rechts)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.liste_titel)
        rl.addWidget(self.liste, 1)
        self.teiler = QSplitter()
        self.teiler.addWidget(self.feld)
        self.teiler.addWidget(rechts)
        self.teiler.setStretchFactor(0, 1)
        self.teiler.setSizes([800, 200])
        self.leer = QLabel("Noch kein Sitzplan. Mit „Neuer Plan …“ geht es los.", objectName="leise")
        self.meldung = Hinweis()
        self.hilfe = QLabel(objectName="leise")
        self.hilfe.setWordWrap(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.addLayout(zeile1)
        lay.addLayout(zeile2)
        lay.addWidget(self.leer)
        lay.addWidget(self.teiler, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(self.hilfe)
        self.modi.button(1).setChecked(True)
        self.setze_modus("personen")

    # ---- Anzeige ---------------------------------------------------------------------------------
    def zeige(self, sd: Stammdaten, jahr: Schuljahr, gruppe: Lerngruppe) -> None:
        if self.sd is not sd:
            self.sd = sd
            self.sp = Sitzplaene(sd.v)
            self.st = Stunden(sd.v)
        neue_gruppe = self.gruppe is None or self.gruppe.id != gruppe.id
        self.jahr, self.gruppe = jahr, gruppe
        self.datum.blockSignals(True)
        self.datum.begrenze(jahr.beginn, jahr.ende)
        if neue_gruppe:                       # beim Wechsel der Gruppe: heute; sonst bleibt der gewählte Tag
            self.datum.setze(min(max(date.today(), jahr.beginn), jahr.ende))
        self.datum.blockSignals(False)
        bisher = self.auswahl.currentData()
        self.auswahl.blockSignals(True)
        self.auswahl.clear()
        for p in self.sp.plaene(gruppe.id):
            self.auswahl.addItem(p.name, p.id)
        idx = self.auswahl.findData(bisher)
        self.auswahl.setCurrentIndex(idx if idx >= 0 else 0)
        self.auswahl.blockSignals(False)
        self._plan_gewaehlt()

    def _plan_gewaehlt(self, *_) -> None:
        pid = self.auswahl.currentData()
        self.plan = self.sp.plan(pid) if pid is not None else None
        da = self.plan is not None
        self.leer.setVisible(not da)
        self.teiler.setVisible(da)
        for w in self.k_plan + [self.werkzeuge, self.personen_werkzeuge]:
            w.setEnabled(da)
        if da:
            for s, wert in ((self.spalten, self.plan.spalten), (self.zeilen, self.plan.zeilen)):
                s.blockSignals(True)
                s.setValue(wert)
                s.blockSignals(False)
        self._laden()

    def aktive_mitglieder(self) -> list[Mitglied]:
        tag = self.datum.wert()
        return [m for m in self.sd.mitglieder(self.gruppe.id) if m.aktiv_am(tag)]

    def _laden(self, *_) -> None:
        if self.plan is None:
            self.feld.setze_daten(None, {}, {}, {})
            self.liste.clear()
            return
        plaetze = self.sp.plaetze(self.plan.id)
        mitglieder = self.aktive_mitglieder()
        namen = {m.schueler.id: m for m in mitglieder}
        tag = self.datum.wert()
        bewertung = {sid: b.wert for (sid, d), b in self.st.eintraege(self.gruppe.id).items() if d == tag}
        self.feld.setze_daten(self.plan, plaetze, namen, bewertung)
        sitzend = {sid for sid in plaetze.values() if sid}
        self.liste.clear()
        for m in mitglieder:
            if m.schueler.id not in sitzend:
                item = QListWidgetItem(f"{m.schueler.nachname}, {m.schueler.vorname}")
                item.setData(Qt.ItemDataRole.UserRole, m.schueler.id)
                self.liste.addItem(item)
        frei = sum(1 for sid in plaetze.values() if sid is None)
        self.liste_titel.setText(f"<b>Ohne Platz</b> ({self.liste.count()}) · {frei} freie Plätze")

    def setze_modus(self, modus: str) -> None:
        self.feld.modus = modus
        self.feld.gewaehlt = None
        self.werkzeuge.setVisible(modus == "tische")
        self.personen_werkzeuge.setVisible(modus == "personen")
        self.bewerten_werkzeuge.setVisible(modus == "bewerten")
        self.hilfe.setText({
            "tische": "Klicken oder Ziehen setzt bzw. entfernt Plätze. Vorlage wählen und anwenden für Reihen, "
                      "Gruppentische oder U-Form. Wer sitzt, behält seinen Platz.",
            "personen": "Namen aus der Liste auf einen Platz ziehen – oder Namen anklicken, dann den Platz. "
                        "Von Platz zu Platz ziehen tauscht. Doppelklick macht einen Platz frei.",
            "bewerten": "Platz antippen und ++ + o – –– wählen – das landet in der Schnellerfassung (Tag oben).",
        }[modus])
        self.feld.update()

    # ---- Aktionen --------------------------------------------------------------------------------
    def neuer_plan(self) -> None:
        name, ok = QInputDialog.getText(self, "Neuer Sitzplan", "Name (z. B. Raum oder „Klassenarbeit“):",
                                        text="Sitzplan" if not self.sp.plaene(self.gruppe.id) else "")
        if not ok:
            return
        plan = self.sp.lege_an(self.gruppe.id, name)
        self.zeige(self.sd, self.jahr, self.gruppe)
        self.auswahl.setCurrentIndex(self.auswahl.findData(plan.id))
        self.modi.button(1).setChecked(True)
        self.setze_modus("personen")
        self.meldung.setze("Plan mit 2er-Tischen angelegt. Tische ändern: Modus „Tische“. "
                           "Personen setzen: ziehen oder „Alphabetisch verteilen“.", "info")

    def umbenennen(self) -> None:
        name, ok = QInputDialog.getText(self, "Sitzplan umbenennen", "Name:", text=self.plan.name)
        if ok:
            try:
                self.sp.umbenennen(self.plan.id, name)
            except SitzplanFehler as e:
                self.meldung.setze(str(e), "fehler")
                return
            self.zeige(self.sd, self.jahr, self.gruppe)

    def loeschen(self) -> None:
        if self.plan and frage(self, "Sitzplan löschen", f"Den Sitzplan „{self.plan.name}“ löschen?",
                               ja="Löschen", warnung=True):
            self.sp.loesche(self.plan.id)
            self.zeige(self.sd, self.jahr, self.gruppe)

    def _groesse(self, *_) -> None:
        if self.plan is None:
            return
        self.sp.setze_groesse(self.plan.id, self.spalten.value(), self.zeilen.value())
        self.plan = self.sp.plan(self.plan.id)
        self._laden()

    def vorlage_anwenden(self) -> None:
        self.sp.vorlage(self.plan.id, self.vorlage.currentData())
        self._laden()

    def _platz(self, x: int, y: int, vorhanden: bool) -> None:
        self.sp.setze_platz(self.plan.id, x, y, vorhanden)
        self._laden()

    def _person(self, x: int, y: int, sid) -> None:
        self.sp.setze_person(self.plan.id, x, y, sid)
        self._laden()

    def _liste_gewaehlt(self, item: QListWidgetItem) -> None:
        self.feld.gewaehlt = item.data(Qt.ItemDataRole.UserRole)
        self.meldung.setze(f"{item.text()}: jetzt auf einen Platz klicken.", "info")
        self.feld.update()

    def verteilen(self, art: str) -> None:
        n = self.sp.verteile(self.plan.id, self.aktive_mitglieder(), art)
        self._laden()
        rest = self.liste.count()
        self.meldung.setze(f"{n} verteilt." + (f" {rest} ohne Platz – es fehlen Plätze." if rest else ""),
                           "warnung" if rest else "ok")

    def abraeumen(self) -> None:
        if frage(self, "Alle abräumen", "Alle Personen von ihren Plätzen nehmen? Die Tische bleiben stehen.",
                 ja="Abräumen"):
            self.sp.raeume_ab(self.plan.id)
            self._laden()

    def _pult(self, an: bool) -> None:
        self.feld.pult = an
        self.feld.update()

    def _bewerten(self, x: int, y: int, wo: QPoint) -> None:
        sid = self.feld.plaetze.get((x, y))
        m = self.feld.namen.get(sid)
        if m is None:
            return
        tag = self.datum.wert()
        bisher = self.feld.bewertung.get(sid)
        menue = QMenu(self)
        menue.addSection(f"{m.schueler.vorname} {m.schueler.nachname} · {tag:%d.%m.}")
        for w, symbol in SYMBOLE.items():
            a = menue.addAction(symbol)
            a.setCheckable(True)
            a.setChecked(bisher == w)
            a.triggered.connect(lambda _=False, w=w: self.bewerte(sid, w))
        weg = menue.addAction("Löschen")
        weg.setEnabled(bisher is not None)
        weg.triggered.connect(lambda: self.bewerte(sid, None))
        menue.exec(wo)

    def bewerte(self, sid: int, wert: int | None) -> None:
        self.st.setze(self.gruppe.id, sid, self.datum.wert(), wert)
        self._laden()
        self.geaendert.emit()

    def markiere_person(self, sid: int) -> None:
        self.feld.gewaehlt = sid
        self.feld.update()

    def drucken(self) -> None:
        from notenverwaltung.ausgabe.sitzplan import SitzplanAusgabe
        from notenverwaltung.ui.vorschau_dialog import VorschauDialog

        optionen = QWidget()
        ol = QVBoxLayout(optionen)
        ol.setContentsMargins(0, 0, 0, 0)
        pult = QCheckBox("Sicht vom Pult (Tafel unten)")
        pult.setChecked(self.pult.isChecked())
        nachname = QCheckBox("Nachnamen ausschreiben")
        nachname.setChecked(True)
        ol.addWidget(pult)
        ol.addWidget(nachname)
        hinweis = QLabel("Ohne Noten – zum Mitgeben an Vertretungskräfte.", objectName="leise")
        hinweis.setWordWrap(True)
        ol.addWidget(hinweis)
        plan, plaetze, namen = self.plan, self.sp.plaetze(self.plan.id), dict(self.feld.namen)

        def baue():
            return SitzplanAusgabe(self.gruppe, plan, plaetze, namen, pult=pult.isChecked(),
                                   nachname=nachname.isChecked())

        d = VorschauDialog(f"Sitzplan – {self.gruppe.bezeichnung}", baue, optionen, self.sd.v,
                           f"Sitzplan {self.gruppe.bezeichnung} {plan.name}.pdf", self)
        pult.toggled.connect(d.aktualisieren)
        nachname.toggled.connect(d.aktualisieren)
        d.aktualisieren()
        self._druckdialog = d
        d.exec()
