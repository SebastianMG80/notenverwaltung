"""Sek II: Punkte 0–15, Klausurschlüssel (NRW), Notensystem, Notenspiegel in Punkten."""

import pytest

from notenverwaltung.modell.noten import (ALLE_PUNKTE, SEK1, SEK2, Note, Notenschluessel, Notenspiegel, Notensystem,
                                          Punkte)

P = Punkte.aus_punkte


def test_punkte_und_sek1_entsprechung():
    # 15/14/13 = 1+/1/1-, 12/11/10 = 2+/2/2-, … 3/2/1 = 5+/5/5-, 0 = 6
    erwartet = ["1+", "1", "1-", "2+", "2", "2-", "3+", "3", "3-", "4+", "4", "4-", "5+", "5", "5-", "6"]
    assert [Note.aus(p.stufe, p.tendenz).kurz for p in ALLE_PUNKTE] == erwartet
    assert [p.punkte for p in ALLE_PUNKTE] == list(range(15, -1, -1))
    p = P(11)
    assert (p.kurz, p.wert, p.speicher, p.wort) == ("11", 11.0, "11P", "11 Punkte")
    assert P(1).wort == "1 Punkt" and P(11).wort_mit_tendenz == "11 Punkte (gut)"
    assert P(12) < P(11) and P(12).rang > P(11).rang                 # kleiner = besser, wie bei Noten
    assert Note.lies("11P") == P(11) and Note.lies("2-") == Note.aus_kurz("2-")
    assert P(11) != Note.aus_kurz("2")                                 # nie verwechselbar
    for falsch in (-1, 16, 2.5):
        with pytest.raises(ValueError):
            P(falsch)


def test_notensystem_eingabe_und_runden():
    assert Notensystem.von("sek2") is SEK2 and Notensystem.von(None) is SEK1
    assert SEK2.eingabe("11") == P(11) and SEK2.eingabe("0") == P(0) and SEK2.eingabe("") is None
    assert SEK2.eingabe("10,5") == P(11) and SEK2.eingabe("10,4") == P(10)    # ,5 zur besseren Punktzahl
    for falsch in ("16", "gut", "-1"):
        with pytest.raises(ValueError):
            SEK2.eingabe(falsch)
    assert SEK1.eingabe("2-") == Note.aus_kurz("2-") and SEK1.eingabe("1,7") == Note.aus_kurz("2+")
    with pytest.raises(ValueError):
        SEK1.eingabe("11")
    assert SEK2.ganz(9.5) == P(10) and SEK2.naechste(9.49) == P(9)
    assert SEK1.ganz(2.5) == Note.aus(2)
    assert SEK2.zahl(10.25) == "10,2" or SEK2.zahl(10.25) == "10,3"
    assert SEK1.zahl(2.345) in ("2,35", "2,34")


def test_klausurschluessel_nrw():
    k = Notenschluessel.standard("sek2")
    assert k.system == "sek2" and Notenschluessel.standard().system == "sek1"
    prozente = {s.note.punkte: s.prozent for s in k.stufen}
    assert prozente == {0: 0, 1: 20, 2: 27, 3: 33, 4: 39, 5: 45, 6: 50, 7: 55, 8: 60, 9: 65, 10: 70, 11: 75,
                        12: 80, 13: 85, 14: 90, 15: 95}
    assert k.note(95, 100) == P(15) and k.note(94.75, 100) == P(14) and k.note(19, 100) == P(0)
    assert k.note(30, 60) == P(6)            # 50 %
    # Speichern/Laden
    assert Notenschluessel.aus_json(k.als_json()) == k and '"15P"' in k.als_json()
    with pytest.raises(ValueError):
        Notenschluessel.aus_liste([(0, "6"), (50, "8P")])                  # gemischt


def test_notenspiegel_in_punkten():
    s = Notenspiegel.aus([P(15), P(11), P(11), P(4), P(0)])
    assert s.sek2 and list(s.anzahl)[:2] == [15, 14] and s.anzahl[11] == 2 and s.gesamt == 5
    assert s.schnitt == pytest.approx(41 / 5) and s.anteil_unter_4 == pytest.approx(40)
    assert s.text_unter == "unter 5 P."
    leer = Notenspiegel.aus([], sek2=True)
    assert leer.sek2 and leer.gesamt == 0 and len(leer.anzahl) == 16
    assert not Notenspiegel.aus([Note.aus(2)]).sek2
