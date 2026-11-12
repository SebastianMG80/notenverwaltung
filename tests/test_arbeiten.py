"""Klassenarbeiten: Aufgaben, Punkte, Noten, Teilnahme, Notenspiegel."""

from datetime import date

import pytest

from notenverwaltung.modell.arbeiten import ArbeitFehler, Arbeiten
from notenverwaltung.modell.noten import Note, Notenschluessel
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter

AUFGABEN_ODS = [("1", 5), ("2", 5), ("3a", 2), ("b", 2), ("c", 2), ("4", 6), ("5a", 2), ("b", 3), ("6a", 5),
                ("b", 2), ("c", 3), ("d", 2), ("7", 6), ("8", 7)]  # Punkteliste.ods, 52 Punkte


@pytest.fixture
def umgebung(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "a", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    ids = [sd.lege_schueler_an(jahr.id, n, "x", k).id for n, k in
           [("Adler", "9.1"), ("Becker", "9.1"), ("Celik", "9.3"), ("Dorn", "9.3")]]
    sd.fuege_hinzu(g.id, ids)
    yield db, sd, Arbeiten(db.verbindung), g, ids
    db.schliessen(speichern=False)


def test_arbeit_wie_punkteliste(umgebung):
    db, sd, ar, g, ids = umgebung
    a = ar.lege_arbeit_an(g.id, ar.titel_vorschlag(g.id), date(2026, 11, 10), AUFGABEN_ODS)
    assert a.titel == "1. Klassenarbeit"
    assert ar.hoechstpunkte(a.id) == 52
    assert a.schluessel == Notenschluessel.standard()  # Vorlage aus Migration = Standard
    auf = ar.aufgaben(a.id)
    assert [x.bezeichnung for x in auf][:5] == ["1", "2", "3a", "b", "c"]
    # Adler: alle Punkte → 52 → 1 (1+ erst ab 105 %)
    for x in auf:
        ar.setze_punkte(x.id, ids[0], x.max_punkte)
    # Becker: 29 Punkte → 3-
    rest = 29
    for x in auf:
        p = min(rest, x.max_punkte)
        ar.setze_punkte(x.id, ids[1], p)
        rest -= p
    # Celik: nur zwei Aufgaben eingetragen → unvollständig, Note aus der Summe
    ar.setze_punkte(auf[0].id, ids[2], 4.5)
    ar.setze_punkte(auf[1].id, ids[2], 3)
    e = {x.mitglied.schueler.id: x for x in ar.ergebnisse(a.id)}
    assert e[ids[0]].summe == 52 and e[ids[0]].note.kurz == "1"
    assert e[ids[1]].summe == 29 and e[ids[1]].note.kurz == "3-" and e[ids[1]].note.wort == "befriedigend"
    assert e[ids[2]].summe == 7.5 and e[ids[2]].unvollstaendig and e[ids[2]].note.kurz == "6"
    assert e[ids[3]].summe is None and e[ids[3]].note is None  # noch nicht korrigiert
    s = ar.notenspiegel(a.id)
    assert s.anzahl == {1: 1, 2: 0, 3: 1, 4: 0, 5: 0, 6: 1} and s.gesamt == 3
    assert s.anteil_unter_4 == pytest.approx(100 / 3)
    stat = ar.aufgaben_statistik(a.id)
    assert stat[0].mittel == pytest.approx((5 + 5 + 4.5) / 3)


def test_punkte_pruefung(umgebung):
    _, _, ar, g, ids = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 4)])
    x = ar.aufgaben(a.id)[0]
    with pytest.raises(ArbeitFehler, match="höchstens 4"):
        ar.setze_punkte(x.id, ids[0], 4.5)
    with pytest.raises(ArbeitFehler, match="negativ"):
        ar.setze_punkte(x.id, ids[0], -1)
    with pytest.raises(ArbeitFehler, match="halbe"):
        ar.setze_punkte(x.id, ids[0], 1.3)
    ar.setze_punkte(x.id, ids[0], 2.25)
    ar.setze_punkte(x.id, ids[0], None)
    assert ar.ergebnisse(a.id)[0].summe is None


