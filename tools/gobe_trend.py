#!/usr/bin/env python3
"""
tools/gobe_trend.py — sezonski trend gobarskega indeksa za pretekla leta.

Za domačo lokacijo (Rečica ob Savinji) izračuna dnevni "overall" gobarski
indeks (isti model kot gobe_model.py) za obdobje 1.4.–30.11. vsakega od
zadnjih PAST_YEARS let, iz Open-Meteo Historical Weather API (ERA5-Land).

Ta API uporablja druga imena spremenljivk za globino tal kot forecast API
(npr. soil_temperature_0_to_7cm namesto soil_temperature_6cm) — gre za
drugačen model (ERA5-Land reanaliza namesto ICON/GFS), zato so vrednosti
približek, ne bit-za-bit isti izračun kot dnevna napoved. Dovolj natančno
za sezonski trend, ne za posamezen dan.

Izhod: gobarska-napoved/trend.json — mesečno povprečje indeksa po letih +
najboljši dan vsakega leta, za graf "letos vs. pretekla leta" na strani.

Uporaba:
  python3 tools/gobe_trend.py                    # izpiše in zapiše trend.json
  python3 tools/gobe_trend.py --years 5 --no-write
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gobe_model import load_rules, load_locations, eval_species, in_season  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREND_JSON_DEFAULT = os.path.join(ROOT, "gobarska-napoved", "trend.json")

PAST_YEARS = 5
SEASON_START = (4, 1)   # 1. april
SEASON_END = (11, 30)   # 30. november

ARCHIVE_HOURLY = [
    "soil_temperature_0_to_7cm",
    "soil_temperature_7_to_28cm",
    "soil_moisture_0_to_7cm",
    "relative_humidity_2m",
    "dew_point_2m",
    "temperature_2m",
]
ARCHIVE_DAILY = ["precipitation_sum", "temperature_2m_min"]


def fetch_archive_year(lat, lon, year):
    """One year of ERA5-Land daily+hourly series for the home spot, capped at
    yesterday for the current year (archive data lags a few days)."""
    today = dt.date.today()
    start = dt.date(year, *SEASON_START)
    end = dt.date(year, *SEASON_END)
    if year == today.year:
        end = min(end, today - dt.timedelta(days=1))
    if start > end:
        return None
    params = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": ",".join(ARCHIVE_DAILY),
        "hourly": ",".join(ARCHIVE_HOURLY),
        "timezone": "Europe/Ljubljana",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def daily_mean(hourly, var, times):
    vals = hourly.get(var) or []
    buckets = {}
    for i, t in enumerate(times):
        v = vals[i] if i < len(vals) else None
        if v is None:
            continue
        d = t[:10]
        s, n = buckets.get(d, (0.0, 0))
        buckets[d] = (s + v, n + 1)
    return {d: s / n for d, (s, n) in buckets.items() if n}


def build_series_from_archive(data):
    """Adapt ERA5-Land archive payload into the series shape eval_species expects."""
    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    precip = [(p if p is not None else 0.0) for p in (daily.get("precipitation_sum") or [])]
    precip += [0.0] * (len(dates) - len(precip))
    tmin = daily.get("temperature_2m_min") or []

    hourly = data.get("hourly") or {}
    htimes = hourly.get("time") or []
    means = {var: daily_mean(hourly, var, htimes) for var in ARCHIVE_HOURLY}

    def soil_temp_at(d):
        t1 = means["soil_temperature_0_to_7cm"].get(d)
        t2 = means["soil_temperature_7_to_28cm"].get(d)
        vals = [v for v in (t1, t2) if v is not None]
        return sum(vals) / len(vals) if vals else None

    return {
        "dates": dates,
        "precip": precip,
        "tmin": [tmin[i] if i < len(tmin) else None for i in range(len(dates))],
        "soil_temp": [soil_temp_at(d) for d in dates],
        "soil_moisture": [means["soil_moisture_0_to_7cm"].get(d) for d in dates],
        "rh": [means["relative_humidity_2m"].get(d) for d in dates],
        "dewpoint": [means["dew_point_2m"].get(d) for d in dates],
        "tair": [means["temperature_2m"].get(d) for d in dates],
    }


def daily_overall(rules, spot, series):
    """Max species index per day, using the same eval_species scoring as the
    live forecast model."""
    indexed = [sp for sp in rules["species"] if sp.get("gets_index")]
    meta = {sp["id"]: sp["name_sl"] for sp in indexed}
    out = []
    for i, dstr in enumerate(series["dates"]):
        date = dt.date.fromisoformat(dstr)
        best_id, best_idx = None, 0
        for sp in indexed:
            if not in_season(date, sp["season"]):
                continue
            r = eval_species(sp, series, i, date, spot, rules)
            if r["index"] > best_idx:
                best_idx, best_id = r["index"], sp["id"]
        out.append({"date": dstr, "overall": best_idx, "top": meta.get(best_id)})
    return out


def monthly_avg(days):
    buckets = {}
    for d in days:
        m = d["date"][5:7]
        s, n = buckets.get(m, (0, 0))
        buckets[m] = (s + d["overall"], n + 1)
    return {m: round(s / n, 1) for m, (s, n) in buckets.items()}


def main():
    ap = argparse.ArgumentParser(description="Sezonski trend gobarskega indeksa (pretekla leta)")
    ap.add_argument("--years", type=int, default=PAST_YEARS)
    ap.add_argument("--out", default=TREND_JSON_DEFAULT)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    rules = load_rules()
    spots, _ = load_locations(rules)
    home = next((s for s in spots if s.get("home")), spots[0])

    today = dt.date.today()
    years = list(range(today.year - args.years + 1, today.year + 1))

    result = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "location": home["name"], "years": {}}
    for year in years:
        print(f"Pridobivam ERA5-Land arhiv {year} …", file=sys.stderr)
        try:
            data = fetch_archive_year(home["lat"], home["lon"], year)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ✗ {year}: {e}", file=sys.stderr)
            continue
        if not data:
            continue
        series = build_series_from_archive(data)
        days = daily_overall(rules, home, series)
        best = max(days, key=lambda d: d["overall"], default=None)
        result["years"][str(year)] = {
            "monthly_avg": monthly_avg(days),
            "best_day": best,
            "days_count": len(days),
        }
        if best:
            print(f"  {year}: najboljši dan {best['date']} — {best['overall']} % ({best['top']})",
                  file=sys.stderr)

    if not args.no_write:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
        print(f"→ {args.out}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
