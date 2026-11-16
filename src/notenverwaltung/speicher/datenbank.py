"""Geöffnete Datenbank: SQLite im Arbeitsspeicher, verschlüsselt auf der Platte.

- Beim Öffnen wird die Datei entschlüsselt und als SQLite-Datenbank im Speicher geladen.
  Unverschlüsselte Daten berühren nie die Festplatte.
- Speichern schreibt zuerst eine Zwischendatei, prüft sie und ersetzt dann das Original (atomar).
- Vor dem ersten Speichern einer Sitzung wird der bisherige Stand als Sicherung abgelegt.
- Eine Sperrdatei warnt, wenn dieselbe Datenbank schon (auf einem anderen Rechner) geöffnet ist.
"""

from __future__ import annotations

import glob
import json
import os
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSysInfo

from notenverwaltung import __version__
from notenverwaltung.speicher import schema
from notenverwaltung.speicher.krypto import KdfParameter
from notenverwaltung.speicher.tresor import PASSWORT, FormatFehler, Tresor
from notenverwaltung.speicher.verlauf import Verlauf

ENDUNG = ".nvdb"
SCHLUESSELDATEI_ENDUNG = ".nvkey"
MAX_SICHERUNGEN = 20
DAUERHAFT = "_vor-Umstellung"   # Namensteil dauerhafter Sicherungen


class GesperrtFehler(Exception):
    """Die Datenbank ist laut Sperrdatei bereits geöffnet."""

    def __init__(self, info: "SperrInfo") -> None:
        super().__init__(f"Die Datenbank ist bereits geöffnet auf „{info.rechner}“ seit {info.seit}.")
        self.info = info


@dataclass
class SperrInfo:
    rechner: str
    pid: int
    seit: str


def sperrdatei(pfad: Path) -> Path:
    return pfad.with_name(pfad.name + ".sperre")


def sicherungsordner(pfad: Path) -> Path:
    return pfad.with_name(pfad.stem + "-Sicherungen")


def _rechnername() -> str:
    return QSysInfo.machineHostName() or "unbekannt"


def _prozess_laeuft(pid: int) -> bool:
    if sys.platform.startswith("win"):
        return True  # unter Windows nicht gefahrlos prüfbar → im Zweifel nachfragen
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lies_sperre(pfad: Path) -> SperrInfo | None:
    try:
        d = json.loads(sperrdatei(pfad).read_text(encoding="utf-8"))
        return SperrInfo(str(d["rechner"]), int(d["pid"]), str(d["seit"]))
    except FileNotFoundError:
        return None
    except (ValueError, KeyError, TypeError, OSError):
        return SperrInfo("unbekannt", -1, "unbekannt")


def _sperre_ist_verwaist(info: SperrInfo) -> bool:
    return info.rechner == _rechnername() and (info.pid == os.getpid() or not _prozess_laeuft(info.pid))


def nur_eigentuemer(pfad: Path, ordner: bool = False) -> None:
    """Beschränkt die Dateirechte auf den eigenen Benutzer (Linux/macOS: 600 bzw. 700 für Ordner).

    Unter Windows regeln das die Rechte des Benutzerordners; dort bewirkt der Aufruf nichts Schädliches.
    Fehler (z. B. FAT-Stick ohne Dateirechte) werden übergangen – die Datei selbst ist ohnehin verschlüsselt.
    """
    if os.name != "posix":
        return
    try:
        os.chmod(pfad, 0o700 if ordner else 0o600)
    except OSError:
        pass


