"""Import von Schülerlisten: Dateiformate, Spaltenerkennung, Abgleich, Übernahme."""

from datetime import date
from pathlib import Path

import pytest

from notenverwaltung.modell.importieren import (
    ImportFehler,
    Zuordnung,
    datensaetze,
    erkenne,
    fuehre_aus,
    gleiche_ab,
    lies_datum,
)
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.modell.tabellen import TabellenFehler, lies_tabelle
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter

DATEN = Path(__file__).parent / "daten"
ERWARTET = [["Nachname", "Vorname", "Klasse", "Geburtsdatum", "Interne ID"],
            ["Müller-Lüdenscheidt", "Zoë", "9.1", "03.04.2011", "1001"],
            ["Straßburger", "Ömer", "9.10", "17.12.2010", "1002"],
            ["Ćorić", "Ana", "9.2", "", "1003"]]


@pytest.fixture
def sd(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "i", "Testpasswort1", KdfParameter(1, 1, 1024))
    s = Stammdaten(db.verbindung)
    s.jahr = s.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    yield s
    db.schliessen(speichern=False)


@pytest.mark.parametrize("datei", ["liste_utf8.csv", "liste.xlsx", "liste.ods"])
def test_formate_lesen_gleich(datei):
    assert lies_tabelle(DATEN / datei) == ERWARTET


def test_cp1252_und_synonyme():
    zeilen = lies_tabelle(DATEN / "liste_cp1252.csv")
    assert zeilen[1][:2] == ["Müller", "Jürgen"]
    z = erkenne(zeilen)
    assert z.kopfzeile and z.spalten["nachname"] == 0 and z.spalten["vorname"] == 1
    assert z.spalten["klasse"] == 2 and z.spalten["geburtsdatum"] == 3


def test_altes_excel_abgelehnt(tmp_path):
    (tmp_path / "a.xls").write_bytes(b"\xd0\xcf\x11\xe0")
    with pytest.raises(TabellenFehler, match="xls"):
        lies_tabelle(tmp_path / "a.xls")


def test_kaputte_xlsx(tmp_path):
    (tmp_path / "a.xlsx").write_bytes(b"kein zip")
    with pytest.raises(TabellenFehler):
        lies_tabelle(tmp_path / "a.xlsx")


def test_ohne_kopfzeile_nach_inhalt(tmp_path):
    """Wie ein Untis-Export: keine Überschriften, Semikolon, Datum als JJJJMMTT."""
    (tmp_path / "GPU010.TXT").write_text('"Kurz1";"Adler";"Anna";"9a";20110304\n"Kurz2";"Brandt";"Ben";"9b";20101112\n',
                                         encoding="cp1252")
    zeilen = lies_tabelle(tmp_path / "GPU010.TXT")
    z = erkenne(zeilen)
    assert not z.kopfzeile
    assert z.spalten["klasse"] == 3 and z.spalten["geburtsdatum"] == 4
    # „Kurz1“ enthält Ziffern → die ersten reinen Textspalten sind Nach- und Vorname
    assert (z.spalten["nachname"], z.spalten["vorname"]) == (1, 2)
    z.spalten.update(extern_id=0)
    s = datensaetze(zeilen, z)
    assert (s[0].nachname, s[0].vorname, s[0].klasse, s[0].jahrgang) == ("Adler", "Anna", "9a", 9)
    assert s[0].geburtsdatum == date(2011, 3, 4) and s[0].extern_id == "Kurz1"


def test_name_komplett_in_einer_spalte():
    zeilen = [["Name", "Klasse"], ["Muster, Hans", "8.4"], ["Adler, Anna", "8.4"]]
    z = erkenne(zeilen)
    assert z.spalten["name_komplett"] == 0 and z.spalten["nachname"] is None
    s = datensaetze(zeilen, z)
    assert (s[0].nachname, s[0].vorname) == ("Muster", "Hans")


def test_kursliste_ohne_klassenspalte_braucht_klasse():
    zeilen = [["Nachname", "Vorname"], ["A", "B"]]
    z = erkenne(zeilen)
    with pytest.raises(ImportFehler, match="Klasse"):
        datensaetze(zeilen, z)
    z.feste_klasse = "9.3"
    assert datensaetze(zeilen, z)[0].klasse == "9.3"


def test_doppelte_zuordnung_abgelehnt():
    z = Zuordnung()
    z.spalten.update(nachname=0, vorname=0, klasse=1)
    with pytest.raises(ImportFehler, match="mehreren"):
        z.pruefe()


def test_datum_lesen():
    assert lies_datum("3.4.11") == date(2011, 4, 3)
    assert lies_datum("2011-04-03") == date(2011, 4, 3)
    assert lies_datum("31.02.2011") is None
    assert lies_datum("") is None


