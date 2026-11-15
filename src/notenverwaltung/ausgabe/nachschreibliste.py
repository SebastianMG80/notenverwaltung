"""Nachschreibliste: alle mit „fehlt“ oder „schreibt nach“, je Arbeit ein Block, Spalten zum Eintragen von Hand.

Bewusst ohne Noten – die Liste darf auch Kolleg:innen oder der Aufsicht beim Nachschreibtermin gezeigt werden.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import STATUS, Nachschreiber

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter

RAND = 18.0
BREITE = 210 - 2 * RAND
KOPF = 20.0
ZEILE = 7.5
BLOCKKOPF = 8.0
UNTEN = 297 - 15.0
# Name | Klasse | Vermerk | Termin | Raum | erledigt
SPALTEN = (("Name", 62.0), ("Klasse", 18.0), ("Vermerk", 26.0), ("Termin", 28.0), ("Raum", 20.0), ("erledigt", 20.0))


class Nachschreibliste(Ausgabe):
    def __init__(self, eintraege: list[Nachschreiber], schuljahr: str, stand: date | None = None) -> None:
        self.eintraege = eintraege
        self.schuljahr = schuljahr
        self.stand = stand or date.today()
        self.titel = f"Nachschreibliste {schuljahr}"
        self._seiten = self._planen()

    def _bloecke(self) -> list[tuple[Nachschreiber, list[Nachschreiber]]]:
        bloecke: list[tuple[Nachschreiber, list[Nachschreiber]]] = []
        for n in self.eintraege:
            if bloecke and bloecke[-1][0].arbeit.id == n.arbeit.id:
                bloecke[-1][1].append(n)
            else:
                bloecke.append((n, [n]))
        return bloecke

    def _planen(self) -> list[list[tuple[float, str, object]]]:
        """Je Seite eine Liste (y, art, inhalt) mit art ∈ {block, kopf, zeile}."""
        seiten: list[list[tuple[float, str, object]]] = [[]]
        y = RAND + KOPF
        for erster, zeilen in self._bloecke():
            fortsetzung = False
            rest = list(zeilen)
            while rest:
                if y + BLOCKKOPF + ZEILE * 2 > UNTEN:      # Kopf nie allein am Seitenende
                    seiten.append([])
                    y = RAND + KOPF
                seiten[-1].append((y, "block", (erster, fortsetzung)))
                y += BLOCKKOPF
                seiten[-1].append((y, "kopf", None))
                y += ZEILE
                while rest and y + ZEILE <= UNTEN:
                    seiten[-1].append((y, "zeile", rest.pop(0)))
                    y += ZEILE
                y += 5
                fortsetzung = True
        return seiten

    def seitenzahl(self) -> int:
        return len(self._seiten)

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        s.stift("#000000")
        s.schrift(14, fett=True)
        s.text(RAND, RAND, BREITE * 0.7, 7, "Nachschreibliste", LINKS)
        s.schrift(9)
        s.stift("#333333")
        s.text(RAND, RAND + 7.5, BREITE * 0.7, 5, f"Schuljahr {self.schuljahr} · Stand {self.stand:%d.%m.%Y}", LINKS)
        s.text(RAND + BREITE * 0.6, RAND, BREITE * 0.4, 7, f"Seite {nummer + 1} von {self.seitenzahl()}", RECHTS)
        if self.kopfzeile:
            s.text(RAND + BREITE * 0.3, RAND + 7.5, BREITE * 0.7, 5, self.kopfzeile, RECHTS)
        s.stift("#000000")
        if not self.eintraege:
            s.schrift(11)
            s.text(RAND, RAND + KOPF, BREITE, 8, "Niemand muss etwas nachschreiben.", LINKS)
            return
        tabelle_oben = None
        for y, art, inhalt in self._seiten[nummer]:
            if art == "block":
                n, fortsetzung = inhalt
                s.schrift(11, fett=True)
                s.text(RAND, y, BREITE, BLOCKKOPF - 1,
                       f"{n.gruppe.bezeichnung} · {n.arbeit.titel} · geschrieben am {n.arbeit.datum:%d.%m.%Y}"
                       + (" (Fortsetzung)" if fortsetzung else ""), LINKS)
            elif art == "kopf":
                tabelle_oben = y
                s.flaeche(RAND, y, BREITE, ZEILE, "#e2e2e2")
                s.schrift(9, fett=True)
                x = RAND
                for kopf, b in SPALTEN:
                    s.text(x + 1.5, y, b - 3, ZEILE, kopf, LINKS if kopf == "Name" else MITTE)
                    x += b
            else:
                n: Nachschreiber = inhalt
                e = n.ergebnis
                s.schrift(10)
                werte = (f"{e.mitglied.schueler.nachname}, {e.mitglied.schueler.vorname}", e.mitglied.klasse,
                         STATUS.get(e.status, e.status), "", "", "✓" if n.erledigt else "")
                x = RAND
                for (kopf, b), w in zip(SPALTEN, werte):
                    s.text(x + 1.5, y, b - 3, ZEILE, w, LINKS if kopf == "Name" else MITTE)
                    x += b
                s.stift("#999999", 0.15)
                s.linie(RAND, y + ZEILE, RAND + BREITE, y + ZEILE)
                s.stift("#000000")
                naechste = next((t for t in self._seiten[nummer] if t[0] > y), None)
                if naechste is None or naechste[1] != "zeile":     # Block zu Ende: Rahmen und Spaltenlinien
                    unten = y + ZEILE
                    s.stift("#555555", 0.2)
                    s.kasten(RAND, tabelle_oben, BREITE, unten - tabelle_oben)
                    x = RAND
                    for _, b in SPALTEN[:-1]:
                        x += b
                        s.linie(x, tabelle_oben, x, unten)
                    s.stift("#000000")
