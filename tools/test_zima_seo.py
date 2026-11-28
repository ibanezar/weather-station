#!/usr/bin/env python3
"""tools/test_zima_seo.py — zimske strani po SEO raziskavi 25. 11. 2026 (meja sneženja, snežna karta, Snegofili, vreme v gorah, hub).

Zaklene:
  - meja sneženja = ničta izoterma − 250 m (do 25. 11. 2026 je stran kazala surovo izotermo),
  - namerne podvojitve konstant winter_engine ↔ generate_zima_page,
  - dolžine <title> (≤ 60) in opisov (≤ 160),
  - nove razdelke, FAQ in navzkrižne povezave (razmejitev meja sneženja / snežna karta / Snegofili),
  - blok »Sneg na Golteh«: samo iz svežega posnetka.
Zaženi: python3 tools/test_zima_seo.py"""
import datetime
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import winter_engine as we  # noqa: E402
import generate_zima_page as z  # noqa: E402
import generate_snezna_karta_page as k  # noqa: E402
import generate_snegofili_page as sg  # noqa: E402
import generate_gore_page as g  # noqa: E402
import generate_seo_pages as seo  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


def text_of(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


# ── 1. meja sneženja = ničta izoterma − odmik ──────────────────────────────
check(we.snow_line_from_freezing_level(1000) == 750, "izoterma 1000 m → meja 750 m")
check(we.snow_line_from_freezing_level(100) == 0, "meja ne pade pod 0 m")
check(we.snow_line_from_freezing_level(None) is None, "brez izoterme None")

times = [f"2026-12-01T{h:02d}:00" for h in range(24)] + [f"2026-12-02T{h:02d}:00" for h in range(24)]
fl = [1000] * 24 + [1400] * 24
hourly = {"time": times, "freezing_level_height": fl, "precipitation": [0.0] * 48}
sl = we.compute_snow_line(hourly, 0)
check(sl["current_line_m"] == 750, "current_line_m je izoterma − 250 (ne surova izoterma)")
check(sl["forecast_24h_m"] == 1150, "forecast_24h_m je izoterma − 250")
check(sl["confidence"] == "nizka", "zanesljivost iz premika surove izoterme (400 m → nizka)")
check(all(d["line_m"] == min(1000, 1000) - 250 or d["line_m"] == 1150 for d in sl["daily"] if d["line_m"] is not None),
      "dnevna najnižja meja je izoterma − 250")

# ── 2. podvojene konstante ────────────────────────────────────────────────
check(z.SNOW_OFFSET_M == we.SNOW_LEVEL_OFFSET_M, "SNOW_OFFSET_M ↔ winter_engine")
check(z.SNOW_MIX_HALF_M == we.SNOW_BAND_HALFWIDTH_M, "SNOW_MIX_HALF_M ↔ winter_engine")
check(z.CONF_SWING_HIGH_M == we.CONF_SWING_HIGH_M and z.CONF_SWING_MID_M == we.CONF_SWING_MID_M,
      "pragovi zanesljivosti ↔ winter_engine")

# ── 3. dolžine naslovov in opisov ─────────────────────────────────────────
for name, title, desc in (
        ("meja sneženja", z.SNOW_LINE_TITLE, None), ("hub", z.HUB_TITLE, z.HUB_DESC),
        ("snežna karta", k.TITLE, k.DESC), ("Snegofili", sg.TITLE, sg.DESC), ("vreme v gorah", g.TITLE, g.DESC)):
    check(len(seo.seo_title(title)) <= 60, f"<title> {name} ≤ 60 znakov")
    if desc:
        check(len(desc) <= 160, f"opis {name} ≤ 160 znakov ({len(desc)})")

# ── 4. stran Meja sneženja na umetnih podatkih ────────────────────────────
DATA = {
    "generated_at_local": "1. 12. 2026 ob 7:00",
    "snow_line": {
        "current_line_m": 510, "forecast_24h_m": 700, "expected_cm_at_station": 0.0, "confidence": "srednja",
        "expected_cm_by_elevation": [{"elevation_m": e, "cm": c} for e, c in ((366, 0.0), (600, 1.0), (900, 4.0), (1200, 8.0), (1600, 12.0))],
        "daily": [{"date": "2026-12-01", "line_m": 400, "cm_at_station": 0.0},
                  {"date": "2026-12-02", "line_m": 300, "cm_at_station": 2.5},
                  {"date": "2026-12-03", "line_m": 250, "cm_at_station": 6.0},
                  {"date": "2026-12-04", "line_m": 900, "cm_at_station": 0.0}],
    },
    "locations": [{"name": "Mozirje", "elevation_m": 340}, {"name": "Rečica ob Savinji", "elevation_m": 366},
                  {"name": "Gornji Grad", "elevation_m": 431}, {"name": "Luče", "elevation_m": 700},
                  {"name": "Solčava", "elevation_m": 560}],
}
body, faq = z.build_snow_line_body(DATA)
txt = text_of(body)
for needle in ("Napoved meje sneženja za naslednje dni", "Kje v dolini sneži in kje dežuje", "Kako zanesljiva je ocena meje sneženja",
               "Meja sneženja danes in jutri"):
    check(needle in txt, f"meja sneženja: vsebuje »{needle}«")
for href in ("/zima/snezna-karta/", "/snegofili/", "/vreme-v-gorah/", "/primerjava-modelov/", "/zima/sneg-porocila/"):
    check(f'href="{href}"' in body, f"meja sneženja: povezava {href}")
qs = [q for q, _ in faq]
for q in ("Do katere višine bo snežilo?", "Zakaj meja sneženja ni enaka višini, kjer je 0 °C?",
          "Kje lahko vidim, kje trenutno sneži?", "Kakšna je meja sneženja na Golteh ali Menini planini?"):
    check(q in qs, f"meja sneženja FAQ: {q}")
check(f"do {we.CONF_SWING_HIGH_M} m" in txt and f"do {we.CONF_SWING_MID_M} m" in txt, "razlaga zanesljivosti navaja prave pragove")
# tri dni v tabeli, četrti ne
check(txt.count("najnižja meja") == 3, "tabela po dnevih ima 3 dni")
# dež / mešano / sneg po krajih (meja 510, pas ±100): do 410 dež, 410–610 mešano, od 610 sneg
places = z.snow_line_places_html(DATA)
check(re.search(r"Mozirje \(340 m\)</th><td>dež<", places) is not None, "Mozirje (340 m) ob meji 510 m: dež")
check(re.search(r"Gornji Grad \(431 m\)</th><td>dež s snegom<", places) is not None, "Gornji Grad (431 m): dež s snegom")
check(re.search(r"Luče \(700 m\)</th><td>sneg<", places) is not None, "Luče (700 m): sneg")
check(re.search(r"Solčava \(560 m\)</th><td>dež s snegom<", places) is not None, "Solčava (560 m, nad mejo, a v pasu): dež s snegom")
# kratko: tri stanja v Rečici (366 m)
def kratko_for(line):
    d = json.loads(json.dumps(DATA)); d["snow_line"]["current_line_m"] = line
    return z.snow_line_kratko(d)
check("pada dež, ne sneg" in kratko_for(800), "kratko: meja 800 m → dež v Rečici")
check("pada dež s snegom" in kratko_for(400), "kratko: meja 400 m → dež s snegom v Rečici")
check("sneži tudi v Rečici" in kratko_for(200), "kratko: meja 200 m → sneži v Rečici")

# ── 5. hub ────────────────────────────────────────────────────────────────
HUB_DATA = None
try:
    hub_path = os.path.join(seo.ROOT, "data", "winter-data.json")
    HUB_DATA = json.load(open(hub_path, encoding="utf-8"))
except Exception:
    pass
if HUB_DATA:
    hub_body, hub_faq = z.build_hub_body(HUB_DATA)
    check("Zimske razmere: kaj iščete?" in hub_body, "hub: usmerjevalnik »kaj iščete«")
    for href in ("/zima/meja-snezenja/", "/zima/snezna-karta/", "/snegofili/", "/vreme-v-gorah/", "/zima/poledica/"):
        check(f'class="zima-finder"' in hub_body and f'href="{href}"' in hub_body, f"hub: povezava {href}")
    check(any("razlika med mejo sneženja" in q for q, _ in hub_faq), "hub FAQ: razlika meja / karta / Snegofili")

# ── 6. snežna karta ───────────────────────────────────────────────────────
kbody = k.build_body()
check("Kje bo snežilo in koliko snega bo zapadlo?" in kbody, "snežna karta: razdelek kje/koliko")
check('href="/zima/meja-snezenja/"' in kbody and 'href="/snegofili/"' in kbody, "snežna karta: povezavi na mejo in Snegofile")
kq = [q for q, _ in k.FAQ]
check("Kakšna je razlika med snežno karto in mejo sneženja?" in kq, "snežna karta FAQ: razmejitev od meje sneženja")
check("meja sneženja" not in k.DESC.lower(), "snežna karta: opis ne tekmuje za »meja sneženja«")

# ── 7. Snegofili ──────────────────────────────────────────────────────────
sq = [q for q, _ in sg.FAQ]
for q in ("Koliko snega je zdaj v Sloveniji?", "Kje trenutno sneži v Sloveniji?", "Kje bo največ novega snega?"):
    check(q in sq, f"Snegofili FAQ: {q}")
check("sneg v sloveniji" in sg.TITLE.lower(), "Snegofili: naslov vsebuje »sneg v Sloveniji«")
allfaq = " ".join(a for _, a in sg.FAQ)
check('href="/zima/meja-snezenja/"' in allfaq and 'href="/zima/snezna-karta/"' in allfaq, "Snegofili FAQ povezuje mejo sneženja in snežno karto")
check("<" not in " ".join(re.sub(r"<a [^>]*>|</a>", "", a) for _, a in sg.FAQ), "Snegofili FAQ: razen povezav brez »<« (izris brez ubeganja)")

# ── 8. Golte: blok samo iz svežega posnetka ───────────────────────────────
def snapshot(age_h, **over):
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=age_h)
    pt = {"id": "golte", "elevation_m": 1400, "past24_cm": 0.0, "next24_cm": 1.8, "next72_cm": 24.6, "snow_line_m": 800}
    pt.update(over)
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "tocke": [pt]}


