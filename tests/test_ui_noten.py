"""Reiter „Noten“: Anzeige, Festsetzen per Eingabe, Vorschläge übernehmen, Gewichtung, ZP10-Spalten."""

from datetime import date

import pytest

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


def _spalte(t, kopf):
    return next(c for c in range(t.tabelle.columnCount()) if t.tabelle.horizontalHeaderItem(c).text() == kopf)


def test_vorschlag_und_festsetzen(umgebung, monkeypatch):
    from notenverwaltung.ui.seiten import noten_tab

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Erdkunde", 9)
    t = noten_tab.NotenTab()
    t.zeige(sd, jahr, g)
    assert t.tabelle.columnCount() == 11
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
    from notenverwaltung.ui.seiten.noten_tab import NotenTab

    sd, jahr = umgebung
    g, sid = _gruppe(sd, jahr, "Mathematik", 10)
    t = NotenTab()
    t.zeige(sd, jahr, g)
    koepfe = [t.tabelle.horizontalHeaderItem(c).text() for c in range(t.tabelle.columnCount())]
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
