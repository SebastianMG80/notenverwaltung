"""Handbuch: Bilder vorhanden, keine versehentlichen Listen, PDF lässt sich setzen, Hinweise stimmen."""

import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
MD = WURZEL / "handbuch" / "HANDBUCH.md"


def test_bilder_vorhanden_und_benutzt():
    text = MD.read_text(encoding="utf-8")
    benutzt = set(re.findall(r"!\[[^\]]*\]\((bilder/[^)]+)\)", text))
    assert len(benutzt) >= 30
    for pfad in benutzt:
        assert (MD.parent / pfad).is_file(), pfad
    ungenutzt = {f"bilder/{p.name}" for p in (MD.parent / "bilder").glob("*.png")} - benutzt
    assert not ungenutzt, f"Bilder ohne Verweis: {sorted(ungenutzt)}"


def test_keine_ungewollten_aufzaehlungen():
    """Eine umbrochene Absatzzeile, die mit „2. …“ beginnt, wäre in Markdown ein Listenpunkt."""
    zeilen = MD.read_text(encoding="utf-8").splitlines()
    for i in range(1, len(zeilen)):
        if re.match(r"^\d+\. ", zeilen[i]):
            davor = zeilen[i - 1]
            assert (not davor.strip() or re.match(r"^(\d+\.|-) ", davor) or davor.startswith("  ")), \
                f"Zeile {i + 1}: {zeilen[i][:40]}"


def test_pdf_setzen(app, tmp_path):
    sys.path.insert(0, str(WURZEL / "werkzeuge"))
    import handbuch_pdf

    html = handbuch_pdf.markdown_zu_html(MD.read_text(encoding="utf-8"))
    assert "page-break-before" in html and "<table" in html and "<img" in html
    ziel = handbuch_pdf.baue(tmp_path / "h.pdf")
    assert ziel.stat().st_size > 500_000


def test_inline():
    sys.path.insert(0, str(WURZEL / "werkzeuge"))
    import handbuch_pdf

    assert handbuch_pdf.inline("**fett** und *kursiv*, `x < 1`, [Link](https://x) \\*") == \
        "<b>fett</b> und <i>kursiv</i>, <code>x &lt; 1</code>, Link *"
