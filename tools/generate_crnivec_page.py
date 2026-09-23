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

Živa kamera s prelaza (CAM_URL spodaj) je neposreden hotlink na uradno
kamero DRSI/promet.si (Direkcija RS za infrastrukturo, Prometno-informacijski
center) — ista slika, ki jo že leta hotlinkajo hribi.net, svethribov.si in
podobne strani (preverjeno pred vgradnjo, ni ugibana pot). Vgrajena je
namenoma neposredno kot <img>, brez Worker proxyja: za prikaz slike (za
razliko od /varpolje-current) CORS ni ovira, samo za branje njenih pikslov
prek JS bi bil. Klientski JS jo osveži vsakih 5 minut (isto pravilo kot
povsod na strani — glej CLAUDE.md, "noben klic pogosteje kot na 5 minut" —
tu še toliko bolj, ker gre klic na tuj strežnik, ne na naš worker). Attribucija
vira (promet.si) je obvezna po njihovih pogojih uporabe za razvijalce.

Poročanje (#crn-report) je bogatejše od dnevnega glasovanja (#crn-vote):
obiskovalec izbere ISTO cono kot merilnik (ne novo lestvico) + neobvezno
opombo, javno, brez prijave — /crnivec/porocilo in /crnivec/porocila v
worker.js, isti R2/feedback vzorec kot /gobe/opazovanje. Šaljive značke
(CRN_BADGES v worker.js) nagradijo ŠTEVILO oddanih poročil enega anonimnega
(localStorage) porocevalca — hec, ne resna lestvica; brisanje localStorage
šteje nazaj na nič in to je v redu.

Piše: crnivec/index.html
Wired into: .github/workflows/zima-forecast.yml (po generate_zima_page.py —
potrebuje isti data/winter-data.json)

Usage:
  python3 tools/generate_crnivec_page.py
"""
import datetime
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
from generate_story_card import dry_streak  # noqa: E402 — isti izračun kot na zgodbah, ne podvojen tu
from crnivec_zones import ZONES, pick_zone  # noqa: E402 — deljeno z generate_story_card.py (tema CRNIVEC)

ROOT = seo.ROOT
DATA_PATH = os.path.join(ROOT, "data", "winter-data.json")

# Uradna kamera DRSI na prelazu (glej opombo na vrhu datoteke) — spremeni
# samo tu, JS jo bere iz istega niza (glej CAM_URL v build_body spodaj).
CAM_URL = "https://www.drsc.si/kamere/Crnivec/Crn1_0001.jpg"

# ZONES/pick_zone sta v skupnem crnivec_zones.py (uvožena spodaj) — tudi
# generate_story_card.py (tema CRNIVEC) ju rabi, glej opombo tam o krožnem
# uvozu.

# Kratke oznake ISTIH con za gumbe poročanja (glej crn-report spodaj) — polni
# ZONES["label"] (npr. "SPOLZKO, PAZI") je glasen naslov za merilnik, v
# štirih ozkih gumbih v vrsti pa ne bi bil čitljiv.
ZONE_SHORT = {"sonce": "Suho", "nekaj": "Nekaj je", "verige": "Verige", "spolzko": "Spolzko"}

# Izvirni citati v duhu šale (glej opombo zgoraj) — NISO navedki resničnih
# objav, ker jih nimamo preverjenih; namenoma zvenijo kot tipičen odgovor v
# FB skupini. Če imaš prave, jih zamenjaj tu.
QUOTES = [
    "Teta pravi, da je suho. Sosed pravi, da je katastrofa. Nekdo se moti.",
    "Grem pogledat in sporočim. Če se vrnem.",
    "Odvisno, kdaj vprašaš. In predvsem – koga.",
    "Kamera kaže sonce. Komentarji pod njo kažejo zimo.",
    "Ko sem jaz šel čez, je bilo čisto suho. Resda pred dvema letoma.",
    "Pol skupine pravi, da rabiš zimske. Druga polovica, da ne. Vzemi oboje.",
    "Vprašaj raje v skupini. Tam imajo vedno tri različne odgovore.",
    "Nekdo je pravkar vprašal isto. Odgovori so že drugačni kot včeraj.",
    "Tehnično prevozno. Praktično pa … saj veš, kako je s Črnivcem.",
    "Indeks pravi eno, dedek drugo. Za zdaj ima dedek boljši rekord.",
    "Če sprašuješ, ali je prevozno, je odgovor verjetno: previdno.",
    "Na kameri je videti dobro. Kar je vedno dober začetek.",
    "Črnivec je prevozen. Vprašanje je samo, za koga.",
    "Cesta pravi »pojdi«. Vreme pravi »premisli«.",
    "Snega ni veliko. Ampak tisti, ki je, je očitno dovolj.",
    "Danes brez težav. Jutri? Vprašaj jutri.",
    "Če imaš zimske gume, si optimist. Če imaš verige, si pripravljen.",
    "V dolini suho, na vrhu pa … dobrodošel na Črnivcu.",
    "Črnivec danes: bolj vprašanje kot odgovor.",
    "Stanje se spreminja. Mnenja še hitreje.",
    "Ni panike. Razen če je.",
    "Zaenkrat gre. Slab znak je, da sem dodal »zaenkrat«.",
    "Lahko greš čez. Ali pa najprej preveriš, kako zelo ti je všeč tvoj avto.",
    "Po podatkih je v redu. Po pripovedovanju soseda pa nikakor.",
    "Črnivec: kraj, kjer »samo malo snega« pomeni štiri različne stvari.",
    "Če greš čez, poročaj. Če ne greš, tudi.",
    "Včeraj je bilo prevozno. Danes je danes.",
    "Stanje na cesti: odvisno od tega, kako samozavestno ga gledaš.",
    "Ni še za paniko. Ampak verige imajo danes lep dan.",
    "Čez gre. Vprašanje je, ali želiš biti tisti, ki to preveri.",
]

# Izven dnevnega izbora (glej pick spodaj) in izven navadnega kroga za gumb
# "Vprašaj še enkrat" — RARE_QUOTE se v rerollu prikaže samo z majhno
# verjetnostjo (glej crn-reroll v SHARE_JS_TEMPLATE), kot easter egg, ne kot
# še en enakovreden citat. Ni deterministična po datumu, ker bi sicer
# "redka" izguba smisel — mora biti presenečenje ob kliku, ne stalnica dneva.
RARE_QUOTE = "Nekdo je pravkar prišel čez. Cesta je suha, sneg ga sploh ni čakal. To se zgodi enkrat na sto vprašanj."


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


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
    zato mora biti statična kopija samozadostna).

    "Premium" prenova 22. 9. 2026: en sam lok z gladkim prelivom (namesto 4
    ločenih barvnih segmentov -- brez trdih šivov med conami), tanke bele
    ločnice na mejah conov (da so cone kljub prelivu še vedno razločne), rahla
    senca (feDropShadow) za globino in dvoslojni kazalec/os za bolj "urni"
    videz. Geometrija (cx/cy/r) ostane enaka kot prej -- velikost na strani
    uravnava CSS (.crn-gauge max-width), ne viewBox."""
    cx, cy, r = 190, 175, 105
    bounds = [180, 135, 90, 45, 0]
    sw = 30  # stroke-width loka -- debelejši pas kot prej (26) za bolj čvrst videz

    x1, y1 = arc_point(cx, cy, r, 180)
    x2, y2 = arc_point(cx, cy, r, 0)
    arc_path = f'M {x1:.1f} {y1:.1f} A {r} {r} 0 0 1 {x2:.1f} {y2:.1f}'
    grad_stops = "".join(
        f'<stop offset="{i / (len(ZONES) - 1) * 100:.0f}%" stop-color="{z["color"]}"/>'
        for i, z in enumerate(ZONES)
    )
    defs = (
        '<defs>'
        f'<linearGradient id="crnGrad" x1="0" y1="0" x2="1" y2="0">{grad_stops}</linearGradient>'
        '<filter id="crnGaugeShadow" x="-30%" y="-30%" width="160%" height="160%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="3.5" flood-color="#000" flood-opacity=".16"/>'
        '</filter>'
        '</defs>'
    )
    # Tanka svetla ločnica na vsaki notranji meji conov (135°/90°/45°), čez
    # celo širino pasu -- brez nje bi gladek preliv zabrisal, kje se cona
    # dejansko konča (glej pick_zone/ZONES bounds).
    ticks = []
    for b in bounds[1:-1]:
        ix1, iy1 = arc_point(cx, cy, r - sw / 2, b)
        ix2, iy2 = arc_point(cx, cy, r + sw / 2, b)
        ticks.append(f'<line x1="{ix1:.1f}" y1="{iy1:.1f}" x2="{ix2:.1f}" y2="{iy2:.1f}" '
                      f'stroke="#fff" stroke-width="2" opacity=".8"/>')
    arc = (f'<g filter="url(#crnGaugeShadow)">'
           f'<path d="{arc_path}" fill="none" stroke="url(#crnGrad)" stroke-width="{sw}" '
           f'stroke-linecap="round"/>{"".join(ticks)}</g>')

    rot = 90 - needle_angle(zone)
    nx, ny = cx, cy - r * 0.72
    needle_shape = (f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#171717" stroke-width="6" '
                     f'stroke-linecap="round"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="14" fill="#171717"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="14" fill="none" stroke="#fff" stroke-width="3"/>'
                     f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="#fff"/>')
    if static:
        needle = f'<g filter="url(#crnGaugeShadow)" transform="rotate({rot:.1f} {cx} {cy})">{needle_shape}</g>'
    else:
        # Brez transform="rotate(...)" atributa -- CSS animacija (crn-needle-settle
        # spodaj) rotacijo prevzame prek --rot spremenljivke, XML atribut bi jo
        # tiho prepisal/mešal z njo (SVG CSS transform ima prednost pred atributom).
        needle = (f'<g class="crn-needle" filter="url(#crnGaugeShadow)" '
                   f'style="--rot:{rot:.1f}deg;transform-origin:{cx}px {cy}px">{needle_shape}</g>')

    # text-anchor="middle" centrira napis simetrično okoli sidrne točke -- za
    # skrajni levi/desni coni (mid blizu 180°/0°, torej vodoravno ob loku) to
    # pomeni, da polovica napisa raste NAZAJ proti loku namesto stran od
    # njega, zato se je dotikala barvnega pasu. Za ti dve coni napis raste
    # samo stran od središča (end=levo, start=desno); zgornji dve coni (mid
    # blizu 90°) sta že dovolj visoko nad lokom in ostaneta na "middle".
    labels = []
    for z in ZONES:
        lx, ly = arc_point(cx, cy, r + 42, z["mid"])
        anchor = "end" if z["mid"] > 135 else "start" if z["mid"] < 45 else "middle"
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" '
                       f'font-weight="800" fill="#171717">{z["label"]}</text>')

    # xmlns je za inline SVG v HTML odveč (brskalnik ga uvrsti v SVG imenski
    # prostor sam), a data:image/svg+xml ga bere kot samostojen XML dokument
    # in ga brez xmlns molče zavrže -- zato je tu vedno, ne le pri static=True.
    # viewBox je širši od izrisa (-20..410 namesto 0..380): skrajni levi/desni
    # napis (text-anchor end/start, glej zgoraj) raste samo stran od loka in
    # pri preozkem viewBoxu se obreže čez rob (izmerjeno z getBBox()).
    size_attrs = ' width="430" height="230"' if static else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-20 0 430 230"{size_attrs} '
            f'class="crn-gauge" role="img" aria-label="Črnivski indeks: {zone["label"]}">'
            + defs + arc + "".join(labels) + needle + "</svg>")


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
  @keyframes crnPanelPop{0%{opacity:0;transform:scale(.86) rotate(-2deg)}
    60%{opacity:1;transform:scale(1.02) rotate(.5deg)}100%{opacity:1;transform:scale(1) rotate(.2deg)}}
  .crn-verdict-star{animation:crnStarPulse 2.6s ease-in-out .8s infinite backwards}
  @keyframes crnStarPulse{0%,100%{transform:translate(-50%,-50%) scale(1);opacity:.5}
    50%{transform:translate(-50%,-50%) scale(1.08);opacity:.65}}
  .crn-quote{animation:crnQuoteIn .5s ease-out .65s backwards}
  @keyframes crnQuoteIn{0%{opacity:0;transform:translateY(14px) rotate(0deg)}
    100%{opacity:1;transform:translateY(0) rotate(-.3deg)}}
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
    .crn-panel.tilt,.crn-verdict-star,.crn-quote,.crn-avatar,.crn-stats,
    .crn-zicon-sonce,.crn-zicon-nekaj,.crn-zicon-verige,.crn-zicon-spolzko{animation:none}
    .crn-panel.tilt{opacity:1;transform:rotate(.2deg)}
    .crn-verdict-star{opacity:.5;transform:translate(-50%,-50%) scale(1)}
    .crn-quote{opacity:1;transform:rotate(-.3deg)}
    .crn-avatar{opacity:1;transform:none}}
  .crn-title{font-size:2.6rem;font-weight:800;line-height:1.05;letter-spacing:-.01em;
    color:#dc2626;text-shadow:3px 3px 0 #111,-1px -1px 0 #111,1px -1px 0 #111,-1px 1px 0 #111;
    transform:rotate(-.6deg);margin:0 0 .3rem;text-transform:uppercase}
  .crn-sub{font-size:1.05rem;font-weight:600;color:#111;margin:0 0 1.6rem;max-width:44ch;
    background:#fdf6e3;display:inline-block;padding:.1rem .3rem}
  .crn-panel{background:#fff;border:4px solid #111;border-radius:18px;padding:1.4rem 1.2rem;
    box-shadow:8px 8px 0 #111;margin-bottom:1.6rem;position:relative}
  .crn-panel.tilt{transform:rotate(.2deg)}
  /* max-width je namenoma velikodušen (ne ozek "mobilni" strop): width:100%
     ga na ozkih telefonih itak strne na širino .crn-panel, na širših
     telefonih/tablicah pa merilnik zdaj dejansko zapolni prostor, ki ga ima
     -- prej je pri 340px na 500-600px zaslonu ostajal velik prazen pas. */
  .crn-gauge{width:100%;max-width:480px;display:block;margin:0 auto}
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
  .crn-verdict span{position:relative;z-index:1;display:inline-block;font-size:1.9rem;
    font-weight:800;text-transform:uppercase;letter-spacing:.01em;background:#fff;
    border:3px solid currentColor;border-radius:12px;padding:.3rem 1rem;margin-top:.15rem}
  .crn-verdict-desc{position:relative;z-index:1;font-size:.92rem;font-weight:600;
    color:#374151;margin-top:.6rem;max-width:32ch}
  .crn-quote-row{display:flex;align-items:flex-end;gap:.7rem;flex-wrap:wrap;margin-top:.2rem}
  .crn-quote{background:#fef08a;border:3px solid #111;border-radius:14px;padding:1rem 1.2rem;
    font-weight:700;font-size:1.05rem;position:relative;transform:rotate(-.3deg);flex:1 1 240px}
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
  .crn-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin-top:1.1rem;
    animation:crnStatIn .4s ease-out .3s backwards}
  @keyframes crnStatIn{0%{opacity:0;transform:translateY(8px)}100%{opacity:1;transform:translateY(0)}}
  .crn-stat{background:#fff;border:3px solid #111;border-radius:14px;box-shadow:5px 5px 0 #111;
    padding:.7rem .5rem;text-align:center}
  .crn-stat-emoji{font-size:1.25rem;line-height:1;display:block;margin-bottom:.15rem}
  .crn-stat-val{font-weight:800;font-size:1.1rem;display:block;color:#111}
  .crn-stat-lbl{font-size:.64rem;font-weight:700;color:#4b5563;text-transform:uppercase;letter-spacing:.02em}
  /* Citat, ki ga (redko) nariše "Vprašaj še enkrat" namesto navadnega
     reroll-a (glej RARE_QUOTE/crn-reroll) -- zlat rob namesto črnega, da je
     jasno, da gre za nekaj izjemnega, ne le drugačno besedilo. */
  .crn-quote.crn-quote-rare{border-color:#ca8a04;background:#fffbeb;box-shadow:0 0 0 3px #fde68a}
  .crn-quote.crn-quote-rare::after{border-top-color:#ca8a04}
  .crn-quote.crn-quote-rare .crn-quote-tail{border-top-color:#fffbeb}
  .crn-visits{display:inline-block;font-size:.76rem;font-weight:700;color:#111;
    background:#fef08a;border:2px solid #111;border-radius:8px;padding:.25rem .6rem;
    margin:0 0 1rem}
  .crn-vote{margin-top:0}
  .crn-vote-q{font-weight:800;font-size:1.05rem;margin:0 0 .9rem;text-align:center}
  .crn-vote-btns{display:flex;gap:.8rem;justify-content:center;flex-wrap:wrap}
  .crn-vote-btn{font:inherit;font-weight:800;font-size:1rem;cursor:pointer;
    background:#fff;border:3px solid #111;border-radius:999px;padding:.6rem 1.5rem;
    box-shadow:4px 4px 0 #111;transition:transform .1s}
  .crn-vote-btn:active{transform:translate(2px,2px);box-shadow:2px 2px 0 #111}
  .crn-vote-btn:disabled{opacity:.6;cursor:default}
  .crn-vote-btn-gre{background:#bbf7d0}
  .crn-vote-btn-ne{background:#fecaca}
  .crn-vote-bar{height:22px;border:3px solid #111;border-radius:999px;overflow:hidden;
    background:#fecaca}
  .crn-vote-bar span{display:block;height:100%;width:50%;background:#16a34a;
    transition:width .5s ease}
  .crn-vote-count{text-align:center;font-weight:700;font-size:.88rem;margin:.7rem 0 0;
    color:#374151}
  .crn-cam{margin-top:0}
  .crn-cam-label{font-weight:800;font-size:1.05rem;margin:0 0 .9rem;text-align:center}
  .crn-cam-frame{border:3px solid #111;border-radius:14px;overflow:hidden;
    box-shadow:5px 5px 0 #111;background:#111;aspect-ratio:640/480}
  .crn-cam-frame img{display:block;width:100%;height:100%;object-fit:cover}
  .crn-cam-fallback{margin:0;padding:1.6rem 1rem;text-align:center;color:#fff;
    font-weight:600;font-size:.92rem}
  .crn-cam-fallback a{color:#93c5fd}
  .crn-cam-meta{font-size:.78rem;color:#4b5563;text-align:center;margin:.7rem 0 0}
  .crn-cam-meta a{color:#1d4ed8;font-weight:700}
  .crn-report{margin-top:0}
  .crn-report-q{font-weight:800;font-size:1.05rem;margin:0 0 .9rem;text-align:center}
  .crn-report-zones{display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem}
  .crn-report-zbtn{font:inherit;font-weight:700;font-size:.76rem;cursor:pointer;
    background:#fff;border:3px solid #111;border-radius:12px;padding:.6rem .2rem;
    box-shadow:3px 3px 0 #111;transition:transform .1s;text-align:center}
  .crn-report-zbtn:active{transform:translate(1px,1px);box-shadow:2px 2px 0 #111}
  .crn-report-zbtn.sel{background:var(--zc);color:#111}
  .crn-report-zbtn .crn-zicon{width:26px;height:26px;margin:0 auto .25rem;display:block}
  .crn-report-zbtn span{display:block}
  #crn-report-form{margin-top:1rem}
  .crn-report-note{width:100%;box-sizing:border-box;border:3px solid #111;border-radius:12px;
    padding:.6rem .8rem;font:inherit;font-size:.92rem;resize:vertical;min-height:3rem;
    margin:0 0 .7rem}
  .crn-report-ime{width:100%;box-sizing:border-box;border:3px solid #111;border-radius:12px;
    padding:.5rem .8rem;font:inherit;font-size:.88rem;margin:0 0 .7rem}
  .crn-report-week{font-size:.82rem;color:#374151;text-align:center;font-weight:600;margin:1rem 0 0}
  .crn-board{margin-top:0}
  .crn-board-q{font-weight:800;font-size:1.05rem;margin:0 0 .9rem;text-align:center}
  .crn-board-list{display:flex;flex-direction:column;gap:.3rem}
  .crn-board-row{display:flex;justify-content:space-between;align-items:center;gap:.6rem;
    font-size:.88rem;border-bottom:1px dashed #d1d5db;padding:.35rem 0;margin:0}
  .crn-board-row:last-child{border-bottom:none}
  .crn-board-rank{font-weight:800;color:#111;width:1.6rem;flex:0 0 auto}
  .crn-board-name{flex:1;color:#111;font-weight:700;overflow:hidden;text-overflow:ellipsis;
    white-space:nowrap}
  .crn-board-badge{color:#6b7280;font-size:.78rem;flex:0 0 auto;text-align:right}
  .crn-board-empty{font-size:.82rem;color:#6b7280;text-align:center;margin:0}
  .crn-report-badge{margin-top:1rem;text-align:center;background:#fef08a;border:3px solid #111;
    border-radius:14px;padding:.9rem 1rem;box-shadow:5px 5px 0 #111}
  .crn-report-badge-title{font-weight:800;font-size:1.15rem;margin:0 0 .2rem}
  .crn-report-badge-desc{font-size:.85rem;color:#374151;margin:0}
  .crn-report-badge-count{font-size:.75rem;color:#6b7280;margin:.4rem 0 0}
  .crn-report-feed{margin-top:1rem;display:flex;flex-direction:column;gap:.5rem}
  .crn-report-feed-item{font-size:.82rem;border-left:3px solid #111;padding:.15rem .7rem;
    color:#374151;margin:0}
  .crn-report-feed-item b{color:#111}
  .crn-report-feed-empty{font-size:.82rem;color:#6b7280;text-align:center;margin:0}
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
  /* Zelena podlaga loči namestitveni gumb od nevtralnih reroll/deli gumbov
     zgoraj -- edini na tej vrsti, ki vodi ven s strani (na domači zaslon),
     zato sme izstopati. */
  .crn-install-btn{background:#bbf7d0}
  /* Namestitveni CTA je čisto na vrhu, nad junaškim naslovom, na sredini --
     prej skrite drobtine ("Meteorec › Kako je čez Črnivec?") so tu odstranjene,
     ta prostor prevzame gumb (JSON-LD BreadcrumbList v <head> ostaja, samo
     vidni napis je bil odveč na strani, ki nima drugih podstrani). */
  .crn-install-top{text-align:center;margin-bottom:.6rem}
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
     merilnika -- brez tega ostane velik prazen pas na obeh straneh. 640px
     je skoraj polna notranja širina panela (720 - 2×(1.2rem padding + 4px
     border) ≈ 674px), tako da merilnik zares zapolni prostor, ki ga ima, s
     še vedno vidnim zračnim robom. Izid (zvezda+ikona+napis) tu zato skupaj
     zraste namesto da bi samo osamljeno stal sredi bele površine. */
  @media (min-width:600px){
    .crn-gauge{max-width:640px}
    .crn-verdict{min-height:280px}
    .crn-verdict-star{width:280px;height:280px}
    .crn-zicon{width:66px;height:66px}
    .crn-verdict span{font-size:2.4rem;padding:.4rem 1.3rem}
    .crn-data{font-size:1rem;padding:1rem 1.3rem}
    .crn-stats{max-width:560px;margin-left:auto;margin-right:auto;gap:1rem}
    .crn-stat-val{font-size:1.25rem}
  }
</style>
'''


SHARE_JS_TEMPLATE = '''
<script>
(function(){
  "use strict";
  var quotes = __QUOTES_JSON__;
  var rareQuote = __RARE_QUOTE_JSON__;
  var share = __SHARE_JSON__;
  var API = "https://weatherireica1.filip-eremita.workers.dev";
  var CAM_URL = __CAM_URL_JSON__;

  // Živa kamera s prelaza (glej opombo na vrhu generate_crnivec_page.py) --
  // neposreden hotlink, brez našega workerja. Prvi prikaz je iz statičnega
  // <img src> (deluje tudi brez JS), JS doda samo periodično osvežitev in
  // padavinsko varovalko, če DRSI kdaj spremeni pot/zavrne hotlink.
  var camImg = document.getElementById("crn-cam-img");
  var camFallback = document.getElementById("crn-cam-fallback");
  if (camImg && CAM_URL) {
    // Samozdravilno: vsak neuspeh pokaže nadomestno sporočilo, vsak naslednji
    // uspešen prenos ga spet skrije -- brez trajne zastavice, ker je prehoden
    // izpad (DRSI stran ne odgovori enkrat) povsem verjeten in se sam popravi.
    camImg.addEventListener("error", function(){
      camImg.hidden = true;
      if (camFallback) camFallback.hidden = false;
    });
    camImg.addEventListener("load", function(){
      camImg.hidden = false;
      if (camFallback) camFallback.hidden = true;
    });
    setInterval(function(){
      // Vljudnostna oznaka v poizvedbi (isto kot ...?hribi.net dela pri
      // drugih straneh, ki isto kamero hotlinkajo) + časovni žig, da brskalnik
      // ne postreže slike iz predpomnilnika iste URL.
      camImg.src = CAM_URL + "?src=meteorec.si&t=" + Date.now();
    }, 5 * 60 * 1000);
  }

  // Koliko obiskov te strani je brskalnik že videl -- namig na to, da bralec
  // raje vpraša (spet), kot da bi pogledal enkrat in si zapomnil (glej uvodno
  // opombo v generate_crnivec_page.py o tem, kaj je sploh šala te strani).
  // Prvi obisk se ne prikaže -- šele od drugega dalje ima "spet si tu" smisel.
  var visitsEl = document.getElementById("crn-visits");
  if (visitsEl) {
    try {
      var obiski = (parseInt(localStorage.getItem("crn-obiski"), 10) || 0) + 1;
      localStorage.setItem("crn-obiski", String(obiski));
      if (obiski > 1) {
        visitsEl.textContent = "To je tvoj " + obiski + ". obisk te strani. Očitno tudi ti raje vprašaš, kot pogledaš sam.";
        visitsEl.hidden = false;
      }
    } catch (_) {}
  }

  var rerollBtn = document.getElementById("crn-reroll");
  var quoteP = document.querySelector(".crn-quote p");
  var quoteBubble = document.querySelector(".crn-quote");
  if (rerollBtn && quoteP && quoteBubble && quotes.length > 1) {
    rerollBtn.hidden = false;
    rerollBtn.addEventListener("click", function(){
      var cur = quoteP.textContent;
      var next = cur;
      // ~1/30 (torej približno tako redko, kot je citatov v navadnem krogu)
      // pokaže RARE_QUOTE namesto navadnega izbora -- presenečenje, ne
      // enakovreden citat, zato ni v `quotes` in ne v dnevnem izboru.
      var rare = rareQuote && Math.random() < (1 / 30) && cur !== rareQuote;
      if (rare) {
        next = rareQuote;
      } else {
        var tries = 0;
        while (next === cur && tries < 20) {
          next = quotes[Math.floor(Math.random() * quotes.length)];
          tries++;
        }
      }
      quoteP.textContent = next;
      quoteBubble.classList.toggle("crn-quote-rare", !!rare);
      quoteBubble.classList.remove("crn-quote-pop");
      void quoteBubble.offsetWidth;
      quoteBubble.classList.add("crn-quote-pop");
    });
  }

  // Namerna podvojitev namestitvenega toka iz app.js (_installPrompt/_isIOS/
  // installApp) -- ta stran ne nalaga app.js (glej opombo na vrhu datoteke o
  // samostojnih generatorjih), zato je edini način za "Namesti na zaslon" tu
  // lasten, majhen odjemalec istega beforeinstallprompt/iOS vzorca.
  var installBtn = document.getElementById("crn-install");
  var installHint = document.getElementById("crn-install-hint");
  if (installBtn) {
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
      (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    var isStandalone = window.matchMedia("(display-mode: standalone)").matches ||
      navigator.standalone === true;
    var deferredPrompt = null;

    function showInstallBtn(){ installBtn.hidden = false; }
    function hideInstallBtn(){
      installBtn.hidden = true;
      if (installHint) installHint.hidden = true;
    }

    if (!isStandalone) {
      window.addEventListener("beforeinstallprompt", function(e){
        e.preventDefault();
        deferredPrompt = e;
        showInstallBtn();
      });
      window.addEventListener("appinstalled", function(){
        deferredPrompt = null;
        hideInstallBtn();
      });
      // Safari na iOS-u beforeinstallprompt ne pozna, zato gumb tu prikažemo
      // takoj -- klik pokaže ročna navodila (glej spodaj), isto kot na
      // naslovni strani.
      if (isIOS) showInstallBtn();
    }

    installBtn.addEventListener("click", function(){
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function(){
          deferredPrompt = null;
          hideInstallBtn();
        });
        return;
      }
      if (!installHint) return;
      installHint.hidden = false;
      installHint.textContent = isIOS ?
        "Tapni ⬆️ (Deli) spodaj in izberi »Na začetni zaslon«." :
        "Namestitev v tem brskalniku ni na voljo.";
    });
  }

  // Dnevno glasovanje skupnosti: "se ti zdi indeks danes pošten?". Namerno
  // ločeno od IZRAČUNANEGA kazalca (isti razkorak med izračunom in tem, kar
  // pravijo ljudje, je bistvo cele strani -- glej citate zgoraj). Isti vzorec
  // kot /poll v worker.js (dnevni ključ, brez prijave, brez omejitve enega
  // glasu na obiskovalca -- to je vzdušje, ne meritev). localStorage samo
  // prepreči, da bi isti brskalnik zase klikal v neskončnost isti dan;
  // strežnik tega ne uveljavlja.
  var voteBox = document.getElementById("crn-vote");
  var voteBtnGre = document.getElementById("crn-vote-gre");
  var voteBtnNe = document.getElementById("crn-vote-ne");
  var voteResult = document.getElementById("crn-vote-result");
  var voteBar = document.getElementById("crn-vote-bar-gre");
  var voteCount = document.getElementById("crn-vote-count");
  if (voteBox && voteBtnGre && voteBtnNe && voteResult && window.fetch) {
    voteBox.hidden = false;
    var VOTE_KEY = "crn-glas-__TODAY_ISO__";

    function showVoteResult(counts){
      var gre = (counts && counts.gre) || 0, ne = (counts && counts.ne) || 0;
      var total = gre + ne;
      var pct = total ? Math.round((gre / total) * 100) : 50;
      if (voteBar) voteBar.style.width = pct + "%";
      if (voteCount) {
        voteCount.textContent = total ?
          (pct + " % pravi, da gre (" + total + (total === 1 ? " glas" : " glasov") + " danes)") :
          "Bodi prvi, ki danes glasuje.";
      }
      voteBtnGre.hidden = true;
      voteBtnNe.hidden = true;
      voteResult.hidden = false;
    }

    function loadVotes(){
      fetch(API + "/crnivec/glas").then(function(r){ return r.json(); })
        .then(function(d){ showVoteResult(d && d.counts); })
        .catch(function(){});
    }

    var already = null;
    try { already = localStorage.getItem(VOTE_KEY); } catch (_) {}
    if (already) {
      loadVotes();
    } else {
      var oddajGlas = function(option){
        voteBtnGre.disabled = true;
        voteBtnNe.disabled = true;
        try { localStorage.setItem(VOTE_KEY, option); } catch (_) {}
        fetch(API + "/crnivec/glas?option=" + option, { method: "POST" })
          .then(function(r){ return r.json(); })
          .then(function(d){ showVoteResult(d && d.counts); })
          .catch(function(){ loadVotes(); });
      };
      voteBtnGre.addEventListener("click", function(){ oddajGlas("gre"); });
      voteBtnNe.addEventListener("click", function(){ oddajGlas("ne"); });
    }
  }

  // Poročanje o dejanskem stanju + šaljive značke (glej CRN_BADGES v
  // worker.js) -- bogatejše od glasovanja zgoraj: tu obiskovalec izbere
  // eno od ISTIH štirih con kot merilnik (gumbi imajo data-zona, glej
  // report_zone_buttons v generate_crnivec_page.py) in po želji doda opombo.
  // Anonimen porocevalec ID v localStorage, isti vzorec kot igralecId() v
  // igra/igra.js -- namerna podvojitev, ta stran ne nalaga igra.js.
  var repBox = document.getElementById("crn-report");
  if (repBox && window.fetch) {
    repBox.hidden = false;
    var repZones = Array.prototype.slice.call(repBox.querySelectorAll(".crn-report-zbtn"));
    var repForm = document.getElementById("crn-report-form");
    var repNote = document.getElementById("crn-report-note");
    var repHp = document.getElementById("crn-report-hp");
    var repSubmit = document.getElementById("crn-report-submit");
    var repStatus = document.getElementById("crn-report-status");
    var repBadge = document.getElementById("crn-report-badge");
    var repWeek = document.getElementById("crn-report-week");
    var repFeed = document.getElementById("crn-report-feed");
    var repIme = document.getElementById("crn-report-ime");
    var izbranaCona = null;
    var ZONE_LABELS = { sonce: "suho", nekaj: "nekaj je", verige: "verige", spolzko: "spolzko" };

    function porocevalecId(){
      var re = /^[a-zA-Z0-9_-]{8,40}$/;
      try {
        var id = localStorage.getItem("crn-porocevalec");
        if (id && re.test(id)) return id;
      } catch (_) {}
      var abc = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
      var bajti = (window.crypto && crypto.getRandomValues) ? crypto.getRandomValues(new Uint8Array(24)) : null;
      var nov = "";
      for (var i = 0; i < 24; i++) nov += abc[(bajti ? bajti[i] : Math.floor(Math.random() * 256)) % abc.length];
      try { localStorage.setItem("crn-porocevalec", nov); } catch (_) {}
      return nov;
    }

    // Vzdevek je okras za javno lestvico, ne identiteta -- isti vzorec kot
    // beriIme()/shraniIme() v napovej.js/igra.js.
    if (repIme) {
      try { repIme.value = localStorage.getItem("crn-porocevalec-ime") || ""; } catch (_) {}
    }

    function setStatusRep(msg){
      if (!repStatus) return;
      repStatus.hidden = !msg;
      repStatus.textContent = msg || "";
    }

    function renderFeed(porocila){
      if (!repFeed) return;
      if (!porocila || !porocila.length) {
        repFeed.innerHTML = '<p class="crn-report-feed-empty">Še nihče ni poročal danes. Bodi prvi.</p>';
        return;
      }
      repFeed.innerHTML = "";
      porocila.slice(0, 6).forEach(function(p){
        var el = document.createElement("p");
        el.className = "crn-report-feed-item";
        var b = document.createElement("b");
        b.textContent = ZONE_LABELS[p.zona] || p.zona;
        el.appendChild(b);
        // textContent, ne innerHTML -- opomba je prosto uporabniško besedilo
        // (isto pravilo kot pri gobarskih opažanjih).
        el.appendChild(document.createTextNode(p.opomba ? (" — " + p.opomba) : ""));
        repFeed.appendChild(el);
      });
    }

    // Tedenski povzetek je čisto klientski izračun iz istega odgovora kot
    // seznam (dni=7 namesto 3) -- brez ločenega endpointa na worker.js.
    function renderWeekStats(porocila){
      if (!repWeek) return;
      if (!porocila || !porocila.length) { repWeek.hidden = true; return; }
      var stevec = {};
      porocila.forEach(function(p){ stevec[p.zona] = (stevec[p.zona] || 0) + 1; });
      var najpogostejsa = null, najvec = 0;
      Object.keys(stevec).forEach(function(z){
        if (stevec[z] > najvec) { najvec = stevec[z]; najpogostejsa = z; }
      });
      repWeek.textContent = "🗓️ Ta teden: " + porocila.length +
        (porocila.length === 1 ? " poročilo" : " poročil") +
        (najpogostejsa ? " · največkrat: " + (ZONE_LABELS[najpogostejsa] || najpogostejsa) : "");
      repWeek.hidden = false;
    }

    function loadFeed(){
      fetch(API + "/crnivec/porocila?dni=7").then(function(r){ return r.json(); })
        .then(function(d){
          renderFeed(d && d.porocila);
          renderWeekStats(d && d.porocila);
        })
        .catch(function(){});
    }

    repZones.forEach(function(btn){
      btn.addEventListener("click", function(){
        izbranaCona = btn.getAttribute("data-zona");
        repZones.forEach(function(b){ b.classList.toggle("sel", b === btn); });
        if (repForm) repForm.hidden = false;
      });
    });

    // Samostojna, majhna canvas risba za "Deli značko" -- namenoma NE deli
    // helperjev z gauge-jevim "Deli kot sliko" spodaj (wrapText/loadSvgImage
    // ipd.): tisti so definirani ŠELE za zgodnjim-vrnitvenim stavkom
    // (if (!shareBtn...) return;), ta blok pa teče PRED njim in bi jih torej
    // tako ali tako ne mogel poklicati.
    function wrapTextRep(ctx, text, maxWidth){
      var words = text.split(" "), lines = [], line = "";
      for (var i = 0; i < words.length; i++) {
        var test = line ? line + " " + words[i] : words[i];
        if (ctx.measureText(test).width > maxWidth && line) { lines.push(line); line = words[i]; }
        else line = test;
      }
      if (line) lines.push(line);
      return lines;
    }
    function drawBadgeCanvas(znacka, stevilo){
      var W = 640, H = 420;
      var canvas = document.createElement("canvas");
      canvas.width = W; canvas.height = H;
      var ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fdf6e3";
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = "#111";
      for (var y = 8; y < H; y += 16) {
        for (var x = 8; x < W; x += 16) { ctx.beginPath(); ctx.arc(x, y, 1, 0, Math.PI * 2); ctx.fill(); }
      }
      ctx.textAlign = "center";
      ctx.font = "800 26px Inter, system-ui, sans-serif";
      ctx.lineJoin = "round"; ctx.lineWidth = 6; ctx.strokeStyle = "#111";
      ctx.strokeText("KAKO JE ČEZ ČRNIVEC?", W / 2, 56);
      ctx.fillStyle = "#dc2626";
      ctx.fillText("KAKO JE ČEZ ČRNIVEC?", W / 2, 56);

      var px = 40, py = 90, pw = W - 80, ph = 240;
      ctx.fillStyle = "#111"; ctx.fillRect(px + 6, py + 6, pw, ph);
      ctx.fillStyle = "#fef08a"; ctx.fillRect(px, py, pw, ph);
      ctx.lineWidth = 4; ctx.strokeStyle = "#111"; ctx.strokeRect(px, py, pw, ph);

      ctx.fillStyle = "#111";
      ctx.font = "800 32px Inter, system-ui, sans-serif";
      ctx.fillText(znacka.naziv, W / 2, py + 62);

      ctx.font = "600 19px Inter, system-ui, sans-serif";
      var lines = wrapTextRep(ctx, znacka.opis, pw - 60);
      lines.forEach(function(line, i){ ctx.fillText(line, W / 2, py + 108 + i * 27); });

      ctx.font = "700 17px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#374151";
      ctx.fillText("Poročil doslej: " + stevilo, W / 2, py + ph - 22);

      ctx.font = "700 16px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#6b7280";
      ctx.fillText("meteorec.si/crnivec", W / 2, H - 22);
      return canvas;
    }
    function dodajBadgeShareBtn(znacka, stevilo){
      if (!repBadge || !window.HTMLCanvasElement) return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "crn-action-btn";
      btn.textContent = "📤 Deli značko";
      btn.style.marginTop = ".8rem";
      btn.addEventListener("click", function(){
        var canvas = drawBadgeCanvas(znacka, stevilo);
        canvas.toBlob(function(blob){
          if (!blob) return;
          var file = new File([blob], "crnivec-znacka.png", { type: "image/png" });
          if (navigator.canShare && navigator.canShare({ files: [file] })) {
            navigator.share({ files: [file], title: znacka.naziv, text: znacka.naziv + " – meteorec.si/crnivec" })
              .catch(function(){});
            return;
          }
          var url = URL.createObjectURL(blob);
          var a = document.createElement("a");
          a.href = url; a.download = "crnivec-znacka.png";
          document.body.appendChild(a); a.click(); document.body.removeChild(a);
          setTimeout(function(){ URL.revokeObjectURL(url); }, 4000);
        }, "image/png");
      });
      repBadge.appendChild(btn);
    }

    if (repSubmit) {
      repSubmit.addEventListener("click", function(){
        if (!izbranaCona) { setStatusRep("Najprej izberi stanje zgoraj."); return; }
        var ime = repIme ? repIme.value.trim() : "";
        try { localStorage.setItem("crn-porocevalec-ime", ime); } catch (_) {}
        repSubmit.disabled = true;
        setStatusRep("Pošiljam …");
        fetch(API + "/crnivec/porocilo", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            zona: izbranaCona,
            opomba: repNote ? repNote.value.trim() : "",
            porocevalec: porocevalecId(),
            ime: ime,
            website: repHp ? repHp.value : ""
          })
        }).then(function(r){ return r.json().then(function(d){ return { ok: r.ok, data: d }; }); })
          .then(function(res){
            if (!res.ok || !res.data || res.data.error) {
              setStatusRep((res.data && res.data.error) || "Poročilo ni uspelo.");
              repSubmit.disabled = false;
              return;
            }
            setStatusRep("Hvala za poročilo!");
            if (repBadge && res.data.znacka) {
              repBadge.hidden = false;
              var t = document.createElement("p");
              t.className = "crn-report-badge-title";
              t.textContent = res.data.znacka.naziv;
              var d2 = document.createElement("p");
              d2.className = "crn-report-badge-desc";
              d2.textContent = res.data.znacka.opis;
              var c = document.createElement("p");
              c.className = "crn-report-badge-count";
              c.textContent = "Poročil doslej: " + res.data.stevilo;
              repBadge.innerHTML = "";
              repBadge.appendChild(t);
              repBadge.appendChild(d2);
              repBadge.appendChild(c);
              dodajBadgeShareBtn(res.data.znacka, res.data.stevilo);
            }
            if (repForm) repForm.hidden = true;
            repZones.forEach(function(b){ b.disabled = true; });
            loadFeed();
            loadBoard();
          }).catch(function(){
            setStatusRep("Poročilo ni uspelo — preveri povezavo.");
            repSubmit.disabled = false;
          });
      });
    }

    loadFeed();
  }

  // Javna lestvica poročevalcev (glej GET /crnivec/lestvica v worker.js) --
  // ista, ki jo osveži oddaja zgoraj (loadBoard po uspešni oddaji). Ločen
  // blok, da deluje tudi, če je crn-report panel iz kakšnega razloga izpuščen.
  var boardBox = document.getElementById("crn-board");
  var boardList = document.getElementById("crn-board-list");
  function loadBoard(){
    if (!boardBox || !boardList || !window.fetch) return;
    boardBox.hidden = false;
    fetch(API + "/crnivec/lestvica").then(function(r){ return r.json(); })
      .then(function(d){
        var lestvica = (d && d.lestvica) || [];
        if (!lestvica.length) {
          boardList.innerHTML = '<p class="crn-board-empty">Še ni dovolj poročil za lestvico. Bodi prvi zgoraj.</p>';
          return;
        }
        boardList.innerHTML = "";
        lestvica.forEach(function(r, i){
          var row = document.createElement("div");
          row.className = "crn-board-row";
          var rank = document.createElement("span");
          rank.className = "crn-board-rank";
          rank.textContent = (i + 1) + ".";
          var name = document.createElement("span");
          name.className = "crn-board-name";
          name.textContent = r.ime || "Anonimni";
          var badge = document.createElement("span");
          badge.className = "crn-board-badge";
          badge.textContent = r.znacka + " · " + r.stevilo;
          row.appendChild(rank); row.appendChild(name); row.appendChild(badge);
          boardList.appendChild(row);
        });
      }).catch(function(){});
  }
  loadBoard();

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
      ctx.font = "600 15px Inter, system-ui, sans-serif";
      ctx.fillStyle = "#6b7280";
      ctx.fillText(share.streak, W / 2, py + 402);

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
            text: share.verdict + " \\u2013 meteorec.si/crnivec"
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

    # Suh niz je iz IZMERJENE zgodovine postaje (dolina), ne iz izračuna za
    # sam prelaz (902 m) — namenoma OZNAČEN kot tak na kartici (isto načelo
    # kot ARSO/Open-Meteo, ki se na padavinski ploščici ne smeta zliti v eno
    # število). dry_streak() je uvožen iz generate_story_card.py, ne
    # podvojen tu; konča na VČERAJ, ker je danes še nepopoln dan (isti klic
    # kot pri story-cardovem DROUGHT_DRY_STREAK).
    hist = seo.load_history()
    streak = dry_streak(hist, seo.TODAY - datetime.timedelta(days=1))

    temp_txt = f'{seo.num(weather.get("temp_c"), 1)} °C' if weather.get("temp_c") is not None else "– °C"
    snow_txt = (f'{seo.num(weather.get("expected_snow_cm_24h"), 1)} cm snega v 24 h'
                if weather.get("expected_snow_cm_24h") is not None else "– cm snega v 24 h")
    # Kratki različici samo za crn-stat kartice (glej build_body spodaj) --
    # temp_txt/snow_txt (polna poved) grosta naprej v share_payload za "Deli
    # kot sliko", da tam ni treba podvajati logike.
    snow_val = (f'{seo.num(weather.get("expected_snow_cm_24h"), 1)} cm'
                if weather.get("expected_snow_cm_24h") is not None else "– cm")
    streak_val = f"{streak} dni"

    # Dnevna OG kartica: isti vzorec kot generate_igra_og.py, poklican iz
    # generate_igra_page.py -- riše se tu (ne v svojem koraku delavnega toka),
    # da slika in og:image na strani nikoli ne moreta biti iz različnih dni.
    # Ob manjkajočem Pillow ali napaki stran pade nazaj na splošno
    # og-image.jpg in stran se vseeno objavi (slika ni vredna tega, da bi
    # zaradi nje izostala stran).
    og_slika = None
    try:
        import generate_crnivec_og  # noqa: PLC0415 — lokalno, da manjkajoč Pillow ne podre teka
        og_slika = generate_crnivec_og.zapisi(zone, weather, quote, streak)
    except Exception as e:  # noqa: BLE001 — namenoma široko, glej opombo zgoraj
        print(f"! OG kartica ni nastala ({e}) — ostane splošna og-image.jpg", file=sys.stderr)

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
        "streak": f"suh niz v dolini: {streak_val}",
        "gauge": gauge_svg(zone, static=True),
        "icon": icon_svg_static(zone["id"]),
    }
    # Gumbi za poročanje uporabijo ISTE cone/ikone kot merilnik zgoraj (glej
    # ZONE_ICONS), samo s krajšo oznako (ZONE_SHORT) -- da poročevalec izbira
    # med istimi štirimi možnostmi, ki jih izračuna prikazuje, in je
    # razkorak med njima (bistvo strani) dejansko primerljiv.
    report_zone_buttons = "".join(
        f'<button type="button" class="crn-report-zbtn" data-zona="{z["id"]}" '
        f'style="--zc:{z["color"]}">{ZONE_ICONS[z["id"]]}<span>{ZONE_SHORT[z["id"]]}</span></button>'
        for z in ZONES
    )

    quotes_json = json.dumps(QUOTES, ensure_ascii=False).replace("</", "<\\/")
    rare_quote_json = json.dumps(RARE_QUOTE, ensure_ascii=False).replace("</", "<\\/")
    share_json = json.dumps(share_payload, ensure_ascii=False).replace("</", "<\\/")
    cam_url_json = json.dumps(CAM_URL, ensure_ascii=False).replace("</", "<\\/")
    share_js = (SHARE_JS_TEMPLATE
                .replace("__QUOTES_JSON__", quotes_json)
                .replace("__RARE_QUOTE_JSON__", rare_quote_json)
                .replace("__SHARE_JSON__", share_json)
                .replace("__CAM_URL_JSON__", cam_url_json)
                .replace("__TODAY_ISO__", today_iso))

    body = f'''{CSS}
  <div class="crn-wrap">
    <div class="crn-install-top">
      <button type="button" id="crn-install" class="crn-action-btn crn-install-btn" hidden>📲 Namesti na zaslon</button>
      <p id="crn-install-hint" class="crn-share-status" role="status" aria-live="polite" hidden></p>
    </div>
    <div class="crn-hero">
      {mountain_icon_svg()}
      <div>
        <h1 class="crn-title">Kako je čez Črnivec?</h1>
        <p class="crn-sub">Vprašanje, ki ga v dolini postavijo vsak dan. Uradnega odgovora
        ni – tale indeks pa (skoraj) enako zanesljivo kaže razmere.</p>
        <p id="crn-visits" class="crn-visits" hidden></p>
      </div>
    </div>

    <div class="crn-panel tilt">
      {gauge_svg(zone)}
      <div class="crn-verdict" style="color:{zone['color']}">{starburst_svg(zone['color'])}{ZONE_ICONS[zone['id']]}<span>{zone['label']}</span>
      <p class="crn-verdict-desc">{zone['desc']}</p></div>
      <div class="crn-stats">
        <div class="crn-stat"><span class="crn-stat-emoji" aria-hidden="true">🌡️</span>
          <span class="crn-stat-val">{temp_txt}</span><span class="crn-stat-lbl">na prelazu</span></div>
        <div class="crn-stat"><span class="crn-stat-emoji" aria-hidden="true">❄️</span>
          <span class="crn-stat-val">{snow_val}</span><span class="crn-stat-lbl">snega v 24 h</span></div>
        <div class="crn-stat"><span class="crn-stat-emoji" aria-hidden="true">🌂</span>
          <span class="crn-stat-val">{streak_val}</span><span class="crn-stat-lbl">suh niz v dolini</span></div>
      </div>
      <div class="crn-data">Isti izračun kot na <a href="/zima/prevoznost-prelazov/">resni strani</a>
      – tukaj so nalepke con samo za hec.</div>
    </div>

    <div class="crn-panel crn-report" id="crn-report" hidden>
      <p class="crn-report-q">📋 Poročaj, kako je bilo, ko si šel čez</p>
      <div class="crn-report-zones" id="crn-report-zones">
        {report_zone_buttons}
      </div>
      <div id="crn-report-form" hidden>
        <textarea id="crn-report-note" class="crn-report-note" maxlength="140"
          placeholder="Neobvezna opomba (npr. »samo do polovice«) …"></textarea>
        <input type="text" id="crn-report-ime" class="crn-report-ime" maxlength="24"
          placeholder="Vzdevek za lestvico (neobvezno)">
        <input type="text" name="website" id="crn-report-hp" autocomplete="off" tabindex="-1"
          style="position:absolute;left:-9999px" aria-hidden="true">
        <button type="button" id="crn-report-submit" class="crn-action-btn">Pošlji poročilo</button>
      </div>
      <p id="crn-report-status" class="crn-share-status" role="status" aria-live="polite" hidden></p>
      <div id="crn-report-badge" class="crn-report-badge" hidden></div>
      <p id="crn-report-week" class="crn-report-week" hidden></p>
      <div id="crn-report-feed" class="crn-report-feed"></div>
    </div>

    <div class="crn-panel crn-board" id="crn-board" hidden>
      <p class="crn-board-q">🏆 Lestvica poročevalcev</p>
      <div id="crn-board-list" class="crn-board-list"></div>
    </div>

    <div class="crn-panel crn-cam">
      <p class="crn-cam-label">📷 Namesto da vprašaš — poglej. Živa kamera s prelaza:</p>
      <div class="crn-cam-frame">
        <img id="crn-cam-img" src="{CAM_URL}" alt="Živa kamera s prelaza Črnivec (902 m)" width="640" height="480">
        <p id="crn-cam-fallback" class="crn-cam-fallback" hidden>Kamera trenutno ni dosegljiva.
        <a href="https://www.promet.si/sl/kamere" target="_blank" rel="noopener">Poglej neposredno na promet.si</a>.</p>
      </div>
      <p class="crn-cam-meta">Vir: <a href="https://www.promet.si" target="_blank" rel="noopener">promet.si</a>
      (Direkcija RS za infrastrukturo) — samodejno se osveži vsakih nekaj minut.</p>
    </div>

    <div class="crn-quote-row">
      <div class="crn-quote"><p>{quote}</p><div class="crn-quote-tail"></div></div>
      <div class="crn-avatar">{avatar_svg()}<span>nekdo iz skupine</span></div>
    </div>

    <div class="crn-panel crn-vote" id="crn-vote" hidden>
      <p class="crn-vote-q">Se ti zdi ta ocena danes poštena?</p>
      <div class="crn-vote-btns">
        <button type="button" id="crn-vote-gre" class="crn-vote-btn crn-vote-btn-gre">🟢 Gre</button>
        <button type="button" id="crn-vote-ne" class="crn-vote-btn crn-vote-btn-ne">🔴 Ne gre</button>
      </div>
      <div class="crn-vote-result" id="crn-vote-result" hidden>
        <div class="crn-vote-bar"><span id="crn-vote-bar-gre"></span></div>
        <p class="crn-vote-count" id="crn-vote-count"></p>
      </div>
    </div>

    <div class="crn-actions">
      <button type="button" id="crn-reroll" class="crn-action-btn" hidden>🔁 Vprašaj še enkrat</button>
      <button type="button" id="crn-share" class="crn-action-btn" hidden>📤 Deli kot sliko</button>
    </div>
    <p id="crn-share-status" class="crn-share-status" role="status" aria-live="polite" hidden></p>

    <p class="crn-fine"><strong>Drobni tisk:</strong> ta indeks je znanstveno pomešan z ugibanjem,
    klepetom v čakalnici in kakšnim komentarjem iz FB. Meteorec ne odgovarja, če je bilo v
    resnici drugače – kar je, mimogrede, tudi bistvo te strani.
    <span class="crn-links">Za resnično stanje ceste glej <a href="/zima/prevoznost-prelazov/">MeteoZima:
    prevoznost prelazov</a> ali uradne vire: promet.si, AMZS, DARS.</span></p>

    <a class="crn-back" href="/">← Nazaj na meteorec.si</a>
  </div>
{share_js}'''
    return body, og_slika


def main():
    data = load_json(DATA_PATH)
    if not data:
        print("✗ data/winter-data.json manjka -- najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1

    body, og_slika = build_body(data)
    title = "Kako je čez Črnivec? – (ne)uradni indeks"
    desc = "Vsakodnevno vprašanje iz lokalnih FB-skupin – s samoironičnim »indeksom« in pravimi vremenskimi informacijami s 902 m visokega prelaza."
    # manifest.json ima relativne poti ("./") -- te se po specifikaciji Web App
    # Manifest razrešijo proti URL-ju SAME manifest.json (koren strani), ne
    # proti tej podstrani, zato je varno linkati isti manifest tudi od tu brez
    # tveganja, da bi "namesti" ustvaril ločeno aplikacijo z obsegom /crnivec/.
    pwa_head = (
        '<meta name="theme-color" content="#dc2626">\n'
        '<meta name="mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-capable" content="yes">\n'
        '<meta name="apple-mobile-web-app-title" content="Meteorec">\n'
        '<link rel="manifest" href="/manifest.json">\n'
        '<link rel="apple-touch-icon" href="/icon-192.png">'
    )
    schema = "\n".join([
        pwa_head,
        seo.webpage_schema("/crnivec/", title, desc, date_published="2026-09-20", image=og_slika),
        seo.crumbs_schema([("Meteorec", "/"), ("Kako je čez Črnivec?", None)]),
    ])
    html = seo.page_shell(title, desc, "/crnivec/", schema, body, og_image=og_slika)
    seo.write_page("crnivec/index.html", html, force=True)
    print(f"  → crnivec/index.html{f' (OG: {og_slika})' if og_slika else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
