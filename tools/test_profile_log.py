#!/usr/bin/env python3
"""tools/test_profile_log.py — dnevni stolpci napovedi profila (lažen Open-Meteo odgovor) in
usklajenost z eval_mtr4 (ista funkcija, ista preslikava skupin)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ai"))
import log_profile_forecasts as L  # noqa: E402
import eval_mtr4 as E              # noqa: E402

fails = []
def check(ok, n):
    if not ok: fails.append(n); print("  ✗", n)

days = ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28"]
times = [f"{d}T{h:02d}:00" for d in days for h in range(24)]
n = len(times)
h = {"time": times}
# T2m: noč 2 °C, dan 12 °C; T925 = T2m + 3 (inverzija ponoči: +3); T850 = T2m - 4
t2 = [12.0 if 10 <= i % 24 <= 18 else 2.0 for i in range(n)]
h["temperature_2m"] = t2
h["temperature_925hPa"] = [x + 3 for x in t2]
h["temperature_850hPa"] = [x - 4 for x in t2]
h["wind_speed_925hPa"] = [10.0] * n
h["cloud_cover_low"] = [80.0 if i % 24 < 9 else 20.0 for i in range(n)]
h["cloud_cover_mid"] = [30.0] * n
h["cloud_cover_high"] = [50.0] * n
h["snow_depth"] = [0.0] * n
h["soil_moisture_0_to_7cm"] = [0.35] * n
h["boundary_layer_height"] = [100.0 if i % 24 < 9 else 900.0 for i in range(n)]
# 28. 10. (lead 4) je izven LEADS; 2. dan ima premalo ur temperature
for i, ts in enumerate(times):
    if ts.startswith("2026-10-26") and ts[11:13] >= "05":
        h["temperature_2m"][i] = None

out = L.summarize({"hourly": h}, "2026-10-24")
check(sorted(out) == ["2026-10-25", "2026-10-27"], f"vodilni časi/popolnost: {sorted(out)}")
r = out["2026-10-25"]
check(r["lead_days"] == 1 and r["issued_at"] == "2026-10-24", "lead/issued")
check(r["inv_n"] == 3.0, f"inv_n {r['inv_n']}")
check(r["lapse_d"] == -4.0 and r["t850_d"] == 8.0, f"lapse/t850 {r['lapse_d']} {r['t850_d']}")
check(r["low_n"] == 80.0 and r["low_d"] == 20.0 and r["mid_d"] == 30.0 and r["high_d"] == 50.0, "oblačnost")
check(r["blh_max"] == 900.0 and r["snow_max"] == 0.0 and r["soil_mean"] == 0.35, "mejna plast/sneg/tla")
check(r["t2_max"] == 12.0 and r["t2_min"] == 2.0, "t2 ekstrema")
check(out["2026-10-27"]["lead_days"] == 3, "lead 3")
check(L.daily_columns({"temperature_2m": [(0, 1.0)]}) is None, "premalo ur → None")

# manjkajoča polja ne podrejo ničesar in so prazna
h2 = {k: v for k, v in h.items() if k not in ("temperature_850hPa", "snow_depth")}
r2 = L.summarize({"hourly": h2}, "2026-10-24")["2026-10-25"]
check(r2["lapse_d"] == "" and r2["t850_d"] == "" and r2["snow_max"] == "" and r2["inv_n"] == 3.0, "manjkajoče spremenljivke")

# eval_mtr4 uporablja isto agregacijo in preslikavo
rec = {k: [[i % 24, v] for i, v in enumerate(vals) if v is not None and times[i].startswith("2026-10-25")]
       for k, vals in h.items() if k != "time"}
g = E.profile_features(rec)
check(g["prof"] == [3.0 / 5, -4.0 / 10, 8.0 / 10, 10.0 / 20], f"prof {g['prof']}")
check(g["stab"] == [3.0 / 5, -4.0 / 10], "stab")
check(g["ctrl"] == [1.2, 0.2], "ctrl")
check(g["cloud3"] == [0.8, 0.2, 0.3, 0.5], "cloud3")
check(g["snow"][:2] == [0.0, 0.0] and abs(g["snow"][2] - 0.25) < 1e-9, f"snow {g['snow']}")
check(g["blh"] == [0.9], "blh")

# vrstice so v dnevniku samo zunanje vrednosti (zasebnost: nobenega notranjega polja)
check(not any("indoor" in f.lower() for f in L.FIELDS + L.VARS), "brez notranjih polj")
print("OK" if not fails else f"{len(fails)} FAIL"); sys.exit(1 if fails else 0)
