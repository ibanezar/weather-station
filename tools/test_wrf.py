#!/usr/bin/env python3
"""tools/test_wrf.py — cevovod lastnega WRF brez modela: domene in namelisti, izbira polj GFS, ploščice DEM,
izvleček iz wrfout (sintetičen), verifikacija. Zaženi: python3 tools/test_wrf.py"""
import datetime
import json
import math
import os
import re
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "wrf"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import config as cfg  # noqa: E402
import dem_tiles as dem  # noqa: E402
import extract as ex  # noqa: E402
import fetch_gfs as gfs  # noqa: E402
import limit_slope as ls  # noqa: E402
import synthetic_geog as sg  # noqa: E402
import verify_wrf as vw  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# ── Domene ───────────────────────────────────────────────────────────────────
for prof in cfg.PROFILES:
    d = cfg.build_domains(prof)
    check(cfg.check_domains(d) == [], f"{prof}: domene brez težav")
    check(all(d[i]["dx"] * 3 == d[i - 1]["dx"] for i in range(1, len(d))), f"{prof}: dx se deli z 3")
prod = cfg.build_domains("prod")
check([x["dx"] for x in prod] == [13500, 4500, 1500, 500], "prod: 13,5 → 4,5 → 1,5 → 0,5 km")
check(abs(cfg.extent_km(prod[3])[0] - 60) < 1e-6, "prod: d04 je 60 km")
check(cfg.time_step(prod) == 54, "časovni korak 4 × dx(km)")
try:
    cfg.PROFILES["_bad"] = {"dx_m": 9000, "cells": [50, 40], "history_min": [60, 60]}  # (40−1) ni deljivo s 3? 39/3 = 13 ok
    cfg.PROFILES["_bad"]["cells"] = [50, 41]
    cfg.build_domains("_bad")
    check(False, "neveljavna velikost gnezda bi morala pasti")
except ValueError:
    check(True, "gnezdo z (e−1) nedeljivim z razmerjem je zavrnjeno")
cfg.PROFILES["_big"] = {"dx_m": 9000, "cells": [31, 91], "history_min": [60, 60]}
try:
    cfg.build_domains("_big")
    check(False, "prevelika nest bi morala pasti")
except ValueError:
    check(True, "gnezdo večje od starša je zavrnjeno")
del cfg.PROFILES["_bad"], cfg.PROFILES["_big"]
# gnezda so geometrijsko znotraj staršev in približno na središču
for a, b in zip(prod, prod[1:]):
    lo = (b["i_start"] - 1) * a["dx"]
    hi = lo + (b["e_we"] - 1) * b["dx"]
    check(lo >= 5 * a["dx"] and hi <= (a["e_we"] - 1 - 5) * a["dx"], f"d{b['id']:02d} znotraj d{a['id']:02d} z robom")
    mid_off = abs((lo + hi) / 2 - (a["e_we"] - 1) * a["dx"] / 2)
    check(mid_off <= a["dx"], f"d{b['id']:02d} središčen v d{a['id']:02d} (odmik {mid_off:.0f} m)")

# ── Namelisti ────────────────────────────────────────────────────────────────
start = cfg.parse_init("2026102212")
end = start + datetime.timedelta(hours=36)
wps = cfg.namelist_wps(prod, start, end)
inp = cfg.namelist_input(prod, start, end, "prod")
check("max_dom = 4" in wps and "max_dom = 4" in inp, "max_dom = 4")
check("start_date = '2026-10-22_12:00:00'" in wps and "end_date   = '2026-10-24_00:00:00'" in wps, "čas v namelist.wps")
check(" run_hours = 36," in inp and "start_hour   = 12, 12, 12, 12," in inp and "end_day      = 24, 24, 24, 24," in inp,
      "čas v namelist.input")
PER_DOM = ("e_we", "e_sn", "dx", "dy", "parent_id", "parent_grid_ratio", "i_parent_start", "j_parent_start", "mp_physics",
           "cu_physics", "bl_pbl_physics", "sf_surface_physics", "history_interval", "radt", "diff_opt", "km_opt",
           "slope_rad", "topo_shading", "parent_time_step_ratio", "e_vert", "gwd_opt", "zdamp", "dampcoef")
