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
  /zima/snezna-karta/       — karta Slovenije: sneženje po urah, meja, skupni novi sneg (JS + worker)
  /zima/poledica/           — tveganje poledice po krajih v dolini + 7-dnevni pregled
  /zima/zled/               — žled (dež, ki zmrzuje): modelski pokazatelj + sondaža ARSO + razlaga
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
import day_score_common as D  # noqa: E402 — gradnik »Opozorilo na telefon« in zapis ocen (isti kot strani »vreme za …«)

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

# Pogoji žleda — namerna podvojitev FREEZING_RAIN_* iz winter_engine.py (generatorji strani si
# ne delijo knjižnic); besedilo na strani jih navaja, preverja tools/test_freezing_rain.py.
FR_T2M, FR_WARM, FR_PRECIP, FR_HIGH = 0.0, 0.5, 0.1, 0.5
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


def snow_map_assets():
    import generate_snezna_karta_page as sk
    sk.write_assets()
    return sk.head_assets()


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
.wrap:has(.zima-card,.zx-hero){max-width:1150px}
/* Accordion vizual za FAQ (native <details>/<summary>, glej faq v vsakem
   build_*_body). SAMO tu, ne globalno v blog.css -- isti <div class="faq">
   vzorec uporabljajo desetine drugih generiranih strani in bi jih nehoteno
   spremenili. */
.wrap:has(.zima-card,.zx-hero) .faq details{background:var(--card-bg);border:1px solid var(--card-border);
  border-radius:14px;padding:.9rem 1.1rem;margin-bottom:.7rem}
.wrap:has(.zima-card,.zx-hero) .faq summary{cursor:pointer;font-weight:650;color:var(--text);
  list-style:none;display:flex;align-items:center;justify-content:space-between;gap:.6rem}
.wrap:has(.zima-card,.zx-hero) .faq summary::-webkit-details-marker{display:none}
.wrap:has(.zima-card,.zx-hero) .faq summary::after{content:"+";color:var(--cyan);font-size:1.25rem;
  font-weight:400;flex:0 0 auto;transition:transform .2s;line-height:1}
.wrap:has(.zima-card,.zx-hero) .faq details[open] summary::after{transform:rotate(45deg)}
.wrap:has(.zima-card,.zx-hero) .faq details p{margin:.6rem 0 0;color:var(--muted);font-size:.9rem;line-height:1.6}
.zima-fog-ladder{display:flex;flex-direction:column;gap:.35rem;margin:1rem 0}
.zima-fog-row{display:flex;justify-content:space-between;gap:.6rem;padding:.5rem .9rem;border-radius:10px;
  background:rgba(255,255,255,.03);border:1px solid var(--card-border);font-size:.88rem}
.zima-fog-row.below{color:var(--muted)}
.zima-fog-elev{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:var(--muted);white-space:nowrap}
.zima-fog-line{text-align:center;font-size:.76rem;color:#94a3b8;padding:.4rem 0;
  border-top:1px dashed var(--card-border);border-bottom:1px dashed var(--card-border);margin:.15rem 0}
.zh-dot{width:.6rem;height:.6rem;border-radius:50%;flex:0 0 auto;animation:zhPulse 2.2s ease-out infinite}
@keyframes zhPulse{0%{box-shadow:0 0 0 0 var(--dot-glow,rgba(148,163,184,.5))}
  70%{box-shadow:0 0 0 9px transparent}100%{box-shadow:0 0 0 0 transparent}}
@media (prefers-reduced-motion: reduce){.zh-dot{animation:none}}
.zima-section-title{display:flex;align-items:center;gap:.5rem}
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


# ── Hub /zima/: prenova 29. 10. 2026 ─────────────────────────────────────
# Kar velja (glej tudi CLAUDE.md, razdelek »MeteoZima: hub«):
#  - Brez emojijev v prikazu: ikone so risane (INDEX_ICONS/HUB_ICONS), stanje nosi barvna pika + beseda.
#  - Barve ravni so CHART_COLOR (preverjene z validate_palette.js), iste kot grafi na podstraneh -- ne uvajaj
#    druge palete za iste ravni. Raven nikoli samo z barvo: ob vsaki piki je beseda, v traku dni `title` + legenda.
#  - Prerez doline v glavi je shematski: višine v merilu, vodoravne razdalje ne (tako piše pod njim).
#  - Grafi so statični SVG v dveh različicah (namizje/telefon, preklop v CSS): en viewBox bi se na telefonu stisnil
#    in pisava bi padla pod 5 px (isto pravilo kot pri MTR grafu, glej CLAUDE.md).
#  - Temperatura in padavine sta DVA grafa na skupni časovni osi, ne ena slika z dvema osema.

WEEKDAY_SL = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]
WEEKDAY_SL_LONG = ["ponedeljek", "torek", "sreda", "četrtek", "petek", "sobota", "nedelja"]
LEVEL_WORD = {"nizko": "Nizko", "srednje": "Srednje", "visoko": "Visoko"}
HEAT_WORD = {"nizko": "Dobra prevetrenost", "srednje": "Zmerna inverzija", "visoko": "Močna inverzija"}
PRECIP_COLOR = "#60a5fa"   # en sam niz na svojem grafu (padavine), ločen od temperature
FOG_FILL = "#cbd5e1"
SNOW_CAP = "#e2e8f0"

# Ikone za seznam strani in opozorila (24×24, obris currentColor, isti jezik kot INDEX_ICONS).
HUB_ICONS = {
    "map": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M3 6.2 L9 4 L15 6.2 L21 4 V17.8 L15 20 L9 17.8 L3 20 Z" fill="currentColor" fill-opacity=".12" '
            'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
            '<path d="M9 4 V17.8 M15 6.2 V20" stroke="currentColor" stroke-width="1.4"/></svg>'),
    "zled": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
             '<path d="M12 2.8 C9.6 6.4 8 8.6 8 10.9 a4 4 0 0 0 8 0 C16 8.6 14.4 6.4 12 2.8 Z" fill="currentColor" '
             'fill-opacity=".16" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
             '<path d="M4 19 H20" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
             '<path d="M7 19 V21.5 M11 19 V22 M15 19 V21 M18 19 V21.8" stroke="currentColor" stroke-width="1.3" '
             'stroke-linecap="round"/></svg>'),
    "article": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<rect x="5" y="3" width="14" height="18" rx="2" fill="currentColor" fill-opacity=".12" '
                'stroke="currentColor" stroke-width="1.6"/>'
                '<path d="M8.5 8 H15.5 M8.5 11.5 H15.5 M8.5 15 H13" stroke="currentColor" stroke-width="1.4" '
                'stroke-linecap="round"/></svg>'),
    "peaks": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
              '<path d="M2 19.5 L8.5 9 L11.5 13.5 L15.5 6 L22 19.5 Z" fill="currentColor" fill-opacity=".13" '
              'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
              '<path d="M13.6 9.6 L15.5 6 L17.4 9.6 L16 9 L15.5 9.8 L14.8 9 Z" fill="currentColor"/></svg>'),
    "road": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
             '<path d="M8.5 21 L10.8 3 M15.5 21 L13.2 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
             '<path d="M12 5 V7.5 M12 10.5 V13.5 M12 16.5 V20" stroke="currentColor" stroke-width="1.4" '
             'stroke-linecap="round"/></svg>'),
    "bell": ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
             '<path d="M6 16.5 V11 a6 6 0 0 1 12 0 V16.5 L19.5 18.5 H4.5 Z" fill="currentColor" fill-opacity=".14" '
             'stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
             '<path d="M10 20.6 a2 2 0 0 0 4 0" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'),
}


INDEX_ICONS["zled"] = HUB_ICONS["zled"]
ZIMA_ACCENT["zled"] = "#67e8f9"


def hub_icon(key, size=22):
    svg = HUB_ICONS.get(key) or INDEX_ICONS[key].replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
    return f'<span class="zx-ico" aria-hidden="true">{svg}</span>'


def _date(iso):
    return datetime.date(int(iso[:4]), int(iso[5:7]), int(iso[8:10]))


def day_short(iso):
    """'danes', 'jutri' ali kratko ime dneva (»čet«)."""
    d = _date(iso)
    if d == TODAY:
        return "danes"
    if d == TODAY + datetime.timedelta(days=1):
        return "jutri"
    return WEEKDAY_SL[d.weekday()]


def day_long(iso):
    d = _date(iso)
    return f"{WEEKDAY_SL_LONG[d.weekday()]} {d.day}. {d.month}."


def lvl_dot(level, word=None):
    """Raven kot pika + beseda (nikoli samo barva)."""
    color = CHART_COLOR.get(level, "#64748b")
    return (f'<span class="zx-lvl" style="--lc:{color}"><i aria-hidden="true"></i>'
            f'{word or LEVEL_WORD.get(level, "ni podatka")}</span>')


