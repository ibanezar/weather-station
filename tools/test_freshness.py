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
print("cron throughput")
import measure_cron_throughput as mc  # noqa: E402
for cron, want in {"*/15 * * * *": 96, "*/20 * * * *": 72, "0 * * * *": 24, "15 1 * * *": 1, "30 6-7 * * *": 2,
                   "10,40 4-5 * * *": 4, "2-59/5 * * * *": 288}.items():
    check(abs(mc.runs_per_day(cron) - want) < 0.01, f"pričakovani tek/dan: {cron}", str(mc.runs_per_day(cron)))
check(abs(mc.runs_per_day("30 5 * * 1") - 1 / 7) < 0.01, "tedenski cron")
check("storm-map.yml" in mc.scheduled_workflows(), "urniki workflowov se preberejo")

print("zdravje workerja")
import json as _json
import subprocess as _sp
health = {"jobs": {"a": {"ok": True, "err": None, "age_min": 3, "max_min": 20, "stale": False},
                   "b": {"ok": False, "err": "manjka GH_DISPATCH_TOKEN", "age_min": 60, "max_min": 1800, "stale": False},
                   "c": {"ok": True, "err": None, "age_min": 90, "max_min": 20, "stale": True},
                   "d": {"ok": False, "err": "ni zapisa", "age_min": None, "max_min": 20, "stale": True}}}
wh = {r["name"]: r for r in cf.worker_health(lambda: health)}
check(wh["Worker cron: a"]["status"] == "ok", "cron v redu")
check(wh["Worker cron: b"]["status"] == "failing" and "GH_DISPATCH_TOKEN" in wh["Worker cron: b"]["hint"], "javil napako: razlog je viden")
check(wh["Worker cron: c"]["status"] == "stale", "cron je predolgo brez teka")
check(wh["Worker cron: d"]["status"] == "stale", "cron brez zapisa je zastarel")
bad = cf.worker_health(lambda: (_ for _ in ()).throw(OSError("x")))
check(len(bad) == 1 and bad[0]["status"] == "unreadable", "nedosegljiv /health je napaka, ne tišina")
text, n = cf.report(list(wh.values()))
check(n == 3 and "napaka" in text, "poročilo šteje napake", f"n={n}")

# prava koda workerja: _cronBeat + _cronHealth nad lažnim KV (tools/_cron_beat_test.mjs)
ROOT = os.path.dirname(HERE)
_p = _sp.run(["node", os.path.join(HERE, "_cron_beat_test.mjs")], capture_output=True, text=True, cwd=ROOT, timeout=60)
try:
    r = _json.loads(_p.stdout)
except ValueError:
    r = None
    check(False, "_cronBeat se požene", (_p.stdout + _p.stderr)[:300])
if r:
    check(r["r1"] is True and r["r2"] is False and r["r3"] is False and r["r4"] is False,
          "_cronBeat: uspeh, {ok:false}, izjema, false", str(r))
    check(r["rewrite"] == 0, "_cronBeat: enako stanje ne piše znova v KV", str(r["rewrite"]))
    jobs = r["health"]["jobs"]
    check(jobs["thresholds"]["ok"] and not jobs["thresholds"]["stale"], "/health: opravilo v redu")
    check(not jobs["dispatch"]["ok"] and "GH_DISPATCH_TOKEN" in jobs["dispatch"]["err"],
          "/health: razlog neuspeha je viden", str(jobs["dispatch"]))
    check(jobs["aurora"]["err"] == "boom", "/health: izjema je zabeležena")
    check(jobs["crnivec"]["waiting"] and not jobs["crnivec"]["stale"] and jobs["crnivec"]["ok"],
          "/health: opravilo brez zapisa znotraj roka od prvega zapisa čaka (ni lažnega izpada)", str(jobs["crnivec"]))
    check(r["long_missing"]["stale"] and not r["long_missing"]["waiting"] and r["long_missing"]["err"] == "ni zapisa",
          "/health: opravilo, ki ga ni > rok od prvega zapisa, je zastarelo", str(r["long_missing"]))
    check(r["since_set"] and r["waiting"]["waiting"] and not r["waiting"]["stale"], "/health: dnevno opravilo po deployu čaka na prvi tek")
    check(r["health"]["ok"] is False, "/health: celota ni ok, če je eno opravilo slabo")

print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
sys.exit(1 if FAILS else 0)
