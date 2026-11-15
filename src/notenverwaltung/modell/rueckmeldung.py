"""Rückmeldungen zu Klassenarbeiten: Textbausteine mit Platzhaltern, Vorschlag aus den Aufgabenergebnissen,
Aufgabenanalyse (Lösungsquote je Aufgabe).

Platzhalter in Textbausteinen: {Vorname}, {Nachname}, {Note}, {Punkte}, {Höchstpunkte}, {Prozent}, {Arbeit},
{Fach}, {Stärken}, {Übungsbedarf}. „Stärken“ sind Aufgaben ab `stark` Prozent, „Übungsbedarf“ Aufgaben unter
`schwach` Prozent (Standard 80 / 50) – genannt wird das Thema der Aufgabe, sonst „Aufgabe 3a“.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from notenverwaltung.modell.arbeiten import Arbeit, Aufgabe, Ergebnis
from notenverwaltung.modell.noten import zahl_text

PLATZHALTER = ("Vorname", "Nachname", "Note", "Punkte", "Höchstpunkte", "Prozent", "Arbeit", "Fach", "Stärken",
               "Übungsbedarf")
STARK, SCHWACH = 80.0, 50.0


class TextbausteinFehler(ValueError):
    pass


@dataclass(frozen=True)
class Textbaustein:
    id: int
    kuerzel: str
    text: str
    fach: str = ""
    position: int = 0


class Textbausteine:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung

    def alle(self, fach: str | None = None) -> list[Textbaustein]:
        """Alle Bausteine; mit `fach` nur die für dieses Fach und die für alle Fächer."""
        liste = [Textbaustein(*z) for z in self.v.execute(
            "SELECT id, kuerzel, text, fach, position FROM textbaustein ORDER BY position, id")]
        if fach is not None:
            f = fach.strip().lower()
            liste = [b for b in liste if not b.fach or b.fach.strip().lower() == f]
        return liste

    def finde(self, kuerzel: str, fach: str | None = None) -> Textbaustein | None:
        k = kuerzel.strip().lower()
        treffer = [b for b in self.alle(fach) if b.kuerzel and b.kuerzel.lower() == k]
        # das fachspezifische vor dem allgemeinen
        treffer.sort(key=lambda b: not b.fach)
        return treffer[0] if treffer else None

    def setze(self, liste: list[tuple[int | None, str, str, str]]) -> None:
        """Ersetzt alle Bausteine durch `liste` aus (id oder None, kürzel, text, fach) – in dieser Reihenfolge."""
        gesehen: set[tuple[str, str]] = set()
        sauber = []
        for bid, kuerzel, text, fach in liste:
            kuerzel, text, fach = kuerzel.strip(), text.strip(), fach.strip()
            if not text:
                if kuerzel:
                    raise TextbausteinFehler(f"Zum Kürzel „{kuerzel}“ fehlt der Text.")
                continue
            if re.search(r"\s", kuerzel):
                raise TextbausteinFehler(f"Das Kürzel „{kuerzel}“ darf keine Leerzeichen enthalten.")
            if kuerzel:
                schluessel = (kuerzel.lower(), fach.lower())
                if schluessel in gesehen:
                    raise TextbausteinFehler(f"Das Kürzel „{kuerzel}“ gibt es doppelt"
                                             + (f" (Fach {fach})." if fach else "."))
                gesehen.add(schluessel)
            sauber.append((bid, kuerzel, text, fach))
        with self.v:
            behalten = {bid for bid, *_ in sauber if bid is not None}
            for (bid,) in self.v.execute("SELECT id FROM textbaustein").fetchall():
                if bid not in behalten:
                    self.v.execute("DELETE FROM textbaustein WHERE id = ?", (bid,))
            for pos, (bid, kuerzel, text, fach) in enumerate(sauber, 1):
                if bid is None:
                    self.v.execute("INSERT INTO textbaustein (kuerzel, text, fach, position) VALUES (?, ?, ?, ?)",
                                   (kuerzel, text, fach, pos))
                else:
                    self.v.execute("UPDATE textbaustein SET kuerzel = ?, text = ?, fach = ?, position = ? "
                                   "WHERE id = ?", (kuerzel, text, fach, pos, bid))


# ---- Auswertung je Person ------------------------------------------------------------------------

def _name(a: Aufgabe) -> str:
    return a.thema.strip() or f"Aufgabe {a.bezeichnung}"


def aufzaehlung(namen: list[str]) -> str:
    if len(namen) <= 1:
        return "".join(namen)
    return ", ".join(namen[:-1]) + " und " + namen[-1]


def staerken_und_uebungsbedarf(e: Ergebnis, aufgaben: list[Aufgabe], stark: float = STARK,
                               schwach: float = SCHWACH) -> tuple[list[str], list[str]]:
    """Themen der Aufgaben ab `stark` % bzw. unter `schwach` % (gleiche Themen nur einmal)."""
    gut: list[str] = []
    ueben: list[str] = []
    for a in aufgaben:
        p = e.punkte.get(a.id)
        if p is None or not a.max_punkte:
            continue
        quote = p / a.max_punkte * 100
        ziel = gut if quote >= stark else ueben if quote < schwach else None
        if ziel is not None and _name(a) not in ziel:
            ziel.append(_name(a))
    gut = [n for n in gut if n not in ueben]          # Teilaufgaben mit gleichem Thema: Übungsbedarf hat Vorrang
    return gut, ueben


def platzhalter_werte(e: Ergebnis, arbeit: Arbeit, fach: str, aufgaben: list[Aufgabe], stark: float = STARK,
                      schwach: float = SCHWACH) -> dict[str, str]:
    hoechst = sum(a.max_punkte for a in aufgaben)
    gut, ueben = staerken_und_uebungsbedarf(e, aufgaben, stark, schwach)
    s = e.mitglied.schueler
    return {
        "Vorname": s.vorname,
        "Nachname": s.nachname,
        "Note": e.note.wort if e.note else "",
        "Punkte": zahl_text(e.summe) if e.summe is not None else "",
        "Höchstpunkte": zahl_text(hoechst),
        "Prozent": f"{e.summe / hoechst * 100:.0f} %" if e.summe is not None and hoechst else "",
        "Arbeit": arbeit.titel,
        "Fach": fach,
        "Stärken": aufzaehlung(gut),
        "Übungsbedarf": aufzaehlung(ueben),
    }


def fuelle(text: str, werte: dict[str, str]) -> str:
    """Setzt Platzhalter ein; unbekannte bleiben stehen (Tippfehler fallen so auf)."""
    return re.sub(r"\{([^{}]+)\}", lambda m: werte.get(m.group(1).strip(), m.group(0)), text)


def vorschlag(e: Ergebnis, aufgaben: list[Aufgabe], stark: float = STARK, schwach: float = SCHWACH) -> str:
    """Rückmeldung aus den Aufgabenergebnissen – nur ein Vorschlag zum Weiterschreiben."""
    if e.summe is None:
        return ""
    gut, ueben = staerken_und_uebungsbedarf(e, aufgaben, stark, schwach)
    saetze = []
    if gut:
        saetze.append(f"Besonders gut gelungen: {aufzaehlung(gut)}.")
    if ueben:
        saetze.append(f"Übe noch einmal: {aufzaehlung(ueben)}.")
    if not saetze:
        saetze.append("Alle Aufgaben hast du zu einem guten Teil gelöst.")
    return " ".join(saetze)


# ---- Aufgabenanalyse für die ganze Lerngruppe ----------------------------------------------------

@dataclass(frozen=True)
class AufgabenAnalyse:
    aufgabe: Aufgabe
    bearbeitet: int          # Personen mit Eintrag
    quote: float | None      # mittlerer Anteil der Höchstpunkte in Prozent
    voll: int                # volle Punktzahl
    null: int                # 0 Punkte


def aufgabenanalyse(ergebnisse: list[Ergebnis], aufgaben: list[Aufgabe]) -> list[AufgabenAnalyse]:
    liste = []
    for a in aufgaben:
        werte = [e.punkte[a.id] for e in ergebnisse if e.punkte.get(a.id) is not None]
        quote = sum(werte) / len(werte) / a.max_punkte * 100 if werte and a.max_punkte else None
        liste.append(AufgabenAnalyse(a, len(werte), quote, sum(1 for w in werte if w >= a.max_punkte),
                                     sum(1 for w in werte if w == 0)))
    return liste
