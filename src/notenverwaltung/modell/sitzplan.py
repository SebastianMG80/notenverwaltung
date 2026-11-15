"""Sitzpläne: ein Raster (Spalten × Reihen), in dem Plätze stehen; auf einem Platz sitzt höchstens eine Person.

Koordinaten aus Sicht der Klasse: x = Spalte von links, y = Reihe von vorne (Tafel). Mehrere Pläne je Lerngruppe
(z. B. für zwei Räume). Vorlagen setzen die Plätze schnell: 2er-Tische in Reihen, 4er-Gruppentische, U-Form.
"""

from __future__ import annotations

import random
import sqlite3
from dataclasses import dataclass

from notenverwaltung.modell.stammdaten import Mitglied, name_schluessel

MAX = 12
VORLAGEN = {"reihen": "Reihen (2er-Tische)", "gruppen": "Gruppentische (4er)", "u": "U-Form", "leer": "Leer"}


class SitzplanFehler(ValueError):
    pass


@dataclass(frozen=True)
class Sitzplan:
    id: int
    lerngruppe_id: int
    name: str
    spalten: int
    zeilen: int


def ist_platz(art: str, x: int, y: int, spalten: int, zeilen: int) -> bool:
    if art == "reihen":
        return x % 3 != 2
    if art == "gruppen":
        return x % 3 != 2 and y % 3 != 2
    if art == "u":
        return x == 0 or x == spalten - 1 or y == zeilen - 1
    return False


