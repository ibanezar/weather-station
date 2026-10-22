#!/usr/bin/env python3
"""
Prototip: točkovna napoved DNEVNE KOLIČINE padavin (mm) za MTR, samo ocena (brez sprememb produkcije).

Primerja po vodilnih časih, z izpuščanjem celega leta (kot blocked_cv_pop):
  OM    surov Open-Meteo best_match
  MEAN  povprečje vseh virov iz data/forecast-archive.csv
  RIDGE grebenska regresija na sqrt(mm) (značilke: sqrt best_match, sqrt povprečje, delež virov z >= 0,2 / >= 1 mm,
        sqrt max, letni hod), povratna pretvorba kvadrat + popravek variance (smearing)
Metrike: MAE, RMSE, pristranskost (napoved − meritev) in MAE na mokrih dneh (>= 1 mm), skupaj z deležem
zadetih razredov (<1 / 1–5 / 5–15 / >15 mm). Rezervni način brez omrežja: samo arhiv več modelov.

usage: eval_precip_amount.py
"""
import csv, math, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import train_recica_mos as t   # noqa: E402

CLASSES = (1.0, 5.0, 15.0)


def cls(v):
    return sum(v >= c for c in CLASSES)


def samples(lead, hist):
    by = {}
    with open(os.path.join(ROOT, "data", "forecast-archive.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if int(r["lead_days"]) != lead or r["precip_mm"] in ("", None):
                continue
            by.setdefault(r["valid_at"], {})[r["model"]] = float(r["precip_mm"])
    out = []
    for day, m in sorted(by.items()):
        obs = hist.get(day)
        if not obs or obs.get("src") == "era5" or obs.get("precipTotal") is None or len(m) < 3:
            continue
        v = list(m.values())
        doy = dt.date.fromisoformat(day).timetuple().tm_yday
        mean = sum(v) / len(v)
        out.append({"date": day, "mm": obs["precipTotal"], "om": m.get("best_match", mean), "mean": mean,
                    "x": [1.0, math.sqrt(min(m.get("best_match", mean), 80)), math.sqrt(min(mean, 80)),
                          sum(a >= 0.2 for a in v) / len(v), sum(a >= 1 for a in v) / len(v),
                          math.sqrt(min(max(v), 80)),
                          math.sin(2 * math.pi * doy / 365.25), math.cos(2 * math.pi * doy / 365.25)]})
    return out


def fit(tr, lam):
    X = [s["x"] for s in tr]
    y = [math.sqrt(s["mm"]) for s in tr]
    c = t.solve_ridge(X, y, lam)
    res = [(t.predict_linear(c, x) - yy) for x, yy in zip(X, y)]
    return c, sum(r * r for r in res) / len(res)    # smearing: E[mm] = E[(mu+e)^2] = mu^2 + var


def predict(c, var, x):
    mu = max(t.predict_linear(c, x), 0.0)
    return mu * mu + var * (1.0 if mu > 0.3 else 0.0)


def report(name, pred, obs):
    n = len(obs)
    mae = sum(abs(a - b) for a, b in zip(pred, obs)) / n
    rmse = math.sqrt(sum((a - b) ** 2 for a, b in zip(pred, obs)) / n)
    bias = sum(a - b for a, b in zip(pred, obs)) / n
    wet = [(a, b) for a, b in zip(pred, obs) if b >= 1]
    mw = sum(abs(a - b) for a, b in wet) / len(wet)
    hit = sum(cls(a) == cls(b) for a, b in zip(pred, obs)) / n
    print(f"    {name:6} MAE {mae:5.2f}  RMSE {rmse:5.2f}  bias {bias:+5.2f}  MAE mokri(>=1mm) {mw:5.2f}  razred {hit:.0%}")


def main():
    hist = t.load_history()
    for lead in (1, 2, 3):
        s = samples(lead, hist)
        years = sorted({x["date"][:4] for x in s})
        print(f"\n=== D+{lead}: {len(s)} dni, povprečno {sum(x['mm'] for x in s)/len(s):.2f} mm/dan, "
              f"mokrih >= 1 mm: {sum(x['mm']>=1 for x in s)}")
        for lam in (1.0, 5.0):
            P, O, OM, MEAN = [], [], [], []
            for y in years:
                tr = [x for x in s if x["date"][:4] != y]
                te = [x for x in s if x["date"][:4] == y]
                if not tr or not te:
                    continue
                c, var = fit(tr, lam)
                for x in te:
                    P.append(predict(c, var, x["x"])); O.append(x["mm"]); OM.append(x["om"]); MEAN.append(x["mean"])
            print(f"  lambda {lam}:")
            if lam == 1.0:
                report("OM", OM, O); report("MEAN", MEAN, O)
            report("RIDGE", P, O)


if __name__ == "__main__":
    main()
