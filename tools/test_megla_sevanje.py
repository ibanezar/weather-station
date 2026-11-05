#!/usr/bin/env python3
"""Osnovni preizkus analize »dvig megle po sevanju« (tools/ai/eval_megla_sevanje.py): jasno nebo, preboj, oblačno jutro."""
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "ai"))
import eval_megla_sevanje as em  # noqa: E402

fails, checks = [], 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


check(em.clear_sky(-3) == 0.0 and em.clear_sky(0) == 0.0, "pod obzorjem ni sevanja")
check(1000 < em.clear_sky(90) < 1060, "sonce v zenitu: ~1040 W/m²", str(em.clear_sky(90)))
check(em.clear_sky(10) < em.clear_sky(30) < em.clear_sky(60), "sevanje narašča z višino sonca")

day = datetime.date(2026, 10, 15)


def series(frac_from_min, frac):
    """Jutranji zapis: do `frac_from_min` 5 % jasnega neba, potem `frac`."""
    out = []
    for m in range(6 * 60 + 30, 12 * 60 + 1, 5):
        e = em.elevation(day, m)
        out.append((m, em.clear_sky(e) * (frac if m >= frac_from_min else 0.05)))
    return out


t, peak = em.radiation_lift(day, series(10 * 60, 0.9))
check(t is not None and 10 * 60 <= t <= 10 * 60 + 15 and peak >= 0.85, "preboj ob 10.00 se zazna na pravem mestu", f"{t} {peak}")
t2, _ = em.radiation_lift(day, series(10 * 60, 0.3))
check(t2 is None, "jutro, ki nikoli ne doseže 60 % jasnega neba, se ne ocenjuje")
t3, _ = em.radiation_lift(day, series(9 * 60 + 30, 0.9))
check(t3 is not None and t3 < t, "zgodnejši preboj da zgodnejši čas")
check(em.hm(9 * 60 + 5) == "9.05" and em.hm(None) == "—", "zapis ure s piko (Pravopis)")

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
