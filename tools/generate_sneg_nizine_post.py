#!/usr/bin/env python3
"""
tools/generate_sneg_nizine_post.py -- »Sneg v nižinah: četrtek še dež, odloča se v noči na soboto« (9. 11. 2026).

Ročno napisan podatkovni članek z interaktivnimi gradniki (ura za uro, delež članov po višinah, zemljevid Slovenije).
Številke pridejo iz posnetka data/sneg-nizine-1109.json, ki ga zapiše tools/sneg_nizine_data.py (Open-Meteo: 7 determinističnih
modelov in 4 ansambli, skupaj 143 članov, za Rečico na petih višinah in za 20 krajev po Sloveniji). Besedilo nič ne izmišlja:
vse številke v stavkih so izračunane iz posnetka, strukturo zgodbe varujejo assert-i. Če se napoved obrne (npr. ansambli
se uskladijo ali sneg v dolini postane večinski), generator pade -- članek je treba prenoviti, ne zaobiti asserta.

Članek je posnetek na dan objave. Postaja IREICA1 snega ne meri; notranjih meritev članek ne uporablja (glej CLAUDE.md).
Meja dež/sneg je poenostavitev po temperaturi zraka (glej tools/sneg_nizine_data.py, PRAG_*), kar članek tudi pove.

Usage:
    python3 tools/sneg_nizine_data.py                      # najprej osveži posnetek (omrežje)
    python3 tools/generate_sneg_nizine_post.py [--dry-run] [--text] [--wire] [--force]
"""
import datetime
import json
import math
import os
import re
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_slane_se_ni_post import (  # noqa: E402  (skupni pomočniki, ne podvojeni)
    NBSP, STYLE as BASE_STYLE, num, temp, fig, tiles)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://meteorec.si"
DATA = os.path.join(ROOT, "data", "sneg-nizine-1109.json")
SLUG = "sneg-v-nizinah-cetrtek-dez-sobota-1109"
TEXT_OUT = os.path.join(ROOT, "docs", "lektura-sneg-nizine.txt")
LINK = 'style="color:var(--blue)"'
INK, MUTED, GRID = "#e8edf8", "#adc0d8", "rgba(255,255,255,.10)"

# barve: faze so po svetlosti ločene (sneg 96, dež s snegom 76, dež 48), sistemi so prvi štirje iz preverjene palete semaforja
C_SNOW, C_MIX, C_RAIN = "#f1f5f9", "#c4b5fd", "#2f6fd6"
C_THU, C_FRI = "#7fb0f0", "#2f6fd6"
SYS_COL = {"ecmwf_ifs025": "#3987e5", "icon_seamless": "#d55181", "gfs025": "#9085e9", "gem_global": "#199e70"}
SYS_NAME = {"ecmwf_ifs025": "ECMWF ENS", "icon_seamless": "ICON-EPS", "gfs025": "GEFS", "gem_global": "GEM ENS"}
SHAPES = {"ecmwf_ifs025": "circle", "icon_seamless": "diamond", "gfs025": "square", "gem_global": "triangle"}

_DAN_V = ["v ponedeljek", "v torek", "v sredo", "v četrtek", "v petek", "v soboto", "v nedeljo"]
_DAN_SH = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]


def a(href, text):
    return f'<a href="{href}" {LINK}>{text}</a>'


def nbsp(s):
    return re.sub(r"(\d) (°C|%|mm|cm|m\b)", lambda m: m.group(1) + NBSP + m.group(2), s)


# ───────────────────────── podatki ─────────────────────────

class Snap:
    def __init__(self):
        self.d = json.load(open(DATA, encoding="utf-8"))
        d = self.d
        self.start = datetime.datetime.fromisoformat(d["start"])
        self.n = d["n_hours"]
        assert self.start.weekday() == 3 and self.start.date() == datetime.date(2026, 11, 12), self.start
        self.fetched = datetime.datetime.fromisoformat(d["fetched_at"]).astimezone(ZoneInfo("Europe/Ljubljana"))
        assert self.fetched.date() == datetime.date.today(), f"posnetek je z dne {self.fetched.date()}; poženi tools/sneg_nizine_data.py"
        self.ids = ["ecmwf_ifs025", "icon_seamless", "gfs025", "gem_global"]

    def hr(self, h):
        return self.start + datetime.timedelta(hours=h)

    def ob(self, h):
        """»v soboto ob 2. uri«"""
        t = self.hr(h)
        return f"{_DAN_V[t.weekday()]} ob {t.hour}. uri"

    def lab(self, h):
        t = self.hr(h)
        return f"{_DAN_SH[t.weekday()]} {t.day}. {t.month}., {t.hour}.00"

    def pooled(self, el, win, k):
        return self.d["pooled"][str(el)][win][k]

    def sysv(self, el, win, sid, k):
        return self.d["systems"][str(el)][sid][win][k]


# ───────────────────────── statični grafi ─────────────────────────

def fig_rain(S):
    """Dež v četrtek in petek po determinističnih modelih + ansambel (mediana in razpon 10-90 %)."""
    rows = []
    for k, v in S.d["det"].items():
        p = v["elev"]["366"]["p"]
        thu, fri = p[0:24], p[24:48]
        if any(x is None for x in thu + fri):
            continue                                              # model, ki ne sega do petka (ARPEGE), ne gre v primerjavo
        rows.append((v["label"], round(sum(thu), 1), round(sum(fri), 1)))
    rows.sort(key=lambda r: -(r[1] + r[2]))
    tf = S.d["pooled"]["366"]["thufri"]
    W, L, R = 560, 118, 54
    rh, top = 30, 34
    H = top + (len(rows) + 1) * rh + 46
    mx = 100.0
    x = lambda v: L + (W - L - R) * v / mx
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Skupne padavine v četrtek in petek po modelih: '
         + "; ".join(f"{r[0]} {num(r[1] + r[2], 0)} mm" for r in rows)
         + f'. Ansambel: mediana {tf["mm50"]} mm, razpon od {tf["mm10"]} do {tf["mm90"]} mm.">']
    for v in (0, 25, 50, 75, 100):
        g.append(f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{top - 8}" y2="{H - 40}" stroke="{GRID}"/>'
                 f'<text x="{x(v):.1f}" y="{H - 24}" fill="{MUTED}" font-size="11" text-anchor="middle">{v}</text>')
    g.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 8}" fill="{MUTED}" font-size="11" text-anchor="middle">mm dežja v Rečici, skupaj četrtek + petek</text>')
    for i, (lab, thu, fri) in enumerate(rows):
        y = top + i * rh
        g.append(f'<text x="{L - 8}" y="{y + 15}" fill="{INK}" font-size="12" text-anchor="end">{lab}</text>')
        g.append(f'<rect x="{x(0):.1f}" y="{y + 3}" width="{x(thu) - x(0):.1f}" height="18" rx="2" fill="{C_THU}"/>')
        g.append(f'<rect x="{x(thu):.1f}" y="{y + 3}" width="{x(thu + fri) - x(thu):.1f}" height="18" rx="2" fill="{C_FRI}"/>')
        g.append(f'<text x="{x(thu + fri) + 6:.1f}" y="{y + 16}" fill="{INK}" font-size="12">{num(thu + fri, 0)} mm</text>')
    y = top + len(rows) * rh + 8
    g.append(f'<line x1="{L - 80}" x2="{W - R + 30}" y1="{y - 4}" y2="{y - 4}" stroke="{GRID}"/>')
    g.append(f'<text x="{L - 8}" y="{y + 15}" fill="{INK}" font-size="12" text-anchor="end">Ansambel (143)</text>')
    g.append(f'<line x1="{x(tf["mm10"]):.1f}" x2="{x(tf["mm90"]):.1f}" y1="{y + 12}" y2="{y + 12}" stroke="{INK}" stroke-width="2"/>'
             f'<line x1="{x(tf["mm10"]):.1f}" x2="{x(tf["mm10"]):.1f}" y1="{y + 6}" y2="{y + 18}" stroke="{INK}" stroke-width="2"/>'
             f'<line x1="{x(tf["mm90"]):.1f}" x2="{x(tf["mm90"]):.1f}" y1="{y + 6}" y2="{y + 18}" stroke="{INK}" stroke-width="2"/>'
             f'<circle cx="{x(tf["mm50"]):.1f}" cy="{y + 12}" r="5.5" fill="{INK}" stroke="#0a0f1c" stroke-width="1.5"/>')
    g.append(f'<text x="{x(tf["mm90"]) + 8:.1f}" y="{y + 16}" fill="{INK}" font-size="12">{tf["mm50"]} mm</text>')
    g.append("</svg>")
    leg = (f'<p class="vs-leg"><span><i style="background:{C_THU}"></i>četrtek</span><span><i style="background:{C_FRI}"></i>petek</span>'
           f'<span><i style="background:{INK};border-radius:50%"></i>ansambel: mediana in razpon 10.–90. percentila</span></p>')
    names = ", ".join(r[0] for r in rows)
    return fig("Dež v četrtek in petek: od kod do kod sežejo modeli", leg + "".join(g),
               f"Vsak vodoravni stolpec je en model (en tek, Rečica, 366 m): svetlejši del so padavine v četrtek, temnejši v petek. Prikazani so {names}. "
               "ARPEGE in nekateri drugi modeli ne segajo do konca petka, zato jih ni. Spodaj je ansambel s 143 člani: krog je mediana, "
               "črta pa razpon, v katerega pade devet desetin članov.")


def shape(kind, x, y, r, color, filled):
    fill = color if filled else "none"
    st = f'fill="{fill}" stroke="{color}" stroke-width="1.6"' + (' fill-opacity=".92"' if filled else "")
    if kind == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" {st}/>'
    if kind == "diamond":
        return f'<path d="M{x:.1f} {y - r - 1:.1f} L{x + r + 1:.1f} {y:.1f} L{x:.1f} {y + r + 1:.1f} L{x - r - 1:.1f} {y:.1f}Z" {st}/>'
    if kind == "square":
        return f'<rect x="{x - r:.1f}" y="{y - r:.1f}" width="{2 * r}" height="{2 * r}" {st}/>'
    return f'<path d="M{x:.1f} {y - r - 1:.1f} L{x + r + 1:.1f} {y + r:.1f} L{x - r - 1:.1f} {y + r:.1f}Z" {st}/>'


