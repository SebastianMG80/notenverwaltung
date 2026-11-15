"""Sitzplan zum Ausdrucken (Querformat), z. B. für Vertretungskräfte – nur Namen, keine Noten."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.sitzplan import Sitzplan
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 14.0
BREITE, HOEHE = 297 - 2 * RAND, 210 - 2 * RAND
KOPF = 16.0
TAFEL = 10.0


class SitzplanAusgabe(Ausgabe):
    quer = True

    def __init__(self, gruppe: Lerngruppe, plan: Sitzplan, plaetze: dict[tuple[int, int], int | None],
                 namen: dict[int, Mitglied], pult: bool = False, nachname: bool = True,
                 stand: date | None = None) -> None:
        self.gruppe, self.plan, self.plaetze, self.namen = gruppe, plan, plaetze, namen
        self.pult, self.nachname = pult, nachname
        self.stand = stand or date.today()
        self.titel = f"Sitzplan {gruppe.bezeichnung} – {plan.name}"

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        s.stift("#000000")
        s.schrift(15, fett=True)
        s.text(RAND, RAND, BREITE * 0.7, 8, f"Sitzplan {self.gruppe.bezeichnung}", LINKS)
        s.schrift(9)
        s.stift("#333333")
        s.text(RAND, RAND + 8, BREITE * 0.7, 5, f"{self.gruppe.fach} · {self.plan.name} · Stand "
                                                f"{self.stand:%d.%m.%Y}" + (" · Sicht vom Pult" if self.pult else ""),
               LINKS)
        if self.kopfzeile:
            s.text(RAND + BREITE * 0.4, RAND, BREITE * 0.6, 6, self.kopfzeile, RECHTS)
        flaeche_oben = RAND + KOPF
        flaeche_h = HOEHE - KOPF - TAFEL - 4
        g_b = BREITE / self.plan.spalten
        g_h = flaeche_h / self.plan.zeilen
        tafel_y = flaeche_oben if not self.pult else flaeche_oben + flaeche_h + 4
        raster_oben = flaeche_oben + (TAFEL + 4 if not self.pult else 0)
        s.flaeche(RAND + BREITE * 0.3, tafel_y, BREITE * 0.4, TAFEL - 2, "#e2e2e2")
        s.stift("#555555")
        s.schrift(9)
        s.text(RAND + BREITE * 0.3, tafel_y, BREITE * 0.4, TAFEL - 2, "Tafel / vorne", MITTE)
        pt = max(7.0, min(11.0, min(g_b, g_h * 1.6) / 3.2))
        for (x, y), sid in self.plaetze.items():
            if self.pult:
                x, y = self.plan.spalten - 1 - x, self.plan.zeilen - 1 - y
            rx, ry = RAND + x * g_b + 1.2, raster_oben + y * g_h + 1.2
            b, h = g_b - 2.4, g_h - 2.4
            s.stift("#333333", 0.35)
            s.kasten(rx, ry, b, h, radius_mm=1.5)
            m = self.namen.get(sid) if sid else None
            if m is None:
                continue
            s.stift("#000000")
            s.schrift(pt, fett=True)
            s.text(rx + 1, ry + 1, b - 2, h / 2 - 1, m.schueler.vorname, Qt.AlignmentFlag.AlignHCenter
                   | Qt.AlignmentFlag.AlignBottom, umbruch=True)
            s.schrift(pt * 0.9)
            nach = m.schueler.nachname if self.nachname else m.schueler.nachname[:1] + "."
            s.text(rx + 1, ry + h / 2, b - 2, h / 2 - 1, nach, Qt.AlignmentFlag.AlignHCenter
                   | Qt.AlignmentFlag.AlignTop, umbruch=True)
