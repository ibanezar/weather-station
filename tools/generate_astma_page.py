#!/usr/bin/env python3
"""
tools/generate_astma_page.py — Vreme in astma: tveganje po dnevih

Generates /astma/index.html: 5-dnevna ocena, kako vreme in zrak v Zgornji
Savinjski dolini lahko obremenita ljudi z astmo. Po zgledu aplikacij tipa
DailyBreath / AsthmaMD, a brez računa, brez dnevnika simptomov na strežniku
in brez zdravstvenih trditev.

Dejavniki (vsak 0-3 točke na dan): cvetni prah, PM2,5, ozon, NO2, mrzel zrak,
vročina, nevihta (+ trava = »nevihtna astma«), hitra sprememba vremena,
vlaga. Skupna ocena je vsota točk; obiskovalec lahko v brskalniku označi
svoje sprožilce (localStorage, nikamor se ne pošlje), ki štejejo dvojno.

To NI diagnoza in NI zdravniški nasvet; ocena ni verjetnost napada. Pragovi so
naša delitev po splošno znanih sprožilcih (EU/WHO meje za onesnaževala).
Zračni podatki: Copernicus CAMS prek Open-Meteo (isti vir in ista funkcija
kot /kakovost-zraka/ -- ne forkaj klica). NOTRANJIH MERITEV POSTAJE TU NI in
ne smejo priti (CLAUDE.md, pravilo na vrhu).

JS pravila seštevanja (ASTMA_JS_CORE) je namerna podvojitev level_for()/
score_for() -- tools/test_astma.py ju primerja z Node.

Usage:
  python3 tools/generate_astma_page.py
"""
import datetime, html, json, math, os, sys, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
from generate_kakovost_zraka_page import fetch_air_quality, POLLEN_TYPES  # noqa: E402 — ne forkaj klica

TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON
DNEVI = 5
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

LEVELS = ["nizko", "zmerno", "povišano", "visoko"]
LEVEL_COLORS = {"nizko": "#059669", "zmerno": "#eab308", "povišano": "#f97316", "visoko": "#ef4444"}
# Meje skupne ocene (privzete uteži): 0-1 nizko, 2-3 zmerno, 4-5 povišano, >=6 visoko.
SCORE_TH = (2, 4, 6)
# En sam dejavnik z 3 točkami da vsaj »povišano«, tudi če je vsota nizka.
FLOOR_PTS = 3
TRIGGER_WEIGHT = 2

# (ključ, oznaka, kratek opis sprožilca za izbiro)
FACTORS = [
    ("pelod", "Cvetni prah", "cvetni prah (breza, trave, ambrozija …)"),
    ("pm", "Drobni delci PM2,5", "onesnažen zrak, prah"),
    ("ozon", "Ozon", "ozon poleti"),
    ("no2", "Dušikov dioksid", "promet in kurjenje"),
    ("mraz", "Mrzel zrak", "mrzel in suh zrak"),
    ("vrocina", "Vročina", "vročina in soparnost"),
    ("nevihta", "Nevihta", "nevihte"),
    ("sprememba", "Hitra sprememba vremena", "hitre spremembe vremena (temperatura, tlak)"),
    ("vlaga", "Zračna vlaga", "zelo vlažen ali zelo suh zrak"),
]
FACTOR_KEYS = [k for k, _, _ in FACTORS]

# Kratka razlaga za bralca: zakaj je dejavnik pomemben (ne zdravniška trditev).
WHY = {
    "pelod": "Cvetni prah lahko draži dihalne poti, zlasti pri alergijski astmi.",
    "pm": "Drobni delci segajo globoko v pljuča in lahko dražijo dihala.",
    "ozon": "Ozon poleti draži dihala, zlasti ob naporu na prostem.",
    "no2": "Dušikov dioksid nastaja pri prometu in kurjenju ter lahko draži dihala.",
    "mraz": "Mrzel in suh zrak lahko pri nekaterih zoži dihalne poti, predvsem ob naporu.",
    "vrocina": "Vročina in soparnost obremenita dihanje.",
    "nevihta": "Nevihta lahko dvigne cvetni prah in prah; ob cvetenju trav je to nevihtna astma.",
    "sprememba": "Hitre spremembe temperature in tlaka so pri nekaterih znan sprožilec.",
    "vlaga": "Zelo vlažen zrak spodbuja plesni in pršice, zelo suh pa draži sluznico.",
}


def updated_text():
    """Čas izračuna po naši uri: »29. 10. 2026 ob 9.20« (ura s piko, Pravopis § 255)."""
    n = datetime.datetime.now(ZoneInfo("Europe/Ljubljana"))
    return f"{n.day}. {n.month}. {n.year} ob {n.hour}.{n.minute:02d}"


HOURLY_WX = "temperature_2m,apparent_temperature,relative_humidity_2m,pressure_msl,weather_code"


# ── Pravila (točke 0-3) ──────────────────────────────────────────────────────

def pts_by_thresholds(v, ths):
    """ths = (t1, t2, t3): pod t1 -> 0, pod t2 -> 1, pod t3 -> 2, sicer 3."""
    if v is None:
        return 0
    return 0 if v < ths[0] else 1 if v < ths[1] else 2 if v < ths[2] else 3


def pts_pollen(v, th):
    """POLLEN_TYPES pragovi so (nizka|zmerna, zmerna|visoka, visoka|zelo visoka)."""
    if v is None or v < th[0]:
        return 0
    return 1 if v < th[1] else 2 if v < th[2] else 3


def pts_cold(amin):
    if amin is None or amin > 0:
        return 0
    return 1 if amin > -5 else 2 if amin > -10 else 3


def pts_heat(amax):
    return pts_by_thresholds(amax, (28, 32, 35))


def pts_storm(storm, grass_max):
    if not storm:
        return 0
    return 3 if (grass_max is not None and grass_max >= POLLEN_TYPES[0][2][0]) else 1


