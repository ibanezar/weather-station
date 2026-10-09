#!/usr/bin/env python3
"""
tools/backtest_lag_window.py — ali okno sprožilnega dežja loči opažanja vrste od običajne glive?

Preizkus predlaganega zamika (npr. lisička 8–16 → 4–14 dni) na istih opažanjih iNaturalist kot
`study_inat_lag.py` (isti predpomnilnik). Za vsako opažanje vrste in vsako opažanje katerekoli glive (kontrola)
izračuna točno tisto ocene sprožilnega dežja, ki jo v modelu računa `gobe_model` (`rain_lag_window` +
`rain_score`, prag = rain_7d_min × dolžina okna / 7). Mera je AUC: verjetnost, da ima naključno opažanje vrste
višjo oceno dežja kot naključno opažanje kontrole (0,5 = brez ločitve).

Ni indeks v celoti (temperature, vlage, geologije ta preizkus ne vidi) — preverja samo dež-sprožilec in
okno, ki se spreminja. Rezultat je smer, ne dokaz.

Usage:
    python3 tools/backtest_lag_window.py --cache-dir DIR --tag siroko --species cantharellus_cibarius [--months 8,9,10,11]
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gobe_model as gm  # noqa: E402
import study_inat_lag as st  # noqa: E402

CANDIDATES = [(8, 16), (6, 14), (4, 14), (3, 10), (2, 8), (5, 12)]


def load(cache, tag, key):
    sfx = f"-{tag}" if tag else ""
    obs = json.load(open(os.path.join(cache, f"{key}{sfx}.json"), encoding="utf-8"))
    ref = json.load(open(os.path.join(cache, f"fungi{sfx}.json"), encoding="utf-8"))
    rain_files = [f for f in os.listdir(cache) if f.startswith(f"rain{sfx}-")]
    rain = json.load(open(os.path.join(cache, sorted(rain_files)[-1]), encoding="utf-8"))
    return obs, ref, rain


def scores(obs, rain, lag, rain_7d_min, cfg):
    out = []
    series_cache = {}
    for day, lat, lon in obs:
        c = st.cell_of(lat, lon)
        key = f"{c[0]},{c[1]}"
        if key not in rain:
            continue
        if key not in series_cache:
            days = sorted(rain[key])
            series_cache[key] = ({d: i for i, d in enumerate(days)}, {"precip": [rain[key][d] for d in days]})
        idx, series = series_cache[key]
        i = idx.get(day)
        if i is None:
            continue
        trig_days = lag[1] - lag[0] + 1
        mm = gm.rain_lag_window(series, i, lag[0], lag[1])
        f, _ = gm.rain_score(mm, rain_7d_min * trig_days / gm.TRIGGER_NORM_DAYS, cfg)
        out.append(f)
    return out


def auc(a, b):
    """P(a > b) + 0,5 P(a = b), a = ocene vrste, b = kontrola."""
    if not a or not b:
        return None
    bs = sorted(b)
    import bisect
    tot = 0.0
    for x in a:
        lo, hi = bisect.bisect_left(bs, x), bisect.bisect_right(bs, x)
        tot += lo + 0.5 * (hi - lo)
    return tot / (len(a) * len(bs))


def main():
    a = sys.argv
    cache = a[a.index("--cache-dir") + 1]
    tag = a[a.index("--tag") + 1] if "--tag" in a else ""
    key = a[a.index("--species") + 1]
    rules = gm.load_rules()
    sp = next(s for s in rules["species"] if s["id"] == key)
    cfg = rules["scoring"]["rain"]
    obs, ref, rain = load(cache, tag, key)
    end = max(max(v) for v in rain.values())
    obs = [o for o in obs if o[0] <= end]
    ref = [o for o in ref if o[0] <= end]
    print(f"{sp['name_sl']}: n={len(obs)}, kontrola n={len(ref)}, rain_7d_min={sp['rain_7d_min']}, "
          f"model {sp['fruiting_lag_days']['min']}–{sp['fruiting_lag_days']['max']}")
    print(f"{'okno':>8} {'AUC':>7} {'povpr. ocena vrste':>20} {'kontrole':>10}")
    for lag in CANDIDATES:
        sa = scores(obs, rain, lag, float(sp["rain_7d_min"]), cfg)
        sb = scores(ref, rain, lag, float(sp["rain_7d_min"]), cfg)
        mark = "  ← model" if lag == (sp["fruiting_lag_days"]["min"], sp["fruiting_lag_days"]["max"]) else ""
        print(f"{lag[0]:>3}–{lag[1]:<4} {auc(sa, sb):7.3f} {sum(sa) / len(sa):20.3f} {sum(sb) / len(sb):10.3f}{mark}")


if __name__ == "__main__":
    main()
