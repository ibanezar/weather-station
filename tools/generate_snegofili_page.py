#!/usr/bin/env python3
"""
tools/generate_snegofili_page.py — /snegofili/ (»Snegofili«: kje je sneg po alpskem loku)

Bere data/snegofili.json (piše tools/snegofili_data.py) in ročni seznam data/snegofili-tocke.json (kamere).
Kar stran je in ni:
- Novi sneg je MODELSKA ocena (padavine × delež snega iz ničte izoterme, kot /vreme-v-gorah/), ne meritev.
- Izmerjena višina odeje je ločen stolpec in samo za postaje ARSO; vira se ne zlivata.
- Kamere: ARSO prek workerja /arso-cam in DRSI Črnivec (slika). Tuje kamere so povezave; vdelava (iframe,
  šele po kliku) samo, če ima vnos `embed` + `embed_terms` + `checked` (test to zahteva).
- Ni plazovni bilten in ni nasvet za turo.

Usage: python3 tools/generate_snegofili_page.py
"""
import html as _html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

DATA_PATH = os.path.join(seo.ROOT, "data", "snegofili.json")
POINTS_PATH = os.path.join(seo.ROOT, "data", "snegofili-tocke.json")
URL = "/snegofili/"
TITLE = "Snegofili: kje je sneg, kamere in napoved"
DESC = ("Kje je zdaj sneg po alpskem loku: novi sneg nazaj in naprej, temperatura, meja sneženja in kamere "
        "za 40 točk od Golt do Zermatta. Modelska ocena, izmerjeno ločeno.")
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
DRSI_CAM = "https://www.drsc.si/kamere/Crnivec/Crn1_0001.jpg"
COUNTRIES = {"SI": "Slovenija", "AT": "Avstrija", "IT": "Italija", "CH": "Švica", "FR": "Francija",
             "DE": "Nemčija", "HR": "Hrvaška"}
TRIP_KM = 200
MIN_CM = 1.0  # pod tem »ni snega« v stavkih (model ob pravilih zaokroževanja)

FAQ = [
    ("Je to izmerjen sneg?",
     "Ne. Novi sneg je modelska ocena: padavine iz celice vremenskega modela (Open-Meteo), pomnožene z deležem, "
     "ki pade kot sneg glede na višino ničte izoterme. Celica ne razloči pobočij in dolin, zato je lahko na terenu "
     "več ali manj. Izmerjeno višino snežne odeje imamo samo za nekaj postaj ARSO in je v svojem stolpcu."),
    ("Zakaj je stolpec »izmerjeno« večinoma prazen?",
     "Višino snežne odeje objavljajo le nekatere postaje ARSO (npr. Krvavec, Rogla, Uršlja gora). Tuje točke "
     "nimajo izmerjene vrednosti na tej strani. Prazno polje pomeni, da meritve nimamo, ne da snega ni."),
    ("Kaj pomenita »nazaj« in »naprej«?",
     "Nazaj je ocena novega snega, ki je padel v zadnjih 24 oziroma 72 urah, naprej pa tisto, kar model napoveduje "
     "v naslednjih 24 oziroma 72 urah. Ura, ki teče, se ne šteje naprej."),
    ("Kako izberem kamero?",
     "Slovenske kamere ARSO in DRSI na prelazu Črnivec so prikazane neposredno z navedbo vira. Pri tujih kamerah "
     "vas povezava odpelje k lastniku kamere (smučišče, turistična organizacija). Vdelamo jih samo, kadar ponudnik "
     "vdelavo uradno dovoljuje."),
    ("Ali stran nadomešča plazovni bilten?",
     "Ne. Ocena snega ne pove nič o plazovni nevarnosti. Pred turo preverite uradni plazovni bilten pristojne "
     "države in razmere pri oskrbovani koči ali smučišču."),
]


def num(x, d=0):
    if x is None:
        return "—"
    out = f"{x:.{d}f}"
    if out.lstrip("-").strip("0.") == "":
        out = out.lstrip("-")
    return out.replace(".", ",")


def cm_cell(cm):
    return "—" if cm < MIN_CM else f"{num(cm, 0 if cm >= 10 else 1)} cm"


def load():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    with open(POINTS_PATH, encoding="utf-8") as f:
        cams = {p["id"]: p for p in json.load(f)["tocke"]}
    return data, cams


