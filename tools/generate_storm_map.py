#!/usr/bin/env python3
"""
tools/generate_storm_map.py — dnevna statična nevihtna karta Slovenije.

Vsako jutro ob 10:00 po naši uri sestavi karto nevihtnega potenciala za vso
Slovenijo (ne le za Rečico) — lastna, ne kopija tuje karte (npr. Neurje.si).
Uporablja isto oceno kot živi pripomoček na naslovni strani (zavihek »Lovec
na nevihte« → »stormmap«, glej app.js `renderSloStormMap`/`sloPointScore`) in
isto formulo kot /nevihte/ (`generate_nevihte_page.storm_threat_score`) — ta
skript ju uvozi, ne podvaja. Obris Slovenije, mreža točk in barvna lestvica so
prenesene iz app.js (`SLO_POLY`, `SLO_CITIES`, `buildSloGrid`,
`sloScoreColor`) — JS in Python ne moreta deliti iste kode, zato so vrednosti
tu ročno prepisane. **Če spremeniš eno, spremeni tudi drugo** (isto načelo
kot pri nevihtnih formulah v generate_nevihte_page.py).

Ocena je za vsako mrežno točko izračunana kot **najvišja pričakovana danes**
(od zdaj do konca dneva) — karta pove, kaj lahko danes pričakuješ, ne le,
kaj je ravno zdaj.

Piše:
  og/storm-map/<datum>.jpg        — različica za objavo (1080×1350, feed)
  og/storm-map/<datum>-story.jpg  — različica za zgodbo (1080×1920)
  og/storm-map/latest.json        — kazalec + should_post (glej spodaj)

`should_post`: FB/IG feed + zgodba naj gresta ven **samo**, če je nekje v
Sloveniji danes vsaj ZMERNO (ocena >= 22) — brez tega bi vsak dan, tudi ob
povsem mirnem vremenu, šel ven prazen "brez neviht" post, kar prej ni imelo
odziva (glej opombo o ARSO newsjack objavah v CLAUDE.md).

Wired into: .github/workflows/storm-map.yml

Usage:
  python3 tools/generate_storm_map.py [--dry-run]
"""
import datetime
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_nevihte_page import idx, magnus_dewpoint, wind_uv, storm_threat_score  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "og", "storm-map")
SITE = "https://meteorec.si"
FONT_DIR = "/usr/share/fonts/truetype/liberation/"
KEEP_DAYS = 14

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Ljubljana")
except Exception:
    TZ = datetime.timezone.utc

# ── Prepisano iz app.js (glej docstring zgoraj — ne podvajaj brez razloga) ──
SLO_POLY = [[13.38, 46.22], [13.70, 46.51], [14.10, 46.48], [14.46, 46.61], [14.96, 46.62],
            [15.35, 46.65], [15.75, 46.69], [16.07, 46.66], [16.37, 46.87], [16.52, 46.50],
            [16.61, 46.47], [16.20, 46.32], [15.67, 46.21], [15.72, 45.88], [15.33, 45.72],
            [15.28, 45.60], [14.90, 45.49], [14.55, 45.62], [14.20, 45.49], [13.92, 45.45],
            [13.58, 45.51], [13.76, 45.59], [13.62, 45.81], [13.65, 46.01], [13.38, 46.22]]

SLO_CITIES = [
    {"n": "Ljubljana", "la": 46.056, "lo": 14.506}, {"n": "Maribor", "la": 46.554, "lo": 15.646},
    {"n": "Celje", "la": 46.231, "lo": 15.260}, {"n": "Kranj", "la": 46.239, "lo": 14.356},
    {"n": "Koper", "la": 45.548, "lo": 13.730}, {"n": "Novo mesto", "la": 45.804, "lo": 15.169},
    {"n": "Murska Sobota", "la": 46.658, "lo": 16.166}, {"n": "Nova Gorica", "la": 45.956, "lo": 13.648},
    {"n": "Postojna", "la": 45.776, "lo": 14.214}, {"n": "Ptuj", "la": 46.420, "lo": 15.870},
]
STATION = {"n": "Rečica ob Savinji", "la": 46.326, "lo": 14.921}

