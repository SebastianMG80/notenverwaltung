"""Stammdaten: Schuljahre, Schüler:innen, Klassen, Lerngruppen und Mitgliedschaften.

Reine Logik ohne Oberfläche – arbeitet direkt auf der SQLite-Verbindung der geöffneten Datenbank.

Begriffe:
- Lerngruppe: eine Klasse in einem Fach („8.4 Deutsch“) oder ein klassenübergreifender Kurs („M9.3E“).
- Zugang/Abgang: Eintritt in die bzw. Austritt aus der Schule während des Schuljahres (gilt für alle Lerngruppen).
- von/bis: Eintritt in bzw. Austritt aus einer einzelnen Lerngruppe (z. B. Kurswechsel).
Nach dem Austritt bleiben alle Daten erhalten; für spätere Leistungen wird keine Eingabe mehr erwartet.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date

SORTIERUNGEN = {"klasse": "Klasse, dann Alphabet", "alphabet": "Alphabet", "eigene": "Eigene Reihenfolge"}

FAECHER = [
    ("Deutsch", "D"), ("Englisch", "E"), ("Mathematik", "M"), ("Französisch", "F"), ("Spanisch", "S"),
    ("Latein", "L"), ("Biologie", "BI"), ("Chemie", "CH"), ("Physik", "PH"), ("Naturwissenschaften", "NW"),
    ("Gesellschaftslehre", "GL"), ("Geschichte", "GE"), ("Erdkunde", "EK"), ("Politik", "PK"),
    ("Wirtschaft", "WI"), ("Arbeitslehre", "AL"), ("Informatik", "IF"), ("Technik", "TC"), ("Kunst", "KU"),
    ("Musik", "MU"), ("Sport", "SP"), ("Ev. Religion", "ER"), ("Kath. Religion", "KR"),
    ("Praktische Philosophie", "PP"), ("Darstellen und Gestalten", "DG"), ("Wahlpflicht", "WP"),
]


class StammdatenFehler(ValueError):
    """Ungültige Eingabe – der Text ist für die Anzeige gedacht."""


# ---- Hilfsfunktionen ---------------------------------------------------------------------------

def _d(wert: str | None) -> date | None:
    return date.fromisoformat(wert) if wert else None


def _iso(wert: date | None) -> str | None:
    return wert.isoformat() if wert else None


def name_schluessel(text: str) -> str:
    """Sortierschlüssel nach DIN 5007-1 (ä wie a, ß wie ss), unabhängig von Groß-/Kleinschreibung."""
    zerlegt = unicodedata.normalize("NFD", text.replace("ß", "ss").replace("ẞ", "SS"))
    return "".join(z for z in zerlegt if not unicodedata.combining(z)).casefold()


def natuerlich(text: str) -> tuple:
    """Natürliche Sortierung: „8.4“ < „8.10“ < „10.1“."""
    return tuple((0, int(t), "") if t.isdigit() else (1, 0, name_schluessel(t))
                 for t in re.findall(r"\d+|\D+", text))


def jahrgang_aus_klasse(klasse: str) -> int | None:
    m = re.match(r"\s*(\d{1,2})", klasse)
    return int(m.group(1)) if m else None


def schuljahr_vorschlag(heute: date | None = None) -> tuple[str, date, date, date]:
    """(Bezeichnung, Beginn, Halbjahreswechsel, Ende) für das Schuljahr, in dem `heute` liegt (Wechsel am 1. August)."""
    heute = heute or date.today()
    j = heute.year if heute.month >= 8 else heute.year - 1
    return f"{j}/{(j + 1) % 100:02d}", date(j, 8, 1), date(j + 1, 2, 1), date(j + 1, 7, 31)


def _in_zeitraum(datum: date, von: date | None, bis: date | None) -> bool:
    return (von is None or von <= datum) and (bis is None or datum <= bis)


# ---- Datenklassen ------------------------------------------------------------------------------

@dataclass(frozen=True)
class Schuljahr:
    id: int
    bezeichnung: str
    beginn: date
    halbjahreswechsel: date
    ende: date

    def enthaelt(self, datum: date) -> bool:
        return self.beginn <= datum <= self.ende

    def halbjahr(self, datum: date) -> int:
        return 1 if datum < self.halbjahreswechsel else 2


@dataclass(frozen=True)
class Schueler:
    id: int
    nachname: str
    vorname: str
    geburtsdatum: date | None = None
    extern_id: str | None = None
    bemerkung: str = ""

    @property
    def name(self) -> str:
        return f"{self.nachname}, {self.vorname}"


@dataclass(frozen=True)
class SchuelerImJahr:
    schueler: Schueler
    jahrgang: int
    klasse: str
    zugang: date | None = None
    abgang: date | None = None

    def aktiv_am(self, datum: date) -> bool:
        return _in_zeitraum(datum, self.zugang, self.abgang)


@dataclass(frozen=True)
class Lerngruppe:
    id: int
    schuljahr_id: int
    bezeichnung: str
    fach: str
    art: str = "kurs"
    jahrgang: int = 5
    fach_kuerzel: str = ""
    niveau: str = ""
    schriftlich: bool = True
    notensystem: str = "sek1"
    sortierung: str = "klasse"

    @property
    def beschreibung(self) -> str:
        teile = [self.fach, "Klasse" if self.art == "klasse" else "Kurs", f"Jahrgang {self.jahrgang}"]
        if self.niveau:
            teile.append(f"{self.niveau}-Kurs")
        teile.append("schriftlich" if self.schriftlich else "mündlich")
        return " · ".join(teile)


@dataclass(frozen=True)
class Mitglied:
    schueler: Schueler
    jahrgang: int
    klasse: str
    von: date | None = None          # Eintritt in die Lerngruppe
    bis: date | None = None          # Austritt aus der Lerngruppe
    zugang: date | None = None       # Eintritt in die Schule
    abgang: date | None = None       # Austritt aus der Schule
    position: int | None = None
    nummer: int = field(default=0, compare=False)  # laufende Nummer in der aktuellen Sortierung

    @property
    def beginn(self) -> date | None:
        werte = [d for d in (self.von, self.zugang) if d]
        return max(werte) if werte else None

    @property
    def ende(self) -> date | None:
        werte = [d for d in (self.bis, self.abgang) if d]
        return min(werte) if werte else None

    def aktiv_am(self, datum: date) -> bool:
        return _in_zeitraum(datum, self.beginn, self.ende)

    @property
    def status(self) -> str:
        if self.abgang:
            return f"Abgang am {self.abgang:%d.%m.%Y}"
        if self.bis:
            return f"ausgetreten am {self.bis:%d.%m.%Y}"
        b = self.beginn
        return f"seit {b:%d.%m.%Y}" if b else ""


# ---- Zugriff -----------------------------------------------------------------------------------

class Stammdaten:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung

    # ---- Schuljahre ----------------------------------------------------------------------------
    @staticmethod
    def _schuljahr(z) -> Schuljahr:
        return Schuljahr(z[0], z[1], _d(z[2]), _d(z[3]), _d(z[4]))

    def schuljahre(self) -> list[Schuljahr]:
        """Neueste zuerst."""
        return [self._schuljahr(z) for z in self.v.execute(
            "SELECT id, bezeichnung, beginn, halbjahreswechsel, ende FROM schuljahr ORDER BY beginn DESC")]

    def schuljahr(self, schuljahr_id: int) -> Schuljahr:
        z = self.v.execute("SELECT id, bezeichnung, beginn, halbjahreswechsel, ende FROM schuljahr WHERE id = ?",
                           (schuljahr_id,)).fetchone()
        if z is None:
            raise StammdatenFehler("Schuljahr nicht gefunden.")
        return self._schuljahr(z)

    def aktuelles_schuljahr(self, heute: date | None = None) -> Schuljahr | None:
        heute = heute or date.today()
        jahre = self.schuljahre()
        for sj in jahre:
            if sj.enthaelt(heute):
                return sj
        vergangen = [sj for sj in jahre if sj.beginn <= heute]
        return vergangen[0] if vergangen else (jahre[-1] if jahre else None)

    @staticmethod
    def _pruefe_schuljahr(bezeichnung: str, beginn: date, wechsel: date, ende: date) -> None:
        if not bezeichnung.strip():
            raise StammdatenFehler("Bitte eine Bezeichnung für das Schuljahr angeben.")
        if not (beginn < wechsel <= ende):
            raise StammdatenFehler("Der Halbjahreswechsel muss zwischen Beginn und Ende des Schuljahres liegen.")

    def lege_schuljahr_an(self, bezeichnung: str, beginn: date, wechsel: date, ende: date) -> Schuljahr:
        self._pruefe_schuljahr(bezeichnung, beginn, wechsel, ende)
        try:
            with self.v:
                c = self.v.execute(
                    "INSERT INTO schuljahr (bezeichnung, beginn, halbjahreswechsel, ende) VALUES (?, ?, ?, ?)",
                    (bezeichnung.strip(), _iso(beginn), _iso(wechsel), _iso(ende)))
        except sqlite3.IntegrityError as e:
            raise StammdatenFehler(f"Das Schuljahr „{bezeichnung}“ gibt es schon.") from e
        return self.schuljahr(c.lastrowid)

    def aendere_schuljahr(self, sj: Schuljahr) -> None:
        self._pruefe_schuljahr(sj.bezeichnung, sj.beginn, sj.halbjahreswechsel, sj.ende)
        try:
            with self.v:
                self.v.execute(
                    "UPDATE schuljahr SET bezeichnung = ?, beginn = ?, halbjahreswechsel = ?, ende = ? WHERE id = ?",
                    (sj.bezeichnung.strip(), _iso(sj.beginn), _iso(sj.halbjahreswechsel), _iso(sj.ende), sj.id))
        except sqlite3.IntegrityError as e:
            raise StammdatenFehler(f"Das Schuljahr „{sj.bezeichnung}“ gibt es schon.") from e

    # ---- Schüler:innen -------------------------------------------------------------------------
    @staticmethod
    def _schueler(z) -> Schueler:
        return Schueler(z[0], z[1], z[2], _d(z[3]), z[4], z[5] or "")

    def schueler(self, schueler_id: int) -> Schueler:
        z = self.v.execute("SELECT id, nachname, vorname, geburtsdatum, extern_id, bemerkung FROM schueler "
                           "WHERE id = ?", (schueler_id,)).fetchone()
        if z is None:
            raise StammdatenFehler("Schüler:in nicht gefunden.")
        return self._schueler(z)

    def _pruefe_datum_im_jahr(self, schuljahr_id: int, *daten: date | None) -> None:
        sj = self.schuljahr(schuljahr_id)
        for d in daten:
            if d is not None and not sj.enthaelt(d):
                raise StammdatenFehler(f"Das Datum {d:%d.%m.%Y} liegt nicht im Schuljahr {sj.bezeichnung}.")

    def lege_schueler_an(self, schuljahr_id: int, nachname: str, vorname: str, klasse: str,
                         jahrgang: int | None = None, zugang: date | None = None,
                         geburtsdatum: date | None = None, extern_id: str | None = None) -> Schueler:
        nachname, vorname, klasse = nachname.strip(), vorname.strip(), klasse.strip()
        if not nachname or not vorname:
            raise StammdatenFehler("Bitte Nach- und Vornamen angeben.")
        if not klasse:
            raise StammdatenFehler("Bitte eine Klasse angeben.")
        jahrgang = jahrgang or jahrgang_aus_klasse(klasse)
        if not jahrgang:
            raise StammdatenFehler("Bitte den Jahrgang angeben.")
        self._pruefe_datum_im_jahr(schuljahr_id, zugang)
        with self.v:
            c = self.v.execute("INSERT INTO schueler (nachname, vorname, geburtsdatum, extern_id) VALUES (?, ?, ?, ?)",
                               (nachname, vorname, _iso(geburtsdatum), extern_id))
            sid = c.lastrowid
            self.v.execute("INSERT INTO klassenzuordnung (schueler_id, schuljahr_id, jahrgang, klasse, zugang) "
                           "VALUES (?, ?, ?, ?, ?)", (sid, schuljahr_id, jahrgang, klasse, _iso(zugang)))
        return self.schueler(sid)

    def aendere_schueler(self, s: Schueler) -> None:
        if not s.nachname.strip() or not s.vorname.strip():
            raise StammdatenFehler("Bitte Nach- und Vornamen angeben.")
        with self.v:
            self.v.execute("UPDATE schueler SET nachname = ?, vorname = ?, geburtsdatum = ?, extern_id = ?, "
                           "bemerkung = ? WHERE id = ?",
                           (s.nachname.strip(), s.vorname.strip(), _iso(s.geburtsdatum), s.extern_id,
                            s.bemerkung, s.id))

    def setze_klasse(self, schueler_id: int, schuljahr_id: int, klasse: str, jahrgang: int | None = None,
                     zugang: date | None = None) -> None:
        """Klasse/Jahrgang/Zugang im Schuljahr setzen (legt die Zuordnung bei Bedarf an)."""
        klasse = klasse.strip()
        jahrgang = jahrgang or jahrgang_aus_klasse(klasse)
        if not klasse or not jahrgang:
            raise StammdatenFehler("Bitte Klasse und Jahrgang angeben.")
        self._pruefe_datum_im_jahr(schuljahr_id, zugang)
        with self.v:
            self.v.execute(
                "INSERT INTO klassenzuordnung (schueler_id, schuljahr_id, jahrgang, klasse, zugang) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (schueler_id, schuljahr_id) DO UPDATE SET jahrgang = excluded.jahrgang, "
                "klasse = excluded.klasse, zugang = excluded.zugang",
                (schueler_id, schuljahr_id, jahrgang, klasse, _iso(zugang)))

    def schueler_im_jahr(self, schuljahr_id: int, klasse: str | None = None) -> list[SchuelerImJahr]:
        sql = ("SELECT s.id, s.nachname, s.vorname, s.geburtsdatum, s.extern_id, s.bemerkung, "
               "k.jahrgang, k.klasse, k.zugang, k.abgang FROM klassenzuordnung k "
               "JOIN schueler s ON s.id = k.schueler_id WHERE k.schuljahr_id = ?")
        werte: list = [schuljahr_id]
        if klasse is not None:
            sql += " AND k.klasse = ?"
            werte.append(klasse)
        liste = [SchuelerImJahr(self._schueler(z[:6]), z[6], z[7], _d(z[8]), _d(z[9]))
                 for z in self.v.execute(sql, werte)]
        liste.sort(key=lambda e: (natuerlich(e.klasse), name_schluessel(e.schueler.nachname),
                                  name_schluessel(e.schueler.vorname)))
        return liste

    def klassen(self, schuljahr_id: int) -> list[str]:
        return sorted((z[0] for z in self.v.execute(
            "SELECT DISTINCT klasse FROM klassenzuordnung WHERE schuljahr_id = ?", (schuljahr_id,))), key=natuerlich)

    def abgang(self, schueler_id: int, schuljahr_id: int, datum: date | None) -> None:
        """Abgang von der Schule (datum=None nimmt ihn zurück). Endet auch in allen Lerngruppen des Jahres."""
        self._pruefe_datum_im_jahr(schuljahr_id, datum)
        with self.v:
            self.v.execute("UPDATE klassenzuordnung SET abgang = ? WHERE schueler_id = ? AND schuljahr_id = ?",
                           (_iso(datum), schueler_id, schuljahr_id))

    def loesche_schueler(self, schueler_id: int) -> None:
        """Löscht die Person mit allen Daten aus allen Schuljahren. Für Abgänge stattdessen `abgang` verwenden."""
        with self.v:
            self.v.execute("DELETE FROM schueler WHERE id = ?", (schueler_id,))

    # ---- Lerngruppen ---------------------------------------------------------------------------
    _LG_SPALTEN = ("id, schuljahr_id, bezeichnung, fach, art, jahrgang, fach_kuerzel, niveau, schriftlich, "
                   "notensystem, sortierung")

    @staticmethod
    def _lerngruppe(z) -> Lerngruppe:
        return Lerngruppe(z[0], z[1], z[2], z[3], z[4], z[5], z[6], z[7], bool(z[8]), z[9], z[10])

    def lerngruppe(self, lerngruppe_id: int) -> Lerngruppe:
        z = self.v.execute(f"SELECT {self._LG_SPALTEN} FROM lerngruppe WHERE id = ?", (lerngruppe_id,)).fetchone()
        if z is None:
            raise StammdatenFehler("Lerngruppe nicht gefunden.")
        return self._lerngruppe(z)

    def lerngruppen(self, schuljahr_id: int) -> list[Lerngruppe]:
        liste = [self._lerngruppe(z) for z in self.v.execute(
            f"SELECT {self._LG_SPALTEN} FROM lerngruppe WHERE schuljahr_id = ?", (schuljahr_id,))]
        liste.sort(key=lambda g: (g.jahrgang, natuerlich(g.bezeichnung)))
        return liste

    @staticmethod
    def _pruefe_lerngruppe(g: Lerngruppe) -> None:
        if not g.bezeichnung.strip():
            raise StammdatenFehler("Bitte eine Bezeichnung angeben.")
        if not g.fach.strip():
            raise StammdatenFehler("Bitte ein Fach angeben.")
        if g.art not in ("klasse", "kurs"):
            raise StammdatenFehler("Unbekannte Art der Lerngruppe.")
        if g.niveau not in ("", "E", "G"):
            raise StammdatenFehler("Das Kursniveau ist E, G oder leer.")
        if g.notensystem != "sek1":
            raise StammdatenFehler("Die Sekundarstufe II wird noch nicht unterstützt.")
        if not 1 <= g.jahrgang <= 13:
            raise StammdatenFehler("Der Jahrgang muss zwischen 1 und 13 liegen.")

    def lege_lerngruppe_an(self, g: Lerngruppe) -> Lerngruppe:
        self._pruefe_lerngruppe(g)
        try:
            with self.v:
                c = self.v.execute(
                    "INSERT INTO lerngruppe (schuljahr_id, bezeichnung, fach, art, jahrgang, fach_kuerzel, niveau, "
                    "schriftlich, notensystem, sortierung) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (g.schuljahr_id, g.bezeichnung.strip(), g.fach.strip(), g.art, g.jahrgang, g.fach_kuerzel.strip(),
                     g.niveau, int(g.schriftlich), g.notensystem, g.sortierung))
        except sqlite3.IntegrityError as e:
            raise StammdatenFehler(f"Die Lerngruppe „{g.bezeichnung}“ gibt es in diesem Schuljahr schon.") from e
        return self.lerngruppe(c.lastrowid)

    def aendere_lerngruppe(self, g: Lerngruppe) -> None:
        self._pruefe_lerngruppe(g)
        try:
            with self.v:
                self.v.execute(
                    "UPDATE lerngruppe SET bezeichnung = ?, fach = ?, art = ?, jahrgang = ?, fach_kuerzel = ?, "
                    "niveau = ?, schriftlich = ?, notensystem = ?, sortierung = ? WHERE id = ?",
                    (g.bezeichnung.strip(), g.fach.strip(), g.art, g.jahrgang, g.fach_kuerzel.strip(), g.niveau,
                     int(g.schriftlich), g.notensystem, g.sortierung, g.id))
        except sqlite3.IntegrityError as e:
            raise StammdatenFehler(f"Die Lerngruppe „{g.bezeichnung}“ gibt es in diesem Schuljahr schon.") from e

    def loesche_lerngruppe(self, lerngruppe_id: int) -> None:
        with self.v:
            self.v.execute("DELETE FROM lerngruppe WHERE id = ?", (lerngruppe_id,))

    # ---- Mitglieder ----------------------------------------------------------------------------
    def mitglieder(self, lerngruppe_id: int, sortierung: str | None = None) -> list[Mitglied]:
        g = self.lerngruppe(lerngruppe_id)
        sortierung = sortierung or g.sortierung
        liste = [
            Mitglied(self._schueler(z[:6]), z[6], z[7], _d(z[8]), _d(z[9]), _d(z[10]), _d(z[11]), z[12])
            for z in self.v.execute(
                "SELECT s.id, s.nachname, s.vorname, s.geburtsdatum, s.extern_id, s.bemerkung, "
                "COALESCE(k.jahrgang, 0), COALESCE(k.klasse, ''), m.von, m.bis, k.zugang, k.abgang, m.position "
                "FROM mitglied m JOIN schueler s ON s.id = m.schueler_id "
                "LEFT JOIN klassenzuordnung k ON k.schueler_id = s.id AND k.schuljahr_id = ? "
                "WHERE m.lerngruppe_id = ?", (g.schuljahr_id, lerngruppe_id))
        ]

        def nach_name(m: Mitglied):
            return (name_schluessel(m.schueler.nachname), name_schluessel(m.schueler.vorname), m.schueler.id)

        if sortierung == "alphabet":
            liste.sort(key=nach_name)
        elif sortierung == "eigene":
            liste.sort(key=lambda m: (m.position is None, m.position or 0, natuerlich(m.klasse), nach_name(m)))
        else:
            liste.sort(key=lambda m: (natuerlich(m.klasse), nach_name(m)))
        return [replace(m, nummer=i) for i, m in enumerate(liste, 1)]

    def fuege_hinzu(self, lerngruppe_id: int, schueler_ids: list[int], von: date | None = None) -> int:
        """Fügt Schüler:innen hinzu (bereits enthaltene werden übersprungen). Gibt die Anzahl neuer Mitglieder zurück."""
        g = self.lerngruppe(lerngruppe_id)
        self._pruefe_datum_im_jahr(g.schuljahr_id, von)
        # Position bleibt leer: Neue stehen in der eigenen Reihenfolge am Ende, bis sie verschoben werden
        neu = 0
        with self.v:
            for sid in schueler_ids:
                c = self.v.execute("INSERT OR IGNORE INTO mitglied (lerngruppe_id, schueler_id, von) VALUES (?, ?, ?)",
                                   (lerngruppe_id, sid, _iso(von)))
                neu += c.rowcount
        return neu

    def uebernimm_klasse(self, lerngruppe_id: int, klasse: str, von: date | None = None,
                         nur_aktive: bool = True) -> int:
        g = self.lerngruppe(lerngruppe_id)
        stichtag = von or self.schuljahr(g.schuljahr_id).beginn
        ids = [e.schueler.id for e in self.schueler_im_jahr(g.schuljahr_id, klasse)
               if not nur_aktive or e.abgang is None or e.abgang >= stichtag]
        return self.fuege_hinzu(lerngruppe_id, ids, von)

    def setze_zeitraum(self, lerngruppe_id: int, schueler_id: int, von: date | None, bis: date | None) -> None:
        """Eintritt/Austritt in einer Lerngruppe (None = Schuljahresbeginn bzw. -ende)."""
        g = self.lerngruppe(lerngruppe_id)
        self._pruefe_datum_im_jahr(g.schuljahr_id, von, bis)
        if von and bis and bis < von:
            raise StammdatenFehler("Der Austritt liegt vor dem Eintritt.")
        with self.v:
            self.v.execute("UPDATE mitglied SET von = ?, bis = ? WHERE lerngruppe_id = ? AND schueler_id = ?",
                           (_iso(von), _iso(bis), lerngruppe_id, schueler_id))

    def entferne_mitglied(self, lerngruppe_id: int, schueler_id: int) -> None:
        """Entfernt komplett (für Versehen). Wer die Gruppe verlässt, bekommt stattdessen ein Austrittsdatum."""
        with self.v:
            self.v.execute("DELETE FROM mitglied WHERE lerngruppe_id = ? AND schueler_id = ?",
                           (lerngruppe_id, schueler_id))

    def setze_sortierung(self, lerngruppe_id: int, sortierung: str) -> None:
        if sortierung not in SORTIERUNGEN:
            raise StammdatenFehler("Unbekannte Sortierung.")
        if sortierung == "eigene":
            eigene = self.mitglieder(lerngruppe_id, "eigene")
            if all(m.position is None for m in eigene):
                # Erstes Mal: die eigene Reihenfolge startet mit der aktuell angezeigten
                self.setze_reihenfolge(lerngruppe_id, [m.schueler.id for m in self.mitglieder(lerngruppe_id)])
            else:
                # Später Hinzugekommene ans Ende
                self.setze_reihenfolge(lerngruppe_id, [m.schueler.id for m in eigene])
        with self.v:
            self.v.execute("UPDATE lerngruppe SET sortierung = ? WHERE id = ?", (sortierung, lerngruppe_id))

    def setze_reihenfolge(self, lerngruppe_id: int, schueler_ids: list[int]) -> None:
        with self.v:
            for pos, sid in enumerate(schueler_ids, 1):
                self.v.execute("UPDATE mitglied SET position = ? WHERE lerngruppe_id = ? AND schueler_id = ?",
                               (pos, lerngruppe_id, sid))

    def verschiebe(self, lerngruppe_id: int, schueler_id: int, schritt: int) -> None:
        """Verschiebt in der eigenen Reihenfolge um `schritt` Plätze (negativ = nach oben)."""
        if self.lerngruppe(lerngruppe_id).sortierung != "eigene":
            self.setze_sortierung(lerngruppe_id, "eigene")
        ids = [m.schueler.id for m in self.mitglieder(lerngruppe_id, "eigene")]
        if schueler_id not in ids:
            return
        i = ids.index(schueler_id)
        j = max(0, min(len(ids) - 1, i + schritt))
        ids.insert(j, ids.pop(i))
        self.setze_reihenfolge(lerngruppe_id, ids)

    def lerngruppen_von(self, schueler_id: int, schuljahr_id: int) -> list[Lerngruppe]:
        return [self._lerngruppe(z) for z in self.v.execute(
            f"SELECT {', '.join('g.' + s.strip() for s in self._LG_SPALTEN.split(','))} FROM lerngruppe g "
            "JOIN mitglied m ON m.lerngruppe_id = g.id WHERE m.schueler_id = ? AND g.schuljahr_id = ?",
            (schueler_id, schuljahr_id))]
