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

livelog = os.path.join(tmp, "data", "mtr-live-log.csv")
pm.OUT_PATH, pm.LIVE_PATH, pm.LIVE_LOG_PATH = frozen, live, livelog
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

import csv  # noqa: E402
rows = list(csv.DictReader(open(livelog, encoding="utf-8")))
check("dnevnik: ena vrstica na dan", len(rows) == len(pm.mos.LEADS))
check("dnevnik: stolpci in vrednosti", list(rows[0]) == pm.LIVE_LOG_FIELDS and rows[0]["tmax"] == "10.0"
      and rows[0]["pop"] == "0.7" and rows[0]["p_frost"] == "")
check("dnevnik: valid_at/lead sledita napovedi", rows[0]["lead_days"] == "1"
      and rows[0]["valid_at"] == (today + dt.timedelta(days=1)).isoformat())

# hours_before: izdaja 16:40 UTC (18:40 CEST) → začetek jutrišnjega dne po 5 h 20 min
t0 = dt.datetime(2026, 10, 24, 16, 40, tzinfo=dt.timezone.utc)
pay = {"generated_at": "2026-10-24T16:40:00Z", "days": [
    {"date": "2026-10-25", "lead": 1, "tmax": 1.0, "tmin": 0.0, "pop": 0.1},
    {"date": "2026-10-26", "lead": 2, "tmax": 2.0, "tmin": 1.0, "pop": 0.2}]}
lp = os.path.join(tmp, "x", "log.csv")
check("hours_before (poletni → zimski čas: 25. 10. 00:00 CEST)", pm.append_live_log(pay, lp, t0) == 2
      and list(csv.DictReader(open(lp)))[0]["hours_before"] == "5.3")
check("zimski čas: 26. 10. 00:00 CET = 30,3 h", list(csv.DictReader(open(lp)))[1]["hours_before"] == "30.3")
check("ista osvežitev se ne zapiše dvakrat", pm.append_live_log(pay, lp, t0) == 0
      and len(list(csv.DictReader(open(lp)))) == 2)
check("druga osvežitev se doda (brez drugega glavnega stolpca)",
      pm.append_live_log(dict(pay, generated_at="2026-10-24T22:40:00Z"), lp) == 2
      and len(open(lp, encoding="utf-8").read().splitlines()) == 5)

os.remove(livelog)
sys.argv = ["predict_recica_mos.py", "--live", "--no-write"]
check("--no-write ne piše dnevnika", pm.main() == 0 and not os.path.exists(livelog))

sys.argv = ["predict_recica_mos.py"]
os.remove(live)
check("brez --live piše zamrznjeno, ne žive", pm.main() == 0 and not os.path.exists(live)
      and json.load(open(frozen, encoding="utf-8"))["days"][0]["pop"] == 0.7)
check("zamrznjena napoved ne gre v dnevnik živih", not os.path.exists(livelog))

# analiza dnevnika (sintetično): osvežitev 12–18 h pred dnevom je točna, zamrznjena zgreši za 2 °C
sys.path.insert(0, os.path.join(HERE, "ai"))
import eval_live_refresh as ev  # noqa: E402
ver, rows2 = {}, []
for i in range(25):
    d = (dt.date(2026, 11, 1) + dt.timedelta(days=i)).isoformat()
    ver[d] = {"actual": {"tmax": 10.0, "tmin": 2.0}, "meteorec": {"tmax": 12.0, "tmin": 4.0}}
    rows2.append({"valid_at": d, "hours_before": "14.0", "tmax": "10.0", "tmin": "2.0"})
    rows2.append({"valid_at": d, "hours_before": "20.0", "tmax": "11.0", "tmin": "3.0"})
    rows2.append({"valid_at": d, "hours_before": "-1.0", "tmax": "10.0", "tmin": "2.0"})
res = ev.analyze(rows2, ver)
r = res["12–18 h"]["tmax"]
check("analiza: razredi po hours_before", set(res) == {"12–18 h", "18–24 h", "že teče (≤0 h)"})
check("analiza: MAE osvežitve 0, zamrznjene 2, diff +2 in REAL+",
      r["n"] == 25 and r["mae_live"] == 0.0 and r["mae_frozen"] == 2.0 and abs(r["diff"] - 2.0) < 1e-9 and r["lo"] > 0)
check("analiza: razred 18–24 h (napaka 1 proti 2) je boljši za 1", abs(res["18–24 h"]["tmin"]["diff"] - 1.0) < 1e-9)
few = ev.analyze(rows2[:12], ver)
check("analiza: pod 20 dni ni sklepa (brez diff)", "diff" not in few["12–18 h"]["tmax"])
check("analiza: zadnja izdaja v razredu zmaga (13 h pred 14 h)", ev.analyze(
    [{"valid_at": "2026-11-01", "hours_before": "14.0", "tmax": "0.0", "tmin": "0.0"},
     {"valid_at": "2026-11-01", "hours_before": "13.0", "tmax": "10.0", "tmin": "2.0"}],
    {"2026-11-01": ver["2026-11-01"]})["12–18 h"]["tmax"]["mae_live"] == 0.0)
check("analiza: neveljavna vrstica se preskoči", ev.analyze([{"valid_at": "x", "hours_before": ""}], {}) == {})

print(f"\n{'OK' if not fails else 'NAPAKE: ' + str(fails)}")
sys.exit(1 if fails else 0)