def scatter_stats(S):
    """Točke za razsevni diagram: ure prihoda ohladitve, padavine za njo in ali član naredi vsaj 1 cm snega."""
    pts = []
    for sid in S.ids:
        f = S.d["front"][sid]
        for h, mm, cm in zip(f["arrive_h"], f["behind_mm"], f["cm"]):
            pts.append((sid, h, mm, cm))
    return pts


def fig_scatter(S, pts):
    W, H = 560, 330
    L, R, T, B = 52, 76, 18, 62
    h0, h1 = 24, 120                                            # petek 0.00 do ponedeljek 0.00
    ymax = 20.0
    DASH = 'stroke-dasharray="4 4"'
    x = lambda h: L + (W - L - R) * (h - h0) / (h1 - h0)
    ys = lambda mm: T + (H - T - B) * (1 - math.sqrt(min(mm, ymax) / ymax))
    g = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Razsevni diagram {len(pts)} članov ansamblov: čas ohladitve in padavine po njej. '
         'Polni liki so člani, ki v dolini do ponedeljka naredijo vsaj 1 cm snega.">']
    for mm in (0, 1, 2, 5, 10, 20):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{ys(mm):.1f}" y2="{ys(mm):.1f}" stroke="{GRID}" {DASH if mm == 1 else ""}/>'
                 f'<text x="{L - 7}" y="{ys(mm) + 4:.1f}" fill="{MUTED}" font-size="11" text-anchor="end">{mm}</text>')
    g.append(f'<text x="{L + 4}" y="{ys(1) - 5:.1f}" fill="{MUTED}" font-size="11">1 mm ≈ 1 cm snega</text>')
    for d in range(24, 121, 24):
        t = S.hr(d)
        g.append(f'<line x1="{x(d):.1f}" x2="{x(d):.1f}" y1="{T}" y2="{H - B}" stroke="{GRID}"/>')
        if d < 120:
            g.append(f'<text x="{x(d + 12):.1f}" y="{H - B + 17}" fill="{MUTED}" font-size="11" text-anchor="middle">{_DAN_SH[t.weekday()]} {t.day}. {t.month}.</text>')
    g.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 30}" fill="{MUTED}" font-size="11" text-anchor="middle">kdaj temperatura zraka v dolini pade na 3 °C ali manj</text>')
    g.append(f'<text transform="translate(13 {(T + H - B) / 2:.0f}) rotate(-90)" fill="{MUTED}" font-size="11" text-anchor="middle">padavine v 48 urah po ohladitvi (mm)</text>')
    # stolpec »ohladitve ni«
    nx = W - R + 36
    g.append(f'<line x1="{W - R + 12}" x2="{W - R + 12}" y1="{T}" y2="{H - B}" stroke="{GRID}" stroke-dasharray="3 4"/>')
    g.append(f'<text x="{nx}" y="{H - B + 17}" fill="{MUTED}" font-size="11" text-anchor="middle">brez</text>'
             f'<text x="{nx}" y="{H - B + 29}" fill="{MUTED}" font-size="11" text-anchor="middle">ohladitve</text>')
    none = {sid: 0 for sid in S.ids}
    for sid, h, mm, cm in pts:
        if h is None:
            none[sid] += 1
            continue
        g.append(shape(SHAPES[sid], x(h), ys(mm), 3.6, SYS_COL[sid], cm >= 1))
    for i, sid in enumerate(S.ids):
        yy = T + 20 + i * 22
        g.append(shape(SHAPES[sid], nx - 16, yy, 3.6, SYS_COL[sid], False)
                 + f'<text x="{nx - 6}" y="{yy + 4}" fill="{INK}" font-size="12">{none[sid]}</text>')
    g.append("</svg>")
    leg = ('<p class="vs-leg">' + "".join(
        f'<span><svg class="sn-ico" viewBox="0 0 14 14" width="14" height="14">'
        f'{shape(SHAPES[sid], 7, 7, 3.6, SYS_COL[sid], True)}</svg>{SYS_NAME[sid]}</span>' for sid in S.ids)
        + '<span>polno: vsaj 1 cm snega</span><span>prazno: manj</span></p>')
    return fig("Kaj mora sovpasti: ohladitev, ki ujame še kaj padavin", leg + "".join(g),
               "Vsak lik je en član ansambla (143 jih je). Vodoravno je čas, ko se temperatura zraka v Rečici prvič spusti na 3 °C ali manj, "
               "navpično pa padavine v naslednjih 48 urah (korenska lestvica, da se vidijo tudi majhne vrednosti). "
               "Polni liki so člani, pri katerih do ponedeljka nastane vsaj 1 cm snega. V desnem stolpcu je število članov, "
               "pri katerih se temperatura do ponedeljka sploh ne spusti na 3 °C.")


# ───────────────────────── interaktivni gradniki ─────────────────────────

WIDGET_CSS = """<style>
.vs-fig.sn-wide svg{max-width:none;width:100%}
.vs-fig svg.sn-ico{display:inline-block;vertical-align:-2px;margin:0 .35rem 0 0;width:14px;height:14px;max-width:14px}
.sn-ctl{display:flex;flex-wrap:wrap;gap:.6rem 1.3rem;margin:.2rem 0 .9rem}
.sn-grp{display:flex;flex-direction:column;gap:.3rem;min-width:0}
.sn-lab{font-family:'JetBrains Mono',monospace;font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.sn-seg{display:inline-flex;flex-wrap:wrap;border:1px solid var(--card-border);border-radius:14px;overflow:hidden;background:rgba(255,255,255,.03)}
.sn-seg button{background:transparent;color:var(--muted);border:0;border-right:1px solid var(--card-border);padding:.5rem .8rem;min-height:44px;min-width:44px;font:inherit;font-size:.86rem;cursor:pointer}
.sn-seg button:last-child{border-right:0}
.sn-seg button[aria-pressed="true"]{background:rgba(147,197,253,.16);color:var(--text);font-weight:600}
.sn-seg button:focus-visible,.sn-btn:focus-visible,.sn-erow:focus-visible,.sn-rank button:focus-visible{outline:2px solid var(--blue);outline-offset:-2px}
.sn-chart{position:relative;min-height:120px}
.sn-range{width:100%;margin:.5rem 0 .2rem;accent-color:#93c5fd;min-height:34px}
.sn-read{background:rgba(255,255,255,.04);border:1px solid var(--card-border);border-radius:12px;padding:.7rem .85rem;font-size:.9rem;line-height:1.5;color:var(--text);margin-top:.5rem}
.sn-read b{font-family:'Space Grotesk',sans-serif}
.sn-read small{color:var(--muted)}
.sn-rd-h{margin-bottom:.15rem}
.sn-pills,.sn-chips{display:flex;flex-wrap:wrap;gap:.3rem .45rem;margin:.35rem 0 0}
.sn-pill,.sn-chip{display:inline-flex;align-items:center;gap:.35rem;font-size:.8rem;padding:.12rem .55rem;border-radius:999px;background:rgba(255,255,255,.06);color:var(--text)}
.sn-pill i,.sn-chip i{width:.65rem;height:.65rem;border-radius:3px;display:inline-block;flex:none}
.sn-chip{color:var(--muted)}
.sn-erow{display:grid;grid-template-columns:5.3rem 1fr 3rem;align-items:center;gap:.6rem;width:100%;background:transparent;border:1px solid transparent;border-radius:12px;color:var(--text);font:inherit;padding:.15rem .4rem;min-height:46px;cursor:pointer;text-align:left}
.sn-erow.sel{background:rgba(147,197,253,.10);border-color:rgba(147,197,253,.35)}
.sn-el-l{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:.95rem;line-height:1.15}
.sn-el-l small{display:block;font-family:inherit;font-weight:400;color:var(--muted);font-size:.72rem}
.sn-track{position:relative;height:22px;border-radius:6px;background:repeating-linear-gradient(90deg,rgba(255,255,255,.06) 0 1px,transparent 1px 25%),rgba(255,255,255,.05)}
.sn-bar{position:absolute;left:0;top:3px;bottom:3px;border-radius:4px;background:linear-gradient(90deg,#9db8e6,#f1f5f9);min-width:2px}
.sn-dot{position:absolute;top:50%;width:11px;height:11px;margin:-5.5px 0 0 -5.5px;border:1.5px solid #0a0f1c;box-shadow:0 0 0 1px rgba(255,255,255,.35)}
.sn-dot.d0{border-radius:50%}.sn-dot.d1{transform:rotate(45deg);border-radius:2px}.sn-dot.d2{border-radius:2px}
.sn-dot.d3{clip-path:polygon(50% 0,100% 100%,0 100%);border:0;box-shadow:none;width:13px;height:12px}
.sn-el-v{font-family:'Space Grotesk',sans-serif;font-weight:600;text-align:right;font-size:1rem}
.sn-btn{background:rgba(255,255,255,.07);color:var(--text);border:1px solid var(--card-border);border-radius:999px;padding:.45rem 1rem;min-height:44px;font:inherit;font-size:.86rem;cursor:pointer}
.sn-map-wrap{display:grid;grid-template-columns:1fr;gap:.8rem}
@media(min-width:760px){.sn-map-wrap{grid-template-columns:1.55fr 1fr}}
.sn-rank{list-style:none;display:flex;flex-direction:column;gap:.15rem;padding:0;margin:0}
.sn-rank li button{display:grid;grid-template-columns:1fr auto;gap:.5rem;width:100%;background:transparent;border:1px solid transparent;border-radius:10px;padding:.35rem .55rem;min-height:40px;color:var(--text);font:inherit;font-size:.88rem;cursor:pointer;text-align:left}
.sn-rank li button.sel{background:rgba(147,197,253,.12);border-color:rgba(147,197,253,.35)}
.sn-rank small{color:var(--muted)}
.sn-rank b{font-family:'Space Grotesk',sans-serif}
.sn-ramp{height:10px;border-radius:5px;margin:.2rem 0 .1rem}
.sn-scen{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.7rem;margin:1.2rem 0}
.sn-sc{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.9rem 1rem}
.sn-sc b.big{display:block;font-family:'Space Grotesk',sans-serif;font-size:2.1rem;line-height:1;color:var(--text)}
.sn-sc h4{font-family:'Space Grotesk',sans-serif;font-size:.95rem;margin:.55rem 0 .3rem;color:var(--text)}
.sn-sc p{font-size:.88rem;line-height:1.5;color:var(--muted);margin:0}
.sn-sc .tag{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.45rem;vertical-align:-.05rem}
.sn-stack{display:flex;height:18px;border-radius:6px;overflow:hidden;margin:.9rem 0 .4rem;border:1px solid var(--card-border)}
.sn-stack span{display:block;height:100%}
@media(prefers-reduced-motion:no-preference){.sn-bar{transition:width .25s ease}}
@media(max-width:480px){.sn-erow{grid-template-columns:4.1rem 1fr 2.6rem;gap:.4rem}.sn-seg button{padding:.5rem .6rem;font-size:.82rem}}
</style>"""

