#!/usr/bin/env python3
"""tools/test_mtr_extras.py — verjetnost zmrzali in režim noči pri napovedi MTR."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict_recica_mos as p  # noqa: E402

FAILS = []
def check(ok, name):
    if not ok:
        FAILS.append(name); print("  ✗", name)

check(abs(p.frost_probability(0.0, 1.5) - 0.5) < 1e-9, "p=0.5 at tmin=0")
check(p.frost_probability(5.0, 1.5) < 0.01, "warm night ~0")
check(p.frost_probability(-5.0, 1.5) > 0.99, "hard frost ~1")
check(p.frost_probability(-1.0, 1.5) > p.frost_probability(1.0, 1.5), "monotone in tmin")
check(p.frost_probability(1.0, 3.0) > p.frost_probability(1.0, 1.0), "wider sd -> more uncertainty above 0")
check(p.frost_probability(None, 1.5) is None and p.frost_probability(1.0, 0) is None, "missing inputs -> None")
check(p.night_regime(10, 2) == "clear_calm", "clear+calm")
check(p.night_regime(10, 8) == "mixed", "clear but windy (>=8) is not calm")
check(p.night_regime(80, 2) == "overcast", "overcast")
check(p.night_regime(50, 2) == "mixed", "partly cloudy")
print("OK" if not FAILS else f"{len(FAILS)} FAIL"); sys.exit(1 if FAILS else 0)
