"""Hilfetexte: eine Seite je Thema, als einfaches HTML (wird im Programm mitgeliefert, nichts wird geladen).

Verweise zwischen Seiten: <a href="#schluessel">. Keine Verweise ins Internet – das Programm bleibt offline.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Thema:
    schluessel: str
    titel: str
    html: str


THEMEN: list[Thema] = [
    Thema("start", "Erste Schritte", """
<h2>Erste Schritte</h2>
<p>Die Notenverwaltung führt deine Noten für ein ganzes Schuljahr: Klassenarbeiten und Klausuren mit Punkten,
mündliche Noten (Sonstige Mitarbeit), Quartals- und Halbjahresnoten mit Vorschlägen – alles in <b>einer
verschlüsselten Datei</b>, die nur auf deinem Rechner liegt.</p>
<ol>
<li><b>Datenbank anlegen</b> (Datei → Neue Datenbank): Datenschutzhinweis lesen, Speicherort wählen, Passwort
festlegen und das <b>Notfallblatt drucken</b>. → <a href="#datenbank">Datenbank und Passwort</a></li>
<li><b>Schuljahr anlegen</b> – es wird passend vorgeschlagen. → <a href="#schuljahr">Schuljahr und Quartale</a></li>
<li><b>Schüler:innen</b> eintragen oder importieren. → <a href="#schueler">Schüler:innen</a>,
<a href="#import">Listen importieren</a></li>
<li><b>Lerngruppen</b> anlegen (Strg+L): eine Klasse in einem Fach oder einen Kurs.
→ <a href="#lerngruppen">Lerngruppen</a></li>
<li>In der Lerngruppe: <a href="#arbeiten">Klassenarbeiten</a>, <a href="#muendlich">mündliche Noten</a> und
<a href="#noten">Noten fürs Zeugnis</a>.</li>
</ol>
<p>Links in der Leiste wählst du Schuljahr, Schüler:innen oder eine Lerngruppe. Das Programm speichert
automatisch (alle 2 Minuten und beim Schließen).</p>
<p><b>Tipp:</b> <b>F1</b> öffnet überall die Hilfe zu der Ansicht, in der du gerade bist.
Hell oder dunkel, Schriftgröße, Kopfzeile der Ausdrucke: → <a href="#darstellung">Darstellung</a></p>
"""),
    Thema("datenbank", "Datenbank und Passwort", """
<h2>Datenbank und Passwort</h2>
<p>Alle Daten stehen in einer Datei mit der Endung <b>.nvdb</b>. Sie ist mit deinem Passwort verschlüsselt
(AES-256). Ohne Passwort, Wiederherstellungscode oder Schlüsseldatei kann niemand sie lesen – auch du nicht.</p>
<h3>Anlegen</h3>
<ul>
<li><b>Datenschutz:</b> Für Schülerdaten auf privaten Geräten brauchst du in NRW die Genehmigung der
Schulleitung (VO-DV I). Der Hinweis steht auch auf dem Notfallblatt.</li>
<li><b>Speicherort:</b> nicht in einem synchronisierten Cloud-Ordner (Nextcloud, OneDrive, Dropbox …). Das
Programm warnt, wenn es einen erkennt.</li>
<li><b>Passwort:</b> mindestens 10 Zeichen. Ein Satz aus mehreren Wörtern ist gut zu merken und sicher.</li>
<li><b>Notfallblatt:</b> enthält den 24-stelligen Wiederherstellungscode (auch als QR-Code). Ausdrucken und
sicher aufbewahren – nicht neben dem Rechner.</li>
</ul>
<h3>Öffnen</h3>
<p>Beim Start erscheint die zuletzt benutzte Datenbank. Mit „Andere Datenbank …“ wählst du eine andere Datei.
Die Datei lässt sich auf einen anderen Rechner kopieren (Linux oder Windows) und dort normal öffnen.</p>
<p>Ist die Datenbank schon woanders geöffnet, warnt das Programm. Öffne sie nie auf zwei Rechnern gleichzeitig.</p>
<h3>Neue Programmversionen</h3>
<p>Neue Versionen öffnen alle älteren Dateien und stellen sie auf das neue Format um. Vorher legt das Programm
die alte Datei als dauerhafte Sicherung ab (<i>…_vor-Umstellung-…</i> im Ordner mit den Sicherungen).
Eine umgestellte Datei lässt sich mit älteren Programmversionen nicht mehr öffnen.</p>
<p>→ <a href="#sicherheit">Sicherheit, Sicherungen und Notfall</a></p>
"""),
    Thema("sicherheit", "Sicherheit, Sicherungen und Notfall", """
