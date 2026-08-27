#!/usr/bin/env python3
"""
tools/calculate_frost_risk.py — izračun tveganja pozebe za /opozorilo-pred-pozebo/

Nocojšnja noč (night 0): radiacijski model iz meritev postaje IREICA1 — hitrost
ohlajanja med sončnim zahodom in trenutkom zagona, ekstrapolirana do zore, s
korekcijo za oblačnost/veter/vlago (Open-Meteo napoved za preostanek noči).
Uporabno šele, ko je sonce dejansko zašlo (14h-19h zagon pred sončnim zahodom v
marcu-maju nima česa ekstrapolirati) — takrat in ob nedosegljivih meritvah
skripta pade nazaj na ARSO napoved za to noč.

Naslednji dve noči (night +1, +2): ARSO napoved min. temperature neposredno,
brez lokalne korekcije — to je sinoptični (adventivni) pojav, ne mikroklimatski
(glej §2 specifikacije). Enaka konvencija indeksov kot obstoječi 7-dnevni alarm
v tools/generate_agrometeo_page.py: dan 0 = "danes zvečer/jutri zjutraj".

Kategorija tveganja je na noč **najslabša med vsemi sledenimi vrstami/fenofazami**
(data/frost-thresholds.json + data/phenophase-current.json) — sadovnjak z več
vrstami je ogrožen, čim je ogrožena ena od njih.

Piše:
  data/frost-risk.json          — trenutni izračun (bere ga generate_frost_page.py)
  data/frost-risk-history.json  — dnevnik napoved/dejansko za nocojšnjo noč, samo
                                   v sezoni (marec-maj); verifikacija dodana, ko
                                   history.json dobi dejanski tempLow za tisti dan.

Wired into:
  .github/workflows/frost-warning.yml (tools/generate_frost_page.py teče za njim)

Usage:
  python3 tools/calculate_frost_risk.py [--dry-run]
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
LAT, LON = 46.325779, 14.921137

try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Ljubljana")
except Exception:
    LOCAL_TZ = datetime.timezone.utc

THRESHOLDS_PATH = os.path.join(ROOT, "data", "frost-thresholds.json")
OVERRIDES_PATH = os.path.join(ROOT, "data", "phenophase-current.json")
HISTORY_STATION_PATH = os.path.join(ROOT, "history.json")
OUT_PATH = os.path.join(ROOT, "data", "frost-risk.json")
LOG_PATH = os.path.join(ROOT, "data", "frost-risk-history.json")

NIGHT_LABELS = ["nocoj", "jutri zvečer", "pojutrišnjem zvečer"]
CATEGORY_RANK = {"NIZKO": 0, "SREDNJE": 1, "VISOKO": 2}
LOG_MAX_AGE_DAYS = 400  # nekaj sezon nazaj, dovolj za graf zgodovine — ne raste v nedogled

# Groba fenofazna koledarska privzetka (glej CLAUDE.md/spec §1) — ±10-14 dni
# negotovosti glede na sezono. Ročni popravek v data/phenophase-current.json
# ima vedno prednost. Vrste brez lastnega "mirovanje" praga v frost-thresholds.json
# (vse razen jabolk) med mirovanjem izposodijo jabolčni prag — glej find_phenophase().
PHENOPHASE_CALENDAR = {
    "jabolka": [
        ((1, 1), (3, 31), "mirovanje"),
        ((4, 1), (4, 14), "rozati-popek"),
        ((4, 15), (4, 24), "polno-cvetenje"),
        ((4, 25), (5, 31), "mladi-plod"),
    ],
    "hruske": [
        ((1, 1), (3, 31), "mirovanje"),
        ((4, 1), (4, 10), "belo-balonasto"),
        ((4, 11), (5, 31), "polno-cvetenje"),
    ],
    "breskve-nektarine": [
        ((1, 1), (3, 20), "mirovanje"),
        ((3, 21), (4, 5), "rozati-popek"),
        ((4, 6), (5, 31), "polno-cvetenje"),
    ],
    "slive": [
        ((1, 1), (3, 25), "mirovanje"),
        ((3, 26), (4, 10), "belo-balonasto"),
        ((4, 11), (5, 31), "polno-cvetenje"),
    ],
    "cesnje": [
        ((1, 1), (3, 25), "mirovanje"),
        ((3, 26), (4, 12), "belo-balonasto"),
        ((4, 13), (5, 31), "polno-cvetenje"),
    ],
}


def log(msg):
    print(msg, file=sys.stderr)


def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Meteorec-FrostRisk/1.0)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_current():
    """Trenutne razmere postaje, brez notranjih meritev (glej CLAUDE.md — worker
    jih že reže pri viru, tu jih režemo še enkrat, da to ne visi na eni obrambi)."""
    try:
        current = fetch_json(PROXY + "/ecowitt-current")
    except Exception as e:
        log(f"⚠ /ecowitt-current ni uspel: {e}")
        return None
    if isinstance(current, dict) and isinstance(current.get("data"), dict):
        current["data"].pop("indoor", None)
    return current


def fetch_hourly():
    try:
        data = fetch_json(PROXY + "/hourly")
        return data.get("observations", [])
    except Exception as e:
        log(f"⚠ /hourly ni uspel: {e}")
        return []


def fetch_arso_forecast():
    try:
        data = fetch_json(PROXY + "/arso-forecast")
        return data.get("days", [])
    except Exception as e:
        log(f"⚠ /arso-forecast ni uspel: {e}")
        return []


def fetch_open_meteo():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,cloud_cover,wind_speed_10m,relative_humidity_2m",
        "daily": "sunrise,sunset",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 4,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        return fetch_json(url, timeout=20)
    except Exception as e:
        log(f"⚠ Open-Meteo ni uspel: {e}")
        return None


def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def interp(x, x0, y0, x1, y1):
    if x is None:
        return 0.0
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


# ── Postaja: trenutno stanje ─────────────────────────────────────────────────

def extract_station_now(current, hourly):
    d = (current or {}).get("data", {}) or {}
    obs = d.get("outdoor", {}) or {}
    wind = d.get("wind", {}) or {}
    temp_now = safe_float((obs.get("temperature") or {}).get("value"))
    hum_now = safe_float((obs.get("humidity") or {}).get("value"))
    wind_now = safe_float((wind.get("wind_speed") or {}).get("value"))
    gust_now = safe_float((wind.get("wind_gust") or {}).get("value"))

    min_24h = None
    for o in (hourly or [])[-24:]:
        tl = safe_float((o.get("metric") or {}).get("tempLow"))
        if tl is not None and (min_24h is None or tl < min_24h):
            min_24h = tl

    return {
        "temp_now_c": temp_now, "humidity_now_pct": hum_now,
        "wind_now_kmh": wind_now, "wind_gust_now_kmh": gust_now,
        "min_24h_c": min_24h,
    }


def parse_wu_time(s):
    """WU urna serija: 'YYYY-MM-DD HH:MM' ali '...:SS'. Naivni lokalni čas."""
    if not s:
        return None
    s = s[:16]
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def nearest_hourly_temp(hourly, target_dt, tolerance_min=75):
    best, best_dt_diff = None, None
    for o in hourly or []:
        dt = parse_wu_time(o.get("obsTimeLocal"))
        if dt is None:
            continue
        diff = abs((dt - target_dt).total_seconds()) / 60
        if diff <= tolerance_min and (best_dt_diff is None or diff < best_dt_diff):
            m = o.get("metric") or {}
            t = safe_float(m.get("tempAvg"))
            if t is None:
                t = safe_float(m.get("tempHigh"))
            if t is not None:
                best, best_dt_diff = t, diff
    return best


def om_daily(om, key, i=0):
    try:
        return (om.get("daily") or {}).get(key, [])[i]
    except (IndexError, AttributeError, TypeError):
        return None


def overnight_avgs(om, start_dt, end_dt):
    """Povprečja Open-Meteo urnih spremenljivk med start_dt in end_dt (naivna
    lokalna časa, Europe/Ljubljana — isti timezone parameter kot poizvedba)."""
    hourly = (om or {}).get("hourly") or {}
    times = hourly.get("time") or []
    clouds, winds, rhs = [], [], []
    for i, t in enumerate(times):
        try:
            dt = datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        if start_dt <= dt <= end_dt:
            c = safe_float((hourly.get("cloud_cover") or [None] * len(times))[i])
            w = safe_float((hourly.get("wind_speed_10m") or [None] * len(times))[i])
            h = safe_float((hourly.get("relative_humidity_2m") or [None] * len(times))[i])
            if c is not None:
                clouds.append(c)
            if w is not None:
                winds.append(w)
            if h is not None:
                rhs.append(h)
    avg = lambda xs: (sum(xs) / len(xs)) if xs else None
    return avg(clouds), avg(winds), avg(rhs)


def compute_radiative_min(hourly, om, station_now, now_local):
    """Nocojšnji minimum iz dejanske hitrosti ohlajanja postaje. Vrne None, če
    sonce (za danes) še ni zašlo dovolj dolgo, da bi imeli kaj meriti — takrat
    kliceč koda pade nazaj na ARSO."""
    sunset_s = om_daily(om, "sunset", 0)
    sunrise_tom_s = om_daily(om, "sunrise", 1)
    if not sunset_s or not sunrise_tom_s or station_now.get("temp_now_c") is None:
        return None
    try:
        sunset_dt = datetime.datetime.strptime(sunset_s[:16], "%Y-%m-%dT%H:%M")
        sunrise_tom_dt = datetime.datetime.strptime(sunrise_tom_s[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return None

    now_naive = now_local.replace(tzinfo=None)
    hours_since_sunset = (now_naive - sunset_dt).total_seconds() / 3600
    if hours_since_sunset < 0.5:
        return None  # sonce še ni dovolj dolgo zašlo za oceno ohlajanja

    temp_sunset = nearest_hourly_temp(hourly, sunset_dt)
    if temp_sunset is None:
        return None
    temp_now = station_now["temp_now_c"]

    cooling_rate = (temp_sunset - temp_now) / hours_since_sunset
    # Tudi če se v tem oknu (še) ni ohladilo (npr. oblačno ob sončnem zahodu),
    # ponoči še vedno pričakujemo neko ohlajanje -- ne dovolimo padca na 0.
    cooling_rate = max(cooling_rate, 0.3)

    dawn_dt = sunrise_tom_dt - datetime.timedelta(minutes=45)
    hours_to_dawn = clamp((dawn_dt - now_naive).total_seconds() / 3600, 3, 14)

    # Radiacijsko ohlajanje čez noč upočasnjuje (izsevana energija se manjša,
    # kondenzacija sprošča latentno toploto) -- linearna ekstrapolacija do zore
    # bi minimum sistematsko podcenila, zato jo dušimo.
    DAMPING = 0.55
    extrapolated = temp_now - cooling_rate * hours_to_dawn * DAMPING

    avg_cloud, avg_wind, avg_rh = overnight_avgs(om, now_naive, dawn_dt)
    # Jasno nebo pospeši sevalno ohlajanje, oblačna odeja ga zavre.
    cloud_corr = interp(avg_cloud, 30, -1.0, 70, 2.5)
    # Miren zrak (< 2 m/s ≈ 7,2 km/h) ne meša zračnih plasti -> hladnejše dno
    # doline; veter nad ~4 m/s (14,4 km/h) mešanje prepreči.
    wind_corr = interp(avg_wind, 7.2, -1.0, 14.4, 2.0)
    # Visoka vlaga dvigne rosišče -- kondenzacija sprošča latentno toploto in
    # dvigne dno padca.
    rh_corr = interp(avg_rh, 40, -0.3, 85, 0.7)

    predicted = extrapolated + cloud_corr + wind_corr + rh_corr
    return {
        "predicted_min_c": round(predicted, 1),
        "cooling_rate_c_per_h": round(cooling_rate, 2),
        "hours_to_dawn": round(hours_to_dawn, 1),
        "temp_sunset_c": round(temp_sunset, 1),
        "temp_now_c": round(temp_now, 1),
        "avg_cloud_pct": round(avg_cloud, 0) if avg_cloud is not None else None,
        "avg_wind_kmh": round(avg_wind, 1) if avg_wind is not None else None,
        "avg_rh_pct": round(avg_rh, 0) if avg_rh is not None else None,
        "cloud_corr_c": round(cloud_corr, 1),
        "wind_corr_c": round(wind_corr, 1),
        "rh_corr_c": round(rh_corr, 1),
    }


# ── Fenofaza in kategorija tveganja ──────────────────────────────────────────

def load_thresholds():
    data = json.load(open(THRESHOLDS_PATH, encoding="utf-8"))
    by_id = {sp["id"]: sp for sp in data["species"]}
    return data, by_id


def load_overrides():
    try:
        return json.load(open(OVERRIDES_PATH, encoding="utf-8"))
    except Exception:
        return {"species": {}}


def fallback_phenophase(species_id, date_obj):
    md = (date_obj.month, date_obj.day)
    for start, end, pid in PHENOPHASE_CALENDAR.get(species_id, []):
        if start <= md <= end:
            return pid
    return "mirovanje"  # izven znanih razponov (poletje/jesen/zima) -- trdota mirovanja


def find_phenophase(species_by_id, species_id, phenophase_id):
    sp = species_by_id.get(species_id)
    if not sp:
        return None
    for p in sp["phenophases"]:
        if p["id"] == phenophase_id:
            return p
    if phenophase_id == "mirovanje":
        # Samo jabolka imajo v tabeli vrstico za mirovanje -- ostale vrste si
        # jo v tej fazi izposodijo kot razumen približek (vse sadno drevje ima
        # v globokem mirovanju podobno trdoto), glej CLAUDE.md/opomba v podatkih.
        jab = species_by_id.get("jabolka")
        if jab:
            for p in jab["phenophases"]:
                if p["id"] == "mirovanje":
                    return p
    return None


def get_current_phenophase(species_by_id, overrides, species_id, date_obj):
    valid_ids = {p["id"] for p in species_by_id[species_id]["phenophases"]}
    override = (overrides.get("species") or {}).get(species_id)
    if override and (override in valid_ids or override == "mirovanje"):
        return override, "ročno"
    return fallback_phenophase(species_id, date_obj), "koledar (privzeto)"


def classify(min_temp, t10, t90):
    if min_temp is None:
        return None
    if min_temp > t10:
        return "NIZKO"
    if min_temp > t90:
        return "SREDNJE"
    return "VISOKO"


def classify_species(species_by_id, overrides, date_obj, predicted_min):
    rows, worst, worst_rank = [], None, -1
    for sp_id, sp in species_by_id.items():
        phen_id, phen_source = get_current_phenophase(species_by_id, overrides, sp_id, date_obj)
        phen = find_phenophase(species_by_id, sp_id, phen_id)
        if phen is None:
            continue
        cat = classify(predicted_min, phen["t10"], phen["t90"])
        row = {
            "id": sp_id, "name": sp["name"],
            "phenophase_id": phen["id"], "phenophase_name": phen["name"],
            "phenophase_source": phen_source,
            "t10": phen["t10"], "t90": phen["t90"], "category": cat,
        }
        rows.append(row)
        rank = CATEGORY_RANK.get(cat, -1)
        if rank > worst_rank:
            worst_rank, worst = rank, row
    rows.sort(key=lambda r: r["name"])
    return rows, worst


# ── ARSO (adventivna pozeba, brez lokalne korekcije) ─────────────────────────

def pick_arso_day(arso_days, date_obj):
    date_s = date_obj.isoformat()
    for d in arso_days:
        if d.get("valid_date") == date_s:
            return d
    return None


# ── Dnevnik napoved/dejansko (verifikacija) ──────────────────────────────────

def load_log():
    try:
        return json.load(open(LOG_PATH, encoding="utf-8"))
    except Exception:
        return []


def load_station_history():
    try:
        return json.load(open(HISTORY_STATION_PATH, encoding="utf-8"))
    except Exception:
        return {}


def verify_log(entries, station_hist, now_utc):
    changed = False
    for e in entries:
        if e.get("actual_min_c") is not None:
            continue
        v = station_hist.get(e["date"])
        tl = (v or {}).get("tempLow")
        if tl is not None:
            e["actual_min_c"] = tl
            e["actual_category"] = classify(tl, e["t10"], e["t90"]) if e.get("t10") is not None else None
            e["verified_at"] = now_utc.isoformat()
            changed = True
    return changed


def upsert_tonight(entries, today_iso, night0, now_utc):
    if night0["predicted_min_c"] is None or night0["worst"] is None:
        return False
    entries[:] = [e for e in entries if e["date"] != today_iso]
    entries.append({
        "date": today_iso,
        "predicted_min_c": night0["predicted_min_c"],
        "predicted_source": night0["source"],
        "predicted_category": night0["worst"]["category"],
        "worst_species_id": night0["worst"]["id"],
        "worst_species_name": night0["worst"]["name"],
        "worst_phenophase_name": night0["worst"]["phenophase_name"],
        "t10": night0["worst"]["t10"], "t90": night0["worst"]["t90"],
        "predicted_at": now_utc.isoformat(),
        "actual_min_c": None, "actual_category": None, "verified_at": None,
    })
    entries.sort(key=lambda e: e["date"])
    return True


def prune_log(entries, today):
    cutoff = (today - datetime.timedelta(days=LOG_MAX_AGE_DAYS)).isoformat()
    entries[:] = [e for e in entries if e["date"] >= cutoff]


# ── Glavni tok ────────────────────────────────────────────────────────────────

def main():
    dry = "--dry-run" in sys.argv[1:]

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    today = now_local.date()
    in_season = today.month in (3, 4, 5)

    _, species_by_id = load_thresholds()
    overrides = load_overrides()

    current = fetch_current()
    hourly = fetch_hourly()
    arso_days = fetch_arso_forecast()
    om = fetch_open_meteo()

    if current is None and not hourly:
        log("✗ Ne postaje ne urne serije ni bilo mogoče pridobiti -- pustim staro data/frost-risk.json.")
        return 0 if not dry else 1

    station = extract_station_now(current, hourly)

    nights = []
    for i, label in enumerate(NIGHT_LABELS):
        date_obj = today + datetime.timedelta(days=i)
        arso_day = pick_arso_day(arso_days, date_obj)
        arso_tmin = safe_float((arso_day or {}).get("tmin"))

        radiative = compute_radiative_min(hourly, om, station, now_local) if i == 0 else None
        if radiative:
            predicted_min = radiative["predicted_min_c"]
            source = "postaja IREICA1 (radiacijski model)"
        elif arso_tmin is not None:
            predicted_min = arso_tmin
            source = "ARSO napoved" if i > 0 else "ARSO napoved (predhodna — sonce še ni dovolj dolgo zašlo za lokalni model)"
        else:
            predicted_min = None
            source = None

        species_rows, worst = classify_species(species_by_id, overrides, date_obj, predicted_min) if in_season else ([], None)

        nights.append({
            "date": date_obj.isoformat(),
            "label": label,
            "predicted_min_c": predicted_min,
            "source": source,
            "arso_tmin_c": arso_tmin,
            "radiative": radiative,
            "species": species_rows,
            "worst": worst,
        })

    overall_category = None
    if in_season and nights[0]["worst"]:
        overall_category = nights[0]["worst"]["category"]

    out = {
        "generated_at": now_utc.isoformat(),
        "generated_at_local": now_local.strftime("%-d. %-m. %Y ob %H:%M"),
        "in_season": in_season,
        "station": station,
        "overall_category": overall_category,
        "nights": nights,
    }

    if dry:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"data/frost-risk.json: {overall_category or ('izven sezone' if not in_season else 'ni podatka')} "
          f"({nights[0]['predicted_min_c']} °C nocoj, vir: {nights[0]['source']})")

    if in_season:
        entries = load_log()
        station_hist = load_station_history()
        v_changed = verify_log(entries, station_hist, now_utc)
        u_changed = upsert_tonight(entries, today.isoformat(), nights[0], now_utc)
        if v_changed or u_changed:
            prune_log(entries, today)
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"data/frost-risk-history.json: {len(entries)} vnosov "
                  f"({'verifikacija' if v_changed else ''}{' + ' if v_changed and u_changed else ''}"
                  f"{'nov vnos' if u_changed else ''}).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
