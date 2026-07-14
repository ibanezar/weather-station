#!/usr/bin/env python3
"""
tools/verify_forecasts.py — daily forecast verification pipeline

Nobody in Slovenia systematically tracks whether ARSO's or Open-Meteo's
day-ahead forecast for a specific valley actually verifies. This station
has the ground truth (history.json) to do it.

Two-step, once per day (after update-history.yml has written yesterday's
actual measurement):

  1. RESOLVE — any pending prediction whose target_date now has an actual
     measurement in history.json gets its error computed (|predicted -
     actual| for tmax/tmin, and precip for Open-Meteo) and is appended to
     forecast_verification.json (permanent, append-only scoreboard log).
  2. PREDICT — fetch tomorrow's ARSO forecast (via the Cloudflare Worker,
     which proxies vreme.arso.gov.si — ARSO blocks cloud IPs) and Open-Meteo
     forecast, and log both as a new pending prediction to be resolved
     tomorrow.

There is no way to backfill history: ARSO/Open-Meteo don't publish
retroactive forecast archives, so the scoreboard only starts accumulating
from the day this pipeline first runs and grows one day at a time.

State:
  tools/.forecast_pending.json    — predictions awaiting resolution
  forecast_verification.json      — resolved verification records (public)

Usage:
  python3 tools/verify_forecasts.py
"""
import datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

ROOT = seo.ROOT
LAT, LON = seo.LAT, seo.LON
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ForecastVerify/1.0; +https://meteorec.si)"}

PENDING_PATH = os.path.join(ROOT, "tools", ".forecast_pending.json")
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_arso_tomorrow(target_date):
    req = urllib.request.Request(f"{WORKER}/arso-forecast", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    for day in data.get("days", []):
        if day.get("valid_date") == target_date:
            return {"tmax": day.get("tmax"), "tmin": day.get("tmin")}
    return None


def fetch_open_meteo_tomorrow(target_date):
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 3,
    })
    req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{params}", headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    d = data.get("daily", {})
    times = d.get("time", [])
    if target_date not in times:
        return None
    i = times.index(target_date)
    tmax = (d.get("temperature_2m_max") or [None] * len(times))[i]
    tmin = (d.get("temperature_2m_min") or [None] * len(times))[i]
    precip = (d.get("precipitation_sum") or [None] * len(times))[i]
    return {"tmax": tmax, "tmin": tmin, "precip": precip}


def err(pred, actual):
    if pred is None or actual is None:
        return None
    return round(abs(pred - actual), 1)


def resolve_pending(pending, hist, verification):
    still_pending = []
    resolved = 0
    for entry in pending:
        target = entry["target_date"]
        actual = hist.get(target)
        if actual is None:
            # Not measured yet (or station gap) — keep waiting, but drop if
            # it's more than 5 days stale to avoid an ever-growing queue.
            made = entry.get("made_at", target)
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(made)).days
            except ValueError:
                age = 0
            if age <= 5:
                still_pending.append(entry)
            continue

        actual_tmax = actual.get("tempHigh")
        actual_tmin = actual.get("tempLow")
        actual_precip = actual.get("precipTotal")

        record = {
            "date": target,
            "made_at": entry.get("made_at"),
            "actual": {"tmax": actual_tmax, "tmin": actual_tmin, "precip": actual_precip},
        }
        arso = entry.get("arso")
        if arso:
            record["arso"] = {
                "tmax": arso.get("tmax"), "tmin": arso.get("tmin"),
                "err_tmax": err(arso.get("tmax"), actual_tmax),
                "err_tmin": err(arso.get("tmin"), actual_tmin),
            }
        om = entry.get("open_meteo")
        if om:
            record["open_meteo"] = {
                "tmax": om.get("tmax"), "tmin": om.get("tmin"), "precip": om.get("precip"),
                "err_tmax": err(om.get("tmax"), actual_tmax),
                "err_tmin": err(om.get("tmin"), actual_tmin),
                "err_precip": err(om.get("precip"), actual_precip),
            }
        verification[target] = record
        resolved += 1
    return still_pending, resolved


def main():
    today = datetime.date.today()
    tomorrow = (today + datetime.timedelta(days=1)).isoformat()

    hist = seo.load_history()
    pending = load_json(PENDING_PATH, [])
    verification = load_json(VERIFICATION_PATH, {})

    still_pending, resolved = resolve_pending(pending, hist, verification)
    print(f"[{today}] Razrešenih napovedi: {resolved}, v čakalni vrsti: {len(still_pending)}")

    if any(e["target_date"] == tomorrow for e in still_pending):
        print(f"  Napoved za {tomorrow} je že zabeležena, preskačem.")
    else:
        arso = om = None
        try:
            arso = fetch_arso_tomorrow(tomorrow)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ⚠ ARSO napoved nedosegljiva: {e}", file=sys.stderr)
        try:
            om = fetch_open_meteo_tomorrow(tomorrow)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            print(f"  ⚠ Open-Meteo napoved nedosegljiva: {e}", file=sys.stderr)

        if arso or om:
            still_pending.append({
                "target_date": tomorrow,
                "made_at": today.isoformat(),
                "arso": arso,
                "open_meteo": om,
            })
            print(f"  Zabeležena napoved za {tomorrow}: ARSO={'da' if arso else 'ne'}, Open-Meteo={'da' if om else 'ne'}")
        else:
            print("  ✗ Nobenega vira napovedi ni bilo mogoče pridobiti.", file=sys.stderr)

    save_json(PENDING_PATH, still_pending)
    save_json(VERIFICATION_PATH, verification)
    print(f"  → forecast_verification.json: {len(verification)} razrešenih dni")


if __name__ == "__main__":
    main()
