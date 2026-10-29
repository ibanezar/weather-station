#!/usr/bin/env python3
"""
tools/day_score_common.py — skupni pogon za strani »vreme za …« (5 dni, ocena po dnevih)

Strani: /susenje-perila/, /vreme-za-kolesarje/, /vreme-za-cebelarje/, /vreme-za-ribolov/,
/vreme-za-pse/ (generate_*_page.py). Vsaka stran je samo KONFIGURACIJA (dejavniki, pragovi,
besedila); točkovanje, grafika in sestavljanje strani so tu — po zgledu atmos_common.py.

Načelo (isto kot /astma/): točke slabosti 0-3 na dejavnik na dan, skupaj vsota; ravni so
štiri (indeks 0 = najboljša). En dejavnik s 3 točkami da vsaj raven 2 (»veto«). Modelska
napoved Open-Meteo za Rečico ob Savinji; NOTRANJIH MERITEV POSTAJE TU NI IN NE SMEJO PRITI
(CLAUDE.md, pravilo na vrhu). Samo strežniški izris, brez JS.

Barve skupin: prvi trije/štirje sloti preverjene palete (dataviz skill, validate_palette.js):
svetlo #2a78d6 #eb6834 #1baf7a #eda100, temno #3987e5 #d95926 #199e70 #c98500.
"""
import datetime, html, json, math, os, sys, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

LAT, LON = seo.LAT, seo.LON
DNEVI = 5
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
DAN_PUN = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
LEVEL_COLORS = ["#059669", "#eab308", "#f97316", "#ef4444"]
PTS_WORD = {0: "ni ovire", 1: "blago", 2: "zmerno", 3: "izrazito"}
FLOOR_PTS = 3
FLOOR_LEVEL = 2
COMPASS = ["S", "SV", "V", "JV", "J", "JZ", "Z", "SZ"]

HOURLY_VARS = ("temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,wind_speed_10m,"
               "wind_gusts_10m,wind_direction_10m,precipitation,precipitation_probability,weather_code,"
               "pressure_msl,shortwave_radiation,uv_index,cloud_cover")

ICONS = {
    "a": '<path d="M3 8h10a3 3 0 1 0-3-3M3 12h14a3 3 0 1 1-3 3M3 16h6"/>',
    "b": '<path d="M7 17a4 4 0 0 1-.5-8A5.5 5.5 0 0 1 17 8.5a3.5 3.5 0 0 1 .5 7"/><path d="M9 20l1-2M13 20l1-2"/>',
    "c": '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
    "d": '<path d="M10 4a2 2 0 0 1 4 0v9.2a4 4 0 1 1-4 0z"/><path d="M12 9v7"/>',
}


# ── Pomočniki za točke ───────────────────────────────────────────────────────

def bands(v, ths):
    """Višje = slabše: pod t0 -> 0, pod t1 -> 1, pod t2 -> 2, sicer 3. Brez podatka = 0."""
    if v is None:
        return 0
    return 0 if v < ths[0] else 1 if v < ths[1] else 2 if v < ths[2] else 3


def bands_desc(v, ths):
    """Nižje = slabše: >= t0 -> 0, >= t1 -> 1, >= t2 -> 2, sicer 3."""
    if v is None:
        return 0
    return 0 if v >= ths[0] else 1 if v >= ths[1] else 2 if v >= ths[2] else 3


def tocke(n):
    """Slovenski sklon: 1 točka, 2 točki, 3–4 točke, ostalo točk."""
    n = int(n)
    r = n % 100
    return f"{n} " + ("točka" if r == 1 else "točki" if r == 2 else "točke" if r in (3, 4) else "točk")


def mean(a):
    return sum(a) / len(a) if a else None


def compass(deg):
    return COMPASS[int((deg % 360) / 45 + 0.5) % 8]


def mean_dir(degs, speeds):
    """Prevladujoča smer: vektorsko povprečje, uteženo s hitrostjo."""
    x = sum(s * math.sin(math.radians(d)) for d, s in zip(degs, speeds))
    y = sum(s * math.cos(math.radians(d)) for d, s in zip(degs, speeds))
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return None
    return math.degrees(math.atan2(x, y)) % 360


# JS kopija level_index()/score_for() za strani z osebnimi sprožilci (test_migrena.py ju primerja z Nodom).
JS_CORE = """function dvScore(pts,w){var s=0;for(var k in pts){s+=pts[k]*(w&&w[k]!=null?w[k]:1);}return s;}
function dvLevel(pts,w,th,floor,floorLevel){var s=dvScore(pts,w),m=0;for(var k in pts){if(pts[k]>m)m=pts[k];}
var l=s<th[0]?0:s<th[1]?1:s<th[2]?2:3;if(m>=floor&&l<floorLevel)l=floorLevel;return l;}"""


def score_for(pts):
    return sum(pts.values())


def level_index(score, max_pts, th):
    lvl = 0 if score < th[0] else 1 if score < th[1] else 2 if score < th[2] else 3
    if max_pts >= FLOOR_PTS:
        lvl = max(lvl, FLOOR_LEVEL)
    return lvl


class Ctx:
    """Urni podatki Open-Meteo, indeksirani po datumu."""

    def __init__(self, hourly):
        self.h = hourly or {}
        self.times = self.h.get("time") or []
        self.by_date = {}
        for i, t in enumerate(self.times):
            self.by_date.setdefault(t[:10], []).append(i)

    def vals(self, key, date_iso, h0=0, h1=23):
        arr = self.h.get(key) or []
        out = []
        for i in self.by_date.get(date_iso, []):
            hr = int(self.times[i][11:13])
            if h0 <= hr <= h1 and i < len(arr) and arr[i] is not None:
                out.append(arr[i])
        return out

    def at(self, key, hour_iso):
        try:
            i = self.times.index(hour_iso)
        except ValueError:
            return None
        arr = self.h.get(key) or []
        return arr[i] if i < len(arr) else None


