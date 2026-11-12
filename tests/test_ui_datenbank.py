"""Dialoge rund um die Datenbank: Assistent, Startdialog, Wiederherstellung, Sicherheit, Hauptfenster."""

import shutil
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QWizard

from notenverwaltung.einstellungen import merke_geoeffnet, zuletzt_geoeffnet
from notenverwaltung.speicher.datenbank import Datenbank, sperrdatei
from notenverwaltung.speicher.krypto import EntschluesselungsFehler
from notenverwaltung.speicher.tresor import PASSWORT, WIEDERHERSTELLUNG

PW = "Sommerferien 2027!"


def assistent_bis_notfall(app, ordner: Path, name="Noten"):
    from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent

    w = NeueDatenbankAssistent()
    w.show()
    w.seite_datenschutz.gelesen.setChecked(True)
    assert w.button(QWizard.WizardButton.NextButton).isEnabled()
    w.next()
    w.seite_ort.name.setText(name)
    w.seite_ort.ordner.setText(str(ordner))
    assert w.seite_ort.isComplete()
    w.next()
    assert not w.seite_passwort.isComplete()
    w.seite_passwort.pw1.setText(PW)
    w.seite_passwort.pw2.setText(PW)
    assert w.seite_passwort.isComplete()
    w.next()
    app.processEvents()
    return w


@pytest.fixture
def db(tmp_path, schnelle_kdf):
    d, code = Datenbank.neu(tmp_path / "Klasse", PW)
    d.code = code
    yield d
    try:
        d.schliessen(speichern=False)
    except Exception:
        pass


# ---- Assistent ----------------------------------------------------------------------------------

def test_assistent_legt_datenbank_an(app, tmp_path, schnelle_kdf):
    w = assistent_bis_notfall(app, tmp_path / "Schule")
    assert w.currentPage() is w.seite_notfall
    assert w.datenbank is not None and w.datenbank.pfad == tmp_path / "Schule" / "Noten.nvdb"
    code = w.seite_notfall.anzeige.code
    assert len(code) == 29
    assert not w.seite_notfall.isComplete()
    w.seite_notfall.anzeige.bestaetigung.setChecked(True)
    assert w.seite_notfall.isComplete()
    w.accept()
    w.datenbank.schliessen()
    Datenbank.oeffnen(tmp_path / "Schule" / "Noten.nvdb", WIEDERHERSTELLUNG, code).schliessen()
    assert w.seite_passwort.pw1.text() == ""  # Passwort nicht im Speicher des Dialogs behalten


def test_assistent_kurzes_passwort(app, tmp_path):
    from notenverwaltung.ui.neue_datenbank import passwort_bewertung

    assert passwort_bewertung("kurz")[0] is False
    assert passwort_bewertung("zehnzeichn")[0] is True
    assert passwort_bewertung("Ein langer Satz als Passwort")[2] == "ok"


def test_assistent_vorhandene_datei(app, db):
    from notenverwaltung.ui.neue_datenbank import SeiteSpeicherort

    s = SeiteSpeicherort()
    s.ordner.setText(str(db.pfad.parent))
    s.name.setText("Klasse")
    assert not s.isComplete()
    assert "gibt es schon" in s.hinweis.text()
    s.name.setText("Kla/sse")
    assert not s.isComplete()


def test_assistent_cloud_warnung(app, tmp_path, monkeypatch):
    from notenverwaltung.ui import neue_datenbank

    s = neue_datenbank.SeiteSpeicherort()
    s.ordner.setText(str(tmp_path / "Nextcloud" / "Schule"))
    assert "Cloud" in s.hinweis.text()
    monkeypatch.setattr(neue_datenbank, "frage", lambda *a, **k: False)
    assert s.validatePage() is False
    monkeypatch.setattr(neue_datenbank, "frage", lambda *a, **k: True)
    assert s.validatePage() is True


