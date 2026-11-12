#!/usr/bin/env python3
"""
tools/generate_sneg_gore_post.py -- »Sneg ta teden: v dolini ne, nad 1200 m nekaj centimetrov« (12. 11. 2026).

Ročni podatkovni članek, nadaljevanje članka z 9. 11. (sneg-v-nizinah-cetrtek-dez-sobota-1109). Številke so izračunane iz
posnetka data/sneg-gore-1112.json (`--fetch`): urna napoved Open-Meteo za Rečico (prek workerja /napoved-om, ker je neposredni
dostop do Open-Meteo iz peskovnika dnevno omejen), MTR (napoved-modela.json), MTR sneg (napoved-snega.json) in izvleček
winter-data.json (jutranji tek 11. 11., samo za primerjavo). Strukturo zgodbe varujejo assert-i: če se napoved obrne
(npr. sneg v dolini postane mogoč), generator pade -- članek je treba prenoviti, ne zaobiti asserta.

Članek je posnetek na dan objave. Postaja IREICA1 snega ne meri; notranjih meritev članek ne uporablja (glej CLAUDE.md).
Temperatura na višini je standardni gradient iz Rečice (seo.LAPSE_RATE_C_PER_100M), kar članek tudi pove.

Usage:
    python3 tools/generate_sneg_gore_post.py --fetch            # osveži posnetek (omrežje)
    python3 tools/generate_sneg_gore_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import STYLE as BASE_STYLE, num, fig, tiles  # noqa: E402  (skupni pomočniki, ne podvojeni)

# barve besedila in mreže v SVG sledijo temi strani (svetla/temna)
STYLE = BASE_STYLE.replace("</style>", ".sg-m{fill:var(--muted)}.sg-i{fill:var(--text)}.sg-g{stroke:var(--card-border)}.sg-z{stroke:var(--text)}"
    ".sg-ctl{display:flex;flex-wrap:wrap;gap:.8rem 1.4rem;margin:.2rem 0 .8rem}.sg-grp{display:flex;flex-direction:column;gap:.3rem;min-width:0;flex:1 1 220px}"
    ".sg-lab{font-family:'JetBrains Mono',monospace;font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}"
    ".sg-seg{display:inline-flex;flex-wrap:wrap;border:1px solid var(--card-border);border-radius:14px;overflow:hidden}"
    ".sg-seg button{background:transparent;color:var(--muted);border:0;border-right:1px solid var(--card-border);padding:.5rem .9rem;min-height:44px;min-width:44px;font:inherit;font-size:.9rem;cursor:pointer}"
    ".sg-seg button:last-child{border-right:0}.sg-seg button[aria-pressed='true']{background:rgba(147,197,253,.16);color:var(--text);font-weight:600}"
    ".sg-seg button:focus-visible,.sg-range:focus-visible{outline:2px solid var(--blue);outline-offset:2px}"
    ".sg-range{width:100%;min-height:34px;accent-color:#93c5fd}.sg-read{background:rgba(255,255,255,.04);border:1px solid var(--card-border);border-radius:12px;padding:.7rem .85rem;font-size:.92rem;line-height:1.5;color:var(--text);margin-top:.5rem}"
    "</style>")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
DATA = os.path.join(ROOT, "data", "sneg-gore-1112.json")
SLUG = "sneg-dolina-in-gore-petek-sobota-1112"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-sneg-gore.txt")
NBSP = " "
LINK = 'style="color:var(--blue)"'
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.12)"

LAPSE = 0.65            # °C na 100 m (isto kot generate_seo_pages.LAPSE_RATE_C_PER_100M)
MODEL_ELEV = 374        # višina celice Open-Meteo za Rečico
# meja dež/sneg po temperaturi zraka na višini kraja -- isto kot v članku z 9. 11. (tools/sneg_nizine_data.py)
PRAG_MRAZ, PRAG_DEZ = 0.5, 2.5
COLD_SHIFT = 2.0        # scenarij: zrak na višinah za toliko hladnejši od osnovnega izračuna
WIN_FROM, WIN_TO = "2026-11-12T12:00", "2026-11-14T12:00"   # četrtek opoldne -- sobota opoldne

# (višina, ime v tabeli) -- Črnivec in vrhovi iz HIGH_POINTS (winter_engine.py)
PLACES = [(366, "Rečica"), (700, ""), (902, "Črnivec"), (1200, ""), (1400, "Golte"), (1500, "Menina planina"), (1577, "Smrekovec")]
LINES = [(366, "#3987e5"), (902, "#d55181"), (1400, "#9085e9"), (1577, "#199e70")]   # barve: preverjena paleta semaforja


def a(href, text):
    return f'<a href="{href}" {LINK}>{text}</a>'


def nbsp(s):
    return re.sub(r"(\d) (°C|%|mm|cm|m\b)", lambda m: m.group(1) + NBSP + m.group(2), s)


def temp(x, d=0):
    return f"{num(x, d)}{NBSP}°C".replace("-", "–")


def rnd(x):
    return int(x + 0.5)


def frac_snow(t):
    if t <= PRAG_MRAZ:
        return 1.0
    if t >= PRAG_DEZ:
        return 0.0
    return (PRAG_DEZ - t) / (PRAG_DEZ - PRAG_MRAZ)


# ───────────────────────── posnetek ─────────────────────────

def fetch():
    req = urllib.request.Request(WORKER + "/napoved-om", headers={"User-Agent": "meteorec.si article generator (+https://meteorec.si)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        om = json.load(r)
    h = om["hourly"]
    mtr = json.load(open(os.path.join(ROOT, "napoved-modela.json")))
    sn = json.load(open(os.path.join(ROOT, "napoved-snega.json")))
    wd = json.load(open(os.path.join(ROOT, "data", "winter-data.json")))
    peaks = {}
    for p in wd["mountains"]["peaks"]:
        d13 = next(x for x in p["daily"] if x["date"] == "2026-11-13")
        peaks[p["name"]] = {"elevation_m": p["elevation_m"], "snow_cm_13": d13["snow_cm"], "precip_mm_13": d13["precip_mm"],
                            "freezing_min_m_13": d13["freezing_min_m"]}
    out = {
        "fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "om_elevation_m": om["elevation"],
        "hourly": {"time": h["time"], "t": h["temperature_2m"], "p": h["precipitation"]},
        "daily": {"time": om["daily"]["time"], "tmin": om["daily"]["temperature_2m_min"], "tmax": om["daily"]["temperature_2m_max"],
                  "precip": om["daily"]["precipitation_sum"]},
        "mtr": {"generated_at": mtr["generated_at"], "days": [
            {"date": d["date"], "tmin": d["tmin"], "p_frost": d["p_frost"], "night_regime": d["night_regime"],
             "wn2_tmin": [d["wn2"]["tmin"]["p10"], d["wn2"]["tmin"]["p90"]]} for d in mtr["days"]]},
        "mtr_sneg": {"generated_at": sn["generated_at"], "days": [
            {"date": d["date"], "p_snow": d["p_snow"], "stations": d["stations"]} for d in sn["days"]]},
        "winter_prev": {"generated_at_local": wd["mountains"]["generated_at_local"], "peaks": peaks},
    }
    json.dump(out, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("✓ posnetek:", os.path.relpath(DATA, ROOT))


class Snap:
    def __init__(self):
        S = json.load(open(DATA, encoding="utf-8"))
        self.raw = S
        self.fetched = datetime.datetime.fromisoformat(S["fetched_at"])
        assert self.fetched.date() == datetime.date.today(), f"posnetek je z dne {self.fetched.date()}; poženi z --fetch"
        h = S["hourly"]
        self.time, self.t, self.p = h["time"], h["t"], [x or 0.0 for x in h["p"]]
        assert S["om_elevation_m"] == MODEL_ELEV, S["om_elevation_m"]
        self.win = [i for i, t in enumerate(self.time) if WIN_FROM <= t <= WIN_TO]
        assert len(self.win) == 49, len(self.win)

    def t_at(self, i, elev, shift=0.0):
        return self.t[i] - LAPSE * (elev - MODEL_ELEV) / 100 + shift

    def snow_cm(self, elev, shift=0.0, days=None):
        """Nov sneg v cm (10 : 1) od četrtka opoldne do sobote opoldne, ali čez vse ure posnetka, če je days='all'."""
        idx = range(len(self.time)) if days == "all" else self.win
        return sum(self.p[i] * frac_snow(self.t_at(i, elev, shift)) for i in idx)

    def day_sum(self, date):
        return sum(p for t, p in zip(self.time, self.p) if t.startswith(date))

    def last_wet(self, before="2026-11-15"):
        idx = [i for i, (t, p) in enumerate(zip(self.time, self.p)) if p >= 0.1 and t < before]
        return idx[-1]


# ───────────────────────── grafi ─────────────────────────

DAYS = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
DAN_V = ["v ponedeljek", "v torek", "v sredo", "v četrtek", "v petek", "v soboto", "v nedeljo"]


def fig_hours(S):
    W, H = 460, 410
    x0, x1 = 40, 372
    yt0, yt1 = 24, 254           # panel temperatura
    tmax, tmin = 14.0, -9.0
    yp0, yp1 = 298, 358          # panel padavine (baza = yp1)
    pmax = 8.0
    n = len(S.win)
    X = lambda k: x0 + k / (n - 1) * (x1 - x0)
    YT = lambda t: yt0 + (tmax - t) / (tmax - tmin) * (yt1 - yt0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    for t in (-5, 0, 5, 10):
        y = YT(t)
        dash = "" if t != 0 else ' stroke-dasharray="5 4"'
        out.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="{'sg-z' if t == 0 else 'sg-g'}" stroke-opacity="{.7 if t == 0 else 1}" stroke-width="1"{dash}/>')
        out.append(f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="13" class="sg-m">{str(t).replace("-", "–")}</text>')
    out.append(f'<text x="{x0}" y="14" font-size="13" class="sg-m">temperatura (°C)</text>')
    for elev, col in LINES:
        pts = " ".join(f"{X(k):.1f},{YT(S.t_at(i, elev)):.1f}" for k, i in enumerate(S.win))
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>')
    # neposredne oznake ob koncih črt (z razmikom, da se ne prekrivajo)
    ends = sorted(((YT(S.t_at(S.win[-1], e)), e, c) for e, c in LINES))
    prev = -99
    for y, e, c in ends:
        y = max(y, prev + 14)
        prev = y
        out.append(f'<text x="{x1 + 6}" y="{y + 4:.1f}" font-size="13" font-weight="600" fill="{c}">{e}{NBSP}m</text>')
    # padavine v Rečici
    out.append(f'<text x="{x0}" y="{yp0 - 10}" font-size="13" class="sg-m">padavine v Rečici (mm/h)</text>')
    out.append(f'<line x1="{x0}" y1="{yp1}" x2="{x1}" y2="{yp1}" class="sg-g" stroke-width="1"/>')
    bw = (x1 - x0) / (n - 1) * 0.78
    for k, i in enumerate(S.win):
        v = S.p[i]
        if v <= 0:
            continue
        hgt = min(v, pmax) / pmax * (yp1 - yp0)
        out.append(f'<rect x="{X(k) - bw / 2:.1f}" y="{yp1 - hgt:.1f}" width="{bw:.1f}" height="{hgt:.1f}" fill="#7fb0f0"/>')
    for v in (0, 4, 8):
        y = yp1 - v / pmax * (yp1 - yp0)
        out.append(f'<text x="{x0 - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="13" class="sg-m">{v}</text>')
    # časovna os
    for k, i in enumerate(S.win):
        hh = int(S.time[i][11:13])
        if hh in (0, 12):
            d = datetime.date.fromisoformat(S.time[i][:10])
            xl = X(k)
            out.append(f'<line x1="{xl:.1f}" y1="{yt0}" x2="{xl:.1f}" y2="{yp1 + 5}" class="sg-g" stroke-width="1" stroke-opacity=".6"/>')
            anchor = "start" if k == 0 else ("end" if k == n - 1 else "middle")
            out.append(f'<text x="{xl:.1f}" y="{yp1 + 22}" text-anchor="{anchor}" font-size="13" class="sg-m">{DAYS[d.weekday()]} {hh}.00</text>')
    out.append("</svg>")
    return "".join(out)


def fig_bars(S, rows):
    row_h = 34
    W, H = 460, 30 + row_h * len(rows)
    lx, x0, x1 = 172, 180, 372
    scale = 40.0
    X = lambda v: x0 + min(v, scale) / scale * (x1 - x0)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{{ARIA}}" font-family="Inter,sans-serif">']
    for v in (0, 10, 20, 30, 40):
        out.append(f'<line x1="{X(v):.1f}" y1="6" x2="{X(v):.1f}" y2="{H - 24}" class="sg-g" stroke-width="1"/>')
        out.append(f'<text x="{X(v):.1f}" y="{H - 8}" text-anchor="middle" font-size="13" class="sg-m">{v}</text>')
    for k, (elev, name, base, cold) in enumerate(rows):
        y = 10 + k * row_h
        label = f"{name} · {elev}{NBSP}m" if name else f"{elev}{NBSP}m"
        out.append(f'<text x="{lx}" y="{y + 15}" text-anchor="end" font-size="13" class="sg-i">{label}</text>')
        if cold > 0:
            out.append(f'<rect x="{x0}" y="{y}" width="{X(cold) - x0:.1f}" height="22" rx="3" fill="#7fb0f0" fill-opacity=".30"/>')
        if base > 0:
            out.append(f'<rect x="{x0}" y="{y + 4}" width="{max(X(base) - x0, 2):.1f}" height="14" rx="2" fill="#3987e5"/>')
        fmt = lambda v: "0" if v < 0.05 else ("&lt;" + NBSP + "1" if v < 1.0 else str(rnd(v)))
        out.append(f'<text x="{X(max(cold, base)) + 6:.1f}" y="{y + 15}" font-size="13" font-weight="600" class="sg-i">{fmt(base)} → {fmt(cold)}{NBSP}cm</text>')
    out.append("</svg>")
    return "".join(out)



WIDGET_JS = r"""
(function(){
var D=__DATA__,E=__ELEVS__,M=__MODEL__,PM=__PM__,PD=__PD__,SC=__SCALE__;
var root=document.getElementById('sg-wid');if(!root)return;
var shift=0,lap=0.65;
function fr(t){return t<=PM?1:(t>=PD?0:(PD-t)/(PD-PM));}
function snow(e,l,s){var x=0;for(var i=0;i<D.t.length;i++){x+=D.p[i]*fr(D.t[i]-l*(e-M)/100+s);}return x;}
function fmt(v){return v<0.05?'0':(v<1?'< 1':String(Math.floor(v+0.5)));}
function sh(){return shift===0?'osnovni izračun':(shift<0?String(-shift).replace('.',',')+'\u00a0°C hladnejši zrak':String(shift).replace('.',',')+'\u00a0°C toplejši zrak');}
function draw(){
 var W=460,rh=34,H=18+rh*E.length,lx=172,x0=180,x1=372,o='<svg viewBox="0 0 '+W+' '+H+'" role="img" aria-label="Pričakovan nov sneg po višinah za izbrane nastavitve" font-family="Inter,sans-serif">';
 for(var v=0;v<=SC;v+=20){var xx=x0+v/SC*(x1-x0);o+='<line x1="'+xx+'" y1="4" x2="'+xx+'" y2="'+(H-22)+'" class="sg-g" stroke-width="1"/><text x="'+xx+'" y="'+(H-6)+'" text-anchor="middle" font-size="13" class="sg-m">'+v+'</text>';}
 var rd=[];
 for(var k=0;k<E.length;k++){var e=E[k][0],n=E[k][1],y=8+k*rh,c=snow(e,lap,shift);rd.push([e,n,c]);
  var lab=(n?n+' · ':'')+e+'\u00a0m';
  o+='<text x="'+lx+'" y="'+(y+16)+'" text-anchor="end" font-size="13" class="sg-i">'+lab+'</text>';
  var w=Math.min(c,SC)/SC*(x1-x0);if(c>=0.05)o+='<rect x="'+x0+'" y="'+(y+2)+'" width="'+Math.max(w,2)+'" height="22" rx="3" fill="#3987e5"/>';
  o+='<text x="'+(x0+w+6)+'" y="'+(y+17)+'" font-size="13" font-weight="600" class="sg-i">'+fmt(c)+'\u00a0cm</text>';}
 o+='</svg>';document.getElementById('sg-chart').innerHTML=o;
 var g=rd.filter(function(r){return r[0]===1400;})[0][2],lo=rd.filter(function(r){return r[0]<=902;}).reduce(function(a,r){return Math.max(a,r[2]);},0);
 document.getElementById('sg-read').textContent='Nastavitev: '+sh()+', gradient '+String(lap).replace('.',',')+'\u00a0°C na 100\u00a0m. Na Golteh pade okoli '+fmt(g)+'\u00a0cm snega, v Rečici in na Črnivcu '+(lo<1?'manj kot 1\u00a0cm':'okoli '+fmt(lo)+'\u00a0cm')+'.';
 document.getElementById('sg-val').textContent=sh();
}
var r=document.getElementById('sg-shift');r.addEventListener('input',function(){shift=parseFloat(r.value);draw();});
var bs=root.querySelectorAll('.sg-seg button');
for(var i=0;i<bs.length;i++){bs[i].addEventListener('click',function(){lap=parseFloat(this.getAttribute('data-lap'));for(var j=0;j<bs.length;j++)bs[j].setAttribute('aria-pressed',bs[j]===this?'true':'false');draw();});}
draw();
})();
"""


def widget_html(S):
    data = {"t": [round(S.t[i], 2) for i in S.win], "p": [round(S.p[i], 3) for i in S.win]}
    js = (WIDGET_JS.replace("__DATA__", json.dumps(data)).replace("__ELEVS__", json.dumps([[e, n] for e, n in PLACES], ensure_ascii=False))
          .replace("__MODEL__", str(MODEL_ELEV)).replace("__PM__", str(PRAG_MRAZ)).replace("__PD__", str(PRAG_DEZ)).replace("__SCALE__", "60"))
    laps = "".join(f'<button type="button" data-lap="{l}" aria-pressed="{"true" if l == LAPSE else "false"}">{str(l).replace(".", ",")}</button>' for l in (0.5, 0.65, 0.8))
    inner = ('<div id="sg-wid"><div class="sg-ctl">'
             '<div class="sg-grp"><span class="sg-lab">Temperatura zraka na višinah: <strong id="sg-val">osnovni izračun</strong></span>'
             '<input id="sg-shift" class="sg-range" type="range" min="-4" max="2" step="0.5" value="0" aria-label="Sprememba temperature zraka glede na osnovni izračun, v stopinjah Celzija">'
             '<span class="vs-note" style="margin:0">levo hladneje, desno toplejše kot v osnovnem izračunu</span></div>'
             f'<div class="sg-grp"><span class="sg-lab">Gradient (°C na 100 m)</span><div class="sg-seg" role="group" aria-label="Gradient temperature z višino">{laps}</div></div></div>'
             '<div id="sg-chart"><noscript>Za ta graf je potreben JavaScript; številke za dva scenarija so v prejšnjem grafu.</noscript></div>'
             '<div id="sg-read" class="sg-read" aria-live="polite"></div></div>')
    cap = ("Premaknite drsnik in izberite gradient: sneg se preračuna iz iste urne napovedi za Rečico kot zgornji graf (četrtek opoldne do sobote opoldne). "
           "Strmejši gradient pomeni hladnejši zrak na višini.")
    return fig("Poskusite sami: kaj spremeni hladnejši zrak", inner, cap) + "<script>" + js + "</script>"

# ───────────────────────── članek ─────────────────────────

def build_article(S):
    raw = S.raw
    prior = open(os.path.join(ROOT, "blog", "sneg-v-nizinah-cetrtek-dez-sobota-1109.html"), encoding="utf-8").read()
    for token in ("16\u00a0%", "59\u00a0%", "143 član"):
        assert token in prior, f"v članku z 9. 11. ni več številke {token}"

    # dolina: dež in ohladitev
    rain12, rain13 = S.day_sum("2026-11-12"), S.day_sum("2026-11-13")
    rain = rain12 + rain13
    assert 45 <= rain <= 70, rain
    snow_valley_all = S.snow_cm(366, days="all")
    assert snow_valley_all == 0.0, f"v dolini je v napovedi sneg ({snow_valley_all} cm): članek je treba prenoviti"
    for e in (500, 700, 902):
        assert S.snow_cm(e) < 0.1, (e, S.snow_cm(e))
    assert S.snow_cm(902, COLD_SHIFT * -1) < 1.0, "na Črnivcu je pri hladnejšem scenariju že ≥ 1 cm"
    lw = S.last_wet()
    lw_t = S.t[lw]
    assert S.time[lw].startswith("2026-11-13") and lw_t >= 4.5, (S.time[lw], lw_t)
    first_below3 = next(i for i in range(lw, len(S.time)) if S.t[i] <= 3.0)
    assert S.time[first_below3] > S.time[lw] and S.p[first_below3] == 0
    below3_h = int(S.time[first_below3][11:13])
    below3_day = DAN_V[datetime.date.fromisoformat(S.time[first_below3][:10]).weekday()]

    # višine: osnovni izračun in hladnejši scenarij
    rows = []
    for elev, name in PLACES:
        rows.append((elev, name, S.snow_cm(elev), S.snow_cm(elev, -COLD_SHIFT)))
    byE = {r[0]: r for r in rows}
    assert byE[1200][2] < 1.0, byE[1200]
    golte_b, golte_c = byE[1400][2], byE[1400][3]
    assert 0.5 <= golte_b <= 5 and golte_c > golte_b, (golte_b, golte_c)
    assert byE[1577][2] > byE[1500][2] > golte_b > byE[1200][2] >= byE[902][2]
    smrek_c = byE[1577][3]
    raduha_b = S.snow_cm(2062)

    # Golte: ob kateri uri izračunana temperatura pade pod 0 °C in koliko pada takrat
    g_i = next(i for i in S.win if S.t_at(i, 1400) <= 0.0 and S.time[i] > "2026-11-13T06:00")
    g_h = int(S.time[g_i][11:13])
    g_p = S.p[g_i]
    assert S.time[g_i].startswith("2026-11-13") and g_p <= 0.5, (S.time[g_i], g_p)
    last_p_after_g = sum(S.p[i] for i in S.win if i >= g_i)
    assert last_p_after_g <= 1.0, last_p_after_g

    # sobotno jutro
    fri_i = S.time.index("2026-11-13T21:00")
    t_fri_902 = S.t_at(fri_i, 902)
    assert 0 <= t_fri_902 <= 4, t_fri_902
    sun_i = S.time.index("2026-11-15T06:00")
    t_sun_valley = S.t[sun_i]
    assert -2 <= t_sun_valley <= 2, t_sun_valley
    sat_i = S.time.index("2026-11-14T06:00")
    t_sat_valley, t_sat_902 = S.t[sat_i], S.t_at(sat_i, 902)
    assert t_sat_valley <= 1.0 and t_sat_902 <= -2.0, (t_sat_valley, t_sat_902)
    mtr = {d["date"]: d for d in raw["mtr"]["days"]}
    sob = mtr["2026-11-14"]
    assert sob["p_frost"] >= 0.9 and sob["night_regime"] == "clear_calm", sob
    sn = {d["date"]: d for d in raw["mtr_sneg"]["days"]}
    snow13 = sn["2026-11-13"]
    assert snow13["p_snow"] <= 0.10, snow13
    gg, rad = snow13["stations"]["Gornji Grad"], snow13["stations"]["Radegunda"]
    assert rad <= 0.2, rad

    # naslednji teden
    dly = dict(zip(raw["daily"]["time"], zip(raw["daily"]["tmin"], raw["daily"]["tmax"], raw["daily"]["precip"])))
    wet_next = [d for d in ("2026-11-16", "2026-11-17", "2026-11-18") if dly[d][2] >= 5 and dly[d][1] >= 10]
    assert len(wet_next) == 3, dly
    wn_tmax = (min(dly[d][1] for d in wet_next), max(dly[d][1] for d in wet_next))
    assert S.snow_cm(366, days="all") == 0 and S.snow_cm(902, days="all") < 0.1, "v dolini ali na Črnivcu je v napovedi sneg"
    smr_next = sum(S.p[i] * frac_snow(S.t_at(i, 1577)) for i, t in enumerate(S.time) if t >= "2026-11-15T12:00")
    assert smr_next > 5, smr_next
    last_day = max(t[:10] for t in S.time)

    # včerajšnji tek (winter-data)
    wp = raw["winter_prev"]
    prevp = wp["peaks"]
    assert prevp["Golte"]["precip_mm_13"] >= 60 and prevp["Raduha"]["snow_cm_13"] > prevp["Smrekovec"]["snow_cm_13"] > prevp["Golte"]["snow_cm_13"] > 0
    prev_gol, prev_smr, prev_rad = prevp["Golte"]["snow_cm_13"], prevp["Smrekovec"]["snow_cm_13"], prevp["Raduha"]["snow_cm_13"]
    prev_mm = prevp["Golte"]["precip_mm_13"]

    rain_s = rnd(rain)
    t_sob = temp(sob["tmin"], 0)
    ph = rnd(sob["p_frost"] * 100)
    gg_s = rnd(gg * 100)
    rad_s = rnd(rad * 100)
    lw_h = int(S.time[lw][11:13])

    aria1 = (f"Graf: temperatura zraka od četrtka opoldne do sobote opoldne na štirih nadmorskih višinah in padavine v Rečici. "
             f"Dež v Rečici preneha v petek okoli {lw_h}. ure pri {temp(lw_t, 0).replace(NBSP, ' ')}; temperatura v dolini pade pod 3 °C šele {below3_day} ob {below3_h}. uri, ko je že suho. "
             f"Na 1400 m pade izračunana temperatura pod 0 °C v petek ob {g_h}. uri, ko pada manj kot pol milimetra na uro.")
    f1 = fig("Ohladitev pride, ko dež preneha",
             '<div class="vs-leg">' + "".join(f'<span><i style="background:{c}"></i>{e}{NBSP}m{" (" + n + ")" if n else ""}</span>' for (e, c), n in zip(LINES, ["Rečica", "Črnivec", "Golte", "Smrekovec"]))
             + "</div>" + fig_hours(S).replace("{ARIA}", aria1),
             "Temperatura na višini je izračunana iz napovedi za Rečico s standardnim gradientom (0,65 °C na 100 m), ne izmerjena. Črtkana črta je 0 °C. "
             "Stolpci kažejo urne padavine v Rečici (366 m).")

    b = lambda r: ("< 1" if 0 < r < 0.5 else str(rnd(r)))
    aria2 = ("Graf: pričakovana količina novega snega od četrtka opoldne do sobote opoldne po nadmorskih višinah, osnovni izračun in scenarij, "
             f"ko je zrak za {rnd(COLD_SHIFT)} °C hladnejši. " + "; ".join(
                 f"{(n + ' ') if n else ''}{e} m: {b(bs)} cm, hladneje {b(cd)} cm" for e, n, bs, cd in rows) + ".")
    f2 = fig("Koliko snega v dveh scenarijih",
             '<div class="vs-leg"><span><i style="background:#3987e5"></i>osnovni izračun</span>'
             f'<span><i style="background:#7fb0f0;opacity:.55"></i>zrak na višinah {rnd(COLD_SHIFT)}{NBSP}°C hladnejši</span></div>'
             + fig_bars(S, rows).replace("{ARIA}", aria2),
             "Nov sneg v centimetrih (1 mm padavin ≈ 1 cm snega), od četrtka opoldne do sobote opoldne. Padavina pri temperaturi do 0,5 °C je ves sneg, "
             "nad 2,5 °C ves dež, vmes sorazmerno. To je izračun, ne napoved debeline snežne odeje.")

    tl = tiles([
        ("0", "cm", f"snega v Rečici do {S.time[-1][8:10].lstrip('0')}. {S.time[-1][5:7].lstrip('0')}. po današnjem izračunu", False),
        (f"{rain_s}", "mm", "dežja v Rečici v četrtek in petek (Open-Meteo)", False),
        (num(sob["tmin"], 0).replace("-", "–"), "°C", f"najnižja temperatura v soboto zjutraj po modelu MTR; zmrzal z verjetnostjo {ph} %", False),
        (f"{gg_s}", "%", "možnost merljivega snega v petek v Gornjem Gradu (428 m) po poskusnem modelu MTR sneg", False),
    ])

    lead = (f"Sneg v dolini ta teden ne bo padal. Ohladitev pride v petek zvečer, ko bo dež že ponehal, v Rečici pa bo do tedaj padlo okoli {rain_s} mm. "
            f"Nad približno 1200 m je ob koncu padavin sneg možen, po osnovnem izračunu na Golteh okoli {rnd(golte_b)} cm, na Črnivcu (902 m) pa ga ne pričakujem.")

    p1 = [
        f"<strong>Kratek odgovor:</strong> v dolini snega ne bo, na Črnivcu skoraj gotovo ne, na Golteh in Smrekovcu pa je odvisno od tega, "
        f"kako hladen je zrak ob koncu padavin. Če je za {rnd(COLD_SHIFT)} °C hladnejši, kot kaže osnovni izračun, "
        f"naj bi na Golteh zapadlo okoli {rnd(golte_c)} cm, na Smrekovcu okoli {rnd(smrek_c)} cm.",
        tl,
        "V ponedeljek sem v članku " + a("/blog/sneg-v-nizinah-cetrtek-dez-sobota-1109.html", "»Sneg v nižinah: četrtek še dež, odločitev v noči na soboto«") +
        " ocenil, da je sneg v dolini manj verjeten kot ne: vsaj 1 cm snega do ponedeljka je napovedovalo 16 % od 143 članov ansamblov, na 900 m pa 59 %. Današnji izračun je bližje manj snežnemu koncu "
        "tega razpona: padavine se končajo, preden je dovolj hladno. Ansamblov danes ni bilo mogoče znova prenesti, zato je spodnja ocena "
        "<strong>en sam izračun</strong> in ne verjetnost; odstotkov iz ponedeljka ne obnavljam.",
    ]
    p2 = [
        f"Dež v Rečici se okrepi v četrtek popoldne in zvečer, glavnina pade v noči na petek. Do petka okoli {lw_h}. ure ga po izračunu pade skupaj okoli {rain_s} mm "
        f"(v četrtek {rnd(rain12)} mm, v petek {rnd(rain13)} mm). Zadnje padavine so v dolini ob {lw_h}. uri pri {temp(lw_t, 0)}.",
        f1,
        f"Temperatura v dolini pade pod 3 °C šele {below3_day} ob {below3_h}. uri, ko je že suho. Na 1400 m (Golte) izračun doseže 0 °C v petek ob {g_h}. uri; takrat pada "
        f"manj kot pol milimetra na uro in po tej uri do sobote opoldne ne več kot {rnd(max(last_p_after_g, 1))} mm. Zato je količina snega na višinah tako občutljiva na čas ohladitve.",
    ]
    p3 = [
        f2,
        widget_html(S),
        f"V osnovnem izračunu ostane sneg pod 900 m pri 0 cm, na 1200 m manj kot 1 cm, na Golteh okoli {rnd(golte_b)} cm, na Menini planini okoli {rnd(byE[1500][2])} cm in na Smrekovcu "
        f"okoli {rnd(byE[1577][2])} cm. Če je zrak za {rnd(COLD_SHIFT)} °C hladnejši, so številke {rnd(golte_c)}, {rnd(byE[1500][3])} in {rnd(smrek_c)} cm. "
        f"Na Črnivcu ostane sneg tudi v tem scenariju pod 1 cm.",
        f"Za primerjavo: jutranji izračun za stran " + a("/zima/", "Zima") + f" ({wp['generated_at_local']}) je za petek napovedoval na Golteh okoli {rnd(prev_gol)} cm, na Smrekovcu okoli "
        f"{rnd(prev_smr)} cm in na Raduhi okoli {rnd(prev_rad)} cm. Takratni tek je imel za petek {rnd(prev_mm)} mm dežja, današnji pa okoli {rnd(rain13)} mm, zato je današnja ocena nižja. "
        f"Raduha (2062 m) je po današnjem izračunu še vedno pretežno v snegu, vendar je ocena za greben najbolj groba: model ne pozna orografije, "
        f"zato bi jo jemal kot »več deset centimetrov«, ne kot številko.",
    ]
    p4 = [
        f"Na Črnivcu izračun ob koncu padavin kaže okoli {temp(t_fri_902, 0)} (petek zvečer) in v soboto zjutraj okoli {temp(t_sat_902, 0)}. Sneg torej ni vprašanje, poledica na mokrem cestišču po {rain_s} mm dežja pa je: "
        f"po moji oceni bo v soboto zjutraj večja težava kot sneg. Izmerjeno stanje na prelazu (postaja DRSI) je na " + a("https://crnivec.si/", "crnivec.si") + ", ocena poledice na " +
        a("/zima/poledica/", "strani o poledici") + ".",
        f"V dolini model MTR za soboto napoveduje najnižjo temperaturo {t_sob} (WeatherNext 2: od {temp(sob['wn2_tmin'][0], 0)} do {temp(sob['wn2_tmin'][1], 0)} med 10. in 90. percentilom članov) in zmrzal z verjetnostjo {ph} %, "
        f"noč je po oceni jasna in mirna. Poskusni model MTR sneg daje za petek v Gornjem Gradu {gg_s} %, v Radegundi (794 m) {rad_s} % možnosti merljivega snega (nov sneg vsaj 1 cm ob jutranjem odčitku).",
    ]
    p5 = [
        f"Nedelja bo po izračunu suha in hladna (zjutraj okoli {temp(t_sun_valley, 0)} v dolini). V ponedeljek, torek in sredo je v napovedi spet dež pri {num(wn_tmax[0], 0)} do {num(wn_tmax[1], 0)} °C v dolini; "
        f"do vključno {last_day[8:]}. {last_day[5:7].lstrip("0")}. izračun v Rečici in na Črnivcu ne kaže snega. Na Smrekovcu (1577 m) je ob dežju v dolini temperatura še vedno blizu 0 do 2 °C, zato je tam občasno mokro sneženje možno; napoved za te dni je bolj negotova, zato jo spremljajte na " + a("/zima/snezna-karta/", "snežni karti") + " in pri ARSO.",
    ]
    omej = [
        "<ul>"
        f"<li><strong>En izračun.</strong> Urna napoved Open-Meteo za Rečico (prenos {S.fetched.day}. {S.fetched.month}. {S.fetched.year}); ansamblov nisem osvežil. Ne vem, ali drugi modeli napovedujejo hladnejši zrak prej.</li>"
        "<li><strong>Višine so preračunane.</strong> Temperaturo na višini sem dobil s standardnim gradientom iz Rečice. Ob dotoku hladnega zraka je gradient lahko strmejši, zato je hladnejši scenarij toliko pomemben; "
        "izračun tudi ne zajame dviga padavin ob pobočjih.</li>"
        f"<li><strong>Sneži ni isto kot obleži.</strong> Tla so po {rain_s} mm dežja mokra in topla; tudi če sneži, se sneg na nižjih legah ne obdrži. Postaja IREICA1 snega ne meri.</li>"
        "<li><strong>MTR sneg je poskusni model</strong>, naučen na opazovanjih ARSO v Gornjem Gradu in drugih dolinskih postajah (Vir: Agencija Republike Slovenije za okolje); ne napoveduje količine ali obležanja.</li>"
        "<li><strong>To ni uradno opozorilo.</strong> Za ukrepanje veljajo ARSO in URSZR.</li>"
        "</ul>",
    ]
    p6 = [
        "Za sobotno jutro računajte z zmrzaljo in poledico, ne s snegom. Napoved za višine in vrhove najdete na straneh " + a("/vreme-v-gorah/", "Vreme v gorah") + " in " +
        a("/zima/meja-snezenja/", "Meja sneženja") + ", količino dežja in vodostaje pa na " + a("/vodostaj-savinje/", "strani o vodostaju Savinje") + ".",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate samo z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Sneg ta teden: v dolini ne, na višinah nekaj centimetrov"
    assert len(title) <= 60, len(title)
    desc = (f"V Rečici bo do petka padlo okoli {rain_s} mm dežja, ohladitev pa pride po koncu padavin. Koliko snega lahko pade na Golteh, Črnivcu in Smrekovcu.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "V dolini ne, na višinah odloča hladnost zraka", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — ura za uro", "heading": "Dež preneha, preden zmrzne", "id": "ura", "paragraphs": p2},
        {"label": "03 — višine", "heading": "Golte, Menina planina, Smrekovec: nekaj centimetrov ali več", "id": "visine", "paragraphs": p3},
        {"label": "04 — Črnivec in dolina", "heading": "Črnivec: poledica pred snegom", "id": "crnivec", "paragraphs": p4},
        {"label": "05 — naslednji dnevi", "heading": "Nedelja suha, od ponedeljka spet dež", "id": "naprej", "paragraphs": p5},
        {"label": "06 — omejitve", "heading": "Česa izračun ne pove?", "id": "omejitve", "paragraphs": omej},
        {"label": "07 — praktično", "heading": "Kaj lahko naredite?", "id": "prakticno", "paragraphs": p6},
    ]
    lead = nbsp(lead)
    for sec in sections:
        sec["paragraphs"] = [x if ("<svg" in x or "<script" in x) else nbsp(x) for x in sec["paragraphs"]]
    return {
        "title": title, "meta_description": desc,
        "tags": ["sneg", "nižine", "Golte", "Črnivec", "napoved", "november"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#93c5fd",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: Open-Meteo (urna napoved za Rečico, " f"prenos z dne {S.fetched.day}. {S.fetched.month}. {S.fetched.year}), model MTR in MTR sneg (Meteorec), "
                         "opazovanja ARSO, na katerih je naučen MTR sneg (Vir: Agencija Republike Slovenije za okolje), WeatherNext 2 (Google DeepMind, prek Open-Meteo, CC BY 4.0). "
                         "Weather data by Open-Meteo.com (CC BY 4.0). Podatki posnetka: data/sneg-gore-1112.json."),
    }


def plain_text(article):
    def clean(h):
        h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|h4|figcaption|li|p|div|b)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace("&lt;", "<").replace(NBSP, " ")
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
        og_title="Sneg ta teden:\nv dolini ne", meta_note="podatkovna analiza",
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
