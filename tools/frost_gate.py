#!/usr/bin/env python3
"""
tools/frost_gate.py — odloči, ali naj zdaj teče izračun tveganja pozebe.

Isto načelo kot tools/storm_map_gate.py in tools/story_gate.py: GitHubov cron
teče po UTC in zamuja, poleti in pozimi pa je razlika do lokalnega časa
različna (CEST/CET), zato workflow sproži več terminov na dan, ta gate pa
spusti skozi samo tistega, ki je pri nas res v pravem oknu, in prepreči
podvojen tek istega termina isti dan.

Za razliko od storm_map_gate ima frost_gate DVA termina na dan (popoldanski
"predhodni" tek in večerni "glavni" tek — glej spec §3, 20h tek je
pomembnejši, ker sonce takrat že zaide in ima radiacijski model kaj meriti),
zato je stanje ločeno po terminu (slot), ne samo po dnevu. Poleg tega je
sezonsko: izven marca-maja `check` vedno vrne proceed=false, tudi na
--force -- izven sezone smiselnega izračuna preprosto ni (sadno drevje je v
mirovanju), workflow pa lahko vseeno teče vse leto brez posebne YAML logike.

Usage:
  python3 tools/frost_gate.py check <afternoon|evening> [--force]
  python3 tools/frost_gate.py mark <afternoon|evening>
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".frost_gate_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

SEASON_MONTHS = (3, 4, 5)
WINDOWS = {
    "afternoon": (14, 17),  # "15h" tek -- predhodna ocena, ARSO napoved
    "evening": (19, 22),    # "20h" tek -- glavni, sonce je (skoraj) povsod že zašlo
}


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
    args = sys.argv[1:]
    if not args or args[0] not in ("check", "mark"):
        sys.exit("Usage: frost_gate.py check|mark <afternoon|evening> [--force]")
    cmd = args[0]
    slot = args[1] if len(args) > 1 and args[1] in WINDOWS else None
    if slot is None:
        sys.exit(f"manjka termin (afternoon|evening): {args}")
    force = "--force" in args

    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()

    if cmd == "mark":
        state = load_state()
        state[slot] = {"lastRun": today, "lastRunAt": now.isoformat()}
        save_state(state)
        print(f"✓ zabeleženo: {slot} termin za {today}")
        return 0

    if now.month not in SEASON_MONTHS:
        emit(False, f"izven sezone pozebe (mesec {now.month}, sezona je marec-maj)")
        return 0

    state = load_state()
    if state.get(slot, {}).get("lastRun") == today and not force:
        emit(False, f"{slot} termin za {today} je že opravljen")
        return 0

    start, end = WINDOWS[slot]
    if not force and not (start <= now.hour < end):
        emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                     f"okno za {slot} je {start}:00-{end}:00")
        return 0

    emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