WIDGET_JS = r"""
(function(){
'use strict';
function init(){
var D=window.SN_D; if(!D) return;
var SNOW='#f1f5f9',MIX='#c4b5fd',RAIN='#2f6fd6',TEMPC='#fbbf24',INK='#e8edf8',MUT='#adc0d8';
var NS='http://www.w3.org/2000/svg';
function S(tag,attrs,parent){var e=document.createElementNS(NS,tag);for(var k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
function H(tag,attrs,html,parent){var e=document.createElement(tag);if(attrs)for(var k in attrs){if(k==='class')e.className=attrs[k];else e.setAttribute(k,attrs[k]);}if(html!=null)e.innerHTML=html;if(parent)parent.appendChild(e);return e;}
function $(id){return document.getElementById(id);}
function fmt(x,d){if(x==null)return '–';if(d==null)d=1;var v=+x;if(Math.abs(v)<Math.pow(10,-d)/2)v=0;return v.toFixed(d).replace('.',',').replace('-','–');}
var P=D.start.split(/[-T:]/).map(Number);
var DAY=['ned','pon','tor','sre','čet','pet','sob'];
function when(h){return new Date(P[0],P[1]-1,P[2],P[3]+h);}
function lbl(h){var d=when(h);return DAY[d.getDay()]+' '+d.getDate()+'. '+(d.getMonth()+1)+'., '+d.getHours()+'.00';}
var CLS=['suho','sneg','dež s snegom','dež'];
var CCOL=['rgba(255,255,255,.07)',SNOW,MIX,RAIN];
var SYSN={all:'vsi člani'};D.sys.forEach(function(s){SYSN[s.id]=s.label;});
var st={el:D.defEl,sys:'all',h:D.defHour,win:'all',met:1};
var NN=D.n;

/* ---------- krmilniki ---------- */
function seg(parentId,opts,cur,cb,label){
  var box=$(parentId);box.innerHTML='';box.setAttribute('role','group');box.setAttribute('aria-label',label);
  opts.forEach(function(o){var b=H('button',{type:'button','aria-pressed':String(o.v===cur)},o.l,box);b.addEventListener('click',function(){
    [].forEach.call(box.children,function(c){c.setAttribute('aria-pressed','false');});b.setAttribute('aria-pressed','true');cb(o.v);});});
}
function setSegPressed(parentId,val,opts){var box=$(parentId);opts.forEach(function(o,i){box.children[i].setAttribute('aria-pressed',String(o.v===val));});}
var ELOPTS=D.elevs.map(function(e){return {v:String(e),l:e+' m'};});
var SYSOPTS=[{v:'all',l:'Vsi'}].concat(D.sys.map(function(s){return {v:s.id,l:s.short};}));

/* ---------- 1) ura za uro ---------- */
var hourBox=$('sn-hour-chart'),rng=$('sn-hour-range'),rd=$('sn-hour-read');
var cur={};
function drawHourly(){
  var W=Math.max(300,hourBox.clientWidth||600),L=60,R=8,cw=(W-L-R)/NN;
  var yT=44,hT=118,yB=yT+hT+40,hB=80,yS=yB+hB+34,rh=15,gp=3,nd=D.det.length;
  var HH=yS+nd*(rh+gp)+34;
  hourBox.innerHTML='';
  var svg=S('svg',{width:W,height:HH,viewBox:'0 0 '+W+' '+HH,role:'img','aria-label':'Ura za uro od četrtka do ponedeljka: temperatura, delež članov ansambla s snegom, dežjem s snegom in dežjem ter posamezni modeli. Natančne vrednosti so v besedilu pod grafom.'},hourBox);
  var defs=S('defs',{},svg);var pat=S('pattern',{id:'snh',width:5,height:5,patternUnits:'userSpaceOnUse',patternTransform:'rotate(45)'},defs);
  S('rect',{width:5,height:5,fill:'rgba(255,255,255,.03)'},pat);S('line',{x1:0,y1:0,x2:0,y2:5,stroke:'rgba(255,255,255,.16)','stroke-width':1.4},pat);
  var R_=D.hourly[st.el][st.sys];
  var x=function(i){return L+(i+.5)*cw;};
  var lo=99,hi=-99;for(var i=0;i<NN;i++){if(R_.t0[i]!=null)lo=Math.min(lo,R_.t0[i]);if(R_.t2[i]!=null)hi=Math.max(hi,R_.t2[i]);}
  lo=Math.floor(Math.min(lo,-1)/2)*2;hi=Math.ceil(Math.max(hi,4)/2)*2;
  var step=(hi-lo)>22?6:((hi-lo)>12?4:2);
  var yv=function(t){return yT+hT*(hi-t)/(hi-lo);};
  // naslovi plošč
  S('text',{x:L,y:yT-9,fill:MUT,'font-size':11},svg).textContent=W<480?'Temperatura zraka (mediana, razpon)':'Temperatura zraka: mediana in razpon 10.–90. percentila';
  S('text',{x:L,y:yB-9,fill:MUT,'font-size':11},svg).textContent='Kaj pada: delež članov';
  S('text',{x:L,y:yS-9,fill:MUT,'font-size':11},svg).textContent='Posamezni modeli (en tek)';
  // mreža temperature
  for(var t=Math.ceil(lo/step)*step;t<=hi;t+=step){
    S('line',{x1:L,x2:W-R,y1:yv(t),y2:yv(t),stroke:t===0?'rgba(255,255,255,.55)':'rgba(255,255,255,.09)','stroke-dasharray':t===0?'5 4':''},svg);
    S('text',{x:L-6,y:yv(t)+4,fill:t===0?INK:MUT,'font-size':11,'text-anchor':'end'},svg).textContent=String(t).replace('-','–');
  }
  // noč na soboto
  var nw=D.night;var rx=L+nw[0]*cw,rw=(nw[1]-nw[0])*cw;
  S('rect',{x:rx,y:yB-2,width:rw,height:hB+4+(yS-yB-hB)+nd*(rh+gp)-gp+4,fill:'rgba(147,197,253,.07)',rx:4},svg);
  // pas
  var d1='',d2='';
  for(i=0;i<NN;i++)d1+=(i?'L':'M')+x(i).toFixed(1)+' '+yv(R_.t2[i]).toFixed(1);
  for(i=NN-1;i>=0;i--)d2+='L'+x(i).toFixed(1)+' '+yv(R_.t0[i]).toFixed(1);
  S('path',{d:d1+d2+'Z',fill:'rgba(251,191,36,.17)'},svg);
  var d3='';for(i=0;i<NN;i++)d3+=(i?'L':'M')+x(i).toFixed(1)+' '+yv(R_.t1[i]).toFixed(1);
  S('path',{d:d3,fill:'none',stroke:TEMPC,'stroke-width':2.2,'stroke-linejoin':'round'},svg);
  // stolpci
  S('text',{x:L-6,y:yB+hB+4,fill:MUT,'font-size':11,'text-anchor':'end'},svg).textContent='0';
  S('text',{x:L-6,y:yB+4,fill:MUT,'font-size':11,'text-anchor':'end'},svg).textContent='100 %';
  S('line',{x1:L,x2:W-R,y1:yB+hB,y2:yB+hB,stroke:'rgba(255,255,255,.18)'},svg);
  for(i=0;i<NN;i++){
    var s=R_.s[i]||0,m=R_.m[i]||0,r=R_.r[i]||0,y0=yB+hB;
    var parts=[[s,SNOW],[m,MIX],[r,RAIN]];
    for(var p=0;p<3;p++){var hh=parts[p][0]/100*hB;if(hh>0.2){y0-=hh;S('rect',{x:(L+i*cw).toFixed(2),y:y0.toFixed(2),width:(cw+.35).toFixed(2),height:hh.toFixed(2),fill:parts[p][1]},svg);}}
  }
  // strip modelov
  D.det.forEach(function(m,k){
    var yy=yS+k*(rh+gp);
    S('text',{x:L-6,y:yy+rh-4,fill:INK,'font-size':11,'text-anchor':'end'},svg).textContent=m.short;
    var f=m.elev[st.el].f;
    for(var j=0;j<NN;j++){var v=f[j];S('rect',{x:(L+j*cw).toFixed(2),y:yy,width:(cw+.35).toFixed(2),height:rh,fill:v==null?'url(#snh)':CCOL[v]},svg);}
  });
  // dnevi in ure
  for(i=0;i<=NN;i+=24){
    S('line',{x1:L+i*cw,x2:L+i*cw,y1:yT-2,y2:yS+nd*(rh+gp)-gp,stroke:'rgba(255,255,255,.18)'},svg);
    if(i<NN){var d=when(i);S('text',{x:L+(i+12)*cw,y:13,fill:INK,'font-size':12,'text-anchor':'middle','font-weight':600},svg).textContent=DAY[d.getDay()]+' '+d.getDate()+'.'+(24*cw>92?' '+(d.getMonth()+1)+'.':'');}
  }
  var ye=yS+nd*(rh+gp)-gp+14;
  var every=cw*6<26?12:6;
  for(i=0;i<NN;i+=every){if(i%24===0&&false)continue;S('text',{x:L+i*cw,y:ye,fill:MUT,'font-size':10,'text-anchor':'middle'},svg).textContent=String(when(i).getHours());}
  S('text',{x:L+nw[0]*cw+rw/2,y:ye+14,fill:'#93c5fd','font-size':11,'text-anchor':'middle'},svg).textContent='noč na soboto';
  S('line',{x1:L+nw[0]*cw,x2:L+nw[1]*cw,y1:ye+3,y2:ye+3,stroke:'#93c5fd','stroke-width':1.5},svg);
  // kazalec
  var g=S('g',{'pointer-events':'none'},svg);cur.line=S('line',{y1:yT-2,y2:yS+nd*(rh+gp)-gp,stroke:'#fff','stroke-width':1.5},g);
  cur.dot=S('circle',{r:4.5,fill:TEMPC,stroke:'#0a0f1c','stroke-width':1.5},g);
  cur.x=x;cur.yv=yv;cur.R=R_;
  var ov=S('rect',{x:L,y:0,width:W-L-R,height:HH,fill:'transparent',style:'touch-action:pan-y;cursor:crosshair'},svg);
  function at(ev){var b=svg.getBoundingClientRect();var h=Math.floor((ev.clientX-b.left-L)/cw);return Math.max(0,Math.min(NN-1,h));}
  ov.addEventListener('pointerdown',function(ev){st.h=at(ev);moveCursor();});
  ov.addEventListener('pointermove',function(ev){if(ev.pointerType==='mouse'||ev.buttons){st.h=at(ev);moveCursor();}});
  moveCursor();
}
function moveCursor(){
  if(!cur.x)return;var h=st.h,X=cur.x(h);cur.line.setAttribute('x1',X);cur.line.setAttribute('x2',X);
  cur.dot.setAttribute('cx',X);cur.dot.setAttribute('cy',cur.yv(cur.R.t1[h]));rng.value=h;
  var R_=cur.R,s=R_.s[h]||0,m=R_.m[h]||0,r=R_.r[h]||0,dry=Math.max(0,100-s-m-r);
  var html='<div class="sn-rd-h"><b>'+lbl(h)+'</b> · '+st.el+' m · '+SYSN[st.sys]+'</div>';
  html+='Temperatura <b>'+fmt(R_.t1[h])+' °C</b> <small>(od '+fmt(R_.t0[h])+' do '+fmt(R_.t2[h])+' °C pri 10. in 90. percentilu)</small>';
  html+='<div class="sn-pills"><span class="sn-pill"><i style="background:'+SNOW+'"></i>sneg '+s+' %</span><span class="sn-pill"><i style="background:'+MIX+'"></i>dež s snegom '+m+' %</span><span class="sn-pill"><i style="background:'+RAIN+'"></i>dež '+r+' %</span><span class="sn-pill"><i style="background:rgba(255,255,255,.15)"></i>suho '+dry+' %</span></div>';
  html+='<div class="sn-chips">';
  D.det.forEach(function(md){var f=md.elev[st.el].f[h],t=md.elev[st.el].t[h];
    html+='<span class="sn-chip"><i style="background:'+(f==null?'rgba(255,255,255,.12)':CCOL[f])+'"></i>'+md.short+': '+(f==null?'izven dosega':CLS[f]+', '+fmt(t)+' °C')+'</span>';});
  html+='</div>';rd.innerHTML=html;
}
rng.max=NN-1;
rng.addEventListener('input',function(){st.h=+rng.value;moveCursor();});

/* ---------- 2) višine ---------- */
var WOPTS=[{v:'night',l:'Noč na soboto'},{v:'sat',l:'Sobota'},{v:'sun',l:'Nedelja'},{v:'all',l:'Do ponedeljka'}];
var MOPTS=[{v:'0',l:'Sneg ali dež s snegom'},{v:'1',l:'vsaj 1 cm'},{v:'2',l:'vsaj 5 cm'}];
var elevBox=$('sn-elev'),elevNote=$('sn-elev-note');
function drawElev(){
  elevBox.innerHTML='';
  D.elevs.forEach(function(e){
    var W_=D.win[e][st.win],pv=W_.all[+st.met];
    var row=H('button',{type:'button',class:'sn-erow'+(String(e)===st.el?' sel':''),'aria-label':e+' m: skupaj '+pv+' %'},'',elevBox);
    var nm=D.elLab[e]||'';
    H('span',{class:'sn-el-l'},e+' m'+(nm?'<small>'+nm+'</small>':''),row);
    var tr=H('span',{class:'sn-track'},'',row);H('span',{class:'sn-bar',style:'width:'+pv+'%'},'',tr);
    D.sys.forEach(function(s,i){var v=W_[s.id][+st.met];H('i',{class:'sn-dot d'+i,style:'left:'+v+'%;background:'+s.color,title:s.label+': '+v+' %'},'',tr);});
    H('span',{class:'sn-el-v'},pv+' %',row);
    row.addEventListener('click',function(){st.el=String(e);drawElev();drawHourly();});
  });
  var W2=D.win[st.el][st.win];
  elevNote.innerHTML='Pri <b>'+st.el+' m</b> skupaj <b>'+W2.all[+st.met]+' %</b> članov. '+D.sys.map(function(s){return s.short+' '+W2[s.id][+st.met]+' %';}).join(' · ')+'.';
}

/* ---------- 3) zemljevid ---------- */
var mapBox=$('sn-map'),rankBox=$('sn-rank'),detBox=$('sn-town'),mrd=$('sn-map-read'),mrng=$('sn-map-range');
var ms={h:D.mapHour,mode:'c',town:D.towns.filter(function(t){return t.n==='Rečica ob Savinji';})[0].n};
var STOPS=[[0,[30,43,68]],[.3,[70,110,172]],[.62,[168,200,244]],[1,[255,255,255]]];
function ramp(v){var t=Math.sqrt(Math.max(0,Math.min(100,v))/100),i=1;while(i<STOPS.length-1&&t>STOPS[i][0])i++;
  var a=STOPS[i-1],b=STOPS[i],u=(t-a[0])/(b[0]-a[0]);return 'rgb('+[0,1,2].map(function(k){return Math.round(a[1][k]+(b[1][k]-a[1][k])*u);}).join(',')+')';}
function mval(t,h){return ms.mode==='c'?t.cum[h]:Math.min(100,(t.snow[h]||0)+(t.mix[h]||0));}
function drawMap(){
  var W=Math.max(300,mapBox.clientWidth||560),b=D.bbox,k=Math.cos(46.1*Math.PI/180);
  var Hm=Math.round(W*(b[3]-b[1])/((b[2]-b[0])*k));mapBox.innerHTML='';
  var svg=S('svg',{width:W,height:Hm,viewBox:'0 0 '+W+' '+Hm,role:'img','aria-label':'Zemljevid Slovenije z deležem članov ansamblov, pri katerih v izbranem kraju sneži. Podatki so tudi v seznamu ob zemljevidu.'},mapBox);
  var px=function(lon,lat){return [ (lon-b[0])/(b[2]-b[0])*W, (b[3]-lat)/(b[3]-b[1])*Hm ];};
  var d='';D.poly.forEach(function(p,i){var q=px(p[0],p[1]);d+=(i?'L':'M')+q[0].toFixed(1)+' '+q[1].toFixed(1);});
  S('path',{d:d+'Z',fill:'rgba(255,255,255,.045)',stroke:'rgba(255,255,255,.30)','stroke-width':1.2,'stroke-linejoin':'round'},svg);
  var order=D.towns.slice().sort(function(a,b){return a.lat<b.lat?1:-1;});
  order.forEach(function(t){
    var q=px(t.lon,t.lat),v=mval(t,ms.h),sel=t.n===ms.town,nar=W<480,rr=nar?8:10.5;
    var g=S('g',{style:'cursor:pointer',tabindex:0,role:'button','aria-label':t.n+', '+t.elev+' m: '+v+' %'},svg);
    if(sel)S('circle',{cx:q[0],cy:q[1],r:rr+4.5,fill:'none',stroke:'#93c5fd','stroke-width':2},g);
    S('circle',{cx:q[0],cy:q[1],r:rr,fill:ramp(v),stroke:'rgba(10,15,28,.9)','stroke-width':1.5},g);
    var tx=S('text',{x:q[0],y:q[1]+3.6,'text-anchor':'middle','font-size':nar?9:10,'font-weight':700,fill:v>45?'#0a0f1c':'#e8edf8'},g);tx.textContent=v;
    if(sel||(!nar&&D.showName.indexOf(t.n)>-1)){var nm=S('text',{x:q[0],y:q[1]-rr-6,'text-anchor':'middle','font-size':11,fill:INK,'paint-order':'stroke',stroke:'#0a0f1c','stroke-width':3},g);nm.textContent=t.short;}
    g.addEventListener('click',function(){ms.town=t.n;drawMap();drawRank();drawTown();});
    g.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();ms.town=t.n;drawMap();drawRank();drawTown();}});
  });
}
function drawRank(){
  var arr=D.towns.slice().sort(function(a,b){return mval(b,ms.h)-mval(a,ms.h)||a.elev-b.elev;});
  rankBox.innerHTML='';$('sn-rank-t').textContent=ms.mode==='c'?'Najvišji deleži (vsaj 1 cm do izbrane ure)':'Najvišji deleži (v izbrani uri)';
  arr.slice(0,8).concat(arr.slice(8).filter(function(t){return t.n===ms.town;})).forEach(function(t){
    var li=H('li',null,'',rankBox),bt=H('button',{type:'button',class:t.n===ms.town?'sel':''},'<span>'+t.short+' <small>'+t.elev+' m</small></span><b>'+mval(t,ms.h)+' %</b>',li);
    bt.addEventListener('click',function(){ms.town=t.n;drawMap();drawRank();drawTown();});
  });
}
function drawTown(){
  var t=D.towns.filter(function(x){return x.n===ms.town;})[0],h=ms.h;
  var W=Math.max(260,detBox.clientWidth||320),Hs=64,cw=W/NN;
  var html='<div class="sn-rd-h"><b>'+t.n+'</b> · '+t.elev+' m</div>V tej uri sneži pri <b>'+(t.snow[h]||0)+' %</b> članov, dež s snegom pri '+(t.mix[h]||0)+' %. Do te ure vsaj 1 cm snega pri <b>'+t.cum[h]+' %</b>. Do ponedeljka: sneg ali dež s snegom '+t.any+' %, vsaj 1 cm '+t.cm1+' %, vsaj 5 cm '+t.cm5+' %.';
  detBox.innerHTML=html;
  var svg=S('svg',{width:W,height:Hs+16,viewBox:'0 0 '+W+' '+(Hs+16),role:'img','aria-label':'Delež članov, pri katerih v kraju '+t.n+' sneži, po urah','style':'max-width:none;width:100%;margin-top:.5rem'},detBox);
  for(var i=0;i<NN;i++){var s=t.snow[i]||0,m=t.mix[i]||0,hs=s/100*Hs,hm=m/100*Hs;
    if(hs>.2)S('rect',{x:i*cw,y:Hs-hs,width:cw+.3,height:hs,fill:SNOW},svg);
    if(hm>.2)S('rect',{x:i*cw,y:Hs-hs-hm,width:cw+.3,height:hm,fill:MIX},svg);}
  S('line',{x1:0,x2:W,y1:Hs,y2:Hs,stroke:'rgba(255,255,255,.2)'},svg);
  S('line',{x1:(h+.5)*cw,x2:(h+.5)*cw,y1:0,y2:Hs,stroke:'#fff','stroke-width':1.5},svg);
  for(i=0;i<NN;i+=24){S('text',{x:i*cw+3,y:Hs+12,fill:MUT,'font-size':10},svg).textContent=DAY[when(i).getDay()];}
}
function mapAll(){
  mrng.value=ms.h;
  mrd.innerHTML='<b>'+lbl(ms.h)+'</b> · '+(ms.mode==='c'?'delež članov, pri katerih je do te ure nastal vsaj 1 cm snega':'delež članov, pri katerih v tej uri sneži ali dežuje s snegom');
  drawMap();drawRank();drawTown();
}
var MODES=[{v:'c',l:'Do izbrane ure vsaj 1 cm'},{v:'h',l:'V izbrani uri sneži'}];
seg('sn-map-mode',MODES,ms.mode,function(v){ms.mode=v;mapAll();},'Kazalnik zemljevida');
var JUMPS=D.jumps;var jb=$('sn-map-jumps');JUMPS.forEach(function(j){var b=H('button',{type:'button',class:'sn-btn'},j.l,jb);b.addEventListener('click',function(){ms.h=j.h;mapAll();});});
var play=$('sn-map-play'),timer=null;
play.addEventListener('click',function(){
  if(timer){clearInterval(timer);timer=null;play.textContent='▶ Predvajaj';return;}
  if(ms.h>=NN-1)ms.h=D.jumps[0].h-12;play.textContent='❚❚ Ustavi';
  timer=setInterval(function(){ms.h++;if(ms.h>=NN-1){clearInterval(timer);timer=null;play.textContent='▶ Predvajaj';}mapAll();},140);
});
mrng.max=NN-1;mrng.addEventListener('input',function(){ms.h=+mrng.value;mapAll();});

/* ---------- zagon ---------- */
seg('sn-seg-el',ELOPTS,st.el,function(v){st.el=v;drawElev();drawHourly();},'Višina');
seg('sn-seg-sys',SYSOPTS,st.sys,function(v){st.sys=v;drawHourly();},'Ansambel');
seg('sn-seg-win',WOPTS,st.win,function(v){st.win=v;drawElev();},'Okno');
seg('sn-seg-met',MOPTS,st.met,function(v){st.met=v;drawElev();},'Kazalnik');
function all(){drawHourly();drawElev();mapAll();}
all();
var tmr;function rs(){clearTimeout(tmr);tmr=setTimeout(function(){drawHourly();drawMap();drawTown();},120);}
if(window.ResizeObserver){var last=hourBox.clientWidth;new ResizeObserver(function(){if(Math.abs(hourBox.clientWidth-last)>4){last=hourBox.clientWidth;rs();}}).observe(hourBox);}
else window.addEventListener('resize',rs);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
"""