def _schreibe_atomar(ziel: Path, daten: bytes) -> None:
    zwischen = ziel.with_name(ziel.name + ".neu")
    # Von Anfang an nur für den eigenen Benutzer lesbar (wichtig für Schlüsseldateien); eine liegengebliebene
    # Zwischendatei wird ersetzt, nicht weiterbeschrieben
    fd = os.open(zwischen, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        nur_eigentuemer(zwischen)
        f.write(daten)
        f.flush()
        os.fsync(f.fileno())
    for versuch in range(10):  # Windows: Virenscanner hält Dateien gelegentlich kurz fest
        try:
            os.replace(zwischen, ziel)
            break
        except PermissionError:
            if versuch == 9:
                raise
            time.sleep(0.2)
    if hasattr(os, "O_DIRECTORY"):
        fd = os.open(ziel.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def sichere_nach(pfad: Path, ordner: Path, anzahl: int = 10) -> Path:
    """Legt eine Kopie der (verschlüsselten) Datenbankdatei mit Zeitstempel in `ordner` ab, z. B. auf einem
    USB-Stick, und behält dort die neuesten `anzahl` Kopien dieser Datenbank. Die Schlüsseldatei wird nie
    mitkopiert. Wirft OSError, wenn der Ordner nicht erreichbar ist (Stick nicht eingesteckt)."""
    pfad, ordner = Path(pfad), Path(ordner)
    if not ordner.is_dir():
        raise OSError(f"Der Ordner „{ordner}“ ist nicht erreichbar.")
    if ordner.resolve() == pfad.parent.resolve():
        raise OSError("Der zweite Sicherungsort darf nicht der Ordner der Datenbank sein.")
    stempel = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ziel = ordner / f"{pfad.stem}_{stempel}{ENDUNG}"
    teil = ziel.with_name(ziel.name + ".teil")
    shutil.copyfile(pfad, teil)
    nur_eigentuemer(teil)
    os.replace(teil, ziel)
    # glob.escape: Namen wie „Noten [2026]“ enthalten Zeichen, die sonst als Muster gelten würden
    alte = sorted(ordner.glob(f"{glob.escape(pfad.stem)}_????-??-??_??-??-??{ENDUNG}"), reverse=True)
    for alt in alte[max(1, anzahl):]:
        alt.unlink(missing_ok=True)
    return ziel


def cloud_hinweis(pfad: Path) -> str | None:
    """Erkennt typische synchronisierte Ordner. Gibt einen Warntext zurück oder None."""
    namen = ("cloud", "nextcloud", "owncloud", "dropbox", "onedrive", "google drive", "googledrive",
             "pcloud", "mega", "icloud", "seafile", "magentacloud", "hidrive", "tresorit", "sync")
    marker = (".nextcloudsync.log", ".owncloudsync.log", ".dropbox", ".dropbox.cache")
    p = Path(pfad).expanduser().resolve()
    for teil in p.parent.parts:
        klein = teil.lower()
        if any(klein == n or klein.startswith(n + " ") or klein.startswith(n + "-") or klein.endswith(" " + n)
               for n in namen):
            return (f"Der Ordner „{teil}“ sieht nach einem synchronisierten Cloud-Ordner aus. "
                    "Die Datenbank ist zwar verschlüsselt, würde damit aber den Rechner verlassen.")
    for ordner in [p.parent, *p.parent.parents]:
        for m in marker:
            if (ordner / m).exists():
                return (f"Im Ordner „{ordner}“ arbeitet ein Synchronisationsprogramm. "
                        "Die Datenbank ist zwar verschlüsselt, würde damit aber den Rechner verlassen.")
        if ordner.name.startswith(".sync_") or any(ordner.glob(".sync_*.db")):
            return (f"Im Ordner „{ordner}“ arbeitet ein Synchronisationsprogramm. "
                    "Die Datenbank ist zwar verschlüsselt, würde damit aber den Rechner verlassen.")
    return None


@dataclass(frozen=True)
class Passwortwechsel:
    code: str                          # neuer Wiederherstellungscode – sofort neues Notfallblatt!
    schluesseldatei_verfallen: bool
    nicht_umgestellt: list[str]        # Sicherungen, die sich nicht umstellen ließen (z. B. Stick fehlt)


class Datenbank:
    def __init__(self, pfad: Path, tresor: Tresor, verbindung: sqlite3.Connection) -> None:
        self.pfad = Path(pfad)
        self.tresor = tresor
        self.verbindung = verbindung
        self._gespeicherte_aenderungen = verbindung.total_changes
        self._tresor_geaendert = False
        self._gesichert = False
        self._sperre_gesetzt = False
        self.verlauf = Verlauf(verbindung)      # Rückgängig / Wiederholen (nur im Arbeitsspeicher)

    # ---- Anlegen / Öffnen --------------------------------------------------------------------
    @classmethod
    def neu(cls, pfad: Path, passwort: str, kdf: KdfParameter | None = None) -> tuple["Datenbank", str]:
        """Legt eine neue Datenbank an und speichert sie sofort. Gibt (datenbank, wiederherstellungscode) zurück."""
        pfad = Path(pfad)
        if pfad.suffix.lower() != ENDUNG:
            pfad = pfad.with_name(pfad.name + ENDUNG)
        if pfad.exists():
            raise FileExistsError(f"Die Datei „{pfad.name}“ gibt es schon.")
        tresor, code = Tresor.neu(passwort, kdf)
        verbindung = cls._neue_verbindung()
        schema.migriere(verbindung)
        with verbindung:
            verbindung.executemany(
                "INSERT INTO meta (schluessel, wert) VALUES (?, ?)",
                [("erstellt", datetime.now().isoformat(timespec="seconds")),
                 ("erstellt_mit", __version__)],
            )
        db = cls(pfad, tresor, verbindung)
        db._sperren()
        db._gesichert = True  # es gibt noch nichts zu sichern
        db.speichern()
        return db, code

    @classmethod
    def oeffnen(cls, pfad: Path, art: str, wert: str | bytes, sperre_ignorieren: bool = False) -> "Datenbank":
        pfad = Path(pfad)
        daten = pfad.read_bytes()
        info = lies_sperre(pfad)
        if info is not None and not sperre_ignorieren and not _sperre_ist_verwaist(info):
            # Erst Zugang prüfen, damit Fremde nicht einmal den Rechnernamen erfahren
            Tresor.oeffne(daten, art, wert)
            raise GesperrtFehler(info)
        tresor, klartext = Tresor.oeffne(daten, art, wert)
        verbindung = cls._neue_verbindung()
        try:
            verbindung.deserialize(klartext)
        except sqlite3.DatabaseError as e:
            raise FormatFehler("Die Datenbank im Inneren der Datei ist beschädigt.") from e
        cls._pruefe_integritaet(verbindung)
        verbindung.execute("PRAGMA foreign_keys = ON")
        stand = schema.schema_version(verbindung)
        migriert = schema.migriere(verbindung)
        db = cls(pfad, tresor, verbindung)
        db._sperren()
        if migriert:
            # Die Datei im alten Format bleibt als eigene, dauerhafte Sicherung erhalten
            db._sichern(f"_vor-Umstellung-Format-{stand}-auf-{schema.SCHEMA_VERSION}")
            db._tresor_geaendert = True  # Schema-Anhebung soll gespeichert werden
        return db

    @staticmethod
    def _neue_verbindung() -> sqlite3.Connection:
        v = sqlite3.connect(":memory:", check_same_thread=False)
        v.execute("PRAGMA foreign_keys = ON")
        # Zwischenspeicher (Rückgängig-Protokoll, große Sortierungen) nie als Datei im Temp-Ordner anlegen:
        # Dort stünden sonst Namen, Noten und Rückmeldungen unverschlüsselt auf der Platte.
        v.execute("PRAGMA temp_store = MEMORY")
        return v

    @staticmethod
    def _pruefe_integritaet(verbindung: sqlite3.Connection) -> None:
        try:
            ergebnis = verbindung.execute("PRAGMA integrity_check").fetchone()[0]
        except sqlite3.DatabaseError as e:
            raise FormatFehler("Die Datenbank im Inneren der Datei ist beschädigt.") from e
        if ergebnis != "ok":
            raise FormatFehler(f"Die Datenbank im Inneren der Datei ist beschädigt ({ergebnis}).")

    # ---- Zustand -----------------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self.pfad.stem

    @property
    def geaendert(self) -> bool:
        return self._tresor_geaendert or self.verbindung.total_changes != self._gespeicherte_aenderungen

    # ---- Speichern ---------------------------------------------------------------------------
    def speichern(self) -> None:
        if self.verbindung.in_transaction:
            self.verbindung.commit()
        if not self._gesichert:
            self._sichern()
        daten = self.tresor.verpacke(self.verbindung.serialize())
        self.tresor.entpacke_eigene(daten)  # Probe: lässt sich das Geschriebene wieder lesen?
        _schreibe_atomar(self.pfad, daten)
        self._gespeicherte_aenderungen = self.verbindung.total_changes
        self._tresor_geaendert = False

    def _sichern(self, zusatz: str = "") -> None:
        """Kopiert die Datei (wie sie auf der Platte liegt) in den Sicherungsordner.

        Mit `zusatz` (z. B. vor einer Format-Umstellung) ist die Sicherung dauerhaft: Sie zählt nicht
        zu den höchstens MAX_SICHERUNGEN gewöhnlichen Sicherungen und wird nie automatisch gelöscht.
        """
        if self.pfad.exists():
            ordner = sicherungsordner(self.pfad)
            if not ordner.is_dir():
                ordner.mkdir()
                nur_eigentuemer(ordner, ordner=True)
            stempel = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            kopie = ordner / f"{self.pfad.stem}_{stempel}{zusatz}{ENDUNG}"
            shutil.copy2(self.pfad, kopie)
            nur_eigentuemer(kopie)
            gewoehnlich = [s for s in self.sicherungen() if DAUERHAFT not in s.name]
            for alt in gewoehnlich[MAX_SICHERUNGEN:]:
                alt.unlink(missing_ok=True)
        self._gesichert = True

    def sicherungen(self) -> list[Path]:
        """Sicherungen dieser Datenbank, neueste zuerst."""
        ordner = sicherungsordner(self.pfad)
        if not ordner.is_dir():
            return []
        return sorted(ordner.glob(f"{glob.escape(self.pfad.stem)}_*{ENDUNG}"), reverse=True)

    def _sicherungen_neu_verpacken(self) -> None:
        """Nach Änderung der Zugänge: Sicherungen auf die neuen Zugänge umstellen.

        Sonst ließe sich eine alte Sicherung weiter mit dem alten Passwort öffnen.
        """
        for datei in self.sicherungen():
            try:
                klartext = self.tresor.entpacke_eigene(datei.read_bytes())
            except Exception:  # fremde oder beschädigte Datei – nicht anfassen
                continue
            _schreibe_atomar(datei, self.tresor.verpacke(klartext))

    # ---- Zugänge ändern ----------------------------------------------------------------------
    def aendere_passwort(self, neues_passwort: str, weitere_ordner: list[Path] | tuple = ()) -> "Passwortwechsel":
        """Neues Passwort mit neuem Hauptschlüssel (Prüfbericht O1).

        Danach gilt ein neuer Wiederherstellungscode (neues Notfallblatt!), eine Schlüsseldatei verfällt.
        Alle Sicherungen – im Sicherungsordner und in `weitere_ordner` (zweiter Sicherungsort) – werden auf den
        neuen Schlüssel umgestellt; alte Kopien öffnen sich also nicht mehr mit dem alten Passwort. Klappt das
        Speichern nicht, bleibt alles beim Alten (alter Schlüssel, altes Passwort).
        """
        alt = self.tresor.kopie()
        hatte_datei = alt.hat_schluesseldatei
        code = self.tresor.erneuere(neues_passwort)
        try:
            self._tresor_geaendert = True
            self.speichern()
        except BaseException:
            self.tresor = alt
            raise
        nicht = self._sicherungen_umschluesseln(alt, [Path(o) for o in weitere_ordner if o])
        return Passwortwechsel(code, hatte_datei, nicht)

    def _sicherungen_umschluesseln(self, alt: Tresor, weitere_ordner: list[Path]) -> list[str]:
        """Sicherungen vom alten auf den neuen Hauptschlüssel umstellen. Gibt zurück, was nicht ging."""
        dateien = list(self.sicherungen())
        nicht: list[str] = []
        for ordner in weitere_ordner:
            if not ordner.is_dir():
                nicht.append(f"{ordner} (nicht erreichbar)")
                continue
            dateien += [p for p in ordner.glob(f"{glob.escape(self.pfad.stem)}_????-??-??_??-??-??{ENDUNG}")]
        for datei in dateien:
            try:
                daten = datei.read_bytes()
            except OSError:
                nicht.append(str(datei))
                continue
            try:
                klartext = alt.entpacke_eigene(daten)
            except Exception:  # schon umgestellt, fremd oder beschädigt – nicht anfassen
                continue
            try:
                _schreibe_atomar(datei, self.tresor.verpacke(klartext))
            except OSError:
                nicht.append(str(datei))
        return nicht

    def neuer_wiederherstellungscode(self) -> str:
        code = self.tresor.neuer_wiederherstellungscode()
        self._zugaenge_geaendert()
        return code

    def neue_schluesseldatei(self, ziel: Path) -> Path:
        ziel = Path(ziel)
        if ziel.suffix.lower() != SCHLUESSELDATEI_ENDUNG:
            ziel = ziel.with_name(ziel.name + SCHLUESSELDATEI_ENDUNG)
        inhalt = self.tresor.neue_schluesseldatei()
        _schreibe_atomar(ziel, inhalt)
        self._zugaenge_geaendert()
        return ziel

    def entferne_schluesseldatei(self) -> None:
        self.tresor.entferne_schluesseldatei()
        self._zugaenge_geaendert()

    def _zugaenge_geaendert(self) -> None:
        self._tresor_geaendert = True
        self.speichern()
        self._sicherungen_neu_verpacken()

    def pruefe_passwort(self, passwort: str) -> bool:
        """Prüft das aktuelle Passwort (z. B. vor einem Passwortwechsel oder zum Entsperren).

        Maßgeblich ist der geöffnete Tresor im Arbeitsspeicher, nicht die Datei auf der Platte: Die könnte
        inzwischen jemand gegen eine eigene Datenbank mit eigenem Passwort ausgetauscht haben.
        """
        return self.tresor.pruefe_zugang(PASSWORT, passwort)

    # ---- Sperre / Schließen ------------------------------------------------------------------
    def _sperren(self) -> None:
        inhalt = {"rechner": _rechnername(), "pid": os.getpid(),
                  "seit": datetime.now().strftime("%d.%m.%Y %H:%M")}
        try:
            sperrdatei(self.pfad).write_text(json.dumps(inhalt), encoding="utf-8")
            nur_eigentuemer(sperrdatei(self.pfad))
            self._sperre_gesetzt = True
        except OSError:
            self._sperre_gesetzt = False  # z. B. schreibgeschützter Stick – Öffnen trotzdem erlauben

    def schliessen(self, speichern: bool = True) -> None:
        if speichern and self.geaendert:
            self.speichern()
        self.verbindung.close()
        if self._sperre_gesetzt:
            info = lies_sperre(self.pfad)
            if info and info.rechner == _rechnername() and info.pid == os.getpid():
                sperrdatei(self.pfad).unlink(missing_ok=True)
            self._sperre_gesetzt = False

    # ---- Metadaten ---------------------------------------------------------------------------
    def meta(self, schluessel: str, standard: str | None = None) -> str | None:
        zeile = self.verbindung.execute("SELECT wert FROM meta WHERE schluessel = ?", (schluessel,)).fetchone()
        return zeile[0] if zeile else standard

    def setze_meta(self, schluessel: str, wert: str) -> None:
        with self.verbindung:
            self.verbindung.execute(
                "INSERT INTO meta (schluessel, wert) VALUES (?, ?) "
                "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
                (schluessel, wert),
            )
