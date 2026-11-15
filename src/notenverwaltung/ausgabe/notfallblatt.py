"""Notfallblatt mit Wiederherstellungscode (Text und QR-Code) und Datenschutzhinweis."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter

from notenverwaltung import texte
from notenverwaltung.ausgabe.seite import Seite, zeichne_pdf
from notenverwaltung.speicher.datenbank import nur_eigentuemer

MONO = "Monospace"
LINKS = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop


def zeichne(painter: QPainter, datenbankname: str, code: str, erstellt: datetime | None = None) -> None:
    s = Seite(painter)
    erstellt = erstellt or datetime.now()
    rand, breite = 20.0, 170.0
    y = 20.0

    s.stift("#000000")
    s.schrift(20, fett=True)
    s.text(rand, y, breite, 10, "Notfallblatt", LINKS)
    y += 11
    s.schrift(11)
    s.stift("#444444")
    s.text(rand, y, breite, 6, "Notenverwaltung – Wiederherstellung der Datenbank", LINKS)
    y += 12

    s.stift("#000000")
    s.schrift(11)
    for bez, wert in (("Datenbank:", datenbankname), ("Erstellt am:", erstellt.strftime("%d.%m.%Y, %H:%M Uhr"))):
        s.schrift(11, fett=True)
        s.text(rand, y, 32, 6, bez, LINKS)
        s.schrift(11)
        s.text(rand + 32, y, breite - 32, 6, wert, LINKS)
        y += 7
    y += 6

    # Code-Kasten mit QR-Code rechts
    kasten_h = 52.0
    s.stift("#000000", 0.4)
    s.kasten(rand, y, breite, kasten_h, fuellung="#f2f2f2", radius_mm=2)
    s.schrift(10, fett=True)
    s.text(rand + 6, y + 5, 100, 6, "Wiederherstellungscode", LINKS)
    gruppen = code.split("-")
    s.schrift(17, fett=True, familie=MONO)
    s.text(rand + 6, y + 15, 115, 10, "-".join(gruppen[:3]), LINKS)
    s.text(rand + 6, y + 27, 115, 10, "-".join(gruppen[3:]), LINKS)
    s.schrift(8)
    s.stift("#444444")
    s.text(rand + 6, y + 41, 110, 6, "Verwechslungsfreie Zeichen: kein I, L, O oder U.", LINKS)
    _qr(s, code, rand + breite - 46, y + 5, 42)
    y += kasten_h + 10

    s.stift("#000000")
    s.schrift(11)
    h = s.texthoehe_mm(breite, texte.NOTFALL_ERKLAERUNG)
    s.text(rand, y, breite, h, texte.NOTFALL_ERKLAERUNG, LINKS, umbruch=True)
    y += h + 7

    s.schrift(12, fett=True)
    s.text(rand, y, breite, 7, "So wird der Code benutzt", LINKS)
    y += 8
    s.schrift(11)
    for i, schritt in enumerate(texte.NOTFALL_SCHRITTE, 1):
        h = s.texthoehe_mm(breite - 8, schritt)
        s.text(rand, y, 8, h, f"{i}.", LINKS)
        s.text(rand + 8, y, breite - 8, h, schritt, LINKS, umbruch=True)
        y += h + 2
    y += 4
    h = s.texthoehe_mm(breite, texte.NOTFALL_ERSATZ)
    s.text(rand, y, breite, h, texte.NOTFALL_ERSATZ, LINKS, umbruch=True)
    y += h + 10

    # Datenschutzhinweis
    s.schrift(10)
    h_text = s.texthoehe_mm(breite - 10, texte.DATENSCHUTZ)
    s.stift("#000000", 0.3)
    s.kasten(rand, y, breite, h_text + 15, radius_mm=2)
    s.schrift(11, fett=True)
    s.text(rand + 5, y + 4, breite - 10, 6, texte.DATENSCHUTZ_TITEL, LINKS)
    s.schrift(10)
    s.text(rand + 5, y + 11, breite - 10, h_text, texte.DATENSCHUTZ, LINKS, umbruch=True)

    s.schrift(8)
    s.stift("#666666")
    s.text(rand, 280, breite, 5,
           "Dieses Blatt gilt, bis im Programm ein neues Notfallblatt erzeugt wird.", LINKS)


def _qr(s: Seite, code: str, x: float, y: float, groesse: float) -> None:
    # Erst hier laden: segno zieht über xml.sax.saxutils das (ungenutzte) urllib.request mit.
    # So lädt ein normaler Programmstart keinerlei Netzwerk-Module (siehe tests/test_offline.py).
    import segno

    qr = segno.make(code, error="m", micro=False)
    s.flaeche(x - 2, y - 2, groesse + 4, groesse + 4, "#ffffff")  # Ruhezone für Scanner
    matrix = qr.matrix
    n = len(matrix)
    modul = groesse / n
    for zeile, werte in enumerate(matrix):
        for spalte, an in enumerate(werte):
            if an:
                s.flaeche(x + spalte * modul, y + zeile * modul, modul + 0.02, modul + 0.02, "#000000")


def als_pdf(pfad: Path, datenbankname: str, code: str, erstellt: datetime | None = None) -> Path:
    pfad = Path(pfad)
    with zeichne_pdf(pfad, f"Notfallblatt {datenbankname}") as (painter, _):
        zeichne(painter, datenbankname, code, erstellt)
    nur_eigentuemer(pfad)      # die Datei enthält den Wiederherstellungscode
    return pfad
