"""Oberfläche Klassenarbeiten: Anlegen, Punkteraster mit Tastatur, Vermerke, Notenschlüssel."""

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.noten import Note, Notenschluessel
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "ui", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    ids = [sd.lege_schueler_an(jahr.id, n, "x", "9.1").id for n in ("Adler", "Becker", "Celik")]
    sd.fuege_hinzu(g.id, ids)
    yield db, sd, jahr, g, ids
    db.schliessen(speichern=False)


def tippe(raster, text: str) -> None:
    """Wie am Rechner: erstes Zeichen öffnet das Eingabefeld, Rest hinein, Enter."""
    from PySide6.QtWidgets import QApplication, QLineEdit

    QApplication.processEvents()  # alte, geschlossene Eingabefelder entsorgen
    QTest.keyClicks(raster, text[0])
    editor = next((e for e in raster.findChildren(QLineEdit) if e.isVisible()), None)
    assert editor is not None, "Eingabefeld wurde nicht geöffnet"
    QTest.keyClicks(editor, text[1:])
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()  # Qt übernimmt die Eingabe verzögert über die Ereignisschleife


def _tab(umgebung):
    from notenverwaltung.ui.seiten.arbeiten_tab import ArbeitenTab

    db, sd, jahr, g, ids = umgebung
    t = ArbeitenTab()
    t.resize(1200, 600)
    t.show()
    t.zeige(sd, jahr, g)
    return t


def test_arbeit_anlegen_ueber_dialog(umgebung):
    from notenverwaltung.ui.arbeit_dialoge import ArbeitDialog

    db, sd, jahr, g, ids = umgebung
    ar = Arbeiten(db.verbindung)
    d = ArbeitDialog(ar, jahr, g)
    assert d.titel.text() == "1. Klassenarbeit"
    assert d.aufgaben.tabelle.rowCount() == 4
    d.aufgaben.neue_teilaufgabe()   # „4“ → „4a“ + „b“
    d.aufgaben.neue_teilaufgabe()   # → „c“
    d.aufgaben.neue_aufgabe()       # → „5“
    assert [d.aufgaben.tabelle.item(r, 0).text() for r in range(7)] == ["1", "2", "3", "4a", "b", "c", "5"]
    d.datum.setze(date(2026, 11, 10))
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    a = d.ergebnis
    assert [x.bezeichnung for x in ar.aufgaben(a.id)][-1] == "5"
    assert ar.hoechstpunkte(a.id) == 5 * 3 + 5 + 1 + 1 + 1  # 4 wird zu 4a (5), b, c je 1, neue 5 mit 1


def test_dialog_fehler_bei_punkten(umgebung):
    from notenverwaltung.ui.arbeit_dialoge import ArbeitDialog

    db, sd, jahr, g, ids = umgebung
    d = ArbeitDialog(Arbeiten(db.verbindung), jahr, g)
    d.aufgaben.tabelle.item(1, 1).setText("viel")
    d._ok()
    assert "keine Punktzahl" in d.meldung.text()
    assert Arbeiten(db.verbindung).arbeiten(g.id) == []  # nichts halb angelegt


def test_raster_eingabe_mit_tastatur(umgebung):
    from notenverwaltung.ui.seiten.arbeiten_tab import FESTE_SPALTEN, SP_NOTE, SP_SUMME

    db, sd, jahr, g, ids = umgebung
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 4), ("2", 6)])
    t = _tab(umgebung)
    r = t.raster
    m = t.modell
    assert r.currentIndex().row() == 0 and r.currentIndex().column() == FESTE_SPALTEN
    # Adler: 4 Enter 5,5 Enter → springt in die nächste Zeile
    tippe(r, "4")
    assert r.currentIndex().column() == FESTE_SPALTEN + 1
    tippe(r, "5,5")
    assert (r.currentIndex().row(), r.currentIndex().column()) == (1, FESTE_SPALTEN)
    assert m.data(m.index(0, SP_SUMME)) == "9,5"
    assert m.data(m.index(0, SP_NOTE)) == "1"  # 9,5/10 = 95 % → 1 (ab 85 %), 1+ erst ab 105 %
    # … Kontrolle direkt über das Modell
    assert ar.ergebnisse(a.id)[0].note == Notenschluessel.standard().note(9.5, 10)
    # Ungültig: zu viele Punkte → Meldung, Cursor bleibt stehen
    tippe(r, "7")
    assert "höchstens 4" in t.meldung.text()
    assert (r.currentIndex().row(), r.currentIndex().column()) == (1, FESTE_SPALTEN)
    assert ar.ergebnisse(a.id)[1].summe is None
    # Richtung „nach unten“
    t.richtung.setCurrentIndex(1)
    tippe(r, "3")
    assert (r.currentIndex().row(), r.currentIndex().column()) == (2, FESTE_SPALTEN)
    assert t.meldung.text() == ""
    # Entf leert
    r.setCurrentIndex(m.index(1, FESTE_SPALTEN))
    QTest.keyClick(r, Qt.Key.Key_Delete)
    assert ar.ergebnisse(a.id)[1].summe is None