def pts_change(dtemp, prange):
    t = 0 if dtemp is None else (2 if abs(dtemp) >= 8 else 1 if abs(dtemp) >= 5 else 0)
    p = 0 if prange is None else (2 if prange >= 12 else 1 if prange >= 8 else 0)
    return max(t, p)


def pts_humidity(rh_mean):
    if rh_mean is None:
        return 0
    return 1 if (rh_mean >= 90 or rh_mean < 30) else 0


def score_for(pts, weights=None):
    w = weights or {}
    return sum(pts.get(k, 0) * w.get(k, 1) for k in FACTOR_KEYS)


def level_for(score, max_pts, th=SCORE_TH):
    """max_pts = največ točk enega (uteženega) dejavnika; tla 3 točke = povišano."""
    lvl = 0 if score < th[0] else 1 if score < th[1] else 2 if score < th[2] else 3
    if max_pts >= FLOOR_PTS:
        lvl = max(lvl, 2)
    return LEVELS[lvl]


# JS kopija -- test_astma.py ju poganja na isti mreži vhodov.
ASTMA_JS_CORE = """function astmaScore(pts,w){var s=0;for(var k in pts){s+=pts[k]*(w&&w[k]!=null?w[k]:1);}return s;}
function astmaLevel(pts,w,th,floor,levels){var s=astmaScore(pts,w),m=0;for(var k in pts){if(pts[k]>m)m=pts[k];}
var l=s<th[0]?0:s<th[1]?1:s<th[2]?2:3;if(m>=floor&&l<2)l=2;return levels[l];}"""


# ── Podatki ──────────────────────────────────────────────────────────────────

def fetch_weather():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "hourly": HOURLY_WX,
        "timezone": "Europe/Ljubljana", "past_days": 1, "forecast_days": DNEVI,
    })
    req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{params}",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _by_day(hourly, key):
    out = {}
    for t, v in zip(hourly.get("time") or [], hourly.get(key) or []):
        if v is not None:
            out.setdefault(t[:10], []).append(v)
    return out


def _mean(a):
    return sum(a) / len(a) if a else None


def day_factors(aq, wx, date_iso):
    """Točke in kratek razlog za vsak dejavnik za en dan. Vrne (pts, detail)."""
    ah, wh = aq.get("hourly") or {}, wx.get("hourly") or {}
    g = lambda key: _by_day(ah, key).get(date_iso, [])
    w = lambda key: _by_day(wh, key).get(date_iso, [])
    n = seo.num
    pts, det = {}, {}

    best, best_p = None, 0
    grass_max = max(g("grass_pollen"), default=None)
    for key, lbl, th in POLLEN_TYPES:
        vals = g(key)
        v = max(vals, default=None)
        p = pts_pollen(v, th)
        if p > best_p:
            best_p, best = p, f"{lbl.split(' ', 1)[1].lower()} {n(v, 0)} zrn/m³"
    pts["pelod"], det["pelod"] = best_p, best or "ni pomembnega cvetnega prahu"

    pm = _mean(g("pm2_5"))
    pts["pm"] = pts_by_thresholds(pm, (15, 25, 50))
    det["pm"] = f"PM2,5 povprečno {n(pm, 0)} µg/m³" if pm is not None else "model ne vrača podatka"
    oz = max(g("ozone"), default=None)
    pts["ozon"] = pts_by_thresholds(oz, (100, 120, 180))
    det["ozon"] = f"ozon do {n(oz, 0)} µg/m³" if oz is not None else "model ne vrača podatka"
    no2 = max(g("nitrogen_dioxide"), default=None)
    pts["no2"] = pts_by_thresholds(no2, (100, 200, 400))
    det["no2"] = f"NO₂ do {n(no2, 0)} µg/m³" if no2 is not None else "model ne vrača podatka"

    app = w("apparent_temperature")
    amin, amax = min(app, default=None), max(app, default=None)
    pts["mraz"] = pts_cold(amin)
    det["mraz"] = f"občutena do {n(amin, 0)} °C" if amin is not None else "model ne vrača podatka"
    pts["vrocina"] = pts_heat(amax)
    det["vrocina"] = f"občutena do {n(amax, 0)} °C" if amax is not None else "model ne vrača podatka"

    storm = any(c >= 95 for c in w("weather_code"))
    pts["nevihta"] = pts_storm(storm, grass_max)
    det["nevihta"] = ("nevihta ob cvetenju trav (nevihtna astma)" if pts["nevihta"] == 3
                      else "napovedana nevihta" if storm else "brez neviht")

    prev = (datetime.date.fromisoformat(date_iso) - datetime.timedelta(days=1)).isoformat()
    t_today, t_prev = _mean(w("temperature_2m")), _mean(_by_day(wh, "temperature_2m").get(prev, []))
    dtemp = None if (t_today is None or t_prev is None) else t_today - t_prev
    pr = w("pressure_msl")
    prange = (max(pr) - min(pr)) if pr else None
    pts["sprememba"] = pts_change(dtemp, prange)
    parts = []
    if dtemp is not None and abs(dtemp) >= 5:
        parts.append(f"povprečje {'+' if dtemp > 0 else '−'}{n(abs(dtemp), 0)} °C glede na včeraj")
    if prange is not None and prange >= 8:
        parts.append(f"tlak {n(prange, 0)} hPa v dnevu")
    det["sprememba"] = ", ".join(parts) or "stabilno"

    rh = _mean(w("relative_humidity_2m"))
    pts["vlaga"] = pts_humidity(rh)
    det["vlaga"] = f"vlaga povprečno {n(rh, 0)} %" if rh is not None else "model ne vrača podatka"
    return pts, det


