#!/usr/bin/env python3
"""
tools/generate_sonce_page.py — /sonce-v-dolini/ (3. 11. 2026)

Kdaj sonce v Zgornji Savinjski dolini ZARES posije: koledarski vzhod in zahod predpostavljata ravno obzorje, v dolini
pa nas pred soncem zakrivajo hribi. Obzorje za sedem krajev je izračunano iz Copernicus DEM (`tools/build_horizons.py`,
enkratno, izhod `data/horizons.json` je committan), položaj sonca pa je NOAA/Meeus (`tools/sonce_horizont.py`).
Generator DEM-a ne rabi, omrežja tudi ne.

Kar stran je in ni:
- Je GEOMETRIJA: koliko ur bi bilo sonce vidno, če bi bilo nebo jasno. Oblačnost, megla in meteorološki podatki niso
  vključeni (kako dolgo traja jutranja megla, je tema strani /jutro-v-dolini/ in /zima/).
- Obzorje je iz POVRŠINSKEGA modela (teren in gozd), prvih 150 m žarka je preskočenih (najbližje hiše in drevesa).
  Zato je ob vsaki številki razpon za ±1,5° obzorja; v krajih, kjer sonce pozimi komaj preseže greben, je razpon velik.
- Ni meritev: čas prvega žarka s postajo še ni preverjen z dovolj ločljivimi podatki (glej razdelek »Preverjanje«).

Izhod: sonce-v-dolini/index.html + sonce-v-dolini/dnevi.json (podatki za orodje na strani; leto 2027, nevisokosno).
Usage:
  python3 tools/generate_sonce_page.py
"""
import datetime
import html as _html
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
import atmos_common as ac  # noqa: E402 — line_chart (SVG), num()
import sonce_horizont as sh  # noqa: E402

OFFSET_DEG = 1.5  # občutljivost obzorja: površinski model vključuje gozd
URL = "/sonce-v-dolini/"
PUBLISHED = "2026-11-03"
MESECI = ["januar", "februar", "marec", "april", "maj", "junij", "julij", "avgust", "september", "oktober",
          "november", "december"]
# Ključni dnevi: solsticij, sredina zime, enakonočji, začetek zime; (mesec, dan, napis)
KEY_DATES = [(12, 21, "21. 12."), (2, 1, "1. 2."), (3, 21, "21. 3."), (6, 21, "21. 6."), (9, 23, "23. 9."),
             (11, 1, "1. 11.")]
CHART_PLACES = [("recica", "Rečica", "#f59e0b"), ("luce", "Luče", "#a855f7"), ("solcava", "Solčava", "#38bdf8")]


def h1(minutes, d=1):
    """Minute → ure z decimalno vejico (»7,3«)."""
    return ac.num(minutes / 60.0, d)


def doy(m, d):
    return (datetime.date(sh.REFERENCE_YEAR, m, d) - datetime.date(sh.REFERENCE_YEAR, 1, 1)).days


def date_label(i):
    d = datetime.date(sh.REFERENCE_YEAR, 1, 1) + datetime.timedelta(days=i)
    return f"{d.day}. {d.month}."


def zero_runs(minutes):
    """Strnjena obdobja dni brez sonca (ciklično čez novo leto): [(prvi_dan_indeks, zadnji_dan_indeks, dolžina)]."""
    n = len(minutes)
    zeros = [m == 0 for m in minutes]
    if not any(zeros):
        return []
    if all(zeros):
        return [(0, n - 1, n)]
    start = next(i for i in range(n) if not zeros[i])  # začni pri dnevu s soncem, da obdobje čez silvestrovo ostane celo
    runs, cur = [], None
    for k in range(n):
        i = (start + k) % n
        if zeros[i]:
            cur = [i, i, 1] if cur is None else [cur[0], i, cur[2] + 1]
        elif cur is not None:
            runs.append(tuple(cur))
            cur = None
    if cur is not None:
        runs.append(tuple(cur))
    return runs


def build_data():
    hz = sh.load_horizons()
    out = []
    for p in hz["places"]:
        cen = sh.year_profiles(p["lat"], p["lon"], p["horizon"])
        free = sh.year_profiles(p["lat"], p["lon"], p["horizon"], offset=-OFFSET_DEG)    # manj zakrito
        blocked = sh.year_profiles(p["lat"], p["lon"], p["horizon"], offset=OFFSET_DEG)  # več zakrito
        out.append({**p, "cen": cen, "free": free, "blocked": blocked})
    return hz, out


