"""Rückmeldebogen: je Person ein Bogen mit Aufgaben, Punkten, Note (ohne Tendenz) und Rückmeldung.

Der Bogen wird vor dem Zeichnen ausgemessen. Lange Erwartungshorizonte (z. B. aus der KI-Hilfe) nutzen die ganze
Tabellenbreite, Teilaufgaben „a) … b) …“ beginnen jeweils in einer neuen Zeile. Passt ein Bogen nicht auf eine Seite,
wird zuerst die Schrift des Erwartungshorizonts etwas kleiner; reicht das nicht, geht er auf einer Folgeseite weiter:
Tabellenkopf wiederholt, Note, Rückmeldung und Unterschriften am Ende. Nichts wird abgeschnitten oder überdruckt.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetricsF, QImage, QPainter

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import STATUS, Arbeit, Arbeiten, Aufgabe, Ergebnis
from notenverwaltung.modell.noten import zahl_text

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
OBEN_LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 20.0
BREITE = 210 - 2 * RAND
OBEN = 18.0
UNTEN = 297 - 14.0             # unten genügt weniger Rand (Drucker: etwa 5 mm)
ZEILE = 7.0
FUSS = 7.0                    # Platz für „Fortsetzung auf Seite …“
UNTERSCHRIFT = 22.0           # Datum und Unterschriftszeilen am Ende der letzten Seite
KOPF_FOLGE = 13.0             # Kopf der Folgeseiten
ERW_GROESSEN = (8.5, 8.0, 7.5, 7.0) # Schrift des Erwartungshorizonts: kleiner, bevor eine Folgeseite nötig wird
MAX_STUECK = 110.0            # längere Absätze werden geteilt, damit sie über Seiten fließen können
TITEL_PT, TITEL_MIN_PT = 16.0, 12.0

# Spalten: Aufgabe | Thema | möglich | erreicht | Anteil
SP_AUFGABE = (RAND, 18.0)
SP_THEMA = (RAND + 18.0, BREITE - 18.0 - 58.0)
SP_MOEGLICH = (RAND + BREITE - 58.0, 20.0)
SP_ERREICHT = (RAND + BREITE - 38.0, 20.0)
SP_ANTEIL = (RAND + BREITE - 18.0, 18.0)
ERW_X = SP_THEMA[0] + 1.5
ERW_BREITE = RAND + BREITE - 2.5 - ERW_X

_TEILAUFGABE = re.compile(r"\s+(?=[a-z]\)\s)")      # „… (1 P.). b) Schaltung …“ → neuer Absatz vor „b)“
_SATZENDE = re.compile(r"(?<=[.!?;])\s+")

Op = Callable[[Seite], None]


def absaetze(text: str) -> list[str]:
    """Zerlegt einen Erwartungshorizont in Absätze: Zeilenumbrüche und Teilaufgaben „a) … b) …“."""
    teile: list[str] = []
    for zeile in text.splitlines():
        teile += [t.strip() for t in _TEILAUFGABE.split(zeile) if t.strip()]
    return teile


class _Messung:
    """Misst Texte so, wie sie im PDF (600 dpi) gesetzt werden – unabhängig vom späteren Gerät."""

    def __init__(self, schrift: str | None) -> None:
        self.bild = QImage(8, 8, QImage.Format.Format_RGB32)
        self.bild.setDotsPerMeterX(int(600 / 0.0254))
        self.bild.setDotsPerMeterY(int(600 / 0.0254))
        self.bild.fill(QColor("#ffffff"))
        self.p = QPainter(self.bild)
        self.s = Seite(self.p)
        self.s.schriftfamilie = schrift
        self._cache: dict[tuple, float] = {}

    def hoehe(self, text: str, breite: float, pt: float, fett: bool = False, kursiv: bool = False) -> float:
        k = ("h", text, breite, pt, fett, kursiv)
        if k not in self._cache:
            self.s.schrift(pt, fett, kursiv=kursiv)
            self._cache[k] = self.s.texthoehe_mm(breite, text)
        return self._cache[k]

    def breite(self, text: str, pt: float, fett: bool = False) -> float:
        self.s.schrift(pt, fett)
        return self.s.textbreite_mm(text)

    def ende(self) -> None:
        self.p.end()


class Rueckmeldebogen(Ausgabe):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, nur_mit_note: bool = True, erwartung: bool = True,
                 unterschrift: bool = True, datum: date | None = None, schueler_ids: list[int] | None = None,
                 beidseitig: bool = False) -> None:
        self.ar, self.arbeit = ar, arbeit
        self.erwartung = erwartung
        self.unterschrift = unterschrift
        self.beidseitig = beidseitig       # jeder Bogen beginnt auf einem neuen Blatt (leere Rückseiten)
        self.datum = datum or arbeit.rueckgabe or date.today()
        self.gruppe = ar.sd.lerngruppe(arbeit.lerngruppe_id)
        self.aufgaben = ar.aufgaben(arbeit.id)
        self.hoechst = sum(a.max_punkte for a in self.aufgaben)
        ergebnisse = ar.ergebnisse(arbeit.id)
        if schueler_ids is not None:
            ergebnisse = [e for e in ergebnisse if e.mitglied.schueler.id in schueler_ids]
        elif nur_mit_note:
            ergebnisse = [e for e in ergebnisse if e.note is not None]
        self.ergebnisse: list[Ergebnis] = ergebnisse
        self.titel = f"Rückmeldebögen {self.gruppe.bezeichnung} – {arbeit.titel}"
        self._plan_fuer: tuple | None = None
        self._seiten: list[list[Op] | None] = []
        self.seiten_je_bogen: list[int] = []
        self.erwartung_pt = ERW_GROESSEN[0]

    # ---- Planung ---------------------------------------------------------------------------------
    def _plan(self) -> list[list[Op] | None]:
        schluessel = (self.schrift, self.beidseitig)
        if self._plan_fuer == schluessel:
            return self._seiten
        m = _Messung(self.schrift)
        try:
            self._kopf_messen(m)
            seiten: list[list[Op] | None] = []
            self.seiten_je_bogen = []
            # Eine Schriftgröße für alle Bögen: die größte, bei der jeder Bogen auf eine Seite passt, der passen kann.
            # Wer auch mit der kleinsten nicht auf eine Seite kommt, bekommt eine Folgeseite in gut lesbarer Größe.
            groesse = ERW_GROESSEN[0]
            for e in self.ergebnisse:
                passend = next((pt for pt in ERW_GROESSEN if pt <= groesse
                                and len(self._plane_bogen(e, m, pt)) == 1), None)
                if passend is not None:
                    groesse = passend
            self.erwartung_pt = groesse
            for e in self.ergebnisse:
                bogen = self._plane_bogen(e, m, groesse)
                if len(bogen) > 1:
                    bogen = self._plane_bogen(e, m, ERW_GROESSEN[0])
                self.seiten_je_bogen.append(len(bogen))
                seiten += bogen
                if self.beidseitig and len(bogen) % 2:
                    seiten.append(None)
        finally:
            m.ende()
        self._seiten = seiten or [[self._keine_ergebnisse]]
        self._plan_fuer = schluessel
        return self._seiten

    @property
    def mehrseitig(self) -> bool:
        self._plan()
        return any(n > 1 for n in self.seiten_je_bogen)

    def _kopf_messen(self, m: _Messung) -> None:
        titel = f"Rückmeldung zur {self.arbeit.titel}"
        pt = TITEL_PT
        while pt > TITEL_MIN_PT and m.breite(titel, pt, True) > BREITE:
            pt -= 0.5
        self._titel = (titel, pt, max(8.0, m.hoehe(titel, BREITE, pt, True)))
        thema = f" · {self.arbeit.thema}" if self.arbeit.thema else ""
        unter = (f"{self.gruppe.fach} · {self.gruppe.bezeichnung} · geschrieben am "
                 f"{self.arbeit.datum:%d.%m.%Y}{thema}")
        self._unterzeile = (unter, max(5.0, m.hoehe(unter, BREITE, 10)))
        self._kopf_h = self._titel[2] + 1 + self._unterzeile[1] + 5 + 11
        self._thema_h = [max(ZEILE, m.hoehe(a.thema or "", SP_THEMA[1] - 3, 10) + 2) for a in self.aufgaben]

    def _stuecke(self, text: str, breite: float, pt: float, m: _Messung, kursiv: bool = False) -> list[tuple[str, float]]:
        """Absätze mit Höhe; zu lange Absätze werden an Satzenden (notfalls Wortgrenzen) geteilt."""
        ergebnis = []
        for absatz in absaetze(text):
            for teil in self._teile(absatz, breite, pt, m, kursiv):
                ergebnis.append((teil, m.hoehe(teil, breite, pt, kursiv=kursiv)))
        return ergebnis

    def _teile(self, text: str, breite: float, pt: float, m: _Messung, kursiv: bool) -> list[str]:
        if m.hoehe(text, breite, pt, kursiv=kursiv) <= MAX_STUECK:
            return [text]
        saetze = _SATZENDE.split(text)
        woerter = len(saetze) == 1
        token = text.split() if woerter else saetze
        teile, aktuell = [], ""
        for t in token:
            probe = f"{aktuell} {t}".strip()
            if aktuell and m.hoehe(probe, breite, pt, kursiv=kursiv) > MAX_STUECK:
                teile.append(aktuell)
                aktuell = t
            else:
                aktuell = probe
        if aktuell:
            teile.append(aktuell)
        if woerter:
            return teile
        return [x for t in teile for x in self._teile(t, breite, pt, m, kursiv)]

    def _plane_bogen(self, e: Ergebnis, m: _Messung, erw_pt: float) -> list[list[Op]]:
        seiten: list[list[Op]] = []
        ops: list[Op] = []
        y = 0.0
        grenze = UNTEN - FUSS

        def neue_seite() -> None:
            nonlocal ops, y
            ops = []
            seiten.append(ops)
            y = OBEN + (self._kopf_h if len(seiten) == 1 else KOPF_FOLGE)

        neue_seite()
        if e.summe is None and e.note is not None:
            # Note ohne Punkte festgesetzt (z. B. Nachschreibarbeit): keine leere Punktetabelle
            ops.append(partial(self._ohne_punkte, y=y))
            y += 12
        else:
            tab_y0 = y

            def tab_kopf() -> None:
                nonlocal y, tab_y0
                tab_y0 = y
                ops.append(partial(self._tabellenkopf, y=y))
                y += ZEILE

            def tab_ende() -> None:
                ops.append(partial(self._rahmen, y0=tab_y0, y1=y))

            def hintergrund(i: int, idx: int, y0: float) -> None:
                if i % 2:
                    ops.insert(idx, partial(self._flaeche, y0=y0, y1=y))

            tab_kopf()
            for i, a in enumerate(self.aufgaben):
                kopf_h = self._thema_h[i]
                stuecke = (self._stuecke(a.erwartung.strip(), ERW_BREITE, erw_pt, m, kursiv=True)
                           if self.erwartung and a.erwartung.strip() else [])
                if y + kopf_h + (stuecke[0][1] + 1.0 if stuecke else 0) > grenze:
                    tab_ende()
                    neue_seite()
                    tab_kopf()
                y0, idx = y, len(ops)
                ops.append(partial(self._zeilenkopf, a=a, e=e, y=y, h=kopf_h))
                y += kopf_h - (1.0 if stuecke else 0)
                for text, h in stuecke:
                    if y + h + 2.0 > grenze:              # 2 mm: Abstand unter dem Absatz bis zum Rahmen
                        hintergrund(i, idx, y0)
                        tab_ende()
                        neue_seite()
                        tab_kopf()
                        y0, idx = y, len(ops)
                        ops.append(partial(self._zeilenkopf_fortsetzung, a=a, y=y))
                        y += ZEILE - 1
                    ops.append(partial(self._erwartung, text=text, y=y, h=h, pt=erw_pt))
                    y += h + 0.6
                if stuecke:
                    y += 1.4
                hintergrund(i, idx, y0)
            if y + ZEILE + 1 > grenze:
                tab_ende()
                neue_seite()
                tab_kopf()
            ops.append(partial(self._summe, e=e, y=y))
            y += ZEILE + 1
            tab_ende()
            y += 6

        # Schluss: Note, Rückmeldung, Unterschriften – möglichst zusammen auf einer Seite
        kommentar = (self._stuecke(e.kommentar.strip(), BREITE, 10.5, m)
                     if e.kommentar and e.kommentar.strip() else [])
        schluss = 18 + (7 + sum(h + 1.5 for _, h in kommentar) if kommentar else 0)
        frei = UNTEN - (UNTERSCHRIFT if self.unterschrift else FUSS)
        if y + 12 > grenze or (y + schluss > frei and OBEN + KOPF_FOLGE + schluss <= frei):
            neue_seite()
        ops.append(partial(self._note, e=e, y=y))
        y += 18

        # Rückmeldung
        if kommentar:
            if y + 7 + kommentar[0][1] > grenze:
                neue_seite()
            ops.append(partial(self._rueckmeldung_titel, y=y))
            y += 7
            for text, h in kommentar:
                if y + h > grenze:
                    neue_seite()
                ops.append(partial(self._absatz, text=text, y=y, h=h))
                y += h + 1.5

        if self.unterschrift:
            if y > UNTEN - UNTERSCHRIFT:
                neue_seite()
            ops.append(self._unterschriften)

        n = len(seiten)
        for k, seite in enumerate(seiten):
            seite.insert(0, partial(self._kopf, e=e, k=k, n=n))
            if k < n - 1:
                seite.append(partial(self._weiter, k=k))
        return seiten

    # ---- Ausgabe ---------------------------------------------------------------------------------
    def seitenzahl(self) -> int:
        return len(self._plan())

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        seite = self._plan()[nummer]
        for op in seite or []:          # None: leere Rückseite für beidseitigen Druck
            s.stift("#000000")
            op(s)

    def _keine_ergebnisse(self, s: Seite) -> None:
        s.schrift(11)
        s.text(RAND, OBEN, BREITE, 10, "Noch keine Ergebnisse.", LINKS)

    def _kopf(self, s: Seite, e: Ergebnis, k: int, n: int) -> None:
        if self.kopfzeile:
            s.schrift(8.5)
            s.stift("#555555")
            s.text(RAND, OBEN - 9, BREITE, 5, self.kopfzeile, RECHTS)
            s.stift("#000000")
        name = f"{e.mitglied.schueler.vorname} {e.mitglied.schueler.nachname}"
        seite = f"Seite {k + 1} von {n}" if n > 1 else ""
        if k:
            f = s.schrift(10, fett=True)
            zeile = QFontMetricsF(f, s.p.device()).elidedText(f"{name} – Rückmeldung zur {self.arbeit.titel}",
                                                              Qt.TextElideMode.ElideRight, s.mm_in_px(BREITE * 0.75 - 2))
            s.text(RAND, OBEN, BREITE * 0.75, 6, zeile, LINKS)
            s.schrift(9)
            s.text(RAND + BREITE * 0.75, OBEN, BREITE * 0.25, 6, seite, RECHTS)
            s.stift("#888888", 0.2)
            s.linie(RAND, OBEN + 7.5, RAND + BREITE, OBEN + 7.5)
            return
        y = OBEN
        titel, pt, h = self._titel
        s.schrift(pt, fett=True)
        s.text(RAND, y, BREITE, h, titel, OBEN_LINKS, umbruch=True)
        y += h + 1
        s.schrift(10)
        s.stift("#333333")
        unter, h = self._unterzeile
        s.text(RAND, y, BREITE, h, unter, OBEN_LINKS, umbruch=True)
        y += h + 5
        s.stift("#000000")
        s.schrift(12, fett=True)
        s.text(RAND, y, BREITE * 0.65, 7, name, LINKS)
        s.schrift(10)
        rechts = f"Klasse {e.mitglied.klasse}" + (f" · {seite}" if seite else "")
        s.text(RAND + BREITE * 0.5, y, BREITE * 0.5, 7, rechts, RECHTS)

    def _weiter(self, s: Seite, k: int) -> None:
        s.schrift(8.5, kursiv=True)
        s.stift("#555555")
        s.text(RAND, UNTEN - 5, BREITE, 5, f"Fortsetzung auf Seite {k + 2} →", RECHTS)

    def _ohne_punkte(self, s: Seite, y: float) -> None:
        s.schrift(10, kursiv=True)
        s.stift("#444444")
        s.text(RAND, y, BREITE, 6, "Diese Arbeit wurde ohne Einzelpunkte bewertet.", LINKS)

    def _tabellenkopf(self, s: Seite, y: float) -> None:
        s.flaeche(RAND, y, BREITE, ZEILE, "#e2e2e2")
        s.schrift(9.5, fett=True)
        for (x, b), t in zip((SP_AUFGABE, SP_THEMA, SP_MOEGLICH, SP_ERREICHT, SP_ANTEIL),
                             ("Aufgabe", "Thema", "möglich", "erreicht", "Anteil")):
            s.text(x + 1.5, y, b - 3, ZEILE, t, LINKS if t == "Thema" else MITTE)

    def _flaeche(self, s: Seite, y0: float, y1: float) -> None:
        s.flaeche(RAND, y0, BREITE, y1 - y0, "#f4f4f4")

    def _rahmen(self, s: Seite, y0: float, y1: float) -> None:
        s.stift("#555555", 0.2)
        s.kasten(RAND, y0, BREITE, y1 - y0)

    def _zeilenkopf(self, s: Seite, a: Aufgabe, e: Ergebnis, y: float, h: float) -> None:
        p = e.punkte.get(a.id)
        s.schrift(10, fett=True)
        s.text(SP_AUFGABE[0], y, SP_AUFGABE[1], ZEILE, a.bezeichnung, MITTE)
        s.schrift(10)
        s.text(SP_THEMA[0] + 1.5, y + 1, SP_THEMA[1] - 3, h - 1, a.thema or "", OBEN_LINKS, umbruch=True)
        s.text(SP_MOEGLICH[0], y, SP_MOEGLICH[1], ZEILE, zahl_text(a.max_punkte), MITTE)
        s.schrift(10, fett=True)
        s.text(SP_ERREICHT[0], y, SP_ERREICHT[1], ZEILE, zahl_text(p) if p is not None else "–", MITTE)
        s.schrift(9)
        anteil = f"{p / a.max_punkte * 100:.0f} %" if p is not None and a.max_punkte else ""
        s.text(SP_ANTEIL[0], y, SP_ANTEIL[1], ZEILE, anteil, MITTE)

    def _zeilenkopf_fortsetzung(self, s: Seite, a: Aufgabe, y: float) -> None:
        s.stift("#666666")
        s.schrift(10, fett=True)
        s.text(SP_AUFGABE[0], y, SP_AUFGABE[1], ZEILE, a.bezeichnung, MITTE)
        s.schrift(9, kursiv=True)
        s.text(SP_THEMA[0] + 1.5, y, SP_THEMA[1] - 3, ZEILE, f"{a.thema or 'Aufgabe ' + a.bezeichnung} (Fortsetzung)",
               LINKS)

    def _erwartung(self, s: Seite, text: str, y: float, h: float, pt: float) -> None:
        s.schrift(pt, kursiv=True)
        s.stift("#444444")
        s.text(ERW_X, y, ERW_BREITE, h, text, OBEN_LINKS, umbruch=True)

    def _summe(self, s: Seite, e: Ergebnis, y: float) -> None:
        s.flaeche(RAND, y, BREITE, ZEILE + 1, "#e2e2e2")
        s.schrift(10.5, fett=True)
        s.text(SP_THEMA[0] + 1.5, y, SP_THEMA[1], ZEILE + 1, "Gesamt", LINKS)
        s.text(SP_MOEGLICH[0], y, SP_MOEGLICH[1], ZEILE + 1, zahl_text(self.hoechst), MITTE)
        s.text(SP_ERREICHT[0], y, SP_ERREICHT[1], ZEILE + 1, zahl_text(e.summe) or "–", MITTE)
        if e.summe is not None and self.hoechst:
            s.text(SP_ANTEIL[0], y, SP_ANTEIL[1], ZEILE + 1, f"{e.summe / self.hoechst * 100:.0f} %", MITTE)

    def _note(self, s: Seite, e: Ergebnis, y: float) -> None:
        s.stift("#000000", 0.4)
        s.kasten(RAND, y, BREITE, 12, radius_mm=2)
        s.schrift(11)
        s.text(RAND + 5, y, 30, 12, "Note:", LINKS)
        s.schrift(16, fett=True)
        note = e.note.wort if e.note else (STATUS.get(e.status) or "–")
        s.text(RAND + 25, y, BREITE - 30, 12, note, LINKS)

    def _rueckmeldung_titel(self, s: Seite, y: float) -> None:
        s.schrift(11, fett=True)
        s.text(RAND, y, BREITE, 6, "Rückmeldung", LINKS)

    def _absatz(self, s: Seite, text: str, y: float, h: float) -> None:
        s.schrift(10.5)
        s.text(RAND, y, BREITE, h, text, OBEN_LINKS, umbruch=True)

    def _unterschriften(self, s: Seite) -> None:
        """Eine Zeile am Seitenende: Datum | Unterschrift Lehrkraft | Kenntnis genommen."""
        linie = UNTEN - 6
        spalten = ((RAND, 30.0), (RAND + 36, (BREITE - 42) / 2), (RAND + 42 + (BREITE - 42) / 2, (BREITE - 42) / 2))
        s.schrift(10)
        s.text(RAND, linie - 6, 30, 5.5, f"{self.datum:%d.%m.%Y}", LINKS)
        for (x, b), text in zip(spalten, ("Datum", "Unterschrift Lehrkraft",
                                          "Kenntnis genommen (Erziehungsberechtigte)")):
            s.stift("#000000", 0.2)
            s.linie(x, linie, x + b, linie)
            s.schrift(8)
            s.text(x, linie + 1, b, 5, text, LINKS)
