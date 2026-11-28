#!/usr/bin/env python3
"""lastmod v sitemap.xml iz `dateModified` same strani (ugotovljeno 28. 11. 2026: zimske strani se osvežujejo dnevno,
sitemap pa je kazal datum zadnje objave članka, ker ga piše samo `wire_all()`).

Vir resnice je JSON-LD `dateModified` strani (ga piše generator iz časa nastanka podatkov). Skript:
  - lastmod samo PREMAKNE NAPREJ (nikoli nazaj, nikoli iz prihodnosti),
  - ne dotakne se strani brez `dateModified` (tam ostane obstoječi datum),
  - ne piše datoteke, če se nič ne spremeni (brez prazne spremembe v gitu).

Uporaba: `python3 tools/sitemap_lastmod.py` (korak v zima-forecast.yml pred commitom).
"""
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
DM_RE = re.compile(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})')
LASTMOD_RE = re.compile(r"<lastmod>(\d{4}-\d{2}-\d{2})</lastmod>")


def page_date_modified(path):
    """Prvi `dateModified` v JSON-LD strani (YYYY-MM-DD) ali None."""
    try:
        with open(path, encoding="utf-8") as f:
            m = DM_RE.search(f.read())
    except OSError:
        return None
    return m.group(1) if m else None


def local_path(loc):
    """https://meteorec.si/zima/x/ -> <ROOT>/zima/x/index.html (kot seo_audit.local_path); None za tuje URL-je."""
    if not loc.startswith(SITE + "/"):
        return None
    rel = loc[len(SITE) + 1:].split("#")[0].split("?")[0]
    if rel == "" or rel.endswith("/"):
        rel += "index.html"
    return os.path.join(ROOT, rel)


def sync(text, reader, today=None):
    """Vrne (novo besedilo, seznam (loc, staro, novo)). `reader(loc)` vrne dateModified ali None."""
    today = today or datetime.date.today().isoformat()
    changes = []

    def fix(m):
        block = m.group(0)
        loc = re.search(r"<loc>(.*?)</loc>", block)
        cur = LASTMOD_RE.search(block)
        if not loc or not cur:
            return block
        dm = reader(loc.group(1))
        if not dm or dm <= cur.group(1) or dm > today:
            return block
        changes.append((loc.group(1), cur.group(1), dm))
        return LASTMOD_RE.sub(f"<lastmod>{dm}</lastmod>", block, count=1)

    return re.sub(r"<url>.*?</url>", fix, text, flags=re.S), changes


def main():
    path = os.path.join(ROOT, "sitemap.xml")
    text = open(path, encoding="utf-8").read()
    new, changes = sync(text, lambda loc: page_date_modified(local_path(loc) or ""))
    for loc, a, b in changes:
        print(f"  {loc}: {a} -> {b}")
    if changes:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
    print(f"sitemap.xml: lastmod popravljen pri {len(changes)} URL-jih.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
