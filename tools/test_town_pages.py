#!/usr/bin/env python3
"""Preizkus krajevnih strani (/vreme-mozirje/ ipd.): vsaka ima statično meritev z
atributoma data-loc/data-where (po njiju jo najde inject_current_weather.py),
smer postaje glede na kraj je nasprotna smeri kraja glede na postajo (prej je
stala obratno), naslov je znotraj 60 znakov in omenja »po urah«."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as g  # noqa: E402
import inject_current_weather as inj  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


# 1) Nasprotna smer: vsaka osem kompasnih smeri je sebi nasprotna dvakrat.
for d in g._OPPOSITE_COMPASS:
    check(f"nasprotje {d}", g._OPPOSITE_COMPASS[g._opposite_compass(d)] == d)
check("severovzhodno → jugozahodno", g._opposite_compass("severovzhodno") == "jugozahodno")

# 2) Krajevne strani so v odkritih ciljih injektorja in imajo markerja.
found = {os.path.basename(os.path.dirname(p)) for p, _t, _c in inj.town_targets()}
for t in g.NEARBY_TOWNS:
    check(f"{t['slug']} odkrita", t["slug"] in found)
    path = os.path.join(g.ROOT, t["slug"], "index.html")
    html = open(path, encoding="utf-8").read()
    check(f"{t['slug']} markerja", inj.START in html and inj.END in html)
    m = re.search(r"<title>([^<]*)</title>", html)
    check(f"{t['slug']} naslov ≤ 60", m and len(m.group(1)) <= 60, m.group(1) if m else "")
    check(f"{t['slug']} naslov »po urah«", m and "po urah" in m.group(1))
    # Postaja je v nasprotni smeri kot kraj: kraj Mozirje je severovzhodno od postaje,
    # postaja pa jugozahodno od Mozirja.
    dirn = g._bearing_compass(g.LAT, g.LON, t["lat"], t["lon"])
    where = re.search(r'data-where="([^"]*)"', html)
    check(f"{t['slug']} smer postaje", where and g._opposite_compass(dirn) in where.group(1),
          where.group(1) if where else "")

# 3) Blok z `place` ima kraj v besedilu in v atributih; brez `place` je kot prej.
b = inj.build_block_history(inj.TAIL_TOWN, inj.CLS_RECICA, ("Mozirju", "3 km jugozahodno od Mozirja, 26 m više"))
check("blok kraj", "Vreme v Mozirju" in b and 'data-loc="Mozirju"' in b)
b0 = inj.build_block_history(inj.TAIL_RECICA, inj.CLS_RECICA)
check("blok brez kraja", "data-loc" not in b0 and "Zadnja znana dnevna meritev" in b0)

print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