def rain_pts(c, d, h0=8, h1=18, cap=3, sum_veto=0.5):
    """Dež v izbranih urah: verjetnost + vsota; vsota >= sum_veto mm je takoj 3 (do cap)."""
    s = sum(c.vals("precipitation", d, h0, h1))
    prob = max(c.vals("precipitation_probability", d, h0, h1), default=None)
    p = bands(prob, (20, 40, 60))
    if s >= sum_veto:
        p = 3
    p = min(p, cap)
    txt = f"padavine {seo.num(s, 1)} mm"
    if prob is not None:
        txt += f", verjetnost do {seo.num(prob, 0)} %"
    return p, txt


def storm_pts(c, d, h0=7, h1=21):
    storm = any(x >= 95 for x in c.vals("weather_code", d, h0, h1))
    return (3 if storm else 0), ("napovedana nevihta" if storm else "brez neviht")


def wind_pts(c, d, mean_ths, gust_ths, h0=8, h1=18):
    w = mean(c.vals("wind_speed_10m", d, h0, h1))
    g = max(c.vals("wind_gusts_10m", d, h0, h1), default=None)
    p = max(bands(w, mean_ths), bands(g, gust_ths))
    txt = "ni podatka"
    if w is not None:
        txt = f"veter povprečno {seo.num(w, 0)} km/h"
        if g is not None:
            txt += f", sunki do {seo.num(g, 0)} km/h"
        dirs = mean_dir(c.vals("wind_direction_10m", d, h0, h1), c.vals("wind_speed_10m", d, h0, h1))
        if dirs is not None and w >= 5:
            txt += f", prevladuje {compass(dirs)}"
    return p, txt


# ── Pridobivanje podatkov ────────────────────────────────────────────────────

CACHE_MAX_AGE_S = 1800


def _cache_path(past_days):
    import tempfile
    return os.path.join(tempfile.gettempdir(), f"dv-ctx-{today_lj().isoformat()}-{past_days}.json")


def fetch_ctx(past_days=2):
    """Ena napoved za vseh pet strani: rezultat se 30 min hrani v začasni datoteki, da pet generatorjev
    zapored ne sproži petih enakih klicev (Open-Meteo ob tem vrača 429)."""
    import time
    path = _cache_path(past_days)
    try:
        if time.time() - os.path.getmtime(path) < CACHE_MAX_AGE_S:
            with open(path, encoding="utf-8") as f:
                return Ctx(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "hourly": HOURLY_VARS,
        "timezone": "Europe/Ljubljana", "past_days": past_days, "forecast_days": DNEVI,
    })
    last = None
    for delay in (0, 10, 30):
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{params}",
                                         headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                hourly = json.load(r).get("hourly")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(hourly, f)
            except OSError:
                pass
            return Ctx(hourly)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
    raise last


def today_lj():
    return datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).date()


def updated_text():
    n = datetime.datetime.now(ZoneInfo("Europe/Ljubljana"))
    return f"{n.day}. {n.month}. {n.year} ob {n.hour}.{n.minute:02d}"


def build_days(cfg, c, today=None):
    today = today or today_lj()
    days = []
    for i in range(DNEVI):
        d = today + datetime.timedelta(days=i)
        iso = d.isoformat()
        pts, det = cfg["day_fn"](c, iso)
        sc = score_for(pts)
        lvl = level_index(sc, max(pts.values()), cfg["th"])
        label = "Danes" if i == 0 else "Jutri" if i == 1 else DAN_KRATKO[d.weekday()]
        full = "danes" if i == 0 else "jutri" if i == 1 else DAN_PUN[d.weekday()]
        days.append({"date": iso, "label": label, "full": full, "pts": pts, "detail": det, "score": sc, "lvl": lvl})
    return days


def reasons(day, k=2):
    ranked = sorted(((p, key) for key, p in day["pts"].items() if p >= 1), reverse=True)
    return [day["detail"][key] for _, key in ranked[:k]]


# ── Najboljše okno ───────────────────────────────────────────────────────────

def best_window(scores, max_score=1, min_run=2):
    """scores = [(hour, score)] po uri; vrne (h_od, h_do vključno) najdaljšega zaporedja ur
    z oceno <= max_score (ob izenačenju prvo) ali None."""
    best, cur = None, []
    for hr, sc in scores:
        ok = sc is not None and sc <= max_score
        if ok and (not cur or hr == cur[-1] + 1):
            cur.append(hr)
            continue
        if len(cur) >= min_run and (best is None or len(cur) > len(best)):
            best = cur
        cur = [hr] if ok else []
    if len(cur) >= min_run and (best is None or len(cur) > len(best)):
        best = cur
    return (best[0], best[-1]) if best else None


def hour_scores(cfg, c, date_iso, h0=6, h1=21, from_hour=0):
    out = []
    for hr in range(h0, h1 + 1):
        if hr < from_hour:
            continue
        out.append((hr, cfg["hour_fn"](c, f"{date_iso}T{hr:02d}:00")))
    return out


def fmt_hours(h0, h1):
    """Okno v zapisu po Pravopisu: »11.00–16.00« (ura s piko, od … do stično)."""
    return f"{h0}.00–{h1 + 1}.00"


