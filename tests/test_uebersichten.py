"""Schnellsuche (Strg+F) und offene Punkte."""

from datetime import date, timedelta

import pytest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.offen import offene_punkte, stichtage
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter
from notenverwaltung.ui.schnellsuche import suche


@pytest.fixture
def welt(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "o", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31),
                                quartal2=date(2026, 10, 26))
    m = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    ek = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "EK 9", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    ids = [sd.lege_schueler_an(jahr.id, n, v, "9.2").id for n, v in
           (("Öztürk", "Ayşe"), ("Weiß", "Jörg"), ("Becker", "Anna"))]
    sd.fuege_hinzu(m.id, ids)
    sd.fuege_hinzu(ek.id, ids[:2])
    yield db, sd, jahr, m, ek, ids
    db.schliessen(speichern=False)


def _texte(punkte):
    return [p.text for p in punkte]


def test_arbeiten_und_nachschreiben(welt):
    db, sd, jahr, m, ek, ids = welt
    ar = Arbeiten(db.verbindung)
    heute = date(2026, 9, 20)
    a = ar.lege_arbeit_an(m.id, "1. KA", date(2026, 9, 10), [("1", 10), ("2", 10)])
    ar.lege_arbeit_an(m.id, "Zukunft", date(2026, 9, 30), [("1", 10)])
    x1, x2 = ar.aufgaben(a.id)
    assert "M9.3E: „1. KA“ vom 10.09. – noch keine Punkte eingetragen" in _texte(offene_punkte(db.verbindung, jahr, heute))
    ar.setze_punkte(x1.id, ids[0], 5)
    ar.setze_punkte(x2.id, ids[0], 5)
    ar.setze_punkte(x1.id, ids[1], 4)                                 # unvollständig
    ar.setze_teilnahme(a.id, ids[2], status="fehlt")
    texte = _texte(offene_punkte(db.verbindung, jahr, heute))
    assert "M9.3E: „1. KA“ vom 10.09. – 1 unvollständig" in texte
    assert "1 Arbeit muss nachgeschrieben werden" in texte
    assert not any("Zukunft" in t for t in texte)
    ar.setze_punkte(x2.id, ids[1], 4)
    ar.setze_teilnahme(a.id, ids[2], note_manuell=Note.aus_kurz("3"))   # nachgeschrieben
    assert offene_punkte(db.verbindung, jahr, heute) == []


def test_zeugnisnoten_vor_dem_stichtag(welt):
    db, sd, jahr, m, ek, ids = welt
    zg = Zeugnis(db.verbindung)
    tag = stichtage(jahr)["q1"]
    assert tag == date(2026, 10, 25) and stichtage(jahr)["hj1"] == date(2027, 1, 31)
    assert offene_punkte(db.verbindung, jahr, tag - timedelta(days=22)) == []        # noch zu früh
    punkte = offene_punkte(db.verbindung, jahr, tag - timedelta(days=10))
    assert _texte(punkte) == ["EK 9: Quartalsnote Q1 fehlt bei 2 Personen (Stichtag 25.10.2026)",
                              "M9.3E: Quartalsnote Q1 fehlt bei 3 Personen (Stichtag 25.10.2026)"]
    assert not any(p.dringend for p in punkte) and punkte[0].reiter == "noten"
    assert all(p.dringend for p in offene_punkte(db.verbindung, jahr, tag - timedelta(days=3)))
    assert all(p.dringend for p in offene_punkte(db.verbindung, jahr, tag + timedelta(days=30)))   # überfällig
    for sid in ids:
        zg.setze(m.id, sid, "q1", Note.aus_kurz("2+"))
    zg.setze(ek.id, ids[0], "q1", Note.aus_kurz("3"))
    assert _texte(offene_punkte(db.verbindung, jahr, tag)) == [
        "EK 9: Quartalsnote Q1 fehlt bei 1 Person (Stichtag 25.10.2026)"]
    sd.abgang(ids[1], jahr.id, date(2026, 10, 1))                      # vor dem Stichtag gegangen: zählt nicht
    assert offene_punkte(db.verbindung, jahr, tag) == []


def test_muendliche_zeitraeume(welt):
    db, sd, jahr, m, ek, ids = welt
    mu, zg = Muendlich(db.verbindung), Zeugnis(db.verbindung)
    z = mu.zeitraeume(ek.id)[0]                                       # 1. Quartal
    heute = z.ende + timedelta(days=1)
    mu.setze_note(z.id, ids[0], Note.aus_kurz("2"))
    texte = _texte(offene_punkte(db.verbindung, jahr, heute))
    assert "EK 9: mündliche Note „1. Quartal“ fehlt bei 1 Person" in texte or any(
        t.startswith("EK 9: mündliche Note") and "1 Person" in t for t in texte)
    zg.setze(ek.id, ids[1], "q1", Note.aus_kurz("3"))                 # Quartalsnote steht schon: nicht mehr offen
    assert not any("mündliche Note" in t for t in _texte(offene_punkte(db.verbindung, jahr, heute)))


def test_suche(welt):
    db, sd, jahr, m, ek, ids = welt
    ar = Arbeiten(db.verbindung)
    ar.lege_arbeit_an(m.id, "Bruchrechnung", date(2026, 9, 10), [("1", 10)], thema="Brüche kürzen")
    t = suche(sd, jahr, "oztu")
    assert [x.art for x in t] == ["person", "person_gruppe", "person_gruppe"]
    assert t[0].text == "Öztürk, Ayşe · 9.2" and {x.gruppe_id for x in t[1:]} == {m.id, ek.id}
    assert suche(sd, jahr, "jörg weiss")[0].schueler_id == ids[1]       # ß = ss
    assert suche(sd, jahr, "jörg weiß")[0].schueler_id == ids[1]
    assert suche(sd, jahr, "JORG")[0].schueler_id == ids[1]
    assert [x.art for x in suche(sd, jahr, "erdkunde")] == ["gruppe"]
    assert [x.art for x in suche(sd, jahr, "kürzen")] == ["arbeit"]
    assert suche(sd, jahr, "   ") == []


