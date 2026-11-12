"""Schülerlisten importieren: Spalten erkennen, mit vorhandenen Daten abgleichen, übernehmen.

Funktioniert mit beliebigen Tabellen (CSV, Excel, ODS) – auch mit Exporten aus SchILD-NRW oder Untis,
deren Spaltennamen über Synonyme erkannt werden. Dateien ohne Überschriftszeile werden anhand der Inhalte
zugeordnet; jede Zuordnung lässt sich im Assistenten von Hand ändern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date

from notenverwaltung.modell.stammdaten import Stammdaten, StammdatenFehler, jahrgang_aus_klasse, name_schluessel

FELDER = {
    "nachname": "Nachname",
    "vorname": "Vorname",
    "name_komplett": "Name, Vorname (eine Spalte)",
    "klasse": "Klasse",
    "jahrgang": "Jahrgang",
    "geburtsdatum": "Geburtsdatum",
    "extern_id": "ID / Nummer",
}

SYNONYME = {
    "nachname": {"nachname", "familienname", "zuname", "langname", "schuelernachname", "nachnamen", "name"},
    "vorname": {"vorname", "rufname", "vornamen", "schuelervorname"},
    "klasse": {"klasse", "kl", "klassen", "klassenbezeichnung", "klassenname", "akt klasse", "aktuelle klasse"},
    "jahrgang": {"jahrgang", "jg", "jgst", "jahrgangsstufe", "stufe", "schuljahrgang"},
    "geburtsdatum": {"geburtsdatum", "gebdatum", "geb datum", "geb", "geburtstag", "geboren"},
    "extern_id": {"id", "interne id", "interne idnummer", "interneidnummer", "interne id nummer", "schuelerid",
                  "schueler id", "schuelernummer", "nummer", "nr", "id nummer", "idnummer", "kennung", "kurzname"},
}


class ImportFehler(ValueError):
    pass


def _norm(text: str) -> str:
    t = name_schluessel(text)
    t = re.sub(r"[^a-z0-9 ]+", " ", t.replace("ü", "ue"))
    return re.sub(r"\s+", " ", t).strip()


def lies_datum(text: str) -> date | None:
    t = text.strip()
    if not t:
        return None
    for muster in (r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", r"(\d{4})-(\d{2})-(\d{2})", r"(\d{1,2})/(\d{1,2})/(\d{4})"):
        m = re.fullmatch(muster, t)
        if m:
            a, b, c = (int(x) for x in m.groups())
            try:
                if muster.startswith(r"(\d{4})"):
                    return date(a, b, c)
                if c < 100:
                    c += 2000 if c < 50 else 1900
                return date(c, b, a)
            except ValueError:
                return None
    if re.fullmatch(r"\d{8}", t):  # Untis: JJJJMMTT
        try:
            return date(int(t[:4]), int(t[4:6]), int(t[6:]))
        except ValueError:
            return None
    return None


def _sieht_aus_wie_klasse(t: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(\s?[./-]?\s?[a-zA-Z0-9]{0,3})", t.strip()))


@dataclass
class Zuordnung:
    """Spaltennummer je Feld (None = nicht vorhanden)."""

    spalten: dict[str, int | None] = field(default_factory=lambda: {f: None for f in FELDER})
    kopfzeile: bool = True
    feste_klasse: str = ""          # für Listen ohne Klassenspalte (z. B. Kursliste)

    def pruefe(self) -> None:
        s = self.spalten
        if s["name_komplett"] is None and (s["nachname"] is None or s["vorname"] is None):
            raise ImportFehler("Bitte die Spalten für Nach- und Vorname zuordnen (oder „Name, Vorname“).")
        if s["klasse"] is None and not self.feste_klasse.strip():
            raise ImportFehler("Bitte die Klassenspalte zuordnen oder eine Klasse für alle angeben.")
        benutzt = [v for v in s.values() if v is not None]
        if len(benutzt) != len(set(benutzt)):
            raise ImportFehler("Eine Spalte ist mehreren Feldern zugeordnet.")


def erkenne(zeilen: list[list[str]]) -> Zuordnung:
    """Schlägt eine Zuordnung vor: zuerst über Überschriften, sonst über die Inhalte."""
    z = Zuordnung()
    if not zeilen:
        return z
    kopf = [_norm(x) for x in zeilen[0]]
    for feld, synonyme in SYNONYME.items():
        for i, k in enumerate(kopf):
            if k in synonyme and i not in z.spalten.values():
                z.spalten[feld] = i
                break
    # „Name“ ohne Vorname-Spalte: vermutlich „Nachname, Vorname“ in einer Spalte
    if z.spalten["nachname"] is not None and z.spalten["vorname"] is None:
        werte = [r[z.spalten["nachname"]] for r in zeilen[1:20] if len(r) > z.spalten["nachname"]]
        if werte and sum("," in w for w in werte) >= len(werte) * 0.8:
            z.spalten["name_komplett"], z.spalten["nachname"] = z.spalten["nachname"], None
    if any(v is not None for v in z.spalten.values()):
        return z

    # Keine bekannte Überschrift: nach Inhalten raten
    z.kopfzeile = False
    probe = zeilen[:30]
    breite = max(len(r) for r in probe)

    def anteil(spalte: int, pruef) -> float:
        werte = [r[spalte] for r in probe if len(r) > spalte and r[spalte]]
        return sum(1 for w in werte if pruef(w)) / len(werte) if werte else 0.0

    for i in range(breite):
        if z.spalten["geburtsdatum"] is None and anteil(i, lambda w: lies_datum(w) is not None) > 0.8:
            z.spalten["geburtsdatum"] = i
        elif z.spalten["klasse"] is None and anteil(i, _sieht_aus_wie_klasse) > 0.8:
            z.spalten["klasse"] = i
    texte = [i for i in range(breite) if i not in z.spalten.values()
             and anteil(i, lambda w: bool(re.fullmatch(r"[^\d]{2,}", w))) > 0.8]
    if texte and anteil(texte[0], lambda w: "," in w) > 0.8:
        z.spalten["name_komplett"] = texte[0]
    elif len(texte) >= 2:
        z.spalten["nachname"], z.spalten["vorname"] = texte[0], texte[1]
    return z


@dataclass(frozen=True)
class Datensatz:
    zeile: int                      # Zeilennummer in der Datei (ab 1)
    nachname: str
    vorname: str
    klasse: str
    jahrgang: int | None
    geburtsdatum: date | None
    extern_id: str | None
    fehler: str = ""


def datensaetze(zeilen: list[list[str]], z: Zuordnung) -> list[Datensatz]:
    z.pruefe()
    s = z.spalten
    ergebnis = []

    def wert(r: list[str], feld: str) -> str:
        i = s[feld]
        return r[i].strip() if i is not None and i < len(r) else ""

    for nr, r in enumerate(zeilen[1:] if z.kopfzeile else zeilen, 2 if z.kopfzeile else 1):
        if s["name_komplett"] is not None:
            komplett = wert(r, "name_komplett")
            nach, _, vor = komplett.partition(",")
        else:
            nach, vor = wert(r, "nachname"), wert(r, "vorname")
        nach, vor = nach.strip(), vor.strip()
        klasse = wert(r, "klasse") or z.feste_klasse.strip()
        jg_text = wert(r, "jahrgang")
        jahrgang = int(jg_text) if jg_text.isdigit() else jahrgang_aus_klasse(klasse)
        geb_text = wert(r, "geburtsdatum")
        geb = lies_datum(geb_text)
        fehler = ""
        if not nach or not vor:
            fehler = "Name unvollständig"
        elif not klasse:
            fehler = "Klasse fehlt"
        elif not jahrgang or not 1 <= jahrgang <= 13:
            fehler = "Jahrgang unbekannt"
        elif geb_text and geb is None:
            fehler = f"Geburtsdatum „{geb_text}“ unlesbar"
        ergebnis.append(Datensatz(nr, nach, vor, klasse, jahrgang, geb, wert(r, "extern_id") or None, fehler))
    return ergebnis


# ---- Abgleich ------------------------------------------------------------------------------------

AKTIONEN = {"neu": "neu anlegen", "vorhanden": "schon vorhanden", "aktualisieren": "Klasse/Angaben aktualisieren",
            "uebernehmen": "aus früherem Schuljahr übernehmen", "ueberspringen": "überspringen"}


@dataclass(frozen=True)
class Abgleich:
    satz: Datensatz
    aktion: str                     # Schlüssel aus AKTIONEN
    schueler_id: int | None         # vorhandene Person, falls erkannt
    hinweis: str = ""

    @property
    def moegliche_aktionen(self) -> list[str]:
        if self.satz.fehler:
            return ["ueberspringen"]
        if self.schueler_id is None:
            return ["neu", "ueberspringen"]
        return [self.aktion, "neu", "ueberspringen"] if self.aktion != "neu" else ["neu", "ueberspringen"]


def gleiche_ab(sd: Stammdaten, schuljahr_id: int, saetze: list[Datensatz]) -> list[Abgleich]:
    im_jahr = sd.schueler_im_jahr(schuljahr_id)
    nach_id = {e.schueler.extern_id: e for e in im_jahr if e.schueler.extern_id}
    nach_name: dict[tuple[str, str], list] = {}
    for e in im_jahr:
        nach_name.setdefault((name_schluessel(e.schueler.nachname), name_schluessel(e.schueler.vorname)), []).append(e)
    alle = {z[0]: z for z in sd.v.execute("SELECT id, nachname, vorname, geburtsdatum, extern_id FROM schueler")}
    im_jahr_ids = {e.schueler.id for e in im_jahr}
    gesehen: set[tuple] = set()
    ergebnis = []
    for s in saetze:
        if s.fehler:
            ergebnis.append(Abgleich(s, "ueberspringen", None, s.fehler))
            continue
        schluessel = (name_schluessel(s.nachname), name_schluessel(s.vorname), s.klasse)
        if schluessel in gesehen:
            ergebnis.append(Abgleich(s, "ueberspringen", None, "doppelt in der Datei"))
            continue
        gesehen.add(schluessel)
        # 1. gleiche ID in diesem Schuljahr
        e = nach_id.get(s.extern_id) if s.extern_id else None
        # 2. gleicher Name in diesem Schuljahr
        if e is None:
            treffer = nach_name.get(schluessel[:2], [])
            e = next((x for x in treffer if x.klasse == s.klasse), None)
            if e is None and len(treffer) == 1:
                ergebnis.append(Abgleich(s, "ueberspringen", treffer[0].schueler.id,
                                         f"gleichnamig in Klasse {treffer[0].klasse} – Klassenwechsel? Bitte prüfen."))
                continue
        if e is not None:
            if e.klasse != s.klasse or (s.geburtsdatum and not e.schueler.geburtsdatum) or \
                    (s.extern_id and not e.schueler.extern_id):
                hinweis = f"bisher Klasse {e.klasse}" if e.klasse != s.klasse else "ergänzt Angaben"
                ergebnis.append(Abgleich(s, "aktualisieren", e.schueler.id, hinweis))
            else:
                ergebnis.append(Abgleich(s, "vorhanden", e.schueler.id))
            continue
        # 3. Person aus einem anderen Schuljahr (ID oder Name + Geburtsdatum)
        frueher = None
        for sid, nach, vor, geb, ext in alle.values():
            if sid in im_jahr_ids:
                continue
            if s.extern_id and ext == s.extern_id:
                frueher = sid
                break
            if (name_schluessel(nach), name_schluessel(vor)) == schluessel[:2] and s.geburtsdatum and \
                    geb == s.geburtsdatum.isoformat():
                frueher = sid
                break
        if frueher is not None:
            ergebnis.append(Abgleich(s, "uebernehmen", frueher, "aus früherem Schuljahr bekannt"))
        else:
            ergebnis.append(Abgleich(s, "neu", None))
    return ergebnis


@dataclass
class ImportErgebnis:
    neu: int = 0
    aktualisiert: int = 0
    uebernommen: int = 0
    unveraendert: int = 0
    uebersprungen: int = 0
    in_lerngruppe: int = 0


def fuehre_aus(sd: Stammdaten, schuljahr_id: int, abgleich: list[Abgleich], lerngruppe_id: int | None = None,
               zugang: date | None = None) -> ImportErgebnis:
    """Übernimmt den Abgleich in einem Rutsch (alles oder nichts).

    Die einzelnen Schritte schließen ihre Transaktionen selbst ab; deshalb wird vorher der komplette Stand
    der (kleinen, im Speicher liegenden) Datenbank gesichert und bei einem Fehler zurückgespielt.
    """
    e = ImportErgebnis()
    ids: list[int] = []
    v = sd.v
    if v.in_transaction:
        v.commit()
    vorher = v.serialize()
    try:
        for a in abgleich:
            s = a.satz
            if a.aktion == "ueberspringen" or s.fehler:
                e.uebersprungen += 1
                continue
            if a.aktion == "neu":
                neu = sd.lege_schueler_an(schuljahr_id, s.nachname, s.vorname, s.klasse, s.jahrgang, zugang,
                                          s.geburtsdatum, s.extern_id)
                ids.append(neu.id)
                e.neu += 1
            elif a.aktion in ("aktualisieren", "uebernehmen"):
                alt = sd.schueler(a.schueler_id)
                sd.aendere_schueler(replace(alt, geburtsdatum=alt.geburtsdatum or s.geburtsdatum,
                                            extern_id=alt.extern_id or s.extern_id))
                bisher = next((x for x in sd.schueler_im_jahr(schuljahr_id) if x.schueler.id == alt.id), None)
                sd.setze_klasse(alt.id, schuljahr_id, s.klasse, s.jahrgang,
                                bisher.zugang if bisher else zugang)
                ids.append(alt.id)
                if a.aktion == "aktualisieren":
                    e.aktualisiert += 1
                else:
                    e.uebernommen += 1
            else:
                ids.append(a.schueler_id)
                e.unveraendert += 1
        if lerngruppe_id is not None and ids:
            e.in_lerngruppe = sd.fuege_hinzu(lerngruppe_id, ids, zugang)
    except Exception:
        if v.in_transaction:
            v.rollback()
        v.deserialize(vorher)
        v.execute("PRAGMA foreign_keys = ON")
        raise
    return e