def test_notenspiegel_und_vermerke(umgebung):
    db, sd, jahr, g, ids = umgebung
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    x = ar.aufgaben(a.id)[0]
    ar.setze_punkte(x.id, ids[0], 10)
    ar.setze_punkte(x.id, ids[1], 3)
    t = _tab(umgebung)
    assert "Unter 4: <b>50 %" in t.zusammenfassung.text()
    t._teilnahme(ids[2], a.id, status="fehlt")
    t._teilnahme(ids[1], a.id, note_manuell=Note.aus_kurz("4"))
    from notenverwaltung.ui.seiten.arbeiten_tab import SP_NOTE

    m = t.modell
    assert m.data(m.index(1, SP_NOTE)) == "4*"
    assert "festgesetzt" in m.data(m.index(1, SP_NOTE), Qt.ItemDataRole.ToolTipRole)
    assert m.data(m.index(2, m.spalte_vermerk)) == "fehlt"
    assert "Unter 4: <b>0 %" in t.zusammenfassung.text()


def test_note_direkt_eintippen(umgebung):
    """Nachschreiber:innen: Note ohne Punkte direkt in die Notenspalte tippen."""
    from notenverwaltung.ui.seiten.arbeiten_tab import SP_NOTE

    db, sd, jahr, g, ids = umgebung
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, ids[0], 10)
    ar.setze_teilnahme(a.id, ids[1], status="nachschreiben")
    t = _tab(umgebung)
    r, m = t.raster, t.modell
    assert m.flags(m.index(1, SP_NOTE)) & Qt.ItemFlag.ItemIsEditable
    assert not m.flags(m.index(len(m.ergebnisse), SP_NOTE)) & Qt.ItemFlag.ItemIsEditable   # Durchschnittszeile
    r.setCurrentIndex(m.index(1, SP_NOTE))
    tippe(r, "3-")
    e = ar.ergebnisse(a.id)[1]
    assert e.summe is None and e.note == Note.aus_kurz("3-") and e.status == ""   # Vermerk erledigt
    assert m.data(m.index(1, SP_NOTE)) == "3-*"
    assert (r.currentIndex().row(), r.currentIndex().column()) == (2, SP_NOTE)   # Enter: eine Zeile tiefer
    tippe(r, "gut")
    assert "keine Note" in t.meldung.text() and ar.ergebnisse(a.id)[2].note is None
    # gleiche Note wie berechnet → keine Festsetzung; andere → Festsetzung mit *
    r.setCurrentIndex(m.index(0, SP_NOTE))
    tippe(r, "1")
    assert ar.ergebnisse(a.id)[0].note_manuell is None and m.data(m.index(0, SP_NOTE)) == "1"
    r.setCurrentIndex(m.index(0, SP_NOTE))
    tippe(r, "2")
    assert m.data(m.index(0, SP_NOTE)) == "2*"
    assert m.data(m.index(0, SP_NOTE), Qt.ItemDataRole.EditRole) == "2"
    # Entf hebt die Festsetzung auf, die Punkte bleiben
    r.setCurrentIndex(m.index(0, SP_NOTE))
    QTest.keyClick(r, Qt.Key.Key_Delete)
    e = ar.ergebnisse(a.id)[0]
    assert e.note_manuell is None and e.summe == 10 and m.data(m.index(0, SP_NOTE)) == "1"


def test_ausgetretene_ausgeblendet(umgebung):
    db, sd, jahr, g, ids = umgebung
    sd.setze_zeitraum(g.id, ids[2], None, date(2026, 10, 1))
    Arbeiten(db.verbindung).lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    t = _tab(umgebung)
    assert len(t.modell.ergebnisse) == 2
    t.alle.setChecked(True)
    assert len(t.modell.ergebnisse) == 3


