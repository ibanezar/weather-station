#!/usr/bin/env python3
"""
tools/generate_snegofili_page.py — /snegofili/ (»Snegofili«: kje je sneg po alpskem loku)

Bere data/snegofili.json (piše tools/snegofili_data.py) in ročni seznam data/snegofili-tocke.json (kamere).
Stran je izrisana strežniško za »zdaj« (vidna brez JS, za pajke); snegofili/snegofili.js doda drsnik skozi čas
(−48 h … +48 h, urne serije v snegofili/ure.json), predvajanje, razvrščanje in delce.

Kar stran je in ni:
- Novi sneg je MODELSKA ocena (padavine × delež snega iz ničte izoterme, kot /vreme-v-gorah/), ne meritev.
- Izmerjena višina odeje je ločena in samo za postaje ARSO; vira se ne zlivata.
- Kamere: ARSO prek workerja /arso-cam in DRSI Črnivec (slika, osvežitev na 5 min, lightbox). Tuje kamere so
  povezave; vdelava (iframe, šele po kliku) samo, če ima vnos `embed` + `embed_terms` + `checked` (test to zahteva).
- Pas »Kjer zdaj sneži«, podrobnost točke (grafi 96 ur), toplotna karta, »Kam peljem?«, priljubljene točke so JS
  (podatki v snegofili/ure.json); brez JS ostanejo karta, prerez, kartice in kamere.
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
DESC = ("Kje zdaj sneži po alpskem loku: karta, kamere, toplotna karta 96 ur, podrobnost vsake točke in izbirnik "
        "»kam peljem po sneg« za 40 točk od Golt do Zermatta. Modelska ocena, izmerjeno ločeno.")
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
     "Slovenske kamere ARSO in DRSI na prelazu Črnivec so prikazane neposredno z navedbo vira; sličica se osveži "
     "vsakih nekaj minut, klik jo odpre večjo. To so sličice, ne video v živo. Pri tujih kamerah vas povezava odpelje "
     "k lastniku kamere (smučišče, turistična organizacija). Vdelamo jih samo, kadar ponudnik vdelavo uradno dovoljuje."),
    ("Kaj pomeni »Kjer zdaj sneži«?",
     "Pas pokaže točke, kjer model za izbrano uro napoveduje vsaj 0,1 cm novega snega na uro. To je modelska ocena "
     "iz padavin in meje sneženja, ne opazovanje: kamera ob njej kaže, kar je tam v resnici, in se z oceno lahko "
     "razlikuje. Ko premaknete drsnik, se pas prilagodi izbrani uri."),
    ("Kako deluje »Kam peljem po sneg?«",
     "Izbirnik razvrsti točke po modelski količini novega snega v izbranem oknu (naslednjih 24 ur, 24–48 ur ali "
     "zadnjih 24 ur), po zračni razdalji od Rečice in po višini. Ni priporočilo za turo: ne upošteva ceste, "
     "plazov, odprtosti smučišč ali vremena po poti."),
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
    embeds = [c for c in p.get("kamere") or [] if valid_embed(c)]
    if p.get("arso_cam") or p.get("drsi_cam") or embeds:
        links.append('<a href="#kamere">kamera</a>')
    for c in p.get("kamere") or []:
        if valid_embed(c):
            continue  # vdelana kamera je že pod »kamera« (lightbox)
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
        f'<div class="sg-spark" aria-hidden="true"></div>'
        f'<dl class="sg-dl"><div><dt>Zdaj</dt><dd class="sg-tt">{num(r["temp_c"], 1)} °C</dd></div>'
        f'<div style="grid-column:span 2"><dt>Meja sneženja</dt><dd class="sg-sl">{sl_txt}</dd></div></dl>'
        f'<div class="sg-foot"><span>72 h: {cm_cell(r["past72_cm"])} nazaj · {cm_cell(r["next72_cm"])} naprej</span>'
        f'<span>{cam_links(p)}</span></div>'
        f'{cam_slot(r["ime"], p)}'
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


# Vdelava samo pri ponudnikih z uradno možnostjo vdelave in samo na teh gostiteljih. WhatsUpCams (S3MEA) namenoma ni
# na seznamu: pogoji prepovedujejo framing in javni prikaz brez pisnega dovoljenja. Ob pisnem dovoljenju ga dodaj
# SKUPAJ z `embed_terms` (povezava ali datum potrdila) in `checked`.
EMBED_HOSTS = {"windy": ("webcams.windy.com", "embed.windy.com"), "youtube": ("www.youtube-nocookie.com",)}
WINDY_CREDIT = ('Webcams provided by <a href="https://www.windy.com/" target="_blank" rel="noopener">windy.com</a> — '
                '<a href="https://www.windy.com/webcams/add" target="_blank" rel="noopener">add a webcam</a>')


def valid_embed(c):
    """(kind, src) če je vdelava dovoljena, sicer None: znan ponudnik, https na dovoljenem gostitelju, pogoji in datum preverjanja."""
    from urllib.parse import urlparse
    kind, src = c.get("embed_kind"), str(c.get("embed") or "")
    if kind not in EMBED_HOSTS or not c.get("embed_terms") or not c.get("checked"):
        return None
    u = urlparse(src)
    if u.scheme != "https" or u.hostname not in EMBED_HOSTS[kind]:
        return None
    return kind, src


def cam_slot(r_name, p):
    """Gumb »Kamera v živo« na kartici točke (iframe se naloži šele po kliku); prazno, če ni dovoljene vdelave."""
    for c in p.get("kamere") or []:
        ok = valid_embed(c)
        if ok:
            kind, src = ok
            credit = f'<p class="sg-attr">{WINDY_CREDIT}</p>' if kind == "windy" else ""
            prov = _html.escape(c.get("ponudnik", kind))
            return (f'<div class="sg-camslot" data-src="{_html.escape(src)}" data-kind="{kind}" '
                    f'data-title="Spletna kamera: {_html.escape(r_name)}">'
                    f'<button type="button" class="sg-live">Kamera v živo</button>'
                    f'<p class="sg-attr">Po kliku se naloži vsebina ponudnika ({prov}), ki lahko nastavi svoje piškotke.</p>{credit}</div>')
    return ""


ALARM_CM = (5, 15, 30)   # ↔ SG_CM_ALLOWED v worker.js (tools/test_snegofili_alarm.mjs): meje stopenj snega v step()
ALARM_MAX_RULES = 3      # ↔ SG_MAX_RULES v worker.js


def alarm_html(rows):
    """Opozorilo na telefon: pravila {točka, prag} do ALARM_MAX_RULES; snegofili.js ga pokaže samo, če brskalnik zna push."""
    opts = "".join(f'<option value="{_html.escape(r["id"])}">{_html.escape(r["ime"])} ({COUNTRIES.get(r["drzava"], r["drzava"])}, {r["elevation_m"]} m)</option>'
                   for r in sorted(rows, key=lambda r: (list(COUNTRIES).index(r["drzava"]), r["ime"])))
    cms = "".join(f'<option value="{c}">{c} cm</option>' for c in ALARM_CM)
    return f'''  <section class="sg-alarm" id="sg-alarm" data-max="{ALARM_MAX_RULES}" aria-labelledby="sg-al-h" hidden>
    <h2 id="sg-al-h">Opozorilo na telefon</h2>
    <p>Obvestilo, ko model za izbrano točko napove vsaj toliko novega snega v naslednjih 24 urah. Do {ALARM_MAX_RULES} pravila; obvestila ne pošiljamo ponoči (22.00–7.00).</p>
    <div class="sg-al-row">
      <label>Točka<select id="sg-al-pt">{opts}</select></label>
      <label>Vsaj<select id="sg-al-cm">{cms}</select></label>
      <button type="button" class="sg-al-btn s" id="sg-al-add">Dodaj pravilo</button>
    </div>
    <ul class="sg-al-list" id="sg-al-list" aria-label="Vaša pravila"></ul>
    <div class="sg-al-row"><button type="button" class="sg-al-btn" id="sg-al-on">Vklopi opozorilo</button> <button type="button" class="sg-al-btn s" id="sg-al-off" hidden>Izklopi</button></div>
    <p class="muted-note" id="sg-al-ios" hidden>Na iPhonu obvestila delujejo samo v aplikaciji, dodani na začetni zaslon (Deli, nato Dodaj na začetni zaslon).</p>
    <p class="muted-note" id="sg-al-msg" aria-live="polite"></p>
    <p class="muted-note">Modelska ocena novega snega iz padavin in meje sneženja, ne meritev; ni plazovni bilten in ni nasvet za turo. Strežnik shrani samo naslovnico naročnine in vaša pravila; izklop jih izbriše.</p>
  </section>'''


def cam_info(p):
    """Kamere točke za JS: ca = ime kamere ARSO, cd = DRSI, ce = seznam dovoljenih vdelav {k, s, p, t, u}, cl = povezave (https)."""
    c = {}
    if p.get("arso_cam"):
        c["ca"] = p["arso_cam"]
    if p.get("drsi_cam"):
        c["cd"] = 1
    ce, links = [], []
    for cam in p.get("kamere") or []:
        ok = valid_embed(cam)
        if ok:
            e = {"k": ok[0], "s": ok[1], "p": cam.get("ponudnik", ok[0]), "t": cam.get("naslov", "")}
            if str(cam.get("url", "")).startswith("https://"):
                e["u"] = cam["url"]
            ce.append(e)
        elif str(cam.get("url", "")).startswith("https://"):
            links.append({"u": cam["url"], "p": cam.get("ponudnik", "")})
    if ce:
        c["ce"] = ce
    if links:
        c["cl"] = links
    return c


def cam_wall_html(rows, cams):
    """Kamerni zid: ploščice so v HTML (rezerviran prostor), slike nalaga JS. Točke samo s tujo povezavo so v seznamu."""
    tiles, links = [], []
    for r in sorted(rows, key=lambda r: -r["elevation_m"]):
        info = cam_info(cams.get(r["id"], {}))
        kind = "arso" if info.get("ca") else "drsi" if info.get("cd") else "embed" if info.get("ce") else None
        if kind:
            src = {"arso": "ARSO", "drsi": "DRSI", "embed": _html.escape(", ".join(sorted({e["p"] for e in info.get("ce", [])})))}[kind]
            if kind != "embed" and info.get("ce"):
                src += " + Windy (časovni zdrs)"
            ime = _html.escape(r["ime"])
            tiles.append(
                f'    <figure class="sg-cam" data-id="{r["id"]}" data-kind="{kind}">'
                f'<button type="button" class="sg-cam-b" aria-label="Poglej kamero: {ime}">'
                f'<span class="sg-cam-img"><span class="sg-cam-msg">Nalagam sličico …</span></span>'
                f'<span class="sg-cam-st"></span></button>'
                f'<figcaption><b>{ime}</b> · {r["elevation_m"]} m · {COUNTRIES[r["drzava"]]} <span class="sg-cam-t"></span>'
                f'<small>Vir: {src}</small></figcaption></figure>')
        elif info.get("cl"):
            for c in info["cl"]:
                links.append(f'<li><a href="{_html.escape(c["u"])}" target="_blank" rel="noopener">{_html.escape(r["ime"])}</a> '
                             f'<small>({_html.escape(c["p"])}, {COUNTRIES[r["drzava"]]})</small></li>')
    if not tiles and not links:
        return ""
    wall = ""
    if tiles:
        wall = (f'  <div id="sg-cams" class="sg-camwall" data-proxy="{PROXY}" data-drsi="{DRSI_CAM}">\n' +
                "\n".join(tiles) + "\n  </div>\n")
    ln = ""
    if links:
        ln = ('  <h3 class="sg-h3">Kamere pri ponudnikih</h3>\n'
              '  <p class="muted-note">Povezava odpre stran lastnika kamere; slike tu ne prikazujemo.</p>\n'
              f'  <ul class="sg-camlinks">{"".join(links)}</ul>\n')
    return (f'  <section id="kamere" class="sg-sec" aria-labelledby="kam-h">\n  <h2 id="kam-h">Kamere</h2>\n'
            '  <p class="archive-intro">Sličice slovenskih kamer ARSO in DRSI se osvežujejo vsakih nekaj minut; klik jo odpre večjo, '
            'ob njej pa piše, kaj za tisto točko napoveduje model. Pri točkah z oznako Windy lahko po kliku predvajate časovni zdrs '
            'zadnjega dne (vsebina ponudnika Windy). <b>To niso videoposnetki v živo.</b> '
            'Kamera in model se lahko razhajata: verjemite sliki.</p>\n' + wall + ln + '  </section>\n')


def stats_html(rows):
    b24 = max(rows, key=lambda r: r["past24_cm"])
    bn = max(rows, key=lambda r: r["next24_cm"])
    fresh = sum(1 for r in rows if r["past24_cm"] >= MIN_CM)

    def tile(i, lab, val, sub):
        return (f'<div class="sg-stat"><small>{lab}</small><b id="sg-st-{i}">{val}</b>'
                f'<span id="sg-st-{i}-n">{sub}</span></div>')
    return ('  <div class="sg-stats" id="sg-stats" role="group" aria-label="Povzetek po modelu">'
            + tile("now", "Zdaj sneži", "—", f"od {len(rows)} točk")
            + tile("past", "Največ nazaj 24 h", cm_cell(b24["past24_cm"]), _html.escape(b24["ime"]))
            + tile("next", "Največ naprej 24 h", cm_cell(bn["next24_cm"]), _html.escape(bn["ime"]))
            + tile("fresh", "Točk s svežim snegom", str(fresh), "≥ 1 cm v 24 h nazaj")
            + '</div>\n')


def measured_html(rows):
    meas = [r for r in rows if r.get("izmerjeno")]
    if not meas:
        return ""
    top = max(40, max(r["izmerjeno"]["depth_cm"] for r in meas))
    li = "".join(
        f'<li><span class="sg-ms-n">{_html.escape(r["ime"])} <small>{r["elevation_m"]} m</small></span>'
        f'<span class="sg-ms-bar" role="img" aria-label="Izmerjeno {r["izmerjeno"]["depth_cm"]} cm"><i style="width:{min(100, r["izmerjeno"]["depth_cm"] / top * 100):.1f}%"></i></span>'
        f'<span class="sg-ms-v"><b>{r["izmerjeno"]["depth_cm"]} cm</b> <small>pred {num(r["izmerjeno"]["age_h"], 0)} h</small></span>'
        f'<span class="sg-ms-m"><small>model: nov sneg 72 h nazaj</small> {cm_cell(r["past72_cm"])}</span></li>'
        for r in sorted(meas, key=lambda r: -r["izmerjeno"]["depth_cm"]))
    return ('  <section id="izmerjeno" class="sg-sec" aria-labelledby="izm-h">\n  <h2 id="izm-h">Izmerjena snežna odeja</h2>\n'
            '  <p class="archive-intro">To je <b>meritev</b> višine snežne odeje na postajah ARSO, ločena od modelske ocene novega snega: '
            'odeja je ostanek preteklih dni, novi sneg pa tisto, kar je zapadlo v zadnjih urah. Vir: Agencija Republike Slovenije za okolje (ARSO).</p>\n'
            f'  <ul class="sg-ms">{li}</ul>\n  </section>\n')


# Karta Windy (embed.windy.com, brez ključa API). Osnovni URL je vzorec, ki ga generira https://embed.windy.com/config/map;
# »overlay« je začetna plast, drugo izbere obiskovalec v meniju karte. Iframe se naloži šele po kliku.
WINDY_MAP = ("https://embed.windy.com/embed2.html?lat=46.4&lon=12.0&detailLat=46.33&detailLon=14.92&width=650&height=450"
             "&zoom=6&level=surface&overlay={overlay}&product=ecmwf&menu=&message=true&marker=true&calendar=now&pressure="
             "&type=map&location=coordinates&detail=&metricWind=km%2Fh&metricTemp=%C2%B0C&radarRange=-1")
WINDY_OVERLAYS = (("snowAccu", "Nov sneg"), ("wind", "Veter"), ("temp", "Temperatura"), ("clouds", "Oblaki"))


def windy_map_html():
    btns = "".join(f'<button type="button" data-ov="{o}" aria-pressed="{"true" if i == 0 else "false"}">{t}</button>'
                   for i, (o, t) in enumerate(WINDY_OVERLAYS))
    return f"""  <section id="windy" class="sg-sec" aria-labelledby="wy-h">
  <h2 id="wy-h">Sneg in veter na zemljevidu Windy</h2>
  <p class="archive-intro">Zunanja interaktivna karta Windy (model ECMWF) za pregled gibanja padavin in vetra. To je vsebina ponudnika, ne naša ocena: številke se lahko razlikujejo od tistih zgoraj.</p>
  <div class="sg-heatbar" role="group" aria-label="Začetna plast karte Windy">{btns}</div>
  <div class="sg-wy" id="sg-wy" data-base="{_html.escape(WINDY_MAP)}"><button type="button" class="sg-live">Naloži karto Windy</button>
  <p class="sg-attr">Po kliku se naloži vsebina ponudnika (Windy), ki lahko nastavi svoje piškotke. Map by <a href="https://www.windy.com/" target="_blank" rel="noopener">windy.com</a>.</p></div>
  </section>
