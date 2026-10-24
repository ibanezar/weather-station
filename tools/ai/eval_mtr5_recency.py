#!/usr/bin/env python3
"""
Poskus nad MTR v1 (24. 10. 2026): ali eksponentna utež novejših dni izboljša Tmax/Tmin?

  eval_mtr5_recency.py V1_CACHE.json [since=2025-10-01]

Zakaj: okolica postaje se spreminja (rast drevja, gradnja), senzorji se starajo; če se nočni ostanek
skozi leta premika, so starejši dnevi slabši učitelj. Isti walk-forward po mesecih, ista lambda iz
notranje validacije (nepopravljena za uteži: pri utežitvi se efektivna velikost vzorca zmanjša, zato je
regularizacija relativno močnejša), produkcijske zastavice (tmin = bias + cond, tmax = multi), enaki dnevi
in uparjen 7-dnevni blokovni bootstrap kot v eval_mtr3.py. Podatki so PRAVI `previous_dayN` (brez uhajanja).

Utež dneva = 0,5 ** (starost / polčas), starost = dni od učnega dne do prvega dne testnega meseca.
`base` = enakomerne uteži (produkcija).
"""
import datetime as dt
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import train_recica_mos as t   # noqa: E402
import eval_mtr3 as e3         # noqa: E402

HALFLIVES = {"base": None, "hl365": 365, "hl180": 180, "hl90": 90}


def weights_for(train, test_month, halflife):
    if not halflife:
        return None
    t0 = dt.date.fromisoformat(test_month + "-01")
    return [0.5 ** ((t0 - dt.date.fromisoformat(s["date"])).days / halflife) for s in train]


def walk_w(samples, target, since, halflife, **kw):
    """[(date, pred, obs, om)] za mesece od `since`; učenje samo iz mesecev pred testnim."""
    months = sorted({s["date"][:7] for s in samples})
    out = []
    for tm in [m for m in months if m >= since[:7]]:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        if len(tr) < 100 or not te:
            continue
        lam = t.select_lambda(tr, target, **kw)
        X = [t.temp_vector(s["f"], target, **kw) for s in tr]
        co = t.solve_ridge(X, [s[target] for s in tr], lam, weights_for(tr, tm, halflife))
        for s in te:
            out.append((s["date"], t.predict_linear(co, t.temp_vector(s["f"], target, **kw)),
                        s[target], s["f"]["om_" + target]))
    return out


def compare(res):
    """{ime: dict(n, mae, om, diff, lo, hi, flag)} proti `base` na skupnih dneh."""
    b = {r[0]: r for r in res["base"]}
    rows = {}
    for name, r in res.items():
        e = {x[0]: x for x in r}
        days = sorted(set(b) & set(e))
        if not days:
            continue
        eb = np.array([abs(b[d][1] - b[d][2]) for d in days])
        ec = np.array([abs(e[d][1] - e[d][2]) for d in days])
        mean, (lo, hi) = e3.boot(eb - ec)
        rows[name] = dict(n=len(days), mae=ec.mean(), om=np.mean([abs(b[d][3] - b[d][2]) for d in days]),
                          diff=mean, lo=lo, hi=hi,
                          flag="" if name == "base" else ("REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum"))
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
            res = {name: walk_w(smp, tg, since, hl, **kw) for name, hl in HALFLIVES.items()}
            for name, r in compare(res).items():
                print(f"{tg} D+{lead} {name:6s} n={r['n']} MAE={r['mae']:.3f} (om {r['om']:.3f}) "
                      f"diff={r['diff']:+.3f} CI[{r['lo']:+.3f},{r['hi']:+.3f}] {r['flag']}", flush=True)
            print()


if __name__ == "__main__":
    main()