# ── Izris ────────────────────────────────────────────────────────────────────

def esc(s):
    return html.escape(str(s))


def icon(i, size=18):
    return (f'<svg class="dv-ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS[i]}</svg>')


CSS = """<style>
.dv-viz{--dv-surface:#0e1624;--dv-ink:var(--text,#e8edf5);--dv-ink2:var(--muted,#9aa7bb);--dv-grid:rgba(255,255,255,.1);
  --g-1:#3987e5;--g-2:#d95926;--g-3:#199e70;--g-4:#c98500;
  --l-0:#059669;--l-1:#eab308;--l-2:#f97316;--l-3:#ef4444}
[data-theme="light"] .dv-viz{--dv-surface:#ffffff;--dv-grid:rgba(0,0,0,.12);--g-1:#2a78d6;--g-2:#eb6834;--g-3:#1baf7a;--g-4:#eda100}
.dv-hero{display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:1.4rem;align-items:center;margin:1rem 0 1.6rem;
  padding:1.2rem 1.3rem;border:1px solid var(--dv-grid);border-radius:16px;
  background:radial-gradient(120% 140% at 0% 0%,color-mix(in srgb,var(--c) 18%,transparent),transparent 60%),var(--dv-surface)}
.dv-gauge{width:100%;height:auto;display:block}
.dv-k{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--dv-ink2)}
.dv-l{font-size:2.3rem;font-weight:800;line-height:1.1;color:var(--c);margin:.1rem 0 .3rem}
.dv-sum{margin:.2rem 0 0;font-size:1rem;color:var(--dv-ink)}
.dv-adv{margin:.6rem 0 0;font-size:.92rem;color:var(--dv-ink)}
.dv-meta{margin:.7rem 0 0;font-size:.76rem;color:var(--dv-ink2)}
.dv-meta a{color:inherit;text-decoration:underline}
.dv-art{float:right;width:64px;height:64px;margin:0 0 .5rem .8rem;padding:6px;border-radius:16px;background:rgba(255,255,255,.1)}
.dv-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem}
.dv-chip{display:inline-flex;align-items:center;gap:.35rem;padding:.3rem .65rem;border-radius:999px;font-size:.8rem;border:1px solid var(--dv-grid);color:var(--dv-ink)}
.dv-chip .dv-ic{color:var(--gc)}
.dv-days{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.6rem;margin:1rem 0 1.4rem}
.dv-day{border:1px solid var(--dv-grid);border-top:4px solid var(--c);border-radius:12px;padding:.75rem .85rem;background:var(--dv-surface)}
.dv-day.dv-today{box-shadow:0 0 0 2px var(--c)}
.dv-day h3{margin:0;font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--dv-ink2)}
.dv-day .dv-lvl{font-size:1.2rem;font-weight:800;color:var(--c);margin:.15rem 0}
.dv-day .dv-sc{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--dv-ink2)}
.dv-day ul{margin:.5rem 0 0;padding-left:1rem;font-size:.8rem}
.dv-card{border:1px solid var(--dv-grid);border-radius:14px;padding:1rem 1.1rem;background:var(--dv-surface);margin:1rem 0 1.6rem}
.dv-svg{width:100%;height:auto;display:block}
.dv-svg text{font-family:inherit}
.dv-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.6rem;font-size:.8rem;color:var(--dv-ink2)}
.dv-legend span{display:inline-flex;align-items:center;gap:.35rem}
.dv-legend i{width:10px;height:10px;border-radius:2px;background:var(--gc);display:inline-block}
.dv-grp{margin-bottom:1rem}
.dv-grp h3{display:flex;align-items:center;gap:.45rem;margin:.2rem 0 .5rem;font-size:.95rem;color:var(--dv-ink)}
.dv-grp h3 .dv-ic{color:var(--gc)}
.dv-row{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:.8rem;align-items:start;font-size:.85rem;margin-bottom:.45rem}
.dv-name{color:var(--dv-ink)}
.dv-track{display:grid;grid-template-columns:repeat(3,1fr);gap:3px;margin-bottom:.15rem}
.dv-track i{height:10px;border-radius:3px;background:var(--dv-grid)}
.dv-track i.on{background:var(--gc)}
.dv-det{font-size:.78rem;color:var(--dv-ink2)}
.dv-why{font-size:.76rem;color:var(--dv-ink2);opacity:.9}
.dv-heat td{text-align:center;font-weight:700}
.dv-heat .dv-g{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:.4rem;background:var(--gc)}
.dv-none{color:var(--dv-ink2);font-weight:400!important;font-size:.78rem}
.dv-reasons{margin:.6rem 0 1rem;font-size:.86rem}
.dv-reasons ul{margin:.5rem 0 0;padding-left:1.1rem}
.dv-strip{display:grid;grid-template-columns:repeat(16,minmax(0,1fr));gap:3px;margin:.5rem 0 .2rem}
.dv-strip b{display:block;height:28px;border-radius:4px;background:var(--lc);font-size:0}
.dv-strip-h{display:grid;grid-template-columns:repeat(16,minmax(0,1fr));gap:3px;font-size:.66rem;color:var(--dv-ink2);text-align:center}
.dv-win{font-weight:700;color:var(--dv-ink);margin:.4rem 0 1rem}
@media (max-width:640px){.dv-days{grid-template-columns:repeat(2,minmax(0,1fr))}.dv-hero{grid-template-columns:1fr}.dv-l{font-size:1.9rem}.dv-row{grid-template-columns:1fr}}
</style>"""


def _pt(cx, cy, r, d):
    rad = math.radians(d)
    return cx - r * math.cos(rad), cy - r * math.sin(rad)


