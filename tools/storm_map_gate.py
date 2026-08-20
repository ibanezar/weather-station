#!/usr/bin/env python3
"""
tools/storm_map_gate.py — odloči, ali naj se danes sploh sestavi/objavi
nevihtna karta Slovenije.

Isto načelo kot tools/story_gate.py (glej tam za polno obrazložitev): GitHubov
cron teče po UTC in redno zamuja, zato workflow sproži dva termina (08:00 in
09:00 UTC, kar je 10:00 po naši uri poleti oz. pozimi), ta gate pa pusti skozi
samo tistega, ki se pri nas res zgodi v oknu, in prepreči dvojno objavo istega
dne. Ločena stanja od story_gate.py (drug ritem, druga vsebina).

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

WINDOW_START = 10  # ne prej kot ob 10:00 po naši uri
WINDOW_END = 15    # in ne kasneje kot ob 15:00 (cron zamuja tudi po nekaj ur)


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
