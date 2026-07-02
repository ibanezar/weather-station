#!/usr/bin/env python3
"""
tools/generate_vodostaj_page.py — Vodostaj Savinje pillar page

Generates /vodostaj-savinje/index.html: current flow/level status for the
Savinja through Zgornja Savinjska dolina, a 7-day GloFAS discharge outlook,
and the historical flood timeline (culminating in August 2023). Mirrors the
logic of the homepage's "Vodostaj" tab (app.js: fetchFlood/initVodostaj) but
renders server-side from two public sources so the page is static/crawlable:

  - Open-Meteo Flood API (GloFAS) for the 7-day discharge outlook at Rečica
  - ARSO's public hydro XML feed for real measured levels/flow/water
    temperature at gauge stations along the Savinja

Usage:
  python3 tools/generate_vodostaj_page.py
"""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

FORECAST_DAYS = 7
REF_LAT, REF_LON = 46.3258, 14.9211  # Rečica ob Savinji, za razvrščanje postaj po bližini

# Isti pragovi kot na živem pripomočku (app.js _RIVER_THRESHOLDS), umerjeni
# na postajo Letuš.
THRESHOLDS = {"raised": 80, "warning": 200, "alarm": 400}

DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

FLOOD_HISTORY = [
    {"date": "November 1990", "q": 820, "desc": "Poplave Savinje — ena prvih večjih po vojni, škoda po celotni dolini."},
    {"date": "Oktober 1998", "q": 950, "desc": "Katastrofalne poplave Zgornje Savinjske doline, škoda presegla 100 mio DEM."},
    {"date": "November 2000", "q": 680, "desc": "Hude poplave, prelitje nasipov pri Letušu in Nazarjah."},
    {"date": "September 2007", "q": 420, "desc": "Poplave po dolgotrajnih padavinah, lokalne evakuacije."},
    {"date": "November 2012", "q": 310, "desc": "Povečan pretok, opozorilo ARSO — brez večjih škod."},
    {"date": "Avgust 2023", "q": 1100, "desc": "Katastrofalne poplave — zgodovinski rekord Savinje, škoda presegla 500 mio €."},
]


