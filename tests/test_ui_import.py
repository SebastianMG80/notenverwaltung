"""Import-Assistent: Datei → Spalten → Abgleich → Übernahme."""

from datetime import date
from pathlib import Path

import pytest

from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank

DATEN = Path(__file__).parent / "daten"


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "i", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    yield sd, jahr, g
    db.schliessen(speichern=False)


def test_assistent_durchlauf(umgebung):
    from notenverwaltung.ui.import_assistent import ImportAssistent

    sd, jahr, g = umgebung
    a = ImportAssistent(sd, jahr, g.id)
    a.show()
    a.seite_datei.lade_datei(DATEN / "liste.ods")
    assert a.seite_datei.isComplete()
    a.next()
    s = a.seite_spalten
    assert s.combos["nachname"].currentData() == 0 and s.combos["klasse"].currentData() == 2
    assert s.isComplete() and "3 Einträge" in s.meldung.text()
    s.combos["klasse"].setCurrentIndex(0)          # Klassenspalte weg …
    assert not s.isComplete()
    s.feste_klasse.setText("9.3")                   # … dafür feste Klasse
    assert s.isComplete()
    s.combos["klasse"].setCurrentIndex(s.combos["klasse"].findData(2))
    a.next()
    ab = a.seite_abgleich
    assert ab.tabelle.rowCount() == 3
    assert ab.lerngruppe.currentData() == g.id
    ab.tabelle.cellWidget(2, 5).setCurrentIndex(ab.tabelle.cellWidget(2, 5).findData("ueberspringen"))
    a.accept()
    assert a.ergebnis.neu == 2 and a.ergebnis.uebersprungen == 1 and a.ergebnis.in_lerngruppe == 2
    assert len(sd.mitglieder(g.id)) == 2


def test_assistent_kaputte_datei(umgebung, tmp_path):
    from notenverwaltung.ui.import_assistent import ImportAssistent

    sd, jahr, g = umgebung
    (tmp_path / "x.xlsx").write_bytes(b"kaputt")
    a = ImportAssistent(sd, jahr)
    a.seite_datei.lade_datei(tmp_path / "x.xlsx")
    assert not a.seite_datei.isComplete()
    assert "nicht gelesen" in a.seite_datei.meldung.text()