def golte_with(data):
    old = g.SNEGOFILI_PATH
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        path = f.name
    try:
        g.SNEGOFILI_PATH = path
        return g.golte_snow_html()
    finally:
        g.SNEGOFILI_PATH = old
        os.unlink(path)


fresh = golte_with(snapshot(3))
check("Sneg na Golteh" in fresh and "25 cm" in fresh and "manj kot 1 cm" in fresh and "/snegofili/#t-golte" in fresh,
      "Golte: svež posnetek da blok (24 h nazaj < 1 cm, 72 h naprej 25 cm, povezava)")
check("ni meritev" in text_of(fresh) or "ne meritev" in text_of(fresh), "Golte: blok pove, da je model, ne meritev")
check(golte_with(snapshot(40)) == "", "Golte: posnetek starejši od 36 h → brez bloka")
check(golte_with(snapshot(3, next72_cm=None)) == "", "Golte: brez podatka → brez bloka")
check(golte_with({"generated_at": "2026-01-01T00:00:00Z", "tocke": []}) == "", "Golte: brez točke → brez bloka")
gq = [q for q, _ in g.FAQ]
check("Kakšno je vreme na Golteh?" in gq and "Ali je na Golteh sneg?" in gq, "vreme v gorah: FAQ o Golteh")
check("vreme golte" in g.TITLE.lower(), "vreme v gorah: naslov vodi z »Vreme Golte«")

