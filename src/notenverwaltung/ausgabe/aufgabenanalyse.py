"""Aufgabenanalyse einer Arbeit: Lösungsquote je Aufgabe als Balken – für die Nachbesprechung oder die Fachkonferenz.

Ohne Namen und ohne Noten einzelner Personen.
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import Arbeit, Arbeiten
from notenverwaltung.modell.noten import zahl_text
from notenverwaltung.modell.rueckmeldung import aufgabenanalyse

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 18.0
BREITE = 210 - 2 * RAND
ZEILE = 8.0
OBEN = RAND + 26
UNTEN = 297 - 18.0
# Aufgabe | Thema | max | Ø | Quote (Balken) | voll | 0 | bearbeitet
SPALTEN = (("Aufg.", 13.0), ("Thema", 66.0), ("max.", 11.0), ("Ø", 12.0), ("Lösungsquote", 42.0),
           ("voll", 10.0), ("0 P.", 10.0), ("n", 10.0))


class Aufgabenanalyse(Ausgabe):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, stark: float = 80.0, schwach: float = 50.0) -> None:
        self.arbeit = arbeit
        self.gruppe = ar.sd.lerngruppe(arbeit.lerngruppe_id)
        self.stark, self.schwach = stark, schwach
        aufgaben = ar.aufgaben(arbeit.id)
        ergebnisse = [e for e in ar.ergebnisse(arbeit.id) if e.summe is not None]
        self.zeilen = aufgabenanalyse(ergebnisse, aufgaben)
        self.anzahl = len(ergebnisse)
        hoechst = sum(a.max_punkte for a in aufgaben)
        self.gesamt = (sum(e.summe for e in ergebnisse) / len(ergebnisse) / hoechst * 100
                       if ergebnisse and hoechst else None)
        self.titel = f"Aufgabenanalyse {self.gruppe.bezeichnung} – {arbeit.titel}"
        je_seite = int((UNTEN - OBEN - ZEILE - 20) // ZEILE)
        self._seiten = [self.zeilen[i:i + je_seite] for i in range(0, len(self.zeilen), je_seite)] or [[]]

    def seitenzahl(self) -> int:
        return len(self._seiten)

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        s.stift("#000000")
        titel = f"Aufgabenanalyse – {self.arbeit.titel}"
        pt = 14.0
        s.schrift(pt, fett=True)
        while pt > 10 and s.textbreite_mm(titel) > BREITE * 0.78:
            pt -= 0.5
            s.schrift(pt, fett=True)
        s.text(RAND, RAND, BREITE * 0.8, 7, titel, LINKS)
        s.schrift(9)
        s.stift("#333333")
        s.text(RAND, RAND + 7.5, BREITE * 0.7, 5, f"{self.gruppe.fach} · {self.gruppe.bezeichnung} · geschrieben am "
                                                  f"{self.arbeit.datum:%d.%m.%Y} · {self.anzahl} Arbeiten ausgewertet",
               LINKS)
        s.text(RAND + BREITE * 0.6, RAND, BREITE * 0.4, 7, f"Seite {nummer + 1} von {self.seitenzahl()}", RECHTS)
        if self.kopfzeile:
            s.text(RAND + BREITE * 0.3, RAND + 13, BREITE * 0.7, 5, self.kopfzeile, RECHTS)
        if self.gesamt is not None:
            s.stift("#000000")
            s.schrift(10)
            s.text(RAND, RAND + 14, BREITE * 0.7, 6, f"Insgesamt erreicht: {self.gesamt:.0f} % der Höchstpunkte", LINKS)
        y = OBEN
        s.flaeche(RAND, y, BREITE, ZEILE, "#e2e2e2")
        s.stift("#000000")
        s.schrift(9, fett=True)
        x = RAND
        for kopf, b in SPALTEN:
            s.text(x + 1.5, y, b - 3, ZEILE, kopf, LINKS if kopf in ("Thema", "Lösungsquote") else MITTE)
            x += b
        y0 = y
        y += ZEILE
        for r, z in enumerate(self._seiten[nummer]):
            if r % 2:
                s.flaeche(RAND, y, BREITE, ZEILE, "#f4f4f4")
            a = z.aufgabe
            mittel = z.quote * a.max_punkte / 100 if z.quote is not None else None
            werte = (a.bezeichnung, a.thema, zahl_text(a.max_punkte), zahl_text(round(mittel, 1)) if mittel is not None
                     else "–", None, str(z.voll), str(z.null), str(z.bearbeitet))
            x = RAND
            for (kopf, b), w in zip(SPALTEN, werte):
                if kopf == "Lösungsquote":
                    self._balken(s, x + 1.5, y + 1.6, b - 3, ZEILE - 3.2, z.quote)
                else:
                    s.stift("#000000")
                    s.schrift(9.5, fett=kopf == "Aufg.")
                    lang = kopf == "Thema" and s.textbreite_mm(w) > b - 3
                    if lang:                                  # lange Themen zweizeilig, etwas kleiner
                        s.schrift(7.5)
                    s.text(x + 1.5, y, b - 3, ZEILE, w, LINKS if kopf == "Thema" else MITTE, umbruch=lang)
                x += b
            y += ZEILE
        s.stift("#555555", 0.2)
        s.kasten(RAND, y0, BREITE, y - y0)
        s.schrift(8, kursiv=True)
        s.stift("#555555")
        s.text(RAND, y + 3, BREITE, 10,
               f"Lösungsquote: mittlerer Anteil der Höchstpunkte. Grün ab {self.stark:g} %, rot unter {self.schwach:g} %. "
               "„voll“ / „0 P.“: Anzahl mit voller Punktzahl bzw. ohne Punkte; n: Anzahl ausgewerteter Arbeiten.",
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, umbruch=True)

    def _balken(self, s: Seite, x: float, y: float, b: float, h: float, quote: float | None) -> None:
        if quote is None:
            s.schrift(9)
            s.text(x, y, b, h, "–", LINKS)
            return
        farbe = "#2e8b57" if quote >= self.stark else "#c0392b" if quote < self.schwach else "#7f8c8d"
        breite = (b - 12) * max(0.0, min(100.0, quote)) / 100
        s.flaeche(x, y, b - 12, h, "#e8e8e8")
        s.flaeche(x, y, breite, h, farbe)
        s.stift("#000000")
        s.schrift(8.5, fett=True)
        s.text(x + b - 11.5, y - 1, 11.5, h + 2, f"{quote:.0f} %", RECHTS)
