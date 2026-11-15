"""Gemeinsame Grundlage für alle Ausdrucke: Zeichnen in Millimetern auf PDF oder Drucker.

Alle Ausgaben rechnen in Millimetern ab der linken oberen Papierecke. So passen Etiketten
(Avery Zweckform) unabhängig vom Gerät, und PDF und Drucker zeigen dasselbe.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

A4 = QPageSize(QPageSize.PageSizeId.A4)

# Bevorzugte Schriften mit Ausweichschriften für Linux (KDE) und Windows
SCHRIFTEN_SANS = ["Noto Sans", "DejaVu Sans", "Segoe UI", "Arial", "Liberation Sans", "Sans Serif"]
SCHRIFTEN_MONO = ["Noto Sans Mono", "DejaVu Sans Mono", "Consolas", "Courier New", "Liberation Mono", "Monospace"]


class Seite:
    """Hilfsobjekt um einen QPainter: Koordinaten in mm, Schriften in pt."""

    def __init__(self, painter: QPainter, versatz_x_mm: float = 0.0, versatz_y_mm: float = 0.0) -> None:
        self.p = painter
        dev = painter.device()
        self._px_pro_mm_x = dev.logicalDpiX() / 25.4
        self._px_pro_mm_y = dev.logicalDpiY() / 25.4
        self.versatz_x = versatz_x_mm
        self.versatz_y = versatz_y_mm
        self.schriftfamilie: str | None = None  # bevorzugte Schrift für Ausdrucke (sonst Standardliste)

    # ---- Umrechnung --------------------------------------------------------------------------
    def x(self, mm: float) -> float:
        return (mm + self.versatz_x) * self._px_pro_mm_x

    def y(self, mm: float) -> float:
        return (mm + self.versatz_y) * self._px_pro_mm_y

    def rechteck(self, x: float, y: float, b: float, h: float) -> QRectF:
        return QRectF(QPointF(self.x(x), self.y(y)), QPointF(self.x(x + b), self.y(y + h)))

    def mm_in_px(self, mm: float) -> float:
        return mm * self._px_pro_mm_x

    # ---- Zeichnen ----------------------------------------------------------------------------
    def schrift(self, pt: float, fett: bool = False, familie: str | None = None, kursiv: bool = False) -> QFont:
        mono = (familie or "").lower() == "monospace"
        f = QFont()
        erste = familie or self.schriftfamilie
        f.setFamilies(SCHRIFTEN_MONO if mono else ([erste] if erste else []) + SCHRIFTEN_SANS)
        # Stil-Hinweis: Windows/Linux wählen eine passende Schrift, auch wenn keine der Familien vorhanden ist
        f.setStyleHint(QFont.StyleHint.TypeWriter if mono else QFont.StyleHint.SansSerif)
        f.setPointSizeF(pt)
        f.setBold(fett)
        f.setItalic(kursiv)
        # ohne Hinting skalieren die Maße linear: Vorschau (80 dpi), PDF (600 dpi) und Drucker brechen gleich um
        f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.p.setFont(f)
        return f

    def stift(self, farbe: str = "#000000", staerke_mm: float = 0.2) -> None:
        pen = QPen(QColor(farbe))
        pen.setWidthF(max(1.0, self.mm_in_px(staerke_mm)))
        self.p.setPen(pen)

    def text(self, x: float, y: float, b: float, h: float, text: str,
             ausrichtung: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
             umbruch: bool = False) -> QRectF:
        flags = ausrichtung | (Qt.TextFlag.TextWordWrap if umbruch else Qt.AlignmentFlag(0))
        return self.p.drawText(self.rechteck(x, y, b, h), int(flags), text)

    def texthoehe_mm(self, b: float, text: str) -> float:
        """Höhe in mm, die ein umbrochener Text bei aktueller Schrift auf Breite b braucht."""
        r = self.p.boundingRect(self.rechteck(0, 0, b, 1000), int(Qt.TextFlag.TextWordWrap), text)
        return r.height() / self._px_pro_mm_y

    def textbreite_mm(self, text: str) -> float:
        """Breite in mm, die ein einzeiliger Text bei aktueller Schrift braucht."""
        return QFontMetricsF(self.p.font(), self.p.device()).horizontalAdvance(text) / self._px_pro_mm_x

    def linie(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.p.drawLine(QPointF(self.x(x1), self.y(y1)), QPointF(self.x(x2), self.y(y2)))

    def kasten(self, x: float, y: float, b: float, h: float, fuellung: str | None = None,
               rand: bool = True, radius_mm: float = 0.0) -> None:
        self.p.save()
        if fuellung:
            self.p.setBrush(QColor(fuellung))
        else:
            self.p.setBrush(Qt.BrushStyle.NoBrush)
        if not rand:
            self.p.setPen(Qt.PenStyle.NoPen)
        r = self.rechteck(x, y, b, h)
        if radius_mm:
            self.p.drawRoundedRect(r, self.mm_in_px(radius_mm), self.mm_in_px(radius_mm))
        else:
            self.p.drawRect(r)
        self.p.restore()

    def flaeche(self, x: float, y: float, b: float, h: float, farbe: str) -> None:
        self.p.fillRect(self.rechteck(x, y, b, h), QColor(farbe))


class Messung:
    """Misst Texte so, wie sie im PDF (600 dpi) gesetzt werden – unabhängig vom späteren Gerät."""

    def __init__(self, schrift: str | None) -> None:
        self.bild = QImage(8, 8, QImage.Format.Format_RGB32)
        self.bild.setDotsPerMeterX(int(600 / 0.0254))
        self.bild.setDotsPerMeterY(int(600 / 0.0254))
        self.bild.fill(QColor("#ffffff"))
        self.p = QPainter(self.bild)
        self.s = Seite(self.p)
        self.s.schriftfamilie = schrift
        self._cache: dict[tuple, float] = {}

    def hoehe(self, text: str, breite: float, pt: float, fett: bool = False, kursiv: bool = False) -> float:
        k = ("h", text, breite, pt, fett, kursiv)
        if k not in self._cache:
            self.s.schrift(pt, fett, kursiv=kursiv)
            self._cache[k] = self.s.texthoehe_mm(breite, text)
        return self._cache[k]

    def breite(self, text: str, pt: float, fett: bool = False) -> float:
        self.s.schrift(pt, fett)
        return self.s.textbreite_mm(text)

    def ende(self) -> None:
        self.p.end()


def neues_pdf(pfad: Path, titel: str, quer: bool = False) -> QPdfWriter:
    w = QPdfWriter(str(pfad))
    w.setResolution(600)
    w.setTitle(titel)
    w.setCreator("Notenverwaltung")
    w.setPageLayout(QPageLayout(A4, QPageLayout.Orientation.Landscape if quer else QPageLayout.Orientation.Portrait,
                                QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter))
    return w


@contextmanager
def zeichne_pdf(pfad: Path, titel: str, quer: bool = False):
    """with zeichne_pdf(pfad, titel) as (painter, writer): …"""
    writer = neues_pdf(Path(pfad), titel, quer)
    painter = QPainter()
    if not painter.begin(writer):
        raise OSError(f"PDF kann nicht geschrieben werden: {pfad}")
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        yield painter, writer
    finally:
        painter.end()


# ---- Mehrseitige Ausgaben: PDF, Drucker, Vorschau ----------------------------------------------------

class Ausgabe:
    """Basisklasse aller Druckausgaben. Unterklassen setzen `titel`, `quer` und implementieren
    `seitenzahl()` und `zeichne_seite(seite, nummer)` (Nummer ab 0)."""

    titel = "Ausgabe"
    quer = False

    def seitenzahl(self) -> int:
        return 1

    def zeichne_seite(self, seite: Seite, nummer: int) -> None:  # pragma: no cover - abstrakt
        raise NotImplementedError

    # Versatz für Drucker, die nicht exakt positionieren (wird von Etiketten benutzt)
    versatz_x = 0.0
    versatz_y = 0.0
    schrift: str | None = None      # bevorzugte Schriftfamilie
    kopfzeile: str = ""             # z. B. „Gesamtschule Musterstadt · Herr Muster“

    def _seite(self, painter: QPainter) -> Seite:
        s = Seite(painter, self.versatz_x, self.versatz_y)
        s.schriftfamilie = self.schrift
        return s


def als_pdf(ausgabe: Ausgabe, pfad: Path) -> Path:
    pfad = Path(pfad)
    with zeichne_pdf(pfad, ausgabe.titel, ausgabe.quer) as (painter, writer):
        for i in range(ausgabe.seitenzahl()):
            if i:
                writer.newPage()
            ausgabe.zeichne_seite(ausgabe._seite(painter), i)
    return pfad


def drucke(ausgabe: Ausgabe, drucker) -> None:
    """`drucker` ist ein eingerichteter QPrinter (setFullPage(True), Ausrichtung passend)."""
    painter = QPainter()
    if not painter.begin(drucker):
        raise OSError("Der Drucker konnte nicht angesprochen werden.")
    try:
        for i in range(ausgabe.seitenzahl()):
            if i:
                drucker.newPage()
            ausgabe.zeichne_seite(ausgabe._seite(painter), i)
    finally:
        painter.end()


def vorschau(ausgabe: Ausgabe, nummer: int, dpi: int = 72):
    """Rendert eine Seite als Bild (weißes Papier) für die Vorschau."""
    from PySide6.QtGui import QImage

    breite_mm, hoehe_mm = (297, 210) if ausgabe.quer else (210, 297)
    bild = QImage(int(breite_mm / 25.4 * dpi), int(hoehe_mm / 25.4 * dpi), QImage.Format.Format_RGB32)
    bild.setDotsPerMeterX(int(dpi / 0.0254))
    bild.setDotsPerMeterY(int(dpi / 0.0254))
    bild.fill(QColor("#ffffff"))
    painter = QPainter(bild)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    try:
        ausgabe.zeichne_seite(ausgabe._seite(painter), nummer)
    finally:
        painter.end()
    return bild


def kopfzeile_aus(verbindung) -> str:
    """„Schule · Lehrkraft“ aus den Angaben der Datenbank (Datei → Angaben für Ausdrucke)."""
    werte = dict(verbindung.execute(
        "SELECT schluessel, wert FROM meta WHERE schluessel IN ('druck_schule', 'druck_lehrkraft')").fetchall())
    return " · ".join(w for w in (werte.get("druck_schule", ""), werte.get("druck_lehrkraft", "")) if w)
