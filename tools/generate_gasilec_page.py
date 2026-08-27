#!/usr/bin/env python3
"""
tools/generate_gasilec_page.py — MeteoGasilec: požarna ogroženost in vreme za
intervencije.

Renders /meteogasilec/ (landing) + tri podstrani. Samostojen generator (isto
načelo kot pri generate_gobe_page.py — generatorji strani si ne delijo
knjižnic): uvaža samo skupne predloge iz generate_seo_pages (`seo`) in svoj
model iz gasilec_model.py (`fm`).

Vsebina:
  * Hero — današnji FWI (kanadska/EFFIS metodologija, isti izračun kot na
    naslovnici, glej gasilec_model.py) + 7-dnevni graf.
  * NASA FIRMS — dejansko zaznane toplotne anomalije v bližini (isti Worker
    endpoint /pozari kot na naslovnici, klican na novo od tu).
  * Tri podstrani: vreme-intervencije/ (lokalni veter + nacionalni nevihtni
    potencial iz že objavljenega og/storm-map/latest.json), nasveti/ (kurjenje
    v naravi, kontakti), metodologija/ (razlaga FWI, viri, omejitve).

Usage:
  python3 tools/generate_gasilec_page.py
"""
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo   # noqa: E402 — shared template helpers
import gasilec_model as fm         # noqa: E402 — FWI model

ROOT = seo.ROOT
TODAY = seo.TODAY
WORKER_BASE = "https://weatherireica1.filip-eremita.workers.dev"
STORM_MAP_JSON = os.path.join(ROOT, "og", "storm-map", "latest.json")


def _esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


BRAND_SWAP = '''<script>(function(){
  var img=document.querySelector(".site-head .brand-logo");
  var nm=document.querySelector(".site-head .brand-name");
  if(img){img.src="/meteogasilec/logo-gasilec.svg";img.alt="MeteoGasilec";}
  if(nm){nm.innerHTML="Meteo<em>Gasilec</em>";}
})();</script>'''

PAGE_CSS = """<style>
[hidden]{display:none!important}
body{
  --blue:#f59e0b; --cyan:#ef4444;
  --gf-sp-3:.75rem; --gf-sp-4:1rem; --gf-sp-6:1.5rem;
}
.gf-hero{position:relative;border:1px solid var(--card-border);border-radius:1.1rem;
  padding:1.5rem;margin:.6rem 0 1.4rem;box-shadow:var(--card-shadow);
  background:var(--card-bg)}
.gf-hero-top{display:flex;align-items:center;gap:1.3rem;flex-wrap:wrap}
.gf-hero-num{font-family:'JetBrains Mono',monospace;font-size:3rem;font-weight:800;
  line-height:1;min-width:5rem}
.gf-hero-sub{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.gf-hero-body{flex:1;min-width:220px}
.gf-badge{display:inline-block;padding:.28rem .8rem;border-radius:999px;font-size:.8rem;
  font-weight:700;margin-bottom:.4rem}
.gf-hero-note{font-size:.78rem;color:var(--muted);margin-top:.6rem;line-height:1.5}
.gf-bars{display:flex;gap:4px;align-items:flex-end;height:80px;margin-top:1.1rem}
.gf-bar-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
.gf-bar{width:100%;max-width:22px;border-radius:3px 3px 0 0}
.gf-bar-lbl{font-size:.55rem;color:var(--muted)}
.gf-feat-group{margin:1.6rem 0}
.gf-feat-group h3{font-size:1rem;margin:0 0 .6rem}
.gf-feat{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:.8rem}
.gf-feat-card{display:block;border:1px solid var(--card-border);border-radius:.9rem;
  padding:1rem;background:var(--card-bg);text-decoration:none;color:var(--text);
  transition:transform .15s ease,border-color .15s ease}
.gf-feat-card:hover{transform:translateY(-2px);border-color:var(--fa,var(--cyan))}
.gf-feat-title{display:block;font-weight:700;margin:.3rem 0 .2rem}
.gf-feat-sub{display:block;font-size:.78rem;color:var(--muted);line-height:1.4}
.gf-firms{border:1px solid var(--card-border);border-radius:.9rem;padding:1rem;
  background:var(--card-bg);margin:1.4rem 0}
.gf-note{font-size:.78rem;color:var(--muted);line-height:1.6;margin-top:.5rem}
.gf-tbl{width:100%;border-collapse:collapse;font-size:.82rem;margin:.8rem 0}
.gf-tbl th,.gf-tbl td{padding:.4rem .5rem;border-bottom:1px solid var(--card-border);text-align:left}
.gf-back{display:inline-block;margin-top:1.4rem;font-size:.85rem}
</style>"""


