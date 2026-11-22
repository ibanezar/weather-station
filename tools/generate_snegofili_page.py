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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402

DATA_PATH = os.path.join(seo.ROOT, "data", "snegofili.json")
POINTS_PATH = os.path.join(seo.ROOT, "data", "snegofili-tocke.json")
OUTLINE_PATH = os.path.join(seo.ROOT, "data", "europe-outline.json")
URL = "/snegofili/"
TITLE = "Snegofili: kje je sneg, kamere in napoved"
DESC = ("Kje zdaj sneži po alpskem loku: karta, kamere, toplotna karta 96 ur, podrobnost vsake točke in izbirnik "
        "»kam peljem po sneg« za več kot 50 točk od Golt do Zermatta in Dachsteina. Modelska ocena, izmerjeno ločeno.")
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


def phase_text(ph, r=None):
    """Pod mejo sneženja pove, ali po modelu pada (≥ 0,1 mm v tekoči uri); brez podatka o padavinah ostane splošna oznaka."""
    if ph == "rain" and r is not None and r.get("precip_now_mm") is not None:
        return "Dež" if r["precip_now_mm"] >= 0.1 else "Brez padavin"
    return PHASE_TXT[ph]

# Powder Tracker: razvrstitev točk po svežini snega. Vse je MODELSKI potencial (padavine × delež snega, temperatura, veter), ne izmerjena kakovost pršiča.
# Meje so naša izbira, na strani so izpisane (»Kako razvrščamo«) in jih varuje tools/test_snegofili.py.
PW_POWDER_CM = 15      # Powder alert: vsaj toliko novega snega v zadnjih 24 urah ...
PW_POWDER_T = 0.0      # ... pri temperaturi zdaj do vključno te vrednosti (°C) ...
PW_GUST_KMH = 50       # ... in brez močnih sunkov (veter odnaša in zbija sneg); če sunka ne poznamo, ga ne upoštevamo
PW_FRESH_CM = 5        # Svež sneg: v zadnjih 24 urah vsaj toliko ...
PW_FRESH72_CM = 20     # ... ali v zadnjih 72 urah vsaj toliko
PW_WAIT24_CM = 10      # Sneg prihaja: v naslednjih 24 urah vsaj toliko ...
PW_WAIT72_CM = 20      # ... ali v naslednjih 72 urah vsaj toliko
PW_SNOWY_CM = 5        # Nekaj snega: v 72 urah nazaj ali naprej vsaj toliko
PW_CATS = (("powder", "Powder alert"), ("fresh", "Svež sneg"), ("waiting", "Sneg prihaja"), ("snowy", "Nekaj snega"))
PW_CAT_LABEL = dict(PW_CATS)
PW_CAT_RANK = {k: i for i, (k, _) in enumerate(PW_CATS)}
PW_GROUPS = (("*", "Vse"), ("si", "Slovenija"), ("alpe", "Alpe"), ("japonska", "Japonska"), ("amerika", "Severna Amerika"))
PW_LIMIT = 5           # privzeto prikazanih vrstic (ostale po gumbu); brez JS so vidne vse

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
    ("Kaj je Powder Tracker?",
     f"Lestvica točk (Alpe, Japonska, Severna Amerika) po svežini snega. »Powder alert« je vsaj {PW_POWDER_CM} cm novega snega v "
     f"24 urah pri temperaturi do {PW_POWDER_T:g} °C in brez sunkov nad {PW_GUST_KMH} km/h; »Svež sneg« vsaj {PW_FRESH_CM} cm v 24 urah "
     f"ali {PW_FRESH72_CM} cm v 72 urah; »Sneg prihaja« vsaj {PW_WAIT24_CM} cm v naslednjih 24 urah ali {PW_WAIT72_CM} cm v 72 urah. "
     "To je modelski potencial, ne izmerjena kakovost snega: model ne ve, kaj je veter odnesel, kako je sneg zbit in ali je smučišče "
     "odprto. Za odločitev poglejte kamero in uradno poročilo smučišča."),
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
    """Modelski nov sneg: pod centimetrom piše »<1 cm«, ne pomišljaja (pomišljaj pomeni »ni podatka«)."""
    return "<1 cm" if cm < MIN_CM else f"{num(cm, 0 if cm >= 10 else 1)} cm"


def cm_h(cm):
    return _html.escape(cm_cell(cm))


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


