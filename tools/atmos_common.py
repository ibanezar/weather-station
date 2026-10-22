#!/usr/bin/env python3
"""
tools/atmos_common.py — skupne pomožne funkcije za strani o velikem vremenu (21. 10. 2026):
/indeksi/ (AO, NAO, ENSO), /stratosfera/ (polarni vrtinec), /prah/ (saharski prah) in /sinopticna/
(ECMWF IFS karte).

Ideja po polarnivrtinec.si (Polarni vrtinec VRTINEC): široka slika ozračja nad Evropo. Izvedba je naša, podatki
so javni (NOAA CPC/PSL, NOAA GFS na AWS, ECMWF open data CC BY 4.0, Open-Meteo/CAMS).

Skupno je samo tisto, kar je res enako (prenos, grafi SVG, projekcija in osnova karte, ovoj strani). Vsak
generator ostane svoja datoteka. Brez podatkov postaje — notranjih meritev tu ni in ne smejo priti.
"""
import datetime
import html as _html
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UA = "Meteorec/1.0 (+https://meteorec.si)"
OUTLINE_PATH = os.path.join(ROOT, "data", "europe-outline.json")


# ── Prenos ───────────────────────────────────────────────────────────────────

def http_get(url, headers=None, timeout=90, tries=3):
    """Prenese URL (bajti). Ob prehodni napaki počaka in poskusi znova — en spodleteli klic ne sme podreti teka."""
    hdr = {"User-Agent": UA}
    hdr.update(headers or {})
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):  # ponavljanje ne pomaga
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
        time.sleep(3 * (i + 1))
    raise last


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


# ── Besedilo ─────────────────────────────────────────────────────────────────

MESECI = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober",
          "november", "december"]
MESECI_ROD = ["januarja", "februarja", "marca", "aprila", "maja", "junija", "julija", "avgusta", "septembra",
              "oktobra", "novembra", "decembra"]


