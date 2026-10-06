#!/usr/bin/env python3
"""
One-off exporter (needs the hourly archive cache): walk-forward BACKTEST of MTR v1
reliability -> data/mtr-reliability.json, read by /trendi/ ("Ko rečemo 70 %...").
It is a backtest (each month predicted from models trained only on earlier
months), not live verification; the page says so. Re-run when the model is
retrained and the cache is available:
  python3 -I tools/ai/export_reliability.py HOURLY_CACHE.json [since]
"""
import datetime, json, math, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr_calibration as cal   # noqa: E402
import eval_mtr2 as e1               # noqa: E402
t = cal.t
ROOT = cal.ROOT
BINS = [0, .1, .3, .5, .7, .9, 1.0]


def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def table(p, y):
    out = []
    for lo, hi in zip(BINS[:-1], BINS[1:]):
        m = (p > lo) & (p <= hi) if lo > 0 else (p <= hi)
        if m.sum() == 0:
            continue
        out.append({"lo": lo, "hi": hi, "n": int(m.sum()), "mean_p": round(float(p[m].mean()), 3),
                    "freq": round(float(y[m].mean()), 3)})
    return out


if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    arch, obs = e1.load()
    res = {"kind": "backtest", "method": "walk-forward po mesecih, učenje samo na prejšnjih mesecih",
           "since": since, "rain": {}, "frost": {}}
    for lead in (1, 2, 3):
        smp = t.build_samples(t._rows_from_cache(cache[str(lead)]), hist, lead)
        # wet-day probability: v1 logistic, retrained for every test month
        days = sorted({s["date"] for s in smp})
        months = sorted({d[:7] for d in days})
        P, Y = [], []
        for tm in months[t.MIN_TRAIN_MONTHS:]:
            tr = [s for s in smp if s["date"][:7] < tm]
            te = [s for s in smp if s["date"][:7] == tm and s["date"] >= since]
            if not te:
                continue
            co = t.solve_logistic([t.pop_vector(s["f"]) for s in tr], [s["wet"] for s in tr])
            P += [t.predict_prob(co, t.pop_vector(s["f"])) for s in te]
            Y += [s["wet"] for s in te]
        P, Y = np.array(P), np.array(Y)
        res["rain"][f"D+{lead}"] = {"n": len(P), "brier": round(float(np.mean((P - Y) ** 2)), 3),
                                    "brier_climatology": round(float(np.mean((Y.mean() - Y) ** 2)), 3),
                                    "bins": table(P, Y)}
        d = cal.walk(smp, "tmin", since)
        pf = np.array([phi((0 - pr) / (1.15 * sd)) for pr, sd in zip(d.pred, d.sd)])
        yf = (d.obs <= 0).astype(float).values
        res["frost"][f"D+{lead}"] = {"n": len(pf), "frost_nights": int(yf.sum()),
                                     "brier": round(float(np.mean((pf - yf) ** 2)), 3),
                                     "brier_climatology": round(float(np.mean((yf.mean() - yf) ** 2)), 3),
                                     "bins": table(pf, yf)}
    res["generated_at"] = datetime.date.today().isoformat()
    path = os.path.join(ROOT, "data", "mtr-reliability.json")
    json.dump(res, open(path, "w"), ensure_ascii=False, indent=1)
    print("written", path)
