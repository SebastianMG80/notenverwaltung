"""Notenübersicht einer Lerngruppe (A4 quer): schriftlich, mündlich, Vorschlag und festgesetzte Note je Abschnitt
in der Reihenfolge der Abgabe (Q1 – 1. Hj. – Q3 – 2. Hj.) sowie Notenspiegel je Abschnitt.

Passt nicht alles auf die Seite, fallen zuerst die Teilnoten der Quartale weg, dann die der Halbjahre,
dann werden Vorschläge ohne Zahlenwert gezeigt – die festgesetzten Noten bleiben immer.
"""

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
FUSS = 36.0
BEMERKUNG_MIN = 25.0


def _z(wert: float | None) -> str:
    return "" if wert is None else f"{wert:.2f}".replace(".", ",")


@dataclass
class UebersichtOptionen:
    halbjahr: int | None = None          # 1, 2 oder None = ganzes Jahr
    vorschlaege: bool = True
    leere_ausblenden: bool = False
    zebra: bool = True
    notenspiegel: bool = True
    quartale: bool = True                # Quartalsnoten (1. und 3. Quartal)


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
        self.spalten = self._passende_spalten()
        zeitraum = {1: "1. Halbjahr", 2: "2. Halbjahr", None: "ganzes Schuljahr"}[self.o.halbjahr]
        self.titel = f"Notenübersicht {self.gruppe.bezeichnung} – {zeitraum}"
        pro_seite = int((HOEHE - KOPF - TKOPF) // ZEILE)
        self._seiten = [zeilen[i:i + pro_seite] for i in range(0, max(1, len(zeilen)), pro_seite)] or [[]]
        rest = KOPF + TKOPF + len(self._seiten[-1]) * ZEILE
        self._fuss_extra = self.o.notenspiegel and rest + FUSS > HOEHE

    def _passende_spalten(self) -> list[tuple[str, str, float]]:
        """Die ausführlichste Spaltenauswahl, die auf die Seite passt."""
        stufen = [dict(q_teile=True, hj_teile=True, kompakt=False), dict(q_teile=False, hj_teile=True, kompakt=False),
                  dict(q_teile=False, hj_teile=False, kompakt=False), dict(q_teile=False, hj_teile=False, kompakt=True),
                  dict(q_teile=False, hj_teile=False, kompakt=True, name=40.0)]
        for st in stufen:
            s = self._spalten(**st)
            if sum(b for _, _, b in s[:-1]) <= BREITE - BEMERKUNG_MIN:
                break
        self.stufe = st
        return s

    def _spalten(self, q_teile: bool = True, hj_teile: bool = True, kompakt: bool = False,
                 name: float = 50.0) -> list[tuple[str, str, float]]:
        s = [("Nr.", "nr", 9), ("Name", "name", name), ("Kl.", "kl", 11)]
        halbjahre = (1, 2) if self.o.halbjahr is None else (self.o.halbjahr,)
        vb = 15 if kompakt else 24
        v = self.o.vorschlaege
        for h in halbjahre:
            p = f"{h}. Hj. "
            if self.o.quartale:
                q = 2 * h - 1
                if q_teile:
                    s += [(f"Q{q} schriftl.", f"sq{q}", 20), (f"Q{q} mündl.", f"mq{q}", 20)]
                if v:
                    s.append((f"Q{q} Vorschl.", f"v:q{q}", vb))
                s.append((f"Q{q} Note", f"f:q{q}", 18))
            if h == 2 and self.gw.zp10:
                if hj_teile:
                    s += [(p + "schriftl.", "s1+2", 20), (p + "mündl.", "m1+2", 20)]
                if v:
                    s.append(("Vornote Vorschl.", "v:vornote", vb if kompakt else vb - 2))
                s += [("Vornote", "f:vornote", 18), ("ZP10", "f:zp10", 14)]
                if v:
                    s.append(("Endnote Vorschl.", "v:hj2", vb if kompakt else vb - 2))
                s.append(("Endnote", "f:hj2", 18))
                continue
            if hj_teile:
                s += [(p + "schriftl.", f"s{h}", 20), (p + "mündl.", f"m{h}", 20)]
            if v:
                s.append((p + ("Vorschl." if kompakt else "Vorschlag"), f"v:hj{h}", vb))
            s.append((p + "Zeugnis", f"f:hj{h}", 20))
        rest = BREITE - sum(b for _, _, b in s)
        s.append(("Bemerkung", "bem", max(BEMERKUNG_MIN, rest)))
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
        if inhalt in ("sq1", "sq3", "mq1", "mq3"):
            t = (z.quartal_s if inhalt[0] == "s" else z.quartal_m).get(int(inhalt[2]))
            return (_z(t.wert) if t else ""), False
        if inhalt in ("s1+2", "m1+2"):
            teile = z.schriftlich if inhalt[0] == "s" else z.muendlich
            werte = [t.wert for t in teile.values() if t.wert is not None]
            return _z(sum(werte) / len(werte)) if werte else "", False
        if inhalt.startswith("v:"):
            v = z.vorschlag.get(inhalt[2:])
            if not (v and v.note):
                return "", False
            return (v.note.kurz if self.stufe.get("kompakt") else f"{v.note.kurz} ({_z(v.wert)})"), False
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
        elif self.o.halbjahr != 1 and self.gw.anteil_hj1 > 0:
            info.append(f"1. Hj. zählt {self.gw.anteil_hj1:g} % zum 2. Hj.")
        if g.sek2:
            info.insert(1, f"{g.kursart or 'Kurs'} · Punkte 0–15")
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
            text = kopf.replace(" Hj. ", " Hj.\n").replace(" Vorschl.", "\nVorschl.").replace("\n\n", "\n")
            if text.startswith("Q") and " " in text and "\n" not in text:
                text = text.replace(" ", "\n", 1)
            s.text(x + 1, y, b - 2, TKOPF, text, LINKS if inhalt in ("name", "bem") else MITTE, umbruch=True)
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
        """Notenspiegel der festgesetzten Noten je Abschnitt (Quartalsnoten nach Stufe gezählt)."""
        arten = []
        if self.o.halbjahr in (None, 1):
            arten += ([("q1", "1. Quartal")] if self.o.quartale else []) + [("hj1", "1. Halbjahr")]
        if self.o.halbjahr in (None, 2):
            arten += ([("q3", "3. Quartal")] if self.o.quartale else []) + [
                ("hj2", "Endnote" if self.gw.zp10 else "2. Halbjahr (Jahresnote)")]
        bloecke: list[tuple[str, list[Note]]] = [(t, [z.fest[a] for z in self.zeilen if a in z.fest]) for a, t in arten]
        abstand = 8.0
        breite = min(7 * 12.0, (BREITE - abstand * (len(bloecke) - 1)) / len(bloecke))
        b = breite / 7
        sek2 = self.gruppe.sek2
        koepfe = ["15–13", "12–10", "9–7", "6–4", "3–1", "0"] if sek2 else [str(k) for k in range(1, 7)]
        for i, (titel, noten) in enumerate(bloecke):
            x0 = RAND + i * (breite + abstand)
            sp = Notenspiegel.aus(noten, sek2=sek2)
            stufen = Notenspiegel.aus(noten, sek2=False).anzahl   # Sek II: nach Notenstufen gebündelt
            s.stift("#000000", 0.15)
            s.schrift(9, fett=True)
            s.text(x0, y, breite + abstand, 5, f"Notenspiegel {titel}", LINKS)
            y1 = y + 6
            s.flaeche(x0, y1, breite, 6, "#e2e2e2")
            s.schrift(8.5, fett=True)
            s.text(x0, y1, b, 6, "P." if sek2 else "Note", MITTE)
            s.schrift(7 if sek2 else 8.5, fett=True)
            for k in range(1, 7):
                s.text(x0 + k * b, y1, b, 6, koepfe[k - 1], MITTE)
            s.schrift(8.5)
            s.text(x0, y1 + 6, b, 6, "Anz.", MITTE)
            for k in range(1, 7):
                s.text(x0 + k * b, y1 + 6, b, 6, str(stufen[k]), MITTE)
            s.kasten(x0, y1, breite, 12)
            s.linie(x0, y1 + 6, x0 + breite, y1 + 6)
            for k in range(1, 7):
                s.linie(x0 + k * b, y1, x0 + k * b, y1 + 12)
            s.schrift(8)
            if sp.gesamt:
                s.text(x0, y1 + 13, breite + abstand, 4.5,
                       f"Schnitt {_z(sp.schnitt)}{' P.' if sek2 else ''} · {sp.text_unter}: {sp.anteil_unter_4:.0f} %",
                       LINKS)
                s.text(x0, y1 + 17.5, breite + abstand, 4.5, f"{sp.gesamt} Noten", LINKS)
            else:
                s.text(x0, y1 + 13, breite + abstand, 4.5, "Noch keine Noten festgesetzt.", LINKS)
