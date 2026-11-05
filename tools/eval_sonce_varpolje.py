#!/usr/bin/env python3
"""
tools/eval_sonce_varpolje.py — ali IREICA1 vidi sonce pozneje kot sosednja postaja IREICA7 (Varpolje)?

Ozadje (CLAUDE.md, »Sonce v dolini«): izmerjeni skok sevanja na IREICA1 je mediano +126 min po izračunanem prvem žarku. Domneva
(ni dokazana): senzor stoji v senci bližnjega objekta. Neodvisna priča je Varpolje: ~1,6 km stran, isto dno doline, isti hribi.
Za vsak dan, ko imata obe postaji zapis, iščemo čas prvega žarka z ISTIM detektorjem (`eval_sonce.detect_first_ray`, ne
podvojen) in poročamo razliko IREICA1 − IREICA7.

Kaj razlika POMENI (in česa ne):
  - IREICA1 pozneje za ≥ 30 min: sonce je v dolini prej, IREICA1 je v senci nečesa lokalnega → domneva se podpre;
    model obzorja za odprt teren je lahko pravilen.
  - Razlika pod 30 min: obe postaji vidita sonce ob (skoraj) istem času → senca ni lokalna za IREICA1 in model obzorja
    (ali njegov DEM) ne drži za to dolino; domneva o senzorju se NE podpre.
  - IREICA1 prej za ≥ 30 min: Varpolje je v senci; ne pove nič o IREICA1.
Razlika ne dokazuje vzroka (drevo, streha, zgradba, napaka senzorja) in ne zamenja ogleda okolice senzorja.

Rezultat: data/sonce-varpolje.json. `razsodba` je prazna, dokler ni vsaj MIN_DAYS dni z obema (jutranjima) zapisoma.

Usage:
  python3 tools/eval_sonce_varpolje.py
"""
import csv
import datetime
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_sonce as es  # noqa: E402  (detect_first_ray, load_days, minute, MIN_DAYS — isti detektor)

ROOT = es.ROOT
VP_PATH = os.path.join(ROOT, "data", "varpolje-solar-5min.csv")
OUT_PATH = os.path.join(ROOT, "data", "sonce-varpolje.json")
MIN_DAYS = es.MIN_DAYS
BIG_DIFF_MIN = 30.0


def load_varpolje(path=VP_PATH):
    """CSV → {datum: [(minuta, W/m²)]}; Varpolje ne zapisuje točno na 5 minut, zato je že zaokroženo navzdol (log_varpolje_solar)."""
    days = {}
    if not os.path.exists(path):
        return days
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["solar_wm2"] in ("", None):
                continue
            days.setdefault(r["date"], {})[es.minute(r["time_local"])] = float(r["solar_wm2"])
    return {d: sorted(v.items()) for d, v in days.items()}


def to_grid(series, step=5):
    """Posnetek soseda je vsakih ~5 min z jitterjem: vrzeli v mreži zapolni prejšnja vrednost, a največ 1 korak (10 min)."""
    if not series:
        return []
    have = dict(series)
    lo, hi = min(have), max(have)
    out, last, age = [], None, 99
    for m in range(lo, hi + 1, step):
        if m in have:
            last, age = have[m], 0
        else:
            age += 1
        if m in have or (last is not None and age <= 1):
            out.append((m, have.get(m, last)))
    return out


def first_ray(series, reverse=False):
    """Prvi (zjutraj) ali zadnji (zvečer) žarek; None, če sevanje nikoli ne doseže CLEAR_MIN_WM2 ali skoka ni."""
    part = [(m, v) for m, v in series if (m >= 13 * 60) == reverse]
    if not part or max(v for _, v in part) < es.CLEAR_MIN_WM2:
        return None
    return es.detect_first_ray(part, reverse=reverse)


def compare(days1, daysv):
    rows = []
    for day in sorted(set(days1) & set(daysv)):
        s1, sv = days1[day], to_grid(daysv[day])
        # primerjamo samo v oknu, ki ga IREICA1 sploh beleži (±30 min okoli njegovega zapisa)
        m1 = [m for m, _ in s1]
        lo, hi = min(m1), max(m1)
        sv = [(m, v) for m, v in sv if lo <= m <= hi]
        rec = {"date": day}
        for key, rev in (("jutro", False), ("vecer", True)):
            a, b = first_ray(s1, rev), first_ray(sv, rev)
            if a is not None and b is not None:
                rec[key] = {"ireica1": a, "ireica7": b, "razlika_min": round(a - b, 1)}
        rows.append(rec)
    return rows


def summarize(rows):
    def stats(key):
        d = [r[key]["razlika_min"] for r in rows if key in r]
        if not d:
            return {"n": 0}
        med = statistics.median(d)
        return {"n": len(d), "mediana_min": round(med, 1),
                "mad_min": round(statistics.median([abs(x - med) for x in d]), 1), "min_min": min(d), "max_min": max(d)}
    j = stats("jutro")
    verdict = None
    if j["n"] >= MIN_DAYS:
        med = j["mediana_min"]
        verdict = ("ireica1_pozneje" if med >= BIG_DIFF_MIN else "ireica1_prej" if med <= -BIG_DIFF_MIN else "podobno")
    return {"jutro": j, "vecer": stats("vecer"), "min_dni": MIN_DAYS, "prag_min": BIG_DIFF_MIN, "razsodba": verdict,
            "opomba": "IREICA1 − IREICA7 (čas prvega žarka); pozitivno = IREICA1 vidi sonce pozneje"}


def main():
    rows = compare(es.load_days(), load_varpolje())
    out = {"generated": datetime.date.today().isoformat(), "dni_z_obema": len(rows), **summarize(rows)}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