def _bars_svg_html(days):
    if not days:
        return ""
    max_fwi = max((d["fwi"] for d in days), default=5) or 5
    dn = ["Ned", "Pon", "Tor", "Sre", "Čet", "Pet", "Sob"]
    today_iso = TODAY.isoformat()
    cols = []
    for d in days:
        h = max(4, round((d["fwi"] / max_fwi) * 64))
        is_today = d["date"] == today_iso
        wd = dn[(_dt.date.fromisoformat(d["date"]).weekday() + 1) % 7]
        outline = "outline:2px solid var(--text);outline-offset:1px;" if is_today else ""
        cols.append(
            f'<div class="gf-bar-col"><div class="gf-bar" style="height:{h}px;background:{d["color"]};'
            f'opacity:{1 if is_today else .6};{outline}" title="{d["date"]}: FWI {d["fwi"]} ({d["level"]})">'
            f'</div><span class="gf-bar-lbl">{wd}</span></div>'
        )
    return f'  <div class="gf-bars">{"".join(cols)}</div>'


def build_hero(payload):
    today = payload
    color = next((d["color"] for d in payload["days"] if d["date"] == payload["date"]), "#f59e0b")
    return f'''  <div class="gf-hero">
    <div class="gf-hero-top">
      <div>
        <div class="gf-hero-num" style="color:{color}">{today["fwi"]:.1f}</div>
        <div class="gf-hero-sub">FWI danes</div>
      </div>
      <div class="gf-hero-body">
        <span class="gf-badge" style="background:{color}22;border:1px solid {color};color:{color}">{_esc(today["level"])}</span>
        <p style="margin:.3rem 0 0;font-size:.88rem;color:var(--muted)">Kanadski/EFFIS indeks požarne ogroženosti za Rečico ob Savinji, izračunan iz napovedi Open-Meteo.
        Ni uradna ocena ARSO ali URSZR — glej <a href="/meteogasilec/metodologija/">metodologijo</a>.</p>
      </div>
    </div>
{_bars_svg_html(payload["days"])}
    <p class="gf-hero-note">🔥 Ista metodologija kot na naslovnici (kartica »Požarna nevarnost – indeks FWI«) — tu preračunana strežniško, da je vidna tudi iskalnikom in brez JS.</p>
  </div>'''


_FI_OGROZENOST = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M12 3.6c-3.4 0-6 2.8-6 6.6 0 3.2 2 4.6 2 7a4 4 0 0 0 8 0c0-2.4 2-3.8 2-7 0-3.8-2.6-6.6-6-6.6Z" '
    'fill="currentColor" fill-opacity=".2" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<path d="M12 9c-1.4 1.6-1.8 3-.8 4.4 1 1.4-.2 2.2-1 1.6" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round"/></svg>')
_FI_VETER = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M3 8.6h11.5a2.7 2.7 0 1 0-2.6-3.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M3 13h15a2.9 2.9 0 1 1-2.8 3.7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M3 17.4h8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" opacity=".7"/></svg>')
_FI_NASVETI = ('<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<rect x="4" y="2.8" width="16" height="18.4" rx="2.6" fill="currentColor" fill-opacity=".14" '
    'stroke="currentColor" stroke-width="1.6"/>'
    '<path d="m7.4 8 1.5 1.5 2.6-2.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
    '<path d="M13.6 8.2h3.2M7.4 13.4h9.2M7.4 17.4h9.2" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round" opacity=".7"/></svg>')

