#!/usr/bin/env python3
"""
Preveri celovitost history.json po posodobitvi.

    python3 tools/validate_history.py YYYY-MM [MIN_COUNT]

YYYY-MM   mesec, ki je bil pravkar posodobljen
MIN_COUNT minimalno pričakovano skupno število dni (pred posodobitvijo)
"""
import json, os, sys
from datetime import date as _date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = ['tempHigh', 'tempLow', 'tempAvg', 'precipTotal', 'windspeedHigh', 'windspeedAvg', 'humidityAvg']

RANGES = {
    'tempHigh':      (-40, 50),
    'tempLow':       (-40, 50),
    'tempAvg':       (-40, 50),
    'precipTotal':   (0, 600),
    'windspeedHigh': (0, 300),
    'windspeedAvg':  (0, 200),
    'humidityAvg':   (0, 100),
}

# Neobvezna polja (samo dnevi s pravo postajo jih imajo). Preverijo se le,
# če so v zapisu — odsotnost NI napaka.
OPTIONAL_RANGES = {
    'dewptHigh':    (-40, 40),
    'dewptLow':     (-40, 40),
    'dewptAvg':     (-40, 40),
    'pressureHigh': (900, 1085),
    'pressureLow':  (900, 1085),
    'pressureAvg':  (900, 1085),
    'windgustHigh': (0, 400),
    'solarHigh':    (0, 1500),
    'uviHigh':      (0, 20),
}

def main():
    if len(sys.argv) < 2:
        sys.exit("Uporaba: validate_history.py YYYY-MM [MIN_COUNT]")

    month = sys.argv[1]
    min_count = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    hp = os.path.join(ROOT, "history.json")

    try:
        with open(hp, encoding="utf-8") as f:
            d = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"NAPAKA: history.json ni veljavna JSON: {e}")
    except FileNotFoundError:
        sys.exit("NAPAKA: history.json ne obstaja")

    errors = []

    # 1. Key format
    for key in d:
        try:
            _date.fromisoformat(key)
        except ValueError:
            errors.append(f"Neveljaven ključ: {key!r}")

    # 2. Required fields, no nulls, value ranges, tempHigh >= tempLow
    for key, entry in d.items():
        for field in REQUIRED:
            if field not in entry:
                errors.append(f"{key}: manjka polje '{field}'")
                continue
            val = entry[field]
            if val is None:
                errors.append(f"{key}.{field}: vrednost je null")
                continue
            lo, hi = RANGES[field]
            if not (lo <= float(val) <= hi):
                errors.append(f"{key}.{field}: {val} izven [{lo}, {hi}]")
        hi_v = entry.get('tempHigh')
        lo_v = entry.get('tempLow')
        if hi_v is not None and lo_v is not None and hi_v < lo_v - 0.1:
            errors.append(f"{key}: tempHigh ({hi_v}) < tempLow ({lo_v})")
        # Neobvezna polja — preveri obseg le, če so prisotna in niso null
        for field, (lo, hi) in OPTIONAL_RANGES.items():
            if field in entry and entry[field] is not None:
                if not (lo <= float(entry[field]) <= hi):
                    errors.append(f"{key}.{field}: {entry[field]} izven [{lo}, {hi}]")

    # 3. No entries were deleted (regression check)
    total = len(d)
    if min_count and total < min_count:
        errors.append(f"Skupno število dni se je zmanjšalo: {total} < {min_count} (brisanje?)")

    # 4. Updated month has at least one entry
    month_days = [k for k in d if k.startswith(month)]
    if not month_days:
        errors.append(f"Mesec {month} nima nobenega vnosa po posodobitvi")

    if errors:
        print(f"VALIDACIJA NEUSPEŠNA — {len(errors)} napaka(e):")
        for e in errors[:25]:
            print(f"  • {e}")
        if len(errors) > 25:
            print(f"  ... in še {len(errors) - 25} napak")
        sys.exit(1)

    print(f"✓ history.json je veljaven ({total} dni skupaj, {len(month_days)} dni za {month})")

if __name__ == "__main__":
    main()
