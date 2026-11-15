"""Tests zu den Funden der Sicherheits- und Fehlerprüfung vom 15.11.2026 (siehe pruefung/BERICHT.md).

Jeder Test trägt die Nummer des Fundes im Bericht. Alle Daten sind erfunden.
"""

import copy
import io
import json
import os
import stat
import struct
import sys
import time
import zipfile
from dataclasses import replace
from datetime import date

import pytest

from notenverwaltung.modell import importieren, ki, tabellen
from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
from notenverwaltung.speicher.datenbank import Datenbank, sichere_nach, sicherungsordner
from notenverwaltung.speicher.krypto import EntschluesselungsFehler, KdfParameter
from notenverwaltung.speicher.tresor import PASSWORT, WIEDERHERSTELLUNG, FormatFehler, Tresor

SCHNELL = KdfParameter(iterationen=1, spuren=1, speicher_kib=1024)
PW = "Blaue Tafel 2026!"
FREMD = "Fremdes Passwort 99"
NUR_POSIX = pytest.mark.skipif(os.name != "posix", reason="Dateirechte gibt es so nur unter Linux/macOS")


@pytest.fixture
def db(tmp_path):
    d, code = Datenbank.neu(tmp_path / "noten", PW, SCHNELL)
    d.code = code
    yield d
    try:
        d.schliessen(speichern=False)
    except Exception:
        pass


def _fuelle(d: Datenbank):
    sd, ar = Stammdaten(d.verbindung), Arbeiten(d.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M", "E"))
    s = sd.lege_schueler_an(jahr.id, "Erfunden", "Erika", "9.1")
    sd.fuege_hinzu(g.id, [s.id])
    a = ar.lege_arbeit_an(g.id, "KA1", date(2026, 11, 10), [("1", 10)])
    return sd, ar, g, s, a


# ---- S1: Sperre / Passwortprüfung nicht gegen die Datei auf der Platte -------------------------------

def test_s1_ausgetauschte_datei_entsperrt_nicht(db, tmp_path):
    fremd, _ = Datenbank.neu(tmp_path / "fremd", FREMD, SCHNELL)
    fremd.schliessen()
    db.pfad.write_bytes((tmp_path / "fremd.nvdb").read_bytes())      # jemand tauscht die Datei aus
    assert not db.pruefe_passwort(FREMD)
    assert db.pruefe_passwort(PW)
    db.pfad.unlink()                                                 # selbst ohne Datei gilt das echte Passwort
    assert db.pruefe_passwort(PW)
    assert not db.pruefe_passwort("")


def test_s1_pruefung_folgt_dem_passwortwechsel(db):
    db.aendere_passwort("Neues Passwort 2027")
    assert db.pruefe_passwort("Neues Passwort 2027")
    assert not db.pruefe_passwort(PW)
    assert db.tresor.pruefe_zugang(WIEDERHERSTELLUNG, db.code)
    assert not db.tresor.pruefe_zugang(WIEDERHERSTELLUNG, "0000-0000-0000-0000-0000-0000")
    assert not db.tresor.pruefe_zugang(WIEDERHERSTELLUNG, "kein Code")


# ---- S2: keine unverschlüsselten Zwischendateien ------------------------------------------------------

def test_s2_zwischenspeicher_bleibt_im_arbeitsspeicher(db):
    assert db.verbindung.execute("PRAGMA temp_store").fetchone()[0] == 2
    db.schliessen()
    wieder = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    try:
        assert wieder.verbindung.execute("PRAGMA temp_store").fetchone()[0] == 2
    finally:
        wieder.schliessen(speichern=False)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="offene Dateien lassen sich nur unter Linux auflisten")
def test_s2_grosses_rueckgaengig_protokoll_erzeugt_keine_temp_datei(db):
    def temp_dateien():
        gefunden = []
        for fd in os.listdir("/proc/self/fd"):
            try:
                ziel = os.readlink(f"/proc/self/fd/{fd}")
            except OSError:
                continue
            if "etilqs" in ziel:
                gefunden.append(ziel)
        return gefunden

    vorher = set(temp_dateien())
    sd, ar, g, s, a = _fuelle(db)
    for i in range(40):                                  # vor der Korrektur entstand die Datei nach ~17 Schritten
        ar.aendere_arbeit(replace(ar.arbeit(a.id), musterloesung=f"Musterlösung {i} " * 4000))
        ar.setze_teilnahme(a.id, s.id, kommentar=f"Rückmeldung {i}")
        db.verlauf.abschliessen()
    assert set(temp_dateien()) == vorher
    assert db.verlauf.rueckgaengig() is not None          # der Verlauf arbeitet weiter


# ---- S3: Dateirechte ----------------------------------------------------------------------------------

