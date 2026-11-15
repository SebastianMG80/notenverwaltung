"""Schüler:innen-Bogen zeigen und drucken: Vorschau mit Häkchen zum Weglassen."""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QVBoxLayout, QWidget

from notenverwaltung.ausgabe.personenbogen import BogenOptionen, PersonenbogenAusgabe
from notenverwaltung.modell.personenbogen import personenbogen
from notenverwaltung.ui.vorschau_dialog import VorschauDialog

TEXTE = {
    "tendenzen": "Tendenzen (2+, 2-)",
    "punkte": "Punkte der Klassenarbeiten",
    "rueckmeldungen": "Rückmeldungen zu Arbeiten",
    "bemerkungen": "Bemerkungen zu mündlichen Noten",
    "beobachtungen": "Schnellerfassung (++ … ––) und Notizen",
    "fruehere_jahre": "Frühere Schuljahre (Verlauf)",
}


def personenbogen_dialog(verbindung, schueler_id: int, parent: QWidget | None = None) -> VorschauDialog:
    bogen = personenbogen(verbindung, schueler_id)
    s = bogen.schueler
    optionen = QWidget()
    lay = QVBoxLayout(optionen)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(QLabel("<b>Aufnehmen</b>"))
    haken = {}
    for feld in fields(BogenOptionen):
        c = QCheckBox(TEXTE[feld.name])
        c.setChecked(feld.default)
        lay.addWidget(c)
        haken[feld.name] = c
    eltern = QPushButton("Für die Weitergabe an Eltern")
    eltern.setToolTip("Ohne Tendenzen, Bemerkungen und Schnellerfassung – Rückmeldungen und Noten bleiben.")
    alles = QPushButton("Alles (für mich)")
    lay.addSpacing(8)
    lay.addWidget(eltern)
    lay.addWidget(alles)
    hinweis = QLabel("Der Bogen enthält Noten – nicht offen liegen lassen und nicht in einer Cloud ablegen.",
                     objectName="leise")
    hinweis.setWordWrap(True)
    lay.addSpacing(8)
    lay.addWidget(hinweis)

    def baue():
        return PersonenbogenAusgabe(bogen, BogenOptionen(**{k: c.isChecked() for k, c in haken.items()}))

    d = VorschauDialog(f"Schüler:innen-Bogen – {s.vorname} {s.nachname}", baue, optionen, verbindung,
                       f"Schülerbogen {s.nachname} {s.vorname}.pdf", parent)

    def setze(o: BogenOptionen) -> None:
        for k, c in haken.items():
            c.blockSignals(True)
            c.setChecked(getattr(o, k))
            c.blockSignals(False)
        d.aktualisieren()

    eltern.clicked.connect(lambda: setze(BogenOptionen.fuer_eltern()))
    alles.clicked.connect(lambda: setze(BogenOptionen()))
    for c in haken.values():
        c.toggled.connect(d.aktualisieren)
    d.haken = haken                    # für Tests
    d.aktualisieren()
    return d
