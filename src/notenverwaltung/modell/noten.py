"""Noten der Sekundarstufe I: Notenstufen mit Tendenz, Notenschlüssel, Notenspiegel.

Festlegungen (Lastenheft, Klärungen):
- Intern wird mit Tendenz gerechnet: „+“ = −0,3, „−“ = +0,3 (gut+ = 1,7; gut− = 2,3; sehr gut+ = 0,7).
- Die 6 hat keine Tendenz.
- Bei schriftlichen Arbeiten erhalten Schüler:innen die Note ohne Tendenz („gut“, nicht „gut (+)“).
- Standard-Notenschlüssel ist die Prozenttabelle aus Punkteliste.ods; die Punktgrenzen entstehen wie dort
  mit ROUND(Höchstpunktzahl × Prozent / 100) (kaufmännisch gerundet).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

WORTE = {1: "sehr gut", 2: "gut", 3: "befriedigend", 4: "ausreichend", 5: "mangelhaft", 6: "ungenügend"}


@dataclass(frozen=True, order=True)
class Note:
    """Notenstufe 1–6 mit Tendenz: +1 = „+“ (besser), −1 = „−“ (schlechter), 0 = ohne."""

    wert_sortierung: float  # nur zum Vergleichen/Sortieren (kleiner = besser)
    stufe: int
    tendenz: int = 0

    @staticmethod
    def aus(stufe: int, tendenz: int = 0) -> "Note":
        if stufe not in WORTE:
            raise ValueError(f"Ungültige Notenstufe: {stufe}")
        if tendenz not in (-1, 0, 1):
            raise ValueError(f"Ungültige Tendenz: {tendenz}")
        if stufe == 6:
            tendenz = 0
        return Note(stufe - 0.3 * tendenz, stufe, tendenz)

    @staticmethod
    def aus_kurz(text: str) -> "Note":
        """„2+“, „2“, „2-“ (auch „2–“) → Note."""
        t = text.strip().replace("–", "-").replace("−", "-")
        if not t or not t[0].isdigit():
            raise ValueError(f"Keine Note: {text!r}")
        stufe = int(t[0])
        rest = t[1:].strip()
        tendenz = {"": 0, "+": 1, "-": -1}.get(rest)
        if tendenz is None:
            raise ValueError(f"Keine Note: {text!r}")
        return Note.aus(stufe, tendenz)

    @property
    def wert(self) -> float:
        """Rechenwert: 2+ = 1,7; 2 = 2,0; 2− = 2,3."""
        return round(self.stufe - 0.3 * self.tendenz, 1)

    @property
    def kurz(self) -> str:
        return f"{self.stufe}{'+' if self.tendenz > 0 else '-' if self.tendenz < 0 else ''}"

    @property
    def wort(self) -> str:
        """Ohne Tendenz – so erfahren es die Schüler:innen bei Klassenarbeiten."""
        return WORTE[self.stufe]

    @property
    def wort_mit_tendenz(self) -> str:
        """Für die Lehrkraft: „gut (+)“."""
        return WORTE[self.stufe] + (" (+)" if self.tendenz > 0 else " (–)" if self.tendenz < 0 else "")

    def __str__(self) -> str:
        return self.kurz


ALLE_NOTEN = [Note.aus(s, t) for s in range(1, 7) for t in ((1, 0, -1) if s < 6 else (0,))]


def runde(wert: float, schritt: float = 1.0) -> float:
    """Kaufmännisch runden auf ein Vielfaches von `schritt` (wie ROUND in der Tabellenkalkulation)."""
    d = Decimal(str(wert)) / Decimal(str(schritt))
    return float(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP) * Decimal(str(schritt)))


# ---- Notenschlüssel ------------------------------------------------------------------------------

@dataclass(frozen=True)
class Stufe:
    prozent: float   # ab diesem Anteil der Höchstpunktzahl …
    note: Note       # … gibt es diese Note


STANDARD_STUFEN = [  # Punkteliste.ods, Tabelle „% / Pkt. / Note“
    (0, "6"), (20, "5-"), (21, "5"), (38, "5+"), (40, "4-"), (42, "4"), (53, "4+"), (55, "3-"), (57, "3"),
    (68, "3+"), (70, "2-"), (72, "2"), (81, "2+"), (83, "1-"), (85, "1"), (105, "1+"),
]


@dataclass(frozen=True)
class Notenschluessel:
    stufen: tuple[Stufe, ...]
    raster: float = 1.0   # Punktgrenzen werden auf Vielfache davon gerundet (1 = ganze Punkte wie in der ODS)

    @staticmethod
    def standard() -> "Notenschluessel":
        return Notenschluessel.aus_liste(STANDARD_STUFEN)

    @staticmethod
    def aus_liste(paare, raster: float = 1.0) -> "Notenschluessel":
        stufen = tuple(sorted((Stufe(float(p), n if isinstance(n, Note) else Note.aus_kurz(n)) for p, n in paare),
                              key=lambda s: s.prozent))
        k = Notenschluessel(stufen, raster)
        k.pruefe()
        return k

    def pruefe(self) -> None:
        if not self.stufen:
            raise ValueError("Der Notenschlüssel ist leer.")
        if self.stufen[0].prozent != 0:
            raise ValueError("Die erste Stufe muss bei 0 % beginnen.")
        prozente = [s.prozent for s in self.stufen]
        if len(set(prozente)) != len(prozente):
            raise ValueError("Zwei Stufen haben denselben Prozentwert.")
        for a, b in zip(self.stufen, self.stufen[1:]):
            if b.note.wert_sortierung >= a.note.wert_sortierung:
                raise ValueError(f"Bei {b.prozent:g} % muss eine bessere Note stehen als bei {a.prozent:g} %.")
        if self.raster not in (0.25, 0.5, 1.0):
            raise ValueError("Das Raster der Punktgrenzen ist 1, 0,5 oder 0,25 Punkte.")

    # ---- Speichern als JSON (in der Arbeit als Kopie, damit spätere Änderungen alte Noten nicht verändern)
    def als_json(self) -> str:
        return json.dumps({"stufen": [[s.prozent, s.note.kurz] for s in self.stufen], "raster": self.raster},
                          separators=(",", ":"))

    @staticmethod
    def aus_json(text: str) -> "Notenschluessel":
        d = json.loads(text)
        return Notenschluessel.aus_liste(d["stufen"], d.get("raster", 1.0))

    # ---- Anwenden
    def grenzen(self, hoechstpunkte: float) -> list[tuple[float, Note]]:
        """Punktgrenzen (ab … Punkte → Note) für eine Arbeit, wie Spalte „Pkt.“ der ODS."""
        return [(runde(hoechstpunkte * s.prozent / 100, self.raster), s.note) for s in self.stufen]

    def note(self, punkte: float, hoechstpunkte: float) -> Note:
        ergebnis = self.stufen[0].note
        for grenze, note in self.grenzen(hoechstpunkte):
            if punkte >= grenze - 1e-9:
                ergebnis = note
        return ergebnis

    def bereiche(self, hoechstpunkte: float) -> list[tuple[float, float, Note]]:
        """(von, bis, Note) je erreichbarer Stufe – für die Anzeige, schlechteste zuerst."""
        g = self.grenzen(hoechstpunkte)
        # Eine Stufe zählt nur, wenn sie erreichbar ist und nicht von der nächsten (gleiche Grenze) verdeckt wird
        sichtbar = [(von, note) for i, (von, note) in enumerate(g)
                    if von <= hoechstpunkte and (i + 1 == len(g) or g[i + 1][0] > von)]
        ergebnis = []
        for i, (von, note) in enumerate(sichtbar):
            bis = sichtbar[i + 1][0] - self.raster if i + 1 < len(sichtbar) else hoechstpunkte
            ergebnis.append((von, bis, note))
        return ergebnis


# ---- Notenspiegel --------------------------------------------------------------------------------

@dataclass(frozen=True)
class Notenspiegel:
    anzahl: dict[int, int]          # Stufe 1–6 → Anzahl (ohne Tendenz, wie in der ODS)
    schnitt: float | None           # Durchschnitt der ganzen Noten
    schnitt_mit_tendenz: float | None
    anteil_unter_4: float | None    # Prozent mit 5 oder 6

    @property
    def gesamt(self) -> int:
        return sum(self.anzahl.values())

    @staticmethod
    def aus(noten: list[Note]) -> "Notenspiegel":
        anzahl = {s: 0 for s in range(1, 7)}
        for n in noten:
            anzahl[n.stufe] += 1
        gesamt = len(noten)
        if not gesamt:
            return Notenspiegel(anzahl, None, None, None)
        return Notenspiegel(
            anzahl,
            sum(s * a for s, a in anzahl.items()) / gesamt,
            sum(n.wert for n in noten) / gesamt,
            (anzahl[5] + anzahl[6]) / gesamt * 100,
        )


def zahl(text: str) -> float | None:
    """Benutzereingabe „3,5“ / „3.5“ / „“ → Zahl bzw. None. Wirft ValueError bei Unsinn."""
    t = text.strip().replace(",", ".")
    if not t:
        return None
    wert = float(t)
    if wert != wert or wert in (float("inf"), float("-inf")):
        raise ValueError("Keine gültige Zahl")
    return wert


def zahl_text(wert: float | None) -> str:
    """3.0 → „3“, 3.5 → „3,5“ (deutsche Schreibweise)."""
    if wert is None:
        return ""
    if abs(wert - round(wert)) < 1e-9:
        return str(int(round(wert)))
    return f"{wert:.2f}".rstrip("0").rstrip(".").replace(".", ",")