"""


def plan_html():
    km = "".join(f'<option value="{k}"{" selected" if k == TRIP_KM else ""}>{"do " + str(k) + " km" if k else "vse"}</option>'
                 for k in (100, TRIP_KM, 400, 0))
    return f"""  <section id="kam-peljem" class="sg-sec sg-plan" aria-labelledby="kp-h" hidden>
  <h2 id="kp-h">Kam peljem po sneg?</h2>
  <p class="archive-intro">Izberite okno, razdaljo in višino: pokažemo tri točke z največ novega snega po modelu.</p>
  <div class="sg-plan-row">
    <label>Kdaj<select id="sg-pl-win"><option value="n24">Naslednjih 24 h</option><option value="n48">24–48 h od zdaj</option><option value="p24">Zadnjih 24 h</option></select></label>
    <label>Razdalja od Rečice<select id="sg-pl-km">{km}</select></label>
    <label>Višina točke<select id="sg-pl-el"><option value="0">vse</option><option value="1000">nad 1000 m</option><option value="1500">nad 1500 m</option><option value="2000">nad 2000 m</option></select></label>
    <label>Vsaj<select id="sg-pl-cm"><option value="1">1 cm</option><option value="5">5 cm</option><option value="15">15 cm</option></select></label>
  </div>
  <ol class="sg-pl-out" id="sg-pl-out" aria-live="polite"></ol>
  <p class="muted-note">Zračna razdalja, ne čas vožnje. Modelska ocena novega snega; ne upošteva ceste, plazov, odprtosti smučišč ali vremena po poti.</p>
  </section>
