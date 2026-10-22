#!/usr/bin/env python3
"""
wrf/config.py — domene in namelisti za lasten WRF nad Zgornjo Savinjsko dolino (glej docs/wrf-model.md).

Iz kratkega opisa (središče, velikosti domen, razmerje gnezdenja) izračuna ugnezdene domene (i/j_parent_start,
e_we/e_sn), preveri omejitve WRF (gnezdo znotraj starša z robom, (e−1) deljivo z razmerjem) in izpiše
`namelist.wps` ter `namelist.input`. Vse je čist Python brez odvisnosti, zato ga preizkusi `tools/test_wrf.py`
brez modela.

Dve »postavitvi« (PROFILES):
- `prod`: 13,5 km → 4,5 km → 1,5 km → 0,5 km, d04 ≈ 60 × 60 km okoli Rečice (dnevni tek, ~2–3 h na 16 jedrih)
- `test`: tri majhne domene 13,5 → 4,5 → 1,5 km za preverjanje cevovoda (minute na 4 jedrih; številke NISO napoved)

Brez notranjih meritev: model ne bere postaje.

Usage:
  python3 wrf/config.py show [--profile prod]
  python3 wrf/config.py render OUTDIR --init 2026102212 --hours 36 [--profile prod] [--geog /geog]
"""
import argparse
import datetime
import os
import sys

CENTER = (46.33, 14.92)  # Rečica ob Savinji (lat, lon)
RATIO = 3
E_VERT = 51
# (bl_pbl_physics, sf_sfclay_physics). MYNN (5, 5) se je v naši sliki (gfortran 9) sesul z »free(): invalid pointer« takoj po
# začetku integracije, YSU in MYJ tečeta — zato je privzet YSU; MYNN ni preizkušen v drugi različici prevajalnika.
PBL = {"ysu": (1, 1), "myj": (2, 2)}
P_TOP = 5000
DT_FACTOR = 4  # časovni korak starša = DT_FACTOR × dx(km); 6 je običajno, 4 je varneje nad strmim terenom
MIN_BUFFER = 5  # najmanj toliko celic starša med gnezdom in robom starša

# širina domene v kilometrih (zunanja) in število celic; razmerje 3:1
PROFILES = {
    "prod": {"dx_m": 13500, "cells": [65, 85, 91, 121], "history_min": [60, 60, 60, 30]},
    "test": {"dx_m": 13500, "cells": [31, 31, 31], "history_min": [60, 60, 30]},
}


def build_domains(profile):
    """Seznam domen {id, parent, dx, e_we, e_sn, i_start, j_start, ratio}. Gnezda so središčena na starša."""
    p = PROFILES[profile]
    doms = []
    for n, cells in enumerate(p["cells"], 1):
        if n == 1:
            doms.append({"id": 1, "parent": 0, "dx": p["dx_m"], "e_we": cells, "e_sn": cells, "i_start": 1,
                         "j_start": 1, "ratio": 1})
            continue
        par = doms[-1]
        if (cells - 1) % RATIO:
            raise ValueError(f"d{n:02d}: (e_we − 1) = {cells - 1} ni deljivo z razmerjem {RATIO}")
        span = (cells - 1) // RATIO  # širina v celicah starša
        i0 = (par["e_we"] - 1 - span) // 2 + 1
        j0 = (par["e_sn"] - 1 - span) // 2 + 1
        doms.append({"id": n, "parent": par["id"], "dx": par["dx"] // RATIO, "e_we": cells, "e_sn": cells,
                     "i_start": i0, "j_start": j0, "ratio": RATIO})
    problems = check_domains(doms)
    if problems:
        raise ValueError("; ".join(problems))
    return doms


def check_domains(doms):
    """Vrne seznam težav (prazen = v redu): gnezdo mora biti znotraj starša z robom, razmerje celo število."""
    out = []
    by_id = {d["id"]: d for d in doms}
    for d in doms:
        if d["parent"] == 0:
            continue
        par = by_id[d["parent"]]
        if par["dx"] != d["dx"] * d["ratio"]:
            out.append(f"d{d['id']:02d}: dx {d['dx']} × {d['ratio']} ≠ dx starša {par['dx']}")
        if (d["e_we"] - 1) % d["ratio"] or (d["e_sn"] - 1) % d["ratio"]:
            out.append(f"d{d['id']:02d}: (e−1) ni deljivo z razmerjem")
        span_i = (d["e_we"] - 1) // d["ratio"]
        span_j = (d["e_sn"] - 1) // d["ratio"]
        if d["i_start"] - 1 < MIN_BUFFER or d["j_start"] - 1 < MIN_BUFFER:
            out.append(f"d{d['id']:02d}: premalo roba na levi/spodnji strani starša")
        if par["e_we"] - (d["i_start"] + span_i) < MIN_BUFFER or par["e_sn"] - (d["j_start"] + span_j) < MIN_BUFFER:
            out.append(f"d{d['id']:02d}: premalo roba na desni/zgornji strani starša")
    return out


