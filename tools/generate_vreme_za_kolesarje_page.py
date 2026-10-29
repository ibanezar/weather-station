#!/usr/bin/env python3
"""tools/generate_vreme_za_kolesarje_page.py — /vreme-za-kolesarje/: kolesarjenje po Savinjski dolini (5 dni + okno po urah)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, mean, rain_pts, storm_pts, wind_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402


def temp_pts(t):
    if t is None:
        return 0
    if t < 0 or t >= 34:
        return 3
    if t < 5 or t >= 30:
        return 2
    if t < 12 or t >= 26:
        return 1
    return 0


def day_fn(c, d):
    pts, det = {}, {}
    pts["dez"], det["dez"] = rain_pts(c, d, 8, 19)
    pts["nevihta"], det["nevihta"] = storm_pts(c, d)
    pts["veter"], det["veter"] = wind_pts(c, d, (12, 20, 30), (45, 60, 75), 8, 19)
    t = mean(c.vals("apparent_temperature", d, 9, 18))
    pts["temp"] = temp_pts(t)
    det["temp"] = f"občutena temperatura povprečno {seo.num(t, 0)} °C" if t is not None else "model ne vrača podatka"
    tm = min(c.vals("temperature_2m", d, 6, 11), default=None)
    pts["poledica"] = 0 if tm is None else 3 if tm <= -2 else 2 if tm <= 1 else 1 if tm <= 3 else 0
    det["poledica"] = f"jutro najnižje {seo.num(tm, 0)} °C" if tm is not None else "model ne vrača podatka"
    uv = max(c.vals("uv_index", d, 9, 17), default=None)
    pts["uv"] = 0 if uv is None else min(bands(uv, (5, 8, 99)), 2)
    det["uv"] = f"UV indeks do {seo.num(uv, 0)}" if uv is not None else "model ne vrača podatka"
    return pts, det


def hour_fn(c, h):
    prob = c.at("precipitation_probability", h) or 0
    pr = c.at("precipitation", h) or 0
    g = c.at("wind_speed_10m", h) or 0
    t = c.at("apparent_temperature", h)
    s = 3 if (prob >= 60 or pr >= 0.3) else 2 if prob >= 40 else 1 if prob >= 20 else 0
    s = max(s, 3 if g >= 40 else 2 if g >= 25 else 1 if g >= 15 else 0)
    if t is not None:
        s = max(s, temp_pts(t))
    if (c.at("weather_code", h) or 0) >= 95:
        s = 3
    return s


CFG = {
    "url": "/vreme-za-kolesarje/", "slug": "vreme-za-kolesarje", "crumb": "Vreme za kolesarje",
    "title": "Vreme za kolesarje: napoved za 5 dni",
    "h1": "Vreme za kolesarje: kdaj je dobro kolesariti",
    "meta": "Dež, veter, temperatura, poledica in UV",
    "kicker": "Kolesarjenje danes · Zgornja Savinjska dolina",
    "levels": ["odlično", "dobro", "zahtevno", "neprimerno"],
    "advice": [
        "Odlični pogoji za kolesarjenje.",
        "Dobri pogoji; oblecite se po temperaturi in veter vzemite v poštev.",
        "Zahtevni pogoji; skrajšajte pot ali jo prestavite na boljši čas dneva.",
        "Pogoji so neprimerni za kolesarjenje, izberite drug dan.",
    ],
    "th": (2, 5, 8), "day_fn": day_fn, "hour_fn": hour_fn,
    "groups": [("Padavine", "Padavine in nevihte", ["dez", "nevihta"]), ("Veter", "Veter", ["veter"]),
               ("Temperatura", "Temperatura", ["temp", "poledica"]), ("Sonce", "Sonce", ["uv"])],
    "group_icons": ["b", "a", "d", "c"],
    "factors": [
        ("dez", "Dež", "Mokra cesta podaljša zavorno pot in hitro ohladi."),
        ("nevihta", "Nevihta", "Strela in močan veter na odprti cesti sta nevarna; nevihta je takoj izrazita ovira."),
        ("veter", "Veter", "Čelni veter močno poveča napor; sunki ogrozijo stabilnost. Prikazana je tudi prevladujoča smer."),
        ("temp", "Občutena temperatura", "Prijetno območje je približno 12–26 °C; mraz in vročina povečata obremenitev."),
        ("poledica", "Poledica zjutraj", "Pri temperaturi okoli ničle je cesta lahko spolzka, še posebej v senci in na mostovih."),
        ("uv", "UV sevanje", "Visok UV zahteva zaščito; ocena je omejena na 2 točki."),
    ],
    "rules": [
        ("Dež (8.–19. ure)", "verjetnost 20 / 40 / 60 % ali ≥ 0,5 mm = 3", "najvišja verjetnost in vsota"),
        ("Nevihta", "napovedana = 3", "koda vremena ≥ 95"),
        ("Veter", "12 / 20 / 30 km/h; sunki 45 / 60 / 75 km/h", "povprečje in sunki"),
        ("Občutena temperatura", "pod 12 ali nad 26 = 1, pod 5 ali nad 30 = 2, pod 0 ali nad 34 = 3", "povprečje 9.–18. ure"),
        ("Poledica zjutraj", "≤ 3 / ≤ 1 / ≤ −2 °C", "najnižja 6.–11. ure"),
        ("UV", "5 / 8", "največ 2 točki"),
    ],
    "method_intro": "Ocena sešteje točke šestih dejavnikov (0–3 na dejavnik, manj je bolje). Raven: do 1 točke odlično, 2–4 dobro, 5–7 zahtevno, 8 ali več neprimerno; izrazit dejavnik (3 točke) da vsaj »zahtevno«. Pragovi so naša splošna ocena, ne prilagojena vaši kondiciji ali kolesu.",
    "limits": ["<strong>Terenske razlike:</strong> v ozki dolini veter in mraz sledita terenu; hladen zrak se zbira na dnu doline.",
               "<strong>Smer vetra</strong> je povprečje čez dan; ob poti se lahko spreminja z doline."],
    "intro_q": "Kdaj je dobro kolesariti po Savinjski dolini?",
    "intro_a": "Najboljši so suhi dnevi z blagim vetrom in občuteno temperaturo med približno 12 in 26 °C; dež, močan veter, poledica in nevihte kolesarjenje otežijo ali onemogočijo.",
    "disclaimer_lead": "Ocena je pripomoček, ne varnostna garancija.",
    "disclaimer": "Za tvegane in dolge ture upoštevajte še uradne napovedi in opozorila ARSO ter svojo izkušnjo.",
    "window_label": "Najboljše okno za kolesarjenje", "window_none": "Danes ni dobrega okna za kolesarjenje.",
    "strip_title": "Okno za kolesarjenje po urah", "strip_intro": "Ocena po urah od 6.00 do 22.00.",
    "faq": [
        ("Kakšen veter je še primeren za kolesarjenje?", "Do približno 12 km/h je blag, do 20 km/h zmeren, nad 30 km/h pa že občutno otežuje vožnjo, zlasti čelni veter in sunki."),
        ("Zakaj je omenjena poledica zjutraj?", "Pri temperaturah okoli ničle je lahko cesta spolzka že pri plusnih vrednostih zraka. Ocena je približek po najnižji jutranji temperaturi."),
        ("Je smer vetra pomembna?", "Da, čelni veter je bolj naporen kot bočni ali hrbtni. Stran pove prevladujočo smer čez dan, ne pa lokalnih sprememb ob poti."),
        ("Ali ocena velja za gorsko kolesarjenje?", "Ne. Podatki so za dno doline; na višinah so veter, mraz in padavine lahko drugačni."),
    ],
    "links": [("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("/susenje-perila/", "Sušenje perila →"),
              ("/vreme-v-gorah/", "Vreme v gorah →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Kolesarjenje po Savinjski dolini danes: {lvl}. Dež, veter, temperatura, poledica in UV za 5 dni ter najboljše okno po urah.",
}

if __name__ == "__main__":
    D.main(CFG)
