"""Hilfefenster mit Inhaltsverzeichnis und Suche; F1 öffnet die Seite zur aktuellen Ansicht.

F1 wird anwendungsweit abgefangen (`F1Filter`). Das passende Thema ergibt sich aus dem Widget mit dem
Tastaturfokus: Von dort aus geht es die Eltern hinauf, bis ein Widget eine Methode `hilfe_thema()`,
eine Eigenschaft „hilfe_thema“ hat oder seine Klasse in `texte.JE_KLASSE` steht.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt, QUrl
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.hilfe.texte import JE_KLASSE, THEMA, THEMEN

STANDARD = "start"


def nur_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def thema_fuer(widget: QWidget | None) -> str:
    """Hilfethema zum Widget (oder dem nächsten passenden Elternteil)."""
    w = widget
    while w is not None:
        if callable(getattr(w, "hilfe_thema", None)):
            thema = w.hilfe_thema()
            if thema:
                return thema
        eigen = w.property("hilfe_thema")
        if eigen:
            return str(eigen)
        thema = JE_KLASSE.get(type(w).__name__)
        if thema:
            return thema
        w = w.parentWidget()
    return STANDARD


class HilfeFenster(QDialog):
    """Nicht-modales Fenster: links Suche und Themen, rechts der Text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hilfe – Notenverwaltung")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setModal(False)
        self.resize(980, 680)
        self.suche = QLineEdit()
        self.suche.setPlaceholderText("Suchen …")
        self.suche.setClearButtonEnabled(True)
        self.suche.textChanged.connect(self._filtern)
        self.liste = QListWidget()
        for t in THEMEN:
            item = QListWidgetItem(t.titel)
            item.setData(Qt.ItemDataRole.UserRole, t.schluessel)
            self.liste.addItem(item)
        self.liste.currentItemChanged.connect(self._gewaehlt)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.liste.setWordWrap(True)
        self.text = QTextBrowser()
        self.text.setOpenLinks(False)              # Verweise selbst behandeln – nie etwas aus dem Netz laden
        self.text.setOpenExternalLinks(False)
        self.text.anchorClicked.connect(self._verweis)
        links = QWidget()
        ll = QVBoxLayout(links)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.suche)
        ll.addWidget(self.liste, 1)
        teiler = QSplitter()
        teiler.addWidget(links)
        teiler.addWidget(self.text)
        teiler.setStretchFactor(1, 1)
        teiler.setSizes([300, 680])
        lay = QHBoxLayout(self)
        lay.addWidget(teiler)
        self.aktuell = STANDARD
        self.zeige(STANDARD)

    def zeige(self, schluessel: str) -> None:
        thema = THEMA.get(schluessel, THEMA[STANDARD])
        self.aktuell = thema.schluessel
        self.text.setHtml(thema.html)
        for i in range(self.liste.count()):
            item = self.liste.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == thema.schluessel:
                self.liste.blockSignals(True)
                self.liste.setCurrentItem(item)
                self.liste.blockSignals(False)
                break
        begriff = self.suche.text().strip()
        if begriff:
            self.text.find(begriff)

    def _gewaehlt(self, item: QListWidgetItem | None, *_) -> None:
        if item is not None:
            self.zeige(item.data(Qt.ItemDataRole.UserRole))

    def _verweis(self, url: QUrl) -> None:
        ziel = url.fragment() or url.toString().lstrip("#")
        if ziel in THEMA:
            self.zeige(ziel)

    def _filtern(self, text: str) -> None:
        begriff = text.strip().lower()
        erster = None
        for i in range(self.liste.count()):
            item = self.liste.item(i)
            t = THEMA[item.data(Qt.ItemDataRole.UserRole)]
            passt = not begriff or begriff in t.titel.lower() or begriff in nur_text(t.html).lower()
            item.setHidden(not passt)
            if passt and erster is None:
                erster = item
        if begriff and erster is not None:
            self.liste.setCurrentItem(erster)
            self.zeige(erster.data(Qt.ItemDataRole.UserRole))

    def sichtbare_themen(self) -> list[str]:
        return [self.liste.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.liste.count())
                if not self.liste.item(i).isHidden()]


_fenster: HilfeFenster | None = None


def zeige_hilfe(thema: str = STANDARD) -> HilfeFenster:
    """Öffnet (oder holt nach vorn) das Hilfefenster. Ist gerade ein Dialog modal geöffnet, gehört die Hilfe
    zu diesem Dialog – sonst wäre sie gesperrt."""
    global _fenster
    besitzer = QApplication.activeModalWidget() or QApplication.activeWindow()
    if besitzer is not None and isinstance(besitzer, HilfeFenster):
        besitzer = besitzer.parentWidget()
    try:
        noch_da = _fenster is not None and _fenster.parentWidget() is besitzer
    except RuntimeError:   # das Fenster wurde inzwischen gelöscht
        noch_da = False
    if not noch_da:
        _fenster = HilfeFenster(besitzer)
        _fenster.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _fenster.destroyed.connect(_vergessen)
    _fenster.zeige(thema)
    _fenster.show()
    _fenster.raise_()
    _fenster.activateWindow()
    return _fenster


def _vergessen(*_) -> None:
    global _fenster
    _fenster = None


class F1Filter(QObject):
    """Fängt F1 in der ganzen Anwendung ab und öffnet die passende Hilfeseite."""

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        if ereignis.type() == QEvent.Type.KeyPress and ereignis.key() == Qt.Key.Key_F1:
            if isinstance(QApplication.activeWindow(), HilfeFenster):
                return True
            widget = QApplication.focusWidget() or QApplication.activeModalWidget() or QApplication.activeWindow()
            zeige_hilfe(thema_fuer(widget))
            return True
        return False


def installiere_f1(app: QApplication) -> None:
    if app.property("hilfe_f1") is None:
        filt = F1Filter(app)
        app.installEventFilter(filt)
        app.setProperty("hilfe_f1", True)
