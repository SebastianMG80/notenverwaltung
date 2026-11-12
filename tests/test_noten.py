"""Notenlogik: Tendenzen, Notenschlüssel wie Punkteliste.ods, Notenspiegel."""

import pytest

from notenverwaltung.modell.noten import (
    ALLE_NOTEN,
    Note,
    Notenschluessel,
    Notenspiegel,
    runde,
    zahl,
    zahl_text,
)


def test_tendenz_werte():
    assert Note.aus_kurz("2+").wert == 1.7
    assert Note.aus_kurz("2-").wert == 2.3
    assert Note.aus_kurz("2–").wert == 2.3
    assert Note.aus_kurz("1+").wert == 0.7
    assert Note.aus_kurz("2").wert == 2.0
    assert Note.aus(6, 1).kurz == "6"  # die 6 hat keine Tendenz
    with pytest.raises(ValueError):
        Note.aus_kurz("7")
    with pytest.raises(ValueError):
        Note.aus_kurz("2++")


def test_texte():
    n = Note.aus_kurz("2+")
    assert n.wort == "gut"                      # für Schüler:innen
    assert n.wort_mit_tendenz == "gut (+)"      # für die Lehrkraft
    assert Note.aus_kurz("5-").wort_mit_tendenz == "mangelhaft (–)"
    assert len(ALLE_NOTEN) == 16
    assert sorted(ALLE_NOTEN)[0].kurz == "1+" and sorted(ALLE_NOTEN)[-1].kurz == "6"


def test_runden_wie_tabellenkalkulation():
    assert runde(2.5) == 3 and runde(3.5) == 4  # kaufmännisch, nicht „Banker's Rounding“
    assert runde(10.4) == 10
    assert runde(10.25, 0.5) == 10.5
    assert runde(10.24, 0.5) == 10.0


def test_punktgrenzen_wie_in_der_punkteliste():
    """Werte aus Punkteliste.ods (Höchstpunktzahl 52, Spalte „Pkt.“)."""
    k = Notenschluessel.standard()
    assert [g for g, _ in k.grenzen(52)] == [0, 10, 11, 20, 21, 22, 28, 29, 30, 35, 36, 37, 42, 43, 44, 55]
    # Zweite Tabelle der ODS (ganze Noten): 0→6, 10→5, 21→4, 29→3, 36→2, 43→1
    assert k.note(9, 52).stufe == 6
    assert k.note(10, 52).kurz == "5-"
    assert k.note(21, 52).kurz == "4-"
    assert k.note(29, 52).kurz == "3-"
    assert k.note(36, 52).kurz == "2-"
    assert k.note(43, 52).kurz == "1-"
    assert k.note(44, 52).kurz == "1"
    assert k.note(52, 52).kurz == "1"    # 1+ erst ab 105 % – wie in der Vorlage
    assert k.note(28.5, 52).kurz == "4+"


def test_alle_noten_der_vorlage():
    k = Notenschluessel.standard()
    erwartet = {0: "6", 10: "5-", 11: "5", 20: "5+", 21: "4-", 22: "4", 28: "4+", 29: "3-", 30: "3", 35: "3+",
                36: "2-", 37: "2", 42: "2+", 43: "1-", 44: "1"}
    for punkte, note in erwartet.items():
        assert k.note(punkte, 52).kurz == note, punkte


def test_bereiche():
    k = Notenschluessel.standard()
    b = k.bereiche(52)
    assert b[0] == (0, 9, Note.aus_kurz("6"))
    assert b[1] == (10, 10, Note.aus_kurz("5-"))
    assert b[-1] == (44, 52, Note.aus_kurz("1"))
    assert all(n.kurz != "1+" for _, _, n in b)
    # Bei kleinen Arbeiten fallen Stufen zusammen – keine doppelten Grenzen
    klein = k.bereiche(5)
    assert len({von for von, _, _ in klein}) == len(klein)


def test_schluessel_pruefung_und_json():
    k = Notenschluessel.standard()
    assert Notenschluessel.aus_json(k.als_json()) == k
    with pytest.raises(ValueError, match="0 %"):
        Notenschluessel.aus_liste([(10, "6"), (50, "4")])
    with pytest.raises(ValueError, match="bessere Note"):
        Notenschluessel.aus_liste([(0, "6"), (50, "4"), (60, "5")])
    with pytest.raises(ValueError, match="denselben"):
        Notenschluessel.aus_liste([(0, "6"), (50, "4"), (50, "3")])
    halb = Notenschluessel.aus_liste([(0, "6"), (50, "4")], raster=0.5)
    assert halb.grenzen(25) == [(0, Note.aus_kurz("6")), (12.5, Note.aus_kurz("4"))]


def test_notenspiegel_wie_ods():
    noten = [Note.aus_kurz(x) for x in ["1", "2+", "2-", "3", "3", "4-", "5", "6"]]
    s = Notenspiegel.aus(noten)
    assert s.anzahl == {1: 1, 2: 2, 3: 2, 4: 1, 5: 1, 6: 1}
    assert s.gesamt == 8
    assert s.schnitt == pytest.approx((1 + 2 * 2 + 3 * 2 + 4 + 5 + 6) / 8)
    assert s.schnitt_mit_tendenz == pytest.approx((1 + 1.7 + 2.3 + 3 + 3 + 4.3 + 5 + 6) / 8)
    assert s.anteil_unter_4 == pytest.approx(25.0)
    leer = Notenspiegel.aus([])
    assert leer.schnitt is None and leer.anteil_unter_4 is None  # kein #DIV/0! wie in der ODS


def test_zahlen_eingabe_und_ausgabe():
    assert zahl("3,5") == 3.5 and zahl(" 4 ") == 4 and zahl("") is None
    with pytest.raises(ValueError):
        zahl("drei")
    with pytest.raises(ValueError):
        zahl("nan")
    assert zahl_text(3.0) == "3" and zahl_text(3.5) == "3,5" and zahl_text(0.25) == "0,25" and zahl_text(None) == ""
