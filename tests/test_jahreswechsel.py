"""Schuljahreswechsel: Klassen hochsetzen, Wiederholer, Abgänge, Lerngruppen übernehmen."""

from datetime import date

import pytest

from notenverwaltung.modell.jahreswechsel import fuehre_aus, hochsetzen, klasse_hoch, plane, setze_wiederholer
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten, StammdatenFehler
from notenverwaltung.modell.zeugnis import Zeugnis
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter


@pytest.fixture
def sd(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "w", "Testpasswort1", KdfParameter(1, 1, 1024))
    s = Stammdaten(db.verbindung)
    s.alt = s.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    s.ids = {n: s.lege_schueler_an(s.alt.id, n, "x", k).id for n, k in
             [("A", "8.4"), ("B", "8.4"), ("C", "8.4"), ("D", "10.1"), ("E", "8.2")]}
    s.abgang(s.ids["E"], s.alt.id, date(2027, 3, 1))
    yield s
    db.schliessen(speichern=False)


def neues_jahr(sd):
    return sd.lege_schuljahr_an("2027/28", date(2027, 8, 1), date(2028, 2, 1), date(2028, 7, 31))


def test_hochsetzen():
    assert klasse_hoch("8.4") == "9.4"
    assert klasse_hoch("10a") == "EF"          # Gesamtschule: nach der 10 kommt die Einführungsphase
    assert klasse_hoch("9.10") == "10.10"
    assert klasse_hoch("Förder") == "Förder"
    assert hochsetzen("M9.3E", 9, 10) == "M10.3E"
    assert hochsetzen("8.4 Deutsch", 8, 9) == "9.4 Deutsch"
    assert hochsetzen("E19G", 9, 10) == "E19G"   # „19“ ist kein Jahrgang 9


def test_plan_und_ausfuehrung(sd):
    g = sd.lege_lerngruppe_an(Lerngruppe(0, sd.alt.id, "M8.3E", "Mathematik", "kurs", 8, "M", "E"))
    sd.fuege_hinzu(g.id, [sd.ids["A"], sd.ids["B"], sd.ids["C"], sd.ids["E"]])
    sd.setze_sortierung(g.id, "eigene")
    sd.verschiebe(g.id, sd.ids["B"], -5)
    Zeugnis(sd.v).setze_gewichtung(g.id, 40, 5, None)

    plan = plane(sd, sd.alt.id, {"8.4": "9.4", "10.1": None})
    namen = {p.eintrag.schueler.nachname: p for p in plan.personen}
    assert "E" not in namen                                  # schon im alten Jahr abgegangen
    assert namen["A"].neue_klasse == "9.4" and namen["D"].aktion == "abgang"
    setze_wiederholer(namen["C"])
    assert namen["C"].neue_klasse == "8.4"
    gp = plan.gruppen[0]
    assert gp.neue_bezeichnung == "M9.3E" and gp.neuer_jahrgang == 9
    gp.uebernehmen = True

    neu = neues_jahr(sd)
    e = fuehre_aus(sd, plan, neu)
    assert (e.versetzt, e.wiederholt, e.abgaenge, e.gruppen, e.mitglieder) == (2, 1, 1, 1, 2)  # C (Wiederholer) nicht im Kurs
    assert sd.klassen(neu.id) == ["8.4", "9.4"]
    neu_g = sd.lerngruppen(neu.id)[0]
    assert (neu_g.bezeichnung, neu_g.jahrgang, neu_g.niveau, neu_g.sortierung) == ("M9.3E", 9, "E", "eigene")
    assert [m.schueler.nachname for m in sd.mitglieder(neu_g.id)] == ["B", "A"]   # eigene Reihenfolge bleibt
    gw = Zeugnis(sd.v).gewichtung(neu_g)
    assert (gw.anteil_schriftlich, gw.anteil_hj1) == (40, 5)
    # Altes Jahr unverändert
    assert len(sd.schueler_im_jahr(sd.alt.id)) == 5
    assert len(sd.mitglieder(g.id)) == 4


def test_fehler_und_alles_oder_nichts(sd):
    plan = plane(sd, sd.alt.id)
    plan.personen[0].neue_klasse = ""
    neu = neues_jahr(sd)
    with pytest.raises(StammdatenFehler, match="gültige neue Klasse"):
        fuehre_aus(sd, plan, neu)
    plan.personen[0].neue_klasse = "Förder"     # kein Jahrgang erkennbar
    with pytest.raises(StammdatenFehler):
        fuehre_aus(sd, plan, neu)
    assert sd.schueler_im_jahr(neu.id) == []
    with pytest.raises(StammdatenFehler, match="gleich"):
        fuehre_aus(sd, plane(sd, sd.alt.id), sd.alt)


