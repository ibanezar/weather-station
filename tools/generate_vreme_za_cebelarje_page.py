#!/usr/bin/env python3
"""tools/generate_vreme_za_cebelarje_page.py — /vreme-za-cebelarje/: letalni pogoji čebel in delo ob panjih (5 dni + okno po urah).
Splošen približek (čebele letijo od približno 10–12 °C); ni strokovni nasvet o čebelarjenju."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, bands_desc, mean, rain_pts, storm_pts, wind_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402


def day_fn(c, d):
    pts, det = {}, {}
    tmax = max(c.vals("temperature_2m", d, 10, 16), default=None)
    pts["temp"] = bands_desc(tmax, (16, 12, 8))
    det["temp"] = f"popoldne do {seo.num(tmax, 0)} °C" if tmax is not None else "model ne vrača podatka"
    sun = mean(c.vals("shortwave_radiation", d, 10, 15))
    pts["sonce"] = min(bands_desc(sun, (400, 200, 0)), 2)
    det["sonce"] = f"sončno sevanje povprečno {seo.num(sun, 0)} W/m²" if sun is not None else "model ne vrača podatka"
    pts["veter"], det["veter"] = wind_pts(c, d, (12, 20, 28), (35, 45, 55), 9, 17)
    pts["dez"], det["dez"] = rain_pts(c, d, 9, 17, sum_veto=0.3)
    pts["nevihta"], det["nevihta"] = storm_pts(c, d, 9, 19)
    return pts, det


def hour_fn(c, h):
    t = c.at("temperature_2m", h)
    w = c.at("wind_speed_10m", h) or 0
    prob = c.at("precipitation_probability", h) or 0
    pr = c.at("precipitation", h) or 0
    s = 0
    if t is not None:
        s = 3 if t < 8 else 2 if t < 12 else 1 if t < 15 else 0
    s = max(s, 3 if w >= 25 else 2 if w >= 18 else 1 if w >= 12 else 0)
    s = max(s, 3 if (pr >= 0.2 or prob >= 60) else 1 if prob >= 30 else 0)
    if (c.at("weather_code", h) or 0) >= 95:
        s = 3
    return s


CFG = {
    "url": "/vreme-za-cebelarje/", "slug": "vreme-za-cebelarje", "crumb": "Vreme za čebelarje",
    "short": "Vreme za čebelarje",
    "title": "Vreme za čebelarje: letalni pogoji za 5 dni",
    "h1": "Vreme za čebelarje: letalni pogoji čebel",
    "meta": "Temperatura, sonce, veter, dež in nevihte",
    "kicker": "Letalni pogoji čebel danes · Zgornja Savinjska dolina",
    "levels": ["odlični", "dobri", "omejeni", "brez letanja"],
    "advice": [
        "Čebele bodo dobro letele; ugodno za delo ob panjih.",
        "Letenje bo dobro, a ne povsem ugodno; delo ob panjih opravite v toplejših urah.",
        "Letenje bo omejeno; odpiranju panjev se izogibajte, če ni nujno.",
        "Čebele skoraj ne bodo letele; panjev ne odpirajte.",
    ],
    "th": (2, 5, 8), "day_fn": day_fn, "hour_fn": hour_fn,
    "groups": [("Toplota", "Toplota in sonce", ["temp", "sonce"]), ("Veter", "Veter", ["veter"]),
               ("Padavine", "Padavine in nevihte", ["dez", "nevihta"])],
    "group_icons": ["c", "a", "b"],
    "factors": [
        ("temp", "Najvišja temperatura", "Čebele običajno začnejo leteti pri približno 10–12 °C; pod tem letijo malo ali nič."),
        ("sonce", "Sonce", "Sonce pospeši aktivnost in delovanje cvetov; ocena je omejena na 2 točki."),
        ("veter", "Veter", "Močan veter ovira let in zahteva več energije; prikazana je tudi prevladujoča smer."),
        ("dez", "Dež", "Med dežjem čebele ne letijo; že blage padavine upočasnijo pašo."),
        ("nevihta", "Nevihta", "Pred nevihto in med njo so čebele lahko bolj vznemirjene; delo ob panjih je tvegano."),
    ],
    "rules": [
        ("Najvišja temperatura (10.–16. ure)", "pod 16 / 12 / 8 °C", "točke po nižjem maksimumu"),
        ("Sonce (10.–15. ure)", "pod 400 / 200 W/m²", "največ 2 točki"),
        ("Veter (9.–17. ure)", "12 / 20 / 28 km/h; sunki 35 / 45 / 55 km/h", "povprečje in sunki"),
        ("Dež (9.–17. ure)", "verjetnost 20 / 40 / 60 % ali ≥ 0,3 mm = 3", "najvišja verjetnost in vsota"),
        ("Nevihta", "napovedana = 3", "koda vremena ≥ 95"),
    ],
    "method_intro": "Ocena sešteje točke petih dejavnikov (0–3 na dejavnik, manj je bolje). Raven: do 1 točke odlični, 2–4 dobri, 5–7 omejeni, 8 ali več brez letanja; izrazit dejavnik (3 točke) da vsaj »omejeni«. Pragovi so splošen približek za medonosno čebelo, ne zamenjava za izkušnje čebelarja.",
    "limits": ["<strong>Čebelja družina, pasma in letni čas</strong> vplivajo na prag letenja; zgodaj spomladi in pozno jeseni so družine občutljivejše.",
               "<strong>Paša (cvetenje, medenje)</strong> ni del ocene; stran meri samo vreme, ne ponudbe nektarja."],
    "intro_q": "Kdaj čebele letijo in kdaj je primerno delo ob panjih?",
    "intro_a": "Čebele običajno letijo pri približno 10–12 °C in več, ob sončnem, suhem in zmerno vetrovnem vremenu; dež, mraz in močan veter let močno omejijo.",
    "disclaimer_lead": "Ocena je pripomoček, ne strokovni čebelarski nasvet.",
    "disclaimer": "Za zdravljenje čebel, krmljenje in odločitve o panjih upoštevajte navodila čebelarske zveze in veterinarja.",
    "window_label": "Najboljše okno za delo ob panjih", "window_none": "Danes ni dobrega okna za delo ob panjih.",
    "strip_title": "Okno za letenje po urah", "strip_intro": "Ocena po urah od 6.00 do 22.00.",
    "faq": [
        ("Pri kateri temperaturi čebele letijo?", "Običajno od približno 10–12 °C, s polno aktivnostjo od okoli 16 °C; natančen prag je odvisen od družine in sezone."),
        ("Ali čebele letijo v dežju?", "Ne, med dežjem večinoma ostanejo v panju; blage padavine paše močno zmanjšajo."),
        ("Kdaj je primerno odpirati panje?", "Najbolje ob toplem, mirnem in suhem vremenu čez dan; ob mrazu, vetru in pred nevihto odpiranja po možnosti odložite."),
        ("Ali stran svetuje glede zdravljenja čebel?", "Ne. Stran ocenjuje samo vreme; navodila za zdravljenje in krmljenje so naloga čebelarske organizacije in veterinarja."),
    ],
    "links": [("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("/agrometeo/", "Agrometeo →"),
              ("/vreme-za-kolesarje/", "Vreme za kolesarje →"), ("https://www.czs.si/", "Čebelarska zveza Slovenije")],
    "desc": lambda lvl: f"Letalni pogoji čebel danes: {lvl}. Temperatura, sonce, veter, dež in nevihte za 5 dni ter okno za delo ob panjih v Rečici ob Savinji.",
}

if __name__ == "__main__":
    D.main(CFG)
