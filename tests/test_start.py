"""Grundgerüst: Fenster startet, Design ist umschaltbar und wird gemerkt."""

from notenverwaltung import APP_NAME
from notenverwaltung.einstellungen import design_name


def test_hauptfenster_startet(app):
    from notenverwaltung.ui.hauptfenster import OFFLINE_HINWEIS, Hauptfenster

    fenster = Hauptfenster()
    fenster.show()
    app.processEvents()
    assert fenster.windowTitle() == APP_NAME
    assert fenster.statusBar().currentMessage() == OFFLINE_HINWEIS
    titel = [m.title().replace("&", "") for m in fenster.menuBar().findChildren(type(fenster.menuBar().addMenu("x")))]
    assert {"Datei", "Ansicht", "Hilfe"} <= set(titel)
    fenster.close()


def test_standard_ist_dunkel(app):
    assert design_name() == "dunkel"
    assert app.property("design") == "dunkel"
    hell = app.palette().window().color().lightness()
    assert hell < 80, "Dunkles Design erwartet"


def test_design_wechsel_wird_gemerkt(app):
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    fenster = Hauptfenster()
    fenster.setze_design("hell")
    assert design_name() == "hell"
    assert app.palette().window().color().lightness() > 200
    fenster.setze_design("dunkel")
    assert design_name() == "dunkel"
    fenster.close()


def test_unbekanntes_design_faellt_auf_dunkel_zurueck(app):
    from notenverwaltung.einstellungen import einstellungen

    einstellungen().setValue("ansicht/design", "pink")
    assert design_name() == "dunkel"
