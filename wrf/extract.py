#!/usr/bin/env python3
"""
wrf/extract.py — iz `wrfout_d0N_*` izlušči napoved za točko Rečice ob Savinji (najbližja celica najgostejše domene)
in jo zapiše kot majhen JSON (urne vrednosti + dnevni povzetek po lokalnem času).

Zakaj JSON in ne wrfout: wrfout so gigabajti; v repozitorij gre samo ta izvleček (`data/wrf/recica-<tek>.json`).

Kar izvleček je in ni:
- MODELSKI IZHOD za eno celico (0,5 km), ne meritev. Višina celice modela je zapisana, ker se od postaje razlikuje.
- Dnevni Tmin/Tmax sta iz izhoda na 30 minut (d04) — to je blizu, a ni enako izmerjenemu minimumu/maksimumu.
- Padavine so razlika akumulacije RAINC+RAINNC; negativne vrednosti (ponastavitev) se odrežejo na 0.
- Veter na 10 m je trenutna vrednost ob času izhoda, NE sunek.

Usage (v vsebniku ali kjer je netCDF4):
  python3 wrf/extract.py --dir /work/run --out /work/recica.json [--domain 4] [--lat 46.33 --lon 14.92]
"""
import argparse
import datetime
import glob
import json
import math
import os
import sys

LAT, LON = 46.33, 14.92


def nearest_cell(xlat, xlong, lat, lon):
    """Indeks (j, i) celice, ki je najbližje točki (ravninska razdalja s popravkom cos φ je dovolj za 0,5 km)."""
    import numpy as np
    d = (xlat - lat) ** 2 + ((xlong - lon) * math.cos(math.radians(lat))) ** 2
    j, i = np.unravel_index(int(np.argmin(d)), d.shape)
    return int(j), int(i)


def parse_wrf_times(char_array):
    """Times (matrika znakov 'YYYY-MM-DD_HH:MM:SS' kot bajti ali nizi) → seznam datetime."""
    out = []
    for row in char_array:
        chars = [c.decode() if isinstance(c, (bytes, bytearray)) else str(c) for c in row]
        out.append(datetime.datetime.strptime("".join(chars).strip(), "%Y-%m-%d_%H:%M:%S"))
    return out


def wind_dir_from(u, v):
    """Smer, ODKOD piha veter (°), iz komponent u (proti vzhodu) in v (proti severu)."""
    return (math.degrees(math.atan2(-u, -v)) + 360.0) % 360.0


def hourly_series(files, lat=LAT, lon=LON):
    """Prebere vse datoteke domene in vrne (meta, vrstice). Padavine: razlika akumulacije med zaporednimi časi."""
    from netCDF4 import Dataset
    import numpy as np
    rows = []
    meta = None
    prev_rain = None
    for path in sorted(files):
        with Dataset(path) as nc:
            if meta is None:
                xlat = np.array(nc.variables["XLAT"][0])
                xlong = np.array(nc.variables["XLONG"][0])
                j, i = nearest_cell(xlat, xlong, lat, lon)
                meta = {"cell_lat": float(xlat[j, i]), "cell_lon": float(xlong[j, i]), "j": j, "i": i,
                        "model_height_m": float(np.array(nc.variables["HGT"][0])[j, i]),
                        "dx_m": float(nc.getncattr("DX")), "title": str(nc.getncattr("TITLE"))}
            times = parse_wrf_times(nc.variables["Times"][:])
            for k, t in enumerate(times):
                t2 = float(nc.variables["T2"][k, meta["j"], meta["i"]]) - 273.15
                u = float(nc.variables["U10"][k, meta["j"], meta["i"]])
                v = float(nc.variables["V10"][k, meta["j"], meta["i"]])
                rain = float(nc.variables["RAINNC"][k, meta["j"], meta["i"]])
                if "RAINC" in nc.variables:
                    rain += float(nc.variables["RAINC"][k, meta["j"], meta["i"]])
                step_mm = 0.0 if prev_rain is None else max(0.0, rain - prev_rain)
                prev_rain = rain
                q2 = float(nc.variables["Q2"][k, meta["j"], meta["i"]])
                psfc = float(nc.variables["PSFC"][k, meta["j"], meta["i"]])
                rows.append({
                    "t": t.strftime("%Y-%m-%dT%H:%M"),
                    "t2_c": round(t2, 2), "wind_ms": round(math.hypot(u, v), 2),
                    "wind_dir": round(wind_dir_from(u, v)), "precip_mm": round(step_mm, 3),
                    "rh2_pct": round(rh_from_q(q2, psfc, t2), 1), "psfc_hpa": round(psfc / 100.0, 1),
                    "swdown_wm2": round(float(nc.variables["SWDOWN"][k, meta["j"], meta["i"]]), 0)
                    if "SWDOWN" in nc.variables else None,
                    "pblh_m": round(float(nc.variables["PBLH"][k, meta["j"], meta["i"]]), 0)
                    if "PBLH" in nc.variables else None,
                })
    return meta, rows


