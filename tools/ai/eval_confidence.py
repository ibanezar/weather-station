#!/usr/bin/env python3
"""
Does model disagreement predict MTR v1's error? (basis for a user-facing
"zaupanje" indicator). Out-of-sample v1 errors by tercile of the multi-model
spread of the target (Tmax/Tmin; IFS, GFS, ICON, ARPEGE, best_match).
usage: eval_confidence.py HOURLY_CACHE.json [since]
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr_calibration as cal   # noqa: E402
import eval_mtr2 as e1               # noqa: E402
t = cal.t

if __name__ == "__main__":
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    arch, obs = e1.load()
    for tg in ("tmax", "tmin"):
        for lead in (1, 2, 3):
            smp = t.build_samples(t._rows_from_cache(cache[str(lead)]), hist, lead)
            v = cal.walk(smp, tg, since)[["date", "pred", "obs"]].rename(columns={"date": "valid_at"})
            w = e1.wide(arch, obs, lead)[["valid_at", f"{tg}_sd"]]
            m = v.merge(w, on="valid_at").dropna()
            m["ae"] = (m.obs - m.pred).abs()
            rho = m[[f"{tg}_sd", "ae"]].corr(method="spearman").iloc[0, 1]
            q = pd.qcut(m[f"{tg}_sd"], 3, labels=["low", "mid", "high"])
            g = m.groupby(q, observed=True).agg(n=("ae", "size"), spread=(f"{tg}_sd", "mean"),
                                                 mae=("ae", "mean"),
                                                 within1=("ae", lambda x: (x <= 1).mean()))
            print(f"\n{tg} D+{lead}: spearman(spread, |err|)={rho:+.2f}")
            print(g.round(2).to_string())
