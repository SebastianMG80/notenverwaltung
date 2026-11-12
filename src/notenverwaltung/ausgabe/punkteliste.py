"""Punkteliste einer Arbeit für die Lehrkraft (A4 quer) – wie der obere Teil von Punkteliste.ods,
dazu Notenspiegel, Schnitt, Anteil unter 4 und Notenschlüssel."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.arbeiten import STATUS, Arbeit, Arbeiten, Ergebnis
from notenverwaltung.modell.noten import zahl_text

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter
OBEN_LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop

RAND = 12.0
BREITE = 297 - 2 * RAND
HOEHE = 210 - 2 * RAND
ZEILE = 6.0
KOPF = 17.0
TABELLENKOPF = 9.0
FUSS = 42.0

FARBE_SCHWACH = "#f4d4d4"
FARBE_LUECKE = "#fbefc4"
FARBE_ZEBRA = "#f2f2f2"
FARBE_KOPF = "#e2e2e2"


@dataclass
class ListenOptionen:
    leere_ausblenden: bool = False
    mit_tendenz: bool = True
    schwache_hervorheben: bool = True       # Noten 5 und 6
    luecken_hervorheben: bool = True        # nicht eingetragene Aufgaben bei Teilkorrektur
    zebra: bool = True
    durchschnitt: bool = True
    notenspiegel: bool = True


class Punkteliste(Ausgabe):
    quer = True

    def __init__(self, ar: Arbeiten, arbeit: Arbeit, optionen: ListenOptionen | None = None) -> None:
        self.ar, self.arbeit = ar, arbeit
        self.o = optionen or ListenOptionen()
        self.gruppe = ar.sd.lerngruppe(arbeit.lerngruppe_id)
        self.jahr = ar.sd.schuljahr(self.gruppe.schuljahr_id)
        self.aufgaben = ar.aufgaben(arbeit.id)
        self.hoechst = sum(a.max_punkte for a in self.aufgaben)
        alle = ar.ergebnisse(arbeit.id)
        zeilen = [e for e in alle if e.erwartet or e.summe is not None or e.note is not None]
        if self.o.leere_ausblenden:
            zeilen = [e for e in zeilen if e.summe is not None or e.note is not None or e.status]
        self.zeilen: list[Ergebnis] = zeilen
        self.statistik = ar.aufgaben_statistik(arbeit.id, alle)
        self.spiegel = ar.notenspiegel(arbeit.id, alle)
        self.titel = f"Punkteliste {self.gruppe.bezeichnung} – {arbeit.titel}"
        # Spaltenbreiten
        fest = {"nr": 8, "nach": 34, "vor": 26, "kl": 10, "summe": 14, "note": 11}
        rest = BREITE - sum(fest.values())
        n = max(1, len(self.aufgaben))
        self.aufgabe_b = min(14.0, max(6.5, (rest - 22) / n))
        self.vermerk_b = rest - self.aufgabe_b * len(self.aufgaben)
        self.fest = fest
        # Seitenaufteilung
        pro_seite = int((HOEHE - KOPF - TABELLENKOPF) // ZEILE)
        extra = 1 if self.o.durchschnitt else 0
        self._seiten: list[list[Ergebnis]] = [self.zeilen[i:i + pro_seite]
                                              for i in range(0, max(1, len(self.zeilen)), pro_seite)] or [[]]
        letzte_hoehe = KOPF + TABELLENKOPF + (len(self._seiten[-1]) + extra) * ZEILE
        self._fuss_eigene_seite = self.o.notenspiegel and letzte_hoehe + FUSS > HOEHE

    def seitenzahl(self) -> int:
        return len(self._seiten) + (1 if self._fuss_eigene_seite else 0)

    # ---- Zeichnen ----------------------------------------------------------------------------------
    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        self._kopf(s, nummer)
        y = RAND + KOPF
        if nummer < len(self._seiten):
            y = self._tabelle(s, y, self._seiten[nummer], letzte=nummer == len(self._seiten) - 1)
            if self.o.notenspiegel and nummer == len(self._seiten) - 1 and not self._fuss_eigene_seite:
                self._fuss(s, y + 6)
        else:
            self._fuss(s, y)

    def _kopf(self, s: Seite, nummer: int) -> None:
        s.stift("#000000")
        s.schrift(14, fett=True)
        s.text(RAND, RAND, BREITE * 0.7, 7, f"{self.arbeit.titel} – {self.gruppe.bezeichnung}", LINKS)
        s.schrift(9)
        s.stift("#333333")
        teile = [self.gruppe.fach, f"geschrieben am {self.arbeit.datum:%d.%m.%Y}",
                 f"{self.jahr.halbjahr(self.arbeit.datum)}. Halbjahr {self.jahr.bezeichnung}"]
        if self.arbeit.thema:
            teile.append(self.arbeit.thema)
        s.text(RAND, RAND + 7.5, BREITE * 0.8, 5, " · ".join(teile), LINKS)
        s.text(RAND + BREITE * 0.6, RAND, BREITE * 0.4, 7,
               f"Seite {nummer + 1} von {self.seitenzahl()}", RECHTS)
        if self.kopfzeile:
            s.text(RAND + BREITE * 0.5, RAND + 7.5, BREITE * 0.5, 5, self.kopfzeile, RECHTS)

    def _spalten(self) -> list[tuple[float, float]]:
        """x-Position und Breite jeder Spalte."""
        breiten = [self.fest["nr"], self.fest["nach"], self.fest["vor"], self.fest["kl"]]
        breiten += [self.aufgabe_b] * len(self.aufgaben)
        breiten += [self.fest["summe"], self.fest["note"], self.vermerk_b]
        x, ergebnis = RAND, []
        for b in breiten:
            ergebnis.append((x, b))
            x += b
        return ergebnis

    def _tabelle(self, s: Seite, y: float, zeilen: list[Ergebnis], letzte: bool) -> float:
        sp = self._spalten()
        na = len(self.aufgaben)
        # Kopfzeile
        s.flaeche(RAND, y, BREITE, TABELLENKOPF, FARBE_KOPF)
        s.stift("#000000")
        s.schrift(8, fett=True)
        koepfe = ["Nr.", "Nachname", "Vorname", "Kl."]
        for i, (x, b) in enumerate(sp[:4]):
            s.text(x + 1, y, b - 2, TABELLENKOPF, koepfe[i], LINKS if i in (1, 2) else MITTE)
        pt_aufgabe = 8 if self.aufgabe_b >= 9 else 7
        for i, a in enumerate(self.aufgaben):
            x, b = sp[4 + i]
            s.schrift(pt_aufgabe, fett=True)
            s.text(x, y + 0.5, b, 4.5, a.bezeichnung, MITTE)
            s.schrift(pt_aufgabe - 1)
            s.text(x, y + 4.3, b, 4.2, f"({zahl_text(a.max_punkte)})", MITTE)
        x, b = sp[4 + na]
        s.schrift(8, fett=True)
        s.text(x, y + 0.5, b, 4.5, "Summe", MITTE)
        s.schrift(7)
        s.text(x, y + 4.3, b, 4.2, f"({zahl_text(self.hoechst)})", MITTE)
        s.schrift(8, fett=True)
        s.text(sp[5 + na][0], y, sp[5 + na][1], TABELLENKOPF, "Note", MITTE)
        s.text(sp[6 + na][0] + 1, y, sp[6 + na][1] - 1, TABELLENKOPF, "Vermerk", LINKS)
        y0 = y
        y += TABELLENKOPF

        for r, e in enumerate(zeilen):
            schwach = self.o.schwache_hervorheben and e.note is not None and e.note.stufe >= 5
            if schwach:
                s.flaeche(RAND, y, BREITE, ZEILE, FARBE_SCHWACH)
            elif self.o.zebra and r % 2:
                s.flaeche(RAND, y, BREITE, ZEILE, FARBE_ZEBRA)
            grau = not e.erwartet or e.status in ("fehlt", "befreit")
            s.stift("#777777" if grau else "#000000")
            s.schrift(8.5)
            werte = [str(e.mitglied.nummer), e.mitglied.schueler.nachname, e.mitglied.schueler.vorname,
                     e.mitglied.klasse]
            for i, (x, b) in enumerate(sp[:4]):
                s.text(x + 1, y, b - 2, ZEILE, werte[i], LINKS if i in (1, 2) else MITTE)
            for i, a in enumerate(self.aufgaben):
                x, b = sp[4 + i]
                p = e.punkte.get(a.id)
                if p is None and e.unvollstaendig and self.o.luecken_hervorheben:
                    s.flaeche(x, y, b, ZEILE, FARBE_LUECKE)
                s.text(x, y, b, ZEILE, zahl_text(p), MITTE)
            s.schrift(8.5, fett=True)
            s.text(sp[4 + na][0], y, sp[4 + na][1], ZEILE, zahl_text(e.summe), MITTE)
            if e.note:
                text = e.note.kurz if self.o.mit_tendenz else str(e.note.stufe)
                s.text(sp[5 + na][0], y, sp[5 + na][1], ZEILE, text + ("*" if e.note_manuell else ""), MITTE)
            vermerk = []
            if e.status:
                vermerk.append(STATUS[e.status])
            if not e.erwartet:
                vermerk.append("nicht in der Gruppe")
            if e.note_manuell:
                vermerk.append("Note festgesetzt")
            if e.unvollstaendig:
                vermerk.append("unvollständig")
            s.schrift(7.5)
            s.text(sp[6 + na][0] + 1, y, sp[6 + na][1] - 2, ZEILE, ", ".join(vermerk), LINKS)
            y += ZEILE

        if letzte and self.o.durchschnitt:
            s.stift("#333333")
            s.schrift(7.5, kursiv=True)
            s.text(sp[1][0] + 1, y, sp[1][1] + sp[2][1], ZEILE, "Durchschnitt je Aufgabe", LINKS)
            for i, st in enumerate(self.statistik):
                x, b = sp[4 + i]
                s.text(x, y, b, ZEILE, f"{st.anteil:.0f} %" if st.anteil is not None else "", MITTE)
            summen = [e.summe for e in self.zeilen if e.summe is not None]
            if summen:
                s.text(sp[4 + na][0], y, sp[4 + na][1], ZEILE, zahl_text(round(sum(summen) / len(summen), 1)), MITTE)
            y += ZEILE

        # Gitter
        s.stift("#555555", 0.15)
        s.kasten(RAND, y0, BREITE, y - y0)
        for x, _ in sp[1:]:
            s.linie(x, y0, x, y)
        s.stift("#999999", 0.1)
        for i in range(len(zeilen) + 1):
            s.linie(RAND, y0 + TABELLENKOPF + i * ZEILE, RAND + BREITE, y0 + TABELLENKOPF + i * ZEILE)
        s.stift("#000000", 0.3)
        for x in (sp[4][0], sp[4 + na][0]):
            s.linie(x, y0, x, y)
        return y

    def _fuss(self, s: Seite, y: float) -> None:
        # Notenspiegel links (wie ODS: Anzahl je ganzer Note, Schnitt, unter 4)
        s.stift("#000000", 0.15)
        b = 13.0
        x0 = RAND
        s.schrift(9, fett=True)
        s.text(x0, y, 60, 5, "Notenspiegel", LINKS)
        y1 = y + 6
        s.flaeche(x0, y1, b * 7, 6, FARBE_KOPF)
        s.schrift(8.5, fett=True)
        s.text(x0, y1, b, 6, "Note", MITTE)
        for i in range(1, 7):
            s.text(x0 + i * b, y1, b, 6, str(i), MITTE)
        s.schrift(8.5)
        s.text(x0, y1 + 6, b, 6, "Anzahl", MITTE)
        for i in range(1, 7):
            s.text(x0 + i * b, y1 + 6, b, 6, str(self.spiegel.anzahl[i]), MITTE)
        s.kasten(x0, y1, b * 7, 12)
        s.linie(x0, y1 + 6, x0 + 7 * b, y1 + 6)
        for i in range(1, 7):
            s.linie(x0 + i * b, y1, x0 + i * b, y1 + 12)
        s.schrift(8.5)
        if self.spiegel.gesamt:
            text = (f"Schnitt: {self.spiegel.schnitt:.2f}   (mit Tendenz {self.spiegel.schnitt_mit_tendenz:.2f})   "
                    f"Unter 4: {self.spiegel.anteil_unter_4:.0f} %   ·   {self.spiegel.gesamt} Noten").replace(".", ",")
        else:
            text = "Noch keine Noten."
        s.text(x0, y1 + 14, b * 7 + 60, 5, text, LINKS)

        # Notenschlüssel rechts
        x1 = RAND + b * 7 + 14
        breite = BREITE - (x1 - RAND)
        s.schrift(9, fett=True)
        s.text(x1, y, breite, 5, "Notenschlüssel", LINKS)
        bereiche = list(reversed(self.arbeit.schluessel.bereiche(self.hoechst))) if self.hoechst else []
        spalten = max(1, math.ceil(len(bereiche) / 4))
        sb = min(36.0, breite / spalten)
        s.schrift(8)
        for i, (von, bis, note) in enumerate(bereiche):
            spalte, zeile = divmod(i, 4)
            punkte = zahl_text(von) if von == bis else f"{zahl_text(von)}–{zahl_text(bis)}"
            s.text(x1 + spalte * sb, y + 6 + zeile * 4.5, sb, 4.5, f"{note.kurz:<3}  {punkte} P.", LINKS)
