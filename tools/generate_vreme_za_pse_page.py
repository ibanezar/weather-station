#!/usr/bin/env python3
"""tools/generate_vreme_za_pse_page.py — /vreme-za-pse/: sprehod s psom (5 dni + okno po urah). Ni veterinarski nasvet."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
from day_score_common import bands, mean, rain_pts, storm_pts  # noqa: E402
import generate_seo_pages as seo  # noqa: E402


def heat_pts(a):
    return bands(a, (24, 28, 32))


def cold_pts(a):
    if a is None:
        return 0
    return 3 if a <= -15 else 2 if a <= -10 else 1 if a <= -5 else 0


def day_fn(c, d):
    pts, det = {}, {}
    amax = max(c.vals("apparent_temperature", d, 8, 19), default=None)
    pts["vrocina"] = heat_pts(amax)
    det["vrocina"] = f"občutena do {seo.num(amax, 0)} °C" if amax is not None else "model ne vrača podatka"
    tmax = max(c.vals("temperature_2m", d, 11, 17), default=None)
    sun = max(c.vals("shortwave_radiation", d, 11, 16), default=None)
    ph = 0
    if tmax is not None and sun is not None:
        ph = 3 if (tmax >= 30 and sun >= 600) else 2 if (tmax >= 25 and sun >= 500) else 1 if (tmax >= 22 and sun >= 300) else 0
    pts["asfalt"] = ph
    det["asfalt"] = (f"zrak do {seo.num(tmax, 0)} °C, sevanje do {seo.num(sun, 0)} W/m²" if tmax is not None and sun is not None else "model ne vrača podatka")
    amin = min(c.vals("apparent_temperature", d, 7, 20), default=None)
    pts["mraz"] = cold_pts(amin)
    det["mraz"] = f"občutena do {seo.num(amin, 0)} °C" if amin is not None else "model ne vrača podatka"
    pts["dez"], det["dez"] = rain_pts(c, d, 7, 20, cap=2, sum_veto=2.0)
    pts["nevihta"], det["nevihta"] = storm_pts(c, d, 7, 21)
    return pts, det


def hour_fn(c, h):
    a = c.at("apparent_temperature", h)
    prob = c.at("precipitation_probability", h) or 0
    s = 0
    if a is not None:
        s = max(heat_pts(a), cold_pts(a))
    s = max(s, 1 if prob >= 60 else 0)
    if (c.at("weather_code", h) or 0) >= 95:
        s = 3
    return s


CFG = {
    "url": "/vreme-za-pse/", "slug": "vreme-za-pse", "crumb": "Vreme za sprehod s psom",
    "short": "Sprehod s psom",
    "title": "Vreme za sprehod s psom: napoved za 5 dni",
    "h1": "Vreme za sprehod s psom: kdaj na pot",
    "meta": "Vročina, asfalt, mraz, dež in nevihte",
    "kicker": "Sprehod s psom danes · Zgornja Savinjska dolina",
    "levels": ["odlično", "dobro", "previdno", "odsvetovano"],
    "advice": [
        "Odlični pogoji za dolg sprehod.",
        "Dobri pogoji; v hladnejših ali toplejših urah pazite na psa.",
        "Previdnost: sprehod prestavite na ugodnejši del dneva in skrajšajte.",
        "Pogoji niso primerni za dolg sprehod; pes naj bo čim manj zunaj.",
    ],
    "th": (2, 4, 6), "day_fn": day_fn, "hour_fn": hour_fn,
    "groups": [("Vročina", "Vročina", ["vrocina", "asfalt"]), ("Mraz", "Mraz", ["mraz"]),
               ("Vreme", "Dež in nevihte", ["dez", "nevihta"])],
    "group_icons": ["c", "d", "b"],
    "factors": [
        ("vrocina", "Občutena vročina", "Psi se slabše ohlajajo (hlapijo samo z jezikom), zato je vročina zanje hitreje nevarna."),
        ("asfalt", "Vroč asfalt", "Sončen asfalt je lahko bistveno bolj vroč od zraka in opeče blazinice; to je ocena iz temperature in sevanja, ne meritev."),
        ("mraz", "Mrzla občutena temperatura", "Kratkodlaki, majhni, stari in mladi psi mraz občutijo prej; prag velja za zdrave odrasle pse srednje velikosti."),
        ("dez", "Dež", "Mokra dlaka ohladi; šteje največ 2 točki."),
        ("nevihta", "Nevihta", "Strela je nevarna, mnogi psi se nevihte tudi bojijo; nevihta je takoj izrazita ovira."),
    ],
    "rules": [
        ("Občutena vročina (8.–19. ure)", "24 / 28 / 32 °C", "najvišja občutena"),
        ("Vroč asfalt", "zrak ≥ 22 °C in sevanje ≥ 300 / 25 °C in 500 / 30 °C in 600 W/m²", "11.–17. ure"),
        ("Mraz (7.–20. ure)", "≤ −5 / −10 / −15 °C", "najnižja občutena"),
        ("Dež (7.–20. ure)", "verjetnost 20 / 40 / 60 %; ≥ 2 mm = 2", "največ 2 točki"),
        ("Nevihta", "napovedana = 3", "koda vremena ≥ 95"),
    ],
    "method_intro": "Ocena sešteje točke petih dejavnikov (0–3 na dejavnik, manj je bolje). Raven: do 1 točke odlično, 2–3 dobro, 4–5 previdno, 6 ali več odsvetovano; izrazit dejavnik (3 točke) da vsaj »previdno«. Pragovi veljajo za zdrave odrasle pse in so splošna ocena.",
    "limits": ["<strong>Pasma, starost in zdravje:</strong> ravno kratkodlaki, brahicefalni (sploščeni obraz), starejši, mladi in bolni psi so občutljivejši kot kaže ocena.",
               "<strong>Temperatura tal</strong> je ocena iz zraka in sevanja; prosto preverite z dlanjo, ki jo za 5 sekund položite na tla."],
    "intro_q": "Kdaj je primeren čas za sprehod s psom?",
    "intro_a": "Zmerna temperatura brez izrazite vročine, mraza in neviht; poleti zgodaj zjutraj ali pozno zvečer, pozimi sredi dneva.",
    "disclaimer_lead": "Ocena je pripomoček, ne veterinarski nasvet.",
    "disclaimer": "Ob znakih pregrevanja (težko dihanje, ohlapnost, bruhanje) ali podhladitve pokličite veterinarja.",
    "window_label": "Najboljši čas za sprehod", "window_none": "Danes ni zelo ugodnega časa za dolg sprehod.",
    "strip_title": "Čas za sprehod po urah", "strip_intro": "Ocena po urah od 6.00 do 22.00.",
    "faq": [
        ("Pri kateri temperaturi je prevroče za psa?", "Občutljivi psi trpijo že od približno 24–25 °C občutene temperature, pri 32 °C in več je nevarno za vse; pomembni so še senca, voda in vlaga."),
        ("Zakaj je asfalt posebej omenjen?", "Sončni asfalt je lahko veliko bolj vroč kot zrak in opeče blazinice. Stran oceni tveganje iz temperature in sevanja; preverite z dlanjo."),
        ("Je mraz nevaren za pse?", "Pri zdravih psih srednje velikosti običajno šele pod približno −5 °C občutene temperature; kratkodlaki, majhni in stari psi prej."),
        ("Ali ocena velja za mačke in drugo?", "Ne, namenjena je sprehodom s psi."),
    ],
    "links": [("/vreme-recica-ob-savinji/", "Vreme Rečica ob Savinji →"), ("/biovreme/", "Biovreme →"),
              ("/vreme-za-kolesarje/", "Vreme za kolesarje →"), ("https://www.arso.gov.si/", "ARSO")],
    "desc": lambda lvl: f"Sprehod s psom danes: {lvl}. Vročina, asfalt, mraz, dež in nevihte za 5 dni ter najboljši čas za sprehod v Rečici ob Savinji.",
}

if __name__ == "__main__":
    D.main(CFG)