def extent_km(d):
    return (d["e_we"] - 1) * d["dx"] / 1000.0, (d["e_sn"] - 1) * d["dx"] / 1000.0


def time_step(doms):
    """Časovni korak starša: DT_FACTOR × dx(km), celo število sekund (WRF priporoča 6; nad Alpami 4)."""
    return int(round(DT_FACTOR * doms[0]["dx"] / 1000.0))


def _fmt(vals, quote=False):
    if quote:
        return ", ".join(f"'{v}'" for v in vals) + ","
    return ", ".join(str(v) for v in vals) + ","


def fmt_wps_time(dt):
    return dt.strftime("%Y-%m-%d_%H:%M:%S")


def namelist_wps(doms, start, end, geog_path="/geog/WPS_GEOG", interval_s=10800, prefix="GFS", geog_res=None,
                 dem=False):
    """dem=True: domene z dx ≤ 1500 m dobijo teren Copernicus GLO-30 (`cop30m+default`, glej wrf/dem_tiles.py)."""
    n = len(doms)
    res_list = [(geog_res or "default")] * n
    if dem:
        res_list = ["cop30m+default" if d["dx"] <= 1500 else (geog_res or "default") for d in doms]
    t0, t1 = fmt_wps_time(start), fmt_wps_time(end)
    return f"""&share
 wrf_core = 'ARW',
 max_dom = {n},
 start_date = {_fmt([t0] * n, True)}
 end_date   = {_fmt([t1] * n, True)}
 interval_seconds = {interval_s},
 io_form_geogrid = 2,
/

&geogrid
 parent_id         = {_fmt([d['parent'] or 1 for d in doms])}
 parent_grid_ratio = {_fmt([d['ratio'] for d in doms])}
 i_parent_start    = {_fmt([d['i_start'] for d in doms])}
 j_parent_start    = {_fmt([d['j_start'] for d in doms])}
 e_we              = {_fmt([d['e_we'] for d in doms])}
 e_sn              = {_fmt([d['e_sn'] for d in doms])}
 geog_data_res     = {_fmt(res_list, True)}
 dx = {doms[0]['dx']},
 dy = {doms[0]['dx']},
 map_proj = 'lambert',
 ref_lat   = {CENTER[0]},
 ref_lon   = {CENTER[1]},
 truelat1  = 44.0,
 truelat2  = 48.5,
 stand_lon = {CENTER[1]},
 geog_data_path = '{geog_path}',
/

&ungrib
 out_format = 'WPS',
 prefix = '{prefix}',
/

&metgrid
 fg_name = '{prefix}',
 io_form_metgrid = 2,
/
"""