def build_days(aq, wx):
    days = []
    for i in range(DNEVI):
        d = TODAY + datetime.timedelta(days=i)
        iso = d.isoformat()
        pts, det = day_factors(aq, wx, iso)
        score = score_for(pts)
        lvl = level_for(score, max(pts.values()))
        label = "Danes" if i == 0 else "Jutri" if i == 1 else DAN_KRATKO[d.weekday()]
        days.append({"date": iso, "label": label, "pts": pts, "detail": det,
                     "score": score, "level": lvl})
    return days


def reasons(day, k=2):
    """Največ k dejavnikov z najvišjimi točkami (od 1 naprej), z besedilom."""
    ranked = sorted(((p, key) for key, p in day["pts"].items() if p >= 1), reverse=True)
    return [day["detail"][key] for _, key in ranked[:k]]


# ── Izris ────────────────────────────────────────────────────────────────────

PTS_WORD = {0: "—", 1: "blago", 2: "zmerno", 3: "visoko"}

# Skupine dejavnikov = 4 kategorije barv (paleta preverjena z validate_palette.js, dataviz skill:
# slot 1-4, svetlo #2a78d6 #eb6834 #1baf7a #eda100, temno #3987e5 #d95926 #199e70 #c98500).
GROUPS = [
    ("zrak", "Zrak", ["pm", "ozon", "no2"]),
    ("pelod", "Cvetni prah", ["pelod"]),
    ("temp", "Temperatura", ["mraz", "vrocina"]),
    ("vreme", "Vreme", ["nevihta", "sprememba", "vlaga"]),
]
GROUP_OF = {k: g for g, _, ks in GROUPS for k in ks}
GROUP_LABEL = {g: l for g, l, _ in GROUPS}
MAX_BAND = 10  # merilnik in graf: vse nad tem je »visoko«

ICONS = {
    "zrak": '<path d="M3 8h10a3 3 0 1 0-3-3M3 12h14a3 3 0 1 1-3 3M3 16h6"/>',
    "pelod": '<circle cx="12" cy="12" r="2.5"/><path d="M12 9.5V5a2.5 2.5 0 0 1 5 0c0 2-2.5 4.5-5 4.5zM14.5 12H19a2.5 2.5 0 0 1 0 5c-2 0-4.5-2.5-4.5-5zM12 14.5V19a2.5 2.5 0 0 1-5 0c0-2 2.5-4.5 5-4.5zM9.5 12H5a2.5 2.5 0 0 1 0-5c2 0 4.5 2.5 4.5 5z" transform="scale(.9) translate(1.3 1.3)"/>',
    "temp": '<path d="M10 4a2 2 0 0 1 4 0v9.2a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>',
    "vreme": '<path d="M7 17a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 8.5a3.5 3.5 0 0 1 .5 7"/><path d="M12 12l-2 4h3l-2 4"/>',
}


def icon(group, size=18):
    return (f'<svg class="as-ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[group]}</svg>')


CSS = """<style>
.as-viz{--as-surface:#0e1624;--as-ink:var(--text,#e8edf5);--as-ink2:var(--muted,#9aa7bb);--as-grid:rgba(255,255,255,.1);
  --g-zrak:#3987e5;--g-pelod:#d95926;--g-temp:#199e70;--g-vreme:#c98500;
  --l-nizko:#059669;--l-zmerno:#eab308;--l-povisano:#f97316;--l-visoko:#ef4444}
[data-theme="light"] .as-viz{--as-surface:#ffffff;--as-grid:rgba(0,0,0,.12);
  --g-zrak:#2a78d6;--g-pelod:#eb6834;--g-temp:#1baf7a;--g-vreme:#eda100}
.as-hero{display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:1.4rem;align-items:center;margin:1rem 0 1.6rem;
  padding:1.2rem 1.3rem;border:1px solid var(--as-grid);border-radius:16px;
  background:radial-gradient(120% 140% at 0% 0%,color-mix(in srgb,var(--c,#059669) 18%,transparent),transparent 60%),var(--as-surface)}
.as-gauge{width:100%;height:auto;display:block}
.as-gauge .as-needle{transform-origin:110px 110px;transition:transform .8s cubic-bezier(.2,.8,.2,1)}
.as-hero-k{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--as-ink2)}
.as-hero-l{font-size:2.3rem;font-weight:800;line-height:1.1;color:var(--c,#059669);margin:.1rem 0 .3rem}
.as-hero-adv{margin:.6rem 0 0;font-size:.92rem;color:var(--as-ink)}
.as-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem}
.as-chip{display:inline-flex;align-items:center;gap:.35rem;padding:.3rem .65rem;border-radius:999px;font-size:.8rem;
  border:1px solid var(--as-grid);color:var(--as-ink)}
.as-chip .as-ic{color:var(--gc)}
.as-days{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.6rem;margin:1rem 0 1.4rem}
.as-day{border:1px solid var(--as-grid);border-top:4px solid var(--c,#059669);border-radius:12px;padding:.75rem .85rem;background:var(--as-surface)}
.as-day h3{margin:0;font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--as-ink2)}
.as-day .as-lvl{font-size:1.25rem;font-weight:800;color:var(--c,#059669);margin:.15rem 0}
.as-day .as-sc{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--as-ink2)}
.as-day ul{margin:.5rem 0 0;padding-left:1rem;font-size:.8rem}
.as-card{border:1px solid var(--as-grid);border-radius:14px;padding:1rem 1.1rem;background:var(--as-surface);margin:1rem 0 1.6rem}
.as-svg{width:100%;height:auto;display:block}
.as-svg text{font-family:inherit}
.as-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.6rem;font-size:.8rem;color:var(--as-ink2)}
.as-legend span{display:inline-flex;align-items:center;gap:.35rem}
.as-legend i{width:10px;height:10px;border-radius:2px;background:var(--gc);display:inline-block}
.as-prof{display:grid;gap:.45rem}
.as-row{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:.8rem;align-items:center;font-size:.85rem}
.as-row .as-name{display:flex;align-items:center;gap:.4rem;color:var(--as-ink)}
.as-row .as-name .as-ic{color:var(--gc)}
.as-track{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;margin-bottom:.15rem}
.as-track i{height:10px;border-radius:3px;background:var(--as-grid)}
.as-track i.on{background:var(--gc)}
.as-det{font-size:.76rem;color:var(--as-ink2)}
.as-heat td{text-align:center;font-weight:700}
.as-heat .as-g{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:.4rem;background:var(--gc)}
.as-today{box-shadow:0 0 0 2px var(--c,#059669)}
.as-hero-sum{margin:.2rem 0 0;font-size:1rem;color:var(--as-ink)}
.as-hero-meta{margin:.7rem 0 0;font-size:.76rem;color:var(--as-ink2)}
.as-hero-meta a{color:inherit;text-decoration:underline}
.as-grp{margin-bottom:1rem}
.as-grp h3{display:flex;align-items:center;gap:.45rem;margin:.2rem 0 .5rem;font-size:.95rem;color:var(--as-ink)}
.as-grp h3 .as-ic{color:var(--gc)}
.as-why{font-size:.76rem;color:var(--as-ink2);margin-top:.1rem;opacity:.9}
.as-none{color:var(--as-ink2);font-weight:400!important;font-size:.78rem}
.as-reasons{margin:.6rem 0 1rem;font-size:.86rem}
.as-reasons ul{margin:.5rem 0 0;padding-left:1.1rem}
.as-actions{display:flex;flex-wrap:wrap;gap:.6rem;margin:.4rem 0}
.as-btn{min-height:44px;padding:.5rem 1rem;border-radius:8px;border:1px solid var(--as-grid);background:transparent;color:var(--as-ink);font:inherit;cursor:pointer}
.as-btn-p{background:var(--g-zrak);border-color:var(--g-zrak);color:#fff;font-weight:700}
.as-status{font-size:.88rem;color:var(--as-ink);margin:.4rem 0}
.as-trig{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.as-trig label{display:flex;align-items:center;gap:.4rem;padding:.45rem .7rem;border:1px solid var(--as-grid);border-radius:8px;cursor:pointer;min-height:44px;font-size:.88rem}
.as-trig input{width:18px;height:18px}
@media (max-width:640px){.as-days{grid-template-columns:repeat(2,minmax(0,1fr))}.as-hero{grid-template-columns:1fr}.as-hero-l{font-size:1.9rem}.as-row{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){.as-gauge .as-needle{transition:none}}
</style>"""


