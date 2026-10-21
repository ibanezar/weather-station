#!/usr/bin/env python3
"""
Prototip: verjetnost padavin po pragovih (>= 0,2 / 1 / 5 mm) za MTR, brez sprememb produkcije.

Isti vhodi in ista logistična regresija kot `pop` (train_recica_mos.pop_vector, solve_logistic);
spreminja se samo cilj. Preverjanje je z izpuščanjem celega leta (kot blocked_cv_pop) IN
walk-forward po mesecih (kot ostali eval_*), Brier proti klimatologiji učne množice, plus
zanesljivostni diagram. Primerja tudi surov Open-Meteo kot enostaven prag (om_prec >= prag).

usage: eval_pop_thresholds.py [--csv] [CACHE.json]
  --csv = rezervni način iz data/forecast-archive.csv (manj značilk; brez omrežja)
  CACHE.json = tools/.mos_cache.json (privzeto; ključi "lead<N>:<od>:<do>"), sicer zajame arhiv.
"""
import json, math, os, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import train_recica_mos as t   # noqa: E402

USE_CSV = False

THRESHOLDS = (0.2, 1.0, 5.0)
BINS = [0, .05, .15, .3, .5, .7, 1.0001]


def load_rows(lead, cache, start, end):
    for k, v in cache.items():
        if k.startswith(f"lead{lead}:") and k.count(":") == 2:
            return t._rows_from_cache(v)
    return t.fetch_archived_forecasts(lead, start, end)


def with_mm(samples, hist):
    """Pripne izmerjene mm dneva (precipTotal IREICA1)."""
    by_day = {d["date"]: d for d in hist} if isinstance(hist, list) else hist
    out = []
    for s in samples:
        obs = by_day.get(s["date"]) or {}
        s = dict(s)
        s["mm"] = obs.get("precipTotal") or 0.0
        out.append(s)
    return out


def brier(p, y):
    return sum((a - b) ** 2 for a, b in zip(p, y)) / len(y)


def fit_predict(tr, te, thr):
    vec = csv_vector if USE_CSV else t.pop_vector
    X = [vec(s["f"]) for s in tr]
    y = [1.0 if s["mm"] >= thr else 0.0 for s in tr]
    if sum(y) < 5:
        return None
    c = t.solve_logistic(X, y)
    clim = sum(y) / len(y)
    return [t.predict_prob(c, vec(s["f"])) for s in te], clim


def eval_lead(samples, thr, mode):
    P, Y, C, OM = [], [], [], []
    if mode == "year":
        groups = sorted({s["date"][:4] for s in samples})
        folds = [([s for s in samples if s["date"][:4] != g], [s for s in samples if s["date"][:4] == g])
                 for g in groups]
    else:
        months = sorted({s["date"][:7] for s in samples})
        folds = [([s for s in samples if s["date"][:7] < m], [s for s in samples if s["date"][:7] == m])
                 for m in months[t.MIN_TRAIN_MONTHS:]]
    for tr, te in folds:
        if not tr or not te:
            continue
        r = fit_predict(tr, te, thr)
        if r is None:
            continue
        p, clim = r
        P += p
        Y += [1.0 if s["mm"] >= thr else 0.0 for s in te]
        C += [clim] * len(te)
        OM += [1.0 if s["f"]["om_prec"] >= thr else 0.0 for s in te]
    return P, Y, C, OM


def csv_samples(lead, hist):
    """Rezervni način (brez Open-Meteo): značilke iz data/forecast-archive.csv — padavine vseh
    virov za dan, vodilni čas `lead`. Manj značilk kot pop_vector (brez vlage, oblačnosti, tlaka)."""
    import csv
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
        out.append({"date": day, "mm": obs["precipTotal"], "f": {
            "om_prec": m.get("best_match", mean), "mean_prec": mean,
            "wet_frac": sum(x >= 0.2 for x in v) / len(v), "n1_frac": sum(x >= 1 for x in v) / len(v),
            "sin_doy": math.sin(2 * math.pi * doy / 365.25), "cos_doy": math.cos(2 * math.pi * doy / 365.25)}})
    return out


def csv_vector(f):
    return [1.0, math.sqrt(min(f["om_prec"], 50)), math.sqrt(min(f["mean_prec"], 50)),
            f["wet_frac"], f["n1_frac"], f["sin_doy"], f["cos_doy"]]


def main():
    global USE_CSV
    USE_CSV = "--csv" in sys.argv
    if USE_CSV:
        sys.argv.remove("--csv")
    cache_path = sys.argv[1] if len(sys.argv) > 1 else t.CACHE_PATH
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    end = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    hist = t.load_history()
    for lead in t.LEADS:
        if USE_CSV:
            samples = csv_samples(lead, hist)
        else:
            rows = load_rows(lead, cache, t.TRAIN_START, end)
            samples = with_mm(t.build_samples(rows, hist, lead), hist)
        print(f"\n=== D+{lead}: {len(samples)} dni ({samples[0]['date']} → {samples[-1]['date']})")
        for thr in THRESHOLDS:
            n_pos = sum(1 for s in samples if s["mm"] >= thr)
            print(f"\n  prag >= {thr} mm  (pozitivnih {n_pos}/{len(samples)} = {n_pos/len(samples):.0%})")
            for mode in ("year", "walk"):
                P, Y, C, OM = eval_lead(samples, thr, mode)
                if not P:
                    print(f"    {mode}: premalo pozitivnih")
                    continue
                b, bc, bo = brier(P, Y), brier(C, Y), brier(OM, Y)
                print(f"    {mode:4}: n={len(P)} Brier MTR {b:.3f} | klimatologija {bc:.3f} "
                      f"| surov OM (0/1) {bo:.3f} | veščina {1 - b/bc:+.2f}")
            P, Y, C, OM = eval_lead(samples, thr, "year")
            if P and thr > 0.2 and lead == 1:
                print("    zanesljivost (year-CV):  bin   n   napoved  dejansko")
                for lo, hi in zip(BINS, BINS[1:]):
                    ix = [i for i, p in enumerate(P) if lo <= p < hi]
                    if ix:
                        print(f"      {lo:.2f}-{min(hi,1):.2f}  {len(ix):4d}   "
                              f"{sum(P[i] for i in ix)/len(ix):.2f}     {sum(Y[i] for i in ix)/len(ix):.2f}")


if __name__ == "__main__":
    main()