<h2>Sicherheit, Sicherungen und Notfall</h2>
<p>Im Menü <b>Datei → Sicherheit</b>:</p>
<ul>
<li><b>Passwort ändern …</b> – Der Wiederherstellungscode bleibt gültig. Auch alle Sicherungen werden auf das
neue Passwort umgestellt.</li>
<li><b>Neues Notfallblatt …</b> – erzeugt einen neuen Wiederherstellungscode; der alte gilt dann nicht mehr.</li>
<li><b>Schlüsseldatei anlegen …</b> – eine zusätzliche Datei (z. B. auf einem USB-Stick), mit der sich die
Datenbank ohne Passwort öffnen lässt. Bewahre sie getrennt vom Rechner auf.</li>
<li><b>Ordner mit Sicherungen anzeigen</b> – Bei jeder Sitzung legt das Programm vor dem ersten Speichern eine
Sicherung an (die letzten 20 bleiben). Eine Sicherung öffnest du wie jede andere Datenbank.</li>
</ul>
<h3>Passwort vergessen?</h3>
<p>Im Startdialog auf <b>„Passwort vergessen?“</b> klicken und den Wiederherstellungscode vom Notfallblatt
eintippen (Groß-/Kleinschreibung und Bindestriche sind egal) oder die Schlüsseldatei wählen. Danach legst du ein
neues Passwort fest.</p>
<p>Ohne Passwort, Code und Schlüsseldatei sind die Daten verloren – es gibt bewusst keine Hintertür.</p>
"""),
    Thema("schuljahr", "Schuljahr und Quartale", """
<h2>Schuljahr und Quartale</h2>
<p>Jedes Schuljahr hat einen Beginn, einen <b>Halbjahreswechsel</b> (erster Tag des 2. Halbjahres) und ein Ende.
Der Halbjahreswechsel entscheidet, welche Noten zum 1. und welche zum 2. Halbjahr zählen.</p>
<h3>Quartale</h3>
<p>Standardmäßig liegt der Quartalswechsel in der Mitte jedes Halbjahres. Unter <b>Datei → Schuljahr →
Schuljahr bearbeiten …</b> kannst du bei „Quartale“ den Haken „automatisch“ entfernen und eigene Daten für den
Beginn des 2. und 4. Quartals eintragen.</p>
<ul>
<li>Eine Arbeit zählt zum Quartal ihres Datums.</li>
<li>Ein mündlicher Zeitraum zählt zum Quartal, in dem er beginnt.</li>
<li>Die mündlichen Zeiträume schon angelegter Lerngruppen bleiben beim Ändern unverändert. Willst du sie
anpassen: Reiter Mündlich → „Zeiträume …“ → „Auf Quartale zurücksetzen“.</li>
</ul>
<p>Zwischen den Schuljahren wechselst du über <b>Datei → Schuljahr</b>. Ein neues Schuljahr kannst du leer anlegen
oder aus dem bisherigen übernehmen. → <a href="#jahreswechsel">Schuljahreswechsel</a></p>
"""),
    Thema("schueler", "Schüler:innen", """