def esc(s):
    return html.escape(str(s))


def _pt(cx, cy, r, d):
    """Točka na loku; d = 0..180 stopinj od leve proti desni čez vrh."""
    rad = math.radians(d)
    return cx - r * math.cos(rad), cy - r * math.sin(rad)


def gauge_deg(score):
    return 180 * min(max(score, 0), MAX_BAND) / MAX_BAND


def gauge_svg(day):
    """Polkrožni merilnik: štirje loki (ravni nizko…visoko) in kazalec na današnji oceni."""
    cx = cy = 110
    r = 88
    bounds = [0, SCORE_TH[0], SCORE_TH[1], SCORE_TH[2], MAX_BAND]
    arcs = []
    for i, lvl in enumerate(LEVELS):
        d1, d2 = gauge_deg(bounds[i]) + 1.2, gauge_deg(bounds[i + 1]) - 1.2
        x1, y1 = _pt(cx, cy, r, d1)
        x2, y2 = _pt(cx, cy, r, d2)
        arcs.append(f'<path d="M{x1:.1f} {y1:.1f}A{r} {r} 0 0 1 {x2:.1f} {y2:.1f}" fill="none" '
                    f'stroke="var(--l-{lvl.replace("š", "s").replace("č", "c")})" stroke-width="16" stroke-linecap="butt"/>')
    ticks = "".join(
        f'<text x="{_pt(cx, cy, r + 17, gauge_deg(b))[0]:.1f}" y="{_pt(cx, cy, r + 17, gauge_deg(b))[1] + 3:.1f}" '
        f'text-anchor="middle" font-size="9" fill="var(--as-ink2)">{b}{"+" if b == MAX_BAND else ""}</text>'
        for b in bounds)
    deg = gauge_deg(day["score"])
    return (f'<svg class="as-gauge" viewBox="0 0 220 138" role="img" aria-label="Merilnik: obremenitev {day["score"]} točk, raven {day["level"]}">'
            + "".join(arcs) + ticks +
            f'<g class="as-needle" id="as-needle" style="transform:rotate({deg:.1f}deg)">'
            f'<path d="M{cx - 70} {cy}L{cx} {cy - 3.5}L{cx} {cy + 3.5}z" fill="var(--as-ink)"/></g>'
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="var(--as-ink)"/><circle cx="{cx}" cy="{cy}" r="3" fill="var(--as-surface)"/>'
            f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="12" fill="var(--as-ink2)" id="as-gauge-sc">obremenitev {day["score"]}</text></svg>')


def lvl_var(level):
    return f'var(--l-{level.replace("š", "s").replace("č", "c")})'


def hero_summary(day):
    rs = reasons(day, 2)
    if not rs:
        return "Danes vreme in zrak nista izrazit sprožilec."
    return "Danes obremenjuje predvsem: " + "; ".join(rs) + "."


def hero_html(days):
    d = days[0]
    rs = sorted(((p, k) for k, p in d["pts"].items() if p >= 1), reverse=True)[:3]
    chips = "".join(
        f'<span class="as-chip" style="--gc:var(--g-{GROUP_OF[k]})">{icon(GROUP_OF[k], 16)}{esc(d["detail"][k])}</span>'
        for _, k in rs) or '<span class="as-chip">brez izrazitih sprožilcev</span>'
    return (f'  <div class="as-hero" id="as-hero" style="--c:{lvl_var(d["level"])}">\n'
            f'    {gauge_svg(d)}\n'
            f'    <div><div class="as-hero-k">Okoljska obremenitev danes · Zgornja Savinjska dolina</div>'
            f'<div class="as-hero-l" id="as-hero-l">{d["level"]}</div>'
            f'<p class="as-hero-sum">{esc(hero_summary(d))}</p>'
            f'<div class="as-chips" id="as-chips">{chips}</div>'
            f'<p class="as-hero-adv">{esc(level_advice(d["level"]))}</p>'
            f'<p class="as-hero-meta">Izračunano {esc(updated_text())} · modelska napoved, ne meritev · '
            f'<a href="#metodologija">kako je ocena izračunana</a></p></div>\n  </div>')


def days_summary(days):
    """En stavek namesto ponavljanja enakih ocen."""
    levels = {d["level"] for d in days}
    if len(levels) == 1:
        return f"Vseh {len(days)} dni je raven enaka: {days[0]['level']}."
    worst = max(days, key=lambda d: (d["score"], -days.index(d)))
    best = min(days, key=lambda d: (d["score"], days.index(d)))
    return (f"Najbolj obremenjujoč je {worst['label'].lower()} ({worst['level']}), "
            f"najugodnejši {best['label'].lower()} ({best['level']}).")


def day_cards_html(days):
    out = []
    for i, d in enumerate(days):
        rs = reasons(d)
        li = "".join(f"<li>{esc(r)}</li>" for r in rs) or "<li>brez izrazitih sprožilcev</li>"
        cls = "as-day as-today" if i == 0 else "as-day"
        out.append(f'    <div class="{cls}" style="--c:{lvl_var(d["level"])}" data-i="{i}">'
                   f'<h3>{esc(d["label"])}</h3><div class="as-lvl">{d["level"]}</div>'
                   f'<div class="as-sc">obremenitev {d["score"]} točk</div><ul>{li}</ul></div>')
    return '  <div class="as-days" id="as-days">\n' + "\n".join(out) + "\n  </div>"


def reasons_by_day_html(days):
    """Razlogi kot vidno besedilo: deluje s tipkovnico in na dotik (ne le ob pomiku miške)."""
    items = []
    for d in days:
        rs = [f'{dict((k2, l2) for k2, l2, _ in FACTORS)[k]}: {d["detail"][k]}'
              for k, p in sorted(d["pts"].items(), key=lambda kv: -kv[1]) if p >= 1]
        items.append(f'<li><strong>{esc(d["label"])}</strong> ({d["level"]}): '
                     f'{esc("; ".join(rs) if rs else "brez izrazitih sprožilcev")}</li>')
    return ('  <details class="as-reasons"><summary>Razlogi po dnevih (besedilo)</summary><ul>'
            + "".join(items) + '</ul></details>')


def legend_html():
    return '<div class="as-legend">' + "".join(
        f'<span style="--gc:var(--g-{g})"><i></i>{icon(g, 14)}{esc(l)}</span>' for g, l, _ in GROUPS) + "</div>"


def stacked_chart_svg(days):
    """Naloženi stolpci: skupna ocena dneva, razrezana po skupinah dejavnikov, na ozadju ravni.
    Dnevi so ločeni, med segmenti 2 px rež; skupna ocena je napisana nad stolpcem."""
    W, H = 640, 270
    pl, pr, pt, pb = 34, 74, 14, 30
    pw, ph = W - pl - pr, H - pt - pb
    top = max(MAX_BAND, max(d["score"] for d in days) + 1)
    y = lambda v: pt + ph * (1 - v / top)
    bounds = [0, SCORE_TH[0], SCORE_TH[1], SCORE_TH[2], top]
    out = [f'<svg class="as-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Skupna ocena po dnevih, razrezana po skupinah dejavnikov">']
    for i, lvl in enumerate(LEVELS):
        y0, y1 = y(bounds[i + 1]), y(bounds[i])
        out.append(f'<rect x="{pl}" y="{y0:.1f}" width="{pw}" height="{y1 - y0:.1f}" fill="{lvl_var(lvl)}" opacity=".09"/>')
        out.append(f'<text x="{W - pr + 8}" y="{(y0 + y1) / 2 + 3:.1f}" font-size="10" fill="var(--as-ink2)">{lvl}</text>')
    for v in range(0, int(top) + 1, 2):
        out.append(f'<line x1="{pl}" x2="{pl + pw}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--as-grid)" stroke-width="1"/>')
        out.append(f'<text x="{pl - 6}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="10" fill="var(--as-ink2)">{v}</text>')
    n = len(days)
    slot = pw / n
    bw = slot * 0.5
    for i, d in enumerate(days):
        x = pl + slot * i + (slot - bw) / 2
        acc = 0
        for g, lbl, keys in GROUPS:
            v = sum(d["pts"][k] for k in keys)
            if v == 0:
                continue
            y_top, y_bot = y(acc + v), y(acc)
            tip = f'{d["label"]} · {lbl}: {v} točk' + "".join(
                f' · {dict((k2, l2) for k2, l2, _ in FACTORS)[k]}: {d["detail"][k]}' for k in keys if d["pts"][k])
            out.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bw:.1f}" height="{max(y_bot - y_top, 0):.1f}" rx="3" '
                       f'fill="var(--g-{g})" stroke="var(--as-surface)" stroke-width="2"><title>{esc(tip)}</title></rect>')
            acc += v
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y(acc) - 6:.1f}" text-anchor="middle" font-size="12" font-weight="700" '
                   f'fill="var(--as-ink)">{acc}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{H - 10}" text-anchor="middle" font-size="11" fill="var(--as-ink2)">{esc(d["label"])}</text>')
    out.append("</svg>")
    return "".join(out)


