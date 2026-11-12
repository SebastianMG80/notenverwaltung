"""Mündliche Noten (Sonstige Mitarbeit) je Zeitraum.

- Jede Lerngruppe hat Zeiträume; Standard sind vier Quartale (zwei je Halbjahr), feiner unterteilbar.
- Ein Zeitraum liegt immer ganz in einem Halbjahr, damit Halbjahresnoten eindeutig sind.
- Noten werden mit Tendenz gespeichert; Eingabe als „2-“ oder als Zahl („2,3“ → 2-).
- Wer vor Beginn eines Zeitraums ausgetreten bzw. erst nach dessen Ende eingetreten ist, bekommt dort keine Note.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Mitglied, Schuljahr, Stammdaten


class MuendlichFehler(ValueError):
    pass


@dataclass(frozen=True)
class Zeitraum:
    id: int
    lerngruppe_id: int
    bezeichnung: str
    beginn: date
    ende: date

    def erfasst(self, m: Mitglied) -> bool:
        """War die Person in diesem Zeitraum (wenigstens zeitweise) in der Lerngruppe?"""
        return (m.beginn is None or m.beginn <= self.ende) and (m.ende is None or m.ende >= self.beginn)


def note_aus_eingabe(text: str) -> Note | None:
    """„2-“, „2+“, „2“ oder Zahl („1,7“, „2.3“, „2,5“ → nächstgelegene Stufe). Leer → None."""
    t = text.strip().replace("–", "-").replace("−", "-")
    if not t:
        return None
    try:
        return Note.aus_kurz(t)
    except ValueError:
        pass
    try:
        wert = float(t.replace(",", "."))
    except ValueError:
        raise MuendlichFehler(f"„{text}“ ist keine Note. Beispiele: 2, 2+, 2-, 1,7") from None
    if not 0.7 <= wert <= 6.0:
        raise MuendlichFehler("Noten liegen zwischen 0,7 (1+) und 6.")
    from notenverwaltung.modell.noten import ALLE_NOTEN

    return min(ALLE_NOTEN, key=lambda n: (abs(n.wert - wert), n.wert))


def standard_zeitraeume(jahr: Schuljahr) -> list[tuple[str, date, date]]:
    """Vier Quartale: jedes Halbjahr in der Mitte geteilt."""
    def halbiere(a: date, b: date) -> date:
        return a + timedelta(days=(b - a).days // 2)

    hj1_ende = jahr.halbjahreswechsel - timedelta(days=1)
    m1 = halbiere(jahr.beginn, hj1_ende)
    m2 = halbiere(jahr.halbjahreswechsel, jahr.ende)
    return [("1. Quartal", jahr.beginn, m1), ("2. Quartal", m1 + timedelta(days=1), hj1_ende),
            ("3. Quartal", jahr.halbjahreswechsel, m2), ("4. Quartal", m2 + timedelta(days=1), jahr.ende)]


class Muendlich:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung
        self.sd = Stammdaten(verbindung)

    # ---- Zeiträume ---------------------------------------------------------------------------
    def zeitraeume(self, lerngruppe_id: int, anlegen: bool = True) -> list[Zeitraum]:
        liste = [Zeitraum(z[0], z[1], z[2], date.fromisoformat(z[3]), date.fromisoformat(z[4])) for z in self.v.execute(
            "SELECT id, lerngruppe_id, bezeichnung, beginn, ende FROM zeitraum WHERE lerngruppe_id = ? "
            "ORDER BY beginn, id", (lerngruppe_id,))]
        if not liste and anlegen:
            jahr = self.sd.schuljahr(self.sd.lerngruppe(lerngruppe_id).schuljahr_id)
            self.setze_zeitraeume(lerngruppe_id, [(None, *z) for z in standard_zeitraeume(jahr)])
            return self.zeitraeume(lerngruppe_id, anlegen=False)
        return liste

    def pruefe_zeitraeume(self, jahr: Schuljahr, liste: list[tuple[int | None, str, date, date]]) -> None:
        if not liste:
            raise MuendlichFehler("Es muss mindestens einen Zeitraum geben.")
        sortiert = sorted(liste, key=lambda z: z[2])
        for _, bez, a, b in sortiert:
            if not bez.strip():
                raise MuendlichFehler("Jeder Zeitraum braucht eine Bezeichnung.")
            if b < a:
                raise MuendlichFehler(f"„{bez}“: Das Ende liegt vor dem Beginn.")
            if not (jahr.enthaelt(a) and jahr.enthaelt(b)):
                raise MuendlichFehler(f"„{bez}“ liegt nicht ganz im Schuljahr {jahr.bezeichnung}.")
            if jahr.halbjahr(a) != jahr.halbjahr(b):
                raise MuendlichFehler(f"„{bez}“ geht über den Halbjahreswechsel – bitte aufteilen.")
        for (_, b1, _, e1), (_, b2, a2, _) in zip(sortiert, sortiert[1:]):
            if a2 <= e1:
                raise MuendlichFehler(f"„{b1}“ und „{b2}“ überschneiden sich.")

    def setze_zeitraeume(self, lerngruppe_id: int, liste: list[tuple[int | None, str, date, date]]) -> None:
        """Gleicht die Zeiträume ab (id oder None, Bezeichnung, Beginn, Ende). Entfernte verlieren ihre Noten."""
        jahr = self.sd.schuljahr(self.sd.lerngruppe(lerngruppe_id).schuljahr_id)
        self.pruefe_zeitraeume(jahr, liste)
        vorhanden = {z[0] for z in self.v.execute("SELECT id FROM zeitraum WHERE lerngruppe_id = ?", (lerngruppe_id,))}
        behalten = {i for i, *_ in liste if i is not None}
        with self.v:
            for alt in vorhanden - behalten:
                self.v.execute("DELETE FROM zeitraum WHERE id = ?", (alt,))
            for zid, bez, a, b in liste:
                if zid is not None and zid in vorhanden:
                    self.v.execute("UPDATE zeitraum SET bezeichnung = ?, beginn = ?, ende = ? WHERE id = ?",
                                   (bez.strip(), a.isoformat(), b.isoformat(), zid))
                else:
                    self.v.execute("INSERT INTO zeitraum (lerngruppe_id, bezeichnung, beginn, ende) VALUES (?, ?, ?, ?)",
                                   (lerngruppe_id, bez.strip(), a.isoformat(), b.isoformat()))

    def teile(self, zeitraum_id: int, stichtag: date, bezeichnungen: tuple[str, str] | None = None) -> None:
        """Teilt einen Zeitraum am Stichtag (Stichtag gehört zum zweiten Teil). Noten bleiben beim ersten Teil."""
        z = next((x for x in self._alle() if x.id == zeitraum_id), None)
        if z is None:
            raise MuendlichFehler("Zeitraum nicht gefunden.")
        if not z.beginn < stichtag <= z.ende:
            raise MuendlichFehler("Der Stichtag muss innerhalb des Zeitraums liegen.")
        a, b = bezeichnungen or (f"{z.bezeichnung} (a)", f"{z.bezeichnung} (b)")
        liste = [(x.id, x.bezeichnung, x.beginn, x.ende) for x in self.zeitraeume(z.lerngruppe_id) if x.id != z.id]
        liste += [(z.id, a, z.beginn, stichtag - timedelta(days=1)), (None, b, stichtag, z.ende)]
        self.setze_zeitraeume(z.lerngruppe_id, liste)

    def _alle(self) -> list[Zeitraum]:
        return [Zeitraum(z[0], z[1], z[2], date.fromisoformat(z[3]), date.fromisoformat(z[4]))
                for z in self.v.execute("SELECT id, lerngruppe_id, bezeichnung, beginn, ende FROM zeitraum")]

    # ---- Noten ---------------------------------------------------------------------------------
    def setze_note(self, zeitraum_id: int, schueler_id: int, note: Note | None, bemerkung: str | None = None) -> None:
        z = next((x for x in self._alle() if x.id == zeitraum_id), None)
        if z is None:
            raise MuendlichFehler("Zeitraum nicht gefunden.")
        if note is not None:
            m = next((m for m in self.sd.mitglieder(z.lerngruppe_id) if m.schueler.id == schueler_id), None)
            if m is None:
                raise MuendlichFehler("Die Person gehört nicht zur Lerngruppe.")
            if not z.erfasst(m):
                raise MuendlichFehler(f"{m.schueler.vorname} {m.schueler.nachname} war im Zeitraum "
                                      f"„{z.bezeichnung}“ nicht in der Lerngruppe.")
        with self.v:
            if note is None:
                self.v.execute("DELETE FROM muendlich WHERE zeitraum_id = ? AND schueler_id = ?", (zeitraum_id, schueler_id))
            else:
                alt = self.v.execute("SELECT bemerkung FROM muendlich WHERE zeitraum_id = ? AND schueler_id = ?",
                                     (zeitraum_id, schueler_id)).fetchone()
                text = bemerkung if bemerkung is not None else (alt[0] if alt else "")
                self.v.execute("INSERT INTO muendlich (zeitraum_id, schueler_id, note, bemerkung) VALUES (?, ?, ?, ?) "
                               "ON CONFLICT (zeitraum_id, schueler_id) DO UPDATE SET note = excluded.note, "
                               "bemerkung = excluded.bemerkung", (zeitraum_id, schueler_id, note.kurz, text))

    def noten(self, lerngruppe_id: int) -> dict[tuple[int, int], tuple[Note, str]]:
        """(zeitraum_id, schueler_id) → (Note, Bemerkung)."""
        return {(z, s): (Note.aus_kurz(n), b) for z, s, n, b in self.v.execute(
            "SELECT m.zeitraum_id, m.schueler_id, m.note, m.bemerkung FROM muendlich m "
            "JOIN zeitraum z ON z.id = m.zeitraum_id WHERE z.lerngruppe_id = ?", (lerngruppe_id,))}

    def halbjahresschnitt(self, lerngruppe_id: int, schueler_id: int, halbjahr: int) -> float | None:
        """Mittel der mündlichen Noten eines Halbjahres (gleich gewichtet), None ohne Noten."""
        jahr = self.sd.schuljahr(self.sd.lerngruppe(lerngruppe_id).schuljahr_id)
        noten = self.noten(lerngruppe_id)
        werte = [noten[(z.id, schueler_id)][0].wert for z in self.zeitraeume(lerngruppe_id)
                 if jahr.halbjahr(z.beginn) == halbjahr and (z.id, schueler_id) in noten]
        return sum(werte) / len(werte) if werte else None
