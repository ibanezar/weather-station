#!/usr/bin/env python3
"""
tools/generate_snegofili_page.py — /snegofili/ (»Snegofili«: kje je sneg po alpskem loku)

Bere data/snegofili.json (piše tools/snegofili_data.py) in ročni seznam data/snegofili-tocke.json (kamere).
Stran je izrisana strežniško za »zdaj« (vidna brez JS, za pajke); snegofili/snegofili.js doda drsnik skozi čas
(−48 h … +48 h, urne serije v snegofili/ure.json), predvajanje, razvrščanje in delce.

Kar stran je in ni:
- Novi sneg je MODELSKA ocena (padavine × delež snega iz ničte izoterme, kot /vreme-v-gorah/), ne meritev.
- Izmerjena višina odeje je ločena in samo za postaje ARSO; vira se ne zlivata.
- Kamere: ARSO prek workerja /arso-cam in DRSI Črnivec (slika). Tuje kamere so povezave; vdelava (iframe,
  šele po kliku) samo, če ima vnos `embed` + `embed_terms` + `checked` (test to zahteva).
- Ni plazovni bilten in ni nasvet za turo.
- Model prikaza (step/phase/radius/barPct) je podvojen v snegofili.js; test_snegofili.py ju primerja.

Usage: python3 tools/generate_snegofili_page.py
"""
import hashlib
import html as _html
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

DATA_PATH = os.path.join(seo.ROOT, "data", "snegofili.json")
POINTS_PATH = os.path.join(seo.ROOT, "data", "snegofili-tocke.json")
OUTLINE_PATH = os.path.join(seo.ROOT, "data", "europe-outline.json")
URL = "/snegofili/"
TITLE = "Snegofili: kje je sneg, kamere in napoved"
DESC = ("Kje je zdaj sneg po alpskem loku: karta, višinski prerez z mejo sneženja, drsnik ±48 ur in kamere "
        "za 40 točk od Golt do Zermatta. Modelska ocena, izmerjeno ločeno.")
PROXY = "https://weatherireica1.filip-eremita.workers.dev"
DRSI_CAM = "https://www.drsc.si/kamere/Crnivec/Crn1_0001.jpg"
COUNTRIES = {"SI": "Slovenija", "AT": "Avstrija", "IT": "Italija", "CH": "Švica", "FR": "Francija",
             "DE": "Nemčija", "HR": "Hrvaška"}
TRIP_KM = 200
MIN_CM = 1.0

# Karta: ekvidistančna projekcija s cos φ, izrez alpskega loka.
MAP_LON = (5.6, 17.4)
MAP_LAT = (43.6, 48.9)
MAP_W = 1000
LAT0 = 46.2
MAP_K = MAP_W / ((MAP_LON[1] - MAP_LON[0]) * math.cos(math.radians(LAT0)))
MAP_H = round((MAP_LAT[1] - MAP_LAT[0]) * MAP_K)
RAMP = ["#3d73b5", "#5a97dd", "#85b9f3", "#b9d9ff", "#f4f9ff"]  # validirano (--ordinal, površina #0a1426); barve so v CSS
# Prerez: višinska os 0–4000 m
PROF_W, PROF_H, PROF_X0, PROF_X1, PROF_Y0, PROF_TOP, PROF_MAX = 800, 350, 46, 792, 250, 20, 4000
PROF_K = (PROF_Y0 - PROF_TOP) / PROF_MAX
RECICA_LAT, RECICA_LON, RECICA_ELEV = 46.3258, 14.9211, 366


# ── model prikaza (namerna podvojitev snegofili.js; primerja ga test_snegofili.py) ──
def step(cm):
    return -1 if cm < 1 else 0 if cm < 5 else 1 if cm < 15 else 2 if cm < 30 else 3 if cm < 60 else 4


def phase(elev, sl_m):
    if sl_m is None:
        return "rain"
    d = elev - sl_m
    return "snow" if d >= 100 else "mix" if d > -100 else "rain"


def radius(cm):
    return 6 if cm < 1 else min(34, 8 + 4.2 * math.sqrt(cm))