# ---- Oberfläche --------------------------------------------------------------------------------------

@pytest.fixture
def fenster(app, tmp_path, schnelle_kdf):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    db, _ = Datenbank.neu(tmp_path / "f", "Testpasswort1")
    f = Hauptfenster()
    f.setze_datenbank(db)
    jahr = f.sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    f.wechsle_schuljahr(jahr)
    g = f.sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M"))
    ids = [f.sd.lege_schueler_an(jahr.id, n, "V", "9a").id for n in ("Adler", "Becker", "Celik")]
    f.sd.fuege_hinzu(g.id, ids)
    a = Arbeiten(db.verbindung).lege_arbeit_an(g.id, "KA", date(2026, 9, 1), [("1", 10)])
    f.show()
    yield f, g, ids, a
    f.schliesse_datenbank()


def test_schnellsuche_springt_zur_person(fenster, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from notenverwaltung.ui.schnellsuche import SchnellsucheDialog

    f, g, ids, a = fenster
    d = SchnellsucheDialog(f.sd, f.jahr)
    QTest.keyClicks(d.feld, "beck")
    assert d.liste.count() == 2 and d.liste.currentRow() == 0
    QTest.keyClick(d.feld, Qt.Key.Key_Down)
    QTest.keyClick(d.feld, Qt.Key.Key_Return)
    assert d.gewaehlt.art == "person_gruppe" and d.result() == 1
    d2 = SchnellsucheDialog(f.sd, f.jahr)
    QTest.keyClicks(d2.feld, "xyz")
    assert d2.liste.item(0).text() == "Nichts gefunden."
    QTest.keyClick(d2.feld, Qt.Key.Key_Return)
    assert d2.gewaehlt is None

    def waehle(art):
        def exec_(self):
            self._suchen("Becker")
            for i in range(self.liste.count()):
                t = self.liste.item(i).data(Qt.ItemDataRole.UserRole)
                if t and t.art == art:
                    self.gewaehlt = t
                    return 1
            return 0
        return exec_

    monkeypatch.setattr(SchnellsucheDialog, "exec", waehle("person_gruppe"))
    f.schnellsuche()
    seite = f.seite_gruppe
    assert f.stapel.currentWidget() is seite and seite.reiter.currentWidget() is seite.arbeiten
    assert seite.arbeiten.raster.currentIndex().row() == 1               # Becker
    seite.reiter.setCurrentWidget(seite.muendlich)
    f.schnellsuche()
    assert seite.reiter.currentWidget() is seite.muendlich and seite.muendlich.raster.currentIndex().row() == 1
    seite.reiter.setCurrentWidget(seite.noten)
    f.schnellsuche()
    assert seite.noten.tabelle.currentRow() == 1
    seite.reiter.setCurrentWidget(seite.mitglieder)
    f.schnellsuche()
    assert seite.mitglieder.tabelle.aktuelle_daten() == ids[1]
    monkeypatch.setattr(SchnellsucheDialog, "exec", waehle("person"))
    f.seite_schueler.suche.setText("Adler")                                # Filter wird zurückgesetzt
    f.schnellsuche()
    assert f.stapel.currentWidget() is f.seite_schueler and f.seite_schueler.tabelle.aktuelle_daten() == ids[1]


def test_offene_punkte_auf_der_schuljahrsseite(fenster, monkeypatch):
    from PySide6.QtCore import Qt

    from notenverwaltung.ui.nachschreib_dialog import NachschreibDialog

    f, g, ids, a = fenster
    ar = Arbeiten(f.db.verbindung)
    ar.setze_teilnahme(a.id, ids[2], status="fehlt")
    f.offene_punkte()
    seite = f.seite_jahr
    assert f.stapel.currentWidget() is seite
    seite.offene_punkte_laden(heute=date(2026, 9, 20))
    texte = [seite.offen.item(i).text() for i in range(seite.offen.count())]
    assert "• M9: „KA“ vom 01.09. – noch keine Punkte eingetragen" in texte
    assert "• 1 Arbeit muss nachgeschrieben werden" in texte and seite.offen_titel.text().endswith("(2)")
    arbeit = next(seite.offen.item(i) for i in range(seite.offen.count()) if "KA" in seite.offen.item(i).text())
    seite._offen_gewaehlt(arbeit)
    assert f.stapel.currentWidget() is f.seite_gruppe
    assert f.seite_gruppe.reiter.currentWidget() is f.seite_gruppe.arbeiten
    geoeffnet = []
    monkeypatch.setattr(NachschreibDialog, "exec", lambda self: geoeffnet.append(True) or 0)
    nach = next(seite.offen.item(i) for i in range(seite.offen.count()) if "nachgeschrieben" in seite.offen.item(i).text())
    seite._offen_gewaehlt(nach)
    assert geoeffnet == [True]
    # Nichts offen
    ar.loesche_arbeit(a.id)
    seite.offene_punkte_laden(heute=date(2026, 9, 20))
    assert seite.offen.item(0).text() == "✓ Nichts offen." and not seite.offen.item(0).flags() & Qt.ItemFlag.ItemIsEnabled