def test_schluessel_dialog(umgebung, monkeypatch):
    from notenverwaltung.ui import arbeit_dialoge

    db, *_ = umgebung
    ar = Arbeiten(db.verbindung)
    d = arbeit_dialoge.SchluesselDialog(ar, Notenschluessel.standard(), 52)
    assert d.tabelle.rowCount() == 16
    assert d.tabelle.item(1, 2).text() == "10"
    assert "nicht erreichbar" in d.tabelle.item(15, 2).text()
    d.tabelle.cellWidget(1, 0).setValue(15)
    assert d.tabelle.item(1, 2).text() == "8"   # 52·0,15 = 7,8 → 8
    d.raster.setCurrentIndex(d.raster.findData(0.5))
    assert d.tabelle.item(3, 2).text() == "20"  # 52·0,38 = 19,76 → 20 (auch bei halben Punkten)
    d.tabelle.cellWidget(2, 0).setValue(20.5)
    assert d.tabelle.item(2, 2).text() == "10,5"  # 52·0,205 = 10,66 → 10,5
    monkeypatch.setattr(arbeit_dialoge.QInputDialog, "getText", staticmethod(lambda *a, **k: ("Mein Schlüssel", True)))
    monkeypatch.setattr(arbeit_dialoge, "frage", lambda *a, **k: False)
    d._als_vorlage()
    assert "Mein Schlüssel" in [v.name for v in ar.vorlagen()]
    d._ok()
    assert d.ergebnis.raster == 0.5 and d.ergebnis.stufen[1].prozent == 15
    # Fehler: Note bei höherem Prozent schlechter
    d.tabelle.cellWidget(2, 1).setCurrentIndex(d.tabelle.cellWidget(2, 1).findData("6"))
    assert "bessere Note" in d.meldung.text()


def test_reiter_nur_bei_schriftlichen(umgebung):
    from notenverwaltung.ui.seiten.stammdaten_seiten import LerngruppeSeite

    db, sd, jahr, g, ids = umgebung
    ek = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "9.1 EK", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    s = LerngruppeSeite()
    s.zeige(sd, jahr, g)
    assert s.reiter.isTabVisible(s.reiter.indexOf(s.arbeiten))
    s.zeige(sd, jahr, ek)
    assert not s.reiter.isTabVisible(s.reiter.indexOf(s.arbeiten))
    assert s.reiter.currentWidget() is s.muendlich  # erster sichtbarer Reiter eines mündlichen Fachs


def test_aufgabenweise_korrigieren(umgebung):
    """Enter nach unten: nach der letzten Person zur ersten der nächsten Aufgabe; Wahl gemerkt; Fortschritt."""
    from notenverwaltung.einstellungen import einstellungen
    from notenverwaltung.ui.seiten.arbeiten_tab import FESTE_SPALTEN

    db, sd, jahr, g, ids = umgebung
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 4), ("2", 6)])
    ar.setze_teilnahme(a.id, ids[1], status="fehlt")
    t = _tab(umgebung)
    t.richtung.setCurrentIndex(1)
    assert einstellungen().value("eingabe/arbeiten_nach_rechts") in (False, "false")
    r, m = t.raster, t.modell
    assert t.fortschritt.text() == "Aufgabe 1: 0 von 2 eingetragen"     # Becker fehlt
    tippe(r, "1")
    tippe(r, "2")
    tippe(r, "3")
    assert (r.currentIndex().row(), r.currentIndex().column()) == (0, FESTE_SPALTEN + 1)   # nächste Aufgabe
    r.setCurrentIndex(m.index(0, FESTE_SPALTEN))
    assert t.fortschritt.text() == "Aufgabe 1: alle 2 eingetragen ✓"
    r.setCurrentIndex(m.index(2, FESTE_SPALTEN + 1))
    tippe(r, "5")
    assert (r.currentIndex().row(), r.currentIndex().column()) == (2, FESTE_SPALTEN + 1)   # Ende: stehen bleiben
    # Umschalt+Tab am Anfang einer Zeile geht ans Ende der vorigen
    assert r.naechste_zelle(m.index(1, FESTE_SPALTEN), -1, seitlich=True) == m.index(0, FESTE_SPALTEN + 1)
    assert r.naechste_zelle(m.index(0, FESTE_SPALTEN + 1), -1, seitlich=False) == m.index(2, FESTE_SPALTEN)
    # ein neuer Reiter übernimmt die gemerkte Richtung
    t2 = _tab(umgebung)
    assert t2.richtung.currentIndex() == 1 and t2.raster.nach_rechts is False