def bar_pct(cm):
    return min(100, math.sqrt(max(cm, 0)) / math.sqrt(40) * 100)


PHASE_TXT = {"snow": "Sneg", "mix": "Moker sneg", "rain": "Dež ali suho"}

FAQ = [
    ("Je to izmerjen sneg?",
     "Ne. Novi sneg je modelska ocena: padavine iz celice vremenskega modela (Open-Meteo), pomnožene z deležem, "
     "ki pade kot sneg glede na višino ničte izoterme. Celica ne razloči pobočij in dolin, zato je lahko na terenu "
     "več ali manj. Izmerjeno višino snežne odeje imamo samo za nekaj postaj ARSO in je v svojem polju."),
    ("Kaj kažeta karta in prerez?",
     "Krog na karti je velik toliko, kolikor snega po modelu pade v 24 urah do izbrane ure. Poln krog pomeni, da je "
     "točka nad mejo sneženja, črtkan rob mokri sneg, prazen krog pa, da novega snega ni ali da dežuje. "
     "Prerez prikazuje višino vsake točke; modri del stolpca je nad mejo sneženja. Točke so razvrščene od zahoda "
     "proti vzhodu, stolpci niso profil gorovja."),
    ("Kaj pomenita »nazaj« in »naprej«?",
     "Nazaj je ocena novega snega v 24 urah do izbrane ure, naprej pa tisto, kar model napoveduje v naslednjih 24 "
     "urah. Drsnik seže 48 ur nazaj in naprej od zadnjega izračuna. Ura, ki teče, se ne šteje naprej."),
    ("Zakaj je polje »izmerjeno« večinoma prazno?",
     "Višino snežne odeje objavljajo le nekatere postaje ARSO (npr. Krvavec, Rogla, Uršlja gora). Tuje točke "
     "nimajo izmerjene vrednosti na tej strani. Prazno polje pomeni, da meritve nimamo, ne da snega ni."),
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


def ver(rel):
    with open(os.path.join(seo.ROOT, rel), "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def load():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    with open(POINTS_PATH, encoding="utf-8") as f:
        cams = {p["id"]: p for p in json.load(f)["tocke"]}
    return data, cams


# ── geometrija ──
def proj(lon, lat):
    return ((lon - MAP_LON[0]) * math.cos(math.radians(LAT0)) * MAP_K, (MAP_LAT[1] - lat) * MAP_K)


_zx0, _zy0 = proj(11.6, 47.4)
_zx1, _zy1 = proj(17.4, 45.0)
ZOOM_VB = f"{_zx0:.0f} {_zy0:.0f} {_zx1 - _zx0:.0f} {_zy1 - _zy0:.0f}"


def _inside(lon, lat, m=1.2):
    return MAP_LON[0] - m <= lon <= MAP_LON[1] + m and MAP_LAT[0] - m <= lat <= MAP_LAT[1] + m


def outline_paths():
    """Obala in meje v koordinatah karte; zunaj izreza se črte prekinejo (SVG viewBox odreže ostalo)."""
    try:
        with open(OUTLINE_PATH, encoding="utf-8") as f:
            o = json.load(f)
    except OSError:
        return "", ""

    def path(lines):
        out = []
        for line in lines:
            seg, last = [], None
            for pt in list(line) + [None]:
                if pt is not None and _inside(pt[0], pt[1]):
                    x, y = proj(pt[0], pt[1])
                    if last is None or abs(x - last[0]) + abs(y - last[1]) >= 1.2:
                        seg.append((x, y))
                        last = (x, y)
                    continue
                if len(seg) > 1:
                    out.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in seg))
                seg, last = [], None
        return "".join(out)
    return path(o.get("coast", [])), path(o.get("borders", []))


def short(name):
    n = name.split("(")[0].strip()
    return n if len(n) <= 15 else n[:14] + "…"