def test_fehlerhafte_zeilen():
    zeilen = [["Nachname", "Vorname", "Klasse", "Geburtsdatum"], ["A", "", "8.4", ""], ["B", "C", "Förder", ""],
              ["D", "E", "8.4", "gestern"]]
    s = datensaetze(zeilen, erkenne(zeilen))
    assert [x.fehler for x in s] == ["Name unvollständig", "Jahrgang unbekannt", "Geburtsdatum „gestern“ unlesbar"]


def test_import_und_abgleich(sd):
    zeilen = lies_tabelle(DATEN / "liste.xlsx")
    saetze = datensaetze(zeilen, erkenne(zeilen))
    plan = gleiche_ab(sd, sd.jahr.id, saetze)
    assert [a.aktion for a in plan] == ["neu", "neu", "neu"]
    g = sd.lege_lerngruppe_an(Lerngruppe(0, sd.jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    e = fuehre_aus(sd, sd.jahr.id, plan, lerngruppe_id=g.id)
    assert (e.neu, e.in_lerngruppe) == (3, 3)
    assert sd.klassen(sd.jahr.id) == ["9.1", "9.2", "9.10"]
    assert sd.schueler_im_jahr(sd.jahr.id, "9.1")[0].schueler.geburtsdatum == date(2011, 4, 3)

    # Zweiter Import derselben Liste: nichts doppelt
    plan2 = gleiche_ab(sd, sd.jahr.id, saetze)
    assert [a.aktion for a in plan2] == ["vorhanden"] * 3
    assert fuehre_aus(sd, sd.jahr.id, plan2).unveraendert == 3
    assert len(sd.schueler_im_jahr(sd.jahr.id)) == 3

    # Klassenwechsel über die ID erkannt
    zeilen[1][2] = "9.3"
    plan3 = gleiche_ab(sd, sd.jahr.id, datensaetze(zeilen, erkenne(zeilen)))
    assert plan3[0].aktion == "aktualisieren" and "9.1" in plan3[0].hinweis
    fuehre_aus(sd, sd.jahr.id, plan3)
    assert sd.schueler_im_jahr(sd.jahr.id, "9.3")[0].schueler.vorname == "Zoë"


def test_gleichnamig_andere_klasse_ohne_id_wird_nicht_geraten(sd):
    sd.lege_schueler_an(sd.jahr.id, "Muster", "Hans", "8.4")
    zeilen = [["Nachname", "Vorname", "Klasse"], ["Muster", "Hans", "8.2"]]
    plan = gleiche_ab(sd, sd.jahr.id, datensaetze(zeilen, erkenne(zeilen)))
    assert plan[0].aktion == "ueberspringen" and "Klassenwechsel" in plan[0].hinweis


def test_person_aus_frueherem_jahr(sd):
    alt = sd.lege_schuljahr_an("2025/26", date(2025, 8, 1), date(2026, 2, 1), date(2026, 7, 31))
    p = sd.lege_schueler_an(alt.id, "Muster", "Hans", "7.4", geburtsdatum=date(2012, 5, 1))
    zeilen = [["Nachname", "Vorname", "Klasse", "Geburtsdatum"], ["Muster", "Hans", "8.4", "01.05.2012"]]
    plan = gleiche_ab(sd, sd.jahr.id, datensaetze(zeilen, erkenne(zeilen)))
    assert plan[0].aktion == "uebernehmen" and plan[0].schueler_id == p.id
    assert fuehre_aus(sd, sd.jahr.id, plan).uebernommen == 1
    assert sd.schueler_im_jahr(sd.jahr.id)[0].schueler.id == p.id  # dieselbe Person, neue Klasse


def test_doppelte_zeilen_in_datei(sd):
    zeilen = [["Nachname", "Vorname", "Klasse"], ["A", "B", "8.4"], ["A", "B", "8.4"]]
    plan = gleiche_ab(sd, sd.jahr.id, datensaetze(zeilen, erkenne(zeilen)))
    assert [a.aktion for a in plan] == ["neu", "ueberspringen"]


def test_alles_oder_nichts(sd, monkeypatch):
    zeilen = [["Nachname", "Vorname", "Klasse"], ["A", "B", "8.4"], ["C", "D", "8.4"]]
    plan = gleiche_ab(sd, sd.jahr.id, datensaetze(zeilen, erkenne(zeilen)))
    original = sd.lege_schueler_an
    aufrufe = []

    def zweiter_scheitert(*a, **k):
        aufrufe.append(1)
        if len(aufrufe) == 2:
            raise ValueError("Testfehler")
        return original(*a, **k)

    monkeypatch.setattr(sd, "lege_schueler_an", zweiter_scheitert)
    with pytest.raises(ValueError):
        fuehre_aus(sd, sd.jahr.id, plan)
    assert sd.schueler_im_jahr(sd.jahr.id) == []
    assert sd.schuljahre()  # restliche Daten unversehrt
