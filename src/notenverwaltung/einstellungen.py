"""Programmeinstellungen (nicht die Notendaten!).

Gespeichert als INI-Datei im Benutzerprofil – auf Linux und Windows im
gleichen Format. Hier steht nur Bedienkomfort (Design, Fenstergröße, zuletzt
geöffnete Datenbank), niemals Schülerdaten.
"""

from PySide6.QtCore import QSettings

from notenverwaltung import APP_NAME, ORG_NAME


def einstellungen() -> QSettings:
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, ORG_NAME, APP_NAME)


def design_name() -> str:
    wert = einstellungen().value("ansicht/design", "dunkel")
    return wert if wert in ("dunkel", "hell") else "dunkel"


def setze_design_name(name: str) -> None:
    s = einstellungen()
    s.setValue("ansicht/design", name)
    s.sync()


# ---- Zuletzt geöffnete Datenbanken ---------------------------------------------------------------
MAX_ZULETZT = 8


def zuletzt_geoeffnet() -> list[str]:
    wert = einstellungen().value("datenbank/zuletzt", [])
    if isinstance(wert, str):
        wert = [wert]
    return [str(w) for w in (wert or []) if w]


def merke_geoeffnet(pfad: str) -> None:
    liste = [p for p in zuletzt_geoeffnet() if p != pfad]
    liste.insert(0, pfad)
    s = einstellungen()
    s.setValue("datenbank/zuletzt", liste[:MAX_ZULETZT])
    s.sync()


def vergiss_geoeffnet(pfad: str) -> None:
    s = einstellungen()
    s.setValue("datenbank/zuletzt", [p for p in zuletzt_geoeffnet() if p != pfad])
    s.sync()


# ---- Schriften ------------------------------------------------------------------------------------

def ui_schrift() -> str:
    """QFont.toString() der gewählten Oberflächenschrift oder leer (= Systemschrift)."""
    return str(einstellungen().value("ansicht/schrift", "") or "")


def setze_ui_schrift(text: str) -> None:
    s = einstellungen()
    s.setValue("ansicht/schrift", text)
    s.sync()


def druck_schrift() -> str:
    return str(einstellungen().value("druck/schrift", "") or "")


def setze_druck_schrift(familie: str) -> None:
    s = einstellungen()
    s.setValue("druck/schrift", familie)
    s.sync()