def stacked_block(days):
    return ('  <div class="as-card">\n    ' + stacked_chart_svg(days) + "\n    " + legend_html() +
            '\n    <p class="muted-note">Graf prikazuje privzeto oceno brez osebnih sprožilcev. Pomik nad stolpec pokaže razloge.</p>\n  </div>')


def profile_html(day):
    """Današnji profil po skupinah: stopnja, vrednost in kratek razlog, zakaj je dejavnik pomemben.
    Vse vrednosti so modelske napovedi (CAMS, Open-Meteo), ne meritve."""
    blocks = []
    for g, glabel, keys in GROUPS:
        rows = []
        for key in keys:
            lbl = dict((k, l) for k, l, _ in FACTORS)[key]
            p = day["pts"][key]
            track = "".join(f'<i class="{"on" if j < p else ""}"></i>' for j in range(3))
            word = PTS_WORD[p] if p else "ni vpliva"
            rows.append(f'      <div class="as-row"><div class="as-name">{esc(lbl)}</div>'
                        f'<div><div class="as-track" role="img" aria-label="{esc(lbl)}: {word}">{track}</div>'
                        f'<div class="as-det"><strong>{word}</strong> · {esc(day["detail"][key])} (modelska napoved)</div>'
                        f'<div class="as-why">{esc(WHY[key])}</div></div></div>')
        blocks.append(f'    <div class="as-grp" style="--gc:var(--g-{g})"><h3>{icon(g, 18)}{esc(glabel)}</h3>\n'
                      + "\n".join(rows) + "\n    </div>")
    return '  <div class="as-card"><div class="as-prof">\n' + "\n".join(blocks) + "\n  </div></div>"


