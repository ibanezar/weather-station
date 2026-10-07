#!/usr/bin/env python3
"""tools/test_gore.py — vreme v gorah (winter_engine.compute_mountains / ridge_wind_kmh / wind_chill_c).
Zaženi: python3 tools/test_gore.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winter_engine as w  # noqa: E402
import generate_gore_page as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# Vetrno hlajenje: znana vrednost (Environment Canada): -10 °C pri 30 km/h ≈ -20 °C
check(abs(w.wind_chill_c(-10, 30) - (-19.5)) < 0.6, "vetrno hlajenje -10 °C @ 30 km/h ≈ -19,5")
check(w.wind_chill_c(15, 40) == 15, "nad 10 °C ni hlajenja")
check(w.wind_chill_c(-5, 3) == -5, "pod 4,8 km/h ni hlajenja")
check(w.wind_chill_c(None, 20) is None, "brez temperature None")

# Veter po višini: interpolacija med 10 m (ELEV) in nivoji
hourly = {"wind_speed_10m": [10],
          "geopotential_height_925hPa": [760], "wind_speed_925hPa": [20],
          "geopotential_height_850hPa": [1500], "wind_speed_850hPa": [40],
          "geopotential_height_700hPa": [3000], "wind_speed_700hPa": [70]}
check(abs(w.ridge_wind_kmh(hourly, 0, 1500) - 40) < 1e-6, "na višini nivoja 850 hPa je veter tega nivoja")
mid = w.ridge_wind_kmh(hourly, 0, 1130)
check(20 < mid < 40, "med nivojema je veter vmes")
check(w.ridge_wind_kmh(hourly, 0, 100) == 10, "pod postajo je veter pri tleh")
check(w.ridge_wind_kmh(hourly, 0, 5000) == 70, "nad zgornjim nivojem ostane zadnja vrednost")
check(w.ridge_wind_kmh({}, 0, 1500) is None, "brez podatkov None")

# Dnevni povzetek
times = ["2026-12-01T%02d:00" % h for h in range(24)]
H = {"time": times, "temperature_2m": [0.0] * 24, "precipitation": [1.0] * 24,
     "freezing_level_height": [800.0] * 24, "wind_speed_10m": [10.0] * 24}
for hpa, h_, v in ((925, 760, 20), (850, 1500, 40), (700, 3000, 70)):
    H[f"geopotential_height_{hpa}hPa"] = [h_] * 24
    H[f"wind_speed_{hpa}hPa"] = [v] * 24
peaks = w.compute_mountains(H, times, 0)
check([p["name"] for p in peaks] == [p["name"] for p in w.HIGH_POINTS], "vsi vrhi iz HIGH_POINTS")
golte = peaks[0]
check(golte["daily"][0]["snow_cm"] == 24.0, "24 mm pri ničti izotermi 800 m na 1400 m = 24 cm snega")
check(golte["daily"][0]["tmin_c"] < 0, "na 1400 m pri 0 °C v dolini je pod ničlo")
check(golte["now"]["felt_c"] < golte["now"]["temp_c"], "občutena je pod temperaturo zraka")

# Izpis
check(g.num(-0.4) == "0", "-0 se izpiše kot 0")
check(g.num(-2.4) == "-2", "negativna vrednost ohrani predznak")
check(g.num(None) == "—", "None je pomišljaj")
print(f"\n15 preverjanj, {fails} razhajanj")
sys.exit(1 if fails else 0)
