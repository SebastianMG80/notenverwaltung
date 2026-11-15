"""Rückmeldungen: Textbausteine (Format 9), Platzhalter, Vorschlag, Aufgabenanalyse – Modell und Oberfläche."""

import shutil
import subprocess
from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.rueckmeldung import (
    TextbausteinFehler,
    Textbausteine,
    aufgabenanalyse,
    aufzaehlung,
    fuelle,
    platzhalter_werte,
    staerken_und_uebungsbedarf,
    vorschlag,
)
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter


@pytest.fixture
def welt(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "r", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "IF 9", "Informatik", "kurs", 9, ""))
    ids = [sd.lege_schueler_an(jahr.id, n, v, "9.2").id for n, v in (("Muster", "Mara"), ("Beispiel", "Ben"),
                                                                    ("Probe", "Paula"))]
    sd.fuege_hinzu(g.id, ids)
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "Logik-Arbeit", date(2026, 11, 10), [("1a", 4), ("b", 2), ("2", 6), ("3", 4)])
    x = ar.aufgaben(a.id)
    ar.setze_aufgaben(a.id, [(x[0].id, "1a", 4, "Grundgatter", ""), (x[1].id, "b", 2, "Halbaddierer", ""),
                             (x[2].id, "2", 6, "Klassenraum-Lüftung", ""), (x[3].id, "3", 4, "", "")])
    x = ar.aufgaben(a.id)
    # Mara: 4/4, 2/2, 2/6, 3/4 – Ben: alles voll – Paula: nichts
    for aufg, p in zip(x, (4, 2, 2, 3)):
        ar.setze_punkte(aufg.id, ids[0], p)
    for aufg in x:
        ar.setze_punkte(aufg.id, ids[1], aufg.max_punkte)
    ar.setze_punkte(x[2].id, ids[2], 0)
    yield db, sd, jahr, g, ids, ar, ar.arbeit(a.id)
    db.schliessen(speichern=False)


def test_standardbausteine_und_verwaltung(welt):
    db, *_ = welt
    tb = Textbausteine(db.verbindung)
    alle = tb.alle()
    assert [b.kuerzel for b in alle][:3] == ["stark", "üben", "weiter"] and len(alle) == 6
    liste = [(b.id, b.kuerzel, b.text, b.fach) for b in alle]
    liste.append((None, "lüft", "Denk an die Wahrheitstabelle, {Vorname}.", "Informatik"))
    liste.append((None, "lüft", "Lüften!", ""))                       # gleiches Kürzel, anderes Fach: erlaubt
    tb.setze(liste)
    assert len(tb.alle()) == 8 and len(tb.alle("Deutsch")) == 7 and len(tb.alle("informatik")) == 8
    assert tb.finde("LÜFT", "Informatik").fach == "Informatik"      # das fachspezifische zuerst
    assert tb.finde("lüft", "Deutsch").text == "Lüften!"
    assert tb.finde("gibtsnicht") is None
    with pytest.raises(TextbausteinFehler, match="doppelt"):
        tb.setze(liste + [(None, "stark", "nochmal", "")])
    with pytest.raises(TextbausteinFehler, match="Leerzeichen"):
        tb.setze([(None, "zwei wörter", "x", "")])
    with pytest.raises(TextbausteinFehler, match="fehlt der Text"):
        tb.setze([(None, "leer", "  ", "")])
    tb.setze([(None, "", "", "")])                                    # leere Zeilen fallen weg
    assert tb.alle() == []


def test_platzhalter_und_vorschlag(welt):
    db, sd, jahr, g, ids, ar, a = welt
    aufgaben = ar.aufgaben(a.id)
    mara, ben, paula = ar.ergebnisse(a.id)[:3] if ar.ergebnisse(a.id)[0].mitglied.schueler.id == ids[0] else (None,) * 3
    erg = {e.mitglied.schueler.id: e for e in ar.ergebnisse(a.id)}
    mara, ben, paula = erg[ids[0]], erg[ids[1]], erg[ids[2]]
    gut, ueben = staerken_und_uebungsbedarf(mara, aufgaben)
    assert gut == ["Grundgatter", "Halbaddierer"] and ueben == ["Klassenraum-Lüftung"]   # 3/4 = 75 %: weder noch
    w = platzhalter_werte(mara, a, g.fach, aufgaben)
    assert w["Vorname"] == "Mara" and w["Punkte"] == "11" and w["Höchstpunkte"] == "16" and w["Prozent"] == "69 %"
    assert w["Note"] == mara.note.wort and w["Fach"] == "Informatik" and w["Arbeit"] == "Logik-Arbeit"
    assert fuelle("{Vorname}: {Stärken}. {Übungsbedarf}! {Unbekannt}", w) == \
        "Mara: Grundgatter und Halbaddierer. Klassenraum-Lüftung! {Unbekannt}"
    assert vorschlag(mara, aufgaben) == ("Besonders gut gelungen: Grundgatter und Halbaddierer. "
                                         "Übe noch einmal: Klassenraum-Lüftung.")
    assert vorschlag(ben, aufgaben) == ("Besonders gut gelungen: Grundgatter, Halbaddierer, Klassenraum-Lüftung "
                                        "und Aufgabe 3.")                 # ohne Thema: „Aufgabe 3“
    assert vorschlag(paula, aufgaben) == "Übe noch einmal: Klassenraum-Lüftung."
    assert vorschlag(mara, aufgaben, stark=95, schwach=10) == "Besonders gut gelungen: Grundgatter und Halbaddierer."
    assert vorschlag(mara, aufgaben, stark=101, schwach=10) == "Alle Aufgaben hast du zu einem guten Teil gelöst."
    assert aufzaehlung([]) == "" and aufzaehlung(["A"]) == "A"
    ar.setze_teilnahme(a.id, ids[2], note_manuell=Note.aus_kurz("4"))
    assert vorschlag(erg[ids[2]].__class__(**{**erg[ids[2]].__dict__, "summe": None}), aufgaben) == ""


