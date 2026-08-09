#!/usr/bin/env python3
"""
tools/generate_biovreme_page.py — Biovreme pillar page

Generates /biovreme/index.html: a daily, non-diagnostic assessment of how
the weather may affect wellbeing, combining four factors —
zračni tlak (front passages), toplotna obremenitev, UV indeks in kakovost
zraka + cvetni prah. Reuses the existing /kakovost-zraka/ fetch/thresholds
for the air-quality factor instead of reforking the Open-Meteo Air Quality
call (see tools/generate_kakovost_zraka_page.py).

This is informational only, not medical advice — see the disclaimer in
build_body() before editing the "Priporočila" copy.

Usage:
  python3 tools/generate_biovreme_page.py
"""
import datetime, json, os, sys, urllib.request, urllib.parse, urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — shared template helpers
from generate_kakovost_zraka_page import fetch_air_quality, aqi_level  # noqa: E402 — don't refork

ROOT = seo.ROOT
SITE = seo.SITE
TODAY = seo.TODAY
LAT, LON = seo.LAT, seo.LON

LEVEL_RANK = {"ugodno": 0, "zmerno": 1, "obremenjujoče": 2}
LEVEL_ORDER = ["ugodno", "zmerno", "obremenjujoče"]


def fetch_forecast():
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "hourly": "pressure_msl",
        "daily": "apparent_temperature_max,apparent_temperature_min,uv_index_max",
        "timezone": "Europe/Ljubljana",
        "forecast_days": 2,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def now_index(times):
    now_str = datetime.datetime.now(ZoneInfo("Europe/Ljubljana")).strftime("%Y-%m-%dT%H")
    for i, t in enumerate(times):
        if t[:13] == now_str:
            return i
    return 0


def pressure_level(hourly):
    times = hourly.get("time") or []
    vals = hourly.get("pressure_msl") or []
    if not times or not vals:
        return "—", "ni podatka"
    i0 = now_index(times)
    window = [v for v in vals[i0:i0 + 24] if v is not None]
    if len(window) < 2:
        return "—", "ni podatka"
    swing = max(window) - min(window)
    if swing < 4:
        return "ugodno", f"{seo.num(swing, 1)} hPa v naslednjih 24 h — stabilno"
    if swing < 8:
        return "zmerno", f"{seo.num(swing, 1)} hPa v naslednjih 24 h — spremenljivo"
    return "obremenjujoče", f"{seo.num(swing, 1)} hPa v naslednjih 24 h — izrazita sprememba (možen prehod fronte)"


def thermal_level(amax, amin):
    if amax is None and amin is None:
        return "—", "ni podatka", None, None
    hot = amax is not None and amax >= 32
    cold = amin is not None and amin <= -10
    warm = amax is not None and amax >= 28
    cool = amin is not None and amin <= -5
    if hot or cold:
        lvl = "obremenjujoče"
    elif warm or cool:
        lvl = "zmerno"
    else:
        lvl = "ugodno"
    parts = []
    if amax is not None:
        parts.append(f"občutena do {seo.num(amax, 0)} °C")
    if amin is not None:
        parts.append(f"občutena od {seo.num(amin, 0)} °C")
    return lvl, " · ".join(parts) if parts else "ni podatka", amax, amin


def uv_level(uv):
    if uv is None:
        return "—", "ni podatka"
    if uv >= 8:
        return "obremenjujoče", f"UV indeks {seo.num(uv, 0)} — zelo visok/ekstremen"
    if uv >= 6:
        return "zmerno", f"UV indeks {seo.num(uv, 0)} — visok"
    return "ugodno", f"UV indeks {seo.num(uv, 0)} — nizek/zmeren"


def air_level(aqi, dom_val, dom_pollen):
    lvl_label, _ = aqi_level(aqi)
    if aqi is None:
        air_bucket = 0
    elif lvl_label in ("ODLIČNO", "DOBRO"):
        air_bucket = 0
    elif lvl_label == "ZMERNO":
        air_bucket = 1
    else:
        air_bucket = 2
    pollen_bucket = 0 if dom_val <= 50 else (1 if dom_val <= 200 else 2)
    bucket = max(air_bucket, pollen_bucket)
    lvl = LEVEL_ORDER[bucket]
    detail = f"EU AQI {aqi if aqi is not None else '—'} ({lvl_label.lower() if aqi is not None else '—'})"
    if dom_val > 10:
        detail += f" · cvetni prah ({dom_pollen.lower()}): {'visok' if dom_val > 50 else 'zmeren'}"
    return lvl, detail


