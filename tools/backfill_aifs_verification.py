#!/usr/bin/env python3
"""
tools/backfill_aifs_verification.py — dopolni semafor točnosti z AIFS za nazaj.

ARSO in Open-Meteo na semaforju nimata zgodovine: ARSO arhiva napovedi ne
objavlja, Open-Meteo pa smo tu začeli beležiti šele sproti. AIFS je izjema —
Open-Meteo hrani arhiv preteklih napovedi (*_previous_dayN), zato se AIFS lahko
oceni tudi za dneve pred današnjim dnem, po povsem enakem pravilu.

Zakaj urne spremenljivke in ne dnevne: arhivski API dnevnih različic
(temperature_2m_max_previous_day1) nima. Tmax/Tmin/vsoto padavin zato seštejemo
sami iz urnih vrednosti — isto pravilo, kot ga uporablja train_recica_mos.py.
Zaradi tega se lahko vrednost od žive dnevne agregacije razlikuje za kakšno
desetinko; zapis zato nosi src "archive" in stran to pove.

Skript je namenjen enkratnemu zagonu (ali ponovitvi po vrzeli) — dnevni tek
opravi tools/verify_forecasts.py sam. Napovedi drugih virov ne dotakne.

Uporaba:
  python3 tools/backfill_aifs_verification.py            # vsi manjkajoči dnevi
  python3 tools/backfill_aifs_verification.py --force    # tudi že izpolnjene
  python3 tools/backfill_aifs_verification.py --dry-run
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verify_forecasts as vf  # noqa: E402

ARCHIVE_API = "https://historical-forecast-api.open-meteo.com/v1/forecast"
HOURLY_VARS = ["temperature_2m", "precipitation"]

# Prej AIFS pri Open-Meteo ne obstaja — ECMWF ga je dal v operativno rabo
# 25. 2. 2025, arhiv Open-Meteo se začne 20. 2. 2025.
AIFS_ARCHIVE_START = "2025-02-20"


def _get_json(url, timeout=120, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=vf.UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, OSError) as e:
            last = e
            print(f"    ponovni poskus ({i + 1}/{tries}): {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"zajem ni uspel: {last}")


def fetch_aifs_archive(start, end):
    """{datum: {"tmax", "tmin", "precip"}} iz arhiva AIFS napovedi izpred enega
    dne — torej natanko to, kar bi AIFS povedal dan prej."""
    hourly = ",".join(f"{v}_previous_day1" for v in HOURLY_VARS)
    q = urllib.parse.urlencode({
        "latitude": vf.LAT, "longitude": vf.LON,
        "start_date": start, "end_date": end,
        "hourly": hourly, "timezone": "Europe/Ljubljana",
        "models": vf.AIFS_MODEL,
    })
    data = _get_json(f"{ARCHIVE_API}?{q}")
    h = data.get("hourly") or {}
    times = h.get("time") or []
    temps = h.get("temperature_2m_previous_day1") or []
    precs = h.get("precipitation_previous_day1") or []

    buckets = {}
    for i, ts in enumerate(times):
        day = ts[:10]
        b = buckets.setdefault(day, {"t": [], "p": []})
        t = temps[i] if i < len(temps) else None
        p = precs[i] if i < len(precs) else None
        if t is not None:
            b["t"].append(t)
        if p is not None:
            b["p"].append(p)

    out = {}
    for day, b in buckets.items():
        # Nepopoln dan bi dal napačen Tmax/Tmin — raje ga izpustimo.
        if len(b["t"]) < 20:
            continue
        out[day] = {
            "tmax": round(max(b["t"]), 1),
            "tmin": round(min(b["t"]), 1),
            "precip": round(sum(b["p"]), 1) if b["p"] else None,
            "model": vf.AIFS_MODEL,
            "src": "archive",
        }
    return out


def main():
    ap = argparse.ArgumentParser(description="Dopolni semafor točnosti z AIFS za nazaj.")
    ap.add_argument("--force", action="store_true", help="prepiši tudi že izpolnjene dneve")
    ap.add_argument("--dry-run", action="store_true", help="samo izpiši, ne piši datoteke")
    args = ap.parse_args()

    verification = vf.load_json(vf.VERIFICATION_PATH, {})
    if not verification:
        print("forecast_verification.json je prazen — ni česa dopolniti.", file=sys.stderr)
        return 1

    hist = vf.seo.load_history()
    dates = sorted(verification)
    start = max(dates[0], AIFS_ARCHIVE_START)
    end = dates[-1]
    if start > end:
        print(f"Semafor se konča pred začetkom arhiva AIFS ({AIFS_ARCHIVE_START}) — nič za dopolniti.")
        return 0

    todo = [d for d in dates if d >= start and (args.force or not verification[d].get("aifs"))]
    if not todo:
        print("Vsi dnevi imajo AIFS že zabeležen.")
        return 0

    print(f"Zajemam arhiv AIFS napovedi {start} → {end} ({len(todo)} dni za dopolniti) …")
    archive = fetch_aifs_archive(start, end)
    print(f"  iz arhiva prišlo {len(archive)} dni")

    filled, missing = 0, []
    for day in todo:
        aifs = archive.get(day)
        if not aifs:
            missing.append(day)
            continue
        actual = hist.get(day)
        if actual is None:
            missing.append(day)
            continue
        record = verification[day]
        verification[day] = vf.build_record(
            day, record.get("made_at"), actual,
            record.get("arso"), record.get("open_meteo"), record.get("meteorec"),
            aifs,
        )
        filled += 1

    print(f"  dopolnjenih dni: {filled}")
    if missing:
        print(f"  brez arhivske napovedi: {len(missing)} ({', '.join(missing[:5])}"
              f"{' …' if len(missing) > 5 else ''})")

    if args.dry_run:
        print("(--dry-run: datoteka ni zapisana)")
        return 0

    vf.save_json(vf.VERIFICATION_PATH, verification)
    print(f"→ forecast_verification.json: {len(verification)} dni, "
          f"{sum(1 for r in verification.values() if r.get('aifs'))} z AIFS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
