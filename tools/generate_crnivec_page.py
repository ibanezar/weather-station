#!/usr/bin/env python3
"""
tools/generate_crnivec_page.py — /crnivec/, humorna stran "Kako je čez Črnivec?"

"Kako je čez Črnivec?" je (po Filipovih besedah) eno najpogostejših vprašanj v
lokalnih FB skupinah — mešanica dveh stvari: (1) odgovori si skoraj vedno
nasprotujejo/so neuporabni, (2) ljudje raje vprašajo, kot da bi pogledali sami.
Ta stran to zafrkava, NAMENOMA ločeno od resne /zima/prevoznost-prelazov/
(ki ostane edina resna referenca — glej cross-link na dnu obeh strani).

Od prenove 24. 9. 2026 je stran HITER MOBILNI DASHBOARD za stanje prelaza
(prej plakat z merilnikom na vrhu): v prvem zaslonu status ceste (STATUS),
temperatura, sneg, čas posodobitve in gumb do kamere; nato kamera | poročanje,
šele potem humor, glasovanje, lestvica in (v accordionih) razlaga indeksa in
značka. Šaljiva nalepka cone ostane kot "Meteorec indeks: …" pod glavnim
statusom, nad njim pa merilnik. Stripovski slog (debel obris, zamaknjena
senca, pikčasto ozadje) namesto temne Meteorec teme; glavo/nogo/spodnji
meni skrije isti CSS-trik kot igra/igra.css. Brez zunanje pisave: obstoječi samostoječi Inter.

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
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
from generate_story_card import dry_streak  # noqa: E402 — isti izračun kot na zgodbah, ne podvojen tu
from crnivec_zones import ZONES, pick_zone  # noqa: E402 — deljeno z generate_story_card.py (tema CRNIVEC)

ROOT = seo.ROOT
DATA_PATH = os.path.join(ROOT, "data", "winter-data.json")

# Uradna kamera DRSI na prelazu (glej opombo na vrhu datoteke) — spremeni
# samo tu, JS jo bere iz istega niza (glej CAM_URL v build_body spodaj).
CAM_URL = "https://www.drsc.si/kamere/Crnivec/Crn1_0001.jpg"

# Isti worker, ki streže /crnivec/porocilo, /crnivec/glas ipd. — tudi
# /crnivec/znacka.svg (vstavljiva značka, glej opombo pri crn-embed spodaj).
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"

# ZONES/pick_zone sta v skupnem crnivec_zones.py (uvožena spodaj) — tudi
# generate_story_card.py (tema CRNIVEC) ju rabi, glej opombo tam o krožnem
# uvozu.

# Kratke oznake ISTIH con za gumbe poročanja (glej crn-report spodaj) — polni
# ZONES["label"] (npr. "SPOLZKO, PAZI") je glasen naslov za merilnik, v
# štirih ozkih gumbih v vrsti pa ne bi bil čitljiv.
ZONE_SHORT = {"sonce": "Suho", "nekaj": "Nekaj je", "verige": "Verige", "spolzko": "Spolzko"}

# Glavni status na strani (prenova 24. 9. 2026). Šaljiva nalepka cone
# (ZONES["label"], npr. "SUHO K POPR") je razumljiva le tistemu, ki stran že
# pozna, zato gre v drugo vrsto kot "Meteorec indeks: …"; naslov kartice mora
# biti jasen vsakomur. Ista uvrstitev (pick_zone), samo drugačno besedilo --
# ZONES ostane nespremenjen, ker ga bereta tudi OG kartica in tema zgodbe.
# bg/ink sta svetla podlaga in temno besedilo v barvi cone: kontrast besedila
# je ≥ 7:1 na vseh štirih, česar polna barva cone (rumena!) z belim ne doseže.
STATUS = {
    "sonce":   {"status": "Cesta je suha",   "desc": "Cesta je normalno prevozna.",
                "bg": "#dcfce7", "ink": "#14532d"},
    "nekaj":   {"status": "Pozor",           "desc": "Okoli ničle — ponekod je lahko sneg ali led. Vozi previdno.",
                "bg": "#fef9c3", "ink": "#713f12"},
    "verige":  {"status": "Zimske razmere",  "desc": "V naslednjih 24 urah je pričakovan sneg. Brez zimske opreme ne hodi.",
                "bg": "#ffedd5", "ink": "#7c2d12"},
    "spolzko": {"status": "Zelo spolzko",    "desc": "Pod ničlo — nevarnost poledice. Vozi zelo previdno.",
                "bg": "#fee2e2", "ink": "#7f1d1d"},
}

# Velike stripovske ilustracije za kartici Temperatura/Sneg (samo na namizju,
# kjer je v desnem stolpcu heroja prostor -- glej .crn-card-art). Isti slog
# kot ZONE_ICONS: debel črn obris, ploskovite barve. Čisti okras (aria-hidden).
CARD_ART = {
    "temp": '''<svg viewBox="0 0 80 120" aria-hidden="true">
      <rect x="28" y="6" width="24" height="80" rx="12" fill="#fff" stroke="#111" stroke-width="5"/>
      <circle cx="40" cy="94" r="20" fill="#dc2626" stroke="#111" stroke-width="5"/>
      <rect x="35" y="40" width="10" height="50" rx="5" fill="#dc2626"/>
      <g stroke="#111" stroke-width="4" stroke-linecap="round">
        <line x1="52" y1="24" x2="62" y2="24"/><line x1="52" y1="40" x2="62" y2="40"/>
        <line x1="52" y1="56" x2="62" y2="56"/><line x1="52" y1="72" x2="62" y2="72"/>
      </g>
      <circle cx="33" cy="88" r="5" fill="#fff" opacity=".7"/>
    </svg>''',
    "snow": '''<svg viewBox="0 0 120 120" aria-hidden="true">
      <circle cx="60" cy="60" r="54" fill="#e0f2fe" stroke="#111" stroke-width="5"/>
      <g stroke="#111" stroke-width="7" stroke-linecap="round">
        <line x1="60" y1="20" x2="60" y2="100"/><line x1="25.4" y1="40" x2="94.6" y2="80"/>
        <line x1="25.4" y1="80" x2="94.6" y2="40"/>
      </g>
      <g stroke="#0284c7" stroke-width="4" stroke-linecap="round">
        <line x1="60" y1="20" x2="60" y2="100"/><line x1="25.4" y1="40" x2="94.6" y2="80"/>
        <line x1="25.4" y1="80" x2="94.6" y2="40"/>
      </g>
      <g fill="none" stroke="#111" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M50 26 60 36 70 26"/><path d="M50 94 60 84 70 94"/>
        <path d="M26 52 38 50 34 38"/><path d="M94 68 82 70 86 82"/>
        <path d="M26 68 38 70 34 82"/><path d="M94 52 82 50 86 38"/>
      </g>
      <circle cx="60" cy="60" r="7" fill="#fff" stroke="#111" stroke-width="4"/>
    </svg>''',
}

# Enotne obrisne ikone za UI (24×24, currentColor) -- emoji ostanejo samo v
# sproščenih, šaljivih delih strani, ne v osnovni ikonografiji.
UI_ICONS = {
    "temp": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><path d="M14 14.8V4a2 2 0 1 0-4 0v10.8a4 4 0 1 0 4 0Z"/></svg>',
    "snow": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'aria-hidden="true"><path d="M12 2v20M4.9 6.5l14.2 11M19.1 6.5 4.9 17.5M9 4l3 2 3-2M9 20l3-2 3 2"/></svg>',
    "cam":  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true"><path d="M3 7h3l2-3h8l2 3h3v13H3Z"/><circle cx="12" cy="13" r="4"/></svg>',
}

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


HISTORY_JSON_PATH = os.path.join(ROOT, "data", "crnivec-history.json")


def archive_yesterday_vote():
    """Enkrat na dan arhivira VČERAJŠNJI (že zaključen) izid dnevnega
    glasovanja (/crnivec/glas v worker.js) v data/crnivec-history.json --
    brez tega bi crnivec_glas:<datum> v KV po 400 dneh (glej opombo tam)
    izginil, ne da bi kdaj postal del dolgoročne statistike na strani (glej
    accuracy_section_html spodaj). Idempotentno (če je včerajšnji dan že
    zapisan, ne kliče znova) in tiho odpove ob mrežni napaki ali izpadu
    workerja -- en manjkajoč dan ne sme podreti generiranja strani."""
    hist = load_json(HISTORY_JSON_PATH, default=[]) or []
    yesterday = (seo.TODAY - datetime.timedelta(days=1)).isoformat()
    if any(e.get("datum") == yesterday for e in hist):
        return hist
    try:
        url = f"{WORKER_BASE}/crnivec/glas?datum={yesterday}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Meteorec-Crnivec/1.0)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        counts = data.get("counts") or {}
        gre, ne = int(counts.get("gre") or 0), int(counts.get("ne") or 0)
        if gre + ne == 0:
            return hist  # nihče ni glasoval -- ni kaj arhivirati, poskusi spet jutri
        hist.append({"datum": yesterday, "gre": gre, "ne": ne})
        hist = hist[-365:]
        with open(HISTORY_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        print(f"⚠ crnivec-history.json ni bil posodobljen: {e}", file=sys.stderr)
    return hist


def accuracy_section_html(history):
    """Poštenost merilnika, izmerjena z GLASOVANJEM skupnosti (isti vzorec
    kot samo glasovanje -- ravno razkorak med izračunom in tem, kar
    pravijo ljudje, je bistvo strani), ne s primerjavo con/poročil: to bi
    zahtevalo dodatno arhiviranje računanega stanja vsak dan, glasovanje pa
    že samo neposredno odgovarja na vprašanje "je ocena poštena?"."""
    n = len(history)
    if n < 7:
        note = (f"Šele začenjam zbirati podatke iz glasovanja (imam {n} od 7 dni, "
                "ki jih rabim za prvo številko) — vrni se čez teden dni.")
        return (f'<section class="crn-panel crn-accuracy">'
                f'<h2 class="crn-h2">Kako pošten je indeks?</h2>'
                f'<p class="crn-accuracy-note">{note}</p></section>')
    fair_days = sum(1 for e in history if e.get("gre", 0) >= e.get("ne", 0))
    pct = round(100 * fair_days / n)
    return (f'<section class="crn-panel crn-accuracy">'
            f'<h2 class="crn-h2">Kako pošten je indeks?</h2>'
            f'<p class="crn-accuracy-big">{pct} %</p>'
            f'<p class="crn-accuracy-note">dni ({fair_days} od {n} zabeleženih), ko je večina '
            f'glasovalcev rekla, da je bila ocena tistega dne poštena.</p></section>')


def needle_angle(zone):
    return zone["mid"]


def arc_point(cx, cy, r, deg):
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy - r * math.sin(rad)


def gauge_svg(zone, static=False):
    """Merilnik "Črnivski indeks". static=True: samostojna različica za
    "Deli kot sliko" (glej SHARE_JS_TEMPLATE) -- eksplicitna width/height
    (canvas Image potrebuje znano velikost) in kazalec zapečen kot SVG
    transform atribut namesto CSS --rot spremenljivke (canvas slika nima
    dostopa do CSS strani/animacije).

    Na strani stoji na vrhu statusne kartice, nad glavnim statusom (prenova
    24. 9. 2026: merilnik je bil za en dan odstranjen in vrnjen na Filipovo
    željo -- je prepoznaven znak strani). Klientski živi preračun v statični
    kopiji zasuka kazalec z regexom na edinem rotate() -- ne dodajaj drugega
    transform="rotate(…)" v SVG."""
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
        # Brez transform="rotate(...)" atributa -- CSS animacija (crnNeedleSettle)
        # rotacijo prevzame prek --rot spremenljivke, XML atribut bi jo tiho
        # prepisal/mešal z njo (SVG CSS transform ima prednost pred atributom).
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
    # in ga brez xmlns molče zavrže -- zato je tu vedno.
    # viewBox je širši od izrisa (-20..410 namesto 0..380): skrajni levi/desni
    # napis (text-anchor end/start, glej zgoraj) raste samo stran od loka in
    # pri preozkem viewBoxu se obreže čez rob (izmerjeno z getBBox()).
    # Na strani (ne static) je viewBox še malo širši: na ozkem telefonu se
    # pisava merilnika pomanjša in zaokroževanje je skrajni napis
    # ("SPOLZKO, PAZI") pri 360 px odrezalo.
    size_attrs = ' width="430" height="230"' if static else ''
    view_box = "-20 0 430 230" if static else "-34 0 458 230"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}"{size_attrs} '
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


CSS = '''
<style>
  /* Prenova 24. 9. 2026: stran je hiter mobilni DASHBOARD za stanje prelaza,
     oblečen v prvotni stripovski slog (debel črn obris, zamaknjena senca,
     pikčasto ozadje, rdeč naslov z obrisom). Hierarhija: status ceste > kamera > meritve > vse
     ostalo (humor, lestvica, značka, drobni tisk). Mobile-first: osnovna
     pravila so za telefon, @media (min-width:…) jih samo razširijo.
     Razmiki so iz lestvice 8/12/16/24/32/48/64 px (--s1…--s7), zaobljenost
     12–18 px. Statusna kartica je edina
     vizualno "glasna" -- njeno barvo nosi data-zone (glej STATUS spodaj),
     barva pa NIKOLI ni edini nosilec pomena (vedno tudi besedilo). */
  .site-head,#bg,.site-foot,.app-bottomnav{display:none!important}
  /* Brez site-foot/app-bottomnav ni nič, kar bi zapolnilo sitewide
     body{min-height:100vh} (style.css) -- telo naj se skrči na vsebino. */
  body{background:#fdf6e3!important;background-image:radial-gradient(#111 1px,transparent 1.4px)!important;
    background-size:16px 16px!important;background-position:-4px -4px!important;min-height:0!important}
  .wrap{max-width:1140px}
  .crn{--s1:8px;--s2:12px;--s3:16px;--s4:24px;--s5:32px;--s6:48px;--s7:64px;
    --ink:#111;--ink2:#374151;--muted:#4b5563;--line:#111;--card:#fff;--link:#1d4ed8;
    --bd:3px solid #111;--sh:5px 5px 0 #111;
    font-family:Inter,system-ui,sans-serif;color:var(--ink);font-size:16px;line-height:1.5;
    padding:var(--s3) 0 var(--s6)}
  .crn a{color:var(--link)}
  .crn [hidden]{display:none!important}

  /* ── Vrhnja vrstica ─────────────────────────────────────────── */
  .crn-top{display:flex;align-items:center;justify-content:space-between;gap:var(--s2);
    min-height:48px;margin-bottom:var(--s3)}
  .crn-brand{font-size:13px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
    color:var(--ink)!important;text-decoration:none;display:inline-flex;align-items:center;min-height:48px;
    background:#fff;border:var(--bd);border-radius:999px;padding:0 var(--s3);box-shadow:3px 3px 0 #111}
  .crn-install-wrap{text-align:right}

  /* ── HERO ───────────────────────────────────────────────────── */
  .crn-hero{max-width:760px;margin:0 auto var(--s5);text-align:center}
  .crn-eyebrow{display:inline-block;font-size:13px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
    color:var(--ink);background:#fef08a;border:2px solid #111;border-radius:8px;padding:2px var(--s1);
    margin:0 0 var(--s2)}
  /* Glava: gorska maskota (klikljiv easter egg, glej #crn-mascot) + naslov. */
  .crn-head{display:flex;flex-direction:column;align-items:center;gap:4px;margin-bottom:var(--s3)}
  .crn-head .crn-title{margin:0}
  .crn-title{font-size:36px;font-weight:800;line-height:1.1;letter-spacing:-.01em;margin:0 0 var(--s4);
    color:#dc2626;text-transform:uppercase;transform:rotate(-.6deg);
    text-shadow:3px 3px 0 #111,-1px -1px 0 #111,1px -1px 0 #111,-1px 1px 0 #111}
  .crn-strike{font-size:15px;font-weight:800;color:#fff;background:#dc2626;border:var(--bd);
    box-shadow:var(--sh);border-radius:12px;padding:var(--s2) var(--s3);margin:0 0 var(--s3);text-align:left}

  .crn-status{--zc:#16a34a;--zbg:#dcfce7;--zink:#14532d;
    background:var(--zbg);color:var(--zink);border:4px solid #111;border-radius:18px;
    padding:var(--s2) var(--s3) var(--s3);box-shadow:8px 8px 0 #111;
    transition:background-color .4s,border-color .4s,color .4s}
  /* Telefon: merilnik, ikona in maskota so namenoma manjši -- status,
     "posodobljeno", temperatura in sneg morajo biti vidni brez drsenja
     (3-sekundni test iz UX audita, 24. 9. 2026). */
  .crn-gauge{width:100%;max-width:290px;display:block;margin:0 auto}
  .crn-needle{animation:crnNeedleSettle .8s cubic-bezier(.34,1.56,.64,1) forwards;
    transition:transform .6s cubic-bezier(.34,1.56,.64,1)}
  @keyframes crnNeedleSettle{from{transform:rotate(0deg)}to{transform:rotate(var(--rot))}}
  .crn-status-icon{display:flex;justify-content:center;margin:-4px 0 var(--s1)}
  .crn-status-icon .crn-zicon{width:36px;height:36px}
  .crn-status-title{font-size:34px;font-weight:800;line-height:1.1;letter-spacing:.01em;
    text-transform:uppercase;margin:0}
  .crn-status-desc{font-size:16px;font-weight:600;margin:var(--s1) auto 0;max-width:34ch}
  .crn-status-index{display:inline-block;font-size:13px;font-weight:700;margin-top:var(--s2);
    background:#fff;color:var(--ink);border:2px solid #111;border-radius:999px;padding:4px var(--s2)}

  .crn-cards{display:grid;grid-template-columns:1fr 1fr;gap:var(--s2);margin-top:var(--s2);text-align:left}
  .crn-card{position:relative;background:var(--card);border:var(--bd);border-radius:14px;box-shadow:var(--sh);padding:var(--s3)}
  .crn-card-art{display:none}
  .crn-card-h{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted);margin:0 0 var(--s1);display:flex;align-items:center;gap:6px}
  .crn-card-h svg{width:16px;height:16px;flex:0 0 auto}
  .crn-big{font-size:28px;font-weight:800;line-height:1.05;letter-spacing:-.02em;margin:0;
    font-variant-numeric:tabular-nums}
  .crn-card-sub{font-size:13px;color:var(--muted);margin:var(--s1) 0 0}
  .crn-card-sub b{color:var(--ink2)}
  .crn-card-h2{margin-top:var(--s2);padding-top:var(--s2);border-top:2px dashed #d6d0c2}
  .crn-mid{font-size:20px;font-weight:800;margin:0;font-variant-numeric:tabular-nums}
  .crn-na{font-size:15px;font-weight:600;color:var(--muted)}

  .crn-updated{font-size:13px;font-weight:700;margin:var(--s2) 0 0;opacity:.85}
  .crn-fresh{font-size:13px;font-weight:700;margin:var(--s1) 0 0}
  .crn-btn{font:inherit;font-size:15px;font-weight:700;cursor:pointer;display:inline-flex;
    align-items:center;justify-content:center;gap:var(--s1);min-height:48px;padding:0 var(--s4);
    border-radius:999px;border:var(--bd);background:var(--card);color:var(--ink)!important;
    box-shadow:4px 4px 0 #111;text-decoration:none;transition:background-color .15s,transform .1s}
  .crn-btn:hover{background:#fef9c3}
  .crn-btn:active{transform:translate(2px,2px);box-shadow:2px 2px 0 #111}
  .crn-btn:disabled{opacity:.6;cursor:default}
  .crn-btn:focus-visible,.crn-zbtn:focus-visible,.crn summary:focus-visible{outline:3px solid #2563eb;outline-offset:2px}
  .crn-btn-primary{background:#dc2626;color:#fff!important;
    text-transform:uppercase;letter-spacing:.04em;width:100%;max-width:420px;margin-top:var(--s3)}
  .crn-btn-primary:hover{background:#b91c1c}
  .crn-btn svg{width:20px;height:20px}

  /* ── Sekcije pod herojem ────────────────────────────────────── */
  /* Telefon: stolpca ne obstajata (display:contents), vrstni red je iz
     .crn-o1…7 -- kamera, poročanje, nasvet, glasovanje, poštenost, lestvica,
     razlaga indeksa + značka. */
  .crn-cols{display:flex;flex-direction:column;gap:var(--s4)}
  .crn-col{display:contents}
  .crn-o1{order:1}.crn-o2{order:2}.crn-o3{order:3}.crn-o4{order:4}.crn-o5{order:5}.crn-o6{order:6}
  .crn-o7{order:7}
  .crn-cols .crn-o7{margin-top:0}
  .crn-panel{background:var(--card);border:4px solid #111;border-radius:18px;
    box-shadow:8px 8px 0 #111;padding:var(--s4) var(--s3)}
  .crn-h2{font-size:20px;font-weight:800;line-height:1.25;margin:0}
  .crn-lead{font-size:15px;color:var(--muted);margin:4px 0 var(--s3)}
  .crn-h3{font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:var(--muted);margin:var(--s4) 0 var(--s2)}
  .crn-stack{display:flex;flex-direction:column;gap:var(--s4);margin-top:var(--s4)}

  /* Kamera */
  .crn-cam-frame{position:relative;border-radius:12px;overflow:hidden;background:#1f2937;border:var(--bd);
    aspect-ratio:4/3;margin-top:var(--s3)}
  .crn-cam-frame img{display:block;width:100%;height:100%;object-fit:cover}
  .crn-cam-badge{position:absolute;top:var(--s2);left:var(--s2);display:inline-flex;align-items:center;gap:6px;
    font-size:12px;font-weight:800;letter-spacing:.06em;color:#fff;background:rgba(17,24,39,.72);
    border-radius:999px;padding:4px 10px}
  .crn-cam-badge i{width:8px;height:8px;border-radius:50%;background:#ef4444;display:block;
    animation:crnLive 2s ease-in-out infinite}
  @keyframes crnLive{0%,100%{opacity:1}50%{opacity:.35}}
  .crn-cam-place{position:absolute;left:var(--s2);bottom:var(--s2);font-size:12px;font-weight:800;
    letter-spacing:.06em;color:#fff;background:rgba(17,24,39,.72);border-radius:8px;padding:4px 10px}
  .crn-cam-frame.is-offline .crn-cam-badge,.crn-cam-frame.is-offline .crn-cam-place,
  .crn-cam-frame.is-loading .crn-cam-badge{display:none}
  .crn-cam-loading{position:absolute;inset:0;margin:0;display:flex;align-items:center;justify-content:center;
    padding:var(--s3);text-align:center;color:#d1d5db;font-size:14px;font-weight:600;
    background:linear-gradient(100deg,#1f2937 30%,#2b3544 50%,#1f2937 70%);background-size:200% 100%;
    animation:crnShimmer 1.4s linear infinite}
  .crn-cam-fallback{position:absolute;inset:0;margin:0;display:flex;flex-direction:column;gap:var(--s1);
    align-items:center;justify-content:center;padding:var(--s3);text-align:center;color:#fff;font-size:15px;font-weight:600}
  .crn-cam-fallback a{color:#93c5fd}
  .crn-cam-time{font-size:14px;font-weight:700;color:var(--ink);margin:var(--s2) 0 0}
  .crn-cam-meta{font-size:13px;color:var(--muted);margin:var(--s2) 0 0}

  /* Poročanje */
  .crn-zones{display:grid;grid-template-columns:1fr 1fr;gap:var(--s1)}
  .crn-zbtn{--zc:#16a34a;--zbg:#dcfce7;font:inherit;font-size:14px;font-weight:800;letter-spacing:.03em;
    text-transform:uppercase;cursor:pointer;min-height:52px;display:flex;align-items:center;gap:var(--s1);
    padding:var(--s1) var(--s2);background:var(--card);color:var(--ink);border:var(--bd);
    border-left:8px solid var(--zc);border-radius:12px;box-shadow:3px 3px 0 #111;text-align:left;
    transition:background-color .15s}
  .crn-zbtn:hover{background:#faf9f6}
  .crn-zbtn.sel{background:var(--zbg);border-left-color:var(--zc)}
  .crn-zbtn:disabled{cursor:default;opacity:.7}
  .crn-zbtn .crn-zicon{width:24px;height:24px;flex:0 0 auto}
  .crn-form{margin-top:var(--s3);display:flex;flex-direction:column;gap:var(--s1)}
  .crn-input{width:100%;box-sizing:border-box;border:var(--bd);border-radius:12px;background:#fff;
    padding:var(--s2);font:inherit;font-size:16px;color:var(--ink)}
  textarea.crn-input{resize:vertical;min-height:72px}
  .crn-status-msg{font-size:15px;font-weight:600;color:var(--ink2);margin:var(--s2) 0 0}
  .crn-status-msg.ok{color:#166534}
  .crn-badge{margin-top:var(--s3);background:#fef08a;border:var(--bd);box-shadow:var(--sh);border-radius:12px;
    padding:var(--s3);text-align:center}
  .crn-badge-title{font-weight:800;font-size:17px;margin:0 0 4px}
  .crn-badge-desc{font-size:14px;color:var(--ink2);margin:0}
  .crn-badge-count{font-size:13px;color:var(--muted);margin:var(--s1) 0 0}

  /* Zadnja poročila */
  .crn-feed{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
  .crn-feed-item{display:flex;gap:var(--s2);align-items:flex-start;padding:var(--s2) 0;
    border-top:1px solid #efece5;margin:0}
  .crn-feed-item:first-child{border-top:0;padding-top:0}
  .crn-dot{width:12px;height:12px;border-radius:50%;flex:0 0 auto;margin-top:6px}
  .crn-feed-zone{font-weight:700}
  .crn-feed-time{font-size:13px;color:var(--muted);margin-left:6px}
  .crn-feed-note{font-size:14px;color:var(--ink2);margin:2px 0 0;overflow-wrap:anywhere}
  .crn-feed-empty{font-size:14px;color:var(--muted);margin:0}
  .crn-week{font-size:13px;color:var(--muted);margin:var(--s2) 0 0}
  .crn-skel{display:block;height:14px;border-radius:6px;margin:6px 0;
    background:linear-gradient(100deg,#eeeae1 30%,#f7f5f0 50%,#eeeae1 70%);background-size:200% 100%;
    animation:crnShimmer 1.4s linear infinite}
  @keyframes crnShimmer{from{background-position:200% 0}to{background-position:-200% 0}}

  /* Sekundarno: glasovanje, nasvet, lestvica, poštenost */
  .crn-vote-row{display:flex;flex-wrap:wrap;align-items:center;gap:var(--s1) var(--s2)}
  .crn-vote-q{font-size:15px;font-weight:700;margin:0;flex:1 1 220px}
  .crn-vote-btns{display:flex;gap:var(--s1)}
  .crn-vote-btns .crn-btn{padding:0 var(--s3);font-size:14px}
  .crn-vote-bar{height:14px;border:2px solid #111;border-radius:999px;overflow:hidden;background:#fecaca;margin-top:var(--s2)}
  .crn-vote-bar span{display:block;height:100%;width:50%;background:#16a34a;transition:width .5s ease}
  .crn-vote-count{font-size:13px;color:var(--muted);margin:var(--s1) 0 0}

  .crn-tip{position:relative;background:#fef08a;border:4px solid #111;border-radius:18px;
    box-shadow:8px 8px 0 #111;padding:var(--s4) var(--s3);transform:rotate(-.3deg)}
  .crn-tip-h{font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:#111;
    margin:0 0 var(--s1)}
  .crn-tip .crn-quote p{font-size:17px;font-weight:700;line-height:1.45;margin:0}
  .crn-tip .crn-quote.crn-quote-rare p{color:#854d0e}
  .crn-quote-pop{animation:crnQuoteReroll .3s ease}
  @keyframes crnQuoteReroll{from{opacity:.3}to{opacity:1}}
  .crn-icon{width:64px;height:auto;flex:0 0 auto;cursor:pointer}
  .crn-icon:hover{animation:crnWobble .5s ease}
  @keyframes crnWobble{0%,100%{transform:rotate(0deg)}25%{transform:rotate(-4deg)}75%{transform:rotate(4deg)}}
  .crn-mascot-msg{display:inline-block;font-size:14px;font-weight:700;color:#111;background:#fef08a;
    border:2px solid #111;border-radius:10px;padding:4px var(--s2);margin:var(--s2) 0 0}
  .crn-visits{font-size:13px;color:#374151;margin:var(--s1) 0 0}
  .crn-actions{display:flex;flex-wrap:wrap;gap:var(--s1);margin-top:var(--s3)}
  .crn-actions .crn-btn{font-size:14px;padding:0 var(--s3)}
  .crn-share-status{font-size:13px;color:var(--muted);margin:var(--s1) 0 0}

  .crn-board-list{display:flex;flex-direction:column}
  .crn-board-row{display:flex;justify-content:space-between;align-items:center;gap:var(--s2);
    font-size:14px;padding:var(--s1) 0;border-top:1px solid #efece5;margin:0}
  .crn-board-row:first-child{border-top:0}
  .crn-board-rank{font-weight:800;width:1.6rem;flex:0 0 auto;color:var(--muted)}
  .crn-board-name{flex:1;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .crn-board-badge{color:var(--muted);font-size:13px;flex:0 0 auto;text-align:right}
  .crn-accuracy-big{font-size:32px;font-weight:800;margin:var(--s1) 0 0}
  .crn-accuracy-note{font-size:14px;color:var(--muted);margin:4px 0 0}

  /* Accordioni (razlaga indeksa, značka) */
  .crn-acc{background:var(--card);border:var(--bd);border-radius:14px;box-shadow:var(--sh)}
  .crn-acc summary{cursor:pointer;list-style:none;min-height:48px;display:flex;align-items:center;
    gap:var(--s1);padding:0 var(--s3);font-weight:700;font-size:15px}
  .crn-acc summary::-webkit-details-marker{display:none}
  .crn-acc summary::after{content:"+";margin-left:auto;font-size:20px;font-weight:600;color:var(--muted)}
  .crn-acc[open] summary::after{content:"–"}
  .crn-acc-body{padding:0 var(--s3) var(--s3);font-size:15px;color:var(--ink2)}
  .crn-acc-body p{margin:0 0 var(--s2)}
  .crn-embed-preview{display:block;margin:0 0 var(--s2)}
  .crn-embed-row{display:flex;gap:var(--s1);align-items:center;flex-wrap:wrap}
  .crn-embed-code{flex:1 1 200px;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:8px;
    padding:var(--s1) var(--s2);font-family:ui-monospace,Consolas,monospace;font-size:12px;
    overflow-x:auto;white-space:nowrap;color:var(--ink)}

  .crn-official{font-size:14px;color:var(--ink2);background:#fdf6e3;border-top:2px dotted #111;
    padding:var(--s3) var(--s1) 0;margin-top:var(--s5)}
  .crn-official p{margin:0 0 var(--s1)}
  .crn-back{margin-top:var(--s3)}

  /* ── Tablica / namizje ──────────────────────────────────────── */
  @media (min-width:600px){
    .crn-title{font-size:52px}
    .crn-icon{width:140px}
    .crn-gauge{max-width:560px}
    .crn-status-icon .crn-zicon{width:48px;height:48px}
    .crn-status{padding:var(--s5) var(--s4)}
    .crn-status-title{font-size:48px}
    .crn-status-icon .crn-zicon{width:64px;height:64px}
    .crn-big{font-size:36px}
    .crn-panel{padding:var(--s4)}
    .crn-zones{grid-template-columns:repeat(4,1fr)}
  }
  @media (min-width:1024px){
    .crn{padding-top:var(--s4)}
    .crn-title{font-size:68px}
    .crn-head{flex-direction:row;justify-content:center;gap:var(--s4)}
    .crn-head-txt{text-align:left}
    .crn-icon{width:170px}
    /* Namizje: celotna širina (1140 px) je izkoriščena -- v heroju merilnik
       levo, meritve + gumb desno; spodaj dva stolpca, vsak svoj sklad, da
       se ne poravnavata po vrsticah (brez lukenj ob krajši kartici). */
    .crn-hero{max-width:none}
    .crn-hero-main{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:var(--s4);
      align-items:stretch;text-align:left}
    .crn-hero-main .crn-status{text-align:center;display:flex;flex-direction:column;justify-content:center}
    .crn-hero-main .crn-status-index{align-self:center}
    .crn-hero-side{display:flex;flex-direction:column}
    .crn-hero-side .crn-cards{grid-template-columns:1fr;margin-top:0;flex:1}
    .crn-hero-side .crn-card{display:flex;flex-direction:column;justify-content:center;padding-right:136px}
    .crn-hero-side .crn-card-art{display:block;position:absolute;right:var(--s4);top:50%;
      width:96px;height:96px;transform:translateY(-50%) rotate(4deg)}
    .crn-hero-side .crn-card-art svg{width:100%;height:100%;display:block}
    .crn-hero-side .crn-btn-primary{max-width:none}
    .crn-cols{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);align-items:start}
    .crn-col{display:flex;flex-direction:column;gap:var(--s4)}
    .crn-col .crn-zones{grid-template-columns:1fr 1fr}
  }
  @media (prefers-reduced-motion:reduce){
    .crn-cam-badge i,.crn-cam-loading,.crn-skel,.crn-quote-pop,.crn-icon:hover{animation:none}
    .crn-needle{animation:none;transition:none;transform:rotate(var(--rot))}
    .crn-status,.crn-btn,.crn-vote-bar span{transition:none}
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

  // Relativni čas ("pred 8 min") -- rabita ga "Posodobljeno" v statusni
  // kartici in seznam zadnjih poročil. Absolutni čas ostane v title.
  // Na vrhu IIFE (ne v bloku poročanja), ker je v "use strict" deklaracija
  // funkcije znotraj if-bloka vidna samo v tem bloku.
  function relCas(iso){
    var s = (Date.now() - Date.parse(iso)) / 1000;
    if (isNaN(s)) return "";
    if (s < 60) return "pravkar";
    var m = Math.round(s / 60);
    if (m < 60) return "pred " + m + " min";
    var h = Math.round(m / 60);
    if (h < 24) return "pred " + h + " h";
    var d = Math.round(h / 24);
    return d === 1 ? "včeraj" : d === 2 ? "pred 2 dnevoma" : "pred " + d + " dnevi";
  }

  // "Posodobljeno pred X min" tik pod statusom -- uporabnik mora takoj
  // vedeti, ali je ocena sveža. data-ts je čas izračuna (strežnik ob
  // generiranju, JS ob uspešnem živem preračunu); besedilo se vsako minuto
  // samo preračuna, brez omrežnega klica.
  var updEl = document.getElementById("crn-updated");
  function izpisiPosodobljeno(){
    if (!updEl || !updEl.dataset.ts) return;
    var rc = relCas(updEl.dataset.ts);
    if (!rc) return;
    updEl.textContent = "Posodobljeno " + rc + " · ocena iz vremenskega modela";
    updEl.title = new Date(updEl.dataset.ts).toLocaleString("sl");
  }
  izpisiPosodobljeno();
  setInterval(izpisiPosodobljeno, 60 * 1000);

  // Živa kamera s prelaza (glej opombo na vrhu generate_crnivec_page.py) --
  // neposreden hotlink, brez našega workerja. Prvi prikaz je iz statičnega
  // <img src> (deluje tudi brez JS), JS doda samo periodično osvežitev in
  // padavinsko varovalko, če DRSI kdaj spremeni pot/zavrne hotlink.
  var camImg = document.getElementById("crn-cam-img");
  var camFallback = document.getElementById("crn-cam-fallback");
  var camLoading = document.getElementById("crn-cam-loading");
  if (camImg && CAM_URL) {
    // Nalaganje ni nujno takojšnje (DRSI strežnik, ne naš CDN) -- brez tega bi
    // obiskovalec na počasni povezavi videl samo prazno črno škatlo in
    // sklepal, da je kamera pokvarjena. Šaljiva vrstica namesto generičnega
    // "nalagam …", ista logika izbire kot pick()/variant_index v
    // generate_story_card.py, samo tu (ne v Pythonu), ker mora biti vsak
    // obisk lahko drugačen, ne enkrat na dan.
    if (camLoading) {
      var CAM_LOADING_LINES = [
        "Nalagam kamero (počasneje kot teta bere komentarje) …",
        "Kamera se prav tako sprašuje, kako je …",
        "Nalagam sliko s prelaza — saj veš, kako je z internetom tam gor …"
      ];
      camLoading.textContent = CAM_LOADING_LINES[Math.floor(Math.random() * CAM_LOADING_LINES.length)];
    }
    // Samozdravilno: vsak neuspeh pokaže nadomestno sporočilo, vsak naslednji
    // uspešen prenos ga spet skrije -- brez trajne zastavice, ker je prehoden
    // izpad (DRSI stran ne odgovori enkrat) povsem verjeten in se sam popravi.
    // Sporočilo "nalagam" izgine po PRVEM izidu (uspeh ali neuspeh) in se ne
    // vrača ob periodičnih osvežitvah spodaj -- takrat stara slika ostane
    // vidna, dokler nova ne prispe, prekrivanje ni potrebno.
    // Oznaka "V ŽIVO" (.crn-cam-badge) se pokaže šele ob uspešni sliki --
    // na pokvarjeni ali še nenaloženi sliki bi bila laž (is-loading/is-offline
    // na okvirju, glej CSS).
    var camFrame = camImg.parentNode;
    function camIzid(ok){
      camImg.hidden = !ok;
      if (camFallback) camFallback.hidden = ok;
      if (camLoading) camLoading.hidden = true;
      if (camFrame && camFrame.classList) {
        camFrame.classList.remove("is-loading");
        camFrame.classList.toggle("is-offline", !ok);
      }
      // Svežina slike: DRSI časa posnetka ne izpostavi (brez CORS/glav), zato
      // pošteno "naložena", ne "posneta".
      var camTime = document.getElementById("crn-cam-time");
      if (camTime) {
        camTime.hidden = !ok;
        if (ok) camTime.textContent = "Slika naložena ob " + uraSl(new Date());
      }
    }
    camImg.addEventListener("error", function(){ camIzid(false); });
    camImg.addEventListener("load", function(){ camIzid(true); });
    // Ta skript je na dnu strani -- če je bila slika hitrejša (predpomnjena
    // ali takojšnja napaka), sta se load/error dogodka morda že zgodila,
    // preden je zgornji addEventListener sploh tekel, in ju ta skript ne bi
    // nikoli ujel ("nalagam …" bi ostalo obviselo za vedno). complete +
    // naturalWidth povesta dejansko stanje neposredno, brez čakanja na dogodek.
    if (camImg.complete) camIzid(camImg.naturalWidth > 0);
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
        visitsEl.textContent = "P. S. To je tvoj " + obiski + ". obisk te strani. Očitno tudi ti raje vprašaš, kot pogledaš sam.";
        visitsEl.hidden = false;
      }
    } catch (_) {}
  }

  // Gorska maskota je klikljiv easter egg -- čist hec, ne nosi nobene
  // vsebine (glej role="button"/aria-label v mountain_icon_svg()). Vsak
  // klik pokaže novo (drugačno od prejšnje) šaljivo vrstico, ki po nekaj
  // sekundah sama izgine -- isti reroll-vzorec kot crn-reroll spodaj, samo
  // brez strežniško izbranega privzetka (maskota nima "dnevnega" stanja).
  var mascot = document.getElementById("crn-mascot");
  var mascotMsg = document.getElementById("crn-mascot-msg");
  if (mascot && mascotMsg) {
    var MASCOT_LINES = [
      "Ne, tudi jaz ne vem.",
      "Vprašaj spodaj, jaz sem samo slika.",
      "Prenehaj me risati na zemljevid.",
      "Če bi vedela, bi ti povedala prva.",
      "Jaz sem gora. Gore ne govorijo. Tehnično.",
      "Klikni še enkrat, morda pa vseeno vem."
    ];
    var mascotTimer = null;
    var pokaziMaskotnoSporocilo = function(){
      var cur = mascotMsg.textContent;
      var next = cur;
      var tries = 0;
      while (next === cur && tries < 10) {
        next = MASCOT_LINES[Math.floor(Math.random() * MASCOT_LINES.length)];
        tries++;
      }
      mascotMsg.textContent = next;
      mascotMsg.hidden = false;
      if (mascotTimer) clearTimeout(mascotTimer);
      mascotTimer = setTimeout(function(){ mascotMsg.hidden = true; }, 4000);
    };
    mascot.addEventListener("click", pokaziMaskotnoSporocilo);
    // role="button" na SVG-ju ne da tipkovničnega vedenja zastonj -- Enter in
    // presledek morata sprožiti klik ročno, isto kot bi ga privzeto naredil
    // pravi <button>.
    mascot.addEventListener("keydown", function(e){
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pokaziMaskotnoSporocilo(); }
    });
  }

  // "Vstavi značko" -- kopiraj gumb za <img> kodo (glej crn-embed zgoraj in
  // GET /crnivec/znacka.svg v worker.js). Brez JS je koda še vedno vidna in
  // ročno izbirljiva (navadno besedilo v <code>), gumb je samo bližnjica.
  var embedCopyBtn = document.getElementById("crn-embed-copy");
  var embedCodeEl = document.getElementById("crn-embed-code");
  var embedStatusEl = document.getElementById("crn-embed-status");
  if (embedCopyBtn && embedCodeEl) {
    embedCopyBtn.addEventListener("click", function(){
      var besedilo = embedCodeEl.textContent;
      function povejStatus(msg){
        if (!embedStatusEl) return;
        embedStatusEl.hidden = false;
        embedStatusEl.textContent = msg;
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(besedilo).then(function(){ povejStatus("Kopirano!"); })
          .catch(function(){ povejStatus("Kopiranje ni uspelo — označi kodo zgoraj in kopiraj ročno."); });
      } else {
        povejStatus("Označi kodo zgoraj in kopiraj ročno.");
      }
    });
  }

  // "Poslušaj namesto beri" -- prebere TRENUTNO stanje neposredno iz DOM-a
  // (ne spečenih vrednosti), zato je pravilen tudi po živi posodobitvi
  // spodaj ali po rerollu citata: bere ob kliku, ne ob nalaganju strani.
  // window.speechSynthesis je vgrajen v brskalnik -- brez strežnika, brez
  // zvočne datoteke za gostiti.
  var listenBtn = document.getElementById("crn-listen");
  if (listenBtn && window.speechSynthesis && window.SpeechSynthesisUtterance) {
    listenBtn.hidden = false;
    listenBtn.addEventListener("click", function(){
      if (window.speechSynthesis.speaking) { window.speechSynthesis.cancel(); return; }
      var labelEl = document.getElementById("crn-status-title");
      var descEl = document.getElementById("crn-status-desc");
      var tempEl = document.getElementById("crn-temp-val");
      var quoteEl = document.querySelector(".crn-quote p");
      var label = labelEl ? labelEl.textContent.toLowerCase() : "";
      var desc = descEl ? descEl.textContent : "";
      var temp = tempEl ? tempEl.textContent.replace("°C", "stopinj") : "";
      var quote = quoteEl ? quoteEl.textContent : "";
      var besedilo = "Kako je čez Črnivec? " + label + ". " + desc +
        (temp ? (" Na prelazu je " + temp + ".") : "") +
        (quote ? (" Meteorec nasvet: " + quote) : "");
      var u = new SpeechSynthesisUtterance(besedilo);
      u.lang = "sl-SI";
      u.rate = 0.95;
      window.speechSynthesis.speak(u);
    });
  }

  // Opozorilo o strelah blizu prelaza -- bere isti trajni zapis kot klientska
  // kartica "Strele v bližini" na naslovni strani (LightningLogger v
  // worker.js), samo da tu primerja razdaljo do PRELAZA (46.25, 14.6833 --
  // sl.wikipedia.org/wiki/Črnivec_(prelaz)), ne do postaje. _crnDist je
  // namerna podvojitev _ltgDist (worker.js/app.js) -- isto načelo kot
  // _smerBesedilo/_ltgDecode drugod v repozitoriju.
  function _crnDist(lat1, lon1, lat2, lon2){
    var R = 6371, dLat = (lat2 - lat1) * Math.PI / 180, dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }
  var strikeBanner = document.getElementById("crn-strike-banner");
  if (strikeBanner && window.fetch) {
    var CRN_PASS_LAT = 46.25, CRN_PASS_LON = 14.6833, CRN_STRIKE_RADIUS_KM = 15;
    var preveriStrele = function(){
      fetch(API + "/strele-zgodovina.json?ur=1").then(function(r){ return r.json(); })
        .then(function(d){
          var strikes = (d && d.strikes) || [];
          var najblizja = null;
          strikes.forEach(function(s){
            var km = _crnDist(CRN_PASS_LAT, CRN_PASS_LON, s.lat, s.lon);
            if (km <= CRN_STRIKE_RADIUS_KM && (najblizja === null || km < najblizja.km)) {
              najblizja = { km: km, ts: s.ts };
            }
          });
          if (najblizja) {
            var ura = new Date(najblizja.ts).toLocaleTimeString("sl", { hour: "2-digit", minute: "2-digit" });
            strikeBanner.textContent = "⚡ V zadnji uri je treščilo blizu prelaza (" +
              najblizja.km.toFixed(1).replace(".", ",") + " km stran, ob " + ura + ").";
            strikeBanner.hidden = false;
          } else {
            strikeBanner.hidden = true;
          }
        }).catch(function(){ /* tiho -- ni to primarna vsebina strani */ });
    };
    preveriStrele();
    setInterval(preveriStrele, 5 * 60 * 1000);
  }

  // Merilnik je zdaj ŽIV: namesto da samo prikaže enkrat-dnevni strežniški
  // izračun (winter_engine.py, ki lahko -- kot ostali GitHub cron na strani
  // -- zamuja za ure), klientski JS ob vsakem obisku pokliče Open-Meteo
  // neposredno in temperaturo/sneg za prelaz preračuna sam. NAMERNA
  // PODVOJITEV formule iz winter_engine.py (compute_pass_weather/
  // snow_fraction) -- worker/klient ne more uvoziti Python kode, isto
  // načelo kot lokalni FWI na /meteogasilec/intervencija/ (gasilec.js) ali
  // _smerBesedilo/_ltgDecode drugod v repozitoriju. Če spremeniš
  // LAPSE_RATE_C_PER_100M/SNOW_* konstante ali formulo v winter_engine.py,
  // spremeni tudi tu.
  var LIVE_LAPSE_RATE = 0.65, LIVE_STATION_ELEV = 366, LIVE_PASS_ELEV = 902;
  var LIVE_SNOW_OFFSET = 250, LIVE_SNOW_HALFWIDTH = 100;
  var ZONE_DATA = __ZONE_DATA_JSON__;

  function numSlLive(x, d){
    if (x == null || isNaN(x)) return "–";
    return x.toFixed(d == null ? 1 : d).replace(".", ",");
  }
  function snowFractionLive(elevM, flM){
    if (flM == null) return 0;
    var eff = flM - LIVE_SNOW_OFFSET;
    var lo = eff - LIVE_SNOW_HALFWIDTH, hi = eff + LIVE_SNOW_HALFWIDTH;
    if (elevM <= lo) return 0;
    if (elevM >= hi) return 1;
    return (elevM - lo) / (hi - lo);
  }
  function pickZoneLive(tempC, snowCm){
    if (snowCm >= 2) return ZONE_DATA[2];        // verige
    if (tempC != null && tempC <= 0) return ZONE_DATA[3];  // spolzko
    if (tempC != null && tempC > 5) return ZONE_DATA[0];   // sonce
    return ZONE_DATA[1];                          // nekaj vmes
  }

  function uraSl(d){
    return d.toLocaleTimeString("sl", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Ljubljana" });
  }

  // Ob zamujenem cronu (glej opombo zgoraj) ali neuspelem živem klicu ostane
  // strežniško spečena vrednost prikazana -- ne skrijemo je, samo označimo,
  // isti prag kot MeteoGasilec/Agrometeo (🟡 26-50h, 🔴 nad 50h).
  function pokaziZastarelostOpozorila(){
    var freshEl = document.getElementById("crn-fresh");
    if (!freshEl || !freshEl.dataset.generated) return;
    var genThen = new Date(freshEl.dataset.generated).getTime();
    if (isNaN(genThen)) return;
    var ageH = (Date.now() - genThen) / 3600000;
    if (ageH < 26) return;
    var rdece = ageH >= 50;
    var gd = new Date(genThen);
    var datum = gd.toLocaleDateString("sl", { day: "2-digit", month: "2-digit", year: "numeric" });
    freshEl.textContent = (rdece ? "🔴 " : "🟡 ") + "Prikazujem zadnji uspešno izračunan podatek — " + datum + " ob " + uraSl(gd) + ".";
    freshEl.style.color = rdece ? "#b91c1c" : "#92400e";
    freshEl.hidden = false;
  }

  function primeniZivoStanje(tempC, snowCm, precipMm){
    var zone = pickZoneLive(tempC, snowCm);
    var tempTxt = (tempC == null ? "–" : numSlLive(tempC, 1)) + " °C";
    var snowTxt = numSlLive(snowCm, 1) + " cm";

    var tEl = document.getElementById("crn-temp-val");
    var sEl = document.getElementById("crn-snow-new");
    var pEl = document.getElementById("crn-precip");
    if (tEl && tempC != null) { tEl.textContent = tempTxt; tEl.className = "crn-big"; }
    if (sEl) sEl.textContent = "+" + snowTxt;
    if (pEl && precipMm != null) pEl.textContent = numSlLive(precipMm, 1) + " mm";

    var card = document.getElementById("crn-status");
    var title = document.getElementById("crn-status-title");
    var desc = document.getElementById("crn-status-desc");
    var idx = document.getElementById("crn-status-index");
    var iconWrap = document.getElementById("crn-status-icon");
    if (card) {
      card.setAttribute("data-zone", zone.id);
      card.style.setProperty("--zc", zone.color);
      card.style.setProperty("--zbg", zone.bg);
      card.style.setProperty("--zink", zone.ink);
    }
    if (title) title.textContent = zone.status;
    if (desc) desc.textContent = zone.statusDesc;
    if (idx) idx.textContent = "Meteorec indeks: " + zone.label;
    if (iconWrap) iconWrap.innerHTML = zone.icon;

    // Kazalec: zasuk prek CSS (isti mehanizem kot prvi izris), animacija
    // crnNeedleSettle pa se izklopi. NE brisati style in pisati SVG
    // transform atributa: animacija s fill-mode forwards bi ostala aktivna,
    // njen CSS transform ima prednost pred atributom, --rot pa bi bil
    // pobrisan -- kazalec je tako obstal naravnost gor (med TAK-TAK in
    // VZEMI VERIGE), čeprav je status kazal "Cesta je suha" (24. 9. 2026).
    // transform-origin ostane v style iz strežniškega izrisa.
    var needle = document.querySelector(".crn-status .crn-needle");
    var gaugeSvg = document.querySelector(".crn-status .crn-gauge");
    if (needle) {
      var rotLive = (90 - zone.mid).toFixed(1) + "deg";
      needle.style.setProperty("--rot", rotLive);
      needle.style.animation = "none";
      needle.style.transform = "rotate(" + rotLive + ")";
    }
    if (gaugeSvg) gaugeSvg.setAttribute("aria-label", "Črnivski indeks: " + zone.label);

    // "Deli kot sliko" naj deli TRENUTNO (živo) stanje, ne tisto, spečeno ob
    // generiranju strani. Kazalec v statični SVG kopiji se zasuka
    // neposredno -- share.gauge ima en sam rotate(), tisti na kazalcu.
    if (share) {
      share.verdict = zone.label;
      share.color = zone.color;
      share.temp = tempTxt;
      share.snow = snowTxt + " snega v 24 h";
      share.gauge = share.gauge.replace(/rotate\\([^)]*\\)/, "rotate(" + (90 - zone.mid).toFixed(1) + " 190 175)")
        .replace(/aria-label="[^"]*"/, 'aria-label="Črnivski indeks: ' + zone.label + '"');
      share.icon = zone.icon.replace('viewBox="0 0 60 60"',
        'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60" width="60" height="60"');
    }

    if (updEl) { updEl.dataset.ts = new Date().toISOString(); izpisiPosodobljeno(); }
    var freshEl = document.getElementById("crn-fresh");
    if (freshEl) freshEl.hidden = true;
  }

  function osveziZivoVreme(){
    if (!window.fetch) { pokaziZastarelostOpozorila(); return; }
    var url = "https://api.open-meteo.com/v1/forecast?latitude=46.325779&longitude=14.921137"
      + "&hourly=temperature_2m,precipitation,freezing_level_height&timezone=Europe%2FLjubljana&forecast_days=2";
    fetch(url).then(function(r){ return r.json(); }).then(function(d){
      var times = (d.hourly && d.hourly.time) || [];
      var temps = (d.hourly && d.hourly.temperature_2m) || [];
      if (!times.length || !temps.length) { pokaziZastarelostOpozorila(); return; }
      var t0 = Date.parse(times[0] + ":00Z");
      var nowShifted = Date.now() + (d.utc_offset_seconds || 0) * 1000;
      var idx = Math.max(0, Math.min(Math.round((nowShifted - t0) / 3600000), times.length - 1));
      var tNow = temps[idx];
      if (tNow == null) { pokaziZastarelostOpozorila(); return; }
      var tempC = tNow - LIVE_LAPSE_RATE * (LIVE_PASS_ELEV - LIVE_STATION_ELEV) / 100;

      var precip = d.hourly.precipitation || [];
      var fl = d.hourly.freezing_level_height || [];
      var snowCm = 0, precipMm = 0;
      for (var i = idx; i < Math.min(idx + 24, times.length); i++) {
        snowCm += (precip[i] || 0) * snowFractionLive(LIVE_PASS_ELEV, fl[i]);
        precipMm += (precip[i] || 0);
      }
      primeniZivoStanje(tempC, Math.round(snowCm * 10) / 10, Math.round(precipMm * 10) / 10);
    }).catch(function(){ pokaziZastarelostOpozorila(); });
  }
  osveziZivoVreme();
  setInterval(osveziZivoVreme, 5 * 60 * 1000);

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

    // Slovenska dvojina/množina gre po zadnjih dveh števkah (101 = ednina).
    function glasovalcev(n){
      var m = n % 100;
      if (m === 1) return n + " uporabnik je danes glasoval";
      if (m === 2) return n + " uporabnika sta danes glasovala";
      if (m === 3 || m === 4) return n + " uporabniki so danes glasovali";
      return n + " uporabnikov je danes glasovalo";
    }

    function showVoteResult(counts){
      var gre = (counts && counts.gre) || 0, ne = (counts && counts.ne) || 0;
      var total = gre + ne;
      var pct = total ? Math.round((gre / total) * 100) : 50;
      if (voteBar) voteBar.style.width = pct + "%";
      if (voteCount) {
        voteCount.textContent = total ?
          (pct + " % pravi, da gre · " + glasovalcev(total)) :
          "Danes še nihče ni glasoval.";
      }
      if (voteBar && voteBar.parentNode) voteBar.parentNode.hidden = !total;
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
    var repZones = Array.prototype.slice.call(repBox.querySelectorAll(".crn-zbtn"));
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
    var ZONE_LABELS = { sonce: "Suho", nekaj: "Nekaj je", verige: "Verige", spolzko: "Spolzko" };
    var ZONE_COLORS = {};
    ZONE_DATA.forEach(function(z){ ZONE_COLORS[z.id] = z.color; });

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

    function setStatusRep(msg, ok){
      if (!repStatus) return;
      repStatus.hidden = !msg;
      repStatus.textContent = msg || "";
      repStatus.classList.toggle("ok", !!ok);
    }

    function renderFeed(porocila){
      if (!repFeed) return;
      if (!porocila || !porocila.length) {
        repFeed.innerHTML = '<li class="crn-feed-empty">Ta teden še nihče ni poročal. Bodi prvi zgoraj.</li>';
        return;
      }
      repFeed.innerHTML = "";
      porocila.slice(0, 6).forEach(function(p){
        var el = document.createElement("li");
        el.className = "crn-feed-item";
        var dot = document.createElement("span");
        dot.className = "crn-dot";
        dot.style.background = ZONE_COLORS[p.zona] || "#9ca3af";
        var txt = document.createElement("div");
        var b = document.createElement("span");
        b.className = "crn-feed-zone";
        b.textContent = ZONE_LABELS[p.zona] || p.zona;
        var t = document.createElement("span");
        t.className = "crn-feed-time";
        t.textContent = relCas(p.ts);
        t.title = new Date(p.ts).toLocaleString("sl");
        txt.appendChild(b);
        txt.appendChild(t);
        // textContent, ne innerHTML -- opomba je prosto uporabniško besedilo
        // (isto pravilo kot pri gobarskih opažanjih).
        if (p.opomba) {
          var n = document.createElement("p");
          n.className = "crn-feed-note";
          n.textContent = p.opomba;
          txt.appendChild(n);
        }
        el.appendChild(dot);
        el.appendChild(txt);
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
      repWeek.textContent = "Ta teden: " + porocila.length +
        (porocila.length === 1 ? " poročilo" : " poročil") +
        (najpogostejsa ? " · največkrat: " + (ZONE_LABELS[najpogostejsa] || najpogostejsa).toLowerCase() : "");
      repWeek.hidden = false;
    }

    function loadFeed(){
      fetch(API + "/crnivec/porocila?dni=7").then(function(r){ return r.json(); })
        .then(function(d){
          renderFeed(d && d.porocila);
          renderWeekStats(d && d.porocila);
        })
        .catch(function(){
          // Napaka enega vira ne sme pustiti večnega skeletona.
          if (repFeed && !repFeed.querySelector(".crn-feed-zone")) {
            repFeed.innerHTML = '<li class="crn-feed-empty">Poročil trenutno ni mogoče naložiti.</li>';
          }
        });
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
      btn.className = "crn-btn";
      btn.textContent = "Deli značko";
      btn.style.marginTop = "12px";
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
            setStatusRep("Hvala! Tvoje poročilo je dodano.", true);
            if (repBadge && res.data.znacka) {
              repBadge.hidden = false;
              var t = document.createElement("p");
              t.className = "crn-badge-title";
              t.textContent = res.data.znacka.naziv;
              var d2 = document.createElement("p");
              d2.className = "crn-badge-desc";
              d2.textContent = res.data.znacka.opis;
              var c = document.createElement("p");
              c.className = "crn-badge-count";
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
    fetch(API + "/crnivec/lestvica").then(function(r){ return r.json(); })
      .then(function(d){
        var lestvica = (d && d.lestvica) || [];
        // Prazna lestvica ne zasede prostora (P3 vsebina, glej opombo pri CSS).
        if (!lestvica.length) { boardBox.hidden = true; return; }
        boardBox.hidden = false;
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
    (mock) prometnim znakom "pozor" ob vznožju. Poenostavljeno za berljivost
    pri ~90 px (prvotna različica s podrobnim avtomobilčkom se je pri tej
    velikosti izgubila — glej git zgodovino). Isti stil kot
    gauge_svg/starburst_svg zgoraj (debel črn obris, ploskovite barve, brez
    naloženih slik).

    Klikljiva (glej #crn-mascot v SHARE_JS_TEMPLATE) -- zato role="button" +
    aria-label namesto aria-hidden: čeprav gre za čisti hec (glej
    crn-mascot-msg), je zdaj interaktivna, ne le okrasje."""
    return '''<svg viewBox="0 0 200 180" class="crn-icon" id="crn-mascot" role="button"
       tabindex="0" aria-label="Gorska maskota — klikni za presenečenje">
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
    # zima-forecast.yml teče enkrat na dan in lahko (kot ostali GitHub cron
    # na tej strani) zamuja za ure — brez tega bi stran tiho kazala včerajšnje
    # stanje kot današnje. Isto načelo kot MeteoGasilec/Agrometeo
    # (renderFreshness()/data-generated v generate_agrometeo_page.py): ne
    # skrivaj stare vrednosti, samo jo označi.
    generated_at = data.get("generated_at") or ""

    # Arhivira včerajšnji glasovalni izid (glej opombo pri funkciji) in iz
    # nabranega ("koliko dni je večina rekla, da je pošteno") sestavi
    # razdelek — samostojen podatek, ne odvisen od živega JS spodaj.
    vote_history = archive_yesterday_vote()
    accuracy_html = accuracy_section_html(vote_history)

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

    temp_c = weather.get("temp_c")
    snow_new = weather.get("expected_snow_cm_24h")
    precip = weather.get("precip_mm_24h")
    temp_txt = f'{seo.num(temp_c, 1)} °C' if temp_c is not None else "– °C"
    snow_txt = (f'{seo.num(snow_new, 1)} cm snega v 24 h'
                if snow_new is not None else "– cm snega v 24 h")
    streak_val = f"{streak} dni"

    # Snežna odeja: tekoča ocena winter_engine.py za pas 900 m (glej
    # compute_snowpack tam) -- najbližji pas višini prelaza (902 m). Ločena od
    # NOVEGA snega (napoved 24 h), ker sta to dva različna podatka: odeja je
    # to, kar že leži, nov sneg to, kar lahko pade. Ne zlivaj ju v eno število.
    snowpack_cm = ((data.get("snowpack") or {}).get("depth_cm") or {}).get("900")

    na = '<span class="crn-na">Podatek trenutno ni na voljo.</span>'
    temp_html = (f'<p class="crn-big" id="crn-temp-val">{temp_txt}</p>' if temp_c is not None
                 else f'<p id="crn-temp-val">{na}</p>')
    snowpack_html = (f'<p class="crn-big">{seo.num(snowpack_cm, 0)} cm</p>' if snowpack_cm is not None
                     else f'<p>{na}</p>')
    snow_new_txt = f'+{seo.num(snow_new, 1)} cm' if snow_new is not None else "–"
    precip_txt = f'{seo.num(precip, 1)} mm' if precip is not None else "–"

    # "Posodobljeno ob …" -- čas izračuna v našem pasu. Živi preračun v JS ga
    # ob uspehu prepiše s trenutnim časom (glej primeniZivoStanje).
    updated_txt = "Posodobljeno: čas izračuna ni znan"
    try:
        gen = datetime.datetime.fromisoformat(generated_at).astimezone(ZoneInfo("Europe/Ljubljana"))
        updated_txt = (f"Posodobljeno ob {gen:%H:%M}" if gen.date() == seo.TODAY
                       else f"Posodobljeno {gen.day}. {gen.month}. ob {gen:%H:%M}")
    except (ValueError, TypeError):
        pass

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

    # "Deli kot sliko" bere ta paket, ne DOM-a (glej gauge_svg/icon_svg_static)
    # — vsi podatki za canvas so tu že pripravljeni, JS jih samo nariše.
    # "Vprašaj še enkrat" dobi cel QUOTES seznam za klientski reroll (server
    # izbere samo dnevni privzetek).
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
    # Gumbi za poročanje uporabijo ISTE cone/ikone kot izračun (glej
    # ZONE_ICONS), samo s krajšo oznako (ZONE_SHORT) -- da poročevalec izbira
    # med istimi štirimi možnostmi, ki jih izračuna prikazuje, in je
    # razkorak med njima (bistvo strani) dejansko primerljiv.
    report_zone_buttons = "".join(
        f'<button type="button" class="crn-zbtn" data-zona="{z["id"]}" '
        f'style="--zc:{z["color"]};--zbg:{STATUS[z["id"]]["bg"]}">{ZONE_ICONS[z["id"]]}'
        f'<span>{ZONE_SHORT[z["id"]]}</span></button>'
        for z in ZONES
    )

    # Klientski živi preračun (glej __ZONE_DATA_JSON__ v SHARE_JS_TEMPLATE)
    # rabi isti ZONES podatek + STATUS + ikone -- v istem vrstnem redu kot
    # pick_zone() vrača (sonce/nekaj/verige/spolzko), da JS lahko indeksira
    # ZONE_DATA[0..3] brez iskanja po id-ju.
    zone_data = [
        {"id": z["id"], "label": z["label"], "color": z["color"], "mid": z["mid"],
         "status": STATUS[z["id"]]["status"], "statusDesc": STATUS[z["id"]]["desc"],
         "bg": STATUS[z["id"]]["bg"], "ink": STATUS[z["id"]]["ink"], "icon": ZONE_ICONS[z["id"]]}
        for z in ZONES
    ]
    st = STATUS[zone["id"]]

    # Koda za "Vstavi značko" (crn-embed spodaj) -- ročno pobegel niz (ne
    # html.escape, ta modul tu ni uvožen), ker gre za en sam znan literal, ne
    # uporabniški vnos.
    embed_snippet = f'&lt;img src="{WORKER_BASE}/crnivec/znacka.svg" alt="Kako je čez Črnivec? – indeks"&gt;'

    quotes_json = json.dumps(QUOTES, ensure_ascii=False).replace("</", "<\\/")
    rare_quote_json = json.dumps(RARE_QUOTE, ensure_ascii=False).replace("</", "<\\/")
    share_json = json.dumps(share_payload, ensure_ascii=False).replace("</", "<\\/")
    cam_url_json = json.dumps(CAM_URL, ensure_ascii=False).replace("</", "<\\/")
    zone_data_json = json.dumps(zone_data, ensure_ascii=False).replace("</", "<\\/")
    share_js = (SHARE_JS_TEMPLATE
                .replace("__QUOTES_JSON__", quotes_json)
                .replace("__RARE_QUOTE_JSON__", rare_quote_json)
                .replace("__SHARE_JSON__", share_json)
                .replace("__CAM_URL_JSON__", cam_url_json)
                .replace("__ZONE_DATA_JSON__", zone_data_json)
                .replace("__TODAY_ISO__", today_iso))

    # Vrstni red je hierarhija (mobile-first, glej opombo pri CSS): status →
    # meritve → čas → kamera → poročanje → zadnja poročila → vse ostalo.
    # Na namizju: v heroju merilnik levo, meritve desno (.crn-hero-main); pod
    # njim dva stolpca (.crn-cols) -- kamera, nasvet, glasovanje | poročanje,
    # poštenost, lestvica, razlaga + značka. Na telefonu sta stolpca
    # display:contents in vrstni red nosijo razredi .crn-o1…7 (glej CSS).
    body = f'''{CSS}
  <div class="crn">
    <div class="crn-top">
      <a class="crn-brand" href="/">Meteorec</a>
      <div class="crn-install-wrap">
        <button type="button" id="crn-install" class="crn-btn" hidden>Namesti na zaslon</button>
        <p id="crn-install-hint" class="crn-share-status" role="status" aria-live="polite" hidden></p>
      </div>
    </div>

    <section class="crn-hero" aria-labelledby="crn-h1">
      <div class="crn-head">
        {mountain_icon_svg()}
        <div class="crn-head-txt">
          <p class="crn-eyebrow">Črnivec · 902 m n. m.</p>
          <h1 class="crn-title" id="crn-h1">Kako je čez Črnivec?</h1>
          <p id="crn-mascot-msg" class="crn-mascot-msg" role="status" hidden></p>
        </div>
      </div>

      <p id="crn-strike-banner" class="crn-strike" role="status" hidden></p>

      <div class="crn-hero-main">
      <div class="crn-status" id="crn-status" data-zone="{zone['id']}"
        style="--zc:{zone['color']};--zbg:{st['bg']};--zink:{st['ink']}" role="status" aria-live="polite">
        {gauge_svg(zone)}
        <div class="crn-status-icon" id="crn-status-icon">{ZONE_ICONS[zone['id']]}</div>
        <p class="crn-status-title" id="crn-status-title">{st['status']}</p>
        <p class="crn-status-desc" id="crn-status-desc">{st['desc']}</p>
        <p class="crn-updated" id="crn-updated" data-ts="{generated_at}">{updated_txt} · ocena iz vremenskega modela</p>
        <p id="crn-fresh" class="crn-fresh" data-generated="{generated_at}" hidden></p>
        <span class="crn-status-index" id="crn-status-index">Meteorec indeks: {zone['label']}</span>
      </div>

      <div class="crn-hero-side">
      <div class="crn-cards">
        <div class="crn-card">
          <span class="crn-card-art">{CARD_ART['temp']}</span>
          <p class="crn-card-h">{UI_ICONS['temp']}Temperatura</p>
          {temp_html}
          <p class="crn-card-sub">na prelazu</p>
        </div>
        <div class="crn-card">
          <span class="crn-card-art">{CARD_ART['snow']}</span>
          <p class="crn-card-h">{UI_ICONS['snow']}Snežna odeja</p>
          {snowpack_html}
          <p class="crn-card-sub">ocena modela, ~900 m</p>
          <p class="crn-card-h crn-card-h2">Nov sneg · napoved 24 h</p>
          <p class="crn-mid" id="crn-snow-new">{snow_new_txt}</p>
          <p class="crn-card-sub">padavine <b id="crn-precip">{precip_txt}</b></p>
        </div>
      </div>

      <a class="crn-btn crn-btn-primary" href="#kamera">{UI_ICONS['cam']}Poglej kamero</a>
      </div>
      </div>
    </section>

    <div class="crn-cols">
      <div class="crn-col">
      <section class="crn-panel crn-o1" id="kamera" aria-labelledby="crn-cam-h">
        <h2 class="crn-h2" id="crn-cam-h">Kamera na prelazu</h2>
        <div class="crn-cam-frame is-loading">
          <p id="crn-cam-loading" class="crn-cam-loading">Nalagam kamero …</p>
          <img id="crn-cam-img" src="{CAM_URL}" alt="Živa kamera s prelaza Črnivec (902 m)" width="640" height="480">
          <span class="crn-cam-badge" aria-hidden="true"><i></i>V živo</span>
          <span class="crn-cam-place" aria-hidden="true">Črnivec · 902 m</span>
          <p id="crn-cam-fallback" class="crn-cam-fallback" hidden>Kamera trenutno ni dosegljiva.
          <a href="https://www.promet.si/sl/kamere" target="_blank" rel="noopener">Poglej na promet.si</a></p>
        </div>
        <p class="crn-cam-time" id="crn-cam-time" hidden></p>
        <p class="crn-cam-meta">Poglej trenutno stanje prelaza. Vir: <a href="https://www.promet.si" target="_blank"
        rel="noopener">promet.si</a> (Direkcija RS za infrastrukturo) — osveži se vsakih 5 minut.</p>
      </section>

      <section class="crn-tip crn-o3" aria-labelledby="crn-tip-h">
        <p class="crn-tip-h" id="crn-tip-h">💡 Meteorec nasvet</p>
        <div class="crn-quote"><p>{quote}</p></div>
        <p id="crn-visits" class="crn-visits" hidden></p>
        <div class="crn-actions">
          <button type="button" id="crn-reroll" class="crn-btn" hidden>Vprašaj še enkrat</button>
          <button type="button" id="crn-listen" class="crn-btn" hidden>Poslušaj</button>
          <button type="button" id="crn-share" class="crn-btn" hidden>Deli kot sliko</button>
        </div>
        <p id="crn-share-status" class="crn-share-status" role="status" aria-live="polite" hidden></p>
      </section>

      <section class="crn-panel crn-vote crn-o4" id="crn-vote" hidden>
        <div class="crn-vote-row">
          <p class="crn-vote-q">Se ti zdi trenutna ocena pravilna?</p>
          <div class="crn-vote-btns">
            <button type="button" id="crn-vote-gre" class="crn-btn">👍 Gre</button>
            <button type="button" id="crn-vote-ne" class="crn-btn">👎 Ne gre</button>
          </div>
        </div>
        <div class="crn-vote-result" id="crn-vote-result" hidden>
          <div class="crn-vote-bar"><span id="crn-vote-bar-gre"></span></div>
          <p class="crn-vote-count" id="crn-vote-count"></p>
        </div>
      </section>
      </div>

      <div class="crn-col">

      <section class="crn-panel crn-report crn-o2" id="crn-report" aria-labelledby="crn-rep-h" hidden>
        <h2 class="crn-h2" id="crn-rep-h">Kako je bilo tebi?</h2>
        <p class="crn-lead">Povej naslednjemu vozniku.</p>
        <div class="crn-zones" id="crn-report-zones">
          {report_zone_buttons}
        </div>
        <div id="crn-report-form" class="crn-form" hidden>
          <textarea id="crn-report-note" class="crn-input" maxlength="140"
            placeholder="Neobvezna opomba (npr. »samo do polovice«) …" aria-label="Opomba"></textarea>
          <input type="text" id="crn-report-ime" class="crn-input" maxlength="24"
            placeholder="Vzdevek za lestvico (neobvezno)" aria-label="Vzdevek">
          <input type="text" name="website" id="crn-report-hp" autocomplete="off" tabindex="-1"
            style="position:absolute;left:-9999px" aria-hidden="true">
          <button type="button" id="crn-report-submit" class="crn-btn">Pošlji poročilo</button>
        </div>
        <p id="crn-report-status" class="crn-status-msg" role="status" aria-live="polite" hidden></p>
        <div id="crn-report-badge" class="crn-badge" hidden></div>

        <h3 class="crn-h3">Zadnja poročila</h3>
        <ul id="crn-report-feed" class="crn-feed" aria-live="polite">
          <li class="crn-feed-item" aria-hidden="true"><span class="crn-skel" style="width:40%"></span></li>
          <li class="crn-feed-item" aria-hidden="true"><span class="crn-skel" style="width:55%"></span></li>
        </ul>
        <p id="crn-report-week" class="crn-week" hidden></p>
      </section>
      <div class="crn-o5">{accuracy_html}</div>

      <section class="crn-panel crn-board crn-o6" id="crn-board" aria-labelledby="crn-board-h" hidden>
        <h2 class="crn-h2" id="crn-board-h">🏆 Lestvica poročevalcev</h2>
        <div id="crn-board-list" class="crn-board-list" style="margin-top:12px"></div>
      </section>

      <div class="crn-stack crn-o7">
        <details class="crn-acc">
          <summary>ⓘ Kako nastane Meteorec indeks?</summary>
          <div class="crn-acc-body">
            <p>Indeks ni meritev na cesti. Iz napovedi Open-Meteo za dolino in višinske razlike do
            prelaza (902 m) izračunamo temperaturo na vrhu in koliko snega lahko pade v naslednjih
            24 urah — isti izračun kot na <a href="/zima/prevoznost-prelazov/">MeteoZima: prevoznost
            prelazov</a>. Iz tega sledi stanje: nad 5 °C brez snega je suho, okoli ničle pozor, pod ničlo
            spolzko, 2 cm ali več novega snega pa zimske razmere. Snežna odeja je tekoča ocena modela
            za pas okoli 900 m. Stran se ob vsakem obisku preračuna sproti.</p>
            <p>Šaljive nalepke con (»SUHO K POPR«, »TAK-TAK« …) so samo za hec. <strong>Drobni tisk:</strong>
            indeks je znanstveno pomešan z ugibanjem, klepetom v čakalnici in kakšnim komentarjem iz FB.
            Meteorec ne odgovarja, če je bilo v resnici drugače – kar je, mimogrede, tudi bistvo te strani.</p>
          </div>
        </details>

        <details class="crn-acc crn-embed">
          <summary>Vstavi značko na svojo stran</summary>
          <div class="crn-acc-body">
            <img class="crn-embed-preview" src="{WORKER_BASE}/crnivec/znacka.svg"
              alt="Črnivec indeks – živa značka" width="153" height="20" loading="lazy">
            <div class="crn-embed-row">
              <code id="crn-embed-code" class="crn-embed-code">{embed_snippet}</code>
              <button type="button" id="crn-embed-copy" class="crn-btn">Kopiraj</button>
            </div>
            <p id="crn-embed-status" class="crn-share-status" role="status" aria-live="polite" hidden></p>
            <p class="crn-share-status">Osveži se sama vsakih nekaj minut — enkrat vstaviš, naprej živi.</p>
          </div>
        </details>
      </div>
      </div>
    </div>

    <footer class="crn-official">
      <p><strong>Meteorec indeks je neuradna informacija.</strong> Za uradno stanje cest glej
      <a href="https://www.promet.si" target="_blank" rel="noopener">promet.si</a>
      (Prometno-informacijski center), AMZS ali DARS.</p>
      <p>Podrobnejša vremenska ocena za vse prelaze: <a href="/zima/prevoznost-prelazov/">MeteoZima:
      prevoznost prelazov</a>.</p>
      <a class="crn-btn crn-back" href="/">← Nazaj na meteorec.si</a>
    </footer>
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
