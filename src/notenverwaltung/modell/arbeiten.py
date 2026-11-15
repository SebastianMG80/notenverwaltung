"""Klassenarbeiten: Aufgaben, Punkte, Noten, Notenspiegel – reine Logik ohne Oberfläche."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from notenverwaltung.modell.noten import Note, Notenschluessel, Notenspiegel, Punkte, zahl_text
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Stammdaten

STATUS = {"": "", "fehlt": "fehlt", "nachschreiben": "schreibt nach", "befreit": "befreit"}


class ArbeitFehler(ValueError):
    """Ungültige Eingabe – der Text ist für die Anzeige gedacht."""


def _d(wert: str | None) -> date | None:
    return date.fromisoformat(wert) if wert else None


@dataclass(frozen=True)
class Aufgabe:
    id: int
    arbeit_id: int
    position: int
    bezeichnung: str
    max_punkte: float
    thema: str = ""
    erwartung: str = ""


@dataclass(frozen=True)
class Arbeit:
    id: int
    lerngruppe_id: int
    titel: str
    datum: date
    schluessel: Notenschluessel
    rueckgabe: date | None = None
    art: str = "klassenarbeit"
    zaehlt: bool = True
    gewicht: float = 1.0
    thema: str = ""
    bemerkung: str = ""
    musterloesung: str = ""


@dataclass(frozen=True)
class Ergebnis:
    mitglied: Mitglied
    punkte: dict[int, float | None]          # Aufgabe-ID → Punkte (None = nichts eingetragen)
    summe: float | None
    note_berechnet: Note | None
    note_manuell: Note | None
    status: str
    kommentar: str
    erwartet: bool                           # war am Tag der Arbeit in der Lerngruppe
    unvollstaendig: bool = field(default=False)

    @property
    def note(self) -> Note | None:
        return self.note_manuell or self.note_berechnet


@dataclass(frozen=True)
class AufgabenStatistik:
    aufgabe: Aufgabe
    mittel: float | None
    anteil: float | None     # Prozent der Höchstpunkte im Mittel


@dataclass(frozen=True)
class Nachschreiber:
    """Eine Person, die eine Arbeit nachschreiben muss (Vermerk „fehlt“ oder „schreibt nach“)."""
    gruppe: Lerngruppe
    arbeit: Arbeit
    ergebnis: Ergebnis

    @property
    def erledigt(self) -> bool:
        return self.ergebnis.note is not None or self.ergebnis.summe is not None


@dataclass(frozen=True)
class SchluesselVorlage:
    id: int
    name: str
    schluessel: Notenschluessel
    standard: bool


class Arbeiten:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung
        self.sd = Stammdaten(verbindung)

    # ---- Notenschlüssel-Vorlagen ---------------------------------------------------------------
    def vorlagen(self) -> list[SchluesselVorlage]:
        return [SchluesselVorlage(z[0], z[1], Notenschluessel.aus_json(z[2]), bool(z[3])) for z in self.v.execute(
            "SELECT id, name, daten, standard FROM notenschluessel ORDER BY standard DESC, name")]

    def vorlagen_fuer(self, system: str) -> list[SchluesselVorlage]:
        """Vorlagen eines Notensystems (Sek I: Noten, Sek II: Punkte), Standard zuerst."""
        return [v for v in self.vorlagen() if v.schluessel.system == system]

    def standard_schluessel(self, system: str = "sek1") -> Notenschluessel:
        vorlagen = self.vorlagen_fuer(system)
        return vorlagen[0].schluessel if vorlagen else Notenschluessel.standard(system)

    def speichere_vorlage(self, name: str, schluessel: Notenschluessel, standard: bool = False) -> None:
        name = name.strip()
        if not name:
            raise ArbeitFehler("Bitte einen Namen für die Vorlage angeben.")
        schluessel.pruefe()
        with self.v:
            if standard:   # nur innerhalb desselben Notensystems gibt es genau einen Standard
                for v in self.vorlagen_fuer(schluessel.system):
                    self.v.execute("UPDATE notenschluessel SET standard = 0 WHERE id = ?", (v.id,))
            self.v.execute("INSERT INTO notenschluessel (name, daten, standard) VALUES (?, ?, ?) "
                           "ON CONFLICT (name) DO UPDATE SET daten = excluded.daten, standard = excluded.standard",
                           (name, schluessel.als_json(), int(standard)))

    def loesche_vorlage(self, vorlage_id: int) -> None:
        v = next((x for x in self.vorlagen() if x.id == vorlage_id), None)
        if v is None:
            return
        gleiche = self.vorlagen_fuer(v.schluessel.system)
        if len(gleiche) <= 1:
            raise ArbeitFehler("Die letzte Vorlage kann nicht gelöscht werden.")
        with self.v:
            self.v.execute("DELETE FROM notenschluessel WHERE id = ?", (vorlage_id,))
            if v.standard:
                rest = sorted((x for x in gleiche if x.id != vorlage_id), key=lambda x: x.name)
                self.v.execute("UPDATE notenschluessel SET standard = 1 WHERE id = ?", (rest[0].id,))

    # ---- Arbeiten ------------------------------------------------------------------------------
    _SPALTEN = ("id, lerngruppe_id, titel, datum, schluessel, rueckgabe, art, zaehlt, gewicht, thema, bemerkung, "
                "musterloesung")

    @staticmethod
    def _arbeit(z) -> Arbeit:
        return Arbeit(z[0], z[1], z[2], _d(z[3]), Notenschluessel.aus_json(z[4]), _d(z[5]), z[6], bool(z[7]),
                      z[8], z[9], z[10], z[11])

    def arbeit(self, arbeit_id: int) -> Arbeit:
        z = self.v.execute(f"SELECT {self._SPALTEN} FROM arbeit WHERE id = ?", (arbeit_id,)).fetchone()
        if z is None:
            raise ArbeitFehler("Arbeit nicht gefunden.")
        return self._arbeit(z)

    def arbeiten(self, lerngruppe_id: int) -> list[Arbeit]:
        return [self._arbeit(z) for z in self.v.execute(
            f"SELECT {self._SPALTEN} FROM arbeit WHERE lerngruppe_id = ? ORDER BY datum, id", (lerngruppe_id,))]

    def titel_vorschlag(self, lerngruppe_id: int) -> str:
        return f"{len(self.arbeiten(lerngruppe_id)) + 1}. Klassenarbeit"

    def _pruefe(self, lerngruppe_id: int, titel: str, datum: date, rueckgabe: date | None) -> None:
        if not titel.strip():
            raise ArbeitFehler("Bitte einen Titel angeben.")
        g = self.sd.lerngruppe(lerngruppe_id)
        jahr = self.sd.schuljahr(g.schuljahr_id)
        if not jahr.enthaelt(datum):
            raise ArbeitFehler(f"Das Datum liegt nicht im Schuljahr {jahr.bezeichnung}.")
        if rueckgabe and rueckgabe < datum:
            raise ArbeitFehler("Die Rückgabe liegt vor dem Tag der Arbeit.")

    def lege_arbeit_an(self, lerngruppe_id: int, titel: str, datum: date,
                       aufgaben: list[tuple[str, float]] | None = None,
                       schluessel: Notenschluessel | None = None, rueckgabe: date | None = None,
                       thema: str = "") -> Arbeit:
        self._pruefe(lerngruppe_id, titel, datum, rueckgabe)
        schluessel = schluessel or self.standard_schluessel(self.sd.lerngruppe(lerngruppe_id).notensystem)
        with self.v:
            c = self.v.execute(
                "INSERT INTO arbeit (lerngruppe_id, titel, datum, rueckgabe, schluessel, thema) VALUES (?, ?, ?, ?, ?, ?)",
                (lerngruppe_id, titel.strip(), datum.isoformat(), rueckgabe.isoformat() if rueckgabe else None,
                 schluessel.als_json(), thema))
        arbeit_id = c.lastrowid
        if aufgaben:
            self.setze_aufgaben(arbeit_id, [(None, b, m, "", "") for b, m in aufgaben])
        return self.arbeit(arbeit_id)

    def aendere_arbeit(self, a: Arbeit) -> None:
        self._pruefe(a.lerngruppe_id, a.titel, a.datum, a.rueckgabe)
        a.schluessel.pruefe()
        with self.v:
            self.v.execute(
                "UPDATE arbeit SET titel = ?, datum = ?, rueckgabe = ?, schluessel = ?, art = ?, zaehlt = ?, "
                "gewicht = ?, thema = ?, bemerkung = ?, musterloesung = ? WHERE id = ?",
                (a.titel.strip(), a.datum.isoformat(), a.rueckgabe.isoformat() if a.rueckgabe else None,
                 a.schluessel.als_json(), a.art, int(a.zaehlt), a.gewicht, a.thema, a.bemerkung, a.musterloesung,
                 a.id))

    def loesche_arbeit(self, arbeit_id: int) -> None:
        with self.v:
            self.v.execute("DELETE FROM arbeit WHERE id = ?", (arbeit_id,))

    # ---- Aufgaben ------------------------------------------------------------------------------
    def aufgaben(self, arbeit_id: int) -> list[Aufgabe]:
        return [Aufgabe(*z) for z in self.v.execute(
            "SELECT id, arbeit_id, position, bezeichnung, max_punkte, thema, erwartung FROM aufgabe "
            "WHERE arbeit_id = ? ORDER BY position", (arbeit_id,))]

    def hoechstpunkte(self, arbeit_id: int) -> float:
        return self.v.execute("SELECT COALESCE(SUM(max_punkte), 0) FROM aufgabe WHERE arbeit_id = ?",
                              (arbeit_id,)).fetchone()[0]

    def setze_aufgaben(self, arbeit_id: int,
                       liste: list[tuple[int | None, str, float, str, str]]) -> list[Aufgabe]:
        """Gleicht die Aufgaben ab: (id oder None, Bezeichnung, Höchstpunkte, Thema, Erwartung) in Reihenfolge.

        Nicht mehr enthaltene Aufgaben werden samt ihren Punkten gelöscht.
        """
        for _, bez, maximum, _, _ in liste:
            if not str(bez).strip():
                raise ArbeitFehler("Jede Aufgabe braucht eine Bezeichnung.")
            if maximum is None or maximum < 0:
                raise ArbeitFehler(f"Aufgabe {bez}: Die Höchstpunktzahl darf nicht negativ sein.")
        vorhanden = {a.id: a for a in self.aufgaben(arbeit_id)}
        behalten = {i for i, *_ in liste if i is not None}
        with self.v:
            for alt_id in set(vorhanden) - behalten:
                self.v.execute("DELETE FROM aufgabe WHERE id = ?", (alt_id,))
            for pos, (aid, bez, maximum, thema, erwartung) in enumerate(liste, 1):
                if aid is not None and aid in vorhanden:
                    zu_viel = self.v.execute("SELECT COUNT(*) FROM punkte WHERE aufgabe_id = ? AND punkte > ?",
                                             (aid, maximum)).fetchone()[0]
                    if zu_viel:
                        raise ArbeitFehler(f"Aufgabe {bez}: {zu_viel} Eintrag/Einträge liegen über der neuen "
                                           f"Höchstpunktzahl {zahl_text(maximum)}.")
                    self.v.execute("UPDATE aufgabe SET position = ?, bezeichnung = ?, max_punkte = ?, thema = ?, "
                                   "erwartung = ? WHERE id = ?", (pos, str(bez).strip(), maximum, thema, erwartung, aid))
                else:
                    self.v.execute("INSERT INTO aufgabe (arbeit_id, position, bezeichnung, max_punkte, thema, erwartung) "
                                   "VALUES (?, ?, ?, ?, ?, ?)", (arbeit_id, pos, str(bez).strip(), maximum, thema,
                                                                 erwartung))
        return self.aufgaben(arbeit_id)

    # ---- Punkte und Teilnahme ------------------------------------------------------------------
    def setze_punkte(self, aufgabe_id: int, schueler_id: int, wert: float | None) -> None:
        z = self.v.execute("SELECT max_punkte, bezeichnung FROM aufgabe WHERE id = ?", (aufgabe_id,)).fetchone()
        if z is None:
            raise ArbeitFehler("Aufgabe nicht gefunden.")
        maximum, bez = z
        with self.v:
            if wert is None:
                self.v.execute("DELETE FROM punkte WHERE aufgabe_id = ? AND schueler_id = ?", (aufgabe_id, schueler_id))
                return
            if wert < 0:
                raise ArbeitFehler("Punkte können nicht negativ sein.")
            if wert > maximum + 1e-9:
                raise ArbeitFehler(f"Aufgabe {bez}: höchstens {zahl_text(maximum)} Punkte.")
            if abs(wert * 4 - round(wert * 4)) > 1e-9:
                raise ArbeitFehler("Bitte ganze, halbe oder Viertelpunkte eingeben.")
            self.v.execute("INSERT INTO punkte (aufgabe_id, schueler_id, punkte) VALUES (?, ?, ?) "
                           "ON CONFLICT (aufgabe_id, schueler_id) DO UPDATE SET punkte = excluded.punkte",
                           (aufgabe_id, schueler_id, wert))

    def setze_teilnahme(self, arbeit_id: int, schueler_id: int, *, status: str | None = None,
                        note_manuell: Note | None | str = "unverändert", kommentar: str | None = None) -> None:
        if status is not None and status not in STATUS:
            raise ArbeitFehler("Unbekannter Status.")
        if isinstance(note_manuell, Note) and (isinstance(note_manuell, Punkte)
                                               != (self.arbeit(arbeit_id).schluessel.system == "sek2")):
            raise ArbeitFehler("In der Oberstufe werden Punkte (0–15) vergeben, sonst Noten (1–6).")
        alt = self.v.execute("SELECT status, note_manuell, kommentar FROM teilnahme WHERE arbeit_id = ? AND "
                             "schueler_id = ?", (arbeit_id, schueler_id)).fetchone() or ("", None, "")
        neu_status = alt[0] if status is None else status
        neu_note = alt[1] if isinstance(note_manuell, str) else (note_manuell.speicher if note_manuell else None)
        neu_kommentar = alt[2] if kommentar is None else kommentar
        with self.v:
            if not neu_status and neu_note is None and not neu_kommentar:
                self.v.execute("DELETE FROM teilnahme WHERE arbeit_id = ? AND schueler_id = ?", (arbeit_id, schueler_id))
            else:
                self.v.execute("INSERT INTO teilnahme (arbeit_id, schueler_id, status, note_manuell, kommentar) "
                               "VALUES (?, ?, ?, ?, ?) ON CONFLICT (arbeit_id, schueler_id) DO UPDATE SET "
                               "status = excluded.status, note_manuell = excluded.note_manuell, "
                               "kommentar = excluded.kommentar",
                               (arbeit_id, schueler_id, neu_status, neu_note, neu_kommentar))

    # ---- Auswertung ----------------------------------------------------------------------------
    def ergebnisse(self, arbeit_id: int) -> list[Ergebnis]:
        a = self.arbeit(arbeit_id)
        aufgaben = self.aufgaben(arbeit_id)
        maximum = sum(x.max_punkte for x in aufgaben)
        punkte: dict[tuple[int, int], float] = {
            (sid, aid): p for aid, sid, p in self.v.execute(
                "SELECT p.aufgabe_id, p.schueler_id, p.punkte FROM punkte p JOIN aufgabe a ON a.id = p.aufgabe_id "
                "WHERE a.arbeit_id = ?", (arbeit_id,))}
        teilnahme = {z[0]: z[1:] for z in self.v.execute(
            "SELECT schueler_id, status, note_manuell, kommentar FROM teilnahme WHERE arbeit_id = ?", (arbeit_id,))}
        ergebnisse = []
        for m in self.sd.mitglieder(a.lerngruppe_id):
            sid = m.schueler.id
            werte = {x.id: punkte.get((sid, x.id)) for x in aufgaben}
            eingetragen = [w for w in werte.values() if w is not None]
            summe = sum(eingetragen) if eingetragen else None
            berechnet = a.schluessel.note(summe, maximum) if summe is not None and maximum > 0 else None
            status, manuell, kommentar = teilnahme.get(sid, ("", None, ""))
            ergebnisse.append(Ergebnis(
                mitglied=m, punkte=werte, summe=summe, note_berechnet=berechnet,
                note_manuell=Note.lies(manuell) if manuell else None, status=status, kommentar=kommentar,
                erwartet=m.aktiv_am(a.datum),
                unvollstaendig=bool(eingetragen) and len(eingetragen) < len(aufgaben)))
        return ergebnisse

    def notenspiegel(self, arbeit_id: int, ergebnisse: list[Ergebnis] | None = None) -> Notenspiegel:
        ergebnisse = ergebnisse if ergebnisse is not None else self.ergebnisse(arbeit_id)
        return Notenspiegel.aus([e.note for e in ergebnisse if e.note is not None],
                                sek2=self.arbeit(arbeit_id).schluessel.system == "sek2")

    def aufgaben_statistik(self, arbeit_id: int, ergebnisse: list[Ergebnis] | None = None) -> list[AufgabenStatistik]:
        ergebnisse = ergebnisse if ergebnisse is not None else self.ergebnisse(arbeit_id)
        statistik = []
        for x in self.aufgaben(arbeit_id):
            werte = [e.punkte[x.id] for e in ergebnisse if e.punkte.get(x.id) is not None]
            mittel = sum(werte) / len(werte) if werte else None
            anteil = mittel / x.max_punkte * 100 if mittel is not None and x.max_punkte else None
            statistik.append(AufgabenStatistik(x, mittel, anteil))
        return statistik

    def nachschreibliste(self, schuljahr_id: int, auch_erledigte: bool = False) -> list[Nachschreiber]:
        """Alle mit „fehlt“ oder „schreibt nach“ aus allen Lerngruppen des Schuljahrs, nach Datum der Arbeit.
        Erledigt ist, wer inzwischen Punkte oder eine Note hat."""
        arbeit_ids = [z[0] for z in self.v.execute(
            "SELECT DISTINCT t.arbeit_id FROM teilnahme t JOIN arbeit a ON a.id = t.arbeit_id "
            "JOIN lerngruppe g ON g.id = a.lerngruppe_id "
            "WHERE g.schuljahr_id = ? AND t.status IN ('fehlt', 'nachschreiben')", (schuljahr_id,))]
        liste = []
        for aid in arbeit_ids:
            a = self.arbeit(aid)
            g = self.sd.lerngruppe(a.lerngruppe_id)
            for e in self.ergebnisse(aid):
                if e.status in ("fehlt", "nachschreiben"):
                    n = Nachschreiber(g, a, e)
                    if auch_erledigte or not n.erledigt:
                        liste.append(n)
        liste.sort(key=lambda n: (n.arbeit.datum, n.gruppe.bezeichnung, n.arbeit.id,
                                  n.ergebnis.mitglied.schueler.nachname, n.ergebnis.mitglied.schueler.vorname))
        return liste