def dnevi_json(places):
    nz = lambda v: -1 if v is None else v  # noqa: E731
    obj = {"leto": sh.REFERENCE_YEAR, "odmik_stopinj": OFFSET_DEG, "p": {}}
    for p in places:
        obj["p"][p["id"]] = {
            "n": p["name"], "e": p["elev"],
            "d": [[nz(c["flat_rise"]), nz(c["flat_set"]), nz(c["first"]), nz(c["last"]), c["sun_min"],
                   f["sun_min"], b["sun_min"]] for c, f, b in zip(p["cen"], p["free"], p["blocked"])]}
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def cell(p, i):
    c, f, b = p["cen"][i], p["free"][i], p["blocked"][i]
    if c["sun_min"] == 0:
        extra = "" if f["sun_min"] == 0 else f'<br><small>ob nižjem obzorju do {h1(f["sun_min"])} h</small>'
        return f"brez sonca{extra}"
    rng = ""
    if f["sun_min"] - b["sun_min"] >= 60:  # razpon pokažemo, ko je negotovost vsaj ura
        rng = f'<br><small>razpon {h1(b["sun_min"])}–{h1(f["sun_min"])} h</small>'
    return f'{h1(c["sun_min"])} h<br><small>{sh.hhmm(c["first"])}–{sh.hhmm(c["last"])}</small>{rng}'


def key_dates_table(places):
    head = "".join(f'<th scope="col">{lab}</th>' for _, _, lab in KEY_DATES)
    rows = []
    for p in places:
        tds = "".join(f"<td>{cell(p, doy(m, d))}</td>" for m, d, _ in KEY_DATES)
        rows.append(f'      <tr><th scope="row">{_html.escape(p["name"])}<br><small>{p["elev"]} m</small></th>{tds}</tr>')
    # koledarske ure kot referenca (za Rečico, razlika med kraji je pod 3 minute)
    ref = places[0]
    tds = "".join(f'<td>{h1(ref["cen"][doy(m, d)]["flat_min"])} h<br><small>{sh.hhmm(ref["cen"][doy(m, d)]["flat_rise"])}–'
                  f'{sh.hhmm(ref["cen"][doy(m, d)]["flat_set"])}</small></td>' for m, d, _ in KEY_DATES)
    rows.append(f'      <tr><th scope="row">Koledar<br><small>ravno obzorje</small></th>{tds}</tr>')
    return ('  <table class="stats sv">\n    <thead><tr><th scope="col">Kraj</th>' + head + '</tr></thead>\n    <tbody>\n'
            + "\n".join(rows) + '\n    </tbody>\n  </table>')


def monthly_table(places):
    month_idx = [[i for i in range(365) if (datetime.date(sh.REFERENCE_YEAR, 1, 1)
                                            + datetime.timedelta(days=i)).month == m] for m in range(1, 13)]
    head = "".join(f'<th scope="col">{_html.escape(p["name"].replace(" ob Savinji", ""))}</th>' for p in places)
    rows = []
    for m in range(12):
        tds = "".join(f'<td>{h1(np.mean([p["cen"][i]["sun_min"] for i in month_idx[m]]))}</td>' for p in places)
        flat = np.mean([places[0]["cen"][i]["flat_min"] for i in month_idx[m]])
        rows.append(f'      <tr><th scope="row">{MESECI[m].capitalize()}</th>{tds}<td>{h1(flat)}</td></tr>')
    ann = "".join(f'<td><strong>{h1(np.mean([c["sun_min"] for c in p["cen"]]))}</strong></td>' for p in places)
    ann_flat = np.mean([c["flat_min"] for c in places[0]["cen"]])
    rows.append(f'      <tr><th scope="row">Povprečje leta</th>{ann}<td><strong>{h1(ann_flat)}</strong></td></tr>')
    return ('  <table class="stats">\n    <thead><tr><th scope="col">Mesec</th>' + head
            + '<th scope="col">Koledar</th></tr></thead>\n    <tbody>\n' + "\n".join(rows) + '\n    </tbody>\n  </table>')


