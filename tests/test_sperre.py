"""Automatisch sperren und zweiter Sicherungsort."""

import time
from datetime import date

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.stammdaten import Lerngruppe
from notenverwaltung.speicher.datenbank import Datenbank, sichere_nach
from notenverwaltung.ui.hauptfenster import betriebszeit


@pytest.fixture
def fenster(app, tmp_path, schnelle_kdf):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    db, _ = Datenbank.neu(tmp_path / "s", "Testpasswort1")
    f = Hauptfenster()
    f.setze_datenbank(db)
    jahr = f.sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    f.wechsle_schuljahr(jahr)
    g = f.sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M"))
    f.sd.fuege_hinzu(g.id, [f.sd.lege_schueler_an(jahr.id, f"N{i}", "V", "9a").id for i in range(3)])
    Arbeiten(db.verbindung).lege_arbeit_an(g.id, "KA", date(2026, 9, 1), [("1", 10)])
    f._navigation_fuellen(("gruppe", g.id))
    f.show()
    f.activateWindow()
    QTest.qWaitForWindowActive(f)
    yield f, g
    f.schliesse_datenbank()


def test_sperrt_nach_einer_weile_und_entsperrt_mit_passwort(fenster):
    from notenverwaltung.einstellungen import setze_sicherheit

    f, g = fenster
    assert f.sperruhr.isActive()
    f.sperre_pruefen()
    assert not f.sperre.aktiv                                       # gerade erst geöffnet
    tab = f.seite_gruppe.arbeiten
    tab.modell.setData(tab.modell.index(0, 5), "4")                 # ungespeichert
    assert f.db.geaendert
    f.letzte_eingabe = betriebszeit() - 15 * 60 - 1
    f.sperre_pruefen()
    assert f.sperre.aktiv and not f.db.geaendert                    # vorher gespeichert
    schirm = f.sperre.eingabe
    assert schirm.parentWidget() is f and schirm.isVisible() and schirm.geometry() == f.rect()
    # Eingaben an die Tabelle kommen nicht an, Tastenkürzel greifen nicht
    tab.raster.setFocus()
    QTest.keyClick(tab.raster, Qt.Key.Key_7)
    QTest.keyClick(tab.raster, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    QApplication.processEvents()
    assert tab.modell.data(tab.modell.index(0, 5)) == "4" and f.sperre.aktiv
    # falsches, dann richtiges Passwort
    schirm.passwort.setFocus()
    QTest.keyClicks(schirm.passwort, "falsch")
    QTest.keyClick(schirm.passwort, Qt.Key.Key_Return)
    assert f.sperre.aktiv and "stimmt nicht" in schirm.meldung.text() and schirm.passwort.text() == ""
    QTest.keyClicks(schirm.passwort, "Testpasswort1")
    schirm.knopf.click()
    assert not f.sperre.aktiv
    QApplication.processEvents()
    # 0 = nie
    setze_sicherheit(0, "", 10)
    f.letzte_eingabe = betriebszeit() - 10_000
    f.sperre_pruefen()
    assert not f.sperre.aktiv


def test_sperre_deckt_offenen_dialog_ab(fenster):
    """Ist ein Dialog offen, kommt das Passwortfeld auf den Dialog; dessen Inhalt bleibt erhalten."""
    from PySide6.QtCore import QTimer

    from notenverwaltung.ui.stammdaten_dialoge import SchuljahrDialog

    f, g = fenster
    d = SchuljahrDialog(f.sd, f.jahr, f)
    ergebnis = {}

    def im_dialog():
        d.bezeichnung.setText("bleibt erhalten")
        f.sperren("Test")
        ergebnis["oben"] = f.sperre.eingabe.parentWidget() is d
        ergebnis["haupt_abgedeckt"] = any(s.parentWidget() is f for s in f.sperre.schirme)
        QTest.keyClicks(f.sperre.eingabe.passwort, "Testpasswort1")
        f.sperre.eingabe.knopf.click()
        ergebnis["text"] = d.bezeichnung.text()
        d.reject()

    QTimer.singleShot(0, im_dialog)
    d.exec()
    assert ergebnis == {"oben": True, "haupt_abgedeckt": True, "text": "bleibt erhalten"}
    assert not f.sperre.aktiv


def test_von_hand_sperren_und_schliessen(fenster):
    f, g = fenster
    f.a_sperren.trigger()
    assert f.sperre.aktiv
    f.schliesse_datenbank()                                         # Schließen hebt die Sperre auf
    assert not f.sperre.aktiv and f.db is None


def test_sichere_nach(tmp_path):
    quelle = tmp_path / "daten" / "Noten.nvdb"
    quelle.parent.mkdir()
    quelle.write_bytes(b"verschluesselt")
    stick = tmp_path / "stick"
    with pytest.raises(OSError, match="nicht erreichbar"):
        sichere_nach(quelle, stick)
    stick.mkdir()
    with pytest.raises(OSError, match="nicht der Ordner"):
        sichere_nach(quelle, quelle.parent)
    (stick / "Andere_2026-01-01_10-00-00.nvdb").write_bytes(b"x")    # fremde Datenbank bleibt
    for i in range(5):
        (stick / f"Noten_2026-01-0{i + 1}_10-00-00.nvdb").write_bytes(b"alt")
    ziel = sichere_nach(quelle, stick, anzahl=3)
    assert ziel.read_bytes() == b"verschluesselt" and ziel.name.startswith("Noten_")
    namen = sorted(p.name for p in stick.iterdir())
    assert len([n for n in namen if n.startswith("Noten_")]) == 3 and "Andere_2026-01-01_10-00-00.nvdb" in namen
    assert not any(n.endswith(".teil") for n in namen)


def test_zweiter_ort_beim_schliessen(fenster, tmp_path):
    from notenverwaltung.einstellungen import setze_sicherheit

    f, g = fenster
    stick = tmp_path / "stick"
    setze_sicherheit(15, str(stick), 10)
    f.zweiten_ort_sichern()                                          # Stick fehlt: Meldung, kein Absturz
    stick.mkdir()
    f.zweiten_ort_sichern()
    assert len(list(stick.glob("s_*.nvdb"))) == 1
    time.sleep(1.1)                                                  # Zeitstempel in Sekunden
    f.schliesse_datenbank()
    kopien = list(stick.glob("s_*.nvdb"))
    assert len(kopien) == 2 and not list(stick.glob("*.schluessel*"))
    assert Datenbank.oeffnen(kopien[0], "passwort", "Testpasswort1", sperre_ignorieren=True) is not None


def test_einstellungen_sicherheit(app, tmp_path):
    from notenverwaltung.einstellungen import sperre_minuten, zweiter_ort, zweiter_ort_anzahl
    from notenverwaltung.ui.einstellungen_dialog import EinstellungenDialog

    d = EinstellungenDialog()
    assert d.sperre.value() == 15 and d.ort.text() == "" and d.anzahl.value() == 10
    d.ort.setText(str(tmp_path / "gibtsnicht"))
    assert "nicht erreichbar" in d.ort_hinweis.text()
    d.ort.setText(str(tmp_path))
    d.sperre.setValue(5)
    d.anzahl.setValue(4)
    d.accept()
    assert (sperre_minuten(), zweiter_ort(), zweiter_ort_anzahl()) == (5, str(tmp_path), 4)
