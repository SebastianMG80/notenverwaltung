"""Feste Texte, die an mehreren Stellen erscheinen (Dialoge, Notfallblatt, Handbuch)."""

DATENSCHUTZ_TITEL = "Hinweis zum Datenschutz"

DATENSCHUTZ = (
    "Personenbezogene Daten von Schüler:innen dürfen auf privaten Geräten von Lehrkräften nur mit "
    "Genehmigung der Schulleitung verarbeitet werden (in NRW geregelt in der VO-DV I). "
    "Bitte hol diese Genehmigung ein, bevor du echte Daten einträgst.\n\n"
    "Das Programm unterstützt die geforderten technischen Maßnahmen: Die Datenbank wird verschlüsselt "
    "gespeichert, und das Programm sendet von sich aus keine Daten. Für den sorgfältigen Umgang – sicheres "
    "Passwort, Bildschirmsperre, Aufbewahrung von Ausdrucken – bleibt die Lehrkraft verantwortlich."
)

PASSWORT_MINDESTLAENGE = 10

NOTFALL_ERKLAERUNG = (
    "Mit dem Wiederherstellungscode lässt sich die Datenbank öffnen, wenn das Passwort vergessen wurde. "
    "Wer den Code besitzt, kann alle Noten lesen – bewahre das Notfallblatt deshalb getrennt vom Rechner "
    "sicher auf (z. B. in einem verschlossenen Ordner zu Hause)."
)

NOTFALL_SCHRITTE = [
    "Notenverwaltung starten und die Datenbank auswählen.",
    "Auf „Passwort vergessen?“ klicken.",
    "Den Wiederherstellungscode eingeben (Groß-/Kleinschreibung und Bindestriche sind egal).",
    "Ein neues Passwort festlegen.",
]

NOTFALL_ERSATZ = (
    "Notfallblatt verloren? Im Programm unter Datei → Sicherheit → „Neues Notfallblatt …“ einen neuen Code "
    "erzeugen. Der alte Code ist danach ungültig."
)
