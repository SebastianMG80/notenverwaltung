"""Verschlüsselte Datenbank: Anlegen, Öffnen, Zugänge, Manipulation, Sicherungen, Sperre."""

import json
import struct
import sys

import pytest

from notenverwaltung.speicher import krypto
from notenverwaltung.speicher.datenbank import (
    Datenbank,
    GesperrtFehler,
    cloud_hinweis,
    sperrdatei,
)
from notenverwaltung.speicher.krypto import EntschluesselungsFehler, KdfParameter
from notenverwaltung.speicher.schema import SCHEMA_VERSION, SchemaFehler
from notenverwaltung.speicher.tresor import (
    PASSWORT,
    SCHLUESSELDATEI,
    WIEDERHERSTELLUNG,
    FormatFehler,
    Tresor,
)

SCHNELL = KdfParameter(iterationen=1, spuren=1, speicher_kib=1024)
PW = "Grüne Wiese 2026!"


@pytest.fixture
def neue_db(tmp_path):
    db, code = Datenbank.neu(tmp_path / "noten", PW, SCHNELL)
    yield db, code
    try:
        db.schliessen(speichern=False)
    except Exception:
        pass


# ---- Wiederherstellungscode ------------------------------------------------------------------

def test_code_format_und_normalisierung():
    code = krypto.neuer_wiederherstellungscode()
    assert len(code) == 29 and code.count("-") == 5
    roh = krypto.normalisiere_code(code)
    assert krypto.normalisiere_code(roh.lower()) == roh
    assert krypto.normalisiere_code(" ".join(roh)) == roh
    assert krypto.normalisiere_code("O" * 24) == "0" * 24
    assert krypto.normalisiere_code("il" * 12) == "1" * 24
    with pytest.raises(ValueError):
        krypto.normalisiere_code("ABC")
    with pytest.raises(ValueError):
        krypto.normalisiere_code("Ä" * 24)


def test_codes_sind_zufaellig():
    assert len({krypto.neuer_wiederherstellungscode() for _ in range(50)}) == 50


# ---- Anlegen und Öffnen ----------------------------------------------------------------------

def test_neu_haengt_endung_an_und_speichert(neue_db, tmp_path):
    db, code = neue_db
    assert db.pfad == tmp_path / "noten.nvdb"
    assert db.pfad.exists()
    assert not db.geaendert
    assert db.meta("erstellt")


def test_klartext_steht_nicht_in_der_datei(neue_db):
    db, _ = neue_db
    db.setze_meta("geheim", "Hans Muster hat eine 2+")
    db.speichern()
    roh = db.pfad.read_bytes()
    assert b"Hans" not in roh and b"Muster" not in roh
    assert b"SQLite format" not in roh
    assert not (db.pfad.parent / "noten.nvdb.neu").exists()


def test_oeffnen_mit_passwort(neue_db):
    db, _ = neue_db
    db.setze_meta("schule", "Gesamtschule Musterstadt")
    db.schliessen()
    db2 = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    assert db2.meta("schule") == "Gesamtschule Musterstadt"
    db2.schliessen()


def test_passwort_unicode_normalisiert(tmp_path):
    zusammengesetzt = "Grün"       # ü als ein Zeichen
    zerlegt = "Grün"              # u + Trema (so liefern manche Systeme Eingaben)
    db, _ = Datenbank.neu(tmp_path / "u", zusammengesetzt, SCHNELL)
    db.schliessen()
    Datenbank.oeffnen(db.pfad, PASSWORT, zerlegt).schliessen()


def test_falsches_passwort(neue_db):
    db, _ = neue_db
    db.schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, "falsch")


def test_oeffnen_mit_wiederherstellungscode(neue_db):
    db, code = neue_db
    db.schliessen()
    eingabe = code.lower().replace("-", " ")
    db2 = Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, eingabe)
    db2.aendere_passwort("Neues Passwort 1")
    db2.schliessen()
    Datenbank.oeffnen(db.pfad, PASSWORT, "Neues Passwort 1").schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


def test_falscher_code(neue_db):
    db, _ = neue_db
    db.schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, krypto.neuer_wiederherstellungscode())
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, "zu kurz")


def test_neuer_code_macht_alten_ungueltig(neue_db):
    db, alt = neue_db
    neu = db.neuer_wiederherstellungscode()
    db.schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, alt)
    Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, neu).schliessen()


def test_schluesseldatei(neue_db, tmp_path):
    db, _ = neue_db
    (tmp_path / "stick").mkdir()
    datei = db.neue_schluesseldatei(tmp_path / "stick" / "noten")
    assert datei.suffix == ".nvkey"
    db.schliessen()
    Datenbank.oeffnen(db.pfad, SCHLUESSELDATEI, datei.read_bytes()).schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, SCHLUESSELDATEI, b"x" * 71)
    db3 = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    db3.entferne_schluesseldatei()
    db3.schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, SCHLUESSELDATEI, datei.read_bytes())


def test_vorhandene_datei_wird_nicht_ueberschrieben(neue_db):
    db, _ = neue_db
    with pytest.raises(FileExistsError):
        Datenbank.neu(db.pfad, "x", SCHNELL)


# ---- Manipulation und Beschädigung -----------------------------------------------------------

def test_keine_datenbank(tmp_path):
    p = tmp_path / "fremd.nvdb"
    p.write_bytes(b"Hallo Welt, das ist keine Datenbank")
    with pytest.raises(FormatFehler):
        Datenbank.oeffnen(p, PASSWORT, PW)


