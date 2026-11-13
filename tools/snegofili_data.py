#!/usr/bin/env python3
"""
tools/snegofili_data.py — podatki za /snegofili/ → data/snegofili.json

Za ~40 točk po alpskem loku (data/snegofili-tocke.json, ročni seznam) en sam batch klic Open-Meteo
(temperatura z `elevation=` na višino točke, padavine, ničta izoterma). Novi sneg je ISTA ocena kot na
/vreme-v-gorah/: padavine × delež snega (winter_engine.snow_fraction iz ničte izoterme) × razmerje
(winter_engine.SNOW_RATIO_CM_PER_MM). Ne nova formula.

Kar je in ni:
- MODELSKA OCENA padavin iz celice modela; ne meritev in ne višina snežne odeje. Celica ne razloči pobočij.
- Izmerjena višina odeje je ločena in samo za postaje ARSO v data/arso-snow-live.csv (arso_id v točkah).
  Vira se ne zlivata v eno številko.
- Ura, ki teče, se ne šteje naprej (vrednost z žigom T velja za T-1h..T): okna nazaj so (zdaj-N, zdaj],
  okna naprej (zdaj, zdaj+N].
- Ob izpadu Open-Meteo ostane stari posnetek (raje star podatek kot prazna stran); izhod 0.
- Notranjih meritev ta cevovod ne bere.

Usage: python3 tools/snegofili_data.py
"""
import csv
import datetime
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import winter_engine as we  # noqa: E402

ROOT = seo.ROOT
POINTS_PATH = os.path.join(ROOT, "data", "snegofili-tocke.json")
OUT_PATH = os.path.join(ROOT, "data", "snegofili.json")
ARSO_CSV = os.path.join(ROOT, "data", "arso-snow-live.csv")
RETRY_DELAYS_S = (5, 15, 45)
ARSO_MAX_AGE_H = 24
HOURLY = "temperature_2m,precipitation,freezing_level_height"
UA = "Mozilla/5.0 (compatible; Meteorec-Snegofili/1.0)"


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def load_points():
    with open(POINTS_PATH, encoding="utf-8") as f:
        return json.load(f)["tocke"]


def fetch_batch(points):
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(p["lat"]) for p in points),
        "longitude": ",".join(str(p["lon"]) for p in points),
        "elevation": ",".join(str(p["elevation_m"]) for p in points),
        "hourly": HOURLY, "timezone": "Europe/Ljubljana",
        "past_days": 3, "forecast_days": 4,
    })
    req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + params,
                                 headers={"User-Agent": UA, "Accept": "application/json"})
    last = None
    for delay in (0,) + RETRY_DELAYS_S:
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data if isinstance(data, list) else [data]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
    raise last


def window_snow(hourly, elevation_m, idxs):
    fl = hourly.get("freezing_level_height") or []
    pr = hourly.get("precipitation") or []
    snow = precip = 0.0
    for i in idxs:
        if not 0 <= i < len(pr):
            continue
        p = pr[i] or 0
        precip += p
        snow += p * we.snow_fraction(elevation_m, fl[i] if i < len(fl) else None) * we.SNOW_RATIO_CM_PER_MM
    return round(snow, 1), round(precip, 1)


def compute_point(hourly, idx_now, elevation_m):
    """Okna nazaj (idx-N, idx], naprej (idx, idx+N]. Vrne None, če serija nima ur nazaj/naprej."""
    times = hourly.get("time") or []
    if idx_now is None or idx_now < 71 or idx_now + 72 >= len(times):
        return None
    fl = hourly.get("freezing_level_height") or []
    t = (hourly.get("temperature_2m") or [None] * len(times))[idx_now]
    f = fl[idx_now] if idx_now < len(fl) else None
    out = {
        "temp_c": None if t is None else round(t, 1),
        "snow_line_m": None if f is None else round(f - we.SNOW_LEVEL_OFFSET_M),
        "snow_now_possible": we.snow_fraction(elevation_m, f) > 0.5,
    }
    for name, lo, hi in (("past24", idx_now - 23, idx_now), ("past72", idx_now - 71, idx_now),
                         ("next24", idx_now + 1, idx_now + 24), ("next72", idx_now + 1, idx_now + 72)):
        cm, mm = window_snow(hourly, elevation_m, range(lo, hi + 1))
        out[name + "_cm"] = cm
        out[name + "_mm"] = mm
    return out


def load_arso(now_utc):
    """Zadnja vrstica na postajo, samo če ni starejša od ARSO_MAX_AGE_H in ima višino odeje."""
    latest = {}
    if not os.path.exists(ARSO_CSV):
        return latest
    with open(ARSO_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            latest[r["id"]] = r
    res = {}
    for sid, r in latest.items():
        try:
            valid = datetime.datetime.strptime(r["valid_utc"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)
            depth = float(r["snow_cm"])
        except (ValueError, KeyError):
            continue
        age_h = (now_utc - valid).total_seconds() / 3600
        if 0 <= age_h <= ARSO_MAX_AGE_H:
            res[sid] = {"depth_cm": round(depth), "valid_utc": r["valid_utc"], "age_h": round(age_h, 1)}
    return res


def build(points, responses, now_local, arso):
    out = []
    for p, resp in zip(points, responses):
        hourly = resp.get("hourly") or {}
        idx = we.nearest_hour_index(hourly.get("time") or [], now_local)
        comp = compute_point(hourly, idx, p["elevation_m"])
        if comp is None:
            continue
        row = {k: p[k] for k in ("id", "ime", "drzava", "regija", "lat", "lon", "elevation_m", "elev_opis")}
        row["km_od_recice"] = round(haversine_km(seo.LAT, seo.LON, p["lat"], p["lon"]))
        row.update(comp)
        if p.get("arso_id") and p["arso_id"] in arso:
            row["izmerjeno"] = arso[p["arso_id"]]
        out.append(row)
    return out


def main():
    points = load_points()
    now_local = datetime.datetime.now(we.LOCAL_TZ)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
        responses = fetch_batch(points)
        if len(responses) != len(points):
            raise ValueError(f"Open-Meteo vrnil {len(responses)} odgovorov za {len(points)} točk")
    except Exception as e:  # noqa: BLE001 — raje star posnetek kot prazna stran
        print(f"✗ Open-Meteo: {e} — ostane stari data/snegofili.json", file=sys.stderr)
        return 0
    rows = build(points, responses, now_local, load_arso(now_utc))
    if len(rows) < len(points) // 2:
        print(f"✗ le {len(rows)}/{len(points)} točk z veljavno serijo — stari posnetek ostane", file=sys.stderr)
        return 0
    payload = {
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_at_local": now_local.strftime("%-d. %-m. %Y ob %-H.%M"),
        "tocke": rows,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"data/snegofili.json: {len(rows)} točk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
