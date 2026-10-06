#!/usr/bin/env python3
"""
Fetch the hourly archived-forecast caches the offline evals need (run on a GitHub Actions
runner: a sandbox with a shared IP gets 429s from Open-Meteo almost permanently).

  fetch_hourly_cache.py V1_OUT.json MODELS_OUT.json [--from 2024-05-26] [--to YYYY-MM-DD]

V1_OUT      {lead: rows}                 default Open-Meteo, D+1..D+3  (eval_mtr2_hourly.py)
MODELS_OUT  {"<model>|<lead>": rows}     IFS, GFS, ICON, ARPEGE, AIFS  (eval_mtr2_models.py)
Resumable: keys already present in the output files are skipped. Each call is retried with
a growing pause; a call that never succeeds is reported and skipped (the eval handles
missing models).
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import train_recica_mos as t   # noqa: E402

MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_arpege_europe", "ecmwf_aifs025_single"]


def patient(fn, tries=6, *a, **k):
    for i in range(tries):
        try:
            return fn(*a, **k)
        except Exception as e:       # noqa: BLE001 - network/API, anything transient
            wait = 30 * (i + 1)
            print(f"  poskus {i + 1}/{tries} neuspel ({str(e)[:80]}); čakam {wait} s", flush=True)
            time.sleep(wait)
    return None


def load(path):
    return json.load(open(path)) if os.path.exists(path) else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("v1_out")
    ap.add_argument("models_out")
    ap.add_argument("--from", dest="start", default="2024-05-26")
    ap.add_argument("--to", dest="end", default=None)
    a = ap.parse_args()
    import datetime as dt
    end = a.end or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    v1, mm = load(a.v1_out), load(a.models_out)
    for lead in (1, 2, 3):
        if str(lead) in v1:
            continue
        rows = patient(t.fetch_archived_forecasts, 6, lead, a.start, end)
        if rows is None:
            print(f"✗ default D+{lead} ni na voljo", file=sys.stderr)
            continue
        v1[str(lead)] = t._rows_to_cache(rows)
        json.dump(v1, open(a.v1_out, "w"))
        print(f"default D+{lead}: {len(rows)} dni", flush=True)
    for m in MODELS:
        for lead in (1, 2, 3):
            key = f"{m}|{lead}"
            if key in mm:
                continue
            rows = patient(t.fetch_archived_forecasts, 6, lead, a.start, end, model=m)
            if rows is None:
                print(f"✗ {key} ni na voljo", file=sys.stderr)
                continue
            mm[key] = t._rows_to_cache(rows)
            json.dump(mm, open(a.models_out, "w"))
            print(f"{key}: {len(rows)} dni", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
