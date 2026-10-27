#!/usr/bin/env python3
"""Preizkus vsebine pojmov na /slovar/ (generate_pojmi_pages.slovar_extras): vsak pojem ima odgovor,
FAQ in številko s postaje (ali jo pošteno izpusti), naslov je znotraj 60 znakov, notranje povezave
obstajajo, committane slovarske strani vsebujejo nov odsek, /pojmi/ so samo preusmeritve."""
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
extras = g.slovar_extras(hist)
check("šest pojmov", len(extras) == 6, str(len(extras)))
for slug, p in extras.items():
    check(f"{slug} odgovor", len(p["answer"]) > 40)
    check(f"{slug} FAQ >= 3", len(p["faq"]) >= 3)
    check(f"{slug} naslov <= 60", len(p["title"]) + len(" | Meteorec") <= 60 or len(p["title"]) <= 60, p["title"])
    html = p["body_html"] + " ".join(h for h, _ in p["links"])
    check(f"{slug} brez /pojmi/ povezav", "/pojmi/" not in html)
    check(f"{slug} brez notranjih meritev", "indoor" not in html.lower())
    for href in re.findall(r'href="(/[^"#?]*)"', html):
        if "." in os.path.basename(href) and not href.endswith(".html"):
            continue
        path = os.path.join(g.ROOT, href.lstrip("/")) if href.endswith(".html") \
            else os.path.join(g.ROOT, href.lstrip("/"), "index.html")
        check(f"{slug} povezava {href}", os.path.exists(path))
    disk = os.path.join(g.ROOT, "slovar", slug, "index.html")
    txt = open(disk, encoding="utf-8").read() if os.path.exists(disk) else ""
    check(f"{slug} slovarska stran ima odsek Na kratko", "<strong>Na kratko:</strong>" in txt)
    check(f"{slug} naslov strani iz pojmov", p["title"] in txt)

for slug in [p["slug"] for p in g.pages(hist)] + [""]:
    f = os.path.join(g.ROOT, "pojmi", slug, "index.html")
    t = open(f, encoding="utf-8").read() if os.path.exists(f) else ""
    check(f"pojmi/{slug} je preusmeritev", 'name="robots" content="noindex' in t and "/slovar/" in t)

f = g.fact_barometer(hist)
check("barometer: delež v [0,1]", f is None or (0 <= f["p_drop"] <= 1 and 0 <= f["p_all"] <= 1))
f = g.fact_inverzija(hist)
check("inverzija: razpon pozitiven", f is None or (f["hi"] > 0 and f["lo"] > 0))

print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
