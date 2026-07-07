#!/usr/bin/env python3
"""
tools/generate_agrometeo_page.py — Agrometeo pillar page

Generates /agrometeo/index.html: growing-degree-day accumulation, hop
phenology stage + disease risk, a per-crop GDD milestone table, a 7-day
frost alarm, spray-window and hay-drying-window outlooks, and a 14-day +
7-day water balance for Zgornja Savinjska dolina. Ports the homepage's
"Agrometeo" tab (app.js: initAgro/_buildAgro*) to Python — GDD/rain
accumulation comes from history.json (real station measurements, more
authoritative than the tab's localStorage cache), everything forward-looking
comes from the same Open-Meteo forecast fields the tab uses.

Usage:
  python3 tools/generate_agrometeo_page.py
"""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

DAN_KRATKO = ["ned", "pon", "tor", "sre", "čet", "pet", "sob"]

# Fenološki pragovi hmelja so vezani na GDD₁₀ (baza 10 °C — agronomski standard za
# hmelj), umerjeni na večletno akumulacijo postaje IREICA1: cvetenje se pri ~600
# začne v začetku julija, obiranje pri ~1250 pade v začetek septembra.
HOP_STAGES = [
    (0, 60, "Mirovanje", "💤"),
    (60, 150, "Odganjanje poganjkov", "🌱"),
    (150, 400, "Vzdolžna rast trt", "🌿"),
    (400, 600, "Stransko razvejanje", "🌾"),
    (600, 950, "Cvetenje in razvoj storžkov", "🌸"),
    (950, 1250, "Oblikovanje storžkov", "🍺"),
    (1250, float("inf"), "Tehnološka zrelost / obiranje", "🎉"),
]

CROP_GDD = [
    ("Hmelj", "🌿", 10, [(150, "odganjanje"), (400, "razvejanje"), (600, "cvetenje"), (950, "storžki"), (1250, "obiranje")]),
    ("Koruza", "🌽", 10, [(100, "kalitev"), (600, "svilanje"), (1300, "metličenje"), (2400, "spravilo")]),
    ("Krompir", "🥔", 7, [(200, "vznik"), (500, "nastavljanje gomoljev"), (1000, "debelitev gomoljev"), (1500, "spravilo")]),
    ("Pšenica", "🌾", 5, [(200, "vznik"), (600, "kolenčenje"), (1200, "klasenje"), (2000, "žetev")]),
    ("Trava", "🌱", 5, [(100, "1. porast"), (400, "1. košnja"), (800, "2. košnja"), (1200, "3. košnja")]),
]


def load_history():
    return json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))


def calc_accum(hist):
    year = TODAY.year
    today_s = TODAY.isoformat()
    d30 = (TODAY - datetime.timedelta(days=30)).isoformat()
    d14 = (TODAY - datetime.timedelta(days=14)).isoformat()
    gdd5 = gdd10 = rain30 = 0.0
    rain14_rows = []
    for k in sorted(hist.keys()):
        v = hist[k]
        th, tl, ta = v.get("tempHigh"), v.get("tempLow"), v.get("tempAvg")
        avg = (th + tl) / 2 if (th is not None and tl is not None) else ta
        if f"{year}-01-01" <= k <= today_s and avg is not None:
            gdd5 += max(0, avg - 5)
            gdd10 += max(0, avg - 10)
        if d30 <= k <= today_s:
            rain30 += v.get("precipTotal") or 0
        if d14 <= k <= today_s:
            rain14_rows.append((k, v.get("precipTotal")))
    return round(gdd5), round(gdd10), round(rain30), rain14_rows


def fetch_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,is_day",
        "daily": "et0_fao_evapotranspiration,precipitation_sum,sunshine_duration,"
                  "temperature_2m_max,temperature_2m_min",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 7,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def hop_stage(gdd10):
    for lo, hi, label, emoji in HOP_STAGES:
        if lo <= gdd10 < hi:
            return lo, hi, label, emoji
    return HOP_STAGES[-1]


def hop_disease_risk(rh, temp):
    dm = max(0, min(100, (rh - 60) / 30 * 60 + (30 if 10 < temp < 25 else 0)))
    pm = max(0, min(100, (40 if 15 < temp < 28 else 0) + (40 if 45 < rh < 80 else 0) + (20 if 18 < temp < 26 else 0)))
    bot = max(0, min(100, (50 if rh > 80 else 0) + (30 if 15 < temp < 22 else 0) + (20 if rh > 90 else 0)))
    return [
        ("Hmeljeva peronospora", dm, "T > 10 °C + visoka vlaga"),
        ("Hmeljeva pepelovka", pm, "T 15–27 °C + zmerna vlaga"),
        ("Siva plesen (Botrytis)", bot, "T 15–22 °C + vlaga > 80 %"),
    ]


