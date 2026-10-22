#!/usr/bin/env python3
"""
wrf/fetch_gfs.py — robni in začetni pogoji za WRF: NOAA GFS 0,25° (AWS Open Data, brez ključa).

Iz `.idx` vsake datoteke izbere samo polja, ki jih potrebuje `Vtable.GFS` (tlačni nivoji HGT/TMP/UGRD/VGRD/RH,
prizemlje 2 m/10 m, tlak, tla in snežna odeja), in jih prenese prek bajtnih območij — ~120 MB namesto ~500 MB
na datoteko. WPS `ungrib` bere takšno združeno datoteko neposredno.

Domen ne obrezuje (to bi zahtevalo wgrib2); zaradi tega je prenos ~1,5 GB na tek, kar strežnik opravi v minuti.

Usage:
  python3 wrf/fetch_gfs.py --init 2026102212 --hours 36 --out /work/gfs [--step 3]
  python3 wrf/fetch_gfs.py --latest --hours 36 --out /work/gfs
"""
import argparse
import datetime
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.{ymd}/{hh}/atmos/gfs.t{hh}z.pgrb2.0p25.f{fff:03d}"
UA = "Meteorec/1.0 (+https://meteorec.si)"

PRESSURE_VARS = {"HGT", "TMP", "UGRD", "VGRD", "RH"}
# (spremenljivka, niz ravni) v .idx: surovo besedilo med 4. in 5. poljem
SURFACE_FIELDS = {
    ("PRES", "surface"), ("MSLET", "mean sea level"), ("HGT", "surface"), ("TMP", "surface"),
    ("TMP", "2 m above ground"), ("RH", "2 m above ground"), ("UGRD", "10 m above ground"),
    ("VGRD", "10 m above ground"), ("LAND", "surface"), ("ICEC", "surface"), ("WEASD", "surface"),
    ("SNOD", "surface"),
    ("SOILW", "0-0.1 m below ground"), ("SOILW", "0.1-0.4 m below ground"), ("SOILW", "0.4-1 m below ground"),
    ("SOILW", "1-2 m below ground"), ("TSOIL", "0-0.1 m below ground"), ("TSOIL", "0.1-0.4 m below ground"),
    ("TSOIL", "0.4-1 m below ground"), ("TSOIL", "1-2 m below ground"),
}
PL_RE = re.compile(r"^\d+(\.\d+)? mb$")


def wanted(var, level):
    """Ali polje `var` na ravni `level` (besedilo iz .idx) potrebuje Vtable.GFS."""
    if var in PRESSURE_VARS and PL_RE.match(level):
        return True
    return (var, level) in SURFACE_FIELDS


def select_ranges(idx_text):
    """.idx → seznam združenih bajtnih območij [(start, end|None)] za potrebna polja, po vrstnem redu v datoteki."""
    rows = []
    for ln in idx_text.splitlines():
        p = ln.split(":")
        if len(p) > 5 and p[1].isdigit():
            rows.append((int(p[1]), p[3], p[4], p[5]))
    ranges = []
    for i, (start, var, level, kind) in enumerate(rows):
        # »anl« ali »N hour fcst«: pri f000 je to analiza, pri drugih urah napoved; obe vzamemo; izpusti
        # povprečja in akumulacije (»0-N hour ave/acc«), ki jih Vtable ne uporablja
        if "ave" in kind or "acc" in kind or "max" in kind or "min" in kind:
            continue
        if not wanted(var, level):
            continue
        end = rows[i + 1][0] - 1 if i + 1 < len(rows) else None
        if ranges and ranges[-1][1] is not None and ranges[-1][1] + 1 == start:
            ranges[-1] = (ranges[-1][0], end)
        else:
            ranges.append((start, end))
    return ranges


def get(url, headers=None, tries=4, timeout=120):
    hdr = {"User-Agent": UA}
    hdr.update(headers or {})
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(4 * (i + 1))
    raise last


def url_for(init, step):
    return BASE.format(ymd=init.strftime("%Y%m%d"), hh=f"{init.hour:02d}", fff=step)


def available(init, step):
    try:
        get(url_for(init, step) + ".idx", tries=1, timeout=30)
        return True
    except Exception:  # noqa: BLE001
        return False


def latest_init(hours, now=None):
    """Zadnji tek GFS (00/06/12/18 UTC), ki ima že zadnji zahtevani korak."""
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    t = datetime.datetime(now.year, now.month, now.day, (now.hour // 6) * 6)
    for _ in range(8):
        if available(t, hours):
            return t
        t -= datetime.timedelta(hours=6)
    raise RuntimeError("noben GFS tek ni dosegljiv")


def download_step(init, step, out_dir):
    url = url_for(init, step)
    ranges = select_ranges(get(url + ".idx").decode())
    if not ranges:
        raise RuntimeError(f"f{step:03d}: v .idx ni nobenega zahtevanega polja")
    path = os.path.join(out_dir, f"gfs.t{init.hour:02d}z.f{step:03d}.grib2")
    with open(path, "wb") as f:
        for start, end in ranges:
            rng = f"bytes={start}-{end}" if end is not None else f"bytes={start}-"
            f.write(get(url, headers={"Range": rng}))
    return path, os.path.getsize(path)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--init", help="YYYYMMDDHH (UTC)")
    g.add_argument("--latest", action="store_true")
    ap.add_argument("--hours", type=int, required=True)
    ap.add_argument("--step", type=int, default=3)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    init = latest_init(a.hours) if a.latest else datetime.datetime.strptime(a.init, "%Y%m%d%H")
    os.makedirs(a.out, exist_ok=True)
    total = 0
    for step in range(0, a.hours + 1, a.step):
        path, size = download_step(init, step, a.out)
        total += size
        print(f"  f{step:03d}: {size / 1e6:.0f} MB", flush=True)
    print(f"  tek {init:%Y-%m-%d %H} UTC: {total / 1e6:.0f} MB → {a.out}")
    # za razčlenitev v run.sh
    with open(os.path.join(a.out, "INIT"), "w") as f:
        f.write(init.strftime("%Y%m%d%H"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
