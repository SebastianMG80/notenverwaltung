"""Schüler:innen-Bogen: alles zu einer Person über alle Gruppen und Schuljahre, mit Weglass-Häkchen."""

import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from notenverwaltung.ausgabe.personenbogen import BogenOptionen, PersonenbogenAusgabe
from notenverwaltung.ausgabe.seite import als_pdf
from notenverwaltung.modell.personenbogen import personenbogen
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank

PDFTEXT = shutil.which("pdftotext")
QUELLE = Path(__file__).parent / "daten" / "version_0_9_0.nvdb"


def text(pfad) -> str:
    roh = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pfad), "-"], capture_output=True).stdout
    return " ".join(roh.decode("utf-8", "replace").split())


@pytest.fixture
def db(app, tmp_path):
    ziel = tmp_path / QUELLE.name
    shutil.copy2(QUELLE, ziel)
    d = Datenbank.oeffnen(ziel, "passwort", "Versionsprüfung 2026 – Ärger vermeiden")
    yield d
    d.schliessen(speichern=False)


def _sid(db, nachname: str) -> int:
    return next(e.schueler.id for j in Stammdaten(db.verbindung).schuljahre()
                for e in Stammdaten(db.verbindung).schueler_im_jahr(j.id) if e.schueler.nachname == nachname)


def test_inhalt_ueber_zwei_schuljahre(db):
    from notenverwaltung.modell.stunden import Stunden

    sd = Stammdaten(db.verbindung)
    sid = _sid(db, "Öztürk")
    ek = next(g for g in sd.lerngruppen(sd.schuljahre()[0].id) if g.fach == "Erdkunde")
    Stunden(db.verbindung).setze(ek.id, sid, date(2026, 9, 17), 2, "Karte erklärt")
    b = personenbogen(db.verbindung, sid)
    assert b.schueler.vorname == "Ayşe"
    assert [(j.jahr.bezeichnung, j.klasse) for j in b.jahre] == [("2026/27", "9.4"), ("2025/26", "8.4")]
    d9 = next(g for g in b.jahre[0].gruppen if g.gruppe.fach == "Deutsch")
    assert {k: n.kurz for k, n in d9.zeugnis.items()} == {"q1": "3", "hj1": "3"}
    assert [(a.titel, a.punkte, a.hoechst, a.status) for a in d9.arbeiten] == [
        ("1. Klassenarbeit", 25.25, 40, ""), ("2. Klassenarbeit", None, 30, "schreibt nach")]
    assert [m.zeitraum for m in d9.muendlich] == ["Sept.", "Okt.", "3. Quartal"]
    ekb = next(g for g in b.jahre[0].gruppen if g.gruppe.fach == "Erdkunde")
    assert ekb.beobachtungen[0].zeitraum == "1. Quartal" and ekb.beobachtungen[0].notizen == [
        (date(2026, 9, 17), "+", "Karte erklärt")]
    alt = b.jahre[1].gruppen[0]
    assert alt.gruppe.bezeichnung == "D 8.4" and alt.zeugnis["hj2"].kurz == "1"
    # Kommentar und Bemerkung einer anderen Person
    andere = personenbogen(db.verbindung, _sid(db, "Achterberg"))
    lk = andere.jahre[0].gruppen[0]
    assert lk.gruppe.kursart == "LK" and lk.arbeiten[0].note.punkte >= 0


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_ausdruck_mit_und_ohne(db, tmp_path):
    sd = Stammdaten(db.verbindung)
    sid = _sid(db, "Weiß")
    b = personenbogen(db.verbindung, sid)
    voll = text(als_pdf(PersonenbogenAusgabe(b), tmp_path / "v.pdf"))
    assert "Jörg Weiß" in voll and "Schuljahr 2026/27 · Klasse 9.4" in voll and "Vertraulich" in voll
    assert "Schnellerfassung" in voll and "Schuljahr 2025/26 · Klasse 8.4" in voll
    assert "Rückmeldung: Sehr gut belegt – weiter so!" in voll
    assert "Punkte" in voll and "Seite 1 von 1" in voll
    eltern = text(als_pdf(PersonenbogenAusgabe(b, BogenOptionen.fuer_eltern()), tmp_path / "e.pdf"))
    assert "Schnellerfassung" not in eltern and "Rückmeldung: Sehr gut belegt" in eltern
    ohne = text(als_pdf(PersonenbogenAusgabe(b, BogenOptionen(punkte=False, rueckmeldungen=False)), tmp_path / "o.pdf"))
    assert "Rückmeldung" not in ohne and " / 40" not in ohne
    # Tendenzen: Weiß (Jörg) hat mündlich Noten mit Tendenz
    w = personenbogen(db.verbindung, _sid(db, "Weiß"))
    mit = text(als_pdf(PersonenbogenAusgabe(w), tmp_path / "m.pdf"))
    ganz = text(als_pdf(PersonenbogenAusgabe(w, BogenOptionen(tendenzen=False)), tmp_path / "g.pdf"))
    assert any(z in mit for z in ("+ ·", "- ·", "+ ", "- ")) and "Mündlich:" in ganz
    assert not any(f" {n}+" in ganz or f" {n}-" in ganz for n in range(1, 7))
    # nur das aktuelle Schuljahr
    nur = text(als_pdf(PersonenbogenAusgabe(w, BogenOptionen(fruehere_jahre=False)), tmp_path / "n.pdf"))
    assert "2025/26" not in nur and "2026/27" in nur


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_viele_eintraege_mehrere_seiten(app, tmp_path, schnelle_kdf):
    from notenverwaltung.modell.arbeiten import Arbeiten

    d, _ = Datenbank.neu(tmp_path / "v", "Testpasswort1")
    sd = Stammdaten(d.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    sid = sd.lege_schueler_an(jahr.id, "Muster", "Mara", "9.2").id
    ar = Arbeiten(d.verbindung)
    for f in range(8):
        g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, f"F{f} 9", f"Fach {f}", "kurs", 9, ""))
        sd.fuege_hinzu(g.id, [sid])
        for k in range(4):
            a = ar.lege_arbeit_an(g.id, f"{k + 1}. Arbeit", date(2026, 9, 1 + k), [("1", 10)])
            ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, 5 + k)
            ar.setze_teilnahme(a.id, sid, kommentar="Ordentlich gelöst. " * 6)
    a = PersonenbogenAusgabe(personenbogen(d.verbindung, sid))
    assert a.seitenzahl() >= 2
    t = text(als_pdf(a, tmp_path / "p.pdf"))
    assert t.count("Ordentlich gelöst.") == 8 * 4 * 6 and f"Seite {a.seitenzahl()} von {a.seitenzahl()}" in t
    for seite in a._plan():                                      # nichts ragt über den unteren Rand
        y, e = seite[-1]
        assert y + e.hoehe <= 297 - 16.0 + 0.01
    leer = PersonenbogenAusgabe(personenbogen(d.verbindung, sd.lege_schueler_an(jahr.id, "Neu", "Nina", "9.2").id))
    assert "Keine Noten in diesem Schuljahr." in text(als_pdf(leer, tmp_path / "l.pdf"))
    d.schliessen(speichern=False)