<h2>Schüler:innen</h2>
<p>Unter <b>Schüler:innen</b> (links in der Leiste) stehen alle Schüler:innen des Schuljahres mit ihrer Klasse.
Der Jahrgang ergibt sich aus der Klasse: „8.4“ → 8, „10b“ → 10, Oberstufe „EF“ → 11, „Q1“ → 12, „Q2“ → 13.</p>
<ul>
<li><b>Neu …</b> – einzeln eintragen. Mit „Zugang im laufenden Schuljahr“ kommt jemand später dazu; für die Zeit
davor wird keine Note erwartet.</li>
<li><b>Importieren …</b> – Listen aus CSV, Excel, ODS, SchILD-NRW oder Untis. → <a href="#import">Listen
importieren</a></li>
<li><b>Abgang …</b> – Wer die Schule verlässt, bekommt ein Abgangsdatum. Die Noten bleiben erhalten, danach wird
keine Eingabe mehr erwartet (graue Felder).</li>
</ul>
<p>Die Zuordnung zu Lerngruppen mit Ein- und Austrittsdatum regelst du in der Lerngruppe im Reiter
„Schüler:innen“. → <a href="#lerngruppen">Lerngruppen</a></p>
"""),
    Thema("import", "Listen importieren", """
<h2>Listen importieren</h2>
<p>Der Import-Assistent liest <b>CSV</b>, <b>Excel (.xlsx)</b>, <b>ODS</b> sowie Exporte aus <b>SchILD-NRW</b>
und <b>Untis</b>.</p>
<ol>
<li><b>Datei wählen</b> – Zeichensatz und Trennzeichen werden erkannt.</li>
<li><b>Spalten zuordnen</b> – Nachname, Vorname, Klasse usw. werden anhand der Spaltennamen vorgeschlagen; du
kannst jede Zuordnung ändern. Die Vorschau zeigt, was ankommt.</li>
<li><b>Abgleich</b> – Wer schon da ist, wird erkannt (über die ID aus SchILD bzw. Name und Klasse) und nicht doppelt
angelegt. Gleiche Namen in anderer Klasse werden zur Prüfung übersprungen.</li>
</ol>
<p>Den Import gibt es auch direkt in einer Lerngruppe („Liste importieren …“): Dann landen die Schüler:innen
zusätzlich in dieser Gruppe.</p>
"""),
    Thema("lerngruppen", "Lerngruppen", """
<h2>Lerngruppen</h2>
<p>Eine Lerngruppe ist entweder eine <b>Klasse in einem Fach</b> (z. B. „8.4 Deutsch“) oder ein
<b>klassenübergreifender Kurs</b> (z. B. „M9.3E“). Neu anlegen: Datei → Neue Lerngruppe (Strg+L).</p>
<ul>
<li><b>Kursniveau</b> (Sek I): E- oder G-Kurs – wird nur vermerkt.</li>
<li><b>Kursart</b> (Oberstufe): GK oder LK. Ab Jahrgang 11 (EF) gibt es Punkte statt Noten.
→ <a href="#oberstufe">Oberstufe</a></li>
<li><b>Fachart:</b> schriftlich (mit Klassenarbeiten/Klausuren) oder nur mündlich.</li>
<li>Bei einer Klasse kannst du gleich alle Schüler:innen der Klasse aufnehmen.</li>
</ul>
<h3>Reiter „Schüler:innen“</h3>
<ul>
<li><b>Hinzufügen …</b> – weitere Schüler:innen aufnehmen (Mehrfachauswahl mit Strg oder Umschalt).</li>
<li><b>Eintritt / Austritt …</b> – Wer später dazukommt oder die Gruppe verlässt, bekommt ein Datum. Vorher bzw.
danach wird keine Note erwartet.</li>
<li><b>Sortierung:</b> Klasse, dann Alphabet (Standard), nur Alphabet oder eine eigene Reihenfolge
(mit ▲ ▼ verschieben). Die Sortierung gilt für alle Listen und Ausdrucke der Gruppe.</li>
</ul>
"""),
    Thema("arbeiten", "Klassenarbeiten und Klausuren", """
