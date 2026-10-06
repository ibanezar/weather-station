#!/usr/bin/env python3
"""
Offline audit of MTR v1 (no production changes):
  A. interval calibration: does the card's band (pred +- 1.2816 * in-sample SD,
     labelled P10-P90) cover ~80 % of out-of-sample days?
  B. wet-day probability: v1 logistic vs LightGBM (multi-model) vs climatology
     (walk-forward Brier), plus a reliability table.
  C. where does v1 lose: out-of-sample error by month, by weather regime, and
     the worst days.
Uses the real v1 code (train_recica_mos) for features, ridge and lambda choice.

usage: eval_mtr_calibration.py HOURLY_CACHE.json [since]
"""
import json, os, sys, math
import numpy as np, pandas as pd
import lightgbm as lgb

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "ai"))
import train_recica_mos as t   # noqa: E402
import eval_mtr2 as e1         # noqa: E402

Z80 = 1.2816


def walk(samples, target, since):
    """Out-of-sample v1 predictions with the sd the card would have shown."""
    months = sorted({s["date"][:7] for s in samples})
    rows = []
    for tm in months[t.MIN_TRAIN_MONTHS:]:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        lam = t.select_lambda(tr, target)
        X = [t.temp_vector(s["f"], target) for s in tr]
        c = t.solve_ridge(X, [s[target] for s in tr], lam)
        sd = t.residual_sd(tr, c, target)
        tr_res = [t.predict_linear(c, x) - s[target] for x, s in zip(X, tr)]
        for s in te:
            if s["date"] < since:
                continue
            p = t.predict_linear(c, t.temp_vector(s["f"], target))
            rows.append({"date": s["date"], "pred": p, "obs": s[target], "sd": sd,
                         "om": s["f"]["om_" + target], "cloud_n": s["f"]["cloud_n"],
                         "wind_n": s["f"]["wind_n"], "prec": s["f"]["om_prec"],
                         "rad": s["f"]["rad"], "train_q": np.quantile(np.abs(tr_res), 0.8)})
    return pd.DataFrame(rows)


def part_a(samples_by_lead, since):
    print("\n== A. Interval calibration (nominal P10-P90 = 80 %) ==")
    for tg in ("tmax", "tmin"):
        for lead, smp in samples_by_lead.items():
            d = walk(smp, tg, since)
            err = d.obs - d.pred
            cov = np.mean(np.abs(err) <= Z80 * d.sd)
            oos_sd = float(np.std(err, ddof=1))
            # split-conformal style: 80th percentile of |err| from earlier folds
            cov_c = np.mean(np.abs(err) <= d.train_q)
            print(f"{tg} D+{lead}: n={len(d)} card_sd={d.sd.mean():.2f} oos_sd={oos_sd:.2f} "
                  f"coverage(card)={cov:.1%} coverage(80th pct |err| of train)={cov_c:.1%} "
                  f"bias={err.mean():+.2f}")


def part_c(samples_by_lead, since):
    print("\n== C. Where v1 loses (D+1, out-of-sample) ==")
    for tg in ("tmax", "tmin"):
        d = walk(samples_by_lead[1], tg, since)
        d["ae_v1"], d["ae_om"] = (d.obs - d.pred).abs(), (d.obs - d.om).abs()
        d["month"] = d.date.str[:7]
        m = d.groupby("month")[["ae_v1", "ae_om"]].mean().round(2)
        m["bias_v1"] = (d.pred - d.obs).groupby(d.month).mean().round(2)
        print(f"\n{tg} by month (MAE v1 / raw OM / mean(pred-obs)):\n{m.to_string()}")
        d["regime"] = np.select(
            [d.prec >= 1, (d.cloud_n < 30) & (d.wind_n < 6), d.cloud_n > 70],
            ["wet", "clear+calm night", "overcast night"], "other")
        r = d.groupby("regime").agg(n=("ae_v1", "size"), v1=("ae_v1", "mean"), om=("ae_om", "mean"))
        r["bias_v1"] = (d.pred - d.obs).groupby(d.regime).mean()
        print(f"\n{tg} by regime:\n{r.round(2).to_string()}")
        w = d.assign(e=d.pred - d.obs).sort_values("ae_v1", ascending=False).head(8)
        print(f"\n{tg} worst days:\n{w[['date','pred','obs','om','cloud_n','wind_n','prec']].round(1).to_string(index=False)}")


def part_b(cache, since):
    print("\n== B. Wet-day probability, walk-forward (wet >= 0.2 mm) ==")
    arch, obs = e1.load()
    for lead in (1, 2, 3):
        smp = t.build_samples(t._rows_from_cache(cache[str(lead)]), t.load_history(), lead)
        w = e1.wide(arch, obs, lead)
        w["wet"] = (w.obs_p.fillna(0) >= t.WET_DAY_MM).astype(float)
        feat = {s["date"]: s["f"] for s in smp}
        w = w[w.valid_at.isin(feat)].reset_index(drop=True)
        v1x = np.array([t.pop_vector(feat[d]) for d in w.valid_at])
        mcols = [f"{m}_precip_mm" for m in e1.MODELS] + ["doy_s", "doy_c"]
        extra = pd.DataFrame(v1x[:, 1:], columns=[f"p{i}" for i in range(v1x.shape[1] - 1)])
        X = pd.concat([w[mcols], extra], axis=1)
        X["n_models_wet"] = (w[[f"{m}_precip_mm" for m in e1.MODELS]] >= 0.2).sum(axis=1)
        y = w.wet.values
        P = {k: np.full(len(w), np.nan) for k in ("clim", "v1", "lgb", "blend")}
        for mth in sorted(w.month.unique()):
            te = (w.month == mth).values
            tr = (w.valid_at < w.valid_at[te].min()).values
            if tr.sum() < 150:
                continue
            P["clim"][te] = y[tr].mean()
            co = t.solve_logistic([list(r) for r in v1x[tr]], list(y[tr]))
            P["v1"][te] = [t.predict_prob(co, list(r)) for r in v1x[te]]
            g = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, num_leaves=5, min_child_samples=25,
                                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0,
                                   verbose=-1).fit(X[tr].fillna(-1), y[tr])
            P["lgb"][te] = g.predict_proba(X[te].fillna(-1))[:, 1]
            P["blend"][te] = 0.5 * P["v1"][te] + 0.5 * P["lgb"][te]
        ok = ~np.isnan(P["lgb"]) & (w.valid_at >= since).values
        br = {k: float(np.mean((P[k][ok] - y[ok]) ** 2)) for k in P}
        print(f"D+{lead} n={ok.sum()} Brier: " + "  ".join(f"{k}={v:.3f}" for k, v in br.items()))
        if lead == 1:
            bins = pd.cut(pd.Series(P["v1"][ok]), [0, .1, .3, .5, .7, .9, 1.0])
            rel = pd.DataFrame({"p": P["v1"][ok], "y": y[ok]}).groupby(bins, observed=True).agg(
                n=("y", "size"), mean_pred=("p", "mean"), freq=("y", "mean")).round(2)
            print("v1 reliability D+1:\n" + rel.to_string())


if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    by_lead = {l: t.build_samples(t._rows_from_cache(cache[str(l)]), hist, l) for l in (1, 2, 3)}
    part_a(by_lead, since)
    part_b(cache, since)
    part_c(by_lead, since)
