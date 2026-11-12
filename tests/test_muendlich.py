"""Mündliche Noten: Zeiträume, Eingabe, Austritte, Halbjahresschnitt."""

from datetime import date

import pytest

from notenverwaltung.modell.muendlich import Muendlich, MuendlichFehler, note_aus_eingabe, standard_zeitraeume
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.speicher.krypto import KdfParameter


@pytest.fixture
def umgebung(tmp_path):
    db, _ = Datenbank.neu(tmp_path / "m", "Testpasswort1", KdfParameter(1, 1, 1024))
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "9.1 EK", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    ids = [sd.lege_schueler_an(jahr.id, n, "x", "9.1").id for n in ("A", "B", "C")]
    sd.fuege_hinzu(g.id, ids)
    yield sd, Muendlich(db.verbindung), jahr, g, ids
    db.schliessen(speichern=False)


def test_eingabe():
    assert note_aus_eingabe("2-").kurz == "2-"
    assert note_aus_eingabe("1,7").kurz == "2+"
    assert note_aus_eingabe("2.3").kurz == "2-"
    assert note_aus_eingabe("2,5").kurz == "2-"   # gleich weit von 2- (2,3) und 3+ (2,7) → die bessere Note
    assert note_aus_eingabe("6").kurz == "6"
    assert note_aus_eingabe("") is None
    with pytest.raises(MuendlichFehler):
        note_aus_eingabe("gut")
    with pytest.raises(MuendlichFehler):
        note_aus_eingabe("7")


def test_standard_quartale(umgebung):
    sd, mu, jahr, g, ids = umgebung
    q = standard_zeitraeume(jahr)
    assert [x[0] for x in q] == ["1. Quartal", "2. Quartal", "3. Quartal", "4. Quartal"]
    assert q[0][1] == jahr.beginn and q[1][2] == date(2027, 1, 31) and q[2][1] == jahr.halbjahreswechsel
    assert q[3][2] == jahr.ende
    z = mu.zeitraeume(g.id)  # werden beim ersten Zugriff angelegt
    assert len(z) == 4 and z[0].ende < z[1].beginn


def test_zeitraeume_pruefen(umgebung):
    sd, mu, jahr, g, ids = umgebung
    with pytest.raises(MuendlichFehler, match="Halbjahreswechsel"):
        mu.setze_zeitraeume(g.id, [(None, "X", date(2027, 1, 1), date(2027, 3, 1))])
    with pytest.raises(MuendlichFehler, match="überschneiden"):
        mu.setze_zeitraeume(g.id, [(None, "A", date(2026, 9, 1), date(2026, 10, 1)),
                                   (None, "B", date(2026, 9, 15), date(2026, 11, 1))])
    with pytest.raises(MuendlichFehler, match="Schuljahr"):
        mu.setze_zeitraeume(g.id, [(None, "A", date(2026, 7, 1), date(2026, 9, 1))])


def test_teilen_feiner(umgebung):
    sd, mu, jahr, g, ids = umgebung
    q1 = mu.zeitraeume(g.id)[0]
    mu.setze_note(q1.id, ids[0], note_aus_eingabe("2"))
    mu.teile(q1.id, date(2026, 9, 15), ("August/September", "Oktober"))
    z = mu.zeitraeume(g.id)
    assert [x.bezeichnung for x in z][:2] == ["August/September", "Oktober"]
    assert len(z) == 5
    assert mu.noten(g.id)[(q1.id, ids[0])][0].kurz == "2"   # Note bleibt beim ersten Teil
    with pytest.raises(MuendlichFehler, match="innerhalb"):
        mu.teile(q1.id, date(2027, 5, 1))


def test_noten_und_halbjahresschnitt(umgebung):
    sd, mu, jahr, g, ids = umgebung
    q = mu.zeitraeume(g.id)
    mu.setze_note(q[0].id, ids[0], note_aus_eingabe("2+"))
    mu.setze_note(q[1].id, ids[0], note_aus_eingabe("3"), "ruhiger geworden")
    mu.setze_note(q[2].id, ids[0], note_aus_eingabe("1"))
    assert mu.halbjahresschnitt(g.id, ids[0], 1) == pytest.approx((1.7 + 3) / 2)
    assert mu.halbjahresschnitt(g.id, ids[0], 2) == pytest.approx(1)
    assert mu.halbjahresschnitt(g.id, ids[1], 1) is None
    assert mu.noten(g.id)[(q[1].id, ids[0])][1] == "ruhiger geworden"
    mu.setze_note(q[1].id, ids[0], note_aus_eingabe("3-"))  # Bemerkung bleibt
    assert mu.noten(g.id)[(q[1].id, ids[0])] == (note_aus_eingabe("3-"), "ruhiger geworden")
    mu.setze_note(q[1].id, ids[0], None)
    assert (q[1].id, ids[0]) not in mu.noten(g.id)


def test_keine_note_nach_austritt(umgebung):
    sd, mu, jahr, g, ids = umgebung
    sd.abgang(ids[1], jahr.id, date(2026, 10, 5))          # mitten im 1. Quartal
    sd.setze_zeitraum(g.id, ids[2], date(2027, 3, 1), None)  # tritt im 3. Quartal ein
    q = mu.zeitraeume(g.id)
    mu.setze_note(q[0].id, ids[1], note_aus_eingabe("3"))     # Abgangsquartal: erlaubt
    with pytest.raises(MuendlichFehler, match="nicht in der Lerngruppe"):
        mu.setze_note(q[1].id, ids[1], note_aus_eingabe("3"))
    with pytest.raises(MuendlichFehler):
        mu.setze_note(q[0].id, ids[2], note_aus_eingabe("2"))
    mu.setze_note(q[2].id, ids[2], note_aus_eingabe("2"))
