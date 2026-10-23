#!/usr/bin/env python3
"""
Pas negotovosti po režimu noči (23. 10. 2026): ali sd ostankov, ločen po razredu
(clear_calm / overcast / mixed iz predict_recica_mos.night_regime), da boljšo pokritost
P10-P90 in boljši p_frost kot ena sama sd? Walk-forward po mesecih, sd samo iz učnih dni.

  eval_mtr_sd.py V1_CACHE.json [since=2025-10-01]
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr3 as e3   # noqa: E402
t = e3.t
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import predict_recica_mos as p   # noqa: E402

Z90 = 1.2816


def cls(f):
    return p.night_regime(f["cloud_n"], f["wind_n"])


def run(smp, tg, since, kw, min_n=40):
    months = sorted({s["date"][:7] for s in smp})
    rows = []
    for tm in [m for m in months if m >= since[:7]]:
        tr = [s for s in smp if s["date"][:7] < tm]
        te = [s for s in smp if s["date"][:7] == tm]
        if len(tr) < 100 or not te:
            continue
        lam = t.select_lambda(tr, tg, **kw)
        X = [t.temp_vector(s["f"], tg, **kw) for s in tr]
        co = t.solve_ridge(X, [s[tg] for s in tr], lam)
        res = [(t.predict_linear(co, x) - s[tg], cls(s["f"])) for x, s in zip(X, tr)]
        g = float(np.std([r for r, _ in res], ddof=1))
        by = {}
        for c in ("clear_calm", "overcast", "mixed"):
            v = [r for r, k in res if k == c]
            by[c] = float(np.std(v, ddof=1)) if len(v) >= min_n else g
        for s in te:
            pr = t.predict_linear(co, t.temp_vector(s["f"], tg, **kw))
            c = cls(s["f"])
            rows.append((s["date"], c, pr, s[tg], g, by[c]))
    return rows


def main():
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    multi = t.load_multi_archive()
    rows = {l: t._rows_from_cache(cache[str(l)]) for l in t.LEADS}
    bias = t.build_bias_series(rows[1], hist)
    for tg in ("tmax", "tmin"):
        for lead in t.LEADS:
            smp = t.build_samples(rows[lead], hist, lead, bias, None, multi)
            if tg == "tmax":
                smp = [s for s in smp if s["f"].get("mm")]
            kw = dict(use_bias=(tg == "tmin"), use_cond=(tg == "tmin"), use_multi=(tg == "tmax"))
            r = run(smp, tg, since, kw)
            for name, ix in (("global", 4), ("regime", 5)):
                cov, ls, per = [], [], {}
                for x in r:
                    sd = x[ix] * p.SD_OOS_K
                    ok = abs(x[3] - x[2]) <= Z90 * sd
                    cov.append(ok)
                    per.setdefault(x[1], []).append(ok)
                    s2 = (x[ix]) ** 2
                    ls.append(0.5 * math.log(2 * math.pi * s2) + (x[3] - x[2]) ** 2 / (2 * s2))
                pc = " ".join(f"{k[:5]}={100*np.mean(v):.0f}%(n{len(v)})" for k, v in sorted(per.items()))
                line = f"{tg} D+{lead} sd={name:6s} pokritost={100*np.mean(cov):.1f}% {pc} logscore={np.mean(ls):.3f}"
                if tg == "tmin":
                    pf = [(0.5 * (1 + math.erf((0 - x[2]) / (p.FROST_SD_K * x[ix]) / math.sqrt(2))), 1.0 if x[3] <= 0 else 0.0) for x in r]
                    line += f" frostBrier={np.mean([(a-b)**2 for a,b in pf]):.4f} (zmrzali {int(sum(b for _,b in pf))})"
                print(line, flush=True)


if __name__ == "__main__":
    main()
