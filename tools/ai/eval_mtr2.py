#!/usr/bin/env python3
"""
Experiment: does a multi-model gradient-boosting correction beat raw models
and a plain ridge on the station's daily Tmax/Tmin? (MTR v2 candidate.)

Inputs only: data/forecast-archive.csv (multi-model daily forecasts) and
history.json (days with src station/wu; era5 days are excluded as labels).
Indoor measurements are never read. Training-only deps: lightgbm, numpy, pandas.

Validation is walk-forward by month (never random): train on all months before
the test month, predict the test month.
"""
import json, os, sys
import numpy as np, pandas as pd
import lightgbm as lgb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless",
          "meteofrance_arpege_europe", "ecmwf_aifs025_single"]
MIN_TRAIN_DAYS = 150


def load():
    arch = pd.read_csv(os.path.join(ROOT, "data", "forecast-archive.csv"))
    hist = json.load(open(os.path.join(ROOT, "history.json")))
    obs = pd.DataFrame(
        [{"valid_at": d, "obs_tmax": v.get("tempHigh"), "obs_tmin": v.get("tempLow"),
          "obs_p": v.get("precipTotal")}
         for d, v in hist.items() if v.get("src") in ("station", "wu")])
    return arch, obs


def wide(arch, obs, lead):
    a = arch[arch.lead_days == lead]
    parts = []
    for m in MODELS:
        s = a[a.model == m].drop_duplicates("valid_at", keep="last").set_index("valid_at")
        parts.append(s[["tmax_c", "tmin_c", "precip_mm"]].add_prefix(m + "_"))
    w = pd.concat(parts, axis=1).reset_index().rename(columns={"index": "valid_at"})
    w = w.merge(obs, on="valid_at", how="inner")
    d = pd.to_datetime(w.valid_at)
    w["doy_s"] = np.sin(2 * np.pi * d.dt.dayofyear / 365.25)
    w["doy_c"] = np.cos(2 * np.pi * d.dt.dayofyear / 365.25)
    w["month"] = d.dt.to_period("M").astype(str)
    for t in ("tmax", "tmin"):
        cols = [f"{m}_{t}_c" for m in MODELS if m != "ecmwf_aifs025_single"]
        w[f"{t}_mean"] = w[cols].mean(axis=1)
        w[f"{t}_sd"] = w[cols].std(axis=1)
    w["rng_mean"] = w.tmax_mean - w.tmin_mean
    return w.sort_values("valid_at").reset_index(drop=True)


def features(target):
    cols = [f"{m}_{target}_c" for m in MODELS] + [f"{target}_mean", f"{target}_sd",
            "rng_mean", "doy_s", "doy_c", "best_match_precip_mm", "ecmwf_ifs025_precip_mm"]
    return cols


def ridge_fit_predict(Xtr, ytr, Xte, lam=5.0):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A = (Xtr - mu) / sd
    A = np.c_[np.ones(len(A)), A]
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ ytr)
    return np.c_[np.ones(len(Xte)), np.clip((Xte - mu) / sd, -5, 5)] @ w


def run(lead, target, since="0000"):
    arch, obs = load()
    w = wide(arch, obs, lead)
    y = w[f"obs_{target}"].values
    cols = features(target)
    X = w[cols].copy()
    X = X.fillna(X.median())  # missing model columns (e.g. AIFS before 2025-02) -> median
    base = w["best_match_%s_c" % target].values
    out = {k: np.full(len(w), np.nan) for k in ("raw", "mean", "ridge", "lgb", "q10", "q90")}
    months = sorted(w.month.unique())
    for m in months:
        te = (w.month == m).values
        tr = (w.valid_at < w.valid_at[te].min()).values
        if tr.sum() < MIN_TRAIN_DAYS:
            continue
        out["raw"][te] = base[te]
        out["mean"][te] = w[f"{target}_mean"].values[te]
        # model the residual against the multi-model mean
        r = y - w[f"{target}_mean"].values
        Xtr, Xte = X[tr].values, X[te].values
        out["ridge"][te] = w[f"{target}_mean"].values[te] + ridge_fit_predict(Xtr, r[tr], Xte)
        p = dict(n_estimators=250, learning_rate=0.03, num_leaves=6, min_child_samples=20,
                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, verbose=-1)
        g = lgb.LGBMRegressor(objective="l1", **p).fit(Xtr, r[tr])
        out["lgb"][te] = w[f"{target}_mean"].values[te] + g.predict(Xte)
        for q, k in ((0.1, "q10"), (0.9, "q90")):
            gq = lgb.LGBMRegressor(objective="quantile", alpha=q, **p).fit(Xtr, r[tr])
            out[k][te] = w[f"{target}_mean"].values[te] + gq.predict(Xte)
    ok = ~np.isnan(out["lgb"]) & ~np.isnan(y) & (w.valid_at >= since).values
    res = {k: float(np.mean(np.abs(out[k][ok] - y[ok]))) for k in ("raw", "mean", "ridge", "lgb")}
    res["n"] = int(ok.sum())
    res["cover80"] = float(np.mean((y[ok] >= out["q10"][ok]) & (y[ok] <= out["q90"][ok])))
    res["from"], res["to"] = w.valid_at[ok].min(), w.valid_at[ok].max()
    return res


if __name__ == "__main__":
    since = sys.argv[1] if len(sys.argv) > 1 else "0000"  # e.g. 2025-10-01 to match MTR v1 window
    for t in ("tmax", "tmin"):
        for lead in (1, 2, 3):
            r = run(lead, t, since)
            print(t, f"D+{lead}", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
