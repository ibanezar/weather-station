#!/usr/bin/env python3
"""
tools/generate_kakovost_zraka_page.py — Kakovost zraka pillar page

Generates /kakovost-zraka/index.html: current EU AQI + level, pollutant
breakdown against EU limits, a 5-day pollen forecast, and health
recommendations for Rečica ob Savinji. Ports the homepage's "Zrak" tab
(app.js: initZrak/_buildAq*) to Python — same Open-Meteo Air Quality API
(CAMS Europe domain), same thresholds.

Usage:
  python3 tools/generate_kakovost_zraka_page.py
"""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

DAN_KRATKO = ["ned", "pon", "tor", "sre", "čet", "pet", "sob"]

HOURLY_VARS = ",".join([
    "pm10", "pm2_5", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide", "ozone",
    "european_aqi", "european_aqi_pm2_5", "european_aqi_pm10",
    "european_aqi_nitrogen_dioxide", "european_aqi_ozone",
    "alder_pollen", "birch_pollen", "grass_pollen", "mugwort_pollen", "ragweed_pollen",
    "dust", "ammonia",
])

POLLEN_TYPES = [
    ("grass_pollen", "🌾 Trave", (10, 50, 200)),
    ("birch_pollen", "🌳 Breza", (10, 100, 1000)),
    ("alder_pollen", "🌲 Jelša", (10, 100, 1000)),
    ("mugwort_pollen", "🌿 Pelin", (10, 100, 300)),
    ("ragweed_pollen", "🌺 Ambrozija", (10, 50, 200)),
]


def fetch_air_quality():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": HOURLY_VARS,
        "timezone": "Europe/Ljubljana",
        "past_days": 1, "forecast_days": 5,
        "domains": "cams_europe",
    })
    url = f"https://air-quality-api.open-meteo.com/v1/air-quality?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def aqi_level(aqi):
    if aqi is None: return "—", "var(--muted)"
    if aqi <= 20: return "ODLIČNO", "zrak je čist, ni omejitev za dejavnosti na prostem"
    if aqi <= 40: return "DOBRO", "sprejemljiv zrak, možni blagi vplivi na zelo občutljive posameznike"
    if aqi <= 60: return "ZMERNO", "občutljive skupine (astmatiki, srčni bolniki, starejši, otroci) naj omejijo dolgotrajnejše aktivnosti na prostem"
    if aqi <= 80: return "SLABO", "večina ljudi lahko občuti vpliv na zdravje, zmanjšajte fizične napore na prostem"
    if aqi <= 100: return "ZELO SLABO", "resni vplivi na zdravje, omejite čas zadrževanja na prostem"
    return "NEVZDRŽNO", "zdravstveni alarm — izogibajte se bivanju na prostem"


def scale_level(v, th):
    if v is None: return "—"
    return "dobro" if v < th[0] else "zmerno" if v < th[1] else "slabo"


def pollen_level(v, th):
    if v is None or v < 0.5: return "—"
    if v < th[0]: return "nizka"
    if v < th[1]: return "zmerna"
    if v < th[2]: return "visoka"
    return "zelo visoka"


def now_index(times):
    now_str = datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).strftime("%Y-%m-%dT%H")
    for i, t in enumerate(times):
        if t[:13] == now_str:
            return i
    return len(times) // 2  # fallback: middle of the fetched window


