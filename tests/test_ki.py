"""KI-Paket: Prompt-Vorlage, Einlesen der Antwort, Übernahme als Arbeit."""

import json
from datetime import date

import pytest

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.ki import BEISPIEL, FORMAT, KiFehler, lies_antwort, prompt_vorlage
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank


def test_prompt_ohne_schuelerdaten():
    p = prompt_vorlage("Mathematik", 9, 40)
    assert "Mathematik" in p and "Jahrgang: 9" in p and "etwa 40" in p and FORMAT in p
    assert "Nachname" not in p and "Vorname" not in p   # keine Felder für Personendaten
    assert "erstelle" in prompt_vorlage(mit_erstellung=True).lower()


def test_antwort_mit_text_und_zaun():
    text = "Gern! Hier ist das Ergebnis:\n```json\n" + json.dumps(BEISPIEL, ensure_ascii=False) + "\n```\nViel Erfolg!"
    k = lies_antwort(text)
    assert k.titel == "2. Klassenarbeit" and [a.bezeichnung for a in k.aufgaben] == ["1", "2a", "b"]
    assert k.hoechstpunkte == 10 and k.aufgaben[0].thema == "Steigung aus zwei Punkten"
    assert k.musterloesung.startswith("Aufgabe 1")


def test_antwort_ohne_zaun_mit_klammern_im_text():
    d = dict(BEISPIEL, musterloesung="Menge {1, 2} und \"Zitat\"")
    k = lies_antwort("Antwort: " + json.dumps(d) + " – Ende")
    assert k.musterloesung == 'Menge {1, 2} und "Zitat"'


@pytest.mark.parametrize("text,meldung", [
    ("nur Text", "kein JSON"),
    ('{"aufgaben": []}', "keine Aufgaben"),
    ('{"aufgaben": [{"bezeichnung": "1", "punkte": "viele"}]}', "keine Punktzahl"),
    ('{"aufgaben": [{"bezeichnung": "1", "punkte": 1.3}]}', "nicht zulässig"),
    ('{"aufgaben": [{"punkte": 2}]}', "keine Bezeichnung"),
    ('{"format": "anderes", "aufgaben": [{"bezeichnung": "1", "punkte": 2}]}', "Unbekanntes Format"),
    ('{"aufgaben": [', "unvollständig"),
])
def test_fehlerhafte_antworten(text, meldung):
    with pytest.raises(KiFehler, match=meldung):
        lies_antwort(text)


def test_punkte_als_text_mit_komma():
    k = lies_antwort('{"aufgaben": [{"bezeichnung": "1", "punkte": "2,5"}]}')
    assert k.aufgaben[0].punkte == 2.5


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "k", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    sid = sd.lege_schueler_an(jahr.id, "Muster", "Hans", "9.1").id
    sd.fuege_hinzu(g.id, [sid])
    yield Arbeiten(db.verbindung), jahr, g, sid
    db.schliessen(speichern=False)


def test_dialog_neue_arbeit(umgebung):
    from notenverwaltung.ui.ki_dialog import KiDialog

    ar, jahr, g, sid = umgebung
    d = KiDialog(ar, jahr, g)
    assert "Mathematik" in d.prompt.toPlainText()
    assert not d.k_neu.isEnabled()
    d.antwort.setPlainText(json.dumps(BEISPIEL))
    assert d.k_neu.isEnabled() and d.vorschau.rowCount() == 3
    d.datum.setze(date(2026, 11, 20))
    d._neu()
    a = d.ergebnis
    assert a.titel == "2. Klassenarbeit" and a.thema == "Lineare Funktionen" and a.musterloesung.startswith("Aufgabe 1")
    assert [x.erwartung[:5] for x in ar.aufgaben(a.id)][0] == "m = ("


def test_dialog_in_vorhandene_arbeit(umgebung, monkeypatch):
    from notenverwaltung.ui import ki_dialog

    ar, jahr, g, sid = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 5), ("2", 5), ("3", 5), ("4", 5)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, 3)
    d = ki_dialog.KiDialog(ar, jahr, g, a)
    d.antwort.setPlainText(json.dumps(BEISPIEL))
    monkeypatch.setattr(ki_dialog, "frage", lambda *x, **k: True)
    d._uebernehmen()
    assert [x.bezeichnung for x in ar.aufgaben(a.id)] == ["1", "2a", "b"]
    assert ar.ergebnisse(a.id)[0].summe == 3          # Punkte der ersten Aufgabe bleiben erhalten
    assert ar.arbeit(a.id).musterloesung


def test_dialog_konflikt_mit_punkten(umgebung):
    from notenverwaltung.ui.ki_dialog import KiDialog

    ar, jahr, g, sid = umgebung
    a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 10)])
    ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, 8)
    d = KiDialog(ar, jahr, g, a)
    d.antwort.setPlainText(json.dumps(BEISPIEL))   # Aufgabe 1 hätte nur noch 4 Punkte
    d._uebernehmen()
    assert "über der neuen" in d.meldung.text()
    assert ar.aufgaben(a.id)[0].max_punkte == 10    # nichts verändert
