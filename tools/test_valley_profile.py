#!/usr/bin/env python3
"""tools/test_valley_profile.py — dolinski profil (app.js: valleyProfileSummary / renderValleyProfile).

Zaženi:  python3 tools/test_valley_profile.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHECKS, FAILS = 0, []


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


def js(calls, prelude=""):
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT,
                       input=json.dumps({"file": "app.js", "names": ["VP_HOME_ELEV", "valleyProfileSummary",
                                                                      "renderValleyProfile", "_duelNum", "valleyTempAt",
                                                                      "valleyZeroHeight", "VALLEY_HERO", "VALLEY_COLORS", "hvColor",
                                                                      "heroValleySvg"],
                                         "calls": calls, "prelude": prelude}))
    out = json.loads(p.stdout)
    assert "results" in out, out
    return out["results"]


P = lambda n, e, t: {"name": n, "elev": e, "t": t}  # noqa: E731
cases = {
    "inverzija": [P("Rečica", 366, 8.0), P("Črnivec", 903, 12.5)],
    "šibek": [P("Rečica", 366, 15.0), P("Črnivec", 903, 13.5)],
    "običajen": [P("Rečica", 366, 20.0), P("Gornji Grad", 428, 19.5), P("Črnivec", 903, 16.5)],
    "strm": [P("Rečica", 366, 25.0), P("Črnivec", 903, 17.0)],
    "šibka inverzija": [P("Rečica", 366, 10.0), P("Črnivec", 903, 11.1)],        # +0,2 °C/100 m
    "strm blizu meje": [P("Rečica", 366, 20.0), P("Črnivec", 903, 14.6)],         # −1,0 °C/100 m
}
res = js([{"fn": "valleyProfileSummary", "args": [v]} for v in cases.values()])
kinds = {k: r["kind"] if r else None for k, r in zip(cases, res)}
check(kinds == {"inverzija": "inversion", "šibek": "weak", "običajen": "normal", "strm": "steep",
                "šibka inverzija": "inversion", "strm blizu meje": "steep"}, "vrsta gradienta", str(kinds))
inv = res[0]
check(abs(inv["lapse"] - (12.5 - 8.0) / 537 * 100) < 1e-9 and inv["lo"]["name"] == "Rečica" and inv["hi"]["name"] == "Črnivec",
      "gradient med najnižjo in najvišjo postajo", str(inv["lapse"]))
check(res[2]["pts"][1]["name"] == "Gornji Grad", "točke so urejene po višini")
one = js([{"fn": "valleyProfileSummary", "args": [[P("Rečica", 366, 8.0)]]},
          {"fn": "valleyProfileSummary", "args": [[P("Rečica", 366, 8.0), {"name": "X", "elev": 900, "t": None}]]},
          {"fn": "valleyProfileSummary", "args": [[]]}])
check(one == [None, None, None], "manj kot dve veljavni točki: brez povzetka (graf se skrije)", str(one))

# izris: brez NaN/undefined, vsebuje vse postaje in navedbo vira
prelude = "var captured=''; var el={set innerHTML(v){captured=v;},get innerHTML(){return captured;}};"
for name, pts in cases.items():
    html = js([{"expr": f"(renderValleyProfile(el, valleyProfileSummary({json.dumps(pts)})), captured)"}], prelude)[0]
    check("NaN" not in html and "undefined" not in html and "Infinity" not in html, f"izris {name}: brez NaN", html[:80])
    check(all(p["name"] in html for p in pts) and "DRSI" in html and "<svg" in html, f"izris {name}: postaje in vir")

# ── Junaški prerez doline (faza A1): valleyTempAt, valleyZeroHeight, hvColor, heroValleySvg ──
Q = [P("Rečica", 366, 2.0), P("Gornji Grad", 428, 4.0), P("Črnivec", 903, 8.0)]
at = js([{"fn": "valleyTempAt", "args": [Q, h]} for h in (300, 366, 397, 428, 665.5, 903, 1000)])
exp = [2.0, 2.0, 3.0, 4.0, 6.0, 8.0, 8.0 - 0.65 * 0.97]
check(all(abs(a - b) < 0.01 for a, b in zip(at, exp)), "valleyTempAt: spodaj ravno, med postajama linearno, nad vrhom −0,65/100 m", str(at))
check(js([{"fn": "valleyTempAt", "args": [[], 500]}])[0] is None, "valleyTempAt: brez točk = null")
zh = js([{"fn": "valleyZeroHeight", "args": [pts, 300, 1000]} for pts in (
    [P("Rečica", 366, 3.0), P("Črnivec", 903, -3.0)],        # 0 °C na sredini izmerjenega razpona
    [P("Rečica", 366, 2.0), P("Črnivec", 903, 0.4)],         # 0 °C šele nad izmerjenim (ocena, ~964 m)
    [P("Rečica", 366, -2.0), P("Črnivec", 903, -6.0)],       # povsod pod 0 °C
    [P("Rečica", 366, 10.0), P("Črnivec", 903, 14.0)],       # povsod nad 0 °C (inverzija)
    [P("Rečica", 366, -1.0), P("Črnivec", 903, 4.0)])])      # inverzija: 0 °C nad dolino, izmerjeno
check(zh[0] and abs(zh[0]["h"] - 634.5) < 3 and zh[0]["est"] is False, "valleyZeroHeight: sredina razpona, izmerjeno", str(zh[0]))
check(zh[1] and zh[1]["est"] is True and 955 < zh[1]["h"] < 975, "valleyZeroHeight: nad izmerjenim = ocena", str(zh[1]))
check(zh[2] is None and zh[3] is None, "valleyZeroHeight: ni preseka = null", str(zh[2:4]))
check(zh[4] and 366 < zh[4]["h"] < 903 and zh[4]["est"] is False, "valleyZeroHeight: inverzija, presek v izmerjenem razponu", str(zh[4]))
col = js([{"fn": "hvColor", "args": [t]} for t in (-20, -8, 3, 9, 30)])
check(col[0] == col[1] == "rgb(59,130,246)" and col[2] == "rgb(45,212,191)" and col[3] == "rgb(163,230,53)" and col[4] == "rgb(249,115,22)",
      "hvColor: robovi in ključne točke lestvice", str(col))
for name, pts_, w in (("inverzija", cases["inverzija"], 330), ("običajen", cases["običajen"], 900), ("samo Rečica", [P("Rečica", 366, 12.0)], 0)):
    svg = js([{"fn": "heroValleySvg", "args": [pts_, None, w]}], prelude="")[0]
    check("NaN" not in svg and "undefined" not in svg and "Infinity" not in svg, f"prerez {name}: brez NaN", svg[:80])
    check("<svg" in svg and 'role="img"' in svg and all(x["name"] in svg for x in pts_), f"prerez {name}: svg, aria in postaje")
    check("hv-air" in svg and "hv-ground" in svg, f"prerez {name}: stolpec zraka in teren")
small = js([{"fn": "heroValleySvg", "args": [cases["običajen"], None, 330]}])[0]
check("· 366 m" not in small, "prerez: ozek zaslon brez višin v oznakah (preprečuje prekrivanje)")
wide = js([{"fn": "heroValleySvg", "args": [cases["običajen"], None, 900]}])[0]
check("· 366 m" in wide and 'viewBox="0 0 900 162"' in wide, "prerez: širok zaslon z višinami, razmerje 0,18", wide[:90])
print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
