#!/usr/bin/env python3
"""
tools/build_forecast_archive.py — backfill + daily update of the /test-napovedi/
forecast archive (Faza 1a v brief-u).

Vir: Open-Meteo Previous Runs API (previous-runs-api.open-meteo.com), edini
vir, ki vrne napoved po vodilnem času (lead_days) — spremenljivke
`<ime>_previous_dayN` povedo, kar je model N dni pred `valid_at` napovedal za
ta dan. Zajema urne vrednosti in jih agregira v dnevne (Tmax/Tmin/vsota
padavin) **po lokalnem času (Europe/Ljubljana)** — ista pravila kot za
meritve v update_history.py, sicer se definicija dneva razide (glavni vir
lažnih rezultatov pri tovrstni analizi).

Piše/dopolnjuje data/forecast-archive.csv (dodaja samo nove (model, lead,
valid_at) vrstice — arhiv se ne prepisuje, kliče se poredko).

Usage:
  python3 tools/build_forecast_archive.py [--models m1,m2,...] [--past-days N]
"""
import csv, datetime, json, os, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAT, LON = 46.325779, 14.921137
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-ForecastTest/1.0; +https://meteorec.si)"}
ARCHIVE_PATH = os.path.join(ROOT, "data", "forecast-archive.csv")

# Faza 1a v brief-u — pet virov za primerjavo. Open-Meteo Previous Runs API
# arhivira previous_dayN spremenljivke enotno od 2024-06-15 za vse tu
# preverjene modele (potrjeno z živim klicem, glej commit sporočilo/PR opis).
MODELS = {
    "ecmwf_ifs025":             "ECMWF IFS",
    "icon_seamless":            "ICON",
    "gfs_seamless":             "GFS",
    "meteofrance_arpege_europe": "ARPEGE",
    "best_match":                "Best Match",
}

LEADS = range(1, 8)
ARCHIVE_START = datetime.date(2024, 6, 15)  # potrjena meja previous-runs arhiva za te modele

FIELDS = ["model", "lead_days", "valid_at", "issued_at", "tmax_c", "tmin_c", "precip_mm"]


def fetch_model(model, past_days):
    hourly_vars = (
        [f"temperature_2m_previous_day{n}" for n in LEADS]
        + [f"precipitation_previous_day{n}" for n in LEADS]
    )
    q = {
        "latitude": LAT, "longitude": LON,
        "timezone": "Europe/Ljubljana",
        "models": model,
        "past_days": past_days,
        "forecast_days": 1,
        "hourly": ",".join(hourly_vars),
    }
    url = "https://previous-runs-api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def aggregate_daily(data, model):
    """Urne previous_dayN vrednosti -> dnevni Tmax/Tmin/vsota padavin, po lokalnem
    koledarskem dnevu. Dan se obdrži samo, če ima vseh 24 ur (popoln dan) —
    enako pravilo kot za meritve, sicer bi robni dnevi (prvi/zadnji v razponu)
    dali lažno nizek Tmax/visok Tmin."""
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    rows_by_lead = {n: {} for n in LEADS}

    for n in LEADS:
        temps = hourly.get(f"temperature_2m_previous_day{n}") or []
        precs = hourly.get(f"precipitation_previous_day{n}") or []
        by_day = {}
        for t, tv, pv in zip(times, temps, precs):
            d = t[:10]
            b = by_day.setdefault(d, {"t": [], "p": [], "hours": set()})
            if tv is not None:
                b["t"].append(tv)
            if pv is not None:
                b["p"].append(pv)
            b["hours"].add(t[11:13])
        for d, b in by_day.items():
            if len(b["hours"]) < 24 or not b["t"]:
                continue
            valid = datetime.date.fromisoformat(d)
            issued = valid - datetime.timedelta(days=n)
            rows_by_lead[n][d] = {
                "model": model, "lead_days": n, "valid_at": d,
                "issued_at": issued.isoformat(),
                "tmax_c": round(max(b["t"]), 1),
                "tmin_c": round(min(b["t"]), 1),
                "precip_mm": round(sum(b["p"]), 1) if b["p"] else None,
            }
    out = []
    for n in LEADS:
        out.extend(rows_by_lead[n].values())
    return out


def load_existing():
    seen = set()
    rows = []
    if os.path.exists(ARCHIVE_PATH):
        with open(ARCHIVE_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                seen.add((row["model"], row["lead_days"], row["valid_at"]))
    return rows, seen


def save_archive(rows):
    rows.sort(key=lambda r: (r["model"], int(r["lead_days"]), r["valid_at"]))
    os.makedirs(os.path.dirname(ARCHIVE_PATH), exist_ok=True)
    with open(ARCHIVE_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    models = list(MODELS)
    past_days = 820
    args = sys.argv[1:]
    if "--models" in args:
        models = args[args.index("--models") + 1].split(",")
    if "--past-days" in args:
        past_days = int(args[args.index("--past-days") + 1])

    existing_rows, seen = load_existing()
    new_rows = []

    for model in models:
        print(f"[{model}] nalagam previous-runs arhiv (past_days={past_days}) ...")
        try:
            data = fetch_model(model, past_days)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            print(f"  ⚠ {model} nedosegljiv: {e}", file=sys.stderr)
            continue
        if "error" in data:
            print(f"  ⚠ {model}: {data.get('reason')}", file=sys.stderr)
            continue
        agg = aggregate_daily(data, model)
        added = 0
        for r in agg:
            key = (r["model"], str(r["lead_days"]), r["valid_at"])
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(r)
            added += 1
        print(f"  → {len(agg)} dnevnih zapisov agregiranih, {added} novih")

    all_rows = existing_rows + [
        {k: str(v) if v is not None else "" for k, v in r.items()} for r in new_rows
    ]
    save_archive(all_rows)
    print(f"✓ data/forecast-archive.csv: {len(all_rows)} vrstic skupaj "
          f"({len(new_rows)} novih v tem teku)")


if __name__ == "__main__":
    main()
