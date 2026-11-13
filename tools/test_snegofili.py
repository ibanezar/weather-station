#!/usr/bin/env python3
"""tools/test_snegofili.py — /snegofili/: seznam točk, izračun snega po oknih, izris, vdelava kamer.
Zaženi: python3 tools/test_snegofili.py"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snegofili_data as d  # noqa: E402
import generate_snegofili_page as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# ── seznam točk ──
pts = d.load_points()
ids = [p["id"] for p in pts]
check(len(ids) == len(set(ids)), "id točk so enolični")
check(len(pts) >= 30, "vsaj 30 točk")
for p in pts:
    check(p["drzava"] in g.COUNTRIES, f"država {p['id']}")
    check(43 <= p["lat"] <= 48.5 and 5 <= p["lon"] <= 17, f"koordinate v alpskem loku {p['id']}")
    check(300 <= p["elevation_m"] <= 4200, f"višina {p['id']}")
    for c in p.get("kamere") or []:
        check(c["url"].startswith("https://"), f"povezava kamere https {p['id']}")
        if c.get("embed"):
            check(c["embed"].startswith("https://") and c.get("embed_terms") and c.get("checked"),
                  f"vdelava brez embed_terms/checked {p['id']}")

# ── izračun po oknih ──
N = 168
IDX = 80  # 72 nazaj + 8 ur


def series(fl, precip_at):
    times = [(datetime.datetime(2026, 11, 10) + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(N)]
    pr = [precip_at.get(i, 0.0) for i in range(N)]
    return {"time": times, "temperature_2m": [-3.0] * N, "precipitation": pr, "freezing_level_height": [fl] * N}


cold = series(0, {i: 1.0 for i in range(N)})
c = d.compute_point(cold, IDX, 1000)
check(c["past24_cm"] == 24.0 and c["past72_cm"] == 72.0, "mraz: 1 mm/h = 1 cm/h nazaj")
check(c["next24_cm"] == 24.0 and c["next72_cm"] == 72.0, "mraz: naprej")
check(c["snow_line_m"] == -250, "meja sneženja = ničta izoterma − 250 m")
warm = series(3000, {i: 1.0 for i in range(N)})
w = d.compute_point(warm, IDX, 1000)
check(w["past24_cm"] == 0 and w["past24_mm"] == 24.0, "topli sloj: dež, ne sneg")
# meje oken: padavina ob idx+1 šteje samo naprej, ob idx samo nazaj
edge = series(0, {IDX: 5.0, IDX + 1: 7.0, IDX - 24: 3.0, IDX - 23: 2.0})
e = d.compute_point(edge, IDX, 1000)
check(e["past24_cm"] == 7.0, "nazaj (idx-24, idx]: 5+2, brez idx-24 in idx+1")
check(e["next24_cm"] == 7.0, "naprej začne pri idx+1")
check(d.compute_point(cold, 10, 1000) is None, "premalo ur nazaj → None")
check(d.compute_point(cold, N - 5, 1000) is None, "premalo ur naprej → None")

# ── izris ──
rows = [{"id": "a", "ime": "Točka <A>", "drzava": "SI", "regija": "R", "lat": 46, "lon": 14, "elevation_m": 1500,
         "elev_opis": "x", "km_od_recice": 20, "temp_c": -2.0, "snow_line_m": 900, "snow_now_possible": True,
         "past24_cm": 12.0, "past72_cm": 30.0, "next24_cm": 4.0, "next72_cm": 6.0,
         "izmerjeno": {"depth_cm": 5, "valid_utc": "2026-11-13T06:00Z", "age_h": 3.0}},
        {"id": "b", "ime": "Daleč", "drzava": "CH", "regija": "R", "lat": 46, "lon": 7, "elevation_m": 3000,
         "elev_opis": "x", "km_od_recice": 700, "temp_c": -9.0, "snow_line_m": 1500, "snow_now_possible": True,
         "past24_cm": 0.2, "past72_cm": 0.4, "next24_cm": 50.0, "next72_cm": 60.0}]
data = {"generated_at": "2026-11-13T06:00:00Z", "generated_at_local": "13. 11. 2026 ob 7.00", "tocke": rows}
cams = {"a": {"id": "a", "ime": "A", "arso_cam": "Krvavec", "kamere": []}, "b": {"id": "b", "ime": "B", "kamere": [
    {"naslov": "k", "url": "https://x.example/cam", "ponudnik": "P"}]}}
body = g.build_body(data, cams)
check("Točka &lt;A&gt;" in body and "Točka <A>" not in body, "ime točke je ubežano")
hs = g.hero_sentence(rows)
check("Točka &lt;A&gt;" in hs and "(12 cm)" in hs.replace(" ", " "), "stavek: najbolj zasnežilo")
check("Daleč" not in hs, "stavek: točka čez 200 km ni v dnevnem izletu")
check("indoor" not in body.lower() and "tempinf" not in body.lower(), "brez notranjih meritev")
check(g.cm_cell(0.4) == "—" and g.cm_cell(3.26).startswith("3,3"), "oblika centimetrov (vejica, pod 1 cm črtica)")
check('class="sg-embed"' not in body, "brez embed polj ni vdelave")
cams["b"]["kamere"][0]["embed"] = "https://x.example/e"
check("sg-embed" not in g.embed_html(cams), "vdelava brez embed_terms/checked se ne izriše")
cams["b"]["kamere"][0].update({"embed_terms": "https://x.example/t", "checked": "2026-11-13"})
check("sg-embed" in g.embed_html(cams), "vdelava z embed_terms/checked se izriše")
check(len(g.TITLE) <= 60, "naslov ≤ 60 znakov")


# ── usklajenost Python ↔ snegofili.js (namerna podvojitev) ──
import subprocess  # noqa: E402

CASES = [0, 0.4, 0.99, 1, 4.9, 5, 14.9, 15, 29.9, 30, 59.9, 60, 120]
js = ("const m=require('./snegofili/snegofili.js');const c=" + json.dumps(CASES) +
      ";console.log(JSON.stringify(c.map(x=>[m.step(x),+m.radius(x).toFixed(3),+m.barPct(x).toFixed(3)])))")
try:
    out = json.loads(subprocess.run(["node", "-e", js], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    capture_output=True, text=True, timeout=30, check=True).stdout)
    for x, (st, rad, bp) in zip(CASES, out):
        check(st == g.step(x) and abs(rad - g.radius(x)) < 1e-3 and abs(bp - g.bar_pct(x)) < 1e-3, f"JS↔Python step/radius/barPct pri {x}")
    jp = ("const m=require('./snegofili/snegofili.js');console.log(JSON.stringify([[1000,null],[1000,800],[1000,900],[1000,901],[1000,1100],[1000,1101],[1000,1500]]"
          ".map(a=>m.phase(a[0],a[1]))))")
    ph = json.loads(subprocess.run(["node", "-e", jp], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   capture_output=True, text=True, timeout=30, check=True).stdout)
    check(ph == [g.phase(a, b) for a, b in [(1000, None), (1000, 800), (1000, 900), (1000, 901), (1000, 1100), (1000, 1101), (1000, 1500)]],
          "JS↔Python phase (meje ±100 m)")
except (OSError, subprocess.SubprocessError) as e:
    check(False, f"node ni dosegljiv: {e}")

# ── urna serija: okno v JS pri »zdaj« = okno v Pythonu ──
hs = d.hourly_series(cold, 1000, IDX)
check(len(hs["sn"]) == 144 and len(hs["sl"]) == 144 and len(hs["t"]) == 144, "urna serija ima 144 ur")
jw = ("const m=require('./snegofili/snegofili.js');const s=" + json.dumps(hs["sn"]) +
      ";console.log(JSON.stringify(m.windows(s,m.NOW)))")
w2 = json.loads(subprocess.run(["node", "-e", jw], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               capture_output=True, text=True, timeout=30, check=True).stdout)
pp = d.compute_point(cold, IDX, 1000)
check(abs(w2["past"] - pp["past24_cm"]) < 1e-6 and abs(w2["next"] - pp["next24_cm"]) < 1e-6, "JS okno pri zdaj = Python past24/next24")
cw = d.compute_point(edge, IDX, 1000)
hs2 = d.hourly_series(edge, 1000, IDX)
w3 = json.loads(subprocess.run(["node", "-e", "const m=require('./snegofili/snegofili.js');console.log(JSON.stringify(m.windows(" + json.dumps(hs2["sn"]) + ",m.NOW)))"],
                               cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), capture_output=True, text=True, timeout=30, check=True).stdout)
check(abs(w3["past"] - cw["past24_cm"]) < 1e-6 and abs(w3["next"] - cw["next24_cm"]) < 1e-6, "JS↔Python okna na mejah (idx, idx+1)")

# ── izris: karta, prerez, kartice ──
check("sg-map" in body and "sg-prof" in body and 'class="sg-card"' in body, "hero ima karto, prerez in kartice")
check("sg-line" not in body, "prerez nima več polilinije")
check(g.ZOOM_VB.count(" ") == 3, "zoom viewBox ima 4 števila")

# ── ARSO: stara meritev se ne prikaže ──
now = datetime.datetime(2026, 11, 13, 12, 0, tzinfo=datetime.timezone.utc)
a = d.load_arso(now)
check(all(v["age_h"] <= d.ARSO_MAX_AGE_H for v in a.values()), "ARSO meritve ≤ 24 h")

print("OK" if not fails else f"{fails} napak")
sys.exit(1 if fails else 0)
