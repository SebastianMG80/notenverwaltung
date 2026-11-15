"""Sitzplan (Format 11): Raster, Vorlagen, Personen setzen/tauschen/verteilen, Bewerten, Ausdruck."""

import random
import shutil
import subprocess
from datetime import date

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from notenverwaltung.modell.sitzplan import Sitzplaene, SitzplanFehler, ist_platz
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.stunden import Stunden
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter


@pytest.fixture
def welt(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "sp", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "IF 9", "Informatik", "kurs", 9, ""))
    ids = [sd.lege_schueler_an(jahr.id, n, v, "9.2").id for n, v in
           (("Weiß", "Jörg"), ("Adler", "Ada"), ("Öztürk", "Ayşe"), ("Becker", "Ben"), ("Celik", "Can"))]
    sd.fuege_hinzu(g.id, ids)
    yield db, sd, jahr, g, ids
    db.schliessen(speichern=False)


def test_vorlagen():
    reihen = [x for x in range(8) if ist_platz("reihen", x, 0, 8, 6)]
    assert reihen == [0, 1, 3, 4, 6, 7]                              # drei 2er-Tische, zwei Gänge
    gruppen = {(x, y) for x in range(8) for y in range(6) if ist_platz("gruppen", x, y, 8, 6)}
    assert len(gruppen) == 24 and (2, 0) not in gruppen and (0, 2) not in gruppen
    u = {(x, y) for x in range(8) for y in range(6) if ist_platz("u", x, y, 8, 6)}
    assert len(u) == 6 + 6 + 6 and (3, 2) not in u


def test_plaene_und_personen(welt):
    db, sd, jahr, g, ids = welt
    sp = Sitzplaene(db.verbindung)
    p = sp.lege_an(g.id, "Raum 204")
    assert (p.spalten, p.zeilen) == (8, 6) and len(sp.plaetze(p.id)) == 36
    assert sp.lege_an(g.id, "  ").name == "Sitzplan" and [x.name for x in sp.plaene(g.id)] == ["Raum 204", "Sitzplan"]
    with pytest.raises(SitzplanFehler):
        sp.lege_an(g.id, "zu groß", spalten=13)
    with pytest.raises(SitzplanFehler):
        sp.umbenennen(p.id, " ")
    sp.umbenennen(p.id, "Raum 205")
    # setzen, verschieben, tauschen, frei machen
    sp.setze_person(p.id, 0, 0, ids[0])
    sp.setze_person(p.id, 1, 0, ids[1])
    sp.setze_person(p.id, 3, 0, ids[0])                              # Weiß zieht um
    pl = sp.plaetze(p.id)
    assert pl[(0, 0)] is None and pl[(3, 0)] == ids[0]
    sp.setze_person(p.id, 1, 0, ids[0])                              # auf besetzten Platz: tauschen
    pl = sp.plaetze(p.id)
    assert pl[(1, 0)] == ids[0] and pl[(3, 0)] == ids[1]
    sp.setze_person(p.id, 1, 0, None)
    assert sp.plaetze(p.id)[(1, 0)] is None
    with pytest.raises(SitzplanFehler, match="kein Platz"):
        sp.setze_person(p.id, 2, 0, ids[2])                          # Gang
    # verteilen: alphabetisch von vorne links
    mitglieder = sd.mitglieder(g.id)
    assert sp.verteile(p.id, mitglieder) == 4                        # Adler sitzt schon (3, 0)
    pl = sp.plaetze(p.id)
    # frei von vorne links: Becker, Celik, Öztürk (Ö wie O), Weiß
    assert [pl[(x, 0)] for x in (0, 1, 3, 4, 6)] == [ids[3], ids[4], ids[1], ids[2], ids[0]]
    sp.raeume_ab(p.id)
    assert all(v is None for v in sp.plaetze(p.id).values())
    assert sp.verteile(p.id, mitglieder, "zufall", random.Random(1)) == 5
    # Vorlage: wer sitzt, behält den Platz
    sitzend = {k: v for k, v in sp.plaetze(p.id).items() if v}
    sp.vorlage(p.id, "u")
    pl = sp.plaetze(p.id)
    assert all(pl[k] == v for k, v in sitzend.items()) and len(pl) == 18 + sum(
        1 for k in sitzend if not ist_platz("u", *k, 8, 6))
    # kleiner machen: Plätze außerhalb fallen weg
    sp.setze_platz(p.id, 7, 5, True)
    sp.setze_groesse(p.id, 4, 3)
    assert all(x < 4 and y < 3 for x, y in sp.plaetze(p.id))
    with pytest.raises(SitzplanFehler):
        sp.setze_platz(p.id, 5, 0, True)
    # Person gelöscht → Platz frei; Gruppe gelöscht → Plan weg
    sp.setze_platz(p.id, 0, 0, True)
    sp.setze_person(p.id, 0, 0, ids[4])
    sd.loesche_schueler(ids[4])
    assert sp.plaetze(p.id)[(0, 0)] is None
    sd.loesche_lerngruppe(g.id)
    assert db.verbindung.execute("SELECT COUNT(*) FROM sitzplatz").fetchone()[0] == 0


