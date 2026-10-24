#!/usr/bin/env python3
"""
Zajem urnih serij za eval_mtr4.py (višinski nivoji, sloji oblačnosti, sneg, tla, mejna plast).

  fetch_profile_cache.py PROFILE_OUT.json [--from 2024-05-26] [--to YYYY-MM-DD] [--v1 V1_OUT.json]

PROFILE_OUT  {"profile": {datum: {spremenljivka: [[ura, vrednost], ...]}},
              "sun": {lead: {datum: [[ura, sekunde sonca v uri], ...]}}}
V1_OUT       (neobvezno) {lead: rows}: privzeti Open-Meteo, D+1..D+3, enak zajem kot
             fetch_hourly_cache.py (eval_mtr3.py/eval_mtr4.py ga rabita).

POMEMBNO: za te spremenljivke Open-Meteo NIMA arhiva `*_previous_dayN` (preverjeno 24. 10. 2026:
pri višinskih nivojih HTTP 400, pri oblačnosti po slojih, snegu, vlagi tal in mejni plasti same
vrednosti null). Zato je tu `historical-forecast-api` brez `previous_day`: za vsako uro zlepljen
najsvežejši model, ki je že blizu analize. To NI napoved izpred 1-3 dni, zato je eval nad temi
podatki zgornja meja informacije, ne obljuba. `sunshine_duration` ima pravi `previous_dayN` in
ga ta skript zajame posebej (ključ "sun", prave napovedi izpred 1-3 dni).

Večkrat se ponovi ob SSL EOF (Open-Meteo občasno prekine rokovanje); zapis je ponovljiv.
"""
import argparse, json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import train_recica_mos as t   # noqa: E402

PROFILE_VARS = [
    "temperature_2m",            # iz iste serije, da je stabilnost znotraj iste izdaje
    "temperature_925hPa", "temperature_850hPa",
    "wind_speed_925hPa", "wind_speed_850hPa",
    "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "snow_depth", "soil_moisture_0_to_7cm", "boundary_layer_height",
]
BASE = "https://historical-forecast-api.open-meteo.com/v1/forecast?"


def fetch_profile(start, end):
    rows = {}
    for year in range(int(start[:4]), int(end[:4]) + 1):
        a, b = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        if a > b:
            continue
        q = urllib.parse.urlencode({
            "latitude": t.LAT, "longitude": t.LON, "start_date": a, "end_date": b,
            "hourly": ",".join(PROFILE_VARS), "timezone": t.TZ,
        })
        print(f"  profil {a} → {b} …", flush=True)
        h = (t._get_json(BASE + q, tries=6) or {}).get("hourly") or {}
        for i, ts in enumerate(h.get("time") or []):
            day, hour = ts[:10], int(ts[11:13])
            rec = rows.setdefault(day, {v: [] for v in PROFILE_VARS})
            for v in PROFILE_VARS:
                x = (h.get(v) or [None] * (i + 1))[i]
                if x is not None:
                    rec[v].append([hour, x])
    return rows


def fetch_sun(lead, start, end):
    """Pravi arhiv napovedi: sunshine_duration_previous_day<lead> (sekunde sonca v uri)."""
    rows = {}
    var = f"sunshine_duration_previous_day{lead}"
    for year in range(int(start[:4]), int(end[:4]) + 1):
        a, b = max(start, f"{year}-01-01"), min(end, f"{year}-12-31")
        if a > b:
            continue
        q = urllib.parse.urlencode({"latitude": t.LAT, "longitude": t.LON, "start_date": a,
                                    "end_date": b, "hourly": var, "timezone": t.TZ})
        print(f"  sonce D+{lead} {a} → {b} …", flush=True)
        h = (t._get_json(BASE + q, tries=6) or {}).get("hourly") or {}
        for i, ts in enumerate(h.get("time") or []):
            x = (h.get(var) or [None] * (i + 1))[i]
            if x is not None:
                rows.setdefault(ts[:10], []).append([int(ts[11:13]), x])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile_out")
    ap.add_argument("--from", dest="start", default="2024-05-26")
    ap.add_argument("--to", dest="end", default=None)
    ap.add_argument("--v1", default=None, help="zapiši še privzeti D+1..D+3 zajem v to datoteko")
    a = ap.parse_args()
    import datetime as dt
    end = a.end or (dt.date.today() - dt.timedelta(days=1)).isoformat()

    blob = json.load(open(a.profile_out)) if os.path.exists(a.profile_out) else {}
    if not blob.get("profile"):
        blob["profile"] = fetch_profile(a.start, end)
        json.dump(blob, open(a.profile_out, "w"))
    blob.setdefault("sun", {})
    for lead in t.LEADS:
        if str(lead) not in blob["sun"]:
            blob["sun"][str(lead)] = fetch_sun(lead, a.start, end)
            json.dump(blob, open(a.profile_out, "w"))
    prof = blob["profile"]
    cover = {v: sum(1 for d in prof.values() if d.get(v)) for v in PROFILE_VARS}
    print(f"profil: {len(prof)} dni; dni z vrednostmi po spremenljivki: {cover}")
    print("sonce:", {l: len(r) for l, r in blob["sun"].items()})

    if a.v1:
        v1 = json.load(open(a.v1)) if os.path.exists(a.v1) else {}
        for lead in t.LEADS:
            if str(lead) in v1:
                continue
            rows = t.fetch_archived_forecasts(lead, a.start, end)
            v1[str(lead)] = t._rows_to_cache(rows)
            json.dump(v1, open(a.v1, "w"))
            print(f"v1 D+{lead}: {len(rows)} dni", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
