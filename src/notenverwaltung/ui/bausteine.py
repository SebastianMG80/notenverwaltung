"""Kleine wiederverwendbare Bausteine für Dialoge."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QMessageBox, QWidget

from notenverwaltung.ui.design import farben


def aktuelle_farben():
    app = QApplication.instance()
    return farben(app.property("design") if app else "dunkel")


class Passwortfeld(QLineEdit):
    """Passwortfeld mit „Anzeigen“-Schalter."""

    def __init__(self, platzhalter: str = "Passwort", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setPlaceholderText(platzhalter)
        self._zeigen = QAction("Anzeigen", self)
        self._zeigen.setCheckable(True)
        self._zeigen.setIcon(QIcon.fromTheme("view-visible"))
        self._zeigen.setToolTip("Passwort anzeigen")
        self._zeigen.toggled.connect(self._umschalten)
        self.addAction(self._zeigen, QLineEdit.ActionPosition.TrailingPosition)

    def _umschalten(self, an: bool) -> None:
        self.setEchoMode(QLineEdit.EchoMode.Normal if an else QLineEdit.EchoMode.Password)


class Hinweis(QLabel):
    """Farbiger Hinweistext: art = "info", "warnung" oder "fehler"."""

    def __init__(self, text: str = "", art: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setze(text, art)

    def setze(self, text: str, art: str = "info") -> None:
        f = aktuelle_farben()
        farbe = {"info": f.text_leise, "warnung": f.warnung, "fehler": f.fehler, "ok": f.akzent}[art]
        self.setStyleSheet(f"color: {farbe};")
        self.setText(text)
        self.setVisible(bool(text))


def frage(parent: QWidget, titel: str, text: str, ja: str = "Ja", nein: str = "Abbrechen",
          warnung: bool = False) -> bool:
    box = QMessageBox(QMessageBox.Icon.Warning if warnung else QMessageBox.Icon.Question, titel, text,
                      parent=parent)
    ja_knopf = box.addButton(ja, QMessageBox.ButtonRole.AcceptRole)
    nein_knopf = box.addButton(nein, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(nein_knopf)
    box.exec()
    return box.clickedButton() is ja_knopf


def fehler(parent: QWidget, titel: str, text: str) -> None:
    QMessageBox.critical(parent, titel, text)


def info(parent: QWidget, titel: str, text: str) -> None:
    QMessageBox.information(parent, titel, text)


# ---- Datumsfelder und Tabellen ---------------------------------------------------------------------
from datetime import date as _date  # noqa: E402

from PySide6.QtCore import QDate  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


def qdate(d: _date) -> QDate:
    return QDate(d.year, d.month, d.day)


def pydate(q: QDate) -> _date:
    return _date(q.year(), q.month(), q.day())


class Datumsfeld(QDateEdit):
    def __init__(self, wert: _date | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd.MM.yyyy")
        self.setDate(qdate(wert or _date.today()))

    def wert(self) -> _date:
        return pydate(self.date())

    def setze(self, d: _date) -> None:
        self.setDate(qdate(d))

    def begrenze(self, von: _date, bis: _date) -> None:
        self.setDateRange(qdate(von), qdate(bis))


class OptionalesDatum(QWidget):
    """Kästchen + Datum, z. B. „Zugang am …“ – ohne Haken gilt der Schuljahresbeginn."""

    def __init__(self, beschriftung: str, wert: _date | None = None, vorgabe: _date | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.an = QCheckBox(beschriftung)
        self.datum = Datumsfeld(wert or vorgabe)
        lay.addWidget(self.an)
        lay.addWidget(self.datum)
        lay.addStretch(1)
        self.an.toggled.connect(self.datum.setEnabled)
        self.an.setChecked(wert is not None)
        self.datum.setEnabled(wert is not None)

    def wert(self) -> _date | None:
        return self.datum.wert() if self.an.isChecked() else None

    def setze(self, d: _date | None) -> None:
        self.an.setChecked(d is not None)
        if d is not None:
            self.datum.setze(d)


class Tabelle(QTableWidget):
    """Schreibgeschützte Liste mit Zeilenauswahl; Zeilendaten über `zeilen_daten`."""

    def __init__(self, spalten: list[str], parent: QWidget | None = None, mehrfach: bool = False) -> None:
        super().__init__(0, len(spalten), parent)
        self.setHorizontalHeaderLabels(spalten)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection if mehrfach
                              else QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.zeilen_daten: list = []

    def fuelle(self, zeilen: list[list[str]], daten: list, gedimmt: list[bool] | None = None) -> None:
        auswahl = self.ausgewaehlte_daten()
        self.setRowCount(0)
        self.setRowCount(len(zeilen))
        self.zeilen_daten = list(daten)
        leise = aktuelle_farben().text_leise
        from PySide6.QtGui import QColor

        for r, zeile in enumerate(zeilen):
            for c, text in enumerate(zeile):
                item = QTableWidgetItem(str(text))
                if gedimmt and gedimmt[r]:
                    item.setForeground(QColor(leise))
                self.setItem(r, c, item)
        self.resizeColumnsToContents()
        for r, d in enumerate(self.zeilen_daten):
            if d in auswahl:
                self.selectRow(r)

    def ausgewaehlte_daten(self) -> list:
        zeilen = sorted({i.row() for i in self.selectedIndexes()})
        return [self.zeilen_daten[r] for r in zeilen if r < len(self.zeilen_daten)]

    def aktuelle_daten(self):
        d = self.ausgewaehlte_daten()
        return d[0] if d else None