# ── karta ──
def map_svg(rows):
    coast, bord = outline_paths()
    rx, ry = proj(RECICA_LON, RECICA_LAT)
    # Imena samo pri največjih točkah in brez prekrivanja (požrešno: bližnja manjša točka ostane brez imena).
    label_ids, placed = set(), [proj(RECICA_LON, RECICA_LAT)]
    for r in sorted(rows, key=lambda r: -max(r["past24_cm"], r["next24_cm"]))[:12]:
        if max(r["past24_cm"], r["next24_cm"]) < 5:
            continue
        x, y = proj(r["lon"], r["lat"])
        if all(abs(x - px) > 150 or abs(y - py) > 30 for px, py in placed):
            placed.append((x, y))
            label_ids.add(r["id"])
    circles, labels = [], []
    for r in sorted(rows, key=lambda r: -r["past24_cm"]):  # večji spodaj, manjši na vrhu
        x, y = proj(r["lon"], r["lat"])
        ph = phase(r["elevation_m"], r["snow_line_m"])
        show = step(r["past24_cm"]) >= 0 and ph != "rain"
        cls = (f"s{step(r['past24_cm'])} " if show else "ring ") + f"ph-{ph}"
        aria = (f'{r["ime"]}, {r["elevation_m"]} m: {PHASE_TXT[ph]}, nazaj 24 h {cm_cell(r["past24_cm"])}, '
                f'naprej 24 h {cm_cell(r["next24_cm"])}')
        rad = radius(r["past24_cm"] if show else 0)
        circles.append(f'<circle class="sg-c {cls}" data-id="{r["id"]}" cx="{x:.1f}" cy="{y:.1f}" '
                       f'r="{rad:.1f}" tabindex="0" role="button" aria-label="{_html.escape(aria)}"/>')
        if r["id"] in label_ids:
            labels.append(f'<text class="sg-lbl" x="{x + 10 + rad:.1f}" y="{y + 7:.1f}">'
                          f'{_html.escape(short(r["ime"]))}</text>')
    return (
        f'<div class="sg-mapwrap"><svg id="sg-map" data-w="{MAP_W}" data-h="{MAP_H}" viewBox="0 0 {MAP_W} {MAP_H}" '
        f'role="group" aria-label="Karta alpskega loka: novi sneg v zadnjih 24 urah po točkah">'
        f'<path class="land" d="M0 0H{MAP_W}V{MAP_H}H0Z"/><path class="bord" d="{bord}"/><path class="coast" d="{coast}"/>'
        f'<path d="M{rx:.1f} {ry - 9:.1f}l8 9l-8 9l-8 -9z" fill="#fff" stroke="#0a1426" stroke-width="2"/>'
        f'<text class="sg-lbl" x="{rx + 14:.1f}" y="{ry + 7:.1f}">Rečica</text>'
        f'{"".join(circles)}{"".join(labels)}</svg><div id="sg-tip" hidden></div></div>')


def legend_html():
    ramp = "".join(f'<i style="background:{c}"></i>' for c in RAMP)
    return (f'<div class="sg-legend" aria-label="Legenda">'
            f'<span>Nov sneg v 24 h: 1 <span class="sg-ramp">{ramp}</span> 60+ cm</span>'
            f'<span><i style="background:#85b9f3;outline:2px dashed #f4f9ff;outline-offset:-3px"></i>mokri sneg</span>'
            f'<span><i style="border:2px solid #7d8da8"></i>brez novega snega ali dež</span>'
            f'<span><i style="background:#fff;border-radius:2px;transform:rotate(45deg) scale(.7)"></i>Rečica</span></div>')


