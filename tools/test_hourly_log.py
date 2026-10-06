#!/usr/bin/env python3
"""tools/test_hourly_log.py — urni zajem: nova zunanja polja, brez notranjih, brez prepisa."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import log_hourly_observations as L  # noqa: E402

FAILS = []
def check(ok, name):
    if not ok:
        FAILS.append(name); print("  ✗", name)

def lst(vals):  # {unix ts: value}, 2026-10-04 12:00..12:55 Europe/Ljubljana (UTC+2)
    base = 1759572000  # 2026-10-04T10:00Z = 12:00 local
    return {"list": {str(base + 300 * i): v for i, v in enumerate(vals)}}

data = {
    "outdoor": {"temperature": lst([10.0, 12.0]), "humidity": lst([80, 90]), "dew_point": lst([6.0, 8.0])},
    "wind": {"wind_speed": lst([4.0, 6.0]), "wind_gust": lst([8.0, 14.0])},
    "pressure": {"relative": lst([1015.0, 1016.0])},
    "solar_and_uvi": {"solar": lst([200.0, 9999.0])},
    "rainfall": {"daily": lst([0.0, 0.0])},
    "indoor": {"temperature": lst([23.47, 23.47]), "humidity": lst([47.3, 47.3])},  # must never appear
}
h = L.hourly_from_ecowitt(data, "2026-10-04")
b = h[12]
check(b["dewpoint_c"] == 7.0 and b["wind_kmh"] == 5.0 and b["gust_kmh"] == 14.0, "mean/max aggregation")
check(b["pressure_hpa"] == 1015.5, "pressure")
check(b["solar_wm2"] == 200.0, "solar glitch (>1500) dropped")
check("23.47" not in repr(h) and "47.3" not in repr(h), "indoor values not read")
check(set(L.FIELDS) >= set(L.EXTRA), "all extra columns in FIELDS")

# existing old-format row: extras are filled, existing values untouched
rows = [{"valid_at_local": "2026-10-04T12:00", "temp_c": "99.0", "precip_mm": "0.0",
         "humidity_pct": "85.0", "quality_flag": "ok"}]
seen = {"2026-10-04T12:00"}
n, flag, added, filled = L.ingest_day("2026-10-04", rows, seen, data)
check(rows[0]["temp_c"] == "99.0" and rows[0]["dewpoint_c"] == 7.0 and filled == 5 and added == 0, "backfill fills only empty")
print("OK" if not FAILS else f"{len(FAILS)} FAIL"); sys.exit(1 if FAILS else 0)
