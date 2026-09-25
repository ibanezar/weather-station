#!/usr/bin/env python3
"""
tools/generate_zima_page.py — MeteoZima, /zima/ podportal (hub + 6 spoke strani)

"MeteoZima" je ime podportala. Glava (logo + ime) se na vseh treh straneh
klientsko zamenja z zimsko izdajo — BRAND_SWAP spodaj, isti vzorec kot
BRAND_SWAP v generate_gobe_page.py (MeteoGobar) — logo je zima/logo-zima.svg,
ista ilustrativna družina kot logo.svg/logo-gobar.svg (64×64, gradienti), ne
ploski ikonski slog spodnjega menija. seo.IC_METEOZIMA (ta slednji slog) je
ločena, še neuporabljena priprava za app_bottomnav() — vstop v glavno
navigacijo CLAUDE.md veže na prvi sneg/november, ne na datum gradnje, zato je
(za razliko od glave) namenoma še ni tu.

Bere data/winter-data.json (tools/winter_engine.py) in iz njega sestavi tri
statične strani po istem vzorcu kot ostale spoke strani
(tools/generate_frost_page.py, tools/generate_agrometeo_page.py) — ne kliče
nobenega API-ja sama, izračun je ločen (winter_engine.py), da se strani
lahko prerenderirajo brez ponovnega klica Open-Meteo:

  /zima/                    — hub: povzetek vseh indeksov za danes/jutri + sezonski dnevnik
  /zima/meja-snezenja/      — meja sneženja po višinskih pasovih + 7-dnevni trend
  /zima/poledica/           — tveganje poledice po krajih v dolini + 7-dnevni pregled
  /zima/kurilni-semafor/    — ocena prevetrenosti za kurjenje + 7-dnevni graf
  /zima/nad-meglo/          — kateri kraji so nad pričakovano meglo + 7-dnevni trend
  /zima/snezna-odeja/       — tekoča modelirana ocena snežne odeje (degree-day model)
  /zima/prevoznost-prelazov/ — vreme na višini gorskih prelazov (Črnivec, Pavličevo sedlo);
                              PASSES v winter_engine.py je ROČNO vzdrževan seznam (glej
                              opombo tam) — nadmorski višini/povezavi sta preverjeni
                              (Wikipedija), dejansko stanje ceste pa ni samodejno

Ločena stran za kakovost zraka NI tu — bi podvajala obstoječi /kakovost-zraka/
(glej opombo pri heating_index v winter_engine.py).

Usage:
  python3 tools/generate_zima_page.py
"""
import datetime, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

DATA_PATH = os.path.join(ROOT, "data", "winter-data.json")

# Zamenja glavo (logo + ime) na vseh treh straneh z MeteoZima izdajo, klientsko
# -- isti vzorec kot BRAND_SWAP v generate_gobe_page.py (MeteoGobar). Namenoma
# tako, ne s spreminjanjem skupnega HEADER-ja v generate_seo_pages.py -- vsaka
# druga generirana stran obdrži navadno glavo Meteorec nespremenjeno.
BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/zima/logo-zima.svg";img.alt="MeteoZima";}
  if(nm){nm.innerHTML="Meteo<em>Zima</em>";}
})();</script>'''

# Isto ime in vrstni red kot RANK_ORDER v winter_engine.py (namerna
# podvojitev — ta datoteka podatkov od tam ne uvaža, samo prebere JSON).
RANK_ORDER = ["nizko", "srednje", "visoko"]

RISK_LABEL = {"nizko": "Nizko tveganje", "srednje": "Srednje tveganje", "visoko": "Visoko tveganje"}
RISK_ICON = {"nizko": "🟢", "srednje": "🟡", "visoko": "🔴"}
RISK_CLASS = {"nizko": "badge-risk-nizko", "srednje": "badge-risk-srednje", "visoko": "badge-risk-visoko"}
CONF_LABEL = {"visoka": "visoka zanesljivost", "srednja": "srednja zanesljivost", "nizka": "nizka zanesljivost"}

# Ročno narisane ikone namesto emoji na kartah/heroj-kartah — isti vizualni
# jezik kot seo.IC_METEOZIMA in app_bottomnav()-jevi ic_* (24×24, obris
# currentColor, ploskev pri nizki prekrivnosti, brez emoji). snow_line
# UPORABI seo.IC_METEOZIMA neposredno (gora + snežinka) namesto lastne
# različice — isti motiv, ne podvojen. Vsaka ostala je zasnovana, da nosi
# pomen svojega indeksa (dimnik s "pokrovom" inverzije, cesta z ledeno
# kepo, vrh nad meglo, snežna odeja z merilno palico, prelaz med vrhovoma).
INDEX_ICONS = {
    "snow_line": None,  # glej icon_html() -- posebna obravnava, uporabi seo.IC_METEOZIMA
    "black_ice": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                  '<path d="M2 17 Q12 13 22 17" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
                  '<path d="M2 20.5 Q12 16.5 22 20.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
                  '<path d="M12 4.5 L15.2 10.5 L12 16 L8.8 10.5 Z" fill="currentColor" fill-opacity=".18" '
                  'stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>'),
    "heating_index": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                       '<rect x="5" y="13.5" width="6" height="7.5" fill="currentColor" fill-opacity=".15" '
                       'stroke="currentColor" stroke-width="1.6"/>'
                       '<path d="M8 13.5 V9.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
                       '<path d="M8 9.5 Q11 6.8 8 4.8 Q6 3.5 8 1.8" stroke="currentColor" stroke-width="1.4" '
                       'stroke-linecap="round" fill="none"/>'
                       '<line x1="3" y1="8.5" x2="21" y2="8.5" stroke="currentColor" stroke-width="1.6" '
                       'stroke-linecap="round" stroke-dasharray="1 3.2"/></svg>'),
    "fog": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<circle cx="17.5" cy="5" r="2.1" fill="currentColor" fill-opacity=".3" stroke="currentColor" stroke-width="1.3"/>'
            '<path d="M4 14.5 L10 6 L14 12 L17 8 L21 14.5 Z" fill="currentColor" fill-opacity=".15" '
            'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
            '<path d="M2 17 Q6 15.2 10 17 T18 17 T22 17" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'
            '<path d="M2 20.3 Q6 18.5 10 20.3 T18 20.3 T22 20.3" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round"/></svg>'),
    "snowpack": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                 '<path d="M3 18.5 Q7 16.5 11 18.5 T21 18.5" fill="currentColor" fill-opacity=".18" '
                 'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
                 '<path d="M3 14.5 Q7 12.5 11 14.5 T21 14.5" fill="none" stroke="currentColor" stroke-width="1.4" '
                 'stroke-linecap="round"/>'
                 '<line x1="17" y1="3.5" x2="17" y2="18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
                 '<line x1="14.7" y1="6.5" x2="17" y2="6.5" stroke="currentColor" stroke-width="1.3"/>'
                 '<line x1="14.7" y1="10.5" x2="17" y2="10.5" stroke="currentColor" stroke-width="1.3"/></svg>'),
    "passes": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
               '<path d="M2 19 L8.5 6 L11.5 12 L14.5 5 L21 19 Z" fill="currentColor" fill-opacity=".13" '
               'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
               '<path d="M9.5 11 Q7 13.3 10 15.3 Q13 17.3 10.5 19.3" stroke="currentColor" stroke-width="1.4" '
               'stroke-linecap="round" fill="none"/></svg>'),
}


# Barvni poudarek na indeks -- isti vzorec kot GOBE_CATEGORIES (--fa/--fa-soft)
# v generate_gobe_page.py: brez tega so vse ikone samo currentColor (siva/bela,
# ista kot besedilo) in stran deluje monotono. Šest jasno ločenih barvnih
# tonov (modra/cian/oranžna/vijolična/roza/rumena), da se sosednje kartice v
# mreži ločijo tudi po barvi, ne le po besedilu. snow_line obdrži isto modro
# kot CHART_LINE_COLOR (isti motiv na kartici in na grafu).
ZIMA_ACCENT = {
    "snow_line": "#38bdf8",
    "black_ice": "#2dd4bf",
    "heating_index": "#fb923c",
    "fog": "#a78bfa",
    "snowpack": "#f472b6",
    "passes": "#fbbf24",
}


def _rgba(hex_color, alpha):
    """#rrggbb -> rgba(r,g,b,alpha) -- mehka podlaga ikone iz istega poudarka
    (namerna podvojitev _rgba() iz generate_gobe_page.py, isto načelo kot
    drugod v repozitoriju -- generatorji strani si ne delijo knjižnic)."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def icon_html(key, size=26):
    svg = seo.IC_METEOZIMA if key == "snow_line" else INDEX_ICONS[key]
    svg = svg.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
    accent = ZIMA_ACCENT[key]
    style = f'--fa:{accent};--fa-soft:{_rgba(accent, ".16")}'
    return f'<span class="zima-icon" aria-hidden="true" style="{style}">{svg}</span>'


def card_style(key, extra="margin-bottom:1.2rem"):
    """--fa/--fa-soft za .zima-card (barvni vrhnji rob, glej ZIMA_CSS) -- iste
    spremenljivke kot na icon_html()-ovi ikoni v isti kartici, da se barva
    roba in ikone ujemata."""
    accent = ZIMA_ACCENT[key]
    return f'--fa:{accent};--fa-soft:{_rgba(accent, ".16")};{extra}'


# Subtilne animacije za ikone/grafe -- ista TEHNIKA (ročno narisan SVG + CSS,
# brez JS knjižnic) kot na /crnivec/, a NAMENOMA drugačen videz: kratka rast/
# izris namesto poskoka/vrtenja -- /zima/ ostane temna in resna, ne stripovska
# (glej opombo pri INDEX_ICONS zgoraj in uporabnikov izrecni "enako tehniko,
# ne izgled"). `.zima-bar` uporablja transform-origin, nastavljen inline v
# daily_bar_chart_svg() (isti vzorec kot crn-needle na /crnivec/ -- CSS
# transform ima prednost pred XML atributom, zato ga stolpec sploh nima).
# `.zima-line` je klasičen "draw-in" trik (stroke-dasharray/dashoffset) --
# 3000 je namenoma precej več od dejanske dolžine katerekoli poti v viewBoxu
# 640x190, da je začetni odmik zagotovo daljši od same črte.
# `prefers-reduced-motion` obe animaciji izklopi, isto kot na /crnivec/ in
# /igra/.

# Subtilen zimski ambient za ozadje hero-ja -- statičen (ni podatkovno odvisen,
# zato konstanta, ne funkcija): nebesni prelivi, tri plasti topografskih
# kontur in silhueta gora, izrisano kot ena SVG (position:absolute, glej
# .zima-hero-bg v ZIMA_CSS spodaj). NAMENOMA brez letečih snežink -- uporabnik
# je to eksplicitno izključil ("ne snežink, ki letijo po ekranu"), samo mirna
# dekoracija. Ni "risan" motiv nobene resnične gore (isto načelo kot
# storm_threat_score -- vizualni jezik, ne trditev o geografiji).
ZIMA_AMBIENT_BG = '''
      <svg class="zima-hero-bg" viewBox="0 0 1150 300" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
        <defs>
          <linearGradient id="zimaSkyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#0c1c33" stop-opacity=".6"/>
            <stop offset="100%" stop-color="#04070e" stop-opacity="0"/>
          </linearGradient>
          <radialGradient id="zimaHalo" cx="80%" cy="12%" r="50%">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity=".2"/>
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
          </radialGradient>
        </defs>
        <rect width="1150" height="300" fill="url(#zimaSkyGrad)"/>
        <rect width="1150" height="300" fill="url(#zimaHalo)"/>
        <path d="M-20 235 Q 200 205 420 232 T 900 220 T 1180 240" fill="none" stroke="#1e293b" stroke-width="1"/>
        <path d="M-20 253 Q 220 224 440 250 T 920 240 T 1180 258" fill="none" stroke="#1e293b" stroke-width="1"/>
        <path d="M-20 270 Q 240 244 460 266 T 940 258 T 1180 274" fill="none" stroke="#1e293b" stroke-width="1"/>
        <path d="M-20 300 L110 170 L215 235 L340 105 L455 220 L610 70 L755 205 L890 135 L1015 225 L1150 165 L1180 190 L1180 300 Z"
              fill="#0a1120" fill-opacity=".62"/>
      </svg>
