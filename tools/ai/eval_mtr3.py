#!/usr/bin/env python3
"""
Poskusi nad MTR v1 (23. 10. 2026): ali kaka dodatna značilka ali razredna obravnava dni
resnično izboljša Tmax/Tmin? Isti walk-forward po mesecih kot train_recica_mos (lambda iz
notranje validacije), primerjava z produkcijsko konfiguracijo na ISTIH dneh in uparjen
blokovni bootstrap (7-dnevni bloki).

  eval_mtr3.py V1_CACHE.json [since=2025-10-01]

V1_CACHE = izhod tools/ai/fetch_hourly_cache.py (prvi argument), {lead: rows}.
Produkcija (mos-train.yml): tmin = bias + cond, tmax = multi (--multi-tmax).
"""
import json, math, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import train_recica_mos as t   # noqa: E402

BLOCK, REPS = 7, 4000
rng = np.random.default_rng(7)


def sigm(x):
    return 1 / (1 + math.exp(-x))


def dewpoint(tc, rh):
    rh = max(1.0, min(100.0, rh))
    g = math.log(rh / 100) + 17.62 * tc / (243.12 + tc)
    return 243.12 * g / (17.62 - g)


# ── kandidati: dodatni stolpci k produkcijskemu vektorju ────────────────────────────────
def gate(f):
    """Mehka utež »jasna in mirna noč« (0..1)."""
    return sigm((40 - f["cloud_n"]) / 12) * sigm((2.5 - f["wind_n"]) / 0.9)


def x_regime(f, target):
    g = gate(f)
    tn = f["om_" + target]
    dp = dewpoint(tn, f["rh"])
    return [g, g * (tn - dp) / 5, g * f["om_tmin"] / 10, g * f["pres"] / 20 - g * 50.65]


def x_wet(f, target):
    wet = min(f["wet_hours"], 12) / 12
    dry = 1 - sigm((f["om_prec"] - 1) / 1.5)
    return [wet, wet * f["om_" + target] / 10, dry * gate(f)]


def x_dp(f, target):
    tn = f["om_" + target]
    dp = dewpoint(tn, f["rh"])
    return [(tn - dp) / 5, f["rh"] / 100 * gate(f)]


EXTRAS = {
    "base": None,
    "regime": x_regime,
    "wet": x_wet,
    "dp": x_dp,
    "regime+wet": lambda f, tg: x_regime(f, tg) + x_wet(f, tg),
}


def make_vec(extra):
    orig = t.temp_vector

    def tv(f, target, with_aifs=False, use_bias=False, use_cond=False, use_multi=False):
        v = orig(f, target, with_aifs, use_bias, use_cond, use_multi)
        return v + extra(f, target) if extra else v
    return tv


def walk(samples, target, since, **kw):
    """Vrne [(date, pred, obs, om, sd_in_fold)] za mesece od `since`."""
    months = sorted({s["date"][:7] for s in samples})
    out = []
    for tm in [m for m in months if m >= since[:7]]:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        if len(tr) < 100 or not te:
            continue
        lam = t.select_lambda(tr, target, **kw)
        X = [t.temp_vector(s["f"], target, **kw) for s in tr]
        co = t.solve_ridge(X, [s[target] for s in tr], lam)
        res = [t.predict_linear(co, x) - s[target] for x, s in zip(X, tr)]
        sd = float(np.std(res, ddof=1))
        for s in te:
            out.append((s["date"], t.predict_linear(co, t.temp_vector(s["f"], target, **kw)),
                        s[target], s["f"]["om_" + target], sd, s["f"]))
    return out


def boot(d):
    n = len(d)
    nb = int(np.ceil(n / BLOCK))
    st = rng.integers(0, n - BLOCK + 1, size=(REPS, nb))
    idx = (st[:, :, None] + np.arange(BLOCK)).reshape(REPS, -1)[:, :n]
    m = d[idx].mean(axis=1)
    return d.mean(), np.percentile(m, [2.5, 97.5])


def main():
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    hist = t.load_history()
    multi = t.load_multi_archive()
    rows = {l: t._rows_from_cache(cache[str(l)]) for l in t.LEADS}
    bias = t.build_bias_series(rows[1], hist)
    base_t = t.temp_vector
    for tg in ("tmax", "tmin"):
        for lead in t.LEADS:
            smp = t.build_samples(rows[lead], hist, lead, bias, None, multi)
            if tg == "tmax":
                smp = [s for s in smp if s["f"].get("mm")]
            kw = dict(use_bias=(tg == "tmin"), use_cond=(tg == "tmin"), use_multi=(tg == "tmax"))
            res = {}
            for name, ex in EXTRAS.items():
                t.temp_vector = make_vec(ex)
                try:
                    res[name] = walk(smp, tg, since, **kw)
                finally:
                    t.temp_vector = base_t
            b = {r[0]: r for r in res["base"]}
            for name, r in res.items():
                e = {x[0]: x for x in r}
                days = sorted(set(b) & set(e))
                eb = np.array([abs(b[d][1] - b[d][2]) for d in days])
                ec = np.array([abs(e[d][1] - e[d][2]) for d in days])
                mean, (lo, hi) = boot(eb - ec)
                flag = "" if name == "base" else ("REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum")
                print(f"{tg} D+{lead} {name:11s} n={len(days)} MAE={ec.mean():.3f} (om {np.mean([abs(b[d][3]-b[d][2]) for d in days]):.3f}) "
                      f"diff={mean:+.3f} CI[{lo:+.3f},{hi:+.3f}] {flag}", flush=True)


if __name__ == "__main__":
    main()
