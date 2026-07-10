#!/usr/bin/env python3
"""
tools/generate_padalci_page.py — Vreme za padalce pillar page

Generates /vreme-za-padalce/index.html: today's flyability score, an
hour-by-hour flying window (6-20h), and a 7-day outlook for paragliding
over Zgornja Savinjska dolina. Ports the homepage's "Padalci" tab (app.js:
initPadalci/_flyScore/_buildPadalci*) to Python — same Open-Meteo fields
(boundary layer height, CAPE, wind, precipitation probability), same
scoring thresholds.

Usage:
  python3 tools/generate_padalci_page.py
"""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

DAN_KRATKO = ["ned", "pon", "tor", "sre", "čet", "pet", "sob"]

HOURLY_VARS = ",".join([
    "boundary_layer_height", "cape", "lifted_index", "wind_speed_10m", "wind_speed_80m",
    "wind_direction_10m", "wind_direction_80m", "precipitation_probability", "precipitation",
    "is_day", "temperature_2m", "dew_point_2m",
])
DAILY_VARS = ",".join([
    "temperature_2m_max", "precipitation_sum", "wind_speed_10m_max", "wind_gusts_10m_max",
    "sunshine_duration", "weather_code",
])


def fetch_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": HOURLY_VARS, "daily": DAILY_VARS,
        "timezone": "Europe/Ljubljana",
        "forecast_days": 7,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fly_score(wind_kmh, precip_prob, cape, bl_h, is_day):
    if not is_day:
        return -1
    if precip_prob > 70 or wind_kmh > 45:
        return 0
    s = 100
    if wind_kmh > 35: s -= 50
    elif wind_kmh > 25: s -= 30
    elif wind_kmh > 18: s -= 15
    if cape > 2000: s -= 50
    elif cape > 1000: s -= 30
    elif cape > 500: s -= 15
    if precip_prob > 50: s -= 35
    elif precip_prob > 30: s -= 20
    elif precip_prob > 15: s -= 10
    if bl_h < 200: s -= 25
    elif bl_h < 500: s -= 10
    elif bl_h > 1500: s += 5
    return max(0, min(100, s))


def fly_label(score):
    if score < 0: return "noč"
    if score >= 70: return "LETI"
    if score >= 40: return "MEJNO"
    return "NE"


