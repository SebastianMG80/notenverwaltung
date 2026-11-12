"""KI-Paket: Prompt-Vorlage erzeugen und die Antwort einer KI (JSON) einlesen.

Das Programm selbst nimmt keinen Kontakt zu einer KI auf (offline!). Die Lehrkraft kopiert die Vorlage
zusammen mit ihrer Arbeit in ein KI-Werkzeug ihrer Wahl und fügt die Antwort hier wieder ein.
Die Vorlage enthält keine Schülerdaten.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

FORMAT = "notenverwaltung-arbeit-1"
MAX_LAENGE = 500_000


class KiFehler(ValueError):
    pass


@dataclass(frozen=True)
class KiAufgabe:
    bezeichnung: str
    punkte: float
    thema: str = ""
    erwartung: str = ""


@dataclass(frozen=True)
class KiArbeit:
    titel: str
    thema: str
    aufgaben: list[KiAufgabe] = field(default_factory=list)
    musterloesung: str = ""

    @property
    def hoechstpunkte(self) -> float:
        return sum(a.punkte for a in self.aufgaben)


BEISPIEL = {
    "format": FORMAT,
    "titel": "2. Klassenarbeit",
    "thema": "Lineare Funktionen",
    "aufgaben": [
        {"bezeichnung": "1", "punkte": 4, "thema": "Steigung aus zwei Punkten",
         "erwartung": "m = (y2 − y1)/(x2 − x1) korrekt angesetzt (2 P.), Ergebnis m = 2 (2 P.)"},
        {"bezeichnung": "2a", "punkte": 3, "thema": "Wertetabelle", "erwartung": "…"},
        {"bezeichnung": "b", "punkte": 3, "thema": "Graph zeichnen", "erwartung": "…"},
    ],
    "musterloesung": "Aufgabe 1: …\nAufgabe 2a: …",
}


def prompt_vorlage(fach: str = "", jahrgang: int | None = None, hoechstpunkte: float | None = None,
                   mit_erstellung: bool = False) -> str:
    """Text zum Kopieren in ein KI-Werkzeug. Enthält keine personenbezogenen Daten."""
    rahmen = []
    if fach:
        rahmen.append(f"Fach: {fach}")
    if jahrgang:
        rahmen.append(f"Jahrgang: {jahrgang} (Sekundarstufe I, NRW)")
    if hoechstpunkte:
        rahmen.append(f"Gewünschte Gesamtpunktzahl: etwa {hoechstpunkte:g}")
    auftrag = (
        "Erstelle eine Klassenarbeit zu dem unten beschriebenen Thema." if mit_erstellung else
        "Unten steht eine Klassenarbeit. Bitte bewerte sie für die Korrektur."
    )
    return f"""{auftrag}

{chr(10).join(rahmen) if rahmen else ""}

Liefere:
1. eine Aufteilung in Aufgaben und Teilaufgaben mit einem Vorschlag zur Bepunktung (ganze oder halbe Punkte),
2. je Aufgabe ein kurzes Thema (höchstens 6 Wörter) und einen Erwartungshorizont (was für volle Punktzahl nötig ist,
   wofür es Teilpunkte gibt),
3. eine vollständige Musterlösung.

Teilaufgaben werden wie in einer Punkteliste bezeichnet: „3a“, dann „b“, „c“ (nicht „3b“).

Antworte ausschließlich mit einem JSON-Objekt in genau diesem Format (keine weiteren Erläuterungen):

{json.dumps(BEISPIEL, ensure_ascii=False, indent=2)}

Regeln: "punkte" ist eine Zahl; "format" bleibt genau "{FORMAT}"; Zeilenumbrüche in Texten als \\n.

--- Hier folgt die Arbeit bzw. die Beschreibung ---
""".replace("\n\n\n", "\n\n")


def _json_ausschnitt(text: str) -> str:
    """Holt das JSON-Objekt aus einer KI-Antwort, auch wenn es in ```json … ``` steht oder Text drumherum hat."""
    if len(text) > MAX_LAENGE:
        raise KiFehler("Die Antwort ist zu lang.")
    zaun = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if zaun:
        return zaun.group(1)
    start = text.find("{")
    if start < 0:
        raise KiFehler("In der Antwort wurde kein JSON-Objekt gefunden.")
    tiefe, im_text, maskiert = 0, False, False
    for i in range(start, len(text)):
        z = text[i]
        if im_text:
            if maskiert:
                maskiert = False
            elif z == "\\":
                maskiert = True
            elif z == '"':
                im_text = False
        elif z == '"':
            im_text = True
        elif z == "{":
            tiefe += 1
        elif z == "}":
            tiefe -= 1
            if tiefe == 0:
                return text[start:i + 1]
    raise KiFehler("Das JSON-Objekt in der Antwort ist unvollständig.")


def _zahl(wert, wo: str) -> float:
    if isinstance(wert, bool):
        raise KiFehler(f"{wo}: Punkte sind keine Zahl.")
    if isinstance(wert, (int, float)):
        z = float(wert)
    elif isinstance(wert, str):
        try:
            z = float(wert.strip().replace(",", "."))
        except ValueError:
            raise KiFehler(f"{wo}: „{wert}“ ist keine Punktzahl.") from None
    else:
        raise KiFehler(f"{wo}: Punkte fehlen.")
    if not 0 <= z <= 1000 or abs(z * 4 - round(z * 4)) > 1e-9:
        raise KiFehler(f"{wo}: {z:g} Punkte sind nicht zulässig (0–1000, Viertelschritte).")
    return z


def lies_antwort(text: str) -> KiArbeit:
    try:
        daten = json.loads(_json_ausschnitt(text))
    except json.JSONDecodeError as e:
        raise KiFehler(f"Die Antwort ist kein gültiges JSON (Zeile {e.lineno}, Spalte {e.colno}).") from None
    if not isinstance(daten, dict):
        raise KiFehler("Die Antwort ist kein JSON-Objekt.")
    if daten.get("format") not in (FORMAT, None):
        raise KiFehler(f"Unbekanntes Format „{daten.get('format')}“.")
    aufgaben_roh = daten.get("aufgaben")
    if not isinstance(aufgaben_roh, list) or not aufgaben_roh:
        raise KiFehler("Die Antwort enthält keine Aufgaben.")
    if len(aufgaben_roh) > 200:
        raise KiFehler("Zu viele Aufgaben.")
    aufgaben = []
    for i, a in enumerate(aufgaben_roh, 1):
        if not isinstance(a, dict):
            raise KiFehler(f"Aufgabe {i} ist kein Objekt.")
        bez = str(a.get("bezeichnung", "")).strip()[:20]
        if not bez:
            raise KiFehler(f"Aufgabe {i} hat keine Bezeichnung.")
        aufgaben.append(KiAufgabe(bez, _zahl(a.get("punkte"), f"Aufgabe {bez}"),
                                  str(a.get("thema", "") or "").strip()[:200],
                                  str(a.get("erwartung", "") or "").strip()[:5000]))
    return KiArbeit(str(daten.get("titel", "") or "").strip()[:100], str(daten.get("thema", "") or "").strip()[:200],
                    aufgaben, str(daten.get("musterloesung", "") or "").strip()[:100_000])