def build_data(S, poly):
    d = S.d
    n = S.n
    ids = S.ids
    sys_meta = []
    for i, sid in enumerate(ids):
        nmem = d["systems"]["366"][sid]["all"]["n"]
        sys_meta.append({"id": sid, "label": f"{SYS_NAME[sid]} ({nmem})", "short": SYS_NAME[sid].split()[0] if sid != "gem_global" else "GEM",
                         "color": SYS_COL[sid]})
    hourly = {}
    for el in d["elevs"]:
        hourly[str(el)] = {}
        for sid in ids + ["all"]:
            r = d["hourly"][str(el)][sid]
            hourly[str(el)][sid] = {"s": r["snow"], "m": r["mix"], "r": r["rain"], "t0": r["t10"], "t1": r["t50"], "t2": r["t90"]}
    short = {"ecmwf_ifs025": "ECMWF", "ecmwf_aifs025_single": "AIFS", "icon_eu": "ICON-EU", "gfs_seamless": "GFS",
             "arpege_europe": "ARPEGE", "ukmo_seamless": "UKMO", "gem_seamless": "GEM"}
    det = []
    for mid, v in d["det"].items():
        det.append({"id": mid, "short": short[mid], "elev": {str(el): {"f": v["elev"][str(el)]["flags"],
                                                                         "t": [None if t is None else round(t, 1) for t in v["elev"][str(el)]["t"]]}
                                                          for el in d["elevs"]}})
    win = {}
    for el in d["elevs"]:
        win[str(el)] = {}
        for w in ("night", "sat", "sun", "all"):
            win[str(el)][w] = {"all": [d["pooled"][str(el)][w][k] for k in ("any", "cm1", "cm5")]}
            for sid in ids:
                win[str(el)][w][sid] = [d["systems"][str(el)][sid][w][k] for k in ("any", "cm1", "cm5")]
    short_town = {"Rečica ob Savinji": "Rečica", "Slovenj Gradec": "Slovenj Gradec", "Murska Sobota": "M. Sobota"}
    towns = []
    for name, t in d["towns"].items():
        towns.append({"n": name, "short": short_town.get(name, name), "lat": t["lat"], "lon": t["lon"], "elev": t["elev"],
                      "snow": t["pooled"]["snow"], "mix": t["pooled"]["mix"], "cum": t["pooled"]["cum1"],
                      "any": t["pooled_all"]["any"], "cm1": t["pooled_all"]["cm1"], "cm5": t["pooled_all"]["cm5"]})
    # privzeta ura zemljevida: ura z največjim deležem članov z vsaj 1 cm v dolini ob Rečici je zadnja; vzamemo soboto 8.00
    h_sat8 = next(h for h in range(n) if S.hr(h).weekday() == 5 and S.hr(h).hour == 8)
    r = d["hourly"]["366"]["all"]
    def_hour = max(range(24, n), key=lambda h: (r["snow"][h] or 0) + (r["mix"][h] or 0))
    jumps = []
    for wd, hh, lab in ((4, 22, "pet 22.00"), (5, 6, "sob 6.00"), (5, 12, "sob 12.00"), (6, 6, "ned 6.00"), (0, 6, "pon 6.00")):
        h = next(h for h in range(n) if S.hr(h).weekday() == wd and S.hr(h).hour == hh)
        jumps.append({"h": h, "l": lab})
    lon = [p[0] for p in poly]
    lat = [p[1] for p in poly]
    bbox = [round(min(lon) - 0.06, 3), round(min(lat) - 0.05, 3), round(max(lon) + 0.06, 3), round(max(lat) + 0.05, 3)]
    # noč na soboto: petek 18.00 do sobota 8.00
    night = [next(h for h in range(n) if S.hr(h).weekday() == 4 and S.hr(h).hour == 18),
             next(h for h in range(n) if S.hr(h).weekday() == 5 and S.hr(h).hour == 8)]
    return {"start": d["start"], "n": n, "elevs": d["elevs"], "defEl": "366", "defHour": def_hour, "mapHour": h_sat8, "night": night,
            "elLab": {"366": "Rečica", "900": "kot Črnivec"}, "sys": sys_meta, "hourly": hourly, "det": det, "win": win,
            "towns": towns, "poly": [[round(p[0], 3), round(p[1], 3)] for p in poly], "bbox": bbox, "jumps": jumps,
            "showName": ["Maribor", "Ljubljana", "Celje", "Novo mesto", "Koper", "Nova Gorica", "Murska Sobota", "Kočevje", "Postojna", "Bovec", "Kranj"]}