def build_body(data):
    h = data.get("hourly") or {}
    d = data.get("daily") or {}
    times = h.get("time") or []
    if not times:
        raise ValueError("Open-Meteo brez urnih podatkov")

    today_s = TODAY.isoformat()
    today_idxs = [i for i, t in enumerate(times) if t.startswith(today_s) and (h.get("is_day") or [0] * len(times))[i]]

    def hv(key, i, default=0):
        arr = h.get(key) or []
        v = arr[i] if i < len(arr) else None
        return v if v is not None else default

    bl_vals = [hv("boundary_layer_height", i) for i in today_idxs]
    bl_vals = [v for v in bl_vals if v > 0]
    cape_vals = [hv("cape", i) for i in today_idxs]
    wind_vals = [hv("wind_speed_10m", i) for i in today_idxs]
    scores_today = [fly_score(hv("wind_speed_10m", i), hv("precipitation_probability", i),
                               hv("cape", i), hv("boundary_layer_height", i), 1) for i in today_idxs]
    max_bl = round(max(bl_vals)) if bl_vals else None
    max_cape = round(max(cape_vals)) if cape_vals else None
    max_wind = round(max(wind_vals)) if wind_vals else None
    fly_hours = sum(1 for s in scores_today if s >= 70)
    best = max(scores_today) if scores_today else 0
    pct = max(0, min(100, round(best)))

    if pct >= 80: desc = f"Odlični pogoji za letenje — okno kakovostne termike predvidoma {fly_hours} h."
    elif pct >= 60: desc = f"Dobri pogoji — okno letenja predvidoma {fly_hours} h."
    elif pct >= 40: desc = "Zmerni pogoji — termika šibka ali veter mejni."
    elif pct >= 20: desc = "Slabi pogoji — veter, dež ali premočna termika."
    else: desc = "Neprimerno za letenje."

    answer = (f'  <p class="archive-intro">Ocena primernosti za letenje danes v Rečici / Savinjski dolini je '
              f'<strong>{pct} %</strong>. {desc} Konvekcijski strop (BL) doseže do '
              f'{max_bl if max_bl is not None else "—"} m, veter do {max_wind if max_wind is not None else "—"} km/h, '
              f'CAPE do {max_cape if max_cape is not None else "—"} J/kg — nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-up">
      <div class="sc-label">Ocena danes</div>
      <div class="sc-val">{pct} %</div>
      <div class="sc-sub">vrhunec dneva</div>
    </div>
    <div class="stat-card c-temp">
      <div class="sc-label">Ure letenja</div>
      <div class="sc-val">{fly_hours} h</div>
      <div class="sc-sub">ocena ≥ 70, danes</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Maks. višina BL</div>
      <div class="sc-val">{max_bl if max_bl is not None else "—"}</div>
      <div class="sc-sub">m · konvektivni strop</div>
    </div>
    <div class="stat-card c-wind">
      <div class="sc-label">Maks. veter</div>
      <div class="sc-val">{max_wind if max_wind is not None else "—"}</div>
      <div class="sc-sub">km/h · površina</div>
    </div>
  </div>'''

    # ── today's flying window (6-20h) ────────────────────────────────────
    window_rows = []
    for i in today_idxs:
        hr = int(times[i][11:13])
        if hr < 6 or hr > 20:
            continue
        wind = hv("wind_speed_10m", i)
        precip = hv("precipitation_probability", i)
        cape = hv("cape", i)
        bl = hv("boundary_layer_height", i)
        score = fly_score(wind, precip, cape, bl, 1)
        window_rows.append(f'      <tr><th>{hr}h</th><td>{fly_label(score)}'
                            f'{f" ({score} %)" if score >= 0 else ""} · BL {round(bl)} m · veter {round(wind)} km/h · dež {round(precip)} %</td></tr>')
    window_table = ('  <table class="stats">\n' + "\n".join(window_rows) + "\n  </table>") if window_rows \
        else '  <p class="muted-note">Ni podatkov za danes.</p>'

    # ── 7-day outlook ──────────────────────────────────────────────────────
    dd_time = d.get("time") or []
    day_rows = []
    for di in range(min(7, len(dd_time))):
        date = dd_time[di]
        dt = datetime.date.fromisoformat(date)
        dn = "danes" if di == 0 else DAN_KRATKO[(dt.weekday() + 1) % 7] + f" {dt.day}. {dt.month}."
        idxs = [i for i, t in enumerate(times) if t.startswith(date) and (h.get("is_day") or [0] * len(times))[i]]
        scores = [fly_score(hv("wind_speed_10m", i), hv("precipitation_probability", i),
                             hv("cape", i), hv("boundary_layer_height", i), 1) for i in idxs]
        max_score = max(scores) if scores else 0
        fly_hrs = sum(1 for s in scores if s >= 70)
        score_lbl = "Leti" if max_score >= 70 else "Meja" if max_score >= 40 else "Ne"
        tmax = (d.get("temperature_2m_max") or [None] * len(dd_time))[di]
        precip = (d.get("precipitation_sum") or [None] * len(dd_time))[di]
        sun_h = ((d.get("sunshine_duration") or [None] * len(dd_time))[di] or 0) / 3600
        day_rows.append(f'      <tr><th>{dn}</th><td>{score_lbl} ({max_score} %) · {fly_hrs}h letenja · '
                         f'{round(tmax) if tmax is not None else "—"}° · {seo.num(precip, 0) if precip is not None else "—"} mm · {seo.num(sun_h, 1)} h sonca</td></tr>')
    day_table = '  <table class="stats">\n' + "\n".join(day_rows) + "\n  </table>"

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kakšni so danes pogoji za jadralno padalstvo v Zgornji Savinjski dolini?",
         f"Ocena primernosti za letenje je danes {pct} %. {desc}"),
        ("Kaj je višina konvekcijskega sloja (BL) in zakaj je pomembna za padalce?",
         "Višina mejne (konvekcijske) plasti pove, do kje segajo termični dvigi. Nad približno 500 m je let mogoč, "
         "nad 1500 m so pogoji ugodni za daljše (XC) preleta."),
        ("Kakšen veter je še varen za jadralno padalstvo?",
         "Ocena na tej strani upošteva veter do 18 km/h kot ugoden, 18–35 km/h kot omejujoč, nad 45 km/h pa let "
         "odsvetuje. Dejanska varna meja je odvisna od izkušenj pilota, terena in opreme."),
        ("Kje najdem uradno padalsko vremensko napoved za Slovenijo?",
         "Specializirani viri, kot so XCmeteo, Meteo Parapente in SkySight, ponujajo podrobnejše termične in "
         "vetrovne modele za jadralno padalstvo — povezave so na dnu te strani."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Vreme za padalce", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Vreme za padalce — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Ocena primernosti za jadralno padalstvo iz podatkov Open-Meteo · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Okno letenja — danes (6–20h)</h2>
{window_table}
  <h2>7-dnevni pregled — priletnost</h2>
{day_table}
  <h2>Kako beremo oceno</h2>
  <p class="archive-intro">Ocena (0–100 %) upošteva veter na 10 m, verjetnost padavin, CAPE (nevihtni potencial) in
  višino konvekcijskega sloja. Nizek veter, malo padavin, zmeren CAPE (brez nevihtnega tveganja) in visok konvekcijski
  strop dajejo najvišjo oceno. Ocena ≥ 70 pomeni dobre pogoje za letenje, 40–69 mejne pogoje, pod 40 pa let odsvetuje.</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🔗 Padalski vremenski viri</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://xcmeteo.net/" target="_blank" rel="noopener" class="mtn-avk-link">🌤 XCmeteo</a>
      <a href="https://www.meteo-parapente.com/#/46.33,14.92,11" target="_blank" rel="noopener" class="mtn-avk-link">🪂 Meteo Parapente</a>
      <a href="https://www.windguru.cz/49928" target="_blank" rel="noopener" class="mtn-avk-link">💨 Windguru — Celje</a>
      <a href="https://www.xcskies.com/" target="_blank" rel="noopener" class="mtn-avk-link">☁️ XCSkies</a>
      <a href="https://www.burnair.ch/" target="_blank" rel="noopener" class="mtn-avk-link">🔥 Burnair</a>
      <a href="https://www.paraglidingmap.com/" target="_blank" rel="noopener" class="mtn-avk-link">🗺 ParaglidingMap</a>
      <a href="https://www.xcontest.org/world/sl/" target="_blank" rel="noopener" class="mtn-avk-link">🏆 XContest SI</a>
      <a href="https://skysight.io/" target="_blank" rel="noopener" class="mtn-avk-link">🔭 SkySight</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model uporablja iste vhodne podatke (Open-Meteo) in enake formule kot živi pripomoček na
  <a href="/">naslovni strani Meteorec</a> (zavihek »Padalci«).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, pct, fly_hours, qa


def main():
    print(f"[{TODAY}] Pridobivam napoved Open-Meteo …")
    try:
        data = fetch_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju napovedi: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        body, pct, fly_hours, qa = build_body(data)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/vreme-za-padalce/"
    title = "Vreme za padalce — Zgornja Savinjska dolina"
    desc = (f"Ocena primernosti za jadralno padalstvo danes: {pct} %, {fly_hours} ur ugodnega okna. "
            f"Konvekcijski strop, veter, CAPE in 7-dnevni pregled za Zgornjo Savinjsko dolino.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme za padalce", None)]),
        seo.faq_schema(qa),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("vreme-za-padalce/index.html", html, force=True)
    print(f"  → vreme-za-padalce/index.html ({pct} %, {fly_hours} h)")


if __name__ == "__main__":
    main()
