#!/usr/bin/env python3
"""
tools/digest_gate.py — odloči, ali naj se jutranji povzetek danes sploh pošlje.

Ista logika kot tools/story_gate.py (glej tisto datoteko za polno obrazložitev
oken/dvojnega crona/DST) — ločena datoteka in lastno stanje, ker gre za
drugačen kanal (potisno obvestilo, ne FB/IG kartica) z drugim oknom in ker si
generatorji v tem repozitoriju namenoma ne delijo take logike (glej CLAUDE.md).

Okno je 7:00–9:00 po naši uri: kdor odpre telefon zjutraj, naj povzetek še
najde aktualnega; po 9h "danes zjutraj" ni več to, kar bralec pričakuje.

Usage:
  python3 tools/digest_gate.py check [--force]   # nastavi proceed=true|false
  python3 tools/digest_gate.py mark              # zabeleži, da je povzetek poslan
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".digest_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

WINDOW_START = 7
WINDOW_END = 9


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
        state["lastSent"] = today
        state["lastSentAt"] = now.isoformat()
        save_state(state)
        print(f"✓ zabeleženo: povzetek poslan {today}")
        return 0

    force = "--force" in sys.argv
    state = load_state()

    if state.get("lastSent") == today and not force:
        emit(False, f"povzetek za {today} je že poslan")
        return 0
    if not force and not (WINDOW_START <= now.hour < WINDOW_END):
        emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                    f"okno za pošiljanje je {WINDOW_START}:00–{WINDOW_END}:00")
        return 0

    emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
