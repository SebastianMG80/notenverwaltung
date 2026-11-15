"""Offene Punkte eines Schuljahres – damit vor der Notenabgabe nichts untergeht.

- Arbeiten (geschrieben, Datum erreicht) ohne Punkte oder mit unvollständigen Einträgen
  (ohne „fehlt“, „schreibt nach“, „befreit“).
- Nachschreiber:innen ohne Ergebnis (eine Zeile für alle, öffnet die Nachschreibliste).
- Mündliche Zeiträume, die vorbei sind, ohne Note – sofern die Note des Quartals/Halbjahres noch nicht steht.
- Quartals- und Halbjahresnoten, die fehlen: ab `VORLAUF` Tagen vor dem Ende des Zeitraums (Stichtag) und danach.
  „Dringend“ ab einer Woche vor dem Stichtag.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis

VORLAUF = 21
DRINGEND = 7
NAMEN = {"q1": "Quartalsnote Q1", "hj1": "Halbjahresnote 1. Hj.", "q3": "Quartalsnote Q3", "hj2": "Zeugnisnote 2. Hj."}


@dataclass(frozen=True)
class OffenerPunkt:
    art: str                       # "arbeit", "nachschreiben", "muendlich", "zeugnis"
    text: str
    gruppe_id: int | None = None
    arbeit_id: int | None = None
    reiter: str = ""               # "arbeiten", "muendlich", "noten"
    stichtag: date | None = None
    dringend: bool = False


def stichtage(jahr: Schuljahr) -> dict[str, date]:
    q = jahr.quartale()
    return {"q1": q[0][1], "hj1": q[1][1], "q3": q[2][1], "hj2": q[3][1]}


def _art_des_zeitraums(jahr: Schuljahr, beginn: date) -> str:
    return ("q1", "hj1", "q3", "hj2")[jahr.quartal(beginn) - 1]


def _anzahl(n: int, einzahl: str, mehrzahl: str) -> str:
    return f"{n} {einzahl if n == 1 else mehrzahl}"


def offene_punkte(v: sqlite3.Connection, jahr: Schuljahr, heute: date | None = None,
                  vorlauf: int = VORLAUF) -> list[OffenerPunkt]:
    heute = heute or date.today()
    sd, ar, mu, zg = Stammdaten(v), Arbeiten(v), Muendlich(v), Zeugnis(v)
    punkte: list[OffenerPunkt] = []
    tage = stichtage(jahr)

    for g in sd.lerngruppen(jahr.id):
        fest = zg.festgesetzt(g.id)
        mitglieder = sd.mitglieder(g.id)

        # --- Arbeiten
        if g.schriftlich:
            for a in ar.arbeiten(g.id):
                if a.datum > heute:
                    continue
                dabei = [e for e in ar.ergebnisse(a.id) if e.erwartet and not e.status]
                ohne = [e for e in dabei if e.summe is None and e.note is None]
                unvoll = [e for e in dabei if e.unvollstaendig and e.note_manuell is None]
                if not dabei or not (ohne or unvoll):
                    continue
                if len(ohne) == len(dabei):
                    rest = "noch keine Punkte eingetragen"
                else:
                    teile = []
                    if ohne:
                        teile.append(_anzahl(len(ohne), "Person ohne Punkte", "Personen ohne Punkte"))
                    if unvoll:
                        teile.append(_anzahl(len(unvoll), "unvollständig", "unvollständig"))
                    rest = ", ".join(teile)
                punkte.append(OffenerPunkt("arbeit", f"{g.bezeichnung}: „{a.titel}“ vom {a.datum:%d.%m.} – {rest}",
                                           g.id, a.id, "arbeiten", a.datum))

        # --- Mündliche Zeiträume, die vorbei sind
        for z in mu.zeitraeume(g.id, anlegen=False):
            if z.ende >= heute:
                continue
            art = _art_des_zeitraums(jahr, z.beginn)
            noten = mu.noten(g.id)
            fehlend = [m for m in mitglieder if z.erfasst(m) and (z.id, m.schueler.id) not in noten
                       and (m.schueler.id, art) not in fest]
            if fehlend:
                punkte.append(OffenerPunkt(
                    "muendlich", f"{g.bezeichnung}: mündliche Note „{z.bezeichnung}“ fehlt bei "
                                 f"{_anzahl(len(fehlend), 'Person', 'Personen')}", g.id, None, "muendlich", z.ende))

        # --- Quartals- und Halbjahresnoten vor dem Stichtag
        zp10 = zg.gewichtung(g).zp10
        for art, tag in tage.items():
            if art == "hj2" and zp10:
                continue                    # ZP10-Fächer: Vornote/ZP10/Endnote im Reiter Noten
            if heute < tag - timedelta(days=vorlauf):
                continue
            stichtag_person = min(tag, heute)
            fehlend = [m for m in mitglieder if m.aktiv_am(stichtag_person) and (m.schueler.id, art) not in fest]
            if fehlend:
                punkte.append(OffenerPunkt(
                    "zeugnis", f"{g.bezeichnung}: {NAMEN[art]} fehlt bei "
                               f"{_anzahl(len(fehlend), 'Person', 'Personen')} (Stichtag {tag:%d.%m.%Y})",
                    g.id, None, "noten", tag, dringend=(tag - heute).days <= DRINGEND))

    # --- Nachschreiben (eine Zeile)
    offen = ar.nachschreibliste(jahr.id)
    if offen:
        punkte.append(OffenerPunkt("nachschreiben", _anzahl(len(offen), "Arbeit muss", "Arbeiten müssen")
                                   + " nachgeschrieben werden", stichtag=min(n.arbeit.datum for n in offen)))

    punkte.sort(key=lambda p: (not p.dringend, p.stichtag or heute, p.text))
    return punkte
