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
