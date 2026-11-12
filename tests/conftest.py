"""Gemeinsame Test-Vorbereitung: Qt ohne Bildschirm, Einstellungen in einem Wegwerf-Ordner."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402


@pytest.fixture(autouse=True)
def eigene_einstellungen(tmp_path):
    """Kein Test darf die echten Einstellungen des Benutzers anfassen."""
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "config"))
    yield


@pytest.fixture
def app():
    from notenverwaltung.app import erzeuge_anwendung

    return erzeuge_anwendung([])
