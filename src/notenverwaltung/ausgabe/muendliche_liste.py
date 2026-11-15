"""Liste der mündlichen Noten einer Lerngruppe: eine Spalte je Zeitraum, Halbjahresmittel, Bemerkungen.

Hochformat, solange die Spalten lesbar breit bleiben, sonst Querformat. Als „Liste zum Eintragen“ ohne Noten,
mit höheren Zeilen zum Ausfüllen von Hand.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.muendlich import Muendlich, Zeitraum
from notenverwaltung.modell.stammdaten import Mitglied

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
OBEN_LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter
RAND = 12.0
KOPF = 17.0
TKOPF = 10.0
FEST_BREITE = 9 + 52 + 11      # Nr., Name, Kl.
SPALTE_MAX = 24.0
SPALTE_HOCH_MIN = 16.0         # schmaler → Querformat
SPALTE_MIN = 10.0
NOTIZEN_MIN = 20.0
BEM_ZEILE = 4.5
BEM_TITEL = 8.0


def _z(wert: float | None) -> str:
    return "" if wert is None else f"{wert:.2f}".replace(".", ",")


@dataclass
class MuendlichOptionen:
    halbjahr: int | None = None        # 1, 2 oder None = ganzes Jahr
    tendenzen: bool = True             # „2+“ statt „2“
    mittel: bool = True                # Ø je Halbjahr
    bemerkungen: bool = False          # Bemerkungen unter der Tabelle
    leerliste: bool = False            # ohne Noten, zum Eintragen von Hand
    leere_ausblenden: bool = False     # Personen ohne Note weglassen
    ausgetretene: bool = False         # auch vor dem Zeitraum Ausgetretene
    zebra: bool = True


@dataclass
class _Seite:
    zeilen: list[Mitglied]
    bemerkungen: list[tuple[str, list[str]]]
    bem_titel: bool = False
    bem_y: float = 0.0


class MuendlicheListe(Ausgabe):
    def __init__(self, mu: Muendlich, lerngruppe_id: int, optionen: MuendlichOptionen | None = None) -> None:
        self.mu = mu
        self.o = optionen or MuendlichOptionen()
        self.gruppe = mu.sd.lerngruppe(lerngruppe_id)
        self.jahr = mu.sd.schuljahr(self.gruppe.schuljahr_id)
        o = self.o
        self.halbjahre = (1, 2) if o.halbjahr is None else (o.halbjahr,)
        self.zeitraeume: list[Zeitraum] = [z for z in mu.zeitraeume(lerngruppe_id)
                                           if self.jahr.halbjahr(z.beginn) in self.halbjahre]
        self.noten = {} if o.leerliste else mu.noten(lerngruppe_id)
        self.mit_mittel = o.mittel and not o.leerliste

        mitglieder = [m for m in mu.sd.mitglieder(lerngruppe_id)
                      if o.ausgetretene or (any(z.erfasst(m) for z in self.zeitraeume)
                                            and (m.ende is None or m.ende >= self.jahr.beginn))]
        if o.leere_ausblenden and not o.leerliste:
            mitglieder = [m for m in mitglieder if any((z.id, m.schueler.id) in self.noten for z in self.zeitraeume)]
        self.mitglieder = mitglieder

        # Spalten und Format
        anzahl = len(self.zeitraeume) + (len(self.halbjahre) if self.mit_mittel else 0)
        self.quer = (210 - 2 * RAND - FEST_BREITE) / max(1, anzahl) < SPALTE_HOCH_MIN
        self.breite = (297 if self.quer else 210) - 2 * RAND
        self.hoehe = (210 if self.quer else 297) - 2 * RAND
        self.spalte = max(SPALTE_MIN, min(SPALTE_MAX, (self.breite - FEST_BREITE) / max(1, anzahl)))
        rest = self.breite - FEST_BREITE - anzahl * self.spalte
        self.notizen = rest if rest >= NOTIZEN_MIN else 0.0
        self.zeile = 8.0 if o.leerliste else 6.0

        zeitraum = {1: "1. Halbjahr", 2: "2. Halbjahr", None: "ganzes Schuljahr"}[o.halbjahr]
        art = "Liste zum Eintragen" if o.leerliste else "Mündliche Noten"
        self.titel = f"{art} {self.gruppe.bezeichnung} – {zeitraum}"
        self._seiten = self._umbrechen()

    # ---- Aufteilung auf Seiten ----------------------------------------------------------------
    def _bemerkungen(self) -> list[tuple[str, list[str]]]:
        if not self.o.bemerkungen or self.o.leerliste:
            return []
        zeichen = int((self.breite - 4) / 1.55)   # vorsichtige Schätzung für 8 pt
        liste = []
        for m in self.mitglieder:
            for z in self.zeitraeume:
                eintrag = self.noten.get((z.id, m.schueler.id))
                if eintrag and eintrag[1].strip():
                    kopf = f"{m.schueler.nachname}, {m.schueler.vorname} – {z.bezeichnung} ({self._note(eintrag[0])})"
                    zeilen = [t for absatz in eintrag[1].strip().splitlines()
                              for t in (textwrap.wrap(absatz, zeichen) or [""])]
                    liste.append((kopf, zeilen))
        return liste

    def _umbrechen(self) -> list[_Seite]:
        pro_seite = max(1, int((self.hoehe - KOPF - TKOPF) // self.zeile))
        seiten = [_Seite(self.mitglieder[i:i + pro_seite], [])
                  for i in range(0, max(1, len(self.mitglieder)), pro_seite)] or [_Seite([], [])]
        bem = self._bemerkungen()
        if not bem:
            return seiten
        unten = RAND + self.hoehe
        letzte = seiten[-1]
        y = RAND + KOPF + TKOPF + len(letzte.zeilen) * self.zeile + 6
        aktuell, titel = letzte, True
        aktuell.bem_y = y
        for kopf, zeilen in bem:
            h = (len(zeilen) + 1) * BEM_ZEILE + 1.5 + (BEM_TITEL if titel else 0)
            if y + h > unten and (aktuell.bemerkungen or aktuell is letzte):
                aktuell = _Seite([], [], bem_y=RAND + KOPF)
                seiten.append(aktuell)
                y = aktuell.bem_y
            if titel:
                aktuell.bem_titel = True
                titel = False
            aktuell.bemerkungen.append((kopf, zeilen))
            y += h
        return seiten

    def seitenzahl(self) -> int:
        return len(self._seiten)

    # ---- Zeichnen -----------------------------------------------------------------------------
    def _note(self, note) -> str:
        return note.kurz if self.o.tendenzen or self.gruppe.sek2 else str(note.stufe)

    def _mittel(self, m: Mitglied, halbjahr: int) -> float | None:
        werte = [self.noten[(z.id, m.schueler.id)][0].wert for z in self.zeitraeume
                 if self.jahr.halbjahr(z.beginn) == halbjahr and (z.id, m.schueler.id) in self.noten]
        return sum(werte) / len(werte) if werte else None

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        seite = self._seiten[nummer]
        s.stift("#000000")
        s.schrift(14, fett=True)
        s.text(RAND, RAND, self.breite * 0.75, 7, self.titel, LINKS)
        s.schrift(9)
        s.stift("#333333")
        info = [self.gruppe.fach, f"Schuljahr {self.jahr.bezeichnung}"]
        if self.gruppe.niveau:
            info.append(f"{self.gruppe.niveau}-Kurs")
        if self.gruppe.kursart:
            info.append(self.gruppe.kursart)
        if not self.o.leerliste:
            info.append("Punkte 0–15" if self.gruppe.sek2 else "Noten mit Tendenz" if self.o.tendenzen else "ganze Noten")
        s.text(RAND, RAND + 7.5, self.breite * 0.6, 5, " · ".join(info), LINKS)
        s.text(RAND + self.breite * 0.6, RAND, self.breite * 0.4, 7, f"Seite {nummer + 1} von {self.seitenzahl()}",
               RECHTS)
        if self.kopfzeile:
            s.text(RAND + self.breite * 0.4, RAND + 7.5, self.breite * 0.6, 5, self.kopfzeile, RECHTS)
        if seite.zeilen or not seite.bemerkungen:
            self._tabelle(s, RAND + KOPF, seite.zeilen)
        if seite.bemerkungen:
            self._zeichne_bemerkungen(s, seite)

    def _spalten(self) -> list[tuple[str, str, float, object]]:
        """(Kopf, Art, Breite, Bezug)."""
        sp: list[tuple[str, str, float, object]] = [("Nr.", "nr", 9, None), ("Name", "name", 52, None),
                                                    ("Kl.", "kl", 11, None)]
        for h in self.halbjahre:
            for z in self.zeitraeume:
                if self.jahr.halbjahr(z.beginn) == h:
                    sp.append((f"{z.bezeichnung}\n{z.beginn:%d.%m.}–{z.ende:%d.%m.}", "z", self.spalte, z))
            if self.mit_mittel:
                sp.append((f"Ø {h}. Hj.", "ø", self.spalte, h))
        if self.notizen:
            sp.append(("Notizen", "notiz", self.notizen, None))
        return sp

    def _tabelle(self, s: Seite, y: float, zeilen: list[Mitglied]) -> None:
        spalten = self._spalten()
        zh = self.zeile
        s.flaeche(RAND, y, self.breite, TKOPF, "#e2e2e2")
        s.stift("#000000")
        x = RAND
        for kopf, art, b, _ in spalten:
            s.schrift(7 if art == "z" else 7.5, fett=True)
            s.text(x + 1, y, b - 2, TKOPF, kopf, LINKS if art in ("name", "notiz") else MITTE, umbruch=True)
            x += b
        y0 = y
        y += TKOPF
        for r, m in enumerate(zeilen):
            if self.o.zebra and r % 2:
                s.flaeche(RAND, y, self.breite, zh, "#f2f2f2")
            x = RAND
            for _, art, b, bezug in spalten:
                text, fett, grau = "", False, False
                if art == "nr":
                    text = str(m.nummer)
                elif art == "name":
                    text = f"{m.schueler.nachname}, {m.schueler.vorname}"
                elif art == "kl":
                    text = m.klasse
                elif art == "z":
                    if not bezug.erfasst(m):
                        grau, text = True, "—"
                    else:
                        eintrag = self.noten.get((bezug.id, m.schueler.id))
                        if eintrag:
                            text = self._note(eintrag[0]) + ("*" if self.o.bemerkungen and eintrag[1].strip() else "")
                elif art == "ø":
                    text, fett = _z(self._mittel(m, bezug)), True
                    s.flaeche(x, y, b, zh, "#e9eef5" if not (self.o.zebra and r % 2) else "#dfe6ef")
                if grau:
                    s.flaeche(x, y, b, zh, "#d9d9d9")
                    s.stift("#777777")
                else:
                    s.stift("#000000")
                s.schrift(8.5, fett=fett)
                s.text(x + 1, y, b - 2, zh, text, LINKS if art == "name" else MITTE)
                x += b
            y += zh
        s.stift("#555555", 0.15)
        s.kasten(RAND, y0, self.breite, y - y0)
        x = RAND
        for _, _, b, _ in spalten[:-1]:
            x += b
            s.linie(x, y0, x, y)
        s.stift("#aaaaaa", 0.1)
        for i in range(1, len(zeilen)):
            s.linie(RAND, y0 + TKOPF + i * zh, RAND + self.breite, y0 + TKOPF + i * zh)
        if self.o.bemerkungen and not self.o.leerliste and zeilen:
            s.stift("#555555")
            s.schrift(7.5)
            s.text(RAND, y + 0.5, self.breite, 4.5, "* Bemerkung vorhanden (siehe unten)", LINKS)

    def _zeichne_bemerkungen(self, s: Seite, seite: _Seite) -> None:
        y = seite.bem_y
        if seite.bem_titel:
            s.stift("#000000")
            s.schrift(10, fett=True)
            s.text(RAND, y, self.breite, 6, "Bemerkungen", LINKS)
            y += BEM_TITEL
        for kopf, zeilen in seite.bemerkungen:
            s.stift("#000000")
            s.schrift(8.5, fett=True)
            s.text(RAND, y, self.breite, BEM_ZEILE, kopf, LINKS)
            y += BEM_ZEILE
            s.schrift(8)
            s.stift("#222222")
            for t in zeilen:
                s.text(RAND + 4, y, self.breite - 4, BEM_ZEILE, t, LINKS)
                y += BEM_ZEILE
            y += 1.5