_zx0, _zy0 = proj(9.6, 48.0)
_zx1, _zy1 = proj(17.4, 44.9)
ZOOM_VB = f"{_zx0:.0f} {_zy0:.0f} {_zx1 - _zx0:.0f} {_zy1 - _zy0:.0f}"
ZOOM_AR = f"{_zx1 - _zx0:.0f} / {_zy1 - _zy0:.0f}"


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
        aria = (f'{r["ime"]}, {r["elevation_m"]} m: {phase_text(ph, r)}, zadnjih 24 ur {cm_cell(r["past24_cm"])}, '
                f'naslednjih 24 ur {cm_cell(r["next24_cm"])}')
        rad = radius(r["past24_cm"] if show else 0)
        circles.append(f'<circle class="sg-c {cls}" data-id="{r["id"]}" cx="{x:.1f}" cy="{y:.1f}" '
                       f'r="{rad:.1f}" tabindex="0" role="button" aria-label="{_html.escape(aria)}"/>')
        if r["id"] in label_ids:
            labels.append(f'<text class="sg-lbl" x="{x + 10 + rad:.1f}" y="{y + 7:.1f}">'
                          f'{_html.escape(short(r["ime"]))}</text>')
    return (
        f'<div class="sg-mapwrap"><svg id="sg-map" class="zoom" data-w="{MAP_W}" data-h="{MAP_H}" data-full="0 0 {MAP_W} {MAP_H}" viewBox="{ZOOM_VB}" style="aspect-ratio:{ZOOM_AR}" '
        f'role="group" aria-label="Karta alpskega loka: novi sneg v zadnjih 24 urah po točkah">'
        f'<path class="land" d="M0 0H{MAP_W}V{MAP_H}H0Z"/><path class="bord" d="{bord}"/><path class="coast" d="{coast}"/>'
        f'<path d="M{rx:.1f} {ry - 9:.1f}l8 9l-8 9l-8 -9z" fill="#fff" stroke="#0a1426" stroke-width="2"/>'
        f'<text class="sg-lbl" id="sg-rec-lbl" x="{rx + 14:.1f}" y="{ry + 7:.1f}">Rečica</text>'
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
    """Vrstica »Kamera: …« na kartici: vsak vir ima svojo oznako (ARSO/DRSI aktualna slika, Windy časovni zdrs, ponudnik)."""
    links = []
    if p.get("arso_cam") or p.get("drsi_cam"):
        links.append('<a href="#kamere">' + ("ARSO" if p.get("arso_cam") else "DRSI") + ': aktualna slika</a>')
    for c in p.get("kamere") or []:
        if valid_embed(c):
            continue  # vdelana kamera (Windy) ima svoj gumb pod vrstico
        if str(c.get("url", "")).startswith("https://"):
            links.append(f'<a href="{_html.escape(c["url"])}" target="_blank" rel="noopener">'
                         f'{_html.escape(c["ponudnik"])}: odpri kamero</a>')
    if any(valid_embed(c) for c in p.get("kamere") or []):
        links.append("Windy: časovni zdrs")
    return ", ".join(links) or "ni kamere"


def sl_text(sl, elev):
    """Meja sneženja kot višina + položaj točke glede nanjo (ne le predznak)."""
    if sl is None:
        return "ni podatka"
    d = elev - sl
    return f"{round(sl, -1):.0f} m · točka {abs(round(d, -1)):.0f} m {'nad' if d >= 0 else 'pod'} njo"


def card_html(r, p, kcr=None):
    ph = phase(r["elevation_m"], r["snow_line_m"])
    av = f'<span class="sg-av ph" data-c="{r["drzava"]}" aria-hidden="true">{r["drzava"]}</span>'
    if kcr and r["id"] in kcr:
        c = kcr[r["id"]]
        av = (f'<img class="sg-av" src="/snegofili/img/kraji/{r["id"]}.jpg" width="48" height="48" alt="" loading="lazy" decoding="async" '
              f'title="Foto: {_html.escape(c["avtor"] or "neznan avtor")}, {_html.escape(c["licenca"])}">')
    meas = r.get("izmerjeno")
    meas_txt = (f'<b>{meas["depth_cm"]} cm</b> (ARSO, pred {num(meas["age_h"], 0)} h'
                f'{", izmerjena ničla" if meas["depth_cm"] == 0 else ""})') if meas else "ni merilne postaje ARSO"
    aria = f'{r["ime"]}: {phase_text(ph, r)}, zadnjih 24 ur {cm_cell(r["past24_cm"])}, naslednjih 24 ur {cm_cell(r["next24_cm"])}'
    return (
        f'    <article class="sg-card" id="t-{r["id"]}" data-c="{r["drzava"]}" data-past="{r["past24_cm"]}" '
        f'data-next="{r["next24_cm"]}" data-fresh="{max(r["past24_cm"], r["next24_cm"])}" '
        f'data-elev="{r["elevation_m"]}" data-km="{r["km_od_recice"]}" data-n="{_html.escape(r["ime"].lower())}" aria-label="{_html.escape(aria)}">'
        f'<div class="sg-head">{av}<div class="sg-hd-t"><h3>{_html.escape(r["ime"])}</h3><p class="sg-sub">{COUNTRIES[r["drzava"]]} · '
        f'{_html.escape(r["regija"])} · {r["elevation_m"]} m · {r["km_od_recice"]} km</p></div>'
        f'<span class="sg-pill ph-{ph}">{phase_text(ph, r)}</span></div>'
        f'<div class="sg-div" role="img" aria-label="{_html.escape(aria)}"><div class="sg-half l">'
        f'<div class="sg-bl" style="width:{bar_pct(r["past24_cm"]) / 2:.1f}%"></div></div><div class="sg-half">'
        f'<div class="sg-br" style="width:{bar_pct(r["next24_cm"]) / 2:.1f}%"></div></div></div>'
        f'<div class="sg-nums"><span><b class="sg-np">{cm_h(r["past24_cm"])}</b><small>zadnjih 24 ur</small></span>'
        f'<span class="r"><b class="sg-nn">{cm_h(r["next24_cm"])}</b><small>naslednjih 24 ur</small></span></div>'
        f'<p class="sg-src"><span class="sg-bdg m">Model</span> nov sneg po modelu</p>'
        f'<div class="sg-spark" aria-hidden="true"></div>'
        f'<dl class="sg-dl"><div><dt>Trenutna ura</dt><dd class="sg-tt">{num(r["temp_c"], 1)} °C</dd></div>'
        f'<div style="grid-column:span 2"><dt>Meja sneženja</dt><dd class="sg-sl">{sl_text(r["snow_line_m"], r["elevation_m"])}</dd></div></dl>'
        f'<div class="sg-foot"><span>Zadnjih 72 ur: {cm_h(r["past72_cm"])} · naslednjih 72 ur: {cm_h(r["next72_cm"])}</span>'
        f'<span>{cam_links(p)}</span></div>'
        f'{cam_slot(r["ime"], p)}'
        f'<div class="sg-foot"><span><span class="sg-bdg r">Meritev</span> {meas_txt}</span></div></article>')


# ── rubrika »Po svetu« (21. 11. 2026): Japonska in Severna Amerika, ločen seznam in ločena datoteka (ne meša se z alpskim lokom) ──
WORLD_PATH = os.path.join(seo.ROOT, "data", "snegofili-svet.json")
COUNTRIES_WORLD = {"JP": "Japonska", "CA": "Kanada", "US": "ZDA"}
WORLD_GROUPS = (("Japonska", ("JP",)), ("Severna Amerika", ("CA", "US")))


def load_world():
    """Vrstice rubrike »Po svetu« ali None, če datoteke ni (prvi tek po uvedbi) ali nima nobene veljavne točke."""
    try:
        with open(WORLD_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    rows = [r for r in (d.get("tocke") or []) if r.get("drzava") in COUNTRIES_WORLD and r.get("past24_cm") is not None
            and r.get("next24_cm") is not None and r.get("elevation_m") is not None]
    return {"rows": rows, "when": d.get("generated_at_local", "")} if rows else None


WORLD_POINTS_PATH = os.path.join(seo.ROOT, "data", "snegofili-svet-tocke.json")
def load_world_cams():
    """Točke »Po svetu« po id-ju (iz ročnega seznama), da kartica dobi kamere iste oblike kot alpske točke (`kamere`, vdelava samo prek valid_embed())."""
    try:
        with open(WORLD_POINTS_PATH, encoding="utf-8") as f:
            return {p["id"]: p for p in json.load(f).get("tocke", [])}
    except (OSError, ValueError):
        return {}


def world_cam_thumb(p):
    """Sličica Windy kamere na kartici: lena, prek workerja /windy-thumb; klik odpre časovni zdrs (gumb pod vrstico). Prazno, če ni dovoljene vdelave."""
    for c in (p or {}).get("kamere") or []:
        ok = valid_embed(c)
        if ok and ok[0] == "windy":
            m = re.search(r"/player/(\d{1,12})/", ok[1])
            if m:
                return (f'<div class="sg-wc-cam" data-wid="{m.group(1)}"><span class="sg-wc-cam-msg">Sličica kamere se nalaga …</span>'
                        f'<span class="sg-wc-cam-cap">Webcams provided by windy.com</span></div>')
    return ""


def world_phase(r):
    """Kot phase(), a ob manjkajoči ničti izotermi (nekateri modeli je ne ponujajo) iz temperature na višini točke."""
    if r.get("snow_line_m") is not None:
        return phase(r["elevation_m"], r["snow_line_m"])
    t = r.get("temp_c")
    return "rain" if t is None else "snow" if t <= 0 else "mix" if t < 2 else "rain"


def spark_svg(sn, w=288, h=44):
    """Sneženje po urah (48 h nazaj in 48 h naprej od »zdaj«, indeksi 24…119 iz 144-urne serije); navpična črta je zdaj.
    Višina stolpcev je sorazmerna z največjo uro (najmanj 1 cm/h, da šum ne izgleda kot sneg)."""
    vals = list(sn[24:120]) if sn and len(sn) >= 120 else []
    if not vals:
        return ""
    mx = max(10, max(v or 0 for v in vals))
    bw = w / len(vals)
    bars = []
    for i, v in enumerate(vals):
        if not v:
            continue
        bh = max(1.5, (v / mx) * (h - 5))
        bars.append(f'<rect class="{"p" if i < 48 else "f"}" x="{i * bw:.1f}" y="{h - bh:.1f}" width="{bw * 0.78:.1f}" height="{bh:.1f}"/>')
    return (f'<svg class="sg-ws" viewBox="0 0 {w} {h}" preserveAspectRatio="none" role="img" '
            f'aria-label="Nov sneg po urah po modelu: 48 ur nazaj in 48 ur naprej od zdaj">'
            f'{"".join(bars)}<line class="n" x1="{w / 2:.1f}" x2="{w / 2:.1f}" y1="0" y2="{h}"/></svg>')


def world_card_html(r, p=None):
    p = p or {}
    ph = world_phase(r)
    where = f'{COUNTRIES_WORLD[r["drzava"]]} · {r["regija"]} · {r["elevation_m"]} m'
    aria = (f'{r["ime"]}: zadnjih 24 ur {cm_cell(r["past24_cm"])}, naslednjih 24 ur {cm_cell(r["next24_cm"])}')
    sl = r.get("snow_line_m")
    sl_txt = sl_text(sl, r["elevation_m"]) if sl is not None else "ni podatka (sneg po temperaturi)"
    return (
        f'    <article class="sg-wc" id="w-{r["id"]}" aria-label="{_html.escape(aria)}">'
        f'<div class="sg-wc-hd"><span class="sg-av ph" data-c="{r["drzava"]}" aria-hidden="true">{r["drzava"]}</span>'
        f'<div class="sg-hd-t"><h4>{_html.escape(r["ime"])}</h4><p class="sg-sub">{_html.escape(where)}</p></div>'
        f'<span class="sg-pill ph-{ph}">{phase_text(ph, r)}</span></div>'
        f'{world_cam_thumb(p)}'
        f'<div class="sg-wc-nums"><span><b>{cm_h(r["past24_cm"])}</b><small>zadnjih 24 ur</small></span>'
        f'<span class="r"><b>{cm_h(r["next24_cm"])}</b><small>naslednjih 24 ur</small></span></div>'
        f'{spark_svg(r.get("sn"))}'
        f'<dl class="sg-dl"><div><dt>Trenutna ura</dt><dd>{num(r["temp_c"], 1)} °C</dd></div>'
        f'<div style="grid-column:span 2"><dt>Meja sneženja</dt><dd>{sl_txt}</dd></div></dl>'
        f'<p class="sg-foot"><span>Zadnjih 72 ur: {cm_h(r["past72_cm"])} · naslednjih 72 ur: {cm_h(r["next72_cm"])}</span>'
        f'<span>{world_cam_links(p)}</span></p>'
        f'{cam_slot(r["ime"], p)}'
        f'</article>')


def world_cam_links(p):
    """Kot cam_links(), a brez sklica na razdelek ARSO kamer (za svet ga ni): »Windy: časovni zdrs«, povezave ponudnikov ali »ni kamere«."""
    return cam_links({"kamere": (p or {}).get("kamere")})


def svet_html(world, wcams=None):
    rows = world["rows"]
    best = max(rows, key=lambda r: r["past72_cm"])
    lead = (f'Po modelu je v zadnjih 72 urah največ snega zapadlo na točki <strong>{_html.escape(best["ime"])}</strong> '
            f'({_html.escape(COUNTRIES_WORLD[best["drzava"]])}, {cm_h(best["past72_cm"])}).'
            if best["past72_cm"] >= MIN_CM else "V zadnjih 72 urah po modelu na nobeni od teh točk ni zapadlo več kot centimeter snega.")
    groups = []
    for title, codes in WORLD_GROUPS:
        part = sorted((r for r in rows if r["drzava"] in codes), key=lambda r: -r["past72_cm"])
        if part:
            groups.append(f'  <h3 class="sg-h3">{title}</h3>\n  <div class="sg-wgrid">\n' +
                          "\n".join(world_card_html(r, (wcams or {}).get(r["id"])) for r in part) + "\n  </div>\n")
    return ('  <section id="po-svetu" class="sg-sec" aria-labelledby="sv-h">\n'
            '  <h2 id="sv-h">Po svetu <span class="sg-bdg m">Model</span></h2>\n'
            f'  <p class="archive-intro">Izven Alp: smučišča na Japonskem in v Severni Ameriki. {lead} '
            'Ista ocena kot za Alpe (padavine iz celice vremenskega modela × delež, ki pade kot sneg); merjene višine odeje za te točke nimamo. '
            '<b>Japonski sneg je pogosto suh in lahek</b>, zato je prava količina lahko večja od modelske (1 mm ≈ 1 cm); poročila objavljajo smučišča sama.</p>\n'
            + "".join(groups) +
            '  <p class="muted-note">Okna »zadnjih 24 ur« in »naslednjih 24 ur« štejejo od zdaj, kot drugje na strani. Višine točk so izbrane za zgornji del '
            'smučišča in še niso preverjene, koordinate so približne. Ni uradna napoved in ni plazovni bilten. Podatki: Open-Meteo.</p>\n'
            '  </section>\n')


def hero_sentence(rows):
    best24 = max(rows, key=lambda r: r["past24_cm"])
    best72 = max(rows, key=lambda r: r["past72_cm"])
    near = [r for r in rows if r["km_od_recice"] <= TRIP_KM and r["next24_cm"] >= MIN_CM]
    parts = []
    if best72["past72_cm"] < MIN_CM:
        parts.append("V zadnjih 72 urah po modelu nikjer v seznamu ni zapadlo več kot centimeter novega snega.")
    else:
        last72 = (f'v zadnjih 72 urah pa na točki <strong>{_html.escape(best72["ime"])}</strong> '
                  f'({cm_h(best72["past72_cm"])}).')
        if best24["past24_cm"] >= MIN_CM:
            parts.append(f'Po modelu je v zadnjih 24 urah najbolj zasnežilo na točki '
                         f'<strong>{_html.escape(best24["ime"])}</strong> ({cm_h(best24["past24_cm"])}), {last72}')
        else:
            parts.append(f'V zadnjih 24 urah po modelu nikjer ni zapadlo več kot centimeter snega, {last72}')
    if near:
        top = max(near, key=lambda r: r["next24_cm"])
        parts.append(f'Od točk do {TRIP_KM} km zračne razdalje od Rečice je v naslednjih 24 urah največ snega '
                     f'napovedanega na točki <strong>{_html.escape(top["ime"])}</strong> '
                     f'({cm_h(top["next24_cm"])}, {top["km_od_recice"]} km).')
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
                    f'<button type="button" class="sg-live">Odpri kamero Windy</button>'
                    f'<p class="sg-attr">Po kliku se naloži vsebina ponudnika ({prov}), ki lahko nastavi svoje piškotke.</p>{credit}</div>')
    return ""


KRAJI_DIR = os.path.join(seo.ROOT, "snegofili", "img", "kraji")


def kraji_credits():
    """Vnosi credits.json za točke, ki imajo krožno fotografijo (datoteka obstaja); navedba avtorja je obvezna in se izpiše na strani."""
    path = os.path.join(KRAJI_DIR, "credits.json")
    if not os.path.exists(path):
        return {}
    c = json.load(open(path, encoding="utf-8"))
    return {k: v for k, v in c.items() if os.path.exists(os.path.join(KRAJI_DIR, k + ".jpg"))}


def kraji_html(rows, cr):
    if not cr:
        return ""
    names = {r["id"]: r["ime"] for r in rows}
    li = "".join(
        f'<li><b>{_html.escape(names[k])}</b>: {_html.escape(v["avtor"] or "neznan avtor")} · '
        + (f'<a href="{_html.escape(v["licenca_url"])}" target="_blank" rel="noopener license">{_html.escape(v["licenca"])}</a>' if v.get("licenca_url") else _html.escape(v["licenca"]))
        + f' · <a href="{_html.escape(v["stran"])}" target="_blank" rel="noopener">Wikimedia Commons</a></li>'
        for k, v in sorted(cr.items(), key=lambda kv: names.get(kv[0], kv[0])) if k in names)
    return ('  <details class="sg-fotocr" id="foto-krajev"><summary>Fotografije krajev: avtorji in licence</summary>\n'
            '  <p class="muted-note">Majhne krožne fotografije ob krajih so z Wikimedia Commons (zmanjšane in izrezane); avtorji in licence so spodaj.</p>\n'
            f'  <ul>{li}</ul></details>\n')


HERO_PHOTO = "hero-zima"   # slug slike v snegofili/img/; če ima vnos v credits.json (avtor, licenca), se pod herom izpiše navedba


def hero_photo():
    """(slug, navedba) za sliko v ozadju hero dela; navedba je prazna, kjer slika nima vnosa v credits.json."""
    if not HERO_PHOTO or not os.path.exists(os.path.join(seo.ROOT, "snegofili", "img", HERO_PHOTO + ".jpg")):
        return None
    path = os.path.join(seo.ROOT, "snegofili", "img", "credits.json")
    c = (json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}).get(HERO_PHOTO)
    if not c:
        return HERO_PHOTO, ""
    lic = (f'<a href="{_html.escape(c["licenca_url"])}" target="_blank" rel="noopener license">{_html.escape(c["licenca"])}</a>'
           if c.get("licenca_url") else _html.escape(c["licenca"]))
    credit = (f'Foto: {_html.escape(c["avtor"])} · {lic} · '
              f'<a href="{_html.escape(c["stran"])}" target="_blank" rel="noopener">Wikimedia Commons</a>')
    return HERO_PHOTO, credit


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
    <label class="sg-al-slo"><input type="checkbox" id="sg-al-slo"> <span><b>Sneži kjerkoli v Sloveniji.</b> Obvestilo, ko model ICON-D2 v naslednjih treh urah napove sneženje v Sloveniji (vsaj tri celice mreže 10 × 8 km, vsaj 0,1 cm na uro). Pošljemo ga ob začetku sneženja, ne ob vsaki uri; največ enkrat na 12 ur. Deluje tudi brez pravil zgoraj.</span></label>
    <div class="sg-al-row"><button type="button" class="sg-al-btn" id="sg-al-on">Vklopi opozorilo</button> <button type="button" class="sg-al-btn s" id="sg-al-off" hidden>Izklopi</button></div>
    <p class="muted-note" id="sg-al-ios" hidden>Na iPhonu obvestila delujejo samo v aplikaciji, dodani na začetni zaslon (Deli, nato Dodaj na začetni zaslon).</p>
    <p class="muted-note" id="sg-al-msg" aria-live="polite"></p>
    <p class="muted-note">Modelska ocena novega snega iz padavin in meje sneženja, ne meritev; ni plazovni bilten in ni nasvet za turo. Strežnik shrani samo naslovnico naročnine, vaša pravila in kljukico »Sneži kjerkoli v Sloveniji«; izklop jih izbriše.</p>
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
                f'    <figure class="sg-cam" data-id="{r["id"]}" data-kind="{kind}" data-c="{r["drzava"]}">'
                f'<button type="button" class="sg-cam-b" aria-label="Poglej kamero: {ime}">'
                f'<span class="sg-cam-img"><span class="sg-cam-msg">Nalagam sliko …</span></span>'
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
    return (f'  <section id="kamere" class="sg-sec" aria-labelledby="kam-h">\n  <h2 id="kam-h">Kamere <span class="sg-bdg c">Slika kamere</span></h2>\n'
            '  <p class="archive-intro"><b>Aktualna slika</b> (ARSO, DRSI) se osveži vsakih nekaj minut, »Oglej si aktualno sliko« jo odpre večjo. '
            'Pri točkah z oznako Windy gumb po kliku predvaja <b>časovni zdrs zadnjega dne</b>. <b>Videa v živo tu ni.</b></p>\n'
            '  <p class="muted-note sg-cam-note">Sličice kamer: Webcams provided by <a href="https://www.windy.com/" target="_blank" rel="noopener">windy.com</a>. '
            'Ob sliki piše, kaj za tisto točko napoveduje model; kamera in model se lahko razhajata: verjemite sliki.</p>\n'
            '  <div class="sg-filter sg-camf" id="sg-camf" role="group" aria-label="Filter kamer" hidden>'
            '<button type="button" data-cf="*" aria-pressed="true">Vse kamere</button>'
            '<button type="button" data-cf="SI" aria-pressed="false">Samo slovenske</button></div>\n' + wall + ln + '  </section>\n')


