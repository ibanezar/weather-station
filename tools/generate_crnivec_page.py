#!/usr/bin/env python3
"""
tools/generate_crnivec_page.py — /crnivec/, humorna stran "Kako je čez Črnivec?"

"Kako je čez Črnivec?" je (po Filipovih besedah) eno najpogostejših vprašanj v
lokalnih FB skupinah — mešanica dveh stvari: (1) odgovori si skoraj vedno
nasprotujejo/so neuporabni, (2) ljudje raje vprašajo, kot da bi pogledali sami.
Ta stran to zafrkava, NAMENOMA ločeno od resne /zima/prevoznost-prelazov/
(ki ostane edina resna referenca — glej cross-link na dnu obeh strani).

Grafično je stran NAMENOMA popolnoma drugačna od preostale strani: stripovska,
udarna, svetla paleta namesto temne Meteorec teme. Glavo/nogo/spodnji meni
skrije isti CSS-trik kot igra/igra.css (glej CLAUDE.md — "Termika" stran) —
uvožen vzorec, ne nov mehanizem. Brez zunanje pisave (Google Fonts): težo
naredi obstoječi samostoječi Inter 800 (najtežji vključen rez, glej
fonts/fonts.css) + CSS text-shadow "obris" trik, ne nov zunanji vir.

Kazalec na merilniku JE resničen (iz istega passes["crnivec"]["weather"], ki
ga računa tools/winter_engine.py — isti lapse-rate/snow_fraction kot na
resni strani) — humor je v NALEPKAH conov in v dnevnem citatu, ne v
izmišljenih podatkih. Citat dneva je deterministično izbran po datumu (isti
vzorec kot izbira teme/različice v generate_story_card.py:
hashlib.sha256(datum|niz)), da je ista cel dan za vse, drug dan pa drugačna.

Piše: crnivec/index.html
Wired into: .github/workflows/zima-forecast.yml (po generate_zima_page.py —
potrebuje isti data/winter-data.json)

Usage:
  python3 tools/generate_crnivec_page.py
"""
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
DATA_PATH = os.path.join(ROOT, "data", "winter-data.json")

# Coni merilnika, levo (najboljše) proti desno (najslabše) — isti vrstni red
# kot na klasičnem "risk" merilniku. Kot je sredina cone na polkrogu
# (180°=levo, 0°=desno, 90°=zgoraj), isti konvenciji sledi needle_angle().
ZONES = [
    {"id": "sonce",    "label": "SUHO K POPR",    "color": "#16a34a", "mid": 157.5},
    {"id": "nekaj",    "label": "JE, PA NEKAJ",   "color": "#eab308", "mid": 112.5},
    {"id": "verige",   "label": "VZEMI VERIGE",   "color": "#ea580c", "mid": 67.5},
    {"id": "spolzko",  "label": "SPOLZKO, PAZI",  "color": "#dc2626", "mid": 22.5},
]

# Izvirni citati v duhu šale (glej opombo zgoraj) — NISO navedki resničnih
# objav, ker jih nimamo preverjenih; namenoma zvenijo kot tipičen odgovor v
# FB skupini. Če imaš prave, jih zamenjaj tu.
QUOTES = [
    "Meni je teta rekla, da je suho. Sosed pravi katastrofa. Nekdo laže.",
    "Grem pogledat in sporočim… čez kakšne tri ure.",
    "Odvisno, kdaj vprašaš — in koga.",
    "Kamera kaže sonce, komentarji pod njo pravijo drugače.",
    "Bilo je super, ko sem jaz šel. Pred dvema letoma, poleti.",
    "Pol skupine pravi zimske, pol pravi, da ni treba. Vzemi obe mnenji.",
    "Vprašaj raje v skupini — jaz osebno ne grem gledat zate.",
    "Nekdo je pravkar vprašal isto. Odgovori so spet drugačni kot včeraj.",
    "Tehnično prevozno. Praktično — na lastno odgovornost, kot vedno.",
    "Tale indeks pravi eno, dedek pa drugo. Dedek ima še vedno prav pogosteje.",
]


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def pick_zone(weather):
    """Resnična izbira cone iz izračunanega vremena na Črnivcu (weather =
    passes["crnivec"]["weather"] iz winter_engine.py) — samo nalepka/barva
    je šala, uvrstitev ne."""
    temp = (weather or {}).get("temp_c")
    snow = (weather or {}).get("expected_snow_cm_24h") or 0
    if snow >= 2:
        return ZONES[2]  # verige
    if temp is not None and temp <= 0:
        return ZONES[3]  # spolzko
    if temp is not None and temp > 5:
        return ZONES[0]  # sonce
    return ZONES[1]  # nekaj vmes