def gauge_deg(score, top):
    return 180 * min(max(score, 0), top) / top


def top_of(cfg):
    return cfg["th"][2] + 4


def gauge_svg(cfg, day):
    cx = cy = 110
    r = 88
    top = top_of(cfg)
    th = cfg["th"]
    bounds = [0, th[0], th[1], th[2], top]
    arcs = []
    for i in range(4):
        d1, d2 = gauge_deg(bounds[i], top) + 1.2, gauge_deg(bounds[i + 1], top) - 1.2
        x1, y1 = _pt(cx, cy, r, d1)
        x2, y2 = _pt(cx, cy, r, d2)
        arcs.append(f'<path d="M{x1:.1f} {y1:.1f}A{r} {r} 0 0 1 {x2:.1f} {y2:.1f}" fill="none" stroke="var(--l-{i})" stroke-width="16"/>')
    ticks = "".join(
        f'<text x="{_pt(cx, cy, r + 17, gauge_deg(b, top))[0]:.1f}" y="{_pt(cx, cy, r + 17, gauge_deg(b, top))[1] + 3:.1f}" '
        f'text-anchor="middle" font-size="9" fill="var(--dv-ink2)">{b}{"+" if b == top else ""}</text>' for b in bounds)
    deg = gauge_deg(day["score"], top)
    return (f'<svg class="dv-gauge" viewBox="0 0 220 138" role="img" aria-label="Merilnik: {tocke(day["score"])}, {cfg["levels"][day["lvl"]]}">'
            + "".join(arcs) + ticks +
            f'<g id="dv-needle" transform="rotate({deg:.1f} {cx} {cy})"><path d="M{cx - 70} {cy}L{cx} {cy - 3.5}L{cx} {cy + 3.5}z" fill="var(--dv-ink)"/></g>'
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="var(--dv-ink)"/><circle cx="{cx}" cy="{cy}" r="3" fill="var(--dv-surface)"/>'
            f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" font-size="12" fill="var(--dv-ink2)" id="dv-gauge-sc">{tocke(day["score"])} (manj je bolje)</text></svg>')


def group_of(cfg):
    return {k: gi for gi, (_, _, ks) in enumerate(cfg["groups"], 1) for k in ks}


def factor_label(cfg):
    return {k: l for k, l, _ in cfg["factors"]}


def hero_html(cfg, days):
    d = days[0]
    g = group_of(cfg)
    lvls = cfg["levels"]
    rs = sorted(((p, k) for k, p in d["pts"].items() if p >= 1), reverse=True)[:3]
    chips = "".join(
        f'<span class="dv-chip" style="--gc:var(--g-{g[k]})">{icon(cfg["group_icons"][g[k] - 1], 16)}{esc(d["detail"][k])}</span>'
        for _, k in rs) or '<span class="dv-chip">brez izrazitih ovir</span>'
    summ = ("Glavne ovire: " + "; ".join(reasons(d, 2)) + ".") if reasons(d, 2) else "Danes ni izrazitih ovir."
    return (f'  <div class="dv-hero" id="dv-hero" style="--c:var(--l-{d["lvl"]})">\n    {gauge_svg(cfg, d)}\n'
            f'    <div>{cfg.get("hero_art", "")}<div class="dv-k">{esc(cfg["kicker"])}</div><div class="dv-l" id="dv-hero-l">{esc(lvls[d["lvl"]])}</div>'
            f'<p class="dv-sum">{esc(summ)}</p><div class="dv-chips">{chips}</div>'
            f'<p class="dv-adv">{esc(cfg["advice"][d["lvl"]])}</p>'
            f'<p class="dv-meta">Izračunano {esc(updated_text())} · modelska napoved, ne meritev · '
            f'<a href="#metodologija">kako je ocena izračunana</a></p></div>\n  </div>')


def days_summary(cfg, days):
    lv = cfg["levels"]
    if len({d["lvl"] for d in days}) == 1:
        return f"Vseh {len(days)} dni je raven enaka: {lv[days[0]['lvl']]}."
    worst = max(days, key=lambda d: (d["score"], -days.index(d)))
    best = min(days, key=lambda d: (d["score"], days.index(d)))
    return (f"Najugodnejši dan je {best['full']} ({lv[best['lvl']]}), "
            f"najmanj ugoden {worst['full']} ({lv[worst['lvl']]}).")


def day_cards_html(cfg, days):
    out = []
    for i, d in enumerate(days):
        li = "".join(f"<li>{esc(r)}</li>" for r in reasons(d)) or "<li>brez izrazitih ovir</li>"
        cls = "dv-day dv-today" if i == 0 else "dv-day"
        out.append(f'    <div class="{cls}" style="--c:var(--l-{d["lvl"]})"><h3>{esc(d["label"])}</h3>'
                   f'<div class="dv-lvl">{esc(cfg["levels"][d["lvl"]])}</div><div class="dv-sc">{tocke(d["score"])}</div><ul>{li}</ul></div>')
    return '  <div class="dv-days" id="dv-days">\n' + "\n".join(out) + "\n  </div>"


def legend_html(cfg):
    return '<div class="dv-legend">' + "".join(
        f'<span style="--gc:var(--g-{i})"><i></i>{icon(cfg["group_icons"][i - 1], 14)}{esc(lbl)}</span>'
        for i, (_, lbl, _) in enumerate(cfg["groups"], 1)) + "</div>"


def stacked_chart_svg(cfg, days):
    W, H = 640, 270
    pl, pr, pt, pb = 34, 96, 14, 30
    pw, ph = W - pl - pr, H - pt - pb
    top = max(top_of(cfg), max(d["score"] for d in days) + 1)
    y = lambda v: pt + ph * (1 - v / top)
    th = cfg["th"]
    bounds = [0, th[0], th[1], th[2], top]
    fl = factor_label(cfg)
    out = [f'<svg class="dv-svg" viewBox="0 0 {W} {H}" role="img" aria-label="Skupna ocena po dnevih, razrezana po skupinah dejavnikov">']
    for i in range(4):
        y0, y1 = y(bounds[i + 1]), y(bounds[i])
        out.append(f'<rect x="{pl}" y="{y0:.1f}" width="{pw}" height="{y1 - y0:.1f}" fill="var(--l-{i})" opacity=".09"/>')
        out.append(f'<text x="{W - pr + 8}" y="{(y0 + y1) / 2 + 3:.1f}" font-size="10" fill="var(--dv-ink2)">{esc(cfg["levels"][i])}</text>')
    step = 2 if top <= 14 else 4
    for v in range(0, int(top) + 1, step):
        out.append(f'<line x1="{pl}" x2="{pl + pw}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--dv-grid)"/>')
        out.append(f'<text x="{pl - 6}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="10" fill="var(--dv-ink2)">{v}</text>')
    slot = pw / len(days)
    bw = slot * 0.5
    for i, d in enumerate(days):
        x = pl + slot * i + (slot - bw) / 2
        acc = 0
        for gi, (_, glabel, keys) in enumerate(cfg["groups"], 1):
            v = sum(d["pts"][k] for k in keys)
            if v == 0:
                continue
            y_top, y_bot = y(acc + v), y(acc)
            tip = f'{d["label"]} · {glabel}: {tocke(v)}' + "".join(f' · {fl[k]}: {d["detail"][k]}' for k in keys if d["pts"][k])
            out.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bw:.1f}" height="{max(y_bot - y_top, 0):.1f}" rx="3" '
                       f'fill="var(--g-{gi})" stroke="var(--dv-surface)" stroke-width="2"><title>{esc(tip)}</title></rect>')
            acc += v
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y(acc) - 6:.1f}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--dv-ink)">{acc}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{H - 10}" text-anchor="middle" font-size="11" fill="var(--dv-ink2)">{esc(d["label"])}</text>')
    out.append("</svg>")
    return "".join(out)


