#!/usr/bin/env python3
"""Preizkus beleženja sevanja sosednje postaje in primerjave prvega žarka (5. 11. 2026).

1. `_vpsAppend()` iz PRAVEGA worker.js (izrezan kot v test_parity): doda posnetek, zavrne star/enak/neveljaven, odreže 72 h,
   in v izhodu ni ničesar razen štirih števil (zasebnost: notranji blok soseda se ne prebere in ne shrani).
2. `log_varpolje_solar`: odgovor workerja → vrstice (lokalni čas navzdol na 5 min), združevanje, zadrževanje.
3. `eval_sonce_varpolje`: sintetični dnevi z znanim zamikom (IREICA1 skoči ob 8.40, Varpolje ob 7.20) → razlika +80 min;
   razsodba je prazna pod MIN_DAYS in se pojavi z njim; isti detektor kot eval_sonce.
4. Nobena datoteka tega niza ne omenja notranjih meritev.
"""
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import log_varpolje_solar as lv  # noqa: E402
import eval_sonce_varpolje as ev  # noqa: E402

fails, checks = [], 0


def check(ok, name, detail=""):
    global checks
    checks += 1
    if not ok:
        fails.append(f"{name} {detail}")


def js(names, exprs, prelude=""):
    p = subprocess.run(["node", os.path.join(HERE, "_parity_js.mjs")], capture_output=True, text=True, cwd=ROOT, timeout=60,
                       input=json.dumps({"file": "worker.js", "names": names, "calls": [{"expr": e} for e in exprs], "prelude": prelude}))
    out = json.loads(p.stdout)
    if "error" in out:
        raise RuntimeError(out["error"])
    return out["results"]


