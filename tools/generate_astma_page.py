#!/usr/bin/env python3
"""
tools/generate_astma_page.py — Vreme in astma: tveganje po dnevih

Generates /astma/index.html: 5-dnevna ocena, kako vreme in zrak v Zgornji
Savinjski dolini lahko obremenita ljudi z astmo. Po zgledu aplikacij tipa
DailyBreath / AsthmaMD, a brez računa, brez dnevnika simptomov na strežniku
in brez zdravstvenih trditev.

Dejavniki (vsak 0-3 točke na dan): cvetni prah, PM2,5, ozon, NO2, mrzel zrak,
vročina, nevihta (+ trava = »nevihtna astma«), hitra sprememba vremena,
vlaga. Skupna ocena je vsota točk; obiskovalec lahko v brskalniku označi
svoje sprožilce (localStorage, nikamor se ne pošlje), ki štejejo dvojno.

To NI diagnoza in NI zdravniški nasvet; ocena ni verjetnost napada. Pragovi so
naša delitev po splošno znanih sprožilcih (EU/WHO meje za onesnaževala).
Zračni podatki: Copernicus CAMS prek Open-Meteo (isti vir in ista funkcija
kot /kakovost-zraka/ -- ne forkaj klica). NOTRANJIH MERITEV POSTAJE TU NI in
ne smejo priti (CLAUDE.md, pravilo na vrhu).

JS pravila seštevanja (ASTMA_JS_CORE) je namerna podvojitev level_for()/
score_for() -- tools/test_astma.py ju primerja z Node.

Usage:
  python3 tools/generate_astma_page.py
"""
import datetime, html, json, os, sys, urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
from generate_kakovost_zraka_page import fetch_air_quality, POLLEN_TYPES  # noqa: E402 — ne forkaj klica

TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON
DNEVI = 5
DAN_KRATKO = ["pon", "tor", "sre", "čet", "pet", "sob", "ned"]

LEVELS = ["nizko", "zmerno", "povišano", "visoko"]
LEVEL_COLORS = {"nizko": "#059669", "zmerno": "#eab308", "povišano": "#f97316", "visoko": "#ef4444"}
# Meje skupne ocene (privzete uteži): 0-1 nizko, 2-3 zmerno, 4-5 povišano, >=6 visoko.
SCORE_TH = (2, 4, 6)
# En sam dejavnik z 3 točkami da vsaj »povišano«, tudi če je vsota nizka.
FLOOR_PTS = 3
TRIGGER_WEIGHT = 2

# (ključ, oznaka, kratek opis sprožilca za izbiro)
FACTORS = [
    ("pelod", "Cvetni prah", "cvetni prah (breza, trave, ambrozija …)"),
    ("pm", "Drobni delci PM2,5", "onesnažen zrak, prah"),
    ("ozon", "Ozon", "ozon poleti"),
    ("no2", "Dušikov dioksid", "promet in kurjenje"),
    ("mraz", "Mrzel zrak", "mrzel in suh zrak"),
    ("vrocina", "Vročina", "vročina in soparnost"),
    ("nevihta", "Nevihta", "nevihte"),
    ("sprememba", "Hitra sprememba vremena", "hitre spremembe vremena (temperatura, tlak)"),
    ("vlaga", "Zračna vlaga", "zelo vlažen ali zelo suh zrak"),
]
FACTOR_KEYS = [k for k, _, _ in FACTORS]

HOURLY_WX = "temperature_2m,apparent_temperature,relative_humidity_2m,pressure_msl,weather_code"


# ── Pravila (točke 0-3) ──────────────────────────────────────────────────────

def pts_by_thresholds(v, ths):
    """ths = (t1, t2, t3): pod t1 -> 0, pod t2 -> 1, pod t3 -> 2, sicer 3."""
    if v is None:
        return 0
    return 0 if v < ths[0] else 1 if v < ths[1] else 2 if v < ths[2] else 3


def pts_pollen(v, th):
    """POLLEN_TYPES pragovi so (nizka|zmerna, zmerna|visoka, visoka|zelo visoka)."""
    if v is None or v < th[0]:
        return 0
    return 1 if v < th[1] else 2 if v < th[2] else 3


