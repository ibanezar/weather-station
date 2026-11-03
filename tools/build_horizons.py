#!/usr/bin/env python3
"""
tools/build_horizons.py — ENKRATNO: obzorje (višina hribov nad ravnino po azimutih) za kraje v Zgornji Savinjski dolini.

Vir: Copernicus GLO-30 DEM (30 m, AWS Open Data). © DLR e.V. 2010–2014 in © Airbus Defence and Space GmbH 2014–2018,
licenca Copernicus (prosta uporaba z navedbo). Izhod `data/horizons.json` je committan; stran `/sonce-v-dolini/`
(`generate_sonce_page.py`) DEM-a ne rabi.

Kaj je izmerjeno in česa ni:
- DEM je površinski model (DSM): drevesa in hiše so v njem. Zato se prvih `SKIP_M` (150 m) žarka preskoči: najbližja
  drevesa in strehe sicer zakrijejo sonce v vsakem kraju in bi to bilo napačno za »dolino«. Gozd na pobočju
  (> 150 m) ostane v modelu, kar obzorje morda za ~1–3° zviša.
- Obzorje velja za eno točko (središče kraja). Že 300 m stran je lahko drugače, zlasti pod pobočjem.
- Ukrivljenost Zemlje in refrakcija sta všteti (koeficient 0,13).

Usage:
  pip install numpy tifffile imagecodecs
  python3 tools/build_horizons.py --dem-dir DIR      # DIR vsebuje N46_E014.tif in N46_E015.tif (glej DEM_URL)
  python3 tools/build_horizons.py --download DIR     # ju najprej prenese
"""
import argparse
import json
import math
import os
import sys
import urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — NEARBY_TOWNS/LAT/LON/ELEV, uvoženo ne podvojeno
from sonce_horizont import HORIZONS_PATH  # noqa: E402

DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
           "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif")
TILES = [(46, 14), (46, 15)]  # pokrijeta 14–16 °E, 46–47 °N: vsi kraji so ≥ 25 km od roba
PX = 3600
SKIP_M = 150
MAX_M = 30000
AZ_STEP = 0.5
K_REFRACT = 0.13
R_EARTH = 6371000.0

PLACES = [{"id": "recica", "name": "Rečica ob Savinji", "lat": seo.LAT, "lon": seo.LON, "elev": seo.ELEV}] + [
    {"id": t["slug"].replace("vreme-", ""), "name": t["town"], "lat": t["lat"], "lon": t["lon"], "elev": t["elev"]}
    for t in seo.NEARBY_TOWNS]


def download(dem_dir):
    os.makedirs(dem_dir, exist_ok=True)
    for la, lo in TILES:
        path = os.path.join(dem_dir, f"N{la}_E{lo:03d}.tif")
        if not os.path.exists(path):
            print("  ↓", path)
            urllib.request.urlretrieve(DEM_URL.format(lat=la, lon=lo), path)


def load_dem(dem_dir):
    """Združeno polje 3600 × 7200 (sever zgoraj): stolpci 14–16 °E, vrstice 47 → 46 °N."""
    import tifffile
    parts = [tifffile.imread(os.path.join(dem_dir, f"N{la}_E{lo:03d}.tif")).astype("float32") for la, lo in TILES]
    return np.concatenate(parts, axis=1)


def sample(dem, lat, lon):
    """Bilinearno vzorčenje (lat/lon sta polji). Ploščice imajo celice 1″ in središče prve celice 0,5″ od roba."""
    x = (lon - 14.0) * PX - 0.5
    y = (47.0 - lat) * PX - 0.5
    x0 = np.clip(np.floor(x).astype(int), 0, dem.shape[1] - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, dem.shape[0] - 2)
    fx, fy = x - x0, y - y0
    return (dem[y0, x0] * (1 - fx) * (1 - fy) + dem[y0, x0 + 1] * fx * (1 - fy)
            + dem[y0 + 1, x0] * (1 - fx) * fy + dem[y0 + 1, x0 + 1] * fx * fy)


def horizon_profile(dem, lat, lon, obs_h):
    """Višina obzorja (°) po azimutih 0…359 (1° korak; vsak je največ dveh vzorcev po 0,5°)."""
    d = np.concatenate([np.arange(SKIP_M, 3000, 30.0), np.arange(3000, MAX_M + 1, 90.0)])
    drop = (d ** 2) / (2 * R_EARTH) * (1 - K_REFRACT)
    n = int(round(360 / AZ_STEP))
    res = np.zeros(n)
    for i in range(n):
        az = math.radians(i * AZ_STEP)
        la = lat + d * math.cos(az) / 111320.0
        lo = lon + d * math.sin(az) / (111320.0 * math.cos(math.radians(lat)))
        h = sample(dem, la, lo)
        ang = np.degrees(np.arctan2(h - obs_h - drop, d))
        res[i] = max(ang.max(), 0.0)
    # 1° korak: največ med vzorcema v razponu ±0,5° okoli vsakega celega azimuta
    per = int(round(1 / AZ_STEP))
    out = []
    for k in range(360):
        idx = [(k * per + j) % n for j in range(-per // 2, per // 2 + 1)]
        out.append(round(float(res[idx].max()), 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem-dir", help="mapa z N46_E014.tif in N46_E015.tif")
    ap.add_argument("--download", help="prenesi ploščici v to mapo in jo uporabi")
    a = ap.parse_args()
    d = a.download or a.dem_dir
    if not d:
        ap.error("podaj --dem-dir ali --download")
    if a.download:
        download(d)
    dem = load_dem(d)
    out = {"generated": "2026-11-03", "source": "Copernicus GLO-30 DEM", "skip_m": SKIP_M, "max_m": MAX_M, "places": []}
    for p in PLACES:
        ground = float(sample(dem, np.array([p["lat"]]), np.array([p["lon"]]))[0])
        h = horizon_profile(dem, p["lat"], p["lon"], ground + 1.5)
        print(f"  {p['name']:<20} DEM {ground:6.0f} m (zapisano {p['elev']} m)  obzorje: povprečje {np.mean(h):4.1f}°, "
              f"največ {max(h):4.1f}° pri azimutu {h.index(max(h))}°")
        out["places"].append({**p, "dem_m": round(ground), "horizon": h})
    with open(HORIZONS_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("  →", HORIZONS_PATH)


if __name__ == "__main__":
    main()
