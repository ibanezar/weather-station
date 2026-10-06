#!/usr/bin/env python3
"""
Is a candidate really better than MTR v1? Paired moving-block bootstrap (7-day
blocks, weather errors are autocorrelated) of the mean absolute-error difference
on identical out-of-sample days. diff = |e_v1| - |e_candidate| > 0 means the
candidate is better; the 95 % CI tells whether that is more than noise.

usage: eval_significance.py HOURLY_CACHE.json [since]
"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr_calibration as cal   # noqa: E402  (walk() = real v1 walk-forward)
import eval_mtr2_hourly as h         # noqa: E402
import eval_mtr2 as e1               # noqa: E402
t = cal.t

BLOCK, REPS = 7, 5000
rng = np.random.default_rng(42)


def block_bootstrap(d):
    n = len(d)
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, n - BLOCK + 1, size=(REPS, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(REPS, -1)[:, :n]
    m = d[idx].mean(axis=1)
    return d.mean(), np.percentile(m, [2.5, 97.5])


if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    arch, obs = e1.load()
    print("diff = MAE(v1) - MAE(candidate) in degC; CI95 excluding 0 => real difference")
    for tg in ("tmax", "tmin"):
        for lead in (1, 2, 3):
            smp = t.build_samples(t._rows_from_cache(cache[str(lead)]), hist, lead)
            v1 = cal.walk(smp, tg, since)[["date", "pred", "obs"]].rename(columns={"date": "valid_at"})
            cand = h.predict_all(lead, tg, cache, arch, obs)
            m = v1.merge(cand.drop(columns="obs"), on="valid_at")
            e_v1 = (m.obs - m.pred).abs().values
            for name in ("v1feat_lgb", "v1+multi_ridge"):
                d = e_v1 - (m.obs - m[name]).abs().values
                mean, (lo, hi) = block_bootstrap(d)
                flag = "REAL" if lo > 0 else ("WORSE" if hi < 0 else "noise")
                print(f"{tg} D+{lead} {name:15s} n={len(m)} diff={mean:+.3f} CI95=[{lo:+.3f},{hi:+.3f}] {flag}")
