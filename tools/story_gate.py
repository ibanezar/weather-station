#!/usr/bin/env python3
"""
tools/story_gate.py — odloči, ali naj se dnevna zgodba danes sploh objavi.

Zakaj je to potrebno:

1. GitHubov cron teče po UTC, mi pa hočemo objavo ob 6:00 po naši uri.
   Poleti je to 04:00 UTC, pozimi 05:00 UTC. Workflow zato sproži OBA termina,
   ta gate pa pusti skozi samo tistega, ki se pri nas res zgodi ob 6h ali kasneje.

2. GitHubov cron redno zamuja eno do dve uri (glej opombo v daily-post.yml), konec
   avgusta 2026 pa je nekaj dni zapored zamujal 6-12 ur (oba scheduled teka sta
   pristala popoldne namesto zjutraj) in je okno 6:00-12:00 zamudil vsak dan, štiri
   dni zapored ni šla ven nobena kartica. Zato okno sega do 15:00 -- zgodba
   "kdaj bo danes začelo deževati" pri 17h res ne pove več nič uporabnega, po 15h
   pa se rajši objavi malce pozna kartica kot nobena.

3. Ker se lahko sprožita oba termina, si zapomnimo, kateri dan je zgodba
   že šla ven, in drugega preskočimo.

4. VEČERNA kartica (`--evening`, 13. 10. 2026): zmrzal/hladno jutro je novica
   dan prej, zvečer -- ko jo je še mogoče upoštevati (pokriti rastline, obleči
   otroke) --, ne opoldne, ko je jutro že mimo. Okno 17:00-23:00 (cron zamuja
   ure), stanje je ločeno (`.story_evening_state.json`, da se dva workflowa ne
   tepeta za isto datoteko pri commitu). Jutranja zgodba iz stanja izve, da je
   večerna že šla ven (`evening_posted_for()`), in jutranje teme ne ponovi.

Usage:
  python3 tools/story_gate.py check [--force]            # nastavi proceed=true|false
  python3 tools/story_gate.py mark                       # zabeleži, da je zgodba objavljena
  python3 tools/story_gate.py check --evening [--force]  # večerna kartica za jutri
  python3 tools/story_gate.py mark --evening
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".story_state.json")
STATE_EVENING = os.path.join(ROOT, "tools", ".story_evening_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

WINDOW_START = 6   # ne prej kot ob 6:00 po naši uri
WINDOW_END = 7     # 19. 10. 2026 (Filip): zgodba je napoved dneva, zato gre ven do 7:00 ali
                   # sploh ne. Popoldanska kartica »danes bo hladneje« je lagala (ohladitev
                   # je bila že mimo/šele popoldne). Zamujen cron = ni kartice, ne pozna kartica.


EVENING_START = 17  # ne prej kot ob 17:00 po naši uri
EVENING_END = 23    # cron zamuja ure; po 23h kartica za jutri ni več "zvečer"


def load_state(path=STATE):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state, path=STATE):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def evening_posted_for(date_iso):
    """Ali je večerna kartica za ta dan (datum JUTRIŠNJEGA jutra) že šla ven."""
    return load_state(STATE_EVENING).get("lastFor") == date_iso


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

    if "--evening" in sys.argv:
        tomorrow = (now.date() + datetime.timedelta(days=1)).isoformat()
        state = load_state(STATE_EVENING)
        if cmd == "mark":
            state["lastFor"] = tomorrow
            state["lastPostedAt"] = now.isoformat()
            save_state(state, STATE_EVENING)
            print(f"✓ zabeleženo: večerna kartica za {tomorrow}")
            return 0
        force = "--force" in sys.argv
        if state.get("lastFor") == tomorrow and not force:
            emit(False, f"večerna kartica za {tomorrow} je že objavljena")
            return 0
        if not force and not (EVENING_START <= now.hour < EVENING_END):
            emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                        f"okno za večerno kartico je {EVENING_START}:00–{EVENING_END}:00")
            return 0
        emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
        return 0

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
