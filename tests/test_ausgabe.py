"""Druckausgaben: Etikettenmaße, Notenabschnitte, Punkteliste, Vorschau, Druckdialog."""

import shutil
import subprocess
from datetime import date

import pytest
from PySide6.QtWidgets import QFileDialog

from notenverwaltung.ausgabe.abschnitte import AVERY_3424, AVERY_3425, Notenabschnitte, freies_format
from notenverwaltung.ausgabe.punkteliste import ListenOptionen, Punkteliste
from notenverwaltung.ausgabe.seite import als_pdf, vorschau
from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.noten import Note
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank

PDFTEXT = shutil.which("pdftotext")


def text(pfad) -> str:
    roh = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pfad), "-"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    return " ".join(roh.split())  # Leerraum vereinheitlichen: Abstände hängen von der Schrift ab


@pytest.fixture
def arbeit(app, tmp_path, schnelle_kdf):
    db, _ = Datenbank.neu(tmp_path / "d", "Testpasswort1")
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    ids = [sd.lege_schueler_an(jahr.id, f"Name{i:02d}", f"Vor{i:02d}", "9.1").id for i in range(1, 41)]
    sd.fuege_hinzu(g.id, ids)
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "1. Klassenarbeit", date(2026, 11, 10), [("1", 10), ("2a", 5), ("b", 5)],
                          rueckgabe=date(2026, 11, 20))
    x1, x2, x3 = ar.aufgaben(a.id)
    for i, sid in enumerate(ids[:30]):
        ar.setze_punkte(x1.id, sid, i % 11)
        ar.setze_punkte(x2.id, sid, min(5, i % 6))
        if i != 3:
            ar.setze_punkte(x3.id, sid, 4)
    yield ar, a, ids
    db.schliessen(speichern=False)


def test_avery_masse():
    """Beide Bögen füllen A4 exakt: seitlich randlos, oben/unten gleich."""
    for fmt, rand in ((AVERY_3424, 4.5), (AVERY_3425, 6.0)):
        assert fmt.spalten * fmt.breite == 210
        x, y = fmt.position(fmt.je_seite - 1)
        assert x + fmt.breite == 210
        assert y + fmt.hoehe == pytest.approx(297 - rand)
        assert fmt.position(0) == (0, rand)
    assert (AVERY_3424.breite, AVERY_3424.hoehe, AVERY_3424.je_seite) == (105, 48, 12)
    assert (AVERY_3425.breite, AVERY_3425.hoehe, AVERY_3425.je_seite) == (105, 57, 10)


def test_freies_format():
    f = freies_format(100, 50)
    assert (f.spalten, f.zeilen) == (2, 5) and f.rahmen
    assert f.rand_links == 5
    with pytest.raises(ValueError):
        freies_format(40, 20)


def test_abschnitte_seiten_und_startplatz(arbeit):
    ar, a, ids = arbeit
    n = Notenabschnitte(ar, a, AVERY_3424)
    assert len(n.ergebnisse) == 30  # nur mit Note
    assert n.seitenzahl() == 3      # 30 / 12
    assert Notenabschnitte(ar, a, AVERY_3424, startplatz=6).seitenzahl() == 3   # 36 Plätze
    assert Notenabschnitte(ar, a, AVERY_3424, startplatz=7).seitenzahl() == 4   # 37 Plätze
    assert len(Notenabschnitte(ar, a, AVERY_3424, nur_mit_note=False).ergebnisse) == 40
    assert Notenabschnitte(ar, a, AVERY_3425).seitenzahl() == 3


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_abschnitte_ohne_tendenz(arbeit, tmp_path):
    ar, a, ids = arbeit
    ar.setze_teilnahme(a.id, ids[0], note_manuell=Note.aus_kurz("2+"))
    pdf = als_pdf(Notenabschnitte(ar, a, AVERY_3425, schueler_ids=[ids[0], ids[1]]), tmp_path / "a.pdf")
    t = text(pdf)
    assert "Vor01 Name01" in t and "Vor02 Name02" in t and "Vor03" not in t
    assert "gut" in t and "(+)" not in t and "2+" not in t  # keine Tendenz für Schüler:innen
    assert "20.11.2026" in t  # Rückgabedatum


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_punkteliste(arbeit, tmp_path):
    ar, a, ids = arbeit
    voll = Punkteliste(ar, a)
    assert voll.seitenzahl() == 2     # 40 Zeilen passen nicht auf eine Seite
    leer = Punkteliste(ar, a, ListenOptionen(leere_ausblenden=True))
    assert len(leer.zeilen) == 30
    t = text(als_pdf(voll, tmp_path / "l.pdf"))
    assert "1. Klassenarbeit – M9.3E" in t and "Notenspiegel" in t and "Notenschlüssel" in t
    assert "Name40" in t and "unvollständig" in t
    assert "Seite 2 von 2" in t