def hero_sentence(rows):
    best24 = max(rows, key=lambda r: r["past24_cm"])
    best72 = max(rows, key=lambda r: r["past72_cm"])
    near = [r for r in rows if r["km_od_recice"] <= TRIP_KM and r["next24_cm"] >= MIN_CM]
    parts = []
    if best72["past72_cm"] < MIN_CM:
        parts.append("V zadnjih 72 urah po modelu nikjer v seznamu ni zapadlo več kot centimeter novega snega.")
    else:
        last72 = (f'v zadnjih 72 urah pa na točki <strong>{_html.escape(best72["ime"])}</strong> '
                  f'({cm_cell(best72["past72_cm"])}).')
        if best24["past24_cm"] >= MIN_CM:
            parts.append(f'Po modelu je v zadnjih 24 urah najbolj zasnežilo na točki '
                         f'<strong>{_html.escape(best24["ime"])}</strong> ({cm_cell(best24["past24_cm"])}), {last72}')
        else:
            parts.append(f'V zadnjih 24 urah po modelu nikjer ni zapadlo več kot centimeter snega, {last72}')
    if near:
        top = max(near, key=lambda r: r["next24_cm"])
        parts.append(f'Od točk do {TRIP_KM} km zračne razdalje od Rečice je v naslednjih 24 urah največ snega '
                     f'napovedanega na točki <strong>{_html.escape(top["ime"])}</strong> '
                     f'({cm_cell(top["next24_cm"])}, {top["km_od_recice"]} km).')
    else:
        parts.append(f'Od točk do {TRIP_KM} km od Rečice model v naslednjih 24 urah ne napoveduje novega snega.')
    return " ".join(parts)


def cam_cell(r, p):
    links = []
    if p.get("arso_cam") or p.get("drsi_cam"):
        links.append('<a href="#kamere">kamera</a>')
    for c in p.get("kamere") or []:
        if str(c.get("url", "")).startswith("https://"):
            links.append(f'<a href="{_html.escape(c["url"])}" target="_blank" rel="noopener">'
                         f'{_html.escape(c["ponudnik"])}</a>')
    return ", ".join(links) or "—"


def row_html(r, p):
    meas = r.get("izmerjeno")
    meas_cell = (f'{meas["depth_cm"]} cm<br><span class="muted-note">ARSO, pred {num(meas["age_h"], 0)} h</span>'
                 if meas else "—")
    line = f'{r["snow_line_m"]} m' if r.get("snow_line_m") is not None else "—"
    return (
        f'      <tr data-c="{r["drzava"]}" data-n24="{r["past24_cm"]}" data-n72="{r["past72_cm"]}">'
        f'<th scope="row">{_html.escape(r["ime"])}<br><span class="muted-note">{COUNTRIES[r["drzava"]]} · '
        f'{_html.escape(r["regija"])} · {r["elevation_m"]} m</span></th>'
        f'<td>{num(r["temp_c"], 1)} °C</td><td>{line}</td>'
        f'<td>{cm_cell(r["past24_cm"])}</td><td>{cm_cell(r["past72_cm"])}</td>'
        f'<td>{cm_cell(r["next24_cm"])}</td><td>{cm_cell(r["next72_cm"])}</td>'
        f'<td>{meas_cell}</td><td>{cam_cell(r, p)}</td></tr>')


def embed_html(cams):
    items = []
    for p in cams.values():
        for c in p.get("kamere") or []:
            e = c.get("embed")
            if e and str(e).startswith("https://") and c.get("embed_terms") and c.get("checked"):
                items.append(
                    f'    <div class="sg-embed" data-src="{_html.escape(e)}"><button type="button">'
                    f'Naloži kamero: {_html.escape(p["ime"])} ({_html.escape(c["ponudnik"])})</button>'
                    f'<p class="muted-note">Po kliku se naloži vsebina ponudnika ({_html.escape(c["ponudnik"])}); '
                    f'ta lahko nastavi svoje piškotke.</p></div>')
    return "\n".join(items)