# ---- Oberfläche --------------------------------------------------------------------------------------

def _tab(welt, monkeypatch, name="Raum 204"):
    from PySide6.QtWidgets import QInputDialog

    from notenverwaltung.ui.seiten.sitzplan_tab import SitzplanTab

    db, sd, jahr, g, ids = welt
    t = SitzplanTab()
    t.resize(1100, 640)
    t.show()
    t.zeige(sd, jahr, g)
    assert t.leer.isVisible() and not t.teiler.isVisible()
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (name, True)))
    t.neuer_plan()
    return t


def _klick(feld, x, y):
    QTest.mouseClick(feld, Qt.MouseButton.LeftButton, pos=feld.rechteck(x, y).center().toPoint())


def test_reiter_tische_personen_bewerten(app, welt, monkeypatch):
    db, sd, jahr, g, ids = welt
    t = _tab(welt, monkeypatch)
    f = t.feld
    assert t.plan.name == "Raum 204" and f.modus == "personen" and t.liste.count() == 5
    assert "5" in t.liste_titel.text() and "36 freie Plätze" in t.liste_titel.text()
    # Tische: Gang (2, 0) anklicken setzt einen Platz, nochmal entfernt ihn
    t.modi.button(0).click()
    assert f.modus == "tische" and t.werkzeuge.isVisible() and not t.personen_werkzeuge.isVisible()
    _klick(f, 2, 0)
    assert (2, 0) in t.sp.plaetze(t.plan.id)
    _klick(f, 2, 0)
    assert (2, 0) not in t.sp.plaetze(t.plan.id)
    # Ziehen über mehrere Felder entfernt eine Reihe
    QTest.mousePress(f, Qt.MouseButton.LeftButton, pos=f.rechteck(0, 5).center().toPoint())
    for x in (1, 3, 4):
        QTest.mouseMove(f, f.rechteck(x, 5).center().toPoint())
    QTest.mouseRelease(f, Qt.MouseButton.LeftButton, pos=f.rechteck(4, 5).center().toPoint())
    assert not any((x, 5) in t.sp.plaetze(t.plan.id) for x in (0, 1, 3, 4))
    # Personen: Namen anklicken, dann Platz
    t.modi.button(1).click()
    item = t.liste.item(0)
    sid = item.data(Qt.ItemDataRole.UserRole)
    t.liste.itemClicked.emit(item)
    assert f.gewaehlt == sid and "Platz klicken" in t.meldung.text()
    _klick(f, 0, 0)
    assert t.sp.plaetze(t.plan.id)[(0, 0)] == sid and t.liste.count() == 4
    f.person_setzen.emit(1, 0, sid)                                   # wie Ziehen von Platz zu Platz
    assert t.sp.plaetze(t.plan.id)[(1, 0)] == sid
    QTest.mouseDClick(f, Qt.MouseButton.LeftButton, pos=f.rechteck(1, 0).center().toPoint())
    assert t.sp.plaetze(t.plan.id)[(1, 0)] is None and t.liste.count() == 5
    t.verteilen("alphabet")
    assert t.liste.count() == 0 and "5 verteilt" in t.meldung.text()
    # Bewerten: Tag wählen, Platz antippen → Schnellerfassung
    t.modi.button(2).click()
    t.datum.setze(date(2026, 9, 3))
    angetippt = []
    f.platz_angetippt.connect(lambda x, y, wo: angetippt.append((x, y)))
    monkeypatch.setattr(t, "_bewerten", lambda *a: None)
    _klick(f, 0, 0)
    assert angetippt == [(0, 0)]
    sid0 = t.sp.plaetze(t.plan.id)[(0, 0)]
    t.bewerte(sid0, 1)
    assert Stunden(db.verbindung).eintraege(g.id)[(sid0, date(2026, 9, 3))].wert == 1
    assert f.bewertung == {sid0: 1}
    t.zeige(sd, jahr, g)                                              # Neuladen: Tag bleibt
    assert t.datum.wert() == date(2026, 9, 3)
    # Größe ändern, Vorlage, Sicht vom Pult
    t.spalten.setValue(6)
    assert t.plan.spalten == 6 and all(x < 6 for x, _ in t.sp.plaetze(t.plan.id))
    links_oben = f.rechteck(0, 0)
    t.pult.setChecked(True)
    assert f.rechteck(0, 0).center().x() > links_oben.center().x() and f.rechteck(0, 0).center().y() > links_oben.center().y()
    t.vorlage.setCurrentIndex(t.vorlage.findData("leer"))
    t.vorlage_anwenden()
    assert all(v is not None for v in t.sp.plaetze(t.plan.id).values())   # nur besetzte Plätze bleiben


