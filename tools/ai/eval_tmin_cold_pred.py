#!/usr/bin/env python3
"""
Pristranskost Tmin po pasu NAPOVEDANE vrednosti (ne izmerjene): izbira po izmerjeni vrednosti
izbere dneve s hladno napako in precenjuje pristranskost pri zmrzali.

  eval_tmin_cold_pred.py V1_CACHE.json

V1_CACHE = izhod tools/ai/fetch_hourly_cache.py (prvi argument), {lead: rows}.
Isti walk-forward po mesecih (od 2025-10) in produkcijske zastavice Tmin
(--use-bias-tmin --use-cond-tmin) kot eval_mtr3.py.

Rezultat 23. 10. 2026: pri napovedi pod 0 °C je pristranskost -0,1..+0,2 °C (D+3 pod -2 °C: +1,0); pas 0..2 °C je
skoraj 50:50 za zmrzal (23-29 od 53-63 noči), kar že odraža p_frost.
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
    r = e3.walk(smp, "tmin", "2025-10-01", use_bias=True, use_cond=True)
    print(f"D+{lead}")
    for lo, hi in ((-99, -2), (-2, 0), (0, 2), (2, 5), (5, 99)):
        v = [(pr - ob, ob) for d, pr, ob, om, sd, f in r if lo <= pr < hi]
        if len(v) < 5: continue
        e = np.array([x[0] for x in v])
        print(f"  napoved Tmin [{lo:>3},{hi:>3}) n={len(v):3d} bias={e.mean():+.2f} MAE={np.abs(e).mean():.2f} dejansko<=0: {sum(1 for x in v if x[1]<=0)}")