def build_body(fc_data, aq_data):
    hourly = fc_data.get("hourly") or {}
    daily = fc_data.get("daily") or {}

    p_lvl, p_detail = pressure_level(hourly)

    amax = (daily.get("apparent_temperature_max") or [None])[0]
    amin = (daily.get("apparent_temperature_min") or [None])[0]
    t_lvl, t_detail, _, _ = thermal_level(amax, amin)

    uv = (daily.get("uv_index_max") or [None])[0]
    u_lvl, u_detail = uv_level(uv)

    aq_hourly = aq_data.get("hourly") or {}
    aq_times = aq_hourly.get("time") or []
    aqi = dom_val = None
    dom_pollen = "—"
    if aq_times:
        ai = now_index(aq_times)
        def aq_get(key):
            arr = aq_hourly.get(key) or []
            return arr[ai] if 0 <= ai < len(arr) else None
        aqi = aq_get("european_aqi")
        pollen_lbls = {"grass_pollen": "Trave", "birch_pollen": "Breza", "alder_pollen": "Jelša",
                       "mugwort_pollen": "Pelin", "ragweed_pollen": "Ambrozija"}
        dom_val = 0
        for key, lbl in pollen_lbls.items():
            v = aq_get(key)
            if v is not None and v > dom_val:
                dom_val, dom_pollen = v, lbl
    a_lvl, a_detail = air_level(aqi, dom_val or 0, dom_pollen)

    factors = [
        ("🌬 Zračni tlak", p_lvl, p_detail),
        ("🌡 Toplotna obremenitev", t_lvl, t_detail),
        ("☀️ UV indeks", u_lvl, u_detail),
        ("🌫 Kakovost zraka in cvetni prah", a_lvl, a_detail),
    ]
    ranked = [LEVEL_RANK[lvl] for _, lvl, _ in factors if lvl in LEVEL_RANK]
    composite = LEVEL_ORDER[max(ranked)] if ranked else "—"

    composite_desc = {
        "ugodno": "nič od štirih dejavnikov trenutno ne izstopa",
        "zmerno": "vsaj en dejavnik je danes izrazitejši",
        "obremenjujoče": "vsaj en dejavnik je danes precej izrazit",
        "—": "ni na voljo dovolj podatkov",
    }[composite]

    answer = (f'  <p class="archive-intro">Današnje biovreme za Rečico ob Savinji je <strong>{composite.upper()}</strong> '
              f'— {composite_desc}. Ocena združuje zračni tlak, toplotno obremenitev, UV indeks in kakovost zraka '
              f'— nazadnje posodobljeno {TODAY.isoformat()}.</p>')

    quick_cards = "\n".join(f'''    <div class="stat-card {cls}">
      <div class="sc-label">{label}</div>
      <div class="sc-val">{lvl.capitalize() if lvl != "—" else "—"}</div>
      <div class="sc-sub">{detail}</div>
    </div>''' for (label, lvl, detail), cls in zip(factors, ["c-up", "c-temp", "c-rain", "c-down"]))
    quick = f'  <div class="stat-grid">\n{quick_cards}\n  </div>'

    rows = "\n".join(
        f'      <tr><th>{label}</th><td>{detail} <span class="muted-note" style="margin:0;display:inline">({lvl if lvl != "—" else "ni podatka"})</span></td></tr>'
        for label, lvl, detail in factors
    )
    factor_table = '  <table class="stats">\n' + rows + "\n  </table>"

    about = '''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">📖 O biovremenu</div>
    <p class="archive-intro" style="margin:.4rem 0 0">Biovreme je uveljavljen pojem slovenske meteorologije — dnevna
    ocena, kako lahko vreme vpliva na počutje. Med prvimi je podnebne razlike na Slovenskem opisal Janez Vajkard
    Valvasor že leta 1689, zdraviliški turizem s poudarkom na podnebju pa je v drugi polovici 19. stoletja na Bledu
    utemeljil Arnold Rikli. Danes tovrstne napovedi (toplotna obremenitev, kakovost zraka, cvetni prah, UV indeks od
    leta 2001) redno objavlja ARSO; Slovenija je leta 1996 gostila tudi mednarodni kongres biometeorologov (ISB).</p>
  </div>'''

    rec_items = []
    if p_lvl == "obremenjujoče":
        rec_items.append("🌬 Nekateri ljudje ob hitrih spremembah zračnega tlaka poročajo o glavobolu, utrujenosti ali težji koncentraciji — če ste občutljivi, si danes vzemite počasnejši dan in bodite previdni za volanom.")
    if t_lvl == "obremenjujoče":
        rec_items.append("🌡 Izrazita toplotna obremenitev — pijte dovolj tekočine, izogibajte se naporu opoldan in poskrbite za senco oz. gretje po potrebi.")
    elif t_lvl == "zmerno":
        rec_items.append("🌡 Zmerna toplotna obremenitev — poslušajte telo pri fizičnem naporu na prostem.")
    if u_lvl == "obremenjujoče":
        rec_items.append("☀️ Visok UV indeks — uporabite zaščito pred soncem (krema, klobuk, senca) med 11. in 16. uro.")
    if a_lvl != "ugodno":
        rec_items.append(f'🌫 Kakovost zraka ali cvetni prah danes nista optimalna — podrobnosti in priporočila za astmatike/alergike na <a href="/kakovost-zraka/">strani o kakovosti zraka</a>.')
    if not rec_items:
        rec_items.append("😊 Noben dejavnik danes ne izstopa. Uživajte na prostem!")
    rec_html = "  <ul>\n" + "\n".join(f"    <li>{i}</li>" for i in rec_items) + "\n  </ul>"
    disclaimer = ('  <p class="muted-note"><strong>To ni zdravniško priporočilo.</strong> Biovreme je splošna, '
                  'informativna ocena na podlagi vremenskih podatkov — ne nadomešča nasveta zdravnika. Če imate '
                  'zdravstvene težave, ki jih povezujete z vremenom, se posvetujte z zdravnikom.</p>')

    qa = [
        ("Kaj je biovreme?",
         "Biovreme je dnevna ocena, kako lahko vreme vpliva na počutje — združuje zračni tlak (prehode front), "
         "toplotno obremenitev, UV sevanje in kakovost zraka. Ni medicinska diagnoza, temveč informativen povzetek."),
        ("Kakšno je danes biovreme v Rečici ob Savinji?",
         f"Današnja skupna ocena je {composite} — {composite_desc}. Razčlenitev po štirih dejavnikih je v tabeli zgoraj."),
        ("Ali sprememba zračnega tlaka res vpliva na počutje?",
         "Raziskave v Sloveniji so v preteklosti povezovale prehode front in razvoj ciklonov s pogostejšimi glavoboli, "
         "nekaterimi možganskožilnimi dogodki in več prometnimi nesrečami (zaradi slabše koncentracije in reakcijskega "
         "časa). Gre za statistične povezave na ravni populacije, ne za zanesljivo napoved za posameznika."),
        ("Od kod prihajajo podatki za to stran?",
         "Zračni tlak, toplotna obremenitev in UV indeks: Open-Meteo napoved. Kakovost zraka in cvetni prah: "
         "Open-Meteo Air Quality API (CAMS Europe) — isti vir kot na strani /kakovost-zraka/."),
    ]
    faq_html = "  <h2>Pogosta vprašanja</h2>\n  <div class=\"faq\">\n" + "\n".join(
        f'    <details><summary>{q}</summary><p>{a}</p></details>' for q, a in qa
    ) + "\n  </div>"

    sources = '''  <div class="card" style="margin-bottom:1rem">
    <div class="clabel">🔗 Viri in sorodne strani</div>
    <div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.65rem">
      <a href="https://www.arso.gov.si/vreme/napovedi%20in%20podatki/biovreme.html" target="_blank" rel="noopener" class="mtn-avk-link">🇸🇮 ARSO — biovreme</a>
      <a href="/kakovost-zraka/" class="mtn-avk-link">🌫️ Kakovost zraka in cvetni prah</a>
      <a href="/slovar/uv-indeks/" class="mtn-avk-link">☀️ UV indeks — slovar</a>
      <a href="/slovar/hladna-fronta/" class="mtn-avk-link">🌬 Hladna fronta — slovar</a>
      <a href="/slovar/biovreme/" class="mtn-avk-link">📖 Biovreme — slovar</a>
    </div>
  </div>'''

    body = f'''{seo.crumbs_html([("Meteorec", "/"), ("Biovreme", None)])}
{seo.stn_badge()}
  <h1 class="page-title">Biovreme — Zgornja Savinjska dolina</h1>
  <p class="post-meta">Zračni tlak, toplotna obremenitev, UV indeks in kakovost zraka · osvežuje se dnevno · {TODAY.isoformat()}</p>
{answer}
{quick}
  <h2>Razčlenitev po dejavnikih</h2>
{factor_table}
{about}
  <h2>Priporočila</h2>
{rec_html}
{disclaimer}
{sources}
{faq_html}
  <a class="back-link" href="/">← Nazaj na trenutno vreme</a>'''

    return body, composite


def main():
    print(f"[{TODAY}] Pridobivam podatke za biovreme …")
    try:
        fc_data = fetch_forecast()
        aq_data = fetch_air_quality()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
        print(f"✗ Napaka pri pridobivanju podatkov: {e}", file=sys.stderr)
        sys.exit(1)

    body, composite = build_body(fc_data, aq_data)

    url = "/biovreme/"
    title = "Biovreme — Zgornja Savinjska dolina"
    desc = (f"Biovreme danes: {composite}. Zračni tlak, toplotna obremenitev, UV indeks in kakovost zraka "
            f"za Rečico ob Savinji — informativna ocena, ne zdravniško priporočilo.")

    schema = "\n".join([
        seo.webpage_schema(url, title, desc, date_published="2026-08-09"),
        seo.crumbs_schema([("Meteorec", "/"), ("Biovreme", None)]),
    ])

    html = seo.page_shell(title, desc, url, schema, body)
    seo.write_page("biovreme/index.html", html, force=True)
    print(f"  → biovreme/index.html (biovreme: {composite})")


if __name__ == "__main__":
    main()