def test_punkteliste_fuss_auf_eigener_seite(arbeit):
    ar, a, ids = arbeit
    o = ListenOptionen(leere_ausblenden=True, durchschnitt=True)
    p = Punkteliste(ar, a, o)
    # 30 Zeilen füllen die erste Seite fast – der Fuß wandert ggf. auf eine eigene Seite
    assert p.seitenzahl() in (1, 2, 3)
    for i in range(p.seitenzahl()):
        vorschau(p, i, dpi=30)  # darf nicht abstürzen


def test_vorschau_groesse(arbeit):
    ar, a, _ = arbeit
    bild = vorschau(Notenabschnitte(ar, a, AVERY_3424), 0, dpi=50)
    assert (bild.width(), bild.height()) == (int(210 / 25.4 * 50), int(297 / 25.4 * 50))
    quer = vorschau(Punkteliste(ar, a), 0, dpi=50)
    assert quer.width() > quer.height()


def test_druckversatz_verschiebt(arbeit):
    from PySide6.QtGui import QImage, QPainter

    from notenverwaltung.ausgabe.seite import Seite

    bild = QImage(100, 100, QImage.Format.Format_RGB32)
    bild.setDotsPerMeterX(int(254 / 0.0254))   # 254 dpi → 10 px je mm
    bild.setDotsPerMeterY(int(254 / 0.0254))
    p = QPainter(bild)
    s = Seite(p, versatz_x_mm=1.5, versatz_y_mm=-1)
    assert s.x(0) == pytest.approx(15) and s.y(2) == pytest.approx(10)
    p.end()


def test_druckdialog(arbeit, tmp_path, monkeypatch):
    from notenverwaltung.ui.druck import DruckDialog

    ar, a, _ = arbeit
    d = DruckDialog(ar, a)
    assert isinstance(d.ausgabe, Punkteliste)
    d.opt["leere_ausblenden"].setChecked(True)
    assert len(d.ausgabe.zeilen) == 30
    d.art_abschnitte.setChecked(True)
    assert isinstance(d.ausgabe, Notenabschnitte)
    d.format.setCurrentIndex(d.format.findData("3425"))
    assert d.startplatz.maximum() == 10
    d.versatz_x.setValue(1.5)
    assert d.ausgabe.versatz_x == 1.5
    d.startplatz.setValue(4)
    assert d.ausgabe.startplatz == 3
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *x, **k: (str(tmp_path / "x"), "")))
    d.als_pdf()
    assert (tmp_path / "x.pdf").exists()
    # Einstellungen werden gemerkt
    d2 = DruckDialog(ar, a)
    assert d2.art_abschnitte.isChecked() and d2.format.currentData() == "3425" and d2.versatz_x.value() == 1.5


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_rueckmeldebogen(arbeit, tmp_path):
    from notenverwaltung.ausgabe.rueckmeldebogen import Rueckmeldebogen

    ar, a, ids = arbeit
    x = ar.aufgaben(a.id)
    ar.setze_aufgaben(a.id, [(x[0].id, "1", 10, "Bruchrechnung", "Hauptnenner bilden"), (x[1].id, "2a", 5, "", ""),
                             (x[2].id, "b", 5, "", "")])
    ar.setze_teilnahme(a.id, ids[0], note_manuell=Note.aus_kurz("2+"), kommentar="Weiter so – besonders Aufgabe 1!")
    b = Rueckmeldebogen(ar, a)
    assert b.seitenzahl() == 30
    t = text(als_pdf(Rueckmeldebogen(ar, a, schueler_ids=[ids[0]]), tmp_path / "b.pdf"))
    assert "Vor01 Name01" in t and "Bruchrechnung" in t and "Hauptnenner bilden" in t
    assert "gut" in t and "(+)" not in t and "2+" not in t
    assert "Weiter so" in t and "Kenntnis genommen" in t
    ohne = text(als_pdf(Rueckmeldebogen(ar, a, erwartung=False, unterschrift=False, schueler_ids=[ids[0]]),
                        tmp_path / "c.pdf"))
    assert "Hauptnenner" not in ohne and "Kenntnis" not in ohne