<h2>Klassenarbeiten und Klausuren</h2>
<p><b>Neue Arbeit …</b>: Titel, Datum, Aufgaben mit Höchstpunkten (auch Teilaufgaben wie 3a, b, c), Thema und
Erwartungshorizont je Aufgabe, Musterlösung. Das Datum bestimmt Halbjahr, Quartal und wer teilnimmt.
Unter „Aufgaben und Einstellungen …“ änderst du das später, auch ob die Arbeit zur Note zählt und mit welchem
Gewicht.</p>
<h3>Punkte eintragen</h3>
<ul>
<li>Einfach lostippen: <b>Enter</b> übernimmt und springt weiter – je nach Einstellung nach rechts (Person für
Person) oder nach unten (Aufgabe für Aufgabe). <b>Tab</b> geht seitlich, <b>Entf</b> leert markierte Felder.</li>
<li>Halbe und Viertelpunkte gehen (2,5 oder 2,25). Zu viele Punkte werden abgelehnt.</li>
<li>Summe und Note erscheinen sofort, rechts der Notenspiegel. Farbig hinterlegt: noch nicht alle Aufgaben eingetragen.</li>
</ul>
<h3>Note ohne Punkte, Vermerke</h3>
<ul>
<li><b>Note direkt eintippen:</b> in die Spalte „Note“ (z. B. 2, 3+ oder 4-; Oberstufe: Punkte 0–15) – etwa bei
Nachschreiber:innen. Ein <b>*</b> markiert eine festgesetzte Note; <b>Entf</b> hebt die Festsetzung auf.</li>
<li><b>Rechtsklick</b> auf eine Zeile: fehlt, schreibt nach, befreit, Note festsetzen, Rückmeldung an die Person
(erscheint auf dem Rückmeldebogen).</li>
</ul>
<p>Schüler:innen sehen bei Klassenarbeiten die Note <b>ohne Tendenz</b> („gut“). Intern wird mit Tendenz gerechnet
(2+ = 1,7; 2- = 2,3).</p>
<p>→ <a href="#schluessel">Notenschlüssel</a> · <a href="#drucken">Drucken</a> · <a href="#ki">KI-Vorlage</a></p>
"""),
    Thema("schluessel", "Notenschlüssel", """
<h2>Notenschlüssel</h2>
<p>Der Schlüssel legt fest, ab welchem Anteil der Höchstpunkte es welche Note gibt. Standard ist die
Prozenttabelle aus der Punkteliste (z. B. ab 85 % eine 1, ab 72 % eine 2). Die Punktgrenzen werden wie in der
Tabellenkalkulation gerundet; auf Wunsch auf halbe oder Viertelpunkte.</p>
<ul>
<li>Jede Arbeit hat ihre <b>eigene Kopie</b> des Schlüssels: Spätere Änderungen an Vorlagen verändern keine
alten Noten.</li>
<li><b>Notenschlüssel …</b> in der Arbeit: Stufen ändern, hinzufügen oder entfernen; die Punktgrenzen siehst du
sofort.</li>
<li><b>Als Vorlage speichern …</b> – für weitere Arbeiten; eine Vorlage kann der Standard für neue Arbeiten
sein.</li>
<li>In der Oberstufe gibt es einen eigenen Standard: den Klausurschlüssel nach NRW-Tabelle.
→ <a href="#oberstufe">Oberstufe</a></li>
</ul>
"""),
    Thema("drucken", "Drucken: Punkteliste, Abschnitte, Rückmeldebogen", """
<h2>Drucken: Punkteliste, Abschnitte, Rückmeldebogen</h2>
<p>In den Klassenarbeiten öffnet <b>„Drucken / PDF …“</b> die Druckvorschau. Links wählst du, was gedruckt wird,
rechts siehst du das Ergebnis. „Als PDF speichern …“ legt eine PDF-Datei an – sie enthält Noten, also bitte
nicht in einer Cloud ablegen.</p>
<ul>
<li><b>Punkteliste</b> (quer): alle Punkte, Summe, Note, Notenspiegel und Schlüssel. Optionen: leere Zeilen
ausblenden, Lücken hervorheben, Tendenz zeigen.</li>
<li><b>Notenabschnitte</b> zum Ausschneiden oder auf Etiketten (Avery Zweckform 3424/3425).
→ <a href="#etiketten">Etiketten</a></li>
<li><b>Rückmeldebögen:</b> eine Seite pro Person mit Aufgaben, Punkten, Erwartungshorizont, Note (ohne Tendenz),
Rückmeldung und auf Wunsch Unterschriftenfeldern.</li>
</ul>
<p>Weitere Ausdrucke: <a href="#muendlich">Liste der mündlichen Noten</a> und
<a href="#noten">Notenübersicht</a>. Schule und Lehrkraft in der Kopfzeile: Datei → Angaben für Ausdrucke.
Die Schrift der Ausdrucke wählst du im Druckdialog. → <a href="#darstellung">Darstellung</a></p>
"""),
    Thema("etiketten", "Notenabschnitte und Etiketten", """