for text, label in ((wps, "wps"), (inp, "input")):
    for m in re.finditer(r"^\s*(\w+)\s*=\s*(.+?),\s*$", text, re.M):
        key, val = m.group(1), m.group(2)
        n = len([v for v in val.split(",") if v.strip()])
        if key in PER_DOM and not (label == "wps" and key in ("dx", "dy")):
            check(n == 4, f"{label}: {key} ima {n} vrednosti namesto 4")
check("cu_physics = 3, 3, 0, 0," in inp, "konvekcija samo na d01/d02")
check("bl_pbl_physics = 1, 1, 1, 1," in inp and "sf_sfclay_physics = 1, 1, 1, 1," in inp, "privzeto YSU + MM5 (MYNN se v sliki sesuje)")
check("bl_pbl_physics = 2, 2, 2, 2," in cfg.namelist_input(prod, start, end, "prod", pbl="myj"), "MYJ je izbirna različica")
check("slope_rad = 0, 0, 1, 1," in inp, "pobočno sevanje samo na d03/d04")
check("history_interval = 60, 60, 60, 30," in inp, "izhod d04 na 30 min")
check("'cop30m+default'" in cfg.namelist_wps(prod, start, end, dem=True)
      and "'cop30m" not in wps, "DEM samo ob izrecni zahtevi, samo d03/d04")
check("indoor" not in (wps + inp).lower(), "brez notranjih meritev")
with tempfile.TemporaryDirectory() as td:
    cfg.render(td, "2026102212", 36, "test")
    check(os.path.exists(os.path.join(td, "namelist.wps")) and os.path.exists(os.path.join(td, "namelist.input")),
          "render zapiše oba namelista")

# ── GFS: izbira polj ─────────────────────────────────────────────────────────
IDX = """1:0:d=2026102200:PRMSL:mean sea level:anl:
2:1000:d=2026102200:MSLET:mean sea level:anl:
3:2000:d=2026102200:HGT:1000 mb:anl:
4:3000:d=2026102200:TMP:1000 mb:anl:
5:4000:d=2026102200:O3MR:100 mb:anl:
6:5000:d=2026102200:UGRD:850 mb:anl:
7:6000:d=2026102200:TMP:2 m above ground:anl:
8:7000:d=2026102200:APCP:surface:0-6 hour acc fcst:
9:8000:d=2026102200:SOILW:0-0.1 m below ground:anl:
10:9000:d=2026102200:TSOIL:0.1-0.4 m below ground:anl:
11:10000:d=2026102200:TMP:850 mb:anl:
"""
r = gfs.select_ranges(IDX)
check(r == [(1000, 3999), (5000, 6999), (8000, None)], f"izbira polj in združevanje sosednjih območij: {r}")
check(not any(a <= 4000 <= (b or 10 ** 9) and a == 4000 for a, b in r), "O3MR ni izbran")
check(gfs.wanted("TMP", "250 mb") and gfs.wanted("RH", "2 m above ground") and not gfs.wanted("CLWMR", "850 mb")
      and not gfs.wanted("APCP", "surface"), "wanted()")
check(gfs.url_for(datetime.datetime(2026, 10, 22, 12), 6).endswith("gfs.20261022/12/atmos/gfs.t12z.pgrb2.0p25.f006"),
      "URL GFS")

# ── DEM ──────────────────────────────────────────────────────────────────────
check(dem.tiles_needed(45.4, 13.8, 47.3, 16.1) == [(la, lo) for la in (45, 46, 47) for lo in (13, 14, 15, 16)],
      "ploščice za okvir")
check(dem.tiles_needed(46.0, 14.0, 47.0, 15.0) == [(46, 14)], "celo polje brez odvečne ploščice")
check(dem.tile_name(0, 0) == "00001-03600.00001-03600" and dem.tile_name(1, 2) == "03601-07200.07201-10800",
      "imena ploščic WPS")
idx = dem.index_text(45, 13)
check("projection=regular_ll" in idx and "wordsize=2" in idx and "tile_x=3600" in idx
      and f"known_lon={13 + 0.5 / 3600:.9f}" in idx, "index ploščic")