def rh_from_q(q2, psfc_pa, t2_c):
    """Relativna vlaga (%) iz mešalnega razmerja Q2 (kg/kg), tlaka (Pa) in temperature (°C); Magnus/Bolton."""
    es = 611.2 * math.exp(17.67 * t2_c / (t2_c + 243.5))  # Pa
    e = q2 * psfc_pa / (0.622 + q2)
    return max(0.0, min(100.0, 100.0 * e / es))


def _last_sunday(year, month):
    d = datetime.date(year, month, 31)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def utc_offset_hours(dt_utc):
    """Zamik Europe/Ljubljana od UTC (ur): poletni čas od zadnje nedelje marca 01:00 UTC do zadnje nedelje oktobra 01:00 UTC.
    Ročno, ker je Python 3.8 v vsebniku (Ubuntu 20.04) brez `zoneinfo`; `tools/test_wrf.py` primerja s `zoneinfo`."""
    y = dt_utc.year
    start = datetime.datetime.combine(_last_sunday(y, 3), datetime.time(1, 0))
    end = datetime.datetime.combine(_last_sunday(y, 10), datetime.time(1, 0))
    return 2 if start <= dt_utc.replace(tzinfo=None) < end else 1


def to_local_date(iso_utc):
    dt = datetime.datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M")
    return (dt + datetime.timedelta(hours=utc_offset_hours(dt))).date().isoformat()


def daily_summary(rows, min_hours=20):
    """Dnevni povzetek po LOKALNEM dnevu. Dan z manj kot `min_hours` ur izhoda je označen kot delen."""
    by = {}
    for r in rows:
        by.setdefault(to_local_date(r["t"]), []).append(r)
    out = {}
    for day, rs in sorted(by.items()):
        span_h = len(rs) * (_step_hours(rows))
        out[day] = {"tmax_c": round(max(r["t2_c"] for r in rs), 1), "tmin_c": round(min(r["t2_c"] for r in rs), 1),
                    "precip_mm": round(sum(r["precip_mm"] for r in rs), 1), "n": len(rs),
                    "complete": span_h >= min_hours}
    return out


def _step_hours(rows):
    if len(rows) < 2:
        return 1.0
    a = datetime.datetime.strptime(rows[0]["t"], "%Y-%m-%dT%H:%M")
    b = datetime.datetime.strptime(rows[1]["t"], "%Y-%m-%dT%H:%M")
    return max((b - a).total_seconds() / 3600.0, 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--domain", type=int, default=None, help="privzeto: najvišja številka domene")
    ap.add_argument("--init", default=None, help="YYYYMMDDHH zagona (za zapis)")
    ap.add_argument("--lat", type=float, default=LAT)
    ap.add_argument("--lon", type=float, default=LON)
    a = ap.parse_args()
    files = glob.glob(os.path.join(a.dir, "wrfout_d*"))
    if not files:
        print("✗ ni datotek wrfout", file=sys.stderr)
        return 1
    dom = a.domain or max(int(os.path.basename(f).split("_")[1][1:]) for f in files)
    sel = [f for f in files if os.path.basename(f).startswith(f"wrfout_d{dom:02d}_")]
    meta, rows = hourly_series(sel, a.lat, a.lon)
    result = {"init": a.init, "domain": dom, "point": {"lat": a.lat, "lon": a.lon}, "cell": meta,
              "step_min": round(_step_hours(rows) * 60), "hourly": rows, "daily": daily_summary(rows),
              "source": "WRF-ARW 4.6.1, lasten tek (GFS 0.25 robni pogoji), modelski izhod za eno celico"}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  → {a.out}: d{dom:02d}, {len(rows)} korakov, celica {meta['cell_lat']:.3f}, {meta['cell_lon']:.3f}, "
          f"višina {meta['model_height_m']:.0f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
