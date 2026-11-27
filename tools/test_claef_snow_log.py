#!/usr/bin/env python3
"""tools/test_claef_snow_log.py — dnevnik napovedi snega C-LAEF (lažen odgovor Open-Meteo) in ocena proti ARSO."""
import csv, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ai"))
import log_claef_snow as L   # noqa: E402
import eval_claef_snow as E  # noqa: E402

fails = []
def check(ok, n):
    if not ok: fails.append(n); print("  ✗", n)

days = ["2026-11-27", "2026-11-28", "2026-11-29", "2026-11-30"]
times = [f"{d}T{h:02d}:00" for d in days for h in range(24)]
n = len(times)
H = {"time": times}
# ICON-D2: 0,1 cm/h 28. 11. (24 ur = 2,4 cm), višina 0,13 m; C-LAEF: samo do 29. 11. ob 11:00 (60 h), višina brez enote
H["snowfall_icon_d2"] = [0.1 if t.startswith("2026-11-28") else 0.0 for t in times]
H["snow_depth_icon_d2"] = [0.13] * n
c = [None] * n
for i, t in enumerate(times):
    if t < "2026-11-29T12:00":
        c[i] = 0.2 if t.startswith("2026-11-28") else 0.0
H["snowfall_geosphere_claef_austria"] = c
H["snow_depth_geosphere_claef_austria"] = [0.5 if x is not None else None for x in c]
loc = {"elevation": 446.0, "hourly": H, "hourly_units": {"snow_depth_icon_d2": "m", "snow_depth_geosphere_claef_austria": "undefined"}}
st = {"GORNJ-GRA_": (46.2987, 14.8063, 428.0)}

out = L.summarize(["GORNJ-GRA_"], [loc], st, "2026-11-27")
ic = out[("2026-11-28", "GORNJ-GRA_", "icon_d2")]
check(ic["lead_days"] == 1 and ic["alt_m"] == 428.0 and ic["cell_elev_m"] == 446.0, "lead/višine")
check(abs(ic["snow_new_cm"] - 2.4) < 1e-9 and ic["depth07_raw"] == 0.13 and ic["depth_unit"] == "m", f"ICON-D2 vrstica {ic}")
cl = out[("2026-11-28", "GORNJ-GRA_", "geosphere_claef_austria")]
check(abs(cl["snow_new_cm"] - 4.8) < 1e-9 and cl["depth07_raw"] == 0.5 and cl["depth_unit"] == "undefined",
      "C-LAEF: surova vrednost in enota nespremenjeni")
c3 = out.get(("2026-11-29", "GORNJ-GRA_", "geosphere_claef_austria"))
check(c3 is not None and c3["snow_new_cm"] == "" and c3["depth07_raw"] == 0.5, "C-LAEF: nepopoln dan (60 h) nima vsote snega")
check(("2026-11-30", "GORNJ-GRA_", "geosphere_claef_austria") not in out, "C-LAEF: dan brez podatkov ni vrstica")
check(("2026-11-27", "GORNJ-GRA_", "icon_d2") not in out, "lead 0 se ne beleži")
check(all(k[2] != "ecmwf_ifs025" for k in out), "model brez podatkov ni vrstica")

# ocena proti ARSO: odčitek mora biti po jutranjem odčitku (≥ 5:30 UTC), ponoči (00:50Z) ne šteje
with tempfile.TemporaryDirectory() as d:
    lg, ar = os.path.join(d, "log.csv"), os.path.join(d, "arso.csv")
    with open(lg, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=L.FIELDS); w.writeheader()
        for r in out.values():
            w.writerow({k: r.get(k, "") for k in L.FIELDS})
    with open(ar, "w", encoding="utf-8", newline="") as f:
        f.write("valid_utc,id,name,alt_m,lat,lon,t,snow_cm,rr_mm,tp_12h_mm\n")
        f.write("2026-11-28T00:50Z,GORNJ-GRA_,Gornji Grad,428.0,46.2,14.8,-1,99.0,0,0\n")   # ponoč: ne šteje
        f.write("2026-11-28T06:50Z,GORNJ-GRA_,Gornji Grad,428.0,46.2,14.8,-1,13.0,0,0\n")
        f.write("2026-11-28T12:50Z,GORNJ-GRA_,Gornji Grad,428.0,46.2,14.8,-1,50.0,0,0\n")  # pozneje: prvi zmaga
    obs = E.observed(ar)
    check(obs == {("GORNJ-GRA_", "2026-11-28"): 13.0}, f"odčitek ARSO {obs}")
    depth, new = E.pairs(lg, ar)
    ic_p = depth[("icon_d2", 1)]
    check(len(ic_p) == 1 and abs(ic_p[0][0] - 13.0) < 1e-9 and ic_p[0][1] == 13.0, f"ICON-D2: m → cm {ic_p}")
    check(("geosphere_claef_austria", 1) not in depth, "C-LAEF: višine odeje ne primerjamo (enota in vrednost nista znani)")
    check(not new, "novi sneg: brez meritve prejšnjega jutra ni para")
    with open(ar, "a", encoding="utf-8", newline="") as f:
        f.write("2026-11-27T06:50Z,GORNJ-GRA_,Gornji Grad,428.0,46.2,14.8,-1,10.0,0,0\n")   # dan prej: 10 cm
    depth, new = E.pairs(lg, ar)
    check(new[("icon_d2", 1)][0][:2] == (2.4, 3.0), f"novi sneg ICON-D2: model 2,4 cm proti prirastku 3 cm {new.get(('icon_d2', 1))}")
    check(new[("geosphere_claef_austria", 1)][0][:2] == (4.8, 3.0), "novi sneg C-LAEF")

# brez postaj ali dnevnika se ne zgodi nič hudega
check(L.read_stations("/nonexistent.csv") == {}, "manjkajoč dnevnik ARSO → prazno")
real = L.read_stations()
check(set(real) <= set(L.STATIONS), "postaje so podmnožica seznama")

if fails:
    print(f"✗ {len(fails)} napak"); sys.exit(1)
print("✓ test_claef_snow_log: vse v redu")
