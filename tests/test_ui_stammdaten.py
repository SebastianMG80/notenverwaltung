"""Oberfläche der Stammdaten: Schuljahr, Schüler:innen, Lerngruppen, Navigation."""

from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from notenverwaltung.modell.stammdaten import Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank


@pytest.fixture
def fenster(app, tmp_path, schnelle_kdf):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    db, _ = Datenbank.neu(tmp_path / "ui", "Testpasswort1")
    f = Hauptfenster()
    f.setze_datenbank(db)
    yield f
    f.schliesse_datenbank()


def _jahr_anlegen(f):
    from notenverwaltung.ui.stammdaten_dialoge import SchuljahrDialog

    d = SchuljahrDialog(f.sd)
    d.bezeichnung.setText("2026/27")
    d.beginn.setze(date(2026, 8, 1))
    d.wechsel.setze(date(2027, 2, 1))
    d.ende.setze(date(2027, 7, 31))
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    f.wechsle_schuljahr(d.ergebnis)
    return d.ergebnis


def _schueler(f, jahr, nach, vor, klasse):
    from notenverwaltung.ui.stammdaten_dialoge import SchuelerDialog

    d = SchuelerDialog(f.sd, jahr)
    d.nachname.setText(nach)
    d.vorname.setText(vor)
    d.klasse.setCurrentText(klasse)
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    return d.ergebnis


def _navigation(f):
    texte = []
    for i in range(f.navigation.topLevelItemCount()):
        oben = f.navigation.topLevelItem(i)
        texte.append(oben.text(0))
        texte += ["  " + oben.child(j).text(0) for j in range(oben.childCount())]
    return texte


def test_ohne_schuljahr_erscheint_uebersicht(fenster):
    assert fenster.jahr is None
    assert fenster.stapel.currentWidget() is fenster.uebersicht
    assert fenster.uebersicht.anlegen.isVisible() or not fenster.isVisible()
    assert not fenster.a_neue_lerngruppe.isEnabled()


def test_schuljahr_dialog_prueft(fenster):
    from notenverwaltung.ui.stammdaten_dialoge import SchuljahrDialog

    d = SchuljahrDialog(fenster.sd)
    d.wechsel.setze(date(2030, 1, 1))
    d._ok()
    assert "Halbjahreswechsel" in d.meldung.text()
    assert d.result() != d.DialogCode.Accepted


def test_schuljahr_dialog_quartale(fenster):
    from notenverwaltung.ui.stammdaten_dialoge import SchuljahrDialog

    jahr = _jahr_anlegen(fenster)
    assert jahr.quartal2 is None and jahr.quartal4 is None
    d = SchuljahrDialog(fenster.sd, jahr)
    assert d.quartale_auto.isChecked() and not d.quartal2.isEnabled()
    assert d.quartal2.wert() == date(2026, 11, 1) and d.quartal4.wert() == date(2027, 5, 3)
    d.wechsel.setze(date(2027, 1, 25))                     # automatisch: Quartalswechsel wandern mit
    assert d.quartal2.wert() == jahr.__class__(0, "", jahr.beginn, date(2027, 1, 25), jahr.ende).quartal2_ab
    d.wechsel.setze(date(2027, 2, 1))
    d.quartale_auto.setChecked(False)
    d.quartal2.setze(date(2026, 10, 26))
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    neu = fenster.sd.schuljahr(jahr.id)
    assert neu.quartal2 == date(2026, 10, 26) and neu.quartal4 == date(2027, 5, 3)
    d = SchuljahrDialog(fenster.sd, neu)
    assert not d.quartale_auto.isChecked() and d.quartal2.wert() == date(2026, 10, 26)
    d.quartal2.setze(date(2027, 3, 1))                     # nicht im 1. Halbjahr
    d._ok()
    assert "2. Quartal" in d.meldung.text() and d.result() != d.DialogCode.Accepted