def needle_angle(zone):
    return zone["mid"]


def arc_point(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def gauge_svg(zone, static=False):
    """static=True: samostojna različica za "Deli kot sliko" (glej
    build_body/SHARE_JS) — eksplicitna width/height (canvas Image potrebuje
    znano velikost) in kazalec zapečen kot SVG transform atribut namesto
    CSS --rot spremenljivke (canvas slika nima dostopa do strani CSS/animacije,
    zato mora biti statična kopija samozadostna)."""
    cx, cy, r = 190, 175, 105
    bounds = [180, 135, 90, 45, 0]
    arcs = []
    for i, z in enumerate(ZONES):
        x1, y1 = arc_point(cx, cy, r, bounds[i])
        x2, y2 = arc_point(cx, cy, r, bounds[i + 1])
        arcs.append(f'<path d="M {x1:.1f} {y1:.1f} A {r} {r} 0 0 1 {x2:.1f} {y2:.1f}" '
                     f'fill="none" stroke="{z["color"]}" stroke-width="26" stroke-linecap="butt"/>')

    rot = 90 - needle_angle(zone)
    nx, ny = cx, cy - r * 0.8
    if static:
        needle = (f'<g transform="rotate({rot:.1f} {cx} {cy})">'
                  f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#111" stroke-width="7" '
                  f'stroke-linecap="round"/></g>'
                  f'<circle cx="{cx}" cy="{cy}" r="13" fill="#111" stroke="#fff" stroke-width="3"/>')
    else:
        # Brez transform="rotate(...)" atributa -- CSS animacija (crn-needle-settle
        # spodaj) rotacijo prevzame prek --rot spremenljivke, XML atribut bi jo
        # tiho prepisal/mešal z njo (SVG CSS transform ima prednost pred atributom).
        needle = (f'<g class="crn-needle" style="--rot:{rot:.1f}deg;transform-origin:{cx}px {cy}px">'
                  f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#111" stroke-width="7" '
                  f'stroke-linecap="round"/></g>'
                  f'<circle cx="{cx}" cy="{cy}" r="13" fill="#111" stroke="#fff" stroke-width="3"/>')

    # text-anchor="middle" centrira napis simetrično okoli sidrne točke -- za
    # skrajni levi/desni coni (mid blizu 180°/0°, torej vodoravno ob loku) to
    # pomeni, da polovica napisa raste NAZAJ proti loku namesto stran od
    # njega, zato se je dotikala barvnega pasu. Za ti dve coni napis raste
    # samo stran od središča (end=levo, start=desno); zgornji dve coni (mid
    # blizu 90°) sta že dovolj visoko nad lokom in ostaneta na "middle".
    labels = []
    for z in ZONES:
        lx, ly = arc_point(cx, cy, r + 40, z["mid"])
        anchor = "end" if z["mid"] > 135 else "start" if z["mid"] < 45 else "middle"
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="10.5" '
                       f'font-weight="800" fill="#111">{z["label"]}</text>')

    # xmlns je za inline SVG v HTML odveč (brskalnik ga uvrsti v SVG imenski
    # prostor sam), a data:image/svg+xml ga bere kot samostojen XML dokument
    # in ga brez xmlns molče zavrže -- zato je tu vedno, ne le pri static=True.
    # viewBox je širši od izrisa (-20..410 namesto 0..380): skrajni levi/desni
    # napis (text-anchor end/start, glej zgoraj) raste samo stran od loka in
    # pri prejšnji ožji širini obrezan čez rob (izmerjeno z getBBox(): "SUHO K
    # POPR" sega do x=-15.5, "SPOLZKO, PAZI" do x=403.4).
    size_attrs = ' width="430" height="230"' if static else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 0 430 230"{size_attrs} '
            f'class="crn-gauge" role="img" aria-label="Črnivski indeks: {zone["label"]}">'
            + "".join(arcs) + "".join(labels) + needle + "</svg>")


def icon_svg_static(zone_id):
    """ZONE_ICONS ima viewBox brez width/height/xmlns (velikost pride iz CSS
    .crn-zicon, xmlns je za inline uporabo odveč) — za canvas Image
    potrebujemo oboje, isto načelo kot pri gauge_svg(static=True)."""
    svg = ZONE_ICONS[zone_id].replace('viewBox="0 0 60 60"',
                                       'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" width="60" height="60"', 1)
    return svg


