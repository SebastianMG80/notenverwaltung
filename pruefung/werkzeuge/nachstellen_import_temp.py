import io, json, os, sys, zipfile, time
from datetime import date
from pathlib import Path
KOPIE, ARBEIT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(KOPIE / "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QSettings
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(ARBEIT / "cfg"))
from notenverwaltung.speicher import tresor as T
from notenverwaltung.speicher.krypto import KdfParameter
from notenverwaltung.speicher.datenbank import Datenbank
from notenverwaltung.modell.stammdaten import Stammdaten, Lerngruppe
from notenverwaltung.modell.arbeiten import Arbeiten
from notenverwaltung.modell import tabellen, importieren, ki
from notenverwaltung.modell.noten import Notenschluessel
from dataclasses import replace
T.STANDARD_KDF = KdfParameter(1, 1, 64)
def titel(t): print("\n=== " + t, flush=True)
def offene():
    erg = []
    for fd in os.listdir("/proc/self/fd"):
        try: z = os.readlink(f"/proc/self/fd/{fd}")
        except OSError: continue
        if "etilqs" in z or "(deleted)" in z:
            erg.append((int(fd), z, os.fstat(int(fd)).st_size))
    return erg

titel("2 TEMP-Speicher: Rückgängig-Protokoll mit großer Musterlösung")
for f in ARBEIT.glob("temp*"):
    if f.is_file(): f.unlink()
db, _ = Datenbank.neu(ARBEIT / "temp.nvdb", "Erfundenes Passwort 1")
sd = Stammdaten(db.verbindung); ar = Arbeiten(db.verbindung)
jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
g = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M9", "Mathematik", "kurs", 9, "M", "E"))
s = sd.lege_schueler_an(jahr.id, "Geheimname", "Erfunden", "9.1"); sd.fuege_hinzu(g.id, [s.id])
a = ar.lege_arbeit_an(g.id, "KA1", date(2026, 11, 10), [("1", 10)])
gefunden_bei = None
for i in range(1, 121):
    a = replace(ar.arbeit(a.id), musterloesung=("Musterloesung GEHEIMTEXT %d " % i) * 4000, bemerkung=f"Bem {i}")
    ar.aendere_arbeit(a)
    ar.setze_teilnahme(a.id, s.id, kommentar=f"Rueckmeldung an Geheimname Nr {i}")
    db.verlauf.abschliessen()
    o = offene()
    if o and gefunden_bei is None:
        gefunden_bei = i
        break
print("Temp-Datei entstanden nach Änderungen:", gefunden_bei, "|", offene())
for fd, z, n in offene():
    inhalt = os.pread(fd, n, 0)
    print("  Datei", z, "Größe", n, "| enthält Klartext 'GEHEIMTEXT':", b"GEHEIMTEXT" in inhalt,
          "| enthält 'Geheimname':", b"Geheimname" in inhalt)
print("SQLITE_TMPDIR/TMPDIR:", os.environ.get("SQLITE_TMPDIR"), os.environ.get("TMPDIR"))
db.schliessen(speichern=False)

titel("6 Import fremder Dateien")
def xlsx(zellen_xml, shared=None, extra=None):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="A" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + zellen_xml + '</sheetData></worksheet>')
        if shared is not None: z.writestr("xl/sharedStrings.xml", shared)
        for n, d in (extra or {}).items(): z.writestr(n, d)
    return b.getvalue()
def probiere(name, daten, endung=".xlsx", grenze=20):
    p = ARBEIT / ("imp" + endung); p.write_bytes(daten)
    import resource, signal
    def alarm(*_): raise TimeoutError("Hänger (über %d s)" % grenze)
    signal.signal(signal.SIGALRM, alarm); signal.alarm(grenze)
    t = time.time()
    try:
        z = tabellen.lies_tabelle(p)
        print(f"  {name:40s} ok, {len(z)} Zeilen, {time.time()-t:.1f}s")
    except BaseException as e:
        print(f"  {name:40s} {type(e).__name__}: {str(e)[:70]} ({time.time()-t:.1f}s)")
    finally:
        signal.alarm(0)
