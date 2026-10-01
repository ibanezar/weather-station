#!/usr/bin/env python3
"""tools/test_storm_verify.py — preizkus preverjanja nevihtne karte proti strelam.

Preverja čisto logiko tools/verify_storm_map.py (okno, pokritost, celice, tabele)
in da SQL združevanje v worker.js (LTG_CELLS_SQL) da iste celice kot Python.
Zaženi:  python3 tools/test_storm_verify.py
"""
import datetime
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import verify_storm_map as vs  # noqa: E402

FAILS = []
CHECKS = 0


def check(ok, name, detail=""):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILS.append(name)
        print(f"  ✗ {name}  {detail}"[:400])


GRID = {"lat0": 45.45, "dlat": 0.18, "lon0": 13.4, "dlon": 0.22}


def pt(k, j, score):
    return [round(GRID["lat0"] + GRID["dlat"] * k, 3), round(GRID["lon0"] + GRID["dlon"] * j, 3), score, "17:00"]


def forecast(date="2026-07-10", issued="2026-07-10T07:00:00+02:00", points=None, national=60):
    pts = points or [pt(0, 0, 0), pt(1, 1, 10), pt(2, 2, 30), pt(3, 3, 45), pt(4, 4, 70)]
    return {"date": date, "issued_at": issued, "grid": GRID,
            "national": {"score": national, "level": vs.score_level(national), "place": "x", "hour": "17:00"},
            "points": pts}


def resp(cells, connected=288, total=288, since=None, n=None):
    od, _ = vs.day_window(forecast())
    return {"cells": [{"k": k, "j": j, "n": c} for k, j, c in cells], "total": n if n is not None else sum(c for *_, c in cells),
            "slots_connected": connected, "slots_total": total,
            "uptime_since": od - 86400000 if since is None else since}


def test_window():
    print("\nokno")
    od, do_ = vs.day_window(forecast())
    d0 = datetime.datetime(2026, 7, 10, 7, 0, tzinfo=vs.TZ)
    d1 = datetime.datetime(2026, 7, 11, 0, 0, tzinfo=vs.TZ)
    check(od == int(d0.timestamp() * 1000), "okno se začne ob izdaji karte")
    check(do_ == int(d1.timestamp() * 1000), "okno se konča ob lokalni polnoči")
    # zimski čas: polnoč je 23:00 UTC
    _, do_w = vs.day_window(forecast("2026-12-10", "2026-12-10T07:00:00+01:00"))
    check(do_w == int(datetime.datetime(2026, 12, 11, 0, 0, tzinfo=vs.TZ).timestamp() * 1000), "okno v zimskem času")
    check(vs.day_window(forecast(issued="2026-07-10T13:00:00"))[0] == int(datetime.datetime(2026, 7, 10, 13, 0, tzinfo=vs.TZ).timestamp() * 1000),
          "izdaja brez ure pasu se razume kot lokalna")


def test_verify():
    print("\nverify_day")
    r = vs.verify_day(forecast(), resp([(3, 3, 5), (4, 4, 1), (9, 9, 4)]))
    check(r["status"] == "ok", "dan z dovolj pokritosti je preverjen", str(r))
    check(r["strike_cells"] == 2, "štejejo se samo celice z mrežno točko", str(r.get("strike_cells")))
    lv = r["levels"]
    check(lv["VISOKO"] == {"n": 1, "obs": 1} and lv["EKSTREMNO"] == {"n": 1, "obs": 1}, "VISOKO in EKSTREMNO zadeta", str(lv))
    check(lv["BREZ"] == {"n": 1, "obs": 0} and lv["NIZKO"] == {"n": 1, "obs": 0} and lv["ZMERNO"] == {"n": 1, "obs": 0},
          "nižje stopnje brez strel", str(lv))
    c = r["contingency"]["22"]
    check(c == {"a": 2, "b": 1, "c": 0, "d": 2}, "kontingenčna tabela za prag ZMERNO", str(c))
    check(r["storm_day"] is True, "dan s strelami")
    # mirni dan
    r0 = vs.verify_day(forecast(), resp([]))
    check(r0["status"] == "ok" and r0["storm_day"] is False and r0["strike_cells"] == 0, "mirni dan")
    check(r0["contingency"]["22"] == {"a": 0, "b": 3, "c": 0, "d": 2}, "mirni dan: lažni alarmi", str(r0["contingency"]["22"]))
    # pokritost
    low = vs.verify_day(forecast(), resp([(4, 4, 9)], connected=200, total=288))
    check(low["status"] == "skipped" and "69" in low["reason"], "slaba pokritost = preskočen dan", str(low))
    edge = vs.verify_day(forecast(), resp([], connected=260, total=288))
    check(edge["status"] == "ok", "pokritost 90,3 % je dovolj", str(edge))
    late = vs.verify_day(forecast(), resp([(4, 4, 9)], since=vs.day_window(forecast())[0] + 3600000))
    check(late["status"] == "skipped", "zapis pokritosti, ki se je začel po izdaji, ne šteje", str(late))
    none = vs.verify_day(forecast(), {**resp([]), "uptime_since": None})
    check(none["status"] == "skipped", "brez zapisa pokritosti ni preverjanja")
    zero = vs.verify_day(forecast(), resp([], connected=0, total=0))
    check(zero["status"] == "skipped", "prazno okno ne deli z nič")


