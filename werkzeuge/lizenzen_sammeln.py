"""Legt die Lizenztexte in ein gebautes Programmpaket (nach PyInstaller, vor dem Zippen).

    python werkzeuge/lizenzen_sammeln.py dist/Notenverwaltung

Kopiert `LICENSE` (GPL-3.0), den Ordner `lizenzen/` und den Lizenztext des verwendeten Python. Unter Linux kommt
für jede mitgelieferte Systembibliothek die Copyright-Datei ihres Debian/Ubuntu-Pakets dazu (über `dpkg -S`),
mit einer Liste Bibliothek → Paket. Liegt `handbuch/Handbuch.pdf` vor, kommt es ebenfalls ins Paket.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
# Bibliotheken aus pip-Paketen (eigene Lizenztexte in lizenzen/) – nicht über dpkg suchen
# libicu*.so.73: ICU, wie es Qt mitbringt (Unicode-Lizenz, siehe lizenzen/README.md)
EIGENE = ("libQt6", "libpyside6", "libshiboken6", "libpython3", "_cffi_backend", "libicu", "Shiboken")


def python_lizenz() -> Path | None:
    kandidaten = [Path(sys.base_prefix) / "LICENSE.txt",
                  Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt",
                  Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"]
    return next((k for k in kandidaten if k.is_file()), None)


def systembibliotheken(paket: Path) -> dict[str, str]:
    """Dateiname → Debian-Paket für alle .so-Dateien, die nicht aus pip-Paketen stammen."""
    if not shutil.which("dpkg"):
        return {}
    ergebnis = {}
    for datei in sorted(paket.rglob("*.so*")):
        name = datei.name
        if "site-packages" in str(datei) or "/PySide6/" in datei.as_posix() or "/cryptography" in datei.as_posix():
            continue
        if name.startswith(EIGENE):
            continue
        r = subprocess.run(["dpkg", "-S", f"*/{name}"], capture_output=True, text=True,
                           env={"LC_ALL": "C", "PATH": "/usr/bin:/bin"})
        zeile = next((z for z in r.stdout.splitlines() if ":" in z and not z.startswith("diversion")), "")
        if zeile:
            ergebnis[name] = zeile.split(":")[0].strip()
        else:
            print(f"Hinweis: kein Paket für {name}", file=sys.stderr)
    return ergebnis


def sammle(paket: Path) -> int:
    paket = Path(paket)
    if not paket.is_dir():
        raise SystemExit(f"Kein Ordner: {paket}")
    shutil.copy2(WURZEL / "LICENSE", paket / "LICENSE.txt")
    ziel = paket / "lizenzen"
    if ziel.exists():
        shutil.rmtree(ziel)
    shutil.copytree(WURZEL / "lizenzen", ziel)
    py = python_lizenz()
    if py:
        shutil.copy2(py, ziel / "Python-LICENSE.txt")
    else:
        print("Warnung: Lizenztext von Python nicht gefunden", file=sys.stderr)
    handbuch = WURZEL / "handbuch" / "Handbuch.pdf"
    if handbuch.is_file():
        shutil.copy2(handbuch, paket / "Handbuch.pdf")
    libs = systembibliotheken(paket)
    if libs:
        unter = ziel / "linux-systembibliotheken"
        unter.mkdir()
        zeilen = ["Mitgelieferte Systembibliotheken (Ubuntu) und ihre Pakete", ""]
        for name, pkt in sorted(libs.items()):
            zeilen.append(f"{name}\t{pkt}")
            basis = pkt.split(":")[0]
            quelle = Path("/usr/share/doc") / basis / "copyright"
            if quelle.is_file() and not (unter / f"{basis}.txt").exists():
                shutil.copy2(quelle, unter / f"{basis}.txt")
        (unter / "LISTE.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        fehlend = sorted({p.split(':')[0] for p in libs.values()} - {f.stem for f in unter.glob('*.txt')})
        if fehlend:
            print("Warnung: ohne Copyright-Datei:", ", ".join(fehlend), file=sys.stderr)
    print(f"Lizenzen gesammelt: {sum(1 for _ in ziel.rglob('*.txt'))} Dateien, {len(libs)} Systembibliotheken")
    return 0


if __name__ == "__main__":
    raise SystemExit(sammle(Path(sys.argv[1]) if len(sys.argv) > 1 else WURZEL / "dist" / "Notenverwaltung"))
