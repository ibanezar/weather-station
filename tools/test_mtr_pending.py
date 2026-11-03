#!/usr/bin/env python3
"""
tools/test_mtr_pending.py — števci »Čaka na podatke« (tools/mtr_pending.py → data/mtr-pending.json).

Sintetični dnevniki v začasni mapi: razred »že teče« se ne šteje k pragu, razred šteje manjši n od Tmax/Tmin,
zimski dnevi so samo nov–feb, sneg je nad 1 cm (0,01 m), prazna/manjkajoča datoteka da ničle, ne napake.
Preveri tudi, da je committana data/mtr-pending.json veljavna in da ne vsebuje ničesar o hiši.
"""
import csv
import datetime as dt
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mtr_pending as mp  # noqa: E402

fails = 0


def check(name, ok):
    global fails
    print(("  ✓ " if ok else "  ✗ ") + name)
    fails += 0 if ok else 1


tmp = tempfile.mkdtemp()
live = os.path.join(tmp, "live.csv")
prof = os.path.join(tmp, "prof.csv")
ver = os.path.join(tmp, "ver.json")

# živi dnevnik: za vsak od 3 dni po ena osvežitev v razredu 6–12 h (hours_before 8) in ena »že teče« (−2)
H = ["issued_at", "valid_at", "lead_days", "hours_before", "tmax", "tmin", "pop", "p_frost", "mm", "om_tmax", "om_tmin"]
days = ["2026-11-0%d" % i for i in (1, 2, 3)]
with open(live, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(H)
    for d in days:
        w.writerow(["2026-10-30T00:00:00Z", d, 1, 8.0, 10.0, 2.0, 0.5, 0.1, "", 9.0, 3.0])
        w.writerow(["2026-10-30T20:00:00Z", d, 1, -2.0, 10.0, 2.0, 0.5, 0.1, "", 9.0, 3.0])
V = {d: {"actual": {"tmax": 11.0, "tmin": 1.0}, "meteorec": {"tmax": 10.5, "tmin": 1.5}} for d in days[:2]}
V[days[2]] = {"actual": {"tmax": 11.0}, "meteorec": {"tmax": 10.5}}      # Tmin manjka → razred šteje 2, ne 3
json.dump(V, open(ver, "w"))

L = mp.live_counts(list(csv.DictReader(open(live, encoding="utf-8"))), V)
check("razred »že teče« ne šteje k pragu", all(not k.startswith("že teče") for k in L["classes"]))
check("razred šteje manjši n od Tmax in Tmin (2, ne 3)", L["classes"].get("6–12 h") == 2)
check("best in best_class", L["best"] == 2 and L["best_class"] == "6–12 h")
check("prag je MIN_DAYS evalne skripte", L["target"] == mp.ev.MIN_DAYS == 20)

PH = ["issued_at", "valid_at", "lead_days", "snow_max"]
rows = [("2026-10-24", 0.0), ("2026-10-24", 0.0), ("2026-11-02", 0.0), ("2026-12-05", 0.02),
        ("2027-01-10", 0.01), ("2027-03-01", 0.5), ("2027-02-30", 0.9), ("", 1.0)]
with open(prof, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(PH)
    for d, sn in rows:
        w.writerow([d, "2027-01-01", 1, sn])
P = mp.profile_counts(list(csv.DictReader(open(prof, encoding="utf-8"))))
check("dnevi se štejejo po datumu izdaje (podvojen dan enkrat, neveljaven datum preskočen)", P["days"] == 5)
check("zimski dnevi samo nov–feb (2. 11., 5. 12., 10. 1. → 3; 24. 10. in 1. 3. ne)", P["winter_days"] == 3)
check("sneg nad 1 cm: 0,01 m ni dovolj, 0,02 in 0,5 so", P["snow_days"] == 2)
check("prag zimskih dni 120", P["target"] == 120)

E = mp.build(live_log=os.path.join(tmp, "x.csv"), profile_log=os.path.join(tmp, "y.csv"), verif=os.path.join(tmp, "z.json"))
check("manjkajoče datoteke dajo ničle brez napake",
      E["live"]["best"] == 0 and E["profile"]["days"] == 0 and E["live"]["best_class"] is None)

real = os.path.join(os.path.dirname(HERE), "data", "mtr-pending.json")
if os.path.exists(real):
    txt = open(real, encoding="utf-8").read()
    d = json.loads(txt)
    check("committana datoteka ima live in profile", "live" in d and "profile" in d and "generated_at" in d)
    check("brez notranjih ključev", "indoor" not in txt.lower() and "tempinf" not in txt.lower())

print("\n%d napak" % fails if fails else "\nVse v redu.")
sys.exit(1 if fails else 0)
