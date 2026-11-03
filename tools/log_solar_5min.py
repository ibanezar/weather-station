#!/usr/bin/env python3
"""
tools/log_solar_5min.py — 5-minutni zapis sončnega sevanja in temperature IREICA1 ob sončnem vzhodu in zahodu.

Zakaj: ali model obzorja (`tools/sonce_horizont.py`, `/sonce-v-dolini/`) res napove čas prvega žarka, se da preveriti
samo s hitrim skokom sevanja, ko sonce pogleda izza grebena. Urni zapis (`data/hourly-observations.csv`) je za to
pregrob. Ecowitt hrani polno 5-minutno ločljivost samo ~90 dni (isto kot `log_hourly_observations.py`), zato se zapisuje
sproti, dan za dnem.

Shranimo samo okna, ki jih preverjanje potrebuje: od 30 min pred koledarskim vzhodom do 4,5 h po njem in od 4,5 h pred
koledarskim zahodom do 30 min po njem (po lokalnem času). Zunanja polja; notranjih blokov ne bere (glej pravilo na
vrhu CLAUDE.md).

Piše data/solar-5min.csv (date, time_local, solar_wm2, temp_c). Drži zadnjih HOLD_DAYS dni.

Usage:
  python3 tools/log_solar_5min.py                  # včeraj
  python3 tools/log_solar_5min.py --backfill 85    # enkratno: do 85 dni nazaj
"""
import csv
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_history as uh  # noqa: E402  (fetch_ecowitt, _ew_list, _pick, TZ)
import generate_seo_pages as seo  # noqa: E402  (LAT, LON — postaja)
import sonce_horizont as sh  # noqa: E402

ROOT = uh.ROOT
LOG_PATH = os.path.join(ROOT, "data", "solar-5min.csv")
FIELDS = ["date", "time_local", "solar_wm2", "temp_c"]
SOLAR_MAX_WM2 = 1500
HOLD_DAYS = 120
BEFORE_RISE_MIN, AFTER_RISE_MIN = 30, 270   # okno zjutraj glede na koledarski vzhod
BEFORE_SET_MIN, AFTER_SET_MIN = 270, 30     # okno zvečer glede na koledarski zahod


def windows_for(day):
    """Dve okni (minute od lokalne polnoči) za dan; None, če sonca ni."""
    p = sh.day_profile(seo.LAT, seo.LON, None, datetime.date.fromisoformat(day))
    if p["flat_rise"] is None:
        return []
    return [(p["flat_rise"] - BEFORE_RISE_MIN, p["flat_rise"] + AFTER_RISE_MIN),
            (p["flat_set"] - BEFORE_SET_MIN, p["flat_set"] + AFTER_SET_MIN)]


def rows_from_ecowitt(data, day):
    """Surov Ecowitt 'data' objekt (en dan) → vrstice za okni; na 5 minut zaokrožen čas (zadnja vrednost v koraku)."""
    solar, temp = {}, {}
    for ts, v in (uh._ew_list(data, "solar_and_uvi", "solar") or {}).items():
        val = uh._pick(v, ["avg", "value", "max"])
        if val is not None and 0 <= val <= SOLAR_MAX_WM2:
            solar[int(ts)] = val
    for ts, v in (uh._ew_list(data, "outdoor", "temperature") or {}).items():
        val = uh._pick(v, ["avg", "value", "max"])
        if val is not None:
            temp[int(ts)] = val
    wins = windows_for(day)
    out = {}
    for ts in sorted(set(solar) | set(temp)):
        dt = uh.datetime.fromtimestamp(ts, uh.TZ)
        if dt.date().isoformat() != day:
            continue
        minute = dt.hour * 60 + dt.minute
        if not any(a <= minute < b for a, b in wins):
            continue
        key = f"{dt.hour:02d}:{(dt.minute // 5) * 5:02d}"
        out[key] = {"date": day, "time_local": key,
                    "solar_wm2": solar.get(ts, out.get(key, {}).get("solar_wm2", "")),
                    "temp_c": temp.get(ts, out.get(key, {}).get("temp_c", ""))}
    return list(out.values())


def load_existing():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    rows.sort(key=lambda r: (r["date"], r["time_local"]))
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    backfill = 0
    if "--backfill" in sys.argv:
        backfill = min(int(sys.argv[sys.argv.index("--backfill") + 1]), 85)
    today = datetime.datetime.now(uh.TZ).date()
    days = ([(today - datetime.timedelta(days=d)).isoformat() for d in range(backfill, 0, -1)]
            if backfill else [(today - datetime.timedelta(days=1)).isoformat()])
    rows = load_existing()
    have_days = {r["date"] for r in rows}
    for day in days:
        if day in have_days:
            print(f"{day} je že zabeležen, preskačem.")
            continue
        if backfill:
            time.sleep(1.5)
        data = uh.fetch_ecowitt(day, day)
        if not data:
            print(f"⚠ Ecowitt ni vrnil podatkov za {day}.", file=sys.stderr)
            continue
        new = rows_from_ecowitt(data, day)
        rows.extend(new)
        print(f"✓ {day}: {len(new)} točk")
    cutoff = (today - datetime.timedelta(days=HOLD_DAYS)).isoformat()
    rows = [r for r in rows if r["date"] >= cutoff]
    save(rows)
    print(f"✓ data/solar-5min.csv: {len(rows)} vrstic")


if __name__ == "__main__":
    main()