# ── prerez ──
def profile_svg(rows):
    srt = sorted(rows, key=lambda r: r["lon"])
    n = len(srt)
    slot = (PROF_X1 - PROF_X0) / n
    out = [f'<svg id="sg-prof" viewBox="0 0 {PROF_W} {PROF_H}" role="img" '
           f'aria-label="Višinski prerez: višine točk od zahoda proti vzhodu, modri del stolpca je nad mejo sneženja">']
    for v in range(0, PROF_MAX + 1, 1000):
        y = PROF_Y0 - v * PROF_K
        out.append(f'<line class="gr" x1="{PROF_X0}" x2="{PROF_X1}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text class="ax" x="{PROF_X0 - 6}" y="{y + 4:.1f}" text-anchor="end">{v} m</text>')
    ry = PROF_Y0 - RECICA_ELEV * PROF_K
    out.append(f'<line class="ref" x1="{PROF_X0}" x2="{PROF_X1}" y1="{ry:.1f}" y2="{ry:.1f}"/>'
               f'<text class="ax" x="{PROF_X1}" y="{ry - 4:.1f}" text-anchor="end">Rečica {RECICA_ELEV} m</text>')
    bxs = {}
    for i, r in enumerate(srt):
        bx = PROF_X0 + slot * (i + 0.5)
        bxs[r["id"]] = round(bx, 1)
        e = min(r["elevation_m"], PROF_MAX)
        top = PROF_Y0 - e * PROF_K
        sl = r["snow_line_m"]
        sy = max(0, min(sl, e)) if sl is not None else e
        snow_h = (e - sy) * PROF_K if sl is not None and r["elevation_m"] > sl else 0
        out.append(f'<rect class="bar" x="{bx - 6:.1f}" y="{top:.1f}" width="12" height="{e * PROF_K:.1f}" rx="2"/>'
                   f'<rect class="sg-snow" data-id="{r["id"]}" data-y0="{PROF_Y0}" data-k="{PROF_K}" '
                   f'x="{bx - 6:.1f}" y="{top:.1f}" width="12" height="{snow_h:.1f}" rx="2" '
                   f'style="opacity:{1 if snow_h > 0 else 0}"><title>{_html.escape(r["ime"])}, {r["elevation_m"]} m</title></rect>'
                   f'<text class="vt" transform="rotate(90 {bx:.1f} {PROF_Y0 + 8})" x="{bx:.1f}" y="{PROF_Y0 + 12}">'
                   f'{_html.escape(short(r["ime"]))}</text>')
        if sl is not None:
            ly = PROF_Y0 - max(0, min(sl, PROF_MAX)) * PROF_K
            out.append(f'<rect class="sg-sl" data-id="{r["id"]}" data-y0="{PROF_Y0}" data-k="{PROF_K}" '
                       f'x="{bx - 9:.1f}" y="{ly - 1.25:.1f}" width="18" height="2.5" rx="1"/>')
    out.append(f'<text class="ax" x="{PROF_X0 + 2}" y="{PROF_TOP - 6}">bela črtica: meja sneženja pri točki</text></svg>')
    return "".join(out), bxs


# ── kartice ──
def cam_links(p):
    links = []
    if p.get("arso_cam") or p.get("drsi_cam"):
        links.append('<a href="#kamere">kamera</a>')
    for c in p.get("kamere") or []:
        if str(c.get("url", "")).startswith("https://"):
            links.append(f'<a href="{_html.escape(c["url"])}" target="_blank" rel="noopener">'
                         f'{_html.escape(c["ponudnik"])}</a>')
    return ", ".join(links) or "—"