def test_mehrere_plaene_und_loeschen(app, welt, monkeypatch):
    from notenverwaltung.ui.seiten import sitzplan_tab

    t = _tab(welt, monkeypatch)
    t.neuer_plan()
    assert t.auswahl.count() == 2
    monkeypatch.setattr(sitzplan_tab, "frage", lambda *a, **k: True)
    t.loeschen()
    assert t.auswahl.count() == 1


def test_ausdruck(app, welt, monkeypatch, tmp_path):
    from notenverwaltung.ausgabe.seite import als_pdf
    from notenverwaltung.ausgabe.sitzplan import SitzplanAusgabe

    db, sd, jahr, g, ids = welt
    t = _tab(welt, monkeypatch)
    t.verteilen("alphabet")
    a = SitzplanAusgabe(g, t.plan, t.sp.plaetze(t.plan.id), dict(t.feld.namen))
    assert a.quer and a.seitenzahl() == 1
    if shutil.which("pdftotext"):
        pfad = als_pdf(a, tmp_path / "s.pdf")
        text = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pfad), "-"],
                              capture_output=True).stdout.decode("utf-8", "replace")
        assert "Sitzplan IF 9" in text and "Ayşe" in text and "Öztürk" in text and "Tafel" in text
        kurz = SitzplanAusgabe(g, t.plan, t.sp.plaetze(t.plan.id), dict(t.feld.namen), pult=True, nachname=False)
        text = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(als_pdf(kurz, tmp_path / "k.pdf")), "-"],
                              capture_output=True).stdout.decode("utf-8", "replace")
        assert "Öztürk" not in text and "Ö." in text and "Sicht vom Pult" in text
    monkeypatch.setattr("notenverwaltung.ui.vorschau_dialog.VorschauDialog.exec", lambda self: 0)
    t.drucken()
    assert t._druckdialog.ausgabe.seitenzahl() == 1
