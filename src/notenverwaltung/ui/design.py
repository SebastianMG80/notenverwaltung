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
    warnung: str
    fehler: str


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
        warnung="#e0b25a",
        fehler="#e57373",
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
        warnung="#9a6700",
        fehler="#b3261e",
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
    #code {{ font-family: monospace; font-size: 18pt; font-weight: 600; color: {f.text};
             background: {f.flaeche_hoch}; border: 1px solid {f.rand}; border-radius: 8px; padding: 12px; }}
    QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{
        background: {f.flaeche}; color: {f.text}; border: 1px solid {f.rand}; border-radius: 5px; padding: 4px 6px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {f.akzent}; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px; height: 14px; border: 1px solid {f.text_leise}; background: {f.flaeche};
    }}
    QCheckBox::indicator {{ border-radius: 3px; }}
    QRadioButton::indicator {{ border-radius: 8px; }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background: {f.akzent}; border: 3px solid {f.flaeche}; outline: 1px solid {f.akzent};
    }}
    QCheckBox::indicator:checked {{ image: none; }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{ border-color: {f.rand}; }}
    QListWidget, QTreeWidget, QTableView, QTableWidget {{
        background: {f.flaeche}; color: {f.text}; border: 1px solid {f.rand}; border-radius: 5px;
        alternate-background-color: {f.flaeche_hoch}; gridline-color: {f.rand};
    }}
    QHeaderView::section {{ background: {f.flaeche_hoch}; color: {f.text}; border: none;
                            border-right: 1px solid {f.rand}; border-bottom: 1px solid {f.rand}; padding: 4px; }}
    QListWidget::item {{ padding: 6px; }}
    QListWidget::item:selected, QTableView::item:selected {{ background: {f.auswahl}; color: {f.text}; }}
    QCheckBox, QRadioButton, QLabel, QGroupBox {{ color: {f.text}; }}
    QGroupBox {{ border: 1px solid {f.rand}; border-radius: 6px; margin-top: 10px; padding-top: 8px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    QTabWidget::pane {{ border: 1px solid {f.rand}; border-radius: 5px; }}
    QTabBar::tab {{ background: {f.flaeche_hoch}; color: {f.text_leise}; padding: 6px 14px; border: 1px solid {f.rand};
                    border-bottom: none; border-top-left-radius: 5px; border-top-right-radius: 5px; }}
    QTabBar::tab:selected {{ background: {f.flaeche}; color: {f.text}; }}
    QToolBar {{ background: {f.hintergrund}; border: none; spacing: 4px; }}
    QPushButton {{
        background: {f.flaeche_hoch}; color: {f.text}; border: 1px solid {f.rand};
        border-radius: 6px; padding: 6px 14px;
    }}
    QPushButton:hover {{ border-color: {f.akzent}; }}
    QPushButton#primaer {{ background: {f.akzent}; color: {f.akzent_text}; border-color: {f.akzent}; }}
    QPushButton:checked {{ background: {f.akzent}; color: {f.akzent_text}; border-color: {f.akzent}; }}
    QPushButton#link {{ background: transparent; border: none; color: {f.akzent}; padding: 2px 4px; }}
    QPushButton#link:hover {{ text-decoration: underline; }}
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
