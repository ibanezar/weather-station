#!/usr/bin/env python3
"""Test /astma/: pravila točkovanja, JS kopija seštevanja (Node), brez notranjih meritev."""
import json, os, subprocess, sys, itertools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_astma_page as A  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


# ── meje točk ──
check("PM2,5 meje", [A.pts_by_thresholds(v, (15, 25, 50)) for v in (14.9, 15, 24.9, 25, 49.9, 50)] == [0, 1, 1, 2, 2, 3])
check("mraz meje", [A.pts_cold(v) for v in (1, 0.1, 0, -4.9, -5, -9.9, -10)] == [0, 0, 1, 1, 2, 2, 3])
check("vročina meje", [A.pts_heat(v) for v in (27.9, 28, 31.9, 32, 34.9, 35)] == [0, 1, 1, 2, 2, 3])
check("brez podatka = 0 točk", A.pts_by_thresholds(None, (1, 2, 3)) == 0 and A.pts_cold(None) == 0 and A.pts_heat(None) == 0)
th_grass = A.POLLEN_TYPES[0][2]
check("pelod: pod pragom 0", A.pts_pollen(th_grass[0] - 0.1, th_grass) == 0)
check("pelod: zelo visoka 3", A.pts_pollen(th_grass[2], th_grass) == 3)
check("nevihtna astma samo s travo", A.pts_storm(True, th_grass[0]) == 3 and A.pts_storm(True, 0) == 1
      and A.pts_storm(True, None) == 1 and A.pts_storm(False, 500) == 0)
check("sprememba: temperatura ali tlak, višji velja", A.pts_change(5, 0) == 1 and A.pts_change(-8, 0) == 2
      and A.pts_change(0, 8) == 1 and A.pts_change(0, 12) == 2 and A.pts_change(5, 12) == 2 and A.pts_change(None, None) == 0)
check("vlaga: obe skrajnosti", A.pts_humidity(90) == 1 and A.pts_humidity(29.9) == 1 and A.pts_humidity(60) == 0)

# ── raven: vsota in tla ──
check("raven brez točk je nizko", A.level_for(0, 0) == "nizko")
check("meje vsote", [A.level_for(s, 1) for s in (1, 2, 3, 4, 5, 6)] == ["nizko", "zmerno", "zmerno", "povišano", "povišano", "visoko"])
check("tla: ena trojka = vsaj povišano", A.level_for(3, 3) == "povišano" and A.level_for(7, 3) == "visoko")
check("največ 9 dejavnikov, 27 točk", len(A.FACTOR_KEYS) == 9 and 3 * len(A.FACTOR_KEYS) == 27)

# ── JS kopija proti Pythonu ──
cases = []
for combo in itertools.product(range(4), repeat=3):
    pts = {k: 0 for k in A.FACTOR_KEYS}
    pts["pelod"], pts["pm"], pts["mraz"] = combo
    for w in ({}, {"pelod": 2}, {"pm": 2, "mraz": 2}):
        cases.append((pts, w))
js = A.ASTMA_JS_CORE + """
var c=JSON.parse(process.argv[1]),o=[];
c.forEach(function(x){o.push([astmaScore(x[0],x[1]),astmaLevel(x[0],x[1],%s,%d,%s)]);});
console.log(JSON.stringify(o));""" % (json.dumps(list(A.SCORE_TH)), A.FLOOR_PTS, json.dumps(A.LEVELS))
out = subprocess.run(["node", "-e", js, json.dumps(cases)], capture_output=True, text=True)
check("node teče", out.returncode == 0)
if out.returncode == 0:
    got = json.loads(out.stdout)
    # JS ob utežitvi tla uporabi neutežene točke -- enako kot Python level_for(score, max_pts)
    ok = all(g[0] == A.score_for(p, w) and g[1] == A.level_for(A.score_for(p, w), max(p.values()))
             for g, (p, w) in zip(got, cases))
    check(f"JS ↔ Python na {len(cases)} primerih", ok)

# ── generirana stran ──
page = os.path.join(ROOT, "astma", "index.html")
if os.path.exists(page):
    s = open(page, encoding="utf-8").read()
    check("stran ne omenja notranjih meritev", "indoor" not in s.lower())
    check("opozorilo, da ni zdravniški nasvet", "ni zdravniški nasvet" in s.lower())
    check("112 omenjen", "112" in s)
    check("canonical", 'rel="canonical" href="https://meteorec.si/astma/"' in s)

sys.exit(1 if fails else 0)
