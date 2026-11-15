"""Schuljahreswechsel: Schüler:innen und Lerngruppen ins neue Schuljahr übernehmen.

- Klassen werden hochgesetzt (8.4 → 9.4); je Klasse anpassbar oder abwählbar (z. B. Abschlussklassen).
- Oberstufe (Gesamtschule, G9): 10.x → EF → Q1 → Q2; die Q2 endet (Abitur). Lerngruppen, die in die
  Oberstufe wechseln, bekommen Punkte (0–15) statt Noten.
- Je Person: versetzen, wiederholen oder Abgang. Wer im alten Jahr bereits abgegangen ist, wird nicht übernommen.
- Lerngruppen können mit angepasster Bezeichnung, Mitgliedern, Gewichtung und Sortierung übernommen werden.
- Das alte Schuljahr bleibt unverändert erhalten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from notenverwaltung.modell.stammdaten import (
    Lerngruppe,
    SchuelerImJahr,
    Schuljahr,
    Stammdaten,
    StammdatenFehler,
    jahrgang_aus_klasse,
)

AKTIONEN = {"versetzen": "versetzen", "wiederholen": "wiederholt", "abgang": "verlässt die Schule"}


def hochsetzen(text: str, alt: int, neu: int) -> str:
    """Ersetzt die erste Jahrgangszahl im Text: „8.4“ → „9.4“, „M9.3E“ → „M10.3E“, „8.4 Deutsch“ → „9.4 Deutsch“."""
    return re.sub(rf"(?<!\d){alt}(?!\d)", str(neu), text, count=1)


STUFENFOLGE = {"EF": "Q1", "Q1": "Q2"}
_STUFE = re.compile(r"(?<![A-Za-z0-9])(EF|Q1|Q2)(?![0-9])", re.IGNORECASE)


def klasse_hoch(klasse: str) -> str:
    """„8.4“ → „9.4“; aus allen 10. Klassen wird die EF; „EF“ → „Q1“ → „Q2“ (die Q2 bleibt, sie endet)."""
    m = _STUFE.search(klasse)
    if m and jahrgang_aus_klasse(klasse):
        neu = STUFENFOLGE.get(m.group(1).upper())
        return klasse if neu is None else klasse[:m.start(1)] + neu + klasse[m.end(1):]
    j = jahrgang_aus_klasse(klasse)
    if j == 10:
        return "EF"
    return hochsetzen(klasse, j, j + 1) if j else klasse


def klasse_endet(klasse: str) -> bool:
    """Q2: Nach dem Abitur verlassen alle die Schule."""
    return jahrgang_aus_klasse(klasse) == 13


def gruppe_hoch(g: Lerngruppe) -> str:
    """Bezeichnung einer Lerngruppe im nächsten Jahr: „8.4 D“ → „9.4 D“, „Q1 D-LK“ → „Q2 D-LK“, „10.2 D“ → „EF D“."""
    if g.jahrgang >= 11:
        return _STUFE.sub(lambda m: STUFENFOLGE.get(m.group(1).upper(), m.group(1)), g.bezeichnung, count=1)
    if g.jahrgang == 10 and g.art == "klasse":
        return re.sub(r"(?<!\d)10(?:\.\d+|[a-zA-Z](?![a-zA-Z]))?(?!\d)", "EF", g.bezeichnung, count=1)
    return hochsetzen(g.bezeichnung, g.jahrgang, g.jahrgang + 1)


@dataclass
class PersonPlan:
    eintrag: SchuelerImJahr
    aktion: str              # Schlüssel aus AKTIONEN
    neue_klasse: str

    @property
    def neuer_jahrgang(self) -> int | None:
        return jahrgang_aus_klasse(self.neue_klasse)


@dataclass
class GruppenPlan:
    gruppe: Lerngruppe
    uebernehmen: bool
    neue_bezeichnung: str
    neuer_jahrgang: int
    mitglieder: bool = True


@dataclass
class Wechselplan:
    alt: Schuljahr
    personen: list[PersonPlan] = field(default_factory=list)
    gruppen: list[GruppenPlan] = field(default_factory=list)


@dataclass
class WechselErgebnis:
    versetzt: int = 0
    wiederholt: int = 0
    abgaenge: int = 0
    gruppen: int = 0
    mitglieder: int = 0


def plane(sd: Stammdaten, alt_id: int, klassen: dict[str, str | None] | None = None) -> Wechselplan:
    """Erster Plan. `klassen` ordnet alte Klassen neuen zu (None = Klasse endet, alle gehen ab)."""
    alt = sd.schuljahr(alt_id)
    klassen = klassen or {k: None if klasse_endet(k) else klasse_hoch(k) for k in sd.klassen(alt_id)}
    plan = Wechselplan(alt)
    for e in sd.schueler_im_jahr(alt_id):
        if e.abgang is not None:
            continue  # schon im alten Jahr abgegangen
        ziel = klassen.get(e.klasse, None if klasse_endet(e.klasse) else klasse_hoch(e.klasse))
        if ziel is None:
            plan.personen.append(PersonPlan(e, "abgang", ""))
        else:
            plan.personen.append(PersonPlan(e, "versetzen", ziel))
    for g in sd.lerngruppen(alt_id):
        plan.gruppen.append(GruppenPlan(g, False, gruppe_hoch(g),
                                        min(13, g.jahrgang + 1)))
    return plan


def setze_wiederholer(p: PersonPlan) -> None:
    p.aktion = "wiederholen"
    p.neue_klasse = p.eintrag.klasse


def fuehre_aus(sd: Stammdaten, plan: Wechselplan, neu: Schuljahr) -> WechselErgebnis:
    """Überträgt den Plan ins (bereits angelegte) neue Schuljahr – alles oder nichts."""
    if neu.id == plan.alt.id:
        raise StammdatenFehler("Altes und neues Schuljahr sind gleich.")
    if neu.beginn <= plan.alt.beginn:
        raise StammdatenFehler("Das neue Schuljahr muss nach dem alten beginnen.")
    for p in plan.personen:
        if p.aktion != "abgang" and (not p.neue_klasse.strip() or not p.neuer_jahrgang):
            s = p.eintrag.schueler
            raise StammdatenFehler(f"{s.vorname} {s.nachname}: Bitte eine gültige neue Klasse angeben.")
    v = sd.v
    if v.in_transaction:
        v.commit()
    vorher = v.serialize()
    e = WechselErgebnis()
    try:
        versetzt: set[int] = set()
        neue_klasse: dict[int, str] = {}
        for p in plan.personen:
            if p.aktion == "abgang":
                e.abgaenge += 1
                continue
            sd.setze_klasse(p.eintrag.schueler.id, neu.id, p.neue_klasse, p.neuer_jahrgang)
            neue_klasse[p.eintrag.schueler.id] = p.neue_klasse.strip()
            if p.aktion == "versetzen":
                versetzt.add(p.eintrag.schueler.id)
            if p.aktion == "wiederholen":
                e.wiederholt += 1
            else:
                e.versetzt += 1
        for gp in plan.gruppen:
            if not gp.uebernehmen:
                continue
            g = gp.gruppe
            in_die_oberstufe = gp.neuer_jahrgang >= 11 and not g.sek2
            neu_g = sd.lege_lerngruppe_an(Lerngruppe(
                0, neu.id, gp.neue_bezeichnung, g.fach, g.art, gp.neuer_jahrgang, g.fach_kuerzel,
                "" if in_die_oberstufe else g.niveau, g.schriftlich, "sek2" if in_die_oberstufe else g.notensystem,
                g.sortierung, g.kursart))
            gewicht = v.execute("SELECT anteil_schriftlich, anteil_hj1, zp10 FROM lerngruppe WHERE id = ?",
                                (g.id,)).fetchone()
            if in_die_oberstufe:   # Oberstufe: Halbjahre getrennt, keine ZP10
                gewicht = (gewicht[0], 0, None)
            with v:
                v.execute("UPDATE lerngruppe SET anteil_schriftlich = ?, anteil_hj1 = ?, zp10 = ? WHERE id = ?",
                          (*gewicht, neu_g.id))
            e.gruppen += 1
            if gp.mitglieder:
                if g.art == "klasse":
                    # Klasse in einem Fach: alle, die im neuen Jahr in dieser Klasse sind (auch Wiederholer:innen)
                    # Zielklasse(n) aus den Mitgliedern ableiten – die Bezeichnung kann „8.4 D“ oder „D 8.4“ sein
                    alte_klassen = {m.klasse for m in sd.mitglieder(g.id)}
                    ziele = {p.neue_klasse.strip() for p in plan.personen
                             if p.aktion == "versetzen" and p.eintrag.klasse in alte_klassen}
                    ids = [sid for sid, k in neue_klasse.items() if k in ziele]
                else:
                    # Kurs: bisherige Mitglieder, die versetzt werden und bis zum Schluss dabei waren
                    ids = [m.schueler.id for m in sd.mitglieder(g.id)
                           if m.schueler.id in versetzt and (m.ende is None or m.ende >= plan.alt.ende)]
                e.mitglieder += sd.fuege_hinzu(neu_g.id, ids)
                if g.sortierung == "eigene":
                    reihenfolge = [m.schueler.id for m in sd.mitglieder(g.id, "eigene") if m.schueler.id in ids]
                    sd.setze_reihenfolge(neu_g.id, reihenfolge)
    except Exception:
        if v.in_transaction:
            v.rollback()
        v.deserialize(vorher)
        v.execute("PRAGMA foreign_keys = ON")
        raise
    return e

