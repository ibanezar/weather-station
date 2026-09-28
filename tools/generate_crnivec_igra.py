#!/usr/bin/env python3
"""
tools/generate_crnivec_igra.py — crnivec.si/igra/, igra »Čez Črnivec«.

Arkadna vožnja po R1-225 od Stahovice čez prelaz (902 m) do Gornjega Grada.
Igra je crnivec-igra/voznja.js (ročno pisana, skopira se na crnivec.si/igra/);
ta skript ji vsak dan sestavi NIVO iz istih razmer, ki jih kaže glavna stran:

- termin je današnja pot v službo (6:00–8:00, commute_hours iz winter_engine.py
  z umeritvijo DRSI) — isti termin kot »Na poti v službo in domov« na strani;
  če je že mimo in ure v podatkih ni več, popoldanski, sicer naslednje ure;
- temperatura na vrhu je iz najhujše ure termina (eval_hour, ista funkcija kot
  na strani), po progi navzdol se preračuna z istim gradientom; ob jutranji
  inverziji (data["fog"]) dolina ni toplejša od vrha;
- vozišče po kilometrih je black_ice_category + road_row — ista ocena kot
  vrstica »Vozišče« na strani, samo za vsako višino posebej;
- megla v dolini je jutranja zgornja meja megle (data["fog"]["top_m"]);
- sunki so IZMERJENI na postaji DRSI ob izračunu (brez modelske rezerve —
  isto pravilo kot vrstica Veter na strani).

Nivo je eden za cel dan (isti za vse igralce, sicer časi na lestvici niso
primerljivi) — isti razlog kot pri Termiki (tools/generate_igra_page.py).
Proga (ovinki) je stilizirana in vsak dan ista; resnična sta dolžina in
višinski profil (PROFIL, približek).

Piše: crnivec-site/igra/index.html, crnivec-site/igra/nivo.json,
      crnivec-site/igra/voznja.js, crnivec-site/igra/voznja.css
Wired into: .github/workflows/zima-forecast.yml (za generate_crnivec_page.py,
pred testom tools/test_crnivec_igra.mjs)

Usage:
  python3 tools/generate_crnivec_igra.py
"""
import datetime
import hashlib
import html
import json
import math
import os
import shutil
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402
from generate_crnivec_page import (  # noqa: E402 — ista ocena vozišča in isti ovoj kot glavna stran
    COMMUTE_WINDOWS, CRN_DIR, CRN_SITE, CSS, DATA_PATH, LEVEL_RANK, WORKER_BASE,
    eval_hour, load_json, measured_bias, road_row, to_crnivec_site)
from crnivec_zones import fetch_drsi_postaje  # noqa: E402
from winter_engine import black_ice_category  # noqa: E402

ROOT = seo.ROOT
SRC_DIR = os.path.join(ROOT, "crnivec-igra")
OUT_DIR = os.path.join(ROOT, CRN_DIR, "igra")
PAGE_PATH = "/crnivec/igra/"      # page_shell → to_crnivec_site → crnivec.si/igra/
PASS_ELEV = 902
L_REAL_KM = 24.5                  # L_REAL_KM v voznja.js
# Višinski profil R1-225 (km od Stahovice, m) — približek iz zemljevida,
# vrh in oba konca sta prava (Gornji Grad 428 m je višina postaje DRSI).
PROFIL = ((0, 440), (4, 520), (8, 680), (11.5, PASS_ELEV), (15, 720), (20, 500), (L_REAL_KM, 428))
CRN_LAT, CRN_LON = 46.26, 14.72   # prelaz (za višino sonca)
PADA_MM = 0.1                     # od toliko mm v uri v igri pada dež/sneg
GUST_MIN_KMH = 30                 # pod tem sunki v igri ne premikajo avta (isto v voznja.js)

# road_row() vrednost → površina v igri (in delež ledu v odseku). Neznana
# vrednost (nov niz v road_row) pade na suho — test tools/test_crnivec_igra.mjs
# tega ne ujame, zato: če dodaš vrednost v road_row, jo dodaj tudi tu.
ROAD_TO_SURF = {
    "možen sneg na cesti": ("sneg", 0.0),
    "nevarnost poledice": ("led", 0.6),
    "ponekod je lahko led": ("led", 0.25),
    "verjetno mokro": ("mokro", 0.0),
    "verjetno suho": ("suho", 0.0),
}
SURF_WORD = {"suho": "suho", "mokro": "mokro", "led": "led", "sneg": "sneg"}


