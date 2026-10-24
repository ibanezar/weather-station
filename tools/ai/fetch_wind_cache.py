#!/usr/bin/env python3
"""
Zajem napovedi vetra (sunki, smer) za eval_mtr7_wind.py: PRAVI arhiv `*_previous_dayN` (brez uhajanja).

  fetch_wind_cache.py WIND_OUT.json [--from 2024-05-26] [--to YYYY-MM-DD]

WIND_OUT  {lead: {datum: {"wind_gusts_10m": [[ura, km/h], ...], "wind_direction_10m": [[ura, stopinje], ...]}}}
Hitrost vetra (wind_speed_10m) je že v V1 zajemu (fetch_profile_cache.py --v1 / fetch_hourly_cache.py).
Zapis je ponovljiv: že zajeti vodilni časi se preskočijo; ob SSL EOF Open-Meteo `_get_json` ponavlja.
"""
import argparse, datetime as dt, json, os, sys, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import train_recica_mos as t   # noqa: E402

VARS = ["wind_gusts_10m", "wind_direction_10m"]
BASE = "https://historical-forecast-api.open-meteo.com/v1/forecast?"


def fetch(lead, start, end):
    rows = {}
    hourly = ",".join(f"{v}_previous_day{lead}" for v in VARS)
    for year in range(int(start[:4]), int(end[:4]) + 1):
        a, b = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        if a > b:
            continue
        q = urllib.parse.urlencode({"latitude": t.LAT, "longitude": t.LON, "start_date": a,
                                    "end_date": b, "hourly": hourly, "timezone": t.TZ})
        print(f"  veter D+{lead} {a} → {b} …", flush=True)
        h = (t._get_json(BASE + q, tries=8) or {}).get("hourly") or {}
        for i, ts in enumerate(h.get("time") or []):
            rec = rows.setdefault(ts[:10], {v: [] for v in VARS})
            for v in VARS:
                vals = h.get(f"{v}_previous_day{lead}") or []
                if i < len(vals) and vals[i] is not None:
                    rec[v].append([int(ts[11:13]), vals[i]])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--from", dest="start", default="2024-05-26")
    ap.add_argument("--to", dest="end", default=None)
    a = ap.parse_args()
    end = a.end or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    blob = json.load(open(a.out)) if os.path.exists(a.out) else {}
    for lead in t.LEADS:
        if str(lead) in blob:
            continue
        blob[str(lead)] = fetch(lead, a.start, end)
        json.dump(blob, open(a.out, "w"))
        n = sum(1 for d in blob[str(lead)].values() if d.get("wind_gusts_10m"))
        print(f"veter D+{lead}: {len(blob[str(lead)])} dni, od tega s sunki {n}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
