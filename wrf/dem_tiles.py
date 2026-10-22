#!/usr/bin/env python3
"""
wrf/dem_tiles.py — ločljivejši teren za geogrid: Copernicus GLO-30 DEM (30 m, AWS Open Data) → binarne ploščice WPS.

Zakaj: privzeti teren WPS (GMTED2010, 30″ ≈ 900 m) ne razloči doline Savinje; pri mreži 0,5 km je teren glavni razlog,
da lasten WRF sploh kaj doda. Ploščice se zapišejo v `<GEOG>/cop30m/` in jih `patch-table` doda kot nov vir za HGT_M.
Domene d03 in d04 jih uporabijo (`config.py render --dem`), zunanji dve ostaneta pri GMTED2010.

Copernicus DEM: © DLR e.V. 2010–2014 in © Airbus Defence and Space GmbH 2014–2018, licenca Copernicus (prosta uporaba z navedbo).

Orodje se poganja zunaj vsebnika (rabi tifffile + imagecodecs, ki ju slika WRF nima):
  pip install numpy tifffile imagecodecs
  python3 wrf/dem_tiles.py build /data/geog/WPS_GEOG --bbox 45.4 13.8 47.3 16.1
  python3 wrf/dem_tiles.py patch-table geogrid/GEOGRID.TBL       # ga kliče run.sh
"""
import argparse
import math
import os
import re
import sys
import urllib.request

URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
       "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif")
RES_NAME = "cop30m"
SUBDIR = "cop30m"
PX = 3600  # celic na stopinjo pri širinah < 50°
DX = 1.0 / PX


def tiles_needed(lat0, lon0, lat1, lon1):
    """Cela stopinjska polja (jugozahodni kot), ki pokrijejo okvir; vrstni red: od juga proti severu, od zahoda."""
    la0, la1 = math.floor(lat0), math.floor(lat1 - 1e-9)
    lo0, lo1 = math.floor(lon0), math.floor(lon1 - 1e-9)
    return [(la, lo) for la in range(la0, la1 + 1) for lo in range(lo0, lo1 + 1)]


def tile_name(ix, iy, size=PX):
    """Ime ploščice WPS: 'xxxxx-xxxxx.yyyyy-yyyyy' (1-based, 5 številk)."""
    x0, y0 = ix * size + 1, iy * size + 1
    return f"{x0:05d}-{x0 + size - 1:05d}.{y0:05d}-{y0 + size - 1:05d}"


def index_text(lat_min, lon_min, size=PX):
    """Datoteka `index`: opis mreže regular_ll z začetkom (1,1) v središču jugozahodne celice."""
    return "\n".join([
        "type=continuous", "signed=yes", "projection=regular_ll",
        f"dx={DX:.12f}", f"dy={DX:.12f}", "known_x=1.0", "known_y=1.0",
        f"known_lon={lon_min + 0.5 * DX:.9f}", f"known_lat={lat_min + 0.5 * DX:.9f}",
        "wordsize=2", "endian=little", f"tile_x={size}", f"tile_y={size}", "tile_z=1",
        'units="meters MSL"', 'description="Copernicus GLO-30 DEM"', "missing_value=-32768", ""])


def write_tile(arr_north_first, path):
    """int16, little endian, vrstice od juga proti severu (TIFF jih ima od severa → obrnemo)."""
    import numpy as np
    a = np.flipud(np.asarray(arr_north_first))
    a = np.clip(np.rint(a), -32767, 32767).astype("<i2")
    a.tofile(path)


def read_tile(path, size=PX):
    """Obratno od write_tile (za teste): vrne polje s severom zgoraj."""
    import numpy as np
    return np.flipud(np.fromfile(path, dtype="<i2").reshape(size, size))


def download(lat, lon, dest):
    url = URL.format(lat=lat, lon=lon)
    req = urllib.request.Request(url, headers={"User-Agent": "Meteorec/1.0 (+https://meteorec.si)"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())


def build(geog_dir, bbox):
    import tempfile
    import tifffile
    out = os.path.join(geog_dir, SUBDIR)
    os.makedirs(out, exist_ok=True)
    tl = tiles_needed(*bbox)
    la_min = min(t[0] for t in tl)
    lo_min = min(t[1] for t in tl)
    with open(os.path.join(out, "index"), "w") as f:
        f.write(index_text(la_min, lo_min))
    for lat, lon in tl:
        with tempfile.NamedTemporaryFile(suffix=".tif") as tmp:
            download(lat, lon, tmp.name)
            arr = tifffile.imread(tmp.name)
        if arr.shape != (PX, PX):
            raise RuntimeError(f"N{lat} E{lon}: nepričakovana velikost {arr.shape} (pričakovano {PX}×{PX})")
        name = tile_name(lon - lo_min, lat - la_min)
        write_tile(arr, os.path.join(out, name))
        print(f"  N{lat} E{lon} → {SUBDIR}/{name}")
    return out


def patch_table_text(text):
    """V blok HGT_M doda vir `cop30m` (ostali ostanejo, privzet vir za druge domene se ne spremeni). Idempotentno."""
    if f"{RES_NAME}:" in text:
        return text
    blk = re.search(r"^name\s*=\s*HGT_M\s*$", text, re.M)
    if not blk:
        raise ValueError("v GEOGRID.TBL ni bloka HGT_M")
    first = re.compile(r"^[ \t]*interp_option\s*=", re.M).search(text, blk.end())
    if not first:
        raise ValueError("v bloku HGT_M ni interp_option")
    ins = (f"        interp_option = {RES_NAME}:average_gcell(4.0)+four_pt+average_4pt\n"
           f"        rel_path = {RES_NAME}:{SUBDIR}/\n")
    return text[:first.start()] + ins + text[first.start():]


def set_smooth_passes(text, passes):
    """V bloku HGT_M nastavi smooth_passes (privzeto 1). Strm teren pri 0,5 km se brez več glajenja lahko sesuje."""
    blk = re.search(r"^name\s*=\s*HGT_M\s*$", text, re.M)
    if not blk:
        raise ValueError("v GEOGRID.TBL ni bloka HGT_M")
    end = re.search(r"^=+\s*$", text[blk.end():], re.M)
    stop = blk.end() + (end.start() if end else len(text) - blk.end())
    seg = text[blk.end():stop]
    if re.search(r"smooth_passes\s*=", seg):
        seg = re.sub(r"smooth_passes\s*=\s*\d+", f"smooth_passes={passes}", seg, count=1)
    else:
        raise ValueError("v bloku HGT_M ni smooth_passes")
    return text[:blk.end()] + seg + text[stop:]


def patch_table(path, smooth=None, add_dem=True):
    real = os.path.realpath(path)
    with open(real) as f:
        t = f.read()
    new = patch_table_text(t) if add_dem else t
    if smooth:
        new = set_smooth_passes(new, smooth)
    if new != t:
        with open(real, "w") as f:
            f.write(new)
    return new != t


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("geog_dir")
    b.add_argument("--bbox", nargs=4, type=float, metavar=("LAT0", "LON0", "LAT1", "LON1"),
                   default=[45.4, 13.8, 47.3, 16.1])
    p = sub.add_parser("patch-table")
    p.add_argument("table")
    p.add_argument("--smooth", type=int, default=None, help="število prehodov glajenja terena (HGT_M)")
    p.add_argument("--no-dem", action="store_true", help="samo glajenje, brez vira cop30m")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.geog_dir, a.bbox)
    else:
        print("  GEOGRID.TBL:", "popravljen" if patch_table(a.table, a.smooth, not a.no_dem) else "brez sprememb")
    return 0


if __name__ == "__main__":
    sys.exit(main())