def pts_cold(amin):
    if amin is None or amin > 0:
        return 0
    return 1 if amin > -5 else 2 if amin > -10 else 3


def pts_heat(amax):
    return pts_by_thresholds(amax, (28, 32, 35))


def pts_storm(storm, grass_max):
    if not storm:
        return 0
    return 3 if (grass_max is not None and grass_max >= POLLEN_TYPES[0][2][0]) else 1


def pts_change(dtemp, prange):
    t = 0 if dtemp is None else (2 if abs(dtemp) >= 8 else 1 if abs(dtemp) >= 5 else 0)
    p = 0 if prange is None else (2 if prange >= 12 else 1 if prange >= 8 else 0)
    return max(t, p)


def pts_humidity(rh_mean):
    if rh_mean is None:
        return 0
    return 1 if (rh_mean >= 90 or rh_mean < 30) else 0


def score_for(pts, weights=None):
    w = weights or {}
    return sum(pts.get(k, 0) * w.get(k, 1) for k in FACTOR_KEYS)


def level_for(score, max_pts, th=SCORE_TH):
    """max_pts = največ točk enega (uteženega) dejavnika; tla 3 točke = povišano."""
    lvl = 0 if score < th[0] else 1 if score < th[1] else 2 if score < th[2] else 3
    if max_pts >= FLOOR_PTS:
        lvl = max(lvl, 2)
    return LEVELS[lvl]


# JS kopija -- test_astma.py ju poganja na isti mreži vhodov.
ASTMA_JS_CORE = """function astmaScore(pts,w){var s=0;for(var k in pts){s+=pts[k]*(w&&w[k]!=null?w[k]:1);}return s;}
function astmaLevel(pts,w,th,floor,levels){var s=astmaScore(pts,w),m=0;for(var k in pts){if(pts[k]>m)m=pts[k];}
var l=s<th[0]?0:s<th[1]?1:s<th[2]?2:3;if(m>=floor&&l<2)l=2;return levels[l];}"""


# ── Podatki ──────────────────────────────────────────────────────────────────

