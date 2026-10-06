#!/usr/bin/env python3
"""
Out-of-sample check of a frost-night probability, P(Tmin <= 0 C) = Phi((0 - pred) / (k * sd)),
using MTR v1 walk-forward predictions and the sd the card would have shown.
Reports Brier vs climatology and a reliability table for k = 1.0 and 1.15.
usage: eval_frost.py HOURLY_CACHE.json [since]
"""
import json, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr_calibration as cal   # noqa: E402
t = cal.t

def phi(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    for lead in (1, 2, 3):
        smp = t.build_samples(t._rows_from_cache(cache[str(lead)]), hist, lead)
        d = cal.walk(smp, "tmin", since)
        y = (d.obs <= 0).astype(float).values
        print(f"\nD+{lead}: n={len(d)} frost nights={int(y.sum())}")
        clim = y.mean()
        print(f"  Brier clim={np.mean((clim - y) ** 2):.4f}")
        for k in (1.0, 1.15):
            p = np.array([phi((0 - pr) / (k * sd)) for pr, sd in zip(d.pred, d.sd)])
            print(f"  k={k}: Brier={np.mean((p - y) ** 2):.4f}")
            if k == 1.15:
                b = pd.cut(pd.Series(p), [-.01, .02, .1, .3, .5, .7, .9, 1.0])
                r = pd.DataFrame({"p": p, "y": y}).groupby(b, observed=True).agg(
                    n=("y", "size"), mean_p=("p", "mean"), freq=("y", "mean")).round(2)
                print(r.to_string())
        # also near-frost misses: model said > 0.3 never frost etc