def build_body(data):
    h = data.get("hourly") or {}
    times = h.get("time") or []
    if not times:
        raise ValueError("Open-Meteo Air Quality API brez urnih podatkov")
    ni = now_index(times)

    def get(key, i=None):
        i = ni if i is None else i
        arr = h.get(key) or []
        return arr[i] if 0 <= i < len(arr) else None

    aqi = get("european_aqi")
    level, desc = aqi_level(aqi)
    pm25, pm10 = get("pm2_5"), get("pm10")
    o3, no2, so2 = get("ozone"), get("nitrogen_dioxide"), get("sulphur_dioxide")
    co = get("carbon_monoxide")

    dom_pollen, dom_val = "—", 0
    pollen_lbls = {"grass_pollen": "Trave", "birch_pollen": "Breza", "alder_pollen": "Jelša",
                   "mugwort_pollen": "Pelin", "ragweed_pollen": "Ambrozija"}
    for key, lbl in pollen_lbls.items():
        v = get(key)
        if v is not None and v > dom_val:
            dom_val, dom_pollen = v, lbl

    answer = (f'  <p class="archive-intro">Trenutna kakovost zraka v Rečici ob Savinji je <strong>{level}</strong> '
              f'(EU AQI {aqi if aqi is not None else "—"}) — {desc}. PM2,5 {seo.num(pm25, 1) if pm25 is not None else "—"} µg/m³, '
              f'PM10 {seo.num(pm10, 0) if pm10 is not None else "—"} µg/m³' +
              (f", prevladujoč cvetni prah: {dom_pollen}" if dom_val > 0.5 else "") +
              f' — nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-up">
      <div class="sc-label">EU AQI zdaj</div>
      <div class="sc-val">{aqi if aqi is not None else "—"}</div>
      <div class="sc-sub">{level}</div>
    </div>
    <div class="stat-card c-temp">
      <div class="sc-label">PM2,5</div>
      <div class="sc-val">{seo.num(pm25, 1) if pm25 is not None else "—"}</div>
      <div class="sc-sub">µg/m³</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">PM10</div>
      <div class="sc-val">{seo.num(pm10, 0) if pm10 is not None else "—"}</div>
      <div class="sc-sub">µg/m³</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Cvetni prah</div>
      <div class="sc-val">{round(dom_val) if dom_val > 0.5 else "nizka"}</div>
      <div class="sc-sub">{dom_pollen if dom_val > 0.5 else "—"}</div>
    </div>
  </div>'''

    # ── pollutants table ──────────────────────────────────────────────────
    poll_rows = [
        ("PM2,5", pm25, "µg/m³", (25, 50), "Dnevna meja: WHO 15 µg/m³ / EU 25 µg/m³"),
        ("PM10", pm10, "µg/m³", (50, 100), "Dnevna meja EU: 50 µg/m³"),
        ("Ozon O₃", o3, "µg/m³", (120, 240), "8-urna meja EU: 120 µg/m³"),
        ("NO₂", no2, "µg/m³", (200, 400), "Urna meja EU: 200 µg/m³"),
        ("SO₂", so2, "µg/m³", (350, 700), "Urna meja EU: 350 µg/m³"),
        ("CO", (co / 1000) if co is not None else None, "mg/m³", (10, 20), "8-urna meja EU: 10 mg/m³"),
        ("Prah (dust)", get("dust"), "µg/m³", None, "Saharski prah + lokalni viri"),
        ("NH₃", get("ammonia"), "µg/m³", None, "Kmetijsko onesnaževalo"),
    ]
    poll_html_rows = []
    for name, val, unit, thresh, note in poll_rows:
        disp = f'{seo.num(val, 1 if val is not None and val < 10 else 0)} {unit}' if val is not None else "—"
        lvl = scale_level(val, thresh) if thresh else "—"
        poll_html_rows.append(f'      <tr><th>{name}</th><td>{disp} — {lvl} <span class="muted-note" style="margin:0;display:inline">({note})</span></td></tr>')
    poll_table = '  <table class="stats">\n' + "\n".join(poll_html_rows) + "\n  </table>"

    # ── pollen 5-day forecast ────────────────────────────────────────────
    today0 = datetime.date.today()
    day_strs = [(today0 + datetime.timedelta(days=i)).isoformat() for i in range(5)]
    day_lbls = ["Danes" if i == 0 else "Jutri" if i == 1 else DAN_KRATKO[(datetime.date.fromisoformat(d).weekday() + 1) % 7]
                for i, d in enumerate(day_strs)]

    def daily_max(key, date_str):
        mx = None
        for i, t in enumerate(times):
            if t.startswith(date_str):
                v = (h.get(key) or [None] * len(times))[i]
                if v is not None:
                    mx = v if mx is None else max(mx, v)
        return mx

    pollen_rows = []
    for key, lbl, th in POLLEN_TYPES:
        cells = " · ".join(f'{day_lbls[i]}: {pollen_level(daily_max(key, d), th)}' for i, d in enumerate(day_strs))
        pollen_rows.append(f'      <tr><th>{lbl}</th><td>{cells}</td></tr>')
    pollen_table = '  <table class="stats">\n' + "\n".join(pollen_rows) + "\n  </table>"

    # ── health recommendations ───────────────────────────────────────────
    health_items = []
    if aqi is not None:
        if aqi <= 20:
            health_items.append("✅ Kakovost zraka je odlična. Ni omejitev za dejavnosti na prostem.")
        elif aqi <= 40:
            health_items.append("🟡 Sprejemljiva kakovost zraka. Zelo občutljivi (npr. s hudo astmo) naj se izogibajo večjim naporom.")
        elif aqi <= 60:
            health_items.append("🟠 Občutljive skupine (astmatiki, srčni bolniki, starejši in otroci) naj omejijo dolgotrajnejšo fizično aktivnost na prostem.")
            health_items.append("💊 Astmatiki naj imajo ob sebi inhalator.")
        elif aqi <= 80:
            health_items.append("🔴 Vsakdo lahko začuti vpliv na zdravje. Zmanjšajte fizične napore na prostem.")
            health_items.append("🚪 Zaprite okna in vrata — preprečite vstop onesnaženega zraka v bivalne prostore.")
        else:
            health_items.append("🚨 Zdravstveni alarm! Izogibajte se zunanjim aktivnostim. Če morate ven, nosite zaščitno masko N95/FFP2.")
            health_items.append("🚪 Zaprite okna. Priporoča se uporaba čistilnika zraka s HEPA-filtrom.")
    if dom_val > 200:
        health_items.append("🤧 Zelo visoka koncentracija cvetnega prahu. Alergiki naj vzamejo antihistaminike, ostanejo v zaprtih prostorih in filtrirajo zrak.")
    elif dom_val > 50:
        health_items.append("🤧 Visoka koncentracija cvetnega prahu. Alergiki naj redno jemljejo antihistaminike in se izogibajo travnatim območjem.")
    elif dom_val > 10:
        health_items.append("😤 Zmerna koncentracija cvetnega prahu. Ob sunkovitem vetru se koncentracija v zraku močno poveča.")
    if not health_items:
        health_items.append("😊 Ni posebnih priporočil. Uživajte na svežem zraku!")
    health_html = "  <ul>\n" + "\n".join(f"    <li>{item}</li>" for item in health_items) + "\n  </ul>"

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kakšna je danes kakovost zraka v Rečici ob Savinji?",
         f"Trenutni EU AQI je {aqi if aqi is not None else '—'} ({level.lower()}). PM2,5 znaša "
         f"{seo.num(pm25, 1) if pm25 is not None else '—'} µg/m³, PM10 {seo.num(pm10, 0) if pm10 is not None else '—'} µg/m³."),
        ("Kaj pomeni EU AQI?",
         "EU AQI (European Air Quality Index) je lestvica od 0 do prek 100, ki združuje koncentracije PM2,5, PM10, "
         "ozona in NO₂ v eno število: 0–20 odlično, 21–40 dobro, 41–60 zmerno, 61–80 slabo, 81–100 zelo slabo, nad 100 nevzdržno."),
        ("Kje v Sloveniji je cvetni prah trenutno najbolj problematičen?",
         f"Podatki na tej strani so za Zgornjo Savinjsko dolino; trenutno prevladujoč cvetni prah je {dom_pollen.lower() if dom_val > 0.5 else 'v nizkih koncentracijah'}. "
         "Za druge regije Slovenije glej ARSO ali specializirane pelodne napovedi."),
        ("Kdaj je kakovost zraka v Savinjski dolini najslabša?",
         "Kot v drugih alpskih dolinah je zrak najslabši pozimi ob temperaturnih inverzijah, ko se onesnaževala (predvsem "
         "PM10 iz kurjenja na trda goriva) zadržujejo na dnu doline zaradi omejenega prezračevanja."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Kakovost zraka", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Kakovost zraka in cvetni prah — Zgornja Savinjska dolina</h1>
  <p class="post-meta">EU AQI, onesnaževala in pelodna napoved (Open-Meteo / CAMS Europe) · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Onesnaževala — trenutne vrednosti glede na mejne</h2>
{poll_table}
  <h2>Cvetni prah — 5-dnevna napoved</h2>
  <p class="archive-intro">Ocena tveganja po vrsti cvetnega prahu za naslednjih 5 dni. Vir: Copernicus CAMS Europe. Sezonska razpoložljivost je odvisna od biološke aktivnosti rastlin.</p>
{pollen_table}
  <h2>Zdravstvena priporočila</h2>
{health_html}
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🔗 Viri podatkov o kakovosti zraka</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.arso.gov.si/zrak/" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 ARSO — kakovost zraka</a>
      <a href="https://aqicn.org/city/celje/" target="_blank" rel="noopener" class="mtn-avk-link">🌍 AQICN — Celje</a>
      <a href="https://atmosphere.copernicus.eu/" target="_blank" rel="noopener" class="mtn-avk-link">🛰 Copernicus CAMS</a>
      <a href="https://www.who.int/news-room/fact-sheets/detail/ambient-(outdoor)-air-quality-and-health" target="_blank" rel="noopener" class="mtn-avk-link">🏥 WHO — smernice</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model uporablja iste vhodne podatke (Open-Meteo Air Quality API, CAMS Europe) kot živi
  pripomoček na <a href="/">naslovni strani Meteorec</a> (zavihek »Zrak«).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, aqi, level, qa


def main():
    print(f"[{TODAY}] Pridobivam podatke o kakovosti zraka …")
    try:
        data = fetch_air_quality()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        body, aqi, level, qa = build_body(data)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/kakovost-zraka/"
    title = "Kakovost zraka in cvetni prah — Zgornja Savinjska dolina"
    desc = (f"EU AQI danes: {aqi if aqi is not None else '—'} ({level.lower()}). Onesnaževala (PM2,5, PM10, ozon, NO₂), "
            f"5-dnevna napoved cvetnega prahu in zdravstvena priporočila za Rečico ob Savinji.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Kakovost zraka", None)]),
        seo.faq_schema(qa),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("kakovost-zraka/index.html", html, force=True)
    print(f"  → kakovost-zraka/index.html (AQI {aqi}, {level})")


if __name__ == "__main__":
    main()