FEATURES = [
    ("/meteogasilec/metodologija/", _FI_OGROZENOST, "#ef4444", "Kako se izračuna FWI",
     "Sestavine kanadskega indeksa (FFMC/DMC/DC/ISI/BUI) in kaj indeks ni."),
    ("/nevihte/", _FI_OGROZENOST, "#f59e0b", "Aktivna opozorila ARSO",
     "Vključno s kategorijo »požarna ogroženost«, sproti vsakih 15 minut."),
    ("/meteogasilec/vreme-intervencije/", _FI_VETER, "#22d3ee", "Vreme za intervencije",
     "Veter, sunki in nacionalni nevihtni potencial za danes."),
    ("/meteogasilec/nasveti/", _FI_NASVETI, "#84cc16", "Kurjenje v naravi in kontakti",
     "Kdaj sme in kdaj ne sme, 112, URSZR, Gasilska zveza Slovenije."),
]


def feature_cards_html():
    cards = []
    for href, icon, accent, title, sub in FEATURES:
        cards.append(
            f'    <a class="gf-feat-card" href="{href}" style="--fa:{accent}">'
            f'<span style="color:{accent}">{icon}</span>'
            f'<span class="gf-feat-title">{_esc(title)}</span>'
            f'<span class="gf-feat-sub">{_esc(sub)}</span></a>'
        )
    return ('  <h2>🧭 Orodja za gasilce</h2>\n'
            '  <div class="gf-feat">\n' + "\n".join(cards) + '\n  </div>')


def firms_widget_html():
    return f'''  <div class="gf-firms">
    <h2 style="margin-top:0">🛰 Aktivna požarišča (NASA FIRMS)</h2>
    <div id="gf-firms-body">Nalaganje…</div>
    <p class="gf-note">Sateliti (MODIS/VIIRS) zaznavajo toplotne anomalije, med katere sodi tudi kmetijsko sežiganje —
    zaznava sama po sebi ni potrjen gozdni požar.</p>
  </div>
  <script>(function(){{
    var el=document.getElementById('gf-firms-body');
    fetch('{WORKER_BASE}/pozari').then(function(r){{return r.json();}}).then(function(d){{
      if(!d||d.configured===false){{el.innerHTML='<p class="gf-note">Vir trenutno ni na voljo.</p>';return;}}
      if(!d.total){{el.innerHTML='<p style="margin:0">✅ V zadnjih '+d.days+' dneh nad Slovenijo ni zaznanih toplotnih anomalij.</p>';return;}}
      var rows=(d.fires||[]).slice(0,8).map(function(it){{
        var t=(it.time||'').padStart(4,'0');
        return '<tr><td>'+(it.dist!=null?it.dist+' km':'—')+'</td><td>'+(t?t.slice(0,2)+':'+t.slice(2)+' UTC':'—')+'</td>'
          +'<td>'+(it.conf||'—')+'</td><td>'+(it.frp!=null?it.frp.toFixed(0):'—')+'</td></tr>';
      }}).join('');
      el.innerHTML='<p style="margin:0 0 .5rem"><b>'+d.total+'</b> zaznav v zadnjih '+d.days+' dneh, '+d.within50+' znotraj 50 km.</p>'
        +'<table class="gf-tbl"><thead><tr><th>Razdalja</th><th>Čas</th><th>Zaupanje</th><th>FRP (MW)</th></tr></thead>'
        +'<tbody>'+rows+'</tbody></table>';
    }}).catch(function(){{el.innerHTML='<p class="gf-note">Vir trenutno ni na voljo.</p>';}});
  }})();</script>'''


def subpage_shell(slug, title, desc, inner_html):
    url = f"/meteogasilec/{slug}/"
    crumbs = [("Meteorec", "/"), ("MeteoGasilec", "/meteogasilec/"), (title, None)]
    schema = "\n".join([seo.webpage_schema(url, title, desc), seo.crumbs_schema(crumbs)])
    head_extras = schema + "\n" + PAGE_CSS
    body = f'''{BRAND_SWAP}
{seo.crumbs_html(crumbs)}
{seo.stn_badge()}
  <h1 class="page-title">{title}</h1>
{inner_html}
  <a class="gf-back" href="/meteogasilec/">← Nazaj na MeteoGasilec</a>'''
    html = seo.page_shell(f"{title} — MeteoGasilec", desc, url, head_extras, body)
    seo.write_page(f"meteogasilec/{slug}/index.html", html, force=True)
    return url