def namelist_input(doms, start, end, profile, num_metgrid_levels=34, hist_min=None, pbl="ysu"):
    n = len(doms)
    hist = hist_min or PROFILES[profile]["history_min"]
    run_h = int(round((end - start).total_seconds() / 3600.0))
    dt = time_step(doms)

    def per(vals):
        return _fmt(vals)

    # zadnji dve domeni (dx ≤ 1,5 km) brez parametrizacije konvekcije; pobočna radiacija in senčenje terena
    cu = [3 if d["dx"] >= 4500 else 0 for d in doms]
    slope = [1 if d["dx"] <= 1500 else 0 for d in doms]
    return f"""&time_control
 run_days = 0,
 run_hours = {run_h},
 run_minutes = 0,
 run_seconds = 0,
 start_year   = {_fmt([start.year] * n)}
 start_month  = {_fmt([start.month] * n)}
 start_day    = {_fmt([start.day] * n)}
 start_hour   = {_fmt([start.hour] * n)}
 end_year     = {_fmt([end.year] * n)}
 end_month    = {_fmt([end.month] * n)}
 end_day      = {_fmt([end.day] * n)}
 end_hour     = {_fmt([end.hour] * n)}
 interval_seconds = 10800,
 input_from_file = {_fmt(['.true.'] * n)}
 history_interval = {per(hist)}
 frames_per_outfile = {per([1000] * n)}
 restart = .false.,
 restart_interval = 7200,
 io_form_history = 2,
 io_form_restart = 2,
 io_form_input = 2,
 io_form_boundary = 2,
/

&domains
 time_step = {dt},
 time_step_fract_num = 0,
 time_step_fract_den = 1,
 max_dom = {n},
 e_we = {per([d['e_we'] for d in doms])}
 e_sn = {per([d['e_sn'] for d in doms])}
 e_vert = {per([E_VERT] * n)}
 dzstretch_s = 1.2,
 dzstretch_u = 1.1,
 dzbot = 25.,
 max_dz = 1000.,
 p_top_requested = {P_TOP},
 num_metgrid_levels = {num_metgrid_levels},
 num_metgrid_soil_levels = 4,
 dx = {_fmt([d['dx'] for d in doms])}
 dy = {_fmt([d['dx'] for d in doms])}
 grid_id = {_fmt([d['id'] for d in doms])}
 parent_id = {_fmt([d['parent'] or 1 for d in doms])}
 i_parent_start = {_fmt([d['i_start'] for d in doms])}
 j_parent_start = {_fmt([d['j_start'] for d in doms])}
 parent_grid_ratio = {_fmt([d['ratio'] for d in doms])}
 parent_time_step_ratio = {_fmt([d['ratio'] for d in doms])}
 feedback = 0,
 smooth_option = 0,
 use_adaptive_time_step = .false.,
/

&physics
 mp_physics = {per([8] * n)}
 ra_lw_physics = {per([4] * n)}
 ra_sw_physics = {per([4] * n)}
 radt = {per([15 if d['dx'] >= 10000 else 5 if d['dx'] >= 4000 else 3 for d in doms])}
 sf_sfclay_physics = {per([PBL[pbl][1]] * n)}
 sf_surface_physics = {per([2] * n)}
 bl_pbl_physics = {per([PBL[pbl][0]] * n)}
 bldt = 0,
 cu_physics = {per(cu)}
 cudt = 5,
 num_soil_layers = 4,
 num_land_cat = 21,
 surface_input_source = 3,
 sf_urban_physics = {per([0] * n)}
 slope_rad = {per(slope)}
 topo_shading = {per(slope)}
 icloud = 1,
/

&dynamics
 hybrid_opt = 2,
 w_damping = 1,
 diff_opt = {per([2] * n)}
 km_opt = {per([4] * n)}
 diff_6th_opt = {per([0] * n)}
 diff_6th_factor = {per([0.12] * n)}
 base_temp = 290.,
 damp_opt = 3,
 zdamp = {per([5000.] * n)}
 dampcoef = {per([0.2] * n)}
 khdif = {per([0] * n)}
 kvdif = {per([0] * n)}
 non_hydrostatic = {per(['.true.'] * n)}
 moist_adv_opt = {per([1] * n)}
 scalar_adv_opt = {per([1] * n)}
 gwd_opt = {per([1 if d['dx'] >= 10000 else 0 for d in doms])}
 epssm = 0.3,
/

&bdy_control
 spec_bdy_width = 5,
 specified = .true.,
/

&namelist_quilt
 nio_tasks_per_group = 0,
 nio_groups = 1,
/
"""


def parse_init(s):
    """'2026102212' → datetime (UTC, brez tz)."""
    return datetime.datetime.strptime(s, "%Y%m%d%H")


def render(outdir, init, hours, profile, geog="/geog/WPS_GEOG", geog_res=None, dem=False, pbl="ysu"):
    doms = build_domains(profile)
    start = parse_init(init)
    end = start + datetime.timedelta(hours=hours)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "namelist.wps"), "w") as f:
        f.write(namelist_wps(doms, start, end, geog, geog_res=geog_res, dem=dem))
    with open(os.path.join(outdir, "namelist.input"), "w") as f:
        f.write(namelist_input(doms, start, end, profile, pbl=pbl))
    return doms


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--profile", default="prod", choices=PROFILES)
    r = sub.add_parser("render")
    r.add_argument("outdir")
    r.add_argument("--init", required=True, help="YYYYMMDDHH (UTC)")
    r.add_argument("--hours", type=int, required=True)
    r.add_argument("--profile", default="prod", choices=PROFILES)
    r.add_argument("--geog", default="/geog/WPS_GEOG")
    r.add_argument("--geog-res", default=None, help="npr. 30s ali 10m (privzeto 'default')")
    r.add_argument("--pbl", default="ysu", choices=PBL, help="shema mejne plasti (privzeto ysu)")
    r.add_argument("--dem", action="store_true", help="teren Copernicus 30 m za domene ≤ 1,5 km")
    a = ap.parse_args()
    if a.cmd == "show":
        for d in build_domains(a.profile):
            ex = extent_km(d)
            print(f"d{d['id']:02d}  dx {d['dx']:>6} m  {d['e_we']}×{d['e_sn']}  {ex[0]:.0f}×{ex[1]:.0f} km  "
                  f"start ({d['i_start']},{d['j_start']}) v d{d['parent']:02d}")
        return 0
    render(a.outdir, a.init, a.hours, a.profile, a.geog, a.geog_res, a.dem, a.pbl)
    print(f"  → {a.outdir}/namelist.wps, namelist.input")
    return 0


if __name__ == "__main__":
    sys.exit(main())