with tempfile.TemporaryDirectory() as td:
    a = np.arange(3600 * 3600, dtype="float32").reshape(3600, 3600) % 2000 + 0.4
    p = os.path.join(td, "t")
    dem.write_tile(a, p)
    b = dem.read_tile(p)
    check(os.path.getsize(p) == 3600 * 3600 * 2 and int(b[0, 5]) == int(round(a[0, 5])) and
          int(b[-1, 7]) == int(round(a[-1, 7])), "zapis/branje ploščice (sever zgoraj, int16)")
    raw = np.fromfile(p, dtype="<i2")
    check(int(raw[7]) == int(round(a[-1, 7])), "prva vrstica v datoteki je JUŽNA (WPS)")
tbl = ("====\nname = HGT_M\n        priority = 1\n        interp_option = gmted2010_30s:x\n"
       "        rel_path = gmted2010_30s:topo/\n====\nname = LANDUSEF\n        interp_option = x:y\n")
t2 = dem.patch_table_text(tbl)
check(t2.count("cop30m:") == 2 and t2.index("cop30m") < t2.index("LANDUSEF") and dem.patch_table_text(t2) == t2,
      "GEOGRID.TBL: cop30m samo v HGT_M, idempotentno")

# ── Omejitev naklona terena ──────────────────────────────────────────────────
yy, xx = np.mgrid[0:60, 0:60]
steep = 1500.0 * np.exp(-(((xx - 30) ** 2 + (yy - 30) ** 2) / 12.0))  # špica 1500 m, strma pobočja
before = ls.max_slope_deg(steep, 500.0)
new, it, frac = ls.limit_slope(steep, 500.0, 22.0)
check(before > 30 and ls.max_slope_deg(new, 500.0) <= 22.5, f"naklon {before:.0f}° → {ls.max_slope_deg(new, 500.0):.1f}°")
check(it > 0 and 0 < frac < 0.5, "spremeni se le del celic")
flat = np.full((20, 20), 400.0)
n2, it2, fr2 = ls.limit_slope(flat, 500.0, 22.0)
check(it2 == 0 and fr2 == 0 and (n2 == flat).all(), "raven teren ostane nedotaknjen")
check(abs(new.mean() - steep.mean()) < 5, "povprečna višina se skoraj ne spremeni")

# ── Sintetični WPS_GEOG (za preizkus cevovoda) ───────────────────────────────
TBL2 = ("=====\nname = HGT_M\n  dest_type = continuous\n  rel_path = default:topo/\n=====\n"
        "name = LANDUSEF\n  dest_type = categorical\n  z_dim_name = land_cat\n  rel_path = default:lu/\n=====\n"
        "name = GREENFRAC\n  dest_type = continuous\n  z_dim_name = month\n  rel_path = default:gf/\n=====\n"
        "name = LAI12M\n  optional = yes\n  rel_path = default:lai/\n=====\n")
bl = sg.parse_table(TBL2)
check([b["name"] for b in bl] == ["HGT_M", "LANDUSEF", "GREENFRAC", "LAI12M"], "parse_table: imena polj")
with tempfile.TemporaryDirectory() as td:
    tp = os.path.join(td, "T.TBL")
    open(tp, "w").write(TBL2)
    made = sg.make(os.path.join(td, "g"), tp)
    check(made == ["HGT_M", "LANDUSEF", "GREENFRAC"], "neobvezna polja (optional=yes) se preskočijo")
    check(os.path.getsize(os.path.join(td, "g", "gf", "00001-00360.00001-00180")) == 12 * 180 * 360 * 2,
          "mesečno polje ima 12 nivojev")
    check("category_max=21" in open(os.path.join(td, "g", "lu", "index")).read(), "kategorična raba tal ima 21 razredov")

# ── Izvleček iz wrfout (sintetičen) ──────────────────────────────────────────
from netCDF4 import Dataset  # noqa: E402


