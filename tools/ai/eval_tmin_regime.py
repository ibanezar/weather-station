#!/usr/bin/env python3
"""
Tmin po razredu noči (jasna in mirna / vmes / oblačna): MAE in pristranskost MTR
proti Open-Meteo, zmrzalne noči posebej in pristranskost jasnih noči po mesecih.

  eval_tmin_regime.py V1_CACHE.json

V1_CACHE = izhod tools/ai/fetch_hourly_cache.py (prvi argument), {lead: rows}.
Isti walk-forward po mesecih (od 2025-10) in produkcijske zastavice Tmin
(--use-bias-tmin --use-cond-tmin) kot eval_mtr3.py.

Rezultat 23. 10. 2026: jasne in mirne noči so najboljši razred (MAE 1,0-1,2 °C, pristranskost ~0), najslabši so
dnevi »vmes«. Zmrzalne noči (izbira po izmerjeni vrednosti) imajo pristranskost +0,9..+1,2 °C, a je to deloma
artefakt izbire; glej eval_tmin_cold_pred.py.
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eval_mtr3 as e3   # noqa: E402
t = e3.t


cache = json.load(open(sys.argv[1]))
hist = t.load_history()
multi = t.load_multi_archive()
rows = {l: t._rows_from_cache(cache[str(l)]) for l in t.LEADS}
bias = t.build_bias_series(rows[1], hist)
for lead in t.LEADS:
    smp = t.build_samples(rows[lead], hist, lead, bias, None, multi)
    r = e3.walk(smp, "tmin", "2025-10-01", use_bias=True, use_cond=True, use_multi=False)
    by = {}
    for d, pr, ob, om, sd, f in r:
        c = t.night_regime(f["cloud_n"], f["wind_n"])
        by.setdefault(c, []).append((pr - ob, om - ob, ob, f))
        if ob <= 0: by.setdefault("zmrzal(<=0)", []).append((pr - ob, om - ob, ob, f))
    print(f"D+{lead}")
    for c in ("clear_calm", "mixed", "overcast", "zmrzal(<=0)"):
        v = by.get(c, [])
        if not v: continue
        em = np.array([x[0] for x in v]); eo = np.array([x[1] for x in v])
        print(f"  {c:12s} n={len(v):3d} MTR MAE={np.abs(em).mean():.2f} bias={em.mean():+.2f} | OM MAE={np.abs(eo).mean():.2f} bias={eo.mean():+.2f} | MTR>2°C napaka: {100*np.mean(np.abs(em)>2):.0f}%")
    # po mesecih za clear_calm
    cc = [(d, pr - ob) for d, pr, ob, om, sd, f in r if t.night_regime(f['cloud_n'], f['wind_n']) == "clear_calm"]
    m = {}
    for d, e in cc: m.setdefault(d[:7], []).append(e)
    print("  clear_calm bias po mesecih:", " ".join(f"{k[2:]}:{np.mean(v):+.1f}({len(v)})" for k, v in sorted(m.items())))
