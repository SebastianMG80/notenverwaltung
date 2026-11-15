"""Schnellsuche (Strg+F): Namen über alle Lerngruppen des Schuljahrs, dazu Lerngruppen und Arbeiten.

Tippen filtert sofort; Pfeiltasten wählen, Enter öffnet. Eine Person in einer Lerngruppe öffnet die Gruppe im
aktuellen Reiter und markiert dort ihre Zeile.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.stammdaten import Schuljahr, Stammdaten

MAX_TREFFER = 60


def _norm(text: str) -> str:
    """Klein, ohne Akzente: „Öztürk“ findet man auch mit „oztu“ (und mit „öztü“)."""
    zerlegt = unicodedata.normalize("NFKD", text.casefold())
    return "".join(z for z in zerlegt if not unicodedata.combining(z))


@dataclass(frozen=True)
class Treffer:
    art: str                  # "person", "person_gruppe", "gruppe", "arbeit"
    text: str
    schueler_id: int | None = None
    gruppe_id: int | None = None
    arbeit_id: int | None = None


def suche(sd: Stammdaten, jahr: Schuljahr, begriff: str) -> list[Treffer]:
    worte = [_norm(w) for w in begriff.split() if w.strip()]
    if not worte:
        return []

    def passt(*felder: str) -> bool:
        gesamt = _norm(" ".join(felder))
        return all(w in gesamt for w in worte)

    treffer: list[Treffer] = []
    gruppen = sd.lerngruppen(jahr.id)
    for e in sd.schueler_im_jahr(jahr.id):
        s = e.schueler
        if not passt(s.vorname, s.nachname):
            continue
        treffer.append(Treffer("person", f"{s.nachname}, {s.vorname} · {e.klasse}", s.id))
        for g in sd.lerngruppen_von(s.id, jahr.id):
            treffer.append(Treffer("person_gruppe", f"      → {g.bezeichnung} ({g.fach})", s.id, g.id))
    for g in gruppen:
        if passt(g.bezeichnung, g.fach):
            treffer.append(Treffer("gruppe", f"Lerngruppe {g.bezeichnung} ({g.fach})", None, g.id))
    ar = Arbeiten(sd.v)
    for g in gruppen:
        if not g.schriftlich:
            continue
        for a in ar.arbeiten(g.id):
            if passt(a.titel, a.thema):
                treffer.append(Treffer("arbeit", f"„{a.titel}“ vom {a.datum:%d.%m.%Y} · {g.bezeichnung}", None, g.id,
                                       a.id))
    return treffer[:MAX_TREFFER]


class SchnellsucheDialog(QDialog):
    def __init__(self, sd: Stammdaten, jahr: Schuljahr, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.sd, self.jahr = sd, jahr
        self.gewaehlt: Treffer | None = None
        self.setWindowTitle("Schnellsuche")
        self.resize(560, 460)
        self.feld = QLineEdit()
        self.feld.setPlaceholderText("Name, Lerngruppe oder Arbeit …")
        self.feld.setClearButtonEnabled(True)
        self.feld.textChanged.connect(self._suchen)
        self.feld.installEventFilter(self)
        self.liste = QListWidget()
        self.liste.itemActivated.connect(self._oeffnen)
        self.hinweis = QLabel(f"Schuljahr {jahr.bezeichnung} · ↑ ↓ wählen, Enter öffnet", objectName="leise")
        lay = QVBoxLayout(self)
        lay.addWidget(self.feld)
        lay.addWidget(self.liste, 1)
        lay.addWidget(self.hinweis)
        self.feld.setFocus()

    def _suchen(self, text: str) -> None:
        self.liste.clear()
        for t in suche(self.sd, self.jahr, text):
            item = QListWidgetItem(t.text)
            item.setData(Qt.ItemDataRole.UserRole, t)
            if t.art == "person":
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            self.liste.addItem(item)
        if self.liste.count():
            self.liste.setCurrentRow(0)
        elif text.strip():
            self.liste.addItem(QListWidgetItem("Nichts gefunden."))

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        if objekt is self.feld and ereignis.type() == QEvent.Type.KeyPress:
            if ereignis.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                schritt = 1 if ereignis.key() == Qt.Key.Key_Down else -1
                self.liste.setCurrentRow(max(0, min(self.liste.count() - 1, self.liste.currentRow() + schritt)))
                return True
            if ereignis.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.liste.currentItem() is not None:
                    self._oeffnen(self.liste.currentItem())
                return True
        return super().eventFilter(objekt, ereignis)

    def _oeffnen(self, item: QListWidgetItem) -> None:
        t = item.data(Qt.ItemDataRole.UserRole)
        if t is None:
            return
        self.gewaehlt = t
        self.accept()