def stacked_block(cfg, days):
    return ('  <div class="dv-card">\n    ' + stacked_chart_svg(cfg, days) + "\n    " + legend_html(cfg) +
            '\n    <p class="muted-note">Manj točk je bolje. Pomik nad stolpec pokaže razloge; isti razlogi so spodaj zapisani kot besedilo.</p>\n  </div>')


def reasons_by_day_html(cfg, days):
    fl = factor_label(cfg)
    items = []
    for d in days:
        rs = [f'{fl[k]}: {d["detail"][k]}' for k, p in sorted(d["pts"].items(), key=lambda kv: -kv[1]) if p >= 1]
        items.append(f'<li><strong>{esc(d["label"])}</strong> ({esc(cfg["levels"][d["lvl"]])}): '
                     f'{esc("; ".join(rs) if rs else "brez izrazitih ovir")}</li>')
    return '  <details class="dv-reasons"><summary>Razlogi po dnevih (besedilo)</summary><ul>' + "".join(items) + "</ul></details>"


def profile_html(cfg, day):
    fl = factor_label(cfg)
    why = {k: w for k, _, w in cfg["factors"]}
    blocks = []
    for gi, (_, glabel, keys) in enumerate(cfg["groups"], 1):
        rows = []
        for k in keys:
            p = day["pts"][k]
            track = "".join(f'<i class="{"on" if j < p else ""}"></i>' for j in range(3))
            rows.append(f'      <div class="dv-row"><div class="dv-name">{esc(fl[k])}</div><div>'
                        f'<div class="dv-track" role="img" aria-label="{esc(fl[k])}: {PTS_WORD[p]}">{track}</div>'
                        f'<div class="dv-det"><strong>{PTS_WORD[p]}</strong> · {esc(day["detail"][k])} (modelska napoved)</div>'
                        f'<div class="dv-why">{esc(why[k])}</div></div></div>')
        blocks.append(f'    <div class="dv-grp" style="--gc:var(--g-{gi})"><h3>{icon(cfg["group_icons"][gi - 1], 18)}{esc(glabel)}</h3>\n'
                      + "\n".join(rows) + "\n    </div>")
    return '  <div class="dv-card">\n' + "\n".join(blocks) + "\n  </div>"


def heatmap_html(cfg, days):
    g = group_of(cfg)
    alpha = {1: 35, 2: 65, 3: 100}
    head = "<th></th>" + "".join(f"<th>{esc(d['label'])}</th>" for d in days)
    rows = []
    for k, lbl, _ in cfg["factors"]:
        cells = []
        for d in days:
            p = d["pts"][k]
            if p == 0:
                cells.append('<td class="dv-none">ni ovire</td>')
            else:
                cells.append(f'<td style="background:color-mix(in srgb,var(--g-{g[k]}) {alpha[p]}%,transparent);'
                             f'color:{"#04070e" if p == 3 else "inherit"}">{PTS_WORD[p]}</td>')
        rows.append(f'<tr style="--gc:var(--g-{g[k]})"><th><span class="dv-g"></span>{esc(lbl)}</th>{"".join(cells)}</tr>')
    return ('  <div class="table-scroll" tabindex="0"><table class="stats dv-heat">\n'
            f'    <tr>{head}</tr>\n    ' + "\n    ".join(rows) + "\n  </table></div>")


