#!/usr/bin/env python3
"""
tools/igra_gate.py — odloči, ali naj se zdaj sestavi nivo dneva za /igra/.

Isto načelo kot tools/story_gate.py in tools/storm_map_gate.py (glej tam za
polno obrazložitev): GitHubov cron teče po UTC in redno zamuja, zato workflow
sproži dva termina (4:45 in 5:45 UTC, kar je 6:45 po naši uri poleti oz.
pozimi), ta gate pa spusti skozi samo tistega, ki se pri nas res zgodi v oknu,
in prepreči dvojno sestavljanje istega dne.

Zakaj 4:45/5:45 in ne 5:00/6:00 kot pri nevihtni karti: zahteva je, da je nivo
NA VOLJO ob 7:00, ne da se takrat šele začne sestavljati. Petnajst minut prej
je dovolj, da tek in objava na GitHub Pages steceta pred sedmo.

Ločeno stanje od ostalih gate-ov (drug ritem, druga vsebina) — glej opozorilo
v CLAUDE.md, da se stanja ne delijo.

Uporaba:
  python3 tools/igra_gate.py check [--force]
  python3 tools/igra_gate.py mark
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "tools", ".igra_state.json")
TZ = ZoneInfo("Europe/Ljubljana")

WINDOW_START = 6    # nivo mora biti nov do 7:00; okno se začne uro prej, da
                    # cron z manjšo zamudo ni izločen po nepotrebnem.
WINDOW_END = 12     # Zgornja meja je kompromis, ne varnostna omejitev kot pri
                    # nevihtni karti. Nivo, sestavljen opoldne, je še vedno
                    # DANAŠNJI in boljši od včerajšnjega, zato okno ni ozko.
                    # Popoldne pa se ne sme več spremeniti: igra obljublja
                    # "isti dan, isti nivo za vse" in kdor je igral zjutraj,
                    # ne sme zvečer dobiti drugačnega stropa. Če cron zgreši
                    # celo dopoldne, ostane včerajšnji nivo, ki ga stran jasno
                    # označi kot nesvežega (🟡/🔴) — raje star in označen kot
                    # tiho zamenjan sredi dneva.


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
        print(f"✓ zabeleženo: nivo za {today} sestavljen")
        return 0

    force = "--force" in sys.argv
    state = load_state()

    if state.get("lastRun") == today and not force:
        emit(False, f"nivo za {today} je že sestavljen")
        return 0
    if not force and not (WINDOW_START <= now.hour < WINDOW_END):
        emit(False, f"lokalna ura je {now.hour}:{now.minute:02d}, "
                    f"okno je {WINDOW_START}:00–{WINDOW_END}:00")
        return 0

    emit(True, f"lokalni čas {now.strftime('%H:%M')}" + (" (--force)" if force else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