def heatmap_html(days):
    head = "<th></th>" + "".join(f"<th>{esc(d['label'])}</th>" for d in days)
    alpha = {1: .35, 2: .65, 3: 1.0}
    rows = []
    for key, lbl, _ in FACTORS:
        g = GROUP_OF[key]
        cells = []
        for d in days:
            p = d["pts"][key]
            if p == 0:
                cells.append('<td class="as-none">ni vpliva</td>')
            else:
                cells.append(f'<td title="{esc(d["detail"][key])}" style="background:color-mix(in srgb,var(--g-{g}) {int(alpha[p] * 100)}%,transparent);'
                             f'color:{"#04070e" if p == 3 else "inherit"}">{PTS_WORD[p]}</td>')
        rows.append(f'<tr style="--gc:var(--g-{g})"><th><span class="as-g"></span>{esc(lbl)}</th>{"".join(cells)}</tr>')
    return ('  <div class="table-scroll" tabindex="0"><table class="stats as-heat">\n'
            f'    <tr>{head}</tr>\n    ' + "\n    ".join(rows) + "\n  </table></div>")


def triggers_html():
    boxes = "".join(
        f'<label><input type="checkbox" value="{k}"> {esc(desc)}</label>' for k, _, desc in FACTORS)
    return (f'  <div class="as-trig" id="as-trig" role="group" aria-label="Moji sprožilci">{boxes}</div>\n'
            '  <div class="as-actions"><button type="button" class="as-btn as-btn-p" id="as-apply">Uporabi moje sprožilce</button>'
            '<button type="button" class="as-btn" id="as-reset">Ponastavi</button></div>\n'
            '  <p class="as-status" id="as-trig-status" role="status" aria-live="polite">Brez osebnih sprožilcev: vsi dejavniki štejejo enako.</p>\n'
            '  <p class="muted-note">Izbira se shrani samo v tem brskalniku in se nikamor ne pošlje. Ista okoljska situacija ne vpliva enako na vse ljudi.</p>')


def client_js(days):
    payload = {
        "days": [{"label": d["label"], "pts": d["pts"], "detail": d["detail"]} for d in days],
        "th": list(SCORE_TH), "floor": FLOOR_PTS, "levels": LEVELS,
        "colors": {k: v for k, v in LEVEL_COLORS.items()}, "names": {k: l for k, l, _ in FACTORS}, "max": MAX_BAND, "weight": TRIGGER_WEIGHT, "keys": FACTOR_KEYS,
    }
    return ("<script>\n(function(){\n" + ASTMA_JS_CORE + "\n"
            "var D=" + json.dumps(payload, ensure_ascii=False) + ",KEY='wx-astma-sprozilci';\n"
            """function load(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')||[];}catch(e){return [];}}
function save(a){try{localStorage.setItem(KEY,JSON.stringify(a));}catch(e){}}
function weights(sel){var w={};if(sel.length){sel.forEach(function(k){w[k]=D.weight;});}return w;}
function render(sel){
  var w=weights(sel),el=document.getElementById('as-days');if(!el)return;
  var cards=el.querySelectorAll('.as-day');
  D.days.forEach(function(d,i){var c=cards[i];if(!c)return;
    var lvl=astmaLevel(d.pts,w,D.th,D.floor,D.levels),sc=astmaScore(d.pts,w);
    c.style.setProperty('--c',D.colors[lvl]);
    c.querySelector('.as-lvl').textContent=lvl;
    c.querySelector('.as-sc').textContent='obremenitev '+sc+' točk'+(sel.length?' (z mojimi sprožilci)':'');
    var r=Object.keys(d.pts).filter(function(k){return d.pts[k]>0;})
      .sort(function(a,b){return (d.pts[b]*(w[b]||1))-(d.pts[a]*(w[a]||1));}).slice(0,2)
      .map(function(k){return d.detail[k];});
    var ul=c.querySelector('ul');ul.textContent='';
    (r.length?r:['brez izrazitih sprožilcev']).forEach(function(t){var li=document.createElement('li');li.textContent=t;ul.appendChild(li);});
  });
}
function hero(sel){var w=weights(sel),d=D.days[0],lvl=astmaLevel(d.pts,w,D.th,D.floor,D.levels),sc=astmaScore(d.pts,w);
  var h=document.getElementById('as-hero');if(!h)return;h.style.setProperty('--c',D.colors[lvl]);
  document.getElementById('as-hero-l').textContent=lvl;
  var n=document.getElementById('as-needle');if(n)n.style.transform='rotate('+(180*Math.min(sc,D.max)/D.max)+'deg)';
  var t=document.getElementById('as-gauge-sc');if(t)t.textContent='obremenitev '+sc;}
var boxes=document.querySelectorAll('#as-trig input'),sel=load(),st=document.getElementById('as-trig-status');
var NAMES=D.names;
function status(){if(!st)return;st.textContent=sel.length?'Uporabljeni sprožilci (štejejo dvojno): '+sel.map(function(k){return NAMES[k];}).join(', ')+'.':'Brez osebnih sprožilcev: vsi dejavniki štejejo enako.';}
function checked(){return [].filter.call(boxes,function(x){return x.checked;}).map(function(x){return x.value;});}
boxes.forEach(function(b){b.checked=sel.indexOf(b.value)>=0;});
var ap=document.getElementById('as-apply'),rs=document.getElementById('as-reset');
if(ap)ap.addEventListener('click',function(){sel=checked();save(sel);render(sel);hero(sel);status();});
if(rs)rs.addEventListener('click',function(){boxes.forEach(function(b){b.checked=false;});sel=[];save(sel);render(sel);hero(sel);status();});
if(sel.length){render(sel);hero(sel);}status();
})();
</script>""")