class Sitzplaene:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung

    # ---- Pläne -----------------------------------------------------------------------------------
    def plaene(self, lerngruppe_id: int) -> list[Sitzplan]:
        return [Sitzplan(*z) for z in self.v.execute(
            "SELECT id, lerngruppe_id, name, spalten, zeilen FROM sitzplan WHERE lerngruppe_id = ? "
            "ORDER BY position, id", (lerngruppe_id,))]

    def plan(self, plan_id: int) -> Sitzplan:
        z = self.v.execute("SELECT id, lerngruppe_id, name, spalten, zeilen FROM sitzplan WHERE id = ?",
                           (plan_id,)).fetchone()
        if z is None:
            raise SitzplanFehler("Sitzplan nicht gefunden.")
        return Sitzplan(*z)

    def lege_an(self, lerngruppe_id: int, name: str = "Sitzplan", spalten: int = 8, zeilen: int = 6,
                vorlage: str = "reihen") -> Sitzplan:
        self._pruefe_groesse(spalten, zeilen)
        name = name.strip() or "Sitzplan"
        with self.v:
            c = self.v.execute("INSERT INTO sitzplan (lerngruppe_id, name, spalten, zeilen, position) VALUES "
                               "(?, ?, ?, ?, (SELECT COALESCE(MAX(position), 0) + 1 FROM sitzplan "
                               "WHERE lerngruppe_id = ?))", (lerngruppe_id, name, spalten, zeilen, lerngruppe_id))
        plan = self.plan(c.lastrowid)
        self.vorlage(plan.id, vorlage)
        return plan

    def umbenennen(self, plan_id: int, name: str) -> None:
        if not name.strip():
            raise SitzplanFehler("Der Sitzplan braucht einen Namen.")
        with self.v:
            self.v.execute("UPDATE sitzplan SET name = ? WHERE id = ?", (name.strip(), plan_id))

    def loesche(self, plan_id: int) -> None:
        with self.v:
            self.v.execute("DELETE FROM sitzplan WHERE id = ?", (plan_id,))

    @staticmethod
    def _pruefe_groesse(spalten: int, zeilen: int) -> None:
        if not (1 <= spalten <= MAX and 1 <= zeilen <= MAX):
            raise SitzplanFehler(f"Das Raster darf höchstens {MAX} × {MAX} Felder groß sein.")

    def setze_groesse(self, plan_id: int, spalten: int, zeilen: int) -> None:
        """Ändert das Raster; Plätze außerhalb fallen weg (ihre Personen werden wieder frei)."""
        self._pruefe_groesse(spalten, zeilen)
        with self.v:
            self.v.execute("UPDATE sitzplan SET spalten = ?, zeilen = ? WHERE id = ?", (spalten, zeilen, plan_id))
            self.v.execute("DELETE FROM sitzplatz WHERE sitzplan_id = ? AND (x >= ? OR y >= ?)",
                           (plan_id, spalten, zeilen))

    # ---- Plätze ----------------------------------------------------------------------------------
    def plaetze(self, plan_id: int) -> dict[tuple[int, int], int | None]:
        """(x, y) → Schüler-ID oder None (freier Platz)."""
        return {(z[0], z[1]): z[2] for z in self.v.execute(
            "SELECT x, y, schueler_id FROM sitzplatz WHERE sitzplan_id = ?", (plan_id,))}

    def setze_platz(self, plan_id: int, x: int, y: int, vorhanden: bool) -> None:
        p = self.plan(plan_id)
        if not (0 <= x < p.spalten and 0 <= y < p.zeilen):
            raise SitzplanFehler("Der Platz liegt außerhalb des Rasters.")
        with self.v:
            if vorhanden:
                self.v.execute("INSERT OR IGNORE INTO sitzplatz (sitzplan_id, x, y) VALUES (?, ?, ?)", (plan_id, x, y))
            else:
                self.v.execute("DELETE FROM sitzplatz WHERE sitzplan_id = ? AND x = ? AND y = ?", (plan_id, x, y))

    def vorlage(self, plan_id: int, art: str) -> None:
        """Setzt die Plätze nach einer Vorlage. Wer auf einem Platz sitzt, der bleibt, behält ihn."""
        if art not in VORLAGEN:
            raise SitzplanFehler(f"Unbekannte Vorlage „{art}“.")
        p = self.plan(plan_id)
        alt = self.plaetze(plan_id)
        with self.v:
            for x in range(p.spalten):
                for y in range(p.zeilen):
                    soll = ist_platz(art, x, y, p.spalten, p.zeilen)
                    if soll and (x, y) not in alt:
                        self.v.execute("INSERT INTO sitzplatz (sitzplan_id, x, y) VALUES (?, ?, ?)", (plan_id, x, y))
                    elif not soll and (x, y) in alt and alt[(x, y)] is None:
                        self.v.execute("DELETE FROM sitzplatz WHERE sitzplan_id = ? AND x = ? AND y = ?",
                                       (plan_id, x, y))

    def setze_person(self, plan_id: int, x: int, y: int, schueler_id: int | None) -> None:
        """Setzt eine Person auf einen Platz (von einem anderen Platz weg). Sitzt dort schon jemand, tauschen
        die beiden; kommt die Person aus der Liste, wird die bisherige frei."""
        plaetze = self.plaetze(plan_id)
        if (x, y) not in plaetze:
            raise SitzplanFehler("Dort ist kein Platz.")
        bisher = plaetze[(x, y)]
        von = next((k for k, sid in plaetze.items() if sid == schueler_id), None) if schueler_id else None
        with self.v:
            if von is not None:
                self.v.execute("UPDATE sitzplatz SET schueler_id = ? WHERE sitzplan_id = ? AND x = ? AND y = ?",
                               (bisher, plan_id, *von))
            self.v.execute("UPDATE sitzplatz SET schueler_id = ? WHERE sitzplan_id = ? AND x = ? AND y = ?",
                           (schueler_id, plan_id, x, y))

    def verteile(self, plan_id: int, mitglieder: list[Mitglied], art: str = "alphabet",
                 zufall: random.Random | None = None) -> int:
        """Setzt alle noch nicht sitzenden Personen auf freie Plätze (vorne links beginnend). Gibt die Anzahl
        zurück. art: „alphabet“ oder „zufall“."""
        plaetze = self.plaetze(plan_id)
        sitzend = {sid for sid in plaetze.values() if sid}
        frei = sorted((k for k, sid in plaetze.items() if sid is None), key=lambda k: (k[1], k[0]))
        offen = [m for m in mitglieder if m.schueler.id not in sitzend]
        if art == "zufall":
            (zufall or random.Random()).shuffle(offen)
        else:
            offen.sort(key=lambda m: (name_schluessel(m.schueler.nachname), name_schluessel(m.schueler.vorname)))
        n = min(len(frei), len(offen))
        with self.v:
            for (x, y), m in zip(frei, offen):
                self.v.execute("UPDATE sitzplatz SET schueler_id = ? WHERE sitzplan_id = ? AND x = ? AND y = ?",
                               (m.schueler.id, plan_id, x, y))
        return n

    def raeume_ab(self, plan_id: int) -> None:
        """Alle Personen von den Plätzen nehmen (die Plätze bleiben)."""
        with self.v:
            self.v.execute("UPDATE sitzplatz SET schueler_id = NULL WHERE sitzplan_id = ?", (plan_id,))
