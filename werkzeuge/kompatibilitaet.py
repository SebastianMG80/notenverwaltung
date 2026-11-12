"""Kompatibilität des Dateiformats zwischen Linux und Windows prüfen.

    python werkzeuge/kompatibilitaet.py erzeuge <datei.nvdb>
    python werkzeuge/kompatibilitaet.py pruefe  <datei.nvdb>

Die Datenbank enthält feste, erfundene Inhalte (mit Umlauten, ß, Akzenten, Viertelpunkten).
Eine unter Linux erzeugte Datei liegt in tests/daten/ und wird auf jedem System geöffnet;
der Windows-Build erzeugt eine eigene, die unter Linux geprüft wird.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from notenverwaltung.modell.arbeiten import Arbeiten  # noqa: E402
from notenverwaltung.modell.noten import Note  # noqa: E402
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten  # noqa: E402
from notenverwaltung.speicher.datenbank import Datenbank  # noqa: E402
from notenverwaltung.speicher.krypto import KdfParameter  # noqa: E402
from notenverwaltung.speicher.tresor import PASSWORT, WIEDERHERSTELLUNG  # noqa: E402

PASSWORT_TEST = "Prüfung Größe Ölmühle 2026"   # Umlaute: prüft die Normalisierung des Passworts
CODE_TEST = "KMPT-2026-ABCD-EFGH-JKMN-PQRS"
SCHUELER = [("Müller-Lüdenscheidt", "Zoë", "9.1"), ("Straßburger", "Ömer", "9.10"), ("Ćorić", "Ana", "9.2")]


def erzeuge(pfad: Path) -> None:
    pfad = Path(pfad)
    for alt in (pfad, pfad.with_name(pfad.name + ".sperre")):
        alt.unlink(missing_ok=True)
    # Kleine Argon2-Kosten: die Datei liegt im Repo und wird oft geöffnet; Format und Rechenweg bleiben gleich
    db, _ = Datenbank.neu(pfad, PASSWORT_TEST, KdfParameter(2, 2, 8 * 1024))
    db.tresor._setze_zugang(WIEDERHERSTELLUNG, CODE_TEST)  # fester Code, damit beide Seiten ihn kennen
    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9.3E", "Mathematik", "kurs", 9, "M", "E"))
    ids = [sd.lege_schueler_an(jahr.id, n, v, k).id for n, v, k in SCHUELER]
    sd.fuege_hinzu(g.id, ids)
    sd.abgang(ids[2], jahr.id, date(2027, 1, 29))
    ar = Arbeiten(db.verbindung)
    a = ar.lege_arbeit_an(g.id, "1. Klassenarbeit", date(2026, 11, 10), [("1", 5), ("2a", 2.5), ("b", 2.5)])
    x = ar.aufgaben(a.id)
    for sid, werte in zip(ids, [(5, 2.5, 2.5), (3.25, 1.5, 0.75), (1, 0, 0.5)]):
        for aufgabe, w in zip(x, werte):
            ar.setze_punkte(aufgabe.id, sid, w)
    ar.setze_teilnahme(a.id, ids[2], note_manuell=Note.aus_kurz("5-"), kommentar="Bitte üben: „Brüche“ – ½ + ¼")
    db.setze_meta("kompatibilitaet", sys.platform)
    db.schliessen()


def pruefe(pfad: Path) -> str:
    """Wirft AssertionError bei Abweichungen; gibt die Plattform zurück, auf der die Datei entstand."""
    pfad = Path(pfad)
    for art, wert in ((PASSWORT, PASSWORT_TEST), (WIEDERHERSTELLUNG, CODE_TEST.lower().replace("-", " "))):
        db = Datenbank.oeffnen(pfad, art, wert, sperre_ignorieren=True)
        try:
            sd = Stammdaten(db.verbindung)
            jahr = sd.schuljahre()[0]
            assert jahr.bezeichnung == "2026/27"
            g = sd.lerngruppen(jahr.id)[0]
            assert (g.bezeichnung, g.niveau) == ("M9.3E", "E")
            namen = [(m.schueler.nachname, m.schueler.vorname, m.klasse) for m in sd.mitglieder(g.id)]
            assert namen == [("Müller-Lüdenscheidt", "Zoë", "9.1"), ("Ćorić", "Ana", "9.2"),
                             ("Straßburger", "Ömer", "9.10")], namen
            ar = Arbeiten(db.verbindung)
            a = ar.arbeiten(g.id)[0]
            e = {x.mitglied.schueler.vorname: x for x in ar.ergebnisse(a.id)}
            assert e["Zoë"].summe == 10 and e["Zoë"].note.kurz == "1"
            assert e["Ömer"].summe == 5.5 and e["Ömer"].note.kurz == "4+"  # Grenze 3- = ROUND(10·55 %) = 6
            assert e["Ana"].note.kurz == "5-" and e["Ana"].kommentar == "Bitte üben: „Brüche“ – ½ + ¼"
            assert e["Ana"].mitglied.abgang == date(2027, 1, 29)
            herkunft = db.meta("kompatibilitaet")
        finally:
            db.schliessen(speichern=False)
    return herkunft


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("erzeuge", "pruefe"):
        print(__doc__)
        sys.exit(2)
    from PySide6.QtCore import QCoreApplication

    QCoreApplication([])
    if sys.argv[1] == "erzeuge":
        erzeuge(Path(sys.argv[2]))
        print(f"erzeugt: {sys.argv[2]} ({sys.platform})")
    else:
        print(f"in Ordnung: {sys.argv[2]} (erzeugt unter {pruefe(Path(sys.argv[2]))}, geprüft unter {sys.platform})")
