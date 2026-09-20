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


def gauge_svg(zone):
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
    needle = (f'<g transform="rotate({rot:.1f} {cx} {cy})">'
              f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" stroke="#111" stroke-width="7" '
              f'stroke-linecap="round"/></g>'
              f'<circle cx="{cx}" cy="{cy}" r="13" fill="#111" stroke="#fff" stroke-width="3"/>')

    labels = []
    for z in ZONES:
        lx, ly = arc_point(cx, cy, r + 40, z["mid"])
        labels.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="10.5" '
                       f'font-weight="800" fill="#111">{z["label"]}</text>')

    return (f'<svg viewBox="0 0 380 230" class="crn-gauge" role="img" '
            f'aria-label="Črnivski indeks: {zone["label"]}">'
            + "".join(arcs) + "".join(labels) + needle + "</svg>")


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
  body{background:#fdf6e3!important;background-image:radial-gradient(#111 1px,transparent 1.4px)!important;
    background-size:16px 16px!important;background-position:-4px -4px!important}
  .wrap{max-width:720px}
  .crn-wrap{font-family:Inter,system-ui,sans-serif;color:#111;padding:1.2rem 0 3rem}
  .crn-hero{display:flex;align-items:center;gap:.8rem;margin-top:.4rem}
  .crn-icon{width:96px;height:auto;flex-shrink:0}
  @media (max-width:520px){.crn-hero{flex-direction:column;align-items:flex-start}
    .crn-icon{width:78px}}
  .crn-title{font-size:2.6rem;font-weight:800;line-height:1.05;letter-spacing:-.01em;
    color:#dc2626;text-shadow:3px 3px 0 #111,-1px -1px 0 #111,1px -1px 0 #111,-1px 1px 0 #111;
    transform:rotate(-1.5deg);margin:0 0 .3rem;text-transform:uppercase}
  .crn-sub{font-size:1.05rem;font-weight:600;color:#111;margin:0 0 1.6rem;max-width:44ch;
    background:#fdf6e3;display:inline-block;padding:.1rem .3rem}
  .crn-panel{background:#fff;border:4px solid #111;border-radius:18px;padding:1.4rem 1.2rem;
    box-shadow:8px 8px 0 #111;margin-bottom:1.6rem;position:relative}
  .crn-panel.tilt{transform:rotate(0.6deg)}
  .crn-gauge{width:100%;max-width:340px;display:block;margin:0 auto}
  .crn-verdict{text-align:center;position:relative;margin-top:.4rem}
  .crn-verdict-star{position:absolute;left:50%;top:50%;width:210px;height:210px;
    transform:translate(-50%,-50%);z-index:0;opacity:.5}
  .crn-verdict span{position:relative;z-index:1;display:inline-block;font-size:1.7rem;
    font-weight:800;text-transform:uppercase;letter-spacing:.01em;background:#fff;
    padding:0 .3rem}
  .crn-quote{background:#fef08a;border:3px solid #111;border-radius:14px;padding:1rem 1.2rem;
    font-weight:700;font-size:1.05rem;position:relative;transform:rotate(-0.8deg)}
  .crn-quote::before{content:"\\201C";font-size:2.4rem;color:#111;line-height:0;
    position:absolute;left:.5rem;top:1.6rem}
  .crn-quote p{margin:0 0 0 1.6rem}
  .crn-data{font-size:.92rem;color:#374151;background:#f3f4f6;border:2px dashed #9ca3af;
    border-radius:10px;padding:.8rem 1rem;margin-top:1rem}
  .crn-fine{font-size:.78rem;color:#6b7280;line-height:1.6;border-top:2px dotted #9ca3af;
    padding-top:1rem;margin-top:1.8rem}
  .crn-links{margin-top:.6rem;font-size:.85rem}
  .crn-links a{color:#1d4ed8;font-weight:700}
  .crn-back{display:inline-block;margin-top:1.6rem;font-weight:700;color:#111;
    background:#fff;border:3px solid #111;border-radius:999px;padding:.5rem 1.1rem;
    text-decoration:none;box-shadow:4px 4px 0 #111}
  @media (max-width:480px){.crn-title{font-size:2rem}}
</style>
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
      <div class="crn-verdict" style="color:{zone['color']}">{starburst_svg(zone['color'])}<span>{zone['label']}</span></div>
      <div class="crn-data">Trenutno na 902 m: {temp_txt}, pričakovanih {snow_txt}
      (ista metoda kot na <a href="/zima/prevoznost-prelazov/">resni strani</a> — le nalepke so tu za hec).</div>
    </div>

    <div class="crn-quote"><p>{quote}</p></div>

    <p class="crn-fine"><strong>Drobni tisk:</strong> ta indeks je znanstveno pomešan z ugibanjem,
    klepetom v čakalnici in enim komentarjem iz FB skupine. Meteorec ne odgovarja, če je bilo v
    resnici čisto drugače — kar je, mimogrede, tudi bistvo te strani.
    <span class="crn-links">Za dejansko uporabno oceno: <a href="/zima/prevoznost-prelazov/">MeteoZima:
    prevoznost prelazov</a> · za uradno stanje ceste: promet.si, AMZS, DARS.</span></p>

    <a class="crn-back" href="/">← Nazaj na meteorec.si</a>
  </div>'''


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
