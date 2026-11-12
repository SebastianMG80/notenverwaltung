"""Stammdaten: Schuljahre, Schüler:innen, Lerngruppen, Sortierung, Zu- und Abgänge."""

from datetime import date

import pytest

from notenverwaltung.modell.stammdaten import (
    Lerngruppe,
    Stammdaten,
    StammdatenFehler,
    jahrgang_aus_klasse,
    name_schluessel,
    natuerlich,
    schuljahr_vorschlag,
)
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter
from notenverwaltung.speicher.tresor import PASSWORT

SCHNELL = KdfParameter(1, 1, 1024)


@pytest.fixture
def db(tmp_path):
    d, _ = Datenbank.neu(tmp_path / "t", "Testpasswort1", SCHNELL)
    yield d
    d.schliessen(speichern=False)


@pytest.fixture
def sd(db):
    return Stammdaten(db.verbindung)


@pytest.fixture
def jahr(sd):
    b, beginn, wechsel, ende = schuljahr_vorschlag(date(2026, 11, 12))
    return sd.lege_schuljahr_an(b, beginn, wechsel, ende)


def kurs(sd, jahr, **k):
    werte = dict(id=0, schuljahr_id=jahr.id, bezeichnung="M9.3E", fach="Mathematik", art="kurs", jahrgang=9,
                 fach_kuerzel="M", niveau="E")
    werte.update(k)
    return sd.lege_lerngruppe_an(Lerngruppe(**werte))


# ---- Hilfsfunktionen ---------------------------------------------------------------------------

