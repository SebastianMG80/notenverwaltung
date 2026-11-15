"""Reiter „Noten“: Anzeige, Festsetzen per Eingabe, Vorschläge übernehmen, Gewichtung, ZP10-Spalten."""

from datetime import date

import pytest
from PySide6.QtCore import Qt

from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.zeugnis import Zeugnis
from notenverwaltung.speicher.datenbank import Datenbank


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "n", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    yield sd, jahr
    db.schliessen(speichern=False)


def _gruppe(sd, jahr, fach, jg):
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, f"{fach} {jg}", fach, "kurs", jg, fach[0]))
    sid = sd.lege_schueler_an(jahr.id, "Muster", "Hans", f"{jg}.1").id
    sd.fuege_hinzu(g.id, [sid])
    mu = Muendlich(sd.v)
    mu.setze_note(mu.zeitraeume(g.id)[0].id, sid, Note.aus_kurz("2-"))
    return g, sid


def _tab(sd, jahr, g, halbjahr=None, einzeln=False):
    """Reiter mit fest gewähltem Zeitraum (sonst hinge die Anzeige vom heutigen Datum ab)."""
    from notenverwaltung.ui.seiten.noten_tab import NotenTab

    t = NotenTab()
    t._zeitraum_gewaehlt = True
    t.zeitraum.setCurrentIndex(t.zeitraum.findData(halbjahr))
    t.ansicht.setCurrentIndex(t.ansicht.findData(einzeln))
    t.zeige(sd, jahr, g)
    return t


def _koepfe(t):
    return [t.tabelle.horizontalHeaderItem(c).text() for c in range(t.tabelle.columnCount())]


def _spalte(t, kopf):
    return next(c for c in range(t.tabelle.columnCount()) if t.tabelle.horizontalHeaderItem(c).text() == kopf)


def test_vorschlag_und_festsetzen(umgebung, monkeypatch):
    from notenverwaltung.ui.seiten import noten_tab

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Erdkunde", 9)
    t = _tab(sd, jahr, g)
    assert t.tabelle.columnCount() == 3 + 4 * 4
    v = t.tabelle.item(0, _spalte(t, "1. Hj.\nVorschlag"))
    assert v.text().startswith("2-") and "mündlich" in v.toolTip()
    # Festsetzen durch Eintippen
    z = t.tabelle.item(0, _spalte(t, "1. Hj.\nZeugnis"))
    z.setText("2")
    assert Zeugnis(sd.v).festgesetzt(g.id)[(sid, "hj1")].kurz == "2"
    # Ungültige Eingabe
    t.tabelle.item(0, _spalte(t, "1. Hj.\nZeugnis")).setText("gut")
    assert "keine Note" in t.meldung.text()
    assert Zeugnis(sd.v).festgesetzt(g.id)[(sid, "hj1")].kurz == "2"
    # Vorschläge übernehmen (alle) → ganze Note
    monkeypatch.setattr(noten_tab, "info", lambda *a, **k: None)
    t._uebernehmen("hj1", False)
    assert t.tabelle.item(0, _spalte(t, "1. Hj.\nZeugnis")).text() == "2"
    assert "festgesetzt" in t.spiegel.text() and "1. Halbjahr" in t.spiegel.text()


def test_zp10_spalten(umgebung):
    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Mathematik", 10)
    t = _tab(sd, jahr, g)
    koepfe = _koepfe(t)
    assert "ZP10" in koepfe and "Vornote" in koepfe and "Endnote\nZeugnis" in koepfe
    t.tabelle.item(0, _spalte(t, "ZP10")).setText("3")
    t.tabelle.item(0, _spalte(t, "Vornote")).setText("2")
    assert t.tabelle.item(0, _spalte(t, "Endnote\nVorschlag")).text().startswith("2-")  # (2+3)/2 = 2,5 → 2-


def test_gewichtung_dialog(umgebung):
    from notenverwaltung.ui.seiten.noten_tab import GewichtungDialog

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Erdkunde", 9)
    zg = Zeugnis(sd.v)
    d = GewichtungDialog(zg, g)
    assert d.automatisch.isChecked() and not d.schriftlich.isEnabled()
    d.automatisch.setChecked(False)
    d.schriftlich.setValue(30)
    d.hj1.setValue(5)
    d._ok()
    gw = zg.gewichtung(sd.lerngruppe(g.id))
    assert (gw.anteil_schriftlich, gw.anteil_hj1, gw.schriftlich_automatisch) == (30, 5, False)


def test_notenuebersicht_druck(umgebung, tmp_path, monkeypatch):
    import shutil
    import subprocess

    from notenverwaltung.ausgabe.notenuebersicht import Notenuebersicht, UebersichtOptionen
    from notenverwaltung.ausgabe.seite import als_pdf
    from notenverwaltung.ui.seiten import noten_tab

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Mathematik", 10)
    zg = Zeugnis(sd.v)
    zg.setze(g.id, sid, "hj1", Note.aus_kurz("2"))
    zg.setze(g.id, sid, "zp10", Note.aus_kurz("3"))
    for hj in (None, 1, 2):
        u = Notenuebersicht(zg, g.id, UebersichtOptionen(halbjahr=hj))
        assert u.seitenzahl() == 1
        koepfe = [k for k, _, _ in u.spalten]
        assert ("ZP10" in koepfe) == (hj != 1)
    if shutil.which("pdftotext"):
        pdf = als_pdf(Notenuebersicht(zg, g.id), tmp_path / "u.pdf")
        t = " ".join(subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True)
                     .stdout.decode().split())
        assert "Notenübersicht" in t and "Muster, Hans" in t and "Notenspiegel 1. Halbjahr" in t
    # Dialog öffnet ohne Fehler (exec abgefangen)
    from notenverwaltung.ui import vorschau_dialog

    monkeypatch.setattr(vorschau_dialog.VorschauDialog, "exec", lambda self: 0)
    t = noten_tab.NotenTab()
    t.zeige(sd, jahr, g)
    t.drucken()
    assert t._druckdialog.ausgabe.seitenzahl() == 1


