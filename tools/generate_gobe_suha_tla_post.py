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
SLUG = "padlo-10-mm-na-suha-tla-zakaj-jurckov-se-ni-1009"
RAIN_DAY = "2026-10-08"
PHOTO_DATE = "2026-09-28"   # datum posnetka (iz fotografije); EXIF je pri obdelavi odstranjen
PHOTO_DIR = os.path.join("img", "blog", "padlo-10-mm-na-suha-tla-zakaj-jurckov-se-ni-1009")
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
SPECIES_SHOW = [("boletus_edulis", "Jurček"), ("cantharellus_cibarius", "Lisička"),
                ("macrolepiota_procera", "Orjaški dežnik (marela)"),
                ("hydnum_repandum", "Rumeni ježek"), ("pleurotus_ostreatus", "Bukov ostrigar")]
ECO_ROWS = [("razkrojevalka", "Razkrojevalke stelje in travinja", "marela, kukmaki"),
            ("lesna", "Lesne vrste", "bukov ostrigar, bezgova uhljevka"),
            ("mikorizna", "Mikorizne vrste", "jurček, rumeni ježek")]
CSS = """<style>
.mini-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.7rem;margin:1.4rem 0 2rem}
.mini-stat{background:var(--card-bg);border:1px solid var(--card-border);border-radius:12px;padding:.9rem .8rem;text-align:center}
.ms-label{font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-family:'JetBrains Mono',monospace}
.ms-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.4rem;line-height:1.1;margin:.18rem 0 .1rem;color:var(--cyan)}
.ms-sub{font-size:.72rem;color:var(--muted)}
@media(max-width:640px){.mini-stat-grid{grid-template-columns:repeat(2,1fr)}}
.disclaimer{background:rgba(239,68,68,.06);border:1px solid var(--card-border);border-radius:10px;padding:.8rem 1rem;margin:1.2rem 0;font-size:.85rem;color:var(--muted)}
.data-table{width:100%;border-collapse:collapse;font-size:.92rem;margin:.2rem 0}
.data-table th{text-align:left;font-weight:600;font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);padding:.5rem .7rem;border-bottom:1px solid var(--card-border);white-space:nowrap}
.data-table td{padding:.62rem .7rem;border-bottom:1px solid rgba(255,255,255,.06)}
.data-table tr:last-child td{border-bottom:0}
.table-scroll{overflow-x:auto;margin:1.2rem 0 1.6rem;border:1px solid var(--card-border);border-radius:12px;background:var(--card-bg)}
.sg-photo{margin:1.6rem auto 1.8rem;max-width:420px}
.sg-photo img{display:block;width:100%;height:auto;border-radius:14px;border:1px solid var(--card-border)}
.sg-photo figcaption{font-size:.8rem;color:var(--muted);margin-top:.6rem;line-height:1.5}
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
    # zamik skupine = najpogostejši v pravilih; vrste z drugačnim (ročno umerjenim) zamikom so svoja vrstica
    from collections import Counter
    cnt = {}
    for sp_ in rules["species"]:
        cnt.setdefault(sp_["ecology"], Counter())[(int(sp_["fruiting_lag_days"]["min"]),
                                                  int(sp_["fruiting_lag_days"]["max"]))] += 1
    lags = {e: c.most_common(1)[0][0] for e, c in cnt.items()}
    lag_lis = (int(sp["cantharellus_cibarius"]["fruiting_lag_days"]["min"]),
               int(sp["cantharellus_cibarius"]["fruiting_lag_days"]["max"]))
    lag_jur = (int(sp["boletus_edulis"]["fruiting_lag_days"]["min"]),
               int(sp["boletus_edulis"]["fruiting_lag_days"]["max"]))
    assert lag_jur == lags["mikorizna"], f"jurček ni več na skupinskem zamiku: {lag_jur} proti {lags['mikorizna']}"

    return {
        "today": today, "rain_day": rain_day, "rain_mm": rain_mm,
        "pre14": pre14, "n_dry": n_dry, "last_wet": last_wet, "last_wet_mm": last_wet_mm,
        "sept_sum": sept_sum, "home": home["name"], "dry_v": dry_v, "full_v": full_v,
        "soil": soil, "peak_sept": peak_sept, "before": before, "after": after,
        "peak_after": peak_after, "nxt": nxt, "om_rain": om_rain, "rain_hist": rain, "thr": thr, "lags": lags, "lag_lis": lag_lis,
    }


def table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    t = f'<table class="data-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'
    return f'<div class="table-scroll" tabindex="0">{t}</div>'


# ── grafi: statični SVG (delujejo brez JS), JS doda samo opis ob prehodu miške ──
C_RAIN, C_SOIL = "#3987e5", "#e8ecef"      # dež: validirana modra; vlaga tal: nevtralna svetla (ni kategorija)
C_GROUP = {"razkrojevalka": "#8e6fd8", "lesna": "#d95926", "mikorizna": "#199e70"}  # validate_palette.js --mode dark, surface #0a0f1c: PASS; modre ni, ker je v grafu 1 dež
GRID = "rgba(255,255,255,.09)"
TXT = "var(--muted)"

CHART_CSS = """<style>
.sg-fig{position:relative;margin:1.4rem 0 .4rem}
.sg-fig svg{width:100%;height:auto;display:block}
.sg-fig text{font-family:'Inter',system-ui,sans-serif;font-size:13px;fill:var(--muted)}
.sg-fig .sg-t{font-size:15px;font-weight:700;fill:var(--text,#e8ecef)}
.sg-fig .sg-u{font-size:12px;fill:var(--muted)}
.sg-fig .sg-v{font-size:14px;font-weight:700;fill:var(--text,#e8ecef);paint-order:stroke;stroke:var(--bg,#0a0f1c);stroke-width:4px;stroke-linejoin:round}
.sg-fig .sg-dry{font-size:12px;fill:var(--muted)}
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
    W, H = 720, 440
    L, R = 50, 22
    step = (W - L - R) / (n - 1)
    X = lambda i: L + i * step
    ry0, rh = 52, 100           # dež
    sy0, sh = 252, 138          # vlaga tal
    rmax = 90.0
    Yr = lambda v: ry0 + rh - rh * min(v, rmax) / rmax
    Ys = lambda v: sy0 + sh - sh * v / 100.0
    today = D["today"]
    ir = days.index(rd)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Dež na postaji IREICA1 in modelska vlaga tal od {_fmt_day(first)} do {_fmt_day(last)}">',
         f'<defs><linearGradient id="sg-fill" x1="0" y1="0" x2="0" y2="1">'
         f'<stop offset="0" stop-color="{C_SOIL}" stop-opacity=".22"/><stop offset="1" stop-color="{C_SOIL}" stop-opacity="0"/>'
         f'</linearGradient></defs>']
    # razdobje brez dežja: senčeno čez obe plošči
    dry0 = days.index(d_add(D["last_wet"], 1)) if d_add(D["last_wet"], 1) in days else 0
    x0, x1 = X(dry0) - step / 2, X(ir) - step / 2
    o.append(f'<rect x="{x0:.1f}" y="{ry0 - 6}" width="{x1 - x0:.1f}" height="{sy0 + sh - ry0 + 6}" rx="8" fill="rgba(255,255,255,.035)"/>')
    o.append(f'<text class="sg-dry" x="{(x0 + x1) / 2:.1f}" y="{ry0 + 8}" text-anchor="middle">{D["n_dry"]} dni skoraj brez dežja</text>')
    # naslova plošč
    o.append(f'<text class="sg-t" x="{L}" y="22">Dež na postaji IREICA1</text>'
             f'<text class="sg-u" x="{L}" y="38">mm na dan, meritev</text>')
    o.append(f'<text class="sg-t" x="{L}" y="{sy0 - 46}">Vlaga tal 3–9 cm</text>'
             f'<text class="sg-u" x="{L}" y="{sy0 - 30}">% lestvice gobarskega modela, modelska ocena</text>')
    # mreža
    for v in (0, 30, 60, 90):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Yr(v):.1f}" y2="{Yr(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{L - 8}" y="{Yr(v) + 4:.1f}" text-anchor="end">{v}</text>')
    for v in (0, 50, 100):
        o.append(f'<line x1="{L}" x2="{W - R}" y1="{Ys(v):.1f}" y2="{Ys(v):.1f}" stroke="{GRID}"/>'
                 f'<text x="{L - 8}" y="{Ys(v) + 4:.1f}" text-anchor="end">{v}</text>')
    # dež: stolpci
    bw = max(5.0, step * 0.62)
    for i, dd in enumerate(days):
        v = rain.get(dd)
        if v is None or dd > rd or v <= 0:
            continue
        h = max(2.0, Yr(0) - Yr(v))
        o.append(f'<rect x="{X(i) - bw / 2:.1f}" y="{Yr(0) - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="3" fill="{C_RAIN}"/>')
    big = max((k for k in days if k < rd and k in rain), key=lambda k: rain[k])
    second = d_add(big, 1) if d_add(big, 1) in rain and rain[d_add(big, 1)] > 20 else None
    ib = days.index(big)
    o.append(f'<text class="sg-v" x="{X(ib) - bw / 2 - 5:.1f}" y="{Yr(rain[big]) + 12:.1f}" text-anchor="end">{num(rain[big])}</text>')
    if second:
        i2 = days.index(second)
        o.append(f'<text class="sg-v" x="{X(i2) + bw / 2 + 5:.1f}" y="{Yr(rain[second]) + 12:.1f}" text-anchor="start">{num(rain[second])}</text>')
    o.append(f'<text class="sg-v" x="{X(ir):.1f}" y="{Yr(rain[rd]) - 7:.1f}" text-anchor="middle">{num(rain[rd])}</text>')
    # dan dežja
    o.append(f'<line x1="{X(ir):.1f}" x2="{X(ir):.1f}" y1="{ry0 - 6}" y2="{sy0 + sh}" stroke="{TXT}" stroke-dasharray="3 4" opacity=".8"/>')
    o.append(f'<text x="{X(ir) + 6:.1f}" y="{ry0 + 8}" text-anchor="start">dež {d_short(rd)}</text>')
    # vlaga tal: površina + črta (polna do danes, črtkana naprej)
    pts = [(i, S[dd]["pct"]) for i, dd in enumerate(days) if dd in S and S[dd]["pct"] is not None]
    solid = [(i, v) for i, v in pts if days[i] < today]
    dashed = [(i, v) for i, v in pts if days[i] >= today]
    if solid and dashed:
        dashed = [solid[-1]] + dashed
    pl = lambda a: " ".join(f"{X(i):.1f},{Ys(v):.1f}" for i, v in a)
    if solid:
        area = pl(solid) + f" {X(solid[-1][0]):.1f},{Ys(0):.1f} {X(solid[0][0]):.1f},{Ys(0):.1f}"
        o.append(f'<polygon points="{area}" fill="url(#sg-fill)"/>')
        o.append(f'<polyline points="{pl(solid)}" fill="none" stroke="{C_SOIL}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    if dashed:
        o.append(f'<polyline points="{pl(dashed)}" fill="none" stroke="{C_SOIL}" stroke-width="2.5" stroke-dasharray="2 6" stroke-linecap="round" opacity=".85"/>')
        mid = dashed[len(dashed) // 2]
        o.append(f'<text x="{X(dashed[-1][0]):.1f}" y="{Ys(0) - 8:.1f}" text-anchor="end">napoved</text>')

    def mark(dd, dx, dy, anchor):
        if dd in days and dd in S:
            i = days.index(dd)
            v = S[dd]["pct"]
            o.append(f'<circle cx="{X(i):.1f}" cy="{Ys(v):.1f}" r="5" fill="{C_SOIL}" stroke="var(--bg,#0a0f1c)" stroke-width="2.5"/>'
                     f'<text class="sg-v" x="{X(i) + dx:.1f}" y="{Ys(v) + dy:.1f}" text-anchor="{anchor}">{v} %</text>')
    mark(D["peak_sept"], 10, -10, "start")
    mark(D["before"], -10, -14, "end")
    mark(D["peak_after"], 0, -12, "middle")
    # x os
    for i, dd in enumerate(days):
        if (n - 1 - i) % 5 == 0:
            o.append(f'<text x="{X(i):.1f}" y="{sy0 + sh + 22}" text-anchor="{"end" if i == n - 1 else "middle"}">{_fmt_day(dd)}</text>')
    # prehodna črta + zadetne površine
    o.append(f'<line class="sg-cross" x1="0" x2="0" y1="{ry0 - 6}" y2="{sy0 + sh}" stroke="{TXT}" style="display:none"/>')
    for i, dd in enumerate(days):
        r_ = rain.get(dd) if dd <= rd else None
        s_ = S[dd]["pct"] if dd in S and S[dd]["pct"] is not None else None
        o.append(f'<rect class="hit" x="{X(i) - step / 2:.1f}" y="{ry0 - 6}" width="{step:.1f}" height="{sy0 + sh - ry0 + 6}" '
                 f'data-x="{X(i):.1f}" data-d="{_fmt_day(dd)}" data-r="{num(r_) if r_ is not None else "–"}" '
                 f'data-s="{"" if s_ is None else s_}" data-f="{1 if dd >= today else 0}"/>')
    o.append("</svg>")
    return (CHART_CSS + f'<figure class="sg-fig" id="sg-a">{"".join(o)}<div class="sg-tip"></div></figure>'
            f'<p class="sg-cap">Pikčasti del črte je napoved modela. Dež 10. in 11. 9. je zaradi lestvice (do 90 mm) najvišji stolpec. '
            f'Vlaga tal ni meritev postaje.</p>' + CHART_JS)


def chart_windows(D):
    """Okna po dežju za skupine (isti zamiki kot v pravilih gobarskega modela)."""
    rd = D["rain_day"]
    L_ = D["lags"]
    rows = [("razkrojevalka", "Razkrojevalke", "marela, kukmaki", L_["razkrojevalka"]),
            ("lesna", "Lesne vrste", "bukov ostrigar, uhljevka", L_["lesna"]),
            ("mikorizna", "Jurček, rumeni ježek", "mikorizni", L_["mikorizna"])]
    if D["lag_lis"] != L_["mikorizna"]:
        rows.append(("mikorizna", "Lisička", "mikorizna, krajši zamik", D["lag_lis"]))
    start, end = d_add(rd, -1), d_add(rd, 19)
    ndays = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(start)).days
    rh = 54
    top = 74
    W, H = 720, top + rh * len(rows) + 40
    Lm, R = 190, 82
    step = (W - Lm - R) / ndays
    X = lambda dd: Lm + (datetime.date.fromisoformat(dd) - datetime.date.fromisoformat(start)).days * step
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Okna rasti po dežju {d_short(rd)} za skupine gob">']
    o.append(f'<text class="sg-t" x="0" y="20">Kdaj po dežju lahko zrastejo</text>'
             f'<text class="sg-u" x="0" y="36">okno = zamik od dežja do trosnjaka, po pravilih modela</text>')
    for k in range(0, ndays + 1, 3):
        dd = d_add(start, k)
        o.append(f'<line x1="{X(dd):.1f}" x2="{X(dd):.1f}" y1="{top - 8}" y2="{top + rh * len(rows) - 6}" stroke="{GRID}"/>'
                 f'<text x="{X(dd):.1f}" y="{top + rh * len(rows) + 14}" text-anchor="middle">{_fmt_day(dd)}</text>')
    for j, (e, name, ex, lag) in enumerate(rows):
        a, b = lag
        d0, d1 = d_add(rd, a), d_add(rd, b)
        y = top + j * rh
        x0, x1 = X(d0), X(d_add(d1, 1))
        o.append(f'<text class="sg-t" x="0" y="{y + 14}">{name}</text>'
                 f'<text class="sg-u" x="0" y="{y + 31}">zamik {a}–{b} dni</text>'
                 f'<rect x="{x0:.1f}" y="{y + 2}" width="{x1 - x0:.1f}" height="28" rx="14" fill="{C_GROUP[e]}"/>'
                 f'<text class="sg-v" x="{x1 + 10:.1f}" y="{y + 21}">{d_rng(d0, d1)}</text>')
    xr = X(rd)
    o.append(f'<line x1="{xr:.1f}" x2="{xr:.1f}" y1="{top - 8}" y2="{top + rh * len(rows) - 6}" stroke="{TXT}" opacity=".8"/>'
             f'<text x="{xr - 6:.1f}" y="{top - 14}" text-anchor="end">dež {d_short(rd)}</text>')
    if start <= D["today"] <= end and D["today"] != rd:
        xt = X(D["today"])
        o.append(f'<line x1="{xt:.1f}" x2="{xt:.1f}" y1="{top - 8}" y2="{top + rh * len(rows) - 6}" stroke="{TXT}" stroke-dasharray="3 4"/>'
                 f'<text x="{xt + 6:.1f}" y="{top - 14}" text-anchor="start">danes</text>')
    o.append("</svg>")
    return (f'<figure class="sg-fig">{"".join(o)}</figure>'
            f'<p class="sg-cap">Okno pomeni, da je dež trosnjak lahko sprožil, ne da je ta zrasel.</p>')


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


def photo_html(D):
    n_photo = (datetime.date.fromisoformat(PHOTO_DATE) - datetime.date.fromisoformat(D["peak_sept"])).days
    return (f'<figure class="sg-photo"><img src="/{PHOTO_DIR.replace(os.sep, "/")}/koprenka.jpg" width="900" height="1200" '
            f'alt="Koprenka z vijoličnim klobukom in temnovijoličnimi lamelami v gozdni stelji">'
            f'<figcaption>Koprenka (<em>Cortinarius</em> sp.), posneto {d_long(PHOTO_DATE)}, {n_photo} dni po septembrskem nalivu. '
            f'Določitev po fotografiji ni zanesljiva, koprenk pa ne nabiramo za prehrano. Foto: Meteorec.</figcaption></figure>')


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
    if len(peak_days) == 1:
        peak_when = d_long(peak_days[0])
    else:
        a_, b_ = datetime.date.fromisoformat(peak_days[0]), datetime.date.fromisoformat(peak_days[-1])
        peak_when = f"{a_.day}. in {b_.day}. {seo.MES_GEN[b_.month]}" if len(peak_days) == 2 else f"od {d_long(peak_days[0])} do {d_long(peak_days[-1])}"
    deep_pct = round(100 * max(0.0, min(1.0, (S[D["peak_after"]]["deep"] - D["dry_v"]) / (D["full_v"] - D["dry_v"]))))
    gap_days = (datetime.date.fromisoformat(D["before"]) - datetime.date.fromisoformat(D["peak_sept"])).days
    between = round(sum(v for k, v in D["rain_hist"].items() if D["peak_sept"] < k <= D["before"]), 1)
    deep_b, deep_a = S[D["before"]]["deep"], S[D["peak_after"]]["deep"]
    need = max(0.0, thr_j - rain)
    L = D["lags"]
    win = {e: d_rng(d_add(rd, L[e][0]), d_add(rd, L[e][1])) for e in L}

    lead = (f"V {wd_acc}, {d_long(rd)}, je na postaji IREICA1 po {D['n_dry']} dneh znova konkretneje deževalo. "
            f"Izmerili smo {num(rain)} mm padavin, zaokroženo 10 mm. V predhodnih 14 dneh je skupaj padel le {num(D['pre14'])} mm dežja. "
            f"Gobarski model za jurčka zahteva {int(thr_j)} mm padavin v sedmih dneh, zato smo dosegli približno {share_j} % tega praga. "
            f"A sama količina dežja ne pove vsega. Po modelski oceni so bila tla pred dežjem skoraj povsem suha, "
            f"z vlažnostjo le {s_before} % na lestvici gobarskega modela. Takšna količina padavin navlaži predvsem vrhnjo plast tal. "
            f"Zato jurčkov in lisičk še ne gre pričakovati na vsakem koraku.")

    stats = ('<div class="mini-stat-grid">'
             f'<div class="mini-stat"><div class="ms-label">Padavine {d_short(rd)}</div><div class="ms-val">{num(rain)} mm</div><div class="ms-sub">postaja IREICA1</div></div>'
             f'<div class="mini-stat"><div class="ms-label">Prejšnjih 14 dni</div><div class="ms-val">{num(D["pre14"])} mm</div><div class="ms-sub">skupaj</div></div>'
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
        (f"Gobarski model za vsako vrsto upošteva prag padavin v sedemdnevnem obdobju. Za jurčka je ta prag {int(thr_j)} mm, "
         f"za lisičko {int(D['thr']['cantharellus_cibarius'])} mm, za marelo pa {int(D['thr']['macrolepiota_procera'])} mm. "
         f"Dež {d_long(rd)} je tako dosegel od približno tretjine do polovice količine, ki jo model zahteva za posamezne vrste."),
        table(["Vrsta", "Prag (7 dni)", f"Padlo do {d_short(rd)}", "Delež praga"], rows1),
        (f"Za primerjavo: v obilnem padavinskem obdobju, ki se je začelo 10. septembra, je v dveh dneh padlo {num(D['sept_sum'])} mm dežja. "
         f"To je skoraj petkrat toliko, kot gobarski model zahteva za jurčka v sedmih dneh. Pozneje je bilo padavin zelo malo. "
         f"Zadnji izrazitejši dež pred zdajšnjim je padel {d_long(D['last_wet'])}, ko je postaja izmerila {num(D['last_wet_mm'])} mm."),
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
        (f"Postaja IREICA1 vlage tal ne meri. Spodnje vrednosti so modelske ocene Open-Meteo za plast tal na globini 3–9 cm "
         f"na območju Rečice ob Savinji. Preračunane so na lestvico gobarskega modela: 0 % pomeni vsebnost vode {num(D['dry_v'], 2)} m³/m³ "
         f"ali manj, 100 % pa {num(D['full_v'], 2)} m³/m³ ali več."),
        chart_rain_soil(D),
        daily_table(D),
        (f"Po septembrskem nalivu je bila vlaga v vrhnji plasti po modelu na najvišji ravni lestvice ({s_peak_sept} %). "
         f"V naslednjih {gap_days} dneh je padlo skupaj le {num(between)} mm dežja, do {d_long(D['before'])} pa je vlažnost po modelu upadla na <strong>{s_before} %</strong>."),
        (f"Model nato kaže povečanje vlage: {d_long(rd)} na {S[rd]['pct']} %, "
         f"{peak_when} na {s_peak} %. "
         + (f"Do {d_long(last_day)} naj bi znova padla na {s_last} %." if s_last is not None and s_last < s_peak else
            "Do konca napovednega okna se to ne spremeni.")),
        (f"Globlja plast tal (9–27 cm) se odziva precej manj izrazito. Vsebnost vode se je po modelu spremenila le z {num(deep_b, 3)} na "
         f"{num(deep_a, 3)} m³/m³. Na lestvici gobarskega modela to ustreza približno {deep_pct} %."),
        (f"Podatki torej kažejo, da se je po dežju vlaga povečala predvsem v vrhnji plasti tal. Micelij mikoriznih gob sega tudi globlje, "
         f"zato je za jurčke pomembno, koliko vode pride do globljih plasti, ne le to, ali je površina tal za kratek čas mokra."),
        ('<div class="disclaimer"><em>Opomba:</em> Vlaga tal je modelska ocena, ne meritev.'
         + (f' Open-Meteo je za {d_long(rd)} napovedal {num(D["om_rain"])} mm dežja, postaja pa je izmerila {num(rain)} mm. '
            'Zato so lahko modelske ocene vlage po padavinah previsoke.' if D["om_rain"] is not None and D["om_rain"] - rain >= 2 else '')
         + ' Gobarski indeks na naši strani uporablja isto oceno vlage tal.</div>'),
    ]

    rows3 = []
    for e, name, ex in ECO_ROWS:
        a, b = L[e]
        rows3.append([name, ex, f"{a}–{b} dni", win[e]])
    lis_differs = D["lag_lis"] != L["mikorizna"]
    win_lis = d_rng(d_add(rd, D["lag_lis"][0]), d_add(rd, D["lag_lis"][1]))
    if lis_differs:
        rows3.append(["Lisička (mikorizna)", "navadna lisička", f"{D['lag_lis'][0]}–{D['lag_lis'][1]} dni", win_lis])
    sec3 = [
        (f"Gobe se po dežju ne pojavijo kar naslednji dan. Različne skupine potrebujejo različno dolgo, da razvijejo trosnjake. "
         f"Gobarski model te časovne zamike povzema v pravilih za posamezne vrste (<code>species_rules.yaml</code>)."),
        chart_windows(D),
        ("Navedeno časovno okno pomeni, da bi dež lahko spodbudil rast trosnjakov, ne pa, da se bodo ti v tem obdobju zagotovo pojavili."),
        (f"Pri jurčku in rumenem ježku se okno odpre šele {d_long(d_add(rd, L['mikorizna'][0]))} in traja do {d_long(d_add(rd, L['mikorizna'][1]))}. "
         + (f"Lisička ima po novih podatkih krajši zamik, od {D['lag_lis'][0]} do {D['lag_lis'][1]} dni, zato se njeno okno odpre že {d_long(d_add(rd, D['lag_lis'][0]))} "
            f"in traja do {d_long(d_add(rd, D['lag_lis'][1]))}. Model zanjo uporablja krajši zamik, ker so opažanja gob na iNaturalistu pokazala, da lisičke pogosto zrastejo že 6 do 8 dni po dežju. " if lis_differs else "")
         + f"Pri razkrojevalkah je zamik {'še ' if lis_differs else ''}krajši, od {L['razkrojevalka'][0]} do {L['razkrojevalka'][1]} dni, vendar tudi pri njih za rast potrebujejo dovolj vlažna tla."),
    ]

    sec4 = [
        ("Po meritvah in modelski oceni vlage je slika takšna:"),
        ("<ul>"
         f"<li><strong>Marele, ostrigarji in druge vrste s krajšim zamikom:</strong> časovno okno za razkrojevalke je {win['razkrojevalka']}, "
         f"za lesne vrste pa {win['lesna']} Vrhnja plast tal naj bi bila po dežju deloma navlažena, vendar je model napovedal več dežja, kot ga je postaja dejansko izmerila. "
         "Zato je smiselno najprej pogledati v senčnih legah, ob potokih in na severnih pobočjih, kjer se vlaga lahko zadrži dlje.</li>"
         f"<li><strong>Jurčki:</strong> po modelu se njihovo časovno okno ne odpre pred {d_long(d_add(rd, L['mikorizna'][0]))}. "
         f"Dež je dosegel le približno {share_j} % praga za jurčka, vlaga v globlji plasti tal pa na lestvici modela ostaja pri {deep_pct} %. "
         "Za zdaj torej ni podlage za pričakovanje množične rasti, razen če vmes pade še nekaj dežja.</li>"
         + (f"<li><strong>Lisičke:</strong> njihovo okno se odpre že {d_long(d_add(rd, D['lag_lis'][0]))}, vendar je dež dosegel le približno "
            f"{round(100 * rain / D['thr']['cantharellus_cibarius'])} % njihovega praga ({int(D['thr']['cantharellus_cibarius'])} mm). "
            "Tudi pri njih torej ni podlage za pričakovanje množične rasti, razen če pride še dež.</li>" if lis_differs else "")
         + f"<li><strong>Kaj bi spremenilo sliko:</strong> da bi jurček dosegel svoj prag, bi moralo v sedmih dneh pasti še vsaj približno {int(round(need))} mm dežja"
         + (f", za lisičko pa še vsaj približno {int(round(D['thr']['cantharellus_cibarius'] - rain))} mm" if lis_differs else "")
         + ". Ker so napovedi padavin negotove, spremljaj aktualni gobarski indeks.</li>"
         "</ul>"),
        ('Današnji indeks za posamezne vrste in območja je na <a href="/gobarska-napoved/danes/" style="color:var(--blue)">gobarski napovedi Meteorec</a>.'),
        ('Če greš v gozd, nam lahko sporočiš tudi svoje opažanje. Zadošča podatek o območju, natančne lokacije najdb pa ni treba razkrivati. '
         'Brez opažanj z različnih območij namreč težko preverimo, kako dobro se napoved ujema z dejanskim stanjem v gozdu.'),
    ]

    src = ('<div class="sources"><strong>Viri:</strong> postaja IREICA1 v Rečici ob Savinji (padavine: <code>history.json</code> in urni podatki), '
           'gobarski model (pragovi in časovni zamiki: <code>species_rules.yaml</code>) ter Open-Meteo (modelska ocena vlage tal za območje Rečice ob Savinji).'
           '<br><em>Modelske ocene niso meritve na terenu. Časovni zamiki in pragovi opisujejo pravila gobarskega modela, ne zagotavljajo pa, '
           'da se bodo trosnjaki pojavili v napovedanem obdobju.</em><br>'
           'Postaja IREICA1, Rečica ob Savinji · <a href="/" style="color:var(--blue)">meteorec.si</a></div>')

    return {
        "title": "Padlo je 10 mm na suha tla. Zakaj jurčkov še ni?",
        "meta_description": (f"{num(rain)} mm dežja po {D['n_dry']} suhih dneh je bilo {share_j} % praga za jurčka. "
                             f"Vlaga tal pred dežjem: {s_before} % (model). Jurčki najprej {d_long(d_add(rd, L['mikorizna'][0]))}."),
        "tags": ["gobe", "gobarski indeks", "dež", "vlaga tal", "oktober", "2026"],
        "section_label": "Gobarski model",
        "og_photo": "gobe-lastna",
        "og_accent_hex": "#34d399",
        "lead": lead,
        "sources_note": CSS + src,
        "sections": [
            {"label": "01 — dež", "heading": "Koliko dežja je padlo in koliko bi ga potrebovali?", "id": "dez", "paragraphs": sec1},
            {"label": "02 — tla", "heading": "Tla so bila pred dežjem skoraj suha", "id": "tla", "paragraphs": sec2},
            {"label": "03 — zamik", "heading": "Katere gobe se lahko pojavijo prej in katere pozneje?", "id": "zamik", "paragraphs": sec3},
            {"label": "04 — nabiranje", "heading": "Kaj to pomeni, če greš v gozd?", "id": "gozd", "paragraphs": sec4},
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
    lead_p = f'<p class="lead">{article["lead"]}</p>'
    assert lead_p in html, "uvod ni najden — fotografije ni mogoče vstaviti"
    html = html.replace(lead_p, lead_p + "\n" + photo_html(D), 1)
    with open(os.path.join(ROOT, "blog", f"{slug}.html"), "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"✓ zapisano: blog/{slug}.html")
    if wire:
        og_src = os.path.join(ROOT, PHOTO_DIR, "og-izrez.jpg")
        if os.path.isfile(og_src):
            os.environ["DRIVE_PHOTO_PATH"] = og_src     # OG slika iz te fotografije, ne iz kataloga
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
