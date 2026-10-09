#!/usr/bin/env python3
"""
tools/generate_gobe_suha_tla_post.py — članek »Padlo je 10 mm na suha tla. Zakaj jurčki še počakajo?«

Ročno zasnovan članek (ne dnevni samodejni). Vse številke so izračunane ob zagonu:

  * dež: IREICA1 (history.json za pretekle dni, Worker /hourly za dan, ki ga history.json še nima),
  * pragovi in zamiki vrst: species_rules.yaml (isti kot gobarski model),
  * vlaga tal: Open-Meteo `soil_moisture_3_to_9cm` za domače območje — MODELSKA OCENA, postaja je ne meri.
    Preračun na lestvico 0–100 % je isti kot v gobe_model (scoring.soil_moisture dry/full).

Članek je POSNETEK ob uri zajema — stran to pove. Notranjih meritev ni nikjer (CLAUDE.md, pravilo na
vrhu). Lektura je izklopljena (CLAUDE.md) — besedilo je treba prebrati ročno.

Usage:
    python3 tools/generate_gobe_suha_tla_post.py [--dry-run] [--wire] [--rain-day 2026-10-08]
"""
import datetime
import json
import os
import re
import statistics as st
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import generate_forecast_test_post as ftp  # noqa: E402
from generate_seo_pages import num  # noqa: E402
import yaml  # noqa: E402

ROOT = seo.ROOT
YEAR = 2026
SLUG = "padlo-10-mm-na-suha-tla-zakaj-jurcki-pocakajo-1009"
RAIN_DAY = "2026-10-08"
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
SPECIES_SHOW = [("boletus_edulis", "Jurček"), ("cantharellus_cibarius", "Lisička"),
                ("macrolepiota_procera", "Orjaški dežnik (marela)"),
                ("hydnum_repandum", "Rumeni ježek"), ("pleurotus_ostreatus", "Bukov ostrigar")]
ECO_ROWS = [("razkrojevalka", "Razkrojevalke stelje in travinja", "marela, kukmaki"),
            ("lesna", "Lesne vrste", "bukov ostrigar, bezgova uhljevka"),
            ("mikorizna", "Mikorizne vrste", "jurček, lisička, rumeni ježek")]
CSS = """<style>
.mini-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.4rem 0 2rem}
.mini-stat{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.9rem .8rem;text-align:center}
.ms-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-family:'JetBrains Mono',monospace}
.ms-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.4rem;line-height:1.1;margin:.18rem 0 .1rem;color:var(--cyan)}
.ms-sub{font-size:.72rem;color:var(--muted)}
@media(max-width:640px){.mini-stat-grid{grid-template-columns:repeat(2,1fr)}}
.disclaimer{background:rgba(239,68,68,.06);border:1px solid var(--card-border);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.85rem;color:var(--muted)}
.sources{font-size:.82rem;color:var(--muted);border-top:1px solid rgba(255,255,255,.07);margin-top:2.2rem;padding-top:1rem;line-height:1.7}
</style>"""


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": WORKER_UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def cached_open_meteo(url):
    """Open-Meteo ob več zaporednih zagonih vrne 429: odgovor se shrani v --cache FILE in ob
    ponovnem zagonu prebere od tam; sicer ponovni poskusi z zamikom."""
    import time
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    if cache and os.path.exists(cache):
        return json.load(open(cache, encoding="utf-8"))
    last = None
    for delay in (0, 15, 45, 90):
        if delay:
            print(f"Open-Meteo: čakam {delay}s …")
            time.sleep(delay)
        try:
            data = get_json(url)
            if cache:
                json.dump(data, open(cache, "w", encoding="utf-8"))
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
    raise last