# ---------- 1. _vpsAppend ----------
NOW = 1_800_000_000_000  # ms
def vp(sol=120.5, age_s=60, **extra):
    d = {"updated_utc": datetime.datetime.fromtimestamp(NOW / 1000 - age_s, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "current": {"solar_radiation_wm2": sol, "uv_index": 2, "temp_c": 7.04}}
    d["current"].update(extra)
    return d
T = int(NOW / 1000) - 60
exprs = [
    f"_vpsAppend([], {json.dumps(vp())}, {NOW})",                                            # 0 nov posnetek
    f"_vpsAppend([[{T}, 100, 1, 5]], {json.dumps(vp())}, {NOW})",                             # 1 isti posnetek
    f"_vpsAppend([], {json.dumps(vp(age_s=20 * 60))}, {NOW})",                                # 2 star 20 min
    f"_vpsAppend([], {json.dumps(vp(sol=-3))}, {NOW})",                                       # 3 negativno
    f"_vpsAppend([], {json.dumps(vp(sol=5000))}, {NOW})",                                     # 4 nemogoče
    f"_vpsAppend([], {json.dumps(vp(sol=None))}, {NOW})",                                     # 5 brez sevanja
    f"_vpsAppend([[{int(NOW / 1000) - 80 * 3600}, 50, 1, 5]], {json.dumps(vp())}, {NOW})",    # 6 odreže >72 h
    f"_vpsAppend([], {json.dumps(vp(uv_index=None))}, {NOW})",                                # 7 UV null
    f"_vpsAppend([], {json.dumps(vp(indoor={'temp_c': 25.1}, tempinf=77))}, {NOW})",          # 8 notranji blok v vhodu
    f"_vpsAppend([], {json.dumps({**vp(), 'indoor': {'temp_c': 24.0}})}, {NOW})",             # 9 notranji blok ob strani
    f"_vpsAppend([], null, {NOW})",                                                           # 10 brez odgovora
    f"_vpsAppend([[{T + 600}, 100, 1, 5]], {json.dumps(vp())}, {NOW})",                       # 11 starejši od zadnjega
]
r = js(["_vpsAppend", "VPS_HOLD_MS", "VPS_MAX_AGE_MS"], exprs)
check(r[0] == [[T, 120.5, 2, 7]], "nov posnetek: [t, W/m², UV, °C]", str(r[0]))
check(r[1] is None, "isti posnetek se ne podvoji", str(r[1]))
check(r[2] is None, "posnetek, star 20 min, ni meritev", str(r[2]))
check(r[3] is None and r[4] is None and r[5] is None, "negativno, nemogoče in manjkajoče sevanje se zavrnejo", str(r[3:6]))
check(r[6] == [[T, 120.5, 2, 7]], "zapisi starejši od 72 h odpadejo", str(r[6]))
check(r[7] and r[7][0][2] is None, "UV null ostane null", str(r[7]))
for i in (8, 9):
    flat = json.dumps(r[i])
    check(r[i] is not None and all(len(x) == 4 for x in r[i]) and "25" not in flat.replace("120.5", "") and "24" not in flat, f"notranji blok se ne shrani (vhod {i})", flat)
check(r[10] is None, "brez odgovora ni zapisa")
check(r[11] is None, "starejši posnetek od zadnjega ne gre na konec", str(r[11]))

# ---------- 2. log_varpolje_solar ----------
def unix(y, mo, d, h, mi, s=0):
    z = datetime.datetime(y, mo, d, h, mi, s, tzinfo=lv.TZ).astimezone(datetime.timezone.utc)
    return int(z.timestamp())
payload = {"ok": True, "rows": [[unix(2026, 11, 4, 7, 42, 17), 55.0, 0, 3.2], [unix(2026, 11, 4, 7, 44, 0), 61.0, 0, 3.3],  # isti 5-min kos: zmaga novejši
                                 [unix(2026, 11, 4, 8, 5, 0), 130.4, 1, None], ["x", 1, 2, 3], [unix(2026, 11, 4, 9, 0), None, 0, 1]]}
rows = lv.rows_from_payload(payload)
check([(r["time_local"], r["solar_wm2"]) for r in rows] == [("07:40", "61.0"), ("08:05", "130.4")], "lokalni čas navzdol na 5 min, neveljavno se preskoči",
      str([(r["time_local"], r["solar_wm2"]) for r in rows]))
check(rows[1]["temp_c"] == "" and rows[0]["uv"] == "0", "manjkajoča temperatura je prazna")
old = [{"date": "2026-11-04", "time_local": "07:40", "solar_wm2": "1.0", "uv": "0", "temp_c": "3"},
       {"date": "2025-01-01", "time_local": "08:00", "solar_wm2": "1.0", "uv": "0", "temp_c": "3"}]
m = lv.merge(old, rows, today=datetime.date(2026, 11, 5))
check([(r["date"], r["time_local"], r["solar_wm2"]) for r in m] == [("2026-11-04", "07:40", "61.0"), ("2026-11-04", "08:05", "130.4")],
      "združevanje: novejše prepiše, staro (> 120 dni) odpade", str(m))
check(lv.FIELDS == ["date", "time_local", "solar_wm2", "uv", "temp_c"], "polja zapisa so samo zunanja")

# ---------- 3. eval_sonce_varpolje ----------
def day(jump_min, peak=400):
    """Zapis 5-minutnih točk od 6.00 do 11.00: nizko sevanje do skoka, nato hitro naraste in ostane visoko."""
    return [(m, 5.0 if m < jump_min else float(peak)) for m in range(6 * 60, 11 * 60 + 1, 5)]
d1 = {f"2026-10-{d:02d}": day(8 * 60 + 40) for d in range(1, 21)}                       # IREICA1: skok ob 8.40
dv = {f"2026-10-{d:02d}": day(7 * 60 + 20) for d in range(1, 21)}                       # Varpolje: ob 7.20
rows = ev.compare(d1, dv)
check(len(rows) == 20 and all(abs(r["jutro"]["razlika_min"] - 80.0) < 1e-9 for r in rows), "razlika IREICA1 − IREICA7 je +80 min", str(rows[:1]))
s = ev.summarize(rows)
check(s["jutro"]["n"] == 20 and s["jutro"]["mediana_min"] == 80.0 and s["razsodba"] == "ireica1_pozneje", "povzetek: 20 dni, +80 min, IREICA1 pozneje", str(s))
check(ev.summarize(rows[:14])["razsodba"] is None, "pod MIN_DAYS razsodbe ni")
same = ev.summarize(ev.compare(d1, d1))
check(same["razsodba"] == "podobno" and same["jutro"]["mediana_min"] == 0.0, "enaka postaji: razlika 0, »podobno«", str(same))
early = ev.summarize(ev.compare(dv, d1))
check(early["razsodba"] == "ireica1_prej", "obratno: IREICA1 prej", str(early))
# razlika v kosih po 5 min: Varpolje zapiše vsak 5. min z vrzeljo; mreža vrzel (1 korak) zapolni
gap = [(m, v) for m, v in day(7 * 60 + 20) if m != 7 * 60 + 25]
check(any(m == 7 * 60 + 25 for m, _ in ev.to_grid(gap)), "mreža zapolni vrzel enega koraka")
check(ev.compare({"2026-10-01": day(8 * 60 + 40)}, {"2026-10-02": day(7 * 60 + 20)}) == [], "dni brez obeh zapisov ni v primerjavi")
cloud = [(m, 5.0) for m in range(6 * 60, 11 * 60 + 1, 5)]
check(ev.first_ray(cloud) is None, "brez sevanja (megla/oblak) skoka ne ugibamo")
check("def detect_first_ray" not in open(os.path.join(HERE, "eval_sonce_varpolje.py"), encoding="utf-8").read(), "detektor ni podvojen v eval_sonce_varpolje (uporablja eval_sonce)")

# ---------- 4. zasebnost ----------
for f in ("worker.js", "tools/log_varpolje_solar.py", "tools/eval_sonce_varpolje.py"):
    text = open(os.path.join(ROOT, f), encoding="utf-8").read()
    if f == "worker.js":
        text = text[text.index("const VPS_KEY"):text.index("async function _cronCheckOcene")]
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith(("//", "#")))
    check(not re.search(r"indoor|tempinf", re.sub(r'""".*?"""', "", code, flags=re.S), re.I), f"{f}: koda ne omenja notranjih meritev")

print(f"{checks} preverjanj, {len(fails)} napak")
for f in fails:
    print("  ✗", f)
sys.exit(1 if fails else 0)