def zero_table(places):
    rows = []
    for p in places:
        m = [c["sun_min"] for c in p["cen"]]
        runs = zero_runs(m)
        fr = zero_runs([c["sun_min"] for c in p["free"]])
        bl = zero_runs([c["sun_min"] for c in p["blocked"]])
        low = min(range(365), key=lambda i: m[i])
        if runs:
            a, b, n = max(runs, key=lambda r: r[2])
            when = f"od {date_label(a)} do {date_label(b)}"
            rng = (f"{sum(r[2] for r in fr)}–{sum(r[2] for r in bl)}")
            cell1, cell2 = f"{n} dni ({when})", rng + " dni"
        else:
            cell1, cell2 = "ni takih dni", ("do " + str(sum(r[2] for r in bl)) + " dni") if bl else "—"
        rows.append(f'      <tr><th scope="row">{_html.escape(p["name"])}</th><td>{cell1}</td><td>{cell2}</td>'
                    f'<td>{h1(m[low])} h ({date_label(low)})</td></tr>')
    return ('  <table class="stats">\n    <thead><tr><th scope="col">Kraj</th><th scope="col">Dnevi brez neposrednega sonca</th>'
            '<th scope="col">Pri obzorju ±1,5°</th><th scope="col">Najkrajši dan</th></tr></thead>\n    <tbody>\n'
            + "\n".join(rows) + '\n    </tbody>\n  </table>')


def chart(places):
    byid = {p["id"]: p for p in places}
    ref = byid["recica"]
    pts = lambda key, p: [(datetime.date(sh.REFERENCE_YEAR, 1, 1) + datetime.timedelta(days=i), c[key] / 60.0)  # noqa: E731
                          for i, c in enumerate(p["cen"])]
    series = [{"name": "Koledar (ravno obzorje)", "color": "currentColor", "pts": pts("flat_min", ref), "width": 1.5,
               "dash": "5 4"}]
    for pid, name, color in CHART_PLACES:
        series.append({"name": name, "color": color, "pts": pts("sun_min", byid[pid]), "width": 2.2})
    svg = ac.line_chart(series, ymin=0, ymax=16, zero=False, unit="ure sonca na dan", width=520, height=300,
                        yfmt=lambda v: str(int(v)), x_every=61,
                        aria="Število ur neposrednega sonca na dan čez leto v Rečici, Lučah in Solčavi, "
                             "primerjano s koledarskim trajanjem dneva")
    leg = ac.legend([("currentColor", "Koledar (ravno obzorje)", True)] + [(c, n, False) for _, n, c in CHART_PLACES])
    return leg + "\n" + svg


VERIF_PATH = os.path.join(seo.ROOT, "data", "sonce-preverjanje.json")


def validation_html():
    """Rezultat preverjanja s 5-minutnimi meritvami, ko je dni dovolj; sicer pove, kaj je in česa ni mogoče preveriti."""
    try:
        with open(VERIF_PATH, encoding="utf-8") as f:
            v = json.load(f)
    except (OSError, ValueError):
        v = None
    if v and v.get("jutro", {}).get("n", 0) >= v.get("min_dni", 15):
        j = v["jutro"]
        extra = ""
        e = v.get("vecer", {})
        if e.get("n", 0) >= v.get("min_dni", 15):
            extra = (f' Zvečer ({e["n"]} dni) je mediana razlike za zadnji žarek {ac.num(e["mediana_min"], 0)} min '
                     f'(razpon {ac.num(e["min_min"], 0)} do {ac.num(e["max_min"], 0)} min).')
        return (f'  <p class="archive-intro">Na {j["n"]} jasnih jutrih sem prvi hiter skok sevanja na postaji IREICA1 primerjal '
                f'z izračunanim prvim žarkom. Mediana razlike je <strong>{ac.num(j["mediana_min"], 0)} min</strong> '
                f'(izmerjeno minus model; pozitivno pomeni, da sonce pride pozneje, kot pravi model), tipično odstopanje '
                f'{ac.num(j["mad_min"], 0)} min, razpon {ac.num(j["min_min"], 0)} do {ac.num(j["max_min"], 0)} min.{extra} '
                f'Razlika je sistematična in prevelika za šum. Skok se pojavi, ko je sonce že visoko (~25° in več), kar ni '
                f'hrib, ampak senca nečesa, kar je blizu: najverjetneje senzor stoji v senci bližnjega objekta ali drevesa. '
                f'To je domneva, ne dokaz. Izračun obzorja torej velja za odprt teren v Rečici in ga s to postajo ni mogoče '
                f'potrditi ali ovreči; za senzor IREICA1 je sonce zjutraj pozneje in zvečer prej, kot je izračunano.</p>')
    n = (v or {}).get("jutro", {}).get("n", 0)
    return ('  <p class="archive-intro">Čas prvega žarka s postajo <strong>še nisem preveril</strong>. Urni zapis sevanja '
            'IREICA1 (113 dni, od 13. 7. 2026) je za to pregrob: ura je daljša od zamika, ki ga iščem, jutra pa pogosto '
            'zakrije megla, ki izgleda enako kot hrib. Na jasnih dneh postaja zjutraj in zvečer res meri manj sevanja, kot bi ga '
            'ob ravnem obzorju, kar je smer, ki jo model napove, vendar je tudi privzeti model čistega neba pri nizkem soncu '
            'preveč radodaren, zato iz tega ne sklepam količine. Pošteno preverjanje omogočajo 5-minutne vrednosti: '
            'postaja jih od 3. novembra 2026 zapisuje ob vzhodu in zahodu, rezultat pa objavim, ko bo vsaj 15 jasnih jutr '
            f'z izrazitim skokom sevanja (zdaj jih je {n}).</p>')