def risk_label(pct):
    return "Nizko" if pct < 30 else "Zmerno" if pct < 60 else "Visoko"


def build_body(hist, fc):
    gdd5, gdd10, rain30, rain14_rows = calc_accum(hist)
    daily = fc.get("daily") or {}
    hourly = fc.get("hourly") or {}

    et0 = (daily.get("et0_fao_evapotranspiration") or [None])[0] or 0
    sun_h = ((daily.get("sunshine_duration") or [0])[0] or 0) / 3600
    today_rain = (daily.get("precipitation_sum") or [0])[0] or 0
    wbal_today = today_rain - et0

    # ── hop phenology + disease risk (current hour) ─────────────────────────
    lo, hi, stage_label, stage_emoji = hop_stage(gdd10)
    now_hour = datetime.datetime.now().hour
    rh_now = (hourly.get("relative_humidity_2m") or [70] * 24)[now_hour] if hourly.get("relative_humidity_2m") else 70
    t_now = (hourly.get("temperature_2m") or [15] * 24)[now_hour] if hourly.get("temperature_2m") else 15
    diseases = hop_disease_risk(rh_now, t_now)

    # ── answer block ─────────────────────────────────────────────────────────
    answer = (f'  <p class="archive-intro">Vsota efektivnih temperatur za Zgornjo Savinjsko dolino je danes '
              f'<strong>GDD₅ {gdd5}</strong> in <strong>GDD₁₀ {gdd10}</strong> (od 1. januarja {TODAY.year}). '
              f'Hmelj je po vsoti GDD₁₀ v fazi <strong>{stage_label.lower()}</strong>. Danes: ET₀ {seo.num(et0, 1)} mm, '
              f'sonce {seo.num(sun_h, 1)} h, vodna bilanca {"+" if wbal_today >= 0 else ""}{seo.num(wbal_today, 1)} mm '
              f'— nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-up">
      <div class="sc-label">GDD₅ letos</div>
      <div class="sc-val">{gdd5}</div>
      <div class="sc-sub">od 1. jan. {TODAY.year}</div>
    </div>
    <div class="stat-card c-temp">
      <div class="sc-label">ET₀ danes</div>
      <div class="sc-val">{seo.num(et0, 1)}</div>
      <div class="sc-sub">mm/dan</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Padavine (30 dni)</div>
      <div class="sc-val">{rain30}</div>
      <div class="sc-sub">mm skupaj</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Vodna bilanca danes</div>
      <div class="sc-val">{"+" if wbal_today >= 0 else ""}{seo.num(wbal_today, 1)}</div>
      <div class="sc-sub">mm (padavine − ET₀)</div>
    </div>
  </div>'''

    # ── hop section ────────────────────────────────────────────────────────
    to_next = f' · do naslednje faze: {round(hi - gdd10)} GDD₁₀' if hi != float("inf") else ""
    disease_rows = "\n".join(
        f'      <tr><th>{name}</th><td>{round(pct)} % — {risk_label(pct)} <span class="muted-note" style="margin:0;display:inline">({note})</span></td></tr>'
        for name, pct, note in diseases
    )
    hop_html = f'''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">{stage_emoji} Fenologija hmelja</div>
    <p class="archive-intro" style="margin:.4rem 0 .8rem">Trenutna faza: <strong>{stage_label}</strong> (GDD₁₀ {gdd10}{to_next}).</p>
    <table class="stats">
{disease_rows}
    </table>
  </div>'''

    # ── crop GDD table ────────────────────────────────────────────────────
    crop_rows = []
    for name, emoji, base, milestones in CROP_GDD:
        gdd = round(gdd5 * 0.72) if base == 7 else (gdd10 if base == 10 else gdd5)
        cur = [m for m in milestones if gdd >= m[0]]
        nxt = next((m for m in milestones if m[0] > gdd), None)
        stage = cur[-1][1] if cur else "pred vznikom"
        nxt_txt = f'{nxt[1]} čez {nxt[0] - gdd} GDD' if nxt else "zaključeno"
        crop_rows.append(f'      <tr><th>{emoji} {name}</th><td>{gdd} GDD — {stage} · {nxt_txt}</td></tr>')
    crop_table = '  <table class="stats">\n' + "\n".join(crop_rows) + "\n  </table>"

    # ── frost alarm (7 days) ──────────────────────────────────────────────
    fd_time = daily.get("time") or []
    tmax_l = daily.get("temperature_2m_max") or []
    tmin_l = daily.get("temperature_2m_min") or []
    frost_rows, frost_warnings = [], []
    for i in range(min(7, len(fd_time))):
        tmin, tmax = tmin_l[i] if i < len(tmin_l) else None, tmax_l[i] if i < len(tmax_l) else None
        dt = datetime.date.fromisoformat(fd_time[i])
        lbl = "danes" if i == 0 else DAN_KRATKO[(dt.weekday() + 1) % 7] + f" {dt.day}. {dt.month}."
        if tmin is None:
            badge = "—"
        elif tmin <= -3:
            badge = "Pozeba!"; frost_warnings.append((lbl, tmin))
        elif tmin < 0:
            badge = "Zmrzal"; frost_warnings.append((lbl, tmin))
        elif tmin < 3:
            badge = "Pozor"
        else:
            badge = "Varno"
        frost_rows.append(f'      <tr><th>{lbl}</th><td>{seo.num(tmax) if tmax is not None else "—"} / '
                           f'{seo.num(tmin) if tmin is not None else "—"} °C — {badge}</td></tr>')
    frost_table = '  <table class="stats">\n' + "\n".join(frost_rows) + "\n  </table>"
    frost_note = (f'⚠️ Predvidena je pozeba/zmrzal: ' + ", ".join(f"{lbl} ({seo.num(t)} °C)" for lbl, t in frost_warnings)
                  if frost_warnings else "✅ V prihodnjih 7 dneh ni predvidene pozebe.")

    # ── spray window (7 days) ────────────────────────────────────────────
    h_time = hourly.get("time") or []
    spray_rows = []
    for i in range(7):
        day = (TODAY + datetime.timedelta(days=i)).isoformat()
        idxs = [k for k, t in enumerate(h_time) if t.startswith(day) and 6 <= int(t[11:13]) < 20]
        if not idxs:
            continue
        ok_hours = []
        for k in idxs:
            wind = (hourly.get("wind_speed_10m") or [99] * len(h_time))[k]
            precip = (hourly.get("precipitation") or [0] * len(h_time))[k]
            temp = (hourly.get("temperature_2m") or [0] * len(h_time))[k]
            if wind is not None and precip is not None and temp is not None and wind <= 4 and precip < 0.1 and temp >= 5:
                ok_hours.append(int(h_time[k][11:13]))
        dt = datetime.date.fromisoformat(day)
        lbl = "danes" if i == 0 else DAN_KRATKO[(dt.weekday() + 1) % 7] + f" {dt.day}. {dt.month}."
        val = f'{len(ok_hours)} primernih ur' + (f' ({", ".join(f"{h}h" for h in ok_hours[:6])})' if ok_hours else "")
        spray_rows.append(f'      <tr><th>{lbl}</th><td>{val}</td></tr>')
    spray_table = '  <table class="stats">\n' + "\n".join(spray_rows) + "\n  </table>"

    # ── hay drying windows (5 days) ──────────────────────────────────────
    windows, cur = [], None
    for i in range(min(len(h_time), 5 * 24)):
        is_day = (hourly.get("is_day") or [0] * len(h_time))[i]
        precip = (hourly.get("precipitation") or [1] * len(h_time))[i] or 0
        rh = (hourly.get("relative_humidity_2m") or [100] * len(h_time))[i]
        temp = (hourly.get("temperature_2m") or [0] * len(h_time))[i]
        good = is_day and precip < 0.1 and rh is not None and rh < 65 and temp is not None and temp >= 12
        if good:
            if cur is None:
                cur = {"start": h_time[i], "end": h_time[i], "hours": 1, "min_rh": rh, "max_t": temp}
            else:
                cur["end"] = h_time[i]; cur["hours"] += 1
                cur["min_rh"] = min(cur["min_rh"], rh); cur["max_t"] = max(cur["max_t"], temp)
        else:
            if cur and cur["hours"] >= 4:
                windows.append(cur)
            cur = None
    if cur and cur["hours"] >= 4:
        windows.append(cur)
    if windows:
        hay_rows = []
        for w in windows[:4]:
            s = datetime.datetime.fromisoformat(w["start"])
            e = datetime.datetime.fromisoformat(w["end"])
            quality = "odlično" if w["hours"] >= 8 and w["min_rh"] < 55 else "dobro" if w["hours"] >= 6 and w["min_rh"] < 60 else "zadostno"
            lbl = DAN_KRATKO[(s.weekday() + 1) % 7] + f" {s.day}. {s.month}. {s.hour:02d}:00–{e.hour:02d}:00"
            hay_rows.append(f'      <tr><th>{lbl}</th><td>{w["hours"]}h sušenja · min. vlaga {round(w["min_rh"])} % · '
                             f'maks. T {round(w["max_t"])} °C — {quality}</td></tr>')
        hay_table = '  <table class="stats">\n' + "\n".join(hay_rows) + "\n  </table>"
    else:
        hay_table = '  <p class="muted-note">⛅ V prihodnjih 5 dneh ni ugodnih oken za sušenje sena (vlaga, dež ali mraz).</p>'

    # ── water balance: 14-day history + 7-day forecast ───────────────────
    wbal_rows = []
    for k, rain in rain14_rows:
        lbl = "danes" if k == TODAY.isoformat() else k[8:10] + "." + k[5:7] + "."
        wbal_rows.append(f'      <tr><th>{lbl}</th><td>{seo.num(rain) if rain is not None else "—"} mm padavin</td></tr>')
    total_rain14 = sum((r or 0) for _, r in rain14_rows)
    for i in range(1, min(8, len(fd_time))):
        k = fd_time[i]
        rain = (daily.get("precipitation_sum") or [None] * len(fd_time))[i]
        et0_f = (daily.get("et0_fao_evapotranspiration") or [None] * len(fd_time))[i]
        lbl = k[8:10] + "." + k[5:7] + "."
        wbal_rows.append(f'      <tr><th>{lbl} (napoved)</th><td>{seo.num(rain) if rain is not None else "—"} mm padavin · '
                          f'ET₀ {seo.num(et0_f) if et0_f is not None else "—"} mm</td></tr>')
    wbal_table = '  <table class="stats">\n' + "\n".join(wbal_rows) + "\n  </table>"

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kaj je GDD (vsota efektivnih temperatur)?",
         "GDD (Growing Degree Days) je vsota dnevnih povprečnih temperatur nad izbranim pragom (najpogosteje 5 ali "
         "10 °C), seštetih od začetka leta. Uporablja se za napovedovanje razvojnih faz rastlin — višja vsota "
         "pomeni naprednejšo rastno fazo."),
        ("V kateri fazi je hmelj trenutno v Zgornji Savinjski dolini?",
         f"Po vsoti GDD₁₀ ({gdd10} od 1. januarja {TODAY.year}) je hmelj trenutno v fazi: {stage_label.lower()}."),
        ("Kdaj je okno za škropljenje primerno?",
         "Škropljenje je primerno, ko je hitrost vetra do 4 km/h, ni padavin in je temperatura vsaj 5 °C — "
         "praviloma zgodaj dopoldan ali pozno popoldan, ko je veter najšibkejši."),
        ("Kako se izračuna vodna bilanca?",
         "Vodna bilanca je razlika med padavinami in referenčno evapotranspiracijo (ET₀, FAO Penman-Monteith). "
         "Pozitivna bilanca pomeni presežek vode v tleh, negativna pa primanjkljaj, ki ga je treba nadomestiti z namakanjem."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Agrometeo", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Agrometeo — Zgornja Savinjska dolina</h1>
  <p class="post-meta">GDD, vodna bilanca in fenologija iz meritev IREICA1 + napoved Open-Meteo · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Fenologija hmelja in tveganje za bolezni</h2>
{hop_html}
  <h2>Vsota efektivnih temperatur (GDD) — po pridelkih</h2>
  <p class="archive-intro">Ocenjena razvojna faza za pet pridelkov, značilnih za Zgornjo Savinjsko dolino, glede na vsoto GDD letos.</p>
{crop_table}
  <h2>Alarm pred pozebo — naslednjih 7 dni</h2>
  <p class="archive-intro">{frost_note}</p>
{frost_table}
  <h2>Okno za škropljenje — naslednjih 7 dni</h2>
  <p class="archive-intro">Primerne ure: veter ≤ 4 km/h, brez padavin, temperatura ≥ 5 °C.</p>
{spray_table}
  <h2>Okno za sušenje sena — naslednjih 5 dni</h2>
{hay_table}
  <h2>Vodna bilanca — zadnjih 14 dni + 7-dnevna napoved</h2>
  <p class="archive-intro">Skupaj padavin v zadnjih 14 dneh: <strong>{round(total_rain14)} mm</strong>.</p>
{wbal_table}
{faq_html}
  <p class="muted-note">Model uporablja iste vhodne podatke (postaja IREICA1, Open-Meteo) in enake formule kot živi
  pripomoček na <a href="/">naslovni strani Meteorec</a> (zavihek »Agrometeo«).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, gdd5, gdd10, stage_label


def main():
    print(f"[{TODAY}] Nalagam history.json in napoved Open-Meteo …")
    hist = load_history()
    try:
        fc = fetch_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju napovedi: {e}", file=sys.stderr)
        sys.exit(1)

    body, gdd5, gdd10, stage_label = build_body(hist, fc)

    url = "/agrometeo/"
    title = "Agrometeo — Zgornja Savinjska dolina"
    desc = (f"GDD₅ {gdd5}, GDD₁₀ {gdd10} od začetka leta. Fenologija hmelja ({stage_label.lower()}), alarm pred "
            f"pozebo, okno za škropljenje in sušenje sena ter vodna bilanca za Zgornjo Savinjsko dolino.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Agrometeo", None)]),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("agrometeo/index.html", html, force=True)
    print(f"  → agrometeo/index.html (GDD₅ {gdd5}, GDD₁₀ {gdd10}, {stage_label})")


if __name__ == "__main__":
    main()
