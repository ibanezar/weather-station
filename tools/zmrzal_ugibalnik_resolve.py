#!/usr/bin/env python3
"""
tools/zmrzal_ugibalnik_resolve.py — razrešitev ugibalnika zmrzali (/ugibalnik-zmrzal/, 19. 11. 2026).

Prva zmrzal sezone je dogodek `prva-zmrzal-<sezona>` v `novosti.json` (zazna ga detect_events() v tools/seo_smart_routine.py: prvi dan od
1. septembra z najnižjo temperaturo <= 0 °C na postaji IREICA1). Ta skript samo prepiše datum v `data/zmrzal-ugibalnik.json`, ki ga bereta
stran (JS) in worker (zaprtje ugibanja). Ničesar ne računa na novo: dogodek je edini vir resnice, da se ugibalnik in stran /novosti/ ne razideta.
(Do 19. 11. 2026 ta dogodek ni nastal nikoli, zaradi napake v pogoju »prej ni bilo zmrzali«; glej tools/test_first_frost.py.)

- Sezona se začne 1. avgusta (takrat se odpre ugibanje), datum ugiba pa je lahko od 1. septembra do 31. decembra.
- Brez dogodka do 31. decembra: `brez_zmrzali: true` (ugibanje je mimo, zmagovalca ni).
- Do 1. avgusta naslednje leta velja še sezona prejšnjega leta (kaže rezultat); nova sezona se odpre sama.
- Datoteka se prepiše samo, če se vsebina spremeni (brez dnevnih commitov zaradi časovnega žiga).

Usage:
    python3 tools/zmrzal_ugibalnik_resolve.py [--today YYYY-MM-DD]
"""
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOVOSTI = os.path.join(ROOT, "novosti.json")
OUT = os.path.join(ROOT, "data", "zmrzal-ugibalnik.json")
SEASON_MONTH = 8          # ↔ data-season-month na strani in `_zmrzalSezona()` v worker.js (tools/test_zmrzal_ugibalnik.mjs)
END_MD = (12, 31)         # zadnji dan ugibanja


def season_of(today):
    return today.year if today.month >= SEASON_MONTH else today.year - 1


def build(today, events):
    s = season_of(today)
    ev = next((e for e in events if e.get("type") == "prva-zmrzal" and e.get("slug") == f"prva-zmrzal-{s}"), None)
    out = {"sezona": s, "prva_zmrzal": None, "vir": "IREICA1 (Rečica ob Savinji, 366 m), najnižja temperatura dneva ≤ 0 °C, od 1. septembra",
           "novosti": f"/novosti/prva-zmrzal-{s}/", "brez_zmrzali": False}
    if ev:
        out["prva_zmrzal"] = ev["date"]
        out["vrednost_c"] = ev.get("value")
    elif today > datetime.date(s, *END_MD):
        out["brez_zmrzali"] = True
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
    print("✓ data/zmrzal-ugibalnik.json:", json.dumps(new, ensure_ascii=False))


if __name__ == "__main__":
    main()
