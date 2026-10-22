#!/usr/bin/env python3
"""
tools/build_europe_outline.py — ENKRATNO: obris obal in državnih meja Evrope → data/europe-outline.json

Natural Earth 50 m (javna domena, naturalearthdata.com): obala in kopenske državne meje, odrezane na okvir
zemljevidov (BBOX), koordinate zaokrožene na 2 decimalki. Izhod je commitan; karte (sinoptična, prah) ga berejo
iz repozitorija in tako ne potrebujejo omrežja ob risanju.

Usage:
  python3 tools/build_europe_outline.py <mapa_z_ne_50m_coastline> <mapa_z_ne_50m_admin_0_boundary_lines_land>
Potrebuje pyshp (pip install pyshp).
"""
import json
import os
import sys

import shapefile  # pyshp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "europe-outline.json")
# Malo širše od okvirja kart (atmos_common.MAP_BBOX), da robovi pri projekciji ne ostanejo prazni.
BBOX = (-40.0, 20.0, 65.0, 80.0)  # lon0, lat0, lon1, lat1


def lines(dirpath):
    base = [f for f in os.listdir(dirpath) if f.endswith(".shp")][0]
    sf = shapefile.Reader(os.path.join(dirpath, base))
    out = []
    for shp in sf.shapes():
        parts = list(shp.parts) + [len(shp.points)]
        for a, b in zip(parts[:-1], parts[1:]):
            seg = [(round(x, 2), round(y, 2)) for x, y in shp.points[a:b]]
            run = []
            for x, y in seg:  # obdrži samo točke v okvirju; prekinitev loči poteze
                if BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]:
                    run.append([x, y])
                elif len(run) > 1:
                    out.append(run)
                    run = []
                else:
                    run = []
            if len(run) > 1:
                out.append(run)
    return out


def main():
    coast = lines(sys.argv[1])
    borders = lines(sys.argv[2])
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"source": "Natural Earth 50m (public domain)", "bbox": BBOX,
                   "coast": coast, "borders": borders}, f, separators=(",", ":"))
    print(f"  → {OUT}: obala {len(coast)} potez, meje {len(borders)} potez, "
          f"{os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