def test_aufgabenanalyse(welt):
    db, sd, jahr, g, ids, ar, a = welt
    zeilen = aufgabenanalyse(ar.ergebnisse(a.id), ar.aufgaben(a.id))
    z1, zb, z2, z3 = zeilen
    assert (z1.bearbeitet, round(z1.quote), z1.voll, z1.null) == (2, 100, 2, 0)
    assert (z2.bearbeitet, round(z2.quote), z2.voll, z2.null) == (3, 44, 1, 1)      # (2 + 6 + 0) / 3 / 6
    assert round(z3.quote) == 88


def test_altdatei_bekommt_standardbausteine(tmp_path):
    """Ältere Dateien (vor Format 9) bekommen beim Öffnen die Standardbausteine."""
    from pathlib import Path

    quelle = Path(__file__).parent / "daten" / "version_0_5_0.nvdb"
    ziel = tmp_path / quelle.name
    shutil.copy2(quelle, ziel)
    db = Datenbank.oeffnen(ziel, "passwort", "Versionsprüfung 2026 – Ärger vermeiden")
    try:
        assert len(Textbausteine(db.verbindung).alle()) == 6
    finally:
        db.schliessen(speichern=False)


# ---- Oberfläche --------------------------------------------------------------------------------------

def _dialog(welt, start=0):
    from notenverwaltung.ui.rueckmeldung_dialog import RueckmeldungDialog

    db, sd, jahr, g, ids, ar, a = welt
    return RueckmeldungDialog(ar, a, g, ids, start)


