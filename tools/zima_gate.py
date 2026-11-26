#!/usr/bin/env python3
"""
tools/zima_gate.py — vrata in preverjanje svežine za zima-forecast.yml (26. 11. 2026).

Zakaj:

1. GitHubov cron `50 5 * * *` zamuja 8–11 ur (zadnji teki 24. in 25. 11.: 16:29 in 16:08 UTC), zato je bil
   crnivec.si dopoldne vedno star do 24 ur. Zimo zdaj sproži tudi Cloudflarov cron (worker.js,
   `_cronDispatchScheduledWorkflows`, 4:10/4:40/5:10/5:40 UTC). Workflow nima časovnih vrat, zato bi štirje
   termini + pozni GitHubov cron zimo sestavili in objavili petkrat na dan (štiri commite, IndexNow, drug
   nivo igre čez dan). Vrata zato spustijo skozi samo tek, ki podatkov danes še NI osvežil.

2. Vrata so hkrati ponovni poskus. `winter_engine.py` ob izpadu Open-Meteo obdrži stari `data/winter-data.json`
   in konča z 0 (25. 11. 2026: »handshake operation timed out«, stran je ostala na podatkih z 24. 11., tek je bil
   zelen). Ker se `generated_at` zapiše samo ob uspešnem klicu, naslednji termin (30 min pozneje) vidi, da danes
   še ni bilo osvežitve, in poskusi znova.

3. `require-fresh` je zadnji korak workflowa: če so podatki kljub vsem poskusom starejši od meje, tek postane
   rdeč. Zelen tek s starimi podatki je bil prav tisto, kar je napako skrilo.

Usage:
  python3 tools/zima_gate.py check [--force]          # nastavi proceed=true|false (GITHUB_OUTPUT)
  python3 tools/zima_gate.py require-fresh [URE]      # izhod 1, če je winter-data.json starejši od URE (privzeto 30)
"""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINTER_DATA = os.path.join(ROOT, "data", "winter-data.json")
TZ = ZoneInfo("Europe/Ljubljana")
STALE_FAIL_H = 30   # en zamujen dan (≈ 24 h + zamuda crona) še ni napaka, dva sta


def load_generated(path=WINTER_DATA):
    """Čas zadnje USPEŠNE osvežitve (aware datetime) ali None, če datoteke ni ali čas ni berljiv."""
    try:
        with open(path, encoding="utf-8") as f:
            ts = json.load(f).get("generated_at")
        dt = datetime.datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def decide(now, generated, force=False):
    """(proceed, razlog). `now` je aware datetime."""
    if force:
        return True, "--force"
    if generated is None:
        return True, "winter-data.json manjka ali nima časa osvežitve"
    gen_local = generated.astimezone(TZ)
    if gen_local.date() == now.astimezone(TZ).date():
        return False, f"podatki so bili danes že osveženi ob {gen_local.strftime('%H:%M')}"
    return True, f"zadnja osvežitev je bila {gen_local.strftime('%-d. %-m. ob %H:%M')}, danes je še ni"


def check_fresh(now, generated, max_h=STALE_FAIL_H):
    """(ok, sporočilo)."""
    if generated is None:
        return False, "winter-data.json nima časa osvežitve"
    age_h = (now - generated).total_seconds() / 3600
    if age_h > max_h:
        return False, (f"winter-data.json je star {age_h:.0f} h (meja {max_h} h): Open-Meteo kljub ponovnim poskusom ni "
                       f"odgovoril, crnivec.si in /zima/ kažeta stare podatke")
    return True, f"winter-data.json je star {age_h:.1f} h"


def emit(proceed, reason):
    print(f"proceed={proceed} — {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"proceed={'true' if proceed else 'false'}\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "check"
    now = datetime.datetime.now(datetime.timezone.utc)
    generated = load_generated()
    if cmd == "require-fresh":
        max_h = float(argv[1]) if len(argv) > 1 else STALE_FAIL_H
        ok, msg = check_fresh(now, generated, max_h)
        if ok:
            print(f"✓ {msg}")
            return 0
        print(f"::error title=Zimski podatki so stari::{msg}")
        return 1
    proceed, reason = decide(now, generated, force="--force" in argv)
    emit(proceed, reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
