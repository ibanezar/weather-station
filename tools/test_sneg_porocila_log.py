#!/usr/bin/env python3
"""tools/test_sneg_porocila_log.py — arhiv agregatov poročil o snegu (log_sneg_porocila.py) in razrešitev ugibalnika."""
import datetime as dt
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import log_sneg_porocila as L  # noqa: E402
import sneg_ugibalnik_resolve as R  # noqa: E402

fails = 0


def check(cond, msg):
    global fails
    if not cond:
        fails += 1
        print("✗", msg)
    else:
        print("✓", msg)


U = dt.timezone.utc
AGG = {"celice": [
    {"regija": "Savinjska", "pas": "p1", "n": 3, "stanja": {"lezi": 2, "pada": 0, "dez-sneg": 0, "brez": 1}, "zadnje": "2026-11-18T07:41:00Z", "sodba": "lezi"},
    {"regija": "Koroška", "pas": "p0", "n": 1, "stanja": {"lezi": 0, "pada": 0, "dez-sneg": 0, "brez": 1}, "zadnje": "2026-11-18T05:00:00Z", "sodba": None}]}

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "x.csv")
    t0 = dt.datetime(2026, 11, 19, 1, 45, tzinfo=U)
    L.main(p, t0, lambda ur: AGG)
    rows = open(p, encoding="utf-8").read().splitlines()
    check(rows[0] == ",".join(L.HEADER) and len(rows) == 3, "prvi tek: glava + 2 celici")
    check(rows[1].startswith("2026-11-19T01:45Z,24,Koroška,p0,1,") and rows[2].endswith("Savinjska,p1,3,2,0,0,1,lezi,2026-11-18T07:41:00Z"), "vrstice urejene, sodba in čas zadnjega")
    L.main(p, t0 + dt.timedelta(hours=5), lambda ur: AGG)
    check(len(open(p, encoding="utf-8").read().splitlines()) == 3, "drugi tek v 5 h se preskoči (okna se ne smejo prekrivati)")
    L.main(p, t0 + dt.timedelta(hours=25), lambda ur: AGG)
    check(len(open(p, encoding="utf-8").read().splitlines()) == 5, "tek čez 25 h doda nove vrstice brez nove glave")
    n = len(open(p, encoding="utf-8").read().splitlines())

    def boom(ur):
        raise OSError("down")
    L.main(p, t0 + dt.timedelta(hours=60), boom)
    L.main(p, t0 + dt.timedelta(hours=61), lambda ur: {"celice": []})
    check(len(open(p, encoding="utf-8").read().splitlines()) == n, "nedosegljiv worker in prazen odgovor: nič zapisano (praznina ni »ni snega«)")

# razrešitev ugibalnika
ev = [{"type": "prvi-sneg", "slug": "prvi-sneg-2026", "date": "2026-12-03", "value": 2.0, "gap": None}]
check(R.season_of(dt.date(2026, 11, 18)) == 2026 and R.season_of(dt.date(2027, 3, 1)) == 2026 and R.season_of(dt.date(2027, 7, 1)) == 2027, "sezona: od julija do junija")
b = R.build(dt.date(2026, 11, 18), [])
check(b["prvi_sneg"] is None and not b["brez_snega"] and b["sezona"] == 2026, "brez dogodka: odprto")
b = R.build(dt.date(2026, 12, 4), ev)
check(b["prvi_sneg"] == "2026-12-03" and b["vrednost_cm"] == 2.0 and b["novosti"] == "/novosti/prvi-sneg-2026/", "z dogodkom: datum prepisan")
check(R.build(dt.date(2026, 12, 4), [{"type": "prvi-sneg", "slug": "prvi-sneg-2025", "date": "2025-12-25"}])["prvi_sneg"] is None, "dogodek druge sezone se ne upošteva")
check(R.build(dt.date(2027, 5, 2), [])["brez_snega"] is True and R.build(dt.date(2027, 4, 30), [])["brez_snega"] is False, "brez snega do 30. aprila: ugibanje mimo")
g = R.build(dt.date(2026, 12, 4), [{**ev[0], "gap": ["2026-11-01", "2026-11-08"]}])
check(g["gap"] == ["2026-11-01", "2026-11-08"], "gap se prenese (stran pove, da datum ni nujno prvi)")
sys.exit(1 if fails else 0)
