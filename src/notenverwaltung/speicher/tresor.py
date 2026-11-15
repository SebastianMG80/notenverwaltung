"""Dateiformat der Notenverwaltung (Version 1).

Aufbau einer .nvdb-Datei (alle Zahlen big-endian):

    4 Byte   Kennung  b"NVDB"
    2 Byte   Formatversion (1)
    4 Byte   Länge L des Kopfes
    L Byte   Kopf als UTF-8-JSON (lesbar, unverschlüsselt, aber durch AES-GCM gegen Veränderung geschützt)
    Rest     AES-256-GCM-Geheimtext der zlib-gepackten SQLite-Datenbank

Der Kopf enthält nur, was zum Entsperren nötig ist (Salze, Nonces, verpackte Hauptschlüssel,
Argon2id-Parameter) – keine Namen, keine Noten. Weil das Format byte-genau festgelegt ist und
nur plattformunabhängige Bausteine nutzt, ist eine Datei unter Linux und Windows identisch lesbar.
"""

from __future__ import annotations

import base64
import hmac
import json
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from notenverwaltung import __version__
from notenverwaltung.speicher import krypto
from notenverwaltung.speicher.krypto import EntschluesselungsFehler, KdfParameter

KENNUNG = b"NVDB"
FORMAT_VERSION = 1
_PRAEFIX = struct.Struct(">4sHI")
MAX_KOPF = 1024 * 1024

PASSWORT = "passwort"
WIEDERHERSTELLUNG = "wiederherstellung"
SCHLUESSELDATEI = "schluesseldatei"
ARTEN = (PASSWORT, WIEDERHERSTELLUNG, SCHLUESSELDATEI)

STANDARD_KDF = KdfParameter()  # Tests setzen hier schnellere Werte ein


class FormatFehler(Exception):
    """Die Datei ist keine (lesbare) Notenverwaltungs-Datenbank."""


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _unb64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"), validate=True)


@dataclass
class Zugang:
    art: str
    salz: bytes
    nonce: bytes
    verpackt: bytes

    def als_dict(self) -> dict:
        return {"art": self.art, "salz": _b64(self.salz), "nonce": _b64(self.nonce), "verpackt": _b64(self.verpackt)}

    @staticmethod
    def aus_dict(d: dict) -> "Zugang":
        if not isinstance(d, dict):
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        if d.get("art") not in ARTEN:
            raise FormatFehler(f"Unbekannte Zugangsart {d.get('art')!r}")
        z = Zugang(d["art"], _unb64(d["salz"]), _unb64(d["nonce"]), _unb64(d["verpackt"]))
        # Feste Längen: Ein veränderter Kopf soll als „beschädigt“ gemeldet werden, nicht als Programmfehler
        if (len(z.salz) != krypto.SALZ_LAENGE or len(z.nonce) != krypto.NONCE_LAENGE
                or len(z.verpackt) != krypto.SCHLUESSEL_LAENGE + 16):
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        return z


def _verpackungs_ad(art: str, salz: bytes) -> bytes:
    return KENNUNG + b"|zugang|" + art.encode("ascii") + b"|" + salz


def _verpackungsschluessel(art: str, geheimnis: bytes, salz: bytes, kdf: KdfParameter) -> bytes:
    if art == SCHLUESSELDATEI:
        return krypto.schluessel_aus_schluesseldatei(geheimnis, salz)
    return krypto.schluessel_aus_geheimnis(geheimnis, salz, kdf)


def _geheimnis(art: str, wert: str | bytes) -> bytes:
    if art == PASSWORT:
        return krypto.normalisiere_passwort(wert)
    if art == WIEDERHERSTELLUNG:
        return krypto.normalisiere_code(wert).encode("ascii")
    return bytes(wert)