def test_druckdialog_rueckmeldebogen(arbeit):
    from notenverwaltung.ausgabe.rueckmeldebogen import Rueckmeldebogen
    from notenverwaltung.ui.druck import DruckDialog

    ar, a, _ = arbeit
    d = DruckDialog(ar, a)
    d.art_bogen.setChecked(True)
    assert isinstance(d.ausgabe, Rueckmeldebogen)
    assert d.box_bogen.isVisibleTo(d) and not d.box_liste.isVisibleTo(d)
    d.bogen_nur_note.setChecked(False)
    assert d.ausgabe.seitenzahl() == 40


def _tinte_spalten(bild) -> list[int]:
    """x-Positionen (Pixel), in denen etwas Nicht-Weißes gezeichnet ist."""
    from PySide6.QtGui import QColor

    weiss = QColor("#ffffff").rgb()
    return [x for x in range(bild.width()) if any(bild.pixel(x, y) != weiss for y in range(0, bild.height(), 2))]


def test_blattrand_etiketten(arbeit):
    """Am Papierrand bleibt der Inhalt mindestens `blattrand` weg (Drucker bedrucken die äußersten mm nicht)."""
    from notenverwaltung.ausgabe.abschnitte import BLATTRAND, INNENRAND

    ar, a, ids = arbeit
    n = Notenabschnitte(ar, a, AVERY_3424)
    assert n.blattrand == BLATTRAND == 7.0
    links = n.innenraender(0, 4.5, 105, 48)
    rechts = n.innenraender(105, 4.5, 105, 48)
    assert links == (7.0, INNENRAND, INNENRAND, INNENRAND)       # zur Mitte hin bleibt der Innenrand
    assert rechts == (INNENRAND, 7.0, INNENRAND, INNENRAND)
    n.versatz_x = 1.5                                            # Versatz nach rechts → rechts mehr Abstand nötig
    assert n.innenraender(105, 4.5, 105, 48)[1] == pytest.approx(8.5)
    assert n.innenraender(0, 4.5, 105, 48)[0] == pytest.approx(5.5)
    n.versatz_x = 0
    dpi = 100
    mm = dpi / 25.4
    spalten = _tinte_spalten(vorschau(n, 0, dpi=dpi))
    assert spalten and min(spalten) >= 6.6 * mm and max(spalten) <= (210 - 6.6) * mm   # Kantenglättung: ±1 Pixel
    # ohne Mindestabstand reicht der Inhalt näher an den Rand (so war es bis 0.3.2)
    alt = Notenabschnitte(ar, a, AVERY_3424, blattrand=0)
    spalten = _tinte_spalten(vorschau(alt, 0, dpi=dpi))
    assert max(spalten) > (210 - 6.0) * mm


@pytest.mark.skipif(not PDFTEXT, reason="pdftotext fehlt")
def test_note_ohne_punkte_im_ausdruck(arbeit, tmp_path):
    """Nachschreiber:in mit festgesetzter Note, aber ohne Punkte: keine leere Tabelle, nur die Note."""
    from notenverwaltung.ausgabe.rueckmeldebogen import Rueckmeldebogen

    ar, a, ids = arbeit
    ar.setze_teilnahme(a.id, ids[35], note_manuell=Note.aus_kurz("2-"))
    a = ar.arbeit(a.id)
    n = Notenabschnitte(ar, a, AVERY_3424, schueler_ids=[ids[0], ids[35]])
    t = text(als_pdf(n, tmp_path / "a.pdf"))
    assert t.count("Bewertet ohne Einzelpunkte.") == 1 and "gut" in t and "max. Punkte" in t   # eine mit, eine ohne
    b = Rueckmeldebogen(ar, a)
    seite = next(i for i, e in enumerate(b.ergebnisse) if e.mitglied.schueler.id == ids[35])
    t = text(als_pdf(b, tmp_path / "b.pdf"))
    assert "Diese Arbeit wurde ohne Einzelpunkte bewertet." in t
    assert seite >= 0 and t.count("Diese Arbeit wurde ohne Einzelpunkte bewertet.") == 1
