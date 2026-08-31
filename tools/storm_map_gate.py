#!/usr/bin/env python3
"""
tools/storm_map_gate.py — odloči, ali naj se danes sploh sestavi/objavi
nevihtna karta Slovenije.

Isto načelo kot tools/story_gate.py (glej tam za polno obrazložitev): GitHubov
cron teče po UTC in redno zamuja, zato workflow sproži dva termina (05:00 in
06:00 UTC, kar je 7:00 po naši uri poleti oz. pozimi -- karta mora biti nova
do 7h zjutraj), ta gate pa pusti skozi samo tistega, ki se pri nas res zgodi
v oknu, in prepreči dvojno objavo istega dne. Ločena stanja od story_gate.py
(drug ritem, druga vsebina).

Usage:
  python3 tools/storm_map_gate.py check [--force]
  python3 tools/storm_map_gate.py mark
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".storm_map_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

WINDOW_START = 6   # karta mora biti nova do 7:00 zjutraj (zahteva 31. 8. 2026)
                   # -- začne se uro prej, da cron, ki zamuja le nekaj minut,
                   # ni izločen po nepotrebnem.
WINDOW_END = 8     # trdi rok je 7:00; do 8:00 je varovalka za manjšo (do ~1h)
                   # zamudo GitHubovega crona. Karta rojena po 8. uri ni več
                   # "pripravljena zjutraj", zato ta dan ostane na zadnji
                   # znani (nevihte-forecast.yml jo vgradi jasno označeno kot
                   # staro -- glej tools/inject_storm_map.py) -- boljše kot
                   # trditi, da je karta iz 7h, ko dejansko ni.


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def emit(proceed, reason):
    print(f"proceed={proceed} — {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"proceed={'true' if proceed else 'false'}\n")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()

    if cmd == "mark":
        state = load_state()
        state["lastRun"] = today
        state["lastRunAt"] = now.isoformat()
        save_state(state)
        print(f"✓ zabeleženo: karta objavljena {today}")
        return 0

    force = "--force" in sys.argv
    state = load_state()

    if state.get("lastRun") == today and not force:
        emit(False, f"karta za {today} je že sestavljena")
        return 0
    if not force and not (WINDOW_START <= now.hour < WINDOW_END):
        emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                    f"okno je {WINDOW_START}:00–{WINDOW_END}:00")
        return 0

    emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
