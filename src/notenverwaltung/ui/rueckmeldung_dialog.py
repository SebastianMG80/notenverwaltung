"""Rückmeldungen schreiben: eine Person nach der anderen, mit Textbausteinen und (opt-in) Vorschlag.

Links der Text, rechts die Bausteine (Doppelklick oder Enter setzt ein, Platzhalter werden ersetzt).
Im Text setzt ein Kürzel + Strg+Leertaste den passenden Baustein ein. „Vorige / Nächste“ speichert und blättert.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.einstellungen import rueckmeldung_vorschlag_an, schwellen
from notenverwaltung.modell.arbeiten import STATUS, Arbeit, Arbeiten, Ergebnis
from notenverwaltung.modell.noten import zahl_text
from notenverwaltung.modell.rueckmeldung import Textbausteine, fuelle, platzhalter_werte, vorschlag
from notenverwaltung.modell.stammdaten import Lerngruppe
from notenverwaltung.ui.bausteine import Hinweis


class RueckmeldungDialog(QDialog):
    def __init__(self, ar: Arbeiten, arbeit: Arbeit, gruppe: Lerngruppe, schueler_ids: list[int], start: int = 0,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar, self.arbeit, self.gruppe = ar, arbeit, gruppe
        self.tb = Textbausteine(ar.v)
        self.ids = schueler_ids
        self.aufgaben = ar.aufgaben(arbeit.id)
        self.stark, self.schwach = schwellen()
        self.pos = max(0, min(start, len(schueler_ids) - 1))
        self.setWindowTitle(f"Rückmeldungen – {arbeit.titel}")
        self.resize(940, 560)

        self.name = QLabel()
        self.name.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.stand = QLabel(objectName="leise")
        self.zurueck = QPushButton("◀ Vorige")
        self.vor = QPushButton("Nächste ▶")
        self.zurueck.setToolTip("Speichern und zur vorigen Person (Strg+Bild auf)")
        self.vor.setToolTip("Speichern und zur nächsten Person (Strg+Bild ab)")
        self.zurueck.clicked.connect(lambda: self.blaettern(-1))
        self.vor.clicked.connect(lambda: self.blaettern(1))
        QShortcut(QKeySequence("Ctrl+PgUp"), self, lambda: self.blaettern(-1))
        QShortcut(QKeySequence("Ctrl+PgDown"), self, lambda: self.blaettern(1))
        self.position = QLabel()
        kopf = QHBoxLayout()
        kopf.addWidget(self.name)
        kopf.addStretch(1)
        kopf.addWidget(self.zurueck)
        kopf.addWidget(self.position)
        kopf.addWidget(self.vor)

        self.text = QPlainTextEdit()
        self.text.setPlaceholderText("Rückmeldung an die Person – erscheint auf dem Rückmeldebogen.")
        self.text.installEventFilter(self)
        self.k_vorschlag = QPushButton("Vorschlag aus den Punkten")
        self.k_vorschlag.setToolTip(f"Stärken (ab {self.stark:g} %) und Übungsbedarf (unter {self.schwach:g} %) "
                                    "aus den Aufgaben – nur ein Vorschlag zum Weiterschreiben.")
        self.k_vorschlag.clicked.connect(self.vorschlag_einfuegen)
        self.k_vorschlag.setVisible(rueckmeldung_vorschlag_an())
        links = QWidget()
        ll = QVBoxLayout(links)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.stand)
        ll.addWidget(self.text, 1)
        unter = QHBoxLayout()
        unter.addWidget(QLabel("Kürzel tippen, dann Strg+Leertaste: Baustein einsetzen.", objectName="leise"), 1)
        unter.addWidget(self.k_vorschlag)
        ll.addLayout(unter)

        self.suche = QLineEdit()
        self.suche.setPlaceholderText("Bausteine durchsuchen …")
        self.suche.setClearButtonEnabled(True)
        self.suche.textChanged.connect(self._filtern)
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.liste.itemActivated.connect(self._baustein_gewaehlt)
        verwalten = QPushButton("Bausteine verwalten …")
        verwalten.clicked.connect(self.verwalten)
        rechts = QWidget()
        rl = QVBoxLayout(rechts)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("<b>Textbausteine</b> (Doppelklick setzt ein)"))
        rl.addWidget(self.suche)
        rl.addWidget(self.liste, 1)
        rl.addWidget(verwalten)

        teiler = QSplitter()
        teiler.addWidget(links)
        teiler.addWidget(rechts)
        teiler.setStretchFactor(0, 3)
        teiler.setStretchFactor(1, 2)
        self.meldung = Hinweis()
        knoepfe = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        knoepfe.button(QDialogButtonBox.StandardButton.Ok).setText("Speichern und schließen")
        knoepfe.accepted.connect(self.accept)
        knoepfe.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(kopf)
        lay.addWidget(teiler, 1)
        lay.addWidget(self.meldung)
        lay.addWidget(knoepfe)
        self._bausteine_laden()
        self._zeigen()

    # ---- Person ---------------------------------------------------------------------------------
    def ergebnis(self) -> Ergebnis:
        sid = self.ids[self.pos]
        return next(e for e in self.ar.ergebnisse(self.arbeit.id) if e.mitglied.schueler.id == sid)

    def _zeigen(self) -> None:
        e = self.ergebnis()
        self._e = e
        s = e.mitglied.schueler
        self.name.setText(f"{s.vorname} {s.nachname}")
        hoechst = sum(a.max_punkte for a in self.aufgaben)
        teile = []
        if e.summe is not None:
            teile.append(f"{zahl_text(e.summe)} von {zahl_text(hoechst)} Punkten"
                         + (f" ({e.summe / hoechst * 100:.0f} %)" if hoechst else ""))
        if e.note is not None:
            teile.append(f"Note: {e.note.wort_mit_tendenz}")
        if e.status:
            teile.append(STATUS.get(e.status, e.status))
        self.stand.setText(" · ".join(teile) or "Noch nichts eingetragen.")
        self.text.setPlainText(e.kommentar)
        self.position.setText(f"{self.pos + 1} von {len(self.ids)}")
        self.zurueck.setEnabled(self.pos > 0)
        self.vor.setEnabled(self.pos < len(self.ids) - 1)
        self.k_vorschlag.setEnabled(e.summe is not None)
        self.meldung.setze("")
        self.text.setFocus()
        self.text.moveCursor(QTextCursor.MoveOperation.End)

    def speichern(self) -> None:
        text = self.text.toPlainText().strip()
        if text != self._e.kommentar:
            self.ar.setze_teilnahme(self.arbeit.id, self.ids[self.pos], kommentar=text)

    def blaettern(self, schritt: int) -> None:
        ziel = self.pos + schritt
        if not 0 <= ziel < len(self.ids):
            return
        self.speichern()
        self.pos = ziel
        self._zeigen()

    def accept(self) -> None:
        self.speichern()
        super().accept()

    # ---- Bausteine ------------------------------------------------------------------------------
    def _werte(self) -> dict[str, str]:
        return platzhalter_werte(self._e, self.arbeit, self.gruppe.fach, self.aufgaben, self.stark, self.schwach)

    def _bausteine_laden(self) -> None:
        self.liste.clear()
        for b in self.tb.alle(self.gruppe.fach):
            item = QListWidgetItem((f"{b.kuerzel} – " if b.kuerzel else "") + b.text)
            item.setData(Qt.ItemDataRole.UserRole, b.text)
            item.setToolTip(b.text + (f"\nNur für {b.fach}" if b.fach else ""))
            self.liste.addItem(item)
        self._filtern(self.suche.text())

    def _filtern(self, text: str) -> None:
        t = text.strip().lower()
        for i in range(self.liste.count()):
            item = self.liste.item(i)
            item.setHidden(bool(t) and t not in item.text().lower())

    def einsetzen(self, text: str) -> None:
        """Setzt den gefüllten Baustein an der Schreibmarke ein (mit Leerzeichen, wo nötig)."""
        fertig = fuelle(text, self._werte())
        c = self.text.textCursor()
        davor = self.text.toPlainText()[:c.position()]
        if davor and not davor[-1].isspace():
            fertig = " " + fertig
        c.insertText(fertig)
        self.text.setTextCursor(c)
        self.text.setFocus()

    def _baustein_gewaehlt(self, item: QListWidgetItem) -> None:
        self.einsetzen(item.data(Qt.ItemDataRole.UserRole))

    def kuerzel_einsetzen(self) -> bool:
        """Ersetzt das Wort vor der Schreibmarke durch den Baustein mit diesem Kürzel."""
        c = self.text.textCursor()
        davor = self.text.toPlainText()[:c.position()]
        wort = davor.split()[-1] if davor.strip() and not davor[-1].isspace() else ""
        b = self.tb.finde(wort, self.gruppe.fach) if wort else None
        if b is None:
            self.meldung.setze(f"Kein Baustein mit dem Kürzel „{wort}“." if wort else
                               "Erst ein Kürzel tippen, dann Strg+Leertaste.", "warnung")
            return False
        for _ in wort:
            c.deletePreviousChar()
        self.text.setTextCursor(c)
        self.einsetzen(b.text)
        self.meldung.setze("")
        return True

    def eventFilter(self, objekt, ereignis) -> bool:  # noqa: N802
        if (objekt is self.text and ereignis.type() == QEvent.Type.KeyPress and ereignis.key() == Qt.Key.Key_Space
                and ereignis.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.kuerzel_einsetzen()
            return True
        return super().eventFilter(objekt, ereignis)

    def vorschlag_einfuegen(self) -> None:
        text = vorschlag(self._e, self.aufgaben, self.stark, self.schwach)
        if text:
            self.einsetzen(text)

    def verwalten(self) -> None:
        from notenverwaltung.ui.textbausteine_dialog import TextbausteineDialog

        if TextbausteineDialog(self.tb, self.gruppe.fach, self).exec():
            self._bausteine_laden()
