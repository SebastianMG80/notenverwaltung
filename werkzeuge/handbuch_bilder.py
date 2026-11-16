"""Bildschirmfotos für das Handbuch – mit einer Beispieldatenbank (nur erfundene Namen).

    python werkzeuge/handbuch_bilder.py            # alle Bilder nach handbuch/bilder/
    python werkzeuge/handbuch_bilder.py sitzplan   # nur Bilder, deren Name „sitzplan“ enthält

Läuft ohne Bildschirm (Qt „offscreen“) im hellen Design. Nummerierte rote Markierungen zeigen die Bedienelemente,
auf die sich der Text im Handbuch bezieht (①, ②, …). Nach Programmänderungen einfach neu ausführen und danach
`werkzeuge/handbuch_pdf.py` für die PDF.
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "src"))

from PySide6.QtCore import QPoint, QRect, QSettings, Qt  # noqa: E402

QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

from PySide6.QtGui import QColor, QFont, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

ZIEL = WURZEL / "handbuch" / "bilder"
HEUTE = date(2026, 11, 16)
PASSWORT = "Beispiel für das Handbuch 2026"
ROT = QColor("#d62828")

VORNAMEN_NACHNAMEN_82 = [
    ("Adler", "Ben"), ("Bauer", "Clara"), ("Çelik", "Deniz"), ("Dietrich", "Emil"), ("Engel", "Fiona"),
    ("Fischer", "Greta"), ("Günther", "Hannes"), ("Hoffmann", "Ida"), ("Ivanova", "Jana"), ("Jansen", "Karl"),
    ("Krüger", "Lea"), ("Lehmann", "Mats"), ("Meyer", "Nele"), ("Nowak", "Oskar"), ("Öztürk", "Ayşe"),
    ("Peters", "Paul"), ("Quast", "Rosa"), ("Richter", "Sami"), ("Schulz", "Tilda"), ("Thomsen", "Urs"),
    ("Ulrich", "Vera"), ("Vogt", "Wiebke"), ("Weiß", "Jörg"), ("Yılmaz", "Zeynep"),
]
NAMEN_81 = [("Arslan", "Mira"), ("Brandt", "Jonas"), ("Claßen", "Elif"), ("Dąbrowski", "Kuba"), ("Eckert", "Lotta"),
            ("Frank", "Malik")]
NAMEN_Q1 = [("Albers", "Jule"), ("Bayraktar", "Can"), ("Conrad", "Merle"), ("Demir", "Leyla"), ("Ernst", "Tobias"),
            ("Fuchs", "Hanna"), ("Graf", "Nico"), ("Haas", "Svenja")]


# ---- Beispieldaten ------------------------------------------------------------------------------------

def beispieldatenbank(ordner: Path):
    from notenverwaltung.modell.arbeiten import Arbeiten
    from notenverwaltung.modell.muendlich import Muendlich
    from notenverwaltung.modell.noten import Note, Punkte
    from notenverwaltung.modell.sitzplan import Sitzplaene
    from notenverwaltung.modell.stammdaten import Lerngruppe, Stammdaten
    from notenverwaltung.modell.stunden import Stunden
    from notenverwaltung.modell.zeugnis import Zeugnis
    from notenverwaltung.speicher.datenbank import Datenbank
    from notenverwaltung.speicher.krypto import KdfParameter

    zufall = random.Random(2026)
    db, code = Datenbank.neu(ordner / "Noten 2026-27", PASSWORT, KdfParameter(1, 1, 8 * 1024))
    db.setze_meta("druck_schule", "Gesamtschule Musterstadt")
    db.setze_meta("druck_lehrkraft", "Frau Beispiel (BE)")
    v = db.verbindung
    sd, ar, mu, zg, st = Stammdaten(v), Arbeiten(v), Muendlich(v), Zeugnis(v), Stunden(v)
    jahr = sd.lege_schuljahr_an("2026/27", date(2026, 8, 1), date(2027, 2, 1), date(2027, 7, 31),
                                quartal2=date(2026, 10, 26))
    ids82 = [sd.lege_schueler_an(jahr.id, n, v_, "8.2", geburtsdatum=date(2012, 1 + i % 12, 1 + i)).id
             for i, (n, v_) in enumerate(VORNAMEN_NACHNAMEN_82)]
    ids81 = [sd.lege_schueler_an(jahr.id, n, v_, "8.1").id for n, v_ in NAMEN_81]
    idsq1 = [sd.lege_schueler_an(jahr.id, n, v_, "Q1").id for n, v_ in NAMEN_Q1]
    sd.abgang(ids82[19], jahr.id, date(2026, 10, 9))                                   # Thomsen verlässt die Schule

    d82 = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "D 8.2", "Deutsch", "klasse", 8, "D"))
    sd.uebernimm_klasse(d82.id, "8.2")
    m8 = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "M8.3E", "Mathematik", "kurs", 8, "M", "E"))
    sd.fuege_hinzu(m8.id, ids82[:12] + ids81)
    ek = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "EK 8.2", "Erdkunde", "klasse", 8, "EK", schriftlich=False))
    sd.uebernimm_klasse(ek.id, "8.2")
    lk = sd.lege_lerngruppe_an(Lerngruppe(0, jahr.id, "Q1 D-LK", "Deutsch", "kurs", 12, "D", kursart="LK",
                                          notensystem="sek2"))
    sd.fuege_hinzu(lk.id, idsq1)

    # Deutsch 8.2: zwei Arbeiten
    a1 = ar.lege_arbeit_an(d82.id, "1. Klassenarbeit", date(2026, 9, 29), [("1", 10), ("2a", 6), ("b", 4), ("3", 20)],
                           rueckgabe=date(2026, 10, 13), thema="Argumentieren und Erörtern")
    x = ar.aufgaben(a1.id)
    ar.setze_aufgaben(a1.id, [
        (x[0].id, "1", 10, "Text erschließen", "Thema und Position des Autors benennen (4 P.), drei Argumente "
                                                 "mit Belegen wiedergeben (6 P.)."),
        (x[1].id, "2a", 6, "Sprachliche Mittel", "Zwei sprachliche Mittel benennen (2 P.) und ihre Wirkung "
                                                   "erklären (4 P.)."),
        (x[2].id, "b", 4, "Wirkung auf Leser:innen", "Wirkung begründet einschätzen (4 P.)."),
        (x[3].id, "3", 20, "Eigene Erörterung", "a) Einleitung mit Hinführung (3 P.). b) Mindestens drei "
                                                 "Argumente mit Beispielen (12 P.). c) Schluss mit Fazit (5 P.)."),
    ])
    x = ar.aufgaben(a1.id)
    for i, sid in enumerate(ids82):
        if i == 19:
            continue
        if i == 6:
            ar.setze_teilnahme(a1.id, sid, status="nachschreiben")
            continue
        if i == 11:
            ar.setze_teilnahme(a1.id, sid, status="fehlt")
            continue
        staerke = 0.35 + 0.6 * zufall.random()
        for aufgabe in x:
            p = round(max(0.0, min(1.0, zufall.gauss(staerke, 0.15))) * aufgabe.max_punkte * 2) / 2
            ar.setze_punkte(aufgabe.id, sid, p)
    ar.setze_teilnahme(a1.id, ids82[0], kommentar="Deine Argumente sind gut belegt. Achte im Schluss darauf, "
                                                  "deine Position noch einmal klar zu nennen.")
    ar.setze_teilnahme(a1.id, ids82[14], kommentar="Sehr überzeugende Erörterung – weiter so, Ayşe!")
    a2 = ar.lege_arbeit_an(d82.id, "2. Klassenarbeit", date(2026, 11, 10), [("1", 12), ("2", 18)],
                           thema="Kurzgeschichten")
    for i, sid in enumerate(ids82[:9]):
        for aufgabe in ar.aufgaben(a2.id):
            ar.setze_punkte(aufgabe.id, sid, round(aufgabe.max_punkte * (0.5 + 0.05 * i) * 2) / 2)

    # Mathematik: eine Arbeit
    a3 = ar.lege_arbeit_an(m8.id, "1. Klassenarbeit", date(2026, 10, 6), [("1a", 4), ("b", 4), ("2", 8), ("3", 9)],
                           thema="Terme und Gleichungen")
    for sid in ids82[:12] + ids81:
        s = 0.3 + 0.65 * zufall.random()
        for aufgabe in ar.aufgaben(a3.id):
            ar.setze_punkte(aufgabe.id, sid, round(max(0, min(1, zufall.gauss(s, 0.2))) * aufgabe.max_punkte * 2) / 2)

    # Oberstufe: eine Klausur
    k1 = ar.lege_arbeit_an(lk.id, "1. Klausur", date(2026, 10, 1), [("1", 40), ("2", 60)],
                           thema="Lyrik der Romantik")
    for sid in idsq1:
        s = 0.35 + 0.6 * zufall.random()
        for aufgabe in ar.aufgaben(k1.id):
            ar.setze_punkte(aufgabe.id, sid, round(max(0, min(1, zufall.gauss(s, 0.1))) * aufgabe.max_punkte))

    # Mündliche Noten, Schnellerfassung, Zeugnisnoten
    noten = ["1-", "2+", "2", "2-", "3+", "3", "3-", "4+", "4"]
    for g, ids in ((d82, ids82), (ek, ids82)):
        zs = mu.zeitraeume(g.id)
        for k, sid in enumerate(ids):
            if k == 19:
                continue
            mu.setze_note(zs[0].id, sid, Note.aus_kurz(zufall.choice(noten)),
                          "Referat über Klimazonen" if (g is ek and k == 3) else None)
            if g is d82 and k % 3:
                mu.setze_note(zs[1].id, sid, Note.aus_kurz(zufall.choice(noten)))
    for z in mu.zeitraeume(lk.id)[:1]:
        for sid in idsq1:
            mu.setze_note(z.id, sid, Punkte.aus_punkte(zufall.randint(5, 14)))
    for tag in (date(2026, 10, 29), date(2026, 11, 5), date(2026, 11, 12)):
        for sid in zufall.sample(ids82[:19] + ids82[20:], 7):
            st.setze(ek.id, sid, tag, zufall.choice([1, 2, 2, 3, 3, 4, 5]),
                     "Karte sehr gut erklärt" if tag.day == 5 and sid == ids82[2] else None)
    zg.uebernimm_vorschlaege(d82.id, "q1")
    zg.uebernimm_vorschlaege(lk.id, "q1")

    # Sitzplan
    sp = Sitzplaene(v)
    raum = sp.lege_an(ek.id, "Raum 112")
    sp.verteile(raum.id, [m for m in sd.mitglieder(ek.id) if m.aktiv_am(HEUTE)])
    db.speichern()
    return db, code, jahr, {"d82": d82, "m8": m8, "ek": ek, "lk": lk, "a1": a1, "a2": a2, "k1": k1,
                            "ids82": ids82}


# ---- Bilder -------------------------------------------------------------------------------------------

def warte(ms: int = 60) -> None:
    from PySide6.QtCore import QEventLoop, QTimer

    schleife = QEventLoop()
    QTimer.singleShot(ms, schleife.quit)
    schleife.exec()
    QApplication.processEvents()


def foto(name: str, fenster: QWidget, marken: list[tuple[QWidget | QRect, str]] = (), filter_: str = "") -> None:
    """Speichert ein Bild des Fensters, mit nummerierten Markierungen um die angegebenen Bedienelemente."""
    if filter_ and filter_ not in name:
        return
    warte()
    bild = fenster.grab()
    if marken:
        p = QPainter(bild)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        schrift = QFont(fenster.font())
        schrift.setBold(True)
        schrift.setPointSizeF(10)
        p.setFont(schrift)
        for ziel, text in marken:
            if isinstance(ziel, QRect):
                r = QRect(ziel)
            else:
                ecke = ziel.mapTo(fenster, QPoint(0, 0))
                r = QRect(ecke, ziel.size())
            r.adjust(-3, -3, 3, 3)
            p.setPen(QPen(ROT, 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r, 6, 6)
            kreis = QRect(r.left() - 11, r.top() - 11, 22, 22)
            p.setBrush(ROT)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(kreis)
            p.setPen(QColor("white"))
            p.drawText(kreis, int(Qt.AlignmentFlag.AlignCenter), text)
        p.end()
    ZIEL.mkdir(parents=True, exist_ok=True)
    bild.save(str(ZIEL / f"{name}.png"))
    print("  ", name)


def main(filter_: str = "") -> int:
    from notenverwaltung.app import erzeuge_anwendung
    from notenverwaltung.einstellungen import merke_geoeffnet, setze_arbeiten_optionen, setze_design_name

    setze_design_name("hell")
    setze_arbeiten_optionen(True, True, 80, 50)
    app = erzeuge_anwendung([])
    import shutil

    basis = Path(tempfile.gettempdir()) / "Handbuch"
    shutil.rmtree(basis, ignore_errors=True)
    ordner = basis / "Dokumente" / "Noten"
    ordner.mkdir(parents=True)
    db, code, jahr, b = beispieldatenbank(ordner)
    merke_geoeffnet(str(db.pfad))

    from notenverwaltung.modell.arbeiten import Arbeiten
    from notenverwaltung.ui.hauptfenster import Hauptfenster

    f = Hauptfenster()
    f.resize(1120, 700)
    f.show()
    f.setze_datenbank(db)
    f.wechsle_schuljahr(jahr)
    db.verlauf.leeren()                     # das Anlegen der Beispieldaten gehört nicht ins Menü „Rückgängig“
    a1x = Arbeiten(db.verbindung).aufgaben(b["a1"].id)[0]
    Arbeiten(db.verbindung).setze_punkte(a1x.id, b["ids82"][1], 7)
    db.verlauf.abschliessen()
    F = filter_

    # Start und Datenbank
    from notenverwaltung.ui.startdialog import StartDialog

    d = StartDialog(f)
    d.show()
    foto("01_startdialog", d, filter_=F)
    d.close()
    from notenverwaltung.ui.neue_datenbank import NeueDatenbankAssistent

    w = NeueDatenbankAssistent(f)
    w.resize(760, 560)
    w.show()
    foto("02_neue_datenbank", w, filter_=F)
    w.close()
    from notenverwaltung.ui.notfall import NotfallDialog

    nd = NotfallDialog(db.name, code, f)
    nd.show()
    foto("03_notfallblatt", nd, filter_=F)
    nd.reject = lambda: None
    nd.hide()

    # Schuljahr mit offenen Punkten, Schüler:innen
    f._navigation_fuellen(("jahr", None))
    f.seite_jahr.offene_punkte_laden(heute=HEUTE)
    foto("04_schuljahr_offene_punkte", f, [(f.navigation, "1"), (f.seite_jahr.offen, "2")], filter_=F)
    from notenverwaltung.ui.stammdaten_dialoge import LerngruppeDialog, SchuljahrDialog

    sj = SchuljahrDialog(f.sd, jahr, f)
    sj.show()
    foto("05_schuljahr_dialog", sj, filter_=F)
    sj.close()
    f._navigation_fuellen(("schueler", None))
    s = f.seite_schueler
    s.tabelle.selectRow(14)
    foto("06_schueler", f, [(s.k_bogen, "1")], filter_=F)
    from notenverwaltung.ui.import_assistent import ImportAssistent

    ia = ImportAssistent(f.sd, jahr, parent=f)
    ia.resize(820, 560)
    ia.show()
    foto("07_import", ia, filter_=F)
    ia.close()

    # Lerngruppen
    lg = LerngruppeDialog(f.sd, jahr, b["m8"], parent=f)
    lg.show()
    foto("08_lerngruppe_dialog", lg, filter_=F)
    lg.close()
    f.oeffne_gruppe(b["d82"].id, "mitglieder")
    foto("09_mitglieder", f, [(f.seite_gruppe.reiter.tabBar(), "1")], filter_=F)

    # Klassenarbeiten
    f.oeffne_gruppe(b["d82"].id, "arbeiten", b["a1"].id)
    t = f.seite_gruppe.arbeiten
    t.raster.setCurrentIndex(t.modell.index(3, 7))
    foto("10_klassenarbeit", f, [(t.auswahl, "1"), (t.raster, "2"), (t.spiegel, "3"), (t.analyse, "4"),
                                (t.k_rueckmeldung, "5"), (t.k_drucken, "6")], filter_=F)
    from notenverwaltung.ui.arbeit_dialoge import ArbeitDialog, SchluesselDialog

    ar = Arbeiten(db.verbindung)
    ad = ArbeitDialog(ar, jahr, b["d82"], ar.arbeit(b["a1"].id), f)
    ad.resize(900, 640)
    ad.show()
    foto("11_arbeit_dialog", ad, filter_=F)
    ad.close()
    a1 = ar.arbeit(b["a1"].id)
    sd_ = SchluesselDialog(ar, a1.schluessel, sum(x.max_punkte for x in ar.aufgaben(a1.id)), f)
    sd_.show()
    foto("12_notenschluessel", sd_, filter_=F)
    sd_.close()
    from notenverwaltung.ui.ki_dialog import KiDialog

    kd = KiDialog(ar, jahr, b["d82"], parent=f)
    kd.resize(900, 640)
    kd.show()
    foto("13_ki_vorlage", kd, filter_=F)
    kd.close()
    from notenverwaltung.ui.druck import DruckDialog

    dd = DruckDialog(ar, a1, f)
    dd.resize(1200, 760)
    dd.show()
    dd.art_liste.setChecked(True)
    foto("14_druck_punkteliste", dd, filter_=F)
    dd.art_abschnitte.setChecked(True)
    foto("15_druck_etiketten", dd, [(dd.box_abschnitte, "1")], filter_=F)
    dd.art_bogen.setChecked(True)
    foto("16_druck_rueckmeldebogen", dd, [(dd.box_bogen, "1")], filter_=F)
    dd.close()
    from notenverwaltung.ui.rueckmeldung_dialog import RueckmeldungDialog

    ids = [e.mitglied.schueler.id for e in t.modell.ergebnisse]
    rd = RueckmeldungDialog(ar, a1, b["d82"], ids, ids.index(b["ids82"][0]), f)
    rd.show()
    foto("17_rueckmeldungen", rd, [(rd.text, "1"), (rd.liste, "2"), (rd.k_vorschlag, "3"), (rd.vor, "4")],
         filter_=F)
    rd.close()
    from notenverwaltung.modell.rueckmeldung import Textbausteine
    from notenverwaltung.ui.textbausteine_dialog import TextbausteineDialog

    tb = TextbausteineDialog(Textbausteine(db.verbindung), "Deutsch", f)
    tb.show()
    foto("18_textbausteine", tb, filter_=F)
    tb.close()

    # Mündlich, Schnellerfassung, Sitzplan
    f.oeffne_gruppe(b["ek"].id, "muendlich")
    m = f.seite_gruppe.muendlich
    foto("19_muendlich", f, [(m.raster, "1")], filter_=F)
    s = f.seite_gruppe
    s.reiter.setCurrentWidget(s.stunden)
    sz = s.stunden
    sz.zeitraum.setCurrentIndex(1)
    foto("20_schnellerfassung", f, [(sz.datum, "1"), (sz.k_uebernehmen, "2")], filter_=F)
    s.reiter.setCurrentWidget(s.sitzplan)
    sp = s.sitzplan
    sp.datum.setze(date(2026, 11, 12))
    sp.modi.button(1).click()
    foto("21_sitzplan_personen", f, [(sp.modi.button(0), "1"), (sp.modi.button(1), "2"), (sp.modi.button(2), "3"),
                                     (sp.liste, "4")], filter_=F)
    sp.modi.button(2).click()
    foto("22_sitzplan_bewerten", f, filter_=F)
    sp.modi.button(0).click()
    foto("23_sitzplan_tische", f, [(sp.werkzeuge, "1")], filter_=F)

    # Noten
    f.oeffne_gruppe(b["d82"].id, "noten")
    n = f.seite_gruppe.noten
    foto("24_noten", f, [(n.zeitraum, "1"), (n.ansicht, "2")], filter_=F)
    n.ansicht.setCurrentIndex(1)
    foto("25_noten_einzeln", f, filter_=F)
    n.ansicht.setCurrentIndex(0)
    from notenverwaltung.modell.zeugnis import Zeugnis
    from notenverwaltung.ui.seiten.noten_tab import GewichtungDialog

    gd = GewichtungDialog(Zeugnis(db.verbindung), b["d82"], f)
    gd.show()
    foto("26_gewichtung", gd, filter_=F)
    gd.close()
    f.oeffne_gruppe(b["lk"].id, "arbeiten")
    foto("27_oberstufe", f, filter_=F)

    # Übersichten
    from notenverwaltung.ui.nachschreib_dialog import NachschreibDialog
    from notenverwaltung.ui.schnellsuche import SchnellsucheDialog

    nd2 = NachschreibDialog(ar, jahr, f)
    nd2.show()
    foto("28_nachschreibliste", nd2, filter_=F)
    nd2.close()
    sd2 = SchnellsucheDialog(f.sd, jahr, f)
    sd2.feld.setText("öz")
    sd2.show()
    foto("29_schnellsuche", sd2, filter_=F)
    sd2.close()
    from notenverwaltung.ui.personenbogen_dialog import personenbogen_dialog

    pb = personenbogen_dialog(db.verbindung, b["ids82"][14], f)
    pb.show()
    foto("30_schuelerbogen", pb, filter_=F)
    pb.close()

    # Jahreswechsel, Einstellungen, Sperre, Hilfe
    from notenverwaltung.ui.jahreswechsel_assistent import JahreswechselAssistent

    jw = JahreswechselAssistent(f.sd, jahr, f)
    jw.resize(860, 600)
    jw.show()
    foto("31_jahreswechsel", jw, filter_=F)
    jw.close()
    from notenverwaltung.ui.einstellungen_dialog import EinstellungenDialog

    ed = EinstellungenDialog(f)
    ed.show()
    foto("32_einstellungen", ed, filter_=F)
    ed.close()
    f._navigation_fuellen(("jahr", None))
    f.sperren("Nach 15 Minuten ohne Eingabe automatisch gesperrt.")
    foto("33_sperre", f, filter_=F)
    f.sperre.aufheben()
    from notenverwaltung.hilfe.fenster import zeige_hilfe

    h = zeige_hilfe("arbeiten")
    foto("34_hilfe", h, filter_=F)
    h.close()
    for name, menue in (("35_menue_bearbeiten", f.m_bearbeiten), ("36_menue_uebersichten", f.m_uebersichten),
                        ("37_menue_sicherheit", f.m_sicherheit)):
        menue.popup(f.mapToGlobal(QPoint(40, 40)))
        warte(120)
        foto(name, menue, filter_=F)
        menue.hide()

    f.db = None
    db.schliessen(speichern=False)
    from notenverwaltung.app import abbauen

    del f
    abbauen(app)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
