#!/usr/bin/env python3
"""
tools/gobe_model.py — species-level mushroom fruiting-conditions model.

Computes a 0-100 "gobarski indeks" (favourability-of-conditions index, NOT a
promise of finds) per species, per day (today + 6), per location, driven
entirely by species_rules.yaml — no thresholds live in this file.

Which thermometer drives a species depends on where it fruits: soil
temperature for mycorrhizal species and litter saprotrophs, air temperature for
wood decayers, which sit on a branch above ground and never feel the soil. For
the same reason the geological terrain multiplier does not apply to them.

Rain is read through the species' own fruiting lag (`fruiting_lag_days`,
derived per ecological group in species_rules.yaml): the trigger window ends
lag_min days back, not today. Litter saprotrophs answer a shower within days,
wood decayers a little later, mycorrhizal species only after a week and a
half — so the same downpour lifts their indices on different days.

Inputs
  * Open-Meteo forecast API: daily precipitation + T min/max, hourly soil
    temperature at 6 and 18 cm, soil moisture 3-9 cm, relative humidity,
    dew point and air temperature (for dew-point spread).
  * history.json (IREICA1 station daily summaries): overrides Open-Meteo
    precipitation for past days at the home location, where the station is
    the more accurate source.

Outputs
  * free JSON  — today's overall index (max across species) for the home
    location; safe to publish on GitHub Pages.
  * premium JSON — full 7-day, per-species, per-location forecast with
    human-readable explanations; meant for the gated Worker endpoint,
    NOT for the public repo.

Usage
  python3 tools/gobe_model.py                       # print summary, write free JSON
  python3 tools/gobe_model.py --out-premium out.json
  python3 tools/gobe_model.py --no-write            # print only
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "species_rules.yaml")
HISTORY_PATH = os.path.join(ROOT, "history.json")
FREE_JSON_DEFAULT = os.path.join(ROOT, "gobarska-napoved", "index.json")

MODEL_VERSION = "1.3"
FORECAST_DAYS = 7

# Padavinski okni se pri vsaki vrsti zamakneta za njen rastni zamik
# (fruiting_lag_days), zato model potrebuje toliko preteklih dni, da najdaljši
# zamik še vidi celo osnovno okno — glej past_days_needed().
BASE_WINDOW_DAYS = 14   # dolžina okna "zaloga vode v tleh"
TRIGGER_NORM_DAYS = 7   # rain_7d_min je izražen kot 7-dnevna kumulativa
MIN_PAST_DAYS = 14

# Locations come from species_rules.yaml (`locations:`); see load_locations().

HOURLY_VARS = [
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_moisture_3_to_9cm",
    "relative_humidity_2m",
    "dew_point_2m",
    "temperature_2m",
]
DAILY_VARS = ["precipitation_sum", "temperature_2m_max", "temperature_2m_min"]


# ── data fetching ────────────────────────────────────────────────────────────

def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_locations(rules):
    """Forecast spots from the config. Protected areas are returned separately —
    they are never ranked as picking spots."""
    spots, protected = [], []
    for loc in rules.get("locations", []):
        (protected if loc.get("protected") else spots).append(loc)
    return spots, protected


def past_days_needed(rules):
    """Koliko preteklih dni mora zajeti poizvedba, da ima tudi vrsta z
    najdaljšim zamikom polno osnovno okno (zamik + 14 dni pred njim)."""
    lags = [int(sp["fruiting_lag_days"]["max"]) for sp in rules.get("species", [])
            if sp.get("fruiting_lag_days")]
    return max(MIN_PAST_DAYS, (max(lags) if lags else 0) + BASE_WINDOW_DAYS)


def fetch_forecast(spots, past_days=MIN_PAST_DAYS):
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(s["lat"]) for s in spots),
        "longitude": ",".join(str(s["lon"]) for s in spots),
        "daily": ",".join(DAILY_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "past_days": past_days,
        "forecast_days": FORECAST_DAYS,
        "timezone": "Europe/Ljubljana",
    }, safe=",")
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data if isinstance(data, list) else [data]


def load_station_precip(path=HISTORY_PATH):
    """IREICA1 daily precipitation totals keyed by ISO date, from history.json."""
    try:
        with open(path, encoding="utf-8") as f:
            hist = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    out = {}
    for day, rec in hist.items():
        p = rec.get("precipTotal")
        if isinstance(p, (int, float)):
            out[day] = float(p)
    return out


# ── per-location daily series ────────────────────────────────────────────────

def daily_mean(hourly, var, times):
    """Bucket an hourly variable into daily means keyed by ISO date."""
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


def build_series(loc, station_precip=None):
    """Normalise one Open-Meteo location block into aligned daily series."""
    daily = loc.get("daily") or {}
    dates = daily.get("time") or []
    precip = [(p if p is not None else 0.0) for p in (daily.get("precipitation_sum") or [])]
    precip += [0.0] * (len(dates) - len(precip))

    today = dt.date.today().isoformat()
    if station_precip:
        # Station rain gauge beats the model grid for days already measured.
        for i, d in enumerate(dates):
            if d < today and d in station_precip:
                precip[i] = station_precip[d]

    hourly = loc.get("hourly") or {}
    htimes = hourly.get("time") or []
    means = {var: daily_mean(hourly, var, htimes) for var in HOURLY_VARS}

    def soil_temp_at(d):
        # "Soil temperature 6-18 cm": mean of both depths, or whichever exists.
        t6 = means["soil_temperature_6cm"].get(d)
        t18 = means["soil_temperature_18cm"].get(d)
        vals = [v for v in (t6, t18) if v is not None]
        return sum(vals) / len(vals) if vals else None

    tmin = daily.get("temperature_2m_min") or []
    return {
        "dates": dates,
        "precip": precip,
        "tmin": [tmin[i] if i < len(tmin) else None for i in range(len(dates))],
        "soil_temp": [soil_temp_at(d) for d in dates],
        "soil_moisture": [means["soil_moisture_3_to_9cm"].get(d) for d in dates],
        "rh": [means["relative_humidity_2m"].get(d) for d in dates],
        "dewpoint": [means["dew_point_2m"].get(d) for d in dates],
        "tair": [means["temperature_2m"].get(d) for d in dates],
    }


def rain_lag_window(series, i, lag_min, lag_max):
    """Cumulative precipitation that fell lag_min..lag_max days before day i.
    Returns 0 when the window lies entirely before the start of the series —
    the caller must fetch enough past days (see past_days_needed()), otherwise
    a truncated window silently under-reports rain."""
    hi = i - lag_min
    if hi < 0:
        return 0.0
    lo = max(0, i - lag_max)
    return sum(series["precip"][lo:hi + 1])


def temp_drop_triggered(series, i, cfg):
    """True if a night-cooling event (per scoring.temp_drop config) occurred
    on day i or within persist_days before it."""
    window = int(cfg["window_days"])
    min_drop = float(cfg["min_drop_c"])
    persist = int(cfg["persist_days"])
    tmin = series["tmin"]

    def drop_at(k):
        prev = [t for t in tmin[max(0, k - window):k] if t is not None]
        if not prev or tmin[k] is None:
            return False
        return (sum(prev) / len(prev)) - tmin[k] >= min_drop

    return any(drop_at(k) for k in range(max(0, i - persist), i + 1))


# ── scoring primitives (all thresholds come from config) ─────────────────────

def trapezoid(x, lo, opt_lo, opt_hi, hi):
    """0 below lo and above hi, 1 between opt_lo and opt_hi, linear ramps between."""
    if x is None or x <= lo or x >= hi:
        return 0.0
    if x < opt_lo:
        return (x - lo) / (opt_lo - lo)
    if x > opt_hi:
        return (hi - x) / (hi - opt_hi)
    return 1.0


def ramp(x, lo, hi):
    """0 at/below lo, 1 at/above hi, linear between."""
    if x is None:
        return None
    if x <= lo:
        return 0.0
    if x >= hi:
        return 1.0
    return (x - lo) / (hi - lo)


def rain_score(cum_mm, min_mm, rain_cfg):
    """Ratio-to-threshold score, capped at 1.0, decaying when oversaturated.
    Returns (score, state) where state ∈ {pod_pragom, nad_pragom, prenamoceno}."""
    if min_mm <= 0:
        return 1.0, "nad_pragom"
    ratio = cum_mm / min_mm
    over_start = float(rain_cfg["oversat_ratio"])
    over_end = float(rain_cfg["oversat_max_ratio"])
    over_floor = float(rain_cfg["oversat_factor"])
    if ratio < 1.0:
        return ratio, "pod_pragom"
    if ratio <= over_start:
        return 1.0, "nad_pragom"
    if ratio >= over_end:
        return over_floor, "prenamoceno"
    frac = (ratio - over_start) / (over_end - over_start)
    return 1.0 - frac * (1.0 - over_floor), "prenamoceno"


def in_season(date, season):
    """True if date falls inside the species' 'MM.DD'..'MM.DD' window
    (window may wrap over New Year)."""
    def md(s):
        m, d = s.split(".")
        return int(m), int(d)
    start, end = md(season["start"]), md(season["end"])
    cur = (date.month, date.day)
    if start <= end:
        return start <= cur <= end
    return cur >= start or cur <= end


# ── per-species evaluation ───────────────────────────────────────────────────

def eval_species(sp, series, i, date, spot, rules):
    """Score one species for one day at one location.
    Returns {index, explanation, components}."""
    weights = rules["weights"]
    scoring = rules["scoring"]

    if not in_season(date, sp["season"]):
        return {
            "index": 0,
            "explanation": f"Izven sezone ({sp['season']['start']}–{sp['season']['end']}).",
            "components": {},
        }

    parts = []       # explanation fragments, most important first
    components = {}

    # Temperature — trapezoid over the species' optimal window. Which
    # thermometer counts depends on where the fungus actually fruits: a wood
    # decayer sits on a branch above ground, so soil temperature at 6-18 cm
    # says nothing about it — for those the air temperature decides.
    if sp.get("ecology") == "lesna":
        shoulder = float(scoring["temperature"]["air_shoulder_c"])
        at = sp["air_temp"]
        lo, hi = float(at["min"]), float(at["max"])
        curve = (lo - shoulder, lo, hi, hi + shoulder)
        temp, temp_label = series["tair"][i], "zračna temp."
    else:
        stc = sp["soil_temp"]
        curve = (stc["min"], stc["opt_low"], stc["opt_high"], stc["max"])
        temp, temp_label = series["soil_temp"][i], "talna temp."
    f_t = trapezoid(temp, *curve)
    components["temperature"] = f_t
    if temp is None:
        parts.append(f"{temp_label} ni na voljo")
    else:
        if f_t >= 1.0:
            state = "optimalna"
        elif f_t <= 0.0:
            state = "izven razpona vrste"
        elif temp < curve[1]:
            state = "pod optimalnim oknom"
        else:
            state = "nad optimalnim oknom"
        parts.append(f"{temp_label} {temp:.1f} °C {state}")

    # Rain — both windows are shifted back by the species' fruiting lag, so what
    # counts is the rain that could have started the fruit body visible today,
    # not the rain that just fell. A litter saprotroph fruits days after a
    # shower; a mycorrhizal bolete needs a week and a half, and until then the
    # same rain must not lift its index.
    rain_cfg = scoring["rain"]
    lag = sp["fruiting_lag_days"]
    lag_min, lag_max = int(lag["min"]), int(lag["max"])

    # Trigger: rain inside the species' lag window. Its length differs per
    # ecological group, so the 7-day-equivalent threshold is scaled to the
    # window — groups stay comparable instead of the widest window winning.
    trig_days = lag_max - lag_min + 1
    trig_mm = rain_lag_window(series, i, lag_min, lag_max)
    trig_min = float(sp["rain_7d_min"]) * trig_days / TRIGGER_NORM_DAYS
    f_trig, trig_state = rain_score(trig_mm, trig_min, rain_cfg)

    # Base: soil water reserve the mycelium had going into that trigger — the
    # 14 days up to the most recent edge of the lag window, so it contains the
    # trigger window the way the old 14-day sum contained the 7-day one.
    base_mm = rain_lag_window(series, i, lag_min, lag_min + BASE_WINDOW_DAYS - 1)
    f_base, base_state = rain_score(base_mm, float(sp["rain_14d_min"]), rain_cfg)

    components["rain_trigger"] = f_trig
    components["rain_base"] = f_base
    trig_txt = {"pod_pragom": "pod pragom", "nad_pragom": "nad pragom",
                "prenamoceno": "prenamočeno"}[trig_state]
    parts.append(f"sprožilni dež pred {lag_min}–{lag_max} dnevi "
                 f"{trig_mm:.1f}/{trig_min:.0f} mm ({trig_txt})")
    if base_state == "prenamoceno" and trig_state != "prenamoceno":
        parts.append("zaloga vode v tleh kaže prenamočenost")

    # Soil moisture and air humidity stay on the current day on purpose: the
    # lag windows above ask whether the fruit body was ever started, these ask
    # whether it can swell and not dry out today.
    smc = scoring["soil_moisture"]
    f_sm = ramp(series["soil_moisture"][i], float(smc["dry"]), float(smc["full"]))
    components["soil_moisture"] = 0.0 if f_sm is None else f_sm
    if f_sm is not None and f_sm <= 0.0:
        parts.append("tla suha")

    # Air humidity ramp, lifted to 1.0 when dew-point spread says saturated air
    hc = scoring["humidity"]
    f_h = ramp(series["rh"][i], float(hc["rh_low"]), float(hc["rh_full"]))
    tair, td = series["tair"][i], series["dewpoint"][i]
    if (tair is not None and td is not None
            and tair - td <= float(hc["dewpoint_spread_full"])):
        f_h = 1.0
    components["humidity"] = 0.0 if f_h is None else f_h

    # Night-cooling trigger
    if sp.get("requires_temp_drop"):
        triggered = temp_drop_triggered(series, i, scoring["temp_drop"])
        components["temp_drop"] = 1.0 if triggered else 0.0
        parts.append("nočna ohladitev zaznana" if triggered else "čaka na nočno ohladitev")
    else:
        components["temp_drop"] = 1.0  # species doesn't need the trigger

    # Display copy of components — drops temp_drop for species that don't use
    # it (there it's a fixed 1.0 bypass for the score sum below, not a real
    # per-day signal, so showing it in a "why" breakdown would be misleading).
    display_components = dict(components)
    if not sp.get("requires_temp_drop"):
        display_components.pop("temp_drop", None)

    score = 100.0 * sum(float(weights[k]) * components[k] for k in weights)

    # Soft elevation preference dampener
    ep = sp.get("elevation_pref_m")
    if ep and not (float(ep["min"]) <= spot["elev_m"] <= float(ep["max"])):
        score *= float(scoring["elevation"]["out_of_range_factor"])
        parts.append("lokacija izven višinske preference vrste")

    # Local-presence prior: a weather-favourable but locally rare/absent species
    # must not top the list (scientific honesty — see species 'frequency' text).
    ff = float(sp.get("frequency_factor", 1.0))
    if ff < 1.0:
        score *= ff
        if ff <= 0.4:
            parts.append("lokalno redka/odsotna vrsta")

    # Geological terrain affinity — match/mismatch multiplier. Ne velja za
    # lesne vrste: te rastejo na lesu, ne v tleh, zato jim podlaga gozda ne
    # more dvigniti ali znižati možnosti (bezgovi uhljevki je prej dvigovala).
    gcfg = scoring.get("geology") or {}
    affinity = sp.get("geology_affinity", "nevtralna")
    terrain = spot.get("terrain")
    if sp.get("ecology") == "lesna":
        pass
    elif affinity == "nevtralna" or not terrain:
        pass
    elif affinity == terrain:
        score *= float(gcfg.get("match_factor", 1.0))
        parts.append(f"geološko ugodno ({terrain})")
    else:
        score *= float(gcfg.get("mismatch_factor", 1.0))
        parts.append(f"geološko manj ugodno (vrsta preferira {affinity})")

    explanation = ", ".join(parts[:4])
    explanation = explanation[0].upper() + explanation[1:] + "."
    return {
        "index": max(0, min(100, round(score))),
        "explanation": explanation,
        "components": {k: round(100 * v) for k, v in display_components.items()},
    }


def level(p):
    if p >= 75: return "ODLIČNA"
    if p >= 55: return "DOBRA"
    if p >= 35: return "ZMERNA"
    if p >= 18: return "SLABA"
    return "BREZ"


# ── forecast assembly ────────────────────────────────────────────────────────

def compute_forecast(rules, spots, locs, station_precip, protected=None):
    today = dt.date.today()
    # Only edible / conditionally-edible species get a foraging index; the rest
    # (poisonous, protected, inedible) live in the config solely as reference and
    # as each edible species' dangerous-double note.
    indexed = [sp for sp in rules["species"] if sp.get("gets_index")]
    # Same dry/full normalisation the per-species scorer uses (ramp()), so the
    # exposed "soil moisture fullness %" reads consistently with why species
    # scored the way they did — not a second, differently-calibrated number.
    smc = rules["scoring"]["soil_moisture"]
    # Static per-species metadata is emitted once, keyed by id; the per-day
    # entries below carry only {id, index, explanation} to keep the payload small.
    species_meta = {sp["id"]: {
        "name_sl": sp["name_sl"],
        "name_lat": sp["name_lat"],
        "edibility": sp.get("edibility"),
        "ecology": sp.get("ecology"),
        # Zamik pove, kateri dež je vrsto sploh lahko sprožil — na kartici stoji
        # ob razlagi, da je vidno, zakaj ista ploha pri dveh vrstah ne šteje enako.
        "lag_days": [int(sp["fruiting_lag_days"]["min"]),
                     int(sp["fruiting_lag_days"]["max"])],
        "doubles": sp.get("doubles") or None,
    } for sp in indexed}
    out_locations = []
    for spot, loc in zip(spots, locs):
        series = build_series(loc, station_precip if spot.get("home") else None)
        dates = series["dates"]
        iso = today.isoformat()
        ti = dates.index(iso) if iso in dates else past_days_needed(rules)

        days = []
        for i in range(ti, min(ti + FORECAST_DAYS, len(dates))):
            date = dt.date.fromisoformat(dates[i])
            species_out = []
            for sp in indexed:
                r = eval_species(sp, series, i, date, spot, rules)
                species_out.append({
                    "id": sp["id"],
                    "index": r["index"],
                    "explanation": r["explanation"],
                    "components": r["components"],
                })
            species_out.sort(key=lambda s: s["index"], reverse=True)
            overall = max((s["index"] for s in species_out), default=0)
            sm_full = ramp(series["soil_moisture"][i], float(smc["dry"]), float(smc["full"]))
            days.append({
                "date": dates[i],
                "overall": overall,
                "level": level(overall),
                "soil_moisture_pct": None if sm_full is None else round(100 * sm_full),
                "species": species_out,
            })
        out_locations.append({
            "name": spot["name"],
            "lat": spot["lat"],
            "lon": spot["lon"],
            "elev_m": spot["elev_m"],
            "terrain": spot.get("terrain"),
            "home": bool(spot.get("home")),
            "days": days,
        })
    return {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "model_version": MODEL_VERSION,
        "species_indexed": len(indexed),
        "species_meta": species_meta,
        "terrains": {t["id"]: t["name_sl"] for t in rules.get("terrains", [])},
        "ecologies": {e["id"]: e["name_sl"] for e in rules.get("ecologies", [])},
        "protected_areas": [p["name"] for p in (protected or [])],
        "locations": out_locations,
    }


def free_payload(premium):
    """Public teaser: today's overall index at the home location only."""
    meta = premium["species_meta"]
    home = next((l for l in premium["locations"] if l["home"]), premium["locations"][0])
    today = home["days"][0]
    best = today["species"][0] if today["species"] else {"index": 0, "id": None}
    return {
        "generated": premium["generated"],
        "model_version": premium["model_version"],
        "date": today["date"],
        "location": home["name"],
        "index": today["overall"],
        "level": today["level"],
        "top_species_sl": meta[best["id"]]["name_sl"] if best["index"] > 0 else None,
        "species_count": len(today["species"]),
        "locations_count": len(premium["locations"]),
        "forecast_days": FORECAST_DAYS,
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def print_summary(premium, top=8):
    meta = premium["species_meta"]
    nm = lambda sid: meta[sid]["name_sl"]
    home = next((l for l in premium["locations"] if l["home"]), premium["locations"][0])
    print(f"\n=== {home['name']} ({home.get('terrain')}) — danes, top {top} vrst (od {premium['species_indexed']}) ===")
    for s in home["days"][0]["species"][:top]:
        m = meta[s["id"]]
        dbl = m.get("doubles")
        dbl = f"  ⚠ {dbl[:60]}" if dbl else ""
        eco = f"[{(m.get('ecology') or '?')[:4]} {'–'.join(str(v) for v in m['lag_days'])}d]"
        print(f"  {s['index']:3d} %  {nm(s['id']):<28} {eco:<12} {s['explanation']}{dbl}")
    print(f"\n=== {home['name']} — 7-dnevni skupni indeks ===")
    for day in home["days"]:
        best = nm(day["species"][0]["id"]) if day["species"] else "-"
        print(f"  {day['date']}  {day['overall']:3d} % ({day['level']:<7}) nosilka: {best}")
    print("\n=== Danes po lokacijah (geo-afiniteta) ===")
    for loc in premium["locations"]:
        d0 = loc["days"][0]
        best = nm(d0["species"][0]["id"]) if d0["species"] else "-"
        print(f"  {d0['overall']:3d} % ({d0['level']:<7}) {loc['name']:<22} {loc.get('terrain','-'):<8} ({loc['elev_m']} m) — {best}")
    if premium.get("protected_areas"):
        print(f"\n  Zaščitena območja (nabiranje prepovedano): {', '.join(premium['protected_areas'])}")


def main():
    ap = argparse.ArgumentParser(description="Species-level gobarski indeks model")
    ap.add_argument("--out-free", default=FREE_JSON_DEFAULT,
                    help="path for the public free-tier JSON")
    ap.add_argument("--out-premium", default=None,
                    help="path for the premium JSON (omit to skip writing)")
    ap.add_argument("--no-write", action="store_true", help="print summary only")
    args = ap.parse_args()

    rules = load_rules()
    spots, protected = load_locations(rules)
    past_days = past_days_needed(rules)
    print(f"Pridobivam Open-Meteo napoved za {len(spots)} lokacij "
          f"(+ {len(protected)} zaščitenih), {past_days} preteklih dni …")
    try:
        locs = fetch_forecast(spots, past_days)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)
    if len(locs) != len(spots):
        print(f"✗ Pričakoval {len(spots)} lokacij, dobil {len(locs)}", file=sys.stderr)
        sys.exit(1)

    station_precip = load_station_precip()
    print(f"IREICA1 padavine: {len(station_precip)} dni iz history.json")

    premium = compute_forecast(rules, spots, locs, station_precip, protected)
    free = free_payload(premium)
    print_summary(premium)

    if not args.no_write:
        os.makedirs(os.path.dirname(args.out_free), exist_ok=True)
        with open(args.out_free, "w", encoding="utf-8") as f:
            json.dump(free, f, ensure_ascii=False, indent=1)
        print(f"\n→ free JSON: {args.out_free}")
        if args.out_premium:
            with open(args.out_premium, "w", encoding="utf-8") as f:
                json.dump(premium, f, ensure_ascii=False, indent=1)
            print(f"→ premium JSON: {args.out_premium}")


if __name__ == "__main__":
    main()