<h2>Notenabschnitte und Etiketten</h2>
<p>Jeder Abschnitt zeigt Name, Aufgaben mit Höchst- und erreichten Punkten, Summe, Datum und die Note ohne
Tendenz. Die Spalten passen sich der Zahl der Aufgaben an; bei sehr vielen Aufgaben wird zweizeilig gedruckt.</p>
<ul>
<li><b>Avery Zweckform 3424</b> (105 × 48 mm, 12 je Bogen) und <b>3425</b> (105 × 57 mm, 10 je Bogen).</li>
<li><b>Frei:</b> eigene Größe auf Normalpapier, mit Schneidelinien.</li>
<li><b>Start bei Etikett:</b> Bei einem angebrochenen Bogen das erste freie Etikett (zeilenweise gezählt).</li>
<li><b>Druckversatz:</b> Trifft der Drucker die Etiketten nicht genau, verschiebst du den Druck in mm
(positiv = nach rechts bzw. unten).</li>
<li><b>Abstand zum Blattrand:</b> Die Etiketten reichen bis an den Papierrand, viele Drucker bedrucken dort aber
4–6 mm nicht. Der Inhalt hält deshalb mindestens 7 mm Abstand. <b>Wird am Rand etwas abgeschnitten, den Wert
erhöhen.</b></li>
</ul>
<p>Tipp: Erst einen Probedruck auf Normalpapier machen und gegen den Etikettenbogen ins Licht halten.</p>
"""),
    Thema("muendlich", "Mündliche Noten (Sonstige Mitarbeit)", """
<h2>Mündliche Noten (Sonstige Mitarbeit)</h2>
<p>Im Reiter <b>Mündlich</b> trägst du Noten je Zeitraum ein. Standard sind die vier Quartale des Schuljahres.</p>
<ul>
<li><b>Eingabe:</b> 2, 2+, 2- oder als Zahl (1,7 → 2+). Oberstufe: Punkte 0–15 (10,5 → 11).
Enter springt nach unten oder nach rechts – oben umschaltbar.</li>
<li><b>Graue Felder:</b> In diesem Zeitraum war die Person nicht in der Gruppe – keine Note nötig.</li>
<li><b>Rechtsklick → Bemerkung:</b> eine Notiz zur Note (✎ in der Zelle).</li>
<li>Rechts stehen die Halbjahresmittel.</li>
</ul>
<h3>Zeiträume</h3>
<p><b>„Zeiträume …“</b>: umbenennen, Grenzen verschieben, in gleich lange Abschnitte teilen, entfernen oder auf die
Quartale zurücksetzen. Ein Zeitraum darf nicht über den Halbjahreswechsel gehen. Beim Entfernen gehen seine Noten
verloren (das Programm fragt vorher).</p>
<h3>Drucken</h3>
<p><b>„Drucken / PDF …“</b>: Liste der mündlichen Noten (mit oder ohne Tendenz, Halbjahresmittel, Bemerkungen) oder
eine <b>leere Liste zum Eintragen</b> von Hand. Bei vielen Zeiträumen automatisch im Querformat.</p>
"""),
    Thema("noten", "Noten: Quartale, Halbjahre, Zeugnis", """
