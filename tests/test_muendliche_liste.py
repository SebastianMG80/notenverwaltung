"""Druck der mündlichen Noten: Spalten, Format, Optionen, Bemerkungen, Seitenumbruch, Reiter-Knopf."""

import shutil
import subprocess
from datetime import date

import pytest

from notenverwaltung.ausgabe.muendliche_liste import MuendlicheListe, MuendlichOptionen
from notenverwaltung.ausgabe.seite import als_pdf, vorschau
from notenverwaltung.modell.muendlich import Muendlich
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank

PDFTEXT = shutil.which("pdftotext")


def text(pfad) -> str:
    roh = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pfad), "-"], capture_output=True).stdout
    return " ".join(roh.decode("utf-8", "replace").split())


@pytest.fixture
def umgebung(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "m", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "9.1 EK", "Erdkunde", "klasse", 9, "EK", schriftlich=False))
    ids = [sd.lege_schueler_an(jahr.id, n, "Test", "9.1").id for n in ("Adler", "Biber", "Dachs")]
    sd.fuege_hinzu(g.id, ids)
    mu = Muendlich(db.verbindung)
    q1, q2, q3, q4 = mu.zeitraeume(g.id)
    mu.setze_note(q1.id, ids[0], Note.aus_kurz("2+"), "arbeitet gut mit")
    mu.setze_note(q2.id, ids[0], Note.aus_kurz("3"))
    mu.setze_note(q3.id, ids[0], Note.aus_kurz("2-"))
    mu.setze_note(q1.id, ids[1], Note.aus_kurz("4"))
    yield sd, mu, jahr, g, ids
    db.schliessen(speichern=False)


def test_spalten_und_format(umgebung):
    sd, mu, jahr, g, ids = umgebung
    li = MuendlicheListe(mu, g.id)
    arten = [a for _, a, _, _ in li._spalten()]
    assert arten.count("z") == 4 and arten.count("ø") == 2
    assert not li.quer and li.seitenzahl() == 1
    assert sum(b for _, _, b, _ in li._spalten()) == pytest.approx(li.breite)   # Tabelle füllt die Seite
    # nur 1. Halbjahr: zwei Quartale + ein Mittel
    li = MuendlicheListe(mu, g.id, MuendlichOptionen(halbjahr=1))
    assert [a for _, a, _, _ in li._spalten()].count("z") == 2
    assert li.titel.endswith("1. Halbjahr")
    # viele Zeiträume → Querformat, Spalten bleiben lesbar
    for z in mu.zeitraeume(g.id):
        mu.teile(z.id, z.beginn + (z.ende - z.beginn) / 2)
    li = MuendlicheListe(mu, g.id)
    assert len(li.zeitraeume) == 8 and li.quer and li.spalte >= 10
    assert sum(b for _, _, b, _ in li._spalten()) <= li.breite + 1e-6


def test_mittel_und_ausblenden(umgebung):
    sd, mu, jahr, g, ids = umgebung
    li = MuendlicheListe(mu, g.id)
    adler = li.mitglieder[0]
    assert li._mittel(adler, 1) == pytest.approx((1.7 + 3.0) / 2)
    assert li._mittel(adler, 2) == pytest.approx(2.3)
    assert len(li.mitglieder) == 3
    assert len(MuendlicheListe(mu, g.id, MuendlichOptionen(leere_ausblenden=True)).mitglieder) == 2
    # Leerliste: keine Noten, keine Mittel, höhere Zeilen; „leer ausblenden“ wirkt dort nicht
    leer = MuendlicheListe(mu, g.id, MuendlichOptionen(leerliste=True, leere_ausblenden=True))
    assert leer.noten == {} and not leer.mit_mittel and leer.zeile > li.zeile and len(leer.mitglieder) == 3
    assert leer.titel.startswith("Liste zum Eintragen")


