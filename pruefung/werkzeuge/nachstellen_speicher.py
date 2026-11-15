"""Nachstellen der Kandidaten an einer Kopie (nur erfundene Daten)."""
import io, json, os, stat, struct, sys, zipfile, traceback, tempfile
from datetime import date
from pathlib import Path

KOPIE, ARBEIT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(KOPIE / "src"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QSettings
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(ARBEIT / "cfg"))

from notenverwaltung.speicher import tresor as T
from notenverwaltung.speicher.krypto import KdfParameter
from notenverwaltung.speicher.datenbank import Datenbank, sichere_nach
from notenverwaltung.speicher.tresor import PASSWORT, Tresor
from notenverwaltung.modell.stammdaten import Stammdaten, Lerngruppe
from notenverwaltung.modell.arbeiten import Arbeiten
T.STANDARD_KDF = KdfParameter(1, 1, 64)

def titel(t): print("\n=== " + t)

def frisch(name, pw="Erfundenes Passwort 1"):
    p = ARBEIT / name
    for f in ARBEIT.glob(p.stem + "*"):
        if f.is_file(): f.unlink()
    return Datenbank.neu(p, pw)

# 1 ---------------------------------------------------------------------------------------------
titel("1 Sperre: Passwortprüfung gegen ausgetauschte Datei")
db, _ = frisch("echt.nvdb", "Das echte Passwort 2026")
fremd, _ = frisch("fremd.nvdb", "Angreifer-Passwort 123")
fremd.schliessen()
print("vor Austausch  – fremdes Passwort gilt:", db.pruefe_passwort("Angreifer-Passwort 123"))
original = db.pfad.read_bytes()
db.pfad.write_bytes((ARBEIT / "fremd.nvdb").read_bytes())
print("nach Austausch – fremdes Passwort gilt:", db.pruefe_passwort("Angreifer-Passwort 123"))
print("nach Austausch – echtes Passwort gilt: ", db.pruefe_passwort("Das echte Passwort 2026"))
db.pfad.write_bytes(original)

# 2 ---------------------------------------------------------------------------------------------
titel("2 TEMP-Speicher von SQLite")
print("temp_store:", db.verbindung.execute("PRAGMA temp_store").fetchone()[0],
      "| Compile-Optionen:", [r[0] for r in db.verbindung.execute("PRAGMA compile_options") if "TEMP" in r[0]])
sd = Stammdaten(db.verbindung)
jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
def offene():
    erg = []
    for fd in os.listdir("/proc/self/fd"):
        try:
            z = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            continue
        if "etilqs" in z or "(deleted)" in z or z.startswith(("/tmp/", "/var/tmp/")):
            erg.append((fd, z, os.fstat(int(fd)).st_size))
    return erg
print("offene Temp-Dateien vorher:", offene())
for i in range(6000):
    s = sd.lege_schueler_an(jahr.id, f"Geheimname{i:05d}" + "x" * 200, "Vorname", "8.1")
db.verlauf.abschliessen()
gef = offene()
print("offene Temp-Dateien nach 6000 Einträgen:", gef)
for fd, z, n in gef:
    inhalt = os.pread(int(fd), n, 0)
    print("  Klartext-Name in der Temp-Datei gefunden:", b"Geheimname00001" in inhalt, "| Größe", n)

# 3 ---------------------------------------------------------------------------------------------
titel("3 Dateirechte (umask %03o)" % (os.umask(0o022) if False else (lambda m: (os.umask(m), m)[1])(os.umask(0))))
db.speichern()
kf = db.neue_schluesseldatei(ARBEIT / "ersatz")
for p in (db.pfad, kf, ARBEIT / "echt.nvdb.sperre"):
    print(f"  {p.name:22s} {stat.filemode(p.stat().st_mode)}")
from notenverwaltung.ausgabe import notfallblatt
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])
nf = notfallblatt.als_pdf(ARBEIT / "nf.pdf", "echt", "0123-4567-89AB-CDEF-GHJK-MNPQ")
print(f"  {nf.name:22s} {stat.filemode(nf.stat().st_mode)}")