def week_strip(cells, label):
    """Trak dni: cells = [(date, fill, text_or_None, title)]. Prazen seznam -> ''."""
    if not cells:
        return ""
    items = []
    for date, fill, text, title in cells:
        inner = f'<span class="zx-dv">{text}</span>' if text else ""
        style = f"background:{fill}" if fill else ""
        cls = "zx-dc" + ("" if fill else " zx-dc-none")
        items.append(f'<li title="{title}"><span class="zx-dn">{day_short(date)}</span>'
                     f'<span class="{cls}" style="{style}">{inner}</span>'
                     f'<span class="sr-only">{title}</span></li>')
    return f'<ul class="zx-week" aria-label="{label}">{"".join(items)}</ul>'


def level_cells(daily, what):
    return [(d["date"], CHART_COLOR.get(d.get("level"), None), None,
             f'{day_long(d["date"])}: {what} {d.get("level", "ni podatka")}') for d in daily or []]


def snow_line_cells(daily):
    """Meja sneženja po dnevih: nižja meja = izrazitejša modra (zaporedna lestvica ene barve)."""
    out = []
    for d in daily or []:
        m = d.get("line_m")
        if m is None:
            out.append((d["date"], None, "—", f'{day_long(d["date"])}: ni podatka'))
            continue
        a = ".14" if m >= 1700 else ".3" if m >= 1200 else ".5" if m >= 800 else ".75"
        snow = d.get("cm_at_station") or 0
        title = f'{day_long(d["date"])}: najnižja meja sneženja {m} m' + (
            f', v dolini do {num(snow, 1)} cm snega' if snow >= 0.2 else "")
        out.append((d["date"], _rgba(CHART_LINE_COLOR, a), f"{m:d}", title))
    return out


def fog_cells(daily):
    out = []
    for d in daily or []:
        top = d.get("top_m")
        if not d.get("has_inversion") or top is None:
            out.append((d["date"], None, "—", f'{day_long(d["date"])} zjutraj: brez izrazite inverzije'))
            continue
        a = ".22" if top < 500 else ".4" if top < 900 else ".62"
        out.append((d["date"], _rgba("#a78bfa", a), f"{top:d}",
                    f'{day_long(d["date"])} zjutraj: megla oziroma nizka oblačnost do približno {top} m'))
    return out


# ── Prerez doline (glava) ──────────────────────────────────────────────────
# Shematski profil: točke so izmišljene razdalje, višine pa prave (Rečica = postaja, vrhovi iz HIGH_POINTS
# v winter_engine.py, ki so ročno preverjeni). Ne riši ga kot karto.
PROFILE_RIDGE = [(0.0, 1180), (0.05, 1650), (0.09, 2062), (0.14, 1700), (0.2, 1380), (0.26, 1577), (0.32, 1150),
                 (0.38, 760), (0.44, 450), (0.5, 366), (0.56, 430), (0.62, 820), (0.69, 1400), (0.75, 1210),
                 (0.82, 1500), (0.9, 1290), (0.96, 1360), (1.0, 1240)]
PROFILE_BACK = [(0.0, 1500), (0.08, 1900), (0.18, 1650), (0.3, 1850), (0.42, 1300), (0.52, 1100), (0.62, 1350),
                (0.72, 1650), (0.85, 1700), (1.0, 1550)]
PROFILE_PEAKS = [(0.09, "Raduha", 2062), (0.26, "Smrekovec", 1577), (0.69, "Golte", 1400), (0.82, "Menina planina", 1500)]
PROFILE_Y = (200, 2300)


def valley_profile_svg(snow_line_m, fog_top_m, snow_cover_from_m, narrow=False):
    w, h = (360, 250) if narrow else (560, 300)
    pl, pr, pt, pb = (48, 8, 18, 10) if narrow else (52, 10, 22, 12)
    lo, hi = PROFILE_Y
    fs = 11 if narrow else 11.5

    def x(f):
        return pl + (w - pl - pr) * f

    def y(m):
        return pt + (h - pt - pb) * (1 - (min(max(m, lo), hi) - lo) / (hi - lo))

    def poly(pts):
        return " ".join(f"{x(f):.1f},{y(m):.1f}" for f, m in pts)

    ground = f"{x(1):.1f},{h} {x(0):.1f},{h}"
    parts = [f'<svg viewBox="0 0 {w} {h}" class="zx-prof-svg {"zx-narrow" if narrow else "zx-wide"}" role="img" '
             f'aria-labelledby="zx-prof-cap">',
             '<defs><linearGradient id="zxTerr{n}" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="#1e2b3f"/><stop offset="1" stop-color="#0a111d"/></linearGradient>'
             '<linearGradient id="zxFog{n}" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{FOG_FILL}" stop-opacity="0"/>'
             f'<stop offset=".22" stop-color="{FOG_FILL}" stop-opacity=".26"/>'
             f'<stop offset="1" stop-color="{FOG_FILL}" stop-opacity=".34"/></linearGradient>'
             '<clipPath id="zxClip{n}"><polygon points="{ridge} {ground}"/></clipPath></defs>'
             .format(n="N" if narrow else "W", ridge=poly(PROFILE_RIDGE), ground=ground)]
    # mreža višin
    for m in (500, 1000, 1500, 2000):
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y(m):.1f}" y2="{y(m):.1f}" stroke="#1a2436" stroke-width="1"/>'
                     f'<text x="{pl - 6}" y="{y(m) + 4:.1f}" text-anchor="end" font-size="{fs - 1}" fill="#8193ad">'
                     f'{m} m</text>')
    parts.append(f'<polygon points="{poly(PROFILE_BACK)} {ground}" fill="#121d30"/>')
    # megla: pas od dna do zgornje meje, nato ga teren prekrije (ostane v zraku doline)
    if fog_top_m:
        top_y = y(fog_top_m) - 10
        parts.append(f'<rect x="{pl}" y="{top_y:.1f}" width="{w - pl - pr}" height="{h - top_y:.1f}" '
                     f'fill="url(#zxFog{"N" if narrow else "W"})"/>')
    parts.append(f'<polygon points="{poly(PROFILE_RIDGE)} {ground}" fill="url(#zxTerr{"N" if narrow else "W"})" '
                 f'stroke="#3b4d68" stroke-width="1.4" stroke-linejoin="round"/>')
    if snow_cover_from_m is not None and snow_cover_from_m < hi:
        parts.append(f'<rect x="0" y="0" width="{w}" height="{y(snow_cover_from_m):.1f}" fill="{SNOW_CAP}" '
                     f'fill-opacity=".62" clip-path="url(#zxClip{"N" if narrow else "W"})"/>')
    # vrhovi
    for f, name, m in PROFILE_PEAKS:
        if narrow and name == "Smrekovec":
            continue
        lbl = name.replace(" planina", "") if narrow else name
        parts.append(f'<circle cx="{x(f):.1f}" cy="{y(m):.1f}" r="3" fill="#e2e8f0" stroke="#0b111e" stroke-width="2"/>'
                     f'<text x="{x(f):.1f}" y="{y(m) - 9:.1f}" text-anchor="middle" font-size="{fs}" '
                     f'fill="#e2e8f0" font-weight="600">{lbl}</text>'
                     f'<text x="{x(f):.1f}" y="{y(m) + 15:.1f}" text-anchor="middle" font-size="{fs - 1.5}" '
                     f'fill="#8193ad">{m} m</text>')
    # postaja na dnu doline
    sx, sy = x(0.5), y(366)
    parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4.5" fill="#22d3ee" stroke="#0b111e" stroke-width="2"/>'
                 f'<text x="{sx:.1f}" y="{sy - 10:.1f}" text-anchor="middle" font-size="{fs}" fill="#e8edf8" '
                 f'font-weight="700">Rečica 366 m</text>')
    # zgornja meja megle: napis sredi doline, kjer je zrak; ob plitvi megli (napis bi trčil v »Rečica«) desno
    if fog_top_m:
        fy = y(fog_top_m)
        if fog_top_m - 366 > 230:
            parts.append(f'<text x="{x(0.5):.1f}" y="{fy - 5:.1f}" text-anchor="middle" font-size="{fs - 0.5}" '
                         f'fill="#e2e8f0">megla jutri do ~{fog_top_m} m</text>')
        else:
            parts.append(f'<text x="{w - pr - 4}" y="{fy - 4:.1f}" text-anchor="end" font-size="{fs - 0.5}" '
                         f'fill="#e2e8f0">megla jutri do ~{fog_top_m} m</text>')
    # meja sneženja
    if snow_line_m is not None:
        above = snow_line_m > hi
        ly = y(snow_line_m) if not above else pt + 2
        parts.append(f'<line x1="{pl}" x2="{w - pr}" y1="{ly:.1f}" y2="{ly:.1f}" stroke="#e0f2fe" stroke-width="1.6" '
                     f'stroke-dasharray="6 4"/>'
                     f'<text x="{w - pr - 4}" y="{ly - 5:.1f}" text-anchor="end" font-size="{fs - 0.5}" fill="#e0f2fe" font-weight="600">'
                     f'meja sneženja {"nad " + str(hi) if above else snow_line_m} m</text>')
    parts.append("</svg>")
    # temen obris pod vsakim napisom: berljiv tudi na beli snežni odeji in na pasu megle
    return "".join(parts).replace("<text ", '<text paint-order="stroke" stroke="#0b111e" stroke-width="3" '
                                  'stroke-linejoin="round" ')


