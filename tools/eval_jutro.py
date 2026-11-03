#!/usr/bin/env python3
"""
tools/eval_jutro.py — kdaj se dolina ogreje po prvem žarku (/jutro-v-dolini/). Statistika zamika in preverjanje napovedi.

Ideja: na dnu doline se jasno, mirno jutro ogreje šele, ko sonce pride do tal. Čas prvega žarka je izračunan iz terena
(`tools/sonce_horizont.py`), zamik od prvega žarka do dviga temperature za `RISE_C` (3 °C) nad jutranjim minimumom pa je
IZMERJEN na postaji IREICA1 (`data/hourly-observations.csv`) na jasnih, mirnih jutrih.

Definicije (zapisane tudi na strani):
- Jutranji minimum: najnižje urno povprečje med 0.00 in 10.00 (lokalno).
- Čas dviga: prvi trenutek po minimumu, ko urno povprečje preseže minimum + 3 °C; med središčema zaporednih ur linearno
  interpolirano (oznaka ure je začetek ure, povprečje velja za njeno sredino).
- Jasno in mirno jutro (za statistiko, izmerjeno): dnevni razpon temperature ≥ 10 °C in povprečni veter 0.00–7.00
  < 3 km/h. Za napoved se isti pogoj nadomesti z modelskim (oblačnost 3–11 h < 30 %, veter 0–8 h < 6 km/h; model
  precenjuje veter na tej postaji ~2×, zato prag 6).
- Zamik za mesec m se zbere iz sosednjih mesecev (m−1, m, m+1), šele ko je jasnih jutr vsaj `MIN_N`. Meseci brez
  zadostnih meritev napovedi NE dobijo: pozimi je zamik verjetno daljši in ga ne smemo izposoditi iz poletja.

Napovedi se beležijo v `data/jutro-napovedi.csv` (generator strani), ta skript pa jih primerja z izmerjenim dnem.
Rezultat: data/jutro-zamik.json.

Usage:
  python3 tools/eval_jutro.py
"""
import csv
import datetime
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sonce_horizont as sh  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS_PATH = os.path.join(ROOT, "data", "hourly-observations.csv")
PRED_PATH = os.path.join(ROOT, "data", "jutro-napovedi.csv")
OUT_PATH = os.path.join(ROOT, "data", "jutro-zamik.json")
RISE_C = 3.0
MIN_RANGE_C = 10.0
MAX_WIND_KMH = 3.0
MIN_N = 8
MIN_HOURS = 22  # dan z manj urami se ne šteje


def load_obs(path=OBS_PATH):
    """{datum: {ura: (temp, veter)}}"""
    days = {}
    if not os.path.exists(path):
        return days
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not r.get("temp_c"):
                continue
            d, t = r["valid_at_local"].split("T")
            w = float(r["wind_kmh"]) if r.get("wind_kmh") not in (None, "") else None
            days.setdefault(d, {})[int(t[:2])] = (float(r["temp_c"]), w)
    return days


def morning_metrics(hours):
    """Iz urnih povprečij enega dne: (tmin, ura_minimuma, čas_dviga_v_minutah|None, razpon, povp_veter_0_7|None)."""
    temps = {h: v[0] for h, v in hours.items()}
    if len(temps) < MIN_HOURS:
        return None
    hm = [h for h in range(0, 10) if h in temps]
    if not hm:
        return None
    mh = min(hm, key=lambda h: temps[h])
    tmin = temps[mh]
    rng = max(temps.values()) - min(temps.values())
    winds = [hours[h][1] for h in range(0, 8) if h in hours and hours[h][1] is not None]
    wind = sum(winds) / len(winds) if len(winds) >= 6 else None
    thr = tmin + RISE_C
    t3 = None
    for h in range(mh + 1, 22):
        if h in temps and temps[h] >= thr and (h - 1) in temps:
            v0, v1 = temps[h - 1], temps[h]
            frac = 0.0 if v1 == v0 else (thr - v0) / (v1 - v0)
            t3 = ((h - 1) + 0.5 + frac) * 60  # sredina ure h−1 + delež koraka
            break
    return tmin, mh, t3, rng, wind


