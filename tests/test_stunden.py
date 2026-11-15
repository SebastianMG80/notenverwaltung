"""Schnellerfassung je Stunde (Format 10): Eingabe, Durchschnitt, Vorschlag, Reiter, Übernahme ins Mündliche."""

import shutil
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import SEK1, SEK2, Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.stunden import Schnitt, Stunden, StundenFehler, vorschlag, wert_aus_eingabe
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter

D1, D2, D3 = date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)


@pytest.fixture
def welt(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "st", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "EK 9", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    ids = [sd.lege_schueler_an(jahr.id, n, "V", "9a").id for n in ("Adler", "Becker", "Celik")]
    sd.fuege_hinzu(g.id, ids)
    yield db, sd, jahr, g, ids
    db.schliessen(speichern=False)


def test_eingabe():
    assert [wert_aus_eingabe(t) for t in ("++", "+", "o", "O", "-", "–", "--", "––", "1", "5", " ", "+ +")] == \
        [1, 2, 3, 3, 4, 4, 5, 5, 1, 5, None, 1]
    for falsch in ("+++", "6", "gut", "-+"):
        with pytest.raises(StundenFehler):
            wert_aus_eingabe(falsch)


def test_vorschlag_sek1_und_sek2():
    s = Schnitt(2.4, 5, {})
    assert vorschlag(s, SEK1).kurz == "2-" and vorschlag(s, SEK2).punkte == 10        # 17 − 7,2 = 9,8 → 10
    assert vorschlag(Schnitt(1.0, 1, {}), SEK2).punkte == 14
    assert vorschlag(Schnitt(5.0, 1, {}), SEK2).punkte == 2
    assert vorschlag(Schnitt(3.0, 1, {}), SEK1) == Note.aus_kurz("3")
    assert vorschlag(Schnitt(None, 0, {}), SEK1) is None


def test_speichern_schnitt_und_rueckgaengig(welt):
    db, sd, jahr, g, ids = welt
    st = Stunden(db.verbindung)
    st.setze(g.id, ids[0], D1, 1, "Referat")
    st.setze(g.id, ids[0], D2, 2)
    st.setze(g.id, ids[0], D3, 4)
    st.setze(g.id, ids[1], D1, 3)
    st.setze(g.id, ids[0], D1, 2)                                # ändern: Notiz bleibt
    e = st.eintraege(g.id)
    assert e[(ids[0], D1)].wert == 2 and e[(ids[0], D1)].notiz == "Referat" and e[(ids[0], D1)].symbol == "+"
    assert st.daten(g.id) == [D1, D2, D3]
    s = st.schnitt(g.id, ids[0], D1, D3)
    assert s.anzahl == 3 and round(s.wert, 3) == 2.667 and s.verteilung[2] == 2
    assert s.text() == "Ø 2,7 aus 3 Stunden (+ 2×, – 1×)"
    assert st.schnitt(g.id, ids[0], D2, D2).anzahl == 1
    st.setze_notiz(g.id, ids[0], D2, "  ruhig  ")
    assert st.eintraege(g.id)[(ids[0], D2)].notiz == "ruhig"
    with pytest.raises(StundenFehler):
        st.setze_notiz(g.id, ids[2], D2, "x")
    with pytest.raises(StundenFehler):
        st.setze(g.id, ids[0], D2, 7)
    db.verlauf.abschliessen()
    st.setze(g.id, ids[0], D3, None)
    assert (ids[0], D3) not in st.eintraege(g.id)
    db.verlauf.rueckgaengig()
    assert st.eintraege(g.id)[(ids[0], D3)].wert == 4
    sd.loesche_lerngruppe(g.id)                                     # Kaskade
    assert db.verbindung.execute("SELECT COUNT(*) FROM beobachtung").fetchone()[0] == 0


def test_altdatei_bekommt_tabelle(tmp_path):
    quelle = Path(__file__).parent / "daten" / "version_0_7_0.nvdb"
    ziel = tmp_path / quelle.name
    shutil.copy2(quelle, ziel)
    db = Datenbank.oeffnen(ziel, "passwort", "Versionsprüfung 2026 – Ärger vermeiden")
    try:
        assert db.verbindung.execute("SELECT COUNT(*) FROM beobachtung").fetchone()[0] == 0
    finally:
        db.schliessen(speichern=False)


# ---- Oberfläche --------------------------------------------------------------------------------------

def _tab(welt):
    from notenverwaltung.ui.seiten.stunden_tab import StundenTab

    db, sd, jahr, g, ids = welt
    t = StundenTab()
    t.resize(1100, 500)
    t.show()
    t.zeige(sd, jahr, g)
    return t


def test_reiter_eingabe_und_uebernahme(app, welt, monkeypatch):
    from test_ui_arbeiten import tippe

    from notenverwaltung.ui.seiten import stunden_tab
    from notenverwaltung.ui.seiten.stunden_tab import FEST

    db, sd, jahr, g, ids = welt
    t = _tab(welt)
    m = t.modell
    t.zeitraum.setCurrentIndex(0)                                   # 1. Quartal
    assert m.tage == [] and "Noch keine Stunde" in t.meldung.text()
    t.datum.setze(D1)
    t.stunde_hinzufuegen()
    assert m.tage == [D1] and t.raster.currentIndex().column() == FEST
    tippe(t.raster, "++")
    tippe(t.raster, "o")
    assert t.raster.currentIndex().row() == 2                       # nach unten
    tippe(t.raster, "x")
    assert "verstehe ich nicht" in t.meldung.text()
    t.datum.setze(D2)
    t.stunde_hinzufuegen()
    t.raster.setCurrentIndex(m.index(0, FEST + 1))
    tippe(t.raster, "2")
    assert m.data(m.index(0, FEST)) == "++" and m.data(m.index(0, FEST + 1)) == "+"
    assert m.data(m.index(0, 3)) == "1,5 → 1-"          # Gleichstand → die bessere and m.data(m.index(1, 3)) == "3,0 → 3"
    assert "Ø 1,5 aus 2 Stunden" in m.data(m.index(0, 3), Qt.ItemDataRole.ToolTipRole)
    # Stunde in einem anderen Quartal: Zeitraum wechselt mit
    t.datum.setze(date(2026, 12, 1))
    t.stunde_hinzufuegen()
    assert t.aktueller_zeitraum().beginn.month in (10, 11) and m.tage == [date(2026, 12, 1)]
    t.zeitraum.setCurrentIndex(0)
    # Übernehmen: Becker hat schon eine mündliche Note → bleibt
    mu = Muendlich(db.verbindung)
    z = t.aktueller_zeitraum()
    mu.setze_note(z.id, ids[1], Note.aus_kurz("4"))
    assert [(x.schueler.id, n.kurz) for x, n in t.vorschlaege()] == [(ids[0], "1-")]
    monkeypatch.setattr(stunden_tab, "frage", lambda *a, **k: True)
    t.uebernehmen()
    noten = mu.noten(g.id)
    assert noten[(z.id, ids[0])][0].kurz == "1-" and noten[(z.id, ids[1])][0].kurz == "4"
    assert "1 mündliche Noten übernommen" in t.meldung.text()
    t.uebernehmen()
    assert "Niemand" in t.meldung.text()
    # „ganzes Schuljahr“: kein Übernehmen
    t.zeitraum.setCurrentIndex(t.zeitraum.count() - 1)
    assert not t.k_uebernehmen.isEnabled() and len(m.tage) == 3
    # Entf löscht
    t.raster.setCurrentIndex(m.index(0, FEST))
    from PySide6.QtTest import QTest
    QTest.keyClick(t.raster, Qt.Key.Key_Delete)
    assert m.data(m.index(0, FEST)) == ""


def test_vorschlag_im_reiter_muendlich(app, welt):
    from notenverwaltung.ui.seiten.muendlich_tab import FEST, MuendlichTab

    db, sd, jahr, g, ids = welt
    st = Stunden(db.verbindung)
    st.setze(g.id, ids[0], D1, 2)
    st.setze(g.id, ids[0], D2, 3)
    t = MuendlichTab()
    t.zeige(sd, jahr, g)
    m = t.modell
    zeile = [x.schueler.id for x in m.mitglieder].index(ids[0])
    zelle = m.index(zeile, FEST)
    assert m.data(zelle) == "(2-)" and m.data(zelle, Qt.ItemDataRole.EditRole) == ""
    assert "Vorschlag aus der Schnellerfassung: 2-" in m.data(zelle, Qt.ItemDataRole.ToolTipRole)
    assert m.data(zelle, Qt.ItemDataRole.FontRole).italic()
    assert m.data(m.index(zeile, FEST + 1)) == ""                   # 2. Quartal: keine Einträge
    z = m.zeitraeume[0]
    t._vorschlag_setzen([(z, m.mitglieder[zeile], m.vorschlag(z, m.mitglieder[zeile])[0])])
    assert m.data(zelle) == "2-"


def test_reiter_in_der_lerngruppe(app, welt):
    from notenverwaltung.ui.seiten.stammdaten_seiten import LerngruppeSeite

    db, sd, jahr, g, ids = welt
    s = LerngruppeSeite()
    s.zeige(sd, jahr, g)
    assert s.reiter.tabText(s.reiter.indexOf(s.stunden)) == "Schnellerfassung"
    assert s.reiter.isTabVisible(s.reiter.indexOf(s.stunden))