def strip_html(cfg, scores, label):
    """Urni trak 6.00–21.00: barva = raven ure, ob vsaki celici besedilo za bralnik; pod trakom najboljše okno."""
    cells, hrs = [], []
    for hr, sc in scores:
        if sc is None:
            cells.append(f'<b style="--lc:var(--dv-grid)" title="{hr}.00: ni podatka"></b>')
        else:
            cells.append(f'<b style="--lc:var(--l-{sc})" title="{hr}.00: {esc(cfg["levels"][sc])}" '
                         f'aria-label="{hr}.00: {esc(cfg["levels"][sc])}"></b>')
        hrs.append(f"<span>{hr}</span>" if hr % 3 == 0 else "<span></span>")
    win = best_window(scores)
    win_txt = (f'{cfg["window_label"]}: {fmt_hours(*win)}' if win else f'{cfg["window_none"]}')
    return (f'  <h3>{esc(label)}</h3>\n  <div class="dv-strip" role="group" aria-label="{esc(label)}">{"".join(cells)}</div>\n'
            f'  <div class="dv-strip-h">{"".join(hrs)}</div>\n  <p class="dv-win">{esc(win_txt)}</p>')


def strips_block(cfg, c, today):
    if not cfg.get("hour_fn"):
        return ""
    now = datetime.datetime.now(ZoneInfo("Europe/Ljubljana"))
    out = [f'  <h2>{esc(cfg["strip_title"])}</h2>',
           f'  <p class="archive-intro">{esc(cfg["strip_intro"])} Barva celice je raven ure: '
           + ", ".join(f"{esc(l)}" for l in cfg["levels"]) + ".</p>", '  <div class="dv-card">']
    out.append(strip_html(cfg, hour_scores(cfg, c, today.isoformat(), from_hour=now.hour if now.date() == today else 0), "Danes"))
    tom = (today + datetime.timedelta(days=1)).isoformat()
    out.append(strip_html(cfg, hour_scores(cfg, c, tom), "Jutri"))
    out.append("  </div>")
    return "\n".join(out)


def faq_html(cfg):
    return '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f"    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in cfg["faq"]) + "\n  </div>"


def build_body(cfg, c, days, today=None):
    today = today or today_lj()
    d0 = days[0]
    lvl = cfg["levels"][d0["lvl"]]
    rs = reasons(d0, 3)
    why = (" Glavne ovire: " + "; ".join(rs) + ".") if rs else " Danes ni izrazitih ovir."
    answer = (f'  <p class="archive-intro"><strong>{esc(cfg["intro_q"])}</strong> {esc(cfg["intro_a"])} '
              f'Ocena za danes v Rečici ob Savinji in Zgornji Savinjski dolini: <strong>{esc(lvl)}</strong> '
              f'({tocke(d0["score"])}, manj je bolje).{esc(why)}</p>')
    rule_rows = "\n".join(f"    <tr><th>{esc(a)}</th><td>{esc(b)}</td><td>{esc(c_)}</td></tr>" for a, b, c_ in cfg["rules"])
    limits = "\n".join(f"    <li>{x}</li>" for x in cfg["limits"])
    ext = ' target="_blank" rel="noopener"'
    links = "".join('      <a href="%s" class="mtn-avk-link"%s>%s</a>\n' % (u, ext if u.startswith("http") else "", esc(t))
                    for u, t in cfg["links"])
    sec = cfg["sections"](cfg, c, days, today) if cfg.get("sections") else {}
    alert = "" if cfg.get("no_ocene") else alert_html(cfg["slug"], cfg["short"], cfg["levels"])
    alert_js = "" if cfg.get("no_ocene") else alert_script(cfg["slug"])
    script = cfg["script"](cfg, days) if cfg.get("script") else ""
    return f'''{seo.crumbs_html([("Meteorec", "/"), (cfg["crumb"], None)])}
{seo.stn_badge()}
  <h1 class="page-title">{esc(cfg["h1"])}</h1>
  <p class="post-meta">{esc(cfg["meta"])} · Rečica ob Savinji in Zgornja Savinjska dolina · izračunano {esc(updated_text())}</p>
<div class="dv-viz">
{hero_html(cfg, days)}
{answer}
  <p class="muted-note"><strong>{esc(cfg["disclaimer_lead"])}</strong> {esc(cfg["disclaimer"])}</p>
{sec.get("after_hero", "")}
  <h2>Naslednjih 5 dni</h2>
  <p class="archive-intro">{esc(days_summary(cfg, days))} Raven je vedno zapisana tudi z besedo.</p>
{day_cards_html(cfg, days)}
{alert}
{sec.get("after_cards", "")}
{strips_block(cfg, c, today)}
  <h2>Skupna ocena po dnevih</h2>
{stacked_block(cfg, days)}
{reasons_by_day_html(cfg, days)}
  <h2>Danes po dejavnikih</h2>
  <p class="archive-intro">Dejavniki so v skupinah. Vsak ima tri stopnje (blago, zmerno, izrazito), vrednost in razlog, zakaj je pomemben.</p>
{profile_html(cfg, d0)}
  <h2>Vsi dnevi in dejavniki</h2>
{heatmap_html(cfg, days)}
  <h2 id="metodologija">Kako je ocena sestavljena</h2>
  <p class="archive-intro">{esc(cfg["method_intro"])}</p>
  <table class="stats">
    <tr><th>Dejavnik</th><td>Pragovi (točke 1 / 2 / 3)</td><td>Opomba</td></tr>
{rule_rows}
  </table>
  <ul class="dv-lim">
{limits}
    <li><strong>Modelska napoved, ne meritev:</strong> podatki so iz Open-Meteo za Rečico ob Savinji, stran se izračuna enkrat na dan ({esc(updated_text())}); mreža modela ne razloči posameznih dolin in lokalnih razlik.</li>
  </ul>
{faq_html(cfg)}
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">Povezave</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
{links}    </div>
  </div>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
</div>
{script}
{alert_js}'''