def test_aufgaben_abgleichen(umgebung):
    _, _, ar, g, ids = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 4), ("2", 6), ("3", 5)])
    x1, x2, x3 = ar.aufgaben(a.id)
    ar.setze_punkte(x2.id, ids[0], 5)
    ar.setze_punkte(x3.id, ids[0], 5)
    # Aufgabe 3 löschen, 2 umbenennen und nach vorn, neue Aufgabe 4
    neu = ar.setze_aufgaben(a.id, [(x2.id, "2*", 6, "Brüche", ""), (x1.id, "1", 4, "", ""), (None, "4", 3, "", "")])
    assert [x.bezeichnung for x in neu] == ["2*", "1", "4"]
    assert ar.hoechstpunkte(a.id) == 13
    e = ar.ergebnisse(a.id)[0]
    assert e.summe == 5  # Punkte von Aufgabe 3 sind mit ihr verschwunden
    with pytest.raises(ArbeitFehler, match="über der neuen"):
        ar.setze_aufgaben(a.id, [(x2.id, "2*", 4, "", "")])
    with pytest.raises(ArbeitFehler, match="Bezeichnung"):
        ar.setze_aufgaben(a.id, [(None, " ", 4, "", "")])


def test_teilnahme_und_manuelle_note(umgebung):
    _, _, ar, g, ids = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    x = ar.aufgaben(a.id)[0]
    ar.setze_punkte(x.id, ids[0], 9)
    ar.setze_teilnahme(a.id, ids[1], status="fehlt")
    ar.setze_teilnahme(a.id, ids[2], note_manuell=Note.aus_kurz("6"), kommentar="Täuschungsversuch")
    ar.setze_teilnahme(a.id, ids[2], status="")   # Note bleibt unverändert
    e = {x.mitglied.schueler.id: x for x in ar.ergebnisse(a.id)}
    assert e[ids[1]].status == "fehlt" and e[ids[1]].note is None
    assert e[ids[2]].note.kurz == "6" and e[ids[2]].note_berechnet is None and e[ids[2]].kommentar == "Täuschungsversuch"
    ar.setze_teilnahme(a.id, ids[2], note_manuell=None, kommentar="")
    assert ar.ergebnisse(a.id)[2].note is None


def test_erwartete_teilnehmende(umgebung):
    _, sd, ar, g, ids = umgebung
    sd.abgang(ids[0], g.schuljahr_id, date(2026, 10, 1))
    sd.setze_zeitraum(g.id, ids[1], date(2026, 12, 1), None)
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    e = {x.mitglied.schueler.id: x for x in ar.ergebnisse(a.id)}
    assert not e[ids[0]].erwartet and not e[ids[1]].erwartet and e[ids[2]].erwartet


def test_arbeit_pruefungen_und_aendern(umgebung):
    _, _, ar, g, _ = umgebung
    with pytest.raises(ArbeitFehler, match="Schuljahr"):
        ar.lege_arbeit_an(g.id, "KA", date(2030, 1, 1))
    with pytest.raises(ArbeitFehler, match="Rückgabe"):
        ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), rueckgabe=date(2026, 11, 1))
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    from dataclasses import replace

    linear = Notenschluessel.aus_liste([(0, "6"), (50, "4"), (90, "1")])
    ar.aendere_arbeit(replace(a, titel="Test", schluessel=linear, rueckgabe=date(2026, 11, 20)))
    b = ar.arbeit(a.id)
    assert b.titel == "Test" and b.schluessel == linear and b.rueckgabe == date(2026, 11, 20)
    ar.loesche_arbeit(a.id)
    assert ar.arbeiten(g.id) == []


def test_vorlagen(umgebung):
    _, _, ar, g, _ = umgebung
    assert [v.name for v in ar.vorlagen()] == ["Standard (Punkteliste)"]
    eigen = Notenschluessel.aus_liste([(0, "6"), (45, "4"), (95, "1")])
    ar.speichere_vorlage("Streng", eigen, standard=True)
    assert ar.vorlagen()[0].name == "Streng" and ar.standard_schluessel() == eigen
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10))
    assert a.schluessel == eigen
    ar.speichere_vorlage("Streng", Notenschluessel.standard())  # Vorlage ändern …
    assert ar.arbeit(a.id).schluessel == eigen                    # … ändert die Arbeit nicht
    for v in ar.vorlagen()[:-1]:
        ar.loesche_vorlage(v.id)
    with pytest.raises(ArbeitFehler, match="letzte"):
        ar.loesche_vorlage(ar.vorlagen()[0].id)


def test_loeschen_kaskadiert(umgebung):
    db, sd, ar, g, ids = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, ids[0], 5)
    sd.loesche_lerngruppe(g.id)
    for tabelle in ("arbeit", "aufgabe", "punkte"):
        assert db.verbindung.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0] == 0
