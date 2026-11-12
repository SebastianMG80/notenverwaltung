Allgemeines Notentool zur Verwaltung von Noten, Bewertung von Klassenarbeiten, Erstellung von Übersichten und Erzeugung von Notenvorschlägen
Ein auf Linux lauffähiges Programm (KDE6.8 muss auf jeden Fall unterstützt werden), Portierung auf Windows wird zeitnah folgen. Beide Versionen müssen zueinander 100% kompatibel sein.

#Allgemeine Struktur
Das Programm ist in Schuljahren strukturiert. Beim Programmstart wird das aktuelle Schuljahr geladen, im Menü Datei kann man zu alten Jahren zurückwechseln.
Unterhalb des Jahres liegen die Fächer. Diese können schriftlich oder mündlich sein - bei schriftlichen Fächern zählen die Arbeiten eines Halbjahres ca. 50% der Note.
Im zweiten Halbjahr zählt die Note des ersten Halbjahres zu 5-10% zur Note - Ausnahme sind die Fächer Deutsch, Englisch, Mathematik in Jahrgang 10, dort gibt es im zweiten Halbjahr eine komplette Ganzjahresnote, welche zu 50% über die Zeugnisnote entscheidet. Die restlichen 50% kommen von der ZP10.

#Funktionen
Korrektur von Klassenarbeiten: Schülerliste, Liste der Aufgaben, siehe Punkteliste.ods. Ausgabe von Notenabschnitten für die Schüler soll ebenfalls möglich sein, aber auch ein ausführlicher Rückmeldebogen (eine Seite pro Person).
Notenspiegel für Klassen / Kurse. Halbjahresweise, aber auch ganzjährig.
Eingabe von mündlichen Noten für verschiedene Zeiträume. Standard ist Quartal, aber auch feiner Abstufungen müssen möglich sein.
Druck sämtlicher Listen mit nützlichen Funktionen (ausblenden leerer Zeilen, Hervorhebungen usw.), Erstellung von PDF Dateien zum späteren Ausdruck. Übersichten verschiedener Art usw.

#Datenbehandlung
Start des Programms gibt Auswahl über zu öffnende Datenbank. Letzte Datenbank ist Standard, aber auch andere oder neue Datenbank sind möglich.
Datenbanken sind sicher verschlüsselt abzuspeichern. Das Passwort wird beim Öffnen der Datenbank abgefragt. Eine Art Notfallschlüssel zur Entsperrung muss implementiert werden. Dazu hätte ich gerne Vorschläge von dir.
Die Daten bleiben zu 100% lokal und das Programm offline.
Datenbanken können an andere Rechner mit dem Programm kopiert und dort normal genutzt werden.
Schüler haben einen Jahrgang und eine Klasse, die ihnen zugewiesen werden. Zum Beispiel "Hans Muster, Klasse 8.4" ist Schüler des 8.Jahrgangs und geht dort in die Klasse 8.4.

#Komfortfunktionen
Arbeiten, die mit KI erstellt werden, sollen direkt einen Vorschlag zur Bepunktung, eine Musterlösung und daraus erzeugt alle Daten für einen Rückmeldebogen mitliefern.
Eine entsprechende Vorlage für den Prompt liefert das Programm selbst und die so erzeugten Daten können in eine bestehende Gruppe eingelesen werden.
Klassen / Kurse können von Hand eingegeben werden, aber auch andere Listenformate können genutzt werden. Neu hinzukommende Schüler können zu beliebigen Zeitpunkten sinnvoll integriert werden. Abgänge von Schülern im laufenden Schuljahr können sinnvoll eingegeben werden. Daten bleiben erhalten, aber bei danach liegenden Noten wird keine Eingabe mehr erwartet / unterstützt.
Sortierung von Schülern in Kursen (diese sind klassenübergreifend) ist nach Alphabet und auch erst nach Klasse, dann nach Alphabet möglich (Standard!). Eigene Reihenfolgen sollen auch möglich sein.
Sämtliche Übersichten und Ausgaben (Druckform) sollen anpassbar sein. Dazu wird eine Art Editor benötigt, der ganz simpel zu bedienen ist und nicht überladen ist.
Ausdruck kleiner Notenabschnitte, wie in der angefügten Tabelle Punkteliste.ods sollen von der Größe anpassbar sein. Als fester Vorschlag soll eine Größe für Avery Zweckform Etiketten 3425 und 3424 angeboten und korrekt umgesetzt werden.

#Allgemeines
Erscheinungsbild des Programm nüchtern, aber freundlich. Design lieber dunkel als hell, aber veränderbar. Auch hinsichtlich Schriftarten.
Gegendert wird mit : (Lehrer:innen).

#Klärungen (12.11.2026)
- Technik: Python + Qt (PySide6, LGPL; Ersatz PyQt6). Ein Code für Linux und Windows, dadurch identisches Dateiformat.
- Offline: Das fertige Programm sendet von sich aus nie etwas nach außen (keine Netzwerkzugriffe im Code). Die Entwicklung liegt in einem eigenen privaten GitHub-Repo.
- Datenbank: eine verschlüsselte Datei (AES-256-GCM, Schlüssel per Argon2id aus dem Passwort). Zufälliger Hauptschlüssel, zweifach hinterlegt: mit Passwort und mit Wiederherstellungscode.
- Notfallschlüssel: 24-stelliger Wiederherstellungscode, ausgegeben als Notfallblatt (PDF mit QR-Code). Optional zusätzlich eine Schlüsseldatei (z. B. USB-Stick).
- Datenschutz: Beim Anlegen einer Datenbank Hinweis anzeigen (Verarbeitung auf privaten Geräten nur mit Genehmigung der Schulleitung, VO-DV I NRW) und denselben Hinweis auf das Notfallblatt drucken.
- Speicherort: Warnung, wenn die Datenbank in einem synchronisierten Cloud-Ordner liegt.
- Druckanpassung: zunächst einfache Variante (Vorlagen mit ein-/ausschaltbaren Bausteinen, Schriften, Hervorhebungen, Live-Vorschau). Der freie Layout-Editor folgt später.
- Notenabschnitte: Spaltenbreite passt sich den tatsächlich genutzten Aufgaben an. Die Schrift bleibt dabei lesbar. Avery Zweckform 3424/3425 als feste Vorlagen.
- KI-Import: Das Programm liefert eine Prompt-Vorlage. Die Antwort (JSON) wird manuell eingelesen. Keine Schülerdaten im Prompt.
- Gewichtungen pro Fach einstellbar (Standardwerte aus dem Lastenheft). Das Programm schlägt vor, die Lehrkraft setzt fest.
- E-/G-Kurse: werden vermerkt, haben vorerst keine Auswirkung auf Schlüssel oder Berechnung.
- Sek II (0–15 Punkte): im Datenmodell vorbereiten, Umsetzung später.
- Notenschlüssel: Prozenttabelle aus Punkteliste.ods ist Standard, pro Arbeit einstellbar. Intern mit Tendenz gerechnet: „+“ = −0,3, „−“ = +0,3 (gut+ = 1,7, gut− = 2,3). Bei schriftlichen Arbeiten wird an Schüler:innen keine Tendenz ausgegeben (nur „gut“).
- ZP10: wird als eine feste Note eingetragen.
- Import: alle genannten Formate – CSV, Excel (.xlsx), ODS, SchILD-NRW-Export, Untis-Export.
- Schuljahreswechsel: Übernahme wird angeboten (z. B. 8.4 → 9.4). Dabei können Schüler:innen wegfallen und hinzukommen.
- Windows: zunächst ein Build. Den Test macht Sebastian selbst.
