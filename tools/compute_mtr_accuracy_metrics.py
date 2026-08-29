#!/usr/bin/env python3
"""
tools/compute_mtr_accuracy_metrics.py — rolling MAE MTR proti Open-Meteo za /trendi/.

Bere data/mtr-accuracy-log.csv (piše ga tools/log_mtr_accuracy.py, en zapis na
dan/vodilni čas: napoved + dejanska vrednost) in izračuna:
  - all-time MAE (MTR, Open-Meteo) in % izboljšave, po (vodilni čas, Tmax/Tmin)
  - rolling 30-dnevno MAE skozi čas, kot časovna vrsta za graf
  - razčlenitev po meteorološki sezoni (zima/pomlad/poletje/jesen), samo za
    sezone z dovolj zapisi (MIN_SEASON_N) — z malo podatki bi bila razčlenitev
    šum, ne signal

Piše data/mtr-accuracy.json, ki ga bere tako /trendi/ (graf) kot MTR kartica na
domači strani (app.js, all-time % izboljšave pri D+1) — ena resnica za oboje.

Uporaba:
  python3 tools/compute_mtr_accuracy_metrics.py
"""
import csv
import datetime as dt
import json
import os
import statistics as st
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "mtr-accuracy-log.csv")
OUT_PATH = os.path.join(ROOT, "data", "mtr-accuracy.json")

ROLLING_WINDOW_DAYS = 30
MIN_ROLLING_N = 5      # premalo za smiseln MAE na dani dan v seriji
MIN_SEASON_N = 10      # premalo za smiselno razčlenitev po sezoni
VARS = ("tmax", "tmin")
LEADS = (1, 2)

SEASON_MONTHS = {
    "zima": (12, 1, 2),
    "pomlad": (3, 4, 5),
    "poletje": (6, 7, 8),
    "jesen": (9, 10, 11),
}


def load_rows():
    if not os.path.exists(LOG_PATH):
        return []
    rows = []
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                r["lead"] = int(r["lead"])
            except (TypeError, ValueError):
                continue
            for k in ("err_mtr_tmax", "err_mtr_tmin", "err_om_tmax", "err_om_tmin"):
                v = r.get(k)
                r[k] = float(v) if v not in (None, "") else None
            rows.append(r)
    return sorted(rows, key=lambda r: (r["date"], r["lead"]))


def mae_pair(rows, err_key_mtr, err_key_om):
    """MAE za MTR in Open-Meteo nad istim naborom vrstic + % izboljšave.
    Primerjava je pošteno seznanjena: dan šteje samo, če imata oba vira napako
    za ta dan (drugače bi manjkajoči dnevi enega vira izkrivili primerjavo)."""
    mtr_errs, om_errs = [], []
    for r in rows:
        m, o = r.get(err_key_mtr), r.get(err_key_om)
        if m is None or o is None:
            continue
        mtr_errs.append(m)
        om_errs.append(o)
    if not mtr_errs:
        return {"n": 0, "mae_mtr": None, "mae_om": None, "improvement_pct": None}
    mae_mtr = round(st.mean(mtr_errs), 2)
    mae_om = round(st.mean(om_errs), 2)
    improvement = round(100 * (mae_om - mae_mtr) / mae_om, 1) if mae_om else None
    return {"n": len(mtr_errs), "mae_mtr": mae_mtr, "mae_om": mae_om, "improvement_pct": improvement}


def season_of(date_str):
    m = dt.date.fromisoformat(date_str).month
    for name, months in SEASON_MONTHS.items():
        if m in months:
            return name
    return None


def rolling_series(rows_by_lead_var):
    """Za vsak (lead, var): za vsak dan, ko je bil zapis razrešen, MAE preko
    zadnjih ROLLING_WINDOW_DAYS dni do vključno tega dne (drseče okno po
    koledarskih, ne zaporednih zapisih — vrzel v postajni zgodovini okna ne
    podaljša)."""
    out = {}
    for (lead, var), rows in rows_by_lead_var.items():
        err_mtr_key = f"err_mtr_{var}"
        err_om_key = f"err_om_{var}"
        dated = [(dt.date.fromisoformat(r["date"]), r) for r in rows
                 if r.get(err_mtr_key) is not None and r.get(err_om_key) is not None]
        dated.sort(key=lambda t: t[0])
        series = []
        for i, (d, _) in enumerate(dated):
            window_start = d - dt.timedelta(days=ROLLING_WINDOW_DAYS - 1)
            window = [r for (dd, r) in dated if window_start <= dd <= d]
            if len(window) < MIN_ROLLING_N:
                continue
            stats = mae_pair(window, err_mtr_key, err_om_key)
            series.append({"date": d.isoformat(), **stats})
        out.setdefault(lead, {})[var] = series
    return out


def main():
    rows = load_rows()
    if not rows:
        print("Ni zapisov v data/mtr-accuracy-log.csv — nič za izračunati "
              "(tools/log_mtr_accuracy.py še ni zabeležil nobenega razrešenega dne).")
        payload = {
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_records": 0, "rolling_window_days": ROLLING_WINDOW_DAYS,
            "leads": {}, "seasons": {},
        }
        os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return 0

    rows_by_lead_var = defaultdict(list)
    for r in rows:
        if r["lead"] not in LEADS:
            continue
        for var in VARS:
            rows_by_lead_var[(r["lead"], var)].append(r)

    leads_out = {}
    for lead in LEADS:
        lead_rows = [r for r in rows if r["lead"] == lead]
        if not lead_rows:
            continue
        all_time = {var: mae_pair(lead_rows, f"err_mtr_{var}", f"err_om_{var}") for var in VARS}
        leads_out[str(lead)] = {
            "n": len(lead_rows),
            "date_range": {"from": lead_rows[0]["date"], "to": lead_rows[-1]["date"]},
            "all_time": all_time,
            "rolling": {},
        }

    rolling = rolling_series(rows_by_lead_var)
    for lead, by_var in rolling.items():
        if str(lead) in leads_out:
            leads_out[str(lead)]["rolling"] = by_var

    # ── Razčlenitev po sezoni ────────────────────────────────────────────────
    seasons_out = {}
    for season in SEASON_MONTHS:
        season_rows = [r for r in rows if season_of(r["date"]) == season]
        if len(season_rows) < MIN_SEASON_N:
            continue
        by_lead = {}
        for lead in LEADS:
            lr = [r for r in season_rows if r["lead"] == lead]
            if not lr:
                continue
            by_lead[str(lead)] = {"n": len(lr),
                                   **{var: mae_pair(lr, f"err_mtr_{var}", f"err_om_{var}") for var in VARS}}
        if by_lead:
            seasons_out[season] = by_lead

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_records": len(rows),
        "date_range": {"from": rows[0]["date"], "to": rows[-1]["date"]},
        "rolling_window_days": ROLLING_WINDOW_DAYS,
        "leads": leads_out,
        "seasons": seasons_out,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    for lead in LEADS:
        entry = leads_out.get(str(lead))
        if not entry:
            continue
        tx, tn = entry["all_time"]["tmax"], entry["all_time"]["tmin"]
        print(f"D+{lead}: Tmax MAE MTR {tx['mae_mtr']} / OM {tx['mae_om']} "
              f"({tx['improvement_pct']}% ), Tmin MAE MTR {tn['mae_mtr']} / OM {tn['mae_om']} "
              f"({tn['improvement_pct']}% ), n={entry['n']}")
    print(f"→ {os.path.relpath(OUT_PATH, ROOT)} zapisan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
