#!/usr/bin/env python3
"""
tools/test_sneg_mos.py -- MTR sneg (proksi): značilke, učenje, napoved, sezona, dnevnik, preverjanje.

Brez omrežja: Open-Meteo nadomestijo lažni vnosi. Model v repozitoriju se preveri samo po obliki.
"""
import csv
import datetime as dt
import json
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import predict_sneg_mos as ps  # noqa: E402
import train_sneg_mos as tsm   # noqa: E402
import verify_sneg as vs       # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✓ " if ok else "  ✗ ") + name)
    fails += 0 if ok else 1


# --- proksi
check("proksi: mokro in hladno = 1", tsm.is_snow_day(3.0, 0.5) == 1)
check("proksi: suho in hladno = 0", tsm.is_snow_day(0.0, -5.0) == 0)
check("proksi: mokro in toplo = 0", tsm.is_snow_day(10.0, 6.0) == 0)
check("proksi: mejni prag 0,2 mm in 1,0 °C šteje", tsm.is_snow_day(0.2, 1.0) == 1 and tsm.is_snow_day(0.1, 1.0) == 0)

# --- značilke
f = tsm.day_features({"best_match": (2.0, -2.0, 4.0), "ecmwf_ifs025": (4.0, 0.0, 2.0),
                      "gfs_seamless": (6.0, 2.0, 0.0), "icon_seamless": (0.0, -4.0, 6.0)})
check("značilke: povprečje T in padavin čez modele", abs(f["tavg"] - 1.0) < 1e-9 and abs(f["prec"] - 3.0) < 1e-9)
check("značilke: delež mokrih modelov", abs(f["wetfrac"] - 0.75) < 1e-9)
check("značilke: premalo modelov -> None", tsm.day_features({"best_match": (1.0, 0.0, 1.0)}) is None)
check("značilke: manjkajoča vrednost izloči model",
      tsm.day_features({"best_match": (1.0, 0.0, None), "ecmwf_ifs025": (1.0, 0.0, 1.0),
                        "gfs_seamless": (1.0, 0.0, 1.0)}) is None)
check("značilke: neznan model se ne šteje",
      tsm.day_features({"best_match": (1.0, 0.0, 1.0), "ecmwf_ifs025": (1.0, 0.0, 1.0),
                        "neznan": (1.0, 0.0, 1.0)}) is None)

# --- matematika
rng = np.random.default_rng(1)
X = np.column_stack([np.ones(400), rng.normal(0, 1, 400)])
y = (rng.random(400) < 1 / (1 + np.exp(-(0.5 + 2.0 * X[:, 1])))).astype(float)
w = tsm.fit_logit(X, y, ridge=0.1)
check("logit: obnovi smer in približno velikost koeficienta", 1.2 < w[1] < 3.0 and -0.3 < w[0] < 1.3)
a, b = tsm.fit_calibration(X @ w * 3.0, y)     # prevelik logit -> naklon b < 1
check("kalibracija: preveč samozavesten logit dobi b < 1", b < 0.8)
a2, b2 = tsm.fit_calibration(X @ w, y)
check("kalibracija: dober logit ostane blizu b = 1", 0.7 < b2 < 1.3)
check("AUC: popoln razvrstitev = 1", tsm.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0)

# --- učenje na sintetičnih podatkih: več dni, mokro in hladno -> sneg
truth, by = {}, {lead: {} for lead in tsm.LEADS}
start = dt.date(2024, 10, 1)
for i in range(700):
    d = start + dt.timedelta(days=i)
    if d.month not in tsm.SEASON:
        continue
    t = 4 * np.sin((d.timetuple().tm_yday + 80) / 58.0) + rng.normal(0, 3)
    p = max(0.0, rng.normal(0.5, 3))
    iso = d.isoformat()
    truth[iso] = (p, t, tsm.is_snow_day(p, t))
    for lead in tsm.LEADS:
        by[lead][iso] = {m: (t + 3 + rng.normal(0, .5), t - 3 + rng.normal(0, .5), max(0.0, p + rng.normal(0, .3)))
                         for m in tsm.MODELS}
by = {k: v for k, v in by.items()}
model = tsm.train(truth, by)
check("učenje: naučil je vse tri vodilne čase", set(model["leads"]) == {"1", "2", "3"})
e = model["leads"]["1"]
cold_wet = tsm.day_features({m: (-1.0, -5.0, 5.0) for m in tsm.MODELS})
warm_wet = tsm.day_features({m: (12.0, 6.0, 5.0) for m in tsm.MODELS})
cold_dry = tsm.day_features({m: (-1.0, -5.0, 0.0) for m in tsm.MODELS})
pw, pwarm, pdry = tsm.predict_p(e, cold_wet), tsm.predict_p(e, warm_wet), tsm.predict_p(e, cold_dry)
check("napoved: mokro in mrzlo >> toplo in mokro", pw > 0.5 and pwarm < 0.1)
check("napoved: mrzlo a suho < mrzlo in mokro", pdry < pw)
check("napoved: verjetnost je v [0, 1]", all(0.0 <= v <= 1.0 for v in (pw, pwarm, pdry)))
check("model: cilj in opozorilo o proksiju sta zapisana",
      "proksi" in model["target"]["name"] and "ne meri" in model["target"]["caveat"])

