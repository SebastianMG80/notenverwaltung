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
    # 3 – Klassenarbeiten: Notenschlüssel-Vorlagen, Arbeiten, Aufgaben, Punkte, Teilnahme
    """
    CREATE TABLE notenschluessel (
        id        INTEGER PRIMARY KEY,
        name      TEXT NOT NULL UNIQUE,
        daten     TEXT NOT NULL,                          -- JSON: Stufen (Prozent → Note) und Raster
        standard  INTEGER NOT NULL DEFAULT 0
    );
    INSERT INTO notenschluessel (name, daten, standard) VALUES ('Standard (Punkteliste)',
        '{"stufen":[[0,"6"],[20,"5-"],[21,"5"],[38,"5+"],[40,"4-"],[42,"4"],[53,"4+"],[55,"3-"],[57,"3"],[68,"3+"],[70,"2-"],[72,"2"],[81,"2+"],[83,"1-"],[85,"1"],[105,"1+"]],"raster":1.0}',
        1);
    CREATE TABLE arbeit (
        id              INTEGER PRIMARY KEY,
        lerngruppe_id   INTEGER NOT NULL REFERENCES lerngruppe(id) ON DELETE CASCADE,
        titel           TEXT NOT NULL,                    -- z. B. "1. Klassenarbeit"
        datum           TEXT NOT NULL,                    -- Tag der Arbeit (bestimmt Halbjahr und Teilnehmende)
        rueckgabe       TEXT,                             -- Datum auf Notenabschnitten (Korrektur/Rückgabe)
        schluessel      TEXT NOT NULL,                    -- Kopie des Notenschlüssels als JSON
        art             TEXT NOT NULL DEFAULT 'klassenarbeit',
        zaehlt          INTEGER NOT NULL DEFAULT 1,       -- zählt zur schriftlichen Note
        gewicht         REAL NOT NULL DEFAULT 1,
        thema           TEXT NOT NULL DEFAULT '',
        bemerkung       TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX arbeit_lerngruppe ON arbeit (lerngruppe_id, datum);
    CREATE TABLE aufgabe (
        id              INTEGER PRIMARY KEY,
        arbeit_id       INTEGER NOT NULL REFERENCES arbeit(id) ON DELETE CASCADE,
        position        INTEGER NOT NULL,
        bezeichnung     TEXT NOT NULL,                    -- "1", "3a", "b"
        max_punkte      REAL NOT NULL CHECK (max_punkte >= 0),
        thema           TEXT NOT NULL DEFAULT '',         -- Kurzbeschreibung für den Rückmeldebogen
        erwartung       TEXT NOT NULL DEFAULT ''          -- Erwartungshorizont / Musterlösung
    );
    CREATE INDEX aufgabe_arbeit ON aufgabe (arbeit_id, position);
    CREATE TABLE punkte (
        aufgabe_id      INTEGER NOT NULL REFERENCES aufgabe(id) ON DELETE CASCADE,
        schueler_id     INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        punkte          REAL NOT NULL CHECK (punkte >= 0),
        PRIMARY KEY (aufgabe_id, schueler_id)
    );
    CREATE TABLE teilnahme (
        arbeit_id       INTEGER NOT NULL REFERENCES arbeit(id) ON DELETE CASCADE,
        schueler_id     INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        status          TEXT NOT NULL DEFAULT '' CHECK (status IN ('', 'fehlt', 'nachschreiben', 'befreit')),
        note_manuell    TEXT,                             -- festgesetzte Note (z. B. bei Täuschung), sonst NULL
        kommentar       TEXT NOT NULL DEFAULT '',         -- Rückmeldung an die Person
        PRIMARY KEY (arbeit_id, schueler_id)
    );
    """,
    # 4 – Mündliche Noten (Sonstige Mitarbeit) je Zeitraum
    """
    CREATE TABLE zeitraum (
        id              INTEGER PRIMARY KEY,
        lerngruppe_id   INTEGER NOT NULL REFERENCES lerngruppe(id) ON DELETE CASCADE,
        bezeichnung     TEXT NOT NULL,                    -- z. B. "1. Quartal"
        beginn          TEXT NOT NULL,
        ende            TEXT NOT NULL,
        CHECK (beginn <= ende)
    );
    CREATE INDEX zeitraum_lerngruppe ON zeitraum (lerngruppe_id, beginn);
    CREATE TABLE muendlich (
        zeitraum_id     INTEGER NOT NULL REFERENCES zeitraum(id) ON DELETE CASCADE,
        schueler_id     INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        note            TEXT NOT NULL,                    -- Kurzform mit Tendenz, z. B. "2-"
        bemerkung       TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (zeitraum_id, schueler_id)
    );
    """,
    # 5 – Notenberechnung: Gewichtung je Lerngruppe, festgesetzte Zeugnisnoten, ZP10
    """
    ALTER TABLE lerngruppe ADD COLUMN anteil_schriftlich REAL;      -- NULL = automatisch (50 % bzw. 0 %)
    ALTER TABLE lerngruppe ADD COLUMN anteil_hj1 REAL NOT NULL DEFAULT 10;
    ALTER TABLE lerngruppe ADD COLUMN zp10 INTEGER;                 -- NULL = automatisch (D/E/M in Jahrgang 10)
    CREATE TABLE zeugnisnote (
        lerngruppe_id   INTEGER NOT NULL REFERENCES lerngruppe(id) ON DELETE CASCADE,
        schueler_id     INTEGER NOT NULL REFERENCES schueler(id) ON DELETE CASCADE,
        art             TEXT NOT NULL CHECK (art IN ('hj1', 'hj2', 'vornote', 'zp10')),
        note            TEXT NOT NULL,                    -- Kurzform, z. B. "2" oder "2-"
        bemerkung       TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (lerngruppe_id, schueler_id, art)
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