def build_page(cfg, c, today=None):
    today = today or today_lj()
    days = build_days(cfg, c, today)
    d0 = days[0]
    desc = cfg["desc"](cfg["levels"][d0["lvl"]])
    schema = "\n".join([
        seo.webpage_schema(cfg["url"], cfg["title"], desc, date_published="2026-10-29"),
        seo.crumbs_schema([("Meteorec", "/"), (cfg["crumb"], None)]),
        seo.faq_schema(cfg["faq"]),
    ]) + "\n" + CSS + "\n" + ("" if cfg.get("no_ocene") else ALERT_CSS)
    page = seo.page_shell(cfg["title"], desc, cfg["url"], schema, build_body(cfg, c, days, today))
    return page, days


# ── Opozorila po ocenah ──────────────────────────────────────────────────────
ALERT_MAX_RULES = 5        # ↔ OCENE_MAX_RULES v worker.js (test_day_pages.py primerja)
OCENE_FILE = os.path.join(seo.ROOT, "data", "vsakdan-ocene.json")
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"


def write_summary(slug, short, url, levels, days, path=None):
    """Zapiše ocene strani v skupni data/vsakdan-ocene.json, ki ga bere worker (opozorila po ocenah).
    days = [{"date", "lvl" (indeks), "reasons" [besedila]}]. Ostale strani v datoteki ostanejo; časi so UTC.
    Strani poganjajo zaporedno (vsakdan-forecast.yml), zato branje-spreminjanje-pisanje ne tekmuje."""
    path = path or OCENE_FILE
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("pages"), dict):
            data = {"pages": {}}
    except (OSError, json.JSONDecodeError):
        data = {"pages": {}}
    data["generated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["pages"][slug] = {"naslov": short, "url": url, "levels": list(levels),
                           "days": [{"date": d["date"], "lvl": int(d["lvl"]), "reasons": list(d.get("reasons") or [])[:2]} for d in days]}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        f.write("\n")


def alert_options(levels):
    """(vrednost, besedilo) izbir za »Obvesti me, ko je raven …«: skrajni ravni točno, vmesni z »ali boljše/slabše«."""
    return [("le0", f"{levels[0]}"), ("le1", f"{levels[1]} ali boljše"), ("ge2", f"{levels[2]} ali slabše"), ("ge3", f"{levels[3]}")]


ALERT_CSS = """<style>
.ov-alert{border:1px solid rgba(255,255,255,.14);border-radius:14px;padding:1rem 1.1rem;margin:1rem 0 1.6rem}
[data-theme="light"] .ov-alert{border-color:rgba(0,0,0,.14)}
.ov-alert h2{margin-top:0}
.ov-row{display:flex;flex-wrap:wrap;gap:.7rem;align-items:flex-end;margin:.6rem 0}
.ov-row label{display:flex;flex-direction:column;gap:.25rem;font-size:.85rem}
.ov-row select{min-height:44px;padding:.4rem .6rem;border-radius:8px;border:1px solid rgba(128,128,128,.5);background:transparent;color:inherit;font:inherit}
.ov-btn{min-height:44px;padding:.5rem 1rem;border-radius:8px;border:1px solid rgba(128,128,128,.5);background:transparent;color:inherit;font:inherit;cursor:pointer}
.ov-btn-p{background:#2a78d6;border-color:#2a78d6;color:#fff;font-weight:700}
.ov-btn:disabled{opacity:.45;cursor:not-allowed}
.ov-msg{font-size:.88rem;margin:.4rem 0}
</style>"""


def alert_html(slug, short, levels, opts=None):
    """Gradnik »Moje opozorilo«; skrit, dokler brskalnik ne podpira Web Push (izpisan v JS).
    opts = [(vrednost, besedilo)] za strani z drugačnim naborom ravni (zimska opozorila); privzeto alert_options(levels)."""
    ops = "".join(f'<option value="{v}">{esc(t)}</option>' for v, t in (opts or alert_options(levels)))
    return (f'  <div class="ov-alert" id="ov-alert" hidden>\n'
            f'  <h2>Opozorilo na telefon</h2>\n'
            f'  <p class="archive-intro">Sami nastavite, kdaj želite obvestilo: izberite raven in dan, mi pa ga pošljemo, ko ocena za »{esc(short)}« ustreza. '
            f'Vsako pravilo sproži obvestilo enkrat na ciljni dan. Strežnik shrani samo naslovnico naročnine in vaša pravila (največ {ALERT_MAX_RULES} na napravi, za vse strani skupaj).</p>\n'
            f'  <div class="ov-row"><label>Obvesti me, ko je raven <select id="ov-op">{ops}</select></label>'
            f'<label>za dan <select id="ov-when"><option value="jutri">jutri</option><option value="danes">danes</option></select></label></div>\n'
            f'  <div class="ov-row"><button type="button" class="ov-btn ov-btn-p" id="ov-on">Vklopi opozorilo</button>'
            f'<button type="button" class="ov-btn" id="ov-off" hidden>Izklopi opozorilo za to stran</button></div>\n'
            f'  <p class="ov-msg" id="ov-msg" role="status" aria-live="polite"></p>\n'
            f'  <p class="ov-msg" id="ov-ios" hidden><b>iPhone in iPad:</b> obvestila delujejo samo v nameščeni aplikaciji. V Safariju tapnite »Deli« in »Dodaj na začetni zaslon«, odprite Meteorec z začetnega zaslona in opozorilo vklopite tam.</p>\n'
            f'  <p class="muted-note">Modelska napoved Open-Meteo, ne meritev ali uradno opozorilo. Opozorilo lahko kadar koli izklopite tukaj.</p>\n  </div>')


