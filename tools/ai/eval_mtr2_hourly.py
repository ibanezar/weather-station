#!/usr/bin/env python3
"""
MTR v2 experiment, step 2: LightGBM / ridge on the MTR v1 feature set
(train_recica_mos.daily_features + temp_vector) plus multi-model daily columns
from data/forecast-archive.csv. Same walk-forward-by-month protocol as
eval_mtr2.py, so numbers are comparable with MTR v1's `skill` block.

usage: eval_mtr2_hourly.py HOURLY_CACHE.json [since]
HOURLY_CACHE.json = {lead: rows} as written by train_recica_mos._rows_to_cache
(untrusted-ish local file; pass it as an argument, run with python -I).
"""
import json, os, sys
import numpy as np, pandas as pd
import lightgbm as lgb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "ai"))
import train_recica_mos as t          # noqa: E402  (daily_features, temp_vector: single source of truth)
import eval_mtr2 as e1                # noqa: E402

MIN_TRAIN_DAYS = 150
V1_COLS = None


def build(lead, cache, arch, obs):
    rows = t._rows_from_cache(cache[str(lead)])
    w = e1.wide(arch, obs, lead)
    recs = []
    for _, r in w.iterrows():
        f = t.daily_features(rows.get(r.valid_at) or {}, r.valid_at)
        if f is None:
            continue
        vec = t.temp_vector(f, "tmax")[1:]          # drop intercept
        d = {f"v1_{i}": x for i, x in enumerate(vec)}
        d["valid_at"] = r.valid_at
        d["windmax"] = f["windmax"]
        d["radsum"] = f["radsum"] / 1000
        d["windcloud_n"] = f["wind_n"] * f["cloud_n"] / 100
        recs.append(d)
    v1 = pd.DataFrame(recs)
    return w.merge(v1, on="valid_at", how="inner")


def run(lead, target, cache, arch, obs, since):
    w = build(lead, cache, arch, obs)
    y = w[f"obs_{target}"].values
    mean = w[f"{target}_mean"].values
    v1cols = [c for c in w.columns if c.startswith("v1_")] + ["windmax", "radsum", "windcloud_n"]
    sets = {
        "v1feat": v1cols,
        "v1+multi": v1cols + e1.features(target),
    }
    out = {}
    months = sorted(w.month.unique())
    res = {"n": 0}
    preds = {f"{k}_{m}": np.full(len(w), np.nan) for k in sets for m in ("ridge", "lgb")}
    for mth in months:
        te = (w.month == mth).values
        tr = (w.valid_at < w.valid_at[te].min()).values
        if tr.sum() < MIN_TRAIN_DAYS:
            continue
        r = y - mean
        for name, cols in sets.items():
            X = w[cols]
            X = X.fillna(X[tr].median())
            Xtr, Xte = X[tr].values, X[te].values
            preds[f"{name}_ridge"][te] = mean[te] + e1.ridge_fit_predict(Xtr, r[tr], Xte, lam=10.0)
            g = lgb.LGBMRegressor(objective="l1", n_estimators=250, learning_rate=0.03, num_leaves=6,
                                  min_child_samples=20, subsample=0.8, subsample_freq=1,
                                  colsample_bytree=0.8, reg_lambda=5.0, verbose=-1).fit(Xtr, r[tr])
            preds[f"{name}_lgb"][te] = mean[te] + g.predict(Xte)
    ok = ~np.isnan(preds["v1feat_lgb"]) & ~np.isnan(y) & (w.valid_at >= since).values
    res["n"] = int(ok.sum())
    res["raw"] = float(np.mean(np.abs(w[f"best_match_{target}_c"].values[ok] - y[ok])))
    for k, p in preds.items():
        res[k] = float(np.mean(np.abs(p[ok] - y[ok])))
    return res


if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    arch, obs = e1.load()
    for tg in ("tmax", "tmin"):
        for lead in (1, 2, 3):
            r = run(lead, tg, cache, arch, obs, since)
            print(tg, f"D+{lead}", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