ZONE_ICONS = {
    "sonce": '''<svg viewBox="0 0 60 60" class="crn-zicon crn-zicon-sonce" aria-hidden="true">
      <g stroke="#111" stroke-width="4" stroke-linecap="round">
        <line x1="30" y1="2" x2="30" y2="13"/><line x1="30" y1="47" x2="30" y2="58"/>
        <line x1="2" y1="30" x2="13" y2="30"/><line x1="47" y1="30" x2="58" y2="30"/>
        <line x1="9" y1="9" x2="17" y2="17"/><line x1="43" y1="43" x2="51" y2="51"/>
        <line x1="51" y1="9" x2="43" y2="17"/><line x1="17" y1="43" x2="9" y2="51"/>
      </g>
      <circle cx="30" cy="30" r="15" fill="#fbbf24" stroke="#111" stroke-width="4"/>
    </svg>''',
    "nekaj": '''<svg viewBox="0 0 60 60" class="crn-zicon crn-zicon-nekaj" aria-hidden="true">
      <g fill="#fef3c7" stroke="#111" stroke-width="3.5" stroke-linejoin="round">
        <circle cx="20" cy="33" r="10"/><circle cx="33" cy="24" r="13"/>
        <circle cx="45" cy="33" r="9"/><rect x="15" y="30" width="35" height="15" rx="7.5"/>
      </g>
      <circle cx="26" cy="35" r="2.2" fill="#111"/><circle cx="40" cy="35" r="2.2" fill="#111"/>
      <line x1="26" y1="42" x2="38" y2="42" stroke="#111" stroke-width="2.6" stroke-linecap="round"/>
    </svg>''',
    "verige": '''<svg viewBox="0 0 60 60" class="crn-zicon crn-zicon-verige" aria-hidden="true">
      <rect x="9" y="18" width="21" height="31" rx="10.5" fill="none" stroke="#111" stroke-width="6"/>
      <rect x="30" y="12" width="21" height="31" rx="10.5" fill="none" stroke="#111" stroke-width="6"/>
    </svg>''',
    "spolzko": '''<svg viewBox="0 0 60 60" class="crn-zicon crn-zicon-spolzko" aria-hidden="true">
      <g stroke="#0284c7" stroke-width="4.5" stroke-linecap="round">
        <line x1="30" y1="6" x2="30" y2="54"/><line x1="10" y1="17" x2="50" y2="43"/><line x1="10" y1="43" x2="50" y2="17"/>
        <path d="M30 6 l-5 6 M30 6 l5 6 M30 54 l-5 -6 M30 54 l5 -6"/>
        <path d="M10 17 l7.5 1 M10 17 l3 6.5 M50 43 l-7.5 -1 M50 43 l-3 -6.5"/>
        <path d="M10 43 l3 -6.5 M10 43 l7.5 -1 M50 17 l-3 6.5 M50 17 l-7.5 1"/>
      </g>
    </svg>''',
}


def avatar_svg():
    """Generičen "nekdo iz skupine" avatar za ob citatu — brez obraza/imena
    (nihče konkreten), samo silhueta, isti debel-obris slog kot vse ostalo."""
    return '''<svg viewBox="0 0 44 44" class="crn-avatar-icon" aria-hidden="true">
      <circle cx="22" cy="22" r="20" fill="#e5e7eb" stroke="#111" stroke-width="3.5"/>
      <circle cx="22" cy="17" r="7.5" fill="#fff" stroke="#111" stroke-width="3"/>
      <path d="M7 40 a15 13 0 0 1 30 0 Z" fill="#fff" stroke="#111" stroke-width="3"/>
    </svg>'''


def starburst_svg(color, points=14):
    """Klasična stripovska "pok" zvezda za ozadje izida — čisto okrasje, glej
    .crn-verdict-star (aria-hidden)."""
    cx = cy = 100
    r_out, r_in = 98, 62
    pts = []
    for i in range(points * 2):
        r = r_out if i % 2 == 0 else r_in
        deg = i * (360 / (points * 2))
        x, y = arc_point(cx, cy, r, deg)
        pts.append(f"{x:.1f},{y:.1f}")
    return (f'<svg viewBox="0 0 200 200" class="crn-verdict-star" aria-hidden="true">'
            f'<polygon points="{" ".join(pts)}" fill="{color}" opacity=".35"/></svg>')


