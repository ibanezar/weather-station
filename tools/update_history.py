#!/usr/bin/env python3
"""
Osveži history.json z dnevnimi povzetki.

PRIMARNI VIR  — prava postaja IREICA1 prek Ecowitt History API (resnične meritve).
REZERVNI VIR  — Open-Meteo Archive (ERA5 reanaliza) za dneve, kjer postaja nima
                podatkov (izpad, vrzel, dnevi pred postavitvijo postaje).

Vsak zapis dobi oznako "src": "station" (meritev) ali "src": "era5" (model).

    python3 tools/update_history.py 2026-06

Ecowitt poverilnice se berejo iz okolja (EW_APP / EW_API / EW_MAC); če niso
nastavljene, se uporabijo javne konstante iz Worker-ja (worker.js).
"""
import json, os, sys, re, calendar, urllib.request, urllib.parse, urllib.error
from datetime import date as _date, datetime, timezone

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Berlin")
except Exception:
    TZ = timezone.utc

LAT  = 46.325779
LON  = 14.921137
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = ['tempHigh', 'tempLow', 'tempAvg', 'precipTotal',
            'windspeedHigh', 'windspeedAvg', 'humidityAvg']

# Ecowitt poverilnice — okolje najprej, sicer javni fallback (enak kot v worker.js)
# .strip() odstrani morebitne presledke/nove vrstice iz prilepljenih secrets.
EW_APP = (os.environ.get("EW_APP") or "A7E5CAF73FCC9BF859CDE788D69A1C91").strip()
EW_API = (os.environ.get("EW_API") or "0bd213c8-8e54-4bf6-b6da-127a1c605034").strip()
EW_MAC = (os.environ.get("EW_MAC") or "BC:DD:C2:42:8D:56").strip()


# ── Pomožne funkcije za vrednosti ──────────────────────────────────────────
def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def _pick(v, keys):
    """Iz skalarja ali objekta {max,min,avg,...} izlušči prvo ne-null vrednost."""
    if isinstance(v, dict):
        for k in keys:
            if v.get(k) is not None:
                return _num(v[k])
        return None
    return _num(v)


# ── PRIMARNI VIR: Ecowitt (prava postaja) ──────────────────────────────────
_HEX32 = re.compile(r"^[0-9a-fA-F]{32}$")
_UUID  = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

def _shape(name, v):
    """Opiše obliko ključa BREZ razkritja vrednosti (za diagnostiko)."""
    if not v:
        return f"{name}: PRAZNO"
    s = v.strip()
    if _HEX32.match(s):
        kind = "32-hex (Application-Key oblika)"
    elif _UUID.match(s):
        kind = "UUID (API-Key oblika)"
    else:
        kind = "neznana oblika"
    extra = " ⚠ presledki/nova vrstica!" if s != v else ""
    return f"{name}: dolžina={len(v)}, {kind}{extra}"

def _diagnose_keys():
    print("  Diagnostika ključev (brez razkritja vrednosti):")
    print("   " + _shape("EW_APP", EW_APP))
    print("   " + _shape("EW_API", EW_API))
    a, i = (EW_APP or "").strip(), (EW_API or "").strip()
    if _UUID.match(a) or (_HEX32.match(i) and not _HEX32.match(a)):
        print("   → KLJUČA STA VERJETNO ZAMENJANA: EW_APP mora biti 32-hex, EW_API pa UUID.")

