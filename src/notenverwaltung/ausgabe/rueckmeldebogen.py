"""Rückmeldebogen: eine Seite pro Person mit Aufgaben, Punkten, Note (ohne Tendenz) und Rückmeldung."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import STATUS, Arbeit, Arbeiten, Ergebnis
from notenverwaltung.modell.noten import zahl_text

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
OBEN_LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 20.0
BREITE = 210 - 2 * RAND


class Rueckmeldebogen(Ausgabe):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, nur_mit_note: bool = True, erwartung: bool = True,
                 unterschrift: bool = True, datum: date | None = None, schueler_ids: list[int] | None = None) -> None:
        self.ar, self.arbeit = ar, arbeit
        self.erwartung = erwartung
        self.unterschrift = unterschrift
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

    def seitenzahl(self) -> int:
        return max(1, len(self.ergebnisse))

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        if not self.ergebnisse:
            s.schrift(11)
            s.text(RAND, RAND, BREITE, 10, "Noch keine Ergebnisse.", LINKS)
            return
        e = self.ergebnisse[nummer]
        y = RAND
        s.stift("#000000")
        s.schrift(16, fett=True)
        s.text(RAND, y, BREITE, 8, f"Rückmeldung zur {self.arbeit.titel}", LINKS)
        y += 9
        s.schrift(10)
        s.stift("#333333")
        thema = f" · {self.arbeit.thema}" if self.arbeit.thema else ""
        s.text(RAND, y, BREITE, 5, f"{self.gruppe.fach} · {self.gruppe.bezeichnung} · geschrieben am "
                                    f"{self.arbeit.datum:%d.%m.%Y}{thema}", LINKS)
        y += 10
        s.stift("#000000")
        s.schrift(12, fett=True)
        s.text(RAND, y, BREITE * 0.7, 7, f"{e.mitglied.schueler.vorname} {e.mitglied.schueler.nachname}", LINKS)
        s.schrift(10)
        s.text(RAND + BREITE * 0.6, y, BREITE * 0.4, 7, f"Klasse {e.mitglied.klasse}", RECHTS)
        y += 11

        # Aufgabentabelle
        sp = [(RAND, 18), (RAND + 18, BREITE - 18 - 3 * 22), (RAND + BREITE - 66, 22), (RAND + BREITE - 44, 22),
              (RAND + BREITE - 22, 22)]
        zeile = 7.0
        s.flaeche(RAND, y, BREITE, zeile, "#e2e2e2")
        s.schrift(9.5, fett=True)
        for (x, b), t in zip(sp, ["Aufgabe", "Thema", "möglich", "erreicht", "Anteil"]):
            s.text(x + 1.5, y, b - 3, zeile, t, LINKS if t == "Thema" else MITTE)
        y0 = y
        y += zeile
        for i, a in enumerate(self.aufgaben):
            erwartung = a.erwartung.strip() if self.erwartung else ""
            s.schrift(8.5)
            h_erw = s.texthoehe_mm(sp[1][1] - 3, erwartung) + 1 if erwartung else 0
            h = max(zeile, 6.5 + h_erw)
            if i % 2:
                s.flaeche(RAND, y, BREITE, h, "#f4f4f4")
            p = e.punkte.get(a.id)
            s.stift("#000000")
            s.schrift(10, fett=True)
            s.text(sp[0][0], y, sp[0][1], zeile, a.bezeichnung, MITTE)
            s.schrift(10)
            s.text(sp[1][0] + 1.5, y, sp[1][1] - 3, zeile, a.thema or "", LINKS)
            if erwartung:
                s.schrift(8.5, kursiv=True)
                s.stift("#444444")
                s.text(sp[1][0] + 1.5, y + 6, sp[1][1] - 3, h_erw, erwartung, OBEN_LINKS, umbruch=True)
                s.stift("#000000")
            s.schrift(10)
            s.text(sp[2][0], y, sp[2][1], zeile, zahl_text(a.max_punkte), MITTE)
            s.schrift(10, fett=True)
            s.text(sp[3][0], y, sp[3][1], zeile, zahl_text(p) if p is not None else "–", MITTE)
            s.schrift(9)
            anteil = f"{p / a.max_punkte * 100:.0f} %" if p is not None and a.max_punkte else ""
            s.text(sp[4][0], y, sp[4][1], zeile, anteil, MITTE)
            y += h
        # Summe
        s.flaeche(RAND, y, BREITE, zeile + 1, "#e2e2e2")
        s.schrift(10.5, fett=True)
        s.text(sp[1][0] + 1.5, y, sp[1][1], zeile + 1, "Gesamt", LINKS)
        s.text(sp[2][0], y, sp[2][1], zeile + 1, zahl_text(self.hoechst), MITTE)
        s.text(sp[3][0], y, sp[3][1], zeile + 1, zahl_text(e.summe) or "–", MITTE)
        if e.summe is not None and self.hoechst:
            s.text(sp[4][0], y, sp[4][1], zeile + 1, f"{e.summe / self.hoechst * 100:.0f} %", MITTE)
        y += zeile + 1
        s.stift("#555555", 0.2)
        s.kasten(RAND, y0, BREITE, y - y0)
        y += 8

        # Note ohne Tendenz
        s.stift("#000000", 0.4)
        s.kasten(RAND, y, BREITE, 14, radius_mm=2)
        s.schrift(11)
        s.text(RAND + 5, y, 30, 14, "Note:", LINKS)
        s.schrift(16, fett=True)
        note = e.note.wort if e.note else (STATUS.get(e.status) or "–")
        s.text(RAND + 25, y, BREITE - 30, 14, note, LINKS)
        y += 22

        # Rückmeldung
        if e.kommentar:
            s.schrift(11, fett=True)
            s.text(RAND, y, BREITE, 6, "Rückmeldung", LINKS)
            y += 7
            s.schrift(10.5)
            h = s.texthoehe_mm(BREITE, e.kommentar)
            s.text(RAND, y, BREITE, h, e.kommentar, OBEN_LINKS, umbruch=True)
            y += h + 8

        # Unterschriften
        if self.unterschrift:
            uy = 297 - RAND - 22
            s.schrift(9)
            s.stift("#000000")
            s.text(RAND, uy - 10, BREITE, 5, f"Datum: {self.datum:%d.%m.%Y}", LINKS)
            for i, text in enumerate(("Unterschrift Lehrkraft", "Kenntnis genommen (Erziehungsberechtigte)")):
                x = RAND + i * (BREITE / 2 + 5)
                s.stift("#000000", 0.2)
                s.linie(x, uy + 8, x + BREITE / 2 - 5, uy + 8)
                s.schrift(8)
                s.text(x, uy + 9, BREITE / 2 - 5, 5, text, LINKS)