CSS = '''
<style>
  .site-head,#bg,.site-foot,.app-bottomnav{display:none!important}
  /* Brez site-foot/app-bottomnav ni nič, kar bi zapolnilo sitewide
     body{min-height:100vh} (style.css) na širših zaslonih/krajši vsebini --
     ostal je prazen pikčast prostor pod "Nazaj na meteorec.si". Ta stran
     nima lepljive noge, zato naj se telo skrči na dejansko vsebino. */
  body{background:#fdf6e3!important;background-image:radial-gradient(#111 1px,transparent 1.4px)!important;
    background-size:16px 16px!important;background-position:-4px -4px!important;min-height:0!important}
  .wrap{max-width:720px}
  .crn-wrap{font-family:Inter,system-ui,sans-serif;color:#111;padding:1.2rem 0 3rem}
  .crn-hero{display:flex;align-items:center;gap:1rem;margin-top:.4rem}
  .crn-icon{width:170px;height:auto;flex-shrink:0;transition:transform .25s}
  .crn-icon:hover{animation:crnWobble .5s ease}
  @keyframes crnWobble{0%,100%{transform:rotate(0deg)}25%{transform:rotate(-4deg)}75%{transform:rotate(4deg)}}
  @media (max-width:520px){.crn-hero{flex-direction:column}
    .crn-icon{width:150px}}
  .crn-needle{animation:crnNeedleSettle .8s cubic-bezier(.34,1.56,.64,1) forwards}
  @keyframes crnNeedleSettle{from{transform:rotate(0deg)}to{transform:rotate(var(--rot))}}
  .crn-panel.tilt{animation:crnPanelPop .6s cubic-bezier(.34,1.56,.64,1) .15s backwards}
  @keyframes crnPanelPop{0%{opacity:0;transform:scale(.82) rotate(-4deg)}
    60%{opacity:1;transform:scale(1.03) rotate(1.2deg)}100%{opacity:1;transform:scale(1) rotate(.6deg)}}
  .crn-verdict-star{animation:crnStarPulse 2.6s ease-in-out .8s infinite backwards}
  @keyframes crnStarPulse{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:.5}
    50%{transform:translate(-50%,-50%) scale(1.08);opacity:.65}}
  .crn-quote{animation:crnQuoteIn .5s ease-out .65s backwards}
  @keyframes crnQuoteIn{0%{opacity:0;transform:translateY(14px) rotate(0deg)}
    100%{opacity:1;transform:translateY(0) rotate(-0.8deg)}}
  .crn-avatar{animation:crnAvatarIn .45s ease-out .8s backwards}
  @keyframes crnAvatarIn{0%{opacity:0;transform:translateY(10px) scale(.85)}100%{opacity:1;transform:translateY(0) scale(1)}}
  .crn-zicon-sonce{animation:crnSunSpin 9s linear infinite}
  @keyframes crnSunSpin{to{transform:rotate(360deg)}}
  .crn-zicon-nekaj{animation:crnCloudFloat 3s ease-in-out infinite}
  @keyframes crnCloudFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
  .crn-zicon-verige{animation:crnChainShake 2.4s ease-in-out infinite}
  @keyframes crnChainShake{0%,100%{transform:rotate(0deg)}25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
  .crn-zicon-spolzko{animation:crnIceGlint 1.8s ease-in-out infinite}
  @keyframes crnIceGlint{0%,100%{opacity:1}50%{opacity:.55}}
  @media (prefers-reduced-motion:reduce){.crn-icon:hover{animation:none}
    .crn-needle{animation:none;transform:rotate(var(--rot))}
    .crn-panel.tilt,.crn-verdict-star,.crn-quote,.crn-avatar,
    .crn-zicon-sonce,.crn-zicon-nekaj,.crn-zicon-verige,.crn-zicon-spolzko{animation:none}
    .crn-panel.tilt{opacity:1;transform:rotate(.6deg)}
    .crn-verdict-star{opacity:.5;transform:translate(-50%,-50%) scale(1)}
    .crn-quote{opacity:1;transform:rotate(-.8deg)}
    .crn-avatar{opacity:1;transform:none}}
  .crn-title{font-size:2.6rem;font-weight:800;line-height:1.05;letter-spacing:-.01em;
    color:#dc2626;text-shadow:3px 3px 0 #111,-1px -1px 0 #111,1px -1px 0 #111,-1px 1px 0 #111;
    transform:rotate(-1.5deg);margin:0 0 .3rem;text-transform:uppercase}
  .crn-sub{font-size:1.05rem;font-weight:600;color:#111;margin:0 0 1.6rem;max-width:44ch;
    background:#fdf6e3;display:inline-block;padding:.1rem .3rem}
  .crn-panel{background:#fff;border:4px solid #111;border-radius:18px;padding:1.4rem 1.2rem;
    box-shadow:8px 8px 0 #111;margin-bottom:1.6rem;position:relative}
  .crn-panel.tilt{transform:rotate(0.6deg)}
  .crn-gauge{width:100%;max-width:340px;display:block;margin:0 auto}
  /* min-height + flex-center: brez tega .crn-verdict rezervira samo prostor
     za ikono+napis (~90px), zvezda (210px, sredinjena nanj) pa je absolutno
     pozicionirana in seže čez spodnji rob -- v .crn-data škatlo pod njo
     (obe sta znotraj istega .crn-panel). Rezervirana višina ujame zvezdo v
     celoti, centriranje pa badge postavi točno v njeno sredino namesto na vrh. */
  .crn-verdict{text-align:center;position:relative;margin-top:.4rem;min-height:210px;
    display:flex;flex-direction:column;align-items:center;justify-content:center}
  .crn-verdict-star{position:absolute;left:50%;top:50%;width:210px;height:210px;
    transform:translate(-50%,-50%);z-index:0;opacity:.5}
  .crn-zicon{position:relative;z-index:1;width:52px;height:52px;display:block;margin:0 auto .2rem}
  .crn-verdict span{position:relative;z-index:1;display:inline-block;font-size:1.7rem;
    font-weight:800;text-transform:uppercase;letter-spacing:.01em;background:#fff;
    padding:0 .3rem}
  .crn-quote-row{display:flex;align-items:flex-end;gap:.7rem;flex-wrap:wrap;margin-top:.2rem}
  .crn-quote{background:#fef08a;border:3px solid #111;border-radius:14px;padding:1rem 1.2rem;
    font-weight:700;font-size:1.05rem;position:relative;transform:rotate(-0.8deg);flex:1 1 240px}
  .crn-quote::before{content:"\\201C";font-size:2.4rem;color:#111;line-height:0;
    position:absolute;left:.5rem;top:1.6rem}
  .crn-quote::after{content:"";position:absolute;left:2rem;bottom:-15px;width:0;height:0;
    border-left:15px solid transparent;border-right:15px solid transparent;border-top:16px solid #111;
    transform:rotate(-6deg)}
  .crn-quote-tail{position:absolute;left:2.15rem;bottom:-9.5px;width:0;height:0;
    border-left:12px solid transparent;border-right:12px solid transparent;border-top:13px solid #fef08a;
    transform:rotate(-6deg);z-index:1}
  .crn-quote p{margin:0 0 0 1.6rem}
  .crn-avatar{display:flex;flex-direction:column;align-items:center;gap:.15rem;flex:0 0 auto}
  .crn-avatar-icon{width:44px;height:44px}
  /* Brez neprosojnega ozadja pikčasto ozadje strani (glej body zgoraj)
     sveti skozi ta drobni napis in ga navidez "prečrta" -- isti trik kot
     .crn-sub zgoraj (background v barvi strani + padding). */
  .crn-avatar span{font-size:.68rem;font-weight:700;color:#4b5563;text-align:center;max-width:70px;
    background:#fdf6e3;padding:.15rem .3rem;border-radius:4px}
  .crn-data{font-size:.92rem;color:#374151;background:#f3f4f6;border:2px dashed #9ca3af;
    border-radius:10px;padding:.8rem 1rem;margin-top:1rem}
  .crn-fine{font-size:.78rem;color:#6b7280;line-height:1.6;border-top:2px dotted #9ca3af;
    padding-top:1rem;margin-top:1.8rem}
  .crn-links{margin-top:.6rem;font-size:.85rem}
  .crn-links a{color:#1d4ed8;font-weight:700}
  .crn-back{display:inline-block;margin-top:1.6rem;font-weight:700;color:#111;
    background:#fff;border:3px solid #111;border-radius:999px;padding:.5rem 1.1rem;
    text-decoration:none;box-shadow:4px 4px 0 #111}
  .crn-actions{display:flex;flex-wrap:wrap;gap:.6rem;margin-top:1rem}
  .crn-action-btn{font:inherit;font-weight:700;font-size:.92rem;color:#111;cursor:pointer;
    background:#fff;border:3px solid #111;border-radius:999px;padding:.5rem 1.1rem;
    box-shadow:4px 4px 0 #111;transition:transform .1s}
  .crn-action-btn:active{transform:translate(2px,2px);box-shadow:2px 2px 0 #111}
  .crn-share-status{font-size:.82rem;font-weight:600;color:#374151;margin-top:.5rem}
  .crn-quote-pop{animation:crnQuoteReroll .35s ease}
  @keyframes crnQuoteReroll{0%{transform:rotate(-0.8deg) scale(.96)}60%{transform:rotate(-0.8deg) scale(1.03)}
    100%{transform:rotate(-0.8deg) scale(1)}}
  @media (max-width:480px){.crn-title{font-size:2rem}}
  /* Mobilno: cel sklop poravnan na sredino namesto ob levi rob. Ta blok mora
     priti PO osnovnih pravilih zgoraj (.crn-quote-row/.crn-back/...), ker so
     ta deklarirana kasneje v datoteki in bi sicer pri enaki specifičnosti
     povozila zgornjo (prejšnjo) medijsko poizvedbo -- glej git zgodovino. */
  @media (max-width:520px){.crn-hero{align-items:center;text-align:center}
    .crn-hero>div{width:100%}
    .crn-quote-row{flex-direction:column;align-items:center}
    .crn-quote{width:100%}
    .crn-actions{justify-content:center}
    .crn-fine{text-align:center}
    .crn-back{display:table;margin:1.6rem auto 0}}
  @media (prefers-reduced-motion:reduce){.crn-quote-pop{animation:none}}
  /* Nad ~600px je .crn-panel (do 720px, glej .wrap zgoraj) veliko širši od
     merilnika (340px) -- ostal je velik prazen pas na obeh straneh. Merilnik
     in izid (zvezda+ikona+napis) tu zato skupaj zrastejo namesto da bi samo
     osamljeno stala sredi bele površine. */
  @media (min-width:600px){
    .crn-gauge{max-width:460px}
    .crn-verdict{min-height:280px}
    .crn-verdict-star{width:280px;height:280px}
    .crn-zicon{width:66px;height:66px}
    .crn-verdict span{font-size:2.2rem}
    .crn-data{font-size:1rem;padding:1rem 1.3rem}
  }
</style>
'''