def test_summary_and_block():
    print("\nsummarize / build_block")
    empty = vs.build_block({"days": []})
    check("šele začelo" in empty and vs.START in empty and vs.END in empty, "prazen blok pove, da se je preverjanje šele začelo")
    days = [vs.verify_day(forecast(), resp([(4, 4, 3)])), vs.verify_day(forecast("2026-07-11", "2026-07-11T07:00:00+02:00"), resp([])),
            {"date": "2026-07-12", "status": "skipped", "reason": "x"}]
    # drugi dan potrebuje svoje okno za uptime_since — preprosto sprejmemo, da je zgoden
    s = vs.summarize([d for d in days if d["status"] == "ok"])
    check(s["storm_days"] == 1 and s["levels"]["EKSTREMNO"] == {"n": 2, "obs": 1}, "skupne številke", str(s))
    check(s["day_level"] == {"a": 1, "b": 1, "c": 0, "d": 0}, "dnevna raven (karta ZMERNO+ proti dnevu s strelami)", str(s["day_level"]))
    block = vs.build_block({"days": days})
    check("Zgoden rezultat" in block, "ob malo dneh s strelami opozori na zgoden rezultat")
    check("<table" in block and "ekstremno" in block, "tabela po stopnjah")
    many = [dict(days[0], date=f"2026-07-{i:02d}") for i in range(1, 13)]
    check("Zgoden rezultat" not in vs.build_block({"days": many}), "ob ≥ 10 dneh s strelami opozorila ni")
    check(vs.pct(0, 0) == "—" and vs.pct(1, 4) == "25 %", "delež brez deljenja z nič")


def test_sql():
    print("\nSQL v worker.js ↔ Python")
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT,
                       input=json.dumps({"file": "worker.js", "names": ["LTG_CELLS_SQL"], "calls": [{"expr": "LTG_CELLS_SQL"}]}))
    sql = json.loads(p.stdout)["results"][0]
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE strikes (ts INTEGER NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, dist_km REAL NOT NULL)")
    import random
    rnd = random.Random(4)
    rows = []
    for _ in range(3000):
        rows.append((rnd.randint(0, 2000), rnd.uniform(45.2, 47.0), rnd.uniform(13.2, 16.7), 10.0))
    db.executemany("INSERT INTO strikes VALUES (?,?,?,?)", rows)
    got = {(k, j): (n, t0, t1) for k, j, n, t0, t1 in db.execute(sql, (500, 1500))}
    want = {}
    for ts, la, lo, _ in rows:
        if 500 <= ts < 1500:
            key = (int(round((la - 45.45) / 0.18)), int(round((lo - 13.4) / 0.22)))
            n, t0, t1 = want.get(key, (0, 10**9, -1))
            want[key] = (n + 1, min(t0, ts), max(t1, ts))
    check(got == want, "SQL združi strele v iste celice kot Python", f"{len(got)} proti {len(want)} celic")
    check(sum(v[0] for v in got.values()) == sum(1 for r in rows if 500 <= r[0] < 1500), "okno [od, do) ne izgubi in ne podvoji strel")


def test_levels_match_map():
    print("\nstopnje")
    import generate_storm_map as gm
    for s in list(range(0, 90)) + [7.99, 21.99, 39.99, 59.99]:
        check(vs.score_level(s) == gm.score_level(s), "score_level = generate_storm_map.score_level", f"{s}")


def main():
    for t in (test_window, test_verify, test_summary_and_block, test_sql, test_levels_match_map):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILS.append(t.__name__)
            print(f"  ✗ izjema: {e!r}")
    print(f"\n{CHECKS} preverjanj, {len(FAILS)} napak")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
