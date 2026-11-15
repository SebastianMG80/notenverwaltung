"""Schüler:innen-Bogen als Ausdruck: Hochformat, fließend über mehrere Seiten, Überschriften bleiben beim Inhalt.

Mit Häkchen lässt sich weglassen, was nicht für die Weitergabe gedacht ist (z. B. an Eltern): Tendenzen,
Punkte, Rückmeldungen, Bemerkungen zu mündlichen Noten, Schnellerfassung, frühere Schuljahre.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Messung, Seite
from notenverwaltung.modell.noten import Note, Punkte, zahl_text
from notenverwaltung.modell.personenbogen import ART_NAMEN, GruppenBlock, JahresBlock, Personenbogen

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
OBEN_LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 18.0
BREITE = 210 - 2 * RAND
OBEN = 18.0
UNTEN = 297 - 16.0
ZEILE = 5.6
# Datum | Arbeit | Punkte | Note | Vermerk
SPALTEN = ((22.0, "Datum"), (BREITE - 22 - 26 - 22 - 26, "Arbeit"), (26.0, "Punkte"), (22.0, "Note"), (26.0, "Vermerk"))


_NIE = object()          # noch nicht geplant (None ist eine gültige Schrift: Standardschrift)


@dataclass
class BogenOptionen:
    tendenzen: bool = True
    punkte: bool = True
    rueckmeldungen: bool = True
    bemerkungen: bool = True
    beobachtungen: bool = True
    fruehere_jahre: bool = True

    @staticmethod
    def fuer_eltern() -> "BogenOptionen":
        """Voreinstellung zum Weitergeben: ohne interne Notizen und ohne Tendenzen."""
        return BogenOptionen(tendenzen=False, bemerkungen=False, beobachtungen=False)


@dataclass
class _Element:
    hoehe: float
    zeichne: Callable[[Seite, float], None]
    halten: bool = False             # Überschrift: nie allein am Seitenende


class PersonenbogenAusgabe(Ausgabe):
    def __init__(self, bogen: Personenbogen, optionen: BogenOptionen | None = None, stand: date | None = None) -> None:
        self.bogen = bogen
        self.o = optionen or BogenOptionen()
        self.stand = stand or date.today()
        s = bogen.schueler
        self.titel = f"Schüler:innen-Bogen {s.vorname} {s.nachname}"
        self._plan_fuer: object = _NIE
        self._seiten: list[list[tuple[float, _Element]]] = []

    # ---- Planung ---------------------------------------------------------------------------------
    def _note(self, n: Note | None) -> str:
        if n is None:
            return "–"
        if isinstance(n, Punkte):
            return f"{n.punkte} P."
        return n.kurz if self.o.tendenzen else str(n.stufe)

    def _plan(self) -> list[list[tuple[float, _Element]]]:
        if self._plan_fuer == self.schrift:
            return self._seiten
        m = Messung(self.schrift)
        try:
            elemente = self._elemente(m)
        finally:
            m.ende()
        seiten: list[list[tuple[float, _Element]]] = [[]]
        y = OBEN
        for i, e in enumerate(elemente):
            naechstes = elemente[i + 1].hoehe if e.halten and i + 1 < len(elemente) else 0
            if seiten[-1] and y + e.hoehe + naechstes > UNTEN:
                seiten.append([])
                y = OBEN
            seiten[-1].append((y, e))
            y += e.hoehe
        self._seiten, self._plan_fuer = seiten, self.schrift
        return seiten

    def _text(self, m: Messung, text: str, pt: float, fett=False, kursiv=False, einzug=0.0, abstand=1.0,
              farbe="#000000", halten=False) -> _Element:
        b = BREITE - einzug
        h = m.hoehe(text, b, pt, fett, kursiv) + abstand

        def zeichne(s: Seite, y: float) -> None:
            s.stift(farbe)
            s.schrift(pt, fett=fett, kursiv=kursiv)
            s.text(RAND + einzug, y, b, h, text, OBEN_LINKS, umbruch=True)
        return _Element(h, zeichne, halten)

    def _elemente(self, m: Messung) -> list[_Element]:
        s = self.bogen.schueler
        el: list[_Element] = []

        def kopf(seite: Seite, y: float) -> None:
            seite.stift("#000000")
            seite.schrift(9)
            seite.text(RAND, y, BREITE, 5, "Schüler:innen-Bogen", LINKS)
            seite.schrift(17, fett=True)
            seite.text(RAND, y + 5, BREITE, 9, f"{s.vorname} {s.nachname}", LINKS)
            teile = []
            if self.bogen.jahre:
                j = self.bogen.jahre[0]
                teile.append(f"Klasse {j.klasse} ({j.jahr.bezeichnung})")
            if s.geburtsdatum:
                teile.append(f"geboren am {s.geburtsdatum:%d.%m.%Y}")
            teile.append(f"Stand {self.stand:%d.%m.%Y}")
            seite.schrift(10)
            seite.stift("#333333")
            seite.text(RAND, y + 14, BREITE, 5, " · ".join(teile), LINKS)
            seite.schrift(8, kursiv=True)
            seite.text(RAND, y + 19, BREITE, 4.5, "Vertraulich – enthält Noten. Nicht offen liegen lassen.", LINKS)
        el.append(_Element(27, kopf))
        jahre = self.bogen.jahre if self.o.fruehere_jahre else self.bogen.jahre[:1]
        if not jahre:
            el.append(self._text(m, "Zu dieser Person gibt es noch keine Einträge.", 10))
        for jb in jahre:
            el.extend(self._jahr(m, jb))
        return el

    def _jahr(self, m: Messung, jb: JahresBlock) -> list[_Element]:
        def balken(s: Seite, y: float) -> None:
            s.flaeche(RAND, y + 1, BREITE, 7, "#e2e2e2")
            s.stift("#000000")
            s.schrift(11, fett=True)
            s.text(RAND + 2, y + 1, BREITE - 4, 7, f"Schuljahr {jb.jahr.bezeichnung} · Klasse {jb.klasse}", LINKS)
        el = [_Element(10, balken, halten=True)]
        gruppen = [g for g in jb.gruppen if not g.leer] or []
        if not gruppen:
            el.append(self._text(m, "Keine Noten in diesem Schuljahr.", 9.5, kursiv=True, farbe="#555555",
                                 abstand=3))
        for gb in gruppen:
            el.extend(self._gruppe(m, gb))
        return el

    def _gruppe(self, m: Messung, gb: GruppenBlock) -> list[_Element]:
        g = gb.gruppe
        zusatz = [g.bezeichnung]
        if g.niveau:
            zusatz.append(f"{g.niveau}-Kurs")
        if g.kursart:
            zusatz.append(g.kursart)
        if not g.schriftlich:
            zusatz.append("mündlich")
        el = [self._text(m, f"{g.fach} · {' · '.join(zusatz)}", 10.5, fett=True, abstand=1.5, halten=True)]
        if gb.zeugnis:
            text = "Zeugnisnoten: " + " · ".join(f"{ART_NAMEN[a]} {self._note(n)}" for a, n in gb.zeugnis.items())
            el.append(self._text(m, text, 9.5, einzug=3, abstand=1.5))
        if gb.arbeiten:
            el.extend(self._arbeiten(m, gb))
        if gb.muendlich:
            text = "Mündlich: " + " · ".join(f"{z.zeitraum} {self._note(z.note)}" for z in gb.muendlich)
            el.append(self._text(m, text, 9.5, einzug=3, abstand=1))
            if self.o.bemerkungen:
                for z in gb.muendlich:
                    if z.bemerkung:
                        el.append(self._text(m, f"{z.zeitraum}: {z.bemerkung}", 8.5, kursiv=True, einzug=7,
                                             farbe="#444444", abstand=0.5))
        if gb.beobachtungen and self.o.beobachtungen:
            text = "Schnellerfassung: " + " · ".join(f"{b.zeitraum} {b.text()}" for b in gb.beobachtungen)
            el.append(self._text(m, text, 9.5, einzug=3, abstand=1))
            for b in gb.beobachtungen:
                for d, symbol, notiz in b.notizen:
                    el.append(self._text(m, f"{d:%d.%m.} {symbol}: {notiz}", 8.5, kursiv=True, einzug=7,
                                         farbe="#444444", abstand=0.5))
        el.append(_Element(4, lambda s, y: None))
        return el

    def _arbeiten(self, m: Messung, gb: GruppenBlock) -> list[_Element]:
        spalten = [sp for sp in SPALTEN if self.o.punkte or sp[1] != "Punkte"]
        breite_arbeit = BREITE - 3 - sum(b for b, k in spalten if k != "Arbeit")

        def kopf(s: Seite, y: float) -> None:
            x = RAND + 3
            s.stift("#555555")
            s.schrift(8.5, fett=True)
            for b, k in spalten:
                b = breite_arbeit if k == "Arbeit" else b
                s.text(x + 1, y, b - 2, ZEILE, k, LINKS if k in ("Arbeit", "Datum") else MITTE)
                x += b
            s.stift("#999999", 0.15)
            s.linie(RAND + 3, y + ZEILE, RAND + BREITE, y + ZEILE)
        el = [_Element(ZEILE + 0.5, kopf, halten=True)]
        for a in gb.arbeiten:
            werte = {"Datum": f"{a.datum:%d.%m.%Y}", "Arbeit": a.titel + ("" if a.zaehlt else " (zählt nicht)"),
                     "Punkte": f"{zahl_text(a.punkte)} / {zahl_text(a.hoechst)}" if a.punkte is not None else "–",
                     "Note": self._note(a.note), "Vermerk": a.status}

            def zeile(s: Seite, y: float, werte=werte) -> None:
                x = RAND + 3
                s.stift("#000000")
                for b, k in spalten:
                    b = breite_arbeit if k == "Arbeit" else b
                    s.schrift(9.5, fett=k == "Note")
                    s.text(x + 1, y, b - 2, ZEILE, werte[k], LINKS if k in ("Arbeit", "Datum") else MITTE)
                    x += b
            el.append(_Element(ZEILE, zeile))
            if self.o.rueckmeldungen and a.kommentar:
                el.append(self._text(m, f"Rückmeldung: {a.kommentar}", 8.5, kursiv=True, einzug=21,
                                     farbe="#444444", abstand=1))
        el.append(_Element(1.5, lambda s, y: None))
        return el

    # ---- Ausgabe ---------------------------------------------------------------------------------
    def seitenzahl(self) -> int:
        return len(self._plan())

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        seiten = self._plan()
        if self.kopfzeile:
            s.schrift(8.5)
            s.stift("#555555")
            s.text(RAND, OBEN - 9, BREITE, 5, self.kopfzeile, RECHTS)
        for y, e in seiten[nummer]:
            s.stift("#000000")
            e.zeichne(s, y)
        sch = self.bogen.schueler
        s.schrift(8)
        s.stift("#555555")
        s.text(RAND, UNTEN + 4, BREITE, 5, f"{sch.vorname} {sch.nachname} · Seite {nummer + 1} von {len(seiten)}",
               RECHTS)