SHARE_JS_TEMPLATE = '''
<script>
(function(){
  "use strict";
  var quotes = __QUOTES_JSON__;
  var share = __SHARE_JSON__;

  var rerollBtn = document.getElementById("crn-reroll");
  var quoteP = document.querySelector(".crn-quote p");
  var quoteBubble = document.querySelector(".crn-quote");
  if (rerollBtn && quoteP && quoteBubble && quotes.length > 1) {
    rerollBtn.hidden = false;
    rerollBtn.addEventListener("click", function(){
      var cur = quoteP.textContent;
      var next = cur;
      var tries = 0;
      while (next === cur && tries < 20) {
        next = quotes[Math.floor(Math.random() * quotes.length)];
        tries++;
      }
      quoteP.textContent = next;
      quoteBubble.classList.remove("crn-quote-pop");
      void quoteBubble.offsetWidth;
      quoteBubble.classList.add("crn-quote-pop");
    });
  }

  var shareBtn = document.getElementById("crn-share");
  var statusEl = document.getElementById("crn-share-status");
  if (!shareBtn || !window.HTMLCanvasElement || !share) return;

  function setStatus(msg){
    if (!statusEl) return;
    statusEl.hidden = !msg;
    statusEl.textContent = msg || "";
  }

  function loadSvgImage(svgStr, w, h){
    return new Promise(function(resolve, reject){
      var img = new Image();
      img.onload = function(){ resolve(img); };
      img.onerror = reject;
      img.width = w;
      img.height = h;
      img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svgStr);
    });
  }

  function wrapText(ctx, text, maxWidth){
    var words = text.split(" ");
    var lines = [];
    var line = "";
    for (var i = 0; i < words.length; i++) {
      var test = line ? line + " " + words[i] : words[i];
      if (ctx.measureText(test).width > maxWidth && line) {
        lines.push(line);
        line = words[i];
      } else {
        line = test;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  function downloadBlob(blob){
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = "crnivec.png";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 4000);
    setStatus("Slika je bila prenesena.");
  }

  function buildCanvas(){
    var fontsReady = (window.document && document.fonts && document.fonts.ready) ?
      document.fonts.ready : Promise.resolve();
    return Promise.all([
      loadSvgImage(share.gauge, 430, 230),
      loadSvgImage(share.icon, 60, 60),
      fontsReady
    ]).then(function(imgs){
      var gaugeImg = imgs[0];
      var iconImg = imgs[1];
      var W = 640, H = 860;
      var canvas = document.createElement("canvas");
      canvas.width = W;
      canvas.height = H;
      var ctx = canvas.getContext("2d");

      ctx.fillStyle = "#fdf6e3";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#111";
      for (var y = 8; y < H; y += 16) {
        for (var x = 8; x < W; x += 16) {
          ctx.beginPath();
          ctx.arc(x, y, 1, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      ctx.textAlign = "center";
      ctx.textBaseline = "alphabetic";
      ctx.font = "800 40px Inter, system-ui, sans-serif";
      ctx.lineJoin = "round";
      ctx.lineWidth = 8;
      ctx.strokeStyle = "#111";
      ctx.strokeText("KAKO JE ČEZ ČRNIVEC?", W / 2, 74);
      ctx.fillStyle = "#dc2626";
      ctx.fillText("KAKO JE ČEZ ČRNIVEC?", W / 2, 74);

      var px = 40, py = 100, pw = W - 80, ph = 430;
      ctx.fillStyle = "#111";
      ctx.fillRect(px + 8, py + 8, pw, ph);
      ctx.fillStyle = "#fff";
      ctx.fillRect(px, py, pw, ph);
      ctx.lineWidth = 4;
      ctx.strokeStyle = "#111";
      ctx.strokeRect(px, py, pw, ph);

      ctx.drawImage(gaugeImg, px + (pw - 430) / 2, py + 20, 430, 230);
      ctx.drawImage(iconImg, W / 2 - 26, py + 260, 52, 52);

      ctx.font = "800 30px Inter, system-ui, sans-serif";
      ctx.fillStyle = share.color;
      ctx.fillText(share.verdict, W / 2, py + 345);

      ctx.font = "600 18px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#374151";
      ctx.fillText(share.temp + " \\u00b7 " + share.snow, W / 2, py + 380);

      var qx = 40, qy = py + ph + 30, qw = W - 80;
      ctx.textAlign = "left";
      ctx.font = "700 20px Inter, system-ui, sans-serif";
      var lines = wrapText(ctx, share.quote, qw - 60);
      var qh = 46 + lines.length * 28;
      ctx.fillStyle = "#111";
      ctx.fillRect(qx + 6, qy + 6, qw, qh);
      ctx.fillStyle = "#fef08a";
      ctx.fillRect(qx, qy, qw, qh);
      ctx.lineWidth = 3;
      ctx.strokeStyle = "#111";
      ctx.strokeRect(qx, qy, qw, qh);
      ctx.fillStyle = "#111";
      for (var li = 0; li < lines.length; li++) {
        ctx.fillText(lines[li], qx + 26, qy + 34 + li * 28);
      }

      ctx.textAlign = "center";
      ctx.font = "700 16px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#6b7280";
      ctx.fillText("meteorec.si/crnivec", W / 2, H - 20);

      return canvas;
    });
  }

  shareBtn.hidden = false;
  shareBtn.addEventListener("click", function(){
    shareBtn.disabled = true;
    setStatus("Pripravljam sliko\\u2026");
    buildCanvas().then(function(canvas){
      canvas.toBlob(function(blob){
        if (!blob) { setStatus("Slike ni bilo mogoče pripraviti."); shareBtn.disabled = false; return; }
        var file = new File([blob], "crnivec.png", { type: "image/png" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          navigator.share({
            files: [file],
            title: "Kako je čez Črnivec?",
            text: share.verdict + " \\u2014 meteorec.si/crnivec"
          }).then(function(){
            setStatus("");
          }).catch(function(err){
            if (err && err.name === "AbortError") { setStatus(""); return; }
            downloadBlob(blob);
          }).then(function(){ shareBtn.disabled = false; });
        } else {
          downloadBlob(blob);
          shareBtn.disabled = false;
        }
      }, "image/png");
    }).catch(function(){
      setStatus("Slike ni bilo mogoče pripraviti.");
      shareBtn.disabled = false;
    });
  });
})();
</script>
'''


