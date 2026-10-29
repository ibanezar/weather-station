#!/usr/bin/env python3
"""Test strani »vreme za …« (day_score_common.py + 5 konfiguracij): pragovi, veto, okno, izris. Brez omrežja."""
import datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import day_score_common as D  # noqa: E402
import generate_susenje_perila_page as P1  # noqa: E402
import generate_vreme_za_kolesarje_page as P2  # noqa: E402
import generate_vreme_za_cebelarje_page as P3  # noqa: E402
import generate_vreme_za_ribolov_page as P4  # noqa: E402
import generate_vreme_za_pse_page as P5  # noqa: E402

fails = []


def check(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


TODAY = datetime.date(2026, 6, 10)
CFGS = [P1.CFG, P2.CFG, P3.CFG, P4.CFG, P5.CFG]


def synth(**o):
    """Urni podatki za 7 dni (2 pretekla + 5 napovedanih), vsak dan enak; o = vrednosti za ves čas."""
    base = dict(temperature_2m=20, apparent_temperature=20, relative_humidity_2m=50, dew_point_2m=9, wind_speed_10m=12,
                wind_gusts_10m=20, wind_direction_10m=180, precipitation=0, precipitation_probability=0, weather_code=1,
                pressure_msl=1015, shortwave_radiation=450, uv_index=4, cloud_cover=20)
    base.update(o)
    times = []
    for i in range(-2, 5):
        d = TODAY + datetime.timedelta(days=i)
        times += [f"{d.isoformat()}T{h:02d}:00" for h in range(24)]
    return D.Ctx({"time": times, **{k: [v] * len(times) for k, v in base.items()}})


# ── pomočniki ──
check("tocke: sklanjatev", [D.tocke(n) for n in (1, 2, 3, 4, 5, 11, 12, 21, 22, 0)] ==
      ["1 točka", "2 točki", "3 točke", "4 točke", "5 točk", "11 točk", "12 točk", "21 točk", "22 točk", "0 točk"])
check("bands: meje navzgor", [D.bands(v, (10, 20, 30)) for v in (9.9, 10, 19.9, 20, 29.9, 30)] == [0, 1, 1, 2, 2, 3])
check("bands_desc: meje navzdol", [D.bands_desc(v, (18, 10, 3)) for v in (18, 17.9, 10, 9.9, 3, 2.9)] == [0, 1, 1, 2, 2, 3])
check("brez podatka = 0 točk", D.bands(None, (1, 2, 3)) == 0 and D.bands_desc(None, (3, 2, 1)) == 0)
check("raven: meje vsote", [D.level_index(s, 1, (2, 5, 8)) for s in (1, 2, 4, 5, 7, 8)] == [0, 1, 1, 2, 2, 3])
check("veto: 3 točke dajo vsaj raven 2", D.level_index(3, 3, (2, 5, 8)) == 2 and D.level_index(9, 3, (2, 5, 8)) == 3)
check("compass", [D.compass(x) for x in (0, 44, 90, 200, 359)] == ["S", "SV", "V", "J", "S"])
check("prevladujoča smer ob enakih vetrovih", abs(D.mean_dir([90, 90], [10, 10]) - 90) < 1e-6)
check("okno: najdaljše zaporedje, ob izenačenju prvo",
      D.best_window([(8, 0), (9, 1), (10, 3), (11, 0), (12, 0), (13, 0), (14, 3)]) == (11, 13)
      and D.best_window([(8, 0), (9, 0), (10, 3), (11, 0), (12, 0)]) == (8, 9))
check("okno: premalo zaporednih ur / vrzel / brez podatka",
      D.best_window([(8, 0), (10, 0)]) is None and D.best_window([(8, 0), (9, None), (10, 0)]) is None
      and D.best_window([(8, 3), (9, 2)]) is None)
check("zapis okna", D.fmt_hours(11, 13) == "11.00–14.00")

# ── dobri in slabi dnevi po straneh ──
good = {c["slug"]: D.build_days(c, synth(), TODAY)[0] for c in CFGS}
check("suh topel dan: perilo ≤ dobro", good["susenje-perila"]["lvl"] <= 1)
check("suh topel dan: kolesarji odlično/dobro", good["vreme-za-kolesarje"]["lvl"] <= 1)
check("suh topel dan: čebelarji odlično/dobro", good["vreme-za-cebelarje"]["lvl"] <= 1)
check("stabilno brez dežja: ribolov ugodno/povprečno", good["vreme-za-ribolov"]["lvl"] <= 1)
check("topel dan: pes odlično/dobro", good["vreme-za-pse"]["lvl"] <= 1)

storm = dict(precipitation=2, precipitation_probability=95, weather_code=95, relative_humidity_2m=97, wind_speed_10m=35,
             wind_gusts_10m=70, temperature_2m=9, apparent_temperature=6, shortwave_radiation=20)
for c in CFGS:
    d = D.build_days(c, synth(**storm), TODAY)[0]
    check(f"nevihta in dež: {c['slug']} vsaj raven 2", d["lvl"] >= 2)

check("perilo: dež ≥ 0,5 mm = veto", D.build_days(P1.CFG, synth(precipitation=0.6, precipitation_probability=0), TODAY)[0]["pts"]["dez"] == 3)
check("perilo: premalo vetra je slabo", D.build_days(P1.CFG, synth(wind_speed_10m=2), TODAY)[0]["pts"]["veter"] == 2)
check("perilo: sonce največ 2", max(D.build_days(P1.CFG, synth(shortwave_radiation=0), TODAY)[0]["pts"]["sonce"], 0) == 2)
check("perilo: zmrzal = 3 za temperaturo", D.build_days(P1.CFG, synth(temperature_2m=-3), TODAY)[0]["pts"]["temp"] == 3)
check("kolesarji: poledica zjutraj −3 °C = 3", D.build_days(P2.CFG, synth(temperature_2m=-3), TODAY)[0]["pts"]["poledica"] == 3)
check("kolesarji: UV največ 2", D.build_days(P2.CFG, synth(uv_index=12), TODAY)[0]["pts"]["uv"] == 2)
check("čebelarji: pod 8 °C = 3 točke", D.build_days(P3.CFG, synth(temperature_2m=5), TODAY)[0]["pts"]["temp"] == 3)
check("ribolov: tlak in dež največ 2 točki",
      D.build_days(P4.CFG, synth(pressure_msl=900, precipitation=5), TODAY)[0]["pts"]["dez"] <= 2
      and max(D.build_days(P4.CFG, synth(), TODAY)[0]["pts"]["tlak"], 0) <= 2)
check("ribolov: padavine 3 dni se seštevajo", D.build_days(P4.CFG, synth(precipitation=1), TODAY)[0]["pts"]["dez48"] >= 2)
check("pes: vročina 33 °C občutena = 3", D.build_days(P5.CFG, synth(apparent_temperature=33), TODAY)[0]["pts"]["vrocina"] == 3)
check("pes: vroč asfalt ob 31 °C in 700 W/m²",
      D.build_days(P5.CFG, synth(temperature_2m=31, shortwave_radiation=700), TODAY)[0]["pts"]["asfalt"] == 3)
check("pes: mraz −12 °C občutena = 2", D.build_days(P5.CFG, synth(apparent_temperature=-12), TODAY)[0]["pts"]["mraz"] == 2)

# ── izris ──
for c in CFGS:
    page, days = D.build_page(c, synth(**storm), TODAY)
    check(f"{c['slug']}: pet dni", len(days) == 5)
    check(f"{c['slug']}: canonical", f'rel="canonical" href="https://meteorec.si{c["url"]}"' in page)
    check(f"{c['slug']}: opozorilo in metodologija", c["disclaimer_lead"] in page and 'id="metodologija"' in page)
    check(f"{c['slug']}: brez notranjih meritev", "indoor" not in page.lower())
    check(f"{c['slug']}: naslov ≤ 60 znakov", len(c["title"]) <= 60)
    body = page.split("</head>")[1]
    check(f"{c['slug']}: ni NaN/None v besedilu", not re.search(r"\bNone\b|\bnan\b|\bNaN\b", body))
    check(f"{c['slug']}: trak po urah le tam, kjer je hour_fn", ("dv-strip" in body) == bool(c.get("hour_fn")))
    check(f"{c['slug']}: konfiguracija usklajena",
          {k for _, _, ks in c["groups"] for k in ks} == {k for k, _, _ in c["factors"]}
          and set(c["day_fn"](synth(), "2026-06-10")[0]) == {k for k, _, _ in c["factors"]}
          and len(c["groups"]) <= 4 and len(c["levels"]) == 4 == len(c["advice"]))
check("barve skupin: največ 4", all(len(c["groups"]) <= 4 for c in CFGS))
sys.exit(1 if fails else 0)