def load_poly():
    src = open(os.path.join(ROOT, "app.js"), encoding="utf-8").read()
    m = re.search(r"const SLO_POLY=(\[\[.*?\]\]);", src, re.S)
    assert m, "SLO_POLY ni v app.js"
    return json.loads(m.group(1))


def widgets_html(S):
    data = build_data(S, load_poly())
    js_data = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    legend = (f'<p class="vs-leg"><span><i style="background:{C_SNOW}"></i>sneg</span><span><i style="background:{C_MIX}"></i>dež s snegom</span>'
              f'<span><i style="background:{C_RAIN}"></i>dež</span><span><i style="background:rgba(255,255,255,.12)"></i>suho</span>'
              f'<span><i style="background:#fbbf24"></i>temperatura</span></p>')
    hourly = (
        '<figure class="vs-fig sn-wide"><h3>Ura za uro: temperatura, padavine in vsi modeli</h3>'
        '<div class="sn-ctl"><div class="sn-grp"><span class="sn-lab">Višina</span><div class="sn-seg" id="sn-seg-el"></div></div>'
        '<div class="sn-grp"><span class="sn-lab">Ansambel</span><div class="sn-seg" id="sn-seg-sys"></div></div></div>'
        + legend +
        '<div class="sn-chart" id="sn-hour-chart"></div>'
        '<input class="sn-range" id="sn-hour-range" type="range" min="0" max="119" step="1" value="0" aria-label="Izberite uro od četrtka do ponedeljka">'
        '<div class="sn-read" id="sn-hour-read" aria-live="off"></div>'
        '<noscript><p class="vs-note">Za ta graf je potreben JavaScript. Ključne številke so v besedilu pod grafom.</p></noscript>'
        '<figcaption>Zgoraj je temperatura zraka na izbrani višini (črta je mediana članov izbranega ansambla, pas razpon od 10. do 90. percentila). V sredini je za vsako uro '
        'delež članov, pri katerih tedaj sneži (belo), dežuje s snegom (vijolično) ali dežuje (modro). Spodaj je sedem posameznih modelov, vsak z enim tekom. '
        'Premaknite drsnik ali se dotaknite grafa. Svetlo modro ozadje je noč na soboto, od petka ob 18. uri do sobote ob 8. uri.</figcaption></figure>')
    elev = (
        '<figure class="vs-fig sn-wide"><h3>Koliko članov napove sneg, glede na višino</h3>'
        '<div class="sn-ctl"><div class="sn-grp"><span class="sn-lab">Obdobje</span><div class="sn-seg" id="sn-seg-win"></div></div>'
        '<div class="sn-grp"><span class="sn-lab">Kaj šteje</span><div class="sn-seg" id="sn-seg-met"></div></div></div>'
        '<p class="vs-leg"><span><i style="background:linear-gradient(90deg,#9db8e6,#f1f5f9)"></i>vsi člani skupaj</span>'
        + "".join(f'<span><svg class="sn-ico" viewBox="0 0 14 14" width="14" height="14">'
                  f'{shape(SHAPES[sid], 7, 7, 3.6, SYS_COL[sid], True)}</svg>{SYS_NAME[sid]}</span>' for sid in S.ids) + '</p>'
        '<div id="sn-elev"></div><p class="sn-read" id="sn-elev-note" aria-live="polite" style="margin-top:.7rem"></p>'
        '<noscript><p class="vs-note">Za ta graf je potreben JavaScript. Ključne številke so v besedilu pod grafom.</p></noscript>'
        '<figcaption>Vsaka vrstica je ena višina nad Rečico; dotik vrstice izbere to višino tudi v grafu zgoraj. Stolpec je delež vseh 143 članov, '
        'liki pa pokažejo delež posameznega ansambla: razmik med njimi je mera, koliko se sistemi razhajajo. '
        'Višino sem popravil z običajnim temperaturnim gradientom, kar je poenostavitev.</figcaption></figure>')
    maps = (
        '<figure class="vs-fig sn-wide"><h3>Slovenija: kje ima sneg več možnosti</h3>'
        '<div class="sn-ctl"><div class="sn-grp"><span class="sn-lab">Kazalnik</span><div class="sn-seg" id="sn-map-mode"></div></div>'
        '<div class="sn-grp"><span class="sn-lab">Skoči na</span><div class="sn-jumps" id="sn-map-jumps" style="display:flex;flex-wrap:wrap;gap:.35rem"></div></div></div>'
        '<div class="sn-map-wrap"><div><div class="sn-chart" id="sn-map"></div>'
        '<input class="sn-range" id="sn-map-range" type="range" min="0" max="119" step="1" value="0" aria-label="Izberite uro za zemljevid">'
        '<div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap"><button type="button" class="sn-btn" id="sn-map-play">▶ Predvajaj</button>'
        '<span class="sn-lab">0 %</span><span class="sn-ramp" style="flex:1;min-width:110px;background:linear-gradient(90deg,rgb(30,43,68),rgb(70,110,172) 30%,rgb(168,200,244) 62%,#fff)"></span><span class="sn-lab">100 %</span></div>'
        '<div class="sn-read" id="sn-map-read" aria-live="off" style="margin-top:.6rem"></div></div>'
        '<div><p class="sn-lab" id="sn-rank-t" style="margin-bottom:.4rem">Najvišji deleži</p><ol class="sn-rank" id="sn-rank"></ol>'
        '<div class="sn-read" id="sn-town"></div></div></div>'
        '<noscript><p class="vs-note">Za zemljevid je potreben JavaScript.</p></noscript>'
        '<figcaption>Barva in številka v krogu sta delež vseh 143 članov, pri katerih velja izbrani kazalnik za ta kraj. Vsak kraj je izračunan na svoji višini. '
        'Izberite kraj na zemljevidu ali v seznamu, spodaj pa se pokaže njegov potek po urah. Krogi niso merilna mesta, ampak točke modela.</figcaption></figure>')
    script = f"<script>window.SN_D={js_data};</script><script>{WIDGET_JS}</script>"
    return hourly, elev, maps, script


