"""Kryptografische Grundbausteine.

Aufbau (Umschlag-Verfahren):
- Die Notendaten werden mit einem zufälligen 256-Bit-Hauptschlüssel verschlüsselt (AES-256-GCM).
- Der Hauptschlüssel liegt mehrfach „verpackt“ in der Datei, jeweils mit einem anderen Zugang:
  Passwort, Wiederherstellungscode, optional Schlüsseldatei.
- Aus Passwort und Wiederherstellungscode wird der Verpackungsschlüssel mit Argon2id abgeleitet,
  aus einer Schlüsseldatei mit HKDF-SHA256 (die Datei enthält selbst schon 256 Zufallsbits).

Ein Passwortwechsel verpackt nur den Hauptschlüssel neu – die Daten selbst bleiben unverändert verschlüsselt.
"""

from __future__ import annotations

import os
import secrets
import unicodedata
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SCHLUESSEL_LAENGE = 32
NONCE_LAENGE = 12
SALZ_LAENGE = 16


class EntschluesselungsFehler(Exception):
    """Falscher Schlüssel oder veränderte Daten – beides ist bei AES-GCM nicht unterscheidbar."""


@dataclass(frozen=True)
class KdfParameter:
    """Argon2id-Kosten. Standard: 64 MiB, 3 Durchläufe, 4 Spuren (≈ 0,3 s auf einem Laptop)."""

    iterationen: int = 3
    spuren: int = 4
    speicher_kib: int = 64 * 1024

    def als_dict(self) -> dict:
        return {"name": "argon2id", "iterationen": self.iterationen, "spuren": self.spuren,
                "speicher_kib": self.speicher_kib}

    @staticmethod
    def aus_dict(d: dict) -> "KdfParameter":
        if d.get("name") != "argon2id":
            raise ValueError(f"Unbekanntes Schlüsselverfahren: {d.get('name')!r}")
        p = KdfParameter(int(d["iterationen"]), int(d["spuren"]), int(d["speicher_kib"]))
        # Schutz vor manipulierten Köpfen, die den Rechner lahmlegen sollen
        if not (1 <= p.iterationen <= 50 and 1 <= p.spuren <= 64 and 8 * p.spuren <= p.speicher_kib <= 4 * 1024 * 1024):
            raise ValueError("Unplausible Schlüsselparameter in der Datei")
        return p


def zufall(n: int) -> bytes:
    return os.urandom(n)


def neuer_hauptschluessel() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def normalisiere_passwort(passwort: str) -> bytes:
    """Unicode-Normalform NFC, damit „ü“ auf Linux und Windows gleich kodiert ist."""
    return unicodedata.normalize("NFC", passwort).encode("utf-8")


def schluessel_aus_geheimnis(geheimnis: bytes, salz: bytes, parameter: KdfParameter) -> bytes:
    return Argon2id(
        salt=salz,
        length=SCHLUESSEL_LAENGE,
        iterations=parameter.iterationen,
        lanes=parameter.spuren,
        memory_cost=parameter.speicher_kib,
    ).derive(geheimnis)


def schluessel_aus_schluesseldatei(inhalt: bytes, salz: bytes) -> bytes:
    if len(inhalt) < 32:
        raise EntschluesselungsFehler("Schlüsseldatei ist zu kurz")
    return HKDF(algorithm=hashes.SHA256(), length=SCHLUESSEL_LAENGE, salt=salz,
                info=b"notenverwaltung-schluesseldatei").derive(inhalt)


def verschluesseln(schluessel: bytes, nonce: bytes, klartext: bytes, zusatzdaten: bytes) -> bytes:
    """AES-256-GCM. Die Zusatzdaten werden mit geschützt, aber nicht verschlüsselt.
    Die Nonce muss für jeden Aufruf mit demselben Schlüssel neu zufällig sein (zufall(NONCE_LAENGE))."""
    return AESGCM(schluessel).encrypt(nonce, klartext, zusatzdaten)


def entschluesseln(schluessel: bytes, nonce: bytes, geheimtext: bytes, zusatzdaten: bytes) -> bytes:
    try:
        return AESGCM(schluessel).decrypt(nonce, geheimtext, zusatzdaten)
    except InvalidTag as e:
        raise EntschluesselungsFehler("Schlüssel falsch oder Daten verändert") from e


# ---- Wiederherstellungscode -------------------------------------------------------------------
# Crockford-Base32: keine leicht verwechselbaren Zeichen (kein I, L, O, U). Beim Eintippen werden
# O→0 und I/L→1 umgedeutet, Leerzeichen und Bindestriche ignoriert. 24 Zeichen = 120 Bit Zufall.

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LAENGE = 24
_UMDEUTUNG = {"O": "0", "I": "1", "L": "1", "U": "V"}


def neuer_wiederherstellungscode() -> str:
    roh = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LAENGE))
    return formatiere_code(roh)


def formatiere_code(code: str) -> str:
    roh = normalisiere_code(code)
    return "-".join(roh[i:i + 4] for i in range(0, len(roh), 4))


def normalisiere_code(eingabe: str) -> str:
    """Macht aus einer Benutzereingabe die kanonische Form oder wirft ValueError."""
    zeichen = []
    for z in eingabe.upper():
        if z in " -\t\n":
            continue
        z = _UMDEUTUNG.get(z, z)
        if z not in ALPHABET:
            raise ValueError(f"Ungültiges Zeichen im Code: {z!r}")
        zeichen.append(z)
    if len(zeichen) != CODE_LAENGE:
        raise ValueError(f"Der Code hat {CODE_LAENGE} Zeichen, eingegeben wurden {len(zeichen)}.")
    return "".join(zeichen)
