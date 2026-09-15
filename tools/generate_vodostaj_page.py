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
# na postajo Letuš. Uporabljajo se SAMO za postaje, za katere ARSO ne objavi
# svojih pragov visokih voda — glej station_status().
THRESHOLDS = {"raised": 80, "warning": 200, "alarm": 400}

DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

# Resnost 0..3 (station_level) -> barva. Zelena je ista validirana temna
# zelena kot na MTR grafu (#34d399 na tem ozadju pade test svetlosti, glej
# opombo pri MTR_CC v app.js); amber/rdeča sta isti barvi kot .warn-banner
# .lvl-orange/.lvl-red v vreme.css — resnost mora izgledati enako povsod na
# strani, ne nova paleta samo za ta graf.
LEVEL_COLORS = ["#059669", "#f59e0b", "#fb923c", "#ef4444"]
LEVEL_LABELS = ["Normalno", "Povečano", "Opozorilo", "Alarm"]

# Grafa na tej strani sta statičen SVG, izrisan tu v Pythonu ob generiranju
# strani — ne client-side fetch+draw kot na /tocnost-napovedi/ ali
# /test-napovedi/. Razlog: vsi podatki (7-dnevna GloFAS napoved, trenutne
# meritve ARSO) so že v Pythonu v trenutku izrisa in stran se tako ali tako
# regenerira enkrat dnevno (glej post-meta besedilo) — client fetch bi tu
# pomenil nov javni JSON samo za dva grafa brez drugega odjemalca, graf pa bi
# bil brez JS prazen. Tak SVG je viden tudi crawlerjem/brez JS, kar je tu
# vrednota (isto načelo kot pri /podatki/, ki je namenoma brez JS).