# ── veter za intervencije ────────────────────────────────────────────────────

def fetch_wind_hourly():
    params = urllib.parse.urlencode({
        "latitude": fm.LAT, "longitude": fm.LON,
        "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
        "forecast_days": 2, "timezone": "Europe/Ljubljana",
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


_DIRS = ["S", "SSV", "SV", "VSV", "V", "VJV", "JV", "JJV", "J", "JJZ", "JZ", "ZJZ", "Z", "ZSZ", "SZ", "SSZ"]


def _dir_label(deg):
    return _DIRS[round(deg / 22.5) % 16]


def load_storm_map():
    try:
        with open(STORM_MAP_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def build_vreme_intervencije_page():
    rows_html = "<tr><td colspan='4'>Vetrovna napoved trenutno ni na voljo.</td></tr>"
    try:
        data = fetch_wind_hourly()
        h = data.get("hourly") or {}
        times = h.get("time") or []
        spd = h.get("wind_speed_10m") or []
        gust = h.get("wind_gusts_10m") or []
        wdir = h.get("wind_direction_10m") or []
        now_iso = _dt.datetime.now().strftime("%Y-%m-%dT%H:00")
        start = next((i for i, t in enumerate(times) if t >= now_iso), 0)
        rows = []
        for i in range(start, min(start + 24, len(times)), 3):
            t = times[i]
            hh = t[11:16]
            day = "danes" if t[:10] == TODAY.isoformat() else "jutri"
            rows.append(
                f"<tr><td>{day} {hh}</td><td>{spd[i]:.0f} km/h</td>"
                f"<td>{gust[i]:.0f} km/h</td><td>{_dir_label(wdir[i])}</td></tr>"
            )
        rows_html = "\n".join(rows)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  ⚠ veter: {e}", file=sys.stderr)

    storm = load_storm_map()
    storm_html = ""
    if storm:
        storm_html = f'''  <h2>🌩 Nacionalni nevihtni potencial danes</h2>
  <p>Najvišja pričakovana ocena danes v Sloveniji: <b>{storm.get("national_score")} ({storm.get("national_level")})</b>,
  okoli {storm.get("national_hour")} pri kraju {_esc(storm.get("national_place"))}.
  Ocena je izpeljana iz CAPE, striga vetra in indeksov nestabilnosti — <a href="/nevihte/">celotna karta in razlaga →</a></p>'''

    inner = f'''  <p class="post-meta">Veter, sunki in nevihtni potencial za naslednjih 24 ur — dopolnilo k požarnemu
  indeksu za presojo širjenja ognja in varnosti med intervencijo.</p>
  <h2>🌬 Veter — Rečica ob Savinji</h2>
  <table class="gf-tbl">
    <thead><tr><th>Čas</th><th>Hitrost</th><th>Sunki</th><th>Smer</th></tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
{storm_html}
  <h2>⚡ Strele in radar v živo</h2>
  <p>Trenutne strele (Blitzortung) in radarska slika sta na voljo na <a href="/">naslovnici</a> (zavihek »Lovec na nevihte«).</p>'''
    return subpage_shell("vreme-intervencije", "Vreme za intervencije",
                          "Veter, sunki vetra in nacionalni nevihtni potencial za Rečico ob Savinji — "
                          "podatki v pomoč gasilskim intervencijam.", inner)


NASVETI_HTML = '''  <p class="post-meta">Kratek povzetek pravil in kontaktov — ne nadomešča uradnih navodil URSZR ali
  lokalnega gasilskega poveljstva.</p>
  <h2>🔥 Kurjenje v naravi</h2>
  <p>Kurjenje v naravnem okolju je ob visoki in zelo visoki požarni ogroženosti (glej FWI zgoraj) močno odsvetovano,
  ob razglašeni povečani požarni ogroženosti pa je ponekod prepovedano z odlokom občine ali uprave za zaščito in
  reševanje. Pred kurjenjem vedno preveri trenutno stanje in morebitne lokalne omejitve.</p>
  <ul>
    <li>Ne odmetavaj cigaretnih ogorkov v naravi.</li>
    <li>Kres oz. ogenj v naravi vedno nadzoruj in ga po končanem kurjenju temeljito pogasi.</li>
    <li>Ob sunkih vetra (glej <a href="/meteogasilec/vreme-intervencije/">vreme za intervencije</a>) se ogenj širi bistveno hitreje.</li>
  </ul>
  <h2>📞 Kontakti</h2>
  <ul>
    <li><b>112</b> — enotna evropska številka za klic v sili (požar, nesreča).</li>
    <li><a href="https://www.gzs-slo.si/" target="_blank" rel="noopener nofollow">Gasilska zveza Slovenije</a></li>
    <li><a href="https://www.gov.si/drzavni-organi/organi-v-sestavi/uprava-za-zascito-in-resevanje/" target="_blank"
       rel="noopener nofollow">URSZR — Uprava RS za zaščito in reševanje</a></li>
    <li><a href="https://meteo.arso.gov.si/met/sl/agromet/pozar/" target="_blank" rel="noopener nofollow">ARSO — uradni indeks požarne ogroženosti</a></li>
  </ul>'''


def build_nasveti_page():
    return subpage_shell("nasveti", "Nasveti in kontakti",
                          "Kurjenje v naravi, kdaj je odsvetovano ali prepovedano, in kontakti ob požaru v naravi.",
                          NASVETI_HTML)


METODOLOGIJA_HTML = '''  <p class="post-meta">MeteoGasilec ni uradna napoved ARSO ali URSZR. Je dodatna, samostojno izračunana
  ocena, namenjena orientaciji — pri odločanju vedno velja uradna ocena in odlok pristojnega organa.</p>
  <h2>🧮 Kanadski Fire Weather Index (FWI)</h2>
  <p>FWI je mednarodno uveljavljena metodologija (Van Wagner, kanadski gozdarski sistem), ki jo za Evropo uporablja
  tudi EFFIS/GWIS (evropski/globalni sistem za spremljanje požarov). Sestavljajo ga trije vlažnostni indeksi in trije
  izpeljani indeksi, ki se dan za dnem gradijo drug na drugem:</p>
  <ul>
    <li><b>FFMC</b> — vlažnost tanke stelje na površini (odziv na uro/dan).</li>
    <li><b>DMC</b> — vlažnost srednje globoke organske plasti (odziv na teden).</li>
    <li><b>DC</b> — sušnost globlje plasti (odziv na mesece — »spomin« na sušno obdobje).</li>
    <li><b>ISI</b> — pričakovana hitrost širjenja ognja glede na veter in FFMC.</li>
    <li><b>BUI</b> — razpoložljivo gorivo za zgorevanje (iz DMC in DC).</li>
    <li><b>FWI</b> — skupna ocena intenzivnosti požara, iz ISI in BUI.</li>
  </ul>
  <p>Izračun poganja dnevna napoved Open-Meteo (temperatura, najnižja relativna vlažnost, veter, padavine) za
  Rečico ob Savinji, 7 dni nazaj (za pravilen zagon vlažnostnih kod) in 7 dni naprej. Ista formula teče strežniško
  (ta stran, tools/gasilec_model.py) in v brskalniku (naslovnica, app.js) — vrednosti za isti dan se ujemata.</p>
  <h2>Kaj indeks ni</h2>
  <ul>
    <li>Ni napoved dejanskega požara — pove le, kako ugodni so pogoji, če bi do vžiga prišlo.</li>
    <li>Ni nadomestilo za uradni <a href="https://meteo.arso.gov.si/met/sl/agromet/pozar/" target="_blank" rel="noopener nofollow">ARSO indeks požarne ogroženosti</a>
    ali odloke lokalnih oblasti.</li>
    <li>Velja za eno točko (Rečica ob Savinji) — v drugih delih Slovenije se razmere lahko razlikujejo.</li>
  </ul>'''


def build_metodologija_page():
    return subpage_shell("metodologija", "Metodologija",
                          "Kako MeteoGasilec izračuna indeks FWI, kateri podatki ga poganjajo in kaj indeks ni.",
                          METODOLOGIJA_HTML)


def main():
    print(f"[{TODAY}] Gradim MeteoGasilec …")
    try:
        data = fm.fetch_daily()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Open-Meteo: {e}", file=sys.stderr)
        sys.exit(1)
    days = fm.fwi_series(data.get("daily") or {})
    if not days:
        print("✗ Open-Meteo ni vrnil dnevnih podatkov", file=sys.stderr)
        sys.exit(1)
    payload = fm.free_payload(days)

    os.makedirs(os.path.join(ROOT, "meteogasilec"), exist_ok=True)
    with open(os.path.join(ROOT, "meteogasilec", "index.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    build_vreme_intervencije_page()
    build_nasveti_page()
    build_metodologija_page()

    body = f'''{BRAND_SWAP}
{seo.stn_badge()}
  <h1 class="page-title">MeteoGasilec — požarna ogroženost, Rečica ob Savinji</h1>
  <p class="post-meta">Indeks FWI in vreme za intervencije · osvežuje se dnevno · {TODAY.isoformat()}</p>
{build_hero(payload)}
{feature_cards_html()}
{firms_widget_html()}
  <h2 id="faq">Pogosta vprašanja</h2>
  <p><b>Je MeteoGasilec uradna napoved?</b><br>Ne. Je samostojen izračun iz javnih podatkov Open-Meteo, po kanadski
  FWI metodologiji, ki jo za Evropo uporablja EFFIS/GWIS. Uradno oceno objavlja ARSO.</p>
  <p><b>Zakaj se FWI tu in na naslovnici lahko za trenutek razlikujeta?</b><br>Oba računata isto formulo iz iste
  Open-Meteo napovedi, a naslovnica jo osveži v brskalniku ob vsakem obisku, ta stran pa enkrat dnevno — v urah po
  novi napovedi je lahko majhna razlika.</p>
  <p><b>Kaj pomenijo pike na karti NASA FIRMS?</b><br>Satelitsko zaznane toplotne anomalije zadnjih dni, ne nujno
  potrjeni gozdni požari — glej opombo ob karti zgoraj.</p>'''

    url = "/meteogasilec/"
    title = "MeteoGasilec — požarna ogroženost, Rečica ob Savinji"
    desc = (f"Indeks požarne ogroženosti FWI danes: {payload['fwi']} ({payload['level']}). Veter za intervencije, "
            f"aktivna opozorila ARSO in zaznana požarišča NASA FIRMS za Rečico ob Savinji.")
    qa = [
        ("Je MeteoGasilec uradna napoved požarne ogroženosti?",
         "Ne. Samostojen izračun po kanadski FWI metodologiji (EFFIS/GWIS) iz javnih podatkov Open-Meteo, ni "
         "nadomestilo za uradno oceno ARSO ali odloke lokalnih oblasti."),
        ("Kaj je indeks FWI?",
         "Kanadski Fire Weather Index — mednarodno uveljavljena ocena požarne ogroženosti iz vlažnosti tal, "
         "temperature, vlage zraka, vetra in padavin zadnjih dni."),
    ]
    schema = "\n".join([
        seo.webpage_schema(url, title, desc),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoGasilec", None)]),
        seo.faq_schema(qa),
    ])
    head_extras = schema + "\n" + PAGE_CSS
    html = seo.page_shell(title, desc, url, head_extras, body)
    seo.write_page("meteogasilec/index.html", html, force=True)
    print(f"  → meteogasilec/index.html (FWI {payload['fwi']}, {payload['level']}) + 3 podstrani")


if __name__ == "__main__":
    main()
