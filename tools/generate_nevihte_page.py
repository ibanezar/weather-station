#!/usr/bin/env python3
"""
tools/generate_nevihte_page.py — Nevihtna napoved pillar page

Generates /nevihte/index.html: today's atmospheric-instability snapshot
(CAPE, CIN, Lifted Index, Total Totals, K-index, wind shear), plus hail-risk
and damaging-wind-risk outlooks for the next 12 hours. Ports the scoring
formulas from the homepage's "Lovec na nevihte" tab (app.js:
scThreatScore/calcStormThreat, calcHailRisk, calcWindRisk) to Python so the
static page never disagrees with the live widget — but skips the tab's
sounding/hodograph visualisations and the Slovenia-wide heatmap, which stay
homepage-only interactive features linked from this page.

Data source: Open-Meteo forecast API, surface + pressure-level hourly
variables (same fields the live widget requests).

Usage:
  python3 tools/generate_nevihte_page.py
"""
import datetime, json, math, os, sys, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

OUTLOOK_HOURS = 12
DAN_KRATKO = ["ned", "pon", "tor", "sre", "čet", "pet", "sob"]

HOURLY_VARS = ",".join([
    "temperature_2m", "dew_point_2m", "relative_humidity_2m",
    "cape", "lifted_index", "convective_inhibition", "freezing_level_height",
    "precipitation_probability", "wind_gusts_10m",
    "wind_speed_10m", "wind_direction_10m",
    "temperature_850hPa", "relative_humidity_850hPa",
    "temperature_700hPa", "relative_humidity_700hPa",
    "temperature_500hPa", "wind_speed_500hPa", "wind_direction_500hPa",
])


def fetch_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": HOURLY_VARS,
        "timezone": "Europe/Ljubljana",
        "forecast_days": 2,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def idx(arr, i):
    if arr is None or i < 0 or i >= len(arr):
        return None
    v = arr[i]
    return v if v is not None else None


def magnus_dewpoint(T, rh):
    if rh is None or rh <= 0 or T is None:
        return T - 10
    rh_safe = max(1, min(100, rh))
    a, b = 17.625, 243.04
    g = math.log(rh_safe / 100) + a * T / (b + T)
    return b * g / (a - g)


def wind_uv(spd, wdir):
    rad = wdir * math.pi / 180
    return -spd * math.sin(rad), -spd * math.cos(rad)


def dir_label(d):
    dirs = ["S", "SSV", "SV", "VSV", "V", "VJV", "JV", "JJV", "J", "JJZ", "JZ", "ZJZ", "Z", "ZSZ", "SZ", "SSZ"]
    return dirs[round(d / 22.5) % 16]


def beaufort(gust):
    if gust >= 118: return 12, "orkan"
    if gust >= 103: return 11, "silovit vihar"
    if gust >= 89: return 10, "vihar"
    if gust >= 75: return 9, "viharni veter"
    if gust >= 62: return 8, "hud veter"
    if gust >= 50: return 7, "zelo močan veter"
    if gust >= 39: return 6, "močan veter"
    return 5, "precej močan veter"


def storm_threat_score(cape, cin, li, tt, shear):
    s = 0
    if cape >= 2500: s += 40
    elif cape >= 1500: s += 30
    elif cape >= 1000: s += 20
    elif cape >= 500: s += 10
    elif cape >= 100: s += 4
    if li <= -6: s += 15
    elif li <= -4: s += 10
    elif li <= -2: s += 5
    elif li <= 0: s += 2
    if tt >= 55: s += 18
    elif tt >= 50: s += 10
    elif tt >= 45: s += 5
    elif tt >= 40: s += 2
    if shear >= 25: s += 15
    elif shear >= 15: s += 8
    elif shear >= 10: s += 4
    if cin < -200: s -= 10
    elif cin < -100: s -= 5
    return s


def storm_threat(cape, cin, li, tt, shear):
    s = storm_threat_score(cape, cin, li, tt, shear)
    if s >= 60: return "EKSTREMNO", "Izjemni pogoji za razvoj neviht. Možne so supercelice, toča in poplave.", s
    if s >= 40: return "VISOKO", "Ugodni pogoji za nevihtni razvoj. Pričakujejo se sunkovit veter, intenzivne padavine in lokalna toča.", s
    if s >= 22: return "ZMERNO", "Zmeren potencial. Možne so lokalne plohe in nevihte, predvsem v popoldanskem času.", s
    if s >= 8: return "NIZKO", "Majhen potencial. Ob zadostnem sprožilcu posamezne nevihte niso povsem izključene.", s
    return "BREZ", "Ozračje je stabilno. Nastanek neviht ni pričakovan.", s


