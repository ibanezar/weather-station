#!/usr/bin/env python3
"""tools/test_species_calibration.py — ročne umeritve vrst (CALIBRATION) so v species_rules.yaml in ničesar drugega ne premaknejo.

Preverja: vsak vnos CALIBRATION ima razlog; umerjeni polji sta v YAML; vse druge mikorizne vrste imajo še vedno
skupinski zamik (nenamerna sprememba skupine bi tiho premaknila ~90 vrst); lisička ima 4–14 z opombo.
Zaženi:  python3 tools/test_species_calibration.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gobe_model as gm  # noqa: E402
import import_species_db as imp  # noqa: E402

fails = []


def check(name, cond):
    print(("  ✓ " if cond else "  ✗ ") + name)
    if not cond:
        fails.append(name)


rules = gm.load_rules()
by = {s["id"]: s for s in rules["species"]}
check("vsak vnos CALIBRATION ima razlog", all(c.get("razlog") for c in imp.CALIBRATION.values()))
check("vse umerjene vrste obstajajo v YAML", all(k in by for k in imp.CALIBRATION))
for sid, cal in imp.CALIBRATION.items():
    for field, val in cal.items():
        if field == "razlog" or field == "fruiting_lag_days":
            continue
        check(f"{sid}: {field} = {val} v YAML", by[sid][field] == val)
lis = by["cantharellus_cibarius"]["fruiting_lag_days"]
check("lisička: zamik 4–14", (lis["min"], lis["max"]) == (4, 14))
text = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "species_rules.yaml"), encoding="utf-8").read()
check("lisička: opomba »ROČNO UMERJENO« ob zamiku", "{ min: 4, max: 14 }  # ROČNO UMERJENO" in text)
default = imp.ecology_lag("mikorizna")
others = [s for s in rules["species"] if s.get("ecology") == "mikorizna" and s["id"] not in imp.CALIBRATION
          and s.get("fruiting_lag_days")]
check("druge mikorizne vrste imajo skupinski zamik", all((s["fruiting_lag_days"]["min"], s["fruiting_lag_days"]["max"]) == tuple(default)
                                                         for s in others) and len(others) > 50)
check("past_days_needed ostane enak (najdaljši zamik 16)", gm.past_days_needed(rules) == 16 + gm.BASE_WINDOW_DAYS)
print(f"\n{len(fails)} neuspelih")
sys.exit(1 if fails else 0)
