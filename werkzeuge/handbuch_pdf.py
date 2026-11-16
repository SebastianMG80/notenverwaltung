"""Setzt handbuch/HANDBUCH.md als PDF (A4, mit Bildern und Seitenzahlen) – nur mit Qt, ohne weitere Werkzeuge.

    python werkzeuge/handbuch_pdf.py        # → handbuch/Handbuch.pdf

Verstanden wird das Markdown, das im Handbuch vorkommt: Überschriften (#, ##, ###), Absätze, Listen (- und 1.),
Tabellen, Bilder ![Unterschrift](pfad), Hinweiskästen (> …), **fett**, *kursiv*, `Code`, Links [Text](Ziel),
„---“ und `<!-- seitenumbruch -->`.
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "handbuch" / "HANDBUCH.md"
ZIEL = WURZEL / "handbuch" / "Handbuch.pdf"

# QTextDocument rechnet in Bildschirmpixeln (Auflösung des Bildschirms, offscreen oft 72 dpi) – die Seitenmaße
# deshalb erst zur Laufzeit aus dieser Auflösung bestimmen, sonst stimmen Schriftgrößen im PDF nicht.
SEITE_B = SEITE_H = RAND = TEXTBREITE = 0.0


def _masse() -> None:
    global SEITE_B, SEITE_H, RAND, TEXTBREITE
    from PySide6.QtGui import QGuiApplication

    px_mm = QGuiApplication.primaryScreen().logicalDotsPerInchX() / 25.4
    SEITE_B, SEITE_H, RAND = 210 * px_mm, 297 * px_mm, 18 * px_mm
    TEXTBREITE = SEITE_B - 2 * RAND
AKZENT = "#2a7f74"

CSS = f"""
body {{ font-size: 10pt; color: #1f2429; }}
h1 {{ font-size: 24pt; color: {AKZENT}; margin-top: 0px; margin-bottom: 10px; }}
h2 {{ font-size: 15pt; color: {AKZENT}; margin-top: 18px; margin-bottom: 6px; }}
h3 {{ font-size: 11.5pt; color: #1f2429; margin-top: 12px; margin-bottom: 4px; }}
p {{ margin-top: 3px; margin-bottom: 5px; line-height: 125%; }}
li {{ margin-bottom: 2px; line-height: 120%; }}
p.bild {{ font-size: 8.5pt; color: #555555; margin-top: 2px; margin-bottom: 12px; }}
code {{ font-family: monospace; background-color: #eef1f3; }}
th {{ background-color: #e3ecea; font-weight: bold; }}
"""


def inline(text: str) -> str:
    t = html.escape(text, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*\\])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = t.replace("\\*", "*")
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)
    return t


def bild(alt: str, pfad: str) -> str:
    from PySide6.QtGui import QImage

    datei = (QUELLE.parent / pfad).resolve()
    img = QImage(str(datei))
    if img.isNull():
        raise SystemExit(f"Bild fehlt: {datei}")
    from PySide6.QtGui import QGuiApplication

    # Bildschirmfotos haben 96 dpi; im Dokument entsprechend skalieren, höchstens Textbreite
    natuerlich = img.width() * QGuiApplication.primaryScreen().logicalDotsPerInchX() / 96
    breite = min(natuerlich, TEXTBREITE)
    # Bild und Unterschrift in einem Absatz: so trennt sie kein Seitenumbruch
    return (f'<p align="center" style="margin-top: 8px; margin-bottom: 12px;">'
            f'<img src="{datei.as_posix()}" width="{breite:.0f}"><br>'
            f'<span style="font-size: 8.5pt; color: #555555;">{inline(alt)}</span></p>')


def tabelle(zeilen: list[str]) -> str:
    zellen = [[z.strip() for z in zeile.strip().strip("|").split("|")] for zeile in zeilen]
    kopf, rumpf = zellen[0], [z for z in zellen[2:]]
    teile = ['<table border="1" cellspacing="0" cellpadding="4" width="100%" '
             'style="border-color: #c8d0d4; border-style: solid; margin-top: 4px; margin-bottom: 8px;">',
             "<tr>" + "".join(f"<th align=left>{inline(k)}</th>" for k in kopf) + "</tr>"]
    for z in rumpf:
        teile.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in z) + "</tr>")
    teile.append("</table>")
    return "".join(teile)


def kasten(text: str) -> str:
    return ('<table width="100%" cellspacing="0" cellpadding="8" style="margin-top: 6px; margin-bottom: 8px;">'
            f'<tr><td style="background-color: #e8f3f1;">{inline(text)}</td></tr></table>')


def markdown_zu_html(md: str) -> str:
    aus: list[str] = []
    absatz: list[str] = []
    liste: list[str] = []
    listenart = ""
    umbruch = False

    def absatz_ende():
        nonlocal absatz
        if absatz:
            aus.append(f"<p>{inline(' '.join(absatz))}</p>")
            absatz = []

    def liste_ende():
        nonlocal liste, listenart
        if liste:
            aus.append(f"<{listenart}>" + "".join(f"<li>{inline(e)}</li>" for e in liste) + f"</{listenart}>")
            liste, listenart = [], ""

    zeilen = md.splitlines()
    i = 0
    while i < len(zeilen):
        z = zeilen[i]
        s = z.strip()
        if s == "<!-- seitenumbruch -->":
            absatz_ende()
            liste_ende()
            umbruch = True
            i += 1
            continue
        stil = ' style="page-break-before: always;"' if umbruch else ""
        if not s:
            absatz_ende()
            liste_ende()
        elif s.startswith("#"):
            absatz_ende()
            liste_ende()
            ebene = len(s) - len(s.lstrip("#"))
            aus.append(f"<h{ebene}{stil}>{inline(s[ebene:].strip())}</h{ebene}>")
            umbruch = False
        elif m := re.fullmatch(r"!\[(.*)\]\((.+)\)", s):
            absatz_ende()
            liste_ende()
            aus.append(bild(m.group(1), m.group(2)))
        elif s.startswith("|"):
            absatz_ende()
            liste_ende()
            block = []
            while i < len(zeilen) and zeilen[i].strip().startswith("|"):
                block.append(zeilen[i])
                i += 1
            aus.append(tabelle(block))
            continue
        elif s.startswith(">"):
            absatz_ende()
            liste_ende()
            block = []
            while i < len(zeilen) and zeilen[i].strip().startswith(">"):
                block.append(zeilen[i].strip()[1:].strip())
                i += 1
            aus.append(kasten(" ".join(block)))
            continue
        elif s == "---":
            absatz_ende()
            liste_ende()
            aus.append("<hr>")
        elif m := re.match(r"^(-|\d+\.)\s+(.*)", s):
            absatz_ende()
            art = "ol" if m.group(1)[0].isdigit() else "ul"
            if listenart and art != listenart:
                liste_ende()
            listenart = art
            liste.append(m.group(2))
        elif liste and z.startswith("  "):
            liste[-1] += " " + s                       # Fortsetzungszeile eines Listenpunkts
        else:
            liste_ende()
            absatz.append(s)
        i += 1
    absatz_ende()
    liste_ende()
    return f"<html><head><style>{CSS}</style></head><body>{''.join(aus)}</body></html>"


def baue(ziel: Path = ZIEL) -> Path:
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])  # noqa: F841 – Schriften brauchen eine Anwendung
    _masse()
    doc = QTextDocument()
    schrift = QFont()
    schrift.setFamilies(["Noto Sans", "DejaVu Sans", "Segoe UI", "Arial"])
    schrift.setPointSizeF(10)
    doc.setDefaultFont(schrift)
    doc.setDocumentMargin(RAND)
    doc.setPageSize(QSizeF(SEITE_B, SEITE_H))
    doc.setHtml(markdown_zu_html(QUELLE.read_text(encoding="utf-8")))
    w = QPdfWriter(str(ziel))
    w.setResolution(300)
    w.setTitle("Notenverwaltung – Handbuch")
    w.setCreator("Notenverwaltung")
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait,
                                QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter))
    doc.print_(w)
    print(f"{ziel} – {doc.pageCount()} Seiten")
    return ziel


if __name__ == "__main__":
    baue(Path(sys.argv[1]) if len(sys.argv) > 1 else ZIEL)
