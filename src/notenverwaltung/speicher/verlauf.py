"""Rückgängig / Wiederholen für alle Änderungen einer Sitzung.

Verfahren nach „Automatic Undo/Redo Using SQLite“ (sqlite.org): TEMP-Trigger schreiben zu jeder Änderung den
SQL-Befehl, der sie umkehrt, in die TEMP-Tabelle `verlauf_log`. Ein Schritt ist ein Bereich dieser Tabelle.
„Rückgängig“ führt die Befehle eines Schritts rückwärts aus; die Trigger protokollieren dabei die Umkehrung,
und die wird zum Schritt für „Wiederholen“ (und umgekehrt).

Weil das an der Datenbank ansetzt, gilt es für jede Eingabe – auch für Funktionen, die erst später dazukommen.
TEMP-Objekte gehören nicht zur gespeicherten Datei: Das Dateiformat bleibt unverändert, der Verlauf endet mit dem
Schließen der Datenbank.

Wo ein Schritt endet, entscheidet die Oberfläche: Sie ruft `abschliessen()` bei jeder Eingabe (Taste, Mausklick).
Alles, was zwischen zwei Eingaben geändert wurde, ist also ein Schritt – eine Zelle, ein „OK“ im Dialog, ein
ganzer Schuljahreswechsel.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass

MAX_SCHRITTE = 200

# Tabelle → Bezeichnung im Menü („Rückgängig: Punkte“), in absteigender Wichtigkeit
BEZEICHNUNG = {
    "schuljahr": "Schuljahr",
    "lerngruppe": "Lerngruppe",
    "arbeit": "Klassenarbeit",
    "aufgabe": "Aufgaben",
    "schueler": "Schüler:in",
    "klassenzuordnung": "Klasse",
    "mitglied": "Mitglieder",
    "zeitraum": "Zeiträume",
    "notenschluessel": "Notenschlüssel",
    "zeugnisnote": "Zeugnisnote",
    "muendlich": "mündliche Note",
    "teilnahme": "Note / Vermerk",
    "punkte": "Punkte",
    "meta": "Einstellungen",
}


class VerlaufFehler(Exception):
    pass


@dataclass
class Schritt:
    von: int          # erste und letzte Nummer in verlauf_log
    bis: int
    text: str


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class Verlauf:
    def __init__(self, verbindung: sqlite3.Connection) -> None:
        self.v = verbindung
        self.rueck: list[Schritt] = []
        self.vor: list[Schritt] = []
        self._einrichten()
        self._grenze = self._letzte_nummer()

    # ---- Einrichten ----------------------------------------------------------------------------
    def _einrichten(self) -> None:
        v = self.v
        if v.in_transaction:
            v.commit()
        v.execute("CREATE TEMP TABLE IF NOT EXISTS verlauf_log "
                  "(nr INTEGER PRIMARY KEY AUTOINCREMENT, tabelle TEXT NOT NULL, befehl TEXT NOT NULL)")
        v.execute("CREATE TEMP TABLE IF NOT EXISTS verlauf_zustand (aktiv INTEGER NOT NULL)")
        if v.execute("SELECT COUNT(*) FROM temp.verlauf_zustand").fetchone()[0] == 0:
            v.execute("INSERT INTO temp.verlauf_zustand VALUES (1)")
        tabellen = [r[0] for r in v.execute(
            "SELECT name FROM main.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for t in tabellen:
            spalten = [r[1] for r in v.execute(f"PRAGMA main.table_info({_q(t)})")]
            wenn = "WHEN (SELECT aktiv FROM temp.verlauf_zustand)"
            log = f"INSERT INTO verlauf_log (tabelle, befehl) VALUES ('{t}', "
            neu_t = _q(t).replace("'", "''")
            setzen = " || ',' || ".join(f"'{_q(s)}=' || quote(old.{_q(s)})" for s in spalten)
            werte = " || ',' || ".join(f"quote(old.{_q(s)})" for s in spalten)
            namen = ",".join(_q(s) for s in spalten).replace("'", "''")
            v.executescript(f"""
                CREATE TEMP TRIGGER IF NOT EXISTS {_q('verlauf_' + t + '_i')} AFTER INSERT ON {_q(t)} {wenn} BEGIN
                    {log}'DELETE FROM {neu_t} WHERE rowid = ' || new.rowid); END;
                CREATE TEMP TRIGGER IF NOT EXISTS {_q('verlauf_' + t + '_u')} AFTER UPDATE ON {_q(t)} {wenn} BEGIN
                    {log}'UPDATE {neu_t} SET ' || {setzen} || ' WHERE rowid = ' || old.rowid); END;
                CREATE TEMP TRIGGER IF NOT EXISTS {_q('verlauf_' + t + '_d')} AFTER DELETE ON {_q(t)} {wenn} BEGIN
                    {log}'INSERT INTO {neu_t} (rowid,{namen}) VALUES (' || old.rowid || ',' || {werte} || ')'); END;
            """)

    def _letzte_nummer(self) -> int:
        return self.v.execute("SELECT COALESCE(MAX(nr), 0) FROM temp.verlauf_log").fetchone()[0]

    def _text(self, von: int, bis: int) -> str:
        tabellen = {r[0] for r in self.v.execute(
            "SELECT DISTINCT tabelle FROM temp.verlauf_log WHERE nr BETWEEN ? AND ?", (von, bis))}
        return next((text for t, text in BEZEICHNUNG.items() if t in tabellen), "Änderung")

    # ---- Schritte ------------------------------------------------------------------------------
    def abschliessen(self) -> bool:
        """Schließt alle seit dem letzten Aufruf protokollierten Änderungen zu einem Schritt ab.
        Eine neue Änderung macht „Wiederholen“ unmöglich. Gibt True zurück, wenn ein Schritt entstand."""
        letzte = self._letzte_nummer()
        if letzte <= self._grenze:
            return False
        schritt = Schritt(self._grenze + 1, letzte, self._text(self._grenze + 1, letzte))
        self._grenze = letzte
        for alt in self.vor:
            self._vergessen(alt)
        self.vor.clear()
        self.rueck.append(schritt)
        while len(self.rueck) > MAX_SCHRITTE:
            self._vergessen(self.rueck.pop(0))
        if self.v.in_transaction:
            self.v.commit()
        return True

    def _vergessen(self, s: Schritt) -> None:
        self.v.execute("DELETE FROM temp.verlauf_log WHERE nr BETWEEN ? AND ?", (s.von, s.bis))
        if self.v.in_transaction:
            self.v.commit()

    @property
    def kann_rueckgaengig(self) -> bool:
        return bool(self.rueck) or self._letzte_nummer() > self._grenze

    @property
    def kann_wiederholen(self) -> bool:
        return bool(self.vor) and self._letzte_nummer() <= self._grenze

    def text_rueckgaengig(self) -> str:
        self.abschliessen()
        return self.rueck[-1].text if self.rueck else ""

    def text_wiederholen(self) -> str:
        return self.vor[-1].text if self.vor and not self.abschliessen() else ""

    def rueckgaengig(self) -> str | None:
        """Macht den letzten Schritt rückgängig. Gibt seine Bezeichnung zurück (None: nichts zu tun)."""
        self.abschliessen()
        if not self.rueck:
            return None
        s = self.rueck.pop()
        neu = self._ausfuehren(s, self.rueck)
        self.vor.append(neu)
        return s.text

    def wiederholen(self) -> str | None:
        if self.abschliessen() or not self.vor:      # nach einer neuen Änderung gibt es nichts zu wiederholen
            return None
        s = self.vor.pop()
        neu = self._ausfuehren(s, self.vor)
        self.rueck.append(neu)
        return s.text

    def _ausfuehren(self, s: Schritt, zurueck_bei_fehler: list[Schritt]) -> Schritt:
        """Führt die Befehle eines Schritts rückwärts aus; was dabei protokolliert wird, ist der Gegenschritt."""
        v = self.v
        if v.in_transaction:
            v.commit()
        befehle = [r[0] for r in v.execute(
            "SELECT befehl FROM temp.verlauf_log WHERE nr BETWEEN ? AND ? ORDER BY nr DESC", (s.von, s.bis))]
        start = self._letzte_nummer()
        try:
            v.execute("BEGIN")
            v.execute("PRAGMA defer_foreign_keys = ON")   # Eltern und Kinder kommen in beliebiger Reihenfolge zurück
            for b in befehle:
                v.execute(b)
            v.execute("DELETE FROM temp.verlauf_log WHERE nr BETWEEN ? AND ?", (s.von, s.bis))
            v.commit()
        except sqlite3.Error as e:
            v.rollback()
            zurueck_bei_fehler.append(s)
            raise VerlaufFehler(f"„{s.text}“ ließ sich nicht umkehren: {e}") from e
        ende = self._letzte_nummer()
        self._grenze = ende
        return Schritt(start + 1, ende, s.text)

    def leeren(self) -> None:
        self.v.execute("DELETE FROM temp.verlauf_log")
        if self.v.in_transaction:
            self.v.commit()
        self.rueck.clear()
        self.vor.clear()
        self._grenze = self._letzte_nummer()


@contextmanager
def ohne_verlauf(verbindung: sqlite3.Connection):
    """Änderungen, die das Programm selbst vornimmt (z. B. Standard-Zeiträume beim ersten Anzeigen), sollen
    nicht als eigener Schritt erscheinen."""
    try:
        verbindung.execute("UPDATE temp.verlauf_zustand SET aktiv = 0")
        aktiv = True
    except sqlite3.OperationalError:     # Verbindung ohne Verlauf (z. B. in Werkzeugen)
        aktiv = False
    try:
        yield
    finally:
        if aktiv:
            verbindung.execute("UPDATE temp.verlauf_zustand SET aktiv = 1")
            if verbindung.in_transaction:
                verbindung.commit()
