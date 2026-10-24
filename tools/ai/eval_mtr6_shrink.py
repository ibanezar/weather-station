#!/usr/bin/env python3
"""
Poskus nad MTR v1 (24. 10. 2026): ali krčenje popravka po režimu noči zmanjša napako?

  eval_mtr6_shrink.py V1_CACHE.json [since=2025-10-01] [warm=2025-04-01]

Ideja (docs/model-recica.md, /trendi/): v dnevih »vmes« je Tmin slabši od Open-Meteo, torej popravek tam
škoduje. Namesto novih značilk (te so 23. 10. padle v šum) popravek MTR − Open-Meteo pomnožimo z w ≤ 1,
naučenim po `night_regime` (clear_calm / overcast / mixed, ki ga napoved že izračuna iz napovedane
oblačnosti in vetra, torej brez uhajanja):  pred' = om + w · (pred − om).

Pošteno ločeno učenje w: model se uči walk-forward po mesecih od `warm` (iz podatkov pred testnim mesecem),
w za testni mesec se izbere NA PRETEKLIH izven-vzorčnih napovedih (mesecev od `warm` do pred testnim) kot
tisti iz mreže 0,0…1,2, ki minimizira MAE v razredu. Vzorčne (in-sample) napovedi bi dale w ≈ 1 (prilega).
Dodatno: razredi z manj kot MIN_CLASS_DAYS dnevi preteklih napovedi dobijo w = 1 (brez krčenja).
Produkcijske zastavice, pravi `previous_dayN`, uparjen 7-dnevni blokovni bootstrap kot eval_mtr3.py.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import train_recica_mos as t   # noqa: E402
import eval_mtr3 as e3         # noqa: E402

GRID = [round(0.1 * i, 1) for i in range(0, 13)]
MIN_CLASS_DAYS = 30


def regime_of(f):
    return t.night_regime(f["cloud_n"], f["wind_n"])


def learn_w(past):
    """{razred: w} iz preteklih izven-vzorčnih napovedi [(regime, pred, obs, om)]."""
    out = {}
    for rg in t.REGIMES:
        rows = [(p, o, m) for r, p, o, m in past if r == rg]
        if len(rows) < MIN_CLASS_DAYS:
            out[rg] = 1.0
            continue
        best = min(GRID, key=lambda w: sum(abs(m + w * (p - m) - o) for p, o, m in rows))
        out[rg] = best
    return out


def shrink_walk(preds, since):
    """preds = [(date, regime, pred, obs, om)] urejene po datumu → seznam (date, pred_shr, obs, om, w)."""
    out = []
    months = sorted({d[:7] for d, *_ in preds})
    for tm in [m for m in months if m >= since[:7]]:
        past = [(r, p, o, m) for d, r, p, o, m in preds if d[:7] < tm]
        w = learn_w(past)
        for d, r, p, o, m in preds:
            if d[:7] == tm:
                out.append((d, m + w[r] * (p - m), o, m, w[r]))
    return out


def main():
    cache = json.load(open(sys.argv[1]))
    since = sys.argv[2] if len(sys.argv) > 2 else "2025-10-01"
    warm = sys.argv[3] if len(sys.argv) > 3 else "2025-04-01"
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
            fmap = {s["date"]: s["f"] for s in smp}
            base = e3.walk(smp, tg, warm, **kw)             # od `warm`: izven-vzorčne napovedi
            preds = [(d, regime_of(fmap[d]), p, o, om) for d, p, o, om, _sd, _f in base]
            sh = shrink_walk(preds, since)
            b = {d: (p, o, om) for d, _r, p, o, om in preds}
            days = [x[0] for x in sh]
            eb = np.array([abs(b[d][0] - b[d][1]) for d in days])
            ec = np.array([abs(x[1] - x[2]) for x in sh])
            mean, (lo, hi) = e3.boot(eb - ec)
            flag = "REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum"
            ws = {rg: sorted({x[4] for x in sh if regime_of(fmap[x[0]]) == rg}) for rg in t.REGIMES}
            n_by = {rg: sum(1 for x in sh if regime_of(fmap[x[0]]) == rg) for rg in t.REGIMES}
            print(f"{tg} D+{lead} n={len(days)} MAE base={eb.mean():.3f} shrink={ec.mean():.3f} "
                  f"(om {np.mean([abs(x[3] - x[2]) for x in sh]):.3f}) "
                  f"diff={mean:+.3f} CI[{lo:+.3f},{hi:+.3f}] {flag}  dni po razredu {n_by}  w {ws}", flush=True)


if __name__ == "__main__":
    main()
