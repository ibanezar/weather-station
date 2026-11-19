#!/usr/bin/env python3
"""tools/test_zmrzal_resolve.py — razreševalnik ugibalnika zmrzali (tools/zmrzal_ugibalnik_resolve.py).

Zaklene: sezona se začne 1. avgusta (do tedaj velja prejšnja), dogodek `prva-zmrzal-<sezona>` iz novosti.json je edini vir datuma
(drugega leta ali tipa ne vzame), brez dogodka do 31. 12. je `brez_zmrzali`, prej še ne. Zaženi: python3 tools/test_zmrzal_resolve.py"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zmrzal_ugibalnik_resolve as z  # noqa: E402

fails = 0


def check(ok, name):
    global fails
    if not ok:
        fails += 1
        print("  ✗", name)


D = datetime.date
ev26 = {"type": "prva-zmrzal", "slug": "prva-zmrzal-2026", "date": "2026-10-23", "value": -0.1}
ev27 = {"type": "prva-zmrzal", "slug": "prva-zmrzal-2027", "date": "2027-10-14", "value": -1.2}
other = {"type": "pozna-zmrzal", "slug": "prva-zmrzal-2026", "date": "2026-05-01", "value": -1.0}

check(z.season_of(D(2027, 7, 31)) == 2026 and z.season_of(D(2027, 8, 1)) == 2027, "sezona se začne 1. avgusta")
check(z.season_of(D(2026, 11, 19)) == 2026 and z.season_of(D(2028, 1, 5)) == 2027, "sezona čez novo leto")
o = z.build(D(2026, 11, 19), [ev26])
check(o["prva_zmrzal"] == "2026-10-23" and o["vrednost_c"] == -0.1 and not o["brez_zmrzali"] and o["novosti"] == "/novosti/prva-zmrzal-2026/", "dogodek sezone 2026")
check(z.build(D(2026, 11, 19), [])["prva_zmrzal"] is None, "brez dogodka: datum ni znan")
check(z.build(D(2026, 11, 19), [ev27])["prva_zmrzal"] is None, "dogodek druge sezone se ne vzame")
check(z.build(D(2026, 11, 19), [other])["prva_zmrzal"] is None, "drug tip dogodka (pozna zmrzal) se ne vzame, čeprav ima isti slug")
check(z.build(D(2027, 8, 2), [ev26])["sezona"] == 2027 and z.build(D(2027, 8, 2), [ev26])["prva_zmrzal"] is None, "avgusta 2027 je nova sezona brez datuma")
check(z.build(D(2026, 12, 31), [])["brez_zmrzali"] is False, "31. 12.: ugibanje še traja")
check(z.build(D(2027, 1, 1), [])["brez_zmrzali"] is True, "1. 1.: brez zmrzali do konca decembra")
check(z.build(D(2027, 1, 1), [ev26])["brez_zmrzali"] is False, "z dogodkom ni »brez zmrzali«")

print("OK" if not fails else f"{fails} napak")
sys.exit(1 if fails else 0)
