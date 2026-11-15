"""Rückgängig / Wiederholen: an der Datenbank, für jede Art von Änderung, ohne Spuren in der Datei."""

from datetime import date

import pytest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.jahreswechsel import fuehre_aus, plane
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher import verlauf as vl
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter


@pytest.fixture
def welt(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "v", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M8.3", "Mathematik", "kurs", 8, ""))
    ids = [sd.lege_schueler_an(jahr.id, f"Name{i}", f"Vor{i}", "8.4").id for i in range(4)]
    sd.fuege_hinzu(g.id, ids)
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "1. Klassenarbeit", date(2026, 11, 10), [("1", 10), ("2", 10)])
    db.verlauf.leeren()            # das Anlegen gehört nicht zu den Tests
    yield db, sd, jahr, g, ids, ar, a
    db.schliessen(speichern=False)


def stand(db) -> dict:
    """Der vollständige Inhalt aller Tabellen (zum Vergleich vorher/nachher)."""
    v = db.verbindung
    tabellen = [r[0] for r in v.execute("SELECT name FROM sqlite_master WHERE type = 'table' "
                                        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {t: sorted(v.execute(f'SELECT rowid, * FROM "{t}"').fetchall(), key=repr) for t in tabellen}


def _p(ar, a, i: int) -> dict:
    return {k: v for k, v in ar.ergebnisse(a.id)[i].punkte.items() if v is not None}


def test_punkte_rueckgaengig_und_wiederholen(welt):
    db, sd, jahr, g, ids, ar, a = welt
    vl_ = db.verlauf
    x1, x2 = ar.aufgaben(a.id)
    assert not vl_.kann_rueckgaengig and vl_.rueckgaengig() is None
    ar.setze_punkte(x1.id, ids[0], 7)
    vl_.abschliessen()
    ar.setze_punkte(x1.id, ids[0], 8)            # Änderung (ON CONFLICT … DO UPDATE)
    ar.setze_punkte(x2.id, ids[0], 3)            # zwei Zellen ohne Eingabe dazwischen: ein Schritt
    assert vl_.text_rueckgaengig() == "Punkte" and len(vl_.rueck) == 2
    assert vl_.rueckgaengig() == "Punkte"
    assert _p(ar, a, 0) == {x1.id: 7}
    assert vl_.kann_wiederholen and vl_.text_wiederholen() == "Punkte"
    assert vl_.rueckgaengig() == "Punkte"
    assert _p(ar, a, 0) == {}
    assert vl_.rueckgaengig() is None
    assert vl_.wiederholen() == "Punkte" and _p(ar, a, 0) == {x1.id: 7}
    assert vl_.wiederholen() == "Punkte" and _p(ar, a, 0) == {x1.id: 8, x2.id: 3}
    assert vl_.wiederholen() is None


def test_neue_aenderung_verwirft_wiederholen(welt):
    db, sd, jahr, g, ids, ar, a = welt
    x1, _ = ar.aufgaben(a.id)
    ar.setze_punkte(x1.id, ids[0], 7)
    db.verlauf.rueckgaengig()
    ar.setze_punkte(x1.id, ids[1], 5)
    assert not db.verlauf.kann_wiederholen and db.verlauf.wiederholen() is None
    assert _p(ar, a, 1) == {x1.id: 5}


def test_geloeschte_arbeit_kommt_vollstaendig_zurueck(welt):
    """Löschen mit Kaskade (Aufgaben, Punkte, Noten) – Rückgängig stellt alles bitgenau wieder her."""
    db, sd, jahr, g, ids, ar, a = welt
    x1, x2 = ar.aufgaben(a.id)
    for i, sid in enumerate(ids):
        ar.setze_punkte(x1.id, sid, i + 3)
        ar.setze_punkte(x2.id, sid, 2 * i)
    ar.setze_teilnahme(a.id, ids[2], note_manuell=Note.aus_kurz("2-"), kommentar="Gut gemacht")
    db.verlauf.abschliessen()
    vorher = stand(db)
    ar.loesche_arbeit(a.id)
    assert ar.arbeiten(g.id) == []
    assert db.verlauf.rueckgaengig() == "Klassenarbeit"
    assert stand(db) == vorher
    db.verlauf.wiederholen()
    assert ar.arbeiten(g.id) == []
    db.verlauf.rueckgaengig()
    assert stand(db) == vorher


def test_lerngruppe_und_schueler(welt):
    db, sd, jahr, g, ids, ar, a = welt
    vorher = stand(db)
    sd.loesche_lerngruppe(g.id)
    db.verlauf.abschliessen()
    sd.lege_schueler_an(jahr.id, "Neu", "Nora", "8.4")
    assert db.verlauf.rueckgaengig() == "Schüler:in"
    assert db.verlauf.rueckgaengig() == "Lerngruppe"
    assert stand(db) == vorher


def test_schuljahreswechsel_ist_ein_schritt(welt):
    db, sd, jahr, g, ids, ar, a = welt
    vorher = stand(db)
    neu = sd.lege_schuljahr_an("2027/28", date(2027, 8, 1), date(2028, 2, 1), date(2028, 7, 31))
    plan = plane(sd, jahr.id, {"8.4": "9.4"})
    for gp in plan.gruppen:
        gp.uebernehmen = True
    fuehre_aus(sd, plan, neu)
    assert db.verlauf.rueckgaengig() == "Schuljahr"
    assert stand(db) == vorher
    db.verlauf.wiederholen()
    assert len(sd.schuljahre()) == 2 and sd.klassen(neu.id) == ["9.4"]


def test_automatische_zeitraeume_kein_schritt(welt):
    db, sd, jahr, g, ids, ar, a = welt
    mu = Muendlich(db.verbindung)
    assert len(mu.zeitraeume(g.id)) == 4                    # legt die Quartale selbst an
    assert not db.verlauf.kann_rueckgaengig
    z = mu.zeitraeume(g.id)[0]
    mu.setze_note(z.id, ids[0], Note.aus_kurz("2+"))
    assert db.verlauf.rueckgaengig() == "mündliche Note" and mu.noten(g.id) == {}
    # ohne_verlauf auf einer Verbindung ohne Verlauf schadet nicht
    import sqlite3
    with vl.ohne_verlauf(sqlite3.connect(":memory:")):
        pass


def test_hoechstens_max_schritte(welt, monkeypatch):
    db, sd, jahr, g, ids, ar, a = welt
    monkeypatch.setattr(vl, "MAX_SCHRITTE", 3)
    x1, _ = ar.aufgaben(a.id)
    for p in range(6):
        ar.setze_punkte(x1.id, ids[0], p)
        db.verlauf.abschliessen()
    assert len(db.verlauf.rueck) == 3
    assert db.verbindung.execute("SELECT COUNT(*) FROM temp.verlauf_log").fetchone()[0] == 3
    for _ in range(5):
        db.verlauf.rueckgaengig()
    assert _p(ar, a, 0) == {x1.id: 2}       # älter geht nicht


def test_fehler_beim_umkehren(welt):
    db, sd, jahr, g, ids, ar, a = welt
    x1, _ = ar.aufgaben(a.id)
    ar.setze_punkte(x1.id, ids[0], 4)
    db.verlauf.abschliessen()
    db.verbindung.execute("UPDATE temp.verlauf_log SET befehl = 'kaputt'")
    with pytest.raises(vl.VerlaufFehler):
        db.verlauf.rueckgaengig()
    assert _p(ar, a, 0) == {x1.id: 4} and len(db.verlauf.rueck) == 1


def test_verlauf_nicht_in_der_datei(welt, tmp_path):
    db, sd, jahr, g, ids, ar, a = welt
    x1, _ = ar.aufgaben(a.id)
    ar.setze_punkte(x1.id, ids[0], 4)
    db.speichern()
    vorher = stand(db)
    db.schliessen()
    wieder = Datenbank.oeffnen(db.pfad, "passwort", "Testpasswort1")
    try:
        namen = {r[0] for r in wieder.verbindung.execute("SELECT name FROM sqlite_master")}
        assert not any("verlauf" in n for n in namen)
        assert stand(wieder) == vorher and not wieder.verlauf.kann_rueckgaengig
    finally:
        wieder.schliessen(speichern=False)


def test_oberflaeche_strg_z(app, tmp_path, schnelle_kdf):
    """Strg+Z im Hauptfenster: Punkte zurück, Arbeit und Zelle bleiben gewählt; Menütexte nennen den Schritt."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from notenverwaltung.ui.hauptfenster import Hauptfenster

    db, _ = Datenbank.neu(tmp_path / "h", "Testpasswort1")
    f = Hauptfenster()
    f.setze_datenbank(db)
    sd = f.sd
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    f.wechsle_schuljahr(jahr)
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M"))
    sd.fuege_hinzu(g.id, [sd.lege_schueler_an(jahr.id, f"N{i}", f"V{i}", "9a").id for i in range(5)])
    ar = Arbeiten(db.verbindung)
    ar.lege_arbeit_an(g.id, "Erste", date(2026, 9, 1), [("1", 10)])
    zweite = ar.lege_arbeit_an(g.id, "Zweite", date(2026, 10, 1), [("1", 10), ("2", 10)])
    f._navigation_fuellen(("gruppe", g.id))
    f.show()
    tab = f.seite_gruppe.arbeiten
    tab.auswahl.setCurrentIndex(tab.auswahl.findData(zweite.id))
    db.verlauf.leeren()
    m = tab.modell
    zelle = m.index(2, m.eingabe_bereich()[0] + 1)
    m.setData(zelle, "7")
    QTest.keyClick(tab.raster, Qt.Key.Key_Down)             # Eingabe: Schritt abgeschlossen
    tab.raster.setCurrentIndex(zelle)
    f._bearbeiten_menue()
    assert f.a_rueckgaengig.text() == "&Rückgängig: Punkte" and f.a_wiederholen.text() == "&Wiederholen"
    f.activateWindow()
    QTest.qWaitForWindowActive(f)
    tab.raster.setFocus()
    QTest.keyClick(tab.raster, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    assert m.data(m.index(2, zelle.column())) in ("", None)
    assert tab.auswahl.currentData() == zweite.id and tab.raster.currentIndex().row() == 2
    assert tab.raster.currentIndex().column() == zelle.column()
    assert "Rückgängig gemacht: Punkte" in f.statusBar().currentMessage()
    QTest.keyClick(tab.raster, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert m.data(m.index(2, zelle.column())) == "7"
    # gelöschte Lerngruppe kommt zurück, die Navigation zeigt sie wieder
    sd.loesche_lerngruppe(g.id)
    f._gruppe_geloescht()
    f.rueckgaengig()
    assert [x.id for x in sd.lerngruppen(jahr.id)] == [g.id]
    f.rueckgaengig()
    f.rueckgaengig()
    f.rueckgaengig()                                         # bis vor das Anlegen: nichts mehr da
    f.schliesse_datenbank()