def _rechte(pfad) -> int:
    return stat.S_IMODE(os.stat(pfad).st_mode)


@NUR_POSIX
def test_s3_dateien_nur_fuer_den_eigenen_benutzer(db, tmp_path, app):
    from notenverwaltung.ausgabe import notfallblatt
    from notenverwaltung.speicher.datenbank import sperrdatei

    alt = os.umask(0o002)                                # so großzügig wie auf vielen Linux-Rechnern
    try:
        db.setze_meta("x", "1")
        db._gesichert = False
        db.speichern()
        schluessel = db.neue_schluesseldatei(tmp_path / "ersatz")
        blatt = notfallblatt.als_pdf(tmp_path / "notfall.pdf", "noten", db.code)
        stick = tmp_path / "stick"
        stick.mkdir()
        kopie = sichere_nach(db.pfad, stick)
    finally:
        os.umask(alt)
    for pfad in (db.pfad, schluessel, blatt, kopie, sperrdatei(db.pfad), *db.sicherungen()):
        assert _rechte(pfad) == 0o600, pfad
    assert _rechte(sicherungsordner(db.pfad)) == 0o700


# ---- S4: Sperr-Uhr zählt den Ruhezustand mit ----------------------------------------------------------

@pytest.mark.skipif(not hasattr(time, "CLOCK_BOOTTIME"), reason="CLOCK_BOOTTIME gibt es nur unter Linux")
def test_s4_betriebszeit_zaehlt_den_ruhezustand(monkeypatch):
    from notenverwaltung.ui import hauptfenster

    assert abs(hauptfenster.betriebszeit() - time.clock_gettime(time.CLOCK_BOOTTIME)) < 1
    monkeypatch.setattr(time, "clock_gettime", lambda uhr: 123456.0 if uhr == time.CLOCK_BOOTTIME else 1.0)
    monkeypatch.setattr(time, "monotonic", lambda: 5.0)   # die schlafende Uhr darf nicht benutzt werden
    assert hauptfenster.betriebszeit() == 123456.0


def test_s4_ohne_boottime_gilt_monotonic(monkeypatch):
    from notenverwaltung.ui import hauptfenster

    monkeypatch.delattr(time, "CLOCK_BOOTTIME", raising=False)
    monkeypatch.setattr(time, "monotonic", lambda: 77.0)
    assert hauptfenster.betriebszeit() == 77.0


# ---- S5: Gesperrt bleibt gesperrt, wenn das Schließen am Speichern scheitert ---------------------------

def test_s5_sperre_bleibt_bei_fehlgeschlagenem_schliessen(app, tmp_path, schnelle_kdf, monkeypatch):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    d, _ = Datenbank.neu(tmp_path / "s", PW)
    f = Hauptfenster()
    f.setze_datenbank(d)
    f.show()
    f.sperren("Test")
    assert f.sperre.aktiv
    d.setze_meta("x", "1")                               # ungespeicherte Änderung …

    def kaputt():
        raise OSError("Datenträger entfernt")

    monkeypatch.setattr(d, "speichern", kaputt)          # … und der Datenträger ist weg
    assert f.schliesse_datenbank() is False
    assert f.sperre.aktiv and f.db is d                  # weiter gesperrt, nichts liegt offen da
    monkeypatch.undo()
    assert f.schliesse_datenbank() is True
    assert not f.sperre.aktiv and f.db is None


# ---- S6: veränderter Dateikopf wird als „beschädigt“ gemeldet ------------------------------------------

def _mit_kopf(daten: bytes, aendern) -> bytes:
    kopf, _, geheim = Tresor.lies_kopf(daten)
    kopf = copy.deepcopy(kopf)
    neu = aendern(kopf)
    kb = json.dumps(kopf if neu is None else neu).encode("ascii")
    return struct.pack(">4sHI", b"NVDB", 1, len(kb)) + kb + geheim


def _setze(pfad, wert):
    def f(kopf):
        ziel = kopf
        for teil in pfad[:-1]:
            ziel = ziel[teil]
        ziel[pfad[-1]] = wert
    return f


@pytest.mark.parametrize("aendern", [
    _setze(("zugaenge",), ["x"]),
    _setze(("zugaenge",), "xyz"),
    _setze(("zugaenge", 0, "salz"), "QUJD"),
    _setze(("zugaenge", 0, "nonce"), "QUJD"),
    _setze(("zugaenge", 0, "verpackt"), "QUJD"),
    _setze(("daten", "nonce"), ""),
    _setze(("daten",), "x"),
    _setze(("kdf",), "argon2id"),
    lambda kopf: [],
    lambda kopf: "x",
], ids=["zugang-kein-objekt", "zugaenge-text", "salz-kurz", "nonce-kurz", "schluessel-kurz", "daten-nonce-leer",
        "daten-text", "kdf-text", "kopf-liste", "kopf-text"])