def test_ausgetretene(umgebung):
    sd, mu, jahr, g, ids = umgebung
    sd.setze_zeitraum(g.id, ids[2], None, date(2026, 9, 15))     # im 1. Quartal ausgetreten
    assert len(MuendlicheListe(mu, g.id).mitglieder) == 3                          # im 1. Hj. noch dabei
    assert len(MuendlicheListe(mu, g.id, MuendlichOptionen(halbjahr=2)).mitglieder) == 2
    assert len(MuendlicheListe(mu, g.id, MuendlichOptionen(halbjahr=2, ausgetretene=True)).mitglieder) == 3


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_pdf_inhalt(umgebung, tmp_path):
    sd, mu, jahr, g, ids = umgebung
    t = text(als_pdf(MuendlicheListe(mu, g.id), tmp_path / "a.pdf"))
    assert "Mündliche Noten 9.1 EK" in t and "Adler, Test" in t and "1. Quartal" in t
    assert "2+" in t and "2-" in t and "2,35" in t and "2,30" in t
    assert "Bemerkungen" not in t and "arbeitet" not in t
    t = text(als_pdf(MuendlicheListe(mu, g.id, MuendlichOptionen(tendenzen=False, bemerkungen=True)),
                     tmp_path / "b.pdf"))
    assert "2+" not in t and "2-" not in t and "ganze Noten" in t
    assert "Bemerkungen" in t and "arbeitet gut mit" in t and "Adler, Test – 1. Quartal (2)" in t
    t = text(als_pdf(MuendlicheListe(mu, g.id, MuendlichOptionen(leerliste=True)), tmp_path / "c.pdf"))
    assert "Liste zum Eintragen" in t and "Dachs, Test" in t and "2+" not in t and "Ø" not in t


def test_seitenumbruch_mit_bemerkungen(umgebung, tmp_path):
    sd, mu, jahr, g, ids = umgebung
    neu = [sd.lege_schueler_an(jahr.id, f"Name{i:02d}", "Vor", "9.1").id for i in range(40)]
    sd.fuege_hinzu(g.id, neu)
    q1 = mu.zeitraeume(g.id)[0]
    lang = "Beteiligt sich regelmäßig, bringt eigene Ideen ein und hilft anderen. " * 6
    for sid in neu:
        mu.setze_note(q1.id, sid, Note.aus_kurz("2"), lang)
    li = MuendlicheListe(mu, g.id, MuendlichOptionen(bemerkungen=True))
    tabellen = [s for s in li._seiten if s.zeilen]
    assert len(tabellen) == 2 and sum(len(s.zeilen) for s in tabellen) == 43
    assert li.seitenzahl() > 2                                         # Bemerkungen brauchen weitere Seiten
    assert sum(s.bem_titel for s in li._seiten) == 1                   # Überschrift genau einmal
    assert sum(len(s.bemerkungen) for s in li._seiten) == 41
    for s in li._seiten:                                               # nichts läuft unten über den Rand
        if s.bemerkungen:
            h = (8.0 if s.bem_titel else 0) + sum((len(z) + 1) * 4.5 + 1.5 for _, z in s.bemerkungen)
            assert s.bem_y + h <= 12 + li.hoehe + 1e-6
    for i in range(li.seitenzahl()):
        assert not vorschau(li, i, dpi=30).isNull()
    if PDFTEXT:
        assert text(als_pdf(li, tmp_path / "d.pdf")).count("Bemerkungen") == 1


def test_reiter_drucken(umgebung, monkeypatch):
    from notenverwaltung.ui import vorschau_dialog
    from notenverwaltung.ui.seiten.muendlich_tab import MuendlichTab

    sd, mu, jahr, g, ids = umgebung
    monkeypatch.setattr(vorschau_dialog.VorschauDialog, "exec", lambda self: 0)
    t = MuendlichTab()
    t.zeige(sd, jahr, g)
    t.drucken()
    d = t._druckdialog
    assert d.ausgabe.seitenzahl() == 1 and d.ausgabe.titel.startswith("Mündliche Noten")
    from PySide6.QtWidgets import QCheckBox

    haken = {c.text(): c for c in d.findChildren(QCheckBox)}
    tendenz = haken["Tendenzen zeigen (2+ statt 2)"]
    haken["Ohne Noten (Liste zum Eintragen)"].setChecked(True)
    assert not tendenz.isEnabled() and d.ausgabe.titel.startswith("Liste zum Eintragen")
