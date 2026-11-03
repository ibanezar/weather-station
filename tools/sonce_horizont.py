#!/usr/bin/env python3
"""
tools/sonce_horizont.py — položaj sonca in obzorje iz terena (knjižnica za /sonce-v-dolini/ in analize).

Dva dela, oba brez omrežja:
- `sun_position()` — NOAA/Meeus algoritem (točnost ~0,01°): višina in azimut sonca (od severa v smeri urnega kazalca).
- `day_profile()` — za en kraj in en dan: kdaj sonce po koledarju vzide/zaide (ravno obzorje) in kdaj ga
  dejansko vidimo prvič/zadnjič, če nas pred njim zakrivajo hribi (obzorje iz `data/horizons.json`).

Obzorje piše enkraten `tools/build_horizons.py` iz Copernicus DEM (terena, ne dreves in hiš: glej opombo tam).

Sonce štejemo za »vidno«, ko je zgornji rob diska nad obzorjem: geometrična višina središča + 0,833° (refrakcija
in polmer diska, enako kot pri koledarskem vzhodu) > višina obzorja v azimutu sonca (obzorje ni nižje od 0°).
"""
import datetime
import json
import math
import os
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HORIZONS_PATH = os.path.join(ROOT, "data", "horizons.json")
TZ = ZoneInfo("Europe/Ljubljana")
SUN_RISE_DEG = -0.833  # geometrična višina središča pri koledarskem vzhodu/zahodu
REFERENCE_YEAR = 2027  # nevisokosno leto; zamik med leti je pod minuto


def sun_position(lat, lon, unix_s):
    """Višina (°) in azimut (° od severa, v smeri urnega kazalca) sonca za polje časov UTC (sekunde od 1970)."""
    unix_s = np.asarray(unix_s, dtype=float)
    jd = unix_s / 86400.0 + 2440587.5
    t = (jd - 2451545.0) / 36525.0
    rad = np.radians
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (np.sin(rad(m)) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + np.sin(rad(2 * m)) * (0.019993 - 0.000101 * t) + np.sin(rad(3 * m)) * 0.000289)
    app_long = l0 + c - 0.00569 - 0.00478 * np.sin(rad(125.04 - 1934.136 * t))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * np.cos(rad(125.04 - 1934.136 * t))
    decl = np.arcsin(np.sin(rad(eps)) * np.sin(rad(app_long)))
    y = np.tan(rad(eps / 2)) ** 2
    eqt = 4 * np.degrees(y * np.sin(rad(2 * l0)) - 2 * e * np.sin(rad(m))
                         + 4 * e * y * np.sin(rad(m)) * np.cos(rad(2 * l0))
                         - 0.5 * y * y * np.sin(rad(4 * l0)) - 1.25 * e * e * np.sin(rad(2 * m)))
    utc_min = (unix_s / 60.0) % 1440
    tst = (utc_min + eqt + 4 * lon) % 1440
    ha = rad(tst / 4 - 180)
    la = rad(lat)
    cosz = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha)
    elev = 90 - np.degrees(np.arccos(np.clip(cosz, -1, 1)))
    az = (np.degrees(np.arctan2(np.sin(ha), np.cos(ha) * np.sin(la) - np.tan(decl) * np.cos(la))) + 180) % 360
    return elev, az


def load_horizons(path=HORIZONS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def horizon_at(horizon, az):
    """Višina obzorja (°) v azimutu `az` iz polja 360 vrednosti (1° korak), linearna interpolacija; nikoli pod 0°."""
    h = np.asarray(horizon, dtype=float)
    az = np.asarray(az, dtype=float) % 360
    i0 = np.floor(az).astype(int) % 360
    i1 = (i0 + 1) % 360
    fr = az - np.floor(az)
    return np.maximum(h[i0] * (1 - fr) + h[i1] * fr, 0.0)


def _day_unix(date):
    """Minute lokalnega dne kot sekunde UTC. Odmik ob poldnevu velja za cel dan (preklop ure je ob 2.–3. uri,
    ko sonca ni)."""
    noon = datetime.datetime(date.year, date.month, date.day, 12, tzinfo=TZ)
    off = noon.utcoffset().total_seconds()
    start = datetime.datetime(date.year, date.month, date.day, tzinfo=datetime.timezone.utc).timestamp() - off
    return start + np.arange(1440) * 60.0, off / 3600.0


def day_profile(lat, lon, horizon, date, offset=0.0):
    """Za en dan: koledarski vzhod/zahod, prvi/zadnji žarek in skupne minute vidnega sonca.
    Časi so minute od lokalne polnoči (None, če dogodka ni). Polarnih dni na naši širini ni.
    `offset` (°) dvigne ali spusti celotno obzorje — za oceno občutljivosti (površinski model vključuje gozd)."""
    unix, _ = _day_unix(date)
    elev, az = sun_position(lat, lon, unix)
    flat = elev > SUN_RISE_DEG
    if horizon is not None:
        vis = (elev - SUN_RISE_DEG) > np.maximum(horizon_at(horizon, az) + offset, 0.0)
    else:
        vis = flat
    vis = vis & flat

    def first_last(mask):
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            return None, None
        return int(idx[0]), int(idx[-1] + 1)  # konec = prva minuta brez sonca

    fr, fs = first_last(flat)
    r, s = first_last(vis)
    # število ločenih odsekov vidnega sonca (npr. sonce za greben izgine in se vrne skozi zarezo)
    segs = int(np.count_nonzero(np.diff(vis.astype(np.int8)) == 1) + (1 if vis[0] else 0))
    return {"flat_rise": fr, "flat_set": fs, "first": r, "last": s,
            "flat_min": int(flat.sum()), "sun_min": int(vis.sum()), "segments": segs,
            "noon_elev": float(elev.max())}


def year_profiles(lat, lon, horizon, year=REFERENCE_YEAR, offset=0.0):
    d = datetime.date(year, 1, 1)
    out = []
    while d.year == year:
        out.append(day_profile(lat, lon, horizon, d, offset))
        d += datetime.timedelta(days=1)
    return out


def hhmm(minute):
    """Minute od polnoči → »7.42« (pika, SP § 255)."""
    if minute is None:
        return "—"
    return f"{minute // 60}.{minute % 60:02d}"
