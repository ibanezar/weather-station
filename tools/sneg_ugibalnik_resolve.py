#!/usr/bin/env python3
"""
tools/sneg_ugibalnik_resolve.py — razrešitev snežnega ugibalnika (/zima/sneg-ugibalnik/, 18. 11. 2026).

Prvi sneg sezone je dogodek `prvi-sneg-<sezona>` v `novosti.json` (zazna ga detect_first_snow() v tools/seo_smart_routine.py:
prva snežna odeja >= 1 cm na ARSO postaji Gornji Grad, od 1. oktobra). Ta skript samo prepiše datum v
`data/sneg-ugibalnik.json`, ki ga bereta stran (JS) in worker (zaprtje ugibanja). Ničesar ne računa na novo: dogodek je edini
vir resnice, da se ugibalnik in stran /novosti/ ne razideta.

- Dogodek z `gap` (med arhivom in prvim odčitkom manjkajo dnevi): datum je »prvi v podatkih, ki jih imamo«; zapišemo `gap`,
  da stran to pove. Ne trdimo, da je bil sneg res prvi.
- Brez dogodka do 30. aprila: `brez_snega: true` (ugibanje je mimo, zmagovalca ni).
- Datoteka se prepiše samo, če se vsebina spremeni (brez dnevnih commitov zaradi časovnega žiga).

Usage:
    python3 tools/sneg_ugibalnik_resolve.py [--today YYYY-MM-DD]
"""
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVOSTI = os.path.join(ROOT, "novosti.json")
OUT = os.path.join(ROOT, "data", "sneg-ugibalnik.json")


def season_of(today):
    return today.year if today.month >= 7 else today.year - 1


def build(today, events):
    s = season_of(today)
    ev = next((e for e in events if e.get("type") == "prvi-sneg" and e.get("slug") == f"prvi-sneg-{s}"), None)
    out = {"sezona": s, "prvi_sneg": None, "vir": "ARSO · Gornji Grad (428 m), višina snežne odeje ≥ 1 cm",
           "novosti": f"/novosti/prvi-sneg-{s}/", "gap": None, "brez_snega": False}
    if ev:
        out["prvi_sneg"] = ev["date"]
        out["vrednost_cm"] = ev.get("value")
        out["gap"] = ev.get("gap")
    elif today > datetime.date(s + 1, 4, 30):
        out["brez_snega"] = True
    return out


def main():
    today = datetime.date.today()
    if "--today" in sys.argv:
        today = datetime.date.fromisoformat(sys.argv[sys.argv.index("--today") + 1])
    events = json.load(open(NOVOSTI, encoding="utf-8"))
    new = build(today, events)
    try:
        old = json.load(open(OUT, encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if {k: v for k, v in old.items() if k != "posodobljeno"} == new:
        print("Brez sprememb:", json.dumps(new, ensure_ascii=False))
        return
    new["posodobljeno"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("✓ data/sneg-ugibalnik.json:", json.dumps(new, ensure_ascii=False))


if __name__ == "__main__":
    main()