def test_rueckmeldungsdialog_blaettern_und_bausteine(app, welt):
    from PySide6.QtWidgets import QApplication

    db, sd, jahr, g, ids, ar, a = welt
    d = _dialog(welt)
    d.show()
    assert d.name.text() == "Mara Muster" and "11 von 16 Punkten (69 %)" in d.stand.text()
    assert d.position.text() == "1 von 3" and not d.zurueck.isEnabled()
    assert not d.k_vorschlag.isVisible()                               # opt-in: standardmäßig aus
    d.text.setPlainText("Gut gemacht.")
    d.text.moveCursor(d.text.textCursor().MoveOperation.End)
    QTest.keyClicks(d.text, " stark")
    QTest.keyClick(d.text, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    assert d.text.toPlainText() == "Gut gemacht. Besonders gut gelungen: Grundgatter und Halbaddierer."
    QTest.keyClicks(d.text, " xyz")
    QTest.keyClick(d.text, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
    assert "Kein Baustein" in d.meldung.text() and d.text.toPlainText().endswith("xyz")
    d.text.setPlainText("Gut gemacht.")
    d.text.moveCursor(d.text.textCursor().MoveOperation.End)
    weiter = next(d.liste.item(i) for i in range(d.liste.count()) if d.liste.item(i).text().startswith("weiter"))
    d._baustein_gewaehlt(weiter)
    assert d.text.toPlainText() == "Gut gemacht. Weiter so, Mara!"
    d.suche.setText("Zeit")
    assert [d.liste.item(i).isHidden() for i in range(d.liste.count())].count(False) == 1
    d.blaettern(1)                                                      # speichert Mara
    assert d.name.text() == "Ben Beispiel" and d.text.toPlainText() == ""
    erg = {e.mitglied.schueler.id: e for e in ar.ergebnisse(a.id)}
    assert erg[ids[0]].kommentar == "Gut gemacht. Weiter so, Mara!"
    d.activateWindow()
    QTest.qWaitForWindowActive(d)
    QTest.keyClick(d.text, Qt.Key.Key_PageUp, Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    assert d.name.text() == "Mara Muster" and d.text.toPlainText() == "Gut gemacht. Weiter so, Mara!"
    d.blaettern(5)                                                      # außerhalb: nichts passiert
    d.text.setPlainText("Neu")
    d.accept()
    assert {e.mitglied.schueler.id: e for e in ar.ergebnisse(a.id)}[ids[0]].kommentar == "Neu"


def test_vorschlag_knopf_opt_in(app, welt):
    from notenverwaltung.einstellungen import setze_arbeiten_optionen

    setze_arbeiten_optionen(True, False, 90, 40)
    d = _dialog(welt, start=2)                                          # Paula: Lüftung 0 %
    assert d.k_vorschlag.isVisibleTo(d) and d.k_vorschlag.isEnabled()
    d.vorschlag_einfuegen()
    assert d.text.toPlainText() == "Übe noch einmal: Klassenraum-Lüftung."
    d2 = _dialog(welt, start=0)                                         # Mara mit 90/40: Lüftung 33 % < 40 %
    d2.vorschlag_einfuegen()
    assert d2.text.toPlainText() == ("Besonders gut gelungen: Grundgatter und Halbaddierer. "
                                     "Übe noch einmal: Klassenraum-Lüftung.")


def test_textbausteine_dialog(app, welt):
    from notenverwaltung.ui.textbausteine_dialog import TextbausteineDialog

    db, *_ = welt
    tb = Textbausteine(db.verbindung)
    d = TextbausteineDialog(tb)
    assert d.tabelle.rowCount() == 6
    d._zeile(None, "stark", "doppelt", "")
    d.accept()
    assert "doppelt" in d.meldung.text() and len(tb.alle()) == 6
    d.tabelle.item(6, 0).setText("neu")
    d.tabelle.setCurrentCell(6, 0)
    d._verschieben(-1)
    d.tabelle.clearSelection()
    d.tabelle.selectRow(0)
    d._loeschen()
    d.accept()
    assert [b.kuerzel for b in tb.alle()] == ["üben", "weiter", "sorgfalt", "zeit", "neu", "gespräch"]


def test_einstellungen_dialog(app):
    from notenverwaltung.einstellungen import aufgabenanalyse_an, rueckmeldung_vorschlag_an, schwellen
    from notenverwaltung.ui.einstellungen_dialog import EinstellungenDialog

    d = EinstellungenDialog()
    assert not d.vorschlag.isChecked() and not d.analyse.isChecked() and d.stark.value() == 80
    d.schwach.setValue(85)
    d.accept()
    assert "kleiner" in d.meldung.text() and schwellen() == (80.0, 50.0)
    d.schwach.setValue(40)
    d.vorschlag.setChecked(True)
    d.analyse.setChecked(True)
    d.accept()
    assert rueckmeldung_vorschlag_an() and aufgabenanalyse_an() and schwellen() == (80.0, 40.0)


def test_analyse_im_reiter_und_druck(app, welt, tmp_path):
    from notenverwaltung.einstellungen import setze_arbeiten_optionen
    from notenverwaltung.ui.druck import DruckDialog
    from notenverwaltung.ui.seiten.arbeiten_tab import ArbeitenTab

    db, sd, jahr, g, ids, ar, a = welt
    t = ArbeitenTab()
    t.show()
    t.zeige(sd, jahr, g)
    assert not t.analyse.isVisible()
    d = DruckDialog(ar, a)
    assert not d.art_analyse.isVisibleTo(d)
    setze_arbeiten_optionen(False, True, 80, 50)
    t.zeige(sd, jahr, g)
    assert t.analyse.isVisible() and t.analyse.rowCount() == 4
    assert t.analyse.item(2, 1).text().startswith("44 %") and t.analyse.item(0, 2).text() == "2"
    d = DruckDialog(ar, a)
    assert d.art_analyse.isVisibleTo(d)
    d.art_analyse.setChecked(True)
    assert type(d.ausgabe).__name__ == "Aufgabenanalyse" and "Aufgabenanalyse" in d._dateiname()
    if shutil.which("pdftotext"):
        from notenverwaltung.ausgabe.seite import als_pdf

        pfad = als_pdf(d.ausgabe, tmp_path / "a.pdf")
        text = " ".join(subprocess.run(["pdftotext", "-layout", str(pfad), "-"], capture_output=True)
                        .stdout.decode().split())
        assert "Klassenraum-Lüftung" in text and "44 %" in text and "Mara" not in text
        assert "3 Arbeiten ausgewertet" in text


def test_rueckmeldung_aus_dem_reiter(app, welt):
    from notenverwaltung.ui.rueckmeldung_dialog import RueckmeldungDialog
    from notenverwaltung.ui.seiten.arbeiten_tab import ArbeitenTab

    db, sd, jahr, g, ids, ar, a = welt
    t = ArbeitenTab()
    t.zeige(sd, jahr, g)
    t.raster.setCurrentIndex(t.modell.index(1, 6))
    gesehen = {}

    def exec_(self):
        gesehen["name"] = self.name.text()
        self.text.setPlainText("Prima!")
        self.accept()
        return 1

    RueckmeldungDialog.exec = exec_
    try:
        t.k_rueckmeldung.click()
    finally:
        del RueckmeldungDialog.exec
    zeile_1 = t.modell.ergebnisse[1].mitglied.schueler
    assert gesehen["name"] == f"{zeile_1.vorname} {zeile_1.nachname}"
    assert t.modell.ergebnisse[1].kommentar == "Prima!"
