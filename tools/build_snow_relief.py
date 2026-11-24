#!/usr/bin/env python3
"""
tools/build_snow_relief.py -- ENKRATEN (ročen) izračun podlage za snežno karto (/zima/snezna-karta/).

Iz Copernicus GLO-30 (AWS Open Data) naredi temno senčeno reliefno podlago v ISTEM okvirju kot mreža workerja
(`MK_LAT0` 45,4, `MK_LON0` 13,3, korak 0,1°, 35 × 16 točk: lon 13,3–16,7, lat 45,4–46,9) in jo zapiše v
`zima/snezna-karta/relief.webp`. Izhod je commitan, skript se ne poganja po urniku.

Podlaga je samo prikaz: nobene številke ne izhajajo iz nje. Izvor DEM-a je naveden na strani (pogoj licence).

Usage:
    pip install tifffile imagecodecs numpy pillow
    python3 tools/build_snow_relief.py [--dem-dir DIR]
"""
import argparse
import math
import os
import sys
import urllib.request

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "zima", "snezna-karta", "relief.webp")
LAT0, LAT1, LON0, LON1 = 45.4, 46.9, 13.3, 16.7          # okvir mreže (središča skrajnih celic), kot v worker.js
TILES_LAT = (45, 46)                                       # ploščica N45 = 45–46 °N, N46 = 46–47 °N
TILES_LON = (13, 14, 15, 16)                               # E013 = 13–14 °E ...
PX = 3600                                                  # celic na ploščico (1″)
BLOCK = 9                                                  # povprečenje 9 × 9: 0,0025° ≈ 190 × 280 m
URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
       "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif")
UA = "meteorec.si relief builder (+https://meteorec.si)"


def fetch(dem_dir):
    os.makedirs(dem_dir, exist_ok=True)
    for la in TILES_LAT:
        for lo in TILES_LON:
            path = os.path.join(dem_dir, f"N{la}_E{lo:03d}.tif")
            if os.path.exists(path):
                continue
            print("  ↓", path)
            req = urllib.request.Request(URL.format(lat=la, lon=lo), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as fh:
                fh.write(r.read())


def load(dem_dir):
    """Združeno, blokovno povprečeno polje (sever zgoraj): 4° lon × 2° lat."""
    import tifffile
    rows = []
    for la in sorted(TILES_LAT, reverse=True):        # sever zgoraj
        parts = []
        for lo in TILES_LON:
            a = tifffile.imread(os.path.join(dem_dir, f"N{la}_E{lo:03d}.tif")).astype("float32")
            a = a[:PX, :PX]
            n = PX // BLOCK
            parts.append(a[:n * BLOCK, :n * BLOCK].reshape(n, BLOCK, n, BLOCK).mean(axis=(1, 3)))
        rows.append(np.concatenate(parts, axis=1))
    return np.concatenate(rows, axis=0)


def hillshade(z, dx, dy, az=315.0, alt=42.0, exag=2.2):
    gy, gx = np.gradient(z * exag, dy, dx)            # gy: sprememba proti jugu (vrstice navzdol)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    azr, altr = math.radians(360 - az + 90), math.radians(alt)
    hs = np.sin(altr) * np.cos(slope) + np.cos(altr) * np.sin(slope) * np.cos(azr - aspect)
    return np.clip(hs, 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem-dir", default=os.path.join("/tmp", "snow-relief-dem"))
    args = ap.parse_args()
    fetch(args.dem_dir)
    z = load(args.dem_dir)
    step = 1.0 / (PX // BLOCK)                       # stopinj na celico
    # izrez okvirja mreže
    x0, x1 = round((LON0 - TILES_LON[0]) / step), round((LON1 - TILES_LON[0]) / step)
    y0, y1 = round((TILES_LAT[-1] + 1 - LAT1) / step), round((TILES_LAT[-1] + 1 - LAT0) / step)
    zc = z[y0:y1, x0:x1]
    mid = math.radians((LAT0 + LAT1) / 2)
    dx, dy = step * 111320 * math.cos(mid), step * 111320
    hs = hillshade(zc, dx, dy)
    # barva: temno modra, višje svetleje; morje (≤ 0 m) najtemnejše
    h = np.clip(zc / 2400.0, 0, 1)[..., None]
    lo = np.array([13, 24, 40], dtype="float32")       # dolina
    hi = np.array([88, 112, 142], dtype="float32")     # visoke gore
    base = lo + (hi - lo) * h
    shade = (0.45 + 0.85 * hs)[..., None]
    rgb = np.clip(base * shade, 0, 255)
    sea = (zc <= 1.0)[..., None]
    rgb = np.where(sea, np.array([8, 15, 28], dtype="float32"), rgb)
    img = Image.fromarray(rgb.astype("uint8"), "RGB")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "WEBP", quality=80, method=6)
    print(f"✓ {OUT}: {img.size[0]}×{img.size[1]} px, {os.path.getsize(OUT) // 1024} kB, višina {zc.min():.0f}–{zc.max():.0f} m")


if __name__ == "__main__":
    sys.exit(main())