def test_schuljahr_vorschlag():
    assert schuljahr_vorschlag(date(2026, 11, 12)) == ("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    assert schuljahr_vorschlag(date(2027, 3, 1))[0] == "2026/27"
    assert schuljahr_vorschlag(date(2027, 8, 1))[0] == "2027/28"
    assert schuljahr_vorschlag(date(2099, 9, 1))[0] == "2099/00"


def test_natuerliche_sortierung_und_din5007():
    assert sorted(["8.10", "10.1", "8.4", "8.2"], key=natuerlich) == ["8.2", "8.4", "8.10", "10.1"]
    assert sorted(["Zimmer", "Äpfel", "Ober", "Özdemir", "ober"], key=name_schluessel) == \
        ["Äpfel", "Ober", "ober", "Özdemir", "Zimmer"]
    assert name_schluessel("Strauß") == name_schluessel("Strauss")


def test_jahrgang_aus_klasse():
    assert jahrgang_aus_klasse("8.4") == 8
    assert jahrgang_aus_klasse("10a") == 10
    assert jahrgang_aus_klasse("Q1") is None


# ---- Schuljahre --------------------------------------------------------------------------------

def test_schuljahre(sd, jahr):
    assert jahr.halbjahr(date(2026, 12, 1)) == 1 and jahr.halbjahr(date(2027, 2, 1)) == 2
    alt = sd.lege_schuljahr_an("2025/26", date(2025, 8, 1), date(2026, 2, 1), date(2026, 7, 31))
    assert [s.bezeichnung for s in sd.schuljahre()] == ["2026/27", "2025/26"]
    assert sd.aktuelles_schuljahr(date(2026, 3, 1)) == alt
    assert sd.aktuelles_schuljahr(date(2026, 11, 12)) == jahr
    assert sd.aktuelles_schuljahr(date(2030, 1, 1)) == jahr  # Zukunft: neuestes
    assert sd.aktuelles_schuljahr(date(2020, 1, 1)) == alt   # Vergangenheit: ältestes
    with pytest.raises(StammdatenFehler, match="gibt es schon"):
        sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    with pytest.raises(StammdatenFehler, match="Halbjahreswechsel"):
        sd.lege_schuljahr_an("X", date(2026, 8, 1), date(2028, 2, 1), date(2027, 7, 31))


# ---- Schüler:innen -----------------------------------------------------------------------------

def test_schueler_anlegen_und_klassen(sd, jahr):
    sd.lege_schueler_an(jahr.id, "Muster", "Hans", "8.4")
    sd.lege_schueler_an(jahr.id, "Ämsig", "Eva", "8.10")
    sd.lege_schueler_an(jahr.id, "Bauer", "Ali", "8.4", zugang=date(2026, 10, 5))
    assert sd.klassen(jahr.id) == ["8.4", "8.10"]
    liste = sd.schueler_im_jahr(jahr.id)
    assert [e.schueler.nachname for e in liste] == ["Bauer", "Muster", "Ämsig"]
    assert liste[0].jahrgang == 8 and liste[0].zugang == date(2026, 10, 5)
    assert not liste[0].aktiv_am(date(2026, 9, 1)) and liste[0].aktiv_am(date(2026, 10, 5))
    assert [e.schueler.vorname for e in sd.schueler_im_jahr(jahr.id, "8.10")] == ["Eva"]


def test_schueler_pruefungen(sd, jahr):
    with pytest.raises(StammdatenFehler):
        sd.lege_schueler_an(jahr.id, "", "Hans", "8.4")
    with pytest.raises(StammdatenFehler, match="Jahrgang"):
        sd.lege_schueler_an(jahr.id, "A", "B", "Förder")
    sd.lege_schueler_an(jahr.id, "A", "B", "Förder", jahrgang=7)
    with pytest.raises(StammdatenFehler, match="liegt nicht im Schuljahr"):
        sd.lege_schueler_an(jahr.id, "A", "B", "8.4", zugang=date(2030, 1, 1))


def test_schueler_aendern_und_loeschen(sd, jahr):
    s = sd.lege_schueler_an(jahr.id, "Muster", "Hans", "8.4")
    from dataclasses import replace

    sd.aendere_schueler(replace(s, nachname="Mustermann", bemerkung="Nachteilsausgleich"))
    assert sd.schueler(s.id).name == "Mustermann, Hans"
    sd.setze_klasse(s.id, jahr.id, "8.2")
    assert sd.schueler_im_jahr(jahr.id)[0].klasse == "8.2"
    sd.loesche_schueler(s.id)
    assert sd.schueler_im_jahr(jahr.id) == []


# ---- Lerngruppen -------------------------------------------------------------------------------

def test_lerngruppe_anlegen(sd, jahr):
    g = kurs(sd, jahr)
    assert g.niveau == "E" and g.schriftlich and g.sortierung == "klasse"
    assert "E-Kurs" in g.beschreibung
    with pytest.raises(StammdatenFehler, match="gibt es"):
        kurs(sd, jahr)
    with pytest.raises(StammdatenFehler, match="Sekundarstufe II"):
        kurs(sd, jahr, bezeichnung="Q1 M", notensystem="sek2")
    with pytest.raises(StammdatenFehler):
        kurs(sd, jahr, bezeichnung="X", niveau="Z")
    k = kurs(sd, jahr, bezeichnung="8.4 Deutsch", fach="Deutsch", art="klasse", jahrgang=8, niveau="")
    assert [x.bezeichnung for x in sd.lerngruppen(jahr.id)] == ["8.4 Deutsch", "M9.3E"]
    sd.loesche_lerngruppe(k.id)
    assert len(sd.lerngruppen(jahr.id)) == 1


def _kursbelegung(sd, jahr):
    g = kurs(sd, jahr)
    ids = {}
    for nach, vor, kl in [("Zander", "Zoe", "9.1"), ("Adler", "Anna", "9.3"), ("Müller", "Max", "9.1"),
                          ("Özkan", "Deniz", "9.10"), ("Becker", "Ben", "9.3")]:
        ids[nach] = sd.lege_schueler_an(jahr.id, nach, vor, kl).id
    assert sd.fuege_hinzu(g.id, list(ids.values())) == 5
    return g, ids


def test_sortierung_standard_klasse_dann_alphabet(sd, jahr):
    g, _ = _kursbelegung(sd, jahr)
    m = sd.mitglieder(g.id)
    assert [x.schueler.nachname for x in m] == ["Müller", "Zander", "Adler", "Becker", "Özkan"]
    assert [x.nummer for x in m] == [1, 2, 3, 4, 5]


def test_sortierung_alphabet(sd, jahr):
    g, _ = _kursbelegung(sd, jahr)
    sd.setze_sortierung(g.id, "alphabet")
    assert [x.schueler.nachname for x in sd.mitglieder(g.id)] == ["Adler", "Becker", "Müller", "Özkan", "Zander"]


def test_eigene_reihenfolge(sd, jahr):
    g, ids = _kursbelegung(sd, jahr)
    sd.setze_sortierung(g.id, "eigene")  # startet mit der bisherigen Anzeige (Klasse → Alphabet)
    assert [x.schueler.nachname for x in sd.mitglieder(g.id)] == ["Müller", "Zander", "Adler", "Becker", "Özkan"]
    sd.verschiebe(g.id, ids["Özkan"], -10)
    sd.verschiebe(g.id, ids["Müller"], 1)
    assert [x.schueler.nachname for x in sd.mitglieder(g.id)] == ["Özkan", "Zander", "Müller", "Adler", "Becker"]
    neu = sd.lege_schueler_an(jahr.id, "Neu", "Nina", "9.1").id
    sd.fuege_hinzu(g.id, [neu])
    assert sd.mitglieder(g.id)[-1].schueler.id == neu  # Neue kommen ans Ende
    sd.setze_sortierung(g.id, "klasse")
    sd.setze_sortierung(g.id, "eigene")  # eigene Reihenfolge bleibt erhalten
    assert sd.mitglieder(g.id)[0].schueler.nachname == "Özkan"


def test_doppelt_hinzufuegen_wird_ignoriert(sd, jahr):
    g, ids = _kursbelegung(sd, jahr)
    assert sd.fuege_hinzu(g.id, [ids["Adler"]]) == 0


def test_klasse_uebernehmen(sd, jahr):
    for n in ("A", "B", "C"):
        sd.lege_schueler_an(jahr.id, n, "x", "8.4")
    weg = sd.lege_schueler_an(jahr.id, "D", "x", "8.4")
    sd.abgang(weg.id, jahr.id, date(2026, 9, 30))
    sd.lege_schueler_an(jahr.id, "Fremd", "x", "8.2")
    g = kurs(sd, jahr, bezeichnung="8.4 D", fach="Deutsch", art="klasse", jahrgang=8, niveau="")
    assert sd.uebernimm_klasse(g.id, "8.4", von=date(2026, 11, 1)) == 3  # Abgang vorher → nicht übernommen
    assert sd.uebernimm_klasse(g.id, "8.4", nur_aktive=False) == 1


def test_abgang_und_austritt(sd, jahr):
    g, ids = _kursbelegung(sd, jahr)
    sd.abgang(ids["Adler"], jahr.id, date(2027, 3, 15))
    sd.setze_zeitraum(g.id, ids["Becker"], None, date(2026, 12, 20))   # Kurswechsel
    sd.setze_zeitraum(g.id, ids["Zander"], date(2026, 11, 2), None)    # späterer Eintritt
    m = {x.schueler.nachname: x for x in sd.mitglieder(g.id)}
    assert m["Adler"].aktiv_am(date(2027, 3, 15)) and not m["Adler"].aktiv_am(date(2027, 3, 16))
    assert m["Adler"].status == "Abgang am 15.03.2027"
    assert not m["Becker"].aktiv_am(date(2027, 1, 10))
    assert m["Becker"].status == "ausgetreten am 20.12.2026"
    assert not m["Zander"].aktiv_am(date(2026, 10, 1)) and m["Zander"].aktiv_am(date(2026, 11, 2))
    assert len(sd.mitglieder(g.id)) == 5  # Daten bleiben erhalten
    sd.abgang(ids["Adler"], jahr.id, None)
    assert sd.mitglieder(g.id)[2].ende is None
    with pytest.raises(StammdatenFehler, match="vor dem Eintritt"):
        sd.setze_zeitraum(g.id, ids["Becker"], date(2027, 1, 1), date(2026, 12, 1))


def test_abgang_mit_spaeterem_kursaustritt_nimmt_frueheres_datum(sd, jahr):
    g, ids = _kursbelegung(sd, jahr)
    sd.setze_zeitraum(g.id, ids["Adler"], None, date(2027, 5, 1))
    sd.abgang(ids["Adler"], jahr.id, date(2027, 3, 1))
    m = next(x for x in sd.mitglieder(g.id) if x.schueler.id == ids["Adler"])
    assert m.ende == date(2027, 3, 1)


def test_mitglied_entfernen(sd, jahr):
    g, ids = _kursbelegung(sd, jahr)
    sd.entferne_mitglied(g.id, ids["Adler"])
    assert len(sd.mitglieder(g.id)) == 4
    assert sd.schueler(ids["Adler"])  # Person bleibt erhalten
    assert sd.lerngruppen_von(ids["Becker"], jahr.id)[0].id == g.id


def test_stammdaten_ueberleben_speichern_und_oeffnen(db, sd, jahr):
    g, _ = _kursbelegung(sd, jahr)
    db.speichern()
    pfad = db.pfad
    db.schliessen()
    db2 = Datenbank.oeffnen(pfad, PASSWORT, "Testpasswort1")
    try:
        sd2 = Stammdaten(db2.verbindung)
        assert len(sd2.mitglieder(g.id)) == 5
    finally:
        db2.schliessen(speichern=False)
    # Fixture schließt db ein zweites Mal – das muss gefahrlos gehen
    db.verbindung = db2.verbindung


def test_loeschen_kaskadiert(sd, jahr, db):
    g, ids = _kursbelegung(sd, jahr)
    with db.verbindung:
        db.verbindung.execute("DELETE FROM schuljahr WHERE id = ?", (jahr.id,))
    assert db.verbindung.execute("SELECT COUNT(*) FROM mitglied").fetchone()[0] == 0
    assert db.verbindung.execute("SELECT COUNT(*) FROM lerngruppe").fetchone()[0] == 0
