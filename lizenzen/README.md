# Lizenzen

## Die Notenverwaltung selbst

Copyright © 2026 SebastianMG80

Die Notenverwaltung ist freie Software: Du darfst sie unter den Bedingungen der **GNU General Public License,
Version 3 oder (nach deiner Wahl) jeder späteren Version** nutzen, weitergeben und verändern. Den Lizenztext
findest du in der Datei `LICENSE` (englisch, verbindlich).

Das Programm wird **ohne jede Gewährleistung** bereitgestellt – auch ohne die Zusicherung, dass es für einen
bestimmten Zweck geeignet ist. Prüfe Noten, bevor du sie abgibst.

Quelltext: <https://github.com/SebastianMG80/notenverwaltung>

## Verwendete Software anderer

Die fertigen Programmpakete (Releases) enthalten außer der Notenverwaltung diese Software. Ihre Lizenzen erlauben
die Weitergabe; die Texte liegen in diesem Ordner.

| Bestandteil | Wofür | Lizenz | Datei |
|---|---|---|---|
| Qt 6 und Qt for Python (PySide6, shiboken6) | Oberfläche, Druck | LGPL-3.0 | `LGPL-3.0.txt` (mit `LICENSE` = GPL-3.0, auf die sie verweist) |
| Python | Laufzeitumgebung | PSF-Lizenz | `Python-LICENSE.txt` (im Paket; enthält auch die Hinweise zu den mit Python ausgelieferten Bibliotheken wie OpenSSL, SQLite, zlib, libffi, bzip2, xz) |
| cryptography (mit OpenSSL) | Verschlüsselung (AES-256-GCM, Argon2id) | Apache-2.0 oder BSD-3-Clause | `cryptography-LICENSE*.txt` |
| cffi | Brücke zu C-Bibliotheken | MIT-0 | `cffi-LICENSE.txt` |
| pycparser | von cffi benötigt | BSD-3-Clause | `pycparser-LICENSE.txt` |
| ICU (von Qt mitgebracht) | Unicode, Sortierung | Unicode License V3 | <https://doc.qt.io/qt-6/licenses-used-in-qt.html> |
| segno | QR-Code auf dem Notfallblatt | BSD-3-Clause | `segno-LICENSE.txt` |
| PyInstaller-Startprogramm | startet das gepackte Programm | GPL-2.0 mit Bootloader-Ausnahme (Weitergabe ohne Einschränkung) | `pyinstaller-COPYING.txt` |

**Qt (LGPL):** Die Qt-Bibliotheken liegen im Paket als eigene Dateien (`_internal/PySide6/…`) und lassen sich
gegen eigene Fassungen austauschen. Quelltext von Qt: <https://download.qt.io/official_releases/qt/>, von Qt for
Python: <https://download.qt.io/official_releases/QtForPython/>. Qt bringt selbst weitere Bibliotheken mit; die
Übersicht steht unter <https://doc.qt.io/qt-6/licenses-used-in-qt.html>.

**Linux-Paket:** Es enthält zusätzlich Bibliotheken des Build-Systems (Ubuntu), etwa GTK, GLib, ICU, FreeType,
fontconfig, HarfBuzz, X11/xcb, Kerberos und GnuTLS – jeweils unter freien Lizenzen (meist LGPL, MIT oder BSD).
Beim Bauen legt `werkzeuge/lizenzen_sammeln.py` zu jeder dieser Bibliotheken die Copyright-Datei ihres
Ubuntu-Pakets in den Ordner `lizenzen/linux-systembibliotheken/` des Pakets, dazu eine Liste (Bibliothek →
Paket). Den Quelltext gibt es über <https://packages.ubuntu.com> bzw. `apt source <paket>`.

**Windows-Paket:** Python bringt die Laufzeitbibliothek von Microsoft Visual C++ mit (`vcruntime140.dll` u. a.),
die Microsoft zur Weitergabe mit Programmen freigibt.