def d_short(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def d_long(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {seo.MES_GEN[d.month]}"


def d_add(iso, n):
    return (datetime.date.fromisoformat(iso) + datetime.timedelta(days=n)).isoformat()


def d_rng(a, b):
    da, db = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    if da.month == db.month:
        return f"{da.day}.–{db.day}. {db.month}."
    return f"{da.day}. {da.month}.–{db.day}. {db.month}."


WEEKDAY = ["ponedeljek", "torek", "sredo", "četrtek", "petek", "soboto", "nedeljo"]
WEEKDAY_NOM = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]


def dni(n):
    return "dan" if n == 1 else "dni"


def build_data(rain_day):
    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    rules = yaml.safe_load(open(os.path.join(ROOT, "species_rules.yaml"), encoding="utf-8"))
    home = next(l for l in rules["locations"] if l.get("home"))
    smc = rules["scoring"]["soil_moisture"]
    dry_v, full_v = float(smc["dry"]), float(smc["full"])

    # ── dež na postaji: history.json za pretekle dni, /hourly za dan dežja ──
    rain = {k: v["precipTotal"] for k, v in hist.items()
            if v.get("precipTotal") is not None and k < rain_day}
    hourly = get_json(PROXY + "/hourly")["observations"]
    vals = [o["metric"]["precipTotal"] for o in hourly
            if o["obsTimeLocal"][:10] == rain_day and o.get("metric", {}).get("precipTotal") is not None]
    if not vals:
        raise SystemExit(f"/hourly nima meritev za {rain_day} — ne izmišljam številke.")
    rain_mm = max(vals)
    event_mm = None
    try:
        cur = get_json(PROXY + "/ecowitt-current")
        event_mm = cur["data"]["rainfall"]["event"]["value"]
    except Exception:  # noqa: BLE001  (dopolnilna številka, ni nujna)
        pass

    pre14 = round(sum(rain.get(d_add(rain_day, -i), 0.0) for i in range(1, 15)), 1)
    # suha serija: dnevi pred dežjem brez ≥ 1 mm
    n_dry, d = 0, d_add(rain_day, -1)
    while d in rain and rain[d] < 1.0:
        n_dry += 1
        d = d_add(d, -1)
    last_wet = d
    last_wet_mm = rain.get(d)
    sept = {k: rain[k] for k in ("2026-09-10", "2026-09-11") if k in rain}
    sept_sum = round(sum(sept.values()), 1)

    # ── vlaga tal (model) ──
    q = urllib.parse.urlencode({
        "latitude": home["lat"], "longitude": home["lon"],
        "hourly": "soil_moisture_3_to_9cm,soil_moisture_9_to_27cm", "daily": "precipitation_sum",
        "past_days": 35, "forecast_days": 4, "timezone": "Europe/Ljubljana"}, safe=",")
    om = cached_open_meteo("https://api.open-meteo.com/v1/forecast?" + q)
    t = om["hourly"]["time"]
    days = {}
    for i, x in enumerate(t):
        days.setdefault(x[:10], []).append((om["hourly"]["soil_moisture_3_to_9cm"][i],
                                            om["hourly"]["soil_moisture_9_to_27cm"][i]))

    def mean(ix, day):
        v = [p[ix] for p in days.get(day, []) if p[ix] is not None]
        return st.mean(v) if v else None

    def pct(v):
        return None if v is None else round(100 * max(0.0, min(1.0, (v - dry_v) / (full_v - dry_v))))

    om_rain = dict(zip(om["daily"]["time"], om["daily"]["precipitation_sum"])).get(rain_day)
    today = datetime.date.today().isoformat()
    soil = {day: {"top": mean(0, day), "deep": mean(1, day)} for day in sorted(days)}
    for day, s in soil.items():
        s["pct"] = pct(s["top"])
    peak_sept = max((dd for dd in soil if "2026-09-09" <= dd < rain_day and soil[dd]["pct"] is not None),
                    key=lambda dd: soil[dd]["top"])
    before = d_add(rain_day, -1)
    after = [dd for dd in soil if dd >= rain_day and soil[dd]["pct"] is not None][:4]
    peak_after = max(after, key=lambda dd: soil[dd]["pct"])
    nxt = d_add(peak_after, 1)

    # ── pragovi in zamiki ──
    sp = {s["id"]: s for s in rules["species"]}
    thr = {sid: float(sp[sid]["rain_7d_min"]) for sid, _ in SPECIES_SHOW}
    lags = {}
    for s in rules["species"]:
        lags.setdefault(s["ecology"], set()).add((int(s["fruiting_lag_days"]["min"]),
                                                  int(s["fruiting_lag_days"]["max"])))
    for e, v in lags.items():
        assert len(v) == 1, f"zamik skupine {e} ni enoten: {v}"
        lags[e] = next(iter(v))

    return {
        "today": today, "rain_day": rain_day, "rain_mm": rain_mm, "event_mm": event_mm,
        "pre14": pre14, "n_dry": n_dry, "last_wet": last_wet, "last_wet_mm": last_wet_mm,
        "sept_sum": sept_sum, "home": home["name"], "dry_v": dry_v, "full_v": full_v,
        "soil": soil, "peak_sept": peak_sept, "before": before, "after": after,
        "peak_after": peak_after, "nxt": nxt, "om_rain": om_rain, "rain_hist": rain, "thr": thr, "lags": lags,
    }


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    t = f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'
    return f'<div class="table-scroll" tabindex="0">{t}</div>'


# ── grafi: statični SVG (delujejo brez JS), JS doda samo opis ob prehodu miške ──
C_RAIN, C_SOIL = "#3987e5", "#8e6fd8"      # validate_palette.js --mode dark, surface #0a0f1c: vsi testi PASS
C_GROUP = {"razkrojevalka": "#3987e5", "lesna": "#d95926", "mikorizna": "#199e70"}  # kot v članku o dežu 8.–10. 10.
GRID = "rgba(255,255,255,.09)"
TXT = "var(--muted)"

CHART_CSS = """<style>
.sg-fig{position:relative;margin:1.4rem 0 .4rem}
.sg-fig svg{width:100%;height:auto;display:block}
.sg-fig text{font-family:'JetBrains Mono',monospace;font-size:11px;fill:var(--muted)}
.sg-fig .sg-t{font-size:12px;fill:var(--text,#e8ecef)}
.sg-fig .hit{fill:transparent;cursor:crosshair}
.sg-tip{position:absolute;pointer-events:none;background:var(--card-bg,#111827);border:1px solid var(--card-border,#2a333c);border-radius:8px;padding:.45rem .6rem;font-size:.78rem;line-height:1.4;display:none;z-index:3;white-space:nowrap}
.sg-cap{font-size:.8rem;color:var(--muted);margin:.2rem 0 1.4rem}
.sg-det{margin:.2rem 0 1.4rem;font-size:.88rem}.sg-det summary{cursor:pointer;color:var(--muted)}
</style>"""

CHART_JS = """<script>
(function(){
var f=document.getElementById('sg-a');if(!f)return;
var tip=f.querySelector('.sg-tip'),svg=f.querySelector('svg'),cx=f.querySelector('.sg-cross');
function show(e){var t=e.target;if(!t.classList||!t.classList.contains('hit'))return;
 var r=f.getBoundingClientRect(),x=e.clientX-r.left,s=t.getAttribute('data-s'),fc=t.getAttribute('data-f')==='1';
 tip.innerHTML='<strong>'+t.getAttribute('data-d')+'</strong><br>dež (postaja): '+t.getAttribute('data-r')+' mm'+
  '<br>vlaga tal (model): '+(s===''?'–':s+' %')+(fc?' <em>(napoved)</em>':'');
 tip.style.display='block';var w=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(r.width-w,x+12))+'px';tip.style.top='8px';
 cx.setAttribute('x1',t.getAttribute('data-x'));cx.setAttribute('x2',t.getAttribute('data-x'));cx.style.display='block'}
function hide(){tip.style.display='none';cx.style.display='none'}
svg.addEventListener('pointermove',show);svg.addEventListener('pointerleave',hide);
})();
</script>"""


def _fmt_day(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day}. {d.month}."


def chart_rain_soil(D):
    """Dve plošči z isto časovno osjo (NE dvojna os): zgoraj dež postaje, spodaj modelska vlaga tal."""
    rd = D["rain_day"]
    S = D["soil"]
    rain = dict(D["rain_hist"])
    rain[rd] = D["rain_mm"]
    first = d_add(rd, -30)
    last = D["after"][-1]
    days = []
    d = first
    while d <= last:
        days.append(d)
        d = d_add(d, 1)
    n = len(days)
    W, H = 720, 420
    L, R = 46, 22
    step = (W - L - R) / (n - 1)
    X = lambda i: L + i * step
    ry0, rh = 30, 96            # dež
    sy0, sh = 214, 150          # vlaga tal
    rmax = 90.0
    Yr = lambda v: ry0 + rh - rh * min(v, rmax) / rmax
    Ys = lambda v: sy0 + sh - sh * v / 100.0
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Dež na postaji IREICA1 in modelska vlaga tal od {_fmt_day(first)} do {_fmt_day(last)}">']
    # mreža + osi
    for v in (0, 30, 60, 90):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Yr(v):.1f}" y2="{Yr(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{L - 6}" y="{Yr(v) + 4:.1f}" text-anchor="end">{v}</text>')
    for v in (0, 50, 100):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Ys(v):.1f}" y2="{Ys(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{L - 6}" y="{Ys(v) + 4:.1f}" text-anchor="end">{v}</text>')
    o.append(f'<text class="sg-t" x="{L}" y="16">Dež na postaji IREICA1 (mm na dan)</text>')
    o.append(f'<text class="sg-t" x="{L}" y="{sy0 - 22}">Vlaga tal 3–9 cm, modelska ocena (% lestvice modela)</text>')
    # dež: stolpci
    bw = max(3.0, step * 0.68)
    for i, dd in enumerate(days):
        v = rain.get(dd)
        if v is None or dd > rd:
            continue
        h = max(0.0, Yr(0) - Yr(v))
        if v > 0:
            o.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{Yr(v):.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{C_RAIN}"/>')
    # izpostavljene oznake dežja
    for dd, anchor in ((max((k for k in days if k < rd and k in rain), key=lambda k: rain[k]), "middle"), (rd, "middle")):
        i = days.index(dd)
        o.append(f'<text x="{X(i):.1f}" y="{Yr(rain[dd]) - 5:.1f}" text-anchor="{anchor}">{num(rain[dd])}</text>')
    # navpična oznaka dežja
    ir = days.index(rd)
    o.append(f'<line x1="{X(ir):.1f}" x2="{X(ir):.1f}" y1="{ry0}" y2="{sy0 + sh}" stroke="{TXT}" stroke-dasharray="3 4" opacity=".7"/>'
             f'<text x="{X(ir) - 5:.1f}" y="{ry0 + 12}" text-anchor="end">dež {d_short(rd)}</text>')
    # vlaga tal: polna črta do danes, črtkana naprej
    today = D["today"]
    pts = [(i, S[dd]["pct"]) for i, dd in enumerate(days) if dd in S and S[dd]["pct"] is not None]
    solid = [(i, v) for i, v in pts if days[i] < today]
    dashed = [(i, v) for i, v in pts if days[i] >= today]
    if solid and dashed:
        dashed = [solid[-1]] + dashed
    pl = lambda a: " ".join(f"{X(i):.1f},{Ys(v):.1f}" for i, v in a)
    if solid:
        o.append(f'<polyline points="{pl(solid)}" fill="none" stroke="{C_SOIL}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    if dashed:
        o.append(f'<polyline points="{pl(dashed)}" fill="none" stroke="{C_SOIL}" stroke-width="2" stroke-dasharray="5 4" stroke-linecap="round"/>')
    # neposredne oznake vlage tal
    def lab(dd, dy=-8, anchor="middle"):
        if dd in days and dd in S:
            i = days.index(dd)
            o.append(f'<circle cx="{X(i):.1f}" cy="{Ys(S[dd]["pct"]):.1f}" r="3.5" fill="{C_SOIL}" stroke="var(--bg,#0a0f1c)" stroke-width="2"/>'
                     f'<text x="{X(i) + (6 if anchor == "start" else -6 if anchor == "end" else 0):.1f}" y="{Ys(S[dd]["pct"]) + dy:.1f}" text-anchor="{anchor}">{S[dd]["pct"]} %</text>')
    lab(D["peak_sept"], dy=-9, anchor="start")
    lab(D["before"], dy=-9, anchor="end")
    lab(D["peak_after"], dy=-9)
    # x os: vsakih 5 dni
    for i, dd in enumerate(days):
        if (len(days) - 1 - i) % 5 == 0:
            o.append(f'<text x="{X(i):.1f}" y="{sy0 + sh + 18}" text-anchor="{"end" if i == n - 1 else "middle"}">{_fmt_day(dd)}</text>')
    # prehodna črta + zadetne površine
    o.append(f'<line class="sg-cross" x1="0" x2="0" y1="{ry0}" y2="{sy0 + sh}" stroke="{TXT}" style="display:none"/>')
    for i, dd in enumerate(days):
        r_ = rain.get(dd) if dd <= rd else None
        s_ = S[dd]["pct"] if dd in S and S[dd]["pct"] is not None else None
        o.append(f'<rect class="hit" x="{X(i) - step / 2:.1f}" y="{ry0}" width="{step:.1f}" height="{sy0 + sh - ry0}" '
                 f'data-x="{X(i):.1f}" data-d="{_fmt_day(dd)}" data-r="{num(r_) if r_ is not None else "–"}" '
                 f'data-s="{"" if s_ is None else s_}" data-f="{1 if dd >= today else 0}"/>')
    o.append("</svg>")
    return (CHART_CSS + f'<figure class="sg-fig" id="sg-a">{"".join(o)}<div class="sg-tip"></div></figure>'
            f'<p class="sg-cap">Zgoraj izmerjen dež, spodaj modelska vlaga tal na isti časovni osi. Črtkani del vlage tal je napoved modela. '
            f'Dež 10. in 11. 9. je zaradi lestvice (do 90 mm) najvišji stolpec. Vlaga tal ni meritev postaje.</p>' + CHART_JS)


def chart_windows(D):
    """Okna po dežju za tri skupine (isti zamiki kot v tabeli)."""
    rd = D["rain_day"]
    L_ = D["lags"]
    start, end = d_add(rd, -1), d_add(rd, 19)
    ndays = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days
    W, H = 720, 210
    Lm, R = 150, 70
    step = (W - Lm - R) / ndays
    X = lambda dd: Lm + (datetime.date.fromisoformat(dd) - datetime.date.fromisoformat(start)).days * step
    rows = [("razkrojevalka", "Razkrojevalke"), ("lesna", "Lesne vrste"), ("mikorizna", "Mikorizne vrste")]
    top, rh = 34, 40
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Okna rasti po dežju {d_short(rd)} za tri skupine gob">']
    for k in range(0, ndays + 1, 3):
        dd = d_add(start, k)
        o.append(f'<line x1="{X(dd):.1f}" x2="{X(dd):.1f}" y1="{top - 6}" y2="{top + rh * 3}" stroke="{GRID}"/>'
                 f'<text x="{X(dd):.1f}" y="{top + rh * 3 + 18}" text-anchor="middle">{_fmt_day(dd)}</text>')
    for j, (e, name) in enumerate(rows):
        a, b = L_[e]
        d0, d1 = d_add(rd, a), d_add(rd, b)
        y = top + j * rh + 6
        x0, x1 = X(d0), X(d_add(d1, 1))
        o.append(f'<text class="sg-t" x="{Lm - 10}" y="{y + 16}" text-anchor="end">{name}</text>'
                 f'<rect x="{x0:.1f}" y="{y}" width="{x1 - x0:.1f}" height="22" rx="4" fill="{C_GROUP[e]}"/>'
                 f'<text x="{x1 + 8:.1f}" y="{y + 16}">{d_rng(d0, d1)}</text>')
    xt = X(D["today"]) if start <= D["today"] <= end else None
    if xt is not None:
        o.append(f'<line x1="{xt:.1f}" x2="{xt:.1f}" y1="{top - 6}" y2="{top + rh * 3}" stroke="{TXT}" stroke-dasharray="3 4"/>'
                 f'<text x="{xt:.1f}" y="{top - 12}" text-anchor="middle">danes</text>')
    xr = X(rd)
    o.append(f'<line x1="{xr:.1f}" x2="{xr:.1f}" y1="{top - 6}" y2="{top + rh * 3}" stroke="{TXT}" opacity=".7"/>'
             f'<text x="{xr:.1f}" y="{top - 24}" text-anchor="middle">dež {d_short(rd)}</text>')
    o.append("</svg>")
    return (f'<figure class="sg-fig">{"".join(o)}</figure>'
            f'<p class="sg-cap">Okno pomeni, da je dež trosnjak lahko sprožil, ne da je ta zrasel. Zamiki so iz pravil vrst v gobarskem modelu.</p>')


def daily_table(D):
    rd = D["rain_day"]
    rain = dict(D["rain_hist"])
    rain[rd] = D["rain_mm"]
    S = D["soil"]
    rows = []
    d = d_add(rd, -30)
    while d <= D["after"][-1]:
        r_ = rain.get(d) if d <= rd else None
        s_ = S.get(d, {}).get("pct")
        rows.append([d_short(d), "–" if r_ is None else num(r_), "–" if s_ is None else f"{s_} %"])
        d = d_add(d, 1)
    return ('<details class="sg-det"><summary>Podatki grafa po dnevih</summary>'
            + table(["Datum", "Dež (mm)", "Vlaga tal (model)"], rows) + "</details>")


def build_article(D):
    S = D["soil"]
    rd = D["rain_day"]
    rain = D["rain_mm"]
    wd = WEEKDAY_NOM[datetime.date.fromisoformat(rd).weekday()]
    wd_acc = WEEKDAY[datetime.date.fromisoformat(rd).weekday()]
    thr_j = D["thr"]["boletus_edulis"]
    share_j = round(100 * rain / thr_j)
    s_before = S[D["before"]]["pct"]
    s_peak_sept = S[D["peak_sept"]]["pct"]
    s_peak = S[D["peak_after"]]["pct"]
    last_day = D["after"][-1]
    s_last = S[last_day]["pct"]
    peak_days = [dd for dd in D["after"] if S[dd]["pct"] == s_peak]
    peak_txt = (d_short(peak_days[0]) if len(peak_days) == 1
                else d_rng(peak_days[0], peak_days[-1]))
    deep_pct = round(100 * max(0.0, min(1.0, (S[D["peak_after"]]["deep"] - D["dry_v"]) / (D["full_v"] - D["dry_v"]))))
    gap_days = (datetime.date.fromisoformat(D["before"]) - datetime.date.fromisoformat(D["peak_sept"])).days
    between = round(sum(v for k, v in D["rain_hist"].items() if D["peak_sept"] < k <= D["before"]), 1)
    deep_b, deep_a = S[D["before"]]["deep"], S[D["peak_after"]]["deep"]
    need = max(0.0, thr_j - rain)
    L = D["lags"]
    win = {e: d_rng(d_add(rd, L[e][0]), d_add(rd, L[e][1])) for e in L}

    lead = (f"{wd.capitalize()}, {d_long(rd)}, je bil na postaji IREICA1 prvi pravi dež po {D['n_dry']} dneh: "
            f"padlo je {num(rain)} mm (zaokroženo 10). V prejšnjih 14 dneh skupaj le {num(D['pre14'])} mm. Gobarski model za jurčka "
            f"šteje 25 mm v sedmih dneh, torej je padlo {share_j} % praga. A število milimetrov ni cela zgodba: "
            f"po modelski oceni so bila tla pred dežjem skoraj povsem suha ({s_before} % na lestvici modela), "
            f"tak dež pa zmoči predvsem vrhnjo plast. Zato jurčki in lisičke še počakajo.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Padlo {d_short(rd)}</div><div class="ms-val">{num(rain)} mm</div><div class="ms-sub">postaja IREICA1</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Prej 14 dni</div><div class="ms-val">{num(D["pre14"])} mm</div><div class="ms-sub">skupaj</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Prag za jurčka</div><div class="ms-val">{int(thr_j)} mm</div><div class="ms-sub">v 7 dneh</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Vlaga tal pred dežjem</div><div class="ms-val">{s_before} %</div><div class="ms-sub">modelska ocena</div></div>'
             '</div>')

    rows1 = []
    for sid, name in SPECIES_SHOW:
        t = D["thr"][sid]
        rows1.append([name, f"{int(t)} mm", f"{num(rain)} mm", f"{round(100 * rain / t)} %"])
    ev = ""
    sec1 = [
        stats,
        (f"V gobarskem modelu mora v sedmih dneh pasti vsaj toliko dežja, kot zahteva vrsta. Jurček potrebuje {int(thr_j)} mm, "
         f"lisička {int(D['thr']['cantharellus_cibarius'])} mm, marela {int(D['thr']['macrolepiota_procera'])} mm. "
         f"Dež {d_short(rd)} je tako izpolnil od tretjine do polovice teh pragov.{ev}"),
        table(["Vrsta", "Prag (7 dni)", f"Padlo do {d_short(rd)}", "Delež praga"], rows1),
        (f"Za primerjavo: 10. in 11. septembra je padlo {num(D['sept_sum'])} mm, kar je skoraj petkrat prag za jurčka. "
         f"Prej je zadnjih {D['n_dry']} {dni(D['n_dry'])} vsak dan padlo manj kot 1 mm "
         f"(zadnji večji dež: {d_short(D['last_wet'])}, {num(D['last_wet_mm'])} mm)."),
    ]

    ROWS_SOIL = []
    picks = [D["peak_sept"], d_add(D["peak_sept"], 16), D["before"]] + D["after"]
    seen = set()
    for dd in picks:
        if dd in seen or dd not in S or S[dd]["pct"] is None:
            continue
        seen.add(dd)
        note = ""
        if dd == D["peak_sept"]:
            note = "vrh po septembrskem nalivu"
        elif dd == D["before"]:
            note = "dan pred dežjem"
        elif dd == rd:
            note = "dan dežja"
        elif dd > D["today"]:
            note = "napoved modela"
        elif dd == D["today"]:
            note = "danes (deloma napoved)"
        ROWS_SOIL.append([d_short(dd), f"{S[dd]['pct']} %", f"{S[dd]['top']:.3f}".replace(".", ","), note])

    sec2 = [
        (f"Postaja vlage tal ne meri. Spodnje številke so <strong>modelska ocena</strong> Open-Meteo za plast 3–9 cm "
         f"na območju {D['home']}, preračunana na lestvico gobarskega modela: 0 % pomeni {num(D['dry_v'], 2)} m³/m³ "
         f"ali manj, 100 % pa {num(D['full_v'], 2)} m³/m³ ali več."),
        chart_rain_soil(D),
        daily_table(D),
        table(["Datum", "Vlaga tal", "m³/m³", "Opomba"], ROWS_SOIL),
        (f"Po septembrskem nalivu je bila vrhnja plast po modelu povsem namočena ({s_peak_sept} %). Do dneva pred dežjem "
         f"je v {gap_days} dneh, ko je padlo skupaj le {num(between)} mm, upadla na <strong>{s_before} %</strong>. Dež {d_short(rd)} jo je "
         f"po modelu dvignil na {s_peak} % ({peak_txt}), "
         + (f"do {d_short(last_day)} pa naj bi spet padla na {s_last} %." if s_last is not None and s_last < s_peak else
            "kar se do konca napovednega okna ne spremeni.")),
        (f"Globlja plast (9–27 cm) skoraj ne reagira: {num(deep_b, 3)} → {num(deep_a, 3)} m³/m³. Na isti lestvici je to {deep_pct} %: takle dež se vpije v prvih "
         f"centimetrih. Mikorizni micelij seže globlje od zgornjih nekaj centimetrov, zato je za jurčke pomembno, "
         f"koliko vode pride globlje, ne samo ali je zgornja plast kratko mokra."),
        ('<div class="disclaimer">Vlaga tal je model, ne meritev.'
         + (f' Open-Meteo je za {d_long(rd)} ocenil {num(D["om_rain"])} mm dežja, postaja pa jih je izmerila {num(rain)}, '
            'zato so vrednosti po dežju lahko preoptimistične.' if D["om_rain"] is not None and D["om_rain"] - rain >= 2 else '')
         + ' Gobarski indeks na strani uporablja isto vlago tal.</div>'),
    ]

    rows3 = []
    for e, name, ex in ECO_ROWS:
        a, b = L[e]
        rows3.append([name, ex, f"{a}–{b} dni", win[e]])
    sec3 = [
        (f"Gobe ne zrastejo naslednji dan: vsaka skupina potrebuje čas od dežja do trosnjaka. Model zamike bere "
         f"iz pravil vrst (<code>species_rules.yaml</code>)."),
        chart_windows(D),
        table(["Skupina", "Primeri", "Zamik po dežju", f"Okno po dežju {d_short(rd)}"], rows3),
        (f"Okno pomeni, da je dež trosnjak <em>lahko</em> sprožil, ne da je ta zrasel. Pri mikoriznih vrstah je okno "
         f"{win['mikorizna']}, torej se ne odpre pred {d_long(d_add(rd, L['mikorizna'][0]))}. Pri razkrojevalkah je zamik krajši "
         f"({L['razkrojevalka'][0]}–{L['razkrojevalka'][1]} dni), a tudi tam pomaga le, če so tla dovolj vlažna za rast."),
    ]

    sec4 = [
        (f"Po modelu in izmerjenem dežju je slika taka:"),
        ("<ul>"
         f"<li><strong>Marela, ostrigarji in druge vrste s krajšim zamikom:</strong> v oknu {win['razkrojevalka']} (razkrojevalke) "
         f"in {win['lesna']} (lesne vrste) je okno odprto. Vrhnja plast tal je po modelu po dežju deloma namočena ({s_peak} %), a model je dež ocenil višje od meritve, zato je rast verjetnejša tam, kjer se vlaga dlje drži: v senci, ob potokih, na severnih pobočjih.</li>"
         f"<li><strong>Jurčki in lisičke:</strong> ne prej kot {d_long(d_add(rd, L['mikorizna'][0]))}. Dež je izpolnil le "
         f"{share_j} % praga za jurčka in globlja plast tal ostaja suha ({deep_pct} % na lestvici modela), zato po modelu ni razloga za veliko rast, razen če pride še dež.</li>"
         f"<li><strong>Kaj bi sliko spremenilo:</strong> še vsaj {int(round(need))} mm v sedmih dneh bi jurčku pripeljalo prag. "
         "Napovedi dežja so negotove, zato glej tekoči indeks.</li>"
         "</ul>"),
        ('Današnji indeks po vrstah in območjih je na <a href="/gobarska-napoved/danes/" style="color:var(--blue)">'
         'meteorec.si/gobarska-napoved/danes</a>. Če greš v gozd, nam lahko pustiš opažanje (območje, ne točne lokacije), '
         'saj brez tvojih najdb ne vemo, ali model drži.'),
    ]

    src = ('<div class="sources">Viri: postaja IREICA1, Rečica ob Savinji (dež: <code>history.json</code> in urni podatki); '
           'gobarski model (praga in zamiki: <code>species_rules.yaml</code>); vlaga tal: Open-Meteo, modelska ocena za '
           f'območje {D["home"]}. Posnetek ob uri zajema, današnji izračun je na '
           '<a href="/gobarska-napoved/" style="color:var(--blue)">meteorec.si/gobarska-napoved</a>.<br>'
           'Postaja IREICA1, Rečica ob Savinji · <a href="/" style="color:var(--blue)">meteorec.si</a></div>')

    return {
        "title": "Padlo je 10 mm na suha tla. Zakaj jurčki še počakajo?",
        "meta_description": (f"{num(rain)} mm dežja po {D['n_dry']} suhih dneh je bilo {share_j} % praga za jurčka. "
                             f"Vlaga tal pred dežjem: {s_before} % (model). Jurčki najprej {d_long(d_add(rd, L['mikorizna'][0]))}."),
        "tags": ["gobe", "gobarski indeks", "dež", "vlaga tal", "oktober", "2026"],
        "section_label": "Gobarski model",
        "og_photo": "gobe-lastna",
        "og_accent_hex": "#34d399",
        "lead": lead,
        "sources_note": CSS + src,
        "sections": [
            {"label": "01 — dež", "heading": "Koliko je padlo in koliko bi moralo", "id": "dez", "paragraphs": sec1},
            {"label": "02 — tla", "heading": "Tla so bila pred dežjem skoraj suha", "id": "tla", "paragraphs": sec2},
            {"label": "03 — zamik", "heading": "Kdo pride prvi in kdo šele čez dva tedna", "id": "zamik", "paragraphs": sec3},
            {"label": "04 — nabiranje", "heading": "Kaj to pomeni za v gozd", "id": "gozd", "paragraphs": sec4},
        ],
    }


def main():
    dry = "--dry-run" in sys.argv
    wire = "--wire" in sys.argv
    rd = sys.argv[sys.argv.index("--rain-day") + 1] if "--rain-day" in sys.argv else RAIN_DAY
    D = build_data(rd)
    article = build_article(D)
    if dry:
        print("TITLE:", article["title"])
        print("\nLEAD:", article["lead"])
        for s in article["sections"]:
            print("\n##", s["heading"])
            for p in s["paragraphs"]:
                if p.lstrip().startswith("<table") or 'class="table-scroll"' in p:
                    rows = re.findall(r"<tr>(.*?)</tr>", p, re.S)
                    for r in rows:
                        cells = re.findall(r"<t[hd]>(.*?)</t[hd]>", r, re.S)
                        print("  | " + " | ".join(re.sub(r"<[^>]+>", "", c) for c in cells))
                else:
                    print(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", p)).strip())
        print("\nMETA:", article["meta_description"], len(article["meta_description"]))
        return
    ftp.TODAY = datetime.date.today().isoformat()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    slug, html, entry, og_meta = ftp.build_html(
        article, YEAR, 10, now_utc, slug=SLUG, back=("/blog/", "← Vsi članki"),
        og_title="Padlo je 10 mm\nna suha tla", meta_note="gobarski model",
        nav_label="O postaji", nav_href="/o-postaji.html")
    with open(os.path.join(ROOT, "blog", f"{slug}.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        try:
            from generate_og_images import make_og
            make_og({"slug": slug, **og_meta})
        except Exception as e:  # noqa: BLE001
            print(f"⚠ OG slika preskočena: {e}")
        from generate_monthly_post import wire_all
        wire_all(entry, entry["url"])
        print("✓ blog.json, blog/index.html, sitemap.xml, blog/rss.xml osveženi.")


if __name__ == "__main__":
    main()
