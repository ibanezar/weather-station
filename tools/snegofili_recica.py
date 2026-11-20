#!/usr/bin/env python3
"""Ročna meritev snega v Rečici ob Savinji za /snegofili/ (data/snegofili-recica.json).

Postaja IREICA1 snega ne meri; višino snežne odeje izmeri lastnik postaje ročno. Skript doda meritev in jo zapiše z
UTC časom (stran ga prikaže po lokalnem času). Brez izmišljenih vrednosti: brez vnosa na strani ni ploščice.

  python3 tools/snegofili_recica.py 3                      # 3 cm, zdaj
  python3 tools/snegofili_recica.py 0                      # izmerjena ničla (je podatek, ne manjkajoči vnos)
  python3 tools/snegofili_recica.py 5 --novi 2             # višina odeje 5 cm, od tega nov sneg 2 cm
  python3 tools/snegofili_recica.py 4 --cas "2026-11-20 07:30"   # čas po naši uri (Europe/Ljubljana)
  python3 tools/snegofili_recica.py --list
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "snegofili-recica.json")
TZ = ZoneInfo("Europe/Ljubljana")
MAX_CM = 500
KEEP = 800


def load():
    with open(PATH, encoding="utf-8") as f:
        return json.load(f)


def add(data, cm, novi=None, cas=None):
    """Vrne nov slovar z dodano meritvijo; ista minuta prepiše obstoječi vnos."""
    if not isinstance(cm, (int, float)) or not 0 <= cm <= MAX_CM:
        raise ValueError(f"višina odeje mora biti od 0 do {MAX_CM} cm")
    if novi is not None and not 0 <= novi <= MAX_CM:
        raise ValueError(f"nov sneg mora biti od 0 do {MAX_CM} cm")
    t = cas or datetime.now(timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=TZ)
    t = t.astimezone(timezone.utc).replace(second=0, microsecond=0)
    if t > datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=1):
        raise ValueError("čas meritve je v prihodnosti")
    iso = t.strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"cas": iso, "cm": round(float(cm), 1) if cm != int(cm) else int(cm)}
    if novi is not None:
        entry["novi"] = round(float(novi), 1) if novi != int(novi) else int(novi)
    rest = [m for m in data.get("meritve", []) if m.get("cas") != iso]
    rest.append(entry)
    rest.sort(key=lambda m: m["cas"])
    out = dict(data)
    out["meritve"] = rest[-KEEP:]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cm", nargs="?", type=float, help="višina snežne odeje v cm (0 = izmerjena ničla)")
    ap.add_argument("--novi", type=float, help="nov sneg v cm (neobvezno)")
    ap.add_argument("--cas", help='čas meritve po naši uri, npr. "2026-11-20 07:30" (privzeto zdaj)')
    ap.add_argument("--list", action="store_true", help="izpiši zadnjih 10 meritev")
    a = ap.parse_args()
    data = load()
    if a.list or a.cm is None:
        for m in data.get("meritve", [])[-10:]:
            print(m)
        if not data.get("meritve"):
            print("(ni meritev)")
        return 0
    cas = datetime.strptime(a.cas, "%Y-%m-%d %H:%M") if a.cas else None
    try:
        out = add(data, a.cm, a.novi, cas)
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("✓ dodano:", out["meritve"][-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
