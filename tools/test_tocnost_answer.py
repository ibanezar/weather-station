#!/usr/bin/env python3
"""tools/test_tocnost_answer.py — blok »Na kratko« na /tocnost-napovedi/ (generate_tocnost_page.answer_block).
Sintetični zapisi: znan vrstni red, znana stalna pristranskost, premalo skupnih dni. Zaženi: python3 tools/test_tocnost_answer.py"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_tocnost_page as g  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


def rec(actual, **src):
    r = {"actual": {"tmax": actual, "tmin": 0.0}}
    for k, (tmax, tmin) in src.items():
        r[k] = {"tmax": tmax, "tmin": tmin, "err_tmax": abs(tmax - actual), "err_tmin": abs(tmin - 0.0)}
    return r


LAB = [("arso", "ARSO"), ("open_meteo", "Open-Meteo"), ("meteorec", "MTR v1")]
d0 = datetime.date(2026, 9, 1)
V = {}
for i in range(40):
    a = 15.0 + (i % 5)
    # MTR: napaka 0,5; Open-Meteo: 1,5; ARSO: stalno 4 °C pod meritvijo
    V[(d0 + datetime.timedelta(days=i)).isoformat()] = rec(a, arso=(a - 4, 0.0), open_meteo=(a + (1.5 if i % 2 else -1.5), 0.5), meteorec=(a + (0.5 if i % 2 else -0.5), 0.2))
out = g.answer_block(V, LAB)
check("Na kratko" in out and "30 dneh" in out and "(30 dni)" in out, "30 skupnih dni in »zadnjih 30 dneh«")
check(out.index("MTR v1") < out.index("Open-Meteo") < out.index("ARSO ±"), "vrstni red po napaki: MTR, Open-Meteo, ARSO")
check("±0,5 °C" in out and "±1,5 °C" in out and "±4,0 °C" in out, "napake so izračunane (0,5 / 1,5 / 4,0)")
check("stalna pristranskost" in out and "ARSO je povprečno 4,0 °C pod meritvijo" in out, "ARSO: stalna pristranskost 4,0 °C pod meritvijo")
check("brez tega odmika bi bila napaka ±0,0 °C" in out, "ARSO: napaka brez odmika (v testu je odmik stalen, torej 0,0)")
check("MTR v1 je povprečno" not in out, "MTR ni označen kot pristranski")
check("ni statistično zanesljiva" not in out, "razlika MTR proti Open-Meteo je zanesljiva")
check("Posodobljeno:" in out, "vidna oznaka Posodobljeno")

# razlika brez moči: oba enako dobra -> opozorilo
V2 = {}
for i in range(40):
    a = 15.0
    e = 1.0 if i % 2 else 1.1
    V2[(d0 + datetime.timedelta(days=i)).isoformat()] = rec(a, open_meteo=(a + e, 0.2), meteorec=(a + (1.1 if i % 2 else 1.0), 0.2))
out2 = g.answer_block(V2, [("open_meteo", "Open-Meteo"), ("meteorec", "MTR v1")])
check("ni statistično zanesljiva" in out2, "skoraj enaka vira: razlika ni označena kot zanesljiva")

# premalo skupnih dni -> brez bloka (ne trdimo iz nič)
V3 = {k: v for k, v in list(V.items())[:6]}
check(g.answer_block(V3, LAB) == "", "pod 10 skupnih dni ni bloka")
# vir, ki je napovedoval le del dni, ne podira skupnih dni
V4 = dict(V)
for k in list(V4)[:30]:
    V4[k] = {kk: vv for kk, vv in V4[k].items() if kk != "meteorec"}
out4 = g.answer_block(V4, LAB)
check(out4 == "" or "(10 dni)" in out4 or "dneh od" in out4, "samo skupni dnevi (%s)" % out4[:60].replace("\n", " "))
print(f"\n{fails} razhajanj")
sys.exit(1 if fails else 0)
