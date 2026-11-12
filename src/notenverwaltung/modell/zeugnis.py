"""Notenberechnung und Notenvorschläge für Halbjahres- und Zeugnisnoten.

Regeln (Lastenheft):
- Halbjahresnote = Anteil schriftlich × Schnitt der Arbeiten des Halbjahres
                   + (1 − Anteil) × Schnitt der mündlichen Noten des Halbjahres.
  Standard: 50 % in schriftlichen Fächern, 0 % in mündlichen; je Lerngruppe einstellbar.
- 2. Halbjahr: Die Note des 1. Halbjahres geht mit einem einstellbaren Anteil ein (Standard 10 %).
- Deutsch, Englisch, Mathematik in Jahrgang 10 (ZP10-Fächer): Im 2. Halbjahr gibt es eine Ganzjahresnote
  (Vornote) aus allen Leistungen des Schuljahres; die Zeugnisnote ist 50 % Vornote + 50 % ZP10.
- Das Programm schlägt vor (nächstgelegene Note mit Tendenz), die Lehrkraft setzt fest.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import ALLE_NOTEN, Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Stammdaten

ZP10_FAECHER = {"deutsch", "englisch", "mathematik", "d", "e", "m"}
ARTEN = ("hj1", "hj2", "vornote", "zp10")


class ZeugnisFehler(ValueError):
    pass


def naechste_note(wert: float) -> Note:
    """Nächstgelegene Note mit Tendenz; bei Gleichstand die bessere (2,15 → 2; 2,5 → 2-)."""
    return min(ALLE_NOTEN, key=lambda n: (round(abs(n.wert - wert), 6), n.wert))


def naechste_ganze_note(wert: float) -> Note:
    """Ganze Note für das Zeugnis (ohne Tendenz); genau ,5 → die bessere (2,5 → 2)."""
    return Note.aus(max(1, min(6, int(wert + 0.5 - 1e-9))))


def _z(wert: float | None) -> str:
    return "–" if wert is None else f"{wert:.2f}".replace(".", ",")


@dataclass(frozen=True)
class Gewichtung:
    anteil_schriftlich: float     # 0…100
    anteil_hj1: float             # 0…100, Anteil der 1.-Halbjahres-Note an der des 2. Halbjahres
    zp10: bool
    schriftlich_automatisch: bool
    zp10_automatisch: bool


@dataclass(frozen=True)
class Teilnote:
    wert: float | None
    anzahl: int
    herleitung: str


@dataclass(frozen=True)
class Vorschlag:
    wert: float | None
    herleitung: list[str] = field(default_factory=list)

    @property
    def note(self) -> Note | None:
        return naechste_note(self.wert) if self.wert is not None else None


@dataclass(frozen=True)
class Zeile:
    mitglied: Mitglied
    schriftlich: dict[int, Teilnote]        # Halbjahr → Teilnote
    muendlich: dict[int, Teilnote]
    vorschlag: dict[str, Vorschlag]         # "hj1", "hj2" bzw. bei ZP10 "vornote" und "hj2" (Endnote)
    fest: dict[str, Note]                   # festgesetzt: "hj1", "hj2", "vornote", "zp10"


class Zeugnis:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung
        self.sd = Stammdaten(verbindung)
        self.ar = Arbeiten(verbindung)
        self.mu = Muendlich(verbindung)

    # ---- Gewichtung ----------------------------------------------------------------------------
    def gewichtung(self, g: Lerngruppe) -> Gewichtung:
        z = self.v.execute("SELECT anteil_schriftlich, anteil_hj1, zp10 FROM lerngruppe WHERE id = ?", (g.id,)).fetchone()
        anteil, hj1, zp10 = z
        zp10_auto = g.jahrgang == 10 and (g.fach.strip().lower() in ZP10_FAECHER
                                          or g.fach_kuerzel.strip().lower() in ZP10_FAECHER) and g.schriftlich
        return Gewichtung(
            anteil_schriftlich=(50.0 if g.schriftlich else 0.0) if anteil is None else float(anteil),
            anteil_hj1=float(hj1), zp10=zp10_auto if zp10 is None else bool(zp10),
            schriftlich_automatisch=anteil is None, zp10_automatisch=zp10 is None)

    def setze_gewichtung(self, lerngruppe_id: int, anteil_schriftlich: float | None, anteil_hj1: float,
                         zp10: bool | None) -> None:
        for wert, name in ((anteil_schriftlich, "Anteil schriftlich"), (anteil_hj1, "Anteil 1. Halbjahr")):
            if wert is not None and not 0 <= wert <= 100:
                raise ZeugnisFehler(f"{name} muss zwischen 0 und 100 % liegen.")
        with self.v:
            self.v.execute("UPDATE lerngruppe SET anteil_schriftlich = ?, anteil_hj1 = ?, zp10 = ? WHERE id = ?",
                           (anteil_schriftlich, anteil_hj1, None if zp10 is None else int(zp10), lerngruppe_id))

    # ---- Festsetzen ----------------------------------------------------------------------------
    def setze(self, lerngruppe_id: int, schueler_id: int, art: str, note: Note | None, bemerkung: str = "") -> None:
        if art not in ARTEN:
            raise ZeugnisFehler("Unbekannte Notenart.")
        with self.v:
            if note is None:
                self.v.execute("DELETE FROM zeugnisnote WHERE lerngruppe_id = ? AND schueler_id = ? AND art = ?",
                               (lerngruppe_id, schueler_id, art))
            else:
                self.v.execute("INSERT INTO zeugnisnote (lerngruppe_id, schueler_id, art, note, bemerkung) "
                               "VALUES (?, ?, ?, ?, ?) ON CONFLICT (lerngruppe_id, schueler_id, art) DO UPDATE SET "
                               "note = excluded.note, bemerkung = excluded.bemerkung",
                               (lerngruppe_id, schueler_id, art, note.kurz, bemerkung))

    def festgesetzt(self, lerngruppe_id: int) -> dict[tuple[int, str], Note]:
        return {(s, a): Note.aus_kurz(n) for s, a, n in self.v.execute(
            "SELECT schueler_id, art, note FROM zeugnisnote WHERE lerngruppe_id = ?", (lerngruppe_id,))}

    # ---- Berechnung ----------------------------------------------------------------------------
    def zeilen(self, lerngruppe_id: int) -> list[Zeile]:
        g = self.sd.lerngruppe(lerngruppe_id)
        jahr = self.sd.schuljahr(g.schuljahr_id)
        gw = self.gewichtung(g)
        a_s = gw.anteil_schriftlich / 100
        arbeiten = [a for a in self.ar.arbeiten(g.id) if a.zaehlt]
        ergebnisse = {a.id: {e.mitglied.schueler.id: e for e in self.ar.ergebnisse(a.id)} for a in arbeiten}
        zeitraeume = self.mu.zeitraeume(g.id)
        muendlich = self.mu.noten(g.id)
        fest = self.festgesetzt(g.id)

        def schriftlich(sid: int, halbjahre: tuple[int, ...]) -> Teilnote:
            werte, teile = [], []
            for a in arbeiten:
                if jahr.halbjahr(a.datum) not in halbjahre:
                    continue
                e = ergebnisse[a.id].get(sid)
                if e is None or e.note is None:
                    continue
                werte.append((e.note.wert, a.gewicht))
                teile.append(f"{a.titel}: {e.note.kurz}" + (f" (×{a.gewicht:g})" if a.gewicht != 1 else ""))
            if not werte:
                return Teilnote(None, 0, "keine Arbeiten")
            summe_g = sum(w for _, w in werte)
            return Teilnote(sum(n * w for n, w in werte) / summe_g, len(werte), ", ".join(teile))

        def muendlich_teil(sid: int, halbjahre: tuple[int, ...]) -> Teilnote:
            werte = [(z.bezeichnung, muendlich[(z.id, sid)][0]) for z in zeitraeume
                     if jahr.halbjahr(z.beginn) in halbjahre and (z.id, sid) in muendlich]
            if not werte:
                return Teilnote(None, 0, "keine mündlichen Noten")
            return Teilnote(sum(n.wert for _, n in werte) / len(werte), len(werte),
                            ", ".join(f"{b}: {n.kurz}" for b, n in werte))

        def mische(s: Teilnote, m: Teilnote) -> Vorschlag:
            if s.wert is None and m.wert is None:
                return Vorschlag(None, ["Noch keine Noten."])
            if s.wert is None or a_s == 0:
                if m.wert is None:
                    return Vorschlag(None, ["Noch keine mündlichen Noten."])
                hinweis = [] if a_s == 0 else ["Achtung: noch keine schriftlichen Noten – nur mündlich."]
                return Vorschlag(m.wert, [f"mündlich {_z(m.wert)} ({m.herleitung})"] + hinweis)
            if m.wert is None or a_s == 1:
                hinweis = [] if a_s == 1 else ["Achtung: noch keine mündlichen Noten – nur schriftlich."]
                return Vorschlag(s.wert, [f"schriftlich {_z(s.wert)} ({s.herleitung})"] + hinweis)
            wert = a_s * s.wert + (1 - a_s) * m.wert
            return Vorschlag(wert, [f"schriftlich {_z(s.wert)} × {gw.anteil_schriftlich:g} % ({s.herleitung})",
                                    f"mündlich {_z(m.wert)} × {100 - gw.anteil_schriftlich:g} % ({m.herleitung})",
                                    f"= {_z(wert)}"])

        zeilen = []
        for m in self.sd.mitglieder(g.id):
            sid = m.schueler.id
            s = {h: schriftlich(sid, (h,)) for h in (1, 2)}
            mu = {h: muendlich_teil(sid, (h,)) for h in (1, 2)}
            v1 = mische(s[1], mu[1])
            f = {art: fest[(sid, art)] for art in ARTEN if (sid, art) in fest}
            vorschlag = {"hj1": v1}
            if gw.zp10:
                ganz = mische(schriftlich(sid, (1, 2)), muendlich_teil(sid, (1, 2)))
                vorschlag["vornote"] = Vorschlag(ganz.wert, ["Ganzjahresnote aus allen Leistungen:"] + ganz.herleitung)
                vor = f.get("vornote")
                vor_wert = vor.wert if vor else ganz.wert
                zp = f.get("zp10")
                if vor_wert is None:
                    vorschlag["hj2"] = Vorschlag(None, ["Noch keine Vornote."])
                elif zp is None:
                    vorschlag["hj2"] = Vorschlag(None, [f"Vornote {_z(vor_wert)}" + (" (festgesetzt)" if vor else "")
                                                        + " – ZP10-Note fehlt noch."])
                else:
                    wert = (vor_wert + zp.wert) / 2
                    vorschlag["hj2"] = Vorschlag(wert, [f"Vornote {_z(vor_wert)}" + (" (festgesetzt)" if vor else "")
                                                        + " × 50 %", f"ZP10 {zp.kurz} × 50 %", f"= {_z(wert)}"])
            else:
                v2 = mische(s[2], mu[2])
                hj1 = f.get("hj1")
                hj1_wert = hj1.wert if hj1 else v1.wert
                a_h = gw.anteil_hj1 / 100
                if v2.wert is not None and hj1_wert is not None and a_h > 0:
                    wert = (1 - a_h) * v2.wert + a_h * hj1_wert
                    vorschlag["hj2"] = Vorschlag(wert, [f"2. Halbjahr {_z(v2.wert)} × {100 - gw.anteil_hj1:g} %:"]
                                                 + ["  " + z for z in v2.herleitung]
                                                 + [f"1. Halbjahr {_z(hj1_wert)}" + (" (festgesetzt)" if hj1 else "")
                                                    + f" × {gw.anteil_hj1:g} %", f"= {_z(wert)}"])
                else:
                    vorschlag["hj2"] = v2
            zeilen.append(Zeile(m, s, mu, vorschlag, f))
        return zeilen

    def uebernimm_vorschlaege(self, lerngruppe_id: int, art: str, nur_leere: bool = True, ganze: bool = True) -> int:
        """Setzt alle (bzw. nur noch leere) Noten einer Art auf den Vorschlag – standardmäßig als ganze Note,
        wie sie auf dem Zeugnis steht. Gibt die Anzahl zurück."""
        if art == "zp10":
            raise ZeugnisFehler("ZP10-Noten werden eingetragen, nicht vorgeschlagen.")
        n = 0
        for z in self.zeilen(lerngruppe_id):
            v = z.vorschlag.get(art)
            if v is None or v.note is None or (nur_leere and art in z.fest):
                continue
            self.setze(lerngruppe_id, z.mitglied.schueler.id, art, naechste_ganze_note(v.wert) if ganze else v.note)
            n += 1
        return n
