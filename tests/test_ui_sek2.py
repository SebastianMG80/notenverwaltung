"""Oberfläche in der Oberstufe: Punkte eintippen (Klausur, Sonstige Mitarbeit, Noten), Klausurschlüssel."""

from datetime import date

import pytest
from PySide6.QtCore import Qt

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.noten import Notenschluessel, Punkte
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis
from notenverwaltung.speicher.datenbank import Datenbank

P = Punkte.aus_punkte


@pytest.fixture
def kurs(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "u2", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "E-GK2", "Englisch", "kurs", 11, "E", kursart="GK",
                                         notensystem="sek2"))
    ids = [sd.lege_schueler_an(jahr.id, n, "Test", "EF").id for n in ("Acar", "Brandt")]
    sd.fuege_hinzu(g.id, ids)
    yield sd, jahr, g, ids
    db.schliessen(speichern=False)


def test_klausur_raster_in_punkten(kurs):
    from test_ui_arbeiten import tippe

    from notenverwaltung.ui.seiten.arbeiten_tab import SP_NOTE, ArbeitenTab

    sd, jahr, g, ids = kurs
    ar = Arbeiten(sd.v)
    a = ar.lege_arbeit_an(g.id, "1. Klausur", date(2026, 10, 1), [("1", 60), ("2", 40)])
    t = ArbeitenTab()
    t.resize(1200, 600)
    t.show()
    t.zeige(sd, jahr, g)
    r, m = t.raster, t.modell
    assert m.headerData(SP_NOTE, Qt.Orientation.Horizontal) == "Noten-\npunkte"
    tippe(r, "57")
    tippe(r, "38")                                       # 95 % → 15 Punkte
    assert m.data(m.index(0, SP_NOTE)) == "15"
    assert "Punkte" in t.zusammenfassung.text()
    assert t.spiegel.rowCount() == 16                    # Klausurschlüssel mit 16 Stufen
    r.setCurrentIndex(m.index(1, SP_NOTE))
    tippe(r, "7")                                        # Nachschreibklausur ohne Punkte
    assert ar.ergebnisse(a.id)[1].note == P(7) and m.data(m.index(1, SP_NOTE)) == "7*"
    r.setCurrentIndex(m.index(1, SP_NOTE))
    tippe(r, "2-")
    assert "Punkte" in t.meldung.text() and ar.ergebnisse(a.id)[1].note == P(7)
    r.setCurrentIndex(m.index(1, SP_NOTE))
    tippe(r, "7,5")
    assert "ganze Punkte" in t.meldung.text()


def test_klausurschluessel_dialog(kurs):
    from notenverwaltung.ui.arbeit_dialoge import SchluesselDialog

    sd, jahr, g, ids = kurs
    d = SchluesselDialog(Arbeiten(sd.v), Notenschluessel.standard("sek2"), 100)
    assert "Punkte" in d.windowTitle() and d.tabelle.rowCount() == 16
    assert [d.vorlage.itemText(i) for i in range(d.vorlage.count())] == ["Standard Sek II (NRW)  (Standard)"]
    assert d.schluessel() == Notenschluessel.standard("sek2")
    combo = d.tabelle.cellWidget(0, 1)
    assert combo.count() == 16 and combo.itemText(0).startswith("15")


def test_muendlich_und_noten_in_punkten(kurs):
    from test_ui_muendlich import tippe

    from notenverwaltung.ui.seiten.muendlich_tab import FEST, MuendlichTab
    from notenverwaltung.ui.seiten.noten_tab import NotenTab

    sd, jahr, g, ids = kurs
    t = MuendlichTab()
    t.show()
    t.zeige(sd, jahr, g)
    assert "Punkte 0–15" in t.hilfe.text()
    t.raster.setCurrentIndex(t.modell.index(0, FEST))
    tippe(t.raster, "12")
    tippe(t.raster, "9,5")                               # → 10
    m = t.modell
    assert m.data(m.index(0, FEST)) == "12" and m.data(m.index(1, FEST)) == "10"
    t.raster.setCurrentIndex(m.index(0, FEST + 1))
    tippe(t.raster, "16")
    assert "0 und 15" in t.meldung.text()
    n = NotenTab()
    n._zeitraum_gewaehlt = True
    n.zeitraum.setCurrentIndex(n.zeitraum.findData(1))
    n.zeige(sd, jahr, g)
    koepfe = [n.tabelle.horizontalHeaderItem(c).text() for c in range(n.tabelle.columnCount())]
    assert "ZP10" not in koepfe
    spalte = koepfe.index("Q1\nVorschlag")
    assert n.tabelle.item(0, spalte).text().startswith("12")
    n.tabelle.item(0, koepfe.index("1. Hj.\nZeugnis")).setText("11")
    assert Zeugnis(sd.v).festgesetzt(g.id)[(ids[0], "hj1")] == P(11)
    n.tabelle.item(0, koepfe.index("1. Hj.\nZeugnis")).setText("2+")
    assert "Punkte" in n.meldung.text()
    assert "unter 5 P." in n.spiegel.text()
