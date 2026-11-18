#!/usr/bin/env python3
"""
tools/generate_nebo_nevihta_post.py -- »Nevihta 30 km stran je naslikala izjemno nebo« (18. 11. 2026).

Ročni podatkovni članek, ne del nobenega workflowa. Številke so izračunane iz posnetka data/nebo-nevihta-1118.json (`--fetch`):
strele LightningLogger po 10-minutnih oknih in celicah (worker /strele-zgodovina.json?celice=1, Blitzortung, radij 200 km), trenutna meritev
in dnevni povzetek IREICA1 (/ecowitt-current, /ecowitt-history; blok indoor je izrezan že v workerju, shranjena so samo zunanja polja),
meritvi DRSI (Črnivec, Gornji Grad), sevanje in temperatura sosednje postaje Varpolje (IREICA7, gost, samo za potek sevanja), ARSO toča in
opozorila. Jutranji odčitki so iz data/juzni-veter-1118.json. Fotografije in posnetek radarja (Windy) je poslal Filip.

Strukturo zgodbe varujejo assert-i: če se podatki ne ujemajo z besedilom, generator pade -- članek je treba prenoviti, ne zaobiti asserta.
Članek je posnetek na dan objave. Notranjih meritev članek ne uporablja (glej CLAUDE.md).

Usage:
    python3 tools/generate_nebo_nevihta_post.py --fetch
    python3 tools/generate_nebo_nevihta_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import math
import os
import re
import sys
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import num, fig, tiles, legend  # noqa: E402
from generate_juzni_veter_post import STYLE, a, nbsp, temp, hm, NBSP  # noqa: E402  (skupni pomočniki in slog, ne podvojeni)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
UA = "meteorec.si article generator (+https://meteorec.si)"
DATA = os.path.join(ROOT, "data", "nebo-nevihta-1118.json")
MORNING = os.path.join(ROOT, "data", "juzni-veter-1118.json")
OUTLINE = os.path.join(ROOT, "data", "europe-outline.json")
SLUG = "nebo-po-nevihti-1118"
IMG = f"/img/blog/{SLUG}"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-nebo-nevihta.txt")
TZ = ZoneInfo("Europe/Ljubljana")
TODAY = datetime.date(2026, 11, 18)
LAT, LON = 46.33, 14.92          # Rečica ob Savinji (postaja IREICA1)
C_W, C_E = "#d55181", "#3987e5"                 # zahod / vzhod (barve iz preverjene palete semaforja)
C_T1, C_T2, C_T3 = "#c98500", "#3987e5", "#d55181"   # tri obdobja na zemljevidu (isti vrstni red kot na semaforju)
START = datetime.datetime(2026, 11, 18, 14, 0, tzinfo=TZ)


def get(path):
    req = urllib.request.Request(WORKER + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def big(n):
    return f"{n:,}".replace(",", NBSP)


def km_bearing(la, lo):
    dy = (la - LAT) * 111.2
    dx = (lo - LON) * 111.2 * math.cos(math.radians(LAT))
    return math.hypot(dx, dy), (math.degrees(math.atan2(dx, dy)) + 360) % 360


def group(b):
    """zahod–severozahod (225°–340°), vzhod–jugovzhod (45°–225°), sicer ostalo"""
    if 225 <= b < 340:
        return "W"
    if 45 <= b < 225:
        return "E"
    return "O"


# ───────────────────────── posnetek ─────────────────────────

def fetch():
    now = datetime.datetime.now(datetime.timezone.utc)
    end = now.replace(minute=now.minute // 10 * 10, second=0, microsecond=0)   # samo polna 10-minutna okna
    bins, t = [], START
    while t + datetime.timedelta(minutes=10) <= end:
        t1 = t + datetime.timedelta(minutes=10)
        j = get(f"/strele-zgodovina.json?celice=1&od={int(t.timestamp() * 1000)}&do={int(t1.timestamp() * 1000)}")
        bins.append({"t0": int(t.timestamp()), "cells": [{"la": c["la"], "lo": c["lo"], "n": c["n"]} for c in j.get("cells", [])],
                     "total": j.get("total", 0), "connected": j.get("slots_connected"), "slots": j.get("slots_total")})
        t = t1
    daily = get("/strele-zgodovina.json?ur=1&dni=3")["daily"]
    cur = get("/ecowitt-current")["data"]
    cur.pop("indoor", None)   # zasebnost (CLAUDE.md): worker bloka že reže, tu še enkrat; shranimo samo izbrana zunanja polja
    summ = {s["obsTimeLocal"]: s["metric"] for s in get("/ecowitt-history?start=2026-11-17&end=2026-11-18")["summaries"]}
    drsi = get("/crnivec-drsi")
    vps = get("/varpolje-solar.json")["rows"]
    toca = get("/arso-toca")
    warn = get("/arso-warning")
    yday = datetime.datetime(2026, 11, 17, tzinfo=TZ).timestamp()
    out = {
        "fetched_at": now.isoformat(timespec="seconds"),
        "bins": bins, "daily": daily,
        "ireica1_now": {
            "time_unix": int(cur["outdoor"]["temperature"]["time"]),
            "temp_c": float(cur["outdoor"]["temperature"]["value"]), "humidity_pct": float(cur["outdoor"]["humidity"]["value"]),
            "dew_c": float(cur["outdoor"]["dew_point"]["value"]), "rain_today_mm": float(cur["rainfall"]["daily"]["value"]),
            "wind_kmh": float(cur["wind"]["wind_speed"]["value"]), "gust_kmh": float(cur["wind"]["wind_gust"]["value"]),
            "dir_deg": float(cur["wind"]["wind_direction"]["value"]), "pressure_hpa": float(cur["pressure"]["relative"]["value"]),
        },
        "ireica1_daily": summ["2026-11-18"],
        "drsi": {k: drsi["postaje"][k] for k in ("crnivec", "gornji_grad")}, "drsi_trend": drsi.get("trend"),
        "varpolje_rows": [r for r in vps if r[0] >= yday],     # [čas, sevanje W/m², UV, °C]
        "arso_toca": {"max_level": max((r.get("level") or 0) for r in toca["regions"]), "ok": all(r.get("ok") for r in toca["regions"]),
                      "savinjska": next(r["level"] for r in toca["regions"] if r["name"] == "Savinjska"),
                      "regions_over_0": [{"name": r["name"], "level": r["level"], "text": r.get("text")} for r in toca["regions"] if (r.get("level") or 0) > 0],
                      "issued": toca["regions"][0].get("issued")},
        "arso_warning": {"issued": warn.get("issued"), "alerts": [{k: x[k] for k in ("level", "type", "timeStr")} for x in warn.get("alerts", [])]},
    }
    json.dump(out, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✓ posnetek:", os.path.relpath(DATA, ROOT), f"({len(bins)} oken)")


# ───────────────────────── izračuni ─────────────────────────

class Snap:
    def __init__(self):
        self.S = S = json.load(open(DATA, encoding="utf-8"))
        self.fetched = datetime.datetime.fromisoformat(S["fetched_at"]).astimezone(TZ)
        assert self.fetched.date() == TODAY, f"posnetek je z dne {self.fetched.date()}; poženi z --fetch"
        self.M = json.load(open(MORNING, encoding="utf-8"))
        self.now = S["ireica1_now"]
        self.bins = []
        for b in S["bins"]:
            t = datetime.datetime.fromtimestamp(b["t0"], TZ)
            w = e = o = 0
            dmin = 999
            for c in b["cells"]:
                d, br = km_bearing(c["la"], c["lo"])
                g = group(br)
                if g == "W":
                    w += c["n"]
                elif g == "E":
                    e += c["n"]
                else:
                    o += c["n"]
                dmin = min(dmin, d)
            self.bins.append({"t": t, "W": w, "E": e, "O": o, "n": w + e + o, "dmin": dmin, "cells": b["cells"], "total": b["total"]})
        self.total = sum(b["n"] for b in self.bins)
        self.daily_count = next(d["count"] for d in S["daily"] if d["date"] == "2026-11-18")
        self.closest = next(d["closest_km"] for d in S["daily"] if d["date"] == "2026-11-18")

    def track(self):
        """[(začetek okna, razdalja najbližje celice zahodne skupine z vsaj 3 strelami v oknu)]"""
        out = []
        for b in self.bins:
            ds = [km_bearing(c["la"], c["lo"])[0] for c in b["cells"] if c["n"] >= 3 and group(km_bearing(c["la"], c["lo"])[1]) == "W"]
            if ds:
                out.append((b["t"], min(ds)))
        return out


def sunset_local(date):
    """Geometrijski zahod sonca (višina –0,833°) na postaji, lokalni čas; zahodne gore nad obzorjem niso všteta."""
    from sonce_horizont import sun_position
    import numpy as np
    base = datetime.datetime(date.year, date.month, date.day, 0, 0, tzinfo=TZ).timestamp()
    ts = base + np.arange(12 * 3600, 20 * 3600, 30)
    el, _ = sun_position(LAT, LON, ts)
    k = int(np.argmax(el < -0.833))
    return datetime.datetime.fromtimestamp(ts[k], TZ), lambda t: float(sun_position(LAT, LON, np.array([t.timestamp()]))[0][0])


# ───────────────────────── grafi ─────────────────────────

def fig_timeline(S):
    bins = S.bins
    W, H = 460, 400
    x0, x1, y0, y1 = 40, 446, 24, 190
    n = len(bins)
    step = (x1 - x0) / n
    ymax = max(b["n"] for b in bins)
    ymax = int(math.ceil(ymax / 50.0) * 50)
    Y = lambda v: y1 - v / ymax * (y1 - y0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    out.append(f'<text x="{x0}" y="14" font-size="13" class="jv-m">število strel v 10 minutah (radij 200 km)</text>')
    for v in range(0, ymax + 1, 50 if ymax <= 300 else 100):
        out.append(f'<line x1="{x0}" y1="{Y(v):.1f}" x2="{x1}" y2="{Y(v):.1f}" class="jv-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{v}</text>')
    bw = step * 0.78
    for k, b in enumerate(bins):
        x = x0 + step * k + (step - bw) / 2
        yb = y1
        for key, col in (("W", C_W), ("E", C_E)):
            h = b[key] / ymax * (y1 - y0)
            if h > 0:
                out.append(f'<rect x="{x:.1f}" y="{yb - h:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{col}"/>')
                yb -= h
        if b["O"]:
            h = b["O"] / ymax * (y1 - y0)
            out.append(f'<rect x="{x:.1f}" y="{yb - h:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="var(--muted)" fill-opacity=".6"/>')
    for k, b in enumerate(bins):
        if b["t"].minute == 0 or b["t"].minute == 30:
            xt = x0 + step * k
            out.append(f'<text x="{xt:.1f}" y="{y1 + 17}" text-anchor="middle" font-size="12" class="jv-m">{hm(b["t"])}</text>')
    out.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" class="jv-g" stroke-width="1"/>')
    # drugi panel: razdalja najbližje zahodne celice (vsaj 3 strele v oknu)
    p0, p1 = 250, 372
    dmax = 120
    YD = lambda d: p1 - d / dmax * (p1 - p0)
    out.append(f'<text x="{x0}" y="{p0 - 14}" font-size="13" class="jv-m">razdalja najbližje zahodne celice (km, vsaj 3 strele v oknu)</text>')
    for d in (0, 40, 80, 120):
        out.append(f'<line x1="{x0}" y1="{YD(d):.1f}" x2="{x1}" y2="{YD(d):.1f}" class="jv-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{YD(d) + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{d}</text>')
    xs = lambda t: x0 + step * (bins.index(next(b for b in bins if b["t"] == t))) + step / 2
    tr = S.track()
    pts = " ".join(f"{xs(t):.1f},{YD(d):.1f}" for t, d in tr)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{C_W}" stroke-width="2" stroke-linejoin="round"/>')
    for t, d in tr:
        out.append(f'<circle cx="{xs(t):.1f}" cy="{YD(d):.1f}" r="3.6" fill="{C_W}"/>')
        out.append(f'<text x="{xs(t):.1f}" y="{YD(d) - 8:.1f}" text-anchor="middle" font-size="11" class="jv-m">{d:.0f}</text>')
    for k, b in enumerate(bins):
        if b["t"].minute in (0, 30):
            out.append(f'<text x="{x0 + step * k:.1f}" y="{p1 + 17}" text-anchor="middle" font-size="12" class="jv-m">{hm(b["t"])}</text>')
    out.append("</svg>")
    return "".join(out)


def fig_map(S):
    o = json.load(open(OUTLINE))
    lon0, lon1, lat0, lat1 = 12.4, 18.6, 44.7, 47.4
    k = math.cos(math.radians(46.0))
    W = 460
    sx = W / ((lon1 - lon0) * k)
    H = round((lat1 - lat0) * sx)
    P = lambda la, lo: ((lo - lon0) * k * sx, (lat1 - la) * sx)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">',
           f'<clipPath id="nm"><rect width="{W}" height="{H}"/></clipPath><g clip-path="url(#nm)">']
    for key, wd in (("coast", 1.2), ("borders", 0.8)):
        for line in o[key]:
            if not any(lon0 - 1 <= p[0] <= lon1 + 1 and lat0 - 1 <= p[1] <= lat1 + 1 for p in line):
                continue
            pts = " ".join("%.1f,%.1f" % P(p[1], p[0]) for p in line)
            out.append(f'<polyline points="{pts}" fill="none" stroke="var(--muted)" stroke-width="{wd}" stroke-opacity="{.75 if key == "coast" else .4}"/>')
    rx, ry = P(LAT, LON)
    for r_km in (50, 100, 150):
        r = r_km / 111.2 * sx
        out.append(f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="{r:.1f}" fill="none" class="jv-g" stroke-dasharray="3 4" stroke-width="1"/>')
        out.append(f'<text x="{rx + r * 0.71 + 2:.1f}" y="{ry - r * 0.71 - 2:.1f}" font-size="11" class="jv-m">{r_km} km</text>')
    # obdobja
    slots = [(datetime.time(14, 0), C_T1), (datetime.time(15, 30), C_T2), (datetime.time(16, 30), C_T3)]
    agg = {}
    for b in S.bins:
        tt = b["t"].time()
        col = [c for st, c in slots if tt >= st][-1]
        for c in b["cells"]:
            agg[(c["la"], c["lo"], col)] = agg.get((c["la"], c["lo"], col), 0) + c["n"]
    for (la, lo, col), n in sorted(agg.items(), key=lambda x: -x[1]):
        x, y = P(la, lo)
        r = 2.0 + math.sqrt(n) * 0.5
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{col}" fill-opacity=".55" stroke="{col}" stroke-width="1"/>')
    out.append(f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="4.5" fill="var(--text,#fff)" stroke="#000" stroke-width="1.2"/>')
    out.append(f'<text x="{rx + 8:.1f}" y="{ry + 4:.1f}" font-size="13" font-weight="700" fill="var(--text,#fff)" stroke="var(--card-bg,#000)" stroke-width="3" paint-order="stroke">Rečica</text>')
    out.append("</g></svg>")
    return "".join(out)


def fig_solar(S, today_rows, yday_rows, sunset_t):
    W, H = 460, 360
    x0, x1 = 40, 446
    t0, t1 = 6.0, 17.5
    X = lambda h: x0 + (h - t0) / (t1 - t0) * (x1 - x0)
    ys0, ys1 = 26, 190
    smax = 400.0
    YS = lambda v: ys1 - v / smax * (ys1 - ys0)
    yt0, yt1 = 238, 330
    tmin, tmax = 11.0, 16.0
    YT = lambda v: yt1 - (v - tmin) / (tmax - tmin) * (yt1 - yt0)
    hh = lambda ts: (datetime.datetime.fromtimestamp(ts, TZ).hour + datetime.datetime.fromtimestamp(ts, TZ).minute / 60)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    out.append(f'<text x="{x0}" y="14" font-size="13" class="jv-m">sončno sevanje (W/m²), sosednja postaja Varpolje</text>')
    for v in (0, 100, 200, 300, 400):
        out.append(f'<line x1="{x0}" y1="{YS(v):.1f}" x2="{x1}" y2="{YS(v):.1f}" class="jv-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{YS(v) + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{v}</text>')
    st_h = sunset_t.hour + sunset_t.minute / 60
    fs = S.bins[next(i for i, b in enumerate(S.bins) if b["n"] > 0)]["t"]
    fs_h = fs.hour + fs.minute / 60
    out.append(f'<rect x="{X(fs_h):.1f}" y="{ys0}" width="{X(17.5) - X(fs_h):.1f}" height="{ys1 - ys0}" fill="{C_W}" fill-opacity=".10"/>')
    out.append(f'<text x="{X(fs_h) + 4:.1f}" y="{ys0 + 12}" font-size="12" class="jv-m">strele od {hm(fs)}</text>')
    out.append(f'<line x1="{X(st_h):.1f}" y1="{ys0}" x2="{X(st_h):.1f}" y2="{ys1}" stroke="#c98500" stroke-width="1.2" stroke-dasharray="4 3"/>')
    out.append(f'<text x="{X(st_h) - 4:.1f}" y="{ys0 + 28}" text-anchor="end" font-size="12" fill="#c98500">zahod {hm(sunset_t)}</text>')
    for rows, col, dash, w in ((yday_rows, "var(--muted)", "4 3", 1.5), (today_rows, C_E, "", 2.2)):
        pts = " ".join(f"{X(hh(r[0])):.1f},{YS(min(r[1], smax)):.1f}" for r in rows if t0 <= hh(r[0]) <= t1)
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linejoin="round" {"stroke-dasharray=" + chr(34) + dash + chr(34) if dash else ""}/>')
    out.append(f'<text x="{x0}" y="{yt0 - 14}" font-size="13" class="jv-m">temperatura zraka danes (°C)</text>')
    for v in (12, 14, 16):
        out.append(f'<line x1="{x0}" y1="{YT(v):.1f}" x2="{x1}" y2="{YT(v):.1f}" class="jv-g" stroke-width="1"/>')
        out.append(f'<text x="{x0 - 6}" y="{YT(v) + 4:.1f}" text-anchor="end" font-size="13" class="jv-m">{v}</text>')
    pts = " ".join(f"{X(hh(r[0])):.1f},{YT(min(max(r[3], tmin), tmax)):.1f}" for r in today_rows if t0 <= hh(r[0]) <= t1)
    out.append(f'<polyline points="{pts}" fill="none" stroke="{C_W}" stroke-width="2.2" stroke-linejoin="round"/>')
    for hr in (6, 8, 10, 12, 14, 16):
        out.append(f'<text x="{X(hr):.1f}" y="{yt1 + 18}" text-anchor="middle" font-size="12" class="jv-m">{hr}.00</text>')
    out.append("</svg>")
    return "".join(out)


def photo(src, alt, cap, cls="", w=1400, h=1050):
    return f'<figure class="jv-ph{cls}"><img src="{IMG}/{src}" alt="{alt}" width="{w}" height="{h}" loading="lazy" decoding="async"><figcaption>{cap}</figcaption></figure>'


# ───────────────────────── članek ─────────────────────────

def build_article(S):
    N, M = S.now, S.M
    DR, TR = S.S["drsi"], S.S["drsi_trend"]
    cr, gg = DR["crnivec"], DR["gornji_grad"]
    d18 = S.S["ireica1_daily"]
    t_now = hm(S.fetched)
    assert S.fetched.hour >= 17, S.fetched
    bins = S.bins
    # okna segajo do zadnje polne desetminutke; dnevni števec logger šteje do trenutka zajema
    assert S.total <= S.daily_count <= 1.12 * S.total, (S.total, S.daily_count)
    # logger je bil ves čas povezan (pokritost), sicer prazno okno ne bi bilo »brez strel«
    assert all(b["total"] == b["n"] for b in bins)
    first = next(b for b in bins if b["n"] > 0)
    assert first["t"].hour == 14 and first["t"].minute >= 40, first["t"]
    last_t = bins[-1]["t"] + datetime.timedelta(minutes=10)
    # 30-minutne vsote
    half = {}
    for b in bins:
        key = b["t"].replace(minute=b["t"].minute // 30 * 30)
        half[key] = half.get(key, 0) + b["n"]
    peak_t, peak_n = max(half.items(), key=lambda x: x[1])
    peak_end = peak_t + datetime.timedelta(minutes=30)
    w_tot, e_tot, o_tot = (sum(b[k] for b in bins) for k in ("W", "E", "O"))
    assert w_tot > 300 and e_tot > 800, (w_tot, e_tot)
    # najbližja celica zahodne skupine in njena razdalja
    wdist = min(km_bearing(c["la"], c["lo"])[0] for b in bins for c in b["cells"] if group(km_bearing(c["la"], c["lo"])[1]) == "W")
    edist = min(km_bearing(c["la"], c["lo"])[0] for b in bins for c in b["cells"] if group(km_bearing(c["la"], c["lo"])[1]) == "E")
    top_w = max(((c["n"], c["la"], c["lo"]) for b in bins for c in b["cells"] if group(km_bearing(c["la"], c["lo"])[1]) == "W"), key=lambda x: x[0])
    top_w_km = km_bearing(top_w[1], top_w[2])[0]
    assert 28 < wdist < 40 and 100 < edist < 140, (wdist, edist)
    track = S.track()
    assert len(track) >= 5, track
    (t_a, d_a), (t_b, d_b) = track[0], track[-1]
    assert d_a >= 65 and d_b <= 35, track
    speed = (d_a - d_b) / ((t_b - t_a).total_seconds() / 3600 + 1 / 6)   # okna so desetminutna: celica je bila v prvem in zadnjem oknu v povprečju na sredini
    assert 30 < speed < 70, speed
    assert 20 < S.closest < 40, S.closest
    prev = {d["date"]: d for d in S.S["daily"]}
    assert prev["2026-11-13"]["count"] > 500 and prev["2026-11-16"]["count"] < 10, prev

    # sončni zahod
    ss, sun_alt = sunset_local(TODAY)
    assert hm(ss) in ("16.24", "16.25", "16.26", "16.27"), ss
    alt_1635 = sun_alt(datetime.datetime(2026, 11, 18, 16, 35, tzinfo=TZ))
    assert -3.0 < alt_1635 < 1.0, alt_1635
    alt_1700 = sun_alt(datetime.datetime(2026, 11, 18, 17, 0, tzinfo=TZ))
    assert -7.0 < alt_1700 < -5.5, alt_1700
    # oblak na višini 9 km je neposredno nad opazovalcem še osvetljen, dokler je sonce manj kot ~3° pod obzorjem: d = sqrt(2h/R)
    dep_9km = math.degrees(math.sqrt(2 * 9.0 / 6371.0))
    assert 2.9 < dep_9km < 3.2, dep_9km

    # sevanje: Varpolje (gost, samo potek sevanja)
    rows = S.S["varpolje_rows"]
    ts = lambda r: datetime.datetime.fromtimestamp(r[0], TZ)
    today_rows = [r for r in rows if ts(r).date() == TODAY]
    yday_rows = [r for r in rows if ts(r).date() == TODAY - datetime.timedelta(days=1)]
    assert len(today_rows) > 100 and len(yday_rows) > 100
    pk_t = max(today_rows, key=lambda r: r[1])
    pk_y = max(yday_rows, key=lambda r: r[1])
    s_16 = max((r[1] for r in today_rows if 14.5 <= ts(r).hour + ts(r).minute / 60 < 15.5), default=None)
    def kwh(rs):   # seštevek sevanja do 17.00 (5-minutni vzorci)
        return sum(r[1] for r in rs if ts(r).hour < 17) * 5 / 60 / 1000
    k_t, k_y = kwh(today_rows), kwh(yday_rows)
    assert 0.4 < k_t < k_y < 1.2 and pk_t[1] > pk_y[1], (k_t, k_y, pk_t, pk_y)
    tmax_vp = max(r[3] for r in today_rows)
    tmin_vp = min(r[3] for r in today_rows)

    # postaja IREICA1
    hi18, lo18 = d18["tempHigh"], d18["tempLow"]
    assert d18["precipTotal"] == 0 and N["rain_today_mm"] == 0, (d18, N)
    assert 14.5 <= hi18 <= 16 and N["pressure_hpa"] > M["ireica1_now"]["pressure_hpa"], (hi18, N, M["ireica1_now"])
    dp = N["pressure_hpa"] - M["ireica1_now"]["pressure_hpa"]
    mn = M["ireica1_now"]
    assert 9 <= N["dew_c"] <= 10 and N["humidity_pct"] >= 80, N
    H_all = {k: v for k, v in json.load(open(os.path.join(ROOT, "history.json"))).items() if v.get("src") != "era5"}
    nov_hi = sorted(((v["tempHigh"], k) for k, v in H_all.items() if k[5:7] == "11" and v.get("tempHigh") is not None), reverse=True)
    n_ge = sum(1 for v, _ in nov_hi if v >= hi18)
    nov_mean_hi = sum(v for v, _ in nov_hi) / len(nov_hi)
    d18_prev = sorted(v["tempHigh"] for k, v in H_all.items() if k[5:] == "11-18")
    assert max(d18_prev) < hi18 and len(d18_prev) == 7, d18_prev
    drsi_t = datetime.datetime.fromisoformat(cr["ts"].replace("Z", "+00:00")).astimezone(TZ)
    assert drsi_t.hour >= 16 and cr["smer"] == "WNW" and cr["veter_kmh"] <= 5, cr
    cm = M["drsi"]["crnivec"]
    assert cm["smer"] == "WSW" and cm["veter_kmh"] == 28 and cm["sunki_kmh"] == 40, cm
    toca = S.S["arso_toca"]
    assert toca["ok"] and toca["savinjska"] == 0 and toca["max_level"] == 1, toca
    assert [r["name"] for r in toca["regions_over_0"]] == ["Gorenjska", "Ljubljana in okolica"], toca
    warn = S.S["arso_warning"]
    assert {x["type"] for x in warn["alerts"]} == {"WarningWind", "WarningRain"} and all(x["level"] == "yellow" for x in warn["alerts"]), warn
    wi = datetime.datetime.fromisoformat(warn["issued"]).astimezone(TZ)

    tl = f"{hm(first['t'])}–{hm(last_t)}"
    lead = (f"V Rečici danes popoldne ni bilo izmerljivega dežja (padlo je le nekaj kapelj), ob mraku pa je nebo zagorelo v oranžnih, rdečih in škrlatnih odtenkih. "
            f"Za barvito predstavo je poskrbela nevihta za gorami. Med {hm(first['t'])} in {hm(last_t)} je mreža Blitzortung v krogu 200 km okoli postaje zabeležila {big(S.total)} strel. "
            f"Najbližja je udarila {num(S.closest, 0)} km od nas.")

    p1 = [
        "<strong>Kratek odgovor:</strong> nevihta je ostala v gorah zahodno od doline, proti večeru pa se je približala na približno 30 km. Njen visoki oblak se je medtem razširil nad Rečico. "
        "Sonce, ki je že zašlo za gore, je osvetljevalo samo še spodnjo stran oblaka. Zato je nebo žarelo v toplih barvah, na tleh pa je bilo že temno.",
        tiles([
            (big(S.total), "", f"toliko strel je bilo zabeleženih v krogu 200 km med {hm(first['t'])} in {hm(last_t)}. Za primerjavo: prejšnji teden jih je bilo 13. novembra {prev['2026-11-13']['count']}, 16. novembra pa {prev['2026-11-16']['count']}.", False),
            (num(S.closest, 0), "km", "razdalja najbližje strele danes. Ob zajemu podatkov so bile najbližje nevihtne celice zahodno od doline, nad gorami.", False),
            (num(peak_n, 0), "", f"toliko strel je bilo zabeleženih v najbolj dejavnem polurnem obdobju ({hm(peak_t)}–{hm(peak_end)}).", True),
            (num(hi18), "°C", f"današnja najvišja temperatura v Rečici. Novembrsko povprečje najvišjih temperatur znaša {num(nov_mean_hi)} °C.", False),
            (num(N["rain_today_mm"], 0), "mm", f"izmerjenega dežja do {t_now} (padlo je le nekaj kapelj, ki jih dežemer ni zabeležil). Radarska ocena toče ARSO ob {toca['issued'][:16].split(' ')[-1].replace(':', '.')}: na Savinjskem stopnja 0, na Gorenjskem in v Ljubljani z okolico pa stopnja 1 (zaznavna).", False),
        ]),
    ]

    leg2 = legend([("zahod in severozahod (225°–340°; Koroška, Karavanke)", C_W, ""), ("vzhod in jug (45°–225°; Hrvaška, Panonska nižina)", C_E, ""), ("ostalo", "var(--muted)", "op")])
    aria1 = (f"Število strel v desetminutnih oknih od {hm(first['t'])} do {t_now}, ločeno po smeri od Rečice. Najbolj dejavna pol ura je {hm(peak_t)}–{hm(peak_end)} z {peak_n} strelami. "
             f"Skupaj {w_tot} strel na zahodu in severozahodu ter {e_tot} na vzhodu in jugu.")
    fig1 = fig("Strele po desetminutnih intervalih in smereh", fig_timeline(S).replace("{ARIA}", aria1),
               f"Zapis LightningLogger (Blitzortung), krog s polmerom 200 km okoli postaje. Smer je izračunana iz središča celice zbirne mreže (približno 20 × 17 km), zato je podatek le groba ocena. "
               f"Interval {hm(S.bins[-1]['t'])}–{hm(last_t)} je zadnji popolni interval pred zajemom podatkov.")
    aria2 = (f"Zemljevid celic strel okoli Rečice v treh obdobjih popoldneva. Zahodna skupina je 40–95 km stran proti Koroški in Karavankam, vzhodna skupina je 100–200 km stran na Hrvaškem. "
             f"Obroči kažejo razdalje 50, 100 in 150 km.")
    leg_map = legend([("14.00–15.30", C_T1, ""), ("15.30–16.30", C_T2, ""), (f"16.30–{hm(last_t)}", C_T3, "")])
    fig2 = fig("Kje so bile zabeležene strele", fig_map(S).replace("{ARIA}", aria2),
               "Krog predstavlja celico zbirne mreže, njegova velikost pa število strel v obravnavanem obdobju. Meje so iz podatkov Natural Earth (javna last). Položaj ni natančen, saj zbirne celice niso posamezne točke udara.")

    ratio13 = S.total / prev["2026-11-13"]["count"]
    NUMW = {2: "dva", 3: "tri", 4: "štiri", 5: "pet"}
    assert round(ratio13) in NUMW, ratio13
    p2 = [
        "V tem primeru je radar povedal več kot pogled v nebo. Ob 16.35 sem v avtu odprl posnetek radarskega prikaza v aplikaciji Windy (prikaz za 16.30). Najmočnejše jedro je bilo na barvni lestvici aplikacije označeno z rdečo do škrlatno barvo. "
        "Segalo je do zahodne meje prikaza, od njega pa se je proti vzhodu raztezal širok pas šibkejših padavin čez Koroško in Štajersko. Rečica je ležala ob njegovem južnem robu.",
        photo("radar.jpg", "Posnetek radarja v aplikaciji Windy ob 16.30: močno jedro ob zahodni meji Slovenije in pas padavin proti severovzhodu",
              "Posnetek zaslona aplikacije Windy.com, radarski prikaz za 16.30 (posnetek zaslona je nastal ob 16.35). Modra pika označuje mojo lokacijo, ikone strel pa so del aplikacije. Vir radarskih podatkov je Windy, ne naša postaja.",
              cls=" jv-v", w=900, h=1434),
        f"Podatki o strelah kažejo podobno sliko. Prve strele so bile zabeležene v desetminutnem intervalu, ki se je začel ob {hm(first['t'])}. Dejavnost je dosegla vrhunec med {hm(peak_t)} in {hm(peak_end)}, ko je bilo zabeleženih {peak_n} strel, nato pa je začela upadati.",
        f"Strele so se razporedile v dve skupini. Vzhodna skupina ({big(e_tot)} strel) je ostala 100–200 km stran, nad Hrvaško in Panonsko nižino. Zahodna skupina ({big(w_tot)} strel) je bila nad Koroško in gorami ob meji. "
        f"Njena najdejavnejša celica, v kateri je bilo zabeleženih približno {top_w[0]} strel, je ležala približno {num(top_w_km, 0)} km stran.",
        f"Zahodna skupina se je približevala. Med {hm(t_a)} in {hm(t_b + datetime.timedelta(minutes=10))} se je najbližja celica z vsaj tremi strelami v desetih minutah pomaknila z oddaljenosti {num(d_a, 0)} km na {num(d_b, 0)} km od postaje. "
        f"To pomeni približno {num(speed, 0)} km/h proti vzhodu, vendar gre za grobo oceno. Zbirne celice so velike približno 17–20 km, zato se izračunana razdalja spreminja v skokih. Ob zajemu podatkov so bile zadnje strele zabeležene nad gorami zahodno od doline.",
        leg2 + fig1,
        fig2.replace("<figure", leg_map + "<figure", 1),
        f"Za primerjavo: 16. novembra je logger zabeležil {prev['2026-11-16']['count']} strel, 13. novembra pa {prev['2026-11-13']['count']}. Danes jih je bilo do {hm(last_t)} približno {NUMW[round(ratio13)]}krat toliko kot 13. novembra.",
    ]

    clouds = [
        "Spodaj je pet fotografij istega neba, ki sem jih posnel proti zahodu. Pri treh sem poskusil razložiti, kaj vidim in pri čem nisem povsem prepričan. Gre za mojo presojo na podlagi fotografij, ne za uradno določitev vrst oblakov.",
        photo("nakovalo.jpg", "Oranžen in siv oblak, ki se v obliki pahljače razširja po modrem nebu nad hmeljišči, na desni gore",
              "Pogled iz avtomobila. Oblak se je kot pahljača razširil od obzorja proti zgornjemu desnemu robu slike."),
        "<strong>Nakovalo.</strong> Na prvi fotografiji se oblak z oranžno osvetljenim spodnjim robom razprostira v obliki pahljače. Takšna oblika je značilna za nakovalo nevihtnega oblaka (<em>cumulonimbus</em>; latinsko poimenovanje oblačne značilnosti je <em>incus</em>). "
        "Ko vzgornik v nevihti doseže tropopavzo, se zrak ne more več dvigati tako kot prej, zato se oblak razširi v vodoravni smeri. Višinski veter ga nato odnese s seboj. "
        "Radarski pas proti severovzhodu in višinski zemljevid ECMWF (spodaj), ki kaže zahodni do jugozahodni tok, se s to razlago ujemata. Celotnega nakovala nisem videl, zato gre za verjetno razlago, ne za dokaz.",
        photo("mamatus.jpg", "Valovite izbokline na spodnji strani oblaka, osvetljene z oranžno in rožnato svetlobo nad gozdom in gorami",
              "Mamatusi (vrečasti oblaki) na spodnji strani oblaka, osvetljeni z zadnjo svetlobo. Fotografija je nastala v somraku."),
        "<strong>Mamatusi.</strong> Na drugi fotografiji so na spodnji strani oblaka vidne zaobljene izbokline, ki visijo navzdol. Imenujemo jih mamatusi (latinsko <em>mamma</em>). Pogosto se pojavijo na spodnji strani nakovala nevihtnega oblaka. "
        "Povezani so z zapletenimi procesi v oblaku, med katerimi ima pomembno vlogo tudi spuščanje zraka. Mamatusi sami po sebi ne pomenijo, da bo nevihta zajela tudi nas: pojavijo se lahko daleč od območja, kjer pada dež. "
        "Da gre res za mamatuse in ne za valovite oblake, je moja presoja na podlagi njihove oblike.",
        photo("lecasti-oblak.jpg", "Lečast oblak nad hišo in cerkvenim zvonikom ter oblaki z rožnatimi robovi proti večernemu nebu",
              "Levo je vidna lečasta oblika pod pasom rožnatih oblakov. Večerno nebo nad gorami je še modro.", w=1400, h=826),
        "<strong>Lečast oblak.</strong> Na tretji fotografiji se levo pod oblačno plastjo pokaže gladek oblak v obliki leče. Takšni oblaki so običajno znak valovanja zraka za gorami. Zrak se pri pretoku čez gorsko pregrado dviga in spušča. "
        "Na območju dviganja se ohlaja in kondenzira, zato nastane oblak, na območju spuščanja pa se ta razkroji. Oblak je lahko videti skoraj nepremičen, čeprav veter skoznj prehaja. "
        "To se ujema z jutranjim jugozahodnikom nad grebeni (spodaj). Ker nimam meritve vetra na tej višini, gre le za razlago na podlagi videza.",
        '<div class="jv-pair">'
        + photo("rdece-nebo.jpg", "Velik rdeč oblak z vijoličnimi pasovi nad črnim gozdom", "Rdeč oblak ob sončnem zahodu, tik pred popolno temo.", w=1400, h=1050)
        + photo("somrak.jpg", "Temen oblak z oranžnim in rožnatim robom, spodaj modro večerno nebo nad gorami", "Zadnji žar večera: temen oblak z oranžnimi robovi.", w=1400, h=1050)
        + "</div>",
        f"<strong>Zakaj je nebo gorelo?</strong> Geometrijski sončni zahod v Rečici je bil ob {hm(ss)}, za zahodnim grebenom pa se je sonce skrilo še nekaj minut prej. Ob 17.00 je bilo po mojem izračunu približno {num(abs(alt_1700), 0)}° pod obzorjem. "
        f"Visoki oblaki so lahko osvetljeni še dolgo po sončnem zahodu. Za oblak, ki je neposredno nad nami na višini 9 km, je meja osvetlitve približno {num(dep_9km, 0)}° pod obzorjem (izračun √(2h/R), brez upoštevanja loma svetlobe). "
        "Oblak, ki leži zahodneje od nas in je torej bliže zahajajočemu soncu, ga lahko vidi še dlje: zanj je sonce še nad obzorjem, čeprav je za nas že zašlo.",
        "Zato je nakovalo nad gorami zahodno od doline verjetno še žarelo, ko je bilo pri nas že temno. Svetloba je do oblaka prepotovala dolgo pot skozi ozračje, kjer se modra svetloba bolj razprši, rdeča in oranžna pa lažje dosežeta naše oči. "
        "Zato so barve tako tople. Svetlo modro nebo pri dnu fotografij je del neba, kjer je sonce že zašlo.",
    ]

    p4 = [
        "Jutranji južni veter, o katerem sem pisal v članku " + a("/blog/juzni-veter-ze-drugi-dan-1118.html", "Južni veter že drugi dan") + ", je v dolino prinesel toplejši zrak. Na grebenu je bil veter zjutraj močan. "
        f"Ob {hm(datetime.datetime.fromisoformat(M['drsi']['crnivec']['ts'].replace('Z', '+00:00')).astimezone(TZ))} je DRSI na Črnivcu (902 m) izmeril hitrost {cm['veter_kmh']} km/h in sunke do {cm['sunki_kmh']} km/h iz smeri WSW. "
        f"Ob {hm(drsi_t)} je bil veter na istem mestu precej šibkejši: {cr['veter_kmh']} km/h, sunki do {cr['sunki_kmh']} km/h, smer pa {cr['smer']}.",
        f"Podobno se je dogajalo v dolini. IREICA1 je zjutraj ob {hm(datetime.datetime.fromtimestamp(mn['time_unix'], TZ))} izmerila hitrost vetra {num(mn['wind_kmh'])} km/h (sunki {num(mn['gust_kmh'])} km/h, smer {num(mn['dir_deg'], 0)}°), "
        f"ob {t_now} pa le še {num(N['wind_kmh'])} km/h (sunki {num(N['gust_kmh'])} km/h, smer {num(N['dir_deg'], 0)}°). "
        f"Zračni tlak se je od jutra ({num(mn['pressure_hpa'])} hPa) do {t_now} ({num(N['pressure_hpa'])} hPa) zvišal za {num(dp)} hPa.",
        "Veter je torej proti večeru popustil, zračni tlak pa se je zvišal. Medtem je v gorah zahodno od nas nastajala nevihta. Iz teh številk ne morem ugotoviti, kdaj natančno je veter popustil, saj za današnji dan nimam urnega poteka vetra in zračnega tlaka.",
        f"Zrak je bil ves dan topel in vlažen. Ob {t_now} je bilo v Rečici {temp(N['temp_c'])}, rosišče je znašalo {temp(N['dew_c'])}, relativna vlažnost pa {num(N['humidity_pct'], 0)} %. "
        f"Najvišja današnja temperatura je bila {temp(hi18)}. V našem nizu meritev od novembra 2019 je bilo med {len(nov_hi)} novembrskimi dnevi {n_ge} takih, ko je bila najvišja temperatura vsaj tako visoka. "
        f"Tako toplega 18. novembra v naših podatkih še ni bilo: prej je bila najvišja izmerjena temperatura na ta datum {temp(max(d18_prev))}.",
        "Takšen topel in vlažen zrak je nevihti verjetno zagotovil dodatno energijo. To je moja razlaga, ne neposredna meritev.",
        '<figure class="jv-ph"><img src="/sinopticna/karte/z500-024.webp" alt="Zemljevid geopotencialne višine 500 hPa nad Evropo za polnoč 18. novembra 2026: gosto stisnjene izohipse nad Alpami, tok z zahoda proti vzhodu" width="960" height="740" loading="lazy" decoding="async">'
        '<figcaption>Geopotencialna višina 500 hPa (ECMWF IFS, tek 17. 11. ob 00 UTC, veljavno 18. 11. ob 00 UTC; vir: ECMWF open data, CC BY 4.0, izris meteorec.si). Zemljevid prikazuje stanje za polnoč, ne za čas nevihte. Gosto razporejene izohipse kažejo na močnejši višinski tok.</figcaption></figure>',
    ]

    solar_aria = (f"Sončno sevanje sosednje postaje Varpolje in temperatura zraka med 6. in 17.30 danes. Sevanje je doseglo največ {num(pk_t[1], 0)} W/m² ob {hm(ts(pk_t))}, "
                  f"popoldne pa je upadlo; zahod sonca je ob {hm(ss)}. Včerajšnji vrh je {num(pk_y[1], 0)} W/m².")
    fig3 = fig("Sevanje in temperatura čez dan", fig_solar(S, today_rows, yday_rows, ss).replace("{ARIA}", solar_aria),
               "Podatki s sosednje postaje Varpolje (IREICA7), katere meritve objavlja prijatelj. Ker petminutnega zapisa postaje IREICA1 za današnji dan še nimam, sem uporabil podatke iz Varpolja. "
               "Ti so le orientacijski, ne referenčni: primerjam samo potek sevanja in temperature. Črtkana črta prikazuje včerajšnje sevanje.")
    p3b = [
        legend([("Danes", C_E, ""), ("Včeraj", "var(--muted)", "dash"), ("Temperatura danes", C_W, "")]) + fig3,
        f"Dan je bil večinoma oblačen, podobno kot včeraj. Do 17. ure je skupno sevanje v Varpolju znašalo približno {num(k_t, 2)} kWh/m², včeraj pa {num(k_y, 2)} kWh/m². "
        f"Opoldne se je za kratek čas zjasnilo: ob {hm(ts(pk_t))} je sevanje doseglo {num(pk_t[1], 0)} W/m², medtem ko je bil včerajšnji vrh {num(pk_y[1], 0)} W/m². Popoldne je sevanje padlo pod 100 W/m² že pred sončnim zahodom.",
        "Iz meritev sevanja ne morem ugotoviti, kdaj je visok oblak nevihte prispel nad dolino. To bi lahko pokazal šele satelitski posnetek ali fotografije, posnete v tistem času. Zato graf prikazuje predvsem okvirne razmere, v katerih je nastal večerni prizor. "
        f"Temperatura v Varpolju se je gibala med {num(tmin_vp)} in {num(tmax_vp)} °C.",
    ]

    p5 = [
        f"Prava vremenska sprememba šele prihaja. ARSO je 18. novembra ob {hm(wi)} izdal rumeni opozorili za četrtek, 19. novembra: za veter (19. 11. od 10.00 do 19.59) in za dež (19. 11. od 8.00 do 20.59).",
        "O dežju v četrtek sem pisal že v jutranjem članku. Današnje nakovalo je morda napovednik te vremenske spremembe, vendar je to za zdaj le moja domneva. Vir opozoril: ARSO. Trenutna opozorila najdete na strani " + a("/nevihte/", "Nevihte") + ".",
        "Uradna opozorila ARSO imajo prednost pred vsem, kar je zapisano v tem članku.",
    ]

    omej = [
        "<ul>"
        "<li><strong>Oblake sem določal po fotografijah.</strong> Poimenovanja oblakov so moja presoja, ne uradna določitev. Njihove višine nisem meril.</li>"
        f"<li><strong>Podatki o strelah so iz mreže Blitzortung.</strong> Mreža ne zazna vseh strel, njihov položaj pa je približen, saj so zbirne celice velike okoli 20 km. Prikaz zajema podatke do {hm(last_t)}, dan pa takrat še ni bil končan.</li>"
        "<li><strong>Smer in hitrost premikanja nevihte sta grobi oceni.</strong> Skupini »zahod« (smeri od 225° do 340°) in »vzhod« (smeri od 45° do 225°, mejni kot 225° spada v zahod) sta določeni z izbranima območjema smeri, ki sem ju izbral za pregled. Hitrost je izračunana iz premika med zbirnimi celicami.</li>"
        "<li><strong>Radarska slika ni iz naše postaje.</strong> Gre za posnetek iz aplikacije Windy za 16.30, ne za meritev postaje.</li>"
        "<li><strong>Podatki o sevanju so s sosednje postaje.</strong> Referenčna postaja je IREICA1, vendar petminutnega zapisa za današnji dan v repozitoriju še nimam. Varpolje leži 1,6 km stran, na istem dnu doline.</li>"
        "<li><strong>Višinskega vetra danes nisem meril.</strong> Zemljevid za 500 hPa je napoved za polnoč, ne meritev v času nevihte.</li>"
        f"<li><strong>Dan še ni končan.</strong> Izmerjenega dežja do {t_now} ni bilo (padlo je le nekaj kapelj, ki jih dežemer ni zabeležil), kasneje pa se lahko to še spremeni.</li>"
        "<li><strong>Ocena toče ni potrditev toče na tleh.</strong> Podatek ARSO je radarska ocena, ne dokaz, da je toča dejansko padala.</li>"
        "</ul>",
    ]

    p7 = [
        "Opozorila o nevihtah in strelah so na " + a("/nevihte/", "strani Nevihte") + ", trenutne meritve pa na " + a("/vreme-recica-ob-savinji/", "strani za Rečico ob Savinji") + ". Ob dežju v četrtek spremljajte " + a("/vodostaj-savinje/", "vodostaj Savinje") + ".",
        "Če imate fotografije večernega neba, jih pošljite. Zanima me, kako je nebo izgledalo drugod v dolini.",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate le ob navedbi avtorja (Filip Eremita, Meteorec) in neposredne povezave na ta članek. '
        'Za prepis ali vdelavo grafov in izračunov se predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Nevihta 30 km stran je naslikala izjemno nebo"
    assert len(title) <= 60
    desc = (f"Dežemer ni zabeležil ničesar, a nebo je gorelo. Radar, {big(S.total)} strel in pet fotografij: nakovalo, mamatusi in lečast oblak nad Rečico.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Nevihta je ostala v gorah, njen oblak pa je segel nad dolino", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — radar in strele", "heading": f"Strele v dveh skupinah, Rečica med njima", "id": "radar", "paragraphs": p2},
        {"label": "03 — oblaki", "heading": "Nakovalo, mamatusi in lečast oblak", "id": "oblaki", "paragraphs": clouds},
        {"label": "04 — veter in toplota", "heading": "Topel zrak in veter v višinah", "id": "veter", "paragraphs": p4 + p3b},
        {"label": "05 — kaj sledi", "heading": "Četrtek: veter in dež", "id": "naprej", "paragraphs": p5},
        {"label": "06 — omejitve", "heading": "Česa podatki ne povedo?", "id": "omejitve", "paragraphs": omej},
        {"label": "07 — praktično", "heading": "Kaj lahko naredite?", "id": "prakticno", "paragraphs": p7},
    ]
    lead = nbsp(lead)
    for sec in sections:
        sec["paragraphs"] = [x if ("<svg" in x or "<script" in x or "<figure" in x or "<video" in x or "jv-pair" in x or "vs-leg" in x) else nbsp(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["nevihta", "oblaki", "strele", "november", "radar", "veter"],
        "section_label": "Vremenski dogodek", "og_photo": "nebo-po-nevihti-1118", "og_accent_hex": "#fb923c",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Strele: Blitzortung.org (zapis LightningLogger, Meteorec); meritve postaje IREICA1 (Ecowitt); sosednja postaja Varpolje (IREICA7), katere podatke objavlja prijatelj, uporabljena samo za prikaz poteka sevanja; "
                         "meritve DRSI na Črnivcu (vir: Direkcija Republike Slovenije za infrastrukturo, ceste.si); radarski posnetek: Windy.com; opozorila in radarska ocena toče: ARSO "
                         f"(Agencija Republike Slovenije za okolje, izdano {wi.day}. {wi.month}. {wi.year} ob {hm(wi)}); geopotencialna višina: ECMWF IFS open data (CC BY 4.0). "
                         f"Fotografije: Filip Eremita, 18. 11. 2026. Podatki za članek: data/nebo-nevihta-1118.json (prenos {S.fetched.day}. {S.fetched.month}. {S.fetched.year} ob {t_now})."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<(script|svg|style|video).*?</\1>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|h4|figcaption|li|p|div|b)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace("&lt;", "<").replace(" ", " ")
        h = re.sub(r"[ \t]+\n", "\n", h)
        return re.sub(r"\n{3,}", "\n\n", h).strip()
    out = [article["title"], "", "META OPIS: " + article["meta_description"], "", "UVOD", clean(article["lead"]), ""]
    for s in article["sections"]:
        out += [f'{s["label"].upper()} -- {s["heading"]}', ""]
        for p in s["paragraphs"]:
            c = clean(p)
            if c:
                out += [c, ""]
    out += ["VIRI", clean(article["sources_note"])]
    return "\n".join(out) + "\n"


def main():
    if "--fetch" in sys.argv:
        fetch()
        return
    dry, wire, force = "--dry-run" in sys.argv, "--wire" in sys.argv, "--force" in sys.argv
    S = Snap()
    article = build_article(S)
    if "--text" in sys.argv:
        open(TEXT_OUT, "w", encoding="utf-8").write(plain_text(article))
        print("✓ besedilo za lekturo:", os.path.relpath(TEXT_OUT, ROOT))
    if dry:
        print(plain_text(article))
        return
    path = os.path.join(ROOT, "blog", f"{SLUG}.html")
    if os.path.exists(path) and not force:
        print(f"blog/{SLUG}.html že obstaja -- brez ponovne objave (--force za prepis).")
        return
    import generate_forecast_test_post as ftp
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ftp.TODAY = today.isoformat()
    slug, html, entry, og_meta = ftp.build_html(
        article, today.year, today.month, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Nevihta 30 km stran\nje naslikala izjemno nebo", meta_note="vremenski dogodek",
        nav_label="O postaji", nav_href="/o-postaji.html")
    lead = f'<p class="lead">{article["lead"]}</p>'
    assert html.count(lead) == 1, "uvoda ni mogoče najti za vstavitev sloga"
    html = html.replace(lead, STYLE + "\n" + lead, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ zapisano: blog/{slug}.html ({round(len(html) / 1024)} kB)")
    if wire or "--og" in sys.argv:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
            print(f"✓ OG slika: og/{slug}.jpg")
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
    if wire:
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml, teme in sorodni članki osveženi.")


if __name__ == "__main__":
    main()
