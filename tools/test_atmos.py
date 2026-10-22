#!/usr/bin/env python3
"""tools/test_atmos.py — strani o velikem vremenu (/indeksi/, /stratosfera/, /prah/, /sinopticna/).
Brez omrežja: razčlenjevanje virov NOAA, razlaga stanj, projekcija, grafi, zasebnost.
Zaženi: python3 tools/test_atmos.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atmos_common as ac  # noqa: E402
import generate_indeksi_page as ix  # noqa: E402
import generate_prah_page as pr  # noqa: E402
import generate_stratosfera_page as st  # noqa: E402

fails = 0
D = datetime.date


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


# ── Indeksi: razčlenjevanje ──────────────────────────────────────────────────
cdas = "year,month,day,ao_index_cdas\n2026,10,18,2.5\n2026,10,19,-0.25\nnapaka,vrstica\n2026,13,40,1\n"
rows = ix.parse_cdas(cdas)
check(rows == [(D(2026, 10, 18), 2.5), (D(2026, 10, 19), -0.25)], "parse_cdas preskoči glavo, smeti in neveljavne datume")

gefs = ("lead,member,time,ao_index,valid_time\n"
        "0,0,2026-10-20,1.0,2026-10-20\n0,1,2026-10-20,3.0,2026-10-20\n"
        "1,0,2026-10-20,0.0,2026-10-21\n"
        "0,0,2026-10-21,9.0,2026-10-21\n")  # novejša izdaja prevlada
fc = ix.parse_forecast(gefs, "ao_index")
check(fc["init"] == "2026-10-21" and fc["by_valid"] == {"2026-10-21": [9.0]}, "napoved vzame samo zadnji čas izdaje")
fc2 = ix.parse_forecast(gefs.replace("0,0,2026-10-21,9.0,2026-10-21\n", ""), "ao_index")
check(fc2["by_valid"]["2026-10-20"] == [1.0, 3.0], "ansambel zbere vse člane za isti veljavni dan")
check(ix.parse_forecast("lead,time,x,valid_time\n", "x") is None, "prazna napoved je None")
check(ix.percentile([1, 2, 3, 4, 5], 50) == 3 and ix.percentile([0, 10], 90) == 9 and ix.percentile([], 50) is None,
      "percentil")

oni = ix.parse_oni("SEAS YR TOTAL ANOM\n DJF 2026 26.0 -0.3\n JAS 2026 29.12 2.16\n XXX 2026 1 1\n")
check(oni == [(D(2026, 1, 1), -0.3, "DJF 2026"), (D(2026, 8, 1), 2.16, "JAS 2026")],
      "ONI: sezona → središčni mesec (DJF = januar, JAS = avgust)")
nino = ix.parse_nino34("1948 2026\n2026 -0.5 0.1 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99\n"
                       " units=degC\n")
check(nino == [(D(2026, 1, 1), -0.5), (D(2026, 2, 1), 0.1)], "Niño 3.4: manjkajoče −99,99 odpade")

# ── Indeksi: razlaga ─────────────────────────────────────────────────────────
check(ix.enso_state(0.49) == "nevtralno" and ix.enso_state(-0.5) == "šibek La Niña", "ENSO: meja ±0,5")
check(ix.enso_state(1.0) == "zmeren El Niño" and ix.enso_state(1.5) == "močan El Niño"
      and ix.enso_state(2.0) == "zelo močan El Niño", "ENSO: stopnje moči")
check(ix.phase(0.3, "pozitiven", "negativen") == "blizu nevtralnega"
      and ix.phase(-1.2, "pozitiven", "negativen") == "izrazito negativen", "faza AO/NAO")

# ── Stratosfera ──────────────────────────────────────────────────────────────
parts = [ln.split(":") for ln in ["1:0:d=2026102200:HGT:10 mb:anl:", "2:100:d=2026102200:UGRD:10 mb:anl:",
                                  "3:250:d=2026102200:VGRD:10 mb:anl:", "4:400:d=2026102200:TMP:10 mb:anl:"]]
check(st.idx_range(parts, "UGRD", 10) == "bytes=100-249", "idx: območje do naslednjega polja")
check(st.idx_range(parts, "TMP", 10) == "bytes=400-", "idx: zadnje polje brez konca")
check(st.idx_range(parts, "UGRD", 50) is None, "idx: manjkajoč nivo je None")

H = {"2026-12-15": {"u60": -2.0}}
check(st.classify(H, [], D(2026, 12, 15))[0] == "ssw", "pozimi u < 0 = kriterij SSW")
H = {"2026-12-15": {"u60": 12.0}}
fcneg = [{"date": "2026-12-20T00", "step": 120, "u60": -1.0}]
check(st.classify(H, fcneg, D(2026, 12, 15))[0] == "napoved", "napovedan obrat pozimi")
check(st.classify(H, [{"date": "2026-12-15T00", "step": 0, "u60": -1.0}], D(2026, 12, 15))[0] == "stabilno",
      "korak 0 ni napoved obrata")
H = {"2026-07-15": {"u60": -20.0}}
check(st.classify(H, [], D(2026, 7, 15))[0] == "poletje", "poleti vzhodnik ni SSW")
H = {"2026-10-20": {"u60": 5.0}}
check(st.classify(H, [], D(2026, 10, 20))[0] == "gradi", "oktober s šibkim vetrom: vrtinec se gradi")
check(st.classify({}, [], D(2026, 1, 1))[0] == "neznano", "brez podatkov")

clima = {"u60": {f"2021-10-{d:02d}": float(d) for d in range(1, 31)}}
band = st.clima_band(clima, D(2026, 10, 10), D(2026, 10, 12))
check(band and band[0][1] <= band[0][2] <= band[0][3], "razpon: min ≤ povprečje ≤ maks")
check(st.clima_band(None, D(2026, 10, 10), D(2026, 10, 12)) == [], "brez klimatologije ni pasu")

# ── Prah ─────────────────────────────────────────────────────────────────────
check(pr.daily_max(["2026-10-22T00:00", "2026-10-22T01:00", "2026-10-23T00:00"], [3.0, 7.0, None])
      == {"2026-10-22": 7.0}, "daily_max: največja po dnevu, None se preskoči")
check(pr.cls(5) == "nizka" and pr.cls(10) == "zmerna" and pr.cls(50) == "visoka" and pr.cls(None) == "—", "razredi prahu")

# ── Projekcija ───────────────────────────────────────────────────────────────
import numpy as np  # noqa: E402
x0, y0 = ac.LCC.xy(12.0, 45.0)
x1, y1 = ac.LCC.xy(20.0, 45.0)
x2, y2 = ac.LCC.xy(12.0, 55.0)
check(abs(x0) < 1e-6 and abs(y0) < 1e-6, "projekcija: središče je v izhodišču")
check(x1 > x0 and y2 > y0, "projekcija: vzhod je desno, sever je zgoraj")
xr, yr = ac.LCC.xy(14.92, 46.33)
check(ac.MAP_X[0] < xr < ac.MAP_X[1] and ac.MAP_Y[0] < yr < ac.MAP_Y[1], "Rečica je znotraj okvirja karte")
for lon, lat in ((-18, 30), (42, 30), (-18, 66), (42, 66)):
    xx, yy = ac.LCC.xy(lon, lat)
    check(abs(xx) < 3600 and abs(yy) < 3600, f"projekcija: kot ({lon},{lat}) je končen in razumen")
check(ac.nice_ticks(0, 10, 5) == [0, 2, 4, 6, 8, 10], "nice_ticks")

# ── Graf ─────────────────────────────────────────────────────────────────────
svg = ac.line_chart([{"name": "a", "color": "#fff", "pts": [(D(2026, 1, 1), 1.0), (D(2026, 1, 10), -2.0)]}],
                    aria="test", hlines=[(0.5, "prag")])
check(svg.startswith("<svg") and 'aria-label="test"' in svg and "polyline" in svg and "prag" in svg, "line_chart SVG")
check(ac.line_chart([{"name": "a", "color": "#fff", "pts": []}]) == "", "prazen graf je prazen niz")
check(ac.num(-0.04, 1) == "0,0" and ac.num(2.8, 1, True) == "+2,8" and ac.num(None) == "—", "num: slovenski zapis")

# ── Zasebnost: strani in podatki ne smejo omenjati notranjih meritev ─────────
for rel in ("indeksi/index.html", "stratosfera/index.html", "prah/index.html", "sinopticna/index.html",
            "data/indeksi.json", "data/stratosfera.json", "data/prah.json", "data/sinopticna.json"):
    path = os.path.join(ac.ROOT, rel)
    if os.path.exists(path):
        txt = open(path, encoding="utf-8").read().lower()
        check("indoor" not in txt and "notranja temperatura" not in txt, f"{rel}: brez notranjih meritev")

if fails:
    print(f"✗ {fails} preverjanj ni uspelo")
    sys.exit(1)
print("✓ test_atmos: vsa preverjanja uspešna")