ALERT_JS = r"""(function(){
  var SLUG=__SLUG__,API=__API__,MAX=__MAX__,RK='wx-ocene-pravila',box=document.getElementById('ov-alert');if(!box)return;
  var op=document.getElementById('ov-op'),when=document.getElementById('ov-when'),onB=document.getElementById('ov-on'),offB=document.getElementById('ov-off'),msg=document.getElementById('ov-msg'),ios=document.getElementById('ov-ios');
  function say(t){msg.textContent=t||'';}
  function load(){try{var r=JSON.parse(localStorage.getItem(RK));return Array.isArray(r)?r:[];}catch(e){return [];}}
  function save(r){try{localStorage.setItem(RK,JSON.stringify(r));}catch(e){}}
  var standalone=(window.matchMedia&&matchMedia('(display-mode: standalone)').matches)||navigator.standalone===true;
  var isIOS=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  function mine(rs){return rs.filter(function(x){return x.page===SLUG;})[0];}
  function show(){var m=mine(load());offB.hidden=!m;onB.textContent=m?'Shrani novo pravilo':'Vklopi opozorilo';
    if(m){op.value=m.op+m.lvl;when.value=m.when;say('Opozorilo je vklopljeno za to stran.');}else say('');}
  if(isIOS&&!standalone){box.hidden=false;ios.hidden=false;onB.disabled=true;return;}
  if(!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window))return;
  box.hidden=false;show();
  function b64(s){var p='='.repeat((4-s.length%4)%4),b=(s+p).replace(/-/g,'+').replace(/_/g,'/'),r=atob(b),o=new Uint8Array(r.length);for(var i=0;i<r.length;i++)o[i]=r.charCodeAt(i);return o;}
  function post(path,body){return fetch(API+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(function(r){return r.json().then(function(j){if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j;});});}
  function reg(){return navigator.serviceWorker.register('/sw.js').then(function(){return navigator.serviceWorker.ready;});}
  // Strežnik hrani celoten seznam pravil te naprave; prazen seznam = odjava (brskalnika ne odjavimo).
  function sync(rules,ok){
    onB.disabled=true;offB.disabled=true;
    return reg().then(function(r){return r.pushManager.getSubscription().then(function(sub){
      if(!rules.length){return sub?post('/push/unsubscribe',{site:'ocene',endpoint:sub.endpoint}):null;}
      if(sub)return sub;
      return fetch(API+'/push/vapid').then(function(x){return x.json();}).then(function(v){return r.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64(v.publicKey)});});
    }).then(function(sub){if(rules.length&&sub)return post('/push/subscribe',{site:'ocene',subscription:sub.toJSON(),rules:rules});});})
    .then(function(){save(rules);show();say(ok);}).catch(function(e){say('Ni uspelo: '+(e&&e.message?e.message:'poskusite znova čez nekaj minut')+'.');})
    .then(function(){onB.disabled=false;offB.disabled=false;});
  }
  onB.addEventListener('click',function(){
    if(Notification.permission==='denied'){say('Obvestila so za to stran v brskalniku blokirana. Dovolite jih v nastavitvah strani.');return;}
    var all=load().filter(function(x){return x.page!==SLUG;});
    if(all.length>=MAX){say('Največ '+MAX+' pravil na napravi (za vse strani skupaj). Eno izklopite na drugi strani.');return;}
    var v=op.value;all.push({page:SLUG,op:v.slice(0,2),lvl:+v.slice(2),when:when.value});
    Notification.requestPermission().then(function(p){
      if(p!=='granted'){say('Brez dovoljenja za obvestila opozorilo ne more delovati.');return;}
      return sync(all,'Opozorilo je vklopljeno: '+op.options[op.selectedIndex].text+', za dan: '+when.value+'.');});
  });
  offB.addEventListener('click',function(){sync(load().filter(function(x){return x.page!==SLUG;}),'Opozorilo za to stran je izklopljeno.');});
})();"""


def alert_script(slug, api=WORKER_BASE):
    return "<script>\n" + (ALERT_JS.replace("__SLUG__", json.dumps(slug)).replace("__API__", json.dumps(api))
                           .replace("__MAX__", str(ALERT_MAX_RULES))) + "\n</script>"


def main(cfg):
    print(f"[{today_lj()}] {cfg['url']} …")
    try:
        c = fetch_ctx(cfg.get("past_days", 2))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        sys.exit(1)
    if not c.times:
        print("✗ Open-Meteo brez urnih podatkov", file=sys.stderr)
        sys.exit(1)
    page, days = build_page(cfg, c)
    seo.write_page(cfg["url"].strip("/") + "/index.html", page, force=True)
    if not cfg.get("no_ocene"):
        write_summary(cfg["slug"], cfg["short"], cfg["url"], cfg["levels"],
                      [{"date": d["date"], "lvl": d["lvl"], "reasons": reasons(d)} for d in days])
    print(f"  → {cfg['url']} (danes {cfg['levels'][days[0]['lvl']]}, {tocke(days[0]['score'])})")
