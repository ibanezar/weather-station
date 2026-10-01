#!/usr/bin/env python3
"""tools/test_freshness.py — preizkus tools/check_freshness.py.

1. Vsaka vrstica REGISTRA se mora razrešiti (napačna pot ali polje bi sicer tiho
   pomenila »nikoli ne opozori«).
2. Presoja starosti: datumski izdelek se šteje od konca dneva, ts od zapisanega časa.
Zaženi:  python3 tools/test_freshness.py
"""
import datetime
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_freshness as cf  # noqa: E402

CHECKS, FAILS = 0, []


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name} {detail}")


print("register")
for name, path, mode, param, max_h, hint in cf.REGISTER:
    t = cf.read_time(path, mode, param)
    check(t is not None, f"vrstica se razreši: {name}", f"{path} ({mode}/{param})")
    check(max_h > 0 and hint, f"prag in namig: {name}")

print("presoja")
tmp = tempfile.mkdtemp()
cf.ROOT = tmp
for fname, content in (("a.json", {"generated_at": "2026-10-01T06:00:00Z"}), ("b.json", {"date": "2026-09-29"}),
                       ("h.json", {"2026-09-30": {}, "2026-09-28": {}, "x": 1}), ("c.csv", None)):
    p = os.path.join(tmp, fname)
    with open(p, "w", encoding="utf-8") as f:
        f.write("2026-09-20,a\n2026-09-30,b\n" if content is None else json.dumps(content))
now = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.timezone.utc)
reg = [("ts sveže", "a.json", "ts", "generated_at", 36, "x"), ("ts zastarelo", "a.json", "ts", "generated_at", 5, "x"),
       ("datum zastarelo", "b.json", "date", "date", 36, "x"), ("datum sveže", "b.json", "date", "date", 72, "x"),
       ("maxkey", "h.json", "maxkey", None, 36, "x"), ("csv", "c.csv", "csvdate", None, 36, "x"),
       ("manjka", "nikoli.json", "ts", "generated_at", 36, "x")]
res = {r["name"]: r for r in cf.evaluate(now, reg)}
check(res["ts sveže"]["status"] == "ok" and res["ts sveže"]["age_h"] == 6.0, "ts: 6 h star", str(res["ts sveže"]))
check(res["ts zastarelo"]["status"] == "stale", "ts: čez prag")
check(res["datum zastarelo"]["status"] == "stale", "datum 29. 9. je ob 12:00 1. 10. čez 36 h od konca dneva", str(res["datum zastarelo"]))
check(res["datum sveže"]["status"] == "ok", "datum znotraj praga")
check(res["maxkey"]["status"] == "ok", "največji datumski ključ (ne ključa x)", str(res["maxkey"]))
check(res["csv"]["status"] == "ok", "csv: zadnja vrstica", str(res["csv"]))
check(res["manjka"]["status"] == "unreadable", "manjkajoča datoteka je napaka, ne tišina")
text, n = cf.report(list(res.values()))
check(n == 3 and "zastarelo" in text and "ni berljivo" in text, "poročilo šteje zastarele in neberljive", f"n={n}")
print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