def collect(days, place):
    """Za vsak jasen, miren dan s prvim žarkom: zapis {date, month, first, t3, lag_h}."""
    out = []
    for d in sorted(days):
        m = morning_metrics(days[d])
        if not m:
            continue
        tmin, mh, t3, rng, wind = m
        if t3 is None or rng < MIN_RANGE_C or wind is None or wind >= MAX_WIND_KMH:
            continue
        date = datetime.date.fromisoformat(d)
        pr = sh.day_profile(place["lat"], place["lon"], place["horizon"], date)
        if pr["first"] is None:
            continue
        out.append({"date": d, "month": date.month, "first": pr["first"], "t3": t3,
                    "lag_h": (t3 - pr["first"]) / 60.0, "tmin": tmin})
    return out


def month_stats(rows):
    """{mesec: {n, sum, sumsq}} (za natančno združevanje sosednjih mesecev)."""
    st = {}
    for r in rows:
        s = st.setdefault(r["month"], {"n": 0, "sum": 0.0, "sumsq": 0.0})
        s["n"] += 1
        s["sum"] += r["lag_h"]
        s["sumsq"] += r["lag_h"] ** 2
    return st


def lag_for_month(stats, month, min_n=MIN_N):
    """Zamik (ure) za dani mesec iz m−1, m, m+1. Vrne {n, mean_h, sd_h} ali None, če je jasnih jutr premalo."""
    ms = [((month - 2) % 12) + 1, month, (month % 12) + 1]
    n = sum(stats.get(str(m), stats.get(m, {})).get("n", 0) for m in ms)
    if n < min_n:
        return None
    s = sum(stats.get(str(m), stats.get(m, {})).get("sum", 0.0) for m in ms)
    q = sum(stats.get(str(m), stats.get(m, {})).get("sumsq", 0.0) for m in ms)
    mean = s / n
    var = max(q / n - mean * mean, 0.0) * n / max(n - 1, 1)
    return {"n": n, "mean_h": round(mean, 2), "sd_h": round(math.sqrt(var), 2), "months": ms}


def evaluate_predictions(days, pred_path=PRED_PATH):
    """Napovedi (ob napovedanem jasnem, mirnem jutru) proti izmerjenemu času dviga. Dni brez dviga ne štejemo."""
    if not os.path.exists(pred_path):
        return {"n": 0}
    errs, inside, total = [], 0, 0
    with open(pred_path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("clear_calm") != "1" or not r.get("mid_min"):
                continue
            hours = days.get(r["date"])
            m = morning_metrics(hours) if hours else None
            if not m or m[2] is None:
                continue
            total += 1
            e = m[2] - float(r["mid_min"])
            errs.append(e)
            if float(r["lo_min"]) <= m[2] <= float(r["hi_min"]):
                inside += 1
    if not errs:
        return {"n": 0}
    return {"n": total, "mae_min": round(sum(abs(e) for e in errs) / total, 0),
            "bias_min": round(sum(errs) / total, 0), "v_razponu": inside}


def main():
    hz = sh.load_horizons()
    rec = next(p for p in hz["places"] if p["id"] == "recica")
    days = load_obs()
    rows = collect(days, rec)
    stats = month_stats(rows)
    out = {
        "generated": datetime.date.today().isoformat(),
        "dni_v_zapisu": len(days),
        "obdobje": [min(days), max(days)] if days else None,
        "jasna_mirna_jutra": len(rows),
        "dvig_c": RISE_C, "min_n": MIN_N,
        "meseci": {str(m): {**s, "mean_h": round(s["sum"] / s["n"], 2)} for m, s in sorted(stats.items())},
        "preverjanje": evaluate_predictions(days),
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"✓ {OUT_PATH}: {len(rows)} jasnih, mirnih jutr; meseci: "
          + ", ".join(f"{m}: n={s['n']}" for m, s in sorted(stats.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
