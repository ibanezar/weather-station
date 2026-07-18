#!/usr/bin/env python3
"""
tools/generate_invazivke_page.py — /invazivke/ pillar page

Generates /invazivke/index.html: pregled invazivnih vrst v Zgornji Savinjski
dolini po podatkih iNaturalist (glej tools/invasive_watch.py). Vsebuje tabelo
vrst, Leaflet zemljevid na ravni mrežnih celic (~1 km, ne natančnih pinov),
pregled po občinah in FAQ.

Bere:
  data/invazivke.json        — statistika po vrstah, nedavna opazovanja
  data/invasive_state.json   — polni seznam videnih celic (za zemljevid)
  data/invasive_species.json — opis vrst (desc_sl)

Usage:
  python3 tools/generate_invazivke_page.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
from invasive_watch import MUNICIPALITIES, SEVERITY_LABEL  # noqa: E402

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_BADGE_CLASS = {"critical": "badge-critical", "high": "badge-high",
                          "medium": "badge-medium", "low": "badge-low"}

EXTRA_STYLE = '''<style>
.badge-critical,.badge-high,.badge-medium,.badge-low{
  display:inline-flex;align-items:center;gap:.3rem;padding:.15rem .55rem;border-radius:999px;
  font-size:.72rem;font-weight:600;letter-spacing:.02em;border:1px solid transparent}
.badge-critical{color:#fca5a5;background:rgba(220,38,38,.12);border-color:rgba(220,38,38,.4)}
.badge-high{color:#fdba74;background:rgba(249,115,22,.12);border-color:rgba(249,115,22,.35)}
.badge-medium{color:#fde047;background:rgba(234,179,8,.12);border-color:rgba(234,179,8,.35)}
.badge-low{color:#86efac;background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.35)}
.iv-map-shell{position:relative;margin:.6rem 0 1rem}
.iv-map{height:min(60vh,460px);border-radius:14px;overflow:hidden;border:1px solid var(--card-border);background:var(--card-bg)}
.iv-map-hint{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:.5rem;background:var(--card-bg);border-radius:14px;cursor:pointer;
  color:var(--muted);font-size:.85rem;text-align:center;padding:1rem}
.iv-map-load{padding:.4rem .9rem;border-radius:999px;border:1px solid var(--card-border);color:var(--text)}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:#130f0b;color:var(--text)}
.leaflet-popup-content{margin:.6rem .8rem}
table.iv-species th,table.iv-species td{vertical-align:middle}
</style>'''


def load_json(name, default=None):
    path = os.path.join(ROOT, "data", name)
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def cell_to_latlng(cell, grid):
    lat, lng = (float(x) for x in cell.split("_"))
    return lat + grid / 2, lng + grid / 2


def municipality_for(lat, lng):
    best, best_d = None, None
    for name, mlat, mlng in MUNICIPALITIES:
        d = (lat - mlat) ** 2 + (lng - mlng) ** 2
        if best_d is None or d < best_d:
            best, best_d = name, d
    return best


def build_map_points(state, config, species_by_slug):
    grid = config.get("grid_size_deg", 0.01)
    pts = []
    for slug, cells in state.get("cells", {}).items():
        sp = species_by_slug.get(slug)
        if not sp:
            continue
        for cell in cells:
            lat, lng = cell_to_latlng(cell, grid)
            pts.append({"lat": round(lat, 3), "lng": round(lng, 3), "sl": sp["sl"],
                        "severity": sp["severity"]})
    return pts


def build_map_section(pts, region):
    if not pts:
        return "", ""
    swlat, swlng = region["bbox"]["swlat"], region["bbox"]["swlng"]
    nelat, nelng = region["bbox"]["nelat"], region["bbox"]["nelng"]
    center_lat, center_lng = (swlat + nelat) / 2, (swlng + nelng) / 2
    pts_json = json.dumps(pts, ensure_ascii=False)

    card = f'''  <div class="iv-map-shell">
    <div class="iv-map" id="iv-map"></div>
    <div class="iv-map-hint" id="iv-map-hint">
      <span>🗺️ Klikni za nalaganje zemljevida (Leaflet · OpenStreetMap / CARTO)</span>
      <span class="iv-map-load">Naloži zemljevid</span>
    </div>
  </div>
  <p class="muted-note">Krogci prikazujejo mrežne celice (~1 km) z vsaj enim opazovanjem — ne natančne
  lokacije posameznih rastlin/živali. Leaflet se naloži šele ob kliku (s storitve unpkg.com).</p>'''

    js = f'''<script>
(function(){{
  var PTS = {pts_json};
  var CENTER = [{center_lat}, {center_lng}];
  var COLOR = {{critical:"#dc2626", high:"#f97316", medium:"#eab308", low:"#22c55e"}};
  var hint = document.getElementById("iv-map-hint");
  var loaded = false;
  function loadCss(href){{ var l=document.createElement("link"); l.rel="stylesheet"; l.href=href; document.head.appendChild(l); }}
  function loadScript(src){{ return new Promise(function(res,rej){{ var s=document.createElement("script"); s.src=src; s.onload=res; s.onerror=rej; document.body.appendChild(s); }}); }}
  async function initMap(){{
    if (loaded) return;
    loaded = true;
    if (!window.L) {{
      loadCss("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
      await loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");
    }}
    hint.style.display = "none";
    var map = L.map("iv-map", {{zoomControl:true, attributionControl:false, scrollWheelZoom:false}}).setView(CENTER, 10);
    L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{maxZoom:15, subdomains:"abcd"}}).addTo(map);
    PTS.forEach(function(p){{
      L.circleMarker([p.lat, p.lng], {{radius:8, color:"#0b0906", weight:1.5,
        fillColor: COLOR[p.severity] || "#60a5fa", fillOpacity:.85}})
        .addTo(map)
        .bindPopup(p.sl);
    }});
  }}
  hint.addEventListener("click", initMap);
}})();
</script>'''
    return card, js


def species_table_rows(species):
    rows = []
    ordered = sorted(species, key=lambda s: SEVERITY_ORDER.get(s["severity"], 9))
    for s in ordered:
        badge = f'<span class="{SEVERITY_BADGE_CLASS[s["severity"]]}">{SEVERITY_LABEL[s["severity"]].capitalize()}</span>'
        last = seo.fmtd(s["last_observed"]) if s.get("last_observed") else "—"
        trend = "↑ nova lokacija (30 dni)" if s.get("new_cells_30d", 0) > 0 else "→ brez sprememb"
        rows.append(
            f'      <tr><th>{s["sl"]}<br><span style="color:var(--muted);font-size:.78rem;font-style:italic">{s["sci"]}</span></th>'
            f'<td>{badge}</td><td>{last}</td><td>{s.get("total_cells", 0)}</td><td>{trend}</td></tr>'
        )
    return "\n".join(rows)


def municipality_section(pts):
    counts = {}
    for p in pts:
        name = municipality_for(p["lat"], p["lng"])
        counts.setdefault(name, {"cells": 0, "species": set()})
        counts[name]["cells"] += 1
        counts[name]["species"].add(p["sl"])
    rows = []
    for name, _, _ in MUNICIPALITIES:
        c = counts.get(name, {"cells": 0, "species": set()})
        rows.append(f'      <tr><th>{name}</th><td>{len(c["species"])} vrst · {c["cells"]} lokacij</td></tr>')
    return "  <table class=\"stats\">\n" + "\n".join(rows) + "\n  </table>"


def build_body(data, state, config, species_cfg):
    species = data.get("species", [])
    species_by_slug = {s["slug"]: s for s in species}
    total_cells = sum(s.get("total_cells", 0) for s in species)
    active_species = sum(1 for s in species if s.get("total_cells", 0) > 0)
    new_30d = sum(s.get("new_cells_30d", 0) for s in species)

    pts = build_map_points(state, config, species_by_slug)
    map_card, map_js = build_map_section(pts, config["region"])

    quick = f'''  <div class="stat-grid">
    <div class="stat-card c-green">
      <div class="sc-label">Spremljanih vrst</div>
      <div class="sc-val">{len(species)}</div>
      <div class="sc-sub">z vsaj eno potrjeno najdbo: {active_species}</div>
    </div>
    <div class="stat-card c-rain">
      <div class="sc-label">Znane lokacije (celice)</div>
      <div class="sc-val">{total_cells}</div>
      <div class="sc-sub">mrežne celice ~1 km²</div>
    </div>
    <div class="stat-card c-dry">
      <div class="sc-label">Nove lokacije (30 dni)</div>
      <div class="sc-val">{new_30d}</div>
      <div class="sc-sub">prva potrjena najdba v celici</div>
    </div>
  </div>'''

    species_table = (
        '  <table class="stats iv-species">\n'
        '    <tr><th>Vrsta</th><th>Resnost</th><th>Zadnje opazovanje</th><th>Lokacij</th><th>Trend</th></tr>\n'
        f'{species_table_rows(species)}\n  </table>'
    )

    qa = [
        ("Kaj so invazivne vrste in zakaj jih spremljamo v Zgornji Savinjski dolini?",
         "Invazivne vrste so rastline in živali, ki so jih v Slovenijo prinesli ljudje (namerno ali "
         "nenamerno) in se zaradi odsotnosti naravnih sovražnikov hitro širijo na račun domorodnih vrst. "
         "V Zgornji Savinjski dolini je zaradi bližine Savinje in njenih pritokov širjenje obrežnih "
         "invazivk (japonski dresnik, žlezava nedotika) posebej hitro, zato spremljanje novih lokacij "
         "pomaga občinam in lastnikom zemljišč pri zgodnjem ukrepanju."),
        ("Je orjaški dežen nevaren?",
         "Da. Sok orjaškega dežna (Heracleum mantegazzianum) v stiku s kožo in kasneje sončno svetlobo "
         "povzroči hude fotokemične opekline in dolgotrajne brazgotine. Rastline se nikoli ne dotikaj — "
         "najdbo prijavi in o njej obvesti pristojno občino."),
        ("Kako prijavim najdbo japonskega dresnika ali druge invazivke?",
         "Fotografiraj rastlino ali žival, odpri aplikacijo ali stran iNaturalist, dodaj lokacijo najdbe "
         "in objavi opazovanje. Skupnost in samodejni algoritmi pomagajo pri potrditvi vrste, potrjena "
         "opazovanja pa se prek te strani samodejno pojavijo tudi tukaj."),
        ("Od kod prihajajo podatki na tej strani?",
         "Podatki prihajajo iz javne baze iNaturalist (opazovanja skupnosti, raziskovalne in "
         "\"potrebna določitev\" kakovosti). Stran se osvežuje vsako noč — natančne koordinate "
         "opazovanj namerno niso objavljene, prikazana je le mrežna celica velikosti približno 1 km."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    map_section = ""
    if map_card:
        map_section = f'  <h2>Zemljevid najdb (po mrežnih celicah)</h2>\n{map_card}'

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Invazivke", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Invazivne vrste Zgornja Savinjska dolina — spremljanje najdb</h1>
  <p class="post-meta">Podatki iNaturalist · osvežuje se vsako noč · {TODAY.isoformat()}</p>
  <p class="archive-intro">Zgornja Savinjska dolina — od Solčave do Nazarij — se zaradi Savinje in njenih
  pritokov spopada z več invazivnimi vrstami, od japonskega dresnika in žlezave nedotike ob rekah do
  zdravju nevarnega orjaškega dežna. Ta stran vsako noč povleče sveža opazovanja s platforme iNaturalist,
  zazna, kdaj se posamezna vrsta prvič pojavi na novi lokaciji, in vodi pregleden arhiv za vseh deset
  ciljnih vrst.</p>
  <p class="archive-intro">Spremljanje ni znanstvena raziskava, temveč orodje za zgodnje opozarjanje —
  namenjeno občinam, lastnikom zemljišč in vsem, ki jih zanima <strong>japonski dresnik Savinjska</strong>
  ali druge invazivke v okolici Mozirja, Ljubnega, Luč, Gornjega Grada in Rečice ob Savinji.</p>
{quick}
  <h2>Pregled vrst</h2>
{species_table}
{map_section}
  <h2>Kako prijaviš opazovanje</h2>
  <p class="archive-intro">Vsak lahko pomaga: fotografiraj rastlino ali žival, odpri
  <a href="https://www.inaturalist.org" target="_blank" rel="noopener" style="color:var(--blue)">iNaturalist</a>
  (splet ali mobilna aplikacija), dodaj lokacijo in objavi opazovanje z oznako kakovosti "raziskovalno" ali
  "potrebna določitev". Ta stran take najdbe samodejno zazna naslednjo noč.</p>
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🔎 Prijava opazovanja</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.inaturalist.org" target="_blank" rel="noopener" class="mtn-avk-link">🌿 iNaturalist — nova prijava</a>
      <a href="https://www.inaturalist.org/observations?place_id=any&nelat={config["region"]["bbox"]["nelat"]}&nelng={config["region"]["bbox"]["nelng"]}&swlat={config["region"]["bbox"]["swlat"]}&swlng={config["region"]["bbox"]["swlng"]}" target="_blank" rel="noopener" class="mtn-avk-link">📍 Vsa opazovanja v dolini</a>
    </div>
  </div>
  <h2>Po občinah</h2>
  <p class="archive-intro">Približna razporeditev znanih lokacij (mrežnih celic) po najbližji občini —
  ocena po geografski bližini, ne uradna evidenca.</p>
{municipality_section(pts)}
  <p class="muted-note">Podatki se dnevno posodabljajo s postopkom, opisanim na
  <a href="/blog/" style="color:var(--blue)">blogu Meteorec</a>; ob novi lokaciji izide kratek samodejni
  zapis, prvi dan v mesecu pa mesečni pregled.</p>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
{map_js}'''

    return body, pts, species


def main():
    print(f"[{TODAY}] Generiram /invazivke/ ...")
    data = load_json("invazivke.json")
    if data is None:
        sys.exit("✗ data/invazivke.json ne obstaja — najprej poženi tools/invasive_watch.py")
    state = load_json("invasive_state.json", {"cells": {}})
    config = load_json("invasive_species.json")
    species_cfg = {s["slug"]: s for s in config["species"]}

    body, pts, species = build_body(data, state, config, species_cfg)

    url = "/invazivke/"
    title = "Invazivne vrste Zgornja Savinjska dolina — spremljanje najdb"
    desc = (f"Spremljanje {len(species)} invazivnih vrst v Zgornji Savinjski dolini prek iNaturalist: "
            f"japonski dresnik, žlezava nedotika, orjaški dežen in druge. Nove lokacije, zemljevid, "
            f"pregled po občinah.")

    qa_schema = [
        ("Kaj so invazivne vrste in zakaj jih spremljamo v Zgornji Savinjski dolini?",
         "Invazivne vrste so rastline in živali, ki jih je v Slovenijo prinesel človek in se zaradi "
         "odsotnosti naravnih sovražnikov hitro širijo na račun domorodnih vrst; v dolini ob Savinji je "
         "širjenje obrežnih vrst posebej hitro."),
        ("Je orjaški dežen nevaren?",
         "Da, sok orjaškega dežna v stiku s kožo in sončno svetlobo povzroči hude opekline — rastline se "
         "ne dotikaj, najdbo prijavi in obvesti občino."),
        ("Kako prijavim najdbo invazivke?",
         "Fotografiraj jo in objavi opazovanje na iNaturalist z lokacijo — potrjena opazovanja se "
         "samodejno pojavijo na tej strani."),
        ("Od kod prihajajo podatki na tej strani?",
         "Iz javne baze iNaturalist (opazovanja skupnosti); stran se osvežuje vsako noč, natančne "
         "koordinate niso objavljene."),
    ]

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-07-18"),
        seo.crumbs_schema([("Meteorec", "/"), ("Invazivke", None)]),
        seo.faq_schema(qa_schema),
        seo.named_dataset_schema(
            url, "Invazivne vrste — Zgornja Savinjska dolina",
            "Nočno posodobljen nabor opazovanj invazivnih vrst (iNaturalist) po mrežnih celicah "
            "za Zgornjo Savinjsko dolino.",
            variable_measured=[{"@type": "PropertyValue", "name": s["sl"]} for s in species],
            temporal_coverage=f"{TODAY.isoformat()}/..",
        ),
        EXTRA_STYLE,
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("invazivke/index.html", html, force=True)
    print(f"  → invazivke/index.html ({len(species)} vrst, {len(pts)} lokacij na zemljevidu)")


if __name__ == "__main__":
    main()