JS = r"""
(function(){
  var PROXY=%(proxy)s, tb=document.querySelector('#sg-table tbody'); if(!tb) return;
  var rows=[].slice.call(tb.rows), bar=document.getElementById('sg-filter');
  function apply(c,fresh){rows.forEach(function(r){var ok=(c==='*'||r.dataset.c===c)&&(!fresh||parseFloat(r.dataset.n72)>=1);r.hidden=!ok});}
  if(bar){var cur='*',fr=false;bar.hidden=false;bar.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;
    if(b.dataset.f==='fresh'){fr=!fr;b.setAttribute('aria-pressed',fr)}else{cur=b.dataset.c;[].forEach.call(bar.querySelectorAll('[data-c]'),function(x){x.setAttribute('aria-pressed',x===b)})}
    apply(cur,fr)})}
  var g=document.getElementById('sg-gen'); if(g){var h=(Date.now()-Date.parse(g.dataset.generated))/36e5;
    if(h>26){g.textContent+=' · podatki niso sveži ('+Math.round(h)+' h)';g.classList.add('sg-stale')}}
  var grid=document.getElementById('sg-cams'); if(!grid) return;
  var live=0; function done(){ if(!live) document.getElementById('kamere').hidden=true }
  function fig(src,cap,alt){var f=document.createElement('figure');var i=document.createElement('img');i.loading='lazy';i.decoding='async';
    i.width=1023;i.height=520;i.alt=alt;i.src=src;i.addEventListener('error',function(){f.remove();live--;done()},{once:true});
    var c=document.createElement('figcaption');c.textContent=cap;f.appendChild(i);f.appendChild(c);grid.appendChild(f);live++}
  (JSON.parse(grid.dataset.arso||'[]')).forEach(function(n){
    fetch(PROXY+'/arso-cam?format=json&kamera='+encodeURIComponent(n)).then(function(r){return r.ok?r.json():null}).then(function(m){
      if(!m) return; var d=m.posnet?new Date(m.posnet):null;
      var t=d&&!isNaN(d)?d.toLocaleTimeString('sl',{hour:'2-digit',minute:'2-digit'}):'';
      fig(PROXY+m.slika+(m.posnet?'&t='+encodeURIComponent(m.posnet):''),'Vir: ARSO · '+m.kamera+(t?' · posneto ob '+t:''),'Spletna kamera ARSO: '+m.kamera)
    }).catch(function(){})});
  if(grid.dataset.drsi){fig(grid.dataset.drsi+'?t='+Math.floor(Date.now()/3e5),'Vir: DRSI · prelaz Črnivec','Spletna kamera DRSI na prelazu Črnivec')}
  [].forEach.call(document.querySelectorAll('.sg-embed button'),function(b){b.addEventListener('click',function(){
    var w=b.parentNode,f=document.createElement('iframe');f.src=w.dataset.src;f.loading='lazy';f.width='100%%';f.height='360';
    f.setAttribute('referrerpolicy','no-referrer');f.setAttribute('title','Spletna kamera');w.replaceChildren(f)})});
})();
""" % {"proxy": json.dumps(PROXY)}

CSS = """
<style>
.sg-filter{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0}
.sg-filter button{min-height:44px;padding:0 .9rem;border-radius:999px;border:1px solid var(--border,#3a4a66);background:transparent;color:inherit;font:inherit;cursor:pointer}
.sg-filter button[aria-pressed="true"]{background:var(--accent,#34d399);color:#04130d;border-color:transparent}
#sg-table th[scope=row]{min-width:9rem}
.sg-stale{color:#d97706}
#sg-cams{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr));gap:.8rem}
#sg-cams figure{margin:0}#sg-cams img{width:100%;height:auto;aspect-ratio:1023/520;object-fit:cover;border-radius:8px}
#sg-cams figcaption{font-size:.8rem;opacity:.8}
.sg-embed button{min-height:44px;padding:0 1rem}
</style>
"""