@dataclass
class Tresor:
    """Hält den Hauptschlüssel einer geöffneten Datenbank und ihre Zugänge."""

    hauptschluessel: bytes
    kdf: KdfParameter = field(default_factory=KdfParameter)
    zugaenge: dict[str, Zugang] = field(default_factory=dict)

    # ---- Anlegen ---------------------------------------------------------------------------
    @staticmethod
    def neu(passwort: str, kdf: KdfParameter | None = None) -> tuple["Tresor", str]:
        """Neuer Tresor mit Passwort und Wiederherstellungscode. Gibt den Code zurück (nur einmal sichtbar!)."""
        t = Tresor(krypto.neuer_hauptschluessel(), kdf or STANDARD_KDF)
        t.setze_passwort(passwort)
        code = t.neuer_wiederherstellungscode()
        return t, code

    def _setze_zugang(self, art: str, wert: str | bytes) -> None:
        salz = krypto.zufall(krypto.SALZ_LAENGE)
        schluessel = _verpackungsschluessel(art, _geheimnis(art, wert), salz, self.kdf)
        nonce = krypto.zufall(krypto.NONCE_LAENGE)
        verpackt = krypto.verschluesseln(schluessel, nonce, self.hauptschluessel, _verpackungs_ad(art, salz))
        self.zugaenge[art] = Zugang(art, salz, nonce, verpackt)

    def setze_passwort(self, passwort: str) -> None:
        if not passwort:
            raise ValueError("Das Passwort darf nicht leer sein.")
        self._setze_zugang(PASSWORT, passwort)

    def neuer_wiederherstellungscode(self) -> str:
        """Erzeugt einen neuen Code; der bisherige wird damit ungültig."""
        code = krypto.neuer_wiederherstellungscode()
        self._setze_zugang(WIEDERHERSTELLUNG, code)
        return code

    def neue_schluesseldatei(self) -> bytes:
        """Erzeugt den Inhalt einer neuen Schlüsseldatei; eine bisherige wird ungültig."""
        inhalt = b"NVKEY1\n" + krypto.zufall(64)
        self._setze_zugang(SCHLUESSELDATEI, inhalt)
        return inhalt

    def entferne_schluesseldatei(self) -> None:
        self.zugaenge.pop(SCHLUESSELDATEI, None)

    @property
    def hat_schluesseldatei(self) -> bool:
        return SCHLUESSELDATEI in self.zugaenge

    # ---- Schreiben -------------------------------------------------------------------------
    def verpacke(self, klartext: bytes) -> bytes:
        """Erzeugt den kompletten Dateiinhalt für die übergebenen Datenbank-Bytes."""
        if PASSWORT not in self.zugaenge or WIEDERHERSTELLUNG not in self.zugaenge:
            raise ValueError("Passwort und Wiederherstellungscode müssen gesetzt sein.")
        nonce = krypto.zufall(krypto.NONCE_LAENGE)
        kopf = {
            "format": FORMAT_VERSION,
            "programm": __version__,
            "gespeichert": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kdf": self.kdf.als_dict(),
            "zugaenge": [self.zugaenge[a].als_dict() for a in ARTEN if a in self.zugaenge],
            "daten": {"nonce": _b64(nonce), "packung": "zlib"},
        }
        kopf_bytes = json.dumps(kopf, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")
        praefix = _PRAEFIX.pack(KENNUNG, FORMAT_VERSION, len(kopf_bytes))
        geheim = krypto.verschluesseln(self.hauptschluessel, nonce, zlib.compress(klartext, 6), praefix + kopf_bytes)
        return praefix + kopf_bytes + geheim

    # ---- Lesen -----------------------------------------------------------------------------
    @staticmethod
    def lies_kopf(daten: bytes) -> tuple[dict, bytes, bytes]:
        """Gibt (kopf, zusatzdaten, geheimtext) zurück, ohne zu entschlüsseln."""
        if len(daten) < _PRAEFIX.size or daten[:4] != KENNUNG:
            raise FormatFehler("Das ist keine Datenbank der Notenverwaltung.")
        _, version, laenge = _PRAEFIX.unpack_from(daten)
        if version > FORMAT_VERSION:
            raise FormatFehler(
                f"Die Datenbank stammt aus einer neueren Programmversion (Format {version}). "
                "Bitte das Programm aktualisieren."
            )
        if version < 1 or laenge > MAX_KOPF or _PRAEFIX.size + laenge > len(daten):
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        kopf_bytes = daten[_PRAEFIX.size:_PRAEFIX.size + laenge]
        try:
            kopf = json.loads(kopf_bytes.decode("ascii"))
        except (UnicodeDecodeError, ValueError, RecursionError) as e:
            raise FormatFehler("Die Datei ist beschädigt (Kopf).") from e
        if not isinstance(kopf, dict):
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        return kopf, daten[:_PRAEFIX.size + laenge], daten[_PRAEFIX.size + laenge:]

    def entpacke_eigene(self, daten: bytes) -> bytes:
        """Entschlüsselt eine Datei (z. B. eine Sicherung) direkt mit dem eigenen Hauptschlüssel."""
        kopf, zusatz, geheim = Tresor.lies_kopf(daten)
        try:
            nonce = _unb64(kopf["daten"]["nonce"])
        except (KeyError, TypeError, ValueError) as e:
            raise FormatFehler("Die Datei ist beschädigt (Kopf).") from e
        if len(nonce) != krypto.NONCE_LAENGE:
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        try:
            return zlib.decompress(krypto.entschluesseln(self.hauptschluessel, nonce, geheim, zusatz))
        except zlib.error as e:
            raise FormatFehler("Die Datei ist beschädigt (Daten).") from e

    @staticmethod
    def vorhandene_zugaenge(daten: bytes) -> list[str]:
        kopf, _, _ = Tresor.lies_kopf(daten)
        zugaenge = kopf.get("zugaenge", [])
        if not isinstance(zugaenge, list):
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")
        return [z.get("art") for z in zugaenge if isinstance(z, dict)]

    def pruefe_zugang(self, art: str, wert: str | bytes) -> bool:
        """Passt dieser Zugang (z. B. das Passwort) zum geöffneten Tresor?

        Geprüft wird gegen den Zugang im Arbeitsspeicher – nicht gegen die Datei auf der Platte. Sonst könnte
        jemand die Datei gegen eine eigene austauschen und die Sperre mit dem eigenen Passwort aufheben.
        """
        zugang = self.zugaenge.get(art)
        if zugang is None:
            return False
        try:
            schluessel = _verpackungsschluessel(art, _geheimnis(art, wert), zugang.salz, self.kdf)
            entpackt = krypto.entschluesseln(schluessel, zugang.nonce, zugang.verpackt,
                                             _verpackungs_ad(art, zugang.salz))
        except (EntschluesselungsFehler, ValueError, TypeError):
            return False
        return hmac.compare_digest(entpackt, self.hauptschluessel)

    @staticmethod
    def oeffne(daten: bytes, art: str, wert: str | bytes) -> tuple["Tresor", bytes]:
        """Entsperrt mit Passwort, Wiederherstellungscode oder Schlüsseldatei-Inhalt.

        Gibt (tresor, datenbank_bytes) zurück. Wirft EntschluesselungsFehler bei falschem Zugang.
        """
        kopf, zusatz, geheim = Tresor.lies_kopf(daten)
        try:
            kdf = KdfParameter.aus_dict(kopf["kdf"])
            zugaenge = {z.art: z for z in map(Zugang.aus_dict, kopf["zugaenge"])}
            nonce = _unb64(kopf["daten"]["nonce"])
            if kopf["daten"].get("packung") != "zlib":
                raise FormatFehler("Unbekannte Packung der Daten.")
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            raise FormatFehler("Die Datei ist beschädigt (Kopf).") from e
        if len(nonce) != krypto.NONCE_LAENGE:
            raise FormatFehler("Die Datei ist beschädigt (Kopf).")

        zugang = zugaenge.get(art)
        if zugang is None:
            raise EntschluesselungsFehler("Für diese Datenbank gibt es keinen solchen Zugang.")
        try:
            geheimnis = _geheimnis(art, wert)
        except ValueError as e:
            raise EntschluesselungsFehler(str(e)) from e
        schluessel = _verpackungsschluessel(art, geheimnis, zugang.salz, kdf)
        hauptschluessel = krypto.entschluesseln(schluessel, zugang.nonce, zugang.verpackt,
                                                _verpackungs_ad(art, zugang.salz))
        try:
            gepackt = krypto.entschluesseln(hauptschluessel, nonce, geheim, zusatz)
        except EntschluesselungsFehler as e:
            # Zugang war richtig, aber die Daten passen nicht: Datei verändert oder beschädigt
            raise FormatFehler("Die Datei ist beschädigt oder wurde verändert.") from e
        try:
            klartext = zlib.decompress(gepackt)
        except zlib.error as e:
            raise FormatFehler("Die Datei ist beschädigt (Daten).") from e
        return Tresor(hauptschluessel, kdf, zugaenge), klartext
