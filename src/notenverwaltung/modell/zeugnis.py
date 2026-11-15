"""Notenberechnung und Notenvorschläge für Halbjahres- und Zeugnisnoten.

Regeln (Lastenheft):
- Halbjahresnote = Anteil schriftlich × Schnitt der Arbeiten des Halbjahres
                   + (1 − Anteil) × Schnitt der mündlichen Noten des Halbjahres.
  Standard: 50 % in schriftlichen Fächern, 0 % in mündlichen; je Lerngruppe einstellbar.
- 2. Halbjahr: Die Note des 1. Halbjahres geht mit einem einstellbaren Anteil ein (Standard 10 %).
- Deutsch, Englisch, Mathematik in Jahrgang 10 (ZP10-Fächer): Im 2. Halbjahr gibt es eine Ganzjahresnote
  (Vornote) aus allen Leistungen des Schuljahres; die Zeugnisnote ist 50 % Vornote + 50 % ZP10.
- Quartalsnoten (1. und 3. Quartal): nur die Leistungen des Quartals, gewichtet wie das Halbjahr,
  ohne Anteil eines anderen Zeitraums. Sie werden mit Tendenz abgegeben.
- Eine Arbeit gehört zum Quartal ihres Datums, ein mündlicher Zeitraum zum Quartal seines Beginns.
- Das Programm schlägt vor (nächstgelegene Note mit Tendenz), die Lehrkraft setzt fest.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date

from notenverwaltung.modell.arbeiten import STATUS as STATUS_LANG
from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import ALLE_NOTEN, SEK1, Note, Notensystem, Punkte, zahl_text
from notenverwaltung.modell.stammdaten import Lerngruppe, Mitglied, Stammdaten

ZP10_FAECHER = {"deutsch", "englisch", "mathematik", "d", "e", "m"}
ARTEN = ("q1", "hj1", "q3", "hj2", "vornote", "zp10")
QUARTALE = ("q1", "q3")                  # werden mit Tendenz festgesetzt


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
    system: Notensystem = SEK1

    @property
    def note(self) -> Note | None:
        return self.system.naechste(self.wert) if self.wert is not None else None


@dataclass(frozen=True)
class Zeile:
    mitglied: Mitglied
    schriftlich: dict[int, Teilnote]        # Halbjahr → Teilnote
    muendlich: dict[int, Teilnote]
    vorschlag: dict[str, Vorschlag]         # "q1", "hj1", "q3", "hj2" bzw. bei ZP10 zusätzlich "vornote"
    fest: dict[str, Note]                   # festgesetzt: "q1", "hj1", "q3", "hj2", "vornote", "zp10"
    quartal_s: dict[int, Teilnote] = field(default_factory=dict)   # Quartal (1 oder 3) → schriftlich
    quartal_m: dict[int, Teilnote] = field(default_factory=dict)   # Quartal (1 oder 3) → mündlich


@dataclass(frozen=True)
class Einzelspalte:
    """Eine einzelne Leistung: eine Arbeit oder ein mündlicher Zeitraum."""
    art: str                 # "arbeit" oder "muendlich"
    id: int
    titel: str
    von: date
    bis: date | None         # nur bei mündlichen Zeiträumen
    quartal: int             # 1–4 (Arbeit: Datum, Zeitraum: Beginn)
    zaehlt: bool = True
    gewicht: float = 1.0

    @property
    def schluessel(self) -> str:
        return f"{self.art}:{self.id}"


@dataclass(frozen=True)
class Einzelnote:
    text: str                # „2-“, „3*“ (festgesetzt), „fehlt“, „—“ (nicht in der Gruppe)
    hinweis: str = ""        # Tooltip
    leise: bool = False      # grau darstellen (fehlt, befreit, nicht in der Gruppe, zählt nicht)


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
        zp10_auto = not g.sek2 and g.jahrgang == 10 and (g.fach.strip().lower() in ZP10_FAECHER
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
        if note is not None and isinstance(note, Punkte) != self.sd.lerngruppe(lerngruppe_id).sek2:
            raise ZeugnisFehler("In der Oberstufe werden Punkte (0–15) vergeben, sonst Noten (1–6).")
        with self.v:
            if note is None:
                self.v.execute("DELETE FROM zeugnisnote WHERE lerngruppe_id = ? AND schueler_id = ? AND art = ?",
                               (lerngruppe_id, schueler_id, art))
            else:
                self.v.execute("INSERT INTO zeugnisnote (lerngruppe_id, schueler_id, art, note, bemerkung) "
                               "VALUES (?, ?, ?, ?, ?) ON CONFLICT (lerngruppe_id, schueler_id, art) DO UPDATE SET "
                               "note = excluded.note, bemerkung = excluded.bemerkung",
                               (lerngruppe_id, schueler_id, art, note.speicher, bemerkung))

    def festgesetzt(self, lerngruppe_id: int) -> dict[tuple[int, str], Note]:
        return {(s, a): Note.lies(n) for s, a, n in self.v.execute(
            "SELECT schueler_id, art, note FROM zeugnisnote WHERE lerngruppe_id = ?", (lerngruppe_id,))}

    # ---- Berechnung ----------------------------------------------------------------------------
    def zeilen(self, lerngruppe_id: int) -> list[Zeile]:
        g = self.sd.lerngruppe(lerngruppe_id)
        jahr = self.sd.schuljahr(g.schuljahr_id)
        system = Notensystem.von(g.notensystem)
        gw = self.gewichtung(g)
        a_s = gw.anteil_schriftlich / 100
        arbeiten = [a for a in self.ar.arbeiten(g.id) if a.zaehlt]
        ergebnisse = {a.id: {e.mitglied.schueler.id: e for e in self.ar.ergebnisse(a.id)} for a in arbeiten}
        zeitraeume = self.mu.zeitraeume(g.id)
        muendlich = self.mu.noten(g.id)
        fest = self.festgesetzt(g.id)

        def im(datum, halbjahre: tuple[int, ...], quartal: int | None) -> bool:
            return jahr.quartal(datum) == quartal if quartal else jahr.halbjahr(datum) in halbjahre

        def schriftlich(sid: int, halbjahre: tuple[int, ...], quartal: int | None = None) -> Teilnote:
            werte, teile = [], []
            for a in arbeiten:
                if not im(a.datum, halbjahre, quartal):
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

        def muendlich_teil(sid: int, halbjahre: tuple[int, ...], quartal: int | None = None) -> Teilnote:
            werte = [(z.bezeichnung, muendlich[(z.id, sid)][0]) for z in zeitraeume
                     if im(z.beginn, halbjahre, quartal) and (z.id, sid) in muendlich]
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
            qs = {q: schriftlich(sid, (), q) for q in (1, 3)}
            qm = {q: muendlich_teil(sid, (), q) for q in (1, 3)}
            vorschlag = {}
            for q in (1, 3):
                a, b = jahr.quartale()[q - 1]
                v = mische(qs[q], qm[q])
                vorschlag[f"q{q}"] = Vorschlag(v.wert, [f"Nur das {q}. Quartal ({a:%d.%m.}–{b:%d.%m.}):"] + v.herleitung)
            vorschlag["hj1"] = v1
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
            vorschlag = {k: replace(v, system=system) for k, v in vorschlag.items()}
            zeilen.append(Zeile(m, s, mu, vorschlag, f, qs, qm))
        return zeilen

    def einzelnoten(self, lerngruppe_id: int) -> tuple[list[Einzelspalte], dict[tuple[str, int], Einzelnote]]:
        """Alle einzelnen Leistungen der Lerngruppe in zeitlicher Reihenfolge: (Spalten, (Schlüssel, Schüler-ID) → Note)."""
        g = self.sd.lerngruppe(lerngruppe_id)
        jahr = self.sd.schuljahr(g.schuljahr_id)
        spalten: list[Einzelspalte] = []
        werte: dict[tuple[str, int], Einzelnote] = {}
        status_text = {"fehlt": "fehlt", "nachschreiben": "n. s.", "befreit": "befr."}
        for a in self.ar.arbeiten(g.id):
            sp = Einzelspalte("arbeit", a.id, a.titel, a.datum, None, jahr.quartal(a.datum), a.zaehlt, a.gewicht)
            spalten.append(sp)
            hoechst = self.ar.hoechstpunkte(a.id)
            for e in self.ar.ergebnisse(a.id):
                sid = e.mitglied.schueler.id
                if e.note is not None:
                    hinweis = (f"{e.note.wort_mit_tendenz} – festgesetzt" if e.note_manuell else
                               f"{e.note.wort_mit_tendenz} – {zahl_text(e.summe)} von {zahl_text(hoechst)} Punkten")
                    if e.note_manuell and e.summe is not None:
                        hinweis += f" ({zahl_text(e.summe)} von {zahl_text(hoechst)} Punkten)"
                    if not a.zaehlt:
                        hinweis += "\nDiese Arbeit zählt nicht für die Note."
                    werte[(sp.schluessel, sid)] = Einzelnote(e.note.kurz + ("*" if e.note_manuell else ""),
                                                            hinweis, not a.zaehlt)
                elif e.status:
                    werte[(sp.schluessel, sid)] = Einzelnote(status_text.get(e.status, e.status),
                                                            STATUS_LANG.get(e.status, e.status), True)
                elif not e.erwartet:
                    werte[(sp.schluessel, sid)] = Einzelnote("—", "Zu diesem Zeitpunkt nicht in der Gruppe.", True)
        mitglieder = self.sd.mitglieder(g.id)
        noten = self.mu.noten(g.id)
        for z in self.mu.zeitraeume(g.id):
            sp = Einzelspalte("muendlich", z.id, z.bezeichnung, z.beginn, z.ende, jahr.quartal(z.beginn))
            spalten.append(sp)
            for m in mitglieder:
                sid = m.schueler.id
                if (z.id, sid) in noten:
                    note, bem = noten[(z.id, sid)]
                    werte[(sp.schluessel, sid)] = Einzelnote(note.kurz, note.wort_mit_tendenz + (f"\n{bem}" if bem else ""))
                elif not z.erfasst(m):
                    werte[(sp.schluessel, sid)] = Einzelnote("—", "In diesem Zeitraum nicht in der Gruppe.", True)
        spalten.sort(key=lambda s: (s.von, s.art != "arbeit", s.id))
        return spalten, werte

    def uebernimm_vorschlaege(self, lerngruppe_id: int, art: str, nur_leere: bool = True,
                              ganze: bool | None = None) -> int:
        """Setzt alle (bzw. nur noch leere) Noten einer Art auf den Vorschlag. Standard: Zeugnisnoten als ganze
        Note (wie auf dem Zeugnis), Quartalsnoten mit Tendenz. Gibt die Anzahl zurück."""
        if ganze is None:
            ganze = art not in QUARTALE
        if art == "zp10":
            raise ZeugnisFehler("ZP10-Noten werden eingetragen, nicht vorgeschlagen.")
        n = 0
        for z in self.zeilen(lerngruppe_id):
            v = z.vorschlag.get(art)
            if v is None or v.note is None or (nur_leere and art in z.fest):
                continue
            self.setze(lerngruppe_id, z.mitglied.schueler.id, art, v.system.ganz(v.wert) if ganze else v.note)
            n += 1
        return n
