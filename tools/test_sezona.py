#!/usr/bin/env python3
"""Preizkus /sezona/ (generate_sezona_page.py): vsaka povezava obstaja, vsak
letni čas se zgradi, klimatologija ne šteje nepokritih let, FAQ shema = vidno
besedilo, tuja datoteka se bere po datumu (ne včerajšnji gobarski indeks)."""
import datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sezona_page as g  # noqa: E402

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f"✗ {name} {detail}")


# 1) Lokalne povezave kažejo na obstoječe strani.
for season, links in g.LINKS.items():
    for href, _n, _w in links:
        if href.startswith("/"):
            path = os.path.join(g.ROOT, href.lstrip("/"), "index.html")
            check(f"povezava {season} {href}", os.path.exists(path))

# 2) Vsak letni čas se zgradi z dejansko zgodovino; FAQ shema = vidno.
hist = g.load_history()
for iso in ("2026-01-15", "2026-04-15", "2026-07-15", "2026-10-15", "2026-12-15"):
    d = datetime.date.fromisoformat(iso)
    html = g.build(hist, d)
    check(f"naslov {iso}", g.SEASONS[g.season_of(d)]["label"] in html)
    paras, qa = g.season_facts(hist, g.season_of(d), d)
    check(f"klimatologija {iso}", len(paras) >= 1, str(paras))
    m = re.search(r'"@type":"FAQPage".*?"mainEntity":(\[.*\])\}', html)
    if qa:
        check(f"FAQ shema {iso}", m is not None)
        names = [x["name"] for x in json.loads(m.group(1))] if m else []
        check(f"FAQ = vidno {iso}", names == [q for q, _ in qa] and all(f"<summary>{q}</summary>" in html for q in names))

# 3) Klimatologija: nepokrito leto ne šteje, zmrzal na meji (0 °C) šteje.
syn = {}
for y in (2020, 2021, 2022):
    d = datetime.date(y, 7, 1)
    while d <= datetime.date(y, 12, 31):
        syn[d.isoformat()] = {"tempLow": 5.0, "tempHigh": 15.0}
        d += datetime.timedelta(days=1)
syn["2020-10-10"]["tempLow"] = 0.0
syn["2021-10-20"]["tempLow"] = -1.0
syn["2022-11-01"]["tempLow"] = -0.5
check("prva zmrzal na meji 0 °C", g.first_autumn_frost(syn, 2020) == datetime.date(2020, 10, 10))
check("prva zmrzal", g.first_autumn_frost(syn, 2021) == datetime.date(2021, 10, 20))
del syn["2022-09-01"]
check("nepokrito leto izpade", g.first_autumn_frost(syn, 2022) is None)
clim = g.date_climatology([datetime.date(2020, 10, 10), datetime.date(2021, 10, 20), datetime.date(2022, 11, 1)])
check("mediana", clim and clim["median"] == "20. oktobra", str(clim))
check("pod tremi leti ni klimatologije", g.date_climatology([datetime.date(2020, 10, 10)] * 2) is None)

# 6) Uvrstitev meseca na mesečnih straneh arhiva (generate_seo_pages.month_rank).
import generate_seo_pages as sp  # noqa: E402
bym = {}
for y, t in ((2020, 10.0), (2021, 12.0), (2022, 11.0), (2023, 9.0)):
    bym[f"{y}-09"] = [(f"{y}-09-{d:02d}", {"tempAvg": t, "precipTotal": 1.0}) for d in range(1, 31)]
bym["2024-09"] = [(f"2024-09-{d:02d}", {"tempAvg": 30.0}) for d in range(1, 10)]  # delni
check("rang: najtoplejši", sp.month_rank(bym, 2021, 9, "tavg") == (1, 4))
check("rang: delni mesec se ne uvršča", sp.month_rank(bym, 2024, 9, "tavg") is None)
check("rang: delni mesec ne šteje drugim", sp.month_rank(bym, 2023, 9, "tavg") == (4, 4))
check("rang: fraza zadnji", sp.rank_phrase((4, 4), "najtoplejši", "najhladnejši") == "najhladnejši")
check("rang: fraza 2.", sp.rank_phrase((2, 4), "najtoplejši", "najhladnejši") == "2. najtoplejši")
check("rang: fraza 3. od 4", sp.rank_phrase((3, 4), "najtoplejši", "najhladnejši") == "2. najhladnejši")
check("rang: sredina", sp.rank_phrase((4, 7), "a", "b") is None)
del bym["2020-09"], bym["2022-09"]
check("rang: pod 3 leti ni uvrstitve", sp.month_rank(bym, 2021, 9, "tavg") is None)

# 4) Gobarski indeks samo, če je današnji.
real = g.read_gobe
tmp = os.path.join(g.ROOT, "gobarska-napoved", "index.json")
cur = json.load(open(tmp, encoding="utf-8"))
day = datetime.date.fromisoformat(cur["date"])
check("današnji gobarski indeks se bere", g.read_gobe(day) is not None)
check("včerajšnji gobarski indeks se ne bere", g.read_gobe(day + datetime.timedelta(days=1)) is None)

# 5) MTR po datumu: pretekli dnevi izpadejo.
mtr = g.read_mtr(datetime.date(2100, 1, 1))
check("MTR iz prihodnosti je prazen (izbira po datumu)", mtr == [])

print(f"\n{ok} preverjanj, {fail} napak")
sys.exit(1 if fail else 0)