def build_body(data, cams):
    rows = sorted(data["tocke"], key=lambda r: (-r["past72_cm"], -r["elevation_m"]))
    present = sorted({r["drzava"] for r in rows}, key=list(COUNTRIES).index)
    chips = ('<button type="button" data-c="*" aria-pressed="true">Vse</button>' +
             "".join(f'<button type="button" data-c="{c}" aria-pressed="false">{COUNTRIES[c]}</button>' for c in present) +
             '<button type="button" data-f="fresh" aria-pressed="false">Samo s svežim snegom</button>')
    table_rows = "\n".join(row_html(r, cams.get(r["id"], {})) for r in rows)
    arso = [p["arso_cam"] for p in cams.values() if p.get("arso_cam")]
    drsi = DRSI_CAM if any(p.get("drsi_cam") for p in cams.values()) else ""
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    embeds = embed_html(cams)
    return f'''{CSS}{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snegofili", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Snegofili: kje je zdaj sneg</h1>
  <p class="post-meta" id="sg-gen" data-generated="{data["generated_at"]}">Modelska ocena · posodobljeno {_html.escape(data["generated_at_local"])}</p>
  <p class="archive-intro">{hero_sentence(rows)}</p>
  <p class="archive-intro">Seznam zajema {len(rows)} točk od Golt do Zermatta. To je <b>modelska ocena novega snega</b>
  iz padavin in višine ničte izoterme, ne meritev. Izmerjeno višino odeje imamo samo za nekaj postaj ARSO in je
  v svojem stolpcu. Za našo dolino glej še <a href="/zima/snezna-karta/">snežno karto</a>,
  <a href="/zima/meja-snezenja/">mejo sneženja</a> in <a href="/vreme-v-gorah/">vreme v gorah</a>.</p>
  <div class="sg-filter" id="sg-filter" hidden>{chips}</div>
  <table class="stats" id="sg-table">
    <thead><tr><th scope="col">Točka</th><th scope="col">Zdaj</th><th scope="col">Meja sneženja</th>
    <th scope="col">Nazaj 24&nbsp;h</th><th scope="col">Nazaj 72&nbsp;h</th><th scope="col">Naprej 24&nbsp;h</th>
    <th scope="col">Naprej 72&nbsp;h</th><th scope="col">Izmerjeno</th><th scope="col">Kamera</th></tr></thead>
    <tbody>
{table_rows}
    </tbody>
  </table>
  <p class="muted-note">Zračna razdalja od Rečice, ne čas vožnje. Temperatura je preračunana na višino točke.
  »—« pri snegu pomeni manj kot centimeter po modelu. Podatki: Open-Meteo, postaje ARSO.</p>
  <section id="kamere" aria-labelledby="kam-h">
  <h2 id="kam-h">Kamere</h2>
  <p class="archive-intro">Slovenske kamere ARSO in DRSI so prikazane tukaj. Pri tujih točkah vas povezava v tabeli odpelje k lastniku kamere.</p>
  <div id="sg-cams" data-arso='{_html.escape(json.dumps(arso, ensure_ascii=False), quote=True)}' data-drsi="{drsi}"></div>
{embeds}
  </section>
{faq_html}
  <p class="muted-note">Ni plazovni bilten in ni nasvet za turo. Pred odhodom preverite uradni plazovni bilten
  pristojne države, <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a> in razmere pri
  oskrbovani koči ali smučišču. Slike kamer so last navedenih virov.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>
<script>{JS}</script>'''


STUB_BODY = """  <h1 class="page-title">Snegofili: kje je zdaj sneg</h1>
  <p class="archive-intro">Prvi izračun za točke po alpskem loku je v pripravi. Medtem glej
  <a href="/zima/snezna-karta/">snežno karto</a>, <a href="/zima/meja-snezenja/">mejo sneženja</a> in
  <a href="/vreme-v-gorah/">vreme v gorah</a>.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>"""


def main():
    data, cams = (None, None)
    if os.path.exists(DATA_PATH):
        data, cams = load()
    if not data or not data.get("tocke"):
        if os.path.exists(os.path.join(seo.ROOT, "snegofili", "index.html")):
            print("✗ data/snegofili.json manjka ali je prazen — obstoječa stran ostane.", file=sys.stderr)
            return 1
        # Prvi zagon brez podatkov: stran obstaja (CORE), a brez izmišljenih številk.
        seo.write_page("snegofili/index.html", seo.page_shell(TITLE, DESC, URL, "", STUB_BODY), force=True)
        print("  → snegofili/index.html (začasna stran brez podatkov)")
        return 0
    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, DESC, date_published="2026-11-13"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snegofili", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(TITLE, DESC, URL, schema, build_body(data, cams))
    seo.write_page("snegofili/index.html", page, force=True)
    print("  → snegofili/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
