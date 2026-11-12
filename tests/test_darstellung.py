"""Darstellung: Schrift der Oberfläche, Schrift und Kopfzeile der Ausdrucke."""

import shutil
import subprocess
from datetime import date

import pytest
from PySide6.QtWidgets import QApplication

from notenverwaltung.einstellungen import druck_schrift, ui_schrift


def test_ui_schrift_groesser_kleiner_standard(app):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    f = Hauptfenster()
    vorher = QApplication.font().pointSizeF()
    f.schrift_groesse(2)
    assert QApplication.font().pointSizeF() == vorher + 2
    assert ui_schrift()
    f.schrift_standard()
    assert ui_schrift() == ""
    assert QApplication.font().pointSizeF() == vorher


def test_gespeicherte_schrift_beim_start(app):
    from PySide6.QtGui import QFont

    from notenverwaltung.app import erzeuge_anwendung
    from notenverwaltung.einstellungen import setze_ui_schrift

    f = QFont(QApplication.font())
    f.setPointSizeF(15)
    setze_ui_schrift(f.toString())
    erzeuge_anwendung([])
    assert QApplication.font().pointSizeF() == 15
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    Hauptfenster().schrift_standard()


@pytest.mark.skipif(not shutil.which("pdftotext"), reason="pdftotext fehlt")
def test_kopfzeile_und_druckschrift(app, tmp_path, schnelle_kdf):
    from notenverwaltung.ausgabe.punkteliste import Punkteliste
    from notenverwaltung.ausgabe.seite import als_pdf
    from notenverwaltung.modell.arbeiten import Arbeiten
    from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
    from notenverwaltung.speicher.datenbank import Datenbank
    from notenverwaltung.ui.druck import DruckDialog

    db, _ = Datenbank.neu(tmp_path / "d", "Testpasswort1")
    try:
        db.setze_meta("druck_schule", "Gesamtschule Musterstadt")
        db.setze_meta("druck_lehrkraft", "Frau Beispiel")
        sd = Stammdaten(db.verbindung)
        jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
        g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M"))
        ar = Arbeiten(db.verbindung)
        a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 5)])
        d = DruckDialog(ar, a)
        assert d.ausgabe.kopfzeile == "Gesamtschule Musterstadt · Frau Beispiel"
        assert d.ausgabe.schrift is None                       # Standard
        d._schrift_gesetzt = True
        d.schrift.setCurrentText("DejaVu Serif")
        assert d.ausgabe.schrift and druck_schrift()
        pdf = als_pdf(d.ausgabe, tmp_path / "p.pdf")
        t = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True).stdout.decode()
        assert "Gesamtschule Musterstadt" in " ".join(t.split())
        d._schrift_standard()
        assert d.ausgabe.schrift is None and druck_schrift() == ""
        assert isinstance(d.ausgabe, Punkteliste)
    finally:
        db.schliessen(speichern=False)