def fetch_flood_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "daily": "river_discharge,river_discharge_mean,river_discharge_max",
        "forecast_days": FORECAST_DAYS,
    })
    url = f"https://flood-api.open-meteo.com/v1/flood?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_arso_stations():
    req = urllib.request.Request(
        "https://www.arso.gov.si/xml/vode/hidro_podatki_zadnji.xml",
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/xml,text/xml,*/*",
                 "Referer": "https://www.arso.gov.si/"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    root = ET.fromstring(data)
    out = []
    for p in root.findall("postaja"):
        reka = (p.findtext("reka") or "")
        if "savinj" not in reka.lower():
            continue
        try:
            lat = float(p.get("wgs84_sirina"))
            lon = float(p.get("wgs84_dolzina"))
        except (TypeError, ValueError):
            continue

        def to_float(tag):
            v = p.findtext(tag)
            try:
                return float(v) if v not in (None, "") else None
            except ValueError:
                return None

        out.append({
            "name": (p.findtext("ime_kratko") or p.findtext("merilno_mesto") or "ARSO").strip(),
            "lat": lat, "lon": lon,
            "vodostaj": to_float("vodostaj"),
            "pretok": to_float("pretok"),
            "temp": to_float("temp_vode"),
            "dist2": (lat - REF_LAT) ** 2 + (lon - REF_LON) ** 2,
        })
    out.sort(key=lambda s: s["dist2"])
    return out


def flow_status(q, mean):
    ratio = (q / mean) if mean else 1.0
    if ratio < 0.6:
        return "Nizek pretok", ratio
    if ratio < 1.5:
        return "Normalen pretok", ratio
    if ratio < 2.5:
        return "Povišan pretok", ratio
    return "Visok pretok", ratio


def station_status(q):
    if q is None:
        return "—"
    if q >= THRESHOLDS["alarm"]:
        return "Alarm"
    if q >= THRESHOLDS["warning"]:
        return "Opozorilo"
    if q >= THRESHOLDS["raised"]:
        return "Povečan"
    return "Normalen"


def build_body(flood, stations):
    d = flood.get("daily") or {}
    discharge = [v for v in (d.get("river_discharge") or []) if v is not None]
    if not discharge:
        raise ValueError("Open-Meteo Flood API brez podatkov o pretoku")
    today_q = discharge[0]
    mean_list = d.get("river_discharge_mean") or []
    mean_q = mean_list[0] if mean_list and mean_list[0] is not None else sum(discharge) / len(discharge)
    max7 = max(discharge)
    status, ratio = flow_status(today_q, mean_q)

    nearest = stations[0] if stations else None
    nearest_txt = ""
    if nearest and nearest.get("pretok") is not None:
        nearest_txt = (f" Najbližja merilna postaja ARSO ({nearest['name']}) trenutno meri "
                        f"{seo.num(nearest['pretok'], 1)} m³/s"
                        + (f" in vodostaj {seo.num(nearest['vodostaj'], 0)} cm" if nearest.get("vodostaj") is not None else "")
                        + ".")

    answer = (f'  <p class="archive-intro">Napoved pretoka Savinje pri Rečici ob Savinji za danes je '
              f'<strong>{seo.num(today_q, 1)} m³/s</strong> ({status.lower()}, {round(ratio * 100)} % tipične vrednosti '
              f'{seo.num(mean_q, 1)} m³/s).{nearest_txt} Podatki GloFAS in ARSO se osvežujejo dnevno — '
              f'nazadnje {TODAY.isoformat()}.</p>')

    warn_box = ""
    if ratio >= 2.5:
        warn_box = ('  <div class="partial-note">⚠️ Pretok znatno presega normalo — spremljaj uradna opozorila ARSO '
                     'in URSZR. Avgusta 2023 je Savinja pri Letušu dosegla 1100 m³/s.</div>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-rain">
      <div class="sc-label">Pretok danes</div>
      <div class="sc-val">{seo.num(today_q, 1)}</div>
      <div class="sc-sub">m³/s · {status} · Rečica ob Savinji</div>
    </div>
    <div class="stat-card c-up">
      <div class="sc-label">Maks. v napovedi (7 dni)</div>
      <div class="sc-val">{seo.num(max7, 1)}</div>
      <div class="sc-sub">m³/s · GloFAS</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Tipičen pretok</div>
      <div class="sc-val">{seo.num(mean_q, 1)}</div>
      <div class="sc-sub">m³/s · {round(ratio * 100)} % tega danes</div>
    </div>
  </div>
{warn_box}'''

    # ── ARSO stations table ────────────────────────────────────────────────
    if stations:
        st_rows = "\n".join(
            f'      <tr><th>{s["name"]}</th>'
            f'<td>{seo.num(s["vodostaj"], 0) if s["vodostaj"] is not None else "—"} cm · '
            f'{seo.num(s["pretok"], 1) if s["pretok"] is not None else "—"} m³/s · '
            f'{station_status(s["pretok"])}</td></tr>'
            for s in stations[:6]
        )
        st_table = f'  <table class="stats">\n{st_rows}\n  </table>'
    else:
        st_table = '  <p class="muted-note">Postaje ARSO trenutno niso dosegljive.</p>'

    # ── 7-day GloFAS outlook ───────────────────────────────────────────────
    times = d.get("time") or []
    out_rows = []
    for k, q in enumerate(discharge[:FORECAST_DAYS]):
        if k < len(times):
            dt = datetime.date.fromisoformat(times[k])
            lbl = "danes" if k == 0 else DAN_KRATKO[dt.weekday()] + f" {dt.day}. {dt.month}."
        else:
            lbl = f"+{k} d"
        out_rows.append((lbl, q))
    outlook_table = '  <table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{seo.num(q, 1)} m³/s</td></tr>' for lbl, q in out_rows
    ) + "\n  </table>"

    # ── Flood history ───────────────────────────────────────────────────────
    max_hist_q = max(e["q"] for e in FLOOD_HISTORY)
    hist_rows = "\n".join(
        f'      <tr><th>{e["date"]}</th><td>{e["q"]} m³/s — {e["desc"]}</td></tr>'
        for e in reversed(FLOOD_HISTORY)
    )
    hist_table = f'  <table class="stats">\n{hist_rows}\n  </table>'

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kakšen je trenutni pretok Savinje pri Rečici ob Savinji?",
         f"Po napovedi GloFAS (Open-Meteo) je pretok Savinje danes okoli {seo.num(today_q, 1)} m³/s, "
         f"kar je {round(ratio * 100)} % tipične vrednosti za ta datum."),
        ("Kdaj je bila zadnja večja poplava Savinje?",
         "Najhujša doslej zabeležena poplava je bila avgusta 2023, ko je pretok pri Letušu dosegel približno "
         "1100 m³/s in povzročil škodo za več kot 500 milijonov evrov po vsej Zgornji Savinjski dolini."),
        ("Kaj pomenijo pragovi 'povečan', 'opozorilo' in 'alarm'?",
         "Gre za okvirne pragove pretoka Savinje (izhodišče postaja Letuš): povečan pretok od približno "
         "80 m³/s, opozorilo od 200 m³/s, alarm od 400 m³/s naprej. To niso uradni ARSO/URSZR pragovi, "
         "temveč orientacijska ocena za hitro presojo razmer."),
        ("Kje spremljam uradna opozorila pred poplavami?",
         "Uradna opozorila objavljata ARSO (meteo.arso.gov.si) in Uprava RS za zaščito in reševanje "
         "(gov.si/urszr); pri višjih vodostajih spremljaj tudi obvestila občine Rečica ob Savinji."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Vodostaj Savinje", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Vodostaj in pretok Savinje — Zgornja Savinjska dolina</h1>
  <p class="post-meta">GloFAS napoved (Open-Meteo) + meritve ARSO · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Merilne postaje ARSO ob Savinji</h2>
  <p class="archive-intro">Trenutno izmerjeni vodostaj, pretok in ocena stanja na postajah ARSO od izvira proti dolvodno — od Solčave do Celja.</p>
{st_table}
  <h2>Napoved pretoka — naslednjih {FORECAST_DAYS} dni</h2>
  <p class="archive-intro">GloFAS napoved pretoka Savinje pri Rečici ob Savinji.</p>
{outlook_table}
  <h2>Zgodovina poplav Savinje</h2>
  <p class="archive-intro">Največje zabeležene poplave Savinje po ocenjenem vršnem pretoku pri postaji Letuš.
  Podroben pregled poplav avgusta 2023 — vzroki, hidrološki rekordi, škoda in obnova — je v
  <a href="/blog/poplave-2023.html">ločenem članku na blogu</a>.</p>
{hist_table}
  <h2>Kako brati pragove pretoka</h2>
  <p class="archive-intro">Pragovi na tej strani (povečan, opozorilo, alarm) so orientacijska ocena, umerjena na
  postajo Letuš, in niso uradna klasifikacija ARSO ali URSZR. Namenjeni so hitri presoji, ali je pretok Savinje
  v danem trenutku bistveno nad običajnim za ta del leta — pri dejanski nevarnosti vedno upoštevaj uradna
  opozorila.</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🚨 Uradni viri in opozorila</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://meteo.arso.gov.si/met/sl/warning/" target="_blank" rel="noopener" class="mtn-avk-link">🌊 ARSO — hidrološka opozorila</a>
      <a href="https://www.gov.si/drzavni-organi/organi-v-sestavi/uprava-za-zascito-in-resevanje/" target="_blank" rel="noopener" class="mtn-avk-link">🛟 URSZR</a>
      <a href="https://vode.arso.gov.si/hidarhiv/" target="_blank" rel="noopener" class="mtn-avk-link">📈 ARSO — hidrološki arhiv</a>
    </div>
  </div>
{faq_html}
  <p class="muted-note">Model pretoka uporablja iste vhodne podatke (GloFAS/Open-Meteo, ARSO) kot živi pripomoček
  na <a href="/">naslovni strani Meteorec</a> (zavihek »Vodostaj«).</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, today_q, status, ratio


def main():
    print(f"[{TODAY}] Pridobivam napoved GloFAS in postaje ARSO …")
    try:
        flood = fetch_flood_forecast()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju GloFAS napovedi: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        stations = fetch_arso_stations()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ET.ParseError) as e:
        print(f"⚠ ARSO postaje nedosegljive, nadaljujem brez njih: {e}", file=sys.stderr)
        stations = []

    try:
        body, today_q, status, ratio = build_body(flood, stations)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/vodostaj-savinje/"
    title = "Vodostaj in pretok Savinje — Zgornja Savinjska dolina"
    desc = (f"Pretok Savinje danes: {seo.num(today_q, 1)} m³/s ({status.lower()}). GloFAS napoved za 7 dni, "
            f"meritve ARSO ob Savinji in zgodovina poplav vključno z avgustom 2023.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vodostaj Savinje", None)]),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("vodostaj-savinje/index.html", html, force=True)
    print(f"  → vodostaj-savinje/index.html ({seo.num(today_q, 1)} m³/s, {status})")


if __name__ == "__main__":
    main()
