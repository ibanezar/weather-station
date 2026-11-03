#!/usr/bin/env python3
"""
tools/eval_sonce.py — preverjanje modela obzorja (/sonce-v-dolini/) s 5-minutnimi meritvami sevanja IREICA1.

Izmerjeni prvi žarek = prvi hitri, trajni skok sevanja zjutraj (`detect_first_ray`): v 5 minutah za vsaj `JUMP_MIN`
W/m² in hkrati vsaj `JUMP_REL` trenutnega sevanja, poleg tega mora biti sevanje v naslednjih 30 minutah ves čas nad
vrednostjo pred skokom + 70 % skoka (oblak ne sme skoka takoj zbrisati). Zadnji žarek zvečer je enak, samo obrnjen.
Dan se šteje samo, če skok obstaja in če sevanje zjutraj/zvečer pozneje doseže vsaj `CLEAR_MIN_WM2`; megla in
oblak, kjer skoka ni, se ne ocenjujejo (ne »uganemo« časa).

To je preizkus, ne dokaz: pri nizkem soncu je skok majhen, razkorak pa lahko povzročijo tudi drevesa blizu postaje, ki
jih model ne vidi (prvih 150 m preskoči). Zato poročam mediano razlike in razpon, ne trdim natančnosti.

Rezultat: data/sonce-preverjanje.json ({n_jutro, n_vecer, mediana_min, mad_min, ...}); stran ga prikaže, ko je dni vsaj
`MIN_DAYS` (15), sicer samo pove, koliko jih je.

Usage:
  python3 tools/eval_sonce.py
"""
import csv
import datetime
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402  (LAT/LON)
import sonce_horizont as sh  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "solar-5min.csv")
OUT_PATH = os.path.join(ROOT, "data", "sonce-preverjanje.json")
JUMP_MIN, JUMP_REL = 25.0, 0.15
HOLD_FRAC, HOLD_MIN = 0.7, 30
CLEAR_MIN_WM2 = 150.0
MIN_DAYS = 15


def minute(hm):
    return int(hm[:2]) * 60 + int(hm[3:5])


def detect_first_ray(series, reverse=False):
    """series: [(minuta, W/m²)] v časovnem zaporedju na 5 minut. Vrne minuto skoka ali None.
    reverse=True: iščemo zadnji žarek (skok navzdol, od konca)."""
    s = sorted(series, reverse=reverse)
    vals = {m: v for m, v in s}
    step = 5
    if reverse:
        step = -5
    order = [m for m, _ in s]
    for m in order:
        prev, cur = vals.get(m - step), vals.get(m)
        if prev is None or cur is None:
            continue
        jump = cur - prev
        if jump < JUMP_MIN or jump < JUMP_REL * cur:
            continue
        tail = [vals.get(m + step * k) for k in range(1, HOLD_MIN // 5 + 1)]
        tail = [t for t in tail if t is not None]
        if len(tail) < 3 or min(tail) < prev + HOLD_FRAC * jump:
            continue
        # čas skoka = sredina 5-minutnega intervala: pri iskanju naprej (m − 5, m], pri iskanju nazaj (m, m + 5]
        return m + 2.5 if reverse else m - 2.5
    return None


def load_days(path=LOG_PATH):
    days = {}
    if not os.path.exists(path):
        return days
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["solar_wm2"] in ("", None):
                continue
            days.setdefault(r["date"], []).append((minute(r["time_local"]), float(r["solar_wm2"])))
    return days


def evaluate(days, hz_place):
    """Za vsak dan primerja izmerjeni in modelski prvi/zadnji žarek (minute). Vrne seznam dnevnih zapisov."""
    rows = []
    for day, ser in sorted(days.items()):
        date = datetime.date.fromisoformat(day)
        pr = sh.day_profile(hz_place["lat"], hz_place["lon"], hz_place["horizon"], date)
        flat_rise, flat_set = pr["flat_rise"], pr["flat_set"]
        if flat_rise is None:
            continue
        morn = [(m, v) for m, v in ser if m < 13 * 60]
        eve = [(m, v) for m, v in ser if m >= 13 * 60]
        rec = {"date": day, "model_first": pr["first"], "model_last": pr["last"]}
        if morn and max(v for _, v in morn) >= CLEAR_MIN_WM2:
            rec["meas_first"] = detect_first_ray(morn)
        if eve and max(v for _, v in eve) >= CLEAR_MIN_WM2:
            rec["meas_last"] = detect_first_ray(eve, reverse=True)
        rows.append(rec)
    return rows


def summarize(rows):
    def stats(key_meas, key_model):
        d = [r[key_meas] - r[key_model] for r in rows
             if r.get(key_meas) is not None and r.get(key_model) is not None]
        if not d:
            return {"n": 0}
        med = statistics.median(d)
        return {"n": len(d), "mediana_min": round(med, 1),
                "mad_min": round(statistics.median([abs(x - med) for x in d]), 1),
                "min_min": round(min(d), 1), "max_min": round(max(d), 1)}
    return {"jutro": stats("meas_first", "model_first"), "vecer": stats("meas_last", "model_last"),
            "min_dni": MIN_DAYS, "opomba": "izmerjeno − model; pozitivno = sonce pride pozneje, kot pravi model"}


def main():
    hz = sh.load_horizons()
    rec = next(p for p in hz["places"] if p["id"] == "recica")
    rows = evaluate(load_days(), rec)
    out = {"generated": datetime.date.today().isoformat(), "dni_v_zapisu": len(rows), **summarize(rows)}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
