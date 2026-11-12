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
    # 2 – Stammdaten: Schuljahre, Schüler:innen, Klassen, Lerngruppen (Klassen-Fächer und Kurse)
    """
    CREATE TABLE schuljahr (
        id                 INTEGER PRIMARY KEY,
        bezeichnung        TEXT NOT NULL UNIQUE,          -- z. B. "2026/27"
        beginn             TEXT NOT NULL,                 -- ISO-Datum
        halbjahreswechsel  TEXT NOT NULL,                 -- erster Tag des 2. Halbjahres
        ende               TEXT NOT NULL,
        CHECK (beginn < halbjahreswechsel AND halbjahreswechsel <= ende)
    );
    CREATE TABLE schueler (
        id            INTEGER PRIMARY KEY,
        nachname      TEXT NOT NULL,
        vorname       TEXT NOT NULL,
        geburtsdatum  TEXT,                               -- optional, hilft beim Import-Abgleich
        extern_id     TEXT,                               -- Kennung aus SchILD/Untis
        bemerkung     TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE klassenzuordnung (
        schueler_id   INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        schuljahr_id  INTEGER NOT NULL REFERENCES schuljahr(id) ON DELETE CASCADE,
        jahrgang      INTEGER NOT NULL,
        klasse        TEXT NOT NULL,                      -- z. B. "8.4"
        zugang        TEXT,                               -- NULL = seit Schuljahresbeginn
        abgang        TEXT,                               -- NULL = bis Schuljahresende
        PRIMARY KEY (schueler_id, schuljahr_id)
    );
    CREATE INDEX klassenzuordnung_jahr ON klassenzuordnung (schuljahr_id, klasse);
    CREATE TABLE lerngruppe (
        id            INTEGER PRIMARY KEY,
        schuljahr_id  INTEGER NOT NULL REFERENCES schuljahr(id) ON DELETE CASCADE,
        bezeichnung   TEXT NOT NULL,                      -- z. B. "M9.3E" oder "8.4 Deutsch"
        fach          TEXT NOT NULL,
        fach_kuerzel  TEXT NOT NULL DEFAULT '',
        art           TEXT NOT NULL CHECK (art IN ('klasse', 'kurs')),
        jahrgang      INTEGER NOT NULL,
        niveau        TEXT NOT NULL DEFAULT '' CHECK (niveau IN ('', 'E', 'G')),
        schriftlich   INTEGER NOT NULL DEFAULT 1,
        notensystem   TEXT NOT NULL DEFAULT 'sek1' CHECK (notensystem IN ('sek1', 'sek2')),
        sortierung    TEXT NOT NULL DEFAULT 'klasse' CHECK (sortierung IN ('klasse', 'alphabet', 'eigene')),
        UNIQUE (schuljahr_id, bezeichnung)
    );
    CREATE TABLE mitglied (
        lerngruppe_id INTEGER NOT NULL REFERENCES lerngruppe(id) ON DELETE CASCADE,
        schueler_id   INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        von           TEXT,                               -- NULL = seit Schuljahresbeginn
        bis           TEXT,                               -- NULL = bis Schuljahresende
        position      INTEGER,                            -- für die eigene Reihenfolge
        PRIMARY KEY (lerngruppe_id, schueler_id)
    );
    CREATE INDEX mitglied_schueler ON mitglied (schueler_id);
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
