#!/usr/bin/env python3
"""
tools/verify_wrf.py — ali lasten WRF (0,5 km) kaj doda? Primerjava proti IREICA1 in proti Open-Meteo modelom.

Izvlečki dnevnih tekov (`data/wrf/recica-<YYYYMMDDHH>.json`, piše jih wrf/extract.py) se za vsak ciljni lokalni dan
primerjajo z meritvijo (`history.json`: tempHigh, tempLow, precipTotal) in z napovedmi drugih modelov, ki so bile
izdane isti dan kot tek (`data/forecast-archive.csv`, lead_days = 1). Rezultat je `data/wrf-verification.json`.

PRAVILA, ki jih ne obračaj:
- **IREICA1 je edina referenca.** Sosednja postaja Varpolje in DRSI tu ne smeta biti merilo.
- **Samo dnevi, ko imajo VSI viri napoved in meritev** — sicer bi se modeli merili na različnih dneh.
- Tek je ob 12 UTC dan prej, ciljni dan je lokalni dan po teku (`target_date()`); dan brez celotnega izhoda
  (`complete`) se ne šteje.
- Do `MIN_DAYS` dni je rezultat označen kot zgoden; stran (če kdaj nastane) ne sme trditi, da je WRF boljši, dokler
  ni vzorca. Negativen rezultat se objavi enako kot pozitiven.

Usage:
  python3 tools/verify_wrf.py [--out data/wrf-verification.json]
"""
import argparse
import csv
import datetime
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_GLOB = os.path.join(ROOT, "data", "wrf", "recica-*.json")
ARCHIVE = os.path.join(ROOT, "data", "forecast-archive.csv")
HISTORY = os.path.join(ROOT, "history.json")
OUT = os.path.join(ROOT, "data", "wrf-verification.json")
REFERENCE_MODELS = ["best_match", "ecmwf_ifs025", "icon_seamless", "gfs_seamless"]
WET_MM = 0.2  # isti prag mokrega dne kot WET_DAY_MM v verify_forecasts.py
MIN_DAYS = 30


def target_date(init):
    """Tek 12 UTC D−1 napoveduje lokalni dan D: pri UTC+1/+2 je to dan 18 ur po začetku."""
    t = datetime.datetime.strptime(init, "%Y%m%d%H") + datetime.timedelta(hours=18)
    return t.date().isoformat()


def load_runs(pattern=RUNS_GLOB):
    out = {}
    for path in sorted(glob.glob(pattern)):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        init = d.get("init") or os.path.basename(path)[len("recica-"):-len(".json")]
        day = target_date(init)
        daily = (d.get("daily") or {}).get(day)
        if daily and daily.get("complete"):
            out[day] = {"init": init, "tmax": daily["tmax_c"], "tmin": daily["tmin_c"], "precip": daily["precip_mm"]}
    return out


def load_archive(path=ARCHIVE, models=REFERENCE_MODELS):
    """{model: {valid_at: {tmax, tmin, precip}}} samo za lead_days = 1."""
    out = {m: {} for m in models}
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["model"] in out and r["lead_days"] == "1":
                    try:
                        out[r["model"]][r["valid_at"]] = {"tmax": float(r["tmax_c"]), "tmin": float(r["tmin_c"]),
                                                          "precip": float(r["precip_mm"])}
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def observed(history, day):
    h = history.get(day)
    if not h or h.get("tempHigh") is None or h.get("tempLow") is None or h.get("precipTotal") is None:
        return None
    return {"tmax": h["tempHigh"], "tmin": h["tempLow"], "precip": h["precipTotal"]}


def score(wrf, archive, history, models=REFERENCE_MODELS):
    """Primerjava na skupnih dnevih. Vrne slovar z n, MAE/bias po viru in številom zmag WRF proti vsakemu modelu."""
    sources = {"wrf": wrf, **{m: archive.get(m, {}) for m in models}}
    days = sorted(d for d in wrf
                  if observed(history, d) and all(d in sources[m] for m in models))
    res = {"n": len(days), "days": days, "sources": {}, "wrf_wins": {}}
    errs = {s: {"tmax": [], "tmin": [], "precip_hit": []} for s in sources}
    for d in days:
        o = observed(history, d)
        for s, data in sources.items():
            f = data[d]
            errs[s]["tmax"].append(f["tmax"] - o["tmax"])
            errs[s]["tmin"].append(f["tmin"] - o["tmin"])
            errs[s]["precip_hit"].append((f["precip"] >= WET_MM) == (o["precip"] >= WET_MM))
    for s, e in errs.items():
        n = len(e["tmax"])
        res["sources"][s] = {
            "mae_tmax": round(sum(abs(x) for x in e["tmax"]) / n, 2) if n else None,
            "mae_tmin": round(sum(abs(x) for x in e["tmin"]) / n, 2) if n else None,
            "bias_tmax": round(sum(e["tmax"]) / n, 2) if n else None,
            "bias_tmin": round(sum(e["tmin"]) / n, 2) if n else None,
            "wet_day_hit": round(sum(e["precip_hit"]) / n, 3) if n else None,
        }
    for m in models:
        for var in ("tmax", "tmin"):
            w = sum(1 for i in range(len(days)) if abs(errs["wrf"][var][i]) < abs(errs[m][var][i]))
            t = sum(1 for i in range(len(days)) if abs(errs["wrf"][var][i]) == abs(errs[m][var][i]))
            res["wrf_wins"][f"{m}:{var}"] = {"wins": w, "ties": t, "of": len(days)}
    res["early"] = len(days) < MIN_DAYS
    res["min_days"] = MIN_DAYS
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    with open(HISTORY, encoding="utf-8") as f:
        history = json.load(f)
    wrf = load_runs()
    res = score(wrf, load_archive(), history)
    res["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"  → {a.out}: {res['n']} skupnih dni" + (" (zgodno, premalo za sklep)" if res["early"] else ""))
    for s, v in res["sources"].items():
        print(f"    {s:>14}: MAE Tmax {v['mae_tmax']}  Tmin {v['mae_tmin']}  moker dan {v['wet_day_hit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
