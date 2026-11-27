#!/usr/bin/env python3
"""tools/test_melt_precip.py — prototip ločevanja taljenja snega v dežemeru od padavin."""
import datetime as dt, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import melt_precip as M  # noqa: E402

FAILS = []
def check(ok, name):
    if not ok:
        FAILS.append(name); print("  ✗", name)

def series(start, rows):
    """rows = [(t, p, solar)] po zaporednih urah od `start`."""
    t0 = dt.datetime.fromisoformat(start)
    return {t0 + dt.timedelta(hours=i): {"t": t, "p": p, "s": s} for i, (t, p, s) in enumerate(rows)}

# --- 26. 11. 2026 (pravi podatki): nočno sneženje ob 0,4–1,8 °C je padavina, popoldansko »padanje« brez
# padavin pri 0,7 °C in soncu pa taljenje snega, ki je čez jutro obležal v lijaku.
real = series("2026-11-25T20:00", [
    (3.0, 1.0, 0), (3.0, 0.0, 0), (2.6, 0.8, 0), (1.8, 2.0, 0), (1.4, 1.1, 0), (1.0, 2.0, 0),
    (0.7, 2.0, 0), (0.6, 0.5, 0), (0.5, 0.3, 0), (0.4, 0.5, 0),                       # do 05:00
    (0.1, 0.0, 0), (-0.1, 0.0, 0), (-0.1, 0.0, 1.6), (0.0, 0.0, 16.4), (0.4, 0.0, 27.3),
    (0.5, 0.0, 28.3), (1.1, 0.0, 73.2), (0.7, 0.0, 112.9),                            # 06:00–13:00
    (0.7, 1.0, 69.4), (0.6, 0.5, 20.8), (0.3, 0.0, 1.1), (0.2, 0.2, 0.0),             # 14:00–17:00
])
k = M.classify(real)
d = dt.datetime
check(k[d(2026, 11, 26, 1)] == "precip" and k[d(2026, 11, 25, 23)] == "precip", "nočni moker sneg/dež = padavine")
check(k[d(2026, 11, 26, 14)] == "melt" and k[d(2026, 11, 26, 15)] == "melt", "popoldne po jutru ob 0 °C = taljenje")
check(k[d(2026, 11, 26, 17)] == "melt", "rep serije (vrzel 1 ura) je isto taljenje")
dd = M.daily(real, k)
check(dd["2026-11-26"]["melt"] == 1.7, "dnevni seštevek taljenja")

# --- jutranje ivje: osamljen drobec ob prvem soncu po mrzli noči
frost = series("2026-11-14T22:00", [(-1.2, 0, 0), (-1.6, 0, 0)] + [(-2.5, 0, 0)] * 6 + [(-2.1, 0, 8.3), (-1.6, 0, 20.4),
                                                                                       (-0.9, 0, 64.9), (0.3, 0.3, 137.0)])
check(M.classify(frost)[d(2026, 11, 15, 9)] == "melt", "ivje ob soncu = taljenje")

# --- toplo: dež ob 5 °C ni nikoli taljenje, tudi če je bila noč mrzla
warm = series("2026-04-10T00:00", [(-1.0, 0, 0)] * 6 + [(5.0, 3.0, 0), (5.0, 2.0, 120.0)])
check(set(M.classify(warm).values()) == {"precip"}, "dež pri ≥ 1,5 °C = padavine")

# --- lijak ni bil hladen: drobna megla/rosenje ob 0,8 °C po topli noči
mild = series("2026-10-27T00:00", [(1.4, 0, 0), (0.9, 0, 0), (0.7, 0, 0), (0.7, 0, 0), (0.8, 0.2, 0)])
check(M.classify(mild)[d(2026, 10, 27, 4)] == "precip", "brez hladne zgodovine ni taljenja")

# --- ponoči pri ledišču, osamljen drobec = negotovo
night = series("2026-11-08T21:00", [(1.2, 0, 0), (0.7, 0, 0), (1.3, 0, 0), (0.6, 0, 0), (0.4, 0, 0), (-0.0, 0, 0),
                                    (-0.5, 0.3, 0)])
check(M.classify(night)[d(2026, 11, 9, 3)] == "uncertain", "nočni drobec ob ledišču = negotovo")

# --- ni padavin: prazen izhod; manjkajoča temperatura ne podre izračuna
check(M.classify(series("2026-01-01T00:00", [(0.0, 0.0, 0)] * 5)) == {}, "brez padavin ni razredov")
check(M.classify(series("2026-01-01T00:00", [(None, 0.4, None)])) == {d(2026, 1, 1): "precip"}, "brez temperature = padavine")

print("OK" if not FAILS else f"{len(FAILS)} FAIL"); sys.exit(1 if FAILS else 0)
