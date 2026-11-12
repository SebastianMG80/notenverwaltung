"""Selbsttest des fertigen Programms: `Notenverwaltung --selbsttest`.

Prüft im gebauten Programm (PyInstaller), dass alle Bausteine enthalten sind und zusammenspielen:
Verschlüsselung, Datenbank, Notenlogik, PDF-Ausgaben, QR-Code, Oberfläche. Arbeitet nur in einem
temporären Ordner und gibt 0 (in Ordnung) oder 1 (Fehler) zurück.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import date
from pathlib import Path


def selbsttest() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    protokoll = Path(tempfile.gettempdir()) / "notenverwaltung-selbsttest.txt"
    zeilen = []
    try:
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([sys.argv[0]])
        with tempfile.TemporaryDirectory() as ordner:
            ordner = Path(ordner)
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(ordner / "cfg"))

            from notenverwaltung.ausgabe import notfallblatt
            from notenverwaltung.ausgabe.abschnitte import AVERY_3424, Notenabschnitte
            from notenverwaltung.ausgabe.punkteliste import Punkteliste
            from notenverwaltung.ausgabe.seite import als_pdf
            from notenverwaltung.modell.arbeiten import Arbeiten
            from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
            from notenverwaltung.speicher.datenbank import Datenbank
            from notenverwaltung.speicher.tresor import PASSWORT, WIEDERHERSTELLUNG
            from notenverwaltung.ui.hauptfenster import Hauptfenster

            db, code = Datenbank.neu(ordner / "selbsttest", "Selbsttest Größe 2026")
            sd = Stammdaten(db.verbindung)
            jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
            g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
            sid = sd.lege_schueler_an(jahr.id, "Müller", "Zoë", "9.1").id
            sd.fuege_hinzu(g.id, [sid])
            ar = Arbeiten(db.verbindung)
            a = ar.lege_arbeit_an(g.id, "KA", date(2026, 11, 10), [("1", 52)])
            ar.setze_punkte(ar.aufgaben(a.id)[0].id, sid, 29)
            assert ar.ergebnisse(a.id)[0].note.kurz == "3-", "Notenlogik"
            db.schliessen()
            zeilen.append("Datenbank anlegen/speichern: ok")

            for art, wert in ((PASSWORT, "Selbsttest Größe 2026"), (WIEDERHERSTELLUNG, code)):
                db = Datenbank.oeffnen(ordner / "selbsttest.nvdb", art, wert)
                assert Stammdaten(db.verbindung).schueler(sid).vorname == "Zoë"
                db.schliessen(speichern=False)
            zeilen.append("Entschlüsseln mit Passwort und Code: ok")

            db = Datenbank.oeffnen(ordner / "selbsttest.nvdb", PASSWORT, "Selbsttest Größe 2026")
            ar = Arbeiten(db.verbindung)
            for name, ausgabe in (("liste", Punkteliste(ar, a)), ("abschnitte", Notenabschnitte(ar, a, AVERY_3424))):
                pdf = als_pdf(ausgabe, ordner / f"{name}.pdf")
                assert pdf.read_bytes()[:4] == b"%PDF", name
            assert notfallblatt.als_pdf(ordner / "nf.pdf", "Test", code).read_bytes()[:4] == b"%PDF"
            zeilen.append("PDF-Ausgaben und QR-Code: ok")

            fenster = Hauptfenster()
            fenster.setze_datenbank(db)
            app.processEvents()
            assert fenster.windowTitle().startswith("selbsttest")
            fenster.schliesse_datenbank()
            zeilen.append("Oberfläche: ok")
        zeilen.append("SELBSTTEST BESTANDEN")
        ergebnis = 0
    except Exception:
        zeilen.append("SELBSTTEST FEHLGESCHLAGEN")
        zeilen.append(traceback.format_exc())
        ergebnis = 1
    text = "\n".join(zeilen)
    try:
        protokoll.write_text(text, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout:
        print(text)
    return ergebnis