# --- model v repozitoriju (oblika)
try:
    real = json.load(open(tsm.MODEL_PATH, encoding="utf-8"))
    ok = all(len(v["coefficients"]) == len(vec) for v in real["leads"].values()
             for vec in [tsm.vector({"tavg": 0, "prec": 0, "wetfrac": 0})])
    check("model/sneg-mos.json: število koeficientov = število značilk", ok and real["leads"])
    check("model/sneg-mos.json: cilj je označen kot proksi", "proksi" in real["target"]["name"])
except FileNotFoundError:
    check("model/sneg-mos.json obstaja", False)

# --- napoved z lažnimi vnosi
today = dt.date(2026, 11, 10)
per_day = {(today + dt.timedelta(days=l)).isoformat(): {m: (-1.0, -5.0, 5.0) for m in tsm.MODELS} for l in (1, 2, 3)}
days = ps.predict_days(real, per_day, today)
check("predict_days: tri dni v sezoni", [d["lead"] for d in days] == [1, 2, 3])
check("predict_days: visoka verjetnost ob mrazu in padavinah", all(d["p_snow"] > 0.3 for d in days))
days_apr = ps.predict_days(real, {(dt.date(2027, 4, 29) + dt.timedelta(days=l)).isoformat():
                                  {m: (-1.0, -5.0, 5.0) for m in tsm.MODELS} for l in (1, 2, 3)}, dt.date(2027, 4, 29))
check("predict_days: dnevi zunaj sezone (maj) izpadejo", [d["lead"] for d in days_apr] == [1])
check("predict_days: premalo modelov -> dan izpade",
      ps.predict_days(real, {(today + dt.timedelta(days=1)).isoformat(): {"best_match": (0.0, -3.0, 2.0)}}, today) == [])

# --- dnevnik
tmp = tempfile.mkdtemp()
log = os.path.join(tmp, "data", "log.csv")
payload = ps.build_payload(real, days, True, dt.datetime(2026, 11, 10, 4, 40, tzinfo=dt.timezone.utc))
n1 = ps.append_log(payload, log)
n2 = ps.append_log(payload, log)
rows = list(csv.DictReader(open(log, encoding="utf-8")))
check("dnevnik: prvi zapis doda 3 vrstice, ponovni nič", n1 == 3 and n2 == 0 and len(rows) == 3)
hb = {int(r["lead_days"]): float(r["hours_before"]) for r in rows}
check("dnevnik: hours_before = ure do začetka ciljnega dne (lokalni čas)", 18.0 < hb[1] < 20.0 and abs(hb[2] - hb[1] - 24) < 1.1)
check("dnevnik: izdana datoteka ne vsebuje notranjih meritev", "indoor" not in json.dumps(payload).lower())

# --- utrip zunaj sezone
hb_path = os.path.join(tmp, "napoved.json")
check("utrip: brez datoteke je zapis potreben", ps.heartbeat_due(hb_path, "2026-07-01"))
json.dump({"in_season": False, "generated_at": "2026-07-01T04:40:00Z"}, open(hb_path, "w"))
check("utrip: isti dan ne ponovi", not ps.heartbeat_due(hb_path, "2026-07-01"))
check("utrip: naslednji dan ponovi", ps.heartbeat_due(hb_path, "2026-07-02"))

# --- preverjanje naprej v času
rows_v = [
    {"issued_at": "a", "valid_at": "2026-12-05", "hours_before": "42.0", "p_snow": "0.8"},   # D+2, zgodnejša
    {"issued_at": "b", "valid_at": "2026-12-05", "hours_before": "30.0", "p_snow": "0.2"},   # D+2, poznejša (ignoriraj)
    {"issued_at": "c", "valid_at": "2026-12-05", "hours_before": "18.0", "p_snow": "0.9"},   # D+1
    {"issued_at": "d", "valid_at": "2026-12-05", "hours_before": "-3.0", "p_snow": "0.9"},   # dan že teče
]
best = vs.pick_issues(rows_v)
check("verify: izbere najzgodnejšo izdajo v razredu vodilnega časa",
      best[("2026-12-05", 2)][1] == 0.8 and best[("2026-12-05", 1)][1] == 0.9)
check("verify: dan, ki že teče, se ne šteje", all(k[1] in (1, 2) for k in best))
res = vs.evaluate(best, {"2026-12-05": (3.0, -1.0, 1)}, real)
check("verify: Brier D+1 = (0,9 - 1)^2", abs(res["1"]["brier"] - 0.01) < 1e-9)
check("verify: malo dogodkov = zgodno", res["1"]["preliminary"] and res["1"]["events"] == 1)
check("verify: vodilni čas brez podatkov ima n = 0", res["3"]["n"] == 0)

print("\n" + ("VSE V REDU" if not fails else f"{fails} NAPAK"))
sys.exit(1 if fails else 0)
