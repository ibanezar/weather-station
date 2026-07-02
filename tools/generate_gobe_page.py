#!/usr/bin/env python3
"""
tools/generate_gobe_page.py — Gobarska napoved pillar page

Generates /gobarska-napoved/index.html: a server-rendered mushroom-foraging
forecast for Zgornja Savinjska dolina. Mirrors the fruiting-score model used
by the live "Gobarji" tab on the homepage (app.js: initGobe/_gobeScore) so
the two never disagree, but renders everything as static HTML/text — no
client-side fetch — so the content is crawlable and citable.

Data source: Open-Meteo forecast API (daily precipitation/temperature +
hourly soil moisture/temperature/humidity), same as the homepage widget.

Usage:
  python3 tools/generate_gobe_page.py
"""
import json, os, sys, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

GOBE_SPOTS = [
    {"name": "Rečica ob Savinji", "lat": 46.326, "lon": 14.921, "elev": "≈400 m"},
    {"name": "Dobrovlje – Čreta",  "lat": 46.300, "lon": 14.860, "elev": "≈900 m"},
    {"name": "Logarska dolina",    "lat": 46.392, "lon": 14.628, "elev": "≈750 m"},
    {"name": "Golte",              "lat": 46.348, "lon": 14.840, "elev": "≈1300 m"},
    {"name": "Smrekovško pogorje", "lat": 46.430, "lon": 14.860, "elev": "≈1300 m"},
]

SPECIES = {
    "boletus":    {"ic": "🍄", "nm": "Jurček (goban)", "nt": "Listnati in iglasti gozdovi; 2–3 tedne po dežju, tla 12–18 °C. Pogost v Savinjski dolini in Kamniško-Savinjskih Alpah."},
    "chant":      {"ic": "🟡", "nm": "Lisička", "nt": "Mahovita, vlažna tla pod smreko in bukvijo; prenese več dežja kot jurček."},
    "morel":      {"ic": "🟤", "nm": "Smrček (mavrah)", "nt": "Pomladanska goba; gaji, jesenovi logi, ob potokih; tla 8–15 °C. Sezona: marec–maj."},
    "stmgeorge":  {"ic": "⚪", "nm": "Majska goba (pripravljavnica)", "nt": "Travniki in robovi gozda v aprilu in maju; raste v skupinah."},
    "chestnut":   {"ic": "🌰", "nm": "Turek / kostanjevka", "nt": "Pod kostanjem in hrastom; topli jesenski dnevi, tla 10–16 °C."},
    "parasol":    {"ic": "☂️", "nm": "Orjaški dežnik", "nt": "Travniki in poseke; pozno poletje in jesen. Zamenljiv s strupenim dežnikom – preveri!"},
    "winter":     {"ic": "❄️", "nm": "Zimska panjevka", "nt": "Na štorih listavcev; raste ob nizkih temperaturah in blagi zmrzali."},
    "oyster":     {"ic": "🦪", "nm": "Bukov ostrigar", "nt": "Na bukovih in topolovih deblih; pozna jesen in zima."},
    "warn":       {"ic": "☠️", "nm": "Pozor: nevarne dvojnice!", "nt": "Mušnice in druge nevarne vrste rastejo sočasno z jedilnimi – natančno preveri vsako gobo!"},
}
BY_MONTH = [
    ["winter", "oyster"],
    ["winter", "oyster"],
    ["morel"],
    ["morel", "stmgeorge"],
    ["stmgeorge", "morel", "boletus"],
    ["boletus", "chant", "warn"],
    ["boletus", "chant", "warn"],
    ["boletus", "chant", "parasol", "warn"],
    ["boletus", "chant", "chestnut", "parasol", "warn"],
    ["boletus", "chant", "chestnut", "parasol", "warn"],
    ["chant", "winter", "oyster"],
    ["winter", "oyster"],
]
MES_FULL = ["januarju", "februarju", "marcu", "aprilu", "maju", "juniju",
            "juliju", "avgustu", "septembru", "oktobru", "novembru", "decembru"]
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

PAST_DAYS = 14
FORECAST_DAYS = 7


