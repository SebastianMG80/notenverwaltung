"""Dateien aller freigegebenen Versionen bleiben lesbar – mit unverändertem Inhalt.

Für jede Version liegt in tests/daten/ eine Datenbank `version_X_Y_Z.nvdb` mit erwartetem Inhalt
`version_X_Y_Z.json` (erzeugt mit werkzeuge/versionsdatei.py, danach nie mehr verändert).
"""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from notenverwaltung.speicher import schema
from notenverwaltung.speicher.datenbank import DAUERHAFT, MAX_SICHERUNGEN, Datenbank, sicherungsordner

WURZEL = Path(__file__).resolve().parent.parent
DATEIEN = sorted((WURZEL / "tests" / "daten").glob("version_*.nvdb"))


def _werkzeug():
    spec = importlib.util.spec_from_file_location("versionsdatei", WURZEL / "werkzeuge" / "versionsdatei.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_es_gibt_versionsdateien():
    assert DATEIEN, "keine Versionsdateien gefunden"
    for d in DATEIEN:
        assert d.with_suffix(".json").exists(), f"{d.name}: erwarteter Inhalt fehlt"


@pytest.mark.parametrize("datei", DATEIEN, ids=lambda p: p.stem)
def test_alte_datei_oeffnen_und_inhalt_gleich(app, tmp_path, datei):
    w = _werkzeug()
    kopie = tmp_path / datei.name
    shutil.copy(datei, kopie)              # Original nie verändern (Sperrdatei, Umstellung, Sicherungen)
    erwartet = json.loads(datei.with_suffix(".json").read_text(encoding="utf-8"))
    fehler = w.vergleiche(erwartet, w.inhalt(kopie))
    assert not fehler, "\n".join(fehler[:20])
    # Speichern im neuen Format und erneut öffnen: immer noch derselbe Inhalt
    db = Datenbank.oeffnen(kopie, "passwort", w.PASSWORT_TEST)
    db.speichern()
    db.schliessen()
    fehler = w.vergleiche(erwartet, w.inhalt(kopie))
    assert not fehler, "\n".join(fehler[:20])


def test_vergleich_findet_abweichungen():
    erwartet = {"tabellen": {"t": {"spalten": ["a", "b"], "zeilen": [[1, "x"]]}},
                "sicht": {"G": {"arbeiten": {"KA": [["A", 10, "2"]]}}}}
    gleich = {"tabellen": {"t": {"spalten": ["a", "neu", "b"], "zeilen": [[1, None, "x"]]}},
              "sicht": {"G": {"arbeiten": {"KA": [["A", 10, "2"]]}, "neu": 1}}}
    assert _werkzeug().vergleiche(erwartet, gleich) == []          # neue Spalten/Teile sind erlaubt
    anders = json.loads(json.dumps(gleich))
    anders["tabellen"]["t"]["zeilen"][0][2] = "y"
    anders["sicht"]["G"]["arbeiten"]["KA"][0][2] = "3"
    assert len(_werkzeug().vergleiche(erwartet, anders)) == 2        # Zeile verändert, Sicht verändert
    anders["tabellen"]["t"]["zeilen"].append([2, None, "z"])
    assert any("1 → 2 Zeilen" in f for f in _werkzeug().vergleiche(erwartet, anders))   # Zeile dazugekommen


def test_sicherung_vor_format_umstellung(app, tmp_path, schnelle_kdf, monkeypatch):
    db, _ = Datenbank.neu(tmp_path / "u", "Testpasswort1")
    db.schliessen()
    pfad = tmp_path / "u.nvdb"
    alt = pfad.read_bytes()
    # künftige Umstellung simulieren
    monkeypatch.setattr(schema, "MIGRATIONEN", [*schema.MIGRATIONEN, "CREATE TABLE zukunft (x INTEGER);"])
    monkeypatch.setattr(schema, "SCHEMA_VERSION", len(schema.MIGRATIONEN))
    db = Datenbank.oeffnen(pfad, "passwort", "Testpasswort1")
    dauerhaft = [s for s in db.sicherungen() if DAUERHAFT in s.name]
    assert len(dauerhaft) == 1 and dauerhaft[0].read_bytes() == alt
    assert f"Format-{schema.SCHEMA_VERSION - 1}-auf-{schema.SCHEMA_VERSION}" in dauerhaft[0].name
    assert db.geaendert
    db.schliessen()
    assert len(db.sicherungen()) == 1                       # keine zusätzliche Sitzungssicherung
    # Viele Sitzungen später: die gewöhnlichen Sicherungen rotieren, die dauerhafte bleibt
    ordner = sicherungsordner(pfad)
    for i in range(MAX_SICHERUNGEN + 5):
        (ordner / f"u_2027-01-{i + 1:02d}_08-00-00.nvdb").write_bytes(b"x")
    db = Datenbank.oeffnen(pfad, "passwort", "Testpasswort1")
    db.speichern()
    db.schliessen(speichern=False)
    namen = [s.name for s in db.sicherungen()]
    assert len(namen) == MAX_SICHERUNGEN + 1 and any(DAUERHAFT in n for n in namen)