# 5 ---------------------------------------------------------------------------------------------
titel("5 Sicherungen bei Namen mit [ ]")
d2, _ = frisch("Noten [2026].nvdb")
d2.setze_meta("x", "1"); d2._gesichert = False; d2.speichern()
print("Dateien im Sicherungsordner:", len(list((ARBEIT / "Noten [2026]-Sicherungen").glob("*"))),
      "| sicherungen() findet:", len(d2.sicherungen()))
ziel = ARBEIT / "stick"; ziel.mkdir(exist_ok=True)
import time
for i in range(3):
    sichere_nach(d2.pfad, ziel, 1); time.sleep(1.05)
print("zweiter Ort, Kopien behalten = 1, vorhanden:", len(list(ziel.glob("*.nvdb"))))
d2.schliessen()

# 4 ---------------------------------------------------------------------------------------------
titel("4 Veränderter Kopf")
daten = (ARBEIT / "fremd.nvdb").read_bytes()
kopf, zusatz, geheim = Tresor.lies_kopf(daten)
def mit(kopf_neu):
    kb = json.dumps(kopf_neu).encode("ascii")
    return struct.pack(">4sHI", b"NVDB", 1, len(kb)) + kb + geheim
import copy
faelle = {}
k = copy.deepcopy(kopf); k["zugaenge"] = ["x"]; faelle["Zugang ist kein Objekt"] = k
k = copy.deepcopy(kopf); k["zugaenge"][0]["salz"] = "QUJD"; faelle["Salz 3 Byte"] = k
k = copy.deepcopy(kopf); k["zugaenge"][0]["nonce"] = "QUJD"; faelle["Nonce 3 Byte"] = k
k = copy.deepcopy(kopf); k["daten"]["nonce"] = ""; faelle["Daten-Nonce leer"] = k
faelle["Kopf ist Liste"] = []
k = copy.deepcopy(kopf); k["kdf"]["speicher_kib"] = 4 * 1024 * 1024; k["kdf"]["iterationen"] = 50; faelle["KDF 4 GiB x 50 (nur Prüfung der Grenzen)"] = None
for name, k in faelle.items():
    if k is None: continue
    for fn, nm in ((lambda d: Tresor.oeffne(d, PASSWORT, "Angreifer-Passwort 123"), "oeffne"),
                   (Tresor.vorhandene_zugaenge, "vorhandene_zugaenge")):
        try:
            fn(mit(k)); print(f"  {name:28s} {nm}: keine Ausnahme")
        except Exception as e:
            print(f"  {name:28s} {nm}: {type(e).__name__}: {str(e)[:60]}")

# 8 ---------------------------------------------------------------------------------------------
titel("8 Abbruch während des Speicherns")
d3, _ = frisch("abbruch.nvdb")
Stammdaten(d3.verbindung).lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31))
d3.speichern()
vorher = d3.pfad.read_bytes()
import notenverwaltung.speicher.datenbank as D
echt_replace = os.replace
def kaputt(a, b): raise OSError("Platte voll (simuliert)")
D.os.replace = kaputt
Stammdaten(d3.verbindung).lege_schuljahr_an("2027/28", date(2027, 8, 1), date(2028, 2, 1), date(2028, 7, 31))
try:
    d3.speichern()
except OSError as e:
    print("Speichern meldet:", e)
D.os.replace = echt_replace
print("Original unverändert:", d3.pfad.read_bytes() == vorher, "| Reste:", sorted(p.name for p in ARBEIT.glob("abbruch*")))
# halb geschriebene .neu-Datei
(ARBEIT / "abbruch.nvdb.neu").write_bytes(b"NVDB halb")
d3.speichern()
print("nach erneutem Speichern lesbar:", bool(Tresor.oeffne(d3.pfad.read_bytes(), PASSWORT, "Erfundenes Passwort 1")))
d3.schliessen()
# abgeschnittene Datei
p = ARBEIT / "abbruch.nvdb"; roh = p.read_bytes(); p.write_bytes(roh[: len(roh) // 2])
try:
    Datenbank.oeffnen(p, PASSWORT, "Erfundenes Passwort 1")
except Exception as e:
    print("abgeschnittene Datei:", type(e).__name__, e)
p.write_bytes(b"")
try:
    Datenbank.oeffnen(p, PASSWORT, "Erfundenes Passwort 1")
except Exception as e:
    print("leere Datei:", type(e).__name__, e)
db.schliessen(speichern=False)
