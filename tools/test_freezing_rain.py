#!/usr/bin/env python3
"""tools/test_freezing_rain.py — žled (winter_engine.freezing_rain_hour) in podvojene konstante v
generate_zima_page.py. Žled terja HKRATI mraz pri tleh, toplo plast in padavine; brez katerega
koli pojava ni (sneg ali navaden dež). Zaženi: python3 tools/test_freezing_rain.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winter_engine as w  # noqa: E402
import generate_zima_page as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


def hour(t2m, t925, t850, precip):
    return {"temperature_2m": [t2m], "temperature_925hPa": [t925], "temperature_850hPa": [t850],
            "precipitation": [precip]}


check(w.freezing_rain_hour(hour(-1.5, 1.0, 2.0, 0.8), 0) == "visoko", "dež pri -1,5 °C s toplo plastjo je visoko")
check(w.freezing_rain_hour(hour(-1.0, 0.8, 1.0, 0.2), 0) == "srednje", "šibek dež je srednje")
check(w.freezing_rain_hour(hour(-1.0, -2.0, -3.0, 2.0), 0) == "nizko", "brez tople plasti pada sneg, ne žled")
check(w.freezing_rain_hour(hour(1.5, 3.0, 2.0, 2.0), 0) == "nizko", "nad ničlo pri tleh dež ne zmrzuje")
check(w.freezing_rain_hour(hour(-1.0, 1.0, 2.0, 0.0), 0) == "nizko", "brez padavin ni žleda")
check(w.freezing_rain_hour(hour(-1.0, 1.0, 2.0, w.FREEZING_RAIN_PRECIP_MIN_MM - 0.01), 0) == "nizko", "pod pragom padavin")
check(w.freezing_rain_hour(hour(0.0, 1.0, 2.0, 0.1), 0) == "srednje", "mejna vrednost: 0 °C in 0,1 mm")
check(w.freezing_rain_hour({"temperature_2m": [None], "precipitation": [1]}, 0) is None, "brez podatka vrne None")
check(w.freezing_rain_hour({"temperature_2m": [-1], "precipitation": [1]}, 0) is None, "brez nivojev vrne None")
check((g.FR_T2M, g.FR_WARM, g.FR_PRECIP, g.FR_HIGH) == (
    w.FREEZING_RAIN_T2M_MAX_C, w.FREEZING_RAIN_WARM_MIN_C,
    w.FREEZING_RAIN_PRECIP_MIN_MM, w.FREEZING_RAIN_HIGH_MM), "konstante strani = konstante motorja")
times = ["2026-12-01T%02d:00" % h for h in range(4)]
hourly = {"time": times, "temperature_2m": [-1, -1, 2, -1], "temperature_925hPa": [1] * 4,
          "temperature_850hPa": [2] * 4, "precipitation": [0, 0.6, 1.0, 0.2]}
r = w.compute_freezing_rain(hourly, times, 0)
check(r["level"] == "visoko" and r["hours"] == [times[1], times[3]], "povzetek 48 h zbere samo ure s pojavom")
check(r["peak_precip_mm"] == 0.6, "vrh padavin samo iz ur z žledom")
print(f"\n13 preverjanj, {fails} razhajanj")
sys.exit(1 if fails else 0)
