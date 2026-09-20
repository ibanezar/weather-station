#!/usr/bin/env python3
"""
tools/generate_zima_page.py — MeteoZima, /zima/ podportal (hub + 5 spoke strani)

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

/zima/prevoznost-prelazov/ in ločena stran za kakovost zraka NISTA tu — glej
odprta vprašanja v specifikaciji: prva rabi javni vir/ročno vzdrževano tabelo
podatkov o gorskih prelazih, ki ju v repozitoriju ni (prazna stran bi bila
slabša izbira kot nobena — glej CLAUDE.md o tankih/praznih straneh); druga bi
podvajala obstoječi /kakovost-zraka/ (glej opombo pri heating_index v
winter_engine.py).

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

RISK_LABEL = {"nizko": "Nizko tveganje", "srednje": "Srednje tveganje", "visoko": "Visoko tveganje"}
RISK_ICON = {"nizko": "🟢", "srednje": "🟡", "visoko": "🔴"}
RISK_CLASS = {"nizko": "badge-risk-nizko", "srednje": "badge-risk-srednje", "visoko": "badge-risk-visoko"}
CONF_LABEL = {"visoka": "visoka zanesljivost", "srednja": "srednja zanesljivost", "nizka": "nizka zanesljivost"}


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
        parts.append(f'<rect x="{cx - bar_w / 2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                      f'height="{bh:.1f}" rx="3" fill="{color}"/>')
        if v is not None:
            parts.append(f'<text x="{cx:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="9.5" '
                          f'fill="#94a3b8">{RISK_ICON.get(lvl, "")} {num(v, 1)}{unit}</text>')
        parts.append(f'<text x="{cx:.1f}" y="{h - 8}" text-anchor="middle" font-size="9.5" '
                      f'fill="#94a3b8">{fmt_day_short(days[i])}</text>')

    return (f'<svg viewBox="0 0 {w} {h}" class="frost-chart" role="img" '
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
        '<polyline points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in s) +
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


# ── /zima/ hub ────────────────────────────────────────────────────────────

def build_hub_body(data):
    snow = data["snow_line"]
    locations = data["locations"]
    worst_loc = max(locations, key=lambda l: ["nizko", "srednje", "visoko"].index(l["indices"]["black_ice"]["risk_level"]))
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

    ice_verdict = (f"Danes ni povečanega tveganja poledice v dolini."
                   if worst_level == "nizko" else
                   f"Najbolj izpostavljen je trenutno kraj {worst_loc['name']} — {risk_badge(worst_level)}.")

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

    cards = f'''  <div class="card-grid">
    <a class="phenom-card" href="/zima/meja-snezenja/">Meja sneženja
      <div class="ph-count">{num(line_m, 0) if line_m is not None else "—"} m n. m.</div></a>
    <a class="phenom-card" href="/zima/poledica/">Tveganje poledice
      <div class="ph-count">{RISK_ICON.get(worst_level, "⚪")} {RISK_LABEL.get(worst_level, "ni podatka")}</div></a>
    <a class="phenom-card" href="/zima/kurilni-semafor/">Kurilni semafor
      <div class="ph-count">{RISK_ICON.get(heating_level, "⚪")} {RISK_LABEL.get(heating_level, "ni podatka")}</div></a>
    <a class="phenom-card" href="/zima/nad-meglo/">Nad meglo
      <div class="ph-count">{f"~{fog['top_m']} m" if fog and fog.get("has_inversion") else "brez megle"}</div></a>
    <a class="phenom-card" href="/zima/snezna-odeja/">Snežna odeja
      <div class="ph-count">{num(station_depth, 0) + " cm" if station_depth is not None else "—"}</div></a>
  </div>'''

    season = data.get("season") or {}
    season_html = ""
    if season.get("days_logged"):
        y, m, d = season["start_date"][:4], int(season["start_date"][5:7]), int(season["start_date"][8:10])
        start_fmt = f"{d}. {m}. {y}"
        season_html = (
            '  <h2>Ta sezona</h2>\n'
            f'  <p>Od {start_fmt}: <strong>{season["heating_high_days"]}</strong> dni z visoko jakostjo '
            f'inverzije, <strong>{season["black_ice_high_days"]}</strong> dni z visokim tveganjem poledice, '
            f'<strong>{season["snow_days"]}</strong> dni s pričakovanim snegom na postaji '
            f'(od {season["days_logged"]} zabeleženih dni).</p>'
        )

    faq = [
        ("Katere kraje pokriva MeteoZima?", "Rečico ob Savinji (postaja IREICA1), Mozirje, Nazarje, Ljubno ob "
         "Savinji, Gornji Grad, Luče in Solčavo — ista naselja kot na straneh »Vreme po krajih v dolini«."),
        ("Ali je to uradno opozorilo?", "Ne. Vsi indeksi so ocena Meteoreca iz javnih napovednih virov "
         "(Open-Meteo), ne uradno opozorilo ARSO. Za uradna opozorila glej "
         "<a href=\"/nevihte/\">stran opozoril</a>, za dejansko kakovost zraka pa "
         "<a href=\"/kakovost-zraka/\">/kakovost-zraka/</a>."),
    ]

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Zimski nadzorni center — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">❄️ Meja sneženja</div>
    <p class="fh-sub">{snow_verdict}</p>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🧊 Poledica</div>
    <p class="fh-sub">{ice_verdict}</p>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🔥 Kurilni semafor</div>
    <p class="fh-sub">{heating_verdict}</p>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🌫️ Nad meglo</div>
    <p class="fh-sub">{fog_verdict}</p>
  </div>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🏔️ Snežna odeja</div>
    <p class="fh-sub">{f"Tekoča ocena na postaji: <strong>{num(station_depth, 0)} cm</strong> (modelirano, ni meritev)." if station_depth is not None else "Ocena trenutno ni na voljo."}</p>
  </div>
{cards}
{season_html}
  <h2>Pogosta vprašanja</h2>
  <div class="faq">
{chr(10).join(f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in faq)}
  </div>
  <p class="muted-note">Podatki izhajajo iz javne napovedi Open-Meteo za postajo IREICA1 in okoliška
  naselja, brez notranjih meritev. Prevoznost prelazov (Menina, Črnivec …) čaka na javno dostopen vir
  podatkov o stanju cest.</p>
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

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Meja sneženja", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Meja sneženja — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">❄️ Trenutna meja sneženja</div>
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

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Poledica", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Tveganje poledice — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
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

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Kurilni semafor", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Kurilni semafor — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🔥 Prevetrenost za kurjenje</div>
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

def build_fog_body(data):
    fog = data.get("fog")
    table = ""

    if not fog:
        hero_sub = "Ocena trenutno ni na voljo — poskusi znova pozneje."
    elif not fog.get("has_inversion"):
        hero_sub = ("Jutri zjutraj ni pričakovane pomembne temperaturne inverzije — "
                     "megla v dolini ni verjetna.")
    else:
        hero_sub = (f'{fmt_day(fog["morning_date"]).capitalize()} zjutraj je pričakovana zgornja meja '
                     f'megle/nizke oblačnosti pri približno <strong>{fog["top_m"]} m n. m.</strong>')
        rows = []
        for l in fog["locations"]:
            status = "🌤️ nad meglo" if l["above"] else "☁️ v megli / pod njo"
            rows.append(f'      <tr><th>{l["name"]} ({l["elevation_m"]} m)</th><td>{status}</td></tr>')
        table = ('  <h2>Kraji glede na pričakovano mejo megle</h2>\n'
                  '  <table class="stats">\n' + "\n".join(rows) + "\n  </table>")

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

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Nad meglo", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Nad meglo — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🌫️ Jutranja megla</div>
    <p class="fh-sub">{hero_sub}</p>
  </div>
{table}
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

    return f'''{BRAND_SWAP}
{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snežna odeja", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Snežna odeja — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Posodobljeno {data.get("generated_at_local", "—")}</p>
  <div class="card" style="margin-bottom:1.2rem">
    <div class="clabel">🏔️ Tekoča ocena snežne odeje</div>
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
