#!/usr/bin/env python3
"""
tools/generate_vodostaj_page.py — Vodostaj Savinje pillar page

Generates /vodostaj-savinje/index.html: current flow/level status for the
Savinja through Zgornja Savinjska dolina, a 7-day GloFAS discharge outlook,
and the historical flood timeline (culminating in August 2023). Mirrors the
logic of the homepage's "Vodostaj" tab (app.js: fetchFlood/initVodostaj) but
renders server-side from two public sources so the page is static/crawlable:

  - Open-Meteo Flood API (GloFAS) for the 7-day discharge outlook at Rečica
  - ARSO's public hydro XML feed for real measured levels/flow/water
    temperature at gauge stations along the Savinja

Usage:
  python3 tools/generate_vodostaj_page.py
"""
import datetime, json, os, re, sys, unicodedata, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

FORECAST_DAYS = 7
REF_LAT, REF_LON = 46.3258, 14.9211  # Rečica ob Savinji, za razvrščanje postaj po bližini

# Isti pragovi kot na živem pripomočku (app.js _RIVER_THRESHOLDS), umerjeni
# na postajo Letuš. Uporabljajo se SAMO za postaje, za katere ARSO ne objavi
# svojih pragov visokih voda — glej station_status().
THRESHOLDS = {"raised": 80, "warning": 200, "alarm": 400}

DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

# Resnost 0..3 (station_level) -> barva. Zelena je ista validirana temna
# zelena kot na MTR grafu (#34d399 na tem ozadju pade test svetlosti, glej
# opombo pri MTR_CC v app.js); amber/rdeča sta isti barvi kot .warn-banner
# .lvl-orange/.lvl-red v vreme.css — resnost mora izgledati enako povsod na
# strani, ne nova paleta samo za ta graf.
LEVEL_COLORS = ["#059669", "#f59e0b", "#fb923c", "#ef4444"]
LEVEL_LABELS = ["Normalno", "Povečano", "Opozorilo", "Alarm"]

# Grafa na tej strani sta statičen SVG, izrisan tu v Pythonu ob generiranju
# strani — ne client-side fetch+draw kot na /tocnost-napovedi/ ali
# /test-napovedi/. Razlog: vsi podatki (7-dnevna GloFAS napoved, trenutne
# meritve ARSO) so že v Pythonu v trenutku izrisa in stran se tako ali tako
# regenerira enkrat dnevno (glej post-meta besedilo) — client fetch bi tu
# pomenil nov javni JSON samo za dva grafa brez drugega odjemalca, graf pa bi
# bil brez JS prazen. Tak SVG je viden tudi crawlerjem/brez JS, kar je tu
# vrednota (isto načelo kot pri /podatki/, ki je namenoma brez JS).


# ── Barve in pomožne funkcije za prikaz ─────────────────────────────────────
NEUTRAL_COLOR = "#94a3b8"   # postaja brez pragov ARSO: stanje ni ocenjeno

# Pritoki Savinje, ki jih ARSO utegne meriti (normalizirano brez šumnikov).
# Seznam je namenoma širši od tega, kar ARSO dejansko objavlja: stran vzame
# samo postaje, ki jih XML res vsebuje, in v dnevniku izpiše vse ostale
# postaje v okolici, ki se niso uvrstile (da se pozna, če pritok manjka v seznamu).
TRIB_RIVERS = {
    "dreta": "Drete", "lucnica": "Lučnice", "bolska": "Bolske", "paka": "Pake",
    "loznica": "Ložnice", "hudinja": "Hudinje", "voglajna": "Voglajne",
    "mozirnica": "Mozirnice", "ljubnica": "Ljubnice", "rinka": "Rinke",
}
BASIN_BBOX = (46.10, 46.50, 14.55, 15.40)  # lat_min, lat_max, lon_min, lon_max


def _norm(s):
    s = unicodedata.normalize("NFD", s or "").lower()
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()


def trib_key(reka):
    k = _norm(reka)
    return k if k in TRIB_RIVERS else None


def short_name(s):
    """»Savinja - Nazarje« -> »Nazarje« (reka je že v oznaki skupine)."""
    n = s["name"]
    return n.split(" - ", 1)[1].strip() if " - " in n else n


def card_level(s):
    """Resnost za prikaz: kot station_level(), a pritok brez pragov ARSO ostane
    neocenjen (enotni približek je umerjen na Letuš in bi za majhno reko lagal)."""
    if s.get("pretok") is None:
        return None
    if s.get("vv1") is None and not s.get("is_savinja", True):
        return None
    return station_level(s["pretok"], s)


def card_label(s):
    lvl = card_level(s)
    if lvl is not None:
        return station_status(s["pretok"], s)
    zn = s.get("znacilni")
    if s.get("pretok") is None:
        return "Pretok ni merjen"
    return (zn[0].upper() + zn[1:]) if zn else "Brez pragov ARSO"


def card_color(s):
    lvl = card_level(s)
    return LEVEL_COLORS[lvl] if lvl is not None else NEUTRAL_COLOR


def fmt_meas(datum):
    """ARSO »2026-11-13 15:30« -> »13. 11. ob 15.30« (pika med uro in minutami)."""
    try:
        dt = datetime.datetime.strptime(datum.strip(), "%Y-%m-%d %H:%M")
        return f"{dt.day}. {dt.month}. ob {dt.hour}.{dt.minute:02d}"
    except (AttributeError, ValueError):
        return datum or "—"


