#!/usr/bin/env python3
"""
tools/log_forward_forecasts.py — Faza 1b v brief-u za /test-napovedi/: ARSO in
Yr.no (MET Norway) nimata arhiva preteklih napovedi, zato ju začnemo beležiti
sproti, dan za dnem, od zdaj naprej. Dokler se ne nabere dovolj razrešenih dni,
ju stran prikazuje ločeno od petih Open-Meteo virov (glej generate_test_napovedi_page.py).

Piše v isto shemo kot data/forecast-archive.csv (source namesto model:
"arso"/"yr"), da ju compute_forecast_test_metrics.py lahko bere po isti poti —
data/forecast-forward-log.csv.

ARSO: prek obstoječega Worker proxyja (/arso-forecast, glej tudi
verify_forecasts.py) — ARSO nima napovedne točke za Rečico ob Savinji, zato
Worker vzame najbližji kraj s svojega seznama (Ljubno ob Savinji, ~9 km gorvodno).

Yr/MET Norway: obvezen User-Agent z imenom projekta in kontaktom (brez njega
blokirajo), spoštujemo `Expires` glavo s klicem enkrat dnevno (cron), ne
pogosteje. Padavine: `next_1_hours` za gosto (urno) bližnje obdobje, sicer
`next_6_hours` za redkeje vzorčeno oddaljeno obdobje — teh dveh se ne sešteva
na istem časovniku, ker bi se prekrivala.

XWeather (Vaisala; nekdanji AerisWeather): komercialna napoved, ki zlije več modelov in jih
popravi s strojnim učenjem — referenca za semafor kot Yr in ARSO. Brez arhiva za nazaj, zato se
beleži sproti (en klic na dan, ~30 od 15.000 mesečnih dostopov). Dostop je **izbiren**: brez
secretov `XWEATHER_CLIENT_ID` in `XWEATHER_CLIENT_SECRET` se vir tiho preskoči (to ni napaka).
Zahtevamo URNO napoved (`filter=1hr`) in dnevne vrednosti sestavimo po lokalnem času
Europe/Ljubljana po isti poti kot pri Yr — tako Tmax/Tmin pomenita isto pri vseh virih in nam ni treba
ugibati, kakšno okno zajema XWeatherjev »dnevni« period. Dan z manj kot 20 urnimi točkami (npr. zadnji,
odrezani dan) se ne zapiše. Odgovor ima ovoj `{"success", "error", "response": [{"periods": [...]}]}`.
**Živo nepreizkušeno** (iz peskovnika api.xweather.com ni dosegljiv): po prvem teku preveri
`data/forecast-forward-log.csv` za model `xweather` (7 dni × tmax/tmin/padavine, smiselne številke).
Ključa nikoli ne izpišemo (gre v URL), User-Agent je generičen (brez kontaktnih podatkov).

Usage:
  python3 tools/log_forward_forecasts.py
"""
import csv, datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT, LON = 46.325779, 14.921137
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA_ARSO = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ForecastTest/1.0; +https://meteorec.si)"}
UA_YR = {"User-Agent": "Meteorec-ForecastTest/1.0 https://meteorec.si filip.eremita@gmail.com"}
FORWARD_LOG_PATH = os.path.join(ROOT, "data", "forecast-forward-log.csv")
FIELDS = ["model", "lead_days", "valid_at", "issued_at", "tmax_c", "tmin_c", "precip_mm"]
MAX_LEAD = 7
XWEATHER_URL = "https://data.api.xweather.com/forecasts/{lat},{lon}"
XWEATHER_MIN_HOURS = 20   # dan z manj urnimi točkami je odrezan (zadnji dan okna) in bi popačil Tmax/Tmin