def test_oeffnen_aus_dem_programm(app, db, monkeypatch):
    from notenverwaltung.ui.hauptfenster import Hauptfenster
    from notenverwaltung.ui.schnellsuche import SchnellsucheDialog, Treffer
    from notenverwaltung.ui.vorschau_dialog import VorschauDialog

    monkeypatch.setattr(VorschauDialog, "exec", lambda self: 0)
    f = Hauptfenster()
    f.setze_datenbank(db)
    sid = _sid(db, "Öztürk")
    # ohne gewählte Person: erst suchen
    monkeypatch.setattr(SchnellsucheDialog, "exec",
                        lambda self: (setattr(self, "gewaehlt", Treffer("person", "", sid)), 1)[1])
    f._navigation_fuellen(("jahr", None))
    f.personenbogen()
    assert "Öztürk" in f._bogendialog.windowTitle() and f._bogendialog.ausgabe.seitenzahl() == 1
    # „Für Eltern“ setzt die Häkchen
    d = f._bogendialog
    from PySide6.QtWidgets import QPushButton
    next(k for k in d.findChildren(QPushButton) if k.text().startswith("Für die Weitergabe")).click()
    assert not d.haken["tendenzen"].isChecked() and not d.haken["beobachtungen"].isChecked()
    assert d.haken["rueckmeldungen"].isChecked() and not d.ausgabe.o.tendenzen
    # aus der Liste der Schüler:innen
    f._navigation_fuellen(("schueler", None))
    f.seite_schueler.markiere_person(sid)
    assert f.seite_schueler.k_bogen.isEnabled()
    f.seite_schueler.bogen()
    assert "Öztürk" in f.seite_schueler._bogendialog.windowTitle()
    # aus einer Lerngruppe: gewählte Zeile
    g = next(g for g in f.sd.lerngruppen(f.jahr.id) if g.fach == "Deutsch")
    f.oeffne_gruppe(g.id, "arbeiten", schueler_id=sid)
    assert f.seite_gruppe.aktuelle_person() == sid
    f.personenbogen()
    assert "Öztürk" in f._bogendialog.windowTitle()
    f.db = None                                                   # Datenbank gehört der Fixture
