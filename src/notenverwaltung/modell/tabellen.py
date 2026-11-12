"""Tabellendateien lesen: CSV/TXT (auch Untis-GPU), Excel (.xlsx) und OpenDocument (.ods).

Bewusst ohne Zusatzbibliotheken: .xlsx und .ods sind ZIP-Archive mit XML, das hier direkt gelesen wird
(Pythons expat-Parser löst keine externen Entitäten auf). Ergebnis ist immer eine Liste von Zeilen mit Texten.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_GROESSE = 20 * 1024 * 1024
MAX_ZEILEN = 20000


class TabellenFehler(ValueError):
    pass


def lies_tabelle(pfad: Path, blatt: int = 0) -> list[list[str]]:
    pfad = Path(pfad)
    if pfad.stat().st_size > MAX_GROESSE:
        raise TabellenFehler("Die Datei ist zu groß für eine Schülerliste.")
    endung = pfad.suffix.lower()
    try:
        if endung == ".xlsx":
            zeilen = _lies_xlsx(pfad, blatt)
        elif endung == ".ods":
            zeilen = _lies_ods(pfad, blatt)
        elif endung in (".xls",):
            raise TabellenFehler("Das alte Excel-Format .xls wird nicht unterstützt. Bitte als .xlsx oder .csv speichern.")
        else:
            zeilen = _lies_text(pfad.read_bytes())
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as e:
        raise TabellenFehler(f"Die Datei kann nicht gelesen werden ({e.__class__.__name__}).") from e
    # Leere Zeilen und Leerraum am Rand entfernen, Zeilen auf gleiche Länge bringen
    zeilen = [[z.strip() for z in zeile] for zeile in zeilen[:MAX_ZEILEN]]
    zeilen = [z for z in zeilen if any(z)]
    breite = max((len(z) for z in zeilen), default=0)
    while breite and all(len(z) < breite or not z[breite - 1] for z in zeilen):
        breite -= 1
    return [(z + [""] * breite)[:breite] for z in zeilen]


def blaetter(pfad: Path) -> list[str]:
    pfad = Path(pfad)
    try:
        if pfad.suffix.lower() == ".xlsx":
            with zipfile.ZipFile(pfad) as z:
                wb = ET.fromstring(z.read("xl/workbook.xml"))
            return [s.get("name", "") for s in wb.iter(f"{{{_X}}}sheet")]
        if pfad.suffix.lower() == ".ods":
            with zipfile.ZipFile(pfad) as z:
                inhalt = ET.fromstring(z.read("content.xml"))
            return [t.get(f"{{{_TABLE}}}name", "") for t in inhalt.iter(f"{{{_TABLE}}}table")]
    except (zipfile.BadZipFile, ET.ParseError, KeyError):
        return []
    return []


# ---- Text (CSV, TXT, Untis-GPU) -----------------------------------------------------------------

def _dekodiere(roh: bytes) -> str:
    for kodierung in ("utf-8-sig", "cp1252"):
        try:
            return roh.decode(kodierung)
        except UnicodeDecodeError:
            continue
    return roh.decode("latin-1")


def _lies_text(roh: bytes) -> list[list[str]]:
    text = _dekodiere(roh)
    probe = "\n".join(text.splitlines()[:20])
    zaehler = {t: probe.count(t) for t in (";", "\t", ",", "|")}
    trenner = max(zaehler, key=zaehler.get) if any(zaehler.values()) else ";"
    return [list(z) for z in csv.reader(io.StringIO(text), delimiter=trenner, quotechar='"')]


# ---- Excel .xlsx --------------------------------------------------------------------------------

_X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _spaltennummer(zelle: str) -> int:
    buchstaben = re.match(r"[A-Z]+", zelle).group(0)
    n = 0
    for b in buchstaben:
        n = n * 26 + ord(b) - 64
    return n - 1


def _lies_xlsx(pfad: Path, blatt: int) -> list[list[str]]:
    with zipfile.ZipFile(pfad) as z:
        namen = set(z.namelist())
        geteilt = []
        if "xl/sharedStrings.xml" in namen:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{{{_X}}}si"):
                geteilt.append("".join(t.text or "" for t in si.iter(f"{{{_X}}}t")))
        datumsformate = _xlsx_datumsstile(z) if "xl/styles.xml" in namen else set()
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        blaetter_ = list(wb.iter(f"{{{_X}}}sheet"))
        if not blaetter_:
            return []
        rid = blaetter_[min(blatt, len(blaetter_) - 1)].get(f"{{{_R}}}id")
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        ziel = next(r.get("Target") for r in rels if r.get("Id") == rid)
        ziel = ziel.lstrip("/")
        ziel = ziel if ziel.startswith("xl/") else "xl/" + ziel
        tabelle = ET.fromstring(z.read(ziel))
    zeilen: list[list[str]] = []
    for row in tabelle.iter(f"{{{_X}}}row"):
        werte: dict[int, str] = {}
        for c in row.iter(f"{{{_X}}}c"):
            typ = c.get("t")
            v = c.find(f"{{{_X}}}v")
            if typ == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{{{_X}}}t"))
            elif v is None or v.text is None:
                text = ""
            elif typ == "s":
                text = geteilt[int(v.text)]
            elif typ in ("str", "b", "e"):
                text = v.text
            else:
                text = v.text
                if c.get("s") and int(c.get("s")) in datumsformate:
                    try:
                        text = (datetime(1899, 12, 30) + timedelta(days=float(text))).strftime("%d.%m.%Y")
                    except (ValueError, OverflowError):
                        pass
                elif re.fullmatch(r"-?\d+\.0+", text):
                    text = text.split(".")[0]
            werte[_spaltennummer(c.get("r", "A1"))] = text
        if werte:
            zeilen.append([werte.get(i, "") for i in range(max(werte) + 1)])
    return zeilen


def _xlsx_datumsstile(z: zipfile.ZipFile) -> set[int]:
    styles = ET.fromstring(z.read("xl/styles.xml"))
    eigene = {int(f.get("numFmtId")): f.get("formatCode", "") for f in styles.iter(f"{{{_X}}}numFmt")}
    datum_ids = set(range(14, 23)) | {i for i, code in eigene.items()
                                      if re.search(r"[dy]", re.sub(r"\[.*?\]|\".*?\"", "", code.lower()))}
    xfs = styles.find(f"{{{_X}}}cellXfs")
    if xfs is None:
        return set()
    return {i for i, xf in enumerate(xfs) if int(xf.get("numFmtId", 0)) in datum_ids}


# ---- OpenDocument .ods --------------------------------------------------------------------------

_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"


def _ods_text(zelle) -> str:
    wert_typ = zelle.get(f"{{{_OFFICE}}}value-type")
    if wert_typ == "date":
        d = zelle.get(f"{{{_OFFICE}}}date-value", "")[:10]
        try:
            return date.fromisoformat(d).strftime("%d.%m.%Y")
        except ValueError:
            pass
    absaetze = []
    for p in zelle.iter(f"{{{_TEXT}}}p"):
        absaetze.append("".join(p.itertext()))
    return "\n".join(absaetze)


def _lies_ods(pfad: Path, blatt: int) -> list[list[str]]:
    with zipfile.ZipFile(pfad) as z:
        inhalt = ET.fromstring(z.read("content.xml"))
    tabellen = list(inhalt.iter(f"{{{_TABLE}}}table"))
    if not tabellen:
        return []
    tabelle = tabellen[min(blatt, len(tabellen) - 1)]
    zeilen: list[list[str]] = []
    for row in tabelle.iter(f"{{{_TABLE}}}table-row"):
        wdh_zeile = min(int(row.get(f"{{{_TABLE}}}number-rows-repeated", "1")), 1000)
        werte: list[str] = []
        for zelle in row:
            if zelle.tag not in (f"{{{_TABLE}}}table-cell", f"{{{_TABLE}}}covered-table-cell"):
                continue
            wdh = min(int(zelle.get(f"{{{_TABLE}}}number-columns-repeated", "1")), 200)
            werte.extend([_ods_text(zelle)] * wdh)
        while werte and not werte[-1]:
            werte.pop()
        if werte:
            zeilen.extend([werte] * wdh_zeile)
        elif zeilen:
            zeilen.append([])
        if len(zeilen) > MAX_ZEILEN:
            break
    return zeilen
