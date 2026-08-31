#!/usr/bin/env python3
"""
tools/update_history_gate.py — odloči, ali update-history.yml danes sploh
potrebuje pravi tek, ali je včerajšnji dan že zabeležen.

Zakaj je to potrebno: GitHubov cron za ta workflow (01:15 UTC) redno zamuja —
ne le za uro ali dve kot drugod v repozitoriju, ampak je konec avgusta 2026 en
tek pristal šele ob 12:46 UTC (skoraj 11,5h zamude). Ker workflow za "record
watch" na vrhu naslovnice (tools/inject_record_watch.py) prikazuje včerajšnji
dan, taka zamuda pomeni, da stran polovico dneva kaže rekord za dan PRED
včerajšnjim.

Popravek je isto načelo kot tools/story_gate.py / tools/storm_map_gate.py
(več sproženih terminov čez dan, gate spusti skozi samo tistega, ki dejansko
opravi delo) — a brez ločene stanjske datoteke: history.json JE stanje. Če
včerajšnji dan že ima "src":"station", je delo za danes že opravljeno in
naslednji sproženi termin samo izstopi, ne da bi znova klical Ecowitt/
Open-Meteo za cel mesec (update_history.py ob vsakem teku znova povpraša
vse dni od 1. v mesecu do včeraj — glej opombo tam). Če je bil zapisan le
rezervni "src":"era5" (Ecowitt tisti dan ni bil dosegljiv) ali dneva sploh
še ni, gate pusti skozi — morda je postaja medtem spet dosegljiva.

Ni okna dneva (ne "prezgodaj", ne "prepozno") kot pri zgodbi/karti, ker tu ni
javne objave, vezane na uro — bolje pozno pravilen rekord kot noben.

Usage:
  python3 tools/update_history_gate.py [--force]
"""
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(ROOT, "history.json")
TZ = ZoneInfo("Europe/Berlin")  # isti pas kot update_history.py/inject_record_watch.py


def emit(proceed, reason):
    print(f"proceed={proceed} — {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"proceed={'true' if proceed else 'false'}\n")


def main():
    force = "--force" in sys.argv[1:]
    yesterday = (datetime.now(TZ).date() - timedelta(days=1)).isoformat()

    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except Exception as e:
        emit(True, f"history.json ni bilo mogoče prebrati ({e})")
        return 0

    if not force and hist.get(yesterday, {}).get("src") == "station":
        emit(False, f"{yesterday} je že zabeležen z meritvijo postaje — verjetno je zgodnejši sprožen termin že opravil delo")
        return 0

    emit(True, f"{yesterday} še nima meritve postaje" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