<h2>Noten: Quartale, Halbjahre, Zeugnis</h2>
<p>Der Reiter <b>Noten</b> zeigt die Noten in der Reihenfolge der Abgabe: <b>1. Quartal – 1. Halbjahr –
3. Quartal – 2. Halbjahr</b>. Je Abschnitt: schriftlicher und mündlicher Schnitt, ein <b>Vorschlag</b> und die
Note, die du festsetzt.</p>
<h3>Wie der Vorschlag entsteht</h3>
<ul>
<li>Halbjahr: Anteil schriftlich × Schnitt der Arbeiten + Rest × Schnitt der mündlichen Noten. Standard 50 % in
schriftlichen Fächern, 0 % in mündlichen.</li>
<li>2. Halbjahr: Die Note des 1. Halbjahres zählt mit (Standard 10 %).</li>
<li>Quartal: nur die Leistungen dieses Quartals, gewichtet wie das Halbjahr.</li>
<li>Fahre mit der Maus über einen Vorschlag, um die vollständige Herleitung zu sehen.</li>
<li><b>Gewichtung …</b> ändert die Anteile für diese Lerngruppe.</li>
</ul>
<h3>Festsetzen</h3>
<ul>
<li>In die fett gedruckten Spalten tippen (z. B. 2 oder 2-), <b>Entf</b> löscht. Weicht eine Note deutlich vom
Vorschlag ab, wird sie farbig markiert.</li>
<li><b>Vorschläge übernehmen ▾</b>: Quartalsnoten mit Tendenz, Halbjahresnoten als ganze Note (genau ,5 wird
zur besseren Note: 2,5 → 2). Wahlweise nur leere Felder.</li>
</ul>
<h3>Ansicht</h3>
<ul>
<li><b>Zeitraum:</b> ganzes Jahr oder ein Halbjahr (Standard: das laufende).</li>
<li><b>Ansicht „mit Einzelnoten“:</b> jede Arbeit und jeder mündliche Zeitraum als eigene Spalte, jeweils vor der
Note, zu der sie zählen. Graue Einträge zählen nicht (fehlt, befreit, Arbeit zählt nicht).</li>
</ul>
<h3>ZP10</h3>
<p>Deutsch, Englisch und Mathematik in Jahrgang 10: Vornote aus dem ganzen Jahr, die ZP10-Note trägst du ein,
Endnote = 50 % Vornote + 50 % ZP10.</p>
<h3>Notenübersicht drucken</h3>
<p><b>„Drucken / PDF …“</b>: Übersicht im Querformat mit Notenspiegeln je Abschnitt. Passt nicht alles auf die
Seite, lässt das Programm zuerst Teilnoten weg – die festgesetzten Noten stehen immer drauf.</p>
"""),
    Thema("oberstufe", "Oberstufe (EF, Q1, Q2)", """
<h2>Oberstufe (EF, Q1, Q2)</h2>
<p>Lerngruppen mit Jahrgang 11–13 (EF, Q1, Q2) arbeiten mit <b>Punkten von 0 bis 15</b>. Das Notensystem ergibt
sich aus dem Jahrgang und lässt sich nicht mehr ändern, sobald Noten eingetragen sind.</p>
<ul>
<li><b>Kursart:</b> GK oder LK; schriftlich oder mündlich belegt.</li>
<li><b>Klausuren:</b> wie Klassenarbeiten. Standardschlüssel nach NRW-Tabelle: ab 95 % 15 Punkte, je 5 % weniger
ein Punkt bis 50 % = 6 Punkte, darunter 45 % = 5, 39 % = 4, 33 % = 3, 27 % = 2, 20 % = 1 Punkt. Pro Klausur
änderbar, eigene Vorlagen möglich.</li>
<li><b>Sonstige Mitarbeit:</b> im Reiter „Mündlich“ in Punkten.</li>
<li><b>Noten:</b> Quartals- und Halbjahresnoten in Punkten. Standard 50 % Klausuren / 50 % Sonstige Mitarbeit;
die Halbjahre werden getrennt bewertet. Schnitte werden auf ganze Punkte gerundet (,5 → mehr Punkte).</li>
<li><b>Notenspiegel</b> zählt Punkte; „unter 5 P.“ ist der Anteil der Defizite.</li>
</ul>
<p>Nicht enthalten: Abiturzulassung und Abiturprüfungen.</p>
<p>Beim <a href="#jahreswechsel">Schuljahreswechsel</a> wird aus allen 10. Klassen die EF, dann Q1 und Q2; die Q2
endet mit dem Abitur.</p>
"""),
    Thema("jahreswechsel", "Schuljahreswechsel", """