def mountain_icon_svg():
    """Stripovska "maskota" strani — gora z ostrim cik-cak klancem in
    (mock) prometnim znakom "pozor" ob vznožju. Čisto okrasje (aria-hidden),
    poenostavljeno za berljivost pri ~90 px (prvotna različica s
    podrobnim avtomobilčkom se je pri tej velikosti izgubila — glej git
    zgodovino). Isti stil kot gauge_svg/starburst_svg zgoraj (debel črn
    obris, ploskovite barve, brez naloženih slik)."""
    return '''<svg viewBox="0 0 200 180" class="crn-icon" aria-hidden="true">
    <path d="M10 168 L82 22 L108 64 L134 18 L192 168 Z" fill="#fdf6e3" stroke="#111" stroke-width="7" stroke-linejoin="round"/>
    <path d="M134 18 L152 48 L138 44 L128 55 L116 46 Z" fill="#fff" stroke="#111" stroke-width="4.5" stroke-linejoin="round"/>
    <path d="M82 22 L96 46 L84 43 L74 52 L64 44 Z" fill="#fff" stroke="#111" stroke-width="4.5" stroke-linejoin="round"/>
    <path d="M108 68 L78 92 L112 108 L80 134 L104 150 L92 168"
          fill="none" stroke="#111" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M108 68 L78 92 L112 108 L80 134 L104 150 L92 168"
          fill="none" stroke="#fff" stroke-width="4" stroke-dasharray="1 11" stroke-linecap="round" stroke-linejoin="round"/>
    <g transform="translate(38,150) rotate(-8)">
      <path d="M0 -20 L18 14 L-18 14 Z" fill="#fef08a" stroke="#dc2626" stroke-width="5" stroke-linejoin="round"/>
      <text x="0" y="10" text-anchor="middle" font-size="16" font-weight="800" fill="#111">!</text>
    </g>
  </svg>'''