def z_at(km):
    for (k0, z0), (k1, z1) in zip(PROFIL, PROFIL[1:]):
        if km <= k1:
            return z0 + (z1 - z0) * (km - k0) / (k1 - k0)
    return PROFIL[-1][1]


def sun_altitude(when_utc, lat=CRN_LAT, lon=CRN_LON):
    """Višina sonca v stopinjah (NOAA približek, ±0,5°) -- dovolj za to, ali
    je ob uri nivoja tema, somrak ali dan."""
    doy = when_utc.timetuple().tm_yday
    hour = when_utc.hour + when_utc.minute / 60
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                    - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    ha = math.radians((hour * 60 + eqt + 4 * lon) / 4 - 180)
    la = math.radians(lat)
    cosz = math.sin(la) * math.sin(decl) + math.cos(la) * math.cos(decl) * math.cos(ha)
    return math.degrees(math.asin(max(-1.0, min(1.0, cosz))))


def light_at(date_iso, hhmm):
    """noc / somrak / dan ob uri nivoja (lokalni čas)."""
    try:
        local = datetime.datetime.fromisoformat(f"{date_iso}T{hhmm}").replace(tzinfo=ZoneInfo("Europe/Ljubljana"))
    except ValueError:
        return "dan"
    alt = sun_altitude(local.astimezone(datetime.timezone.utc))
    return "noc" if alt < -6 else "somrak" if alt < 3 else "dan"


def snowpack_at_z(data, z):
    """Snežna odeja (cm) na višini z -- linearno med pasovi winter_engine.py."""
    bands = sorted(((b["elevation_m"], b.get("depth_cm") or 0)
                    for b in ((data.get("snowpack") or {}).get("by_elevation") or [])), key=lambda x: x[0])
    if not bands:
        return 0.0
    if z <= bands[0][0]:
        return bands[0][1]
    for (z0, d0), (z1, d1) in zip(bands, bands[1:]):
        if z <= z1:
            return d0 + (d1 - d0) * (z - z0) / (z1 - z0)
    return bands[-1][1]


def pick_hours(weather, drsi, today_iso):
    """(ključ, oznaka, [(surova ura, ocenjena ura)]) za današnji termin."""
    bias = measured_bias(weather, drsi)
    entries = weather.get("commute_hours") or []
    for key, label, hs in COMMUTE_WINDOWS:
        sel = [(e, eval_hour(e, bias)) for e in entries
               if (e.get("time") or "")[:10] == today_iso and int(e["time"][11:13]) in hs]
        if sel:
            return key, label, sel
    sel = [(e, eval_hour(e, bias)) for e in (weather.get("next_hours") or [])[:3]]
    return "zdaj", "naslednje ure", sel


def build_level(data, drsi, today):
    today_iso = today.isoformat()
    passes = data.get("passes") or []
    weather = (next((p for p in passes if p["id"] == "crnivec"), None) or {}).get("weather") or {}
    key, label, sel = pick_hours(weather, drsi, today_iso)
    sel = [x for x in sel if x[1]["temp"] is not None]
    if not sel:
        return None
    # Najhujša ura termina: najvišja raven, ob enaki najnižja temperatura.
    e, ev = max(sel, key=lambda x: (LEVEL_RANK[x[1]["level"]], -x[1]["temp"]))
    t_pass = ev["temp"]

    fog = data.get("fog") or {}
    inversion = (key == "jutro" and fog.get("has_inversion") and fog.get("morning_date") == today_iso
                 and fog.get("top_m"))
    fog_top = fog.get("top_m") if inversion else None

    odseki = []
    km = 0
    while km < L_REAL_KM:
        do = min(L_REAL_KM, km + 1)
        z0, z1 = z_at(km), z_at(do)
        z = (z0 + z1) / 2
        if fog_top and z < fog_top:
            t = t_pass     # inverzija: dolina ni toplejša od vrha
        else:
            t = t_pass + seo.LAPSE_RATE_C_PER_100M * (PASS_ELEV - z) / 100
        res = black_ice_category(t, e.get("cloud_pct"), e.get("wind_kmh_valley"), e.get("dew_c_valley"),
                                 e.get("precip_mm"), e.get("precip_mm_prev"))
        # Sneg na vrhu je izračunan za 902 m; niže in topleje pada kot dež.
        snow3 = e.get("snow_cm_3h") if t <= 1.0 else 0
        road = road_row(res[0] if res else None, e.get("precip_mm_3h"), snow3, t)
        surf, led = ROAD_TO_SURF.get(road["value"], ("suho", 0.0))
        # Padavine v uri nivoja: sneg, kjer je dovolj mraz (isto pravilo kot
        # sneg na cesti zgoraj), sicer dež. Samo za prikaz (delci na zaslonu).
        pada = None
        if (e.get("precip_mm") or 0) >= PADA_MM:
            pada = "sneg" if t <= 1.0 else "dez"
        odseki.append({"od_km": km, "z_od": round(z0), "z_do": round(z1), "t": round(t, 1),
                       "pada": pada, "odeja": snowpack_at_z(data, z) >= 1,
                       "povrsina": surf, "led_delez": led,
                       "mokro": (e.get("precip_mm_3h") or 0) >= 0.2,
                       "megla": bool(fog_top and z < fog_top)})
        km += 1

    gust = (drsi or {}).get("sunki_kmh")
    gust = round(gust) if gust is not None and gust >= GUST_MIN_KMH else None
    snowpack = ((data.get("snowpack") or {}).get("depth_cm") or {}).get("900")
    vrh = next(o for o in odseki if o["od_km"] == 11)
    date_ev = ev.get("date") or today_iso
    return {
        "datum": today_iso,
        "svetloba": light_at(date_ev, ev["time"]),
        "padavine_mm": e.get("precip_mm") or 0,
        "termin": key, "termin_txt": label,
        "ura": ev["time"],
        "t_vrh": t_pass,
        "vozisce": road_word(vrh),
        "odeja_cm": round(snowpack) if snowpack is not None else 0,
        "megla_do_m": round(fog_top) if fog_top else None,
        "sunki_kmh": gust,
        "odseki": odseki,
        "opis": opis(key, label, t_pass, odseki, fog_top, gust),
        "generated_at": data.get("generated_at"),
    }