def _svg_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def outlook_chart_svg(rows, mean_q):
    """Linijski graf 7-dnevne GloFAS napovedi z gradientno podlago in črto tipičnega pretoka."""
    W, H = 640, 240
    pad_l, pad_r, pad_t, pad_b = 38, 16, 24, 30
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    vals = [v for _, v in rows]
    max_v = max(vals + ([mean_q] if mean_q else [])) * 1.25 or 1

    def x(i):
        return pad_l + plot_w * (i / (len(rows) - 1) if len(rows) > 1 else 0)

    def y(v):
        return pad_t + plot_h * (1 - max(0, v) / max_v)

    base = pad_t + plot_h
    parts = [f'<svg viewBox="0 0 {W} {H}" class="vod-svg" role="img" '
             f'aria-label="Napoved pretoka GloFAS za naslednjih {len(rows)} dni" preserveAspectRatio="xMidYMid meet">',
             '<defs><linearGradient id="vodArea" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="#60a5fa" stop-opacity=".38"/>'
             '<stop offset="1" stop-color="#60a5fa" stop-opacity=".02"/></linearGradient></defs>']
    for f in (0, .25, .5, .75, 1):
        v = max_v * f
        parts.append(f'<line class="vg" x1="{pad_l}" y1="{y(v):.1f}" x2="{W - pad_r}" y2="{y(v):.1f}"/>')
        parts.append(f'<text class="vm" x="{pad_l - 6}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="10">{seo.num(v, 0)}</text>')
    if mean_q:
        parts.append(f'<line x1="{pad_l}" y1="{y(mean_q):.1f}" x2="{W - pad_r}" y2="{y(mean_q):.1f}" '
                     f'stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="5,4"/>')
        parts.append(f'<text x="{W - pad_r}" y="{y(mean_q) - 6:.1f}" text-anchor="end" font-size="10" fill="#a78bfa">'
                     f'tipičen pretok ({seo.num(mean_q, 1)})</text>')
    line = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(rows))
    parts.append(f'<polygon points="{x(0):.1f},{base:.1f} {line} {x(len(rows) - 1):.1f},{base:.1f}" fill="url(#vodArea)"/>')
    parts.append(f'<polyline points="{line}" fill="none" stroke="#60a5fa" stroke-width="2.6" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    for i, (lbl, v) in enumerate(rows):
        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="#60a5fa" class="vdot"/>')
        parts.append(f'<text class="vt" x="{x(i):.1f}" y="{y(v) - 10:.1f}" text-anchor="middle" font-size="10" '
                     f'font-weight="700">{seo.num(v, 1)}</text>')
        parts.append(f'<text class="vm" x="{x(i):.1f}" y="{H - 9}" text-anchor="middle" font-size="10">{_svg_esc(lbl)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def river_schema_svg(main, tribs):
    """Shema rečnega sistema: Savinja kot glavna črta od izvira (levo) proti Celju (desno),
    pritoki kot veje, pritrjene na odsek med sosednjima postajama glede na zemljepisno
    dolžino. Postaje so razporejene enakomerno, ne v merilu, soteska ni zemljevid."""
    pts = [s for s in main if s.get("pretok") is not None or s.get("vodostaj") is not None]
    if len(pts) < 2:
        return ""
    pts = sorted(pts, key=lambda s: s["lon"])
    W = 840
    x0, x1 = 54, W - 170
    n = len(pts)
    xs = [x0 + (x1 - x0) * i / (n - 1) for i in range(n)]
    ym = 78
    has_t = bool(tribs)
    LABEL_W = 135   # širina oznake pritoka desno od vozlišča
    ROW_H = 46
    H = 200  # začasno; dokončna višina sledi razporeditvi pritokov

    def main_x(lon):
        if lon <= pts[0]["lon"]:
            return xs[0]
        for i in range(n - 1):
            a, b = pts[i]["lon"], pts[i + 1]["lon"]
            if a <= lon <= b:
                return xs[i] + (xs[i + 1] - xs[i]) * ((lon - a) / (b - a) if b > a else 0)
        return xs[-1]

    parts = [f'<svg viewBox="0 0 {W} {H}" class="vod-svg vod-schema" role="img" '
             f'aria-label="Shema merilnih postaj na Savinji in pritokih" preserveAspectRatio="xMidYMid meet">',
             '<defs><linearGradient id="vodRiver" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="840" y2="0">'
             '<stop offset="0" stop-color="#38bdf8"/><stop offset="1" stop-color="#2563eb"/></linearGradient></defs>']
    parts.append(f'<path d="M{x0 - 34},{ym} L{x1 + 34},{ym}" stroke="url(#vodRiver)" stroke-width="7" '
                 f'stroke-linecap="round" fill="none" opacity=".9"/>')
    parts.append(f'<path d="M{x1 + 28},{ym - 6} L{x1 + 38},{ym} L{x1 + 28},{ym + 6}" stroke="#2563eb" '
                 f'stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    parts.append(f'<text class="vm" x="{x0 - 34}" y="{ym - 46}" font-size="10">← gorvodno</text>')
    parts.append(f'<text class="vm" x="{x1 + 34}" y="{ym - 46}" font-size="10" text-anchor="end">dolvodno →</text>')

    # pritoki (veja navzdol od glavne črte). Razporeditev po vrsticah od desne proti levi:
    # vsak je za eno vrstico globlje od najglobljega bližnjega soseda desno, zato steblo
    # nobenega pritoka ne seka oznake drugega.
    tl = sorted(((main_x(t["lon"]), t) for t in tribs), key=lambda a: -a[0])
    rows_of, placed = {}, []
    for tx, t in tl:
        near = [r for px, r in placed if 0 <= px - tx < LABEL_W + 14]
        row = (max(near) + 1) if near else 0
        placed.append((tx, row))
        rows_of[id(t)] = (tx, row)
    nrows = (max(r for _, r in placed) + 1) if placed else 0
    H = 118 + (nrows * ROW_H + 24 if has_t else 0)
    parts[0] = (f'<svg viewBox="0 0 {W} {H}" class="vod-svg vod-schema" role="img" '
                f'aria-label="Shema merilnih postaj na Savinji in pritokih" preserveAspectRatio="xMidYMid meet">')
    for tx, t in tl:
        _, row = rows_of[id(t)]
        ty = ym + 62 + row * ROW_H
        c = card_color(t)
        parts.append(f'<path d="M{tx:.1f},{ty - 10} L{tx:.1f},{ym + 5}" '
                     f'stroke="#38bdf8" stroke-width="3" fill="none" stroke-linecap="round" opacity=".8"/>')
        parts.append(f'<circle cx="{tx:.1f}" cy="{ty}" r="8" fill="{c}" class="vnode"/>')
        q = t.get("pretok")
        val = f"{seo.num(q, 1)} m³/s" if q is not None else (f"{seo.num(t['vodostaj'], 0)} cm" if t.get("vodostaj") is not None else "—")
        parts.append(f'<text class="vt" x="{tx + 14:.1f}" y="{ty - 1}" font-size="11.5" font-weight="700">{_svg_esc(short_name(t))}</text>')
        parts.append(f'<text class="vm" x="{tx + 14:.1f}" y="{ty + 12}" font-size="10.5">{_svg_esc(t["reka"])} · {val}</text>')

    for s, sx in zip(pts, xs):
        c = card_color(s)
        q = s.get("pretok")
        top = f"{seo.num(q, 0)}" if q is not None else (f"{seo.num(s['vodostaj'], 0)} cm" if s.get("vodostaj") is not None else "—")
        parts.append(f'<circle cx="{sx:.1f}" cy="{ym}" r="13" fill="{c}" class="vnode" />')
        parts.append(f'<circle cx="{sx:.1f}" cy="{ym}" r="4.5" fill="#fff" opacity=".9"/>')
        parts.append(f'<text class="vt" x="{sx:.1f}" y="{ym - 22}" text-anchor="middle" font-size="14" font-weight="800">{top}</text>')
        parts.append(f'<text class="vt" x="{sx:.1f}" y="{ym + 34}" text-anchor="middle" font-size="11.5" font-weight="600">{_svg_esc(short_name(s))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def gauge_html(s):
    """Merilo stanja na LASTNI lestvici postaje (do tretjega praga ARSO)."""
    q = s.get("pretok")
    vv1, vv2, vv3 = s.get("vv1"), s.get("vv2"), s.get("vv3")
    if q is None or vv1 is None or vv3 is None or not vv2:
        return '<div class="vod-nogauge">ARSO za to postajo ne objavlja pragov visokih voda</div>'
    top = vv3 * 1.15
    pct = lambda v: max(0, min(100, 100 * v / top))
    zones = [(0, vv1, 0), (vv1, vv2, 1), (vv2, vv3, 2), (vv3, top, 3)]
    z = "".join(f'<i style="left:{pct(a):.1f}%;width:{pct(b) - pct(a):.1f}%;background:{LEVEL_COLORS[l]}"></i>' for a, b, l in zones)
    mark = f'<b style="left:{pct(q):.1f}%" aria-hidden="true"></b>'
    lbl = f'{seo.num(vv1, 0)} · {seo.num(vv2, 0)} · {seo.num(vv3, 0)} m³/s'
    return (f'<div class="vod-gauge" role="img" aria-label="Pretok {seo.num(q, 1)} m³/s; pragovi ARSO {lbl}">{z}{mark}</div>'
            f'<div class="vod-gauge-t">pragovi ARSO: {lbl}</div>')


def station_card_html(s):
    c = card_color(s)
    q, h, t = s.get("pretok"), s.get("vodostaj"), s.get("temp")
    big = (f'<div class="vod-q">{seo.num(q, 1)}<small> m³/s</small></div>' if q is not None
           else (f'<div class="vod-q">{seo.num(h, 0)}<small> cm</small></div>' if h is not None else '<div class="vod-q">—</div>'))
    facts = []
    if q is not None and h is not None:
        facts.append(f'<span>vodostaj <b>{seo.num(h, 0)} cm</b></span>')
    if t is not None:
        facts.append(f'<span>voda <b>{seo.num(t, 1)} °C</b></span>')
    facts_html = "".join(facts) or '<span>brez dodatnih meritev</span>'
    return (f'<article class="vod-card" style="--c:{c}">'
            f'<header><span class="vod-river">{_svg_esc(s["reka"])}</span>'
            f'<h3>{_svg_esc(short_name(s))}</h3></header>'
            f'{big}'
            f'<span class="vod-pill">{_svg_esc(card_label(s))}</span>'
            f'<div class="vod-facts">{facts_html}</div>'
            f'{gauge_html(s)}'
            f'<footer>meritev {fmt_meas(s.get("datum"))}</footer></article>')


def flood_bars_html(events):
    top = max(e["q"] for e in events)
    out = []
    for e in reversed(events):
        rec = e["q"] == top
        out.append(f'<div class="vod-fl{" rec" if rec else ""}">'
                   f'<div class="vod-fl-h"><span class="vod-fl-d">{e["date"]}</span>'
                   f'<span class="vod-fl-q">{e["q"]} m³/s</span></div>'
                   f'<div class="vod-fl-bar"><i style="width:{100 * e["q"] / top:.1f}%"></i></div>'
                   f'<p>{e["desc"]}</p></div>')
    return '<div class="vod-floods">' + "".join(out) + '</div>'


CHART_CSS = """<style>
.vod-hero{display:grid;grid-template-columns:1.25fr 1fr;gap:1rem;margin:1.2rem 0 1.6rem}
.vod-hero-main{position:relative;overflow:hidden;border-radius:18px;padding:1.3rem 1.4rem;
  background:linear-gradient(135deg,rgba(56,189,248,.20),rgba(37,99,235,.10) 55%,rgba(37,99,235,.02));
  border:1px solid var(--card-border)}
.vod-hero-main:after{content:"";position:absolute;right:-30px;bottom:-34px;width:190px;height:190px;border-radius:50%;
  background:radial-gradient(circle,rgba(56,189,248,.28),transparent 68%);pointer-events:none}
.vod-eyebrow{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.07em;text-transform:uppercase;color:var(--cyan,#22d3ee)}
.vod-big{font-size:clamp(2.6rem,9vw,3.8rem);font-weight:800;line-height:1.05;margin:.3rem 0 .5rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.vod-big small{font-size:1.1rem;font-weight:600;color:var(--muted);letter-spacing:0}
.vod-hero-meta{color:var(--muted);font-size:.86rem;margin-top:.55rem;position:relative;z-index:1}
.vod-hero-side{display:grid;grid-template-columns:1fr 1fr;gap:.7rem}
.vod-mini{border-radius:14px;padding:.85rem .95rem;background:var(--card-bg);border:1px solid var(--card-border)}
.vod-mini span{display:block;font-size:.72rem;color:var(--muted);line-height:1.35}
.vod-mini b{display:block;font-size:1.55rem;font-weight:800;margin:.15rem 0;font-variant-numeric:tabular-nums}
.vod-mini em{font-style:normal;font-size:.72rem;color:var(--muted)}
.vod-pill{display:inline-block;padding:.22rem .7rem;border-radius:999px;font-size:.78rem;font-weight:700;
  color:var(--c,#94a3b8);background:color-mix(in srgb,var(--c,#94a3b8) 16%,transparent);
  border:1px solid color-mix(in srgb,var(--c,#94a3b8) 45%,transparent)}
.vod-h-pill{position:relative;z-index:1}
.vod-section-t{display:flex;align-items:baseline;gap:.6rem;flex-wrap:wrap}
.vod-count{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--muted)}
.vod-chart-block{margin:1.2rem 0 1.8rem;padding:1rem 1rem .8rem;border-radius:16px;background:var(--card-bg);border:1px solid var(--card-border)}
.vod-chart-title{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.06em;
  text-transform:uppercase;color:var(--cyan,#22d3ee);margin-bottom:.4rem}
.vod-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.vod-scroll .vod-schema{min-width:600px}
.vod-svg{width:100%;height:auto;display:block}
.vod-svg .vg{stroke:var(--text);stroke-opacity:.1}
.vod-svg .vt{fill:var(--text)}
.vod-svg .vm{fill:var(--muted)}
.vod-svg .vnode{stroke:var(--card-bg);stroke-width:3}
.vod-svg .vdot{stroke:var(--card-bg);stroke-width:2}
.vod-note{font-size:.76rem;color:var(--muted);margin:.5rem 0 0;line-height:1.5}
.vod-group-t{font-size:1.02rem;margin:1.5rem 0 .6rem;display:flex;align-items:center;gap:.5rem}
.vod-group-t:before{content:"";width:9px;height:9px;border-radius:50%;background:#38bdf8}
.vod-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.85rem}
.vod-card{position:relative;border-radius:16px;padding:1rem 1.05rem .8rem;background:var(--card-bg);
  border:1px solid var(--card-border);border-top:3px solid var(--c);overflow:hidden}
.vod-card header{display:flex;flex-direction:column;gap:.1rem;margin-bottom:.4rem}
.vod-river{font-family:'JetBrains Mono',monospace;font-size:.66rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.vod-card h3{margin:0;font-size:1.08rem}
.vod-q{font-size:2rem;font-weight:800;line-height:1.1;font-variant-numeric:tabular-nums;margin:.15rem 0 .45rem}
.vod-q small{font-size:.8rem;font-weight:600;color:var(--muted)}
.vod-facts{display:flex;gap:.9rem;flex-wrap:wrap;margin:.55rem 0 .7rem;font-size:.8rem;color:var(--muted)}
.vod-facts b{color:var(--text)}
.vod-gauge{position:relative;height:9px;border-radius:5px;overflow:visible;background:rgba(127,127,127,.18)}
.vod-gauge i{position:absolute;top:0;bottom:0;opacity:.85}
.vod-gauge i:first-child{border-radius:5px 0 0 5px}
.vod-gauge i:last-of-type{border-radius:0 5px 5px 0}
.vod-gauge b{position:absolute;top:-4px;width:4px;height:17px;margin-left:-2px;border-radius:2px;background:var(--text);box-shadow:0 0 0 2px var(--card-bg)}
.vod-gauge-t{margin-top:.35rem;font-size:.66rem;color:var(--muted);font-family:'JetBrains Mono',monospace}
.vod-nogauge{font-size:.72rem;color:var(--muted);padding:.4rem 0;border-top:1px dashed var(--card-border)}
.vod-card footer{margin-top:.6rem;font-size:.7rem;color:var(--muted)}
.vod-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.7rem;font-size:.78rem;color:var(--muted)}
.vod-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.3rem;vertical-align:middle}
.vod-floods{display:grid;gap:.7rem;margin:1rem 0}
.vod-fl{padding:.75rem .95rem;border-radius:14px;background:var(--card-bg);border:1px solid var(--card-border)}
.vod-fl.rec{border-color:#ef4444;background:color-mix(in srgb,#ef4444 8%,var(--card-bg))}
.vod-fl-h{display:flex;justify-content:space-between;gap:.6rem;font-weight:700}
.vod-fl-q{font-variant-numeric:tabular-nums}
.vod-fl-bar{height:7px;border-radius:4px;background:rgba(127,127,127,.18);margin:.45rem 0 .5rem;overflow:hidden}
.vod-fl-bar i{display:block;height:100%;border-radius:4px;background:linear-gradient(90deg,#60a5fa,#2563eb)}
.vod-fl.rec .vod-fl-bar i{background:linear-gradient(90deg,#fb923c,#ef4444)}
.vod-fl p{margin:0;font-size:.85rem;color:var(--muted);line-height:1.55}
@media(max-width:760px){.vod-hero{grid-template-columns:1fr}.vod-cards{grid-template-columns:1fr 1fr}}
@media(max-width:480px){.vod-cards{grid-template-columns:1fr}.vod-hero-side{grid-template-columns:1fr 1fr}}
</style>"""


FLOOD_HISTORY = [
    {"date": "November 1990", "q": 820, "desc": "Poplave Savinje — ena prvih večjih po vojni, škoda po celotni dolini."},
    {"date": "Oktober 1998", "q": 950, "desc": "Katastrofalne poplave Zgornje Savinjske doline, škoda presegla 100 mio DEM."},
    {"date": "November 2000", "q": 680, "desc": "Hude poplave, prelitje nasipov pri Letušu in Nazarjah."},
    {"date": "September 2007", "q": 420, "desc": "Poplave po dolgotrajnih padavinah, lokalne evakuacije."},
    {"date": "November 2012", "q": 310, "desc": "Povečan pretok, opozorilo ARSO — brez večjih škod."},
    {"date": "Avgust 2023", "q": 1100, "desc": "Katastrofalne poplave — zgodovinski rekord Savinje, škoda presegla 500 mio €."},
]


def fetch_flood_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "daily": "river_discharge,river_discharge_mean,river_discharge_max",
        "forecast_days": FORECAST_DAYS,
    })
    url = f"https://flood-api.open-meteo.com/v1/flood?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def _fetch_arso_root():
    req = urllib.request.Request(
        "https://www.arso.gov.si/xml/vode/hidro_podatki_zadnji.xml",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*",
                 "Referer": "https://www.arso.gov.si/"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    return ET.fromstring(data)


def _parse_station(p):
    try:
        lat = float(p.get("wgs84_sirina"))
        lon = float(p.get("wgs84_dolzina"))
    except (TypeError, ValueError):
        return None

    def to_float(tag):
        v = p.findtext(tag)
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    reka = (p.findtext("reka") or "").strip()
    return {
        "name": (p.findtext("ime_kratko") or p.findtext("merilno_mesto") or "ARSO").strip(),
        "reka": reka,
        "sifra": p.get("sifra"),
        "datum": (p.findtext("datum") or "").strip(),
        "lat": lat, "lon": lon,
        "vodostaj": to_float("vodostaj"),
        "pretok": to_float("pretok"),
        "temp": to_float("temp_vode"),
        # Uradni pragovi visokih voda za TO postajo — brez njih je ocena
        # stanja umerjena na eno samo postajo in za ostale napačna.
        "vv1": to_float("prvi_vv_pretok"),
        "vv2": to_float("drugi_vv_pretok"),
        "vv3": to_float("tretji_vv_pretok"),
        "znacilni": (p.findtext("pretok_znacilni") or "").strip() or None,
        "is_savinja": "savinj" in reka.lower(),
        "dist2": (lat - REF_LAT) ** 2 + (lon - REF_LON) ** 2,
    }


def fetch_arso_stations():
    """Postaje na Savinji, po bližini Rečice. Uvaža jih MeteoGasilec
    (/meteogasilec/vodotoki/), zato se izhod ne sme spremeniti."""
    out = []
    for p in _fetch_arso_root().findall("postaja"):
        s = _parse_station(p)
        if s and s["is_savinja"]:
            out.append(s)
    out.sort(key=lambda s: s["dist2"])
    return out


def fetch_arso_basin():
    """Savinja + njeni pritoki (TRIB_RIVERS) v okolici doline. Vrne (savinja, pritoki,
    ostale_v_okolici): zadnje so postaje v BASIN_BBOX, ki niso na seznamu, samo za
    dnevnik -- da se pozna, če ARSO meri pritok, ki ga seznam ne pozna."""
    lat0, lat1, lon0, lon1 = BASIN_BBOX
    main, tribs, other = [], [], []
    for p in _fetch_arso_root().findall("postaja"):
        s = _parse_station(p)
        if not s:
            continue
        in_box = lat0 <= s["lat"] <= lat1 and lon0 <= s["lon"] <= lon1
        if s["is_savinja"]:
            main.append(s)
        elif in_box and trib_key(s["reka"]):
            tribs.append(s)
        elif in_box:
            other.append(s)
    main.sort(key=lambda s: s["lon"])           # od izvira proti Celju
    tribs.sort(key=lambda s: (_norm(s["reka"]), s["lon"]))
    return main, tribs, other



def flow_status(q, mean):
    ratio = (q / mean) if mean else 1.0
    if ratio < 0.6:
        return "Nizek pretok", ratio
    if ratio < 1.5:
        return "Normalen pretok", ratio
    if ratio < 2.5:
        return "Povišan pretok", ratio
    return "Visok pretok", ratio


def station_level(q, station=None):
    """Resnost stanja postaje: None (ni podatka) ali 0–3.

    Meri se po pragovih visokih voda, ki jih ARSO objavi ZA TO POSTAJO
    (`prvi/drugi/tretji_vv_pretok`). THRESHOLDS je umerjen na Letuš in za druge
    postaje ne velja: pri Solčavi je naš prag za »Opozorilo« (200 m³/s) nad
    tretjim pragom ARSO (100), torej bi tam pravo visoko vodo prikazali kot
    normalno stanje. Naš približek zato ostane samo tam, kjer ARSO pragov ne
    objavi — in je v izpisu tako tudi označen.
    """
    if q is None:
        return None
    s = station or {}
    vv1, vv2, vv3 = s.get("vv1"), s.get("vv2"), s.get("vv3")
    if vv1 is not None:
        if vv3 is not None and q >= vv3:
            return 3
        if vv2 is not None and q >= vv2:
            return 2
        return 1 if q >= vv1 else 0
    if q >= THRESHOLDS["alarm"]:
        return 3
    if q >= THRESHOLDS["warning"]:
        return 2
    return 1 if q >= THRESHOLDS["raised"] else 0


def station_status(q, station=None):
    """Besedna oznaka stanja. Pod prvim pragom prevzame ARSO-jevo lastno
    oznako (`pretok_znacilni`, npr. »mali pretok«) namesto naše besede."""
    lvl = station_level(q, station)
    if lvl is None:
        return "—"
    s = station or {}
    if s.get("vv1") is not None:
        if lvl:
            return f"{lvl}. prag ARSO"
        zn = s.get("znacilni")
        return zn[0].upper() + zn[1:] if zn else "Pod pragom"
    return ["Normalen (ocena)", "Povečan (ocena)", "Opozorilo (ocena)", "Alarm (ocena)"][lvl]


def build_body(flood, main, tribs):
    d = flood.get("daily") or {}
    discharge = [v for v in (d.get("river_discharge") or []) if v is not None]
    if not discharge:
        raise ValueError("Open-Meteo Flood API brez podatkov o pretoku")
    today_q = discharge[0]
    mean_list = d.get("river_discharge_mean") or []
    mean_q = mean_list[0] if mean_list and mean_list[0] is not None else sum(discharge) / len(discharge)
    max7 = max(discharge)
    status, ratio = flow_status(today_q, mean_q)

    # Na vprašanje »kakšen je pretok danes« odgovori IZMERJENA vrednost, ne
    # modelska. GloFAS ima mrežo ~5 km in Savinje v ozki dolini ne razloči —
    # njegova celica pri Rečici kaže nekajkrat manj od meritve na postaji nekaj
    # kilometrov dolvodno. Model ostane na strani kot napoved poteka, jasno
    # označen; vira se ne zlivata v eno številko.
    by_dist = sorted(main, key=lambda s: s["dist2"])
    nearest = by_dist[0] if by_dist else None
    meritev = nearest.get("pretok") if nearest else None
    all_st = main + tribs

    model_txt = (f'Modelska napoved GloFAS za današnji dan je {seo.num(today_q, 1)} m³/s '
                 f'({status.lower()}, {round(ratio * 100)} % tipične vrednosti {seo.num(mean_q, 1)} m³/s); '
                 f'v ozki dolini pretok podceni, zato je merodajna meritev.')
    trib_txt = ""
    tq = [t for t in tribs if t.get("pretok") is not None]
    if tq:
        trib_txt = " Pritoki: " + ", ".join(
            f'{t["reka"]} ({short_name(t)}) {seo.num(t["pretok"], 1)} m³/s' for t in tq) + "."
    if meritev is not None:
        answer = (f'  <p class="archive-intro"><strong>Na kratko:</strong> Savinja pri Rečici ob Savinji ima danes izmerjen pretok '
                  f'<strong>{seo.num(meritev, 1)} m³/s</strong>'
                  + (f' in vodostaj {seo.num(nearest["vodostaj"], 0)} cm' if nearest.get("vodostaj") is not None else '')
                  + f' — najbližja merilna postaja ARSO je {nearest["name"]} '
                  f'({station_status(meritev, nearest).lower()}).{trib_txt} {model_txt} '
                  f'Podatki se osvežujejo dnevno — nazadnje {TODAY.isoformat()}. '
                  f'Vir: meritve ARSO (Agencija Republike Slovenije za okolje) in modelska napoved GloFAS (Open-Meteo); '
                  f'to ni uradno opozorilo, za ukrepanje veljata ARSO in URSZR.</p>')
    else:
        answer = (f'  <p class="archive-intro"><strong>Na kratko:</strong> meritev ARSO trenutno ni na voljo. {model_txt} '
                  f'Podatki se osvežujejo dnevno — nazadnje {TODAY.isoformat()}. '
                  f'Vir: meritve ARSO (Agencija Republike Slovenije za okolje) in modelska napoved GloFAS (Open-Meteo); '
                  f'to ni uradno opozorilo, za ukrepanje veljata ARSO in URSZR.</p>')

    warn_box = ""
    if ratio >= 2.5:
        warn_box = ('  <div class="partial-note">⚠️ Pretok znatno presega normalo — spremljaj uradna opozorila ARSO '
                    'in URSZR. Avgusta 2023 je Savinja pri Letušu dosegla 1100 m³/s.</div>')

    # ── Hero: izmerjena vrednost najbližje postaje + model ob strani ─────────
    if nearest is not None and (meritev is not None or nearest.get("vodostaj") is not None):
        hc = card_color(nearest)
        hv = (f'{seo.num(meritev, 1)}<small> m³/s</small>' if meritev is not None
              else f'{seo.num(nearest["vodostaj"], 0)}<small> cm</small>')
        meta = []
        if meritev is not None and nearest.get("vodostaj") is not None:
            meta.append(f'vodostaj {seo.num(nearest["vodostaj"], 0)} cm')
        if nearest.get("temp") is not None:
            meta.append(f'voda {seo.num(nearest["temp"], 1)} °C')
        meta.append(f'meritev {fmt_meas(nearest.get("datum"))}')
        hero_main = (f'<div class="vod-hero-main" style="--c:{hc}">'
                     f'<div class="vod-eyebrow">Izmerjeno · {_svg_esc(nearest["name"])} · ARSO</div>'
                     f'<div class="vod-big">{hv}</div>'
                     f'<span class="vod-pill vod-h-pill">{_svg_esc(card_label(nearest))}</span>'
                     f'<div class="vod-hero-meta">{" · ".join(meta)}</div></div>')
    else:
        hero_main = ('<div class="vod-hero-main"><div class="vod-eyebrow">Izmerjeno · ARSO</div>'
                     '<div class="vod-big">—</div><div class="vod-hero-meta">meritev trenutno ni na voljo</div></div>')
    quick = f'''  <div class="vod-hero">
    {hero_main}
    <div class="vod-hero-side">
      <div class="vod-mini"><span>Največ v napovedi (7 dni)</span><b>{seo.num(max7, 1)}</b><em>m³/s · model GloFAS</em></div>
      <div class="vod-mini"><span>Tipičen pretok za ta čas</span><b>{seo.num(mean_q, 1)}</b><em>m³/s · model GloFAS</em></div>
      <div class="vod-mini"><span>Merilnih postaj</span><b>{len(all_st)}</b><em>{len(main)} na Savinji{f", {len(tribs)} na pritokih" if tribs else ""}</em></div>
      <div class="vod-mini"><span>Model proti meritvi</span><b>{round(ratio * 100)} %</b><em>današnji model glede na tipičen pretok</em></div>
    </div>
  </div>
{warn_box}'''

    # ── Postaje: shema, kartice, tabela ─────────────────────────────────────
    if all_st:
        schema_svg = river_schema_svg(main, tribs)
        schema = (
            '  <div class="vod-chart-block" id="vod-schema">\n'
            '  <div class="vod-chart-title">Rečni sistem — pretok na postajah (m³/s)</div>\n'
            f'  <div class="vod-scroll" tabindex="0">{schema_svg}</div>\n'
            '  <p class="vod-note">Shema, ne zemljevid: postaje so razporejene enakomerno po toku Savinje, pritoki so '
            'pripeti približno glede na zemljepisno dolžino. Barva kroga je stanje glede na prage ARSO za tisto '
            'postajo; siva pomeni, da ARSO za postajo pragov ne objavlja.</p>\n  </div>'
        ) if schema_svg else ""
        cards_main = "".join(station_card_html(s) for s in main)
        cards_trib = "".join(station_card_html(s) for s in tribs)
        cards = f'  <h3 class="vod-group-t">Savinja <span class="vod-count">{len(main)} postaj, od izvira proti Celju</span></h3>\n  <div class="vod-cards">{cards_main}</div>\n'
        if tribs:
            names = ", ".join(sorted({t["reka"] for t in tribs}))
            cards += (f'  <h3 class="vod-group-t">Pritoki <span class="vod-count">{len(tribs)} postaj · {names}</span></h3>\n'
                      f'  <div class="vod-cards">{cards_trib}</div>\n')
        legend = ('<div class="vod-legend">' + "".join(
            f'<span><i style="background:{c}"></i>{lbl}</span>' for c, lbl in zip(LEVEL_COLORS, LEVEL_LABELS)
        ) + f'<span><i style="background:{NEUTRAL_COLOR}"></i>brez pragov ARSO</span></div>')
        note = ('  <p class="vod-note">Besede ob številki (npr. »veliki pretok«) so ARSO-jeva razvrstitev pretoka glede na '
                'značilne pretoke in ne pomenijo poplave. Opozorilni pragovi visokih voda so označeni na merilu pod številko.</p>')
        st_rows = "\n".join(
            f'      <tr><th>{s["name"]}</th><td>{_svg_esc(s["reka"])}</td>'
            f'<td>{seo.num(s["vodostaj"], 0) if s["vodostaj"] is not None else "—"} cm</td>'
            f'<td>{seo.num(s["pretok"], 1) if s["pretok"] is not None else "—"} m³/s</td>'
            f'<td>{seo.num(s["temp"], 1) if s["temp"] is not None else "—"} °C</td>'
            f'<td>{_svg_esc(card_label(s))}</td></tr>'
            for s in all_st
        )
        st_table = ('  <div class="table-scroll" tabindex="0"><table class="stats">\n'
                    '    <tr><th>Postaja</th><th>Reka</th><th>Vodostaj</th><th>Pretok</th><th>Voda</th><th>Stanje</th></tr>\n'
                    f'{st_rows}\n  </table></div>')
    else:
        schema = cards = legend = note = ""
        st_table = '  <p class="muted-note">Postaje ARSO trenutno niso dosegljive.</p>'

    # ── 7-day GloFAS outlook: graf + tabela ─────────────────────────────────
    times = d.get("time") or []
    out_rows = []
    for k, q in enumerate(discharge[:FORECAST_DAYS]):
        if k < len(times):
            dt = datetime.date.fromisoformat(times[k])
            lbl = "danes" if k == 0 else DAN_KRATKO[dt.weekday()] + f" {dt.day}. {dt.month}."
        else:
            lbl = f"+{k} d"
        out_rows.append((lbl, q))
    outlook_chart = (
        '  <div class="vod-chart-block" id="vod-chart-outlook">\n'
        '  <div class="vod-chart-title">Napoved pretoka GloFAS, naslednjih 7 dni</div>\n'
        f'  {outlook_chart_svg(out_rows, mean_q)}\n  </div>'
    )
    outlook_table = '  <div class="table-scroll" tabindex="0"><table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{seo.num(q, 1)} m³/s</td></tr>' for lbl, q in out_rows
    ) + "\n  </table></div>"

    # ── Zgodovina poplav: vodoravni stolpci ─────────────────────────────────
    hist_bars = flood_bars_html(FLOOD_HISTORY)

    # ── Opis in FAQ ─────────────────────────────────────────────────────────
    trib_names = sorted({t["reka"] for t in tribs})
    present = {trib_key(r) for r in trib_names}
    trib_gen = [g for k, g in TRIB_RIVERS.items() if k in present]  # Dreta prva, ne abecedno
    where = (f"Savinje in pritokov ({', '.join(trib_names)})" if trib_names else "Savinje")
    qa = [
        ("Kakšen je trenutni pretok Savinje pri Rečici ob Savinji?",
         (f"Najbližja merilna postaja ARSO ({nearest['name']}) danes meri {seo.num(meritev, 1)} m³/s. "
          if meritev is not None else "Meritev ARSO trenutno ni na voljo. ")
         + f"Modelska napoved GloFAS (Open-Meteo) za isti dan je {seo.num(today_q, 1)} m³/s, kar je "
           f"{round(ratio * 100)} % tipične vrednosti za ta datum; model ima mrežo približno 5 km in "
           f"pretok v ozki dolini podceni, zato je merodajna meritev."),
    ]
    for t in tribs:
        if t.get("pretok") is not None or t.get("vodostaj") is not None:
            v = (f"{seo.num(t['pretok'], 1)} m³/s" if t.get("pretok") is not None else f"vodostaj {seo.num(t['vodostaj'], 0)} cm")
            qa.append((f"Kakšen je trenutni pretok reke {t['reka']} ({short_name(t)})?",
                       f"Postaja ARSO {t['name']} je {fmt_meas(t.get('datum'))} izmerila {v}. "
                       f"{'Pragove visokih voda ARSO za to postajo objavlja, merilo je na kartici. ' if t.get('vv1') is not None else 'ARSO za to postajo ne objavlja pragov visokih voda, zato stanje ni ocenjeno. '}"
                       f"To je meritev, ne uradno opozorilo."))
    qa += [
        ("Katere reke in merilne postaje spremlja ta stran?",
         f"Stran prikazuje meritve ARSO za {where}: skupaj {len(all_st)} postaj. "
         + ("Pritoki se pojavijo, kadar jih ARSO objavlja v svojem javnem seznamu hidroloških postaj. " if tribs else
            "ARSO v tem trenutku ne objavlja nobenega pritoka v bližini doline, zato so prikazane samo postaje na Savinji. ")
         + "Seznam se osvežuje ob vsakem generiranju strani."),
        ("Kdaj je bila zadnja večja poplava Savinje?",
         "Najhujša doslej zabeležena poplava je bila avgusta 2023, ko je pretok pri Letušu dosegel približno "
         "1100 m³/s in povzročil škodo za več kot 500 milijonov evrov po vsej Zgornji Savinjski dolini."),
        ("Kaj pomenijo pragovi pri posameznih postajah?",
         "Stanje vsake postaje se primerja z njenimi lastnimi pragovi visokih voda, ki jih objavi ARSO — "
         "ti se med postajami močno razlikujejo, ker se razlikuje velikost prispevnega območja: prvi prag "
         "je pri Solčavi okoli 56 m³/s, pri Letušu pa okoli 360 m³/s. Kjer ARSO pragov ne objavi, je "
         "stanje Savinje označeno kot ocena po enotnem približku (povečan od 80, opozorilo od 200, alarm od "
         "400 m³/s), umerjenem na Letuš; pritoki brez pragov ostanejo neocenjeni. Za ukrepanje vedno štejejo "
         "uradna opozorila ARSO in URSZR."),
        ("Kje spremljam uradna opozorila pred poplavami?",
         "Uradna opozorila objavljata ARSO (meteo.arso.gov.si) in Uprava RS za zaščito in reševanje "
         "(gov.si/urszr); pri višjih vodostajih spremljaj tudi obvestila občine Rečica ob Savinji."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    h1 = "Vodostaj in pretok Savinje" + (f" in {trib_gen[0]}" if trib_gen else "") + " — Zgornja Savinjska dolina"
    intro_st = (f"Trenutno izmerjeni vodostaj, pretok in temperatura vode na postajah ARSO: {len(main)} na Savinji od Solčave do Celja"
                + (f" in {len(tribs)} na pritokih ({', '.join(trib_names)})." if tribs else "."))

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Vodostaj Savinje", None)])}
{seo.stn_badge()}
  <h1 class="page-title">{h1}</h1>
  <p class="post-meta">GloFAS napoved (Open-Meteo) + meritve ARSO · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Merilne postaje ARSO: {where}</h2>
  <p class="archive-intro">{intro_st}</p>
{schema}
{cards}
  {legend}
{note}
  <h2>Vse postaje v tabeli</h2>
{st_table}
  <h2>Napoved pretoka — naslednjih {FORECAST_DAYS} dni</h2>
  <p class="archive-intro">GloFAS napoved pretoka Savinje pri Rečici ob Savinji. Model je grob (mreža približno 5 km): kaže potek, ne točne vrednosti.</p>
{outlook_chart}
{outlook_table}
  <h2>Zgodovina poplav Savinje</h2>
  <p class="archive-intro">Največje zabeležene poplave Savinje po ocenjenem vršnem pretoku pri postaji Letuš.
  Podroben pregled poplav avgusta 2023 — vzroki, hidrološki rekordi, škoda in obnova — je v
  <a href="/blog/poplave-2023.html">ločenem članku na blogu</a>.</p>
{hist_bars}
  <h2>Kako brati pragove pretoka</h2>
  <p class="archive-intro">Stanje posamezne postaje se primerja z njenimi lastnimi pragovi
  visokih voda, kot jih objavi ARSO (prvi, drugi in tretji prag). Ti se med postajami močno razlikujejo, ker
  se razlikuje velikost prispevnega območja — enoten prag za vso dolino bi bil pri Solčavi previsok in pri
  Celju prenizek. Kjer ARSO pragov ne objavi, je stanje Savinje izrecno označeno kot ocena po enotnem približku,
  umerjenem na Letuš, pritoki pa so brez ocene. Nobena od teh oznak ni uradno opozorilo: pri dejanski nevarnosti
  vedno štejejo objave ARSO in URSZR. Vir meritev: Agencija Republike Slovenije za okolje (ARSO).</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🚨 Uradni viri in opozorila</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener" class="mtn-avk-link">🌊 ARSO — hidrološka opozorila</a>
      <a href="https://www.gov.si/drzavni-organi/organi-v-sestavi/uprava-za-zascito-in-resevanje/" target="_blank" rel="noopener" class="mtn-avk-link">🛟 URSZR</a>
      <a href="https://vode.arso.gov.si/hidarhiv/" target="_blank" rel="noopener" class="mtn-avk-link">📈 ARSO — hidrološki arhiv</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model pretoka uporablja iste vhodne podatke (GloFAS/Open-Meteo, ARSO) kot živi pripomoček
  na <a href="/">naslovni strani Meteorec</a> (zavihek »Vodostaj«).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, today_q, status, ratio, meritev, trib_gen


def page_title(trib_gen):
    base = "Vodostaj Savinje danes: Nazarje, Letuš, Solčava"
    if trib_gen:
        cand = f"Vodostaj Savinje in {trib_gen[0]} danes: Nazarje, Letuš"
        if len(cand) <= 60:
            return cand
    return base


def main():
    print(f"[{TODAY}] Pridobivam napoved GloFAS in postaje ARSO …")
    try:
        flood = fetch_flood_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju GloFAS napovedi: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        main_st, tribs, other = fetch_arso_basin()
        print(f"  postaje: {len(main_st)} na Savinji, {len(tribs)} na pritokih "
              f"({', '.join(t['reka'] + '/' + short_name(t) for t in tribs) or '—'})")
        if other:
            print("  ostale postaje ARSO v okolici (niso uvrščene; če je med njimi pritok Savinje, dodaj ga v TRIB_RIVERS): "
                  + "; ".join(f"{o['reka']}/{short_name(o)}" for o in other))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as e:
        print(f"⚠ ARSO postaje nedosegljive, nadaljujem brez njih: {e}", file=sys.stderr)
        main_st, tribs = [], []

    try:
        body, today_q, status, ratio, meritev, trib_gen = build_body(flood, main_st, tribs)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/vodostaj-savinje/"
    title = page_title(trib_gen)
    # Opis vodi izmerjena vrednost; modelska gre v besedilo strani, ne v opis,
    # ker je opis odgovor na "kakšen je pretok danes".
    desc = ((f"Pretok Savinje danes: {seo.num(meritev, 1)} m³/s, izmerjeno na najbližji postaji ARSO. "
             if meritev is not None else "Pretok Savinje danes po napovedi GloFAS. ")
            + ("Tudi " + ", ".join(trib_gen) + " in drugi pritoki, " if trib_gen else "")
            + "Nazarje, Letuš, Solčava, napoved za 7 dni in zgodovina poplav.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vodostaj Savinje", None)]),
    ]) + "\n" + CHART_CSS

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("vodostaj-savinje/index.html", html, force=True)
    print(f"  → vodostaj-savinje/index.html (izmerjeno {seo.num(meritev, 1)} m³/s, model {seo.num(today_q, 1)} m³/s, {status})")


if __name__ == "__main__":
    main()
