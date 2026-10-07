#!/usr/bin/env python3
"""
tools/backfill_aifs_verification.py — dopolni semafor točnosti z AI modeloma
(ECMWF AIFS in Google DeepMind WeatherNext 2) za nazaj.

ARSO in Open-Meteo na semaforju nimata zgodovine: ARSO arhiva napovedi ne
objavlja, Open-Meteo pa smo tu začeli beležiti šele sproti. AI modela sta
izjema — Open-Meteo hrani arhiv preteklih napovedi (*_previous_dayN), zato se
lahko ocenita tudi za dneve pred današnjim dnem, po povsem enakem pravilu.

Vira imata različen arhiv: AIFS je na arhivskem API-ju od 20. 2. 2025,
WeatherNext 2 pa na ensemble API-ju šele od 4. 9. 2026 (prej so vrednosti
*_previous_day1 prazne). Ime skripta je ostalo, ker ga kliče workflow.

Zakaj urne spremenljivke in ne dnevne: arhivski API dnevnih različic
(temperature_2m_max_previous_day1) nima. Tmax/Tmin/vsoto padavin zato seštejemo
sami iz urnih vrednosti — isto pravilo, kot ga uporablja train_recica_mos.py.
Zaradi tega se lahko vrednost od žive dnevne agregacije razlikuje za kakšno
desetinko; zapis zato nosi src "archive" in stran to pove.

Skript je namenjen enkratnemu zagonu (ali ponovitvi po vrzeli) — dnevni tek
opravi tools/verify_forecasts.py sam. Napovedi drugih virov ne dotakne.

Uporaba:
  python3 tools/backfill_aifs_verification.py              # vsi manjkajoči dnevi, oba vira
  python3 tools/backfill_aifs_verification.py --source wn2 # samo WeatherNext 2
  python3 tools/backfill_aifs_verification.py --force      # tudi že izpolnjene
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

# Prvi CEL dan, ko ima WeatherNext 2 pri Open-Meteo vrednosti *_previous_day1
# (prve so 4. 9. ob 2:00, preverjeno 7. 10. 2026). Ensemble API sprejme tudi starejše datume (od
# 6. 7. 2026), a so tam samo zlepljeni najsvežejši teki — to ni napoved dan
# prej in bi model na semaforju nezasluženo pohvalilo.
WN2_ARCHIVE_START = "2026-09-05"

# ključ v zapisu → (model, API, začetek arhiva, oznaka)
SOURCES = {
    "aifs": (vf.AIFS_MODEL, ARCHIVE_API, AIFS_ARCHIVE_START, "ECMWF AIFS"),
    "wn2": (vf.WN2_MODEL, vf.ENSEMBLE_API, WN2_ARCHIVE_START, "WeatherNext 2"),
}


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


def fetch_archive(start, end, model, api):
    """{datum: {"tmax", "tmin", "precip"}} iz arhiva napovedi izpred enega dne —
    torej natanko to, kar bi model povedal dan prej."""
    hourly = ",".join(f"{v}_previous_day1" for v in HOURLY_VARS)
    q = urllib.parse.urlencode({
        "latitude": vf.LAT, "longitude": vf.LON,
        "start_date": start, "end_date": end,
        "hourly": hourly, "timezone": "Europe/Ljubljana",
        "models": model,
    })
    data = _get_json(f"{api}?{q}")
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
            "model": model,
            "src": "archive",
        }
    return out


def main():
    ap = argparse.ArgumentParser(description="Dopolni semafor točnosti z AI modeloma za nazaj.")
    ap.add_argument("--force", action="store_true", help="prepiši tudi že izpolnjene dneve")
    ap.add_argument("--dry-run", action="store_true", help="samo izpiši, ne piši datoteke")
    ap.add_argument("--source", choices=sorted(SOURCES), action="append",
                    help="samo ta vir (privzeto vsi)")
    args = ap.parse_args()

    verification = vf.load_json(vf.VERIFICATION_PATH, {})
    if not verification:
        print("forecast_verification.json je prazen — ni česa dopolniti.", file=sys.stderr)
        return 1

    hist = vf.seo.load_history()
    dates = sorted(verification)
    failed = False
    for key in (args.source or list(SOURCES)):
        model, api, archive_start, label = SOURCES[key]
        start = max(dates[0], archive_start)
        end = dates[-1]
        if start > end:
            print(f"{label}: semafor se konča pred začetkom arhiva ({archive_start}) — nič za dopolniti.")
            continue

        todo = [d for d in dates if d >= start and (args.force or not verification[d].get(key))]
        if not todo:
            print(f"{label}: vsi dnevi so že zabeleženi.")
            continue

        print(f"{label}: zajemam arhiv napovedi {start} → {end} ({len(todo)} dni za dopolniti) …")
        try:
            archive = fetch_archive(start, end, model, api)
        except RuntimeError as e:
            # En vir ne sme podreti drugega — workflow teče naprej z || true.
            print(f"  ✗ {e}", file=sys.stderr)
            failed = True
            continue
        print(f"  iz arhiva prišlo {len(archive)} dni")

        filled, missing = 0, []
        for day in todo:
            entry = archive.get(day)
            actual = hist.get(day)
            if not entry or actual is None:
                missing.append(day)
                continue
            record = dict(verification[day])
            record[key] = entry
            verification[day] = vf.build_record(
                day, record.get("made_at"), actual,
                record.get("arso"), record.get("open_meteo"), record.get("meteorec"),
                record.get("aifs"), record.get("wn2"),
            )
            filled += 1

        print(f"  dopolnjenih dni: {filled}")
        if missing:
            print(f"  brez arhivske napovedi: {len(missing)} ({', '.join(missing[:5])}"
                  f"{' …' if len(missing) > 5 else ''})")

    if args.dry_run:
        print("(--dry-run: datoteka ni zapisana)")
        return 1 if failed else 0

    vf.save_json(vf.VERIFICATION_PATH, verification)
    print(f"→ forecast_verification.json: {len(verification)} dni, "
          + ", ".join(f"{sum(1 for r in verification.values() if r.get(k))} z {SOURCES[k][3]}"
                      for k in SOURCES))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
