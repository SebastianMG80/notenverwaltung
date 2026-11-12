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


@pytest.fixture(autouse=True)
def keine_meldungsfenster(monkeypatch):
    """Meldungsfenster würden Tests blockieren: sie werden nur protokolliert.

    Fragen (bausteine.frage) gelten als mit „Abbrechen“ beantwortet, sofern ein Test sie nicht überschreibt.
    """
    from PySide6.QtWidgets import QMessageBox

    protokoll = []

    def merke(art):
        def f(*args, **kwargs):
            protokoll.append((art, args[1:3] if len(args) > 2 else args))
            return QMessageBox.StandardButton.Ok
        return f

    monkeypatch.setattr(QMessageBox, "information", staticmethod(merke("info")))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(merke("fehler")))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(merke("warnung")))
    monkeypatch.setattr(QMessageBox, "about", staticmethod(merke("about")))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: protokoll.append(("frage", self.text())) or 0)
    return protokoll


@pytest.fixture
def schnelle_kdf(monkeypatch):
    """Argon2id mit minimalen Kosten, damit UI-Tests schnell bleiben."""
    from notenverwaltung.speicher import tresor
    from notenverwaltung.speicher.krypto import KdfParameter

    monkeypatch.setattr(tresor, "STANDARD_KDF", KdfParameter(iterationen=1, spuren=1, speicher_kib=1024))


@pytest.fixture(autouse=True)
def fenster_aufraeumen():
    """Nach jedem Test alle Fenster schließen und löschen.

    Sonst leben Qt-Fenster bis zum Ende des Python-Prozesses weiter und werden beim Herunterfahren in
    ungünstiger Reihenfolge abgebaut – das führte gelegentlich zu einem Absturz nach erfolgreichem Testlauf.
    """
    yield
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for w in QApplication.topLevelWidgets():
        w.close()
        w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