"""


def build_body(data, cams):
    rows = sorted(data["tocke"], key=lambda r: (-r["past72_cm"], -r["elevation_m"]))
    present = sorted({r["drzava"] for r in rows}, key=list(COUNTRIES).index)
    prof, bx = profile_svg(rows)

    def pt(r):
        x, y = proj(r["lon"], r["lat"])
        o = {"id": r["id"], "n": r["ime"], "e": r["elevation_m"], "x": round(x, 1), "y": round(y, 1), "bx": bx[r["id"]],
             "k": r["km_od_recice"], "c": r["drzava"]}
        o.update(cam_info(cams.get(r["id"], {})))
        if r.get("izmerjeno"):
            o["m"] = {"d": r["izmerjeno"]["depth_cm"], "a": r["izmerjeno"]["age_h"]}
        return o
    pts_json = json.dumps([pt(r) for r in rows], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    chips = ('<button type="button" data-c="*" aria-pressed="true">Vse</button>' +
             "".join(f'<button type="button" data-c="{c}" aria-pressed="false">{COUNTRIES[c]}</button>' for c in present) +
             '<button type="button" data-f="fresh" aria-pressed="false">Samo s svežim snegom</button>'
             '<button type="button" data-f="fav" aria-pressed="false">★ Moje točke</button>'
             '<span class="sep"></span>'
             '<button type="button" data-s="past" aria-pressed="true">Nazaj 24 h</button>'
             '<button type="button" data-s="next" aria-pressed="false">Naprej 24 h</button>'
             '<button type="button" data-s="elev" aria-pressed="false">Višina</button>'
             '<button type="button" data-s="km" aria-pressed="false">Razdalja</button>')
    cards_html = "\n".join(card_html(r, cams.get(r["id"], {})) for r in rows)
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    return f"""{seo.crumbs_html([("Meteorec", "/"), ("MeteoZima", "/zima/"), ("Snegofili", None)])}
{seo.stn_badge()}
  <div class="sg-app">
  <section class="sg-hero" aria-labelledby="sg-h1">
    <canvas id="sg-snow" aria-hidden="true"></canvas>
    <div class="sg-brand"><img src="/snegofili/brand/logo-hero.svg" width="222" height="58" alt="" decoding="async">
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
      <span id="sg-time" aria-live="polite">zdaj</span>
      <span class="sg-seg" role="group" aria-label="Kaj kaže karta"><button type="button" data-m="past" aria-pressed="true">Zadnjih 24 h</button><button type="button" data-m="next" aria-pressed="false">Naslednjih 24 h</button></span></div>
      <p class="sg-readout" id="sg-readout"></p>
    </div>
    <div class="sg-profwrap">
      <h2>Višinski prerez Alp</h2>
      <p>Višine točk od zahoda proti vzhodu. Modri del stolpca je nad mejo sneženja, bela črtica je meja sneženja pri točki ob izbrani uri; kjer lebdi nad stolpcem, je meja višje od točke.</p>
      <div class="sg-scroll" tabindex="0" role="region" aria-label="Višinski prerez: meja sneženja in točke">{prof}</div>
      <p class="sg-hint">Povlecite vodoravno za ostale točke.</p>
    </div>
  </section>
{stats_html(rows)}  <section id="zdaj-snezi" class="sg-sec sg-nowsec" aria-labelledby="zs-h" hidden>
  <h2 id="zs-h">Kjer zdaj sneži</h2>
  <p class="archive-intro" id="zs-sub"></p>
  <div class="sg-nowrow" id="sg-now-row" role="list"></div>
  <div class="sg-top" id="sg-top"></div>
  </section>
{cam_wall_html(rows, cams)}{windy_map_html()}{plan_html()}  <section id="toplotna-karta" class="sg-sec sg-heatsec" aria-labelledby="hm-h" hidden>
  <h2 id="hm-h">Kdaj in kje sneži: 96 ur</h2>
  <p class="archive-intro">Vsaka vrstica je ena točka, vsak stolpec ena ura od 48 ur nazaj do 48 ur naprej. Svetlejša in večja količina pomeni več novega snega na uro po modelu. Navpična črta je ura, ki jo kaže drsnik; klik na vrstico odpre podrobnost točke.</p>
  <div class="sg-heatbar" role="group" aria-label="Razvrstitev toplotne karte"><button type="button" data-hs="snow" aria-pressed="true">Najbolj snežno</button><button type="button" data-hs="elev" aria-pressed="false">Višina</button><button type="button" data-hs="km" aria-pressed="false">Razdalja</button></div>
  <div class="sg-heat" id="sg-heat" tabindex="0" role="region" aria-label="Toplotna karta po točkah in urah (drsno vodoravno)"><div class="sg-hm-lab" id="sg-hm-lab"></div>
    <div class="sg-hm-main"><div class="sg-hm-ax" id="sg-hm-ax"></div>
    <div class="sg-hm-cv"><canvas id="sg-hm-cv" role="img" aria-label="Toplotna karta novega snega po točkah in urah. Iste podatke najdete v karticah točk spodaj."></canvas><div class="sg-hm-cur" id="sg-hm-cur"></div></div></div></div>
  <p class="sg-hm-leg" id="sg-hm-leg" aria-hidden="true"></p>
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
{measured_html(rows)}{alarm_html(rows)}
{faq_html}
  <p class="muted-note">Ni plazovni bilten in ni nasvet za turo. Pred odhodom preverite uradni plazovni bilten
  pristojne države, <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a> in razmere pri
  oskrbovani koči ali smučišču. Slike kamer so last navedenih virov.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>
  </div>
<script type="application/json" id="sg-pts">{pts_json}</script>"""


def head_extras(schema):
    return ('<meta name="theme-color" content="#1b6ef3">\n'
            '<link rel="preload" href="/snegofili/fonts/Bricolage-latin.woff2" as="font" type="font/woff2" crossorigin>\n'
            '<link rel="icon" type="image/svg+xml" href="/snegofili/brand/favicon.svg">\n'
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