def load_existing():
    seen, rows = set(), []
    if os.path.exists(FORWARD_LOG_PATH):
        with open(FORWARD_LOG_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                seen.add((row["model"], row["issued_at"], row["valid_at"]))
    return rows, seen


def save(rows):
    rows.sort(key=lambda r: (r["model"], r["issued_at"], r["valid_at"]))
    os.makedirs(os.path.dirname(FORWARD_LOG_PATH), exist_ok=True)
    with open(FORWARD_LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def fetch_arso(today):
    req = urllib.request.Request(f"{WORKER}/arso-forecast", headers=UA_ARSO)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    out = []
    for day in data.get("days", []):
        d = day.get("valid_date")
        if not d:
            continue
        lead = (datetime.date.fromisoformat(d) - today).days
        if not (1 <= lead <= MAX_LEAD):
            continue
        if day.get("tmax") is None:
            continue
        out.append({
            "model": "arso", "lead_days": lead, "valid_at": d, "issued_at": today.isoformat(),
            "tmax_c": day.get("tmax"), "tmin_c": day.get("tmin"), "precip_mm": day.get("precip"),
        })
    return out


def fetch_yr(today):
    url = (f"https://api.met.no/weatherapi/locationforecast/2.0/compact"
           f"?lat={LAT}&lon={LON}")
    req = urllib.request.Request(url, headers=UA_YR)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    ts = (data.get("properties") or {}).get("timeseries") or []

    by_day = {}
    for pt in ts:
        t = pt.get("time")  # ISO UTC, npr. "2026-08-24T09:00:00Z"
        if not t:
            continue
        utc = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        local = utc.astimezone(TZ_LJ)
        d = local.date().isoformat()
        b = by_day.setdefault(d, {"temp": [], "precip": 0.0, "has_1h": set()})
        dd = pt.get("data") or {}
        temp = ((dd.get("instant") or {}).get("details") or {}).get("air_temperature")
        if temp is not None:
            b["temp"].append(temp)
        n1 = (dd.get("next_1_hours") or {}).get("details") or {}
        if "precipitation_amount" in n1:
            b["precip"] += n1["precipitation_amount"] or 0.0
            b["has_1h"].add(d)

    # Za redkeje vzorčeno obdobje (brez next_1_hours na tem dnevu) uporabimo
    # next_6_hours -- ampak šele v drugem prehodu, da vemo, kateri dnevi so že
    # dobili urno vsoto (teh next_6_hours NE prištevamo, da se ne podvoji).
    for pt in ts:
        t = pt.get("time")
        if not t:
            continue
        utc = datetime.datetime.fromisoformat(t.replace("Z", "+00:00"))
        local = utc.astimezone(TZ_LJ)
        d = local.date().isoformat()
        b = by_day.get(d)
        if b is None or d in b["has_1h"]:
            continue
        dd = pt.get("data") or {}
        n6 = (dd.get("next_6_hours") or {}).get("details") or {}
        if "precipitation_amount" in n6:
            b["precip"] += n6["precipitation_amount"] or 0.0

    out = []
    for d, b in by_day.items():
        lead = (datetime.date.fromisoformat(d) - today).days
        if not (1 <= lead <= MAX_LEAD) or not b["temp"]:
            continue
        out.append({
            "model": "yr", "lead_days": lead, "valid_at": d, "issued_at": today.isoformat(),
            "tmax_c": round(max(b["temp"]), 1), "tmin_c": round(min(b["temp"]), 1),
            "precip_mm": round(b["precip"], 1),
        })
    return out


class XWeatherError(Exception):
    pass


def xweather_credentials():
    cid = os.environ.get("XWEATHER_CLIENT_ID", "").strip()
    sec = os.environ.get("XWEATHER_CLIENT_SECRET", "").strip()
    return (cid, sec) if cid and sec else None


def parse_xweather(data, today):
    """Urni odgovor XWeather → dnevne vrstice (lokalni dan Europe/Ljubljana)."""
    if data.get("success") is False:
        code = ((data.get("error") or {}).get("code")) or "unknown"
        raise XWeatherError(f"API napaka: {code}")
    resp = data.get("response")
    if isinstance(resp, list):
        resp = resp[0] if resp else {}
    periods = (resp or {}).get("periods") or []
    by_day = {}
    for p in periods:
        t = p.get("dateTimeISO")
        temp = p.get("tempC")
        if not t or temp is None:
            continue
        local = datetime.datetime.fromisoformat(t).astimezone(TZ_LJ)
        b = by_day.setdefault(local.date().isoformat(), {"temp": [], "precip": [], "hours": set()})
        if local.hour in b["hours"]:
            continue   # podvojena ura (varovalka)
        b["hours"].add(local.hour)
        b["temp"].append(temp)
        if p.get("precipMM") is not None:
            b["precip"].append(p["precipMM"])
    out = []
    for d, b in by_day.items():
        lead = (datetime.date.fromisoformat(d) - today).days
        if not (1 <= lead <= MAX_LEAD) or len(b["temp"]) < XWEATHER_MIN_HOURS:
            continue
        out.append({
            "model": "xweather", "lead_days": lead, "valid_at": d, "issued_at": today.isoformat(),
            "tmax_c": round(max(b["temp"]), 1), "tmin_c": round(min(b["temp"]), 1),
            "precip_mm": round(sum(b["precip"]), 1) if b["precip"] else None,
        })
    return out


def fetch_xweather(today):
    cred = xweather_credentials()
    if cred is None:
        return None   # vir ni nastavljen: preskok, ne napaka
    q = urllib.parse.urlencode({"filter": "1hr", "limit": 192,
                                "client_id": cred[0], "client_secret": cred[1]})
    url = XWEATHER_URL.format(lat=LAT, lon=LON) + "?" + q
    req = urllib.request.Request(url, headers=UA_ARSO)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return parse_xweather(data, today)


def main():
    global TZ_LJ
    try:
        from zoneinfo import ZoneInfo
        TZ_LJ = ZoneInfo("Europe/Ljubljana")
    except Exception:
        TZ_LJ = datetime.timezone.utc

    today = datetime.date.today()
    rows, seen = load_existing()
    added = 0

    try:
        for r in fetch_arso(today):
            key = (r["model"], r["issued_at"], r["valid_at"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({k: str(v) if v is not None else "" for k, v in r.items()})
            added += 1
        print("✓ ARSO napoved zabeležena.")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ ARSO napoved nedosegljiva: {e}", file=sys.stderr)

    try:
        for r in fetch_yr(today):
            key = (r["model"], r["issued_at"], r["valid_at"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({k: str(v) if v is not None else "" for k, v in r.items()})
            added += 1
        print("✓ Yr/MET Norway napoved zabeležena.")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"⚠ Yr napoved nedosegljiva: {e}", file=sys.stderr)

    try:
        xw = fetch_xweather(today)
        if xw is None:
            print("• XWeather preskočen: XWEATHER_CLIENT_ID/XWEATHER_CLIENT_SECRET nista nastavljena.")
        else:
            if not xw:
                print("⚠ XWeather: odgovor brez uporabnih dni (preveri obliko odgovora).", file=sys.stderr)
            for r in xw:
                key = (r["model"], r["issued_at"], r["valid_at"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append({k: str(v) if v is not None else "" for k, v in r.items()})
                added += 1
            if xw:
                print("✓ XWeather napoved zabeležena.")
    except XWeatherError as e:
        print(f"⚠ XWeather: {e}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        # urllib napake ne vsebujejo URL-ja, zato ključ ne uide v dnevnik; izpišemo samo vrsto in kodo
        print(f"⚠ XWeather napoved nedosegljiva: {type(e).__name__} {getattr(e, 'code', '') or ''}", file=sys.stderr)

    save(rows)
    print(f"✓ data/forecast-forward-log.csv: {len(rows)} vrstic skupaj ({added} novih)")


if __name__ == "__main__":
    main()
