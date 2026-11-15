"""Sek II im Ablauf: Kurs anlegen, Klausur mit NRW-Schlüssel, Sonstige Mitarbeit, Quartals- und Halbjahresnoten."""

from datetime import date

import pytest

from notenverwaltung.modell.arbeiten import ArbeitFehler, Arbeiten
from notenverwaltung.modell.muendlich import Muendlich, MuendlichFehler
from notenverwaltung.modell.noten import Note, Notenschluessel, Punkte
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis, ZeugnisFehler
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter

P = Punkte.aus_punkte


@pytest.fixture
def kurs(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "s2", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "D-LK1", "Deutsch", "kurs", 12, "D", kursart="LK",
                                         notensystem="sek2"))
    ids = [sd.lege_schueler_an(jahr.id, n, "Test", "Q1").id for n in ("Arslan", "Berg")]
    sd.fuege_hinzu(g.id, ids)
    yield db, sd, g, ids
    db.schliessen(speichern=False)


def test_klausur_in_punkten(kurs):
    db, sd, g, ids = kurs
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "1. Klausur", date(2026, 10, 6), [("1", 40), ("2", 40), ("3", 20)])
    assert a.schluessel == Notenschluessel.standard("sek2")              # NRW-Schlüssel automatisch
    x = ar.aufgaben(a.id)
    for aufgabe, w in zip(x, (38, 38, 19)):                              # 95 % → 15
        ar.setze_punkte(aufgabe.id, ids[0], w)
    for aufgabe, w in zip(x, (20, 15, 9.5)):                             # 44,5 % → 4 Punkte (ab 39 %)
        ar.setze_punkte(aufgabe.id, ids[1], w)
    e = {r.mitglied.schueler.nachname: r for r in ar.ergebnisse(a.id)}
    assert e["Arslan"].note == P(15) and e["Berg"].note == P(4)
    sp = ar.notenspiegel(a.id)
    assert sp.sek2 and sp.anzahl[15] == 1 and sp.anzahl[4] == 1 and sp.anteil_unter_4 == 50
    # Festsetzen: nur Punkte; Speichern und wieder lesen
    ar.setze_teilnahme(a.id, ids[1], note_manuell=P(5))
    assert ar.ergebnisse(a.id)[1].note_manuell == P(5)
    assert db.verbindung.execute("SELECT note_manuell FROM teilnahme").fetchone()[0] == "5P"
    with pytest.raises(ArbeitFehler, match="Punkte"):
        ar.setze_teilnahme(a.id, ids[1], note_manuell=Note.aus_kurz("2"))


def test_sonstige_mitarbeit_und_zeugnis(kurs):
    db, sd, g, ids = kurs
    ar, mu, zg = Arbeiten(db.verbindung), Muendlich(db.verbindung), Zeugnis(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "1. Klausur", date(2026, 10, 6), [("1", 100)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, ids[0], 72)                # 72 % → 10 Punkte
    zs = mu.zeitraeume(g.id)
    mu.setze_note(zs[0].id, ids[0], P(13))
    mu.setze_note(zs[1].id, ids[0], P(12))
    with pytest.raises(MuendlichFehler, match="Punkte"):
        mu.setze_note(zs[1].id, ids[1], Note.aus_kurz("2"))
    gw = zg.gewichtung(sd.lerngruppe(g.id))
    assert (gw.anteil_schriftlich, gw.anteil_hj1, gw.zp10) == (50, 0, False)
    z = zg.zeilen(g.id)[0]
    assert z.vorschlag["q1"].wert == pytest.approx(0.5 * 10 + 0.5 * 13) and z.vorschlag["q1"].note == P(12)  # 11,5 → 12
    assert z.vorschlag["hj1"].wert == pytest.approx(0.5 * 10 + 0.5 * 12.5) and z.vorschlag["hj1"].note == P(11)
    assert zg.uebernimm_vorschlaege(g.id, "hj1") == 1 and zg.uebernimm_vorschlaege(g.id, "q1") == 1
    z = zg.zeilen(g.id)[0]
    assert z.fest == {"hj1": P(11), "q1": P(12)}
    with pytest.raises(ZeugnisFehler, match="Punkte"):
        zg.setze(g.id, ids[1], "hj1", Note.aus_kurz("3"))
    # 2. Halbjahr ohne Anteil des 1. Halbjahres
    mu.setze_note(zs[2].id, ids[0], P(6))
    assert zg.zeilen(g.id)[0].vorschlag["hj2"].wert == pytest.approx(6)


def test_speichern_und_oeffnen(kurs, tmp_path):
    db, sd, g, ids = kurs
    mu = Muendlich(db.verbindung)
    mu.setze_note(mu.zeitraeume(g.id)[0].id, ids[0], P(0))
    db.speichern()
    db2 = Datenbank.oeffnen(db.pfad, "passwort", "Testpasswort1", sperre_ignorieren=True)
    try:
        g2 = Stammdaten(db2.verbindung).lerngruppe(g.id)
        assert g2.sek2 and g2.kursart == "LK"
        assert list(Muendlich(db2.verbindung).noten(g.id).values())[0][0] == P(0)
    finally:
        db2.schliessen(speichern=False)
