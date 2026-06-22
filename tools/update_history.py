#!/usr/bin/env python3
"""
Osveži history.json z dnevnimi povzetki iz Open-Meteo Archive API.
API ne zahteva ključa; vrne ERA5 reanalizo za koordinate postaje.

    python3 tools/update_history.py 2026-06
"""
import json, os, sys, calendar, urllib.request, urllib.parse
from datetime import date as _date

LAT  = 46.325779
LON  = 14.921137
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def fetch(start, end):
    params = urllib.parse.urlencode({
        "latitude":        LAT,
        "longitude":       LON,
        "start_date":      start,
        "end_date":        end,
        "daily":           "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,windspeed_10m_max",
        "hourly":          "relativehumidity_2m,windspeed_10m",
        "timezone":        "Europe/Berlin",
        "wind_speed_unit": "kmh",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        sys.exit(f"Open-Meteo {e.code}\nOdgovor: {body}")
    except Exception as e:
        sys.exit(f"Napaka pri klicu Open-Meteo: {e}")

def hourly_means(data, key):
    """Returns dict {date: mean_value} from hourly data."""
    times  = data.get("hourly", {}).get("time", [])
    values = data.get("hourly", {}).get(key, [])
    by_day = {}
    for t, v in zip(times, values):
        if v is not None:
            by_day.setdefault(t[:10], []).append(float(v))
    return {d: round(sum(vs) / len(vs), 1) for d, vs in by_day.items()}

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: update_history.py YYYY-MM")
    ym = sys.argv[1]
    y, m = int(ym[:4]), int(ym[5:7])
    start    = f"{ym}-01"
    month_end = f"{ym}-{calendar.monthrange(y, m)[1]:02d}"
    today    = _date.today().isoformat()
    end      = min(month_end, today)

    data  = fetch(start, end)
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        sys.exit(f"Open-Meteo ni vrnil podatkov za {ym}")

    hum_avg  = hourly_means(data, "relativehumidity_2m")
    wind_avg = hourly_means(data, "windspeed_10m")

    hp   = os.path.join(ROOT, "history.json")
    hist = json.load(open(hp, encoding="utf-8"))

    def get(key, i):
        lst = daily.get(key, [])
        return lst[i] if i < len(lst) else None

    added = 0
    for i, date in enumerate(dates):
        if not date.startswith(ym):
            continue
        t_avg = get("temperature_2m_mean", i)
        if t_avg is None:
            continue
        hist[date] = {
            "tempHigh":      get("temperature_2m_max", i),
            "tempLow":       get("temperature_2m_min", i),
            "tempAvg":       t_avg,
            "precipTotal":   get("precipitation_sum",  i) or 0,
            "windspeedHigh": get("windspeed_10m_max",  i),
            "windspeedAvg":  wind_avg.get(date),
            "humidityAvg":   hum_avg.get(date),
        }
        added += 1

    if not added:
        sys.exit(f"Za {ym} ni uporabnih dni v odgovoru Open-Meteo.")

    out = {k: hist[k] for k in sorted(hist)}
    json.dump(out, open(hp, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"✓ history.json: posodobljenih {added} dni za {ym} (skupaj {len(out)} dni)")

if __name__ == "__main__":
    main()
