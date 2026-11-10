#!/usr/bin/env python3
"""
tools/build_polarni_vrtinec_data.py -- ENKRATNO orodje za članek o polarnem vrtincu (10. 11. 2026).

Potrebuje omrežje (NOAA GFS na AWS) in eccodes; ni v nobenem workflowu. Izhod je commitan:
  - data/polarni-vrtinec-1110.json  datumi obratov vetra (10 hPa, 60 °N) v našem arhivu analiz GFS ob 00 UTC,
                                    razpon temperature na zemljevidih
  - img/blog/<slug>/vrtinec-pred.webp, vrtinec-po.webp
                                    zemljevida temperature in višine ploskve 10 hPa nad severno poloblo

Datumi obratov so NAŠ izračun iz trenutnih analiz GFS ob 00 UTC, ne uradni seznam (ta nastane iz reanaliz in dnevnih
povprečij); članek to pove. Notranjih meritev orodje ne bere.

Usage:
    python3 tools/build_polarni_vrtinec_data.py [--no-maps] [--no-events]
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np  # noqa: E402

import generate_stratosfera_page as gs  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = "polarni-vrtinec-se-je-ustavil-novembra-1110"
OUT_JSON = os.path.join(ROOT, "data", "polarni-vrtinec-1110.json")
IMG_DIR = os.path.join(ROOT, "img", "blog", SLUG)

# Okna, v katerih je naš 3-dnevni arhiv (data/stratosfera-klima.json) pokazal prehod pod ničlo ali tik nad njo.
BRACKETS = [("2023-02-12", "2023-02-20"), ("2024-01-13", "2024-01-19"), ("2024-03-01", "2024-03-07"),
            ("2025-03-05", "2025-03-13"), ("2025-11-21", "2025-12-02"), ("2026-03-02", "2026-03-07")]
MAP_BEFORE = datetime.date(2026, 10, 24)   # najmočnejši veter te jeseni v našem zapisu
MAP_AFTER = datetime.date(2026, 11, 6)     # prvi dan z vzhodnim vetrom v našem zapisu
LAT_EDGE = 25.0                            # rob zemljevida (°N)
LON0 = 15.0                                # poldnevnik, ki kaže navzdol (Slovenija je pod tečajem)
SIZE = 880
RAMP = [(0.0, (11, 7, 36)), (0.2, (59, 15, 112)), (0.4, (140, 41, 129)), (0.6, (222, 73, 104)),
        (0.8, (254, 159, 109)), (1.0, (252, 253, 191))]
T_MIN, T_MAX = -80.0, -20.0                # °C, enaka lestvica na obeh zemljevidih
HGT_STEP = 200.0                           # izohipse na 200 m
SLO = (46.3, 14.9)


def events():
    out = []
    for a, b in BRACKETS:
        d, end = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
        row = {"okno": [a, b], "datum": None, "u60": []}
        while d <= end:
            u = gs.day_stats(d, with_temp=False)["u60"]
            row["u60"].append([d.isoformat(), u])
            if u < 0 and row["datum"] is None:
                row["datum"] = d.isoformat()
            d += datetime.timedelta(days=1)
        print(a, b, "->", row["datum"], [x[1] for x in row["u60"]])
        out.append(row)
    return out


def land_mask(init):
    """Kopenska maska GFS (LAND:surface) -- za obris obal; gfs_fields pozna samo tlačne ploskve."""
    import atmos_common as ac
    url = gs.gfs_url(init, 0)
    parts = [ln.split(":") for ln in ac.http_get(url + ".idx", timeout=60).decode().splitlines()]
    for i, p in enumerate(parts):
        if len(p) > 4 and p[3] == "LAND" and p[4] == "surface":
            blob = ac.http_get(url, headers={"Range": f"bytes={int(p[1])}-{int(parts[i + 1][1]) - 1}"}, timeout=120)
            for _s, _l, _st, lats, lons, vals in ac.grib_messages(blob):
                return lats, lons, vals
    raise SystemExit("LAND:surface ni v .idx")


def ramp(v):
    x = np.clip((v - T_MIN) / (T_MAX - T_MIN), 0, 1)
    out = np.zeros(v.shape + (3,))
    for (a, ca), (b, cb) in zip(RAMP, RAMP[1:]):
        m = (x >= a) & (x <= b)
        f = ((x - a) / (b - a))[m][:, None]
        out[m] = np.array(ca) * (1 - f) + np.array(cb) * f
    return out


def sample(lats, lons, vals, lat, lon):
    j = np.clip(np.rint((lat - lats[0]) / (lats[1] - lats[0])).astype(int), 0, len(lats) - 1)
    i = np.rint((lon - lons[0]) / (lons[1] - lons[0])).astype(int) % len(lons)
    return vals[j, i]


def edges(k):
    e = np.zeros(k.shape, bool)
    e[:-1, :] |= k[:-1, :] != k[1:, :]
    e[:, :-1] |= k[:, :-1] != k[:, 1:]
    return e


def render(day, land, path):
    from PIL import Image, ImageDraw, ImageFont
    init = datetime.datetime(day.year, day.month, day.day, 0)
    f = gs.gfs_fields(init, 0, (("TMP", 10), ("HGT", 10)))
    S = SIZE * 2                                             # 2x, nato pomanjšano (mehki robovi)
    yy, xx = np.mgrid[0:S, 0:S]
    cx = cy = (S - 1) / 2
    R = S / 2 - 8
    dx, dy = (xx - cx) / R, (yy - cy) / R
    r = np.hypot(dx, dy)
    lat = 90.0 - r * (90.0 - LAT_EDGE)                       # azimutna ekvidistantna projekcija
    lon = (np.degrees(np.arctan2(dx, dy)) + LON0 + 180) % 360 - 180
    inside = r <= 1.0
    la, lo, t = f[("TMP", 10)]
    tc = sample(la, lo, t, lat, lon) - 273.15
    img = ramp(tc)
    la, lo, h = f[("HGT", 10)]
    hk = np.floor(sample(la, lo, h, lat, lon) / HGT_STEP)
    cont = edges(hk)
    cont |= np.roll(cont, 1, 0) | np.roll(cont, 1, 1)
    img[cont] = img[cont] * 0.45 + np.array([255, 255, 255]) * 0.55
    lla, llo, lm = land
    coast = edges(sample(lla, llo, lm, lat, lon) > 0.5)
    coast |= np.roll(coast, 1, 0)
    img[coast] = img[coast] * 0.25 + np.array([10, 15, 28]) * 0.75
    for ring in (40, 60, 80):                                # vzporedniki
        rr = (90.0 - ring) / (90.0 - LAT_EDGE)
        m = np.abs(r - rr) < 1.2 / R
        img[m] = img[m] * 0.7 + 255 * 0.3
    img[~inside] = (10, 15, 28)
    im = Image.fromarray(img.astype("uint8")).resize((SIZE, SIZE), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    bold = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 22)
    reg = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 17)

    def xy(la_, lo_):
        rr = (90.0 - la_) / (90.0 - LAT_EDGE) * (SIZE / 2 - 4)
        a = np.radians(lo_ - LON0)
        return SIZE / 2 + rr * np.sin(a), SIZE / 2 + rr * np.cos(a)

    px, py = xy(*SLO)
    d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(255, 255, 255), outline=(10, 15, 28), width=2)
    d.text((px + 11, py - 10), "Slovenija", font=reg, fill=(255, 255, 255), stroke_width=2, stroke_fill=(10, 15, 28))
    d.line([SIZE / 2 - 7, SIZE / 2, SIZE / 2 + 7, SIZE / 2], fill=(255, 255, 255), width=2)
    d.line([SIZE / 2, SIZE / 2 - 7, SIZE / 2, SIZE / 2 + 7], fill=(255, 255, 255), width=2)
    d.text((SIZE / 2 + 10, SIZE / 2 + 6), "tečaj", font=reg, fill=(255, 255, 255), stroke_width=2, stroke_fill=(10, 15, 28))
    d.text((14, 12), f"{day.day}. {day.month}. {day.year}", font=bold, fill=(232, 237, 248))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "WEBP", quality=82, method=6)
    cap = tc[inside & (lat >= 60)]
    print(os.path.relpath(path, ROOT), os.path.getsize(path) // 1024, "kB", "T 60-90N:", round(float(cap.min()), 1),
          round(float(cap.max()), 1))
    return {"datum": day.isoformat(), "t_min_60n": round(float(cap.min()), 1), "t_max_60n": round(float(cap.max()), 1)}


def main():
    data = json.load(open(OUT_JSON, encoding="utf-8")) if os.path.exists(OUT_JSON) else {}
    if "--no-events" not in sys.argv:
        data["obrati"] = events()
    if "--no-maps" not in sys.argv:
        init = datetime.datetime(MAP_AFTER.year, MAP_AFTER.month, MAP_AFTER.day, 0)
        land = land_mask(init)
        data["zemljevida"] = {
            "lestvica": [T_MIN, T_MAX], "izohipse_m": HGT_STEP,
            "pred": render(MAP_BEFORE, land, os.path.join(IMG_DIR, "vrtinec-pred.webp")),
            "po": render(MAP_AFTER, land, os.path.join(IMG_DIR, "vrtinec-po.webp")),
        }
    data["vir"] = "NOAA GFS 0,25°, analiza ob 00 UTC (noaa-gfs-bdp-pds); izračun tools/build_polarni_vrtinec_data.py"
    data["zgrajeno"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print("✓", os.path.relpath(OUT_JSON, ROOT))


if __name__ == "__main__":
    main()