def card_html(r, p):
    ph = phase(r["elevation_m"], r["snow_line_m"])
    sl = r["snow_line_m"]
    d = None if sl is None else r["elevation_m"] - sl
    sl_txt = "—" if d is None else (f"nad mejo +{abs(round(d, -1)):.0f}" if d >= 0 else f"pod mejo −{abs(round(d, -1)):.0f}") + " m"
    meas = r.get("izmerjeno")
    meas_txt = f'{meas["depth_cm"]} cm (ARSO, pred {num(meas["age_h"], 0)} h)' if meas else "—"
    aria = f'{r["ime"]}: {PHASE_TXT[ph]}, nazaj 24 h {cm_cell(r["past24_cm"])}, naprej 24 h {cm_cell(r["next24_cm"])}'
    return (
        f'    <article class="sg-card" id="t-{r["id"]}" data-c="{r["drzava"]}" data-past="{r["past24_cm"]}" '
        f'data-next="{r["next24_cm"]}" data-fresh="{max(r["past24_cm"], r["next24_cm"])}" '
        f'data-elev="{r["elevation_m"]}" data-km="{r["km_od_recice"]}" aria-label="{_html.escape(aria)}">'
        f'<div class="sg-head"><div><h3>{_html.escape(r["ime"])}</h3><p class="sg-sub">{COUNTRIES[r["drzava"]]} · '
        f'{_html.escape(r["regija"])} · {r["elevation_m"]} m · {r["km_od_recice"]} km</p></div>'
        f'<span class="sg-pill ph-{ph}">{PHASE_TXT[ph]}</span></div>'
        f'<div class="sg-div" role="img" aria-label="{_html.escape(aria)}"><div class="sg-half l">'
        f'<div class="sg-bl" style="width:{bar_pct(r["past24_cm"]) / 2:.1f}%"></div></div><div class="sg-half">'
        f'<div class="sg-br" style="width:{bar_pct(r["next24_cm"]) / 2:.1f}%"></div></div></div>'
        f'<div class="sg-nums"><span><b class="sg-np">{cm_cell(r["past24_cm"])}</b><small>nazaj 24 h</small></span>'
        f'<span class="r"><b class="sg-nn">{cm_cell(r["next24_cm"])}</b><small>naprej 24 h</small></span></div>'
        f'<dl class="sg-dl"><div><dt>Zdaj</dt><dd class="sg-tt">{num(r["temp_c"], 1)} °C</dd></div>'
        f'<div style="grid-column:span 2"><dt>Meja sneženja</dt><dd class="sg-sl">{sl_txt}</dd></div></dl>'
        f'<div class="sg-foot"><span>72 h: {cm_cell(r["past72_cm"])} nazaj · {cm_cell(r["next72_cm"])} naprej</span>'
        f'<span>{cam_links(p)}</span></div>'
        f'<div class="sg-foot"><span>Izmerjeno: {meas_txt}</span></div></article>')


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