def fetch_forecast():
    lats = ",".join(str(s["lat"]) for s in GOBE_SPOTS)
    lons = ",".join(str(s["lon"]) for s in GOBE_SPOTS)
    params = urllib.parse.urlencode({
        "latitude": lats,
        "longitude": lons,
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min",
        "hourly": "soil_moisture_3_to_9cm,soil_temperature_6cm,relative_humidity_2m",
        "past_days": PAST_DAYS,
        "forecast_days": FORECAST_DAYS,
        "timezone": "Europe/Ljubljana",
    }, safe=",")
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    return data if isinstance(data, list) else [data]


def daily_agg(loc):
    """Aggregate hourly soil/RH to daily means, keyed by ISO date."""
    h = loc.get("hourly") or {}
    times = h.get("time") or []
    buckets = {}
    for i, t in enumerate(times):
        d = t[:10]
        o = buckets.setdefault(d, {"sm": 0.0, "smn": 0, "st": 0.0, "stn": 0, "rh": 0.0, "rhn": 0})
        sm = (h.get("soil_moisture_3_to_9cm") or [None] * len(times))[i]
        st = (h.get("soil_temperature_6cm") or [None] * len(times))[i]
        rh = (h.get("relative_humidity_2m") or [None] * len(times))[i]
        if sm is not None:
            o["sm"] += sm; o["smn"] += 1
        if st is not None:
            o["st"] += st; o["stn"] += 1
        if rh is not None:
            o["rh"] += rh; o["rhn"] += 1
    out = {}
    for d, o in buckets.items():
        out[d] = {
            "sm": (o["sm"] / o["smn"]) if o["smn"] else None,
            "st": (o["st"] / o["stn"]) if o["stn"] else None,
            "rh": (o["rh"] / o["rhn"]) if o["rhn"] else None,
        }
    return out


def today_idx(loc):
    times = (loc.get("daily") or {}).get("time") or []
    iso = TODAY.isoformat()
    return times.index(iso) if iso in times else PAST_DAYS


def gobe_inputs(loc, agg, i):
    d = loc.get("daily") or {}
    precip = d.get("precipitation_sum") or []
    def rain_at(k):
        return precip[k] if 0 <= k < len(precip) and precip[k] is not None else 0
    ar = sum(rain_at(k) for k in range(i - 12, i - 3))  # inclusive i-12..i-4
    times = d.get("time") or []
    date = times[i] if 0 <= i < len(times) else None
    a = agg.get(date) if date else None
    tmax_l = d.get("temperature_2m_max") or []
    tmin_l = d.get("temperature_2m_min") or []
    tmax = tmax_l[i] if 0 <= i < len(tmax_l) else None
    tmin = tmin_l[i] if 0 <= i < len(tmin_l) else None
    if tmax is not None and tmin is not None:
        tmean = (tmax + tmin) / 2
    else:
        tmean = tmax if tmax is not None else tmin
    return {"ar": ar, "sm": a["sm"] if a else None, "st": a["st"] if a else None,
            "rh": a["rh"] if a else None, "tmean": tmean}


def gobe_score(inp):
    s = 0
    ar = inp["ar"]
    if ar >= 60: s += 34
    elif ar >= 35: s += 27
    elif ar >= 20: s += 18
    elif ar >= 10: s += 9
    elif ar >= 4: s += 3
    sm = inp["sm"]
    if sm is not None:
        if sm >= 0.32: s += 24
        elif sm >= 0.26: s += 18
        elif sm >= 0.20: s += 11
        elif sm >= 0.15: s += 4
    st = inp["st"]
    if st is not None:
        if 10 <= st <= 18: s += 18
        elif (7 <= st < 10) or (18 < st <= 21): s += 10
        elif 4 <= st <= 24: s += 4
    rh = inp["rh"]
    if rh is not None:
        if rh >= 85: s += 12
        elif rh >= 75: s += 8
        elif rh >= 65: s += 4
    tmean = inp["tmean"]
    if tmean is not None:
        if tmean < 2: s -= 22
        elif tmean < 5: s -= 8
        elif tmean > 26: s -= 10
    return max(0, min(100, round(s)))


