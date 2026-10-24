#!/usr/bin/env python3
"""
Poskus (24. 10. 2026): MOS za veter in sunke v dolini (nov cilj MTR).

  eval_mtr7_wind.py V1_CACHE.json WIND.json [since=2025-10-01]

V1_CACHE = {lead: rows} (hitrost vetra wind_speed_10m + oblačnost, tlak …), WIND = izhod fetch_wind_cache.py
(sunki in smer, PRAVI `previous_dayN`). Cilja iz history.json (IREICA1, enota kot Open-Meteo, km/h):
  mean  = windspeedAvg  (dnevno povprečje)   ← Open-Meteo: povprečje wind_speed_10m
  gust  = windgustHigh  (dnevni največji sunek) ← Open-Meteo: največ wind_gusts_10m

Hipoteza: postaja stoji na zavetrnem dnu doline, zato model veter sistematično precenjuje (povprečno
2× pri hitrosti) — ponovljiva razlika, ki jo MOS odstrani, kot Tmin ponoči.

Primerjani modeli (isti walk-forward po mesecih, lambda iz notranje validacije, enaki dnevi, uparjen 7-dnevni
blokovni bootstrap kot eval_mtr3.py):
  raw      surov Open-Meteo
  scalar   Open-Meteo × mediana razmerja (obs/om) na učnih dnevih          ← preprosta osnova
  loglin1  log1p(obs) = a + b · log1p(om)                                  ← preprosta osnova z nelinearnostjo
  mos      log1p(obs) = ridge(značilke: hitrost/sunek, noč/dan, smer, oblačnost, sevanje, tlak, letni hod)
Zanimiva je razlika mos − scalar in mos − loglin1: če jo mos ne premaga, je dobitek samo »postaja je
zavetrna«, ne napoved. Ocena je v km/h (MAE), model deluje v log1p prostoru (veter je asimetričen).
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import train_recica_mos as t   # noqa: E402
import eval_mtr3 as e3         # noqa: E402

GRID = [0.1, 0.5, 2.0, 8.0, 32.0]
INNER = 3
TARGETS = {"mean": "windspeedAvg", "gust": "windgustHigh"}


def _l(x):
    return math.log1p(max(x, 0.0))


def hourly(rec, key):
    return [(int(h), v) for h, v in (rec.get(key) or [])]


def wind_columns(rows_day, wind_day):
    """Dnevne vrednosti iz urnih serij: hitrost, sunek, smer. None, če manjka."""
    w = hourly(rows_day, "wind_speed_10m")
    g = hourly(wind_day or {}, "wind_gusts_10m")
    d = {h: v for h, v in hourly(wind_day or {}, "wind_direction_10m")}
    if len(w) < 20 or len(g) < 20:
        return None
    wn = [v for h, v in w if h in t.NIGHT_HOURS]
    wd = [v for h, v in w if h in t.DAY_HOURS]
    s = sum(v for _, v in w)
    ex = sum(v * math.sin(math.radians(d[h])) for h, v in w if h in d) / s if s > 0 else 0.0
    ey = sum(v * math.cos(math.radians(d[h])) for h, v in w if h in d) / s if s > 0 else 0.0
    return {"wmean": s / len(w), "wmax": max(v for _, v in w), "wn": sum(wn) / len(wn),
            "wd": sum(wd) / len(wd), "gmax": max(v for _, v in g),
            "gmean_d": sum(v for h, v in g if h in t.DAY_HOURS) / max(1, sum(1 for h, _ in g if h in t.DAY_HOURS)),
            "ex": ex, "ey": ey}


def vec_mos(c, f):
    return [1.0, _l(c["wmean"]), _l(c["wmax"]), _l(c["wn"]), _l(c["wd"]), _l(c["gmax"]), _l(c["gmean_d"]),
            c["ex"], c["ey"], f["cloud"] / 100, f["cloud_n"] / 100, f["rad"] / 100, (f["pres"] - 1013) / 10,
            f["sin_doy"], f["cos_doy"]]


def vec_loglin(c, key):
    return [1.0, _l(c[key])]


def solve(X, y, lam):
    return t.solve_ridge(X, y, lam)


def pick_lambda(tr, vec):
    months = sorted({s["date"][:7] for s in tr})
    if len(months) <= INNER:
        return 2.0
    best, bm = 2.0, None
    for lam in GRID:
        errs = []
        for tm in months[-INNER:]:
            a = [s for s in tr if s["date"][:7] < tm]
            b = [s for s in tr if s["date"][:7] == tm]
            if not a or not b:
                continue
            co = solve([vec(s) for s in a], [s["y"] for s in a], lam)
            errs += [abs(math.expm1(t.predict_linear(co, vec(s))) - math.expm1(s["y"])) for s in b]
        if errs and (bm is None or sum(errs) / len(errs) < bm):
            bm, best = sum(errs) / len(errs), lam
    return best


def walk(samples, since, key):
    """Vrne {ime: [(date, pred, obs)]} za raw / scalar / loglin1 / mos."""
    out = {k: [] for k in ("raw", "scalar", "loglin1", "mos")}
    months = sorted({s["date"][:7] for s in samples})
    for tm in [m for m in months if m >= since[:7]]:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        if len(tr) < 100 or not te:
            continue
        ratio = float(np.median([s["obs"] / s["om"] for s in tr if s["om"] > 0.5] or [1.0]))
        v1 = lambda s: vec_loglin(s["c"], key)
        co1 = solve([v1(s) for s in tr], [s["y"] for s in tr], 0.01)
        vm = lambda s: vec_mos(s["c"], s["f"])
        com = solve([vm(s) for s in tr], [s["y"] for s in tr], pick_lambda(tr, vm))
        for s in te:
            out["raw"].append((s["date"], s["om"], s["obs"]))
            out["scalar"].append((s["date"], s["om"] * ratio, s["obs"]))
            out["loglin1"].append((s["date"], max(math.expm1(t.predict_linear(co1, v1(s))), 0.0), s["obs"]))
            out["mos"].append((s["date"], max(math.expm1(t.predict_linear(com, vm(s))), 0.0), s["obs"]))
    return out


def summarize(res):
    """{ime: dict(n, mae, bias, vs_scalar, vs_loglin1)}, razlike so MAE(osnova) − MAE(model) z blokovnim CI."""
    by = {k: {d: (p, o) for d, p, o in r} for k, r in res.items()}
    days = sorted(set.intersection(*[set(v) for v in by.values()]))
    err = {k: np.array([abs(by[k][d][0] - by[k][d][1]) for d in days]) for k in by}
    out = {}
    for k in by:
        row = dict(n=len(days), mae=float(err[k].mean()),
                   bias=float(np.mean([by[k][d][0] - by[k][d][1] for d in days])))
        for base in ("scalar", "loglin1"):
            if k in ("raw", base):
                continue
            mean, (lo, hi) = e3.boot(err[base] - err[k])
            row[base] = (float(mean), float(lo), float(hi))
        out[k] = row
    return out


def main():
    cache = json.load(open(sys.argv[1]))
    wind = json.load(open(sys.argv[2]))
    since = sys.argv[3] if len(sys.argv) > 3 else "2025-10-01"
    hist = t.load_history()
    for name, field in TARGETS.items():
        for lead in t.LEADS:
            rows = t._rows_from_cache(cache[str(lead)])
            samples = []
            key = "wmean" if name == "mean" else "gmax"
            for day in sorted(rows):
                o = hist.get(day)
                if not o or o.get("src") not in ("station", "wu") or o.get(field) is None:
                    continue
                f = t.daily_features(rows[day], day)
                c = wind_columns(rows[day], wind[str(lead)].get(day))
                if f is None or c is None or c[key] is None:
                    continue
                samples.append({"date": day, "f": f, "c": c, "om": c[key], "obs": o[field], "y": _l(o[field])})
            res = walk(samples, since, key)
            for k, r in summarize(res).items():
                tail = ""
                for base in ("scalar", "loglin1"):
                    if base in r:
                        m, lo, hi = r[base]
                        flag = "REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum"
                        tail += f" | vs {base}: {m:+.3f} CI[{lo:+.3f},{hi:+.3f}] {flag}"
                print(f"{name} D+{lead} {k:8s} n={r['n']} MAE={r['mae']:.3f} bias={r['bias']:+.2f}{tail}", flush=True)
            print()


if __name__ == "__main__":
    main()
