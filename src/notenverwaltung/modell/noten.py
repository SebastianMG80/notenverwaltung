"""Noten: Sekundarstufe I (1–6 mit Tendenz) und Sekundarstufe II (0–15 Punkte), Notenschlüssel, Notenspiegel.

Festlegungen (Lastenheft, Klärungen):
- Intern wird mit Tendenz gerechnet: „+“ = −0,3, „−“ = +0,3 (gut+ = 1,7; gut− = 2,3; sehr gut+ = 0,7).
- Die 6 hat keine Tendenz.
- Bei schriftlichen Arbeiten erhalten Schüler:innen die Note ohne Tendenz („gut“, nicht „gut (+)“).
- Standard-Notenschlüssel ist die Prozenttabelle aus Punkteliste.ods; die Punktgrenzen entstehen wie dort
  mit ROUND(Höchstpunktzahl × Prozent / 100) (kaufmännisch gerundet).
- Sek II: 0–15 Punkte (Klasse `Punkte`, eine Unterart von `Note`). Gespeichert als „11P“, damit Punkte nie mit
  Sek-I-Noten verwechselt werden. Rechenwert = Punktzahl (höher = besser); Schnitte werden auf ganze Punkte
  gerundet, ,5 zur besseren Punktzahl. Klausurschlüssel: NRW-Tabelle (ab 95 % 15 Punkte … ab 20 % 1 Punkt).
- Welche Art gilt, bestimmt die Lerngruppe (`notensystem` „sek1“/„sek2“) – siehe `Notensystem`.
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

    @property
    def speicher(self) -> str:
        """So steht die Note in der Datenbank."""
        return self.kurz

    @property
    def rang(self) -> float:
        """Größer = besser (für beide Notensysteme gleich zu benutzen)."""
        return -self.wert_sortierung

    def __str__(self) -> str:
        return self.kurz

    @staticmethod
    def lies(text: str) -> "Note":
        """Gespeicherte Note lesen: „2-“ (Sek I) oder „11P“ (Sek II)."""
        t = text.strip()
        if t.endswith("P"):
            return Punkte.aus_punkte(int(t[:-1]))
        return Note.aus_kurz(t)


@dataclass(frozen=True, order=True)
class Punkte(Note):
    """Sek II: 0–15 Punkte. `stufe`/`tendenz` geben die entsprechende Sek-I-Note an (11 Punkte = 2)."""

    punkte: int = 0

    @staticmethod
    def aus_punkte(p: int) -> "Punkte":
        if not isinstance(p, int) or not 0 <= p <= 15:
            raise ValueError(f"Punkte liegen zwischen 0 und 15, nicht {p!r}.")
        if p == 0:
            stufe, tendenz = 6, 0
        else:
            stufe = 6 - (p + 2) // 3
            tendenz = {0: 1, 2: 0, 1: -1}[p % 3]
        return Punkte(-float(p), stufe, tendenz, p)

    @property
    def wert(self) -> float:
        return float(self.punkte)

    @property
    def kurz(self) -> str:
        return str(self.punkte)

    @property
    def wort(self) -> str:
        return f"{self.punkte} Punkt" + ("" if self.punkte == 1 else "e")

    @property
    def wort_mit_tendenz(self) -> str:
        return f"{self.wort} ({Note.aus(self.stufe, self.tendenz).wort_mit_tendenz})"

    @property
    def speicher(self) -> str:
        return f"{self.punkte}P"


ALLE_NOTEN = [Note.aus(s, t) for s in range(1, 7) for t in ((1, 0, -1) if s < 6 else (0,))]
ALLE_PUNKTE = [Punkte.aus_punkte(p) for p in range(15, -1, -1)]


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
# Sek II, NRW: ab 95 % 15 Punkte, je 5 % ein Punkt weniger bis 50 % = 6 Punkte; 45/39/33/27/20 % = 5/4/3/2/1
STANDARD_STUFEN_SEK2 = [(0, "0P"), (20, "1P"), (27, "2P"), (33, "3P"), (39, "4P"), (45, "5P")] + [
    (50 + 5 * i, f"{6 + i}P") for i in range(10)]


@dataclass(frozen=True)
class Notenschluessel:
    stufen: tuple[Stufe, ...]
    raster: float = 1.0   # Punktgrenzen werden auf Vielfache davon gerundet (1 = ganze Punkte wie in der ODS)

    @staticmethod
    def standard(system: str = "sek1") -> "Notenschluessel":
        return Notenschluessel.aus_liste(STANDARD_STUFEN_SEK2 if system == "sek2" else STANDARD_STUFEN)

    @property
    def system(self) -> str:
        return "sek2" if isinstance(self.stufen[0].note, Punkte) else "sek1"

    @staticmethod
    def aus_liste(paare, raster: float = 1.0) -> "Notenschluessel":
        stufen = tuple(sorted((Stufe(float(p), n if isinstance(n, Note) else Note.lies(n)) for p, n in paare),
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
        if len({type(s.note) for s in self.stufen}) != 1:
            raise ValueError("Ein Notenschlüssel enthält entweder Noten (1–6) oder Punkte (0–15).")
        if len(set(prozente)) != len(prozente):
            raise ValueError("Zwei Stufen haben denselben Prozentwert.")
        for a, b in zip(self.stufen, self.stufen[1:]):
            if b.note.wert_sortierung >= a.note.wert_sortierung:
                raise ValueError(f"Bei {b.prozent:g} % muss eine bessere Note stehen als bei {a.prozent:g} %.")
        if self.raster not in (0.25, 0.5, 1.0):
            raise ValueError("Das Raster der Punktgrenzen ist 1, 0,5 oder 0,25 Punkte.")

    # ---- Speichern als JSON (in der Arbeit als Kopie, damit spätere Änderungen alte Noten nicht verändern)
    def als_json(self) -> str:
        return json.dumps({"stufen": [[s.prozent, s.note.speicher] for s in self.stufen], "raster": self.raster},
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
    """Sek I: Anzahl je Stufe 1–6 (ohne Tendenz, wie in der ODS). Sek II: Anzahl je Punktzahl 15–0."""
    anzahl: dict[int, int]          # Stufe bzw. Punktzahl → Anzahl, in Anzeigereihenfolge (beste zuerst)
    schnitt: float | None           # Sek I: Durchschnitt der ganzen Noten; Sek II: Punkteschnitt
    schnitt_mit_tendenz: float | None
    anteil_unter_4: float | None    # Prozent mangelhaft oder schlechter (Sek II: unter 5 Punkten)
    sek2: bool = False

    @property
    def gesamt(self) -> int:
        return sum(self.anzahl.values())

    @property
    def text_unter(self) -> str:
        return "unter 5 P." if self.sek2 else "unter 4"

    @staticmethod
    def aus(noten: list[Note], sek2: bool | None = None) -> "Notenspiegel":
        if sek2 is None:
            sek2 = any(isinstance(n, Punkte) for n in noten)
        if sek2:
            anzahl = {p: 0 for p in range(15, -1, -1)}
            for n in noten:
                anzahl[n.punkte] += 1
        else:
            anzahl = {s: 0 for s in range(1, 7)}
            for n in noten:
                anzahl[n.stufe] += 1
        gesamt = len(noten)
        if not gesamt:
            return Notenspiegel(anzahl, None, None, None, sek2)
        schnitt = sum(n.wert for n in noten) / gesamt
        return Notenspiegel(
            anzahl,
            schnitt if sek2 else sum(s * a for s, a in anzahl.items()) / gesamt,
            schnitt,
            sum(1 for n in noten if (n.punkte < 5 if sek2 else n.stufe >= 5)) / gesamt * 100,   # Sek II: Defizite
            sek2,
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


# ---- Notensystem der Lerngruppe ------------------------------------------------------------------

@dataclass(frozen=True)
class Notensystem:
    """Alles, was sich zwischen Sek I und Sek II unterscheidet, an einer Stelle."""

    name: str                       # "sek1" oder "sek2"

    @staticmethod
    def von(name: str | None) -> "Notensystem":
        return SEK2 if name == "sek2" else SEK1

    @property
    def sek2(self) -> bool:
        return self.name == "sek2"

    @property
    def alle(self) -> list[Note]:
        return ALLE_PUNKTE if self.sek2 else ALLE_NOTEN

    @property
    def einheit(self) -> str:
        return "Punkte" if self.sek2 else "Note"

    @property
    def beispiele(self) -> str:
        return "11, 7 oder 0" if self.sek2 else "2, 2+, 2- oder 1,7"

    @property
    def warnabstand(self) -> float:
        """Ab dieser Abweichung vom Vorschlag wird eine festgesetzte Note hervorgehoben."""
        return 3.0 if self.sek2 else 1.0

    def standard_schluessel(self) -> Notenschluessel:
        return Notenschluessel.standard(self.name)

    def eingabe(self, text: str) -> Note | None:
        """Benutzereingabe → Note. Sek I: „2-“, „2+“, „2“ oder Zahl („1,7“ → nächste Stufe).
        Sek II: 0–15, Kommazahlen werden gerundet (,5 nach oben). Leer → None. ValueError bei Unsinn."""
        t = text.strip().replace("–", "-").replace("−", "-").replace("*", "").strip()
        if not t:
            return None
        if self.sek2:
            try:
                wert = float(t.replace(",", "."))
            except ValueError:
                raise ValueError(f"„{text}“ sind keine Punkte. Beispiele: {self.beispiele}") from None
            if not 0 <= wert <= 15:
                raise ValueError("Punkte liegen zwischen 0 und 15.")
            return self.naechste(wert)
        try:
            return Note.aus_kurz(t)
        except ValueError:
            pass
        try:
            wert = float(t.replace(",", "."))
        except ValueError:
            raise ValueError(f"„{text}“ ist keine Note. Beispiele: {self.beispiele}") from None
        if not 0.7 <= wert <= 6.0:
            raise ValueError("Noten liegen zwischen 0,7 (1+) und 6.")
        return self.naechste(wert)

    def naechste(self, wert: float) -> Note:
        """Rechenwert → nächstgelegene Note (Sek I mit Tendenz) bzw. Punktzahl; Gleichstand → die bessere."""
        if self.sek2:
            return Punkte.aus_punkte(max(0, min(15, int(runde(wert)))))
        return min(ALLE_NOTEN, key=lambda n: (round(abs(n.wert - wert), 6), n.wert))

    def ganz(self, wert: float) -> Note:
        """Zeugnisnote: Sek I ohne Tendenz (,5 → besser), Sek II ganze Punkte (,5 → besser)."""
        if self.sek2:
            return self.naechste(wert)
        return Note.aus(max(1, min(6, int(wert + 0.5 - 1e-9))))

    def zahl(self, wert: float | None) -> str:
        """Schnitt als Text: Sek I „2,35“, Sek II „10,5“."""
        if wert is None:
            return ""
        return (f"{wert:.1f}" if self.sek2 else f"{wert:.2f}").replace(".", ",")


SEK1 = Notensystem("sek1")
SEK2 = Notensystem("sek2")