def num(x, d=1, plus=False):
    """Število s slovensko decimalno vejico; »-0« ni berljivo."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    out = f"{x:.{d}f}"
    if out.lstrip("-").replace(".", "").strip("0") == "":
        out = out.lstrip("-")
    elif plus and x > 0:
        out = "+" + out
    return out.replace(".", ",").replace("-", "−")


def fmt_date(d, year=False):
    if isinstance(d, str):
        d = datetime.date.fromisoformat(d)
    s = f"{d.day}. {d.month}."
    return f"{s} {d.year}" if year else s


def fmt_dt_local(iso_utc):
    """ISO čas v UTC → »21. 10. 2026 ob 14:30« po času Europe/Ljubljana."""
    from zoneinfo import ZoneInfo
    dt = datetime.datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    dt = dt.astimezone(ZoneInfo("Europe/Ljubljana"))
    return f"{dt.day}. {dt.month}. {dt.year} ob {dt.hour}:{dt.minute:02d}"


def now_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Graf SVG (črte, pas, navpična oznaka) ────────────────────────────────────

def nice_ticks(lo, hi, n=5):
    span = max(hi - lo, 1e-9)
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = mag * 10
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw:
            step = m * mag
            break
    t = math.ceil(lo / step - 1e-9) * step
    out = []
    while t <= hi + 1e-9:
        out.append(round(t, 6))
        t += step
    return out


def line_chart(series, ymin=None, ymax=None, marker=None, zero=True, unit="", aria="", width=720, height=300,
               yfmt=None, x_every=None, hlines=None):
    """Črtni graf kot vgrajen SVG (barve in pisava prek currentColor — stran je temna).

    series: [{name, color, pts: [(date, value)], width, dash, band: [(date, lo, hi)] }]
    marker: (date, napis) navpična črta (npr. »danes« ali začetek napovedi)
    """
    pts_all = [p for s in series for p in s["pts"]] + [(b[0], b[1]) for s in series for b in s.get("band", [])]
    if not pts_all:
        return ""
    xs = [p[0].toordinal() for p in pts_all]
    x0, x1 = int(math.floor(min(xs))), max(xs)
    vals = [p[1] for p in pts_all] + [b[2] for s in series for b in s.get("band", [])]
    lo = min(vals) if ymin is None else ymin
    hi = max(vals) if ymax is None else ymax
    if zero:
        lo, hi = min(lo, 0), max(hi, 0)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    L, R, T, B = 46, 14, 14, 32
    W, H = width, height
    pw, ph = W - L - R, H - T - B

    def X(d):
        return L + (d.toordinal() - x0) / max(x1 - x0, 1) * pw

    def Y(v):
        return T + (hi - v) / (hi - lo) * ph

    yf = yfmt or (lambda v: num(v, 1 if (hi - lo) < 8 else 0))
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{_html.escape(aria)}" '
         f'style="width:100%;height:auto;display:block;font-family:inherit">']
    for t in nice_ticks(lo, hi):
        y = Y(t)
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="currentColor" '
                 f'stroke-opacity=".12"/>')
        g.append(f'<text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="currentColor" '
                 f'fill-opacity=".7">{yf(t)}</text>')
    if zero and lo < 0 < hi:
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(0):.1f}" y2="{Y(0):.1f}" stroke="currentColor" '
                 f'stroke-opacity=".45"/>')
    for hv, hlab in (hlines or []):
        if lo < hv < hi:
            g.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(hv):.1f}" y2="{Y(hv):.1f}" stroke="currentColor" '
                     f'stroke-opacity=".3" stroke-dasharray="2 4"/>')
            g.append(f'<text x="{W - R - 2}" y="{Y(hv) - 3:.1f}" text-anchor="end" font-size="10" '
                     f'fill="currentColor" fill-opacity=".65">{_html.escape(hlab)}</text>')
    span_days = x1 - x0
    step = x_every or max(1, round(span_days / 6))
    d = x0
    while d <= x1:
        dd = datetime.date.fromordinal(d)
        lab = f"{dd.day}. {dd.month}." if span_days < 400 else f"{MESECI[dd.month - 1][:3]} {dd.year % 100:02d}"
        g.append(f'<text x="{X(dd):.1f}" y="{H - 10}" text-anchor="middle" font-size="11" fill="currentColor" '
                 f'fill-opacity=".7">{lab}</text>')
        d += step
    for s in series:
        band = s.get("band")
        if band:
            top = " ".join(f"{X(b[0]):.1f},{Y(b[2]):.1f}" for b in band)
            bot = " ".join(f"{X(b[0]):.1f},{Y(b[1]):.1f}" for b in reversed(band))
            g.append(f'<polygon points="{top} {bot}" fill="{s["color"]}" fill-opacity=".18" stroke="none"/>')
    for s in series:
        if not s["pts"]:
            continue
        dash = f' stroke-dasharray="{s["dash"]}"' if s.get("dash") else ""
        path = " ".join(f"{X(p[0]):.1f},{Y(p[1]):.1f}" for p in s["pts"])
        g.append(f'<polyline points="{path}" fill="none" stroke="{s["color"]}" stroke-width="{s.get("width", 2)}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{dash}/>')
    if marker:
        mx = X(marker[0])
        g.append(f'<line x1="{mx:.1f}" x2="{mx:.1f}" y1="{T}" y2="{T + ph}" stroke="currentColor" '
                 f'stroke-opacity=".5" stroke-dasharray="3 3"/>')
        g.append(f'<text x="{mx + 4:.1f}" y="{T + 10}" font-size="11" fill="currentColor" '
                 f'fill-opacity=".8">{_html.escape(marker[1])}</text>')
    if unit:
        g.append(f'<text x="{L}" y="{T - 3}" font-size="11" fill="currentColor" fill-opacity=".7">'
                 f'{_html.escape(unit)}</text>')
    g.append("</svg>")
    return "\n".join(g)


def legend(items):
    """items: [(barva, napis, črtkano?)] → vrstica legende nad grafom."""
    out = []
    for color, label, dashed in items:
        dash = ' stroke-dasharray="4 3"' if dashed else ""
        out.append(f'<span style="display:inline-flex;align-items:center;gap:.4rem;margin-right:1rem">'
                   f'<svg width="22" height="8" aria-hidden="true"><line x1="0" x2="22" y1="4" y2="4" '
                   f'stroke="{color}" stroke-width="3"{dash}/></svg>{_html.escape(label)}</span>')
    return '<p class="muted-note" style="margin:.2rem 0 .4rem">' + "".join(out) + "</p>"


# ── GRIB (eccodes) ───────────────────────────────────────────────────────────

def grib_messages(path_or_bytes):
    """Generator (shortName, level, step, lats[nj], lons[ni], vals[nj][ni]) za pravilno mrežo lat/lon.

    Dolžine 0..360 se preslikajo v −180..180 in vrstice uredijo, tako da je mreža naraščajoča po obeh oseh.
    """
    import numpy as np
    from eccodes import (codes_get, codes_get_values, codes_grib_new_from_file, codes_release)
    tmp = None
    if isinstance(path_or_bytes, (bytes, bytearray)):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
        tmp.write(path_or_bytes)
        tmp.close()
        path = tmp.name
    else:
        path = path_or_bytes
    try:
        with open(path, "rb") as f:
            while True:
                gid = codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    ni, nj = codes_get(gid, "Ni"), codes_get(gid, "Nj")
                    la1 = codes_get(gid, "latitudeOfFirstGridPointInDegrees")
                    la2 = codes_get(gid, "latitudeOfLastGridPointInDegrees")
                    lo1 = codes_get(gid, "longitudeOfFirstGridPointInDegrees")
                    di = codes_get(gid, "iDirectionIncrementInDegrees")
                    vals = codes_get_values(gid).reshape(nj, ni)
                    lats = np.linspace(la1, la2, nj)
                    lons = lo1 + di * np.arange(ni)
                    lons = np.where(lons > 180, lons - 360, lons)
                    oj = np.argsort(lats)
                    oi = np.argsort(lons)
                    yield (codes_get(gid, "shortName"), codes_get(gid, "level"), codes_get(gid, "step"),
                           lats[oj], lons[oi], vals[oj][:, oi])
                finally:
                    codes_release(gid)
    finally:
        if tmp is not None:
            os.unlink(tmp.name)


# ── Projekcija in osnova karte ───────────────────────────────────────────────

class Lambert:
    """Lambertova konformna stožčasta projekcija (kot jo uporabljajo sinoptične karte nad Evropo)."""

    def __init__(self, lon0=12.0, lat1=35.0, lat2=60.0):
        r = math.radians
        self.lon0 = r(lon0)
        p1, p2 = r(lat1), r(lat2)
        self.n = math.log(math.cos(p1) / math.cos(p2)) / math.log(
            math.tan(math.pi / 4 + p2 / 2) / math.tan(math.pi / 4 + p1 / 2))
        self.F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** self.n / self.n
        self.rho0 = float(self._rho(r(45.0)))

    def _rho(self, phi):
        import numpy as np
        return 6371.0 * self.F / np.tan(np.pi / 4 + phi / 2) ** self.n

    def xy(self, lon, lat):
        """Dolžina/širina v stopinjah (skalar ali numpy) → x, y v km."""
        import numpy as np
        lam = np.radians(lon)
        rho = self._rho(np.radians(lat))
        th = self.n * (lam - self.lon0)
        return rho * np.sin(th), self.rho0 - rho * np.cos(th)


LCC = Lambert()
# Okvir karte v projiciranih km (izbran tako, da pokrije Evropo, Sredozemlje in severno Afriko do ~28 °N)
MAP_X = (-2850.0, 2650.0)
MAP_Y = (-2050.0, 1650.0)
MAP_BBOX = (-45.0, 15.0, 75.0, 82.0)  # širši izrez podatkov, da robovi karte ne ostanejo prazni


def crop_grid(lats, lons, vals, bbox=MAP_BBOX):
    import numpy as np
    ii = np.where((lons >= bbox[0]) & (lons <= bbox[2]))[0]
    jj = np.where((lats >= bbox[1]) & (lats <= bbox[3]))[0]
    return lats[jj], lons[ii], vals[np.ix_(jj, ii)]


def new_map(title, subtitle, credit, size=(9.6, 7.4)):
    """Prazna osnova: obala, meje, mreža stopinj. Vrne (fig, ax). Pisave: DejaVu (vgrajena v matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    import numpy as np
    fig = plt.figure(figsize=size, dpi=100, facecolor="#ffffff")
    ax = fig.add_axes([0.01, 0.065, 0.98, 0.835])
    ax.set_xlim(*MAP_X)
    ax.set_ylim(*MAP_Y)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor("#f3f6fa")
    ax.add_patch(plt.Rectangle((MAP_X[0], MAP_Y[0]), MAP_X[1] - MAP_X[0], MAP_Y[1] - MAP_Y[0],
                               facecolor="#eef3f8", edgecolor="#8896a8", lw=1.0, zorder=0))
    # mreža stopinj
    for lon in range(-40, 80, 10):
        la = np.linspace(20, 80, 120)
        x, y = LCC.xy(np.full_like(la, lon), la)
        ax.plot(x, y, color="#b9c4d2", lw=0.5, zorder=1)
    for lat in range(20, 85, 10):
        lo = np.linspace(-45, 75, 240)
        x, y = LCC.xy(lo, np.full_like(lo, lat))
        ax.plot(x, y, color="#b9c4d2", lw=0.5, zorder=1)
    ol = read_json(OUTLINE_PATH)
    if ol:
        for key, color, lw in (("coast", "#33414f", 0.9), ("borders", "#7d8a99", 0.5)):
            segs = []
            for poly in ol[key]:
                a = np.array(poly)
                x, y = LCC.xy(a[:, 0], a[:, 1])
                segs.append(np.column_stack([x, y]))
            ax.add_collection(LineCollection(segs, colors=color, linewidths=lw, zorder=6))
    fig.text(0.012, 0.955, title, fontsize=13.5, fontweight="bold", color="#14202e", va="center")
    fig.text(0.012, 0.918, subtitle, fontsize=10, color="#3c4b5c", va="center")
    fig.text(0.012, 0.02, credit, fontsize=8, color="#5b6a7b", va="center")
    return fig, ax


def save_webp(fig, path, quality=74):
    """Shrani sliko kot WebP (prek PNG v pomnilniku in Pillow); stare datoteke prepiše."""
    import matplotlib.pyplot as plt
    from PIL import Image
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
    plt.close(fig)
    buf.seek(0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.open(buf).convert("RGB").save(path, "WEBP", quality=quality, method=6)


def local_extrema(a, size=11, prominence=0.0, min_dist=0):
    """Indeksi lokalnih maksimumov in minimumov 2D polja (okno size×size), brez robov, z minimalno izrazitostjo."""
    from scipy.ndimage import maximum_filter, minimum_filter
    import numpy as np
    mx = (a == maximum_filter(a, size=size, mode="nearest"))
    mn = (a == minimum_filter(a, size=size, mode="nearest"))
    edge = np.zeros_like(a, dtype=bool)
    m = size // 2
    edge[m:-m, m:-m] = True
    # Šibke »gube« v ravnem polju niso središča: točka mora stati vsaj prominence nad/pod povprečjem okolice.
    from scipy.ndimage import uniform_filter
    mean = uniform_filter(a, size=size * 2 + 1, mode="nearest")
    hi = np.argwhere(mx & edge & (a - mean >= prominence))
    lo = np.argwhere(mn & edge & (mean - a >= prominence))
    return _thin(hi, a, True, min_dist), _thin(lo, a, False, min_dist)


def _thin(cands, a, is_max, min_dist):
    """Od središč, ki so bliže kot min_dist celic, obdrži najizrazitejše (največji max / najmanjši min)."""
    import numpy as np
    if len(cands) == 0 or not min_dist:
        return cands
    order = sorted(range(len(cands)), key=lambda i: -a[tuple(cands[i])] if is_max else a[tuple(cands[i])])
    kept = []
    for i in order:
        if all(np.hypot(*(cands[i] - cands[j])) >= min_dist for j in kept):
            kept.append(i)
    return cands[sorted(kept)]


# ── Ovoj strani ──────────────────────────────────────────────────────────────

def related_links(current):
    """Vrstica povezav na sestrske strani (v isti družini)."""
    items = [("/sinopticna/", "Sinoptična karta"), ("/stratosfera/", "Stratosfera in polarni vrtinec"),
             ("/indeksi/", "Indeksi AO, NAO, ENSO"), ("/prah/", "Saharski prah"),
             ("/primerjava-modelov/", "Primerjava modelov za Rečico")]
    parts = [f'<a href="{u}">{_html.escape(t)}</a>' for u, t in items if u != current]
    return '  <p class="muted-note">Še iz širše slike ozračja: ' + " · ".join(parts) + "</p>"


def write_site_page(rel_path, url, title, desc, body_inner, faq, crumb, published, modified=None,
                    og_image=None, extra_head=""):
    """Sestavi in zapiše stran prek skupnega ovoja (generate_seo_pages.page_shell)."""
    import generate_seo_pages as seo
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in faq
    ) + "\n  </div>"
    crumbs = [("Meteorec", "/"), (crumb, None)]
    body = (f'{seo.crumbs_html(crumbs)}\n{seo.stn_badge()}\n{body_inner}\n{faq_html}\n'
            f'{related_links(url)}\n  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>')
    wp = seo.webpage_schema(url, title, desc, date_published=published,
                            image=(f"{seo.SITE}{og_image}" if og_image and og_image.startswith("/") else og_image))
    if modified:
        wp = wp.replace(f'"datePublished":"{published}"', f'"datePublished":"{published}","dateModified":"{modified}"')
    schema_parts = [wp, seo.crumbs_schema(crumbs), seo.faq_schema(faq)]
    page = seo.page_shell(title, desc, url, "\n".join(schema_parts) + "\n" + extra_head, body,
                          og_image=(f"{seo.SITE}{og_image}" if og_image and og_image.startswith("/") else og_image))
    seo.write_page(rel_path.lstrip("/"), page, force=True)
    print(f"  → {rel_path}")