# ── 48 ur: temperatura + padavine (dva grafa, ena časovna os) ─────────────
def _hour_index(times):
    out = []
    for t in times:
        try:
            out.append(datetime.datetime.strptime(t[:16], "%Y-%m-%dT%H:%M"))
        except ValueError:
            out.append(None)
    return out


def temp48_svg(h48, narrow=False):
    times = h48.get("times") or []
    temps = h48.get("temp_c") or []
    now = h48.get("now_idx")
    n = len(times)
    known = [(i, v) for i, v in enumerate(temps) if v is not None]
    if len(known) < 2 or now is None or n < 2:
        return None
    w, h = (360, 210) if narrow else (960, 240)
    pl, pr, pt, pb = (30, 8, 26, 24) if narrow else (40, 14, 28, 26)
    fs = 11.5 if narrow else 11.5
    vals = [v for _, v in known]
    lo, hi = min(vals), max(vals)
    if lo <= 5:                       # pozimi mora biti ničla vidna, ko je blizu
        lo = min(lo, -1)
    step = 2 if hi - lo <= 12 else 5
    lo = step * (lo // step)
    hi = step * (-(-hi // step))
    if hi == lo:
        hi += step

    def x(i):
        return pl + (w - pl - pr) * i / (n - 1)

    def y(v):
        return pt + (h - pt - pb) * (1 - (v - lo) / (hi - lo))

    dts = _hour_index(times)
    p = [f'<svg viewBox="0 0 {w} {h}" class="zx-chart {"zx-narrow" if narrow else "zx-wide"}" '
         f'data-pl="{pl / w:.4f}" data-pr="{pr / w:.4f}" role="img" '
         f'aria-label="Temperatura po urah, {n} ur, od {num(min(vals), 1)} do {num(max(vals), 1)} °C">']
    v = lo
    while v <= hi + 1e-9:
        stroke = "#4b5d78" if v == 0 else "#1a2436"
        p.append(f'<line x1="{pl}" x2="{w - pr}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{stroke}" stroke-width="1"/>'
                 f'<text x="{pl - 6}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="{fs - 1}" fill="#8193ad">'
                 f'{num(v, 0)}°</text>')
        v += step
    if lo < 0 < hi:
        p.append(f'<rect x="{pl}" y="{y(0):.1f}" width="{w - pl - pr}" height="{y(lo) - y(0):.1f}" '
                 f'fill="#38bdf8" fill-opacity=".05"/>'
                 f'<text x="{w - pr - 4}" y="{y(0) + 13:.1f}" text-anchor="end" font-size="{fs - 1}" fill="#8193ad">'
                 f'pod lediščem</text>')
    # dnevi: ločnica ob polnoči, ime dneva v pasu nad grafom
    for i, dt in enumerate(dts):
        if dt is None:
            continue
        if dt.hour == 0 and 0 < i < n - 1:
            p.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{pt - 18}" y2="{h - pb}" stroke="#26344b" stroke-width="1"/>')
        every = 12 if narrow else 6
        if dt.hour % every == 0 and dt.hour != 0:
            p.append(f'<text x="{x(i):.1f}" y="{h - 7}" text-anchor="middle" font-size="{fs - 1}" fill="#8193ad">'
                     f'{dt.hour}.00</text>')
    seen = set()
    for i, dt in enumerate(dts):
        if dt is None or dt.date() in seen:
            continue
        seen.add(dt.date())
        last = max(j for j, d2 in enumerate(dts) if d2 and d2.date() == dt.date())
        if last - i < (5 if narrow else 3):
            continue
        name = day_short(dt.date().isoformat())
        if not narrow and name not in ("danes", "jutri"):
            name = WEEKDAY_SL_LONG[dt.weekday()]
        p.append(f'<text x="{x(i) + 5:.1f}" y="{pt - 8}" font-size="{fs}" fill="#cbd5e1" font-weight="600">{name}</text>')
    past = [(i, t) for i, t in known if i <= now]
    fut = [(i, t) for i, t in known if i >= now]
    if fut:
        area = " ".join(f"{x(i):.1f},{y(t):.1f}" for i, t in fut)
        p.append(f'<polygon points="{x(fut[0][0]):.1f},{h - pb} {area} {x(fut[-1][0]):.1f},{h - pb}" '
                 f'fill="{CHART_LINE_COLOR}" fill-opacity=".09"/>')
    if len(past) > 1:
        p.append(f'<polyline points="{" ".join(f"{x(i):.1f},{y(t):.1f}" for i, t in past)}" fill="none" '
                 f'stroke="{CHART_LINE_COLOR}" stroke-opacity=".4" stroke-width="2" stroke-linecap="round" '
                 f'stroke-linejoin="round"/>')
    if len(fut) > 1:
        p.append(f'<polyline class="zima-line" points="{" ".join(f"{x(i):.1f},{y(t):.1f}" for i, t in fut)}" '
                 f'fill="none" stroke="{CHART_LINE_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
    nx = x(now)
    p.append(f'<line x1="{nx:.1f}" x2="{nx:.1f}" y1="{pt}" y2="{h - pb}" stroke="#94a3b8" stroke-width="1" '
             f'stroke-dasharray="3 3"/><text x="{nx + 4:.1f}" y="{pt + 11}" font-size="{fs - 1}" fill="#cbd5e1" '
             f'font-weight="600">zdaj</text>')
    # neposredni oznaki: najnižja in najvišja napovedana vrednost
    if fut:
        for (i, t), tag in ((min(fut, key=lambda a: a[1]), "min"), (max(fut, key=lambda a: a[1]), "max")):
            ty = y(t) + (16 if tag == "min" else -9)
            anchor = "end" if x(i) > w - 60 else "start" if x(i) < pl + 40 else "middle"
            p.append(f'<circle cx="{x(i):.1f}" cy="{y(t):.1f}" r="4" fill="{CHART_LINE_COLOR}" stroke="#0b111e" '
                     f'stroke-width="2"/><text x="{x(i):.1f}" y="{ty:.1f}" text-anchor="{anchor}" font-size="{fs}" '
                     f'fill="#e8edf8" font-weight="700">{num(t, 1)} °C</text>')
    p.append("</svg>")
    return "".join(p)


def precip48_svg(h48, narrow=False):
    times = h48.get("times") or []
    pr_ = h48.get("precip_mm") or []
    n = len(times)
    if n < 2 or not any((v or 0) > 0 for v in pr_):
        return None
    w, h = (360, 64) if narrow else (960, 70)
    pl, pr, pt, pb = (30, 8, 14, 6) if narrow else (40, 14, 14, 6)
    top = max(1.0, max(v or 0 for v in pr_))
    slot = (w - pl - pr) / (n - 1)
    bw = max(1.5, min(24, slot - 2))
    p = [f'<svg viewBox="0 0 {w} {h}" class="zx-chart zx-precip {"zx-narrow" if narrow else "zx-wide"}" '
         f'role="img" aria-label="Padavine po urah, največ {num(max(v or 0 for v in pr_), 1)} mm na uro">',
         f'<line x1="{pl}" x2="{w - pr}" y1="{h - pb}" y2="{h - pb}" stroke="#26344b" stroke-width="1"/>']
    best = max(range(n), key=lambda i: pr_[i] or 0)
    for i, v in enumerate(pr_):
        if not v:
            continue
        bh = max(1.5, (h - pt - pb) * v / top)
        cx = pl + slot * i
        p.append(f'<rect x="{cx - bw / 2:.1f}" y="{h - pb - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="1.5" '
                 f'fill="{PRECIP_COLOR}"><title>{times[i][11:13]}.00: {num(v, 1)} mm</title></rect>')
    bx = pl + slot * best
    p.append(f'<text x="{bx:.1f}" y="{pt - 3}" text-anchor="{"end" if bx > w - 60 else "middle"}" font-size="11" '
             f'fill="#cbd5e1">{num(pr_[best], 1)} mm</text></svg>')
    return "".join(p)


HUB_JS = r"""<script>(function(){
  var fig=document.querySelector('.zx-48');if(!fig)return;
  var T=JSON.parse(fig.getAttribute('data-times')),V=JSON.parse(fig.getAttribute('data-t')),P=JSON.parse(fig.getAttribute('data-p'));
  var plot=fig.querySelector('.zx-48-plot'),tip=fig.querySelector('.zx-tip'),bar=fig.querySelector('.zx-cross');
  var D=['ned','pon','tor','sre','čet','pet','sob'];
  function svg(){var s=plot.querySelectorAll('svg.zx-chart:not(.zx-precip)');for(var i=0;i<s.length;i++)if(s[i].getBoundingClientRect().width>0)return s[i];return null;}
  function f1(x){return (Math.round(x*10)/10).toFixed(1).replace('.',',');}
  function show(e){var s=svg();if(!s)return;var r=s.getBoundingClientRect(),pr=plot.getBoundingClientRect();
    var pl=+s.getAttribute('data-pl')*r.width,prr=+s.getAttribute('data-pr')*r.width,w=r.width-pl-prr;
    var f=(e.clientX-r.left-pl)/w;if(f<0||f>1){hide();return;}
    var i=Math.round(f*(T.length-1)),t=T[i],d=new Date(t+':00');
    var x=r.left-pr.left+pl+w*i/(T.length-1);
    bar.style.left=x+'px';bar.hidden=false;
    tip.innerHTML='';var b=document.createElement('b');b.textContent=D[d.getDay()]+' '+d.getHours()+'.00';tip.appendChild(b);
    var l1=document.createElement('span');l1.textContent=V[i]==null?'ni podatka':f1(V[i])+' °C';tip.appendChild(l1);
    var l2=document.createElement('span');l2.textContent='padavine '+f1(P[i]||0)+' mm';tip.appendChild(l2);
    tip.hidden=false;var tw=tip.offsetWidth;tip.style.left=Math.max(0,Math.min(pr.width-tw,x-tw/2))+'px';}
  function hide(){tip.hidden=true;bar.hidden=true;}
  plot.addEventListener('pointermove',show);plot.addEventListener('pointerdown',show);plot.addEventListener('pointerleave',hide);
})();</script>"""


HUB_CSS = """<style>
.zx-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:1.6rem;align-items:center;
  background:radial-gradient(120% 90% at 85% 0%,rgba(56,189,248,.10),transparent 60%),var(--card-bg);
  border:1px solid var(--card-border);border-radius:22px;padding:1.9rem 2rem 1.6rem;margin:1rem 0 2.2rem;box-shadow:var(--card-shadow)}
.zx-kicker{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:#7dd3fc;margin:0 0 .5rem}
.zx-hero .page-title{margin:0 0 1rem;font-size:clamp(1.9rem,4.2vw,2.7rem);line-height:1.08;letter-spacing:-.01em}
.zx-status{display:inline-flex;align-items:center;gap:.55rem;padding:.38rem .8rem .38rem .65rem;border-radius:999px;
  background:rgba(255,255,255,.05);border:1px solid var(--card-border);font-weight:700;font-size:.82rem;letter-spacing:.02em;margin:0 0 .85rem}
.zx-status .zh-dot{background:var(--lc);--dot-glow:color-mix(in srgb,var(--lc) 55%,transparent)}
.zx-verdict{font-size:1.08rem;line-height:1.6;margin:0 0 1.1rem;color:var(--text);max-width:34rem}
.zx-updated{font-size:.8rem;color:var(--muted);margin:0 0 1.1rem}
.zx-jump{display:flex;flex-wrap:wrap;gap:.45rem}
.zx-jump a{font-size:.8rem;font-weight:650;color:var(--text);text-decoration:none;padding:.42rem .8rem;border-radius:999px;
  border:1px solid var(--card-border);background:rgba(255,255,255,.03);transition:border-color .18s,color .18s}
.zx-jump a:hover{border-color:var(--cyan);color:var(--cyan)}
.zx-prof{margin:0}
.zx-prof-svg{width:100%;height:auto;display:block}
.zx-prof figcaption{display:flex;flex-wrap:wrap;gap:.35rem 1rem;font-size:.75rem;color:var(--muted);margin-top:.55rem}
.zx-key{display:inline-flex;align-items:center;gap:.4rem}
.zx-key i{display:inline-block;width:18px;height:10px;border-radius:2px}
.zx-key .k-line{height:0;border-top:2px dashed #e0f2fe;border-radius:0}
.zx-key .k-fog{background:rgba(203,213,225,.35)}
.zx-key .k-snow{background:#e2e8f0}
.zx-key .k-stn{width:10px;height:10px;border-radius:50%;background:#22d3ee}
.zx-note{flex-basis:100%;font-size:.72rem;opacity:.85}
svg.zx-narrow{display:none}
@media (max-width:640px){svg.zx-wide{display:none}svg.zx-narrow{display:block}}
.zx-sec{margin:2.4rem 0 1rem;scroll-margin-top:1rem}
.zx-sec h2{margin:0 0 .25rem;font-size:1.45rem}
.zx-sec p{margin:0;color:var(--muted);font-size:.9rem;line-height:1.55}
.zx-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}
.zx-card{position:relative;display:flex;flex-direction:column;gap:.55rem;text-decoration:none;color:inherit;
  background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px;padding:1.05rem 1.15rem 1.1rem;
  overflow:hidden;transition:border-color .18s,transform .18s}
.zx-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--fa)}
.zx-card:hover{border-color:var(--fa);transform:translateY(-2px)}
.zx-card-head{display:flex;align-items:center;gap:.6rem;font-weight:700;font-size:.95rem}
.zx-card-head .zima-icon{margin:0;vertical-align:0}
.zx-go{margin-left:auto;color:var(--muted);font-weight:400;transition:color .18s,transform .18s}
.zx-card:hover .zx-go{color:var(--fa);transform:translateX(2px)}
.zx-val{font-family:'Space Grotesk',sans-serif;font-weight:800;font-size:1.65rem;line-height:1.1;color:#fff}
.zx-val small{font-family:Inter,sans-serif;font-size:.78rem;font-weight:500;color:var(--muted);margin-left:.35rem}
.zx-lvl{display:inline-flex;align-items:center;gap:.5rem}
.zx-lvl i{width:.7rem;height:.7rem;border-radius:50%;background:var(--lc);box-shadow:0 0 0 3px color-mix(in srgb,var(--lc) 22%,transparent)}
.zx-card p{margin:0;font-size:.88rem;line-height:1.55;color:var(--muted)}
.zx-week{list-style:none;margin:auto 0 0;padding:.55rem 0 0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}
.zx-week li{display:flex;flex-direction:column;align-items:stretch;gap:3px;min-width:0}
.zx-dn{font-size:.62rem;color:var(--muted);text-align:center;white-space:nowrap;overflow:hidden;text-overflow:clip}
.zx-dc{display:flex;align-items:center;justify-content:center;height:22px;border-radius:4px}
.zx-dc-none{background:transparent;border:1px dashed #26344b}
.zx-dv{font-family:'JetBrains Mono',monospace;font-size:.6rem;color:#e8edf8;letter-spacing:-.02em}
.zx-dc-none .zx-dv{color:#64748b}
.zx-bands{display:grid;gap:5px;margin:auto 0 0;padding-top:.4rem}
.zx-band{display:grid;grid-template-columns:3.6rem 1fr 3.2rem;align-items:center;gap:.5rem;font-size:.72rem;color:var(--muted)}
.zx-band b{font-family:'JetBrains Mono',monospace;font-weight:500;color:var(--text);text-align:right}
.zx-bar{height:8px;border-radius:4px;background:#141d2c;overflow:hidden}
.zx-bar i{display:block;height:100%;background:#e2e8f0;border-radius:4px}
.zx-legend{display:flex;flex-wrap:wrap;gap:.4rem 1.1rem;font-size:.76rem;color:var(--muted);margin:.85rem 0 0}
.zx-legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:.4rem;vertical-align:-1px}
.zx-48{position:relative;background:var(--card-bg);border:1px solid var(--card-border);border-radius:16px;padding:1rem 1rem .9rem;margin:0}
.zx-48-plot{position:relative;touch-action:pan-y;cursor:crosshair}
.zx-chart{width:100%;height:auto;display:block}
.zx-precip{margin-top:.2rem}
.zx-48-lbl{font-size:.72rem;color:var(--muted);margin:.7rem 0 0 .2rem}
.zx-tip[hidden],.zx-cross[hidden]{display:none}
.zx-cross{position:absolute;top:0;bottom:0;width:1px;background:rgba(226,232,240,.45);pointer-events:none}
.zx-tip{position:absolute;top:.1rem;display:flex;flex-direction:column;gap:.1rem;
  background:#111a2b;border:1px solid #2a3a55;border-radius:10px;padding:.45rem .65rem;font-size:.78rem;color:var(--text);
  pointer-events:none;white-space:nowrap;box-shadow:0 8px 24px rgba(0,0,0,.45);z-index:3}
.zx-tip b{font-size:.72rem;color:#7dd3fc}
.zx-48 figcaption{font-size:.78rem;color:var(--muted);margin:.6rem .2rem 0;line-height:1.5}
.zx-passes{display:grid;gap:.7rem}
.zx-pass{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1.5fr) auto;align-items:center;gap:1rem;
  background:var(--card-bg);border:1px solid var(--card-border);border-radius:14px;padding:.9rem 1.15rem}
.zx-pass-name{font-weight:700;font-size:1rem}
.zx-pass-name span{font-family:'JetBrains Mono',monospace;font-size:.78rem;font-weight:500;color:var(--muted);margin-left:.35rem}
.zx-pass-meta{font-size:.78rem;color:var(--muted);margin-top:.15rem}
.zx-chips{display:flex;flex-wrap:wrap;gap:.4rem}
.zx-chip{display:inline-flex;align-items:center;gap:.4rem;font-size:.78rem;padding:.3rem .6rem;border-radius:8px;
  background:rgba(255,255,255,.04);border:1px solid var(--card-border);white-space:nowrap}
.zx-chip .zx-lvl i{width:.55rem;height:.55rem}
.zx-pass-side{display:flex;flex-direction:column;align-items:flex-end;gap:.25rem;font-size:.76rem;color:var(--muted);text-align:right}
.zx-pass-side a{color:var(--cyan);font-weight:650;text-decoration:none}
.zx-pass-side a:hover{text-decoration:underline}
.zx-more{display:inline-flex;margin-top:.8rem;font-size:.85rem;font-weight:650;color:var(--cyan);text-decoration:none}
.zx-more:hover{text-decoration:underline}
.zx-alerts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.8rem}
.zx-alert{display:flex;flex-direction:column;gap:.45rem;text-decoration:none;color:inherit;background:var(--card-bg);
  border:1px solid var(--card-border);border-radius:14px;padding:.95rem 1rem;transition:border-color .18s}
.zx-alert:hover{border-color:var(--fa)}
.zx-alert b{display:flex;align-items:center;gap:.55rem;font-size:.92rem}
.zx-alert b .zima-icon{margin:0;width:1.9rem;height:1.9rem;vertical-align:0}
.zx-alert span{font-size:.8rem;color:var(--muted);line-height:1.45}
.zx-alert em{font-style:normal;font-size:.8rem;font-weight:650;color:var(--fa);margin-top:auto}
.zx-links{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:.6rem}
.zx-link{display:flex;align-items:center;gap:.8rem;text-decoration:none;color:inherit;padding:.75rem .9rem;border-radius:12px;
  border:1px solid var(--card-border);background:rgba(255,255,255,.02);transition:border-color .18s,background .18s}
.zx-link:hover{border-color:rgba(34,211,238,.45);background:rgba(34,211,238,.04)}
.zx-ico{display:inline-flex;align-items:center;justify-content:center;width:2.2rem;height:2.2rem;flex:0 0 auto;border-radius:10px;
  background:rgba(125,211,252,.1);color:#7dd3fc}
.zx-link b{display:block;font-size:.9rem}
.zx-link small{display:block;font-size:.76rem;color:var(--muted);margin-top:.1rem}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media (max-width:980px){.zx-cards{grid-template-columns:repeat(2,minmax(0,1fr))}.zx-alerts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:860px){.zx-hero{grid-template-columns:1fr;padding:1.4rem 1.2rem 1.2rem;gap:1.2rem}
  .zx-pass{grid-template-columns:1fr}.zx-pass-side{align-items:flex-start;text-align:left}}
@media (max-width:620px){.zx-cards{grid-template-columns:1fr}}
@media (max-width:420px){.zx-alerts{grid-template-columns:1fr}.zx-hero{border-radius:18px}}
@media (prefers-reduced-motion: reduce){.zx-card,.zx-go{transition:none}.zx-card:hover{transform:none}}
</style>"""


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

    heating = data.get("heating_index") or {}
    heating_level = heating.get("level")
    zled = data.get("freezing_rain") or {}
    zled_level = zled.get("level")
    fog = data.get("fog")
    fog_top = fog["top_m"] if fog and fog.get("has_inversion") else None
    snowpack = data.get("snowpack") or {}
    bands = snowpack.get("by_elevation") or []
    station_depth = next((b["depth_cm"] for b in bands if b["elevation_m"] == seo.ELEV), None)
    snow_from = next((b["elevation_m"] for b in sorted(bands, key=lambda b: b["elevation_m"]) if (b["depth_cm"] or 0) > 0), None)
    passes = data.get("passes") or []

    # ── Glavno stanje: snežna odeja prevlada (dejstvo modela, ne ocena tveganja), sicer najslabši od
    # poledice/kurjenja. Kadar kurilni semafor edini preseže poledico, glava govori o prevetrenosti, ne o
    # »zimskem tveganju« (opomba uporabnika 22. 9. 2026; isto načelo kot »primernost, ne tveganje« pri agrometeu).
    ice_rank = RANK_ORDER.index(worst_level)
    heat_rank = RANK_ORDER.index(heating_level) if heating_level in RANK_ORDER else -1
    overall_rank = max(ice_rank, heat_rank)
    overall_level = RANK_ORDER[overall_rank] if overall_rank >= 0 else None
    heating_only = heat_rank > ice_rank
    if station_depth:
        status_color, label = "#e2e8f0", "Snežna odeja v dolini"
        verdict = (f"V dolini po oceni leži <strong>{num(station_depth, 0)} cm</strong> snežne odeje "
                   f"(modelirano, ni meritev).")
    elif heating_only and overall_level in ("visoko", "srednje"):
        status_color = CHART_COLOR[overall_level]
        label = "Slaba prevetrenost doline" if overall_level == "visoko" else "Zmerna prevetrenost doline"
        verdict = heating.get("advice") or "Ocena kurilnega semaforja trenutno ni na voljo."
    elif overall_level == "visoko":
        status_color, label = CHART_COLOR["visoko"], "Povečano zimsko tveganje"
        verdict = "Vsaj eden od zimskih kazalnikov je danes na visoki stopnji. Kateri, pokažejo kartice spodaj."
    elif overall_level == "srednje":
        status_color, label = CHART_COLOR["srednje"], "Delno zimsko tveganje"
        verdict = "Vsaj eden od zimskih kazalnikov je danes na srednji stopnji. Kateri, pokažejo kartice spodaj."
    else:
        status_color, label = CHART_COLOR["nizko"], "Brez zimskih razmer"
        verdict = snow_verdict

    fig_keys = ['<span class="zx-key"><i class="k-stn"></i>postaja IREICA1</span>']
    if line_m is not None:
        fig_keys.append('<span class="zx-key"><i class="k-line"></i>meja sneženja danes</span>')
    if fog_top:
        fig_keys.append('<span class="zx-key"><i class="k-fog"></i>megla jutri zjutraj</span>')
    if snow_from is not None:
        fig_keys.append('<span class="zx-key"><i class="k-snow"></i>snežna odeja (ocena)</span>')
    hero_html = f'''  <section class="zx-hero">
    <div>
      <p class="zx-kicker">MeteoZima · Zgornja Savinjska dolina</p>
      <h1 class="page-title">Zimski nadzorni center</h1>
      <p class="zx-status" style="--lc:{status_color}"><span class="zh-dot"></span>{label}</p>
      <p class="zx-verdict">{verdict}</p>
      <p class="zx-updated">Posodobljeno {data.get("generated_at_local", "—")} · ocena iz napovedi Open-Meteo, ne meritev</p>
      <nav class="zx-jump" aria-label="Na tej strani">
        <a href="#razmere">Razmere</a><a href="#48-ur">48 ur</a><a href="#snezna-karta">Snežna karta</a>
        <a href="#zimske-ceste">Ceste</a><a href="#opozorila">Opozorila na telefon</a>
      </nav>
    </div>
    <figure class="zx-prof">
      {valley_profile_svg(line_m, fog_top, snow_from)}
      {valley_profile_svg(line_m, fog_top, snow_from, narrow=True)}
      <figcaption id="zx-prof-cap">{"".join(fig_keys)}
        <span class="zx-note">Shematski prerez doline: višine so v merilu, vodoravne razdalje niso.</span></figcaption>
    </figure>
  </section>'''

    # ── Razmere: šest enakih kartic, vsaka z vrednostjo, stavkom in trakom dni ──
    def card(key, href, title, value, text, foot, extra_cls=""):
        return (f'    <a class="zx-card{extra_cls}" href="{href}" style="{card_style(key, "")}">\n'
                f'      <div class="zx-card-head">{icon_html(key, 22)}{title}<span class="zx-go" aria-hidden="true">→</span></div>\n'
                f'      <div class="zx-val">{value}</div>\n      <p>{text}</p>\n      {foot}\n    </a>')

    ice_text = ("V dolini ni povečanega tveganja." if worst_level == "nizko"
                else f"Najbolj izpostavljen kraj: {worst_loc['name']}. Previdno na mostovih in v senci.")
    zled_hours = zled.get("hours") or []
    zled_text = ("Model ne kaže dežja, ki bi zmrzoval." if zled_level in (None, "nizko") or not zled_hours
                 else f"Možen v {len(zled_hours)} urah, prvič {fmt_hour(zled_hours[0])}.")
    if fog_top:
        peaks = [l["name"] for l in fog["locations"] if l["above"] and l["elevation_m"] >= 1000]
        fog_val, fog_text = (f"do ~{fog_top} m<small>jutri zjutraj</small>",
                             (f"Nad meglo: {', '.join(peaks)}." if peaks else "Megla bo segala nad spremljane vrhove."))
    else:
        fog_val, fog_text = ("Brez megle<small>jutri zjutraj</small>",
                             "Izrazite inverzije ni, megla v dolini ni verjetna.")
    maxd = max([b["depth_cm"] or 0 for b in bands] + [1])
    band_rows = "".join(
        f'<div class="zx-band"><span class="zx-bl">{b["elevation_m"]} m</span>'
        f'<span class="zx-bar"><i style="width:{100 * (b["depth_cm"] or 0) / maxd:.0f}%"></i></span><b>{num(b["depth_cm"], 0)} cm</b></div>'
        for b in bands)
    pack_text = ("Na nobeni spremljani višini ni ocenjene snežne odeje." if not snow_from
                 else f"Snežna odeja od približno {snow_from} m navzgor.")
    cards = [
        card("snow_line", "/zima/meja-snezenja/", "Meja sneženja",
             f"{num(line_m, 0)} m<small>danes</small>" if line_m is not None else "—",
             snow_verdict.split(" — ")[-1].capitalize() if " — " in snow_verdict else snow_verdict,
             week_strip(snow_line_cells(snow.get("daily")), "Najnižja meja sneženja po dnevih")),
        card("black_ice", "/zima/poledica/", "Poledica",
             f'{lvl_dot(worst_level)}<small>36 h</small>', ice_text,
             week_strip(level_cells((data.get("black_ice_outlook") or {}).get("daily"), "poledica"),
                        "Tveganje poledice po dnevih")),
        card("zled", "/zima/zled/", "Žled",
             f'{lvl_dot(zled_level)}<small>48 h</small>', zled_text,
             week_strip(level_cells(zled.get("daily"), "žled"), "Pokazatelj žleda po dnevih")),
        card("heating_index", "/zima/kurilni-semafor/", "Kurilni semafor",
             lvl_dot(heating_level, HEAT_WORD.get(heating_level)),
             "Zrak se dobro prevetri." if heating_level == "nizko"
             else ((heating.get("advice") or "Ocena ni na voljo.").split(" — ", 1)[-1].capitalize()),
             week_strip(level_cells(heating.get("daily"), "inverzija"), "Kurilni semafor po dnevih")),
        card("fog", "/zima/nad-meglo/", "Nad meglo", fog_val, fog_text,
             week_strip(fog_cells((fog or {}).get("daily")), "Zgornja meja jutranje megle po dnevih")),
        card("snowpack", "/zima/snezna-odeja/", "Snežna odeja",
             f'{num(station_depth, 0)} cm<small>v dolini</small>' if station_depth is not None else "—",
             pack_text, f'<div class="zx-bands" aria-label="Snežna odeja po višinah">{band_rows}</div>'),
    ]
    legend = "".join(f'<span><i style="background:{CHART_COLOR[k]}"></i>{LEVEL_WORD[k].lower()}</span>' for k in RANK_ORDER)
    conditions_html = f'''  <div class="zx-sec" id="razmere"><h2>Razmere v dolini</h2>
    <p>Ocena za danes in trak za naslednjih sedem dni. Kartica vodi na podrobno stran.</p></div>
  <div class="zx-cards">
{chr(10).join(cards)}
  </div>
  <div class="zx-legend" aria-label="Legenda ravni">{legend}<span><i style="background:{_rgba(CHART_LINE_COLOR, ".5")}"></i>meja sneženja, megla: izrazitejše = nižje</span></div>'''

    # ── 48 ur ──
    h48 = data.get("hourly_48h") or {}
    tw, tn = temp48_svg(h48), temp48_svg(h48, narrow=True)
    chart_html = ""
    if tw:
        pw, pn = precip48_svg(h48), precip48_svg(h48, narrow=True)
        precip_html = (f'<div class="zx-48-lbl">Padavine po urah (mm)</div>{pw}{pn}' if pw
                       else '<div class="zx-48-lbl">V tem obdobju model ne napoveduje padavin.</div>')
        chart_html = f'''  <div class="zx-sec" id="48-ur"><h2>Naslednjih 48 ur</h2>
    <p>Temperatura in padavine za Rečico po urni napovedi. Dotaknite se grafa za vrednost ob uri.</p></div>
  <figure class="zx-48" data-times='{json.dumps(h48.get("times") or [])}' data-t='{json.dumps(h48.get("temp_c") or [])}' data-p='{json.dumps(h48.get("precip_mm") or [])}'>
    <div class="zx-48-plot">{tw}{tn}{precip_html}<div class="zx-cross" hidden></div><div class="zx-tip" hidden></div></div>
    <figcaption>Napoved Open-Meteo za postajo IREICA1. Bledi del črte je preteklih nekaj ur, črtkana navpičnica je trenutna ura.</figcaption>
  </figure>'''

    snow_map_html = '''  <div class="zx-sec" id="snezna-karta"><h2>Snežna karta Slovenije</h2>
    <p>Sneženje, meja sneženja in skupni novi sneg do +48 ur (model ICON-D2, ne uradna napoved).</p></div>
  <div id="sk-app" data-compact="1" data-view="s" data-hours="24" aria-live="polite">Nalagam snežno karto …</div>'''

    # ── Ceste ──
    pass_rows = []
    for p in passes:
        w = p.get("weather") or {}
        chips = []
        if w.get("temp_c") is not None:
            chips.append(f'<span class="zx-chip">{num(w["temp_c"], 0)} °C</span>')
            chips.append(f'<span class="zx-chip">sneg 24 h: {num(w.get("expected_snow_cm_24h"), 0)} cm</span>')
        ice = (w.get("now") or {}).get("black_ice")
        if ice:
            chips.append(f'<span class="zx-chip">poledica {lvl_dot(ice, LEVEL_WORD[ice].lower())}</span>')
        status = p.get("status")
        side = (f'<span>stanje: {status}</span>' if status else '<span>stanje ceste ni ročno preverjeno</span>')
        if p["id"] == "crnivec":
            side += '<a href="https://crnivec.si/">kamera in meritve →</a>'
        pass_rows.append(f'''    <div class="zx-pass">
      <div><div class="zx-pass-name">{p["name"]}<span>{p["elevation_m"]} m</span></div>
        <div class="zx-pass-meta">{p["connects"]}</div></div>
      <div class="zx-chips">{"".join(chips) or '<span class="zx-chip">vreme na tej višini ni na voljo</span>'}</div>
      <div class="zx-pass-side">{side}</div>
    </div>''')
    passes_html = f'''  <div class="zx-sec" id="zimske-ceste"><h2>Zimske ceste in prelazi</h2>
    <p>Vreme na višini prelaza je ocena modela, ni uradna prometna informacija. Pred vožnjo preverite promet.si, AMZS ali DARS.</p></div>
  <div class="zx-passes">
{chr(10).join(pass_rows)}
  </div>
  <a class="zx-more" href="/zima/prevoznost-prelazov/">Vse o prelazih →</a>'''

    links = [
        ("map", "/zima/snezna-karta/", "Snežna karta", "sneženje po urah, +48 ur"),
        ("peaks", "/vreme-v-gorah/", "Vreme v gorah", "Golte, Menina, Smrekovec, Raduha"),
        ("road", "https://crnivec.si/", "Črnivec in Lipa", "kamera, meritve DRSI, vozišče"),
        ("passes", "/zima/prevoznost-prelazov/", "Prevoznost prelazov", prelazi_n(len(passes))),
        ("zled", "/zima/zled/", "Žled", "kdaj dež zmrzuje"),
        ("article", "/blog/zima-2026-2027-el-nino-napoved.html", "Zima 2026/27", "El Niño: kaj čaka dolino"),
    ]
    links_html = "".join(f'<a class="zx-link" href="{u}">{hub_icon(k)}<span><b>{t}</b><small>{d}</small></span></a>'
                         for k, u, t, d in links)
    topics_html = f'''  <div class="zx-sec"><h2>Še več o zimi</h2></div>
  <div class="zx-links">{links_html}</div>'''

    season = data.get("season") or {}
    season_html = ""
    if season.get("days_logged"):
        y, m, d = season["start_date"][:4], int(season["start_date"][5:7]), int(season["start_date"][8:10])
        start_fmt = f"{d}. {m}. {y}"
        # Štirje šteti so dejanski dnevi iz zabeleženega dnevnika (compute_season_stats), ne modelirana ocena.
        season_html = f'''  <div class="zx-sec"><h2>Zima v številkah</h2>
    <p>Od {start_fmt}, {season["days_logged"]} zabeleženih dni.</p></div>
  <div class="stat-grid">
    <div class="stat-card"><div class="sc-label">Dni z visoko inverzijo</div>
      <div class="sc-val">{season["heating_high_days"]}</div>
      <div class="sc-sub">kurilni semafor: visoko</div></div>
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

    return f'''{BRAND_SWAP}{ZIMA_CSS}{HUB_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", None)])}
{hero_html}
{conditions_html}
{chart_html}
{snow_map_html}
{passes_html}
{hub_alerts_html()}
{season_html}
{topics_html}
  <div class="zx-sec"><h2>Pogosta vprašanja</h2></div>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Podatki izhajajo iz javne napovedi Open-Meteo za postajo IREICA1 in okoliška
  naselja, brez notranjih meritev. Dejansko stanje prelazov je ročno vzdrževano polje — preveri tudi
  promet.si, AMZS ali DARS pred vožnjo.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
{HUB_JS}''', faq


# ── Zimska opozorila na telefon ───────────────────────────────────────────
# Isti mehanizem kot »Opozorila po ocenah« na straneh »vreme za …« (worker.js, _cronCheckOcene): obiskovalec si sam nastavi
# raven in dan, worker pa dnevne ocene prebere iz datoteke, ki jo piše Python. Ločena datoteka (ne data/vsakdan-ocene.json),
# ker jo piše zima-forecast.yml, vsakdan-forecast.yml pa svojo -- dva workflowa v isti datoteki sta se že enkrat tepla
# (astma-forecast.yml). Ocene računa Python, worker jih samo bere. Modelska napoved, ne uradno opozorilo.
ZIMA_OCENE_FILE = os.path.join(seo.ROOT, "data", "zima-ocene.json")
SNEG_LEVELS = ["brez snega", "do 1 cm", "1–5 cm", "več kot 5 cm"]
SNEG_CM_BANDS = (0.2, 1.0, 5.0)           # spodnje meje ravni 1, 2, 3 (cm novega snega v dolini v enem dnevu)
MEGLA_LEVELS = ["brez inverzije", "nizka (do 500 m)", "srednja (500–900 m)", "visoka (nad 900 m)"]
MEGLA_TOP_BANDS = (500, 900)              # zgornja meja inverzije: pod 500 m, 500–900 m, nad 900 m
HAZARD_LEVELS = ["nizko", "srednje", "visoko"]
ZIMA_ALERTS = {
    "zima-poledica": {"short": "Poledica", "url": "/zima/poledica/", "levels": HAZARD_LEVELS,
                       "opts": [("ge1", "srednje ali visoko"), ("ge2", "visoko")]},
    "zima-sneg": {"short": "Sneg v dolini", "url": "/zima/meja-snezenja/", "levels": SNEG_LEVELS,
                   "opts": [("ge1", "kakršen koli sneg (od 0,2 cm)"), ("ge2", "1 cm ali več"), ("ge3", "več kot 5 cm")]},
    "zima-zled": {"short": "Žled", "url": "/zima/zled/", "levels": HAZARD_LEVELS,
                   "opts": [("ge1", "srednje ali visoko"), ("ge2", "visoko")]},
    "zima-megla": {"short": "Nad meglo", "url": "/zima/nad-meglo/", "levels": MEGLA_LEVELS,
                    "opts": [("ge1", "inverzija (dolina v megli, vrhovi na soncu)"), ("ge2", "megla seže nad 500 m"),
                             ("ge3", "megla seže nad 900 m")]},
}


def _rank(level):
    return RANK_ORDER.index(level) if level in RANK_ORDER else 0


def sneg_level(cm):
    """Raven novega snega v dolini po dnevni količini (cm); None = ni podatka."""
    if cm is None:
        return None
    return sum(1 for b in SNEG_CM_BANDS if cm >= b)


def megla_level(top_m, has_inversion):
    """Raven jutranje inverzije po zgornji meji megle; brez inverzije 0."""
    if not has_inversion or top_m is None:
        return 0
    return 1 + sum(1 for b in MEGLA_TOP_BANDS if top_m >= b)


def _oklepaj(names):
    return ", ".join(names[:-1]) + " in " + names[-1] if len(names) > 1 else (names[0] if names else "")


def zima_ocene(data):
    """{slug: [{date, lvl, reasons}]} za štiri zimska opozorila iz data/winter-data.json (čista funkcija, preizkusi jo
    test_zima_alarm.py). Dan brez podatka izpustimo -- worker ga ne more oceniti in obvestila ne pošlje."""
    out = {k: [] for k in ZIMA_ALERTS}
    for d in (data.get("black_ice_outlook") or {}).get("daily") or []:
        out["zima-poledica"].append({"date": d["date"], "lvl": _rank(d["level"]), "reasons": []})
    for d in (data.get("freezing_rain") or {}).get("daily") or []:
        out["zima-zled"].append({"date": d["date"], "lvl": _rank(d["level"]), "reasons": []})
    for d in (data.get("snow_line") or {}).get("daily") or []:
        lvl = sneg_level(d.get("cm_at_station"))
        if lvl is None:
            continue
        why = []
        if lvl:
            why.append(f"v dolini po oceni {num(d['cm_at_station'], 1)} cm novega snega")
            if d.get("line_m") is not None:
                why.append(f"meja sneženja do {d['line_m']} m")
        out["zima-sneg"].append({"date": d["date"], "lvl": lvl, "reasons": why})
    fog = data.get("fog") or {}
    locs = fog.get("locations") or []
    for d in fog.get("daily") or []:
        top = d.get("top_m")
        lvl = megla_level(top, d.get("has_inversion"))
        why = []
        if lvl:
            above = [l["name"] for l in locs if l["elevation_m"] >= 1000 and l["elevation_m"] > top]
            why.append(f"megla do približno {top} m")
            if above:
                why.append(f"nad njo: {_oklepaj(above)}")
        out["zima-megla"].append({"date": d["date"], "lvl": lvl, "reasons": why})
    return out


def write_zima_ocene(data, path=None):
    """Zapiše data/zima-ocene.json, ki ga bere worker; vrne število zapisanih strani."""
    path = path or ZIMA_OCENE_FILE
    try:
        os.remove(path)                    # datoteka je izpeljana v celoti iz winter-data.json, ostanki starih strani nimajo smisla
    except OSError:
        pass
    n = 0
    for slug, days in zima_ocene(data).items():
        if not days:
            continue
        c = ZIMA_ALERTS[slug]
        D.write_summary(slug, c["short"], c["url"], c["levels"], days, path=path)
        n += 1
    return n


def alert_block(slug):
    """CSS + gradnik + skript opozorila za eno od zimskih strani."""
    c = ZIMA_ALERTS[slug]
    return D.ALERT_CSS + "\n" + D.alert_html(slug, c["short"], c["levels"], c["opts"]) + "\n" + D.alert_script(slug)


def with_alert(body, slug):
    """Gradnik opozorila vstavi tik pred povezavo »Nazaj« (ob nezanesljivih podatkih strani ne podira)."""
    marker = '  <a class="back-link"'
    i = body.rfind(marker)
    return body if i < 0 else body[:i] + alert_block(slug) + "\n" + body[i:]


ZIMA_ALERT_TEXT = {
    "zima-poledica": ("black_ice", "ko je tveganje poledice srednje ali visoko"),
    "zima-sneg": ("snow_line", "ko model napove sneg v dolini"),
    "zima-zled": ("zled", "ko je pokazatelj žleda srednji ali visok"),
    "zima-megla": ("fog", "ko bo dolina v megli, vrhovi pa na soncu"),
}


def hub_alerts_html():
    cards = []
    for slug, c in ZIMA_ALERTS.items():
        key, text = ZIMA_ALERT_TEXT[slug]
        cards.append(f'<a class="zx-alert" href="{c["url"]}#ov-alert" style="{card_style(key, "")}">'
                     f'<b>{icon_html(key, 20)}{c["short"]}</b><span>Obvestilo, {text}.</span><em>Nastavi opozorilo →</em></a>')
    return ('  <div class="zx-sec" id="opozorila"><h2>Opozorila na telefon</h2>\n'
            '    <p>Na vsaki od teh strani izberete raven in dan, mi pa vam pošljemo obvestilo, ko ocena ustreza. '
            'Modelska napoved, ne uradno opozorilo.</p></div>\n'
            f'  <div class="zx-alerts">{"".join(cards)}</div>')


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


# ── /zima/zled/ ──────────────────────────────────────────────────────────

ARSO_SOUNDING_IMG = "https://meteo.arso.gov.si/uploads/probase/www/aviation/observ/upper/graphic/sigps_ljubljana-bezigrad.png"


def build_zled_body(data):
    fr = data.get("freezing_rain") or {}
    level = fr.get("level", "nizko")
    hours = fr.get("hours") or []
    if level == "nizko":
        hero_sub = "V naslednjih 48 h model ne kaže pogojev za žled (dež pri tleh pod ničlo, nad njimi pa topla plast)."
    else:
        hero_sub = (f"V naslednjih 48 h so po modelu možni pogoji za žled — {risk_badge(level)}. "
                    f"Ure: {', '.join(fmt_hour(h) for h in hours[:6])}"
                    f"{' …' if len(hours) > 6 else ''}. Največ {num(fr.get('peak_precip_mm', 0), 1)} mm na uro.")
    outlook = fr.get("daily") or []
    outlook_html = ""
    if outlook:
        chips = "\n".join(
            f'    <div class="stat-card"><div class="sc-label">{fmt_day_short(d["date"])}</div>'
            f'<div class="sc-val">{RISK_ICON.get(d["level"], "⚪")}</div>'
            f'<div class="sc-sub">{RISK_LABEL.get(d["level"], "ni podatka")}</div></div>'
            for d in outlook
        )
        outlook_html = f'  <h2>7-dnevni pregled</h2>\n  <div class="stat-grid">\n{chips}\n  </div>'

    faq = [
        ("Kaj je žled in kako se razlikuje od poledice?",
         "Žled nastane, ko dež ali pršeč dež pade na podhlajena tla in drevesa ter takoj zmrzne v plast ledu. "
         "Poledica je širši pojem: zmrznjena površina po vseh poteh, tudi po sevalnem ohlajanju ob jasni noči "
         "(to ocenjuje stran Poledica). Žled je redkejši, a veliko bolj nevaren — v žledolomu 2014 je ob "
         "prelomu januarja in februarja poškodoval okoli 40 % slovenskih gozdov."),
        ("Kako beremo, ali bo žled, na vertikalni sondaži?",
         "Iščemo tri stvari: pri tleh temperatura pod 0 °C, nad njo plast s temperaturo nad 0 °C (tam se "
         "sneg stopi v dež) in vlažen zrak, ki dež vzdržuje. Če je pod ničlo vsa višina, pada sneg; če je nad "
         "ničlo že pri tleh, pada navaden dež."),
        ("Ali je ta ocena uradno opozorilo?",
         "Ne. To je modelski pokazatelj iz javne napovedi Open-Meteo za Rečico ob Savinji. Ne napove "
         "debeline ledu in ne zajame lokalnih razlik v dolini. Uradna opozorila izdaja ARSO — preveri jih "
         "pred potjo."),
        ("Zakaj vidim ob dežju pod ničlo včasih nizko tveganje?",
         "Ker model potrebuje hkrati mraz pri tleh, toplo plast nad njimi in vsaj 0,1 mm padavin na uro. "
         "Če nobenega pogoja ni, je tveganje nizko, tudi če je zunaj mrzlo."),
    ]

    return f'''{BRAND_SWAP}{ZIMA_CSS}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Žled", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Žled — nevarnost dežja, ki zmrzuje</h1>
  <p class="post-meta">Posodobljeno {fr.get("generated_at_local") or data.get("generated_at_local", "—")}</p>
  <div class="card zima-card" style="{card_style("black_ice")}">
    <div class="clabel">{icon_html("black_ice")}Žled — naslednjih 48 h</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
{outlook_html}
  <h2>Vertikalna sondaža nad Ljubljano</h2>
  <p class="archive-intro">Balon se spusti iz Ljubljane (Bežigrad) in izmeri temperaturo, vlago ter veter po
  višini. Na sliki spodaj poglej, ali je pri tleh pod ničlo, nad tem pa topla plast — to je tipična
  »recepta« za žled. Sondaža je za Ljubljano, ne za Rečico, zato je lahko v naši dolini ob jasni noči pri tleh
  hladneje.</p>
  <p><img src="{ARSO_SOUNDING_IMG}" alt="Vertikalna sondaža atmosfere nad Ljubljano (ARSO)" loading="lazy"
    style="max-width:100%;height:auto;border-radius:8px;background:#fff"></p>
  <p class="muted-note">Vir: <a href="https://meteo.arso.gov.si/met/sl/aviation/" target="_blank" rel="noopener">ARSO — Agencija RS za okolje</a>,
  radiosondaža Ljubljana. Čas meritve je izpisan na sliki.</p>
  <h2>Kako nastane žled</h2>
  <p class="archive-intro">Pri nas ga najpogosteje povzroči <strong>temperaturna inverzija</strong>: ob tleh se
  zadržuje hladen zrak pod lediščem, z jugozahoda pa nad njim priteka toplejši in zelo vlažen zrak. Padavine
  nastanejo kot sneg, v topli plasti se stalijo v dež, v hladni plasti tik nad tlemi pa se dežne kapljice podhladijo
  in ob stiku s tlemi, cestami, vejami ali žicami zmrznejo. Kjer je hladna plast debelejša, kapljice zmrznejo že
  v zraku in padejo kot ledena zrna.</p>
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Pogoji za oceno: temperatura pri tleh ≤ {FR_T2M} °C, topla plast
  (≥ {FR_WARM} °C na 925 ali 850 hPa) in vsaj {FR_PRECIP} mm padavin na uro; od {FR_HIGH} mm na uro je tveganje
  »visoko«. Ni uradno opozorilo — preveri <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank"
  rel="noopener">opozorila ARSO</a> in <a href="/nevihte/">stran opozoril</a>. Za poledico po sevalnem
  ohlajanju glej <a href="/zima/poledica/">Poledica</a>.</p>
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

def prelazi_n(n, spremljan=False):
    """»2 prelaza«, »3 prelazi«, »5 prelazov« (dvojina/množina)."""
    oblika = {1: ("prelaz", "spremljan"), 2: ("prelaza", "spremljana"),
              3: ("prelazi", "spremljani"), 4: ("prelazi", "spremljani")}.get(n % 100 if n % 100 < 5 else 0,
                                                                            ("prelazov", "spremljanih"))
    return f"{n} {oblika[1] + ' ' if spremljan else ''}{oblika[0]}"


def build_passes_body(data):
    passes = data.get("passes") or []

    known = [(p, p["weather"]) for p in passes if (p.get("weather") or {}).get("expected_snow_cm_24h") is not None]
    if known:
        worst_pass, worst_w = max(known, key=lambda pw: pw[1]["expected_snow_cm_24h"])
        hero_sub = (f'{prelazi_n(len(passes), True)}. Največ snega v naslednjih 24 h je pričakovanih na '
                    f'{worst_pass["name"]} ({worst_pass["elevation_m"]} m) — do '
                    f'{num(worst_w["expected_snow_cm_24h"], 1)} cm.')
    else:
        hero_sub = f'{prelazi_n(len(passes), True)} — vreme na višini trenutno ni na voljo.'

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
                           "/zima/", schema + "\n" + snow_map_assets(), body)
    seo.write_page("zima/index.html", html, force=True)
    print("  → zima/index.html")

    # ── meja-snezenja ──
    body, faq = build_snow_line_body(data)
    body = with_alert(body, "zima-sneg")
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
    body = with_alert(body, "zima-poledica")
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

    # ── zled ──
    body, faq = build_zled_body(data)
    body = with_alert(body, "zima-zled")
    schema = "\n".join([
        seo.webpage_schema("/zima/zled/", "Žled: kdaj dež zmrzuje in ali ga bo v dolini",
                            "Modelski pokazatelj žleda za Rečico ob Savinji, vertikalna sondaža Ljubljana "
                            "(ARSO) in razlaga, kako nastane žled.",
                            date_published="2026-10-07"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Žled", None)]),
        seo.faq_schema(faq),
    ])
    html = seo.page_shell("Žled: kdaj dež zmrzuje in ali ga bo v dolini",
                           "Modelski pokazatelj žleda za Rečico ob Savinji, vertikalna sondaža Ljubljana in "
                           "razlaga, kako nastane žled.",
                           "/zima/zled/", schema, body)
    seo.write_page("zima/zled/index.html", html, force=True)
    print("  → zima/zled/index.html")

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
    body = with_alert(body, "zima-megla")
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

    print(f"  → data/zima-ocene.json ({write_zima_ocene(data)} strani)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