<h2>Schuljahreswechsel</h2>
<p><b>Datei → Schuljahr → „Neues Schuljahr aus bisherigem übernehmen …“</b> führt durch vier Schritte:</p>
<ol>
<li><b>Neues Schuljahr</b> mit Beginn, Halbjahreswechsel und Ende.</li>
<li><b>Klassen:</b> Jede Klasse wird hochgesetzt (8.4 → 9.4, 10.x → EF, EF → Q1 → Q2). Neue Klasse änderbar;
mit „endet“ verlassen alle die Schule (z. B. Abschlussklassen, die Q2 ist vorausgewählt).</li>
<li><b>Schüler:innen:</b> Ausnahmen festlegen – wiederholt, verlässt die Schule oder eine andere Klasse.</li>
<li><b>Lerngruppen:</b> welche übernommen werden, mit neuer Bezeichnung. Klassengruppen bekommen alle aus der
neuen Klasse, Kurse nur die versetzten Mitglieder. Gewichtung und Sortierung werden mitgenommen.</li>
</ol>
<p>Das alte Schuljahr bleibt unverändert und ist über Datei → Schuljahr erreichbar. Neue Schüler:innen trägst du
danach wie gewohnt ein oder importierst sie.</p>
"""),
    Thema("ki", "KI-Vorlage", """
<h2>KI-Vorlage</h2>
<p>Für Arbeiten, die du mit einer KI erstellst, liefert das Programm eine fertige Anweisung (Prompt). Die KI
antwortet in einem festen Format; das Programm liest daraus Aufgaben, Punkte, Erwartungshorizont und Musterlösung.</p>
<ol>
<li>Klassenarbeiten → <b>„KI-Vorlage …“</b> → Prompt kopieren („In die Zwischenablage kopieren“).</li>
<li>In der KI deiner Wahl einfügen und die Arbeit beschreiben bzw. die Arbeit mitgeben.</li>
<li>Die Antwort der KI zurück ins Programm einfügen und prüfen.</li>
<li>„Als neue Arbeit anlegen“ oder in die gewählte Arbeit übernehmen.</li>
</ol>
<p>Das Programm selbst sendet nichts – du kopierst von Hand. <b>Gib der KI keine Schülerdaten</b>; die Vorlage
enthält keine.</p>
"""),
    Thema("darstellung", "Darstellung und Ausdrucke", """
<h2>Darstellung und Ausdrucke</h2>
<ul>
<li><b>Ansicht → Design:</b> dunkel oder hell.</li>
<li><b>Ansicht → Schrift …</b>, größer (Strg + Plus), kleiner (Strg + Minus), Standardschrift.</li>
<li><b>Datei → Angaben für Ausdrucke …:</b> Schule und Lehrkraft für die Kopfzeile aller Ausdrucke. Die Angaben
stehen in der (verschlüsselten) Datenbank.</li>
<li>Die Schrift der Ausdrucke wählst du im Druckdialog; sie gilt für alle Ausdrucke.</li>
</ul>
"""),
    Thema("tasten", "Tastenkürzel", """
<h2>Tastenkürzel</h2>
<table cellpadding="4">
<tr><td><b>F1</b></td><td>Hilfe zur aktuellen Ansicht</td></tr>
<tr><td><b>Strg + N</b></td><td>Neue Datenbank</td></tr>
<tr><td><b>Strg + O</b></td><td>Datenbank öffnen</td></tr>
<tr><td><b>Strg + S</b></td><td>Speichern</td></tr>
<tr><td><b>Strg + W</b></td><td>Datenbank schließen</td></tr>
<tr><td><b>Strg + L</b></td><td>Neue Lerngruppe</td></tr>
<tr><td><b>Strg + Plus / Minus</b></td><td>Schrift größer / kleiner</td></tr>
<tr><td><b>Strg + Q</b></td><td>Beenden</td></tr>
</table>
<h3>In den Eingabetabellen</h3>
<table cellpadding="4">
<tr><td><b>Zahl tippen</b></td><td>Eingabe beginnt sofort</td></tr>
<tr><td><b>Enter</b></td><td>übernehmen und weiter (Richtung oben einstellbar)</td></tr>
<tr><td><b>Tab / Umschalt + Tab</b></td><td>seitlich weiter / zurück</td></tr>
<tr><td><b>Entf</b></td><td>markierte Felder leeren bzw. Festsetzung aufheben</td></tr>
<tr><td><b>Esc</b></td><td>Eingabe abbrechen</td></tr>
<tr><td><b>Rechtsklick</b></td><td>Vermerke, Note festsetzen, Bemerkung</td></tr>
</table>
"""),
    Thema("probleme", "Häufige Fragen", """
