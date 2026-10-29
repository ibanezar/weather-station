#!/usr/bin/env python3
"""tools/generate_vreme_za_ribolov_page.py — /vreme-za-ribolov/: vreme za ribolov na Savinji (5 dni).
Stran ne meri vode (vodostaj: /vodostaj-savinje/) in ne svetuje o ribolovnem režimu; tlak je ribiško izročilo, ne dokaz."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datetime  # noqa: E402
import day_score_common as D  # noqa: E402
from day_score_common import bands, mean, rain_pts, storm_pts, wind_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402


def _prev(d, n):
    return (datetime.date.fromisoformat(d) - datetime.timedelta(days=n)).isoformat()


def day_fn(c, d):
    pts, det = {}, {}
    p_today = mean(c.vals("pressure_msl", d))
    p_prev = mean(c.vals("pressure_msl", _prev(d, 1)))
    dp = None if (p_today is None or p_prev is None) else p_today - p_prev
    pts["tlak"] = 0 if dp is None else min(bands(abs(dp), (2, 5, 8)), 2)
    det["tlak"] = f"tlak {'+' if dp >= 0 else '−'}{seo.num(abs(dp), 1)} hPa glede na včeraj" if dp is not None else "model ne vrača podatka"
    r48 = sum(c.vals("precipitation", d)) + sum(c.vals("precipitation", _prev(d, 1))) + sum(c.vals("precipitation", _prev(d, 2)))
    pts["dez48"] = bands(r48, (5, 15, 30))
    det["dez48"] = f"padavine zadnje 3 dni {seo.num(r48, 0)} mm"
    t3 = mean(c.vals("temperature_2m", d) + c.vals("temperature_2m", _prev(d, 1)) + c.vals("temperature_2m", _prev(d, 2)))
    pts["temp"] = 0 if t3 is None else (2 if (t3 < 4 or t3 >= 24) else 1 if (t3 < 8 or t3 >= 20) else 0)
    det["temp"] = f"zrak 3 dni povprečno {seo.num(t3, 0)} °C" if t3 is not None else "model ne vrača podatka"
    pts["veter"], det["veter"] = wind_pts(c, d, (15, 25, 35), (40, 55, 70), 6, 20)
    pts["dez"], det["dez"] = rain_pts(c, d, 6, 20, cap=2, sum_veto=2.0)
    pts["nevihta"], det["nevihta"] = storm_pts(c, d, 6, 21)
    return pts, det


CFG = {
    "url": "/vreme-za-ribolov/", "slug": "vreme-za-ribolov", "crumb": "Vreme za ribolov",
    "title": "Vreme za ribolov na Savinji: napoved za 5 dni",
    "h1": "Vreme za ribolov na Savinji: pogoji za 5 dni",
    "meta": "Tlak, dež, veter, temperatura in nevihte",
    "kicker": "Ribolov danes · Savinja in Zgornja Savinjska dolina",
    "levels": ["ugodno", "povprečno", "težavno", "odsvetovano"],
    "advice": [
        "Vreme je ugodno; vodostaj in barvo vode preverite sami.",
        "Povprečni pogoji; obrnite pozornost na vodostaj in veter.",
        "Pogoji so težavni (voda lahko narašča, motnost, veter); ravnajte previdno.",
        "Vreme ni primerno za ribolov; strela, naraščajoča voda ali neurje so nevarni.",
    ],
    "th": (2, 4, 7), "day_fn": day_fn, "hour_fn": None,
    "groups": [("Voda", "Voda (posredno iz vremena)", ["dez48", "temp"]), ("Zrak", "Zrak", ["tlak", "veter"]),
               ("Padavine", "Padavine in nevihte", ["dez", "nevihta"])],
    "group_icons": ["b", "a", "d"],
    "factors": [
        ("dez48", "Padavine zadnje 3 dni", "Veliko dežja pomeni višjo, hitrejšo in motnejšo vodo; to je približek, ne meritev vodostaja."),
        ("temp", "Temperatura zraka (3 dni)", "Zelo mrzla ali topla voda in zrak zmanjšata aktivnost rib; ocena je posredna, temperature vode ne poznamo."),
        ("tlak", "Zračni tlak (sprememba)", "Ribiško izročilo meni, da hitre spremembe tlaka vplivajo na grizenje; dokazov ni, zato ocena šteje največ 2 točki."),
        ("veter", "Veter", "Močan veter oteži metanje in varnost na bregu; prikazana je tudi prevladujoča smer."),
        ("dez", "Dež danes", "Dež vpliva na udobje in hitrost naraščanja vode; šteje največ 2 točki."),
        ("nevihta", "Nevihta", "Strela je nevarna ob vodi in z dolgo palico; nevihta je takoj izrazita ovira."),
    ],
    "rules": [
        ("Padavine 3 dni", "5 / 15 / 30 mm", "vsota današnjega in dveh prejšnjih dni"),
        ("Temperatura zraka 3 dni", "pod 8 ali nad 20 = 1, pod 4 ali nad 24 = 2", "povprečje"),
        ("Zračni tlak", "razlika dnevnih povprečij 2 / 5 / 8 hPa", "največ 2 točki (ribiško izročilo)"),
        ("Veter (6.–20. ure)", "15 / 25 / 35 km/h; sunki 40 / 55 / 70 km/h", "povprečje in sunki"),
        ("Dež danes", "verjetnost 20 / 40 / 60 %; ≥ 2 mm = 2", "največ 2 točki"),
        ("Nevihta", "napovedana = 3", "koda vremena ≥ 95"),
    ],
    "method_intro": "Ocena sešteje točke šestih dejavnikov (0–3 na dejavnik, manj je bolje). Raven: do 1 točke ugodno, 2–3 povprečno, 4–6 težavno, 7 ali več odsvetovano; izrazit dejavnik (3 točke) da vsaj »težavno«. Voda in ribe niso del modela.",
    "limits": ["<strong>Stran ne meri vode:</strong> vodostaj in pretok Savinje so na strani Vodostaj Savinje (ARSO); temperature vode ne poznamo.",
               "<strong>Ribolovni režim:</strong> dovoljenja, revirje, čas in količine določa ribiška družina; stran o tem ne svetuje."],
    "intro_q": "Kakšno vreme je dobro za ribolov na Savinji?",
    "intro_a": "Najbolj ugodno je stabilno, ne preveč vetrovno vreme brez neviht in brez izrazitih padavin v zadnjih dneh, ko voda ne narašča in ni motna.",
    "disclaimer_lead": "Ocena je pripomoček, ne ribiški ali varnostni nasvet.",
    "disclaimer": "Ob vodi upoštevajte opozorila ARSO in ribiške družine; ob nevihti in naraščajoči vodi se umaknite od brega.",
    "faq": [
        ("Ali zračni tlak res vpliva na grizenje rib?", "Ribiško izročilo to trdi, a dokazov ni zanesljivih. Zato stran tlaku daje največ 2 točki in ga ne uporablja kot veto."),
        ("Zakaj stran šteje dež zadnjih treh dni?", "Veliko padavin pomeni višji pretok in motnejšo vodo. To je približek; za dejansko stanje glejte vodostaj Savinje (ARSO)."),
        ("Ali stran pove, ali je voda varna?", "Ne. Nevarnost naraščanja vode in poplav ocenjujejo ARSO in Direkcija za vode; stran je samo vremenska ocena."),
        ("Kaj z dovoljenji in lovnimi pravili?", "Določa jih ribiška družina za vaš revir; stran o tem ne svetuje."),
    ],
    "links": [("/vodostaj-savinje/", "Vodostaj Savinje →"), ("/nevihte/", "Nevihte in opozorila ARSO →"),
              ("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Ribolov na Savinji danes: {lvl}. Tlak, dež zadnjih dni, veter in nevihte za 5 dni; vodo preverite na strani Vodostaj Savinje.",
}

if __name__ == "__main__":
    D.main(CFG)
