#!/usr/bin/env python3
"""
tools/test_mtr_live.py — `predict_recica_mos.py --live` piše samo živo datoteko.

Zamrznjena napoved (napoved-modela.json) gre na semafor točnosti in je čez dan ne smemo
prepisati; živa jo mora le brati (za `today`). Mrežo in model nadomestijo lažni vnosi.
"""
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import predict_recica_mos as pm  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✓ " if ok else "  ✗ ") + name)
    fails += 0 if ok else 1


today = dt.date.today()
tmp = tempfile.mkdtemp()
frozen = os.path.join(tmp, "napoved-modela.json")
live = os.path.join(tmp, "napoved-modela-live.json")
FROZEN_TXT = json.dumps({
    "generated_at": "2000-01-01T00:00:00Z",
    "days": [{"date": today.isoformat(), "lead": 1, "pop": 0.4, "mm": 2.0}],
})
with open(frozen, "w", encoding="utf-8") as f:
    f.write(FROZEN_TXT)

pm.OUT_PATH, pm.LIVE_PATH = frozen, live
pm.load_model = lambda: {}
pm.fetch_live_forecast = lambda model_id=None: {
    (today + dt.timedelta(days=l)).isoformat(): [1] for l in pm.mos.LEADS}
pm.fetch_wn2_spread = lambda: {}
pm.mos.daily_features = lambda series, target: {"om_prec": 1.0}
pm.predict_day = lambda model, lead, feats: {
    "tmax": 10.0, "tmin": 2.0, "om_tmax": 9.0, "om_tmin": 3.0, "d_tmax": 1.0, "d_tmin": -1.0, "pop": 0.7}

print("MTR live")
sys.argv = ["predict_recica_mos.py", "--live"]
check("izhod 0", pm.main() == 0)
check("zamrznjena datoteka je nedotaknjena", open(frozen, encoding="utf-8").read() == FROZEN_TXT)
check("živa datoteka obstaja", os.path.exists(live))
j = json.load(open(live, encoding="utf-8"))
check("živa nosi dneve D+1…", len(j["days"]) == len(pm.mos.LEADS) and j["days"][0]["pop"] == 0.7)
check("živa nosi `today` iz zamrznjene (pop 0,4)", (j.get("today") or {}).get("pop") == 0.4)

sys.argv = ["predict_recica_mos.py"]
os.remove(live)
check("brez --live piše zamrznjeno, ne žive", pm.main() == 0 and not os.path.exists(live)
      and json.load(open(frozen, encoding="utf-8"))["days"][0]["pop"] == 0.7)

print(f"\n{'OK' if not fails else 'NAPAKE: ' + str(fails)}")
sys.exit(1 if fails else 0)
