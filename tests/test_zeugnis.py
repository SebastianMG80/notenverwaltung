"""Notenberechnung: Gewichtung, Halbjahre, Anteil 1. Halbjahr, ZP10-Fächer, Festsetzen."""

from datetime import date

import pytest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis, ZeugnisFehler, naechste_note
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter

N = Note.aus_kurz


@pytest.fixture
def db(tmp_path):
    d, _ = Datenbank.neu(tmp_path / "z", "Testpasswort1", KdfParameter(1, 1, 1024))
    yield d
    d.schliessen(speichern=False)


def gruppe(db, fach="Mathematik", jahrgang=9, schriftlich=True):
    sd = Stammdaten(db.verbindung)
    jahre = sd.schuljahre()
    jahr = jahre[0] if jahre else sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, f"{fach} {jahrgang}", fach, "kurs", jahrgang,
                                         fach[0], schriftlich=schriftlich))
    sid = sd.lege_schueler_an(jahr.id, "Muster", "Hans", f"{jahrgang}.1").id
    sd.fuege_hinzu(g.id, [sid])
    return g, sid


def arbeit(db, g, sid, datum, note_prozent, titel="KA", gewicht=1.0):
    from dataclasses import replace

    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, titel, datum, [("1", 100)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, note_prozent)
    if gewicht != 1:
        ar.aendere_arbeit(replace(ar.arbeit(a.id), gewicht=gewicht))
    return a


def muendlich(db, g, sid, quartal, note):
    mu = Muendlich(db.verbindung)
    mu.setze_note(mu.zeitraeume(g.id)[quartal].id, sid, N(note))


def test_naechste_ganze_note():
    from notenverwaltung.modell.zeugnis import naechste_ganze_note

    assert [naechste_ganze_note(w).kurz for w in (0.7, 1.49, 2.5, 2.51, 5.9)] == ["1", "1", "2", "3", "6"]


def test_naechste_note():
    assert naechste_note(2.15).kurz == "2"
    assert naechste_note(2.16).kurz == "2-"
    assert naechste_note(2.5).kurz == "2-"   # Gleichstand → bessere
    assert naechste_note(0.7).kurz == "1+"
    assert naechste_note(5.8).kurz == "6"


def test_standardgewichtung(db):
    g, _ = gruppe(db)
    ek, _ = gruppe(db, "Erdkunde", schriftlich=False)
    z = Zeugnis(db.verbindung)
    assert z.gewichtung(g).anteil_schriftlich == 50 and z.gewichtung(g).anteil_hj1 == 10
    assert z.gewichtung(ek).anteil_schriftlich == 0
    assert not z.gewichtung(g).zp10


def test_halbjahr_schriftlich_und_muendlich(db):
    g, sid = gruppe(db)
    arbeit(db, g, sid, date(2026, 10, 1), 90)   # 1
    arbeit(db, g, sid, date(2026, 12, 1), 60)   # 3
    muendlich(db, g, sid, 0, "2")
    muendlich(db, g, sid, 1, "3+")
    z = Zeugnis(db.verbindung).zeilen(g.id)[0]
    assert z.schriftlich[1].wert == pytest.approx(2.0) and z.schriftlich[1].anzahl == 2
    assert z.muendlich[1].wert == pytest.approx((2 + 2.7) / 2)
    v = z.vorschlag["hj1"]
    assert v.wert == pytest.approx(0.5 * 2 + 0.5 * 2.35)
    assert v.note.kurz == "2-"  # 2,175 liegt näher an 2,3 als an 2,0
    assert any("schriftlich" in h for h in v.herleitung)


def test_gewicht_einer_arbeit(db):
    g, sid = gruppe(db)
    arbeit(db, g, sid, date(2026, 10, 1), 90)               # 1
    arbeit(db, g, sid, date(2026, 12, 1), 60, gewicht=3)    # 3, dreifach
    z = Zeugnis(db.verbindung).zeilen(g.id)[0]
    assert z.schriftlich[1].wert == pytest.approx((1 + 3 * 3) / 4)


def test_nur_eine_seite_vorhanden(db):
    g, sid = gruppe(db)
    muendlich(db, g, sid, 0, "2")
    v = Zeugnis(db.verbindung).zeilen(g.id)[0].vorschlag["hj1"]
    assert v.wert == 2 and any("Achtung" in h for h in v.herleitung)