def gobe_level(p):
    if p >= 75: return "ODLIČNA"
    if p >= 55: return "DOBRA"
    if p >= 35: return "ZMERNA"
    if p >= 18: return "SLABA"
    return "BREZ"


def gobe_desc(p):
    if p >= 75: return "Odlične razmere – tla vlažna in topla, gobe so verjetno v polni rasti."
    if p >= 55: return "Dobre razmere za gobe. Po izdatnem dežju je smiselno na lov."
    if p >= 35: return "Zmerne razmere – posamezne gobe možne, predvsem v vlažnih legah."
    if p >= 18: return "Slabe razmere – pretežno suho ali prehladno za obrodnost."
    return "Brez obrodnosti – premalo vlage ali prenizke temperature."


def build_body(locs):
    aggs = [daily_agg(loc) for loc in locs]
    primary, primary_agg = locs[0], aggs[0]
    ti = today_idx(primary)

    inp_today = gobe_inputs(primary, primary_agg, ti)
    pct_today = gobe_score(inp_today)
    lvl_today = gobe_level(pct_today)
    desc_today = gobe_desc(pct_today)

    d = primary.get("daily") or {}
    precip = d.get("precipitation_sum") or []
    rain14 = sum((precip[k] or 0) for k in range(max(0, ti - 13), ti + 1))
    dsr = None
    for k in range(ti, -1, -1):
        if k < len(precip) and (precip[k] or 0) >= 5:
            dsr = ti - k
            break
    if dsr is None:
        dsr_txt = "> 14 dni"
    elif dsr == 0:
        dsr_txt = "danes"
    elif dsr == 1:
        dsr_txt = "1 dan"
    else:
        dsr_txt = f"{dsr} dni"

    month = TODAY.month - 1  # 0-indexed
    species_now = [SPECIES[k] for k in BY_MONTH[month]]
    species_note = ("Razmere so ugodne – spodaj naštete vrste so trenutno najbolj verjetne."
                     if pct_today >= 55 else
                     "Razmere so zmerne – verjetnost je manjša, a v vlažnih legah se splača pogledati."
                     if pct_today >= 35 else
                     "Trenutno je presuho ali prehladno – kljub sezoni je obrodnost teh vrst malo verjetna.")

    # ── Answer block (AI-Overview-style summary) ─────────────────────────────
    answer = (f'  <p class="archive-intro">Danes je <strong>gobarski indeks</strong> za Rečico ob Savinji in okoliške '
              f'gozdove Zgornje Savinjske doline <strong>{pct_today} % ({lvl_today})</strong>. {desc_today} '
              f'Ocena upošteva padavine zadnjih 12 dni ({seo.num(rain14, 0)} mm v zadnjih 14 dneh), vlago in temperaturo '
              f'tal ter zračno vlago — nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-rain">
      <div class="sc-label">Gobarski indeks danes</div>
      <div class="sc-val">{pct_today} %</div>
      <div class="sc-sub">{lvl_today} · Rečica ob Savinji</div>
    </div>
    <div class="stat-card c-temp">
      <div class="sc-label">Padavine (14 dni)</div>
      <div class="sc-val">{seo.num(rain14, 0)} mm</div>
      <div class="sc-sub">sprožilec obrodnosti je dež izpred 5–12 dni</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Dni od zadnjega dežja ≥ 5 mm</div>
      <div class="sc-val">{dsr_txt}</div>
      <div class="sc-sub">Rečica ob Savinji</div>
    </div>
  </div>'''

    # ── Nearby forests comparison ─────────────────────────────────────────────
    rows = []
    for loc, agg, spot in zip(locs, aggs, GOBE_SPOTS):
        ti_s = today_idx(loc)
        pct = gobe_score(gobe_inputs(loc, agg, ti_s))
        rows.append((spot["name"], spot["elev"], pct, gobe_level(pct)))
    rows.sort(key=lambda r: r[2], reverse=True)
    spots_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{name} <span class="muted-note" style="margin:0;display:inline">({elev})</span></th>'
        f'<td>{pct} % — {lvl}</td></tr>'
        for name, elev, pct, lvl in rows
    ) + "\n  </table>"

    # ── 7-day outlook for the primary spot ────────────────────────────────────
    times = d.get("time") or []
    out_rows = []
    for k in range(ti, min(ti + FORECAST_DAYS, len(times))):
        inp = gobe_inputs(primary, primary_agg, k)
        pct = gobe_score(inp)
        lvl = gobe_level(pct)
        import datetime as _dt
        dt = _dt.date.fromisoformat(times[k])
        lbl = "danes" if k == ti else DAN_KRATKO[dt.weekday()] + f" {dt.day}. {dt.month}."
        rain = precip[k] if k < len(precip) and precip[k] is not None else 0
        out_rows.append((lbl, rain, pct, lvl))
    outlook_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{seo.num(rain, 0)} mm · {pct} % ({lvl})</td></tr>'
        for lbl, rain, pct, lvl in out_rows
    ) + "\n  </table>"

    # ── Species this month + full calendar ────────────────────────────────────
    species_now_html = "\n".join(
        f'    <div class="gobe-sp"><span class="gobe-sp-ic">{s["ic"]}</span>'
        f'<div><div class="gobe-sp-nm">{s["nm"]}</div><div class="gobe-sp-nt">{s["nt"]}</div></div></div>'
        for s in species_now
    )
    calendar_rows = []
    for m in range(12):
        names = ", ".join(SPECIES[k]["nm"] for k in BY_MONTH[m] if k != "warn")
        warn = " ☠️" if "warn" in BY_MONTH[m] else ""
        calendar_rows.append((seo.MES_NOM[m + 1].capitalize(), names + warn))
    calendar_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{mn}</th><td style="text-align:left">{sp}</td></tr>' for mn, sp in calendar_rows
    ) + "\n  </table>"

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kdaj rastejo jurčki v Savinjski dolini?",
         "Jurčki (gobani) v Zgornji Savinjski dolini najpogosteje rastejo od maja do oktobra, "
         "2–3 tedne po izdatnem dežju, ko je temperatura tal med 12 in 18 °C. Najboljša meseca sta "
         "praviloma junij in september."),
        ("Koliko dni po dežju zrastejo gobe?",
         "Večina gozdnih vrst (jurček, lisička) potrebuje 5–12 dni po izdatnejšem dežju (vsaj 20–30 mm), "
         "da se sproži obrodnost — to je t. i. zamik rasti, ki ga upošteva tudi gobarski indeks na tej strani."),
        (f"Katere gobe trenutno (v {MES_FULL[month]}) rastejo v Zgornji Savinjski dolini?",
         "Trenutno so v sezoni: " + ", ".join(s["nm"] for s in species_now if s is not SPECIES["warn"]) + "."),
        ("Koliko gob smem nabrati na dan?",
         "V Sloveniji je dovoljeno nabrati do 2 kg gob na osebo na dan (Uredba o varstvu samoniklih gliv)."),
        ("Ali je gobarski indeks na tej strani napoved ali meritev?",
         "Gre za model, izračunan iz napovedi Open-Meteo (padavine, vlaga in temperatura tal, zračna vlaga) "
         "po istem algoritmu kot živi pripomoček na naslovni strani Meteorec — ni uradna napoved ARSO."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Gobarska napoved", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Gobarska napoved — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Model rasti gob iz podatkov Open-Meteo · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Okoliški gozdovi — primerjava danes</h2>
  <p class="archive-intro">Gobarski indeks za pet znanih nabiralnih območij Zgornje Savinjske doline, izračunan iz istih vhodnih podatkov (vlaga in temperatura tal, padavine, zračna vlaga).</p>
{spots_table}
  <h2>Napoved obrodnosti — naslednjih {FORECAST_DAYS} dni</h2>
  <p class="archive-intro">Okno obrodnosti za Rečico ob Savinji. Višja padavinska vsota 5–12 dni nazaj praviloma dvigne indeks z zamikom.</p>
{outlook_table}
  <h2>Kaj utegne rasti v {MES_FULL[month]}</h2>
  <p class="archive-intro">{species_note}</p>
  <div class="card" style="margin-bottom:1rem">
{species_now_html}
  </div>
  <h2>Gobarski koledar — Zgornja Savinjska dolina po mesecih</h2>
{calendar_table}
  <h2>Kako izračunamo gobarski indeks</h2>
  <p class="archive-intro">Indeks (0–100 %) sešteje pet dejavnikov: <strong>predhodne padavine</strong> (vsota dežja
  5–12 dni pred izbranim dnem — jurčki in lisičke fruktificirajo z zamikom, ne takoj po dežju), <strong>vlago tal</strong>
  na globini 3–9 cm, <strong>temperaturo tal</strong> na 6 cm (optimalno 10–18 °C), <strong>relativno zračno vlago</strong>
  in <strong>povprečno dnevno temperaturo zraka</strong> (pod 2 °C ali nad 26 °C obrodnost zavira). Vhodni podatki so
  napoved Open-Meteo za pet točk v dolini; model je enak tistemu, ki poganja živi pripomoček na naslovni strani.</p>
  <h2>Kje nabirati v Zgornji Savinjski dolini</h2>
  <p class="archive-intro"><strong>Dobrovlje – Čreta</strong> (≈900 m) je mešan gozd nad Rečico z dobro vlago v spodnjem
  sloju. <strong>Logarska dolina</strong> (≈750 m) ponuja hladnejšo, bolj zasenčeno klimo pod Kamniško-Savinjskimi Alpami
  — kasnejša, a daljša sezona. <strong>Golte</strong> in <strong>Smrekovško pogorje</strong> (obe ≈1300 m) sta iglasta
  gozdova na višji nadmorski višini, kjer sezona jurčkov in lisičk pogosto traja dlje v jesen kot na dnu doline.</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">📋 Nasveti in pravila</div>
    <div style="font-size:.85rem;color:var(--muted);line-height:1.7;margin-top:.5rem">
      ⚖️ V Sloveniji je dovoljeno nabrati <b>do 2 kg gob na osebo na dan</b> (Uredba o varstvu samoniklih gliv).<br>
      🧺 Gobe nosi v zračni košari, ne v vrečki — trosi se tako raznašajo.<br>
      🔪 Gobo izvij ali odreži pri dnu in mesto rahlo prekrij.<br>
      ☠️ <b>Nikoli ne uživaj gobe, ki je ne poznaš 100 %.</b> Ob dvomu se posvetuj z gobarskim društvom ali mikologom.<br>
      🌡 Najboljše razmere: vlažna tla, temperatura tal 10–18 °C, nekaj dni po izdatnem dežju.
    </div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.gobe.si/" target="_blank" rel="noopener" class="mtn-avk-link">🍄 Gobe.si</a>
      <a href="https://www.gobarskazveza.si/" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 Gobarska zveza Slovenije</a>
      <a href="https://meteo.arso.gov.si/met/sl/agromet/" target="_blank" rel="noopener" class="mtn-avk-link">🌱 ARSO — agrometeorologija</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model gobarskega indeksa uporablja iste vhodne podatke in isti algoritem kot živi pripomoček
  na <a href="/">naslovni strani Meteorec</a> (zavihek »Gobarji«), kjer lahko premikaš napoved po dnevih naprej.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, pct_today, lvl_today, desc_today


def main():
    print(f"[{TODAY}] Pridobivam napoved Open-Meteo za {len(GOBE_SPOTS)} lokacij …")
    try:
        locs = fetch_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju napovedi: {e}", file=sys.stderr)
        sys.exit(1)
    if len(locs) != len(GOBE_SPOTS):
        print(f"✗ Nepričakovano število lokacij v odgovoru ({len(locs)} namesto {len(GOBE_SPOTS)})", file=sys.stderr)
        sys.exit(1)

    body, pct_today, lvl_today, desc_today = build_body(locs)

    url = "/gobarska-napoved/"
    title = "Gobarska napoved — Zgornja Savinjska dolina"
    desc = (f"Gobarski indeks danes: {pct_today} % ({lvl_today}). {desc_today} Napoved za pet gozdov "
            f"Zgornje Savinjske doline, gobarski koledar po mesecih in razlaga modela.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Gobarska napoved", None)]),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("gobarska-napoved/index.html", html, force=True)
    print(f"  → gobarska-napoved/index.html ({pct_today} %, {lvl_today})")


if __name__ == "__main__":
    main()