def fetch_ecowitt(start, end):
    """Vrne surov Ecowitt 'data' objekt ali None (ob napaki — sledi fallback)."""
    if not (EW_APP and EW_API and EW_MAC):
        return None
    # Ecowitt device/history zahteva GET s query parametri — POST vrne 40010.
    params = urllib.parse.urlencode({
        "application_key":   EW_APP,
        "api_key":           EW_API,
        "mac":               EW_MAC,
        "start_date":        start + " 00:00:00",
        "end_date":          end + " 23:59:59",
        "cycle_type":        "auto",
        "call_back":         ("outdoor.temperature,outdoor.humidity,outdoor.dew_point,"
                              "wind.wind_speed,wind.wind_gust,pressure.relative,"
                              "rainfall.daily,solar_and_uvi.solar,solar_and_uvi.uvi"),
        "temp_unitid":       "1",   # °C (velja tudi za rosišče)
        "pressure_unitid":   "3",   # hPa
        "wind_speed_unitid": "7",   # km/h
        "rainfall_unitid":   "12",  # mm
        "solar_irradiance_unitid": "16",  # W/m²
    })
    req = urllib.request.Request(
        "https://api.ecowitt.net/api/v3/device/history?" + params,
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
    except Exception as e:
        print(f"⚠ Ecowitt nedosegljiv ({e}); uporabim Open-Meteo.")
        return None
    if j.get("code") != 0:
        print(f"⚠ Ecowitt napaka {j.get('code')}: {j.get('msg')}; uporabim Open-Meteo.")
        _diagnose_keys()
        return None
    return j.get("data")

def _ew_list(data, *path):
    cur = data
    for k in path:
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(k)
    return cur.get("list") if isinstance(cur, dict) else {}

def _ew_day(ts):
    return datetime.fromtimestamp(int(ts), TZ).date().isoformat()

def normalize_ecowitt(data):
    """Surove pod-dnevne meritve → {date: dnevni povzetek}."""
    if not data:
        return {}
    days = {}
    def bucket(ts):
        return days.setdefault(_ew_day(ts), {
            "hi": [], "lo": [], "av": [], "wH": [], "wA": [], "hum": [], "rain": [],
            "dpH": [], "dpL": [], "dpA": [], "wg": [],
            "prH": [], "prL": [], "prA": [], "sol": [], "uv": []})

    for ts, v in (_ew_list(data, "outdoor", "temperature") or {}).items():
        b = bucket(ts)
        b["hi"].append(_pick(v, ["max", "avg", "value"]))
        b["lo"].append(_pick(v, ["min", "avg", "value"]))
        b["av"].append(_pick(v, ["avg", "value", "max"]))
    for ts, v in (_ew_list(data, "outdoor", "humidity") or {}).items():
        bucket(ts)["hum"].append(_pick(v, ["avg", "value", "max"]))
    for ts, v in (_ew_list(data, "outdoor", "dew_point") or {}).items():
        b = bucket(ts)
        b["dpH"].append(_pick(v, ["max", "avg", "value"]))
        b["dpL"].append(_pick(v, ["min", "avg", "value"]))
        b["dpA"].append(_pick(v, ["avg", "value", "max"]))
    for ts, v in (_ew_list(data, "wind", "wind_speed") or {}).items():
        b = bucket(ts)
        b["wH"].append(_pick(v, ["max", "avg", "value"]))
        b["wA"].append(_pick(v, ["avg", "value", "max"]))
    for ts, v in (_ew_list(data, "wind", "wind_gust") or {}).items():
        bucket(ts)["wg"].append(_pick(v, ["max", "avg", "value"]))
    for ts, v in (_ew_list(data, "pressure", "relative") or {}).items():
        b = bucket(ts)
        b["prH"].append(_pick(v, ["max", "avg", "value"]))
        b["prL"].append(_pick(v, ["min", "avg", "value"]))
        b["prA"].append(_pick(v, ["avg", "value", "max"]))
    for ts, v in (_ew_list(data, "rainfall", "daily") or {}).items():
        bucket(ts)["rain"].append(_pick(v, ["total", "max", "value"]) or 0.0)
    for ts, v in (_ew_list(data, "solar_and_uvi", "solar") or {}).items():
        bucket(ts)["sol"].append(_pick(v, ["max", "avg", "value"]))
    for ts, v in (_ew_list(data, "solar_and_uvi", "uvi") or {}).items():
        bucket(ts)["uv"].append(_pick(v, ["max", "avg", "value"]))

    def clean(a):
        return [n for n in a if n is not None]

    out = {}
    for d, x in days.items():
        hi, lo, av  = clean(x["hi"]), clean(x["lo"]), clean(x["av"])
        wH, wA, hum = clean(x["wH"]), clean(x["wA"]), clean(x["hum"])
        rain        = clean(x["rain"])
        dpH, dpL, dpA = clean(x["dpH"]), clean(x["dpL"]), clean(x["dpA"])
        prH, prL, prA = clean(x["prH"]), clean(x["prL"]), clean(x["prA"])
        wg, sol, uv   = clean(x["wg"]), clean(x["sol"]), clean(x["uv"])
        rec = {
            "tempHigh":      round(max(hi), 1) if hi else None,
            "tempLow":       round(min(lo), 1) if lo else None,
            "tempAvg":       round(sum(av) / len(av), 1) if av else None,
            "precipTotal":   round(max(rain), 1) if rain else 0,
            "windspeedHigh": round(max(wH), 1) if wH else None,
            "windspeedAvg":  round(sum(wA) / len(wA), 1) if wA else None,
            "humidityAvg":   round(sum(hum) / len(hum), 1) if hum else None,
        }
        # Neobvezna polja — dodamo le, če postaja za ta dan ima senzor/podatke.
        opt = {
            "dewptHigh":     round(max(dpH), 1) if dpH else None,
            "dewptLow":      round(min(dpL), 1) if dpL else None,
            "dewptAvg":      round(sum(dpA) / len(dpA), 1) if dpA else None,
            "pressureHigh":  round(max(prH), 1) if prH else None,
            "pressureLow":   round(min(prL), 1) if prL else None,
            "pressureAvg":   round(sum(prA) / len(prA), 1) if prA else None,
            "windgustHigh":  round(max(wg), 1) if wg else None,
            "solarHigh":     round(max(sol), 1) if sol else None,
            "uviHigh":       round(max(uv), 1) if uv else None,
        }
        rec.update({k: v for k, v in opt.items() if v is not None})
        out[d] = rec
    return out


# ── REZERVNI VIR: Open-Meteo Archive (ERA5) ────────────────────────────────
def fetch_openmeteo(start, end):
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
        print(f"⚠ Open-Meteo {e.code}: {body}")
        return None
    except Exception as e:
        print(f"⚠ Napaka pri klicu Open-Meteo: {e}")
        return None

def _hourly_means(data, key):
    times  = data.get("hourly", {}).get("time", [])
    values = data.get("hourly", {}).get(key, [])
    by_day = {}
    for t, v in zip(times, values):
        if v is not None:
            by_day.setdefault(t[:10], []).append(float(v))
    return {d: round(sum(vs) / len(vs), 1) for d, vs in by_day.items()}

def openmeteo_days(start, end, ym):
    """Open-Meteo → {date: dnevni povzetek} (samo dnevi v mesecu ym)."""
    data = fetch_openmeteo(start, end)
    if not data:
        return {}
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if not dates:
        return {}
    hum_avg  = _hourly_means(data, "relativehumidity_2m")
    wind_avg = _hourly_means(data, "windspeed_10m")

    def get(key, i):
        lst = daily.get(key, [])
        return lst[i] if i < len(lst) else None

    out = {}
    for i, date in enumerate(dates):
        if not date.startswith(ym):
            continue
        t_avg = get("temperature_2m_mean", i)
        if t_avg is None:
            continue
        out[date] = {
            "tempHigh":      get("temperature_2m_max", i),
            "tempLow":       get("temperature_2m_min", i),
            "tempAvg":       t_avg,
            "precipTotal":   get("precipitation_sum",  i) or 0,
            "windspeedHigh": get("windspeed_10m_max",  i),
            "windspeedAvg":  wind_avg.get(date),
            "humidityAvg":   hum_avg.get(date),
        }
    return out


# ── Združevanje ────────────────────────────────────────────────────────────
def _complete(m):
    return all(m.get(f) is not None for f in REQUIRED)

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: update_history.py YYYY-MM")
    ym = sys.argv[1]
    y, m = int(ym[:4]), int(ym[5:7])
    start     = f"{ym}-01"
    month_end = f"{ym}-{calendar.monthrange(y, m)[1]:02d}"
    today     = _date.today().isoformat()
    end       = min(month_end, today)

    # 1) prava postaja (primarni vir)
    station = normalize_ecowitt(fetch_ecowitt(start, end))
    # 2) Open-Meteo (rezerva)
    era5 = openmeteo_days(start, end, ym)

    if not station and not era5:
        sys.exit(f"Ne postaja ne Open-Meteo nista vrnila podatkov za {ym}.")

    hp   = os.path.join(ROOT, "history.json")
    hist = json.load(open(hp, encoding="utf-8"))

    n_station = n_era5 = 0
    for date in sorted(set(station) | set(era5)):
        if not date.startswith(ym):
            continue
        s = station.get(date)
        e = era5.get(date)

        # Postaja ima prednost; manjkajoča polja dopolni iz Open-Meteo
        if s:
            if e:
                for f in REQUIRED:
                    if s.get(f) is None and e.get(f) is not None:
                        s[f] = e[f]
            if _complete(s):
                hist[date] = {**s, "src": "station"}
                n_station += 1
                continue

        # Rezerva — a nikoli ne povozi že zabeležene prave meritve z modelom
        if e and _complete(e):
            if hist.get(date, {}).get("src") == "station":
                continue
            hist[date] = {**e, "src": "era5"}
            n_era5 += 1

    if not (n_station + n_era5):
        sys.exit(f"Za {ym} ni uporabnih dni (ne postaja ne Open-Meteo).")

    out = {k: hist[k] for k in sorted(hist)}
    json.dump(out, open(hp, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"✓ history.json: {n_station} dni iz postaje, {n_era5} iz Open-Meteo "
          f"za {ym} (skupaj {len(out)} dni)")

if __name__ == "__main__":
    main()
