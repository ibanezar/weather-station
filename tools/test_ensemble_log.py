#!/usr/bin/env python3
"""tools/test_ensemble_log.py — povzetek članov ansambla (lažen Open-Meteo odgovor)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import log_ensemble_forecasts as L  # noqa: E402

times = [f"2026-10-0{d}T{h:02d}:00" for d in (7, 8) for h in range(24)]
def col(v): return [v] * 48
h = {"time": times}
# 5 members for ecmwf: control + member01..04; Tmin day 1 = -1, 0.5, 1, 2, 3 -> p_frost 0.2 (only -1 <= 0)
for i, tn in enumerate([-1.0, 0.5, 1.0, 2.0, 3.0]):
    name = "" if i == 0 else f"_member{i:02d}"
    t = [tn + (10 if 10 <= j % 24 <= 16 else 0) for j in range(48)]
    h[f"temperature_2m{name}_ecmwf_ifs025_ensemble"] = t
    h[f"precipitation{name}_ecmwf_ifs025_ensemble"] = [0.0 if i < 3 else 0.1] * 48   # 2.4 mm/day for members 3,4
out = L.summarize({"hourly": h}, "2026-10-06")
r = out[("ecmwf_ifs025", "2026-10-07")]
fails = []
def check(ok, n):
    if not ok: fails.append(n); print("  ✗", n)
check(r["n_members"] == 5 and r["lead_days"] == 1, "members/lead")
check(r["p_frost"] == 0.2, f"p_frost {r['p_frost']}")
check(r["p_wet"] == 0.4, f"p_wet {r['p_wet']}")
check(r["tmax_p50"] == 11.0 and r["tmin_p50"] == 1.0, "quantiles")
check(("icon_seamless", "2026-10-07") not in out, "absent model skipped")
check(("ecmwf_ifs025", "2026-10-06") not in out, "lead 0 skipped")
print("OK" if not fails else f"{len(fails)} FAIL"); sys.exit(1 if fails else 0)