ST_ICONS = {
    "past": '<path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9M9.5 4.5 12 7l2.5-2.5M9.5 19.5 12 17l2.5 2.5"/>',
    "next": '<rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M8 3v4M16 3v4"/>',
    "fresh": '<path d="m3 19 6-10 4 6 3-4 5 8z"/>',
    "meas": '<path d="M4 17 17 4l3 3L7 20H4zM13 8l3 3M10 11l2 2M7 14l2 2"/>',
    "rec": '<path d="M12 21s-6-5.2-6-10a6 6 0 0 1 12 0c0 4.8-6 10-6 10zM12 13a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z"/>',
}


def st_icon(i):
    return (f'<svg class="sg-st-ic" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ST_ICONS[i]}</svg>')


def stats_html(rows):
    """Štiri kartice v herou. Alpe (vse točke) in območje do TRIP_KM od Rečice sta ločena podatka."""
    near = [r for r in rows if r["km_od_recice"] <= TRIP_KM]
    b24, bn = max(rows, key=lambda r: r["past24_cm"]), max(rows, key=lambda r: r["next24_cm"])
    fresh = sum(1 for r in rows if r["past24_cm"] >= MIN_CM)
    meas = sum(1 for r in rows if r.get("izmerjeno"))

    def near_line(key):
        if not near:
            return ""
        b = max(near, key=lambda r: r[key])
        if b[key] < MIN_CM:
            return f"Do {TRIP_KM} km od Rečice: nikjer ≥ 1 cm"
        return f'Do {TRIP_KM} km od Rečice: {cm_h(b[key])} · {_html.escape(b["ime"])}'

    def tile(i, lab, bdg, val, sub, extra="", hid=False):
        cls, attr = ("sg-stat sg-st-rec", ' id="sg-st-rec-w" hidden') if hid else ("sg-stat", "")
        return (f'<div class="{cls}"{attr}><small>{st_icon(i)}<span>{lab}</span> <span class="sg-bdg {bdg[0]}">{bdg[1]}</span></small><b id="sg-st-{i}">{val}</b>'
                f'<span id="sg-st-{i}-n">{sub}</span>'
                + (f'<span class="sg-st-near" id="sg-st-{i}-c">{extra}</span>' if extra else "") + '</div>')
    mod = ("m", "Model")
    return ('  <div class="sg-stats" id="sg-stats" role="group" aria-label="Povzetek po modelu in meritvah">'
            + tile("past", "Nov sneg, zadnjih 24 ur", mod, cm_h(b24["past24_cm"]), _html.escape(b24["ime"]) if b24["past24_cm"] >= MIN_CM else "nikjer", near_line("past24_cm"))
            + tile("next", "Nov sneg, naslednjih 24 ur", mod, cm_h(bn["next24_cm"]), _html.escape(bn["ime"]) if bn["next24_cm"] >= MIN_CM else "nikjer", near_line("next24_cm"))
            + tile("fresh", "Lokacij s snegom", mod, f"{fresh}", f"od {len(rows)} lokacij · ≥ 1 cm v zadnjih 24 urah")
            + tile("meas", "Postaj ARSO", ("r", "Meritev"), f"{meas}", "z izmerjeno višino snežne odeje")
            + tile("rec", "Rečica, sneg v dolini", ("r", "Meritev"), "ni meritve", "višina snežne odeje (ročna meritev)", hid=True)
            + '</div>\n')