def test_s6_veraenderter_kopf_ist_formatfehler(db, aendern):
    db.schliessen()
    kaputt = _mit_kopf(db.pfad.read_bytes(), aendern)
    with pytest.raises((FormatFehler, EntschluesselungsFehler)):
        Tresor.oeffne(kaputt, PASSWORT, PW)
    try:
        Tresor.vorhandene_zugaenge(kaputt)
    except FormatFehler:
        pass
    db.pfad.write_bytes(kaputt)
    with pytest.raises((FormatFehler, EntschluesselungsFehler)):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


# ---- S7: Sicherungen bei Dateinamen mit Musterzeichen --------------------------------------------------

def test_s7_sicherungen_bei_namen_mit_eckigen_klammern(tmp_path):
    d, _ = Datenbank.neu(tmp_path / "Noten [2026]", PW, SCHNELL)
    try:
        d.setze_meta("x", "1")
        d._gesichert = False
        d.speichern()
        assert len(d.sicherungen()) == 1
        d.aendere_passwort("Neues Passwort 2027")        # Sicherungen werden neu verpackt
        with pytest.raises(EntschluesselungsFehler):
            Tresor.oeffne(d.sicherungen()[0].read_bytes(), PASSWORT, PW)
        Tresor.oeffne(d.sicherungen()[0].read_bytes(), PASSWORT, "Neues Passwort 2027")
        stick = tmp_path / "stick"
        stick.mkdir()
        for i in range(3):
            ziel = sichere_nach(d.pfad, stick, 1)
            if i < 2:
                ziel.rename(ziel.with_name(f"Noten [2026]_2026-01-0{i + 1}_10-00-00.nvdb"))
        assert len(list(stick.glob("*.nvdb"))) == 1      # nur die neueste Kopie bleibt
    finally:
        d.schliessen(speichern=False)


# ---- S8: Import fremder Tabellen -----------------------------------------------------------------------

_NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _xlsx(pfad, zellen: str, geteilt: bytes | str | None = None, stile: str | None = None):
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", f'<workbook {_NS} xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
                   '2006/relationships"><sheets><sheet name="A" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
                   '2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {_NS}><sheetData>{zellen}</sheetData></worksheet>")
        if geteilt is not None:
            z.writestr("xl/sharedStrings.xml", geteilt)
        if stile is not None:
            z.writestr("xl/styles.xml", stile)
    return pfad


@pytest.mark.parametrize("zellen, stile", [
    ('<row r="1"><c r="ZZZZZZZ1" t="inlineStr"><is><t>x</t></is></c></row>', None),      # hing minutenlang
    ('<row r="1"><c r="1A"><v>1</v></c></row>', None),
    ('<row r="1"><c r="A1" t="s"><v>7</v></c></row>', None),
    ('<row r="1"><c r="A1" t="s"><v>x</v></c></row>', None),
    ('<row r="1"><c r="A1" s="x"><v>1</v></c></row>',
     f'<styleSheet {_NS}><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>'),
], ids=["riesige-spalte", "zellbezug-ungueltig", "text-fehlt", "verweis-keine-zahl", "stil-keine-zahl"])
def test_s8_kaputte_xlsx_gibt_verstaendlichen_fehler(tmp_path, zellen, stile):
    pfad = _xlsx(tmp_path / "liste.xlsx", zellen, stile=stile)
    beginn = time.monotonic()
    with pytest.raises(tabellen.TabellenFehler):
        tabellen.lies_tabelle(pfad)
    assert time.monotonic() - beginn < 5


def test_s8_kleingeschriebener_zellbezug_wird_gelesen(tmp_path):
    pfad = _xlsx(tmp_path / "liste.xlsx", '<row r="1"><c r="b1" t="inlineStr"><is><t>Erfunden</t></is></c></row>')
    assert tabellen.lies_tabelle(pfad) == [["", "Erfunden"]]


def test_s8_zip_bombe_wird_abgelehnt(tmp_path, monkeypatch):
    monkeypatch.setattr(tabellen, "MAX_ENTPACKT", 1024 * 1024)
    pfad = _xlsx(tmp_path / "bombe.xlsx", '<row r="1"><c r="A1"><v>1</v></c></row>',
                 geteilt=b"<sst>" + b" " * (4 * 1024 * 1024) + b"</sst>")
    assert pfad.stat().st_size < 100_000                 # winzige Datei, riesiger Inhalt
    with pytest.raises(tabellen.TabellenFehler, match="zu groß"):
        tabellen.lies_tabelle(pfad)
    assert tabellen.blaetter(pfad) == ["A"]


