#!/usr/bin/env python3
"""
MTR v2 experiment, step 3 (two ideas, tested walk-forward and against MTR v1):

  HM  hourly-derived features of EVERY model (cloud/wind/radiation of IFS, GFS,
      ICON, ARPEGE, AIFS; their ensemble mean and spread; per-model coldpool),
      not only Tmax/Tmin of the other models.
  ERA prior  the valley offset learned from 7 years of station vs ERA5 analysis
      (same daily_features/temp_vector as MTR v1), applied to the FORECAST
      features of the default model, then given to the forecast-trained ridge
      as one extra feature. ERA5 is used only to learn the local offset; the
      forecast error itself is still learned on real archived forecasts, so the
      evaluation is not inflated by analysis-vs-forecast leakage.

Both go through the same walk-forward by month as eval_mtr2*.py; the paired
block bootstrap tells whether the difference to MTR v1 is more than noise.

usage: eval_mtr2_models.py V1_CACHE.json MODELS_CACHE.json [since]
  V1_CACHE.json     {lead: rows}  (default model, as for eval_mtr2_hourly.py)
  MODELS_CACHE.json {"<model>|<lead>": rows, "era5|<year>": rows}
"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr2 as e1               # noqa: E402
import eval_mtr2_hourly as h         # noqa: E402
import eval_mtr_calibration as cal   # noqa: E402
import eval_significance as sig      # noqa: E402
t = cal.t

MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_arpege_europe", "ecmwf_aifs025_single"]
SHORT = {"ecmwf_ifs025": "ifs", "gfs_seamless": "gfs", "icon_seamless": "icon",
         "meteofrance_arpege_europe": "arp", "ecmwf_aifs025_single": "aifs"}
LAM = 10.0


def model_features(w, mcache, lead):
    """Add per-model hourly-derived columns to the daily frame `w`."""
    rows_default = None
    cols = {}
    ens = {k: [] for k in ("cloud_n", "wind_n", "rad", "rh", "coldpool")}
    for m in MODELS:
        key = f"{m}|{lead}"
        if key not in mcache:
            continue
        rows = t._rows_from_cache(mcache[key])
        feats = [t.daily_features(rows.get(d) or {}, d) for d in w.valid_at]
        s = SHORT[m]
        for name in ("cloud_n", "wind_n", "rad", "rh"):
            vals = np.array([f[name] if f else np.nan for f in feats], float)
            cols[f"{s}_{name}"] = vals
            ens[name].append(vals)
        cp = np.array([((100 - f["cloud_n"]) / 100 * (1 / (1 + f["wind_n"]))) if f else np.nan for f in feats])
        cols[f"{s}_coldpool"] = cp
        ens["coldpool"].append(cp)
    for name, lst in ens.items():
        if lst:
            a = np.vstack(lst)
            cols[f"ens_{name}"] = np.nanmean(a, axis=0)
            if name in ("cloud_n", "wind_n"):
                cols[f"ens_{name}_sd"] = np.nanstd(a, axis=0)
    return pd.concat([w, pd.DataFrame(cols, index=w.index)], axis=1), sorted(cols)


def era_days(mcache):
    days = {}
    for k, v in mcache.items():
        if k.startswith("era5|"):
            days.update(t._rows_from_cache(v))
    return days


def era_prior_fit(era, hist, target, before):
    """Ridge of station target on ERA5 daily features, days strictly before `before`."""
    X, y = [], []
    for day in sorted(era):
        if day >= before:
            break
        obs = hist.get(day)
        if not obs or obs.get("src") not in ("station", "wu"):
            continue
        v = obs.get("tempHigh" if target == "tmax" else "tempLow")
        f = t.daily_features(era[day], day)
        if v is None or f is None:
            continue
        X.append(t.temp_vector(f, target))
        y.append(v)
    if len(y) < 300:
        return None
    return t.solve_ridge(X, y, 2.0)


def run(lead, target, v1cache, mcache, since, hist, arch, obs):
    w = h.build(lead, v1cache, arch, obs)
    w, mcols = model_features(w, mcache, lead)
    rows = t._rows_from_cache(v1cache[str(lead)])
    fdef = {d: t.daily_features(rows.get(d) or {}, d) for d in w.valid_at}
    era = era_days(mcache)
    y = w[f"obs_{target}"].values
    mean = w[f"{target}_mean"].values
    v1cols = [c for c in w.columns if c.startswith("v1_")] + ["windmax", "radsum", "windcloud_n"]
    base = v1cols + e1.features(target)
    sets = {"base(v1+multiTmax)": base, "+HM": base + mcols, "+ERA": base + ["prior"], "+HM+ERA": base + mcols + ["prior"]}
    preds = {k: np.full(len(w), np.nan) for k in sets}
    for mth in sorted(w.month.unique()):
        te = (w.month == mth).values
        first = w.valid_at[te].min()
        tr = (w.valid_at < first).values
        if tr.sum() < h.MIN_TRAIN_DAYS:
            continue
        co = era_prior_fit(era, hist, target, first) if era else None
        w["prior"] = [t.predict_linear(co, t.temp_vector(fdef[d], target)) - mean[i]
                      if (co and fdef[d]) else np.nan for i, d in enumerate(w.valid_at)]
        r = y - mean
        for name, cols in sets.items():
            if "prior" in cols and co is None:
                continue
            X = w[cols]
            X = X.fillna(X[tr].median())
            preds[name][te] = mean[te] + e1.ridge_fit_predict(X[tr].values, r[tr], X[te].values, lam=LAM)
    df = pd.DataFrame({"valid_at": w.valid_at, "obs": y, **preds})
    return df[df.valid_at >= since].dropna(subset=["obs", "base(v1+multiTmax)"]).reset_index(drop=True)


if __name__ == "__main__":
    v1cache, mcache = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
    since = sys.argv[3] if len(sys.argv) > 3 else "2025-10-01"
    hist = t.load_history()
    arch, obs = e1.load()
    print(f"models in cache: {sorted({k.split('|')[0] for k in mcache})}")
    for tg in ("tmax", "tmin"):
        for lead in (1, 2, 3):
            df = run(lead, tg, v1cache, mcache, since, hist, arch, obs)
            smp = t.build_samples(t._rows_from_cache(v1cache[str(lead)]), hist, lead)
            v1 = cal.walk(smp, tg, since)[["date", "pred"]].rename(columns={"date": "valid_at"})
            m = v1.merge(df, on="valid_at")
            e_v1 = (m.obs - m.pred).abs().values
            line = [f"{tg} D+{lead} n={len(m)} v1={e_v1.mean():.3f}"]
            for name in ("base(v1+multiTmax)", "+HM", "+ERA", "+HM+ERA"):
                if m[name].isna().all():
                    continue   # data for this variant not available (e.g. no ERA5 cache)
                d = e_v1 - (m.obs - m[name]).abs().values
                mean_d, (lo, hi) = sig.block_bootstrap(d)
                tag = "REAL" if lo > 0 else ("WORSE" if hi < 0 else "noise")
                line.append(f"{name}={(m.obs - m[name]).abs().mean():.3f}({mean_d:+.3f} {tag})")
            print("  ".join(line))