import resource
resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
probiere("normale Zelle", xlsx('<row r="1"><c r="A1" t="inlineStr"><is><t>Name</t></is></c></row>'))
probiere("Spalte ZZZZZZZ1", xlsx('<row r="1"><c r="ZZZZZZZ1" t="inlineStr"><is><t>x</t></is></c></row>'), grenze=15)
probiere("Zellbezug klein 'a1'", xlsx('<row r="1"><c r="a1"><v>1</v></c></row>'))
probiere("Verweis auf fehlenden Text", xlsx('<row r="1"><c r="A1" t="s"><v>7</v></c></row>'))
probiere("Verweis kein Zahlwert", xlsx('<row r="1"><c r="A1" t="s"><v>x</v></c></row>'))
probiere("Stil keine Zahl", xlsx('<row r="1"><c r="A1" s="x"><v>1</v></c></row>', extra={"xl/styles.xml": '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs><xf numFmtId="14"/></cellXfs></styleSheet>'}))
probiere("Zip-Bombe sharedStrings 1 GiB", xlsx('<row r="1"><c r="A1"><v>1</v></c></row>', shared=b"<sst>" + b" " * (1024**3) + b"</sst>"), grenze=60)
lol = '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa">' + "".join(f'<!ENTITY {chr(98+i)} "{("&"+chr(97+i)+";")*10}">' for i in range(9)) + ']><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>&j;</t></si></sst>'
probiere("Entitäten-Bombe (billion laughs)", xlsx('<row r="1"><c r="A1" t="s"><v>0</v></c></row>', shared=lol), grenze=30)
ext = '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY x SYSTEM "file:///etc/hostname">]><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>&x;</t></si></sst>'
p = ARBEIT / "imp.xlsx"; p.write_bytes(xlsx('<row r="1"><c r="A1" t="s"><v>0</v></c></row>', shared=ext))
try: print("  externe Entität (Datei lesen):           Ergebnis", tabellen.lies_tabelle(p))
except Exception as e: print("  externe Entität:", type(e).__name__, e)
probiere("CSV mit 200-kB-Feld", ("Name;Vorname;Klasse\n" + "x" * 200000 + ";a;8.1\n").encode(), ".csv")
probiere("CSV mit NUL-Byte", b"Name;Vorname;Klasse\nA\x00B;a;8.1\n", ".csv")
probiere("leere Datei", b"", ".csv")
probiere("kein Zip als .xlsx", b"hallo", ".xlsx")
probiere("ODS Wiederholung keine Zahl", (lambda: (lambda b: (zipfile.ZipFile(b, "w").__enter__().writestr("content.xml", '<d xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><table:table><table:table-row table:number-rows-repeated="x"><table:table-cell><text:p>a</text:p></table:table-cell></table:table-row></table:table></d>'), b)[1])(io.BytesIO()))().getvalue(), ".ods")

zeilen = [["Nachname", "Vorname", "Klasse", "Jahrgang"], ["Muster", "Mia", "8.1", "²"]]
try:
    print("  Jahrgang '²':", importieren.datensaetze(zeilen, importieren.erkenne(zeilen)))
except Exception as e:
    print("  Jahrgang '²':", type(e).__name__, e)

titel("7 KI-Antwort")
for name, text in (("tief verschachtelt", '{"aufgaben": ' + "[" * 100000 + "]" * 100000 + "}"),
                   ("Punkte 1e999", '{"aufgaben":[{"bezeichnung":"1","punkte":1e999}]}'),
                   ("Punkte NaN", '{"aufgaben":[{"bezeichnung":"1","punkte":NaN}]}'),
                   ("viele Zäune", ("```{" + "}" * 50) * 5000)):
    t = time.time()
    try:
        ki.lies_antwort(text); print(f"  {name:22s} angenommen")
    except Exception as e:
        print(f"  {name:22s} {type(e).__name__}: {str(e)[:60]} ({time.time()-t:.1f}s)")

titel("12 Notenschlüssel bei kleinen Höchstpunktzahlen")
k = Notenschluessel.standard()
for h in (1, 2, 3, 5, 9, 10, 20, 52):
    print(f"  Höchstpunkte {h:3d}: 0 Punkte → {k.note(0, h).kurz:3s} | volle Punkte → {k.note(h, h).kurz}")
k2 = Notenschluessel.standard("sek2")
for h in (1, 2, 4, 10):
    print(f"  Sek II Höchstpunkte {h:3d}: 0 Punkte → {k2.note(0, h).kurz:3s} | volle Punkte → {k2.note(h, h).kurz}")