def road_word(o):
    if o["povrsina"] == "led":
        return "ponekod led" if o["led_delez"] < 0.5 else "poledica"
    return {"suho": "suho vozišče", "mokro": "mokro vozišče", "sneg": "sneg na cesti"}[o["povrsina"]]


def opis(key, label, t_pass, odseki, fog_top, gust):
    kdaj = {"jutro": f"Današnje jutro ({label})", "popoldne": f"Današnje popoldne ({label})"}.get(
        key, "Današnje razmere")
    deli = [f"{kdaj}: na vrhu {seo.num(t_pass, 0)} °C"]
    vrste = {}
    for o in odseki:
        vrste.setdefault(road_word(o), []).append(o["od_km"])
    drugo = [(w, k) for w, k in vrste.items() if w != "suho vozišče"]
    if not drugo:
        deli.append("suho vozišče")
    else:
        txt = ", ".join(f"{w} (km {min(k)}–{seo.num(min(L_REAL_KM, max(k) + 1), 1).replace(',0', '')})"
                        for w, k in drugo)
        deli.append(txt + (", drugod suho" if "suho vozišče" in vrste else ""))
    if fog_top:
        deli.append(f"v dolini megla do {fog_top:.0f} m")
    if gust:
        deli.append(f"na vrhu sunki do {gust} km/h")
    return ", ".join(deli) + "."


def asset_version(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:10]


def surface_strip(level):
    barve = {"suho": "#9ca3af", "mokro": "#475569", "led": "#93c5fd", "sneg": "#f8fafc"}
    cells = "".join(
        f'<span class="cv-strip-c" style="background:{barve[o["povrsina"]]}" '
        f'title="km {o["od_km"]}–{o["od_km"] + 1}: {road_word(o)}, {seo.num(o["t"], 0)} °C'
        f'{", megla" if o["megla"] else ""}">{"≋" if o["megla"] else ""}</span>'
        for o in level["odseki"])
    return (f'<div class="cv-strip" aria-hidden="true">{cells}</div>'
            '<div class="cv-strip-l" aria-hidden="true"><span>Stahovica</span><span>Črnivec 902 m</span>'
            '<span>Gornji Grad</span></div>')


