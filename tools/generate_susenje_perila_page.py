#!/usr/bin/env python3
"""tools/generate_susenje_perila_page.py — /susenje-perila/: kdaj se perilo na prostem posuši (5 dni + okno po urah).
Konfiguracija za day_score_common.py; samo modelska napoved Open-Meteo, brez meritev postaje."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, bands_desc, mean, rain_pts, wind_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402


def day_fn(c, d):
    pts, det = {}, {}
    pts["dez"], det["dez"] = rain_pts(c, d, 8, 18)
    rh = mean(c.vals("relative_humidity_2m", d, 8, 18))
    pts["vlaga"] = bands(rh, (60, 75, 88))
    det["vlaga"] = f"vlaga povprečno {seo.num(rh, 0)} %" if rh is not None else "model ne vrača podatka"
    t = mean(c.vals("temperature_2m", d, 8, 18))
    pts["temp"] = bands_desc(t, (18, 10, 3))
    det["temp"] = f"temperatura povprečno {seo.num(t, 0)} °C" if t is not None else "model ne vrača podatka"
    pts["veter"], det["veter"] = wind_pts(c, d, (10, 10, 10), (40, 50, 60))
    # premalo vetra je slabo za sušenje (obratno kot pri ostalih): točke po povprečju
    w = mean(c.vals("wind_speed_10m", d, 8, 18))
    gust = max(c.vals("wind_gusts_10m", d, 8, 18), default=None)
    pts["veter"] = max(bands_desc(w, (10, 5, 0)) if w is not None and w < 5 else 0, 3 if (gust or 0) >= 50 else 2 if (gust or 0) >= 40 else 0,
                       1 if (w is not None and 5 <= w < 10) else 0)
    sun = mean(c.vals("shortwave_radiation", d, 9, 16))
    pts["sonce"] = min(bands_desc(sun, (300, 150, 0)), 2)
    det["sonce"] = f"sončno sevanje povprečno {seo.num(sun, 0)} W/m²" if sun is not None else "model ne vrača podatka"
    return pts, det


def hour_fn(c, h):
    prob = c.at("precipitation_probability", h) or 0
    pr = c.at("precipitation", h) or 0
    rh = c.at("relative_humidity_2m", h)
    t = c.at("temperature_2m", h)
    g = c.at("wind_gusts_10m", h) or 0
    s = 0
    if prob >= 50 or pr >= 0.1:
        s = 3
    elif prob >= 30:
        s = 2
    if rh is not None:
        s = max(s, 2 if rh >= 88 else 1 if rh >= 75 else 0)
    if t is not None and t < 3:
        s = max(s, 2)
    if g >= 50:
        s = 3
    return s


CFG = {
    "url": "/susenje-perila/", "slug": "susenje-perila", "crumb": "Sušenje perila",
    "title": "Sušenje perila na prostem: napoved za 5 dni",
    "h1": "Sušenje perila na prostem: kdaj se bo posušilo",
    "meta": "Dež, vlaga, temperatura, veter in sonce",
    "kicker": "Sušenje perila danes · Zgornja Savinjska dolina",
    "levels": ["odlično", "dobro", "slabo", "neprimerno"],
    "advice": [
        "Perilo se bo hitro posušilo, razobesite ga zjutraj.",
        "Perilo se bo posušilo, a počasneje; razobesite ga čim prej.",
        "Sušenje bo počasno ali tvegano; razmislite o sušenju v zaprtem prostoru.",
        "Na prostem se perilo ne bo posušilo ali ga bo zmočilo; sušite v zaprtem prostoru.",
    ],
    "th": (2, 5, 8),
    "day_fn": day_fn, "hour_fn": hour_fn,
    "groups": [("Padavine", "Padavine", ["dez"]), ("Zrak", "Zrak in veter", ["vlaga", "veter"]),
               ("Toplota", "Toplota in sonce", ["temp", "sonce"])],
    "group_icons": ["b", "a", "c"],
    "factors": [
        ("dez", "Dež", "Moker zrak in dež perilo zmočita; že blage padavine lahko uničijo sušenje."),
        ("vlaga", "Zračna vlaga", "Vlažen zrak sprejme malo vlage iz tkanine, zato se perilo suši počasi."),
        ("veter", "Veter", "Veter odnaša vlago in pospeši sušenje; premočni sunki perilo odnesejo ali zapraskajo."),
        ("temp", "Temperatura", "Toplejši zrak sprejme več vlage; ob ničli se perilo lahko le zmrzne."),
        ("sonce", "Sonce", "Sonce pospeši sušenje, a ni nujno; ocena je omejena na 2 točki."),
    ],
    "rules": [
        ("Dež (8.–18. ure)", "verjetnost 20 / 40 / 60 % ali ≥ 0,5 mm = 3", "najvišja verjetnost in vsota"),
        ("Zračna vlaga (povprečje)", "60 / 75 / 88 %", "dnevno povprečje čez dan"),
        ("Temperatura (povprečje)", "pod 18 / 10 / 3 °C", "povprečje čez dan"),
        ("Veter", "pod 10 km/h = 1, pod 5 km/h = 2; sunki ≥ 40 / 50 km/h = 2 / 3", "premalo in preveč vetra sta slaba"),
        ("Sonce", "pod 300 / 150 W/m²", "največ 2 točki"),
    ],
    "method_intro": "Ocena sešteje točke petih dejavnikov (0–3 na dejavnik, manj je bolje). Raven: do 1 točke odlično, 2–4 dobro, 5–7 slabo, 8 ali več neprimerno; izrazit dejavnik (3 točke) da vsaj »slabo«. Pragovi so naša ocena, ne fizikalni izračun sušenja.",
    "limits": ["<strong>Sušenje je odvisno tudi od tkanine in debeline</strong> (težke žimke, jopice), ki jih model ne pozna.",
               "<strong>Jutranja rosa in megla</strong> v dolini sta lahko izrazitejši, kot jo vidi model."],
    "intro_q": "Kdaj je dobro sušiti perilo na prostem?",
    "intro_a": "Najbolje je ob suhem, vetrovnem in toplem vremenu z nizko zračno vlago; dež in vlaga nad približno 85 % sušenje onemogočita.",
    "disclaimer_lead": "Ocena sušenja je pripomoček.",
    "disclaimer": "Temelji na modelski napovedi in ne upošteva vaše lege ali sence; pred odhodom od doma preverite še nebo.",
    "window_label": "Najboljše okno za sušenje", "window_none": "Ni zanesljivega okna za sušenje na prostem.",
    "strip_title": "Okno za sušenje po urah",
    "strip_intro": "Ocena po urah od 6.00 do 22.00.",
    "faq": [
        ("Kako dolgo se perilo suši na prostem?", "Odvisno od vlage, vetra in tkanine; ob suhem toplem vetrovnem vremenu običajno nekaj ur, ob vlagi nad 80 % pa pogosto ni mogoče. Stran ocenjuje pogoje, ne trajanja."),
        ("Ali se perilo suši pozimi?", "Ob temperaturah pod ničlo perilo zmrzne in se počasi osuši (izparevanje). Ocena zato ob nizkih temperaturah doda točke."),
        ("Zakaj je premalo vetra slabo?", "Brez vetra se okoli perila nabira vlažen zrak in sušenje se upočasni; blag veter ga odnaša."),
        ("Je ocena merjena na postaji?", "Ne. Podatki so modelska napoved Open-Meteo za Rečico ob Savinji; postaja Meteorec te ocene ne vodi."),
    ],
    "links": [("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("/vreme-za-kolesarje/", "Vreme za kolesarje →"),
              ("/biovreme/", "Biovreme →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Sušenje perila na prostem danes: {lvl}. Dež, vlaga, veter in sonce za 5 dni ter najboljše okno po urah v Rečici ob Savinji.",
}

if __name__ == "__main__":
    D.main(CFG)