def make_wrfout(path, t0, n_t, rain_per_step, lat0=46.0, lon0=14.4, shape=(21, 21), dx=500.0):
    ny, nx = shape
    with Dataset(path, "w") as nc:
        nc.createDimension("Time", None)
        nc.createDimension("DateStrLen", 19)
        nc.createDimension("south_north", ny)
        nc.createDimension("west_east", nx)
        nc.setncattr("DX", dx)
        nc.setncattr("TITLE", " OUTPUT FROM WRF V4.6.1 MODEL")
        times = nc.createVariable("Times", "S1", ("Time", "DateStrLen"))
        lat = nc.createVariable("XLAT", "f4", ("Time", "south_north", "west_east"))
        lon = nc.createVariable("XLONG", "f4", ("Time", "south_north", "west_east"))
        hgt = nc.createVariable("HGT", "f4", ("Time", "south_north", "west_east"))
        names = ["T2", "U10", "V10", "RAINNC", "RAINC", "Q2", "PSFC", "SWDOWN", "PBLH"]
        vs = {n: nc.createVariable(n, "f4", ("Time", "south_north", "west_east")) for n in names}
        jj, ii = np.meshgrid(np.arange(ny), np.arange(nx), indexing="ij")
        for k in range(n_t):
            t = t0 + datetime.timedelta(minutes=30 * k)
            times[k, :] = np.array(list(t.strftime("%Y-%m-%d_%H:%M:%S")), dtype="S1")
            lat[k] = lat0 + jj * 0.0045
            lon[k] = lon0 + ii * 0.0065
            hgt[k] = 400.0 + jj
            vs["T2"][k] = 280.0 + k * 0.1 + 0 * jj
            vs["U10"][k] = 3.0 + 0 * jj
            vs["V10"][k] = 4.0 + 0 * jj
            vs["RAINNC"][k] = k * rain_per_step + 0 * jj
            vs["RAINC"][k] = 0 * jj
            vs["Q2"][k] = 0.005 + 0 * jj
            vs["PSFC"][k] = 97000.0 + 0 * jj
            vs["SWDOWN"][k] = 0 * jj
            vs["PBLH"][k] = 100.0 + 0 * jj


lat_t, lon_t = 46.0 + 7 * 0.0045 + 0.001, 14.4 + 12 * 0.0065 - 0.001  # blizu celice (j=7, i=12)
check(ex.nearest_cell(np.array([[46.0, 46.0], [46.01, 46.01]]), np.array([[14.0, 14.02], [14.0, 14.02]]),
                      46.0099, 14.019) == (1, 1), "najbližja celica")
check(abs(ex.wind_dir_from(0, -5) - 0) < 1e-6 and abs(ex.wind_dir_from(-5, 0) - 90) < 1e-6
      and abs(ex.wind_dir_from(0, 5) - 180) < 1e-6 and abs(ex.wind_dir_from(5, 0) - 270) < 1e-6,
      "smer vetra: odkod piha (sever 0°, vzhod 90°)")
check(abs(ex.rh_from_q(0.0, 100000, 10.0)) < 1e-9 and 99 < ex.rh_from_q(0.00811, 100000, 10.0) < 101,
      "RH iz Q2 (10 °C, 1000 hPa nasičeno ≈ 8,1 g/kg)")
with tempfile.TemporaryDirectory() as td:
    t0 = datetime.datetime(2026, 10, 22, 22, 0)  # 00:00 lokalno 23. 10. (UTC+2)
    make_wrfout(os.path.join(td, "wrfout_d04_2026-10-22_22:00:00"), t0, 48, 0.1)
    meta, rows = ex.hourly_series([os.path.join(td, "wrfout_d04_2026-10-22_22:00:00")], lat_t, lon_t)
    check((meta["j"], meta["i"]) == (7, 12), f"izvleček: celica {(meta['j'], meta['i'])}")
    check(len(rows) == 48 and rows[0]["precip_mm"] == 0.0 and abs(rows[1]["precip_mm"] - 0.1) < 1e-3,
          "padavine so razlika akumulacije (prvi korak 0)")
    check(abs(rows[0]["t2_c"] - 6.85) < 0.01 and abs(rows[0]["wind_ms"] - 5.0) < 1e-6 and rows[0]["wind_dir"] == 217,
          "T2 v °C, veter 5 m/s iz 217°")
    check(meta["model_height_m"] == 407.0, "višina celice modela je zapisana")
    day = ex.daily_summary(rows)
    check(list(day) == ["2026-10-23"] and day["2026-10-23"]["complete"], "dnevni povzetek po lokalnem dnevu")
    check(abs(day["2026-10-23"]["precip_mm"] - 4.7) < 0.01, "dnevna vsota padavin")
    check(abs(day["2026-10-23"]["tmin_c"] - 6.85) < 0.06 and abs(day["2026-10-23"]["tmax_c"] - 11.55) < 0.06,
      "Tmin/Tmax dneva")
    short = ex.daily_summary(rows[:10])
    check(short["2026-10-23"]["complete"] is False, "krajši izhod je označen kot nepopoln dan")
    # ponastavitev akumulacije ne sme dati negativnih padavin
    make_wrfout(os.path.join(td, "wrfout_d04_b"), t0, 4, -1.0)
    _, r2 = ex.hourly_series([os.path.join(td, "wrfout_d04_b")], lat_t, lon_t)
    check(all(r["precip_mm"] >= 0 for r in r2), "negativne padavine se odrežejo")
    out = os.path.join(td, "o.json")
    sys.argv = ["x", "--dir", td, "--out", out, "--init", "2026102212", "--lat", str(lat_t), "--lon", str(lon_t)]
    os.rename(os.path.join(td, "wrfout_d04_b"), os.path.join(td, "tmp_b"))
    check(ex.main() == 0 and json.load(open(out))["domain"] == 4, "extract.main zapiše JSON za d04")