FAQ = [
    ("Zakaj sonce v dolini posije pozneje, kot piše v koledarju?",
     "Koledarski vzhod velja za ravno obzorje. V dolini je obzorje na vzhodni strani dvignjeno za več stopinj: "
     "v Rečici znaša povprečno 8°, v Solčavi 23°. Sonce mora dvigniti nad greben, preden ga zagledate."),
    ("Kako ste izračunali, kdaj sonce posije?",
     "Višino hribov po vseh smereh sem izračunal iz Copernicus DEM (30 m), položaj sonca pa po algoritmu NOAA/Meeus. "
     "Sonce štejem za vidno, ko je zgornji rob diska nad obzorjem v smeri sonca."),
    ("Je to napoved sončnega vremena?",
     "Ne. To je geometrija: koliko ur bi bilo sonce vidno, če bi bilo nebo jasno. Oblaki in megla niso vključeni. "
     "Za dejansko vreme glejte napoved na naslovni strani."),
    ("Kako natančni so časi?",
     "Za obzorje velja negotovost približno ±1,5°, ker digitalni model vključuje gozd in ker obzorje velja za eno točko. "
     "Pozimi, ko sonce komaj preseže greben, ta razlika naredi tudi uro ali več; ob vsaki številki zato objavljam razpon."),
    ("Zakaj ni moje vasi ali domačije?",
     "Obzorje velja za eno točko. Že 300 m stran je lahko drugačno, zlasti pod pobočjem. Tu so središča sedmih krajev; "
     "za svojo točko izračun lahko ponovite z orodjem iz repozitorija."),
]