# ───────────────────────── članek ─────────────────────────

def build_article(S):
    d = S.d
    pooled = lambda el, w, k: S.pooled(el, w, k)
    n_mem = d["pooled"]["366"]["all"]["n"]
    assert n_mem == 143, n_mem
    ecm = {w: S.sysv(366, w, "ecmwf_ifs025", "cm1") for w in ("all", "night")}
    icon_c1 = S.sysv(366, "all", "icon_seamless", "cm1")
    gefs_c1 = S.sysv(366, "all", "gfs025", "cm1")
    gem_c1 = S.sysv(366, "all", "gem_global", "cm1")
    c1_by = {sid: S.sysv(366, "all", sid, "cm1") for sid in S.ids}
    order = sorted(S.ids, key=lambda sid: -c1_by[sid])
    hi_sys, lo_sys = order[0], order[-1]
    hi_v, lo_v = c1_by[hi_sys], c1_by[lo_sys]
    ANY, C1, C5 = pooled(366, "all", "any"), pooled(366, "all", "cm1"), pooled(366, "all", "cm5")
    C1_500, C1_700, C1_900, C1_1200 = (pooled(e, "all", "cm1") for e in (500, 700, 900, 1200))
    C5_900, C5_1200 = pooled(900, "all", "cm5"), pooled(1200, "all", "cm5")
    ANY_700, ANY_900 = pooled(700, "all", "any"), pooled(900, "all", "any")
    TF = d["pooled"]["366"]["thufri"]
    FROST_SUN = {e: pooled(e, "sun", "frost") for e in (366, 500, 700, 900)}
    SUN = d["pooled"]["366"]["sun"]

    # --- struktura zgodbe (če se obrne, članek ni več pravilen) ---
    th = d["hourly"]["366"]["all"]
    assert all((th["snow"][h] or 0) + (th["mix"][h] or 0) <= 1 for h in range(24)), "v četrtek sneg v dolini ni več izključen"
    assert min(th["t50"][h] for h in range(24)) >= 5.0, "četrtek v dolini ni več topel"
    assert C1_1200 > C1_900 > C1_700 > C1_500 > C1 >= 3, (C1, C1_500, C1_700, C1_900, C1_1200)
    assert C1 < 35 and C5 <= 15, f"sneg v dolini ni več manj verjeten kot ne: {C1} {C5}"
    assert max(ecm["all"], icon_c1, gefs_c1, gem_c1) - min(ecm["all"], icon_c1, gefs_c1, gem_c1) >= 15, "ansambli se ne razhajajo več"
    assert C1_900 >= 50, "na 900 m sneg ni več bolj verjeten kot ne"
    assert 20 <= TF["mm50"] <= 120, TF
    assert FROST_SUN[366] >= 20 and FROST_SUN[900] > FROST_SUN[366], FROST_SUN

    # --- čas ohladitve po sistemih ---
    arr = {}
    for sid in S.ids:
        a_ = sorted(x for x in d["front"][sid]["arrive_h"] if x is not None)
        arr[sid] = (a_[len(a_) // 2], len(a_), d["front"][sid]["n"])
    pts = scatter_stats(S)
    snowy = [p for p in pts if p[3] >= 1]
    sat12 = next(h for h in range(S.n) if S.hr(h).weekday() == 5 and S.hr(h).hour == 12)
    snowy_early = [p for p in snowy if p[1] is not None and p[1] <= sat12]
    snowy_wet = [p for p in snowy if p[2] is not None and p[2] >= 1]
    assert snowy and len(snowy_wet) >= 0.7 * len(snowy), (len(snowy), len(snowy_wet))
    share_wet = round(100 * len(snowy_wet) / len(snowy))
    share_early = round(100 * len(snowy_early) / len(snowy))
    with_front = [p for p in pts if p[1] is not None]
    no_front = len(pts) - len(with_front)

    rec = d["hourly"]["366"]["all"]
    h_t5 = next(h for h in range(24, S.n) if rec["t50"][h] <= 5)
    h_t3 = next((h for h in range(24, S.n) if rec["t50"][h] <= 3), None)
    fri12 = next(h for h in range(S.n) if S.hr(h).weekday() == 4 and S.hr(h).hour == 12)
    rain_fri12 = rec["rain"][fri12]
    sat4 = next(h for h in range(S.n) if S.hr(h).weekday() == 5 and S.hr(h).hour == 4)
    dry_sat4 = 100 - (rec["snow"][sat4] or 0) - (rec["mix"][sat4] or 0) - (rec["rain"][sat4] or 0)
    peak_snow = max(rec["snow"][h] + rec["mix"][h] for h in range(24, S.n))
    peak_snow_900 = max(d["hourly"]["900"]["all"]["snow"][h] + d["hourly"]["900"]["all"]["mix"][h] for h in range(24, S.n))

    towns = {k: v for k, v in d["towns"].items()}
    town_rank = sorted(towns.items(), key=lambda kv: -kv[1]["pooled_all"]["cm1"])
    top = town_rank[:3]
    low = sorted(((k, v["pooled_all"]["cm1"]) for k, v in towns.items() if v["pooled_all"]["cm1"] <= 3), key=lambda kv: kv[1])
    assert any(k == "Koper" for k, _ in low), low
    low_txt = ", ".join(f"{k} ({v} %)" for k, v in low)
    cm1_t = lambda n: towns[n]["pooled_all"]["cm1"]
    assert cm1_t("Kranj") > cm1_t("Bled") and cm1_t("Velenje") > cm1_t("Bled") and towns["Bled"]["elev"] > towns["Kranj"]["elev"], "primerjava Kranj/Velenje/Bled ne drži več"

    thu_t850 = []
    for k in ("ecmwf_ifs025", "gfs_seamless", "icon_eu", "ukmo_seamless", "gem_seamless", "arpege_europe"):
        thu_t850.append([x for x in d["det"][k]["elev"]["366"]["t850"][0:24] if x is not None])
    t850_lo = round(min(min(x) for x in thu_t850 if x))
    t850_hi = round(max(max(x) for x in thu_t850 if x))

    arr_sorted = sorted(S.ids, key=lambda sid: arr[sid][0])
    early_s, late_s = arr_sorted[0], arr_sorted[-1]
    def behind_med(sid):
        v = sorted(x for x in d["front"][sid]["behind_mm"] if x is not None)
        return v[len(v) // 2]
    when_early, when_late = S.ob(arr[early_s][0]), S.ob(arr[late_s][0])
    bm_early, bm_late = behind_med(early_s), behind_med(late_s)

    tots = []
    for k, v in d["det"].items():
        pp = v["elev"]["366"]["p"][0:48]
        if all(x is not None for x in pp):
            tots.append(sum(pp))
    rain_lo, rain_hi = round(min(tots)), round(max(tots))
    hourly_w, elev_w, map_w, script = widgets_html(S)

    # --- ploščice ---
    t_tiles = tiles([
        (f'{TF["mm50"]}', "mm", f'dežja v Rečici v četrtek in petek (mediana ansambla; devet desetin članov napove od {TF["mm10"]} do {TF["mm90"]} mm)', False),
        (f"{C1}", "%", "članov ansamblov napove na dnu doline (366 m) vsaj 1 cm snega do ponedeljka", True),
        (f"{C1_900}", "%", "isto na 900 m, kot je Črnivec: tam je sneg bolj verjeten kot ne", False),
        (f'{FROST_SUN[366]}', "%", "članov: v nedeljo zjutraj v dolini 0 °C ali manj, tudi če sneg ne pride", False),
    ])

    lead = (f"V četrtek in petek bo v Rečici po modelih padlo okoli <strong>{TF['mm50']} mm dežja</strong>, ne snega: nad dolino je še topel zrak. "
            f"Hladna fronta pride šele ob koncu padavin, zato je sneg v nižinah odvisen od tega, ali bo za njo še kaj padlo. "
            f"Po {n_mem} članih štirih ansamblov dobi dno doline do ponedeljka <strong>vsaj 1 cm snega v {C1} %</strong> primerov, na 900 m pa v {C1_900} %.")

    p1 = [
        "<strong>Kratek odgovor: v četrtek je sneg v nižinah po modelih praktično izključen, v noči na soboto je možen, a manj verjeten kot ne.</strong> "
        f"V četrtek in petek je temperatura na višini 850 hPa (približno 1,5 km) po modelih med {t850_lo} in {t850_hi} °C. "
        "Hladen zrak prihaja v valu, ki ga modeli postavijo na petek zvečer in soboto, ko je glavnina padavin že mimo.",
        "Podatki v številkah:",
        t_tiles,
        f"Številke izhajajo iz {n_mem} članov štirih ansamblov: ECMWF ENS ({d['systems']['366']['ecmwf_ifs025']['all']['n']}), ICON-EPS ({d['systems']['366']['icon_seamless']['all']['n']}), "
        f"GEFS ({d['systems']['366']['gfs025']['all']['n']}) in GEM ENS ({d['systems']['366']['gem_global']['all']['n']}). Član je ena možna različica vremena, "
        "delež članov je torej ocena verjetnosti, ne obljuba. "
        "Za »sneg« sem vzel padavino pri temperaturi zraka do 1,5 °C na višini kraja, med 0,5 in 2,5 °C je delež snega sorazmeren. Več o tem je v razdelku o omejitvah.",
    ]

    p2 = [
        f"Četrtek je še v toplem sektorju pred fronto. Temperatura na 850 hPa je med {t850_lo} in {t850_hi} °C, ničelna izoterma je blizu treh kilometrov, "
        "sneženja torej ni niti na višjih legah. Padavine se okrepijo v petek, ko prek doline potuje fronta.",
        fig_rain(S),
        f"Skupaj modeli napovedujejo za četrtek in petek od {rain_lo} do {rain_hi} mm. Mediana ansambla je <strong>{TF['mm50']} mm</strong>, "
        f"devet desetin članov pa napove od {TF['mm10']} do {TF['mm90']} mm. To je veliko padavin za dva dni in za tla pomeni, da bodo mokra in topla, "
        "ko se ohladi. Ravno zato sneženje v dolini še ne pomeni bele podlage.",
        "Takšna količina dežja se bo poznala tudi na rekah. Stanje spremljajte na "
        f'{a("/vodostaj-savinje/", "strani o vodostaju Savinje")} in pri ARSO; ta članek ni opozorilo.',
    ]

    p3 = [
        f"Spodnji graf je jedro članka. Pokaže, kako se uro za uro menjata dež in sneg, kdaj pade temperatura in kaj o tem pravi vsak model posebej. "
        "Izberite višino in ansambel ter premaknite drsnik.",
        hourly_w,
        "Kaj se vidi:",
        "<ul>"
        f"<li><strong>Petek čez dan je dež.</strong> V petek opoldne dežuje v dolini {rain_fri12} % članov, sneži pri nobenem.</li>"
        f"<li><strong>Mraz pride, ko padavine že pojenjajo.</strong> Mediana temperature v dolini pade pod 5 °C {S.ob(h_t5)}; v soboto ob 4. uri je suho že pri {dry_sat4} % članov.</li>"
        f"<li><strong>Tudi v najugodnejši uri je sneg v dolini manjšina.</strong> V tej uri sneži ali dežuje s snegom v dolini {peak_snow} % članov, na 900 m pa {peak_snow_900} %.</li>"
        "</ul>",
    ]

    ranked = ", ".join(f"{c1_by[sid]} % {SYS_NAME[sid]}" for sid in order)
    p4 = [
        f"Ansambli se pri vprašanju o snegu v dolini razhajajo bolj, kot bi bilo udobno. Do ponedeljka vsaj 1 cm snega v dolini napove "
        f"<strong>{hi_v} %</strong> članov ansambla {SYS_NAME[hi_sys]} in le {lo_v} % ansambla {SYS_NAME[lo_sys]}. Po vrsti: {ranked}. "
        "Spodnji graf pokaže te razlike za vsako višino in obdobje.",
        elev_w,
        f"Z višino verjetnost hitro raste: pri 500 m je {C1_500} %, pri 700 m {C1_700} %, pri 900 m {C1_900} % in pri 1200 m {C1_1200} %. "
        f"Vsaj 5 cm snega napove na 900 m {C5_900} % članov, na 1200 m pa {C5_1200} %.",
        f"Razhajanje ima konkretno obliko: mediana ohladitve je pri {SYS_NAME[early_s]} {when_early}, pri {SYS_NAME[late_s]} šele {when_late}. "
        f"V 48 urah po ohladitvi pade po mediani {num(bm_early)} mm pri prvem in {num(bm_late)} mm pri drugem. "
        "Kdo ima prav, bo jasno šele z novimi teki modelov.",
    ]

    p5 = [
        "Sneg v dolini potrebuje tri stvari hkrati: dovolj hladen zrak, padavine v tistem trenutku in dovolj padavin, da se karkoli nabere. "
        "Razsevni diagram spodaj pokaže prvi dve: kdaj se ohladi in koliko pade potem.",
        fig_scatter(S, pts),
        f"Od {len(snowy)} članov, ki v dolini naredijo vsaj 1 cm snega, jih {share_wet} % po ohladitvi dobi vsaj 1 mm padavin, "
        f"{share_early} % pa se ohladi do sobote opoldne. {no_front} od {len(pts)} članov se do ponedeljka sploh ne ohladi na 3 °C ali manj, ti sneg v dolini ne naredijo.",
    ]

    town_txt = ", ".join(f"{k} ({v['elev']} m) {v['pooled_all']['cm1']} %" for k, v in top)
    p6 = [
        "Zemljevid pokaže iste podatke za 20 krajev. Vsak kraj je izračunan na svoji višini, kazalnik je delež vseh članov. "
        "Premaknite drsnik ali pritisnite predvajanje.",
        map_w,
        f"Najvišji deleži do ponedeljka (vsaj 1 cm): {town_txt}. "
        f"Najmanj možnosti imajo {low_txt}. "
        "Zakaj je razporeditev takšna, iz teh podatkov ne morem zanesljivo ugotoviti: višina je pomembna, a sama ne razloži vsega, saj imata Kranj (385 m) in Velenje (390 m) več kot Bled (475 m).",
    ]

    scen_a = 100 - ANY
    scen_b = ANY - C1
    scen_c = C1
    scenarios = (
        f'<div class="sn-stack" role="img" aria-label="Brez snega {scen_a} %, rahlo {scen_b} %, vsaj 1 cm {scen_c} %">'
        f'<span style="width:{scen_a}%;background:{C_RAIN}"></span><span style="width:{scen_b}%;background:{C_MIX}"></span><span style="width:{scen_c}%;background:{C_SNOW}"></span></div>'
        '<div class="sn-scen">'
        f'<div class="sn-sc"><b class="big">{scen_a} %</b><h4><span class="tag" style="background:{C_RAIN}"></span>Dež, nato mraz</h4>'
        "<p>Dež preneha, preden se ohladi. V nedeljo zjutraj je v dolini mrzlo, na mokrih cestah je poledica, snega ni.</p></div>"
        f'<div class="sn-sc"><b class="big">{scen_b} %</b><h4><span class="tag" style="background:{C_MIX}"></span>Poprh ali dež s snegom</h4>'
        "<p>Ob koncu padavin pade dež s snegom ali nekaj snežink, a manj kot 1 cm. Mokra tla ga pogoltnejo.</p></div>"
        f'<div class="sn-sc"><b class="big">{scen_c} %</b><h4><span class="tag" style="background:{C_SNOW}"></span>Bela podlaga</h4>'
        f"<p>Ohladitev ujame še padavine: vsaj 1 cm, pri {C5} % članov vsaj 5 cm. Prej na višjih legah, v dolini zlasti v noči na soboto.</p></div></div>"
    )
    p7 = [
        "Za dno doline vidim tri možne poteke. Deleži so seštevek članov, ne napoved, in se bodo z novimi teki spreminjali.",
        scenarios,
        f"Kdor bi stavil, bi stavil na prvo možnost. Druge dve nista zanemarljivi: najbolj snežni ansambel, {SYS_NAME[hi_sys]}, pripisuje vsaj 1 cm snega {hi_v} % članov.",
    ]

    p8 = [
        f"Najbolj verjeten rezultat je tudi najmanj opazen: mraz. V nedeljo zjutraj je temperatura v dolini po {n_mem} članih 0 °C ali manj pri <strong>{FROST_SUN[366]} %</strong> članov, "
        f"pri 500 m pri {FROST_SUN[500]} %, pri 700 m pri {FROST_SUN[700]} % in pri 900 m pri {FROST_SUN[900]} %. "
        f"Mediana nedeljske najnižje temperature v dolini je {temp(SUN['tmin50'])}, najhladnejša desetina članov pa napove {temp(SUN['tmin10'])} ali manj.",
        "To pomeni poledico na mokrih cestah, tudi kjer sneg ne pade. Oceno poledice za naslednje dni najdete na "
        f'{a("/zima/poledica/", "strani o poledici")}, razliko med žledom in poledico pa sem pojasnil {a("/blog/zled-ali-poledica-razlika-1027.html", "v članku o žledu")}.',
    ]

    p9 = [
        "<ul>"
        f'<li><strong>Zimska oprema:</strong> če še niste menjali gum, je kritičen odsek od petka zvečer do nedelje zjutraj. Kdaj je to običajno smiselno in kaj velja po pravilih, '
        f'sem zbral {a("/blog/kdaj-menjati-zimske-gume-recica-1027.html", "v članku o zimskih gumah")}; za pravila preverite AMZS.</li>'
        f'<li><strong>Čez prelaze:</strong> na 900 m (kot Črnivec) vsaj 1 cm snega napove {C1_900} % članov. Stanje meritve na prelazu je na {a("https://crnivec.si/", "crnivec.si")}, '
        f'več o snegu tam pa {a("/blog/crnivec-pozimi-sneg-verige-1027.html", "v članku o Črnivcu pozimi")}.</li>'
        f'<li><strong>Opozorilo na telefon:</strong> na strani {a("/zima/meja-snezenja/", "meja sneženja")} si lahko nastavite obvestilo za sneg v dolini za danes ali jutri.</li>'
        f'<li><strong>Karta in gore:</strong> {a("/zima/snezna-karta/", "snežna karta")} bo z bližanjem petka pokazala tudi ta dan, {a("/vreme-v-gorah/", "vreme v gorah")} pa kaže ocene na vrhovih.</li>'
        f'<li><strong>Prvi sneg v dolini:</strong> kdaj je v zadnjih letih prvi sneg v dolini običajno padel, je v {a("/blog/kdaj-pade-prvi-sneg-v-dolini-recica-1027.html", "članku o prvem snegu")}.</li>'
        "</ul>",
    ]

    omejitve = [
        "<ul>"
        f"<li><strong>Dež ali sneg je moja poenostavitev.</strong> Ansambli v Open-Meteo nimajo temperature mokrega termometra. Padavino štejem za sneg pri temperaturi zraka do 1,5 °C (v celoti do 0,5 °C), "
        "sorazmerno do 2,5 °C, 1 mm padavin je 1 cm snega. Z drugačno mejo se deleži premaknejo; polja snega, ki ga objavlja Open-Meteo sam, nisem uporabil.</li>"
        "<li><strong>Sneži ni isto kot obleži.</strong> Model ne pozna temperature tal. Po več deset milimetrih dežja so tla mokra in topla, zato rahel sneg ob 1 °C v dolini običajno ne obleži.</li>"
        "<li><strong>Višine so popravljene s standardnim gradientom.</strong> Temperatura na višjih legah je izračunana z običajnim zniževanjem s višino. V resnici je lahko pozimi drugače, zlasti pri inverziji.</li>"
        "<li><strong>Člani niso neodvisni.</strong> 143 članov ni 143 neodvisnih mnenj; večji ansambel ima večjo težo v skupnem deležu (ECMWF ENS je 51 od 143). Zato so ob skupnem deležu posebej prikazani tudi ansambli.</li>"
        "<li><strong>Metoda ni preverjena na preteklih primerih.</strong> Postaja IREICA1 snega ne meri; v teh dneh bo izmerila temperaturo, vlago in padavine, sneg bo treba oceniti s kamer in poročil.</li>"
        f"<li><strong>Članek je posnetek.</strong> Podatki so s prenosa {S.fetched.day}. {S.fetched.month}. {S.fetched.year} ob {S.fetched.hour}.{S.fetched.minute:02d}. "
        "Do četrtka se bodo teki modelov večkrat spremenili in z njimi tudi deleži. Ta članek se ne posodablja samodejno. "
        'Za uradna opozorila spremljajte <a href="https://vreme.arso.gov.si/napoved" style="color:var(--blue)">ARSO</a>; nič v tem članku ni uradno vremensko opozorilo.</li>'
        "</ul>",
        '<p class="vs-note" style="margin-top:1.5rem"><strong>Uporaba vsebine:</strong> Besedilo, grafe in podatke lahko povzemate samo z '
        'navedbo avtorja (Filip Eremita, Meteorec) in neposredno povezavo na ta članek. Za prepis ali vdelavo grafov in izračunov se '
        'predhodno dogovorite z avtorjem.</p>',
    ]

    title = "Sneg v nižinah: četrtek še dež, odloča se v noči na soboto"
    assert len(title) <= 60, len(title)
    desc = (f"Četrtek in petek prineseta dež, sneg v nižinah pa je možen šele ob koncu padavin. Ura za uro, višine in zemljevid iz {n_mem} članov ansamblov.")
    assert len(desc) <= 160, len(desc)
    sections = [
        {"label": "01 — odgovor", "heading": "Četrtek je dež, odločitev pade v noči na soboto", "id": "odgovor", "paragraphs": p1},
        {"label": "02 — četrtek in petek", "heading": "Najprej pride dež, ne sneg", "id": "dez", "paragraphs": p2},
        {"label": "03 — ura za uro", "heading": "Kdaj se ohladi in ali takrat še pada", "id": "ura", "paragraphs": p3},
        {"label": "04 — višine", "heading": "Kdo ima prav: ansambli se razhajajo", "id": "visine", "paragraphs": p4},
        {"label": "05 — mehanizem", "heading": "Kaj mora sovpasti za sneg v dolini", "id": "mehanizem", "paragraphs": p5},
        {"label": "06 — Slovenija", "heading": "Po Sloveniji: kje ima sneg več možnosti", "id": "zemljevid", "paragraphs": p6},
        {"label": "07 — scenariji", "heading": "Trije poteki za dno doline", "id": "scenariji", "paragraphs": p7},
        {"label": "08 — nedelja", "heading": "Če sneg ne pride, pride mraz", "id": "nedelja", "paragraphs": p8},
        {"label": "09 — praktično", "heading": "Kaj lahko naredite", "id": "prakticno", "paragraphs": p9},
        {"label": "10 — omejitve", "heading": "Česa podatki ne povedo", "id": "omejitve", "paragraphs": omejitve},
    ]

    def nb(h):
        return nbsp(h)

    lead = nb(lead)
    for sec in sections:
        sec["paragraphs"] = [x if ("<script" in x or x.lstrip().startswith("<figure")) else nb(x) for x in sec["paragraphs"]]
    # skript gre na konec prvega razdelka z gradnikom (podatki so vdelani samo enkrat)
    sections[2]["paragraphs"].append(script)
    return {
        "title": title, "meta_description": desc,
        "tags": ["sneg", "nižine", "napoved", "ansambli", "zima", "november"],
        "section_label": "Podatkovna analiza", "og_photo": "misty-valley", "og_accent_hex": "#93c5fd",
        "lead": lead, "sections": sections, "callout": None,
        "sources_note": ("Viri: Open-Meteo (modeli ECMWF IFS in AIFS, ICON-EU, GFS, ARPEGE, UKMO, GEM; ansambli ECMWF ENS, ICON-EPS, NCEP GEFS, GEM ENS), "
                         f"prenos z dne {S.fetched.day}. {S.fetched.month}. {S.fetched.year}. Weather data by Open-Meteo.com (CC BY 4.0). "
                         "Obris Slovenije: Natural Earth / app.js. Podatki posnetka: data/sneg-nizine-1109.json."),
    }


STYLE = BASE_STYLE.replace("</style>", "</style>") + "\n" + WIDGET_CSS


def plain_text(article):
    def clean(h):
        h = re.sub(r"<script.*?</script>", "", h, flags=re.S)
        h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
        h = re.sub(r"<style.*?</style>", "", h, flags=re.S)
        h = re.sub(r"</?(h3|h4|figcaption|li|p|div|b)[^>]*>", "\n", h)
        h = re.sub(r"<[^>]+>", "", h)
        h = h.replace("&shy;", "").replace(NBSP, " ")
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
        og_title="Sneg v nižinah:\nčetrtek še dež", meta_note="podatkovna analiza",
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
