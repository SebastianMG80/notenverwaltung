"""Hilfe im Programm: Texte vollständig und offline, Verweise, Suche, F1 je Ansicht und Dialog."""

import ast
import re
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtTest import QTest

from notenverwaltung.hilfe import fenster as hf
from notenverwaltung.hilfe.texte import JE_KLASSE, THEMA, THEMEN

QUELLE = Path(__file__).resolve().parent.parent / "src" / "notenverwaltung"


def test_themen_vollstaendig_und_offline():
    schluessel = [t.schluessel for t in THEMEN]
    assert len(schluessel) == len(set(schluessel)) and "start" in THEMA
    for t in THEMEN:
        assert t.titel and f"<h2>{t.titel}</h2>" in t.html, t.schluessel
        assert not re.search(r"https?://|www\.|<img|src=", t.html), f"{t.schluessel}: nichts aus dem Netz laden"
        for ziel in re.findall(r'href="([^"]*)"', t.html):
            assert ziel.startswith("#") and ziel[1:] in THEMA, f"{t.schluessel}: toter Verweis {ziel}"
        # Gendern mit Doppelpunkt, nicht mit Sternchen oder Binnen-I
        assert not re.search(r"\w\*innen|\wInnen\b", hf.nur_text(t.html)), t.schluessel


def test_jedes_thema_ist_erreichbar():
    """Jede Seite ist aus dem Inhalt (Start) über Verweise oder über F1 erreichbar."""
    erreicht, offen = set(), ["start"] + list(set(JE_KLASSE.values())) + ["tasten", "probleme"]
    while offen:
        s = offen.pop()
        if s in erreicht:
            continue
        erreicht.add(s)
        offen += [z[1:] for z in re.findall(r'href="(#[^"]*)"', THEMA[s].html)]
    assert erreicht == set(THEMA)


def test_alle_dialoge_haben_ein_thema():
    """Jede Dialog- und Assistentenklasse der Oberfläche steht in JE_KLASSE (oder bekommt die Hilfe ihres Reiters)."""
    erlaubt_ohne = {"_Dialog", "VorschauDialog", "HilfeFenster"}   # Basisklasse; Vorschau erbt vom Reiter
    klassen = set()
    for datei in (QUELLE / "ui").rglob("*.py"):
        for knoten in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
            if isinstance(knoten, ast.ClassDef) and knoten.name.endswith(("Dialog", "Assistent")):
                klassen.add(knoten.name)
    fehlend = klassen - set(JE_KLASSE) - erlaubt_ohne
    assert not fehlend, f"Hilfethema fehlt für: {sorted(fehlend)}"
    assert set(JE_KLASSE.values()) <= set(THEMA)


def test_fenster_suche_und_verweise(app):
    w = hf.HilfeFenster()
    assert w.aktuell == "start" and "Erste Schritte" in w.text.toPlainText()
    w._verweis(QUrl("#schluessel"))
    assert w.aktuell == "schluessel" and w.liste.currentItem().text() == "Notenschlüssel"
    w._verweis(QUrl("https://example.org"))            # externe Verweise werden ignoriert
    assert w.aktuell == "schluessel"
    w.suche.setText("Avery")
    assert w.sichtbare_themen()[0] == "drucken" and "etiketten" in w.sichtbare_themen()
    assert w.aktuell == "drucken"
    w.suche.setText("Wiederherstellungscode")
    assert {"datenbank", "sicherheit", "probleme"} <= set(w.sichtbare_themen())
    w.suche.setText("")
    assert len(w.sichtbare_themen()) == len(THEMEN)
    assert not w.text.openExternalLinks() and not w.text.openLinks()


@pytest.fixture
def fenster(app, tmp_path, schnelle_kdf):
    from notenverwaltung.modell.stammdaten import Lerngruppe
    from notenverwaltung.speicher.datenbank import Datenbank
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    db, _ = Datenbank.neu(tmp_path / "h", "Testpasswort1")
    f = Hauptfenster()
    f.setze_datenbank(db)
    jahr = f.sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    f.wechsle_schuljahr(jahr)
    g = f.sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M"))
    f.show()
    yield f, g
    f.schliesse_datenbank()


def _f1(widget):
    from PySide6.QtWidgets import QApplication

    widget.setFocus()
    QApplication.processEvents()
    QTest.keyClick(widget, Qt.Key.Key_F1)
    QApplication.processEvents()
    return hf._fenster


def test_f1_je_ansicht(fenster):
    f, g = fenster
    f._navigation_fuellen(("gruppe", g.id))
    seite = f.seite_gruppe
    for reiter, thema in ((seite.arbeiten, "arbeiten"), (seite.muendlich, "muendlich"), (seite.noten, "noten"),
                          (seite.mitglieder, "lerngruppen")):
        seite.reiter.setCurrentWidget(reiter)
        assert f.hilfe_thema() == thema
        assert hf.thema_fuer(reiter) == thema
    seite.reiter.setCurrentWidget(seite.noten)
    w = _f1(f.navigation)                                   # Fokus links in der Leiste: Thema der Ansicht
    assert w is not None and w.isVisible() and w.aktuell == "noten"
    w.close()
    assert hf.thema_fuer(f.seite_schueler) == "schueler" and hf.thema_fuer(f.seite_jahr) == "schuljahr"
    assert hf.thema_fuer(None) == "start"


def test_f1_in_einem_modalen_dialog(fenster):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from notenverwaltung.ui.stammdaten_dialoge import SchuljahrDialog

    f, g = fenster
    d = SchuljahrDialog(f.sd, f.jahr, f)
    ergebnis = {}

    def im_dialog():
        w = _f1(d.bezeichnung)
        ergebnis["thema"] = w.aktuell if w else None
        ergebnis["besitzer"] = w.parentWidget() if w else None
        w.close()
        d.reject()

    QTimer.singleShot(0, im_dialog)
    d.exec()
    QApplication.processEvents()
    assert ergebnis == {"thema": "schuljahr", "besitzer": d}      # gehört zum Dialog, sonst wäre sie gesperrt


def test_hilfe_menue(fenster):
    f, g = fenster
    texte = [a.text() for m in f.menuBar().actions() if m.text() == "&Hilfe" for a in m.menu().actions()]
    assert any(t.startswith("&Hilfe zu dieser Ansicht") and t.endswith("\tF1") for t in texte)
    assert "&Tastenkürzel" in texte and "Ü&ber …" in texte
    w = hf.zeige_hilfe("tasten")
    assert w.aktuell == "tasten" and "Strg + L" in w.text.toPlainText()
    w.close()
