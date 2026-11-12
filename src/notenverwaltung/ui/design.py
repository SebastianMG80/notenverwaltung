"""Erscheinungsbild: nüchtern, aber freundlich. Dunkel ist Standard, hell wählbar.

Alle Farben stehen an einer Stelle, damit spätere Anpassungen (Etappe 12)
nur hier ansetzen müssen.
"""

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory


@dataclass(frozen=True)
class Farben:
    hintergrund: str
    flaeche: str
    flaeche_hoch: str
    rand: str
    text: str
    text_leise: str
    akzent: str
    akzent_text: str
    auswahl: str


DESIGNS: dict[str, Farben] = {
    "dunkel": Farben(
        hintergrund="#1d2126",
        flaeche="#252a30",
        flaeche_hoch="#2e343b",
        rand="#3a4149",
        text="#e4e7eb",
        text_leise="#9aa3ad",
        akzent="#5fb3a8",
        akzent_text="#10201e",
        auswahl="#35554f",
    ),
    "hell": Farben(
        hintergrund="#f3f4f6",
        flaeche="#ffffff",
        flaeche_hoch="#eceef1",
        rand="#cfd4da",
        text="#1f2429",
        text_leise="#5d6670",
        akzent="#2f7f75",
        akzent_text="#ffffff",
        auswahl="#cde6e2",
    ),
}


def farben(name: str) -> Farben:
    return DESIGNS.get(name, DESIGNS["dunkel"])


def _palette(f: Farben) -> QPalette:
    p = QPalette()
    rollen = {
        QPalette.ColorRole.Window: f.hintergrund,
        QPalette.ColorRole.WindowText: f.text,
        QPalette.ColorRole.Base: f.flaeche,
        QPalette.ColorRole.AlternateBase: f.flaeche_hoch,
        QPalette.ColorRole.Text: f.text,
        QPalette.ColorRole.Button: f.flaeche_hoch,
        QPalette.ColorRole.ButtonText: f.text,
        QPalette.ColorRole.ToolTipBase: f.flaeche_hoch,
        QPalette.ColorRole.ToolTipText: f.text,
        QPalette.ColorRole.PlaceholderText: f.text_leise,
        QPalette.ColorRole.Highlight: f.akzent,
        QPalette.ColorRole.HighlightedText: f.akzent_text,
        QPalette.ColorRole.Link: f.akzent,
    }
    for rolle, farbe in rollen.items():
        p.setColor(rolle, QColor(farbe))
    for rolle in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rolle, QColor(f.text_leise))
    return p


def _stylesheet(f: Farben) -> str:
    return f"""
    QMainWindow, QDialog {{ background: {f.hintergrund}; }}
    QMenuBar {{ background: {f.hintergrund}; color: {f.text}; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {f.auswahl}; color: {f.text}; }}
    QMenu {{ background: {f.flaeche}; border: 1px solid {f.rand}; color: {f.text}; }}
    QStatusBar {{ background: {f.hintergrund}; color: {f.text_leise}; }}
    QSplitter::handle {{ background: {f.rand}; }}
    #navigation {{ background: {f.flaeche}; border: none; }}
    #navigation::item {{ padding: 4px 6px; }}
    #navigation::item:selected {{ background: {f.auswahl}; color: {f.text}; }}
    #karte {{ background: {f.flaeche}; border: 1px solid {f.rand}; border-radius: 10px; }}
    #titel {{ font-size: 20pt; font-weight: 600; color: {f.text}; }}
    #leise {{ color: {f.text_leise}; }}
    QPushButton {{
        background: {f.flaeche_hoch}; color: {f.text}; border: 1px solid {f.rand};
        border-radius: 6px; padding: 6px 14px;
    }}
    QPushButton:hover {{ border-color: {f.akzent}; }}
    QPushButton#primaer {{ background: {f.akzent}; color: {f.akzent_text}; border-color: {f.akzent}; }}
    QPushButton:disabled, QPushButton#primaer:disabled {{
        background: {f.flaeche_hoch}; color: {f.text_leise}; border-color: {f.rand};
    }}
    """


def wende_design_an(app: QApplication, name: str) -> None:
    """Setzt Stil, Palette und Stylesheet. Fusion sieht unter KDE und Windows gleich aus."""
    f = farben(name)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(_palette(f))
    app.setStyleSheet(_stylesheet(f))
    app.setProperty("design", name if name in DESIGNS else "dunkel")