def test_assistent_abbruch_ohne_notfallblatt(app, tmp_path, schnelle_kdf, monkeypatch):
    from notenverwaltung.ui import neue_datenbank

    w = assistent_bis_notfall(app, tmp_path)
    monkeypatch.setattr(neue_datenbank, "frage", lambda *a, **k: False)
    w.reject()
    assert w.isVisible()  # „Zurück“ gewählt
    monkeypatch.setattr(neue_datenbank, "frage", lambda *a, **k: True)
    w.reject()
    assert w.result() == QWizard.DialogCode.Accepted  # Datenbank gibt es – sie wird geöffnet
    w.datenbank.schliessen()


def test_notfallblatt_als_pdf(app, tmp_path, monkeypatch):
    from notenverwaltung.ui.notfall import NotfallAnzeige

    a = NotfallAnzeige()
    a.setze("Klasse", "ABCD-EFGH-JKMN-PQRS-TVWX-YZ23")
    ziel = tmp_path / "blatt"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *x, **k: (str(ziel), "")))
    a._pdf()
    assert (tmp_path / "blatt.pdf").read_bytes()[:4] == b"%PDF"
    assert "Gespeichert" in a.status.text()
    if shutil.which("pdftotext"):
        import subprocess

        text = subprocess.run(["pdftotext", str(tmp_path / "blatt.pdf"), "-"], capture_output=True, text=True).stdout
        assert "ABCD-EFGH-JKMN" in text and "VO-DV I" in text and "Klasse" in text


# ---- Startdialog ----------------------------------------------------------------------------------

def test_startdialog_falsches_und_richtiges_passwort(app, db):
    from notenverwaltung.ui.startdialog import StartDialog

    db.schliessen()
    merke_geoeffnet(str(db.pfad))
    d = StartDialog()
    assert d.ausgewaehlt() == db.pfad
    d.passwort.setText("falsch")
    d._oeffnen()
    assert "falsch" in d.meldung.text()
    assert d.datenbank is None
    d.passwort.setText(PW)
    d._oeffnen()
    assert d.datenbank is not None
    assert d.passwort.text() == ""
    d.datenbank.schliessen()


def test_startdialog_zuletzt_benutzte_vorausgewaehlt(app, tmp_path, schnelle_kdf):
    from notenverwaltung.ui.startdialog import StartDialog

    pfade = []
    for name in ("A", "B"):
        d, _ = Datenbank.neu(tmp_path / name, PW)
        d.schliessen()
        merke_geoeffnet(str(d.pfad))
        pfade.append(d.pfad)
    merke_geoeffnet(str(tmp_path / "weg.nvdb"))  # gelöschte Datei
    dialog = StartDialog()
    assert dialog.ausgewaehlt() == pfade[1]
    assert dialog.liste.count() == 3
    assert zuletzt_geoeffnet()[0].endswith("weg.nvdb")


def test_startdialog_fremde_sperre(app, db, monkeypatch):
    from notenverwaltung.ui import startdialog

    db.schliessen()
    sperrdatei(db.pfad).write_text('{"rechner": "Lehrerzimmer", "pid": 1, "seit": "heute"}')
    merke_geoeffnet(str(db.pfad))
    d = startdialog.StartDialog()
    d.passwort.setText(PW)
    monkeypatch.setattr(startdialog, "frage", lambda *a, **k: False)
    d._oeffnen()
    assert d.datenbank is None
    monkeypatch.setattr(startdialog, "frage", lambda *a, **k: True)
    d.passwort.setText(PW)
    d._oeffnen()
    assert d.datenbank is not None
    d.datenbank.schliessen()


def test_wiederherstellen_mit_code(app, db):
    from notenverwaltung.ui.startdialog import WiederherstellenDialog

    db.schliessen()
    w = WiederherstellenDialog(db.pfad)
    ok = w.knoepfe.button(w.knoepfe.StandardButton.Ok)
    assert not ok.isEnabled()
    w.code.setText(db.code.lower().replace("-", " "))
    w.pw1.setText("Neues Passwort 42")
    w.pw2.setText("Neues Passwort 42")
    assert ok.isEnabled()
    w._entsperren()
    assert w.datenbank is not None
    w.datenbank.schliessen()
    Datenbank.oeffnen(db.pfad, PASSWORT, "Neues Passwort 42").schliessen()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, PASSWORT, PW)