def _svg_esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def outlook_chart_svg(rows, mean_q):
    """Linijski graf 7-dnevne GloFAS napovedi z vodoravno črto tipičnega pretoka."""
    W, H = 640, 220
    pad_l, pad_r, pad_t, pad_b = 34, 14, 20, 28
    plot_w, plot_h = W - pad_l - pad_r, H - pad_t - pad_b
    vals = [v for _, v in rows]
    max_v = max(vals + ([mean_q] if mean_q else [])) * 1.2 or 1

    def x(i):
        return pad_l + plot_w * (i / (len(rows) - 1) if len(rows) > 1 else 0)

    def y(v):
        return pad_t + plot_h * (1 - max(0, v) / max_v)

    parts = [f'<svg viewBox="0 0 {W} {H}" class="vod-svg" preserveAspectRatio="xMidYMid meet">']
    for f in (0, .25, .5, .75, 1):
        v = max_v * f
        parts.append(f'<line x1="{pad_l}" y1="{y(v):.1f}" x2="{W - pad_r}" y2="{y(v):.1f}" stroke="rgba(255,255,255,.08)"/>')
        parts.append(f'<text x="{pad_l - 6}" y="{y(v) + 3:.1f}" text-anchor="end" font-size="9" fill="var(--muted)">{seo.num(v, 0)}</text>')
    if mean_q:
        parts.append(f'<line x1="{pad_l}" y1="{y(mean_q):.1f}" x2="{W - pad_r}" y2="{y(mean_q):.1f}" '
                      f'stroke="#a78bfa" stroke-width="1.5" stroke-dasharray="5,4"/>')
        parts.append(f'<text x="{W - pad_r}" y="{y(mean_q) - 5:.1f}" text-anchor="end" font-size="9" fill="#a78bfa">'
                      f'tipičen pretok ({seo.num(mean_q, 1)})</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(rows))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#60a5fa" stroke-width="2.4" '
                 f'stroke-linecap="round" stroke-linejoin="round"/>')
    for i, (lbl, v) in enumerate(rows):
        parts.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="#60a5fa"/>')
        parts.append(f'<text x="{x(i):.1f}" y="{y(v) - 9:.1f}" text-anchor="middle" font-size="9" '
                     f'fill="var(--text)" font-weight="600">{seo.num(v, 1)}</text>')
        parts.append(f'<text x="{x(i):.1f}" y="{H - 8}" text-anchor="middle" font-size="9" '
                     f'fill="var(--muted)">{_svg_esc(lbl)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def stations_chart_svg(stations):
    """Vodoravni prikaz stanja vsake postaje na njeni LASTNI lestvici (do
    njenega tretjega praga) — ista logika kot station_level()/station_status()
    zgoraj, samo narisana namesto izpisana."""
    rows = [s for s in stations[:6] if s.get("pretok") is not None]
    if not rows:
        return ""
    W = 640
    row_h = 48
    pad_l, pad_r, pad_t = 108, 46, 10
    bar_h = 14
    plot_w = W - pad_l - pad_r
    H = pad_t + row_h * len(rows) + 6

    parts = [f'<svg viewBox="0 0 {W} {H}" class="vod-svg" preserveAspectRatio="xMidYMid meet">']
    for i, s in enumerate(rows):
        q = s["pretok"]
        vv1, vv2, vv3 = s.get("vv1"), s.get("vv2"), s.get("vv3")
        if vv3 is not None:
            scale_max = vv3 * 1.15
            ticks = [t for t in (vv1, vv2, vv3) if t is not None]
        else:
            scale_max = THRESHOLDS["alarm"] * 1.15
            ticks = [THRESHOLDS["raised"], THRESHOLDS["warning"], THRESHOLDS["alarm"]]
        lvl = station_level(q, s) or 0
        frac = max(0, min(1, q / scale_max)) if scale_max else 0
        y0 = pad_t + row_h * i
        cy = y0 + bar_h / 2
        color = LEVEL_COLORS[lvl]
        parts.append(f'<text x="0" y="{cy + 3:.1f}" font-size="10.5" font-weight="600" fill="var(--text)">{_svg_esc(s["name"])}</text>')
        parts.append(f'<rect x="{pad_l}" y="{y0}" width="{plot_w}" height="{bar_h}" rx="4" fill="rgba(255,255,255,.08)"/>')
        parts.append(f'<rect x="{pad_l}" y="{y0}" width="{plot_w * frac:.1f}" height="{bar_h}" rx="4" fill="{color}"/>')
        for t in ticks:
            tx = pad_l + plot_w * min(1, t / scale_max)
            parts.append(f'<line x1="{tx:.1f}" y1="{y0 - 2}" x2="{tx:.1f}" y2="{y0 + bar_h + 2}" stroke="rgba(255,255,255,.35)" stroke-width="1"/>')
        parts.append(f'<text x="{pad_l + plot_w + 8}" y="{cy + 3:.1f}" font-size="10" fill="{color}" font-weight="700">{seo.num(q, 1)}</text>')
        parts.append(f'<text x="0" y="{cy + 16:.1f}" font-size="8.5" fill="var(--muted)">{_svg_esc(LEVEL_LABELS[lvl])}</text>')
    parts.append("</svg>")
    legend = ('<div class="vod-legend">' + "".join(
        f'<span><i style="background:{c}"></i>{lbl}</span>' for c, lbl in zip(LEVEL_COLORS, LEVEL_LABELS)
    ) + '<span>┆ oznaka = prag ARSO</span></div>')
    return "".join(parts) + legend


CHART_CSS = """<style>
.vod-chart-block{margin:1.2rem 0 1.8rem}
.vod-chart-title{font-family:'JetBrains Mono',monospace;font-size:.7rem;letter-spacing:.06em;
  text-transform:uppercase;color:var(--cyan,#22d3ee);opacity:.85;margin-bottom:.3rem}
.vod-svg{width:100%;height:auto;display:block}
.vod-legend{display:flex;flex-wrap:wrap;gap:.9rem;margin-top:.5rem;font-size:.78rem;color:var(--muted)}
.vod-legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:.3rem;vertical-align:middle}
</style>"""

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
            # Uradni pragovi visokih voda za TO postajo — brez njih je ocena
            # stanja umerjena na eno samo postajo in za ostale napačna.
            "vv1": to_float("prvi_vv_pretok"),
            "vv2": to_float("drugi_vv_pretok"),
            "vv3": to_float("tretji_vv_pretok"),
            "znacilni": (p.findtext("pretok_znacilni") or "").strip() or None,
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


def station_level(q, station=None):
    """Resnost stanja postaje: None (ni podatka) ali 0–3.

    Meri se po pragovih visokih voda, ki jih ARSO objavi ZA TO POSTAJO
    (`prvi/drugi/tretji_vv_pretok`). THRESHOLDS je umerjen na Letuš in za druge
    postaje ne velja: pri Solčavi je naš prag za »Opozorilo« (200 m³/s) nad
    tretjim pragom ARSO (100), torej bi tam pravo visoko vodo prikazali kot
    normalno stanje. Naš približek zato ostane samo tam, kjer ARSO pragov ne
    objavi — in je v izpisu tako tudi označen.
    """
    if q is None:
        return None
    s = station or {}
    vv1, vv2, vv3 = s.get("vv1"), s.get("vv2"), s.get("vv3")
    if vv1 is not None:
        if vv3 is not None and q >= vv3:
            return 3
        if vv2 is not None and q >= vv2:
            return 2
        return 1 if q >= vv1 else 0
    if q >= THRESHOLDS["alarm"]:
        return 3
    if q >= THRESHOLDS["warning"]:
        return 2
    return 1 if q >= THRESHOLDS["raised"] else 0


def station_status(q, station=None):
    """Besedna oznaka stanja. Pod prvim pragom prevzame ARSO-jevo lastno
    oznako (`pretok_znacilni`, npr. »mali pretok«) namesto naše besede."""
    lvl = station_level(q, station)
    if lvl is None:
        return "—"
    s = station or {}
    if s.get("vv1") is not None:
        if lvl:
            return f"{lvl}. prag ARSO"
        zn = s.get("znacilni")
        return zn[0].upper() + zn[1:] if zn else "Pod pragom"
    return ["Normalen (ocena)", "Povečan (ocena)", "Opozorilo (ocena)", "Alarm (ocena)"][lvl]


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

    # Na vprašanje »kakšen je pretok danes« odgovori IZMERJENA vrednost, ne
    # modelska. GloFAS ima mrežo ~5 km in Savinje v ozki dolini ne razloči —
    # njegova celica pri Rečici kaže nekajkrat manj od meritve na postaji nekaj
    # kilometrov dolvodno. Model ostane na strani kot napoved poteka, jasno
    # označen; vira se ne zlivata v eno številko.
    nearest = stations[0] if stations else None
    meritev = nearest.get("pretok") if nearest else None

    model_txt = (f'Modelska napoved GloFAS za današnji dan je {seo.num(today_q, 1)} m³/s '
                 f'({status.lower()}, {round(ratio * 100)} % tipične vrednosti {seo.num(mean_q, 1)} m³/s); '
                 f'v ozki dolini pretok podceni, zato je merodajna meritev.')
    if meritev is not None:
        answer = (f'  <p class="archive-intro">Savinja pri Rečici ob Savinji ima danes izmerjen pretok '
                  f'<strong>{seo.num(meritev, 1)} m³/s</strong>'
                  + (f' in vodostaj {seo.num(nearest["vodostaj"], 0)} cm' if nearest.get("vodostaj") is not None else '')
                  + f' — najbližja merilna postaja ARSO je {nearest["name"]} '
                  f'({station_status(meritev, nearest).lower()}). {model_txt} '
                  f'Podatki se osvežujejo dnevno — nazadnje {TODAY.isoformat()}.</p>')
    else:
        answer = (f'  <p class="archive-intro">Meritev ARSO trenutno ni na voljo. {model_txt} '
                  f'Podatki se osvežujejo dnevno — nazadnje {TODAY.isoformat()}.</p>')

    warn_box = ""
    if ratio >= 2.5:
        warn_box = ('  <div class="partial-note">⚠️ Pretok znatno presega normalo — spremljaj uradna opozorila ARSO '
                     'in URSZR. Avgusta 2023 je Savinja pri Letušu dosegla 1100 m³/s.</div>')

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-rain">
      <div class="sc-label">Pretok danes — izmerjeno</div>
      <div class="sc-val">{seo.num(meritev, 1) if meritev is not None else "—"}</div>
      <div class="sc-sub">m³/s · {nearest["name"] if meritev is not None else "meritev ni na voljo"} · ARSO</div>
    </div>
    <div class="stat-card c-up">
      <div class="sc-label">Maks. v napovedi (7 dni)</div>
      <div class="sc-val">{seo.num(max7, 1)}</div>
      <div class="sc-sub">m³/s · model GloFAS</div>
    </div>
    <div class="stat-card c-down">
      <div class="sc-label">Tipičen pretok</div>
      <div class="sc-val">{seo.num(mean_q, 1)}</div>
      <div class="sc-sub">m³/s · {round(ratio * 100)} % tega danes</div>
    </div>
  </div>
{warn_box}'''

    # ── ARSO stations: graf + tabela ────────────────────────────────────────
    if stations:
        rows6 = stations[:6]
        st_rows = "\n".join(
            f'      <tr><th>{s["name"]}</th>'
            f'<td>{seo.num(s["vodostaj"], 0) if s["vodostaj"] is not None else "—"} cm</td>'
            f'<td>{seo.num(s["pretok"], 1) if s["pretok"] is not None else "—"} m³/s</td>'
            f'<td>{station_status(s["pretok"], s)}</td></tr>'
            for s in rows6
        )
        st_table = ('  <div class="table-scroll"><table class="stats">\n'
                    '    <tr><th>Postaja</th><th>Vodostaj</th><th>Pretok</th><th>Stanje</th></tr>\n'
                    f'{st_rows}\n  </table></div>')
        st_chart_svg = stations_chart_svg(rows6)
        st_chart = (
            '  <div class="vod-chart-block" id="vod-chart-stations">\n'
            '  <div class="vod-chart-title">Stanje postaje glede na njene lastne pragove</div>\n'
            f'  {st_chart_svg}\n  </div>'
        ) if st_chart_svg else ""
    else:
        st_table = '  <p class="muted-note">Postaje ARSO trenutno niso dosegljive.</p>'
        st_chart = ""

    # ── 7-day GloFAS outlook: graf + tabela ─────────────────────────────────
    times = d.get("time") or []
    out_rows = []
    for k, q in enumerate(discharge[:FORECAST_DAYS]):
        if k < len(times):
            dt = datetime.date.fromisoformat(times[k])
            lbl = "danes" if k == 0 else DAN_KRATKO[dt.weekday()] + f" {dt.day}. {dt.month}."
        else:
            lbl = f"+{k} d"
        out_rows.append((lbl, q))
    outlook_chart = (
        '  <div class="vod-chart-block" id="vod-chart-outlook">\n'
        '  <div class="vod-chart-title">Napoved pretoka GloFAS, naslednjih 7 dni</div>\n'
        f'  {outlook_chart_svg(out_rows, mean_q)}\n  </div>'
    )
    outlook_table = '  <div class="table-scroll"><table class="stats">\n' + "\n".join(
        f'      <tr><th>{lbl}</th><td>{seo.num(q, 1)} m³/s</td></tr>' for lbl, q in out_rows
    ) + "\n  </table></div>"

    # ── Flood history ───────────────────────────────────────────────────────
    max_hist_q = max(e["q"] for e in FLOOD_HISTORY)
    hist_rows = "\n".join(
        f'      <tr><th>{e["date"]}</th><td>{e["q"]} m³/s</td><td>{e["desc"]}</td></tr>'
        for e in reversed(FLOOD_HISTORY)
    )
    hist_table = ('  <div class="table-scroll"><table class="stats">\n'
                  '    <tr><th>Datum</th><th>Vršni pretok</th><th>Opis</th></tr>\n'
                  f'{hist_rows}\n  </table></div>')

    # ── FAQ ─────────────────────────────────────────────────────────────────
    qa = [
        ("Kakšen je trenutni pretok Savinje pri Rečici ob Savinji?",
         (f"Najbližja merilna postaja ARSO ({nearest['name']}) danes meri {seo.num(meritev, 1)} m³/s. "
          if meritev is not None else "Meritev ARSO trenutno ni na voljo. ")
         + f"Modelska napoved GloFAS (Open-Meteo) za isti dan je {seo.num(today_q, 1)} m³/s, kar je "
           f"{round(ratio * 100)} % tipične vrednosti za ta datum; model ima mrežo približno 5 km in "
           f"pretok v ozki dolini podceni, zato je merodajna meritev."),
        ("Kdaj je bila zadnja večja poplava Savinje?",
         "Najhujša doslej zabeležena poplava je bila avgusta 2023, ko je pretok pri Letušu dosegel približno "
         "1100 m³/s in povzročil škodo za več kot 500 milijonov evrov po vsej Zgornji Savinjski dolini."),
        ("Kaj pomenijo pragovi pri posameznih postajah?",
         "Stanje vsake postaje se primerja z njenimi lastnimi pragovi visokih voda, ki jih objavi ARSO — "
         "ti se med postajami močno razlikujejo, ker se razlikuje velikost prispevnega območja: prvi prag "
         "je pri Solčavi okoli 56 m³/s, pri Letušu pa okoli 360 m³/s. Kjer ARSO pragov ne objavi, je "
         "stanje označeno kot ocena po enotnem približku (povečan od 80, opozorilo od 200, alarm od "
         "400 m³/s), umerjenem na Letuš. Za ukrepanje vedno štejejo uradna opozorila ARSO in URSZR."),
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
{st_chart}
{st_table}
  <h2>Napoved pretoka — naslednjih {FORECAST_DAYS} dni</h2>
  <p class="archive-intro">GloFAS napoved pretoka Savinje pri Rečici ob Savinji.</p>
{outlook_chart}
{outlook_table}
  <h2>Zgodovina poplav Savinje</h2>
  <p class="archive-intro">Največje zabeležene poplave Savinje po ocenjenem vršnem pretoku pri postaji Letuš.
  Podroben pregled poplav avgusta 2023 — vzroki, hidrološki rekordi, škoda in obnova — je v
  <a href="/blog/poplave-2023.html">ločenem članku na blogu</a>.</p>
{hist_table}
  <h2>Kako brati pragove pretoka</h2>
  <p class="archive-intro">Stanje posamezne postaje v tabeli zgoraj se primerja z njenimi lastnimi pragovi
  visokih voda, kot jih objavi ARSO (prvi, drugi in tretji prag). Ti se med postajami močno razlikujejo, ker
  se razlikuje velikost prispevnega območja — enoten prag za vso dolino bi bil pri Solčavi previsok in pri
  Celju prenizek. Kjer ARSO pragov ne objavi, je stanje izrecno označeno kot ocena po enotnem približku,
  umerjenem na Letuš. Nobena od teh oznak ni uradno opozorilo: pri dejanski nevarnosti vedno štejejo
  objave ARSO in URSZR.</p>
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

    return body, today_q, status, ratio, meritev


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
        body, today_q, status, ratio, meritev = build_body(flood, stations)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        sys.exit(1)

    url = "/vodostaj-savinje/"
    title = "Vodostaj in pretok Savinje — Zgornja Savinjska dolina"
    # Opis vodi izmerjena vrednost; modelska gre v besedilo strani, ne v opis,
    # ker je opis odgovor na "kakšen je pretok danes".
    desc = ((f"Pretok Savinje danes: {seo.num(meritev, 1)} m³/s, izmerjeno na najbližji postaji ARSO. "
             if meritev is not None else "Pretok Savinje danes po napovedi GloFAS. ")
            + "GloFAS napoved za 7 dni, meritve ARSO ob Savinji in zgodovina poplav vključno z avgustom 2023.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-02"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vodostaj Savinje", None)]),
    ]) + "\n" + CHART_CSS

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("vodostaj-savinje/index.html", html, force=True)
    print(f"  → vodostaj-savinje/index.html (izmerjeno {seo.num(meritev, 1)} m³/s, model {seo.num(today_q, 1)} m³/s, {status})")


if __name__ == "__main__":
    main()
