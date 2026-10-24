#!/usr/bin/env python3
"""
tools/log_profile_forecasts.py — dnevni zajem PRAVIH napovedi višinskega profila in
dodatnih polj Open-Meteo za Rečico (D+1..D+3), od zdaj naprej.

Zakaj: Open-Meteo nima arhiva `*_previous_dayN` za višinske nivoje (T925/T850), oblačnost po
slojih, višino snega, vlago tal in mejno plast. Poskus 24. 10. 2026 (`tools/ai/eval_mtr4.py`,
docs/model-recica.md) je zato lahko uporabil samo zlepljene serije blizu analize, pri katerih
dobitka ni mogoče ločiti od uhajanja informacije. Pošten odgovor, ali npr. stabilnost
T925 − T2m izboljša Tmin, dobimo samo iz napovedi, kakršne so bile dan–tri dni prej — te se
nabirajo samo s tekočim beleženjem. Vsak dan zamujenega zajema je izgubljen za vedno.

Piše data/profile-forward-log.csv: ena vrstica na (issued_at, valid_at) z dnevnimi
vrednostmi (stolpci v COLUMNS). Agregacijo dela `daily_columns()` — ISTA funkcija, ki jo uporablja
tools/ai/eval_mtr4.py, da učenje in napoved nikoli ne dobita različnih vhodov (isto načelo kot
`daily_features` v train_recica_mos.py). Ure noči/dneva so uvožene iz train_recica_mos.

Samo zunanje vrednosti Open-Meteo; notranjih meritev ne bere (glej pravilo na vrhu CLAUDE.md).
Privzeti model (seamless), kakršnega MTR uči. Razlika do arhiva: izdaja je ob uri teka
workflowa (GitHubov cron zamuja ure), zato je lahko naslednji tek modela že vključen.
Ob nedosegljivem viru skript konča z 0 in ne spremeni ničesar.

Usage:
  python3 tools/log_profile_forecasts.py
"""
import csv, datetime, json, os, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_recica_mos as t  # noqa: E402  (NIGHT_HOURS, DAY_HOURS, LAT, LON)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "profile-forward-log.csv")
TZ = ZoneInfo("Europe/Ljubljana")
UA = {"User-Agent": "Meteorec-ProfileLog/1.0 https://meteorec.si"}
VARS = ["temperature_2m", "temperature_925hPa", "temperature_850hPa",
        "wind_speed_925hPa", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
        "snow_depth", "soil_moisture_0_to_7cm", "boundary_layer_height"]
LEADS = (1, 2, 3)
DAYS = max(LEADS) + 1          # danes + 3 dni
COLUMNS = ["inv_n", "lapse_d", "t850_d", "w925_n", "low_n", "low_d", "mid_d", "high_d",
           "snow_max", "soil_mean", "blh_max", "t2_max", "t2_min"]
FIELDS = ["issued_at", "valid_at", "lead_days"] + COLUMNS
RETRY_S = (5, 15)


def _mean(pairs, hours=None):
    xs = [v for h, v in pairs if hours is None or h in hours]
    return sum(xs) / len(xs) if xs else None


def _diff_mean(a, b, hours):
    """Povprečje (a − b) po urah, ki jih imata obe seriji."""
    bm = {h: v for h, v in b}
    xs = [v - bm[h] for h, v in a if h in hours and h in bm]
    return sum(xs) / len(xs) if xs else None


def daily_columns(series):
    """Urne serije enega dneva {spremenljivka: [(ura, vrednost), ...]} → {stolpec: vrednost | None}.
    Vrne None, kadar dan nima vsaj 20 ur temperature. Pomen stolpcev:
      inv_n    povprečje (T925 − T2m) v nočnih urah (00–08): pozitivno = inverzija
      lapse_d  povprečje (T850 − T2m) podnevi (10–18)
      t850_d   povprečje T850 podnevi; w925_n: povprečje vetra 925 hPa ponoči (km/h)
      low_n/low_d/mid_d/high_d  oblačnost po slojih (%), ponoči/podnevi
      snow_max najvišja višina snega v dnevu (m); soil_mean povprečna vlaga tal 0–7 cm
      blh_max  največja višina mejne plasti (m); t2_max/t2_min ekstrema T2m (°C)"""
    s = {k: [(int(h), x) for h, x in (series.get(k) or [])] for k in VARS}
    t2 = s["temperature_2m"]
    if len(t2) < 20:
        return None
    snow = s["snow_depth"]
    blh = s["boundary_layer_height"]
    return {
        "inv_n": _diff_mean(s["temperature_925hPa"], t2, t.NIGHT_HOURS),
        "lapse_d": _diff_mean(s["temperature_850hPa"], t2, t.DAY_HOURS),
        "t850_d": _mean(s["temperature_850hPa"], t.DAY_HOURS),
        "w925_n": _mean(s["wind_speed_925hPa"], t.NIGHT_HOURS),
        "low_n": _mean(s["cloud_cover_low"], t.NIGHT_HOURS),
        "low_d": _mean(s["cloud_cover_low"], t.DAY_HOURS),
        "mid_d": _mean(s["cloud_cover_mid"], t.DAY_HOURS),
        "high_d": _mean(s["cloud_cover_high"], t.DAY_HOURS),
        "snow_max": max((v for _, v in snow), default=None),
        "soil_mean": _mean(s["soil_moisture_0_to_7cm"]),
        "blh_max": max((v for _, v in blh), default=None),
        "t2_max": max(v for _, v in t2),
        "t2_min": min(v for _, v in t2),
    }


def fetch():
    q = urllib.parse.urlencode({
        "latitude": t.LAT, "longitude": t.LON, "hourly": ",".join(VARS),
        "forecast_days": DAYS, "timezone": "Europe/Ljubljana"})
    last = None
    for wait in (0,) + RETRY_S:
        time.sleep(wait)
        try:
            req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + q, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:                     # noqa: BLE001 - omrežje/API, prehodno
            last = e
    raise RuntimeError(last)


def summarize(data, issued):
    """{valid_at: vrstica} za vodilne čase LEADS iz urnega odgovora Open-Meteo."""
    h = data.get("hourly") or {}
    times = h.get("time") or []
    days = {}
    for i, ts in enumerate(times):
        rec = days.setdefault(ts[:10], {k: [] for k in VARS})
        for k in VARS:
            vals = h.get(k) or []
            if i < len(vals) and vals[i] is not None:
                rec[k].append((int(ts[11:13]), vals[i]))
    out = {}
    for day, rec in days.items():
        lead = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(issued)).days
        if lead not in LEADS:
            continue
        cols = daily_columns(rec)
        if cols is None:
            continue
        row = {"issued_at": issued, "valid_at": day, "lead_days": lead}
        row.update({k: ("" if v is None else round(v, 3)) for k, v in cols.items()})
        out[day] = row
    return out


def main():
    issued = datetime.datetime.now(TZ).date().isoformat()
    rows, seen = [], set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                seen.add((r["issued_at"], r["valid_at"]))
    try:
        data = fetch()
    except Exception as e:                         # omrežje/API: dnevnik ostane nedotaknjen
        print(f"⚠ napoved profila ni dosegljiva ({e}) — preskočeno.", file=sys.stderr)
        return 0
    new = [r for d, r in sorted(summarize(data, issued).items()) if (issued, d) not in seen]
    if not new:
        print("Ni novih vrstic.")
        return 0
    rows += new
    rows.sort(key=lambda r: (r["issued_at"], r["valid_at"]))
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"✓ {len(new)} novih vrstic ({issued}), skupaj {len(rows)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