FAQ = [
    ("Kako je izračunana ocena?",
     "Za vsak dan seštejemo točke (0–3) devetih dejavnikov: cvetni prah, PM2,5, ozon, NO₂, mrzel zrak, vročina, nevihta, "
     "hitra sprememba vremena in vlaga. Ocena 0–1 je nizko, 2–3 zmerno, 4–5 povišano, 6 ali več visoko; en sam dejavnik s "
     "tremi točkami da vsaj povišano. Pragovi so naša delitev po znanih sprožilcih in niso klinična lestvica."),
    ("Je ocena verjetnost astmatičnega napada?",
     "Ne. Je pregled sprožilcev, ki jih napovedujeta vreme in zrak. Kako se posameznik odzove, je zelo različno in "
     "odvisno od zdravljenja, zato ocene ne uporabljajte za odločanje o zdravilih."),
    ("Kaj je nevihtna astma?",
     "Redek pojav, ko nevihta v času cvetenja trav v zrak dvigne drobne delce cvetnega prahu in jih tudi ljudje brez znane "
     "astme vdihnejo globlje. Stran ga označi samo, kadar sta napovedana hkrati nevihta in cvetenje trav."),
    ("Zakaj mrzel zrak in vročina?",
     "Mrzel in suh zrak lahko pri nekaterih zoži dihalne poti, zlasti ob naporu; vročina in soparnost obremenita dihanje, "
     "poleti pa ju spremlja še ozon. Zato se pri teh dejavnikih upošteva občutena temperatura."),
    ("Ali stran shranjuje moje podatke?",
     "Ne. Izbira sprožilcev ostane v vašem brskalniku (localStorage) in se ne pošlje na strežnik. Strani ne vodita ne računa "
     "ne dnevnika simptomov."),
]


def level_advice(level):
    return {
        "nizko": "Vreme in zrak niso izrazit sprožilec. Ravnajte po svojem načrtu zdravljenja.",
        "zmerno": "Občutljivejši naj bodo pozorni na simptome; zdravilo za lajšanje naj bo pri roki, kot ga je predpisal zdravnik.",
        "povišano": "Za občutljive je to dan z več sprožilci. Naporne dejavnosti na prostem razmislite premakniti na boljši čas dneva; ravnajte po načrtu, ki ste ga dobili pri zdravniku.",
        "visoko": "Več sprožilcev hkrati. Naporne dejavnosti na prostem odložite, zdravilo naj bo pri roki, ob poslabšanju ravnajte po načrtu zdravljenja ali pokličite zdravnika (nujna pomoč: 112).",
    }[level]