def test_veraenderter_geheimtext_wird_erkannt(neue_db):
    db, _ = neue_db
    db.schliessen()
    roh = bytearray(db.pfad.read_bytes())
    roh[-5] ^= 0x01
    db.pfad.write_bytes(bytes(roh))
    with pytest.raises(FormatFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


def test_veraenderter_kopf_wird_erkannt(neue_db):
    db, _ = neue_db
    db.schliessen()
    kopf, _, geheim = Tresor.lies_kopf(db.pfad.read_bytes())
    kopf["programm"] = "9.9.9"
    neu = json.dumps(kopf, sort_keys=True, separators=(",", ":")).encode("ascii")
    db.pfad.write_bytes(struct.pack(">4sHI", b"NVDB", 1, len(neu)) + neu + geheim)
    with pytest.raises(FormatFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


def test_neueres_format_wird_abgelehnt(neue_db):
    db, _ = neue_db
    db.schliessen()
    roh = bytearray(db.pfad.read_bytes())
    roh[4:6] = struct.pack(">H", 99)
    db.pfad.write_bytes(bytes(roh))
    with pytest.raises(FormatFehler, match="neueren"):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


def test_unplausible_kdf_parameter_werden_abgelehnt():
    with pytest.raises(ValueError):
        KdfParameter.aus_dict({"name": "argon2id", "iterationen": 3, "spuren": 4, "speicher_kib": 10**9})


def test_neueres_schema_wird_abgelehnt(neue_db):
    db, _ = neue_db
    db.verbindung.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 5}")
    db.speichern()
    db.schliessen(speichern=False)
    with pytest.raises(SchemaFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


# ---- Sicherungen -----------------------------------------------------------------------------

def test_sicherung_vor_erstem_speichern_der_sitzung(neue_db):
    db, _ = neue_db
    assert db.sicherungen() == []  # frisch angelegt: nichts zu sichern
    db.schliessen()
    db2 = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    db2.setze_meta("a", "1")
    db2.speichern()
    db2.setze_meta("a", "2")
    db2.speichern()
    assert len(db2.sicherungen()) == 1  # nur einmal pro Sitzung
    db2.schliessen()


def test_passwortwechsel_gilt_auch_fuer_sicherungen(neue_db):
    db, _ = neue_db
    db.schliessen()
    db2 = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    db2.setze_meta("a", "1")
    db2.speichern()
    sicherung = db2.sicherungen()[0]
    db2.aendere_passwort("Ganz neu 123")
    db2.schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Tresor.oeffne(sicherung.read_bytes(), PASSWORT, PW)
    Tresor.oeffne(sicherung.read_bytes(), PASSWORT, "Ganz neu 123")


# ---- Sperre ----------------------------------------------------------------------------------

def test_sperre_wird_gesetzt_und_entfernt(neue_db):
    db, _ = neue_db
    assert sperrdatei(db.pfad).exists()
    db.schliessen()
    assert not sperrdatei(db.pfad).exists()


def test_fremde_sperre_meldet(neue_db):
    db, _ = neue_db
    db.schliessen()
    sperrdatei(db.pfad).write_text(json.dumps({"rechner": "Schul-PC-12", "pid": 4711, "seit": "12.11.2026 08:00"}))
    with pytest.raises(GesperrtFehler) as e:
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    assert e.value.info.rechner == "Schul-PC-12"
    # falsches Passwort verrät die Sperre nicht
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, "falsch")
    Datenbank.oeffnen(db.pfad, PASSWORT, PW, sperre_ignorieren=True).schliessen()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="unter Windows wird bei eigener Sperre nachgefragt")
def test_verwaiste_eigene_sperre_wird_uebernommen(neue_db):
    from notenverwaltung.speicher.datenbank import _rechnername

    db, _ = neue_db
    db.schliessen()
    sperrdatei(db.pfad).write_text(json.dumps({"rechner": _rechnername(), "pid": 2**22 + 12345, "seit": "gestern"}))
    Datenbank.oeffnen(db.pfad, PASSWORT, PW).schliessen()


# ---- Cloud-Erkennung -------------------------------------------------------------------------

@pytest.mark.parametrize("ordner", ["Cloud", "Nextcloud", "OneDrive - Schule", "Dropbox", "Google Drive"])
def test_cloud_ordner_wird_erkannt(tmp_path, ordner):
    assert cloud_hinweis(tmp_path / ordner / "noten.nvdb") is not None


def test_nextcloud_marker(tmp_path):
    (tmp_path / "Daten").mkdir()
    (tmp_path / "Daten" / ".sync_abc123.db").write_text("")
    assert cloud_hinweis(tmp_path / "Daten" / "x" / "noten.nvdb") is not None


def test_normaler_ordner_ohne_hinweis(tmp_path):
    assert cloud_hinweis(tmp_path / "Dokumente" / "Schule" / "noten.nvdb") is None


# ---- Plattformunabhängigkeit -----------------------------------------------------------------

def test_dateiformat_ist_byte_genau_festgelegt(neue_db):
    """Der Kopf ist reines ASCII-JSON mit festen Feldern – unabhängig von Betriebssystem und Gebietsschema."""
    db, _ = neue_db
    kopf, zusatz, _ = Tresor.lies_kopf(db.pfad.read_bytes())
    assert zusatz[:4] == b"NVDB"
    assert set(kopf) == {"format", "programm", "gespeichert", "kdf", "zugaenge", "daten"}
    assert [z["art"] for z in kopf["zugaenge"]] == [PASSWORT, WIEDERHERSTELLUNG]