def test_s8_externe_entitaet_wird_nicht_aufgeloest(tmp_path):
    geheim = tmp_path / "geheim.txt"
    geheim.write_text("NICHT-LESEN", encoding="utf-8")
    xml = (f'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY x SYSTEM "{geheim.as_uri()}">]>'
           f'<sst {_NS}><si><t>&x;</t></si></sst>')
    pfad = _xlsx(tmp_path / "x.xlsx", '<row r="1"><c r="A1" t="s"><v>0</v></c></row>', geteilt=xml)
    try:
        zeilen = tabellen.lies_tabelle(pfad)
    except tabellen.TabellenFehler:
        return
    assert "NICHT-LESEN" not in str(zeilen)


def test_s8_csv_mit_uebergrossem_feld(tmp_path):
    pfad = tmp_path / "liste.csv"
    pfad.write_text("Nachname;Vorname;Klasse\n" + "x" * 200_000 + ";Erika;8.1\n", encoding="utf-8")
    with pytest.raises(tabellen.TabellenFehler):
        tabellen.lies_tabelle(pfad)


def test_s8_ods_mit_unsinniger_wiederholung(tmp_path):
    pfad = tmp_path / "liste.ods"
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr("content.xml", '<d xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
                   'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><table:table>'
                   '<table:table-row table:number-rows-repeated="x"><table:table-cell><text:p>a</text:p>'
                   '</table:table-cell></table:table-row></table:table></d>')
    with pytest.raises(tabellen.TabellenFehler):
        tabellen.lies_tabelle(pfad)


def test_s8_jahrgang_mit_sonderziffer():
    zeilen = [["Nachname", "Vorname", "Klasse", "Jahrgang"], ["Erfunden", "Erika", "8.1", "²"],
              ["Erdacht", "Emil", "9.2", "9"], ["Ersonnen", "Ella", "7.3", "2026"]]
    saetze = importieren.datensaetze(zeilen, importieren.erkenne(zeilen))
    assert [s.jahrgang for s in saetze] == [8, 9, 2026]
    assert [bool(s.fehler) for s in saetze] == [False, False, True]


# ---- S9: Namen in Beschriftungen --------------------------------------------------------------------------

def test_s9_namen_werden_nicht_als_html_gedeutet(app, db):
    from notenverwaltung.ui.stammdaten_dialoge import AbgangDialog

    sd = Stammdaten(db.verbindung)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
    sd.lege_schueler_an(jahr.id, "<i>Erfunden</i>", "A<b", "8.1")
    dialog = AbgangDialog(sd, jahr, sd.schueler_im_jahr(jahr.id)[0])
    from PySide6.QtWidgets import QLabel

    texte = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "&lt;i&gt;Erfunden&lt;/i&gt;" in texte and "<i>Erfunden" not in texte


# ---- S10: KI-Antwort --------------------------------------------------------------------------------------

def test_s10_tief_verschachtelte_antwort():
    with pytest.raises(ki.KiFehler):
        ki.lies_antwort('{"aufgaben": ' + "[" * 100_000 + "]" * 100_000 + "}")


# ---- Speichern: Abbruch mittendrin lässt die alte Datei unversehrt ------------------------------------------

def test_abbruch_beim_speichern_laesst_original_stehen(db, monkeypatch):
    import notenverwaltung.speicher.datenbank as modul

    db.setze_meta("stand", "alt")
    db.speichern()
    vorher = db.pfad.read_bytes()
    db.setze_meta("stand", "neu")

    def kaputt(quelle, ziel):
        raise OSError("Platte voll")

    monkeypatch.setattr(modul.os, "replace", kaputt)
    with pytest.raises(OSError):
        db.speichern()
    monkeypatch.undo()
    assert db.pfad.read_bytes() == vorher
    assert db.geaendert                                   # das Programm weiß, dass noch nicht gespeichert ist
    db.pfad.with_name(db.pfad.name + ".neu").write_bytes(b"halb geschrieben")
    db.speichern()
    db.schliessen()
    wieder = Datenbank.oeffnen(db.pfad, PASSWORT, PW)
    assert wieder.meta("stand") == "neu"
    wieder.schliessen(speichern=False)


def test_abgeschnittene_und_leere_datei(db):
    db.schliessen()
    roh = db.pfad.read_bytes()
    for inhalt in (roh[: len(roh) // 2], roh[:8], b"", b"NVDB", roh[:-1], roh + b"x"):
        db.pfad.write_bytes(inhalt)
        with pytest.raises(FormatFehler):
            Datenbank.oeffnen(db.pfad, PASSWORT, PW)