def fetch_weather():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "hourly": HOURLY_WX,
        "timezone": "Europe/Ljubljana", "past_days": 1, "forecast_days": DNEVI,
    })
    req = urllib.request.Request(f"https://api.open-meteo.com/v1/forecast?{params}",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _by_day(hourly, key):
    out = {}
    for t, v in zip(hourly.get("time") or [], hourly.get(key) or []):
        if v is not None:
            out.setdefault(t[:10], []).append(v)
    return out


def _mean(a):
    return sum(a) / len(a) if a else None


def day_factors(aq, wx, date_iso):
    """Točke in kratek razlog za vsak dejavnik za en dan. Vrne (pts, detail)."""
    ah, wh = aq.get("hourly") or {}, wx.get("hourly") or {}
    g = lambda key: _by_day(ah, key).get(date_iso, [])
    w = lambda key: _by_day(wh, key).get(date_iso, [])
    n = seo.num
    pts, det = {}, {}

    best, best_p = None, 0
    grass_max = max(g("grass_pollen"), default=None)
    for key, lbl, th in POLLEN_TYPES:
        vals = g(key)
        v = max(vals, default=None)
        p = pts_pollen(v, th)
        if p > best_p:
            best_p, best = p, f"{lbl.split(' ', 1)[1].lower()} {n(v, 0)} zrn/m³"
    pts["pelod"], det["pelod"] = best_p, best or "ni pomembnega cvetnega prahu"

    pm = _mean(g("pm2_5"))
    pts["pm"] = pts_by_thresholds(pm, (15, 25, 50))
    det["pm"] = f"PM2,5 povprečno {n(pm, 0)} µg/m³" if pm is not None else "ni podatka"
    oz = max(g("ozone"), default=None)
    pts["ozon"] = pts_by_thresholds(oz, (100, 120, 180))
    det["ozon"] = f"ozon do {n(oz, 0)} µg/m³" if oz is not None else "ni podatka"
    no2 = max(g("nitrogen_dioxide"), default=None)
    pts["no2"] = pts_by_thresholds(no2, (100, 200, 400))
    det["no2"] = f"NO₂ do {n(no2, 0)} µg/m³" if no2 is not None else "ni podatka"

    app = w("apparent_temperature")
    amin, amax = min(app, default=None), max(app, default=None)
    pts["mraz"] = pts_cold(amin)
    det["mraz"] = f"občutena do {n(amin, 0)} °C" if amin is not None else "ni podatka"
    pts["vrocina"] = pts_heat(amax)
    det["vrocina"] = f"občutena do {n(amax, 0)} °C" if amax is not None else "ni podatka"

    storm = any(c >= 95 for c in w("weather_code"))
    pts["nevihta"] = pts_storm(storm, grass_max)
    det["nevihta"] = ("nevihta ob cvetenju trav (nevihtna astma)" if pts["nevihta"] == 3
                      else "napovedana nevihta" if storm else "brez neviht")

    prev = (datetime.date.fromisoformat(date_iso) - datetime.timedelta(days=1)).isoformat()
    t_today, t_prev = _mean(w("temperature_2m")), _mean(_by_day(wh, "temperature_2m").get(prev, []))
    dtemp = None if (t_today is None or t_prev is None) else t_today - t_prev
    pr = w("pressure_msl")
    prange = (max(pr) - min(pr)) if pr else None
    pts["sprememba"] = pts_change(dtemp, prange)
    parts = []
    if dtemp is not None and abs(dtemp) >= 5:
        parts.append(f"povprečje {'+' if dtemp > 0 else '−'}{n(abs(dtemp), 0)} °C glede na včeraj")
    if prange is not None and prange >= 8:
        parts.append(f"tlak {n(prange, 0)} hPa v dnevu")
    det["sprememba"] = ", ".join(parts) or "stabilno"

    rh = _mean(w("relative_humidity_2m"))
    pts["vlaga"] = pts_humidity(rh)
    det["vlaga"] = f"vlaga povprečno {n(rh, 0)} %" if rh is not None else "ni podatka"
    return pts, det


def build_days(aq, wx):
    days = []
    for i in range(DNEVI):
        d = TODAY + datetime.timedelta(days=i)
        iso = d.isoformat()
        pts, det = day_factors(aq, wx, iso)
        score = score_for(pts)
        lvl = level_for(score, max(pts.values()))
        label = "Danes" if i == 0 else "Jutri" if i == 1 else DAN_KRATKO[d.weekday()]
        days.append({"date": iso, "label": label, "pts": pts, "detail": det,
                     "score": score, "level": lvl})
    return days


def reasons(day, k=2):
    """Največ k dejavnikov z najvišjimi točkami (od 1 naprej), z besedilom."""
    ranked = sorted(((p, key) for key, p in day["pts"].items() if p >= 1), reverse=True)
    return [day["detail"][key] for _, key in ranked[:k]]


# ── Izris ────────────────────────────────────────────────────────────────────

PTS_WORD = {0: "—", 1: "blago", 2: "zmerno", 3: "visoko"}
PTS_COLOR = {1: "#eab308", 2: "#f97316", 3: "#ef4444"}

CSS = """<style>
.as-days{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem;margin:1rem 0 1.4rem}
.as-day{border:1px solid rgba(255,255,255,.1);border-top:4px solid var(--c,#059669);border-radius:10px;padding:.75rem .85rem;background:rgba(255,255,255,.03)}
.as-day h3{margin:0;font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.as-day .as-lvl{font-size:1.25rem;font-weight:800;color:var(--c,#059669);margin:.15rem 0}
.as-day .as-sc{font-family:'JetBrains Mono',monospace;font-size:.72rem;color:var(--muted)}
.as-day ul{margin:.5rem 0 0;padding-left:1rem;font-size:.8rem}
.as-heat td{text-align:center}
.as-trig{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.as-trig label{display:flex;align-items:center;gap:.4rem;padding:.45rem .7rem;border:1px solid rgba(255,255,255,.18);border-radius:8px;cursor:pointer;min-height:44px;font-size:.88rem}
.as-trig input{width:18px;height:18px}
</style>"""


def esc(s):
    return html.escape(str(s))


def day_cards_html(days):
    out = []
    for d in days:
        col = LEVEL_COLORS[d["level"]]
        rs = reasons(d)
        li = "".join(f"<li>{esc(r)}</li>" for r in rs) or "<li>brez izrazitih sprožilcev</li>"
        out.append(f'    <div class="as-day" style="--c:{col}" data-i="{days.index(d)}">'
                   f'<h3>{esc(d["label"])}</h3><div class="as-lvl">{d["level"]}</div>'
                   f'<div class="as-sc">ocena {d["score"]} od 27</div><ul>{li}</ul></div>')
    return '  <div class="as-days" id="as-days">\n' + "\n".join(out) + "\n  </div>"


def heatmap_html(days):
    head = "<th></th>" + "".join(f"<th>{esc(d['label'])}</th>" for d in days)
    rows = []
    for key, lbl, _ in FACTORS:
        cells = []
        for d in days:
            p = d["pts"][key]
            if p == 0:
                cells.append("<td>—</td>")
            else:
                cells.append(f'<td title="{esc(d["detail"][key])}" style="background:{PTS_COLOR[p]};'
                             f'color:#04070e;font-weight:700">{PTS_WORD[p]}</td>')
        rows.append(f"<tr><th>{esc(lbl)}</th>{''.join(cells)}</tr>")
    return ('  <div class="table-scroll" tabindex="0"><table class="stats as-heat">\n'
            f'    <tr>{head}</tr>\n    ' + "\n    ".join(rows) + "\n  </table></div>")


def triggers_html():
    boxes = "".join(
        f'<label><input type="checkbox" value="{k}"> {esc(desc)}</label>' for k, _, desc in FACTORS)
    return (f'  <div class="as-trig" id="as-trig" role="group" aria-label="Moji sprožilci">{boxes}</div>\n'
            '  <p class="muted-note" id="as-trig-note">Izbira se shrani samo v tem brskalniku in se nikamor ne pošlje.</p>')


def client_js(days):
    payload = {
        "days": [{"label": d["label"], "pts": d["pts"], "detail": d["detail"]} for d in days],
        "th": list(SCORE_TH), "floor": FLOOR_PTS, "levels": LEVELS,
        "colors": LEVEL_COLORS, "weight": TRIGGER_WEIGHT, "keys": FACTOR_KEYS,
    }
    return ("<script>\n(function(){\n" + ASTMA_JS_CORE + "\n"
            "var D=" + json.dumps(payload, ensure_ascii=False) + ",KEY='wx-astma-sprozilci';\n"
            """function load(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')||[];}catch(e){return [];}}
function save(a){try{localStorage.setItem(KEY,JSON.stringify(a));}catch(e){}}
function weights(sel){var w={};if(sel.length){sel.forEach(function(k){w[k]=D.weight;});}return w;}
function render(sel){
  var w=weights(sel),el=document.getElementById('as-days');if(!el)return;
  var cards=el.querySelectorAll('.as-day');
  D.days.forEach(function(d,i){var c=cards[i];if(!c)return;
    var lvl=astmaLevel(d.pts,w,D.th,D.floor,D.levels),sc=astmaScore(d.pts,w);
    c.style.setProperty('--c',D.colors[lvl]);
    c.querySelector('.as-lvl').textContent=lvl;
    c.querySelector('.as-sc').textContent='ocena '+sc+(sel.length?' (moji sprožilci štejejo dvojno)':' od 27');
    var r=Object.keys(d.pts).filter(function(k){return d.pts[k]>0;})
      .sort(function(a,b){return (d.pts[b]*(w[b]||1))-(d.pts[a]*(w[a]||1));}).slice(0,2)
      .map(function(k){return d.detail[k];});
    var ul=c.querySelector('ul');ul.textContent='';
    (r.length?r:['brez izrazitih sprožilcev']).forEach(function(t){var li=document.createElement('li');li.textContent=t;ul.appendChild(li);});
  });
}
var boxes=document.querySelectorAll('#as-trig input'),sel=load();
boxes.forEach(function(b){b.checked=sel.indexOf(b.value)>=0;
  b.addEventListener('change',function(){sel=[].filter.call(boxes,function(x){return x.checked;}).map(function(x){return x.value;});save(sel);render(sel);});});
if(sel.length)render(sel);
})();
</script>""")


FAQ = [
    ("Kako je izračunana ocena?",
     "Za vsak dan seštejemo točke (0–3) devetih dejavnikov: cvetni prah, PM2,5, ozon, NO₂, mrzel zrak, vročina, nevihta, "
     "hitra sprememba vremena in vlaga. Ocena 0–1 je nizko, 2–3 zmerno, 4–5 povišano, 6 ali več visoko; en sam dejavnik s "
     "tremi točkami da vsaj povišano. Pragovi so naša delitev po znanih sprožilcih in niso klinična lestvica."),
    ("Je ocena verjetnost astmatičnega napada?",
     "Ne. Je pregled sprožilcev, ki jih napovedujeta vreme in zrak. Kako se posameznik odzove, je zelo različno in "
     "odvisno od zdravljenja, zato ocene ne uporabljajte za odločanje o zdravilih."),
    ("Kaj je nevihtna astma?",
     "Redek pojav, ko nevihta v času cvetenja trav v zrak dvigne drobne delce cvetnega prahu in jih tudi ljudje brez znane "
     "astme vdihnejo globlje. Stran ga označi samo, kadar sta napovedana hkrati nevihta in cvetenje trav."),
    ("Zakaj mrzel zrak in vročina?",
     "Mrzel in suh zrak lahko pri nekaterih zoži dihalne poti, zlasti ob naporu; vročina in soparnost obremenita dihanje, "
     "poleti pa ju spremlja še ozon. Zato se pri teh dejavnikih upošteva občutena temperatura."),
    ("Ali stran shranjuje moje podatke?",
     "Ne. Izbira sprožilcev ostane v vašem brskalniku (localStorage) in se ne pošlje na strežnik. Strani ne vodita ne računa "
     "ne dnevnika simptomov."),
]


def level_advice(level):
    return {
        "nizko": "Vreme in zrak niso izrazit sprožilec. Ravnajte po svojem načrtu zdravljenja.",
        "zmerno": "Občutljivejši naj bodo pozorni na simptome; zdravilo za lajšanje naj bo pri roki, kot ga je predpisal zdravnik.",
        "povišano": "Za občutljive je to dan z več sprožilci. Naporne dejavnosti na prostem razmislite premakniti na boljši čas dneva; ravnajte po načrtu, ki ste ga dobili pri zdravniku.",
        "visoko": "Več sprožilcev hkrati. Naporne dejavnosti na prostem odložite, zdravilo naj bo pri roki, ob poslabšanju ravnajte po načrtu zdravljenja ali pokličite zdravnika (nujna pomoč: 112).",
    }[level]


def build_body(days):
    today = days[0]
    rs = reasons(today, 3)
    why = (" Glavni razlogi: " + "; ".join(rs) + ".") if rs else " Danes ni izrazitih sprožilcev."
    answer = (f'  <p class="archive-intro" id="as-answer">Tveganje za ljudi z astmo v Zgornji Savinjski dolini je danes '
              f'<strong>{today["level"]}</strong> (ocena {today["score"]} od 27).{esc(why)} '
              f'{esc(level_advice(today["level"]))} Osvežitev {TODAY.isoformat()}.</p>')

    best = min(days, key=lambda d: (d["score"], d["date"]))
    outlook = (f'Najugodnejši je {esc(best["label"].lower())} (ocena {best["score"]}).'
               if best["score"] < today["score"] else "Danes je najugodnejši dan v napovedi.")

    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f"    <details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in FAQ) + "\n  </div>"

    rules = [
        ("Cvetni prah", "najvišja vrsta; pragovi kot na /kakovost-zraka/", "blago od nizke, visoko ≥ zelo visoke"),
        ("PM2,5 (dnevno povprečje)", "15 / 25 / 50 µg/m³", "WHO / EU dnevna meja"),
        ("Ozon (urni najvišji)", "100 / 120 / 180 µg/m³", "120 = ciljna vrednost EU, 180 = opozorilni prag"),
        ("NO₂ (urni najvišji)", "100 / 200 / 400 µg/m³", "200 = urna meja EU"),
        ("Mrzel zrak (najnižja občutena)", "≤ 0 / ≤ −5 / ≤ −10 °C", "občutena temperatura"),
        ("Vročina (najvišja občutena)", "≥ 28 / 32 / 35 °C", "občutena temperatura"),
        ("Nevihta", "1 točka; 3 ob cvetenju trav", "nevihtna astma"),
        ("Hitra sprememba", "povprečje ±5 / ±8 °C ali tlak ≥ 8 / 12 hPa", "glede na prejšnji dan"),
        ("Zračna vlaga", "1 točka pri ≥ 90 % ali < 30 %", "dnevno povprečje"),
    ]
    rule_rows = "\n".join(f"    <tr><th>{esc(a)}</th><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rules)

    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Vreme in astma", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Vreme in astma: napoved tveganja za 5 dni</h1>
  <p class="post-meta">Cvetni prah, onesnažen zrak, mraz, vročina, nevihte in hitre spremembe · Zgornja Savinjska dolina · {TODAY.isoformat()}</p>
{answer}
  <p class="muted-note"><strong>To ni zdravniški nasvet.</strong> Ocena prikazuje sprožilce, ki jih napovedujeta vreme in zrak,
  ne verjetnosti napada. Za zdravljenje in ukrepe veljajo navodila vašega zdravnika; v nujnem primeru pokličite 112.</p>
  <h2>Naslednjih 5 dni</h2>
  <p class="archive-intro">{outlook} Karte so barvane po oceni, raven pa je vedno zapisana tudi z besedo.</p>
{day_cards_html(days)}
  <h2>Kateri dejavniki so v igri</h2>
  <p class="archive-intro">Najvišji dnevni vpliv posameznega dejavnika. Pomik nad celico pokaže razlog.</p>
{heatmap_html(days)}
  <h2>Moji sprožilci</h2>
  <p class="archive-intro">Označite, kaj občutite pri sebi. Izbrani dejavniki bodo pri oceni šteli dvojno.</p>
{triggers_html()}
  <h2>Kako je ocena sestavljena</h2>
  <table class="stats">
    <tr><th>Dejavnik</th><td>Pragovi (blago / zmerno / visoko)</td><td>Opomba</td></tr>
{rule_rows}
  </table>
  <p class="muted-note">Podatki: Copernicus CAMS Europe (zrak, cvetni prah) in Open-Meteo (temperatura, vlaga, tlak, nevihte) za Rečico ob
  Savinji. Gre za modelsko napoved, ne za meritev; mreža modela ne razloči dolin in lokalnih virov.</p>
{faq_html}
  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">Povezave</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="/kakovost-zraka/" class="mtn-avk-link">Kakovost zraka in cvetni prah →</a>
      <a href="/biovreme/" class="mtn-avk-link">Biovreme →</a>
      <a href="https://www.arso.gov.si/zrak/" target="_blank" rel="noopener" class="mtn-avk-link">ARSO — kakovost zraka</a>
      <a href="https://www.nijz.si/" target="_blank" rel="noopener" class="mtn-avk-link">NIJZ</a>
    </div>
  </div>
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>
{client_js(days)}'''


def main():
    print(f"[{TODAY}] Pridobivam zrak in vreme za astmo …")
    try:
        aq = fetch_air_quality()
        wx = fetch_weather()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        sys.exit(1)

    days = build_days(aq, wx)
    if not any(sum(d["pts"].values()) or d["detail"]["pm"] != "ni podatka" for d in days):
        print("✗ Podatkov ni (vsi dnevi brez vrednosti)", file=sys.stderr)
        sys.exit(1)

    url = "/astma/"
    title = "Vreme in astma: napoved tveganja za 5 dni"
    t = days[0]
    desc = (f"Tveganje za ljudi z astmo danes: {t['level']}. Pelod, PM2,5, ozon, mraz, vročina, nevihte in hitre "
            f"spremembe vremena za 5 dni v Zgornji Savinjski dolini.")
    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-10-29"),
        seo.crumbs_schema([("Meteorec", "/"), ("Vreme in astma", None)]),
        seo.faq_schema(FAQ),
    ]) + "\n" + CSS
    page = seo.page_shell(title, desc, url, schema, build_body(days))
    seo.write_page("astma/index.html", page, force=True)
    print(f"  → astma/index.html (danes {t['level']}, ocena {t['score']})")


if __name__ == "__main__":
    main()