def test_assistent(sd, app, monkeypatch):
    from notenverwaltung.ui import jahreswechsel_assistent as ja

    monkeypatch.setattr(ja, "info", lambda *a, **k: None)
    g = sd.lege_lerngruppe_an(Lerngruppe(0, sd.alt.id, "8.4 Deutsch", "Deutsch", "klasse", 8, "D"))
    sd.uebernimm_klasse(g.id, "8.4")
    a = ja.JahreswechselAssistent(sd, sd.alt)
    a.show()
    assert a.seite_jahr.bezeichnung.text() == "2027/28"
    assert a.seite_jahr.validatePage()
    a.next()
    k = a.seite_klassen
    zeilen = {k.tabelle.item(r, 0).text(): r for r in range(k.tabelle.rowCount())}
    assert k.tabelle.item(zeilen["8.4"], 2).text() == "9.4"
    k.tabelle.cellWidget(zeilen["10.1"], 3).setChecked(True)   # Abschlussklasse endet
    a.next()
    p = a.seite_personen
    zeile_c = next(r for r in range(p.tabelle.rowCount()) if p.tabelle.item(r, 0).text().startswith("C,"))
    p.tabelle.cellWidget(zeile_c, 2).setCurrentIndex(p.tabelle.cellWidget(zeile_c, 2).findData("wiederholen"))
    assert p.tabelle.item(zeile_c, 3).text() == "8.4"
    a.next()
    gr = a.seite_gruppen
    assert gr.tabelle.item(0, 2).text() == "9.4 Deutsch"
    gr.tabelle.cellWidget(0, 0).setChecked(True)
    a.accept()
    neu = a.neues_jahr
    assert neu.bezeichnung == "2027/28"
    assert sd.klassen(neu.id) == ["8.4", "9.4"]
    ng = sd.lerngruppen(neu.id)[0]
    assert ng.bezeichnung == "9.4 Deutsch"
    assert sorted(m.schueler.nachname for m in sd.mitglieder(ng.id)) == ["A", "B"]  # C wiederholt die 8.4


@pytest.mark.parametrize("bezeichnung", ["8.4 Deutsch", "D 8.4", "Deutsch"])
def test_klassengruppe_unabhaengig_von_bezeichnung(sd, bezeichnung):
    """Die neue Klasse kommt aus den Mitgliedern, nicht aus dem ersten Wort der Bezeichnung."""
    g = sd.lege_lerngruppe_an(Lerngruppe(0, sd.alt.id, bezeichnung, "Deutsch", "klasse", 8, "D"))
    sd.uebernimm_klasse(g.id, "8.4")
    sd.fuege_hinzu(g.id, [])
    plan = plane(sd, sd.alt.id)
    setze_wiederholer(next(p for p in plan.personen if p.eintrag.schueler.nachname == "C"))
    plan.gruppen[0].uebernehmen = True
    neu = neues_jahr(sd)
    fuehre_aus(sd, plan, neu)
    neu_g = sd.lerngruppen(neu.id)[0]
    assert sorted(m.schueler.nachname for m in sd.mitglieder(neu_g.id)) == ["A", "B"]   # C wiederholt die 8.4


def test_oberstufe_hochsetzen():
    from notenverwaltung.modell.jahreswechsel import gruppe_hoch, klasse_endet

    assert [klasse_hoch(k) for k in ("10.1", "10b", "EF", "Q1", "Q2", "ef", "Q1 b")] == [
        "EF", "EF", "Q1", "Q2", "Q2", "Q1", "Q2 b"]
    assert [klasse_endet(k) for k in ("Q2", "Q1", "10.1")] == [True, False, False]
    g = lambda b, j, art="kurs": Lerngruppe(0, 1, b, "Deutsch", art, j, "D")  # noqa: E731
    assert gruppe_hoch(g("Q1 D-LK", 12)) == "Q2 D-LK"
    assert gruppe_hoch(g("D-GK1", 11)) == "D-GK1"
    assert gruppe_hoch(g("10.2 Deutsch", 10, "klasse")) == "EF Deutsch"
    assert gruppe_hoch(g("D 10b", 10, "klasse")) == "D EF"
    assert gruppe_hoch(g("M9.3E", 9)) == "M10.3E"


def test_wechsel_in_die_oberstufe(sd):
    from notenverwaltung.modell.noten import Punkte

    ids = {n: sd.lege_schueler_an(sd.alt.id, n, "y", k).id for n, k in
           [("Q2a", "Q2"), ("Q1a", "Q1"), ("EFa", "EF"), ("Zehn", "10.2")]}
    d10 = sd.lege_lerngruppe_an(Lerngruppe(0, sd.alt.id, "10.2 Deutsch", "Deutsch", "klasse", 10, "D"))
    sd.uebernimm_klasse(d10.id, "10.2")
    lk = sd.lege_lerngruppe_an(Lerngruppe(0, sd.alt.id, "Q1 D-LK", "Deutsch", "kurs", 12, "D", kursart="LK",
                                          notensystem="sek2"))
    sd.fuege_hinzu(lk.id, [ids["Q1a"]])
    plan = plane(sd, sd.alt.id)
    namen = {p.eintrag.schueler.nachname: p for p in plan.personen}
    assert namen["Q2a"].aktion == "abgang"                                # Abitur
    assert (namen["Q1a"].neue_klasse, namen["EFa"].neue_klasse, namen["Zehn"].neue_klasse) == ("Q2", "Q1", "EF")
    assert namen["Zehn"].neuer_jahrgang == 11
    for gp in plan.gruppen:
        gp.uebernehmen = gp.gruppe.id in (d10.id, lk.id)
    neu = neues_jahr(sd)
    fuehre_aus(sd, plan, neu)
    gruppen = {x.bezeichnung: x for x in sd.lerngruppen(neu.id)}
    ef = gruppen["EF Deutsch"]
    assert (ef.jahrgang, ef.notensystem, ef.niveau) == (11, "sek2", "")
    assert Zeugnis(sd.v).gewichtung(ef).anteil_hj1 == 0
    assert [m.schueler.nachname for m in sd.mitglieder(ef.id)] == ["D", "Zehn"]   # alle aus den 10. Klassen
    q2 = gruppen["Q2 D-LK"]
    assert (q2.jahrgang, q2.kursart, q2.notensystem) == (13, "LK", "sek2")
    assert [m.schueler.nachname for m in sd.mitglieder(q2.id)] == ["Q1a"]
    from notenverwaltung.modell.muendlich import Muendlich

    mu = Muendlich(sd.v)
    mu.setze_note(mu.zeitraeume(ef.id)[0].id, ids["Zehn"], Punkte.aus_punkte(10))   # Punkte gehen
