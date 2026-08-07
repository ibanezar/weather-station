#!/usr/bin/env python3
"""
tools/story_gate.py — odloči, ali naj se dnevna zgodba danes sploh objavi.

Zakaj je to potrebno:

1. GitHubov cron teče po UTC, mi pa hočemo objavo ob 6:00 po naši uri.
   Poleti je to 04:00 UTC, pozimi 05:00 UTC. Workflow zato sproži OBA termina,
   ta gate pa pusti skozi samo tistega, ki se pri nas res zgodi ob 6h ali kasneje.

2. GitHubov cron redno zamuja eno do dve uri (glej opombo v daily-post.yml).
   Zato ne zahtevamo natanko 6h, ampak okno med 6:00 in 12:00 -- zgodba
   "kdaj bo danes začelo deževati" ob 14h ne pove več nič uporabnega, zato
   se po 12h rajši ne objavi nič.

3. Ker se lahko sprožita oba termina, si zapomnimo, kateri dan je zgodba
   že šla ven, in drugega preskočimo.

Usage:
  python3 tools/story_gate.py check [--force]   # nastavi proceed=true|false
  python3 tools/story_gate.py mark              # zabeleži, da je zgodba objavljena
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".story_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

WINDOW_START = 6   # ne prej kot ob 6:00 po naši uri
WINDOW_END = 12    # in ne kasneje kot ob 12:00


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
        state["lastPosted"] = today
        state["lastPostedAt"] = now.isoformat()
        save_state(state)
        print(f"✓ zabeleženo: zgodba objavljena {today}")
        return 0

    force = "--force" in sys.argv
    state = load_state()

    if state.get("lastPosted") == today and not force:
        emit(False, f"zgodba za {today} je že objavljena")
        return 0
    if not force and not (WINDOW_START <= now.hour < WINDOW_END):
        emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                    f"okno za objavo je {WINDOW_START}:00–{WINDOW_END}:00")
        return 0

    emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