def slo_alert_html():
    """Okno »Zdaj sneži v Sloveniji«: skrito, dokler JS (sloAlert() v snegofili.js) ne najde slovenske točke, kjer po modelu
    ob trenutni uri sneži. Vsebino (seznam točk) napolni JS; brez JS ostane skrito, ker bi statičen posnetek hitro zastarel."""
    return ('  <aside class="sg-slo" id="sg-slo" role="status" aria-live="polite" aria-labelledby="sg-slo-t" hidden>\n'
            '    <div class="sg-slo-hd"><span class="sg-slo-dot" aria-hidden="true"></span><h2 id="sg-slo-t">Zdaj sneži v Sloveniji</h2>'
            '<span class="sg-bdg m">Model</span>'
            '<button type="button" class="sg-slo-x" id="sg-slo-x" aria-label="Zapri okno »Zdaj sneži v Sloveniji«">×</button></div>\n'
            '    <p class="sg-slo-s" id="sg-slo-s"></p>\n'
            '    <ul class="sg-slo-l" id="sg-slo-l"></ul>\n'
            '    <p class="sg-slo-f"><a href="#zdaj-snezi">Vse točke, kjer sneži</a></p>\n'
            '  </aside>\n')


def measured_html(rows):
    meas = [r for r in rows if r.get("izmerjeno")]
    if not meas:
        return ""
    top = max(40, max(r["izmerjeno"]["depth_cm"] for r in meas))
    li = "".join(
        f'<li><span class="sg-ms-n">{_html.escape(r["ime"])} <small>{r["elevation_m"]} m</small></span>'
        f'<span class="sg-ms-bar" role="img" aria-label="Izmerjeno {r["izmerjeno"]["depth_cm"]} cm"><i style="width:{min(100, r["izmerjeno"]["depth_cm"] / top * 100):.1f}%"></i></span>'
        f'<span class="sg-ms-v"><b>{r["izmerjeno"]["depth_cm"]} cm</b> <small>{"izmerjena ničla, " if r["izmerjeno"]["depth_cm"] == 0 else ""}pred {num(r["izmerjeno"]["age_h"], 0)} h</small></span>'
        f'<span class="sg-ms-m"><small>model: nov sneg zadnjih 72 ur</small> {cm_h(r["past72_cm"])}</span></li>'
        for r in sorted(meas, key=lambda r: -r["izmerjeno"]["depth_cm"]))
    return ('  <section id="izmerjeno" class="sg-sec" aria-labelledby="izm-h">\n  <h2 id="izm-h">Izmerjena snežna odeja <span class="sg-bdg r">Meritev</span></h2>\n'
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
  <details class="sg-fold"><summary><h2 id="wy-h">Dodatne karte: sneg, veter, temperatura in oblaki (Windy)</h2></summary>
  <p class="archive-intro">Zunanja interaktivna karta Windy (model ECMWF) za pregled gibanja padavin in vetra. To je vsebina ponudnika, ne naša ocena: številke se lahko razlikujejo od tistih zgoraj.</p>
  <div class="sg-heatbar" role="group" aria-label="Začetna plast karte Windy">{btns}</div>
  <div class="sg-wy" id="sg-wy" data-base="{_html.escape(WINDY_MAP)}"><button type="button" class="sg-live">Naloži karto Windy</button>
  <p class="sg-attr">Po kliku se naloži vsebina ponudnika (Windy), ki lahko nastavi svoje piškotke. Map by <a href="https://www.windy.com/" target="_blank" rel="noopener">windy.com</a>.</p></div>
  </details>
  </section>
"""


def plan_html():
    km = "".join(f'<option value="{k}"{" selected" if k == TRIP_KM else ""}>{"do " + str(k) + " km" if k else "vse"}</option>'
                 for k in (100, TRIP_KM, 400, 0))
    return f"""  <section id="kam-peljem" class="sg-plan sg-rank" aria-labelledby="kp-h" hidden>
  <h2 id="kp-h">Kje bo največ novega snega?</h2>
  <div class="sg-plan-row">
    <label>Kdaj<select id="sg-pl-win"><option value="n24">Naslednjih 24 h</option><option value="n48">24–48 h od zdaj</option><option value="p24">Zadnjih 24 h</option></select></label>
    <label>Razdalja od Rečice<select id="sg-pl-km">{km}</select></label>
    <label>Višina točke<select id="sg-pl-el"><option value="0">vse</option><option value="1000">nad 1000 m</option><option value="1500">nad 1500 m</option><option value="2000">nad 2000 m</option></select></label>
    <label>Vsaj<select id="sg-pl-cm"><option value="1">1 cm</option><option value="5">5 cm</option><option value="15">15 cm</option></select></label>
  </div>
  <ol class="sg-pl-out" id="sg-pl-out" aria-live="polite"></ol>
  <p class="muted-note">Zračna razdalja, ne čas vožnje. Modelska ocena; ne upošteva ceste, plazov ali odprtosti smučišč.</p>
  </section>
"""


def powder_category(r):
    """Kategorija točke (ključ iz PW_CATS) ali None, če ni snega ne nazaj ne naprej. Vrstni red pravil je pomemben (prvo, ki velja)."""
    p24, p72, n24, n72 = (r.get(k) or 0 for k in ("past24_cm", "past72_cm", "next24_cm", "next72_cm"))
    t, g = r.get("temp_c"), r.get("gust_kmh")
    if p24 >= PW_POWDER_CM and t is not None and t <= PW_POWDER_T and not (g is not None and g >= PW_GUST_KMH):
        return "powder"
    if p24 >= PW_FRESH_CM or p72 >= PW_FRESH72_CM:
        return "fresh"
    if n24 >= PW_WAIT24_CM or n72 >= PW_WAIT72_CM:
        return "waiting"
    if max(p72, n72) >= PW_SNOWY_CM:
        return "snowy"
    return None


def powder_quality(t):
    """Opis snega po temperaturi zdaj (ne meritev vlage snega)."""
    if t is None:
        return ""
    return "suh, lahek sneg" if t <= -3 else "običajen sneg" if t <= 0 else "moker, težji sneg (nad 0 °C)"


def powder_sort_key(r, cat):
    first = r["next24_cm"] if cat == "waiting" else r["past24_cm"]
    return (PW_CAT_RANK[cat], -first, -r["past72_cm"], -r["next72_cm"], -r["elevation_m"])


def powder_groups(r, world):
    if world:
        return "japonska" if r["drzava"] == "JP" else "amerika"
    return "alpe si" if r["drzava"] == "SI" else "alpe"


def powder_wind(r):
    w, g = r.get("wind_kmh"), r.get("gust_kmh")
    if w is None and g is None:
        return ""
    return f'veter {w if w is not None else "—"} km/h' + (f' (sunki {g})' if g is not None else "")


def powder_item(r, cat, world):
    """Kompaktna vrstica: ime, ena drobna vrstica (država · višina · temperatura · sneg po temperaturi · veter), kategorija in tri količine."""
    cc = COUNTRIES_WORLD if world else COUNTRIES
    href = ("#w-" if world else "#t-") + r["id"]
    sub = [cc.get(r["drzava"], r["drzava"]), f'{r["elevation_m"]} m',
           f'{num(r["temp_c"], 1)} °C' if r.get("temp_c") is not None else "", powder_quality(r.get("temp_c")), powder_wind(r)]
    aria = (f'{r["ime"]}: {PW_CAT_LABEL[cat]}, zadnjih 24 ur {cm_cell(r["past24_cm"])}, naslednjih 24 ur {cm_cell(r["next24_cm"])}')
    return (f'    <li class="sg-pw-i" data-cat="{cat}" data-g="{powder_groups(r, world)}">'
            f'<a href="{href}" aria-label="{_html.escape(aria)}">'
            f'<span class="sg-pw-n"><b>{_html.escape(r["ime"])}</b><small>{_html.escape(" · ".join(x for x in sub if x))}</small></span>'
            f'<span class="sg-pill pw-{cat}">{PW_CAT_LABEL[cat]}</span>'
            f'<span class="sg-pw-v a"><b>{cm_h(r["past24_cm"])}</b><small>zadnjih 24 ur</small></span>'
            f'<span class="sg-pw-v b"><b>{cm_h(r["next24_cm"])}</b><small>naslednjih 24 ur</small></span>'
            f'<span class="sg-pw-v c"><b>{cm_h(r["past72_cm"])}</b><small>zadnjih 72 ur</small></span>'
            f'</a></li>')


def powder_html(rows, world_rows):
    """Powder Tracker: strežniško izrisan seznam (vidno brez JS in iskalnikom); JS samo filtrira po območju in kategoriji."""
    items = []
    for world, part in ((False, rows), (True, world_rows or [])):
        for r in part:
            cat = powder_category(r)
            if cat:
                items.append((powder_sort_key(r, cat), cat, r, world))
    items.sort(key=lambda x: x[0])
    counts = {k: sum(1 for i in items if i[1] == k) for k, _ in PW_CATS}
    if items:
        top = items[0]
        r = top[2]
        lead = (f'Najbolj obetavno: <strong>{_html.escape(r["ime"])}</strong> '
                f'({_html.escape((COUNTRIES_WORLD if top[3] else COUNTRIES).get(r["drzava"], r["drzava"]))}), '
                f'{cm_h(r["past24_cm"])} v zadnjih 24 urah'
                f'{", " + num(r["temp_c"], 1) + " °C" if r.get("temp_c") is not None else ""}.')
    else:
        lead = "Po modelu trenutno na nobeni točki ni dovolj novega snega za uvrstitev."
    cat_chips = ('<button type="button" data-pc="*" aria-pressed="true">Vse (%d)</button>' % len(items) +
                 "".join(f'<button type="button" data-pc="{k}" aria-pressed="false">{v} ({counts[k]})</button>' for k, v in PW_CATS if counts[k]))
    present = {g for it in items for g in powder_groups(it[2], it[3]).split()}
    reg_chips = "".join(f'<button type="button" data-pg="{k}" aria-pressed="{"true" if k == "*" else "false"}">{v}</button>'
                        for k, v in PW_GROUPS if k == "*" or k in present)
    lis = "\n".join(powder_item(i[2], i[1], i[3]) for i in items)
    return f"""  <section id="powder" class="sg-sec sg-pw" aria-labelledby="pw-h" data-limit="{PW_LIMIT}">
  <h2 id="pw-h">Powder Tracker <span class="sg-bdg m">Model</span></h2>
  <p class="archive-intro">{lead} <b>Modelski potencial</b> (sneg, temperatura, veter), ne izmerjena kakovost snega.</p>
  <div class="sg-filter" id="sg-pw-f" hidden role="group" aria-label="Filter Powder Trackerja">{cat_chips}<span class="sep"></span>{reg_chips}</div>
  <div class="sg-pw-hd" aria-hidden="true"><span>zadnjih 24 ur</span><span>naslednjih 24 ur</span><span>zadnjih 72 ur</span></div>
  <ol class="sg-pw-list" id="sg-pw-list">
{lis}
  </ol>
  <p class="muted-note" id="sg-pw-empty" hidden>Za ta izbor po modelu ni točk s snegom.</p>
  <button type="button" class="sg-pw-more" id="sg-pw-more" hidden></button>
  <details class="sg-fold"><summary>Kako razvrščamo</summary>
  <ul class="sg-pw-how">
    <li><b>Powder alert</b>: vsaj {PW_POWDER_CM} cm novega snega v zadnjih 24 urah, temperatura zdaj do {PW_POWDER_T:g} °C in sunki pod {PW_GUST_KMH} km/h.</li>
    <li><b>Svež sneg</b>: vsaj {PW_FRESH_CM} cm v zadnjih 24 urah ali {PW_FRESH72_CM} cm v zadnjih 72 urah.</li>
    <li><b>Sneg prihaja</b>: vsaj {PW_WAIT24_CM} cm v naslednjih 24 urah ali {PW_WAIT72_CM} cm v naslednjih 72 urah.</li>
    <li><b>Nekaj snega</b>: vsaj {PW_SNOWY_CM} cm v 72 urah nazaj ali naprej.</li>
  </ul>
  <p>Točka dobi prvo kategorijo, ki ji ustreza; znotraj kategorije so točke po količini snega (pri »Sneg prihaja« po napovedani). Količina je ocena iz padavin in
  meje sneženja, ista kot drugje na strani. Temperatura in veter sta vrednosti zdaj na višini točke. Model ne vidi, koliko snega je veter odnesel ali zbil,
  ne pozna priprave prog in ne ve, ali je smučišče odprto; japonski sneg je pogosto suh, zato je tam prava količina lahko večja. Ni plazovni bilten.</p>
  </details>
  </section>
"""


def build_body(data, cams):
    rows = sorted(data["tocke"], key=lambda r: (-r["past72_cm"], -r["elevation_m"]))
    present = sorted({r["drzava"] for r in rows}, key=list(COUNTRIES).index)
    prof, bx = profile_svg(rows)
    kcr = kraji_credits()

    def pt(r):
        x, y = proj(r["lon"], r["lat"])
        o = {"id": r["id"], "n": r["ime"], "e": r["elevation_m"], "x": round(x, 1), "y": round(y, 1), "bx": bx[r["id"]],
             "k": r["km_od_recice"], "c": r["drzava"]}
        if r["id"] in kcr:
            o["f"] = 1
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
             '<button type="button" data-s="past" aria-pressed="true">Zadnjih 24 ur</button>'
             '<button type="button" data-s="next" aria-pressed="false">Naslednjih 24 ur</button>'
             '<button type="button" data-s="elev" aria-pressed="false">Višina</button>'
             '<button type="button" data-s="km" aria-pressed="false">Razdalja</button>')
    cards_html = "\n".join(card_html(r, cams.get(r["id"], {}), kcr) for r in rows)
    faq_html = '  <h2>Pogosta vprašanja</h2>\n  <div class="faq">\n' + "\n".join(
        f'    <details><summary>{_html.escape(q)}</summary><p>{_html.escape(a)}</p></details>' for q, a in FAQ) + "\n  </div>"
    cams_sec = cam_wall_html(rows, cams)
    world = load_world()
    world_sec = svet_html(world, load_world_cams()) if world else ""
    hp = hero_photo()
    nav = [("zemljevid", "Zemljevid"), ("powder", "Powder")] + ([("kamere", "Kamere")] if cams_sec else []) + [
        ("toplotna-karta", "96 ur"), ("lokacije", "Lokacije")] + ([("po-svetu", "Po svetu")] if world_sec else []) + [
        ("izmerjeno", "Meritve"), ("sg-alarm", "Opozorila")]
    nav_html = ('  <nav class="sg-nav" id="sg-nav" aria-label="Razdelki strani"><ul>' +
                "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in nav) + '</ul></nav>\n')
    tab_ic = {
        "zemljevid": '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14"/>',
        "kam-peljem": '<path d="m3 19 6-10 4 6 3-4 5 8z"/>',
        "kamere": '<path d="M4 8h3l2-2h6l2 2h3v11H4zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z"/>',
        "lokacije": '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
        "sg-alarm": '<path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7zM10 20a2 2 0 0 0 4 0"/>',
    }
    tabs = [("zemljevid", "Zemljevid"), ("kam-peljem", "Kje sneži")] + ([("kamere", "Kamere")] if cams_sec else []) + [
        ("lokacije", "Lokacije"), ("sg-alarm", "Opozorila")]
    tabbar = ('<nav class="sg-tabbar" id="sg-tabbar" aria-label="Glavni razdelki"><ul>' + "".join(
        f'<li><a href="#{i}"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{tab_ic[i]}</svg><span>{t}</span></a></li>' for i, t in tabs) +
        '</ul></nav>\n')
    return f"""  <div class="sg-app">
  <section class="sg-hero{" has-photo" if hp else ""}" aria-labelledby="sg-h1"{f' style="--sg-hero-img:url(/snegofili/img/{hp[0]}.jpg)"' if hp else ""}>
    <canvas id="sg-snow" aria-hidden="true"></canvas>
    <div class="sg-brand"><img src="/snegofili/brand/logo-hero.svg" width="332" height="87" alt="Snegofili" decoding="async">
    <div class="sg-brand-r"><button type="button" class="sg-install" id="sg-install" hidden aria-label="Namesti aplikacijo Snegofili" title="Namesti na zaslon"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11M7.5 11 12 15.5 16.5 11M5 20h14"/></svg><span class="sg-install-t">Namesti</span></button><a class="sg-back" href="/zima/">← MeteoZima</a><p class="sg-kicker">Alpski lok · {len(rows)} točk</p></div></div>
    <h1 class="page-title" id="sg-h1">Kje zdaj pada sneg?</h1>
    <p class="sg-sub2">Spremljanje snežnih razmer po Alpah: modelska ocena, meritve ARSO in kamere.</p>
    <div class="sg-hero-row"><p class="sg-nowline" id="sg-nowline" aria-live="polite"></p>
    <p class="sg-meta" id="sg-gen" data-generated="{data["generated_at"]}">Modelska ocena · posodobljeno {_html.escape(data["generated_at_local"])}</p></div>
    <p class="sg-install-hint" id="sg-install-hint" role="status" aria-live="polite" hidden></p>
    <div class="sg-hero-cta"><a class="sg-cta p" href="#zemljevid">Trenutne snežne razmere</a>
    <a class="sg-cta o" id="sg-al-cta" href="#sg-alarm" hidden>Nastavi snežno opozorilo</a></div>
{f'    <p class="sg-credit">{hp[1]}</p>' if hp and hp[1] else ""}
  </section>
{stats_html(rows)}{slo_alert_html()}{nav_html}  <section id="zemljevid" class="sg-sec sg-mapsec" aria-labelledby="zm-h">
  <h2 id="zm-h">Zemljevid snežnih razmer <span class="sg-bdg m">Model</span></h2>
  <p class="archive-intro">Barva in velikost kroga kažeta novi sneg po modelu; dotik točke odpre povzetek. Privzeti pogled je Slovenija z Avstrijo in severno Italijo.</p>
  <div class="sg-win sg-mapgrid">
    <div class="sg-mapcol">
{map_svg(rows)}
    <div class="sg-zoom" id="sg-zoom" hidden><button type="button" aria-pressed="true" data-zoom="{ZOOM_VB}" data-full="0 0 {MAP_W} {MAP_H}">Pokaži ves alpski lok</button></div>
{legend_html()}
    <div class="sg-ctlwrap">
      <div id="sg-ctl" hidden><button type="button" id="sg-play" aria-pressed="false">Predvajaj</button>
      <input type="range" id="sg-range" aria-label="Čas od −48 do +48 ur"><button type="button" id="sg-now">Trenutna ura</button>
      <span id="sg-time" aria-live="polite">trenutna ura</span>
      <span class="sg-seg" role="group" aria-label="Kaj kaže karta"><button type="button" data-m="past" aria-pressed="true">Zadnjih 24 ur</button><button type="button" data-m="next" aria-pressed="false">Naslednjih 24 ur</button></span></div>
      <p class="sg-readout" id="sg-readout"></p>
    </div>
    </div>
    <aside class="sg-panel" id="sg-panel" aria-label="Povzetek izbrane točke" hidden></aside>
{plan_html()}  </div>
  </section>
  <p class="sg-brief">{hero_sentence(rows)}</p>
  <section id="zdaj-snezi" class="sg-sec sg-nowsec" aria-labelledby="zs-h" hidden>
  <h2 id="zs-h">Kjer zdaj sneži <span class="sg-bdg m">Model</span></h2>
  <p class="archive-intro" id="zs-sub"></p>
  <div class="sg-nowrow" id="sg-now-row" role="list"></div>
  <div class="sg-top" id="sg-top"></div>
  </section>
{powder_html(rows, world["rows"] if world else None)}  <div class="sg-duo">
  <section id="prerez" class="sg-sec" aria-labelledby="pr-h">
    <div class="sg-profwrap">
      <h2 id="pr-h">Višinski prerez Alp <span class="sg-bdg m">Model</span></h2>
      <p>Višine točk od zahoda proti vzhodu. Modri del stolpca je nad mejo sneženja, bela črtica je meja sneženja pri točki ob izbrani uri; kjer lebdi nad stolpcem, je meja višje od točke. Ura sledi drsniku na zemljevidu.</p>
      <div class="sg-scroll" tabindex="0" role="region" aria-label="Višinski prerez: meja sneženja in točke">{prof}</div>
      <p class="sg-hint">Povlecite vodoravno za ostale točke.</p>
    </div>
  </section>
  <section id="toplotna-karta" class="sg-sec sg-heatsec" aria-labelledby="hm-h" hidden>
  <h2 id="hm-h">96-urni pregled sneženja <span class="sg-bdg m">Model</span></h2>
  <p class="archive-intro"><b>48 ur nazaj in 48 ur naprej</b> od zadnjega modelskega izračuna (prvi del je preteklost, drugi napoved). Vsaka vrstica je ena točka, vsak stolpec ena ura. Svetlejša in večja količina pomeni več novega snega na uro po modelu. Navpična vijolična črta je ura, ki jo kaže drsnik; klik na vrstico odpre podrobnosti točke.</p>
  <div class="sg-heatbar" id="sg-hbar" role="group" aria-label="Razvrstitev in izbor toplotne karte"><button type="button" data-hs="snow" aria-pressed="true">Najbolj snežno</button><button type="button" data-hs="elev" aria-pressed="false">Višina</button><button type="button" data-hs="km" aria-pressed="false">Razdalja</button><span class="sep"></span><button type="button" data-hc="*" aria-pressed="true">Vse točke</button><button type="button" data-hc="SI" aria-pressed="false">Samo Slovenija</button></div>
  <div class="sg-heat" id="sg-heat" tabindex="0" role="region" aria-label="Toplotna karta po točkah in urah (drsno vodoravno)"><div class="sg-hm-lab" id="sg-hm-lab"></div>
    <div class="sg-hm-main"><div class="sg-hm-ax" id="sg-hm-ax"></div>
    <div class="sg-hm-cv"><canvas id="sg-hm-cv" role="img" aria-label="Toplotna karta novega snega po točkah in urah. Iste podatke najdete v karticah točk spodaj."></canvas><div class="sg-hm-cur" id="sg-hm-cur"></div></div></div></div>
  <p class="sg-hm-leg" id="sg-hm-leg" aria-hidden="true"></p>
  </section>
  </div>
{cams_sec}{windy_map_html()}  <section id="lokacije" class="sg-sec" aria-labelledby="lok-h">
  <h2 id="lok-h">Primerjava {len(rows)} lokacij <span class="sg-bdg m">Model</span></h2>
  <p class="archive-intro">Seznam zajema {len(rows)} točk od Golt do Zermatta in Dachsteina. To je <b>modelska ocena novega snega</b>
  iz padavin in višine ničte izoterme, ne meritev. Izmerjeno višino odeje imamo samo za nekaj postaj ARSO in je
  v svojem razdelku in v vrstici »Meritev« na kartici. Za našo dolino glej še <a href="/zima/snezna-karta/">snežno karto</a>,
  <a href="/zima/meja-snezenja/">mejo sneženja</a> in <a href="/vreme-v-gorah/">vreme v gorah</a>.</p>
  <div class="sg-filter" id="sg-filter" hidden><label class="sg-search"><span class="sg-vh">Poišči lokacijo</span><input type="search" id="sg-q" placeholder="Poišči: Golte, Krvavec, Dachstein …" autocomplete="off"></label>{chips}</div>
  <div id="sg-cards">
{cards_html}
  </div>
  <p class="muted-note">Zračna razdalja od Rečice, ne čas vožnje. Temperatura je preračunana na višino točke.
  »&lt;1 cm« pri snegu pomeni manj kot centimeter po modelu, »ni podatka« pa da vrednosti nimamo. Podatki: Open-Meteo, postaje ARSO.</p>
  </section>
{world_sec}{measured_html(rows)}{alarm_html(rows)}{kraji_html(rows, kcr)}
{faq_html}
  <p class="muted-note">Ni plazovni bilten in ni nasvet za turo. Pred odhodom preverite uradni plazovni bilten
  pristojne države, <a href="https://meteo.arso.gov.si/" target="_blank" rel="noopener">ARSO</a> in razmere pri
  oskrbovani koči ali smučišču. Slike kamer so last navedenih virov.</p>
  <a class="back-link" href="/zima/">← Nazaj na Zimski nadzorni center</a>
  </div>
{tabbar}<script type="application/json" id="sg-pts">{pts_json}</script>"""


def head_extras(schema):
    hp = hero_photo()
    pre = f'<link rel="preload" as="image" href="/snegofili/img/{hp[0]}.jpg" fetchpriority="high">\n' if hp else ""
    return (pre +'<meta name="theme-color" content="#1b6ef3">\n'
            '<link rel="manifest" href="/snegofili/manifest.json">\n'
            '<meta name="apple-mobile-web-app-capable" content="yes">\n'
            '<meta name="apple-mobile-web-app-title" content="Snegofili">\n'
            '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
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