def faq_items():
    return [
        ("Ali igra res uporablja današnje razmere na Črnivcu?",
         "Da. Vsako jutro se nivo sestavi iz istega izračuna kot glavna stran crnivec.si: temperatura na "
         "vrhu za pot v službo (umerjena z meritvami postaje DRSI), ocena vozišča po višini, jutranja megla "
         "v dolini in izmerjeni sunki vetra na prelazu. Ovinki so stilizirani, dolžina proge in višinski "
         "profil pa sta prava."),
        ("Kdaj se splača natakniti verige?",
         "Na startu so verige zastonj, med vožnjo pa jih lahko nadeneš ali snameš samo, ko stojiš, in stane "
         "15 sekund. Na ledu in snegu z njimi voziš precej hitreje, na suhem pa ropotaš z največ 50 km/h. "
         "Preden izbereš, poglej, kaj piše o vozišču."),
        ("Ali je igra napoved stanja ceste?",
         "Ne. Vozišče v igri je ista ocena kot na glavni strani, a za igro poenostavljena. Za pravo pot preveri "
         "status na crnivec.si, kamero in uradno stanje ceste na promet.si."),
        ("Kako se šteje čas?",
         "Čas vožnje od Stahovice do Gornjega Grada, s kaznimi: 8 sekund za vsak jarek in 15 sekund za vsako "
         "menjavo verig med vožnjo. Na dnevni lestvici je najboljši čas vsakega igralca za današnji nivo."),
        ("Ali je lestvica zaščitena pred goljufanjem?",
         "Le delno. Igra teče v brskalniku, zato strežnik preveri samo, da je čas za današnji nivo in ni "
         "krajši, kot je sploh mogoče. Kdor si priredi igro, lahko vpiše lažen čas. Lestvica je za hec."),
    ]


