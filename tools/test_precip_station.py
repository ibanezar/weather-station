#!/usr/bin/env python3
"""
Padavine IREICA1 na padavinski karti (`generate_precip_map.fetch_station_rr24h`): isto 24-urno
okno kot ARSO (06:00 UTC do 06:00 UTC), seštevek iz dveh dnevnih kumulativ (ponastavitev ob
lokalni polnoči), brez številke ob vrzeli ob robu okna, ob ročno popravljenem dnevu dežemera
in ob nekonsistentnih podatkih. Notranjih meritev ne bere (samo `rainfall.daily`).

usage: python3 tools/test_precip_station.py
"""
import datetime as dt, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_precip_map as pm  # noqa: E402

FAIL = []
UTC = dt.timezone.utc


def check(ok, name):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAIL.append(name)


def ts(y, m, d, h, mi=0):
    return int(dt.datetime(y, m, d, h, mi, tzinfo=UTC).timestamp())


# okno: zadnji 06:00 UTC
s, e = pm.station_window(dt.datetime(2026, 11, 20, 7, 30, tzinfo=UTC))
check(e == dt.datetime(2026, 11, 20, 6, tzinfo=UTC) and s == dt.datetime(2026, 11, 19, 6, tzinfo=UTC),
      "okno ob 7.30 UTC: 19. 11. 06:00 do 20. 11. 06:00")
s, e = pm.station_window(dt.datetime(2026, 11, 20, 5, 0, tzinfo=UTC))
check(e == dt.datetime(2026, 11, 19, 6, tzinfo=UTC), "pred 06:00 UTC je konec okna včerajšnji")

# 5-minutne kumulative: 19. 11. lokalno (UTC+1): od 7:00 do polnoči pade 3 mm, pred 7:00 že 1,2 mm;
# 20. 11. od polnoči do 7:00 pade 2 mm
prev = [(ts(2026, 11, 19, 5, 55), 1.2), (ts(2026, 11, 19, 6, 0), 1.2), (ts(2026, 11, 19, 12, 0), 2.5),
        (ts(2026, 11, 19, 22, 55), 4.2)]
nxt = [(ts(2026, 11, 19, 23, 5), 0.5), (ts(2026, 11, 20, 5, 55), 1.8), (ts(2026, 11, 20, 6, 0), 2.0),
       (ts(2026, 11, 20, 6, 5), 2.1)]
a, b = ts(2026, 11, 19, 6), ts(2026, 11, 20, 6)
mid = ts(2026, 11, 19, 23)  # lokalna polnoč (UTC+1)
check(pm.rain_between(prev, nxt, a, b, mid) == 5.0, "(4,2 − 1,2) + 2,0 = 5,0 mm")
check(pm.rain_between(prev, nxt, a, b, mid) != nxt[-1][1] + prev[-1][1], "točka po robu okna se ne šteje")

# vrzel zvečer: zadnja točka prvega dne je dolgo pred polnočjo -- večerni dež bi manjkal
early = [(ts(2026, 11, 19, 6), 1.2), (ts(2026, 11, 19, 18, 0), 3.0)]
check(pm.rain_between(early, nxt, a, b, mid) is None, "vrzel zvečer prvega dne: ni številke")

# vrzel ob robu: najbližja točka pred začetkom je starejša od 15 min
gap = [(ts(2026, 11, 19, 5, 30), 1.0), (ts(2026, 11, 19, 22, 55), 4.2)]
check(pm.rain_between(gap, nxt, a, b, mid) is None, "vrzel ob začetku okna: ni številke")
gap2 = [(ts(2026, 11, 20, 5, 30), 1.8)]
check(pm.rain_between(prev, gap2, a, b, mid) is None, "vrzel ob koncu okna: ni številke")
check(pm.rain_between([], nxt, a, b, mid) is None and pm.rain_between(prev, [], a, b, mid) is None, "prazna serija: ni številke")
bad = [(ts(2026, 11, 19, 6), 3.0), (ts(2026, 11, 19, 22, 55), 1.0)]
check(pm.rain_between(bad, nxt, a, b, mid) is None, "kumulativa, ki pade: ni številke")
check(pm.rain_between(prev, [(ts(2026, 11, 20, 6), 0.0)], a, b, mid) == 3.0, "brez dežja po polnoči: samo prvi dan")


def eco(series):
    return {"rainfall": {"daily": {"list": {str(t): v for t, v in series}}}}


calls = []


def fake(start, end):
    calls.append((start, end))
    return eco(prev) if start == "2026-11-19" else eco(nxt)


now = dt.datetime(2026, 11, 20, 6, 30, tzinfo=UTC)
check(pm.fetch_station_rr24h(now, fake) == 5.0, "fetch: pravilna količina")
check(calls == [("2026-11-19", "2026-11-19"), ("2026-11-20", "2026-11-20")], "fetch: en klic na lokalni dan")
check(pm.fetch_station_rr24h(dt.datetime(2026, 11, 20, 6, 5, tzinfo=UTC), fake) is None,
      "tik po robu okna Ecowitt še nima točke: ni številke")
check(pm.fetch_station_rr24h(now, lambda s, e: None) is None, "Ecowitt nedosegljiv: ni številke")


def boom(s, e):
    raise OSError("omrežje")


check(pm.fetch_station_rr24h(now, boom) is None, "izjema pri prenosu ne podre karte")
# dan z ročnim popravkom dežemera
pm.uh.PRECIP_OVERRIDES["2026-11-19"] = {"precipTotal": 0, "razlog": "test"}
try:
    check(pm.fetch_station_rr24h(now, fake) is None, "dan z ročnim popravkom dežemera: ni številke")
finally:
    del pm.uh.PRECIP_OVERRIDES["2026-11-19"]

# zasebnost: klic bere samo zunanjo kumulativo
src = open(pm.__file__, encoding="utf-8").read()
check("indoor" not in src.lower(), "generator ne omenja notranjih meritev")

# izris: karta z domačo postajo in brez nje (brez napake)
stations = [{"name": "Vojsko", "la": 46.0, "lo": 13.9, "mm": 46.0}, {"name": "Celje", "la": 46.24, "lo": 15.26, "mm": 20.0}]
now_l = dt.datetime(2026, 11, 20, 7, 30, tzinfo=pm.TZ)
for hm in (None, 20.4, 0.0):
    img = pm.render(1080, 1350, 60, 1290, stations, {"top_name": "Vojsko", "top_mm": 46.0}, now_l, "20.11.2026 7:00 CET", hm)
    check(img.size == (1080, 1350), f"render s postajo {hm}")
page = pm.build_page(stations, {"top_name": "Vojsko", "top_mm": 46.0},
                     {"issued": "x", "image": "https://meteorec.si/x.jpg", "date": "2026-11-20"}, now_l, 20.4)
check("20,4 mm" in page and "IREICA1" in page, "stran navaja postajo z decimalno vejico")
page0 = pm.build_page(stations, {"top_name": "Vojsko", "top_mm": 46.0},
                      {"issued": "x", "image": "https://meteorec.si/x.jpg", "date": "2026-11-20"}, now_l, None)
check("Dodana je naša postaja" not in page0, "stran brez podatka postaje je ne omenja")

print(f"\n{len(FAIL)} napak" if FAIL else "\nvse OK")
sys.exit(1 if FAIL else 0)
