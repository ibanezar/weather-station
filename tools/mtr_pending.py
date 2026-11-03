#!/usr/bin/env python3
"""
tools/mtr_pending.py — števci za razdelek »Čaka na podatke« (zavihek MTR, kartica v kuhinji).

Piše data/mtr-pending.json. Vsak odprt poskus iz docs/model-recica.md, ki ga ni mogoče sklepati, dokler se
ne nabere dovolj podatkov, ima tu število zbranih dni proti pragu. Pragovi so iz dokumenta, ne izmišljeni:

  live     živa osvežitev: najmanj MIN_DAYS (20) razrešenih dni na razred ur do začetka dneva
           (isti `analyze()` in isti razredi kot tools/ai/eval_live_refresh.py, uvožena, ne podvojena)
  profile  prave napovedi višinskega profila (data/profile-forward-log.csv): ~120 zimskih dni (nov–feb),
           ocena šele po zimi 2026/27. Šteje se dan izdaje napovedi.

Poganja ga mtr-live.yml za vsako osvežitvijo. Brez omrežja, notranjih meritev ne bere (samo zunanje
napovedi in meritev iz forecast_verification.json prek eval_live_refresh).
"""
import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "ai"))
import eval_live_refresh as ev  # noqa: E402

LIVE_LOG = os.path.join(ROOT, "data", "mtr-live-log.csv")
PROFILE_LOG = os.path.join(ROOT, "data", "profile-forward-log.csv")
VERIF = os.path.join(ROOT, "forecast_verification.json")
OUT = os.path.join(ROOT, "data", "mtr-pending.json")

WINTER_TARGET = 120
WINTER_MONTHS = (11, 12, 1, 2)
SNOW_M = 0.01          # snow_max je višina snega v m (Open-Meteo snow_depth): 0,01 m = 1 cm


def _rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def live_counts(log_rows, verification):
    """Razrešeni dnevi po razredih (Tmax in Tmin ločeno; kot razred šteje manjši n, ker sklep terja oba)."""
    res = ev.analyze(log_rows, verification)
    classes = {}
    for name, byt in res.items():
        if name.startswith("že teče"):
            continue          # ni poštena primerjava (glej eval_live_refresh), ne šteje k pragu
        n = min(byt.get("tmax", {}).get("n", 0), byt.get("tmin", {}).get("n", 0))
        classes[name] = n
    best_name = max(classes, key=classes.get) if classes else None
    return {"target": ev.MIN_DAYS, "classes": classes,
            "best": classes[best_name] if best_name else 0, "best_class": best_name,
            "log_rows": len(log_rows)}


def profile_counts(rows):
    days, winter, snow = set(), set(), set()
    for r in rows:
        d = (r.get("issued_at") or "")[:10]
        try:
            month = dt.date.fromisoformat(d).month
        except ValueError:
            continue
        days.add(d)
        if month in WINTER_MONTHS:
            winter.add(d)
        try:
            if float(r.get("snow_max") or 0) > SNOW_M:
                snow.add(d)
        except ValueError:
            pass
    return {"target": WINTER_TARGET, "days": len(days), "winter_days": len(winter),
            "snow_days": len(snow)}


def build(live_log=LIVE_LOG, profile_log=PROFILE_LOG, verif=VERIF, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    verification = json.load(open(verif, encoding="utf-8")) if os.path.exists(verif) else {}
    return {"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "live": live_counts(_rows(live_log), verification),
            "profile": profile_counts(_rows(profile_log))}


def main():
    out = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