def test_ablauf_jahr_schueler_lerngruppe(fenster):
    from notenverwaltung.ui.stammdaten_dialoge import LerngruppeDialog, MitgliederDialog

    jahr = _jahr_anlegen(fenster)
    assert fenster.stapel.currentWidget() is fenster.seite_jahr
    assert fenster.a_neue_lerngruppe.isEnabled()
    for nach, vor, kl in [("Muster", "Hans", "8.4"), ("Adler", "Anna", "8.4"), ("Zorn", "Zoe", "8.2"),
                          ("Kurs", "Karl", "9.1")]:
        _schueler(fenster, jahr, nach, vor, kl)

    # Klasse-Fach: Bezeichnung und Kürzel werden vorgeschlagen, Klasse wird übernommen
    d = LerngruppeDialog(fenster.sd, jahr)
    d.ist_klasse.setChecked(True)
    d.klasse.setCurrentText("8.4")
    d.fach.setCurrentText("Deutsch")
    assert d.bezeichnung.text() == "8.4 Deutsch"
    assert d.kuerzel.text() == "D"
    assert d.jahrgang.value() == 8
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    deutsch = d.ergebnis
    assert [m.schueler.nachname for m in fenster.sd.mitglieder(deutsch.id)] == ["Adler", "Muster"]

    # Kurs mit E-Niveau
    d = LerngruppeDialog(fenster.sd, jahr)
    d.ist_kurs.setChecked(True)
    d.fach.setCurrentText("Mathematik")
    d.jahrgang.setValue(8)
    d.niveau.setCurrentIndex(d.niveau.findData("E"))
    assert d.bezeichnung.text() == "M8E"
    d.bezeichnung.selectAll()
    QTest.keyClicks(d.bezeichnung, "M8.3E")  # wie von Hand getippt
    d.niveau.setCurrentIndex(d.niveau.findData("G"))
    assert d.bezeichnung.text() == "M8.3E"  # von Hand geändert → kein neuer Vorschlag
    d.niveau.setCurrentIndex(d.niveau.findData("E"))
    d._ok()
    kurs = d.ergebnis
    assert kurs.niveau == "E" and kurs.art == "kurs"

    # Mitglieder für den Kurs: standardmäßig nur der eigene Jahrgang
    m = MitgliederDialog(fenster.sd, jahr, kurs)
    assert sorted(r for r in m.tabelle.zeilen_daten) == sorted(
        e.schueler.id for e in fenster.sd.schueler_im_jahr(jahr.id) if e.jahrgang == 8)
    m.tabelle.selectAll()
    m._ok()
    assert m.hinzugefuegt == 3

    fenster._navigation_fuellen()
    nav = _navigation(fenster)
    assert nav[:3] == ["Schuljahr 2026/27", "Schüler:innen", "Lerngruppen"]
    assert "  8.4 Deutsch" in nav and "  M8.3E" in nav


def test_lerngruppe_oberstufe(fenster):
    from notenverwaltung.ui.stammdaten_dialoge import LerngruppeDialog, SchuelerDialog

    jahr = _jahr_anlegen(fenster)
    d = SchuelerDialog(fenster.sd, jahr)
    d.klasse.setCurrentText("Q1")
    assert d.jahrgang.value() == 12 and d.jahrgang.text() == "12 (Q1)"
    d = LerngruppeDialog(fenster.sd, jahr)
    d.show()
    d.ist_kurs.setChecked(True)
    d.fach.setCurrentText("Deutsch")
    assert d.niveau.isVisible() and not d.kursart.isVisible()
    d.jahrgang.setValue(12)
    assert not d.niveau.isVisible() and d.kursart.isVisible() and "Punkte" in d.notensystem.text()
    d.kursart.setCurrentIndex(d.kursart.findData("LK"))
    assert d.bezeichnung.text() == "D-LK"
    d._ok()
    assert d.result() == d.DialogCode.Accepted, d.meldung.text()
    g = d.ergebnis
    assert (g.notensystem, g.kursart, g.jahrgang, g.niveau) == ("sek2", "LK", 12, "")
    # Mit Noten kein Wechsel mehr zwischen Sek I und Oberstufe
    from notenverwaltung.modell.muendlich import Muendlich
    from notenverwaltung.modell.noten import Punkte

    sid = fenster.sd.lege_schueler_an(jahr.id, "Kaya", "Ela", "Q1").id
    fenster.sd.fuege_hinzu(g.id, [sid])
    mu = Muendlich(fenster.sd.v)
    mu.setze_note(mu.zeitraeume(g.id)[0].id, sid, Punkte.aus_punkte(11))
    d = LerngruppeDialog(fenster.sd, jahr, g)
    assert d.jahrgang.value() == 12 and d.kursart.currentData() == "LK"
    d.jahrgang.setValue(10)
    d._ok()
    assert "nicht mehr gewechselt" in d.meldung.text() and d.result() != d.DialogCode.Accepted


