"""Datenbankschema mit fortlaufenden Migrationen.

Jede Migration hebt `PRAGMA user_version` um eins. Neue Etappen hängen hier nur an,
bereits ausgelieferte Migrationen werden nie verändert.
"""

from __future__ import annotations

import sqlite3

MIGRATIONEN: list[str] = [
    # 1 – Grundlage: Metadaten der Datenbank
    """
    CREATE TABLE meta (
        schluessel TEXT PRIMARY KEY,
        wert       TEXT NOT NULL
    );
    """,
]

SCHEMA_VERSION = len(MIGRATIONEN)


class SchemaFehler(Exception):
    pass


def schema_version(verbindung: sqlite3.Connection) -> int:
    return verbindung.execute("PRAGMA user_version").fetchone()[0]


def migriere(verbindung: sqlite3.Connection) -> int:
    """Bringt die Datenbank auf den aktuellen Stand. Gibt die Anzahl ausgeführter Migrationen zurück."""
    stand = schema_version(verbindung)
    if stand > SCHEMA_VERSION:
        raise SchemaFehler(
            f"Die Datenbank wurde mit einer neueren Programmversion bearbeitet (Schema {stand}). "
            "Bitte das Programm aktualisieren."
        )
    for nummer in range(stand + 1, SCHEMA_VERSION + 1):
        with verbindung:
            verbindung.executescript("BEGIN;" + MIGRATIONEN[nummer - 1] + f"PRAGMA user_version = {nummer};COMMIT;")
    return SCHEMA_VERSION - stand