# ── 8b. 0 m = »v nižinah«, ne »pri 0 m«; dateModified iz časa podatkov (28. 11. 2026) ──
check(z.line_phrase(0) == "v nižinah (0 m n. m. ali nižje)", "meja 0 m: »v nižinah«, ne »pri 0 m«")
check(z.line_phrase(-5).startswith("v nižinah"), "meja pod 0 m: »v nižinah«")
check(z.line_phrase(760) == "pri 760 m" and z.line_phrase(760, html=True) == "pri <strong>760 m n. m.</strong>",
      "meja nad 0 m: »pri N m«")
data0 = {"snow_line": {"current_line_m": 0, "forecast_24h_m": 228, "confidence": "srednja",
                       "expected_cm_by_elevation": [], "daily": []}}
check("pri <strong>0 m" not in z.snow_line_kratko(data0) and "v nižinah" in z.snow_line_kratko(data0),
      "»Na kratko« ob meji 0 m ne pravi »pri 0 m«")
check(z._dm({"generated_at": "2026-11-27T23:30:00+00:00"}) == "2026-11-28", "dateModified: lokalni datum nastanka podatkov")
check(z._dm({}) is None and z._dm(None) is None, "dateModified: brez podatka ga ni (ne ugibamo)")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_zima_page.py"), encoding="utf-8").read()
check(src.count("seo.webpage_schema(") == src.count("date_modified=_dm(data)"),
      "vsaka zimska stran iz generate_zima_page.py nosi dateModified")

# ── 9. notranjih meritev ni nikjer ────────────────────────────────────────
for name, html in (("meja sneženja", body), ("snežna karta", kbody)):
    check("indoor" not in html.lower() and "tempinf" not in html.lower(), f"{name}: brez notranjih meritev")

print(f"\n{fails} razhajanj" if fails else "\nzima SEO: 0 razhajanj")
sys.exit(1 if fails else 0)