def test_lerngruppenseite_sortierung_und_verschieben(fenster):
    jahr = _jahr_anlegen(fenster)
    from notenverwaltung.modell.stammdaten import Lerngruppe

    g = fenster.sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M8.3E", "Mathematik", "kurs", 8, "M", "E"))
    ids = [_schueler(fenster, jahr, n, "x", k).id for n, k in [("B", "8.2"), ("A", "8.4"), ("C", "8.1")]]
    fenster.sd.fuege_hinzu(g.id, ids)
    fenster._navigation_fuellen(("gruppe", g.id))
    seite = fenster.seite_gruppe
    assert fenster.stapel.currentWidget() is seite
    tab = seite.mitglieder
    assert [tab.tabelle.item(r, 1).text() for r in range(3)] == ["C", "B", "A"]  # Klasse → Alphabet
    assert not tab.hoch.isEnabled()
    tab.sortierung.setCurrentIndex(tab.sortierung.findData("alphabet"))
    assert [tab.tabelle.item(r, 1).text() for r in range(3)] == ["A", "B", "C"]
    tab.sortierung.setCurrentIndex(tab.sortierung.findData("eigene"))
    tab.tabelle.selectRow(2)
    assert tab.hoch.isEnabled()
    tab._verschieben(-1)
    assert [tab.tabelle.item(r, 1).text() for r in range(3)] == ["A", "C", "B"]
    assert fenster.sd.lerngruppe(g.id).sortierung == "eigene"


def test_schuelerseite_filter_und_abgang(fenster):
    from notenverwaltung.ui.stammdaten_dialoge import AbgangDialog

    jahr = _jahr_anlegen(fenster)
    _schueler(fenster, jahr, "Muster", "Hans", "8.4")
    _schueler(fenster, jahr, "Zorn", "Zoe", "8.2")
    fenster._navigation_fuellen(("schueler", None))
    seite = fenster.seite_schueler
    assert seite.tabelle.rowCount() == 2
    seite.filter_klasse.setCurrentIndex(seite.filter_klasse.findData("8.4"))
    assert seite.tabelle.rowCount() == 1
    seite.filter_klasse.setCurrentIndex(0)
    seite.suche.setText("zo")
    assert seite.tabelle.rowCount() == 1
    eintrag = fenster.sd.schueler_im_jahr(jahr.id, "8.2")[0]
    d = AbgangDialog(fenster.sd, jahr, eintrag)
    d.datum.setze(date(2027, 1, 31))
    d._ok()
    assert fenster.sd.schueler_im_jahr(jahr.id, "8.2")[0].abgang == date(2027, 1, 31)


def test_schuljahr_wechseln(fenster):
    jahr = _jahr_anlegen(fenster)
    alt = fenster.sd.lege_schuljahr_an("2025/26", date(2025, 8, 1), date(2026, 2, 1), date(2026, 7, 31))
    fenster._schuljahr_menue_fuellen()
    texte = [a.text() for a in fenster.m_schuljahr.actions() if a.text()]
    assert texte[:2] == ["2026/27", "2025/26"]
    fenster.wechsle_schuljahr(alt)
    assert fenster.navigation.topLevelItem(0).text(0) == "Schuljahr 2025/26"
    fenster.wechsle_schuljahr(jahr)


def test_daten_bleiben_nach_schliessen(fenster, tmp_path):
    from notenverwaltung.speicher.tresor import PASSWORT

    jahr = _jahr_anlegen(fenster)
    _schueler(fenster, jahr, "Muster", "Hans", "8.4")
    pfad = fenster.db.pfad
    fenster.schliesse_datenbank()
    db = Datenbank.oeffnen(pfad, PASSWORT, "Testpasswort1")
    assert Stammdaten(db.verbindung).schueler_im_jahr(jahr.id)[0].schueler.nachname == "Muster"
    fenster.setze_datenbank(db)  # Fixture schließt wieder
    assert fenster.jahr is not None
    assert fenster.navigation.currentItem().data(0, Qt.ItemDataRole.UserRole) == ("jahr", None)