def test_wiederherstellen_falscher_code(app, db):
    from notenverwaltung.speicher.krypto import neuer_wiederherstellungscode
    from notenverwaltung.ui.startdialog import WiederherstellenDialog

    db.schliessen()
    w = WiederherstellenDialog(db.pfad)
    assert not w.mit_datei.isEnabled()  # keine Schlüsseldatei eingerichtet
    w.code.setText(neuer_wiederherstellungscode())
    w.pw1.setText("Neues Passwort 42")
    w.pw2.setText("Neues Passwort 42")
    w._entsperren()
    assert w.datenbank is None
    assert "passt nicht" in w.meldung.text()


# ---- Hauptfenster und Sicherheit -----------------------------------------------------------------

def test_hauptfenster_mit_datenbank(app, db):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    f = Hauptfenster()
    assert not f.a_speichern.isEnabled()
    f.setze_datenbank(db)
    assert f.windowTitle().startswith("Klasse")
    assert f.stapel.currentWidget() is f.uebersicht
    assert f.a_speichern.isEnabled() and not f.a_schluesseldatei_weg.isEnabled()
    db.setze_meta("x", "1")
    assert db.geaendert
    f._autospeichern()
    assert not db.geaendert
    assert f.schliesse_datenbank()
    assert f.db is None and not sperrdatei(db.pfad).exists()
    assert f.stapel.currentWidget() is f.willkommen


def test_passwort_aendern_dialog(app, db):
    from notenverwaltung.ui.sicherheit import PasswortAendernDialog

    d = PasswortAendernDialog(db)
    d.alt.setText("falsch")
    d.pw1.setText("Ganz neues Passwort")
    d.pw2.setText("Ganz neues Passwort")
    d._aendern()
    assert "falsch" in d.meldung.text()
    d.alt.setText(PW)
    d._aendern()
    assert d.result() == d.DialogCode.Accepted
    db.schliessen()
    Datenbank.oeffnen(db.pfad, PASSWORT, "Ganz neues Passwort").schliessen()


def test_neues_notfallblatt_im_hauptfenster(app, db, monkeypatch):
    from notenverwaltung.ui import hauptfenster

    gezeigt = []
    monkeypatch.setattr(hauptfenster, "frage", lambda *a, **k: True)
    monkeypatch.setattr(hauptfenster.NotfallDialog, "exec", lambda self: gezeigt.append(self.anzeige.code))
    f = hauptfenster.Hauptfenster()
    f.setze_datenbank(db)
    f.neues_notfallblatt()
    assert gezeigt and gezeigt[0] != db.code
    f.schliesse_datenbank()
    with pytest.raises(EntschluesselungsFehler):
        Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, db.code)
    Datenbank.oeffnen(db.pfad, WIEDERHERSTELLUNG, gezeigt[0]).schliessen()


def test_schluesseldatei_im_hauptfenster(app, db, tmp_path, monkeypatch):
    from notenverwaltung.speicher.tresor import SCHLUESSELDATEI
    from notenverwaltung.ui import hauptfenster

    monkeypatch.setattr(hauptfenster, "frage", lambda *a, **k: True)
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        staticmethod(lambda *x, **k: (str(tmp_path / "stick"), "")))
    f = hauptfenster.Hauptfenster()
    f.setze_datenbank(db)
    f.schluesseldatei_anlegen()
    assert f.a_schluesseldatei_weg.isEnabled()
    f.schliesse_datenbank()
    Datenbank.oeffnen(db.pfad, SCHLUESSELDATEI, (tmp_path / "stick.nvkey").read_bytes()).schliessen()
