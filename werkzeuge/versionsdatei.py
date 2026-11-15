"""Testdateien je freigegebener Version: Jede neue Programmversion muss sie öffnen und unverändert zeigen.

    python werkzeuge/versionsdatei.py erzeuge tests/daten/version_0_3_2

legt `version_0_3_2.nvdb` (Datenbank mit allen Datenarten dieser Version, erfundene Namen) und
`version_0_3_2.json` (erwarteter Inhalt) an. Erzeugt wird **nur einmal**, mit genau der Version, die
freigegeben wurde – danach werden die Dateien nie wieder verändert. `tests/test_versionsdateien.py`
öffnet alle Dateien mit der aktuellen Version und vergleicht:

- Tabellen: Jede Zeile der alten Datei muss (in den alten Spalten) unverändert vorhanden sein.
  Neue Spalten und Tabellen sind erlaubt. Bei Datentabellen darf auch keine Zeile dazukommen.
- Sicht: Was die Lehrkraft sieht (Punkte, Noten, mündliche Noten, Zeugnisnoten, Vorschläge) bleibt gleich.
  Neue Einträge in Wörterbüchern (z. B. Quartalsvorschläge ab 0.4) sind erlaubt, alte müssen gleich bleiben.

Ändert eine neue Version absichtlich eine Berechnung, schlägt der Test fehl – dann muss die Änderung
bewusst begründet und hier dokumentiert werden.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from notenverwaltung import __version__  # noqa: E402
from notenverwaltung.modell import jahreswechsel  # noqa: E402
from notenverwaltung.modell.arbeiten import Arbeiten  # noqa: E402
from notenverwaltung.modell.muendlich import Muendlich  # noqa: E402
from notenverwaltung.modell.noten import Note, Notenschluessel, Punkte  # noqa: E402
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten  # noqa: E402
from notenverwaltung.modell.zeugnis import Zeugnis  # noqa: E402
from notenverwaltung.speicher.datenbank import Datenbank  # noqa: E402
from notenverwaltung.speicher.krypto import KdfParameter  # noqa: E402

PASSWORT_TEST = "Versionsprüfung 2026 – Ärger vermeiden"
# Tabellen, in die neue Versionen eigene Zeilen schreiben dürfen (z. B. Voreinstellungen)
ERWEITERBAR = {"meta", "notenschluessel"}


def n(kurz: str) -> Note:
    return Note.aus_kurz(kurz)


def erzeuge(ziel: Path) -> None:
    ziel = Path(ziel)
    pfad = ziel.with_suffix(".nvdb")
    for alt in (pfad, pfad.with_name(pfad.name + ".sperre")):
        alt.unlink(missing_ok=True)
    db, _ = Datenbank.neu(pfad, PASSWORT_TEST, KdfParameter(2, 2, 8 * 1024))
    v = db.verbindung
    db.setze_meta("druck_schule", "Gesamtschule Musterstadt")
    db.setze_meta("druck_lehrkraft", "Frau Beispiel")
    sd, ar, mu, zg = Stammdaten(v), Arbeiten(v), Muendlich(v), Zeugnis(v)

    # --- Schuljahr 2025/26: Klasse 8.4, Deutsch, eine Arbeit, Zeugnisnoten; dann Wechsel nach 2026/27
    alt = sd.lege_schuljahr_an("2025/26", date(2025, 8, 1), date(2026, 2, 1), date(2026, 7, 31))
    personen = [("Öztürk", "Ayşe", "8.4"), ("Weiß", "Jörg", "8.4"), ("Nguyễn", "Lan", "8.4"),
                ("D'Angelo", "Luca", "8.4"), ("Groß-Schäfer", "Mia-Sophie", "8.4")]
    ids = [sd.lege_schueler_an(alt.id, nn, vn, k, geburtsdatum=date(2011, 3, i + 1), extern_id=f"S-{100 + i}").id
           for i, (nn, vn, k) in enumerate(personen)]
    d8 = sd.lege_lerngruppe_an(Lerngruppe(0, alt.id, "D 8.4", "Deutsch", "klasse", 8, "D"))
    sd.fuege_hinzu(d8.id, ids)
    a0 = ar.lege_arbeit_an(d8.id, "1. Klassenarbeit", date(2025, 10, 7), [("1", 12), ("2", 8)])
    x0 = ar.aufgaben(a0.id)
    for sid, (p1, p2) in zip(ids, [(12, 8), (9.5, 5), (6, 4.25), (3, 2), (10, 7.75)]):
        ar.setze_punkte(x0[0].id, sid, p1)
        ar.setze_punkte(x0[1].id, sid, p2)
    for sid, k in zip(ids, ["1", "3", "4", "5", "2"]):
        zg.setze(d8.id, sid, "hj1", n(k))
        zg.setze(d8.id, sid, "hj2", n(k), "Jahresnote" if k == "1" else "")

    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31),
                                quartal2=date(2026, 10, 26))                       # ab 0.4: Quartalswechsel
    plan = jahreswechsel.plane(sd, alt.id)
    jahreswechsel.setze_wiederholer(next(p for p in plan.personen if p.eintrag.schueler.id == ids[3]))
    for g in plan.gruppen:
        g.uebernehmen = True
    jahreswechsel.fuehre_aus(sd, plan, jahr)
    neu = [sd.lege_schueler_an(jahr.id, nn, vn, k, zugang=z).id for nn, vn, k, z in
           [("Kowalski", "Zofia", "9.4", None), ("Ben Ali", "Yusuf", "9.4", date(2026, 11, 2)),
            ("Fischer", "Lea", "10.2", None), ("Ćosić", "Emir", "10.1", None), ("Lindqvist", "Åsa", "10.2", None)]]

    # --- 2026/27: Deutsch 9.4 (aus dem Wechsel), eigene Reihenfolge, Arbeit mit eigenem Schlüssel
    d9 = next(g for g in sd.lerngruppen(jahr.id) if g.fach == "Deutsch")
    sd.fuege_hinzu(d9.id, neu[:1])
    sd.fuege_hinzu(d9.id, neu[1:2], von=date(2026, 11, 2))
    sd.setze_sortierung(d9.id, "eigene")
    reihe = [m.schueler.id for m in sd.mitglieder(d9.id)]
    sd.setze_reihenfolge(d9.id, list(reversed(reihe)))
    sd.abgang(ids[1], jahr.id, date(2027, 3, 12))
    schluessel = Notenschluessel.aus_liste([(0, "6"), (20, "5"), (45, "4"), (60, "3"), (75, "2"), (90, "1")], raster=0.5)
    ar.speichere_vorlage("Deutsch Jg. 9", schluessel)
    a1 = ar.lege_arbeit_an(d9.id, "1. Klassenarbeit", date(2026, 10, 14), schluessel=schluessel,
                           rueckgabe=date(2026, 10, 28), thema="Kurzgeschichten – „Das Brot“")
    ar.setze_aufgaben(a1.id, [(None, "1", 10, "Inhalt", "Thema benennen; Figuren beschreiben"),
                              (None, "2a", 6.5, "Sprache", "Stilmittel mit Wirkung"),
                              (None, "b", 3.5, "", ""), (None, "3", 20, "Deutung", "Schluss deuten, belegen")])
    ar.aendere_arbeit(replace(ar.arbeit(a1.id), musterloesung="1) Die Frau …\n2a) Wiederholung …",
                              bemerkung="Zeitzuschlag Nachteilsausgleich"))
    x1 = ar.aufgaben(a1.id)
    mitglieder = [m for m in sd.mitglieder(d9.id) if m.aktiv_am(a1.datum)]
    punkte = [(10, 6.5, 3.5, 19.75), (7, 4, 2.25, 12), (5.5, 3, 1, 9), (2, 1.5, 0, 4.5), (8, 5, 3, 15), (9, 6, 3.5, 18)]
    for m, werte in zip(mitglieder, punkte):
        for x, w in zip(x1, werte):
            ar.setze_punkte(x.id, m.schueler.id, w)
    letzte = mitglieder[-1].schueler.id
    ar.setze_punkte(x1[3].id, letzte, None)                                     # unvollständig
    ar.setze_teilnahme(a1.id, mitglieder[0].schueler.id, kommentar="Sehr gut belegt – weiter so!")
    ar.setze_teilnahme(a1.id, mitglieder[2].schueler.id, note_manuell=n("3-"))
    a2 = ar.lege_arbeit_an(d9.id, "2. Klassenarbeit", date(2026, 12, 9), [("1", 15), ("2", 15)])
    x2 = ar.aufgaben(a2.id)
    for i, m in enumerate(sd.mitglieder(d9.id)):
        if i == 0:
            ar.setze_teilnahme(a2.id, m.schueler.id, status="fehlt")
        elif i == 1:
            ar.setze_teilnahme(a2.id, m.schueler.id, status="nachschreiben", note_manuell=n("2"))  # ohne Punkte
        elif i == 2:
            ar.setze_teilnahme(a2.id, m.schueler.id, status="befreit")
        else:
            ar.setze_punkte(x2[0].id, m.schueler.id, 15 - i)
            ar.setze_punkte(x2[1].id, m.schueler.id, 12 - i * 1.25)
    zs = mu.zeitraeume(d9.id)
    mu.teile(zs[0].id, date(2026, 9, 15), ("Sept.", "Okt."))
    zs = mu.zeitraeume(d9.id)
    for k, m in enumerate(sd.mitglieder(d9.id)):
        for j, z in enumerate(zs[:4]):
            if z.erfasst(m) and (k + j) % 4 != 3:
                mu.setze_note(z.id, m.schueler.id, n(["2+", "3", "2-", "1-", "4+", "3-"][(k + j) % 6]),
                              "Referat gehalten" if (k, j) == (1, 2) else None)
    zg.setze_gewichtung(d9.id, 60, 5, None)
    zg.uebernimm_vorschlaege(d9.id, "hj1")
    zg.uebernimm_vorschlaege(d9.id, "q1")                                      # ab 0.4: Quartalsnoten

    # --- Mathematik E-Kurs Jg. 10 (ZP10), Erdkunde mündlich
    m10 = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M10 E1", "Mathematik", "kurs", 10, "M", "E",
                                           sortierung="alphabet"))
    sd.fuege_hinzu(m10.id, neu[2:])
    a3 = ar.lege_arbeit_an(m10.id, "ZP-Probe", date(2027, 3, 3), [("A1", 4), ("A2", 6), ("B", 30)])
    for i, sid in enumerate(neu[2:]):
        for x, w in zip(ar.aufgaben(a3.id), [(4, 5.5, 27), (2, 3, 14.25), (3.75, 6, 20)][i]):
            ar.setze_punkte(x.id, sid, w)
    for sid, (h1, vor, zp) in zip(neu[2:], [("2", "2", "1"), ("4", "4", "5"), ("3", "3", "3")]):
        zg.setze(m10.id, sid, "hj1", n(h1))
        zg.setze(m10.id, sid, "vornote", n(vor))
        zg.setze(m10.id, sid, "zp10", n(zp))
    zg.uebernimm_vorschlaege(m10.id, "hj2", ganze=False)
    zg.setze(m10.id, neu[2], "q3", n("2+"), "Quartalsnote mit Tendenz")
    ek = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "EK 9.4", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    sd.uebernimm_klasse(ek.id, "9.4")
    sd.setze_zeitraum(ek.id, neu[0], date(2026, 9, 1), date(2027, 4, 30))
    for z in mu.zeitraeume(ek.id):
        for m in sd.mitglieder(ek.id):
            if z.erfasst(m):
                mu.setze_note(z.id, m.schueler.id, n("2" if m.schueler.nachname < "M" else "3+"))
    zg.setze_gewichtung(ek.id, None, 10, False)

    # --- ab 0.5: Oberstufe – Deutsch-LK in der Q1 mit Klausur, Sonstiger Mitarbeit und Punkten
    q1 = [sd.lege_schueler_an(jahr.id, nn, vn, "Q1").id for nn, vn in
          [("Achterberg", "Jule"), ("Bayraktar", "Deniz"), ("Ó Briain", "Seán")]]
    lk = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "Q1 D-LK", "Deutsch", "kurs", 12, "D", kursart="LK",
                                          notensystem="sek2"))
    sd.fuege_hinzu(lk.id, q1)
    k1 = ar.lege_arbeit_an(lk.id, "1. Klausur", date(2026, 10, 7), [("1", 40), ("2", 60)])
    for sid, (p1, p2) in zip(q1[:2], [(39, 57.5), (20, 25.25)]):
        x = ar.aufgaben(k1.id)
        ar.setze_punkte(x[0].id, sid, p1)
        ar.setze_punkte(x[1].id, sid, p2)
    ar.setze_teilnahme(k1.id, q1[2], note_manuell=Punkte.aus_punkte(9), kommentar="Nachschreibklausur")
    for z in mu.zeitraeume(lk.id)[:2]:
        for i, sid in enumerate(q1):
            mu.setze_note(z.id, sid, Punkte.aus_punkte([13, 5, 0][i] + (z.beginn.month % 2)))
    zg.uebernimm_vorschlaege(lk.id, "q1")
    zg.uebernimm_vorschlaege(lk.id, "hj1")
    ar.speichere_vorlage("Sek II streng", Notenschluessel.aus_liste([(0, "0P"), (50, "5P"), (96, "15P")]))

    # --- ab 0.7: Textbausteine (Standard geändert, eigener, fachbezogener)
    try:
        from notenverwaltung.modell.rueckmeldung import Textbausteine
    except ImportError:          # ältere Programmstände
        Textbausteine = None
    if Textbausteine is not None:
        tb = Textbausteine(v)
        liste = [(b.id, b.kuerzel, b.text, b.fach) for b in tb.alle() if b.kuerzel != "zeit"]
        liste[2] = (liste[2][0], "prima", "Prima, {Vorname} – {Punkte} von {Höchstpunkte} Punkten!", "")
        liste.append((None, "beleg", "Belege deine Deutung mit Zitaten (Zeilenangabe).", "Deutsch"))
        tb.setze(liste)

    # --- ab 0.9: Schnellerfassung je Stunde und Sitzplan (Erdkunde 9.4)
    try:
        from notenverwaltung.modell.sitzplan import Sitzplaene
        from notenverwaltung.modell.stunden import Stunden
    except ImportError:          # ältere Programmstände
        Sitzplaene = Stunden = None
    if Stunden is not None:
        st = Stunden(v)
        ek_mitglieder = [m for m in sd.mitglieder(ek.id) if m.aktiv_am(date(2026, 9, 10))]
        for i, m in enumerate(ek_mitglieder):
            for k, tag in enumerate((date(2026, 9, 3), date(2026, 9, 10), date(2026, 11, 12))):
                if (i + k) % 3 != 2:
                    st.setze(ek.id, m.schueler.id, tag, 1 + (i + 2 * k) % 5,
                             "Kartenarbeit vorgestellt" if (i, k) == (0, 1) else None)
        sp = Sitzplaene(v)
        raum = sp.lege_an(ek.id, "Raum 112", spalten=8, zeilen=4)
        sp.setze_platz(raum.id, 2, 0, True)                                    # Einzelplatz vorne im Gang
        sp.verteile(raum.id, ek_mitglieder)
        sp.setze_person(raum.id, 2, 0, ek_mitglieder[-1].schueler.id)
        gruppen = sp.lege_an(ek.id, "Gruppenarbeit", spalten=8, zeilen=6, vorlage="gruppen")
        sp.verteile(gruppen.id, ek_mitglieder, "zufall", __import__("random").Random(7))

    db.setze_meta("versionsdatei", __version__)
    db.schliessen()
    ziel.with_suffix(".json").write_text(json.dumps(inhalt(pfad), ensure_ascii=False, indent=1, sort_keys=True),
                                         encoding="utf-8")


# ---- Inhalt ------------------------------------------------------------------------------------------
def _tabellen(v) -> dict:
    erg = {}
    for (name,) in v.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                             "ORDER BY name"):
        spalten = [z[1] for z in v.execute(f'PRAGMA table_info("{name}")')]
        zeilen = sorted((list(z) for z in v.execute(f'SELECT * FROM "{name}"')), key=repr)
        erg[name] = {"spalten": spalten, "zeilen": zeilen}
    return erg


def _sicht(v) -> dict:
    sd, ar, mu, zg = Stammdaten(v), Arbeiten(v), Muendlich(v), Zeugnis(v)
    erg = {}
    for jahr in sd.schuljahre():
        for g in sd.lerngruppen(jahr.id):
            name = lambda m: f"{m.schueler.nachname}, {m.schueler.vorname} ({m.klasse})"  # noqa: E731
            gruppe = {"reihenfolge": [name(m) for m in sd.mitglieder(g.id)], "arbeiten": {}}
            for a in ar.arbeiten(g.id):
                gruppe["arbeiten"][a.titel] = [
                    [name(e.mitglied), e.summe, e.note.kurz if e.note else None, e.status, e.kommentar,
                     e.note_manuell.kurz if e.note_manuell else None]
                    for e in ar.ergebnisse(a.id)]
            gruppe["muendlich"] = sorted([z.bezeichnung, str(z.beginn), str(z.ende)] for z in mu.zeitraeume(g.id, False))
            gruppe["muendlich_noten"] = sorted([zid, sid, note.kurz, bem] for (zid, sid), (note, bem)
                                               in mu.noten(g.id).items())
            gruppe["zeugnis"] = [
                [name(z.mitglied), {k: (round(x.wert, 6) if x.wert is not None else None)
                                    for k, x in sorted(z.vorschlag.items())},
                 {k: x.kurz for k, x in sorted(z.fest.items())}]
                for z in zg.zeilen(g.id)]
            erg[f"{jahr.bezeichnung} {g.bezeichnung}"] = gruppe
    return erg


def inhalt(pfad: Path) -> dict:
    db = Datenbank.oeffnen(Path(pfad), "passwort", PASSWORT_TEST, sperre_ignorieren=True)
    try:
        return json.loads(json.dumps({"tabellen": _tabellen(db.verbindung), "sicht": _sicht(db.verbindung)},
                                     ensure_ascii=False))
    finally:
        db.schliessen(speichern=False)


def enthaelt(alt, neu) -> bool:
    """Ist `alt` unverändert in `neu` enthalten? Wörterbücher dürfen neue Schlüssel haben, Listen nicht wachsen."""
    if isinstance(alt, dict):
        return isinstance(neu, dict) and all(k in neu and enthaelt(v, neu[k]) for k, v in alt.items())
    if isinstance(alt, list):
        return isinstance(neu, list) and len(alt) == len(neu) and all(enthaelt(a, b) for a, b in zip(alt, neu))
    return alt == neu


def vergleiche(erwartet: dict, ist: dict) -> list[str]:
    """Liste der Abweichungen (leer = alles in Ordnung)."""
    fehler = []
    for name, alt in erwartet["tabellen"].items():
        neu = ist["tabellen"].get(name)
        if neu is None:
            fehler.append(f"Tabelle {name} fehlt")
            continue
        try:
            pos = [neu["spalten"].index(s) for s in alt["spalten"]]
        except ValueError as e:
            fehler.append(f"Tabelle {name}: Spalte fehlt ({e})")
            continue
        projiziert = [[z[i] for i in pos] for z in neu["zeilen"]]
        for zeile in alt["zeilen"]:
            if zeile not in projiziert:
                fehler.append(f"Tabelle {name}: Zeile fehlt oder verändert: {zeile}")
        if name not in ERWEITERBAR and len(neu["zeilen"]) != len(alt["zeilen"]):
            fehler.append(f"Tabelle {name}: {len(alt['zeilen'])} → {len(neu['zeilen'])} Zeilen")
    for gruppe, alt in erwartet["sicht"].items():
        neu = ist["sicht"].get(gruppe)
        if neu is None:
            fehler.append(f"Lerngruppe {gruppe} fehlt")
            continue
        for teil, wert in alt.items():
            if not enthaelt(wert, neu.get(teil)):
                fehler.append(f"{gruppe} / {teil}: erwartet {wert!r}, jetzt {neu.get(teil)!r}")
    return fehler


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "erzeuge":
        print(__doc__)
        sys.exit(2)
    from PySide6.QtCore import QCoreApplication

    QCoreApplication([])
    erzeuge(Path(sys.argv[2]))
    print(f"erzeugt: {sys.argv[2]}.nvdb/.json mit Version {__version__}")