def build_body(places, data_ref):
    byid = {p["id"]: p for p in places}
    rec, sol = byid["recica"], byid["solcava"]
    i_dec = doy(12, 21)
    c_rec = rec["cen"][i_dec]
    zr = zero_runs([c["sun_min"] for c in sol["cen"]])
    assert zr, "Solčava mora imeti obdobje brez sonca, sicer je uvod napačen — pregled besedila"
    a, b, n = max(zr, key=lambda r: r[2])
    first_back = (b + 1) % 365
    lead = (f'<strong>Kratek odgovor:</strong> 21. decembra sonce v Rečici po koledarju vzide ob {sh.hhmm(c_rec["flat_rise"])}, '
            f'do dolinskega dna pa pride ob {sh.hhmm(c_rec["first"])}; zaide ob {sh.hhmm(c_rec["last"])} namesto '
            f'ob {sh.hhmm(c_rec["flat_set"])}. Dneva je tako {h1(c_rec["sun_min"])} ure namesto {h1(c_rec["flat_min"])}. '
            f'V Solčavi je središče kraja po izračunu {n} dni, od {date_label(a)} do {date_label(b)}, brez '
            f'neposrednega sonca.')
    nofree = [p for p in places if p["id"] != "recica" and min(c["sun_min"] for c in p["cen"]) < 240]
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("Sonce v dolini", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Kdaj sonce zares posije v Zgornji Savinjski dolini</h1>
  <p class="post-meta">Izračun za sedem krajev · Copernicus DEM in položaj sonca · objavljeno 3. novembra 2026</p>
  <p class="archive-intro">{lead}</p>
  <p class="archive-intro">Koledar zna povedati samo, kdaj sonce vzide nad ravnim obzorjem. V dolini ga pred nami skrivajo
  hribi, zato je prvi žarek na dnu doline pozneje in zadnji prej. Spodaj je za vsak kraj izračunano, kdaj in koliko ur sonce
  res vidimo, če je nebo jasno. To je geometrija, ne vremenska napoved.</p>

  <h2>Izberite kraj in dan</h2>
  <div class="sv-tool" id="sv-tool">
    <label>Kraj <select id="sv-place">{"".join(f'<option value="{p["id"]}">{_html.escape(p["name"])} ({p["elev"]} m)</option>' for p in places)}</select></label>
    <label>Dan <input type="date" id="sv-date"></label>
    <p id="sv-out" class="archive-intro" aria-live="polite">Za izračun potrebuje stran JavaScript. Brez njega glejte tabelo ključnih dni spodaj.</p>
  </div>

  <h2>Ključni dnevi</h2>
  <p class="archive-intro">Ure neposrednega sonca ob jasnem nebu in čas od prvega do zadnjega žarka. Zadnja vrstica je
  koledar za ravno obzorje.</p>
{key_dates_table(places)}

  <h2>Skozi leto</h2>
{chart(places)}
  <p class="muted-note">Črtkana črta je trajanje dneva po koledarju. Razlika do polne črte je sonce, ki ga zakrijejo hribi.</p>

  <h2>Dnevi brez sonca</h2>
  <p class="archive-intro">V krajih ob strmih pobočjih pozimi sonce ne preseže grebena. Tu je, koliko dni v letu je
  središče kraja brez neposrednega sonca; v tretjem stolpcu je razpon, če je obzorje 1,5° nižje ali višje od izračunanega.</p>
{zero_table(places)}

  <h2>Povprečne ure sonca po mesecih</h2>
  <p class="archive-intro">Povprečje ur neposrednega sonca na dan ob jasnem nebu za sredino obzorja. V zadnjem stolpcu je
  koledar.</p>
{monthly_table(places)}

  <h2>Kako je izračunano</h2>
  <ul>
    <li><strong>Obzorje:</strong> za vsak kraj sem po 360 smereh izračunal, pod kolikšnim kotom vidim najvišji hrib, do
    30 km daleč. Upoštevana sta ukrivljenost Zemlje in lom svetlobe. Vir višin je Copernicus DEM (30 m).</li>
    <li><strong>Sonce:</strong> položaj po algoritmu NOAA/Meeus. Vidno je, ko je zgornji rob diska nad obzorjem, enako
    kot pri koledarskem vzhodu.</li>
    <li><strong>Gozd in hiše:</strong> digitalni model je površinski, torej vsebuje tudi gozd na pobočjih. Prvih 150 m
    žarka sem preskočil, da se ne računajo najbližja drevesa in strehe. Zato objavljam razpon za ±1,5°.</li>
    <li><strong>Leto:</strong> izračun je za leto 2027; med leti se časi razlikujejo za minuto ali manj.</li>
  </ul>
  <p class="muted-note">Podatki o terenu: Copernicus DEM GLO-30, © DLR e.V. 2010–2014 in © Airbus Defence and Space GmbH
  2014–2018, licenca Copernicus.</p>

  <h2>Preverjanje</h2>
{validation_html()}
  <p class="muted-note">Nadaljevanje: <a href="/jutro-v-dolini/">kdaj se po prvem žarku dolina ogreje</a> ·
  <a href="/zima/">MeteoZima</a> · <a href="/vreme-recica-ob-savinji/">Vreme Rečica ob Savinji</a>.</p>'''


CSS = '''<style>
.sv-tool{display:grid;gap:.8rem;margin:.5rem 0 1.2rem}
.sv-tool label{display:grid;gap:.25rem;font-size:.9rem}
.sv-tool select,.sv-tool input{font:inherit;color:inherit;background:transparent;border:1px solid rgba(128,128,128,.45);
border-radius:.6rem;padding:.65rem .75rem;min-height:48px;max-width:22rem}
.sv-tool #sv-out{margin:.2rem 0}
.stats small{opacity:.75;font-weight:400}
.stats.sv td,.stats.sv th{white-space:nowrap}
</style>'''

JS = '''<script>
(function(){
var out=document.getElementById('sv-out'),selP=document.getElementById('sv-place'),inD=document.getElementById('sv-date');
if(!out)return;
function pad(n){return n<10?'0'+n:''+n}
var t=new Date();inD.value=t.getFullYear()+'-'+pad(t.getMonth()+1)+'-'+pad(t.getDate());
function hm(m){return m<0?'—':Math.floor(m/60)+'.'+pad(m%60)}
function hh(m){return (m/60).toFixed(1).replace('.',',')}
var DATA=null;
function idx(d){var dim=[31,28,31,30,31,30,31,31,30,31,30,31];var m=d.getMonth(),day=Math.min(d.getDate(),dim[m]);
 return Math.round((Date.UTC(2027,m,day)-Date.UTC(2027,0,1))/86400000)}
function show(){
 if(!DATA)return;var v=inD.value.split('-');if(v.length<3)return;
 var d=new Date(+v[0],+v[1]-1,+v[2]);if(isNaN(d))return;
 var p=DATA.p[selP.value],r=p.d[idx(d)];
 var day=d.getDate()+'. '+(d.getMonth()+1)+'. '+d.getFullYear();
 var s='<strong>'+p.n+', '+day+'.</strong> ';
 if(r[4]===0){
  s+='Neposrednega sonca v središču kraja ta dan ob jasnem nebu <strong>ni</strong>. Koledar sicer obljublja sonce od '+hm(r[0])+' do '+hm(r[1])+' ('+hh(r[1]-r[0])+' h).';
  if(r[5]>0)s+=' Če je obzorje za 1,5° nižje, bi sonca bilo do '+hh(r[5])+' h.';
 }else{
  s+='Koledarski vzhod ob '+hm(r[0])+', <strong>prvi žarek ob '+hm(r[2])+'</strong>; zadnji žarek ob '+hm(r[3])+', koledarski zahod ob '+hm(r[1])+'. ';
  s+='Neposrednega sonca je <strong>'+hh(r[4])+' h</strong> od '+hh(r[1]-r[0])+' h po koledarju (razpon pri obzorju ±1,5°: '+hh(r[6])+'–'+hh(r[5])+' h).';
 }
 out.innerHTML=s;
}
selP.addEventListener('change',show);inD.addEventListener('input',show);
fetch('/sonce-v-dolini/dnevi.json').then(function(r){return r.json()}).then(function(j){DATA=j;show()}).catch(function(){
 out.textContent='Podatkov ni bilo mogoče naložiti. Glejte tabelo ključnih dni spodaj.'});
})();
</script>'''


def main():
    hz, places = build_data()
    data_ref = hz["source"]
    body = build_body(places, data_ref)
    title = "Kdaj sonce posije v dolini: Rečica, Luče, Solčava"
    desc = ("Kdaj sonce v Zgornji Savinjski dolini res posije: prvi in zadnji žarek, ure sonca in dnevi brez sonca "
            "za sedem krajev. Izračun iz terena (Copernicus DEM), ne meritev.")
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ
    ) + "\n  </div>"
    page_body = body + "\n" + faq_html + '\n  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>\n' + JS
    schema = "\n".join([
        seo.webpage_schema(URL, title, desc, date_published=PUBLISHED),
        seo.crumbs_schema([("Meteorec", "/"), ("Sonce v dolini", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(title, desc, URL, schema + "\n" + CSS, page_body)
    seo.write_page("sonce-v-dolini/index.html", page, force=True)
    os.makedirs(os.path.join(seo.ROOT, "sonce-v-dolini"), exist_ok=True)
    with open(os.path.join(seo.ROOT, "sonce-v-dolini", "dnevi.json"), "w", encoding="utf-8") as f:
        f.write(dnevi_json(places))
    print("  → sonce-v-dolini/index.html, sonce-v-dolini/dnevi.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
