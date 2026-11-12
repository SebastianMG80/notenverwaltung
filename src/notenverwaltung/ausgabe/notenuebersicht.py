"""Notenübersicht einer Lerngruppe (A4 quer): schriftlich, mündlich, Vorschlag und Zeugnisnote je Halbjahr
sowie Notenspiegel je Halbjahr und fürs ganze Jahr."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt

from notenverwaltung.ausgabe.seite import Ausgabe, Seite
from notenverwaltung.modell.noten import Note, Notenspiegel
from notenverwaltung.modell.zeugnis import Zeile, Zeugnis

LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RECHTS = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
MITTE = Qt.AlignmentFlag.AlignCenter
RAND = 12.0
BREITE = 297 - 2 * RAND
HOEHE = 210 - 2 * RAND
ZEILE = 6.0
KOPF = 17.0
TKOPF = 10.0
FUSS = 34.0


def _z(wert: float | None) -> str:
    return "" if wert is None else f"{wert:.2f}".replace(".", ",")


@dataclass
class UebersichtOptionen:
    halbjahr: int | None = None          # 1, 2 oder None = ganzes Jahr
    vorschlaege: bool = True
    leere_ausblenden: bool = False
    zebra: bool = True
    notenspiegel: bool = True


class Notenuebersicht(Ausgabe):
    quer = True

    def __init__(self, zg: Zeugnis, lerngruppe_id: int, optionen: UebersichtOptionen | None = None) -> None:
        self.zg = zg
        self.o = optionen or UebersichtOptionen()
        self.gruppe = zg.sd.lerngruppe(lerngruppe_id)
        self.jahr = zg.sd.schuljahr(self.gruppe.schuljahr_id)
        self.gw = zg.gewichtung(self.gruppe)
        zeilen = zg.zeilen(lerngruppe_id)
        if self.o.leere_ausblenden:
            zeilen = [z for z in zeilen if z.fest or any(v.wert is not None for v in z.vorschlag.values())]
        self.zeilen: list[Zeile] = zeilen
        self.spalten = self._spalten()
        zeitraum = {1: "1. Halbjahr", 2: "2. Halbjahr", None: "ganzes Schuljahr"}[self.o.halbjahr]
        self.titel = f"Notenübersicht {self.gruppe.bezeichnung} – {zeitraum}"
        pro_seite = int((HOEHE - KOPF - TKOPF) // ZEILE)
        self._seiten = [zeilen[i:i + pro_seite] for i in range(0, max(1, len(zeilen)), pro_seite)] or [[]]
        rest = KOPF + TKOPF + len(self._seiten[-1]) * ZEILE
        self._fuss_extra = self.o.notenspiegel and rest + FUSS > HOEHE

    def _spalten(self) -> list[tuple[str, str, float]]:
        s = [("Nr.", "nr", 9), ("Name", "name", 50), ("Kl.", "kl", 11)]
        halbjahre = (1, 2) if self.o.halbjahr is None else (self.o.halbjahr,)
        for h in halbjahre:
            p = f"{h}. Hj. "
            if h == 2 and self.gw.zp10:
                s += [(p + "schriftl.", "s1+2", 20), (p + "mündl.", "m1+2", 20)]
                if self.o.vorschlaege:
                    s.append(("Vornote Vorschl.", "v:vornote", 22))
                s += [("Vornote", "f:vornote", 18), ("ZP10", "f:zp10", 14)]
                if self.o.vorschlaege:
                    s.append(("Endnote Vorschl.", "v:hj2", 22))
                s.append(("Endnote", "f:hj2", 18))
                continue
            s += [(p + "schriftl.", f"s{h}", 20), (p + "mündl.", f"m{h}", 20)]
            if self.o.vorschlaege:
                s.append((p + "Vorschlag", f"v:hj{h}", 24))
            s.append((p + "Zeugnis", f"f:hj{h}", 20))
        rest = BREITE - sum(b for _, _, b in s)
        s.append(("Bemerkung", "bem", max(28.0, rest)))
        return s

    def seitenzahl(self) -> int:
        return len(self._seiten) + (1 if self._fuss_extra else 0)

    def _wert(self, z: Zeile, inhalt: str) -> tuple[str, bool]:
        """(Text, fett)."""
        m = z.mitglied
        if inhalt == "nr":
            return str(m.nummer), False
        if inhalt == "name":
            return f"{m.schueler.nachname}, {m.schueler.vorname}", False
        if inhalt == "kl":
            return m.klasse, False
        if inhalt in ("s1", "s2", "m1", "m2"):
            t = (z.schriftlich if inhalt[0] == "s" else z.muendlich)[int(inhalt[1])]
            return _z(t.wert), False
        if inhalt in ("s1+2", "m1+2"):
            teile = z.schriftlich if inhalt[0] == "s" else z.muendlich
            werte = [t.wert for t in teile.values() if t.wert is not None]
            return _z(sum(werte) / len(werte)) if werte else "", False
        if inhalt.startswith("v:"):
            v = z.vorschlag.get(inhalt[2:])
            return (f"{v.note.kurz} ({_z(v.wert)})" if v and v.note else ""), False
        if inhalt.startswith("f:"):
            n = z.fest.get(inhalt[2:])
            return (n.kurz if n else ""), True
        if inhalt == "bem":
            return m.status if (m.ende or m.beginn) else "", False
        return "", False

    def zeichne_seite(self, s: Seite, nummer: int) -> None:
        s.stift("#000000")
        s.schrift(14, fett=True)
        s.text(RAND, RAND, BREITE * 0.75, 7, self.titel, LINKS)
        s.schrift(9)
        s.stift("#333333")
        g = self.gruppe
        info = [g.fach, f"Schuljahr {self.jahr.bezeichnung}",
                f"schriftlich {self.gw.anteil_schriftlich:g} % / mündlich {100 - self.gw.anteil_schriftlich:g} %"]
        if self.gw.zp10:
            info.append("ZP10-Fach")
        elif self.o.halbjahr != 1:
            info.append(f"1. Hj. zählt {self.gw.anteil_hj1:g} % zum 2. Hj.")
        s.text(RAND, RAND + 7.5, BREITE * 0.75, 5, " · ".join(info), LINKS)
        s.text(RAND + BREITE * 0.6, RAND, BREITE * 0.4, 7, f"Seite {nummer + 1} von {self.seitenzahl()}", RECHTS)
        if self.kopfzeile:
            s.text(RAND + BREITE * 0.5, RAND + 7.5, BREITE * 0.5, 5, self.kopfzeile, RECHTS)
        y = RAND + KOPF
        if nummer < len(self._seiten):
            y = self._tabelle(s, y, self._seiten[nummer])
            if self.o.notenspiegel and nummer == len(self._seiten) - 1 and not self._fuss_extra:
                self._spiegel(s, y + 6)
        else:
            self._spiegel(s, y)

    def _tabelle(self, s: Seite, y: float, zeilen: list[Zeile]) -> float:
        x0 = RAND
        s.flaeche(RAND, y, BREITE, TKOPF, "#e2e2e2")
        s.stift("#000000")
        x = x0
        for kopf, inhalt, b in self.spalten:
            s.schrift(7.5, fett=True)
            s.text(x + 1, y, b - 2, TKOPF, kopf.replace(" Hj. ", " Hj.\n").replace(" Vorschl.", "\nVorschl."),
                   LINKS if inhalt in ("name", "bem") else MITTE, umbruch=True)
            x += b
        y0 = y
        y += TKOPF
        for r, z in enumerate(zeilen):
            if self.o.zebra and r % 2:
                s.flaeche(RAND, y, BREITE, ZEILE, "#f2f2f2")
            x = x0
            for _, inhalt, b in self.spalten:
                text, fett = self._wert(z, inhalt)
                s.schrift(8.5 if inhalt != "bem" else 7.5, fett=fett)
                if inhalt.startswith("f:"):
                    s.flaeche(x, y, b, ZEILE, "#e9eef5" if not (self.o.zebra and r % 2) else "#dfe6ef")
                s.text(x + 1, y, b - 2, ZEILE, text, LINKS if inhalt in ("name", "bem") else MITTE)
                x += b
            y += ZEILE
        s.stift("#555555", 0.15)
        s.kasten(RAND, y0, BREITE, y - y0)
        x = x0
        for _, _, b in self.spalten[:-1]:
            x += b
            s.linie(x, y0, x, y)
        s.stift("#aaaaaa", 0.1)
        for i in range(1, len(zeilen) + 1):
            s.linie(RAND, y0 + TKOPF + i * ZEILE, RAND + BREITE, y0 + TKOPF + i * ZEILE)
        return y

    def _spiegel(self, s: Seite, y: float) -> None:
        """Notenspiegel der festgesetzten Zeugnisnoten (ganze Noten) je Halbjahr bzw. fürs Jahr."""
        bloecke: list[tuple[str, list[Note]]] = []
        if self.o.halbjahr in (None, 1):
            bloecke.append(("1. Halbjahr", [z.fest["hj1"] for z in self.zeilen if "hj1" in z.fest]))
        if self.o.halbjahr in (None, 2):
            bloecke.append(("Endnote" if self.gw.zp10 else "2. Halbjahr (Jahresnote)",
                            [z.fest["hj2"] for z in self.zeilen if "hj2" in z.fest]))
        b = 12.0
        for i, (titel, noten) in enumerate(bloecke):
            x0 = RAND + i * (b * 7 + 40)
            sp = Notenspiegel.aus(noten)
            s.stift("#000000", 0.15)
            s.schrift(9, fett=True)
            s.text(x0, y, b * 7 + 30, 5, f"Notenspiegel {titel}", LINKS)
            y1 = y + 6
            s.flaeche(x0, y1, b * 7, 6, "#e2e2e2")
            s.schrift(8.5, fett=True)
            s.text(x0, y1, b, 6, "Note", MITTE)
            for k in range(1, 7):
                s.text(x0 + k * b, y1, b, 6, str(k), MITTE)
            s.schrift(8.5)
            s.text(x0, y1 + 6, b, 6, "Anzahl", MITTE)
            for k in range(1, 7):
                s.text(x0 + k * b, y1 + 6, b, 6, str(sp.anzahl[k]), MITTE)
            s.kasten(x0, y1, b * 7, 12)
            s.linie(x0, y1 + 6, x0 + 7 * b, y1 + 6)
            for k in range(1, 7):
                s.linie(x0 + k * b, y1, x0 + k * b, y1 + 12)
            text = (f"Schnitt {_z(sp.schnitt)} · unter 4: {sp.anteil_unter_4:.0f} % · {sp.gesamt} Noten"
                    if sp.gesamt else "Noch keine Zeugnisnoten festgesetzt.")
            s.text(x0, y1 + 14, b * 7 + 40, 5, text, LINKS)