# lokalni čas brez zoneinfo (Python 3.8 v vsebniku) ≡ zoneinfo na vseh urah treh let
from zoneinfo import ZoneInfo  # noqa: E402
bad = 0
t = datetime.datetime(2025, 1, 1)
while t < datetime.datetime(2028, 1, 1):
    ref = t.replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo("Europe/Ljubljana")).utcoffset().total_seconds() / 3600
    if ex.utc_offset_hours(t) != ref:
        bad += 1
    t += datetime.timedelta(minutes=30)
check(bad == 0, f"ročni lokalni čas se ujema z zoneinfo ({bad} neujemanj)")

# ── Verifikacija ─────────────────────────────────────────────────────────────
check(vw.target_date("2026102212") == "2026-10-23" and vw.target_date("2026123112") == "2027-01-01",
      "tek 12 UTC napoveduje naslednji lokalni dan")
hist = {"2026-10-23": {"tempHigh": 12.0, "tempLow": 5.0, "precipTotal": 0.0},
        "2026-10-24": {"tempHigh": 10.0, "tempLow": 4.0, "precipTotal": 3.0}}
wrf = {"2026-10-23": {"tmax": 11.0, "tmin": 5.5, "precip": 0.0}, "2026-10-24": {"tmax": 10.5, "tmin": 2.0, "precip": 2.0}}
arch = {"best_match": {"2026-10-23": {"tmax": 14.0, "tmin": 7.0, "precip": 0.5},
                       "2026-10-24": {"tmax": 9.0, "tmin": 4.0, "precip": 0.0}}}
res = vw.score(wrf, arch, hist, models=["best_match"])
check(res["n"] == 2 and res["early"], "verifikacija: 2 skupna dneva, zgodno")
check(res["sources"]["wrf"]["mae_tmax"] == 0.75 and res["sources"]["wrf"]["mae_tmin"] == 1.25, "MAE WRF")
check(res["sources"]["best_match"]["mae_tmax"] == 1.5 and res["sources"]["best_match"]["bias_tmax"] == 0.5,
      "MAE in pristranskost referenčnega modela")
check(res["sources"]["wrf"]["wet_day_hit"] == 1.0 and res["sources"]["best_match"]["wet_day_hit"] == 0.0,
      "zadetek mokrega dne (prag 0,2 mm)")
check(res["wrf_wins"]["best_match:tmax"] == {"wins": 2, "ties": 0, "of": 2}
      and res["wrf_wins"]["best_match:tmin"] == {"wins": 1, "ties": 0, "of": 2}, "zmage WRF po spremenljivki")
arch2 = {"best_match": {"2026-10-24": arch["best_match"]["2026-10-24"]}}
check(vw.score(wrf, arch2, hist, models=["best_match"])["n"] == 1, "dan brez napovedi enega vira se ne šteje")
check(vw.score(wrf, arch, {"2026-10-23": hist["2026-10-23"]}, models=["best_match"])["n"] == 1,
      "dan brez meritve se ne šteje")
check(vw.observed({"d": {"tempHigh": None, "tempLow": 1, "precipTotal": 0}}, "d") is None, "manjkajoča meritev")

if fails:
    print(f"✗ {fails} preverjanj ni uspelo")
    sys.exit(1)
print("✓ test_wrf: vsa preverjanja uspešna")