SCORE_STOPS = [
    (0, (74, 222, 128)), (8, (132, 204, 22)), (22, (251, 191, 36)),
    (40, (249, 115, 22)), (60, (220, 38, 38)), (78, (162, 28, 175)),
]
LEGEND = [("BREZ", (74, 222, 128)), ("NIZKO", (132, 204, 22)), ("ZMERNO", (251, 191, 36)),
          ("VISOKO", (249, 115, 22)), ("EKSTREMNO", (220, 38, 38))]

POST_THRESHOLD = 22  # ZMERNO — pod tem se FB/IG objava preskoči (glej docstring)

WHITE, MUTED, DIM = (255, 255, 255), (208, 219, 235), (150, 163, 186)
BG_TOP, BG_BOT = (10, 8, 24), (5, 5, 12)
C_PURPLE = (167, 139, 250)

HOURLY_VARS = ",".join([
    "cape", "lifted_index", "wind_speed_10m", "wind_direction_10m",
    "wind_speed_500hPa", "wind_direction_500hPa",
    "temperature_850hPa", "temperature_500hPa", "relative_humidity_850hPa",
])


def point_in_slovenia(lon, lat):
    inside = False
    n = len(SLO_POLY)
    j = n - 1
    for i in range(n):
        xi, yi = SLO_POLY[i]
        xj, yj = SLO_POLY[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def build_grid():
    pts = []
    la = 45.45
    while la <= 46.85:
        lo = 13.4
        while lo <= 16.55:
            if point_in_slovenia(lo, la):
                pts.append({"la": round(la, 3), "lo": round(lo, 3)})
            lo += 0.22
        la += 0.18
    return pts


def fetch_grid(points):
    lats = ",".join(str(p["la"]) for p in points)
    lons = ",".join(str(p["lo"]) for p in points)
    params = urllib.parse.urlencode({
        "latitude": lats, "longitude": lons, "hourly": HOURLY_VARS,
        "timezone": "Europe/Ljubljana", "forecast_days": 2,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    arr = data if isinstance(data, list) else [data]
    out = []
    for i, o in enumerate(arr):
        out.append({"la": points[i]["la"], "lo": points[i]["lo"], "hourly": o.get("hourly") or {}})
    return out


def point_score(hourly, ci):
    cape = idx(hourly.get("cape"), ci) or 0
    li = idx(hourly.get("lifted_index"), ci) or 0
    T850 = idx(hourly.get("temperature_850hPa"), ci)
    T500 = idx(hourly.get("temperature_500hPa"), ci)
    rh850 = idx(hourly.get("relative_humidity_850hPa"), ci) or 60
    if T850 is not None and T500 is not None:
        tt = T850 + magnus_dewpoint(T850, rh850) - 2 * T500
    else:
        tt = 0
    ws10 = idx(hourly.get("wind_speed_10m"), ci) or 0
    wd10 = idx(hourly.get("wind_direction_10m"), ci) or 0
    ws500 = idx(hourly.get("wind_speed_500hPa"), ci) or ws10
    wd500 = idx(hourly.get("wind_direction_500hPa"), ci) or wd10
    u0, v0 = wind_uv(ws10, wd10)
    u5, v5 = wind_uv(ws500, wd500)
    shear = math.hypot(u5 - u0, v5 - v0)
    return storm_threat_score(cape, 0, li, tt, shear)


def today_peak(hourly, times, ci_now):
    if not times:
        return 0
    day = times[ci_now][:10]
    best = 0
    ci = ci_now
    while ci < len(times) and times[ci][:10] == day:
        best = max(best, point_score(hourly, ci))
        ci += 1
    return best


def score_color(s):
    stops = SCORE_STOPS
    if s <= stops[0][0]:
        return stops[0][1]
    if s >= stops[-1][0]:
        return stops[-1][1]
    for i in range(1, len(stops)):
        s0, c0 = stops[i - 1]
        s1, c1 = stops[i]
        if s <= s1:
            t = (s - s0) / (s1 - s0)
            return tuple(round(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
    return stops[-1][1]


def score_level(s):
    if s >= 60:
        return "EKSTREMNO"
    if s >= 40:
        return "VISOKO"
    if s >= 22:
        return "ZMERNO"
    if s >= 8:
        return "NIZKO"
    return "BREZ"


def nearest_score(lon, lat, pts):
    best, bd = 0, float("inf")
    for p in pts:
        d = (lat - p["la"]) ** 2 + ((lon - p["lo"]) * 0.69) ** 2
        if d < bd:
            bd, best = d, p["score"]
    return best


def nearest_city(lon, lat, extra=None):
    cities = SLO_CITIES + ([extra] if extra else [])
    best, bd = None, float("inf")
    for c in cities:
        d = (lat - c["la"]) ** 2 + ((lon - c["lo"]) * 0.69) ** 2
        if d < bd:
            bd, best = d, c
    return best["n"] if best else "Slovenija"


def compute():
    grid = build_grid()
    grid_data = fetch_grid(grid)
    now = datetime.datetime.now(TZ).replace(tzinfo=None)

    pts = []
    for g in grid_data:
        times = g["hourly"].get("time") or []
        if not times:
            continue
        ci_now = 0
        for k, t in enumerate(times):
            if datetime.datetime.fromisoformat(t) >= now:
                ci_now = max(0, k - 1)
                break
        score = today_peak(g["hourly"], times, ci_now)
        pts.append({"la": g["la"], "lo": g["lo"], "score": score})

    if not pts:
        raise ValueError("Open-Meteo ni vrnil podatkov za mrežo")

    peak = max(pts, key=lambda p: p["score"])
    level = score_level(peak["score"])
    place = nearest_city(peak["lo"], peak["la"], STATION)
    return pts, {"score": peak["score"], "level": level, "place": place}


def font(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)


def build_color_raster(pts, rw, rh, bbox):
    min_lo, max_lo, min_la, max_la = bbox
    raster = Image.new("RGBA", (rw, rh))
    px = raster.load()
    reach = 0.30
    lat_corr = 0.69
    for y in range(rh):
        lat = max_la - (y / (rh - 1)) * (max_la - min_la)
        for x in range(rw):
            lon = min_lo + (x / (rw - 1)) * (max_lo - min_lo)
            num = den = 0.0
            nearest = float("inf")
            for p in pts:
                dla = lat - p["la"]
                dlo = (lon - p["lo"]) * lat_corr
                d2 = dla * dla + dlo * dlo
                if d2 < nearest:
                    nearest = d2
                w = 1 / (d2 + 1e-4)
                num += w * p["score"]
                den += w
            score = num / den if den else 0
            r, g, b = score_color(score)
            nd = math.sqrt(nearest)
            a = 1.0 if nd < reach else max(0.0, 1 - (nd - reach) / 0.22)
            px[x, y] = (r, g, b, round(min(1.0, a) * 235))
    return raster


def poly_mask(rw, rh, bbox):
    min_lo, max_lo, min_la, max_la = bbox
    mask = Image.new("L", (rw, rh), 0)
    md = ImageDraw.Draw(mask)
    poly_px = [
        ((lon - min_lo) / (max_lo - min_lo) * (rw - 1),
         (max_la - lat) / (max_la - min_la) * (rh - 1))
        for lon, lat in SLO_POLY
    ]
    md.polygon(poly_px, fill=255)
    return mask


def draw_map(img, pts, box, bbox):
    """Nariše karto (interpolirano barvno polje + obris + mesta) v `box`
    (x0,y0,x1,y1) na `img`, geografsko projicirano iz `bbox`."""
    bx0, by0, bx1, by1 = box
    bw, bh = bx1 - bx0, by1 - by0
    min_lo, max_lo, min_la, max_la = bbox

    rw, rh = 130, round(130 * bh / bw)
    raster = build_color_raster(pts, rw, rh, bbox)
    mask = poly_mask(rw, rh, bbox)
    raster.putalpha(Image.composite(raster.getchannel("A"), Image.new("L", (rw, rh), 0), mask))
    raster = raster.resize((bw, bh), Image.LANCZOS)
    img.paste(raster, (bx0, by0), raster)

    def to_px(lon, lat):
        return (bx0 + (lon - min_lo) / (max_lo - min_lo) * bw,
                by0 + (max_la - lat) / (max_la - min_la) * bh)

    d = ImageDraw.Draw(img)
    poly_px = [to_px(lon, lat) for lon, lat in SLO_POLY]
    d.line(poly_px, fill=(255, 255, 255, 210), width=3, joint="curve")

    f_city = font("LiberationSans-Regular.ttf", 22)
    f_stn = font("LiberationSans-Bold.ttf", 24)
    for c in SLO_CITIES:
        x, y = to_px(c["lo"], c["la"])
        d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(30, 41, 59), outline=WHITE, width=1)
        d.text((x + 9, y - 12), c["n"], font=f_city, fill=MUTED)

    sx, sy = to_px(STATION["lo"], STATION["la"])
    d.ellipse([sx - 9, sy - 9, sx + 9, sy + 9], fill=C_PURPLE, outline=WHITE, width=2)
    d.text((sx + 14, sy - 14), "Rečica ob Savinji", font=f_stn, fill=WHITE)


def render(w, h, top, bottom, pts, summary, now):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for row in range(h):
        t = row / h
        col = tuple(round(BG_TOP[k] + (BG_BOT[k] - BG_TOP[k]) * t) for k in range(3))
        gd.line([(0, row), (w, row)], fill=(*col, 255))
    img = Image.alpha_composite(img, grad)
    d = ImageDraw.Draw(img)

    pad = 70
    f_brand = font("LiberationSans-Bold.ttf", 40)
    f_date = font("LiberationSans-Regular.ttf", 26)
    f_title = font("LiberationSans-Bold.ttf", 52)
    f_sub = font("LiberationSans-Regular.ttf", 28)
    f_legend = font("LiberationSans-Bold.ttf", 20)
    f_foot = font("LiberationSans-Regular.ttf", 25)
    f_foot_b = font("LiberationSans-Bold.ttf", 28)

    y = top
    logo = Image.open(os.path.join(ROOT, "icon-512.png")).convert("RGBA")
    ls = 84
    logo = logo.resize((ls, ls), Image.LANCZOS)
    img.paste(logo, (pad, y), logo)
    d = ImageDraw.Draw(img)
    d.text((pad + ls + 22, y), "METEOREC", font=f_brand, fill=WHITE)
    DNI = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
    MES = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust",
           "september", "oktober", "november", "december"]
    datum = f"{DNI[now.weekday()]}, {now.day}. {MES[now.month - 1]} · izdano ob {now:%H:%M}"
    d.text((pad + ls + 24, y + 46), datum, font=f_date, fill=DIM)

    y += ls + 46
    d.text((pad, y), "Nevihtna karta Slovenije", font=f_title, fill=WHITE)
    y += 66
    d.text((pad, y), "Najvišji pričakovan potencial danes po območjih", font=f_sub, fill=MUTED)
    y += 52

    legend_h = 56
    foot_h = 130
    map_top = y + 14
    bottom_block_top = bottom - legend_h - foot_h - 20
    map_box_w = w - 2 * pad

    min_lo = min(p[0] for p in SLO_POLY) - 0.05
    max_lo = max(p[0] for p in SLO_POLY) + 0.05
    min_la = min(p[1] for p in SLO_POLY) - 0.05
    max_la = max(p[1] for p in SLO_POLY) + 0.05
    lat_corr = 0.69
    geo_w, geo_h = (max_lo - min_lo) * lat_corr, (max_la - min_la)
    # Slovenija je širša kot visoka -- na pokončni zgodbi (9:16) bi
    # sredinjenje karte v celotnem razpoložljivem okviru pustilo velik prazen
    # pas nad in pod njo, ker širina omeji merilo prej kot višina. Zato je
    # karta poravnana na vrh, preostanek prostora do nog pa zapolni seznam
    # tveganja po mestih (glej spodaj) namesto da bi ostal prazen.
    scale = min(map_box_w / geo_w, (bottom_block_top - map_top) / geo_h)
    bw, bh = round(geo_w * scale), round(geo_h * scale)
    bx0 = pad + (map_box_w - bw) // 2
    by0 = map_top
    draw_map(img, pts, (bx0, by0, bx0 + bw, by0 + bh), (min_lo, max_lo, min_la, max_la))
    d = ImageDraw.Draw(img)

    leftover = bottom_block_top - (by0 + bh)
    if leftover >= 260:
        f_city_lbl = font("LiberationSans-Regular.ttf", 27)
        f_city_lvl = font("LiberationSans-Bold.ttf", 27)
        ranked = sorted(
            [(c["n"], nearest_score(c["lo"], c["la"], pts)) for c in (SLO_CITIES + [STATION])],
            key=lambda r: -r[1],
        )
        list_top = by0 + bh + 34
        d.text((pad, list_top), "Potencial po mestih danes", font=f_sub, fill=MUTED)
        row_top = list_top + 44
        row_h = min(52, (bottom_block_top - 20 - row_top) // ((len(ranked) + 1) // 2))
        col_w = map_box_w // 2
        for i, (name, score) in enumerate(ranked):
            col, row = divmod(i, (len(ranked) + 1) // 2)
            rx = pad + col * col_w
            ry = row_top + row * row_h
            lvl = score_level(score)
            col_rgb = score_color(score)
            d.ellipse([rx, ry + 6, rx + 16, ry + 22], fill=col_rgb)
            d.text((rx + 26, ry), name, font=f_city_lbl, fill=MUTED)
            tb = d.textbbox((0, 0), lvl, font=f_city_lvl)
            d.text((rx + col_w - 40 - (tb[2] - tb[0]), ry), lvl, font=f_city_lvl, fill=WHITE)

    ly = bottom_block_top
    lx = pad
    for label, col in LEGEND:
        d.rounded_rectangle([lx, ly, lx + 22, ly + 22], radius=5, fill=col)
        tb = d.textbbox((0, 0), label, font=f_legend)
        d.text((lx + 30, ly), label, font=f_legend, fill=MUTED)
        lx += 30 + (tb[2] - tb[0]) + 26

    fy = ly + legend_h
    d.line([(pad, fy), (w - pad, fy)], fill=(255, 255, 255, 40), width=1)
    fy += 20
    place_txt = f"Najvišji potencial danes: {summary['level']} — bliže {summary['place']}"
    d.text((pad, fy), place_txt, font=f_foot_b, fill=WHITE)
    fy += 40
    d.text((pad, fy), "Model iz podatkov Open-Meteo, ni uradno opozorilo ARSO. meteorec.si/nevihte",
           font=f_foot, fill=DIM)

    return img.convert("RGB")


def prune_old(today):
    if not os.path.isdir(OUT_DIR):
        return []
    cutoff = today - datetime.timedelta(days=KEEP_DAYS)
    removed = []
    for name in os.listdir(OUT_DIR):
        if not name.endswith(".jpg"):
            continue
        base = name[:-4].split("-story")[0]
        try:
            d = datetime.date.fromisoformat(base)
        except ValueError:
            continue
        if d < cutoff:
            os.remove(os.path.join(OUT_DIR, name))
            removed.append(name)
    return removed


def main():
    dry = "--dry-run" in sys.argv[1:]
    now = datetime.datetime.now(TZ)
    today = now.date()

    print(f"[{today}] Sestavljam nevihtno karto Slovenije …")
    try:
        pts, summary = compute()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        return 1

    should_post = summary["score"] >= POST_THRESHOLD
    print(f"  → najvišji potencial: {summary['level']} ({summary['score']}/88) — bliže {summary['place']}")
    print(f"  → should_post={should_post}")

    if dry:
        print("(--dry-run: slike niso zapisane)")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    feed = render(1080, 1350, 60, 1290, pts, summary, now)
    story = render(1080, 1920, 200, 1700, pts, summary, now)

    name = f"{today.isoformat()}.jpg"
    name_story = f"{today.isoformat()}-story.jpg"
    feed.save(os.path.join(OUT_DIR, name), "JPEG", quality=90)
    story.save(os.path.join(OUT_DIR, name_story), "JPEG", quality=90)
    print(f"✓ zapisano: og/storm-map/{name} + {name_story}")

    removed = prune_old(today)
    if removed:
        print(f"✓ pobrisane stare karte: {', '.join(sorted(removed))}")

    meta = {
        "date": today.isoformat(),
        "issued_at": now.isoformat(),
        "national_score": summary["score"],
        "national_level": summary["level"],
        "national_place": summary["place"],
        "should_post": should_post,
        "image": f"{SITE}/og/storm-map/{name}",
        "image_story": f"{SITE}/og/storm-map/{name_story}",
    }
    with open(os.path.join(OUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
