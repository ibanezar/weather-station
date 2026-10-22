#!/usr/bin/env python3
"""
Grobo pričakovana dnevna količina padavin MTR (mean_precip v predict_recica_mos.py):
povprečje best_match in drugih modelov, brez objave pri premalo virih; zajem dnevne vsote
po modelih v fetch_live_multi; zamrznitev `mm` v polju `today`.

usage: python3 tools/test_precip_amount.py
"""
import datetime as dt, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict_recica_mos as p  # noqa: E402

FAIL = []


def check(ok, name):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAIL.append(name)


mm, n = p.mean_precip(4.0, {"a": 6.0, "b": 2.0, "c": 8.0, "d": 5.0})
check((mm, n) == (5.0, 5), f"povprečje petih virov ({mm}, {n})")
mm, n = p.mean_precip(0.0, {"a": 0.0, "b": 0.3, "c": 0.0, "d": 0.0})
check(mm == 0.1 and n == 5, "zaokrožitev na 0,1 mm")
mm, n = p.mean_precip(4.0, {"a": 6.0, "b": 2.0, "c": 8.0})
check(mm == 5.0 and n == 4, "štirje viri še zadoščajo")
mm, n = p.mean_precip(4.0, {"a": 6.0, "b": 2.0})
check(mm is None and n == 3, "trije viri: količine ne objavimo")
mm, n = p.mean_precip(None, {"a": 6.0, "b": 2.0, "c": 8.0})
check(mm is None, "brez best_match količine ne objavimo")
mm, n = p.mean_precip(3.0, None)
check(mm is None and n == 1, "brez drugih modelov količine ne objavimo")

# fetch_live_multi: dnevna vsota padavin po modelu; model z < 20 urami ne šteje
def fake_forecast(m):
    full = [(h, 0.5) for h in range(24)]
    return {"2026-10-23": {"temperature_2m": [(h, 10.0) for h in range(24)],
                           "precipitation": full if m != "kratek" else full[:5]}}

orig = p.fetch_live_forecast
p.fetch_live_forecast = fake_forecast
try:
    out = p.fetch_live_multi(["ecmwf_ifs025", "kratek"])
finally:
    p.fetch_live_forecast = orig
e = out["2026-10-23"]
check(abs(e["prec"]["ecmwf_ifs025"] - 12.0) < 1e-9, "dnevna vsota padavin po modelu")
check("kratek" not in e["prec"] and "kratek" in e["tmax"], "premalo ur padavin: model brez prec, temperatura ostane")

# zamrznitev: mm gre v `today`
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "n.json")
    json.dump({"generated_at": "2026-10-21T06:30:00Z",
               "days": [{"date": "2026-10-22", "lead": 1, "pop": 0.9, "pop1": 0.8, "pop5": 0.4,
                         "mm": 7.5, "mm_n": 5}]}, open(path, "w"))
    fz = p.frozen_today(path, dt.date(2026, 10, 22))
    check(fz and fz["mm"] == 7.5 and fz["mm_n"] == 5, "mm se zamrzne v `today`")

sys.exit(1 if FAIL else 0)
