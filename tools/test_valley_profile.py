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
                                                                      "renderValleyProfile", "_duelNum"],
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
print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