<h2>Häufige Fragen</h2>
<h3>Auf den Etiketten wird rechts oder links etwas abgeschnitten.</h3>
<p>Im Druckdialog „Abstand zum Blattrand“ erhöhen (z. B. auf 9 mm). Sitzt alles verschoben, den Druckversatz
anpassen. → <a href="#etiketten">Etiketten</a></p>
<h3>„Die Datenbank ist bereits geöffnet“</h3>
<p>Sie ist auf einem anderen Rechner offen – oder das Programm wurde dort nicht ordentlich beendet. Erst dort
schließen. Bist du sicher, dass sie nirgends offen ist, kannst du sie trotzdem öffnen.</p>
<h3>Ich habe mein Passwort vergessen.</h3>
<p>Startdialog → „Passwort vergessen?“ → Wiederherstellungscode vom Notfallblatt oder Schlüsseldatei.
→ <a href="#sicherheit">Sicherheit</a></p>
<h3>Eine ältere Programmversion öffnet meine Datei nicht mehr.</h3>
<p>Die Datei wurde von einer neueren Version umgestellt. Nimm die neue Version – oder für die alte Version die
Sicherung „…_vor-Umstellung-…“. → <a href="#datenbank">Datenbank</a></p>
<h3>Eine Person bekommt keine Note / das Feld ist grau.</h3>
<p>Sie war zu diesem Zeitpunkt nicht in der Gruppe (Eintritt, Austritt oder Abgang). Prüfen im Reiter
„Schüler:innen“ → „Eintritt / Austritt …“.</p>
<h3>Der Vorschlag passt nicht zu meiner Erwartung.</h3>
<p>Maus über den Vorschlag halten: Die Herleitung zeigt jede Note und jeden Anteil. Prüfe Gewichtung, ob jede
Arbeit „zählt“ und ihr Gewicht, und welchem Quartal/Halbjahr Arbeiten und Zeiträume zugeordnet sind.</p>
<h3>Sendet das Programm Daten ins Internet?</h3>
<p>Nein. Es stellt keine Verbindung her – weder für Updates noch für Statistik.</p>
"""),
]

THEMA = {t.schluessel: t for t in THEMEN}

# F1: welche Hilfeseite zu welcher Ansicht bzw. welchem Dialog gehört (Klassenname → Thema)
JE_KLASSE: dict[str, str] = {
    "Willkommen": "start", "DatenbankUebersicht": "start",
    "SchuljahrSeite": "schuljahr", "SchuljahrDialog": "schuljahr",
    "SchuelerSeite": "schueler", "SchuelerDialog": "schueler", "AbgangDialog": "schueler",
    "LerngruppeDialog": "lerngruppen", "MitgliederDialog": "lerngruppen", "ZeitraumDialog": "lerngruppen",
    "MitgliederTab": "lerngruppen",
    "ArbeitenTab": "arbeiten", "ArbeitDialog": "arbeiten", "SchluesselDialog": "schluessel",
    "DruckDialog": "drucken",
    "MuendlichTab": "muendlich", "ZeitraeumeDialog": "muendlich",
    "NotenTab": "noten", "GewichtungDialog": "noten",
    "ImportAssistent": "import", "JahreswechselAssistent": "jahreswechsel", "KiDialog": "ki",
    "StartDialog": "datenbank", "NeueDatenbankAssistent": "datenbank",
    "WiederherstellenDialog": "sicherheit", "PasswortAendernDialog": "sicherheit", "NotfallDialog": "sicherheit",
}
