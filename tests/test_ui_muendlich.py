"""Reiter „Mündlich“: Eingabe, gesperrte Zeiträume, Halbjahresmittel, Zeiträume-Dialog."""

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "m", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "9.1 EK", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    ids = [sd.lege_schueler_an(jahr.id, n, "x", "9.1").id for n in ("A", "B")]
    sd.fuege_hinzu(g.id, ids)
    yield sd, jahr, g, ids
    db.schliessen(speichern=False)


def tippe(raster, text):
    from PySide6.QtWidgets import QApplication, QLineEdit

    QApplication.processEvents()
    QTest.keyClicks(raster, text[0])
    editor = next(e for e in raster.findChildren(QLineEdit) if e.isVisible())
    QTest.keyClicks(editor, text[1:])
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()


def test_eingabe_nach_unten_und_schnitt(umgebung):
    from notenverwaltung.ui.seiten.muendlich_tab import FEST, MuendlichTab

    sd, jahr, g, ids = umgebung
    t = MuendlichTab()
    t.show()
    t.zeige(sd, jahr, g)
    m = t.modell
    assert m.columnCount() == FEST + 4 + 2
    t.raster.setCurrentIndex(m.index(0, FEST))
    tippe(t.raster, "2+")
    assert (t.raster.currentIndex().row(), t.raster.currentIndex().column()) == (1, FEST)  # nach unten
    tippe(t.raster, "1,7")
    t.raster.setCurrentIndex(m.index(0, FEST + 1))
    tippe(t.raster, "3")
    assert m.data(m.index(0, FEST + 4)) == "2,35"      # Ø 1. Hj. aus 1,7 und 3
    assert m.data(m.index(1, FEST)) == "2+"            # 1,7 → 2+
    t.raster.setCurrentIndex(m.index(0, FEST + 2))
    tippe(t.raster, "gut")
    assert "keine Note" in t.meldung.text()


def test_gesperrte_zeitraeume(umgebung):
    from notenverwaltung.ui.seiten.muendlich_tab import FEST, MuendlichTab

    sd, jahr, g, ids = umgebung
    sd.abgang(ids[1], jahr.id, date(2026, 9, 30))
    t = MuendlichTab()
    t.zeige(sd, jahr, g)
    m = t.modell
    assert m.flags(m.index(1, FEST)) & Qt.ItemFlag.ItemIsEditable          # 1. Quartal: noch da
    assert not m.flags(m.index(1, FEST + 1)) & Qt.ItemFlag.ItemIsEditable  # danach gesperrt
    assert m.data(m.index(1, FEST + 1)) == "—"


def test_zeitraeume_dialog_teilen(umgebung, monkeypatch):
    from notenverwaltung.ui.seiten import muendlich_tab

    sd, jahr, g, ids = umgebung
    mu = Muendlich(sd.v)
    d = muendlich_tab.ZeitraeumeDialog(mu, jahr, g)
    assert d.tabelle.rowCount() == 4
    d.tabelle.setCurrentCell(0, 0)
    monkeypatch.setattr(muendlich_tab.QInputDialog, "getInt", staticmethod(lambda *a, **k: (3, True)))
    d._teilen()
    assert d.tabelle.rowCount() == 6
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    z = mu.zeitraeume(g.id)
    assert [x.bezeichnung for x in z][:3] == ["1. Quartal (1)", "1. Quartal (2)", "1. Quartal (3)"]
    assert z[0].beginn == jahr.beginn and z[2].ende < z[3].beginn  # lückenlos geteilt, keine Überschneidung


def test_reiter_in_lerngruppe(umgebung):
    from notenverwaltung.ui.seiten.stammdaten_seiten import LerngruppeSeite

    sd, jahr, g, ids = umgebung
    s = LerngruppeSeite()
    s.zeige(sd, jahr, g)
    assert s.reiter.currentWidget() is s.muendlich  # mündliches Fach: erster sichtbarer Reiter