def hail_risk(cape, li, freeze, shear, tt):
    h = 0
    if cape >= 2500: h += 42
    elif cape >= 1800: h += 34
    elif cape >= 1200: h += 26
    elif cape >= 700: h += 16
    elif cape >= 350: h += 7
    if li <= -6: h += 12
    elif li <= -4: h += 8
    elif li <= -2: h += 4
    if tt >= 55: h += 10
    elif tt >= 50: h += 6
    elif tt >= 45: h += 3
    if shear >= 25: h += 18
    elif shear >= 18: h += 12
    elif shear >= 12: h += 6
    elif shear >= 8: h += 2
    if freeze < 2000: melt = 0.9
    elif freeze <= 3300: melt = 1.0
    elif freeze <= 3900: melt = 0.7
    elif freeze <= 4500: melt = 0.4
    else: melt = 0.18
    pct = round(max(0, min(100, h * melt)))
    if pct >= 70: level = "EKSTREMNO"
    elif pct >= 45: level = "VISOKO"
    elif pct >= 25: level = "ZMERNO"
    elif pct >= 10: level = "NIZKO"
    else: level = "BREZ"
    return pct, level


def wind_risk(gust, cape, shear):
    if gust >= 118: pct = 88 + min(12, (gust - 118) / 4)
    elif gust >= 103: pct = 72 + (gust - 103) / 15 * 16
    elif gust >= 89: pct = 54 + (gust - 89) / 14 * 18
    elif gust >= 75: pct = 36 + (gust - 75) / 14 * 18
    elif gust >= 62: pct = 20 + (gust - 62) / 13 * 16
    elif gust >= 50: pct = 8 + (gust - 50) / 12 * 12
    else: pct = max(0, gust / 50 * 8)
    if cape >= 1500 and shear >= 15: pct += 6
    elif cape >= 800: pct += 3
    pct = round(max(0, min(100, pct)))
    if pct >= 80: level = "EKSTREMNO"
    elif pct >= 58: level = "VISOKO"
    elif pct >= 35: level = "ZMERNO"
    elif pct >= 15: level = "NIZKO"
    else: level = "BREZ"
    return pct, level


def indices_at(d, i):
    T2 = idx(d.get("temperature_2m"), i) or 15
    rh2 = idx(d.get("relative_humidity_2m"), i) or 60
    cape = idx(d.get("cape"), i) or 0
    cin = idx(d.get("convective_inhibition"), i) or 0
    li = idx(d.get("lifted_index"), i)
    if li is None: li = 0
    freeze = idx(d.get("freezing_level_height"), i) or 3000
    gust = idx(d.get("wind_gusts_10m"), i) or 0
    pprecip = idx(d.get("precipitation_probability"), i) or 0
    ws10 = idx(d.get("wind_speed_10m"), i) or 0
    wd10 = idx(d.get("wind_direction_10m"), i) or 0
    T850 = idx(d.get("temperature_850hPa"), i)
    rh850 = idx(d.get("relative_humidity_850hPa"), i)
    if T850 is None: T850 = T2 - 5
    if rh850 is None: rh850 = rh2
    Td850 = magnus_dewpoint(T850, rh850)
    T700 = idx(d.get("temperature_700hPa"), i)
    rh700 = idx(d.get("relative_humidity_700hPa"), i)
    if T700 is None: T700 = T2 - 10
    if rh700 is None: rh700 = rh2 * 0.8
    Td700 = magnus_dewpoint(T700, rh700)
    T500 = idx(d.get("temperature_500hPa"), i)
    if T500 is None: T500 = T2 - 20
    ws500 = idx(d.get("wind_speed_500hPa"), i) or ws10
    wd500 = idx(d.get("wind_direction_500hPa"), i) or wd10
    u0, v0 = wind_uv(ws10, wd10)
    u5, v5 = wind_uv(ws500, wd500)
    shear = math.sqrt((u5 - u0) ** 2 + (v5 - v0) ** 2)
    tt = T850 + Td850 - 2 * T500
    ki = T850 - T500 + Td850 - (T700 - Td700)
    return {"cape": cape, "cin": cin, "li": li, "tt": tt, "ki": ki, "shear": shear,
            "freeze": freeze, "gust": gust, "pprecip": pprecip}


