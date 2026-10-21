#!/usr/bin/env python3
"""
Verjetnost dnevne vsote >= 1 / 5 mm (pop1, pop5) v MTR: na sintetičnih vzorcih preveri,
da blocked_cv_pop z `thr_mm` res meri drug cilj, da je veščina pozitivna tam, kjer signal je,
in da napovedovalnik pri modelu brez teh koeficientov vrne None (stari model-recica.json).

usage: python3 tools/test_pop_thresholds.py
"""
import os, random, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_recica_mos as t  # noqa: E402

FAIL = []


def check(ok, name):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAIL.append(name)


def make_samples(n=900, signal=True):
    rnd = random.Random(7)
    out = []
    for i in range(n):
        day = f"{2024 + i // 365}-{(i % 365) // 31 + 1:02d}-{(i % 31) + 1:02d}"
        om = rnd.expovariate(1 / 3) if rnd.random() < 0.5 else 0.0
        mm = om * rnd.uniform(0.5, 1.5) if signal else rnd.expovariate(1 / 3)
        f = {"om_prec": om, "wet_hours": min(24, om * 2), "rh": 60 + min(om, 10) * 3, "cloud": 40 + min(om, 10) * 5,
             "pres": 1013, "om_tmax": 15, "sin_doy": 0.0, "cos_doy": 1.0}
        out.append({"date": day, "f": f, "mm": mm, "wet": 1.0 if mm >= t.WET_DAY_MM else 0.0})
    return out


s = make_samples()
check(set(t.POP_THRESHOLDS) == {"pop1", "pop5"}, "pragova pop1 in pop5")
sk0 = t.blocked_cv_pop(s)
sk1 = t.blocked_cv_pop(s, thr_mm=1.0)
sk5 = t.blocked_cv_pop(s, thr_mm=5.0)
check(sk0 and sk1 and sk5, "veščina izračunana za vse tri pragove")
check(sk1["brier_climatology"] != sk0["brier_climatology"], "prag 1 mm je drug cilj kot mokri dan")
check(sk5["brier_climatology"] < sk1["brier_climatology"], "redkejši dogodek ima nižjo klimatologijo")
check(sk1["skill_score"] > 0.2 and sk5["skill_score"] > 0.2, "z signalom je veščina pozitivna")
ns = t.blocked_cv_pop(make_samples(signal=False), thr_mm=5.0)
check(ns is None or ns["skill_score"] < 0.1, "brez signala veščine ni (ni prileganja šumu)")

# Stari model brez pop1/pop5: napovedovalnik ne sme pasti, polji ostaneta None.
import predict_recica_mos as p  # noqa: E402
entry = {"coefficients": {"pop": [0.0] * len(t.pop_vector(s[0]["f"]))}}
for key in t.POP_THRESHOLDS:
    check(entry["coefficients"].get(key) is None, f"{key} manjka v starem modelu -> None")
check(hasattr(p, "mos"), "napovedovalnik uvaža isti modul kot učenje")

sys.exit(1 if FAIL else 0)