def build_body(days):
    today = days[0]
    rs = reasons(today, 3)
    why = (" Glavni razlogi: " + "; ".join(rs) + ".") if rs else " Danes ni izrazitih sprožilcev."
    answer = (f'  <p class="archive-intro" id="as-answer"><strong>Kako vreme in kakovost zraka vplivata na astmo?</strong> '
              f'Cvetni prah, drobni delci, ozon, mraz, vročina, nevihte in hitre spremembe vremena so pri nekaterih ljudeh znani sprožilci. '
              f'Ocena obremenitve zaradi okoljskih sprožilcev v Rečici ob Savinji in Zgornji Savinjski dolini je danes '
              f'<strong>{today["level"]}</strong> ({today["score"]} točk od največ 27).{esc(why)}</p>')

    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f"    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in FAQ) + "\n  </div>"

    rules = [
        ("Cvetni prah", "najvišja vrsta; pragovi kot na /kakovost-zraka/", "blago od nizke, visoko ≥ zelo visoke"),
        ("PM2,5 (dnevno povprečje)", "15 / 25 / 50 µg/m³", "WHO / EU dnevna meja"),
        ("Ozon (urni najvišji)", "100 / 120 / 180 µg/m³", "120 = ciljna vrednost EU, 180 = opozorilni prag"),
        ("NO₂ (urni najvišji)", "100 / 200 / 400 µg/m³", "200 = urna meja EU"),
        ("Mrzel zrak (najnižja občutena)", "≤ 0 / ≤ −5 / ≤ −10 °C", "občutena temperatura"),
        ("Vročina (najvišja občutena)", "≥ 28 / 32 / 35 °C", "občutena temperatura"),
        ("Nevihta", "1 točka; 3 ob cvetenju trav", "nevihtna astma"),
        ("Hitra sprememba", "povprečje ±5 / ±8 °C ali tlak ≥ 8 / 12 hPa", "glede na prejšnji dan"),
        ("Zračna vlaga", "1 točka pri ≥ 90 % ali < 30 %", "dnevno povprečje"),
    ]
    rule_rows = "\n".join(f"    <tr><th>{esc(a)}</th><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rules)

    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Vreme in astma", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Vreme in astma: napoved okoljskih sprožilcev za 5 dni</h1>
  <p class="post-meta">Okoljski sprožilci za astmo · Rečica ob Savinji in Zgornja Savinjska dolina · izračunano {esc(updated_text())}</p>
<div class="as-viz">
{hero_html(days)}
  <p class="muted-note"><strong>To ni zdravniški nasvet.</strong> Ocena prikazuje okoljske sprožilce, ki jih napovedujeta vreme in zrak,
  in ne verjetnosti astmatičnega napada ali nadomestila za osebni načrt zdravljenja. Za zdravljenje in ukrepe veljajo navodila vašega
  zdravnika; v nujnem primeru pokličite 112.</p>
  <h2>Naslednjih 5 dni</h2>
  <p class="archive-intro">{esc(days_summary(days))} Raven je vedno zapisana tudi z besedo.</p>
{day_cards_html(days)}
  <h2>Moji sprožilci</h2>
  <p class="archive-intro">Označite, kaj občutite pri sebi, in pritisnite »Uporabi moje sprožilce«. Izbrani dejavniki bodo pri oceni šteli dvojno.</p>
{triggers_html()}
  <h2>Skupna obremenitev po dnevih</h2>
{stacked_block(days)}
{reasons_by_day_html(days)}
  <h2>Danes po dejavnikih</h2>
  <p class="archive-intro">Dejavniki so razvrščeni v skupine. Vsak ima tri stopnje (blago, zmerno, visoko), vrednost in razlog, zakaj je pomemben.</p>
{profile_html(days[0])}
  <h2>Vsi dnevi in dejavniki</h2>
  <p class="archive-intro">Najvišji dnevni vpliv posameznega dejavnika. Razlogi so zapisani tudi v besedilu zgoraj.</p>
{heatmap_html(days)}
  <h2 id="metodologija">Kako je ocena sestavljena</h2>
  <p class="archive-intro">Gre za informativni model, ki sešteje točke devetih dejavnikov (0–3 na dejavnik, skupaj največ 27). Točkovanje in pragovi so naša
  delitev po splošno znanih sprožilcih, ne klinična lestvica.</p>
  <table class="stats">
    <tr><th>Dejavnik</th><td>Pragovi (blago / zmerno / visoko)</td><td>Opomba</td></tr>
{rule_rows}
  </table>
  <ul class="as-lim">
    <li><strong>Modelske napovedi, ne meritve:</strong> zrak in cvetni prah prihajata iz modela Copernicus CAMS Europe, vreme iz Open-Meteo. Postaja Meteorec teh dejavnikov ne meri.</li>
    <li><strong>Prostorska ločljivost:</strong> mreža modela je približno 10 km, zato ne razloči dolin, ceste ob hiši ali lokalnih virov kurjenja.</li>
    <li><strong>Čas:</strong> stran se izračuna enkrat na dan ({esc(updated_text())}); urne vrednosti se čez dan lahko spremenijo.</li>
    <li><strong>Ni enako za vse:</strong> ista okoljska situacija ne vpliva enako na vse ljudi; ocena je zato le izhodišče, ne napoved vašega počutja.</li>
  </ul>
  <p class="muted-note">Podatki: Copernicus CAMS Europe (zrak, cvetni prah) in Open-Meteo (temperatura, vlaga, tlak, nevihte).</p>
{faq_html}
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">Povezave</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="/kakovost-zraka/" class="mtn-avk-link">Kakovost zraka in cvetni prah →</a>
      <a href="/biovreme/" class="mtn-avk-link">Biovreme →</a>
      <a href="/migrena/" class="mtn-avk-link">Vreme in migrena →</a>
      <a href="/susenje-perila/" class="mtn-avk-link">Sušenje perila →</a>
      <a href="/vreme-za-kolesarje/" class="mtn-avk-link">Vreme za kolesarje →</a>
      <a href="/vreme-za-pse/" class="mtn-avk-link">Vreme za sprehod s psom →</a>
      <a href="https://www.arso.gov.si/zrak/" target="_blank" rel="noopener" class="mtn-avk-link">ARSO — kakovost zraka</a>
      <a href="https://www.nlzoh.si/" target="_blank" rel="noopener" class="mtn-avk-link">NLZOH — cvetni prah</a>
      <a href="https://www.nijz.si/" target="_blank" rel="noopener" class="mtn-avk-link">NIJZ</a>
    </div>
  </div>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
</div>
{client_js(days)}'''


def main():
    print(f"[{TODAY}] Pridobivam zrak in vreme za astmo …")
    try:
        aq = fetch_air_quality()
        wx = fetch_weather()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        sys.exit(1)

    days = build_days(aq, wx)
    if not any(sum(d["pts"].values()) or d["detail"]["pm"] != "model ne vrača podatka" for d in days):
        print("✗ Podatkov ni (vsi dnevi brez vrednosti)", file=sys.stderr)
        sys.exit(1)

    url = "/astma/"
    title = "Vreme in astma: napoved okoljskih sprožilcev za 5 dni"
    t = days[0]
    desc = (f"Okoljska obremenitev za ljudi z astmo danes: {t['level']}. Pelod, PM2,5, ozon, mraz, vročina, nevihte in hitre "
            f"spremembe vremena za 5 dni v Rečici ob Savinji in Zgornji Savinjski dolini.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-10-29"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme in astma", None)]),
        seo.faq_schema(FAQ),
    ]) + "\n" + CSS
    page = seo.page_shell(title, desc, url, schema, build_body(days))
    seo.write_page("astma/index.html", page, force=True)
    print(f"  → astma/index.html (danes {t['level']}, {t['score']} točk)")


if __name__ == "__main__":
    main()
