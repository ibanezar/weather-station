#!/usr/bin/env python3
"""Preizkus /pojmi/ (generate_pojmi_pages.py): vsaka notranja povezava obstaja,
vsak pojem ima odgovor, FAQ in številko s postaje (ali jo pošteno izpusti),
naslov je znotraj 60 znakov in committane strani obstajajo."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_pojmi_pages as g  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


hist = g.load_history()
items = g.pages(hist)
check("šest pojmov", len(items) == 6, str(len(items)))
lastmod = max(g.real_days(hist))
for p in items:
    html = g.build_page(p, lastmod)
    check(f"{p['slug']} odgovor", len(p["answer"]) > 40)
    check(f"{p['slug']} FAQ ≥ 3", len(p["faq"]) >= 3)
    m = re.search(r"<title>([^<]*)</title>", html)
    check(f"{p['slug']} naslov ≤ 60", m and len(m.group(1)) <= 60, m.group(1) if m else "")
    for href in re.findall(r'href="(/[^"#?]*)"', html):
        if href.endswith(".html"):
            path = os.path.join(g.ROOT, href.lstrip("/"))
        else:
            path = os.path.join(g.ROOT, href.lstrip("/"), "index.html")
        # skupne datoteke (CSS, ikone …) niso strani
        if href.startswith(("/fonts/", "/blog/blog.css", "/vreme/vreme.css")) or "." in os.path.basename(href):
            if not href.endswith(".html"):
                continue
        check(f"{p['slug']} povezava {href}", os.path.exists(path))
    check(f"{p['slug']} brez notranjih meritev", "indoor" not in html.lower())
    # Stran mora obstajati (zapiše jo generator, dnevni tek jo osveži).
    disk = os.path.join(g.ROOT, "pojmi", p["slug"], "index.html")
    check(f"{p['slug']} obstaja", os.path.exists(disk))

# Številke: pogoji, pod katerimi se dejstvo izpusti, ne smejo vrniti napačne vrednosti.
f = g.fact_barometer(hist)
check("barometer: delež v [0,1]", f is None or (0 <= f["p_drop"] <= 1 and 0 <= f["p_all"] <= 1))
f = g.fact_inverzija(hist)
check("inverzija: razpon pozitiven", f is None or (f["hi"] > 0 and f["lo"] > 0))
check("hub se zgradi", "Vremenski pojmi" in g.build_hub(items, lastmod))

print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
