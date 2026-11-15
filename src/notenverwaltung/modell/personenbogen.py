"""Schüler:innen-Bogen: alles zu einer Person aus allen eigenen Lerngruppen, über alle Schuljahre (neueste zuerst).

Je Lerngruppe: Zeugnisnoten (Q1, 1. Hj., Q3, 2. Hj., ZP10), Klassenarbeiten mit Punkten, Note, Vermerk und
Rückmeldung, mündliche Noten je Zeitraum mit Bemerkung, Schnellerfassung je Zeitraum mit Notizen.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from notenverwaltung.modell.arbeiten import STATUS, Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Schueler, Schuljahr, Stammdaten
from notenverwaltung.modell.stunden import SYMBOLE, Stunden
from notenverwaltung.modell.zeugnis import ARTEN, Zeugnis

ART_NAMEN = {"q1": "Q1", "hj1": "1. Hj.", "q3": "Q3", "hj2": "2. Hj.", "vornote": "Vornote", "zp10": "ZP10"}


@dataclass(frozen=True)
class ArbeitZeile:
    titel: str
    datum: date
    punkte: float | None
    hoechst: float
    note: Note | None
    status: str
    kommentar: str
    zaehlt: bool


@dataclass(frozen=True)
class MuendlichZeile:
    zeitraum: str
    note: Note
    bemerkung: str


@dataclass(frozen=True)
class BeobachtungZeile:
    zeitraum: str
    schnitt: float
    verteilung: dict[int, int]
    notizen: list[tuple[date, str, str]]          # (Tag, Symbol, Notiz)

    def text(self) -> str:
        teile = ", ".join(f"{SYMBOLE[w]} {n}×" for w, n in sorted(self.verteilung.items()) if n)
        return f"Ø {self.schnitt:.1f}".replace(".", ",") + f" ({teile})"


@dataclass
class GruppenBlock:
    gruppe: Lerngruppe
    zeugnis: dict[str, Note] = field(default_factory=dict)
    arbeiten: list[ArbeitZeile] = field(default_factory=list)
    muendlich: list[MuendlichZeile] = field(default_factory=list)
    beobachtungen: list[BeobachtungZeile] = field(default_factory=list)

    @property
    def leer(self) -> bool:
        return not (self.zeugnis or self.arbeiten or self.muendlich or self.beobachtungen)


@dataclass
class JahresBlock:
    jahr: Schuljahr
    klasse: str
    jahrgang: int
    gruppen: list[GruppenBlock] = field(default_factory=list)


@dataclass
class Personenbogen:
    schueler: Schueler
    jahre: list[JahresBlock]


def personenbogen(v: sqlite3.Connection, schueler_id: int) -> Personenbogen:
    sd, ar, mu, zg, st = Stammdaten(v), Arbeiten(v), Muendlich(v), Zeugnis(v), Stunden(v)
    s = sd.schueler(schueler_id)
    jahre = []
    for jahr in sorted(sd.schuljahre(), key=lambda j: j.beginn, reverse=True):
        eintrag = next((e for e in sd.schueler_im_jahr(jahr.id) if e.schueler.id == schueler_id), None)
        if eintrag is None:
            continue
        jb = JahresBlock(jahr, eintrag.klasse, eintrag.jahrgang)
        for g in sd.lerngruppen_von(schueler_id, jahr.id):
            gb = GruppenBlock(g)
            fest = zg.festgesetzt(g.id)
            gb.zeugnis = {art: fest[(schueler_id, art)] for art in ARTEN if (schueler_id, art) in fest}
            if g.schriftlich:
                for a in ar.arbeiten(g.id):
                    aufgaben = ar.aufgaben(a.id)
                    e = next((x for x in ar.ergebnisse(a.id) if x.mitglied.schueler.id == schueler_id), None)
                    if e is None or not (e.erwartet or e.summe is not None or e.note is not None or e.status):
                        continue
                    gb.arbeiten.append(ArbeitZeile(a.titel, a.datum, e.summe, sum(x.max_punkte for x in aufgaben),
                                                   e.note, STATUS.get(e.status, e.status), e.kommentar, a.zaehlt))
            noten = mu.noten(g.id)
            zeitraeume = mu.zeitraeume(g.id, anlegen=False)
            for z in zeitraeume:
                if (z.id, schueler_id) in noten:
                    note, bem = noten[(z.id, schueler_id)]
                    gb.muendlich.append(MuendlichZeile(z.bezeichnung, note, bem or ""))
            eintraege = {d: b for (sid, d), b in st.eintraege(g.id).items() if sid == schueler_id}
            for z in zeitraeume:
                im = sorted((d, b) for d, b in eintraege.items() if z.beginn <= d <= z.ende)
                if im:
                    werte = [b.wert for _, b in im]
                    gb.beobachtungen.append(BeobachtungZeile(
                        z.bezeichnung, sum(werte) / len(werte), {w: werte.count(w) for w in SYMBOLE},
                        [(d, b.symbol, b.notiz) for d, b in im if b.notiz]))
            jb.gruppen.append(gb)
        jahre.append(jb)
    return Personenbogen(s, jahre)