def build_body(data):
    passes = data.get("passes") or []
    crnivec = next((p for p in passes if p["id"] == "crnivec"), None)
    weather = (crnivec or {}).get("weather") or {}
    zone = pick_zone(weather)

    today_iso = seo.TODAY.isoformat()
    quote = QUOTES[int(hashlib.sha256(f"{today_iso}|crnivec-quote".encode()).hexdigest(), 16) % len(QUOTES)]

    temp_txt = f'{seo.num(weather.get("temp_c"), 1)} °C' if weather.get("temp_c") is not None else "ni podatka"
    snow_txt = (f'{seo.num(weather.get("expected_snow_cm_24h"), 1)} cm snega v 24 h'
                if weather.get("expected_snow_cm_24h") is not None else "ni podatka")

    # "Deli kot sliko" bere ta paket, ne živega animiranega DOM-a (glej
    # gauge_svg(static=True)/icon_svg_static) — vsi podatki za canvas so tu
    # že pripravljeni, JS jih samo nariše. "Vprašaj še enkrat" dobi cel
    # QUOTES seznam za klientski reroll (server izbere samo dnevni privzetek).
    share_payload = {
        "verdict": zone["label"],
        "color": zone["color"],
        "quote": quote,
        "temp": temp_txt,
        "snow": snow_txt,
        "gauge": gauge_svg(zone, static=True),
        "icon": icon_svg_static(zone["id"]),
    }
    quotes_json = json.dumps(QUOTES, ensure_ascii=False).replace("</", "<\\/")
    share_json = json.dumps(share_payload, ensure_ascii=False).replace("</", "<\\/")
    share_js = SHARE_JS_TEMPLATE.replace("__QUOTES_JSON__", quotes_json).replace("__SHARE_JSON__", share_json)

    return f'''{CSS}
  <div class="crn-wrap">
{seo.crumbs_html([("Meteorec", "/"), ("Kako je čez Črnivec?", None)])}
    <div class="crn-hero">
      {mountain_icon_svg()}
      <div>
        <h1 class="crn-title">Kako je čez Črnivec?</h1>
        <p class="crn-sub">Vprašanje, ki ga v tej dolini nekdo vpraša vsak dan. Uradnega odgovora
        ni — tale je (skoraj) enako zanesljiv.</p>
      </div>
    </div>

    <div class="crn-panel tilt">
      {gauge_svg(zone)}
      <div class="crn-verdict" style="color:{zone['color']}">{starburst_svg(zone['color'])}{ZONE_ICONS[zone['id']]}<span>{zone['label']}</span></div>
      <div class="crn-data">Trenutno na 902 m: {temp_txt}, pričakovanih {snow_txt}
      (ista metoda kot na <a href="/zima/prevoznost-prelazov/">resni strani</a> — le nalepke so tu za hec).</div>
    </div>

    <div class="crn-quote-row">
      <div class="crn-quote"><p>{quote}</p><div class="crn-quote-tail"></div></div>
      <div class="crn-avatar">{avatar_svg()}<span>nekdo iz skupine</span></div>
    </div>

    <div class="crn-actions">
      <button type="button" id="crn-reroll" class="crn-action-btn" hidden>🔁 Vprašaj še enkrat</button>
      <button type="button" id="crn-share" class="crn-action-btn" hidden>📤 Deli kot sliko</button>
    </div>
    <p id="crn-share-status" class="crn-share-status" role="status" aria-live="polite" hidden></p>

    <p class="crn-fine"><strong>Drobni tisk:</strong> ta indeks je znanstveno pomešan z ugibanjem,
    klepetom v čakalnici in enim komentarjem iz FB skupine. Meteorec ne odgovarja, če je bilo v
    resnici čisto drugače — kar je, mimogrede, tudi bistvo te strani.
    <span class="crn-links">Za dejansko uporabno oceno: <a href="/zima/prevoznost-prelazov/">MeteoZima:
    prevoznost prelazov</a> · za uradno stanje ceste: promet.si, AMZS, DARS.</span></p>

    <a class="crn-back" href="/">← Nazaj na meteorec.si</a>
  </div>
{share_js}'''


def main():
    data = load_json(DATA_PATH)
    if not data:
        print("✗ data/winter-data.json manjka -- najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1

    body = build_body(data)
    title = "Kako je čez Črnivec? — (ne)uradni indeks"
    desc = "Vsakodnevno vprašanje iz lokalnih FB skupin, s(e) samoironičnim indeksom in resničnim vremenom na prelazu."
    schema = "\n".join([
        seo.webpage_schema("/crnivec/", title, desc, date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("Kako je čez Črnivec?", None)]),
    ])
    html = seo.page_shell(title, desc, "/crnivec/", schema, body)
    seo.write_page("crnivec/index.html", html, force=True)
    print("  → crnivec/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