CAM_JS = r"""
(function(){
  var PROXY=%(proxy)s, g=document.getElementById('sg-gen');
  if(g){var h=(Date.now()-Date.parse(g.dataset.generated))/36e5;
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


def build_body(data, cams):
    rows = sorted(data["tocke"], key=lambda r: (-r["past72_cm"], -r["elevation_m"]))
    present = sorted({r["drzava"] for r in rows}, key=list(COUNTRIES).index)
    prof, bx = profile_svg(rows)
    pts_json = json.dumps([{"id": r["id"], "n": r["ime"], "e": r["elevation_m"],
                            "x": round(proj(r["lon"], r["lat"])[0], 1), "y": round(proj(r["lon"], r["lat"])[1], 1),
                            "bx": bx[r["id"]]} for r in rows], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    chips = ('<button type="button" data-c="*" aria-pressed="true">Vse</button>' +
             "".join(f'<button type="button" data-c="{c}" aria-pressed="false">{COUNTRIES[c]}</button>' for c in present) +
             '<button type="button" data-f="fresh" aria-pressed="false">Samo s svežim snegom</button>'
             '<span class="sep"></span>'
             '<button type="button" data-s="past" aria-pressed="true">Nazaj 24 h</button>'
             '<button type="button" data-s="next" aria-pressed="false">Naprej 24 h</button>'
             '<button type="button" data-s="elev" aria-pressed="false">Višina</button>'
             '<button type="button" data-s="km" aria-pressed="false">Razdalja</button>')
    cards_html = "\n".join(card_html(r, cams.get(r["id"], {})) for r in rows)
    arso = [p["arso_cam"] for p in cams.values() if p.get("arso_cam")]
    drsi = DRSI_CAM if any(p.get("drsi_cam") for p in cams.values()) else ""
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    embeds = embed_html(cams)
    return f'''{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snegofili", None)])}
{seo.stn_badge()}
  <section class="sg-hero" aria-labelledby="sg-h1">
    <canvas id="sg-snow" aria-hidden="true"></canvas>
    <div class="sg-brand"><img src="/snegofili/brand/mark.svg" width="44" height="44" alt="" decoding="async">
    <p class="sg-kicker">Alpski lok · {len(rows)} točk</p></div>
    <h1 class="page-title" id="sg-h1">Snegofili: kje je zdaj sneg</h1>
    <p class="sg-meta" id="sg-gen" data-generated="{data["generated_at"]}">Modelska ocena · posodobljeno {_html.escape(data["generated_at_local"])}</p>
    <p class="sg-lead">{hero_sentence(rows)}</p>
{map_svg(rows)}
    <div class="sg-zoom" id="sg-zoom" hidden><button type="button" aria-pressed="false" data-view="{ZOOM_VB}">Približaj: Slovenija in sosedje</button></div>
{legend_html()}
    <div class="sg-ctlwrap">
      <div id="sg-ctl" hidden><button type="button" id="sg-play" aria-pressed="false">Predvajaj</button>
      <input type="range" id="sg-range" aria-label="Čas od −48 do +48 ur"><button type="button" id="sg-now">Zdaj</button>
      <span id="sg-time" aria-live="polite">zdaj</span></div>
      <p class="sg-readout" id="sg-readout"></p>
    </div>
    <div class="sg-profwrap">
      <h2>Višinski prerez Alp</h2>
      <p>Višine točk od zahoda proti vzhodu. Modri del stolpca je nad mejo sneženja, bela črtica je meja sneženja pri točki ob izbrani uri; kjer lebdi nad stolpcem, je meja višje od točke.</p>
      <div class="sg-scroll">{prof}</div>
      <p class="sg-hint">Povlecite vodoravno za ostale točke.</p>
    </div>
  </section>
  <p class="archive-intro">Seznam zajema {len(rows)} točk od Golt do Zermatta. To je <b>modelska ocena novega snega</b>
  iz padavin in višine ničte izoterme, ne meritev. Izmerjeno višino odeje imamo samo za nekaj postaj ARSO in je
  v svojem polju. Za našo dolino glej še <a href="/zima/snezna-karta/">snežno karto</a>,
  <a href="/zima/meja-snezenja/">mejo sneženja</a> in <a href="/vreme-v-gorah/">vreme v gorah</a>.</p>
  <div class="sg-filter" id="sg-filter" hidden>{chips}</div>
  <div id="sg-cards">
{cards_html}
  </div>
  <p class="muted-note">Zračna razdalja od Rečice, ne čas vožnje. Temperatura je preračunana na višino točke.
  »—« pri snegu pomeni manj kot centimeter po modelu. Podatki: Open-Meteo, postaje ARSO.</p>
  <section id="kamere" aria-labelledby="kam-h">
  <h2 id="kam-h">Kamere</h2>
  <p class="archive-intro">Slovenske kamere ARSO in DRSI so prikazane tukaj. Pri tujih točkah vas povezava na kartici odpelje k lastniku kamere.</p>
  <div id="sg-cams" data-arso='{_html.escape(json.dumps(arso, ensure_ascii=False), quote=True)}' data-drsi="{drsi}"></div>
{embeds}
  </section>
{faq_html}
  <p class="muted-note">Ni plazovni bilten in ni nasvet za turo. Pred odhodom preverite uradni plazovni bilten
  pristojne države, <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a> in razmere pri
  oskrbovani koči ali smučišču. Slike kamer so last navedenih virov.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>
<script type="application/json" id="sg-pts">{pts_json}</script>
<script>{CAM_JS}</script>'''


def head_extras(schema):
    return ('<link rel="icon" type="image/svg+xml" href="/snegofili/brand/favicon.svg">\n'
            '<link rel="apple-touch-icon" href="/snegofili/brand/apple-touch-icon.png">\n'
            f'<link rel="stylesheet" href="/snegofili/snegofili.css?v={ver("snegofili/snegofili.css")}">\n'
            f'<script defer src="/snegofili/snegofili.js?v={ver("snegofili/snegofili.js")}"></script>\n{schema}')


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
        seo.write_page("snegofili/index.html", seo.page_shell(TITLE, DESC, URL, "", STUB_BODY), force=True)
        print("  → snegofili/index.html (začasna stran brez podatkov)")
        return 0
    schema = "\n".join([
        seo.webpage_schema(URL, TITLE, DESC, date_published="2026-11-13"),
        seo.crumbs_schema([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snegofili", None)]),
        seo.faq_schema(FAQ),
    ])
    page = seo.page_shell(TITLE, DESC, URL, head_extras(schema), build_body(data, cams),
                          og_image=f"{seo.SITE}/snegofili/brand/og.png")
    seo.write_page("snegofili/index.html", page, force=True)
    print("  → snegofili/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
