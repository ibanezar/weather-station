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

# 2b) Kampi in Menina imajo markerja napovedi in so v injektorju napovedi (sicer bi ostali prazni).
import inject_forecast as IF  # noqa: E402
tw = {t[0] for t in IF.TOWNS}
for slug in ["vreme-kamp-menina"] + [c["slug"] for c in g.VALLEY_CAMPS]:
    html = open(os.path.join(g.ROOT, slug, "index.html"), encoding="utf-8").read()
    check(f"{slug} markerja napovedi", IF.FC7_START in html and IF.FCH_START in html)
    check(f"{slug} v TOWNS", slug in tw)

# 3) Blok z `place` ima kraj v besedilu in v atributih; brez `place` je kot prej.
b = inj.build_block_history(inj.TAIL_TOWN, inj.CLS_RECICA, ("Mozirju", "3 km jugozahodno od Mozirja, 26 m više"))
check("blok kraj", "Vreme v Mozirju" in b and 'data-loc="Mozirju"' in b)
b0 = inj.build_block_history(inj.TAIL_RECICA, inj.CLS_RECICA)
check("blok brez kraja", "data-loc" not in b0 and "Zadnja znana dnevna meritev" in b0)

# 4) »Na kratko« + grafa po mesecih (računano iz history.json, ne vtipkano; HTML se zgradi v delovnem toku).
hist = g.load_history()
mc = g.monthly_climate(hist)
check("mesečno podnebje ima 12 mesecev", len(mc) == 12)
for t in g.NEARBY_TOWNS:
    lapse = -g.LAPSE_RATE_C_PER_100M * (t["elev"] - g.ELEV) / 100
    kratko, chart, qa = g.town_climate_blocks(hist, t, lapse, g.climate_facts(hist))
    check(f"{t['slug']} Na kratko", "Na kratko:" in kratko and t["loc"] in kratko)
    check(f"{t['slug']} grafa", chart.count("<svg") == 2 and chart.count('role="img"') == 2)
    check(f"{t['slug']} FAQ", len(qa) == 2 and all(q.strip() and a.strip() for q, a in qa))
    check(f"{t['slug']} pravi minus", "okrog -" not in kratko and "okrog -" not in qa[0][1])
    check(f"{t['slug']} brez notranjih meritev", "indoor" not in (kratko + chart).lower())

# 5) Logarska dolina ima napoved (koordinate doline), »zadnjih 14 dni« računa po meritvah, ne po ERA5.
check("Logarska v TOWNS", "vreme-logarska-dolina" in tw)
import datetime as _dt
syn = {}
d0 = _dt.date(2024, 1, 1)
for i in range(900):
    d = (d0 + _dt.timedelta(days=i)).isoformat()
    syn[d] = {"tempAvg": 10.0, "tempHigh": 14.0, "tempLow": 6.0, "precipTotal": 0.0, "src": "station"}
last = max(syn)
syn[last]["tempAvg"] = 15.0
syn[(_dt.date.fromisoformat(last) - _dt.timedelta(days=1)).isoformat()]["src"] = "era5"
sent, svg = g.recent_days_block(syn)
check("zadnjih dni: stavek in SVG", sent and "<svg" in svg and "nad običajnim" in sent)
check("zadnjih dni: ERA5 izpuščen", svg.count("<circle") == 14)
check("običajno ≈ 10", abs(g.day_normal(syn, last) - 10.0) < 0.5)

print(f"{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
