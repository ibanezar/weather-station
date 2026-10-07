#!/usr/bin/env python3
"""tools/test_storm_events.py — zaznava nevihtnih dnevi (seo_smart_routine.detect_storms).

Število strel samo ne pove nič (logger šteje v radiju 200 km, daljna nevihta nad Jadranom da
tisoče strel), zato mora dogodek zahtevati tudi najbližjo strelo. Zaženi: python3 tools/test_storm_events.py
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seo_smart_routine as m  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


d = (m.TODAY - datetime.timedelta(days=2)).isoformat()
old = (m.TODAY - datetime.timedelta(days=40)).isoformat()
hist = {d: {"precipTotal": 12.0, "windgustHigh": 30.0}, old: {}}


def run(count, closest, date=d, history=hist):
    return m.detect_storms(history, {date: {"date": date, "count": count, "closest_km": closest}})


check(len(run(5000, 4.0)) == 1, "nevihta nad dolino se zazna")
check(run(5000, 4.0)[0]["slug"] == f"nevihta-{d}", "slug nosi datum")
check(not run(15000, 60.0), "daljna nevihta z veliko streli se NE zazna")
check(not run(m.STORM_MIN_STRIKES - 1, 2.0), "premalo strel se ne zazna")
check(len(run(m.STORM_MIN_STRIKES, m.STORM_MAX_CLOSEST_KM)) == 1, "mejna vrednost se zazna")
check(not run(5000, None), "brez najbližje strele ni dogodka")
check(not run(5000, 4.0, date="2099-01-01"), "dan brez meritve postaje se preskoči")
check(not run(5000, 4.0, date=old), "izven okna iskanja se ne zazna")
print(f"\n8 preverjanj, {fails} razhajanj")
sys.exit(1 if fails else 0)
