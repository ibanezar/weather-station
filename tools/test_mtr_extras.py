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
# predict_day: card sd = raw sd * SD_OOS_K; p_frost keeps using the RAW sd (own factor)
feats = {"om_tmax": 10.0, "om_tmin": 1.0, "om_prec": 0.0, "wet_hours": 0, "cloud": 20.0, "cloud_n": 10.0,
         "wind": 2.0, "wind_n": 1.0, "rh": 60.0, "pres": 1013.0, "rad": 100.0, "windmax": 3.0,
         "radsum": 1000.0, "sin_doy": 0.0, "cos_doy": 1.0}
c = [0.0] * 16; c[2] = 1.0     # tmin prediction = om_tmin
model = {"leads": {"1": {"coefficients": {"tmax": c[:], "tmin": c[:], "pop": [0.0] * 9},
                         "residual_sd": {"tmax": 2.0, "tmin": 2.0}, "skill": {}}}}
r = p.predict_day(model, 1, feats)
check(r["tmin_sd"] == round(2.0 * p.SD_OOS_K, 2), f"card sd inflated ({r['tmin_sd']})")
check(r["p_frost"] == round(p.frost_probability(r["tmin"], 2.0), 2), "p_frost from raw sd")
check(r["night_regime"] == "clear_calm", "regime in output")
# multi-model features (--multi-tmax)
mos = p.mos
f = {"om_tmax": 10.0, "mm": {"tmax": {"ecmwf_ifs025": 12.0, "gfs_seamless": 8.0}, "tmin": {}}}
v = mos.multi_vector(f, "tmax")
check(len(v) == len(mos.MULTI_FEATURES), "multi_vector length matches MULTI_FEATURES")
check(v[:4] == [2.0, -2.0, 0.0, 0.0], f"missing models are neutral ({v[:4]})")
check(abs(v[4]) < 1e-9 and abs(v[5] - 1.633) < 1e-3, f"mean diff / spread ({v[4:]})")
check(mos.multi_vector({"om_tmin": 3.0}, "tmin") == [0.0] * 5 + [0.0], "no archive -> neutral zeros")
base = dict(feats); base["mm"] = f["mm"]
n0 = len(mos.temp_vector(base, "tmax")); n1 = len(mos.temp_vector(base, "tmax", use_multi=True))
check(n1 - n0 == len(mos.MULTI_FEATURES), "temp_vector appends exactly MULTI_FEATURES")
print("OK" if not FAILS else f"{len(FAILS)} FAIL"); sys.exit(1 if FAILS else 0)