'''

ZIMA_CSS = '''
<style>
.zima-icon{display:inline-flex;align-items:center;justify-content:center;width:2.15rem;height:2.15rem;
  border-radius:10px;background:var(--fa-soft,rgba(148,163,184,.14));color:var(--fa,#94a3b8);
  margin-right:.6rem;flex:0 0 auto;vertical-align:-.65rem}
.zima-icon svg{width:1.3rem;height:1.3rem;display:block}
.zima-card{position:relative;overflow:hidden}
.zima-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa,#38bdf8)}
.zima-phenom{position:relative;overflow:hidden}
.zima-phenom .ph-icon{display:flex;justify-content:center}
.zima-phenom .ph-icon .zima-icon{margin-right:0}
.zima-phenom::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa,#38bdf8)}
.zima-phenom:hover{border-color:var(--fa,#38bdf8)!important}
.zima-bar{animation:zimaGrow .5s ease-out backwards;animation-delay:var(--zdelay,0ms)}
@keyframes zimaGrow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
.zima-line{stroke-dasharray:3000;stroke-dashoffset:3000;animation:zimaDraw 1.4s ease-out forwards}
@keyframes zimaDraw{to{stroke-dashoffset:0}}
@media (prefers-reduced-motion: reduce){
  .zima-bar,.zima-line{animation:none;stroke-dashoffset:0}
}
/* Širši layout na VSEH /zima/* straneh (:has(.zima-card) jih loči od ostalih
   generiranih strani, ki delijo isti .wrap iz blog.css s privzetim
   max-width:720px) -- glej opombo uporabnika o "preozki" strani. .zima-card
   je na vseh sedmih straneh (hub + 6 spoke), .zima-hero samo na hubu -- prvi
   poskus je pomotoma zožil samo hub, spoke strani so ostale na 720px.
   Brskalnik brez podpore :has() preprosto obdrži 720px, varno degradiranje. */
.wrap:has(.zima-card){max-width:1150px}
/* Accordion vizual za FAQ (native <details>/<summary>, glej faq v vsakem
   build_*_body). SAMO tu, ne globalno v blog.css -- isti <div class="faq">
   vzorec uporabljajo desetine drugih generiranih strani in bi jih nehoteno
   spremenili. */
.wrap:has(.zima-card) .faq details{background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:14px;padding:.9rem 1.1rem;margin-bottom:.7rem}
.wrap:has(.zima-card) .faq summary{cursor:pointer;font-weight:650;color:var(--text);
  list-style:none;display:flex;align-items:center;justify-content:space-between;gap:.6rem}
.wrap:has(.zima-card) .faq summary::-webkit-details-marker{display:none}
.wrap:has(.zima-card) .faq summary::after{content:"+";color:var(--cyan);font-size:1.25rem;
  font-weight:400;flex:0 0 auto;transition:transform .2s;line-height:1}
.wrap:has(.zima-card) .faq details[open] summary::after{transform:rotate(45deg)}
.wrap:has(.zima-card) .faq details p{margin:.6rem 0 0;color:var(--muted);font-size:.9rem;line-height:1.6}
.zima-fog-ladder{display:flex;flex-direction:column;gap:.35rem;margin:1rem 0}
.zima-fog-row{display:flex;justify-content:space-between;gap:.6rem;padding:.5rem .9rem;border-radius:10px;
  background:rgba(255,255,255,.03);border:1px solid var(--card-border);font-size:.88rem}
.zima-fog-row.below{color:var(--muted)}
.zima-fog-elev{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--muted);white-space:nowrap}
.zima-fog-line{text-align:center;font-size:.76rem;color:#94a3b8;padding:.4rem 0;
  border-top:1px dashed var(--card-border);border-bottom:1px dashed var(--card-border);margin:.15rem 0}
.zima-hero{position:relative;overflow:hidden;background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:22px;padding:1.8rem 2rem;margin:1rem 0 1.4rem;box-shadow:var(--card-shadow)}
.zima-hero::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;z-index:2;
  background:linear-gradient(90deg,#38bdf8,#2dd4bf,#fbbf24,#a78bfa,#f472b6)}
/* ZIMA_AMBIENT_BG (glej konstanto zgoraj) -- position:absolute čez cel hero,
   za besedilom (.zh-content nosi position:relative;z-index:1, glej spodaj). */
/* Fiksna višina (ne inset:0 čez cel hero) -- na ozkem/visokem mobilnem heroju
   (skladi CTA/stat kartic naredijo hero visok) bi raztegnjena celotna višina
   silhueto gora popačila v navpično konico. Fiksnih 220px + preserveAspectRatio
   "slice" pomeni: obreže robove na ozkih zaslonih, ne raztegne proporcev. */
.zima-hero-bg{position:absolute;left:0;right:0;bottom:0;width:100%;height:220px;z-index:0;pointer-events:none;display:block}
.zh-content{position:relative;z-index:1}
.zima-hero .page-title{margin:.1rem 0 .15rem}
.zima-hero .zh-sub{color:var(--muted);font-size:.95rem;margin:0 0 1.1rem}
.zima-hero .zh-verdict{font-size:1.12rem;font-weight:600;line-height:1.6;margin:0 0 1.3rem;max-width:44rem}
/* Utripajoča piko ob statusu ("bolj animiran status", glej uporabnikov predlog)
   -- barva po stanju (isto besedišče kot RISK_ICON/RANK_ORDER: visoko/srednje/
   nizko + snow za snežno odejo, ki prevlada nad tveganji). Izklopljeno pod
   prefers-reduced-motion, isto načelo kot .zima-bar/.zima-line zgoraj. */
.zh-status{display:inline-flex;align-items:center;gap:.5rem}
.zh-dot{width:.6rem;height:.6rem;border-radius:50%;flex:0 0 auto;animation:zhPulse 2.2s ease-out infinite}
.zh-status-visoko .zh-dot{background:#f87171;--dot-glow:rgba(248,113,113,.55)}
.zh-status-srednje .zh-dot{background:var(--amber);--dot-glow:rgba(245,158,11,.5)}
.zh-status-nizko .zh-dot{background:#34d399;--dot-glow:rgba(52,211,153,.5)}
.zh-status-snow .zh-dot{background:#e2e8f0;--dot-glow:rgba(226,232,240,.5)}
@keyframes zhPulse{0%{box-shadow:0 0 0 0 var(--dot-glow,rgba(148,163,184,.5))}
  70%{box-shadow:0 0 0 9px transparent}100%{box-shadow:0 0 0 0 transparent}}
@media (prefers-reduced-motion: reduce){.zh-dot{animation:none}}
.zh-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.85rem;margin-bottom:1.4rem}
.zh-stat{background:rgba(255,255,255,.035);border:1px solid var(--card-border);border-radius:14px;padding:.85rem 1rem}
.zh-stat-label{font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);
  font-family:'JetBrains Mono',monospace}
.zh-stat-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.7rem;color:#fff;
  margin:.25rem 0 0;line-height:1.1}
.zh-cta{display:flex;gap:.7rem;flex-wrap:wrap}
.zh-cta a{display:inline-flex;align-items:center;gap:.4rem;padding:.6rem 1.15rem;border-radius:10px;
  border:1px solid var(--card-border);background:rgba(255,255,255,.035);color:var(--text);
  text-decoration:none;font-size:.87rem;font-weight:650;transition:border-color .18s,color .18s}
.zh-cta a:hover{border-color:var(--cyan);color:var(--cyan)}
.zima-section-title{display:flex;align-items:center;gap:.5rem}
/* Mreža 5 stanj namesto prejšnjega enega stolpca -- glej card_style() klice v
   build_hub_body(), ki za to mrežo pošljejo prazen extra="" (brez privzetega
   margin-bottom, ker razmik zdaj dela grid gap). zima-card-wide (kurilni
   semafor) zavzame celo širino vrstice, da je vidno večji od ostalih štirih. */
.zima-conditions-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin-bottom:1.2rem}
.zima-conditions-grid .zima-card-wide{grid-column:1/-1}
.zima-meter-svg{width:100%;height:auto;display:block}
.zima-passes-list{display:grid;gap:.7rem;margin:1rem 0 1.2rem}
.zima-pass-row{background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;
  padding:.9rem 1.1rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}
.zima-pass-name{font-weight:700;color:var(--text)}
.zima-pass-meta{font-size:.8rem;color:var(--muted);margin-top:.15rem}
.zima-pass-status{font-size:.82rem;font-weight:650;white-space:nowrap}
</style>'''


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def num(x, d=1):
    return seo.num(x, d)


def risk_badge(level):
    if level is None:
        return '<span class="badge-risk badge-risk-none">ni podatka</span>'
    return f'<span class="badge-risk {RISK_CLASS[level]}">{RISK_ICON[level]} {RISK_LABEL[level]}</span>'


def fmt_day(date_iso):
    """'2026-11-16' -> 'jutri' / 'danes' glede na TODAY, sicer 'D. M.'."""
    y, m, d = int(date_iso[:4]), int(date_iso[5:7]), int(date_iso[8:10])
    date_obj = datetime.date(y, m, d)
    if date_obj == TODAY:
        return "danes"
    if date_obj == TODAY + datetime.timedelta(days=1):
        return "jutri"
    return f"{d}. {m}."


def fmt_hour(iso):
    """'2026-11-16T05:00' -> 'jutri, 05:00' / 'danes, 05:00' glede na TODAY."""
    try:
        dt = datetime.datetime.strptime(iso[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return iso
    return f"{fmt_day(iso[:10])}, {dt.strftime('%H:%M')}"


def fmt_day_short(date_iso):
    d, m = int(date_iso[8:10]), int(date_iso[5:7])
    return "danes" if date_iso == TODAY.isoformat() else f"{d}.{m}."


# ── Grafi (7-dnevni pregled) ─────────────────────────────────────────────
#
# Statični, strežniško izrisan SVG — isti vzorec kot history_chart_svg v
# generate_frost_page.py (brez JS, brez zunanjih knjižnic; te strani so
# statične SEO strani, ne živi app.js pripomočki na naslovni strani).
# Razred "frost-chart" (width:100%;height:auto;display:block v vreme.css) je
# generičen kljub imenu — uporabljen tudi tu, da se CSS ne podvaja.
#
# Barve (CHART_COLOR) so LOČENE od badge-risk/RISK_CLASS: to so paličaste/
# črtne barve za velike ploskve na grafu, ne majhne značke. Preverjene s
# skill `dataviz`, `scripts/validate_palette.js "#0284c7,#d97706,#e11d48"
# --mode dark --surface "#04070e"` (dejansko ozadje strani, ne privzeto iz
# skripte) — vse šest preverjanj (svetlost, kroma, CVD-ločljivost, normalna
# ločljivost, kontrast) je uspešno. Ne menjaj teh barv brez ponovne
# validacije (glej CLAUDE.md, opomba pri MTR grafu).
CHART_COLOR = {"nizko": "#0284c7", "srednje": "#d97706", "visoko": "#e11d48"}
CHART_LINE_COLOR = "#38bdf8"  # en sam niz (meja sneženja/megla) — brez kategorij, brez validacije potrebno


def daily_bar_chart_svg(days, values, levels, unit=""):
    """Stolpci: višina = values[i] (magnituda), barva = levels[i] (kategorija
    iz CHART_COLOR). Uporabljeno za kurilni semafor (jakost inverzije)."""
    n = len(days)
    if n == 0:
        return None
    w, h, pad_l, pad_r, pad_t, pad_b = 640, 190, 8, 8, 26, 26
    known = [v for v in values if v is not None]
    hi = max(known + [0.1])
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    slot_w = plot_w / n
    bar_w = slot_w * 0.55

    parts = []
    for i, (v, lvl) in enumerate(zip(values, levels)):
        cx = pad_l + slot_w * (i + 0.5)
        color = CHART_COLOR.get(lvl, "#64748b")
        bh = max((v / hi) * plot_h, 3) if v else 3
        y = pad_t + plot_h - bh
        # zima-bar + --by/--delay: CSS animira rast iz osnovne črte (glej ZIMA_CSS) --
        # zaporedoma po dnevih, ne vseh naenkrat, da graf deluje kot da se "izriše".
        parts.append(f'<rect class="zima-bar" x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                      f'height="{bh:.1f}" rx="3" fill="{color}" '
                      f'style="--zdelay:{i * 70}ms;transform-origin:{cx:.1f}px {h - pad_b:.1f}px"/>')
        if v is not None:
            parts.append(f'<text x="{cx:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="9.5" '
                          f'fill="#94a3b8">{RISK_ICON.get(lvl, "")} {num(v, 1)}{unit}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - 8}" text-anchor="middle" font-size="9.5" '
                      f'fill="#94a3b8">{fmt_day_short(days[i])}</text>')

    return (f'<svg viewBox="0 0 {w} {h}" class="frost-chart zima-chart" role="img" '
            f'aria-label="Sedemdnevni pregled po dnevih">' + "".join(parts) + '</svg>')


def daily_line_chart_svg(days, values, unit="", color=CHART_LINE_COLOR):
    """Ena črta (magnituda skozi dneve) — uporabljeno za mejo sneženja in
    mejo megle. Manjkajoča vrednost (None, npr. dan brez inverzije pri
    megli) PRETRGA črto namesto da bi jo povezala čez prazen dan."""
    n = len(days)
    known_idx = [i for i, v in enumerate(values) if v is not None]
    if len(known_idx) < 2:
        return None
    w, h, pad_l, pad_r, pad_t, pad_b = 640, 190, 40, 12, 16, 28
    vals = [values[i] for i in known_idx]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    pad = (hi - lo) * 0.2
    lo, hi = lo - pad, hi + pad
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b
    slot_w = plot_w / n

    def x_of(i):
        return pad_l + slot_w * (i + 0.5)

    def y_of(v):
        return pad_t + plot_h * (1 - (v - lo) / (hi - lo))

    segments, seg = [], []
    for i, v in enumerate(values):
        if v is None:
            if len(seg) > 1:
                segments.append(seg)
            seg = []
        else:
            seg.append((x_of(i), y_of(v)))
    if len(seg) > 1:
        segments.append(seg)

    lines = "".join(
        '<polyline class="zima-line" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in s) +
        f'" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        for s in segments
    )
    dots = "".join(
        f'<circle cx="{x_of(i):.1f}" cy="{y_of(v):.1f}" r="3.2" fill="{color}"/>'
        for i, v in enumerate(values) if v is not None
    )
    gaps = "".join(
        f'<circle cx="{x_of(i):.1f}" cy="{h - pad_b + 4}" r="2" fill="#475569"/>'
        for i, v in enumerate(values) if v is None
    )
    labels = "".join(
        f'<text x="{x_of(i):.1f}" y="{h - 8}" text-anchor="middle" font-size="9.5" '
        f'fill="#94a3b8">{fmt_day_short(days[i])}</text>'
        for i in range(n)
    )
    y_lbl = (f'<text x="{pad_l - 6}" y="{y_of(hi) + 3:.1f}" text-anchor="end" font-size="9" '
             f'fill="#94a3b8">{num(hi, 0)}{unit}</text>'
             f'<text x="{pad_l - 6}" y="{y_of(lo) + 3:.1f}" text-anchor="end" font-size="9" '
             f'fill="#94a3b8">{num(lo, 0)}{unit}</text>')

    return (f'<svg viewBox="0 0 {w} {h}" class="frost-chart" role="img" '
            f'aria-label="Sedemdnevni trend">' + lines + dots + gaps + y_lbl + labels + '</svg>')


def hourly_temp_chart_svg(hourly_48h):
    """Temperatura na postaji za naslednjih ~48 ur (+ 6 ur nazaj za kontekst,
    glej compute_hourly_48h v winter_engine.py) — isti 'draw-in' CSS trik
    (zima-line) kot daily_line_chart_svg, a z urno osjo namesto dnevne in
    navpično črto pri trenutni uri (now_idx, izračunan že v winter_engine.py,
    da ga tu ni treba znova iskati po času)."""
    if not hourly_48h:
        return None
    times = hourly_48h.get("times") or []
    temps = hourly_48h.get("temp_c") or []
    now_idx = hourly_48h.get("now_idx")
    n = len(times)
    known = [(i, v) for i, v in enumerate(temps) if v is not None]
    if len(known) < 2 or now_idx is None or n < 2:
        return None
    w, h, pad_l, pad_r, pad_t, pad_b = 640, 190, 34, 10, 22, 28
    vals = [v for _, v in known]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    pad = (hi - lo) * 0.18
    lo, hi = lo - pad, hi + pad
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    def x_of(i):
        return pad_l + plot_w * (i / (n - 1))

    def y_of(v):
        return pad_t + plot_h * (1 - (v - lo) / (hi - lo))

    pts = " ".join(f"{x_of(i):.1f},{y_of(v):.1f}" for i, v in known)
    line = (f'<polyline class="zima-line" points="{pts}" fill="none" stroke="{CHART_LINE_COLOR}" '
            f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>')
    now_x = x_of(now_idx)
    now_line = (f'<line x1="{now_x:.1f}" y1="{pad_t}" x2="{now_x:.1f}" y2="{h - pad_b}" '
                f'stroke="#64748b" stroke-width="1" stroke-dasharray="3 3"/>'
                f'<text x="{now_x:.1f}" y="{pad_t - 6}" text-anchor="middle" font-size="9.5" '
                f'fill="#94a3b8">zdaj</text>')

    dividers, labels = [], []
    for i, t in enumerate(times):
        try:
            dt = datetime.datetime.strptime(t[:16], "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        if dt.hour == 0:
            dividers.append(f'<line x1="{x_of(i):.1f}" y1="{pad_t}" x2="{x_of(i):.1f}" y2="{h - pad_b}" '
                             f'stroke="#1e293b" stroke-width="1"/>')
        if dt.hour % 6 == 0:
            labels.append(f'<text x="{x_of(i):.1f}" y="{h - 8}" text-anchor="middle" font-size="9" '
                          f'fill="#94a3b8">{dt.strftime("%H")}h</text>')
    y_lbl = (f'<text x="{pad_l - 6}" y="{y_of(hi) + 3:.1f}" text-anchor="end" font-size="9" '
             f'fill="#94a3b8">{num(hi, 0)}°C</text>'
             f'<text x="{pad_l - 6}" y="{y_of(lo) + 3:.1f}" text-anchor="end" font-size="9" '
             f'fill="#94a3b8">{num(lo, 0)}°C</text>')

    return (f'<svg viewBox="0 0 {w} {h}" class="frost-chart" role="img" '
            f'aria-label="Temperatura naslednjih 48 ur">'
            + "".join(dividers) + line + now_line + y_lbl + "".join(labels) + '</svg>')


def snow_line_meter_svg(line_m, station_elev=None, scale_max=2500):
    """Vodoravna lestvica 0–scale_max m z označeno postajo in trikotnim
    kazalcem pri trenutni meji sneženja — razlaga številke, ki jo hero že
    pove kot besedilo (glej build_hub_body), grafično: kaj je pod mejo (dež,
    modri konec lestvice) in kaj nad njo (sneg, svetli konec). Vrednost nad
    scale_max se prikaže s puščico ob desnem robu in ">X m" napisom, namesto
    da bi kazalec pobegnil iz slike."""
    if line_m is None:
        return None
    station_elev = station_elev if station_elev is not None else seo.ELEV
    w, h, pad_l, pad_r = 640, 96, 16, 16
    bar_y, bar_h = 46, 10
    plot_w = w - pad_l - pad_r

    def x_at(v):
        return pad_l + plot_w * (max(0, min(v, scale_max)) / scale_max)

    ticks_m = [0, 500, 1000, 1500, 2000, scale_max]
    ticks = "".join(
        f'<line x1="{x_at(t):.1f}" y1="{bar_y - 4}" x2="{x_at(t):.1f}" y2="{bar_y + bar_h + 4}" '
        f'stroke="#334155" stroke-width="1"/>'
        f'<text x="{x_at(t):.1f}" y="{bar_y + bar_h + 18}" text-anchor="middle" font-size="9.5" '
        f'fill="#94a3b8">{t} m</text>'
        for t in ticks_m
    )
    grad = ('<defs><linearGradient id="zimaMeterGrad" x1="0" y1="0" x2="1" y2="0">'
            '<stop offset="0%" stop-color="#0369a1"/><stop offset="55%" stop-color="#38bdf8"/>'
            '<stop offset="100%" stop-color="#e2e8f0"/></linearGradient></defs>')
    bar = f'<rect x="{pad_l}" y="{bar_y}" width="{plot_w}" height="{bar_h}" rx="5" fill="url(#zimaMeterGrad)"/>'
    station_x = x_at(station_elev)
    station = (f'<circle cx="{station_x:.1f}" cy="{bar_y + bar_h / 2:.1f}" r="4.5" fill="#fff" '
               f'stroke="#04070e" stroke-width="1.5"/>'
               f'<text x="{station_x:.1f}" y="{bar_y - 10}" text-anchor="middle" font-size="9.5" '
               f'fill="#94a3b8">Rečica {station_elev} m</text>')
    line_x = x_at(line_m)
    marker_label = f'>{scale_max} m' if line_m > scale_max else f'{line_m} m'
    marker = (f'<path d="M{line_x:.1f} {bar_y - 3} l-7 -12 h14 Z" fill="{CHART_LINE_COLOR}"/>'
              f'<text x="{line_x:.1f}" y="{bar_y - 19}" text-anchor="middle" font-size="11" '
              f'font-weight="700" fill="#e8edf8">{marker_label}</text>')

    return (f'<svg viewBox="0 0 {w} {h}" class="frost-chart zima-meter-svg" role="img" '
            f'aria-label="Meja sneženja na lestvici 0 do {scale_max} m">'
            + grad + bar + ticks + station + marker + '</svg>')


# ── /zima/ hub ────────────────────────────────────────────────────────────

def build_hub_body(data):
    snow = data["snow_line"]
    locations = data["locations"]
    worst_loc = max(locations, key=lambda l: RANK_ORDER.index(l["indices"]["black_ice"]["risk_level"]))
    worst_level = worst_loc["indices"]["black_ice"]["risk_level"]

    line_m = snow.get("current_line_m")
    if line_m is None:
        snow_verdict = "Meja sneženja trenutno ni na voljo."
    elif line_m > 1700:
        snow_verdict = f"Meja sneženja je danes pri {line_m} m — nad vsemi spremljanimi višinami v dolini, sneg ni pričakovan."
    else:
        below = [b for b in snow["expected_cm_by_elevation"] if b["cm"] > 0]
        if below:
            snow_verdict = (f"Meja sneženja je pri {line_m} m — nad {below[0]['elevation_m']} m n. m. "
                             f"je v naslednjih 24 h pričakovanih do {num(max(b['cm'] for b in below), 1)} cm snega.")
        else:
            snow_verdict = f"Meja sneženja je pri {line_m} m, a v naslednjih 24 h ni pričakovanih pomembnejših padavin."

    ice_verdict = (f"V naslednjih 36 h ni povečanega tveganja poledice v dolini."
                   if worst_level == "nizko" else
                   f"V naslednjih 36 h je najbolj izpostavljen kraj {worst_loc['name']} — {risk_badge(worst_level)}.")

    heating = data.get("heating_index") or {}
    heating_level = heating.get("level")
    heating_verdict = (f"Zrak se dobro prevetri, posebnih omejitev za kurjenje ni."
                        if heating_level == "nizko" else
                        f"{heating.get('advice', '')}" if heating.get("advice")
                        else "Ocena kurilnega semaforja trenutno ni na voljo.")

    fog = data.get("fog")
    if not fog:
        fog_verdict = "Ocena megle trenutno ni na voljo."
    elif not fog.get("has_inversion"):
        fog_verdict = "Jutri zjutraj ni pričakovane pomembne inverzije — megla v dolini ni verjetna."
    else:
        above = [l["name"] for l in fog["locations"] if l["above"]]
        fog_verdict = (f"Jutri zjutraj pričakovana megla/nizka oblačnost do ~{fog['top_m']} m — "
                        + (f"nad njo bi lahko bili: {', '.join(above)}." if above
                           else "noben spremljan kraj v dolini danes ne bi bil nad njo."))

    snowpack = data.get("snowpack") or {}
    station_depth = next((b["depth_cm"] for b in snowpack.get("by_elevation", []) if b["elevation_m"] == seo.ELEV), None)

    passes = data.get("passes") or []

    # ── Hero: en glavni status namesto pet enakovrednih kartic druga pod
    # drugo (glej uporabnikov predlog) — snežna odeja je edino stanje, ki
    # upravičeno prevlada nad tveganji (fizično dejstvo, ne ocena), sicer
    # zmaga najslabši od poledice/kurjenja. hero_verdict je NAMENOMA isto
    # besedilo kot snow_verdict v "brez razmer" primeru -- eno besedilo o
    # trenutni meji sneženja, ne dve različici, ki bi se sčasoma razšli.
    ice_rank = RANK_ORDER.index(worst_level)
    heat_rank = RANK_ORDER.index(heating_level) if heating_level in RANK_ORDER else -1
    overall_rank = max(ice_rank, heat_rank)
    overall_level = RANK_ORDER[overall_rank] if overall_rank >= 0 else None
    # Kurilni semafor meri prevetrenost/inverzijo -- pojav, ki ni vezan na
    # sneg/led/zimo (jasna mirna noč ga sproži tudi sredi jeseni, glej opombo
    # uporabnika 22. 9. 2026: hero je javil "POVEČANO ZIMSKO TVEGANJE", ker je
    # bil edini presežen indeks kurilni semafor, poledica pa je bila le
    # srednja). Zato, kadar kurilni semafor edini preseže poledico, hero
    # poroča o PREVETRENOSTI, ne o "zimskem tveganju" -- isto načelo kot
    # "primernost, ne tveganje %" pri agrometeo (glej CLAUDE.md).
    heating_only = heat_rank > ice_rank
    has_snow = station_depth is not None and station_depth > 0
    if has_snow:
        hero_icon, hero_label, status_cls = "⚪", "SNEŽNA ODEJA V DOLINI", "snow"
        hero_verdict = (f"V dolini trenutno po oceni leži <strong>{num(station_depth, 0)} cm</strong> "
                         f"snežne odeje (modelirano, ni meritev).")
    elif heating_only and overall_level in ("visoko", "srednje"):
        hero_icon = "🔴" if overall_level == "visoko" else "🟡"
        hero_label = ("KURILNI SEMAFOR: SLABA PREVETRENOST" if overall_level == "visoko"
                       else "KURILNI SEMAFOR: ZMERNA PREVETRENOST")
        status_cls = overall_level
        hero_verdict = heating.get("advice") or "Ocena kurilnega semaforja trenutno ni na voljo."
    elif overall_level == "visoko":
        hero_icon, hero_label, status_cls = "🔴", "POVEČANO ZIMSKO TVEGANJE", "visoko"
        hero_verdict = "Danes je vsaj eden od zimskih indeksov na visoki stopnji — poglej razmere spodaj."
    elif overall_level == "srednje":
        hero_icon, hero_label, status_cls = "🟡", "DELNO ZIMSKO TVEGANJE", "srednje"
        hero_verdict = "Danes je vsaj eden od zimskih indeksov na srednji stopnji — poglej razmere spodaj."
    else:
        hero_icon, hero_label, status_cls = "🟢", "BREZ ZIMSKIH RAZMER", "nizko"
        hero_verdict = snow_verdict

    # ── Subtilen zimski ambient v ozadju hero-ja: nebesni prelivi + topografske
    # konture + silhueta gora, glej ZIMA_AMBIENT_BG. NAMENOMA brez snežink, ki
    # bi letele čez zaslon (uporabnik je to izrecno izključil) — samo statična
    # dekoracija za .zh-content (glej ZIMA_CSS za z-index sklad). Živ status
    # dobi utripajočo piko (isti prefers-reduced-motion izklop kot zima-bar/
    # zima-line zgoraj), da hero deluje kot "živ" nadzorni center, ne statičen
    # posnetek. ──
    hero_html = f'''  <div class="zima-hero">
{ZIMA_AMBIENT_BG}
    <div class="zh-content">
    <h1 class="page-title">❄️ Zimski nadzorni center</h1>
    <p class="zh-sub">Zgornja Savinjska dolina · MeteoZima</p>
    <p class="zh-verdict"><span class="zh-status zh-status-{status_cls}"><span class="zh-dot"></span>{hero_icon} <strong>{hero_label}</strong></span><br>{hero_verdict}</p>
    <div class="zh-stats">
      <div class="zh-stat"><div class="zh-stat-label">Sneg zdaj</div>
        <div class="zh-stat-val">{num(station_depth, 0) + " cm" if station_depth is not None else "—"}</div></div>
      <div class="zh-stat"><div class="zh-stat-label">Meja sneženja</div>
        <div class="zh-stat-val">{num(line_m, 0) + " m" if line_m is not None else "—"}</div></div>
      <div class="zh-stat"><div class="zh-stat-label">Tveganje poledice</div>
        <div class="zh-stat-val" style="font-size:1.05rem">{risk_badge(worst_level)}</div></div>
    </div>
    <div class="zh-cta">
      <a href="/">🌡️ Trenutno vreme</a>
      <a href="#zimski-pogoji">❄️ Zimske razmere</a>
      <a href="#zimske-ceste">🚗 Zimske ceste</a>
    </div>
    <p class="post-meta" style="margin:.9rem 0 0">Posodobljeno {data.get("generated_at_local", "—")}</p>
    </div>
  </div>'''

    # ── 48-urni graf temperature (glej compute_hourly_48h v winter_engine.py) ──
    hourly_svg = hourly_temp_chart_svg(data.get("hourly_48h"))
    chart_html = ""
    if hourly_svg:
        chart_html = f'''  <h2 class="zima-section-title">🌡️ Naslednjih 48 ur</h2>
  <div class="card zima-card" style="{card_style("snow_line", "")}">
    <div class="frost-chart-wrap">{hourly_svg}</div>
    <p class="muted-note" style="margin-top:.3rem">Temperatura na postaji IREICA1, urna napoved Open-Meteo.
    Navpična črta označuje trenutno uro.</p>
  </div>'''

    # ── Zimski pogoji: mreža namesto enega stolpca -- kurilni semafor
    # (zima-card-wide) zavzame celo vrstico, glej opombo uporabnika, da je bil
    # prej "osamljen" med petimi enako velikimi kartami. ──
    conditions_html = f'''  <h2 id="zimski-pogoji" class="zima-section-title">❄️ Zimski pogoji</h2>
  <div class="zima-conditions-grid">
    <div class="card zima-card" style="{card_style("snow_line", "")}">
      <div class="clabel">{icon_html("snow_line")}Meja sneženja</div>
      <p class="fh-sub">{snow_verdict}</p>
    </div>
    <div class="card zima-card" style="{card_style("black_ice", "")}">
      <div class="clabel">{icon_html("black_ice")}Poledica</div>
      <p class="fh-sub">{ice_verdict}</p>
    </div>
    <div class="card zima-card zima-card-wide" style="{card_style("heating_index", "")}">
      <div class="clabel">{icon_html("heating_index")}Kurilni semafor</div>
      <p class="fh-sub">{heating_verdict}</p>
    </div>
    <div class="card zima-card" style="{card_style("fog", "")}">
      <div class="clabel">{icon_html("fog")}Nad meglo</div>
      <p class="fh-sub">{fog_verdict}</p>
    </div>
    <div class="card zima-card" style="{card_style("snowpack", "")}">
      <div class="clabel">{icon_html("snowpack")}Snežna odeja</div>
      <p class="fh-sub">{f"Tekoča ocena na postaji: <strong>{num(station_depth, 0)} cm</strong> (modelirano, ni meritev)." if station_depth is not None else "Ocena trenutno ni na voljo."}</p>
    </div>
  </div>'''

    # ── Snežna meja kot vizualni meter (glej snow_line_meter_svg) — razlaga
    # številke iz hero/kartice grafično, ne samo kot besedilo. ──
    meter_svg = snow_line_meter_svg(line_m)
    meter_html = ""
    if meter_svg:
        meter_html = f'''  <div class="card zima-card" style="{card_style("snow_line", "")}margin-bottom:1.2rem">
    <div class="clabel">{icon_html("snow_line")}Snežna meja na lestvici</div>
    {meter_svg}
  </div>'''

    # ── Zimske ceste: bivša ena vrstica ("2 prelaza") postane pravi seznam s
    # stanjem — glej uporabnikov predlog za povečan modul prelazov. ──
    def pass_status_chip(p):
        status = p.get("status")
        if not status:
            return '<span class="zima-pass-status" style="color:var(--muted)">⚪ ni ročno preverjeno</span>'
        low = status.lower()
        if any(k in low for k in ("zaprt", "sneg", "zimsk")):
            return f'<span class="zima-pass-status" style="color:#f87171">🔴 {status}</span>'
        if any(k in low for k in ("previd", "delno", "omej")):
            return f'<span class="zima-pass-status" style="color:var(--amber)">🟡 {status}</span>'
        return f'<span class="zima-pass-status" style="color:var(--green)">🟢 {status}</span>'

    pass_rows = []
    for p in passes:
        w = p.get("weather") or {}
        weather_txt = (f'{num(w.get("temp_c"), 1)} °C · do {num(w.get("expected_snow_cm_24h"), 1)} cm snega/24h'
                       if w.get("temp_c") is not None else "vreme na tej višini ni na voljo")
        pass_rows.append(f'''    <div class="zima-pass-row">
      <div><div class="zima-pass-name">{p["name"]} ({p["elevation_m"]} m)</div>
      <div class="zima-pass-meta">{p["connects"]} · {weather_txt}</div></div>
      {pass_status_chip(p)}
    </div>''')
    passes_html = f'''  <h2 id="zimske-ceste" class="zima-section-title">🚗 Zimske ceste</h2>
  <div class="zima-passes-list">
{chr(10).join(pass_rows)}
  </div>
  <p class="muted-note">Stanje je ročno vzdrževano polje, NI uradna prometna informacija. Pred vožnjo
  preveri tudi promet.si, AMZS ali DARS.</p>
  <a class="mtn-avk-link" href="/zima/prevoznost-prelazov/">Vse podrobnosti o prelazih →</a>'''

    nav_cards = f'''  <h2 class="zima-section-title">📚 Podrobno po temah</h2>
  <div class="card-grid">
    <a class="phenom-card zima-phenom" href="/zima/meja-snezenja/" style="{card_style("snow_line", "")}">
      <span class="ph-icon">{icon_html("snow_line", 30)}</span>Meja sneženja
      <div class="ph-count">{num(line_m, 0) if line_m is not None else "—"} m n. m.</div></a>
    <a class="phenom-card zima-phenom" href="/zima/poledica/" style="{card_style("black_ice", "")}">
      <span class="ph-icon">{icon_html("black_ice", 30)}</span>Tveganje poledice
      <div class="ph-count">{RISK_ICON.get(worst_level, "⚪")} {RISK_LABEL.get(worst_level, "ni podatka")}</div></a>
    <a class="phenom-card zima-phenom" href="/zima/kurilni-semafor/" style="{card_style("heating_index", "")}">
      <span class="ph-icon">{icon_html("heating_index", 30)}</span>Kurilni semafor
      <div class="ph-count">{RISK_ICON.get(heating_level, "⚪")} {RISK_LABEL.get(heating_level, "ni podatka")}</div></a>
    <a class="phenom-card zima-phenom" href="/zima/nad-meglo/" style="{card_style("fog", "")}">
      <span class="ph-icon">{icon_html("fog", 30)}</span>Nad meglo
      <div class="ph-count">{f"~{fog['top_m']} m" if fog and fog.get("has_inversion") else "brez megle"}</div></a>
    <a class="phenom-card zima-phenom" href="/zima/snezna-odeja/" style="{card_style("snowpack", "")}">
      <span class="ph-icon">{icon_html("snowpack", 30)}</span>Snežna odeja
      <div class="ph-count">{num(station_depth, 0) + " cm" if station_depth is not None else "—"}</div></a>
    <a class="phenom-card zima-phenom" href="/zima/prevoznost-prelazov/" style="{card_style("passes", "")}">
      <span class="ph-icon">{icon_html("passes", 30)}</span>Prevoznost prelazov
      <div class="ph-count">{len(passes)} prelaza</div></a>
  </div>'''

    season = data.get("season") or {}
    season_html = ""
    if season.get("days_logged"):
        y, m, d = season["start_date"][:4], int(season["start_date"][5:7]), int(season["start_date"][8:10])
        start_fmt = f"{d}. {m}. {y}"
        # "Zima v številkah" -- glej uporabnikov predlog: štiri velike kartice
        # namesto enega stavka, isti .stat-grid/.stat-card/sc-* vzorec kot
        # black_ice_outlook zgoraj v tej datoteki in stat-card v blog.css, ne
        # nov razred. Vsi štirje šteti so DEJANSKI dnevi iz zabeleženega
        # dnevnika (glej compute_season_stats), ne modelirana ocena.
        season_html = f'''  <h2 class="zima-section-title">📊 Zima v številkah</h2>
  <p class="muted-note" style="margin-top:-.6rem">Od {start_fmt}, {season["days_logged"]} zabeleženih dni.</p>
  <div class="stat-grid">
    <div class="stat-card"><div class="sc-label">Dni z visoko inverzijo</div>
      <div class="sc-val">{season["heating_high_days"]}</div>
      <div class="sc-sub">kurilni semafor 🔴</div></div>
    <div class="stat-card"><div class="sc-label">Dni z visokim tveganjem poledice</div>
      <div class="sc-val">{season["black_ice_high_days"]}</div>
      <div class="sc-sub">vsaj en kraj v dolini</div></div>
    <div class="stat-card"><div class="sc-label">Dni s snegom na postaji</div>
      <div class="sc-val">{season["snow_days"]}</div>
      <div class="sc-sub">pričakovan sneg, IREICA1</div></div>
    <div class="stat-card"><div class="sc-label">Zabeleženih dni</div>
      <div class="sc-val">{season["days_logged"]}</div>
      <div class="sc-sub">od {start_fmt}</div></div>
  </div>'''

    faq = [
        ("Katere kraje pokriva MeteoZima?", "Rečico ob Savinji (postaja IREICA1), Mozirje, Nazarje, Ljubno ob "
         "Savinji, Gornji Grad, Luče in Solčavo — ista naselja kot na straneh »Vreme po krajih v dolini«."),
        ("Ali je to uradno opozorilo?", "Ne. Vsi indeksi so ocena Meteoreca iz javnih napovednih virov "
         "(Open-Meteo), ne uradno opozorilo ARSO. Za uradna opozorila glej "
         "<a href=\"/nevihte/\">stran opozoril</a>, za dejansko kakovost zraka pa "
         "<a href=\"/kakovost-zraka/\">/kakovost-zraka/</a>."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", None)])}
{seo.stn_badge()}
{hero_html}
{chart_html}
{conditions_html}
{meter_html}
{passes_html}
{nav_cards}
{season_html}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Podatki izhajajo iz javne napovedi Open-Meteo za postajo IREICA1 in okoliška
  naselja, brez notranjih meritev. Dejansko stanje prelazov je ročno vzdrževano polje — preveri tudi
  promet.si, AMZS ali DARS pred vožnjo.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>''', faq


# ── /zima/meja-snezenja/ ─────────────────────────────────────────────────

def build_snow_line_body(data):
    snow = data["snow_line"]
    line_m = snow.get("current_line_m")
    fc_m = snow.get("forecast_24h_m")
    conf = snow.get("confidence")

    if line_m is None:
        hero_sub = "Meja sneženja trenutno ni na voljo — poskusi znova pozneje."
    else:
        trend = ""
        if fc_m is not None and line_m is not None:
            diff = fc_m - line_m
            if abs(diff) >= 100:
                trend = f" V naslednjih 24 h se pričakuje premik na {fc_m} m ({'dvig' if diff > 0 else 'spust'})."
        # Zanesljivost prikažemo samo, kadar je meja dovolj nizko, da je sploh
        # relevantna za spremljane pasove (do 1600 m) — nad tem je "nizka
        # zanesljivost" pri 4000+ m samo zmedla bi bralca brez razloga.
        conf_txt = f" ({CONF_LABEL.get(conf, 'ocena')})" if conf and line_m <= 2000 else ""
        hero_sub = f'Trenutna meja sneženja je pri <strong>{line_m} m n. m.</strong>{conf_txt}.{trend}'

    rows = []
    for b in snow["expected_cm_by_elevation"]:
        rows.append(f'      <tr><th>{b["elevation_m"]} m n. m.</th><td>{num(b["cm"], 1)} cm v naslednjih 24 h</td></tr>')
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"

    daily = snow.get("daily") or []
    chart = daily_line_chart_svg([d["date"] for d in daily], [d["line_m"] for d in daily], unit=" m")
    chart_html = (f'  <h2>Trend meje sneženja (7 dni)</h2>\n  <div class="frost-chart-wrap">{chart}'
                   '<p class="muted-note" style="margin-top:.3rem">Nižja črta = meja sneženja se spusti niže = '
                   'sneg je verjetnejši na nižjih legah tisti dan.</p></div>' if chart else "")

    faq = [
        ("Kaj pomeni »meja sneženja«?", "To je nadmorska višina, nad katero padavine padajo kot sneg — "
         "izpeljana iz ničte izoterme (Open-Meteo), znižane za približno 200–300 m, ker se padavina ob "
         "padanju skozi zrak dodatno ohlaja. Pod to mejo pada dež, tik ob njej pa mešano."),
        ("Zakaj ni številke za konkretno goro (Golte, Menina …)?", "Ker bi bila trdna povezava številka-vrh "
         "ugibana — vrhovi v okolici se med seboj razlikujejo za stotine metrov nadmorske višine. Namesto "
         "tega tabela pokaže pričakovan sneg po višinskih pasovih; za goro nad določeno višino preberi "
         "ustrezno vrstico."),
        ("Kako natančna je ocena?", "Uporablja splošno znan sinoptičen približek (~10:1 razmerje padavine/sneg, "
         "meja sneženja ~200–300 m pod ničto izotermo), ne uradne mikrofizike padavin. Za odločitve z visokim "
         "tveganjem (gorske ture, prevoznost) preveri tudi uradno napoved ARSO."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Meja sneženja", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Meja sneženja — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("snow_line")}">
    <div class="clabel">{icon_html("snow_line")}Trenutna meja sneženja</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
  <h2>Pričakovan sneg po višinskih pasovih (naslednjih 24 h)</h2>
{table}
{chart_html}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena Meteoreca iz javne napovedi Open-Meteo, ne uradno opozorilo ARSO. Meja
  sneženja je regionalna vrednost in se znotraj dolinskega dna Zgornje Savinjske doline ne razlikuje
  pomembno med kraji — razlika je v nadmorski višini, ne v legi.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/poledica/ ──────────────────────────────────────────────────────

def build_black_ice_body(data):
    locations = data["locations"]
    worst_loc = max(locations, key=lambda l: ["nizko", "srednje", "visoko"].index(l["indices"]["black_ice"]["risk_level"]))
    worst_level = worst_loc["indices"]["black_ice"]["risk_level"]
    hero_sub = (f"V naslednjih 36 h ni povečanega tveganja poledice v dolini."
                if worst_level == "nizko" else
                f"V naslednjih 36 h je najbolj izpostavljen kraj {worst_loc['name']} — {risk_badge(worst_level)}.")
    rows = []
    for loc in locations:
        bi = loc["indices"]["black_ice"]
        hours = ", ".join(fmt_hour(h) for h in bi["risk_hours"][:4]) if bi["risk_hours"] else "—"
        detail = (f'{risk_badge(bi["risk_level"])} — cestišče ~{num(bi["ground_temp_c"], 1)} °C, '
                   f'rosišče {num(bi["dew_point_c"], 1)} °C. Ure tveganja: {hours}.'
                   if bi["ground_temp_c"] is not None else risk_badge(bi["risk_level"]))
        rows.append(f'      <tr><th>{loc["name"]} ({loc["elevation_m"]} m)</th><td>{detail}</td></tr>')
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"

    micro_items = "\n".join(f'    <li><strong>{l["name"]}:</strong> {l["microclimate"]}</li>' for l in locations)

    outlook = (data.get("black_ice_outlook") or {}).get("daily") or []
    outlook_html = ""
    if outlook:
        chips = "\n".join(
            f'    <div class="stat-card"><div class="sc-label">{fmt_day_short(d["date"])}</div>'
            f'<div class="sc-val">{RISK_ICON.get(d["level"], "⚪")}</div>'
            f'<div class="sc-sub">{RISK_LABEL.get(d["level"], "ni podatka")}</div></div>'
            for d in outlook
        )
        outlook_html = f'  <h2>7-dnevni pregled (najslabši kraj tisti dan)</h2>\n  <div class="stat-grid">\n{chips}\n  </div>'

    faq = [
        ("Je to uradno opozorilo ARSO?", "Ne. To je Meteorecov lasten kriterij (ocenjena temperatura cestišča "
         "proti rosišču, iz javne napovedi Open-Meteo) — enako poimenovana previdnostna opomba kot pri "
         "MeteoGasilcu, ne uradna prometna informacija. Za uradna opozorila in stanje cest preveri ARSO in "
         "promet.si."),
        ("Zakaj se ocena razlikuje po krajih, čeprav so si blizu?", "Ker uporablja dokumentirane mikroklimatske "
         "razlike med kraji v dolini (glej spodaj) in nadmorsko višino — ne isto številko za vso dolino."),
        ("Zakaj so mostovi posebej omenjeni?", "Mostovi in nadvozi se ohlajajo z obeh strani (zgoraj in "
         "spodaj) in zato zmrznejo prej kot cestišče na tleh — splošno znano pravilo cestne meteorologije, ne "
         "izračunano posebej za vsak most."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Poledica", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Tveganje poledice — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("black_ice")}">
    <div class="clabel">{icon_html("black_ice")}Poledica — naslednjih 36 h</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
  <h2>Ocena po krajih (naslednjih 36 h)</h2>
{table}
{outlook_html}
  <h2>Mikroklima po krajih</h2>
  <ul>
{micro_items}
  </ul>
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena upošteva samo sevalno ohlajanje cestišča (oblačnost, veter, temperatura,
  rosišče) — ne posipa, prometne obremenitve ali dejanskega stanja vozišča. Vedno preveri tudi uradna
  opozorila ARSO na <a href="/nevihte/">strani opozoril</a>.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/kurilni-semafor/ ────────────────────────────────────────────────

def build_heating_index_body(data):
    heating = data.get("heating_index") or {}
    level = heating.get("level")
    strength = heating.get("inversion_strength_c")
    wind = heating.get("wind_kmh")
    hours = ", ".join(fmt_hour(h) for h in heating.get("risk_hours", [])[:4]) if heating.get("risk_hours") else "—"

    if level is None:
        hero_sub = "Ocena trenutno ni na voljo — poskusi znova pozneje."
    else:
        hero_sub = (f'{risk_badge(level)} — {heating.get("advice", "")} '
                    f'(ocenjena jakost inverzije {num(strength, 1)} °C, veter {num(wind, 1)} km/h '
                    f'v najslabši uri). Ure z največjim tveganjem: {hours}.')

    daily = heating.get("daily") or []
    chart = daily_bar_chart_svg([d["date"] for d in daily], [d["inversion_strength_c"] for d in daily],
                                 [d["level"] for d in daily], unit="°C")
    chart_html = (f'  <h2>7-dnevni pregled jakosti inverzije</h2>\n  <div class="frost-chart-wrap">{chart}'
                   '<p class="muted-note" style="margin-top:.3rem">Višji stolpec = močnejša inverzija tisti dan '
                   '(izven poldanskih ur) — 🟢 nizko · 🟡 srednje · 🔴 visoko tveganje.</p></div>' if chart else "")

    faq = [
        ("Kaj je temperaturna inverzija?", "Stanje, ko je zrak više toplejši kot pri tleh — obrnjeno od "
         "običajnega. Topel zrak deluje kot pokrov in prepreči mešanje: dim iz dimnikov in izpušni plini "
         "ostanejo ujeti v dolini namesto da bi se razredčili navzgor."),
        ("Zakaj je pomembna za kurjenje?", "Ob močni inverziji in mirnem vetru se dim iz kurjenja slabo "
         "razprši in se v dolini kopiči — to poslabša kakovost zraka za vse. Ocena zato svetuje previdnost "
         "ali odlog kurjenja, ne prepoveduje ga."),
        ("Kako je izračunano?", "Iz primerjave temperature na postaji s temperaturo na 925/850/700 hPa "
         "(Open-Meteo) — če je više topleje, gre za inverzijo. Ta izračun je nov (v repozitoriju ni obstajal "
         "prej) in je ocena, ne uradna meritev prevetrenosti."),
        ("Ali to pove, kako onesnažen je zrak zdaj?", "Ne — za dejanske koncentracije delcev (PM10, PM2,5) "
         "in cvetni prah glej <a href=\"/kakovost-zraka/\">/kakovost-zraka/</a>. Ta stran meri samo, kako "
         "dobro se zrak giblje, ne kaj je trenutno v njem."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Kurilni semafor", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Kurilni semafor — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("heating_index")}">
    <div class="clabel">{icon_html("heating_index")}Prevetrenost za kurjenje</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
{chart_html}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena Meteoreca iz javne napovedi Open-Meteo, ne uradno opozorilo ali predpis o
  kurjenju. Za dejansko kakovost zraka glej <a href="/kakovost-zraka/">/kakovost-zraka/</a>, za uradna
  opozorila ARSO <a href="/nevihte/">stran opozoril</a>.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/nad-meglo/ ──────────────────────────────────────────────────────

def fog_ladder_html(fog):
    """Kraji, razvrščeni po nadmorski višini, s prelomno črto pri pričakovani
    meji megle — grafičen odgovor na "kje bo jutri sonce?" namesto gole
    tabele (glej uporabnikov predlog: "Nad meglo je super feature, daj mu
    več prostora"). Uporabi fog["locations"] tak, kot ga vrne compute_fog
    (postaja + NEARBY_TOWNS + HIGH_POINTS, glej winter_engine.py) — brez
    lastnega, ožjega izbora krajev."""
    if not fog or not fog.get("has_inversion"):
        return ""
    locs = sorted(fog["locations"], key=lambda l: l["elevation_m"], reverse=True)
    top = fog["top_m"]
    rows, divider_done = [], False
    for l in locs:
        if not divider_done and l["elevation_m"] <= top:
            rows.append(f'<div class="zima-fog-line">☁️ zgornja meja megle/oblačnosti — ~{top} m n. m.</div>')
            divider_done = True
        icon = "☀️" if l["above"] else "🌫️"
        cls = "" if l["above"] else " below"
        rows.append(f'<div class="zima-fog-row{cls}"><span>{icon} {l["name"]}</span>'
                     f'<span class="zima-fog-elev">{l["elevation_m"]} m</span></div>')
    if not divider_done:
        rows.append(f'<div class="zima-fog-line">☁️ zgornja meja megle/oblačnosti — ~{top} m n. m.</div>')
    return '  <div class="zima-fog-ladder">' + "".join(rows) + '</div>'


def build_fog_body(data):
    fog = data.get("fog")
    ladder = ""

    if not fog:
        hero_sub = "Ocena trenutno ni na voljo — poskusi znova pozneje."
    elif not fog.get("has_inversion"):
        hero_sub = ("Jutri zjutraj ni pričakovane pomembne temperaturne inverzije — "
                     "megla v dolini ni verjetna.")
    else:
        hero_sub = (f'{fmt_day(fog["morning_date"]).capitalize()} zjutraj je pričakovana zgornja meja '
                     f'megle/nizke oblačnosti pri približno <strong>{fog["top_m"]} m n. m.</strong>')
        ladder = ('  <h2 class="zima-section-title">☁️ Kje bo jutri sonce?</h2>\n' + fog_ladder_html(fog)
                   + f'\n  <p class="muted-note">Za dejanske razmere v gorah preveri tudi '
                     f'<a href="{seo.ARSO_MOUNTAIN_FORECAST}" rel="nofollow">uradno gorsko napoved ARSO</a>.</p>')

    daily = fog.get("daily") if fog else []
    chart = daily_line_chart_svg([d["date"] for d in (daily or [])], [d["top_m"] for d in (daily or [])], unit=" m")
    chart_html = (f'  <h2>Trend jutranje meje megle (7 dni)</h2>\n  <div class="frost-chart-wrap">{chart}'
                   '<p class="muted-note" style="margin-top:.3rem">Prekinjena črta = tisto jutro ni pričakovane '
                   'pomembne inverzije (siva pika na osnovni črti), megla torej ni verjetna.</p></div>'
                   if chart else "")

    faq = [
        ("Kaj pomeni »nad meglo«?", "Da je kraj po oceni više od pričakovane zgornje meje jutranje "
         "temperaturne inverzije — v resnični megli/nizki oblačnosti torej morda ne bi bil, ampak nad njo, "
         "na soncu."),
        ("Od kod nadmorske višine za Golte, Menino, Smrekovec in Raduho?", "Iz objavljenih/preverjenih "
         "podatkov, ki jih na strani že uporablja igra Termika (koridorji jadralnega letenja) — ne iz "
         "surovega Elevation API-ja, ki gorske vrhove napačno splošči (npr. Golte na 705 m namesto pravih "
         "~1400 m). Za dejanski pogled uporabi tudi spletno kamero na naslovni strani (napredni pogled → "
         "Zgornja Savinjska/Logarska dolina)."),
        ("Kako natančna je ocena?", "Meri temperaturno inverzijo iz regionalnega profila (Open-Meteo), ne "
         "dejanske megle — resnična megla je odvisna tudi od vlage in se lahko krajevno razlikuje. Vzemi jo "
         "kot grobo usmeritev, ne zagotovilo."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Nad meglo", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Nad meglo — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("fog")}">
    <div class="clabel">{icon_html("fog")}Jutranja megla</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
{ladder}
{chart_html}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Ocena Meteoreca iz javne napovedi Open-Meteo (temperaturni profil), ne meritev
  megle. Za živo sliko preveri spletne kamere na naslovni strani.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/snezna-odeja/ ───────────────────────────────────────────────────

def build_snowpack_body(data):
    snowpack = data.get("snowpack") or {}
    by_elev = snowpack.get("by_elevation") or []
    station_row = next((b for b in by_elev if b["elevation_m"] == seo.ELEV), None)

    if station_row is None:
        hero_sub = "Ocena trenutno ni na voljo — poskusi znova pozneje."
    else:
        hero_sub = (f'Tekoča ocena na postaji: <strong>{num(station_row["depth_cm"], 0)} cm</strong>. '
                    f'V naslednjih 7 dneh je pričakovanih še do {num(station_row["new_snow_7d_cm"], 1)} cm '
                    f'novega snega (brez upoštevanega taljenja).')

    rows = []
    for b in by_elev:
        rows.append(f'      <tr><th>{b["elevation_m"]} m n. m.</th>'
                     f'<td>{num(b["depth_cm"], 0)} cm zdaj · +{num(b["new_snow_7d_cm"], 1)} cm v 7 dneh</td></tr>')
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>"

    faq = [
        ("Ali je to izmerjena snežna odeja?", "Ne — postaja IREICA1 nima senzorja za sneg ali tla. To je "
         "TEKOČA OCENA iz poenostavljenega modela: vsak dan prišteje pričakovan nov sneg in odšteje taljenje "
         "(degree-day model — vsaka stopinja nad 0 °C stopi približno 0,6 cm snega), izračunano iz javne "
         "napovedi Open-Meteo."),
        ("Zakaj se lahko ocena čez sezono zmoti?", "Ker nima kontrolne točke (meritve), s katero bi se "
         "vsakič znova umerila — majhne napake se dan za dnem seštevajo. Najbolj zanesljiva je kmalu po "
         "sveže zapadlem snegu, manj proti koncu dolge zime brez padavin."),
        ("Zakaj je »novi sneg v 7 dneh« ločeno število od trenutne odeje?", "Ker prvo NE upošteva "
         "vmesnega taljenja (bruto pričakovana količina), drugo pa je tekoča neto ocena — sešteti v eno "
         "število bi bilo zavajajoče, če vmes pride otoplitev."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snežna odeja", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Snežna odeja — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("snowpack")}">
    <div class="clabel">{icon_html("snowpack")}Tekoča ocena snežne odeje</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
  <h2>Po višinskih pasovih</h2>
{table}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Modelirana ocena Meteoreca (degree-day model iz javne napovedi Open-Meteo), NI
  meritev — postaja nima senzorja za sneg/tla. Vzemi kot grobo usmeritev, ne natančno število.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


# ── /zima/prevoznost-prelazov/ ────────────────────────────────────────────

def build_passes_body(data):
    passes = data.get("passes") or []

    known = [(p, p["weather"]) for p in passes if (p.get("weather") or {}).get("expected_snow_cm_24h") is not None]
    if known:
        worst_pass, worst_w = max(known, key=lambda pw: pw[1]["expected_snow_cm_24h"])
        hero_sub = (f'{len(passes)} spremljana prelaza. Največ snega v naslednjih 24 h je pričakovanih na '
                    f'{worst_pass["name"]} ({worst_pass["elevation_m"]} m) — do '
                    f'{num(worst_w["expected_snow_cm_24h"], 1)} cm.')
    else:
        hero_sub = f'{len(passes)} spremljana prelaza — vreme na višini trenutno ni na voljo.'

    rows = []
    for p in passes:
        w = p.get("weather") or {}
        weather_txt = (f'{num(w.get("temp_c"), 1)} °C, pričakovanih {num(w.get("expected_snow_cm_24h"), 1)} '
                        'cm snega v 24 h' if w.get("temp_c") is not None else "ni podatka")
        if p.get("status"):
            status_txt = f'{p["status"]} (preverjeno {fmt_day(p["status_checked"])})' if p.get("status_checked") else p["status"]
        else:
            status_txt = f'ni ročno preverjeno — glej <a href="{p["source"]}">vir</a>'
        joke_link = (' · <a href="https://crnivec.si/">(neuradna varianta: kako je čez Črnivec?)</a>'
                      if p["id"] == "crnivec" else "")
        rows.append(
            f'      <tr><th>{p["name"]} ({p["elevation_m"]} m)</th>'
            f'<td>{p["connects"]}<br>Vreme na tej višini: {weather_txt}.<br>Stanje: {status_txt}.{joke_link}</td></tr>'
        )
    table = '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>" if rows else ""

    faq = [
        ("Je »stanje« uradna prometna informacija?", "Ne. Stanje je ročno vzdrževano polje (kot pri "
         "hidrantih v MeteoGasilcu) — dokler ga nihče ne preveri in vnese, stran to jasno pove, namesto da "
         "bi si izmislila »prevozno«. Za uradno stanje cest pred vožnjo preveri promet.si, AMZS ali DARS."),
        ("Kaj pomeni »vreme na tej višini«?", "Izračunana ocena (isti gradient in metoda za sneg kot na "
         "/zima/meja-snezenja/ in /zima/poledica/) — NE meritev na prelazu, ker tam ni postaje. Pove, kakšno "
         "vreme lahko pričakuješ, ne ali je cesta dejansko prevozna (sneg lahko počisti plug, poledica pa "
         "ostane kljub plusu na termometru)."),
        ("Od kod nadmorski višini in povezavi?", "S slovenske Wikipedije (Črnivec, Pavličevo sedlo) — "
         "preverjeni podatki, ne ocena. Viri so navedeni ob vsakem prelazu v tabeli."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Prevoznost prelazov", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Prevoznost prelazov — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("passes")}">
    <div class="clabel">{icon_html("passes")}Prelazi zdaj</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
{table}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Vreme na višini prelaza je ocena Meteoreca iz javne napovedi Open-Meteo — NI
  uradna prometna informacija in ne pove, ali je cesta dejansko odprta. Pred vožnjo čez prelaz vedno
  preveri promet.si, AMZS ali DARS.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>''', faq


def main():
    data = load_json(DATA_PATH)
    if not data:
        print("✗ data/winter-data.json manjka -- najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1

    # ── hub ──
    body, faq = build_hub_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/", "MeteoZima — Zgornja Savinjska dolina",
                            "MeteoZima — zimski nadzorni center: meja sneženja in tveganje poledice za "
                            "Zgornjo Savinjsko dolino, iz meritev IREICA1 in javne napovedi.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("MeteoZima — Zgornja Savinjska dolina",
                           "MeteoZima: meja sneženja in tveganje poledice za Zgornjo Savinjsko dolino, "
                           "posodobljeno dnevno.",
                           "/zima/", schema, body)
    seo.write_page("zima/index.html", html, force=True)
    print("  → zima/index.html")

    # ── meja-snezenja ──
    body, faq = build_snow_line_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/meja-snezenja/", "Meja sneženja — Zgornja Savinjska dolina",
                            "Trenutna in 24-urna napoved meje sneženja po višinskih pasovih za Zgornjo "
                            "Savinjsko dolino.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Meja sneženja", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Meja sneženja — Zgornja Savinjska dolina",
                           "Trenutna meja sneženja in pričakovan sneg po višinskih pasovih, posodobljeno dnevno.",
                           "/zima/meja-snezenja/", schema, body)
    seo.write_page("zima/meja-snezenja/index.html", html, force=True)
    print("  → zima/meja-snezenja/index.html")

    # ── poledica ──
    body, faq = build_black_ice_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/poledica/", "Tveganje poledice — Zgornja Savinjska dolina",
                            "Ocena tveganja poledice po krajih Zgornje Savinjske doline, iz meritev "
                            "IREICA1 in javne napovedi.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Poledica", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Tveganje poledice — Zgornja Savinjska dolina",
                           "Ocena tveganja poledice po krajih Zgornje Savinjske doline, posodobljeno dnevno.",
                           "/zima/poledica/", schema, body)
    seo.write_page("zima/poledica/index.html", html, force=True)
    print("  → zima/poledica/index.html")

    # ── kurilni-semafor ──
    body, faq = build_heating_index_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/kurilni-semafor/", "Kurilni semafor — Zgornja Savinjska dolina",
                            "Ocena prevetrenosti za kurjenje na podlagi temperaturne inverzije v Zgornji "
                            "Savinjski dolini.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Kurilni semafor", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Kurilni semafor — Zgornja Savinjska dolina",
                           "Ocena prevetrenosti za kurjenje (temperaturna inverzija) za Zgornjo Savinjsko "
                           "dolino, posodobljeno dnevno.",
                           "/zima/kurilni-semafor/", schema, body)
    seo.write_page("zima/kurilni-semafor/index.html", html, force=True)
    print("  → zima/kurilni-semafor/index.html")

    # ── nad-meglo ──
    body, faq = build_fog_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/nad-meglo/", "Nad meglo — Zgornja Savinjska dolina",
                            "Kateri kraji v Zgornji Savinjski dolini bodo jutri zjutraj po oceni nad "
                            "pričakovano meglo/nizko oblačnostjo.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Nad meglo", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Nad meglo — Zgornja Savinjska dolina",
                           "Ocena, kateri kraji v Zgornji Savinjski dolini bodo jutri zjutraj nad pričakovano "
                           "meglo, posodobljeno dnevno.",
                           "/zima/nad-meglo/", schema, body)
    seo.write_page("zima/nad-meglo/index.html", html, force=True)
    print("  → zima/nad-meglo/index.html")

    # ── snezna-odeja ──
    body, faq = build_snowpack_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/snezna-odeja/", "Snežna odeja — Zgornja Savinjska dolina",
                            "Tekoča modelirana ocena snežne odeje po višinskih pasovih za Zgornjo Savinjsko "
                            "dolino.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snežna odeja", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Snežna odeja — Zgornja Savinjska dolina",
                           "Tekoča modelirana ocena snežne odeje po višinskih pasovih, posodobljeno dnevno.",
                           "/zima/snezna-odeja/", schema, body)
    seo.write_page("zima/snezna-odeja/index.html", html, force=True)
    print("  → zima/snezna-odeja/index.html")

    # ── prevoznost-prelazov ──
    body, faq = build_passes_body(data)
    schema = "\n".join([
        seo.webpage_schema("/zima/prevoznost-prelazov/", "Prevoznost prelazov — Zgornja Savinjska dolina",
                            "Vreme na višini gorskih prelazov (Črnivec, Pavličevo sedlo) okoli Zgornje "
                            "Savinjske doline.",
                            date_published="2026-09-20"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Prevoznost prelazov", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Prevoznost prelazov — Zgornja Savinjska dolina",
                           "Vreme na višini gorskih prelazov okoli Zgornje Savinjske doline, posodobljeno "
                           "dnevno.",
                           "/zima/prevoznost-prelazov/", schema, body)
    seo.write_page("zima/prevoznost-prelazov/index.html", html, force=True)
    print("  → zima/prevoznost-prelazov/index.html")

    return 0


if __name__ == "__main__":
    sys.exit(main())
