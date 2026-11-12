"""KI-Paket: Prompt-Vorlage kopieren, KI-Antwort einfügen, als Arbeit übernehmen."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from notenverwaltung.modell.arbeiten import Arbeit, ArbeitFehler, Arbeiten
from notenverwaltung.modell.ki import KiArbeit, KiFehler, lies_antwort, prompt_vorlage
from notenverwaltung.modell.noten import zahl_text
from notenverwaltung.modell.stammdaten import Lerngruppe, Schuljahr
from notenverwaltung.ui.bausteine import Datumsfeld, Hinweis, frage


class KiDialog(QDialog):
    def __init__(self, ar: Arbeiten, jahr: Schuljahr, gruppe: Lerngruppe, arbeit: Arbeit | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ar, self.jahr, self.gruppe, self.arbeit = ar, jahr, gruppe, arbeit
        self.ergebnis: Arbeit | None = None
        self.ki: KiArbeit | None = None
        self.setWindowTitle("KI-Vorlage für eine Arbeit")
        self.resize(820, 680)

        # ---- Reiter 1: Prompt
        self.art_bewerten = QRadioButton("Ich habe eine fertige Arbeit – bitte Bepunktung und Musterlösung vorschlagen")
        self.art_erstellen = QRadioButton("Bitte eine Arbeit zu einem Thema erstellen")
        g = QButtonGroup(self)
        g.addButton(self.art_bewerten)
        g.addButton(self.art_erstellen)
        self.art_bewerten.setChecked(True)
        self.punkte = QDoubleSpinBox()
        self.punkte.setRange(0, 500)
        self.punkte.setDecimals(0)
        self.punkte.setSpecialValueText("egal")
        self.prompt = QPlainTextEdit()
        self.prompt.setReadOnly(True)
        self.prompt.setFont(QFont("Monospace", 9))
        kopieren = QPushButton("In die Zwischenablage kopieren", objectName="primaer")
        kopieren.clicked.connect(self._kopieren)
        self.kopiert = Hinweis()
        datenschutz = Hinweis("Wichtig: Gib in das KI-Werkzeug keine Namen oder sonstigen Daten von Schüler:innen ein – "
                              "nur die Aufgaben. Das Programm selbst sendet nichts.", "warnung")
        r1 = QWidget()
        l1 = QVBoxLayout(r1)
        l1.addWidget(self.art_bewerten)
        l1.addWidget(self.art_erstellen)
        f1 = QFormLayout()
        f1.addRow("Gesamtpunktzahl:", self.punkte)
        l1.addLayout(f1)
        l1.addWidget(QLabel("So gehst du vor: Text kopieren, im KI-Werkzeug einfügen, darunter deine Arbeit bzw. das "
                            "Thema ergänzen, Antwort im zweiten Reiter einfügen."))
        l1.addWidget(self.prompt, 1)
        zeile = QHBoxLayout()
        zeile.addWidget(kopieren)
        zeile.addWidget(self.kopiert, 1)
        l1.addLayout(zeile)
        l1.addWidget(datenschutz)
        for w in (self.art_bewerten, self.art_erstellen):
            w.toggled.connect(self._prompt)
        self.punkte.valueChanged.connect(self._prompt)

        # ---- Reiter 2: Antwort
        self.antwort = QPlainTextEdit()
        self.antwort.setPlaceholderText("Antwort der KI hier einfügen (das JSON, gern mit dem Text drumherum) …")
        self.antwort.setFont(QFont("Monospace", 9))
        self.antwort.textChanged.connect(self._pruefen)
        self.vorschau = QTableWidget(0, 4)
        self.vorschau.setHorizontalHeaderLabels(["Aufgabe", "Punkte", "Thema", "Erwartungshorizont"])
        self.vorschau.verticalHeader().setVisible(False)
        self.vorschau.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.meldung = Hinweis()
        self.datum = Datumsfeld(date.today() if jahr.enthaelt(date.today()) else jahr.beginn)
        self.datum.begrenze(jahr.beginn, jahr.ende)
        self.k_neu = QPushButton("Als neue Arbeit anlegen", objectName="primaer")
        self.k_neu.clicked.connect(self._neu)
        self.k_uebernehmen = QPushButton(f"In „{arbeit.titel}“ übernehmen" if arbeit else "In aktuelle Arbeit übernehmen")
        self.k_uebernehmen.setVisible(arbeit is not None)
        self.k_uebernehmen.clicked.connect(self._uebernehmen)
        r2 = QWidget()
        l2 = QVBoxLayout(r2)
        l2.addWidget(self.antwort, 2)
        l2.addWidget(self.meldung)
        l2.addWidget(self.vorschau, 3)
        unten = QHBoxLayout()
        unten.addWidget(QLabel("Geschrieben am:"))
        unten.addWidget(self.datum)
        unten.addStretch(1)
        unten.addWidget(self.k_uebernehmen)
        unten.addWidget(self.k_neu)
        l2.addLayout(unten)

        self.reiter = QTabWidget()
        self.reiter.addTab(r1, "1. Vorlage kopieren")
        self.reiter.addTab(r2, "2. Antwort einfügen")
        schliessen = QPushButton("Schließen")
        schliessen.clicked.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(self.reiter, 1)
        z = QHBoxLayout()
        z.addStretch(1)
        z.addWidget(schliessen)
        lay.addLayout(z)
        self._prompt()
        self._pruefen()

    def _prompt(self, *_) -> None:
        self.prompt.setPlainText(prompt_vorlage(self.gruppe.fach, self.gruppe.jahrgang, self.punkte.value() or None,
                                                self.art_erstellen.isChecked()))
        self.kopiert.setze("")

    def _kopieren(self) -> None:
        QGuiApplication.clipboard().setText(self.prompt.toPlainText())
        self.kopiert.setze("Kopiert. Jetzt im KI-Werkzeug einfügen und deine Arbeit darunter setzen.", "ok")

    def _pruefen(self) -> None:
        text = self.antwort.toPlainText()
        self.ki = None
        self.vorschau.setRowCount(0)
        if not text.strip():
            self.meldung.setze("")
        else:
            try:
                self.ki = lies_antwort(text)
            except KiFehler as e:
                self.meldung.setze(str(e), "fehler")
            else:
                self.vorschau.setRowCount(len(self.ki.aufgaben))
                for r, a in enumerate(self.ki.aufgaben):
                    for c, w in enumerate([a.bezeichnung, zahl_text(a.punkte), a.thema, a.erwartung]):
                        self.vorschau.setItem(r, c, QTableWidgetItem(w))
                self.vorschau.resizeColumnsToContents()
                self.vorschau.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
                self.meldung.setze(f"{len(self.ki.aufgaben)} Aufgaben, zusammen {zahl_text(self.ki.hoechstpunkte)} Punkte"
                                   + (" · mit Musterlösung" if self.ki.musterloesung else ""), "ok")
        self.k_neu.setEnabled(self.ki is not None)
        self.k_uebernehmen.setEnabled(self.ki is not None)

    def _zeilen(self, vorhanden: list | None = None) -> list[tuple]:
        """Aufgaben der KI; vorhandene Aufgaben werden der Reihe nach weiterverwendet (Punkte bleiben erhalten)."""
        alt = vorhanden or []
        return [(alt[i].id if i < len(alt) else None, a.bezeichnung, a.punkte, a.thema, a.erwartung)
                for i, a in enumerate(self.ki.aufgaben)]

    def _neu(self) -> None:
        if self.ki is None:
            return
        try:
            a = self.ar.lege_arbeit_an(self.gruppe.id, self.ki.titel or self.ar.titel_vorschlag(self.gruppe.id),
                                       self.datum.wert(), thema=self.ki.thema)
            self.ar.setze_aufgaben(a.id, self._zeilen())
            self.ar.aendere_arbeit(replace(self.ar.arbeit(a.id), musterloesung=self.ki.musterloesung))
        except ArbeitFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.ergebnis = self.ar.arbeit(a.id)
        self.accept()

    def _uebernehmen(self) -> None:
        if self.ki is None or self.arbeit is None:
            return
        alt = self.ar.aufgaben(self.arbeit.id)
        if len(alt) > len(self.ki.aufgaben) and not frage(
                self, "Aufgaben entfallen",
                f"Die Arbeit hat {len(alt)} Aufgaben, die Vorlage nur {len(self.ki.aufgaben)}. Die übrigen Aufgaben "
                "werden samt eingetragener Punkte gelöscht. Fortfahren?", ja="Fortfahren", warnung=True):
            return
        try:
            self.ar.setze_aufgaben(self.arbeit.id, self._zeilen(alt))
            neu = replace(self.ar.arbeit(self.arbeit.id), musterloesung=self.ki.musterloesung or self.arbeit.musterloesung,
                          thema=self.arbeit.thema or self.ki.thema)
            self.ar.aendere_arbeit(neu)
        except ArbeitFehler as e:
            self.meldung.setze(str(e), "fehler")
            return
        self.ergebnis = self.ar.arbeit(self.arbeit.id)
        self.accept()
