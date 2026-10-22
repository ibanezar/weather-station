#!/usr/bin/env python3
"""
wrf/limit_slope.py — omejitev naklona terena v geo_em.d0N.nc (HGT_M) pred metgridom.

Zakaj: Copernicus 30 m, povprečen na 0,5 km mrežo, ima naklone do ~40° (Kamniško-Savinjske Alpe). Koordinata WRF, ki sledi
terenu, se pri tem sesuje — prvi poskus lastnega teka je 1–3 sekunde po začetku zrasel w na 10³ m/s v najstrmejši celici
(v_cfl), ne glede na korak (1–2 s), diff_opt, epssm in dodatno enakomerno glajenje. Zato se samo celice s preveč strmim
naklonom gladijo (dokler naklon ne pade pod prag), ostalo ostane nedotaknjeno.

Gladi se samo HGT_M (metgrid ga prepiše v met_em, real ga vzame od tam). SLPX/SLPY in HGT_U/V ostanejo iz geogrida; za
pobočno sevanje je razlika zanemarljiva, a ni enaka — to je izrecno kompromis.

Usage:
  python3 wrf/limit_slope.py geo_em.d04.nc [geo_em.d03.nc …] [--max-deg 22]
"""
import argparse
import math
import sys


def max_slope_deg(h, dx):
    import numpy as np
    gy, gx = np.gradient(h, dx)
    return float(np.degrees(np.arctan(np.hypot(gx, gy).max())))


def limit_slope(h, dx, max_deg=22.0, max_iter=400, blend=0.5):
    """Vrne (nov h, število iteracij, delež spremenjenih celic). Gladi samo celice z naklonom nad pragom in njihovo okolico."""
    import numpy as np
    h = np.array(h, dtype="float64", copy=True)
    h0 = h.copy()
    thr = math.tan(math.radians(max_deg))
    it = 0
    for it in range(1, max_iter + 1):
        gy, gx = np.gradient(h, dx)
        steep = np.hypot(gx, gy) > thr
        if not steep.any():
            it -= 1
            break
        mask = steep.copy()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):  # razširi za eno celico
            mask |= np.roll(steep, (dj, di), axis=(0, 1))
        p = np.pad(h, 1, mode="edge")
        mean3 = sum(p[1 + dj:1 + dj + h.shape[0], 1 + di:1 + di + h.shape[1]]
                    for dj in (-1, 0, 1) for di in (-1, 0, 1)) / 9.0
        h = np.where(mask, (1 - blend) * h + blend * mean3, h)
    changed = float((np.abs(h - h0) > 0.5).mean())
    return h, it, changed


def process(path, max_deg):
    from netCDF4 import Dataset
    import numpy as np
    with Dataset(path, "r+") as nc:
        dx = float(nc.getncattr("DX"))
        h = np.array(nc.variables["HGT_M"][0])
        before = max_slope_deg(h, dx)
        new, it, frac = limit_slope(h, dx, max_deg)
        nc.variables["HGT_M"][0] = new.astype(h.dtype)
        after = max_slope_deg(new, dx)
    return {"dx": dx, "before_deg": round(before, 1), "after_deg": round(after, 1), "iter": it, "changed": round(frac, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-deg", type=float, default=22.0)
    a = ap.parse_args()
    for f in a.files:
        r = process(f, a.max_deg)
        print(f"  {f}: naklon {r['before_deg']}° → {r['after_deg']}° ({r['iter']} iteracij, "
              f"{100 * r['changed']:.1f} % celic spremenjenih)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
