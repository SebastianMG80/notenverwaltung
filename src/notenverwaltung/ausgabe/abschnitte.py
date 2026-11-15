"""Notenabschnitte für Schüler:innen (wie der untere Teil von Punkteliste.ods).

Jeder Abschnitt zeigt Name, Aufgaben mit Höchst- und erreichten Punkten, Summe, Datum und die Note
**ohne Tendenz** („gut“, nicht „gut (+)“). Formate: frei wählbare Größe oder Avery-Zweckform-Etiketten.

Avery Zweckform (A4, 210 × 297 mm):
- 3424: 105 × 48 mm, 2 × 6 = 12 je Bogen → seitlich randlos, oben/unten je 4,5 mm
- 3425: 105 × 57 mm, 2 × 5 = 10 je Bogen → seitlich randlos, oben/unten je 6 mm
Druckerabweichungen gleicht der einstellbare Druckversatz aus. Weil die Etiketten seitlich bis an den
Papierrand reichen, die meisten Drucker dort aber 4–6 mm nicht bedrucken, hält der Inhalt einen einstellbaren
Mindestabstand zum Blattrand (Standard 7 mm); zur Mitte hin bleibt es beim Innenrand von 4 mm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import Arbeit, Arbeiten, Aufgabe, Ergebnis
from notenverwaltung.modell.noten import zahl_text

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter
MIN_PT = 6.0
INNENRAND = 4.0        # Abstand des Inhalts zum Rand des Abschnitts
BLATTRAND = 7.0        # Standard: so weit bleibt der Inhalt mindestens vom Papierrand weg
MAX_PT = 9.0


@dataclass(frozen=True)
class Format:
    name: str
    breite: float
    hoehe: float
    spalten: int
    zeilen: int
    rand_links: float
    rand_oben: float
    abstand_x: float = 0.0
    abstand_y: float = 0.0
    rahmen: bool = False      # Schneidelinien bei Normalpapier

    @property
    def je_seite(self) -> int:
        return self.spalten * self.zeilen

    def position(self, platz: int) -> tuple[float, float]:
        """Linke obere Ecke des Abschnitts Nr. `platz` (0-basiert, zeilenweise) auf der Seite."""
        z, s = divmod(platz, self.spalten)
        return (self.rand_links + s * (self.breite + self.abstand_x),
                self.rand_oben + z * (self.hoehe + self.abstand_y))


AVERY_3424 = Format("Avery Zweckform 3424 (105 × 48 mm, 12 je Bogen)", 105, 48, 2, 6, 0, 4.5)
AVERY_3425 = Format("Avery Zweckform 3425 (105 × 57 mm, 10 je Bogen)", 105, 57, 2, 5, 0, 6)


def freies_format(breite: float, hoehe: float, rand: float = 5.0) -> Format:
    """So viele Abschnitte wie auf A4 passen, mittig, mit Schneidelinien."""
    if breite < 60 or hoehe < 30:
        raise ValueError("Ein Abschnitt braucht mindestens 60 × 30 mm.")
    spalten = max(1, int((210 - 2 * rand) // breite))
    zeilen = max(1, int((297 - 2 * rand) // hoehe))
    if spalten * breite > 210 or zeilen * hoehe > 297:
        raise ValueError("Der Abschnitt ist größer als ein A4-Blatt.")
    return Format(f"Frei ({zahl_text(breite)} × {zahl_text(hoehe)} mm)", breite, hoehe, spalten, zeilen,
                  (210 - spalten * breite) / 2, (297 - zeilen * hoehe) / 2, rahmen=True)


class Notenabschnitte(Ausgabe):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, fmt: Format, startplatz: int = 0, nur_mit_note: bool = True,
                 rahmen: bool | None = None, datum: date | None = None, schueler_ids: list[int] | None = None,
                 blattrand: float = BLATTRAND) -> None:
        self.ar = ar
        self.blattrand = blattrand
        self.arbeit = arbeit
        self.fmt = fmt
        self.startplatz = max(0, min(startplatz, fmt.je_seite - 1))
        self.rahmen = fmt.rahmen if rahmen is None else rahmen
        self.datum = datum or arbeit.rueckgabe or date.today()
        self.gruppe = ar.sd.lerngruppe(arbeit.lerngruppe_id)
        self.aufgaben: list[Aufgabe] = ar.aufgaben(arbeit.id)
        self.hoechst = sum(a.max_punkte for a in self.aufgaben)
        ergebnisse = ar.ergebnisse(arbeit.id)
        if schueler_ids is not None:
            ergebnisse = [e for e in ergebnisse if e.mitglied.schueler.id in schueler_ids]
        elif nur_mit_note:
            ergebnisse = [e for e in ergebnisse if e.note is not None]
        self.ergebnisse: list[Ergebnis] = ergebnisse
        self.titel = f"Notenabschnitte {self.gruppe.bezeichnung} – {arbeit.titel}"

    def seitenzahl(self) -> int:
        return max(1, math.ceil((self.startplatz + len(self.ergebnisse)) / self.fmt.je_seite))

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        erster = nummer * self.fmt.je_seite - self.startplatz
        for platz in range(self.fmt.je_seite):
            i = erster + platz
            if 0 <= i < len(self.ergebnisse):
                x, y = self.fmt.position(platz)
                self.zeichne_abschnitt(s, x, y, self.fmt.breite, self.fmt.hoehe, self.ergebnisse[i])

    # ---- ein Abschnitt -----------------------------------------------------------------------------
    def _schriftgroesse(self, s: Seite, spaltenbreite_mm: float) -> float | None:
        """Größte Schrift (9 … 6 pt), bei der alle Einträge in die Spalte passen; None, wenn nicht einmal 6 pt passt."""
        texte = [a.bezeichnung for a in self.aufgaben] + [zahl_text(a.max_punkte) for a in self.aufgaben] + ["10,5"]
        pt = MAX_PT
        while pt >= MIN_PT:
            f = s.schrift(pt, fett=True)
            breite = max(QFontMetricsF(f, s.p.device()).horizontalAdvance(t) for t in texte)
            if breite / s.mm_in_px(1) + 0.8 <= spaltenbreite_mm:
                return pt
            pt -= 0.5
        return None

    def innenraender(self, x: float, y: float, b: float, h: float) -> tuple[float, float, float, float]:
        """(links, rechts, oben, unten): mindestens INNENRAND, am Papierrand mindestens `blattrand`.
        Der Druckversatz verschiebt den Abschnitt auf dem Papier und wird mitgerechnet."""
        px, py = x + self.versatz_x, y + self.versatz_y
        return (max(INNENRAND, self.blattrand - px), max(INNENRAND, self.blattrand - (210 - px - b)),
                max(INNENRAND, self.blattrand - py), max(INNENRAND, self.blattrand - (297 - py - h)))

    def zeichne_abschnitt(self, s: Seite, x: float, y: float, b: float, h: float, e: Ergebnis) -> None:
        if self.rahmen:
            s.stift("#999999", 0.15)
            s.p.save()
            stift = s.p.pen()
            stift.setStyle(Qt.PenStyle.DashLine)
            s.p.setPen(stift)
            s.kasten(x, y, b, h)
            s.p.restore()
        links, rechts, oben, unten = self.innenraender(x, y, b, h)
        ix, iy, ib, ih = x + links, y + oben, b - links - rechts, h - oben - unten

        # Kopf: Name links, Lerngruppe/Arbeit rechts
        s.stift("#000000")
        s.schrift(10, fett=True)
        name = f"{e.mitglied.schueler.vorname} {e.mitglied.schueler.nachname}"
        s.text(ix, iy, ib * 0.6, 5, name, LINKS)
        s.schrift(7.5)
        s.stift("#333333")
        s.text(ix + ib * 0.4, iy, ib * 0.6, 5, f"{self.gruppe.bezeichnung} · {self.arbeit.titel}", RECHTS)

        if e.summe is None and e.note is not None:
            # Note ohne Punkte festgesetzt (z. B. Nachschreibarbeit): keine leere Punktetabelle
            s.stift("#444444")
            s.schrift(8, kursiv=True)
            s.text(ix, iy + 9, ib, 5, "Bewertet ohne Einzelpunkte.", LINKS)
            self.schrift_pt, self.zweizeilig = None, False
        else:
            self._tabellen(s, ix, iy, ib, e)
        self._fuss(s, ix, iy, ib, ih, e)

    def _tabellen(self, s: Seite, ix: float, iy: float, ib: float, e: Ergebnis) -> None:
        # Tabelle Aufgabe / max / erreicht; bei Platzmangel zweizeilig
        beschriftung = 17.0
        summe_b = 11.0
        n = len(self.aufgaben)
        bloecke = [self.aufgaben]
        spalte = (ib - beschriftung - summe_b) / max(1, n)
        pt = self._schriftgroesse(s, spalte)
        if pt is None:  # zu viele Aufgaben für eine Zeile: zweizeilig, damit es lesbar bleibt
            mitte = math.ceil(n / 2)
            bloecke = [self.aufgaben[:mitte], self.aufgaben[mitte:]]
            spalte = (ib - beschriftung - summe_b) / mitte
            pt = self._schriftgroesse(s, spalte) or MIN_PT
        self.schrift_pt, self.zweizeilig = pt, len(bloecke) == 2
        zeile = 4.2 if len(bloecke) == 1 else 3.8
        ty = iy + 6.5
        for bi, block in enumerate(bloecke):
            letzter = bi == len(bloecke) - 1
            self._tabelle(s, ix, ty, beschriftung, spalte, summe_b, zeile, pt, block, e, letzter)
            ty += 3 * zeile + 1.5

    def _fuss(self, s: Seite, ix: float, iy: float, ib: float, ih: float, e: Ergebnis) -> None:
        # Fuß: Datum links, Note rechts (ohne Tendenz)
        fy = iy + ih - 6.5
        s.stift("#000000")
        s.schrift(8)
        s.text(ix, fy, ib / 2, 6.5, f"Datum: {self.datum:%d.%m.%Y}", LINKS)
        note = e.note.wort if e.note else (e.status and {"fehlt": "fehlt", "nachschreiben": "schreibt nach",
                                                           "befreit": "befreit"}.get(e.status, "")) or ""
        s.schrift(8)
        notenbreite = ib * 0.55
        s.text(ix + ib - notenbreite, fy, 12, 6.5, "Note:", LINKS)
        s.schrift(12, fett=True)
        s.text(ix + ib - notenbreite + 11, fy, notenbreite - 11, 6.5, note, LINKS)

    def _tabelle(self, s: Seite, x: float, y: float, beschriftung: float, spalte: float, summe_b: float,
                 zeile: float, pt: float, aufgaben: list[Aufgabe], e: Ergebnis, mit_summe: bool) -> None:
        s.stift("#000000", 0.15)
        zeilen = [("Aufgabe", [a.bezeichnung for a in aufgaben], "Summe"),
                  ("max. Punkte", [zahl_text(a.max_punkte) for a in aufgaben], zahl_text(self.hoechst)),
                  ("erreicht", [zahl_text(e.punkte.get(a.id)) or "–" for a in aufgaben], zahl_text(e.summe) or "–")]
        breite_gesamt = spalte * len(aufgaben) + (summe_b if mit_summe else 0)
        for r, (bez, werte, summe) in enumerate(zeilen):
            zy = y + r * zeile
            if r == 0:
                s.flaeche(x + beschriftung, zy, breite_gesamt, zeile, "#e6e6e6")
            s.schrift(min(pt, 7.0), fett=(r == 2))  # Beschriftung klein halten, damit sie in die Spalte passt
            s.text(x, zy, beschriftung - 1, zeile, bez, RECHTS)
            s.schrift(pt, fett=(r == 2))
            for c, w in enumerate(werte):
                s.text(x + beschriftung + c * spalte, zy, spalte, zeile, w, MITTE)
            if mit_summe:
                s.schrift(min(pt, 7.5) if r == 0 else pt, fett=True)
                s.text(x + beschriftung + len(werte) * spalte, zy, summe_b, zeile, summe, MITTE)
        # Gitter
        s.kasten(x + beschriftung, y, breite_gesamt, 3 * zeile)
        for r in (1, 2):
            s.linie(x + beschriftung, y + r * zeile, x + beschriftung + breite_gesamt, y + r * zeile)
        for c in range(1, len(aufgaben) + (1 if mit_summe else 0)):
            cx = x + beschriftung + c * spalte
            s.linie(cx, y, cx, y + 3 * zeile)
