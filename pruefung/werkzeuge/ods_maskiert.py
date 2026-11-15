import sys, zipfile, re
from xml.etree import ElementTree as ET
p = sys.argv[1]
z = zipfile.ZipFile(p)
print("Einträge:", [(i.filename, i.file_size) for i in z.infolist()])
meta = z.read("meta.xml").decode("utf-8", "replace")
# nur Feldnamen und maskierte Werte der Metadaten
for m in re.finditer(r"<(meta:[\w-]+|dc:[\w-]+)[^>]*>([^<]*)<", meta):
    w = m.group(2)
    print("  meta", m.group(1), "→", (w[:1] + "…(%d Zeichen)" % len(w)) if m.group(1) in ("meta:initial-creator", "dc:creator") else w[:40])
T = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"; X = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
inhalt = ET.fromstring(z.read("content.xml"))
for t in inhalt.iter(f"{{{T}}}table"):
    texte = []
    for c in t.iter(f"{{{T}}}table-cell"):
        s = "".join("".join(pp.itertext()) for pp in c.iter(f"{{{X}}}p")).strip()
        if s: texte.append(s)
    worte = [s for s in texte if re.fullmatch(r"[A-Za-zÄÖÜäöüß' -]{3,}", s)]
    print("Tabelle", t.get(f"{{{T}}}name"), "| Zellen mit Text:", len(texte), "| reine Wort-Zellen:", len(worte))
    print("   Wort-Zellen (maskiert):", sorted({w[:2] + "*" * (len(w) - 2) for w in worte})[:80])
    print("   mit Komma (Name, Vorname?):", sum(1 for s in texte if re.fullmatch(r"[^\d,]{2,}, ?[^\d,]{2,}", s)))