def test_zweites_halbjahr_mit_anteil_hj1(db):
    g, sid = gruppe(db)
    zg = Zeugnis(db.verbindung)
    muendlich(db, g, sid, 0, "1")                 # HJ1 nur mündlich → 1
    arbeit(db, g, sid, date(2026, 10, 1), 90)     # HJ1 schriftlich 1
    arbeit(db, g, sid, date(2027, 3, 1), 60)      # HJ2 schriftlich 3
    muendlich(db, g, sid, 2, "3")                 # HJ2 mündlich 3
    v2 = zg.zeilen(g.id)[0].vorschlag["hj2"]
    assert v2.wert == pytest.approx(0.9 * 3 + 0.1 * 1)
    # Festgesetzte HJ1-Note hat Vorrang vor dem Vorschlag
    zg.setze(g.id, sid, "hj1", N("2"))
    assert zg.zeilen(g.id)[0].vorschlag["hj2"].wert == pytest.approx(0.9 * 3 + 0.1 * 2)
    zg.setze_gewichtung(g.id, 60, 0, None)
    z = zg.zeilen(g.id)[0]
    assert z.vorschlag["hj2"].wert == pytest.approx(3.0)
    with pytest.raises(ZeugnisFehler):
        zg.setze_gewichtung(g.id, 120, 10, None)


def test_zp10_fach(db):
    g, sid = gruppe(db, "Deutsch", jahrgang=10)
    zg = Zeugnis(db.verbindung)
    assert zg.gewichtung(g).zp10 and zg.gewichtung(g).zp10_automatisch
    arbeit(db, g, sid, date(2026, 10, 1), 90)     # 1 (HJ1)
    arbeit(db, g, sid, date(2027, 3, 1), 60)      # 3 (HJ2)
    muendlich(db, g, sid, 0, "2")
    muendlich(db, g, sid, 3, "2")
    z = zg.zeilen(g.id)[0]
    vornote = z.vorschlag["vornote"].wert
    assert vornote == pytest.approx(0.5 * 2 + 0.5 * 2)   # ganzes Jahr: schriftlich (1+3)/2, mündlich 2
    assert z.vorschlag["hj2"].wert is None and "ZP10" in z.vorschlag["hj2"].herleitung[0]
    zg.setze(g.id, sid, "zp10", N("4"))
    assert zg.zeilen(g.id)[0].vorschlag["hj2"].wert == pytest.approx((2 + 4) / 2)
    zg.setze(g.id, sid, "vornote", N("2-"))
    assert zg.zeilen(g.id)[0].vorschlag["hj2"].wert == pytest.approx((2.3 + 4) / 2)
    # Abschalten möglich (z. B. Englisch, das nicht ZP10-Fach ist)
    zg.setze_gewichtung(g.id, None, 10, False)
    assert not zg.gewichtung(g).zp10


def test_zp10_nur_jahrgang_10_und_hauptfaecher(db):
    zg = Zeugnis(db.verbindung)
    for fach, jg, erwartet in (("Mathematik", 10, True), ("Englisch", 10, True), ("Mathematik", 9, False),
                               ("Biologie", 10, False)):
        g, _ = gruppe(db, fach, jg)
        assert zg.gewichtung(g).zp10 is erwartet, (fach, jg)


def test_vorschlaege_uebernehmen(db):
    g, sid = gruppe(db)
    zg = Zeugnis(db.verbindung)
    muendlich(db, g, sid, 0, "2-")
    assert zg.uebernimm_vorschlaege(g.id, "hj1") == 1
    assert zg.festgesetzt(g.id)[(sid, "hj1")].kurz == "2"        # Zeugnis: ganze Note
    zg.uebernimm_vorschlaege(g.id, "hj1", nur_leere=False, ganze=False)
    assert zg.festgesetzt(g.id)[(sid, "hj1")].kurz == "2-"
    zg.setze(g.id, sid, "hj1", N("2"))
    assert zg.uebernimm_vorschlaege(g.id, "hj1") == 0          # Festgesetztes bleibt
    assert zg.uebernimm_vorschlaege(g.id, "hj1", nur_leere=False) == 1
    with pytest.raises(ZeugnisFehler):
        zg.uebernimm_vorschlaege(g.id, "zp10")