def build_body(data):
    d = data.get("hourly") or {}
    times = d.get("time") or []
    if not times:
        raise ValueError("Open-Meteo brez urnih podatkov")
    now = datetime.datetime.now()
    ci_now = 0
    for k, t in enumerate(times):
        if datetime.datetime.fromisoformat(t) >= now:
            ci_now = max(0, k - 1)
            break

    inp = indices_at(d, ci_now)
    level, desc, score = storm_threat(inp["cape"], inp["cin"], inp["li"], inp["tt"], inp["shear"])
    h_pct, h_level = hail_risk(inp["cape"], inp["li"], inp["freeze"], inp["shear"], inp["tt"])
    w_pct, w_level = wind_risk(inp["gust"], inp["cape"], inp["shear"])

    answer = (f'  <p class="archive-intro">Trenutni nevihtni potencial za Rečico ob Savinji je '
              f'<strong>{level}</strong>. {desc} CAPE {round(inp["cape"])} J/kg, indeks dviga '
              f'{seo.num(inp["li"], 1)} K, Total Totals {round(inp["tt"])}, striženje vetra 0–5,5 km '
              f'{round(inp["shear"])} km/h. Verjetnost toče je {h_pct} % ({h_level.lower()}), verjetnost '
              f'močnejših sunkov vetra pa {w_pct} % ({w_level.lower()}) — nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-up">
      <div class="sc-label">Nevihtni potencial</div>
      <div class="sc-val">{level}</div>
      <div class="sc-sub">skupna ocena {score}/88 · Rečica ob Savinji</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Verjetnost toče</div>
      <div class="sc-val">{h_pct} %</div>
      <div class="sc-sub">{h_level}</div>
    </div>
    <div class="stat-card c-wind">
      <div class="sc-label">Verjetnost močnih sunkov</div>
      <div class="sc-val">{w_pct} %</div>
      <div class="sc-sub">{w_level} · sunki {round(inp["gust"])} km/h</div>
    </div>
  </div>'''

    idx_rows = [
        ("CAPE", f'{round(inp["cape"])} J/kg',
         "šibka nestabilnost" if inp["cape"] < 100 else "zmerna do velika nestabilnost" if inp["cape"] < 1000
         else "ekstremna nestabilnost" if inp["cape"] < 2500 else "izjemna nestabilnost"),
        ("CIN — konvekcijska inhibicija", f'{round(inp["cin"])} J/kg',
         "šibka zaporna plast" if inp["cin"] > -25 else "zmerna zaporna plast" if inp["cin"] > -100
         else "močna zaporna plast" if inp["cin"] > -200 else "izredno močna zaporna plast"),
        ("Indeks dviga (Lifted Index)", f'{seo.num(inp["li"], 1)} K',
         "stabilno" if inp["li"] > 0 else "šibka nestabilnost" if inp["li"] > -2 else "zmerna nestabilnost"
         if inp["li"] > -4 else "velika nestabilnost" if inp["li"] > -6 else "izredno nestabilno"),
        ("Total Totals", f'{round(inp["tt"])}',
         "brez neviht" if inp["tt"] < 44 else "nevihte so verjetne" if inp["tt"] < 50
         else "močne nevihte" if inp["tt"] < 55 else "nevihte izjemno verjetne"),
        ("K-indeks", f'{round(inp["ki"])}',
         "nevihte malo verjetne" if inp["ki"] < 20 else "nevihte verjetne" if inp["ki"] < 30 else "izjemen potencial"),
        ("Višina ledišča", f'{seo.num(inp["freeze"] / 1000, 1)} km',
         "nizka – možna toča ali sneg v nižinah" if inp["freeze"] < 2500 else "normalna višina"
         if inp["freeze"] < 3500 else "visoka – toča manj verjetna"),
        ("Striženje vetra 0–5,5 km", f'{round(inp["shear"])} km/h',
         "šibko – nevihte se premikajo počasi" if inp["shear"] < 10 else "zmerno" if inp["shear"] < 20
         else "močno – možne supercelice" if inp["shear"] < 30 else "izjemno – potencial za tornado"),
    ]
    idx_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{name}</th><td>{val} — {note}</td></tr>' for name, val, note in idx_rows
    ) + "\n  </table>"

    # ── 12h outlook tables ────────────────────────────────────────────────
    hail_rows, wind_rows = [], []
    for k in range(OUTLOOK_HOURS + 1):
        ci = min(ci_now + k, len(times) - 1)
        t = datetime.datetime.fromisoformat(times[ci])
        lbl = "zdaj" if k == 0 else f"{DAN_KRATKO[(t.weekday() + 1) % 7]} {t.hour:02d}:00 (+{k} h)"
        hi = indices_at(d, ci)
        hp, hl = hail_risk(hi["cape"], hi["li"], hi["freeze"], hi["shear"], hi["tt"])
        wp, wl = wind_risk(hi["gust"], hi["cape"], hi["shear"])
        hail_rows.append((lbl, hp, hl))
        wind_rows.append((lbl, wp, wl, round(hi["gust"])))

    hail_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{p} % — {lv}</td></tr>' for lbl, p, lv in hail_rows
    ) + "\n  </table>"
    wind_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{p} % — {lv} · sunki {g} km/h</td></tr>' for lbl, p, lv, g in wind_rows
    ) + "\n  </table>"

    bf_n, bf_name = beaufort(inp["gust"])

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kaj je CAPE in zakaj je pomemben za nevihte?",
         "CAPE (Convective Available Potential Energy) meri razpoložljivo energijo za dviganje zraka v ozračju. "
         "Višje vrednosti (nad 1000–1500 J/kg) pomenijo močnejše vzgornike in večjo verjetnost intenzivnih neviht."),
        ("Kaj pomeni indeks dviga (Lifted Index)?",
         "Lifted Index primerja temperaturo dvignjenega zračnega delca s temperaturo okolice na 500 hPa. "
         "Negativne vrednosti pomenijo nestabilnost — bolj negativna vrednost, večja nevihtna nevarnost."),
        ("Kako natančna je ta napoved v primerjavi z ARSO?",
         "Gre za model, izračunan iz napovedi Open-Meteo (isti vhodni podatki in algoritem kot živi pripomoček "
         "na naslovni strani), namenjen hitri orientaciji. Za uradna opozorila vedno preveri ARSO."),
        ("Kdaj je verjetnost toče v Sloveniji največja?",
         "Toča je v Sloveniji, tudi v Zgornji Savinjski dolini, najpogostejša med majem in avgustom v popoldanskih "
         "in večernih urah, ko je dnevno segrevanje največje in atmosfera najbolj nestabilna."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Nevihte", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Nevihtna napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model atmosferske nestabilnosti iz podatkov Open-Meteo · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Indeksi nestabilnosti — trenutno</h2>
  <p class="archive-intro">Ključni atmosferski indeksi, ki jih meteorologi uporabljajo za oceno nevihtnega potenciala nad Rečico ob Savinji.</p>
{idx_table}
  <h2>Verjetnost toče — naslednjih {OUTLOOK_HOURS} ur</h2>
{hail_table}
  <h2>Verjetnost močnejših sunkov vetra — naslednjih {OUTLOOK_HOURS} ur</h2>
  <p class="archive-intro">Trenutni sunki vetra: {round(inp["gust"])} km/h ({bf_n}. stopnja Beauforta — {bf_name}).</p>
{wind_table}
  <h2>Kako beremo te indekse</h2>
  <p class="archive-intro"><strong>CAPE</strong> (konvektivna razpoložljiva potencialna energija) pove, koliko energije
  ima zrak na voljo za dviganje — višje vrednosti pomenijo močnejše vzgornike. <strong>CIN</strong> je "pokrov", ki
  zadržuje dviganje, dokler se dovolj ne segreje ali sproži. <strong>Indeks dviga</strong> in <strong>Total Totals</strong>
  merita nestabilnost na drugačen način in se med seboj dopolnjujeta. <strong>Striženje vetra</strong> (razlika hitrosti
  in smeri vetra med tlemi in višino ~5,5 km) organizira nevihte — višje vrednosti povečajo možnost dolgotrajnejših,
  močnejših neviht. <strong>Višina ledišča</strong> določa, ali se toča staja, preden doseže tla.</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">⚠️ Uradna opozorila</div>
    <div style="font-size:.85rem;color:var(--muted);line-height:1.7;margin-top:.5rem">
      Ta stran je informativni model, ne uradna napoved. Ob dejanski nevihtni nevarnosti vedno upoštevaj uradna
      opozorila ARSO in navodila civilne zaščite.
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener" class="mtn-avk-link">⚡ ARSO — vremenska opozorila</a>
      <a href="https://www.gov.si/drzavni-organi/organi-v-sestavi/uprava-za-zascito-in-resevanje/" target="_blank" rel="noopener" class="mtn-avk-link">🛟 URSZR</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model uporablja iste vhodne podatke in enake formule kot živi pripomoček na
  <a href="/">naslovni strani Meteorec</a> (zavihek »Lovec na nevihte«), kjer najdeš tudi karto Slovenije,
  sondažno analizo in hodograf vetra.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, level, h_pct, w_pct


def main():
    print(f"[{TODAY}] Pridobivam napoved Open-Meteo …")
    try:
        data = fetch_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju napovedi: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        body, level, h_pct, w_pct = build_body(data)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/nevihte/"
    title = "Nevihtna napoved — Zgornja Savinjska dolina"
    desc = (f"Nevihtni potencial danes: {level.lower()}. Verjetnost toče {h_pct} %, verjetnost močnih sunkov "
            f"vetra {w_pct} %. Indeksi nestabilnosti (CAPE, CIN, Lifted Index, Total Totals) za Rečico ob Savinji.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Nevihte", None)]),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("nevihte/index.html", html, force=True)
    print(f"  → nevihte/index.html ({level}, toča {h_pct} %, veter {w_pct} %)")


if __name__ == "__main__":
    main()
