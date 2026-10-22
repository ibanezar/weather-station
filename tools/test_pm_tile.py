#!/usr/bin/env python3
"""tools/test_pm_tile.py — ploščica PM2,5 (Varpolje) v herou (app.js: pmBand / pmTileModel).

Zaženi:  python3 tools/test_pm_tile.py
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


def js(calls):
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT,
                       input=json.dumps({"file": "app.js", "names": ["PM_MAX_AGE_MIN", "pmBand", "pmTileModel"], "calls": calls}))
    out = json.loads(p.stdout)
    assert "results" in out, out
    return out["results"]


# razredi lestvice EAQI (urna, PM2,5): meje vključene v nižji razred
bands = js([{"fn": "pmBand", "args": [v]} for v in (0, 10, 10.1, 20, 25, 25.1, 50, 75, 75.1, 300)])
labels = [b["label"] for b in bands]
check(labels == ["Zelo dobro", "Zelo dobro", "Dobro", "Dobro", "Zmerno", "Slabo", "Slabo", "Zelo slabo", "Nevarno", "Nevarno"],
      "pmBand: meje razredov", str(labels))
check(js([{"fn": "pmBand", "args": [None]}, {"fn": "pmBand", "args": ["x"]}]) == [None, None], "pmBand: brez vrednosti = null")

NOW = 1_800_000_000_000
iso = lambda mins: __import__("datetime").datetime.fromtimestamp(NOW / 1000 - mins * 60, __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
mk = lambda pm, avg, age: {"updated_utc": iso(age), "current": {"pm25_ugm3": pm, "pm25_24h_avg_ugm3": avg}}  # noqa: E731
cases = [mk(7.46, 12.04, 5), mk(1, 85.8, 5), mk(None, 5, 5), mk(12, 10, 46), mk(12, 10, 45), mk(12, None, 0), None,
         {"updated_utc": None, "current": {"pm25_ugm3": 9}}, {"updated_utc": iso(1), "current": {}}]
res = js([{"fn": "pmTileModel", "args": [c, NOW]} for c in cases])
check(res[0]["value"] == "7,5" and res[0]["band"]["label"] == "Zelo dobro" and "24 h povpr. 12,0" in res[0]["sub"], "model: običajen posnetek, decimalna vejica", str(res[0]))
check(res[1]["value"] == "1,0" and "85,8" in res[1]["sub"], "model: nizka trenutna, visoko 24 h povprečje se vidi", str(res[1]))
check(res[2]["value"] is None and res[2]["sub"] == "meritev ni dosegljiva", "model: pm25 = null", str(res[2]))
check(res[3]["value"] is None and "star 46 min" in res[3]["sub"], "model: posnetek starejši od 45 min se ne prikaže", str(res[3]))
check(res[4]["value"] == "12,0", "model: točno 45 min še velja", str(res[4]))
check(res[5]["value"] == "12,0" and "24 h" not in res[5]["sub"], "model: brez 24 h povprečja", str(res[5]))
check(res[6]["value"] is None and res[7]["value"] is None and res[8]["value"] is None, "model: manjkajoči podatki = brez vrednosti")
check(all("NaN" not in json.dumps(r) and "undefined" not in json.dumps(r) for r in res), "model: brez NaN in undefined")
print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
