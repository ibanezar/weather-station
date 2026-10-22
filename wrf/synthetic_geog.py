#!/usr/bin/env python3
"""
wrf/synthetic_geog.py — SINTETIČNI geografski podatki WPS za preizkus cevovoda brez 29 GB WPS_GEOG.

Za vsako polje iz GEOGRID.TBL (z `default:` potjo, brez `optional=yes`) zapiše svetovno mrežo 1° s stalno
vrednostjo (gozd, ilovica, albedo 15 % …). Teren ni stalen, če obstaja `<GEOG>/cop30m` (ga zapiše dem_tiles.py), ga
geogrid vzame za domene ≤ 1,5 km.

Namen je SAMO preveriti, da namelisti, geogrid → real → wrf tečejo in da se mreže ujemajo. Dobljena napoved ni fizikalno
smiselna (ni terena in rabe tal) in je ne smemo primerjati z meritvami.

Usage:
  python3 wrf/synthetic_geog.py /tmp/geog/WPS_GEOG /opt/WPS/geogrid/GEOGRID.TBL.ARW
"""
import os
import re
import sys

import numpy as np

# vrednost (v enotah polja) in faktor shrambe (int16 · scale)
VALUES = {
    "HGT_M": (300.0, 1.0), "SOILTEMP": (285.0, 0.1), "ALBEDO12M": (15.0, 0.1), "GREENFRAC": (0.5, 0.01),
    "LAI12M": (2.0, 0.01), "SNOALB": (45.0, 0.1), "LAKE_DEPTH": (50.0, 1.0), "IRRIGATION": (0.0, 1.0),
}
CATEGORICAL = {"LANDUSEF": (5, 21), "SOILCTOP": (6, 16), "SOILCBOT": (6, 16)}  # (vrednost, št. kategorij)
SKIP_PREFIX = ("MH_URB2D", "ZD_URB2D", "Z0_URB2D", "BUILD_AREA", "LF_URB2D", "AHE")


def parse_table(text):
    """GEOGRID.TBL → seznam {name, keys: {ključ: [vrednosti]}}."""
    out = []
    for blk in re.split(r"^=+\s*$", text, flags=re.M):
        keys = {}
        for line in blk.splitlines():
            line = line.split("#")[0].strip()
            if "=" in line:
                k, v = (x.strip() for x in line.split("=", 1))
                keys.setdefault(k, []).append(v)
        if "name" in keys:
            out.append({"name": keys["name"][0], "keys": keys})
    return out


def z_levels(name, zdim):
    return {"month": 12, "num_urb_params": 132, "dust_erosion_dimension": 3, "month_hour": 288}.get(zdim or "", 1)


def index_text(name, cat, zlev, scale):
    base = ["projection=regular_ll", "dx=1.0", "dy=1.0", "known_x=1.0", "known_y=1.0", "known_lon=-179.5",
            "known_lat=-89.5", "wordsize=2", "endian=little", "tile_x=360", "tile_y=180", f"tile_z={zlev}", "signed=yes",
            'units="synthetic"', 'description="synthetic"']
    if cat:
        base = ["type=categorical", f"category_min=1", f"category_max={cat[1]}"] + base
    else:
        base = ["type=continuous", f"scale_factor={scale}"] + base
    return "\n".join(base) + "\n"


def make(geog_dir, tbl_path):
    with open(tbl_path) as f:
        blocks = parse_table(f.read())
    made = []
    for b in blocks:
        name, keys = b["name"], b["keys"]
        if name.startswith(SKIP_PREFIX) or (keys.get("optional") or ["no"])[0].lower().startswith("y"):
            continue
        paths = [v.split(":", 1)[1] for v in keys.get("rel_path", []) if v.startswith("default:")]
        if not paths:
            continue
        rel = paths[0]
        d = os.path.join(geog_dir, rel)
        os.makedirs(d, exist_ok=True)
        zlev = z_levels(name, (keys.get("z_dim_name") or [None])[0])
        cat = CATEGORICAL.get(name)
        val, scale = VALUES.get(name, (0.0, 1.0))
        if cat:
            val, zlev = cat[0], 1
        with open(os.path.join(d, "index"), "w") as f:
            f.write(index_text(name, cat, zlev, scale))
        raw = int(round(val / scale)) if not cat else int(val)
        arr = np.full((zlev, 180, 360), raw, dtype="<i2")
        arr.tofile(os.path.join(d, "00001-00360.00001-00180"))
        made.append(name)
    return made


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1
    made = make(sys.argv[1], sys.argv[2])
    print(f"  → {len(made)} sintetičnih polj v {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
