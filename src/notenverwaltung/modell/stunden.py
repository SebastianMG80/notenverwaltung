"""Schnellerfassung je Stunde: ++ / + / o / – / –– je Person und Tag, sporadisch.

Werte: ++ = 1, + = 2, o = 3, – = 4, –– = 5. Der Durchschnitt eines mündlichen Zeitraums ist nur ein Vorschlag für
die mündliche Note (Sek I: nächste Note mit Tendenz; Sek II: Punkte = 17 − 3 × Durchschnitt, also 1 → 14 P.,
2 → 11 P., 3 → 8 P., 4 → 5 P., 5 → 2 P.). Die Note setzt immer die Lehrkraft.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from notenverwaltung.modell.noten import Note, Notensystem

SYMBOLE = {1: "++", 2: "+", 3: "o", 4: "–", 5: "––"}
_EINGABE = {"++": 1, "+": 2, "o": 3, "0": 3, "-": 4, "--": 5, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


class StundenFehler(ValueError):
    pass


def wert_aus_eingabe(text: str) -> int | None:
    """„++“, „+“, „o“, „-“, „--“ (auch – und 1–5) → 1…5; leer → None."""
    t = text.strip().lower().replace("–", "-").replace("−", "-").replace(" ", "")
    if not t:
        return None
    if t in _EINGABE:
        return _EINGABE[t]
    raise StundenFehler(f"„{text}“ verstehe ich nicht. Eingabe: ++  +  o  -  -- (oder 1 bis 5).")


@dataclass(frozen=True)
class Beobachtung:
    lerngruppe_id: int
    schueler_id: int
    datum: date
    wert: int
    notiz: str = ""

    @property
    def symbol(self) -> str:
        return SYMBOLE[self.wert]


@dataclass(frozen=True)
class Schnitt:
    wert: float | None
    anzahl: int
    verteilung: dict[int, int]

    def text(self) -> str:
        if self.wert is None:
            return "keine Einträge"
        teile = ", ".join(f"{SYMBOLE[w]} {n}×" for w, n in sorted(self.verteilung.items()) if n)
        return f"Ø {self.wert:.1f} aus {self.anzahl} {'Stunde' if self.anzahl == 1 else 'Stunden'} ({teile})".replace(
            ".", ",", 1)


def vorschlag(schnitt: Schnitt, system: Notensystem) -> Note | None:
    if schnitt.wert is None:
        return None
    if system.sek2:
        return system.naechste(max(0.0, min(15.0, 17 - 3 * schnitt.wert)))
    return system.naechste(schnitt.wert)


class Stunden:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung

    def eintraege(self, lerngruppe_id: int) -> dict[tuple[int, date], Beobachtung]:
        return {(z[1], date.fromisoformat(z[2])): Beobachtung(z[0], z[1], date.fromisoformat(z[2]), z[3], z[4])
                for z in self.v.execute("SELECT lerngruppe_id, schueler_id, datum, wert, notiz FROM beobachtung "
                                        "WHERE lerngruppe_id = ?", (lerngruppe_id,))}

    def daten(self, lerngruppe_id: int) -> list[date]:
        return [date.fromisoformat(z[0]) for z in self.v.execute(
            "SELECT DISTINCT datum FROM beobachtung WHERE lerngruppe_id = ? ORDER BY datum", (lerngruppe_id,))]

    def setze(self, lerngruppe_id: int, schueler_id: int, datum: date, wert: int | None,
              notiz: str | None = None) -> None:
        """Setzt die Bewertung (None löscht sie samt Notiz). `notiz=None` lässt eine vorhandene Notiz stehen."""
        if wert is not None and wert not in SYMBOLE:
            raise StundenFehler("Bewertungen gehen von ++ (1) bis –– (5).")
        with self.v:
            if wert is None:
                self.v.execute("DELETE FROM beobachtung WHERE lerngruppe_id = ? AND schueler_id = ? AND datum = ?",
                               (lerngruppe_id, schueler_id, datum.isoformat()))
                return
            self.v.execute(
                "INSERT INTO beobachtung (lerngruppe_id, schueler_id, datum, wert, notiz) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (lerngruppe_id, schueler_id, datum) DO UPDATE SET wert = excluded.wert"
                + (", notiz = excluded.notiz" if notiz is not None else ""),
                (lerngruppe_id, schueler_id, datum.isoformat(), wert, (notiz or "").strip()))

    def setze_notiz(self, lerngruppe_id: int, schueler_id: int, datum: date, notiz: str) -> None:
        with self.v:
            c = self.v.execute("UPDATE beobachtung SET notiz = ? WHERE lerngruppe_id = ? AND schueler_id = ? "
                               "AND datum = ?", (notiz.strip(), lerngruppe_id, schueler_id, datum.isoformat()))
        if c.rowcount == 0:
            raise StundenFehler("Erst eine Bewertung eintragen, dann eine Notiz.")

    def schnitt(self, lerngruppe_id: int, schueler_id: int, von: date, bis: date,
                eintraege: dict[tuple[int, date], Beobachtung] | None = None) -> Schnitt:
        eintraege = eintraege if eintraege is not None else self.eintraege(lerngruppe_id)
        werte = [b.wert for (sid, d), b in eintraege.items() if sid == schueler_id and von <= d <= bis]
        verteilung = {w: werte.count(w) for w in SYMBOLE}
        return Schnitt(sum(werte) / len(werte) if werte else None, len(werte), verteilung)