def test_reihenfolge_quartale_und_halbjahre(umgebung, monkeypatch):
    from notenverwaltung.ui.seiten import noten_tab

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Erdkunde", 9)
    t = _tab(sd, jahr, g)
    noten = [k for k in _koepfe(t) if k.endswith(("\nNote", "\nZeugnis"))]
    assert noten == ["Q1\nNote", "1. Hj.\nZeugnis", "Q3\nNote", "2. Hj.\nZeugnis"]     # Reihenfolge der Abgabe
    assert t.tabelle.item(0, _spalte(t, "Q1\nVorschlag")).text().startswith("2-")
    assert "1. Quartal" in t.tabelle.item(0, _spalte(t, "Q1\nVorschlag")).toolTip()
    t.tabelle.item(0, _spalte(t, "Q1\nNote")).setText("2-")                    # Quartalsnote mit Tendenz
    assert Zeugnis(sd.v).festgesetzt(g.id)[(sid, "q1")].kurz == "2-"
    assert "1. Quartal" in t.spiegel.text()
    monkeypatch.setattr(noten_tab, "info", lambda *a, **k: None)
    Zeugnis(sd.v).setze(g.id, sid, "q1", None)
    t._uebernehmen("q1", True)
    assert t.tabelle.item(0, _spalte(t, "Q1\nNote")).text() == "2-"            # nicht auf „2“ gerundet
    # Zeitraum: nur 2. Halbjahr
    t.zeitraum.setCurrentIndex(t.zeitraum.findData(2))
    noten = [k for k in _koepfe(t) if k.endswith(("\nNote", "\nZeugnis"))]
    assert noten == ["Q3\nNote", "2. Hj.\nZeugnis"] and "1. Quartal" not in t.spiegel.text()


def test_einzelnoten_ansicht(umgebung):
    from notenverwaltung.modell.arbeiten import Arbeiten

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Mathematik", 9)
    ar = Arbeiten(sd.v)
    for titel, datum in (("Klassenarbeit Nr. 1", date(2026, 9, 20)), ("KA 2", date(2026, 12, 3))):
        a = ar.lege_arbeit_an(g.id, titel, datum, [("1", 10)])
        ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, 9)
    t = _tab(sd, jahr, g, halbjahr=1)
    assert len(_koepfe(t)) == 3 + 8                                  # zusammengefasst
    t.ansicht.setCurrentIndex(t.ansicht.findData(True))
    k = _koepfe(t)
    # Q1-Leistungen vor den Q1-Spalten, Q2-Leistungen vor den Halbjahres-Spalten
    assert k[3:] == ["1. Quartal\nmdl. 01.08.", "Klassenar…\n20.09.",
                     "Q1\nschriftl.", "Q1\nmündl.", "Q1\nVorschlag", "Q1\nNote",
                     "2. Quartal\nmdl. 01.11.", "KA 2\n03.12.",
                     "1. Hj.\nschriftl.", "1. Hj.\nmündl.", "1. Hj.\nVorschlag", "1. Hj.\nZeugnis"]
    c = _spalte(t, "Klassenar…\n20.09.")
    assert t.tabelle.item(0, c).text() == "1" and "9 von 10 Punkten" in t.tabelle.item(0, c).toolTip()
    assert "Klassenarbeit Nr. 1" in t.tabelle.horizontalHeaderItem(c).toolTip()
    assert t.tabelle.item(0, _spalte(t, "1. Quartal\nmdl. 01.08.")).text() == "2-"
    assert not t.tabelle.item(0, c).flags() & Qt.ItemFlag.ItemIsEditable
    assert t.tabelle.columnWidth(c) < t.tabelle.columnWidth(_spalte(t, "Q1\nNote"))


@pytest.mark.parametrize("fach,jg", [("Erdkunde", 9), ("Mathematik", 10)])
def test_uebersicht_passt_immer_auf_die_seite(umgebung, fach, jg):
    from itertools import product

    from notenverwaltung.ausgabe.notenuebersicht import BREITE, Notenuebersicht, UebersichtOptionen

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, fach, jg)
    zg = Zeugnis(sd.v)
    for hj, quartale, vorschlaege in product((None, 1, 2), (True, False), (True, False)):
        u = Notenuebersicht(zg, g.id, UebersichtOptionen(halbjahr=hj, quartale=quartale, vorschlaege=vorschlaege))
        assert sum(b for _, _, b in u.spalten) <= BREITE + 1e-6, (hj, quartale, vorschlaege, u.stufe)
        inhalte = [i for _, i, _ in u.spalten]
        pflicht = {1: ["f:hj1"], 2: ["f:hj2"], None: ["f:hj1", "f:hj2"]}[hj]
        pflicht += [f"f:q{q}" for q in (1, 3) if quartale and (hj is None or q == 2 * hj - 1)]
        assert all(p in inhalte for p in pflicht), (hj, quartale, inhalte)      # festgesetzte Noten bleiben immer
    # Halbjahr mit Quartalen: alles passt ungekürzt
    u = Notenuebersicht(zg, g.id, UebersichtOptionen(halbjahr=1))
    assert u.stufe["q_teile"] and u.stufe["hj_teile"]
    ganz = Notenuebersicht(zg, g.id, UebersichtOptionen())
    reihenfolge = [i for _, i, _ in ganz.spalten if i.startswith("f:")]
    assert reihenfolge[:3] == ["f:q1", "f:hj1", "f:q3"]