def schema(title, desc, faq):
    data = [
        {"@context": "https://schema.org", "@type": "WebPage", "@id": f"{CRN_SITE}/igra/",
         "name": title, "description": desc, "url": f"{CRN_SITE}/igra/", "inLanguage": "sl",
         "isPartOf": {"@id": f"{CRN_SITE}/#website"},
         "author": {"@id": f"{seo.SITE}/#person"},
         "about": {"@id": f"{CRN_SITE}/#prelaz"},
         "datePublished": "2026-09-28",
         "dateModified": datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).isoformat(timespec="seconds")},
        {"@context": "https://schema.org", "@type": "FAQPage", "@id": f"{CRN_SITE}/igra/#vprasanja",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    return "\n".join(
        f'<script type="application/ld+json">\n{json.dumps(d, ensure_ascii=False, separators=(",", ":"))}\n</script>'
        for d in data)


def build_body(level, faq):
    v_js = asset_version(os.path.join(SRC_DIR, "voznja.js"))
    v_css = asset_version(os.path.join(SRC_DIR, "voznja.css"))
    level_json = json.dumps(level, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    vrh = next(o for o in level["odseki"] if o["od_km"] == 11)
    rows = [
        ("Termin", f'{html.escape(level["termin_txt"])}'),
        ("Na vrhu", f'{seo.num(level["t_vrh"], 1)} °C · {road_word(vrh)}'),
        ("Megla", f'v dolini do {level["megla_do_m"]} m' if level["megla_do_m"] else "ne"),
        ("Sunki na vrhu", f'{level["sunki_kmh"]} km/h (izmerjeno, DRSI)' if level["sunki_kmh"] else "brez"),
    ]
    rows_html = "".join(f'<li><span>{k}</span><strong>{v}</strong></li>' for k, v in rows)
    vprasanja = "\n".join(
        f'''        <details class="crn-acc">
          <summary><h3 class="crn-faq-q">{q}</h3></summary>
          <div class="crn-acc-body"><p>{a}</p></div>
        </details>''' for q, a in faq)
    return f'''{CSS}
<link rel="stylesheet" href="/igra/voznja.css?v={v_css}">
  <div class="crn cv">
    <div class="crn-top">
      <a class="crn-brand" href="{CRN_SITE}/"><img src="/logo-crnivec.svg" alt="crnivec.si" width="166" height="36"></a>
      <a class="crn-sib" href="{CRN_SITE}/">← Stanje ceste</a>
    </div>

    <section class="cv-head" aria-labelledby="cv-h1">
      <p class="crn-eyebrow">Igra · nivo {datetime.date.fromisoformat(level["datum"]).strftime("%-d. %-m. %Y")}</p>
      <h1 class="crn-title" id="cv-h1">Čez Črnivec</h1>
      <p class="cv-lead">Od Stahovice čez prelaz do Gornjega Grada, v današnjih razmerah. Pred startom se
      odloči: verige ali ne?</p>
    </section>

    <section class="crn-panel cv-cond" aria-labelledby="cv-cond-h">
      <h2 class="crn-h2" id="cv-cond-h">Današnja proga</h2>
      <p class="cv-opis">{html.escape(level["opis"])}</p>
      {surface_strip(level)}
      <ul class="cv-legend" aria-hidden="true"><li><i style="background:#9ca3af"></i>suho</li>
        <li><i style="background:#475569"></i>mokro</li><li><i style="background:#93c5fd"></i>led</li>
        <li><i style="background:#f8fafc"></i>sneg</li><li>≋ megla</li></ul>
      <ul class="cv-rows">{rows_html}</ul>
      <p class="cv-small" id="cv-stale" hidden>⚠️ Ta nivo ni današnji (jutranji izračun še ni osvežen).
      Igraš lahko, na lestvico pa se ne šteje.</p>
    </section>

    <section class="cv-game" aria-label="Igra">
      <div class="cv-stage">
        <canvas id="cv-canvas" tabindex="0" aria-label="Vožnja čez Črnivec. Puščici levo in desno za volan, gor za plin, dol za zavoro, V za verige."></canvas>
        <div class="cv-overlay" id="cv-overlay"><div class="cv-ov-in"><p class="cv-ov-sub">Igra potrebuje JavaScript.</p></div></div>
      </div>
      <div class="cv-ctrl">
        <button type="button" class="cv-key" data-cv="levo" aria-label="Levo">◀</button>
        <button type="button" class="cv-key cv-brake" data-cv="zavora" aria-label="Zavora">ZAVORA</button>
        <button type="button" class="cv-key cv-gas" data-cv="plin" aria-label="Plin">PLIN</button>
        <button type="button" class="cv-key" data-cv="desno" aria-label="Desno">▶</button>
      </div>
      <button type="button" class="crn-btn cv-chain" id="cv-chain">⛓ Natakni verige</button>
      <p class="cv-small cv-help">Tipkovnica: ← → volan, ↑ plin, ↓ zavora, V verige (samo ko stojiš).</p>
    </section>

    <section class="crn-panel cv-lb-panel" aria-labelledby="cv-lb-h">
      <h2 class="crn-h2" id="cv-lb-h">🏁 Danes najhitrejši</h2>
      <div id="cv-lb" aria-live="polite"><p class="cv-small">Nalagam …</p></div>
      <label class="cv-small cv-ime-l" for="cv-ime">Vzdevek na lestvici (neobvezno)</label>
      <input type="text" id="cv-ime" class="crn-input" maxlength="24" placeholder="Anonimni" autocomplete="nickname">
    </section>

    <section class="crn-info crn-faq" id="vprasanja" aria-labelledby="cv-faq-h">
      <h2 class="crn-h2" id="cv-faq-h">Pogosta vprašanja o igri</h2>
{vprasanja}
    </section>
  </div>
<script type="application/json" id="cv-level">{level_json}</script>
<script src="/igra/voznja.js?v={v_js}" defer></script>
'''


def main():
    data = load_json(DATA_PATH)
    if not data:
        print("✗ data/winter-data.json manjka -- najprej poženi tools/winter_engine.py.", file=sys.stderr)
        return 1
    today = datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).date()
    drsi = fetch_drsi_postaje().get("crnivec")
    level = build_level(data, drsi, today)
    if not level:
        # Brez ur v podatkih ostane včerajšnji nivo (stran ga označi kot
        # nesvežega in ga ne pošilja na lestvico) — raje star nivo kot nobene igre.
        print("⚠ Za danes ni ur v commute_hours/next_hours — nivo ostane nespremenjen.", file=sys.stderr)
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    for ime in ("voznja.js", "voznja.css"):
        shutil.copyfile(os.path.join(SRC_DIR, ime), os.path.join(OUT_DIR, ime))
    with open(os.path.join(OUT_DIR, "nivo.json"), "w", encoding="utf-8") as f:
        json.dump(level, f, ensure_ascii=False, indent=1)

    faq = faq_items()
    title = "Čez Črnivec: igra vožnje v današnjih razmerah"
    desc = ("Pripelji se od Stahovice čez prelaz Črnivec do Gornjega Grada. Led, sneg in megla v igri so "
            "iz današnjih razmer. Verige ali ne?")
    head = "\n".join([
        '<meta name="theme-color" content="#dc2626">',
        '<link rel="manifest" href="/manifest.json">',
        '<link rel="icon" href="/favicon.ico" sizes="32x32">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png">',
        schema(title, desc, faq)])
    page = seo.page_shell(title, desc, PAGE_PATH, head, build_body(level, faq))
    seo.write_page(f"{CRN_DIR}/igra/index.html", to_crnivec_site(page), force=True)
    print(f"  → {CRN_DIR}/igra/ (crnivec.si/igra/): {level['opis']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
