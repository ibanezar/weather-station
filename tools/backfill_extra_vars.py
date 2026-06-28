#!/usr/bin/env python3
"""
Enkratni/večkratni backfill: dopolni OBSTOJEČE dneve postaje v history.json
z dodatnimi spremenljivkami iz Ecowitta (tlak, rosišče, sunki, obsevanje, UV).

Za razliko od update_history.py ta skript NE prepiše obstoječih meritev:
za vsak dan, ki je že src="station", doda LE manjkajoča neobvezna polja
(dewpt*, pressure*, windgust*, solar*, uvi*), če jih Ecowitt za ta dan vrne.
Temperatura, padavine, veter, vlaga in src ostanejo nedotaknjeni.

    python3 tools/backfill_extra_vars.py                  # 2021-03 → tekoči mesec
    python3 tools/backfill_extra_vars.py 2024-01 2024-12  # samo izbran razpon
    python3 tools/backfill_extra_vars.py --dry-run        # samo poročilo

Ecowitt pod-dnevne podatke za starejše mesece morda ne hrani več; takih dni
skript preprosto ne dopolni (in to izpiše).
"""
import json, os, sys, calendar, importlib.util
from datetime import date as _date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY  = "--dry-run" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]

# Privzeti razpon: od prvega meseca s pravo postajo do danes.
START_MONTH = ARGS[0] if len(ARGS) > 0 else "2021-03"
END_MONTH   = ARGS[1] if len(ARGS) > 1 else _date.today().isoformat()[:7]

# Nova (neobvezna) polja, ki jih ta backfill dodaja.
EXTRA = ["dewptHigh", "dewptLow", "dewptAvg",
         "pressureHigh", "pressureLow", "pressureAvg",
         "windgustHigh", "solarHigh", "uviHigh"]

# Uvozi fetch_ecowitt / normalize_ecowitt iz update_history.py (en sam vir resnice).
_spec = importlib.util.spec_from_file_location(
    "update_history", os.path.join(os.path.dirname(__file__), "update_history.py"))
uh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(uh)


def months(start_ym, end_ym):
    y, m = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_ym[:4]), int(end_ym[5:7])
    while (y, m) <= (ey, em):
        yield f"{y:04d}-{m:02d}"
        m += 1
        if m > 12:
            y, m = y + 1, 1


def main():
    hp = os.path.join(ROOT, "history.json")
    hist = json.load(open(hp, encoding="utf-8"))

    today = _date.today().isoformat()
    n_days = 0          # dni, ki so dobili vsaj eno novo polje
    n_fields = 0        # skupno število dodanih polj
    empty_months = []   # meseci, kjer Ecowitt ni vrnil nobenih dodatnih polj

    for ym in months(START_MONTH, END_MONTH):
        y, m = int(ym[:4]), int(ym[5:7])
        start = f"{ym}-01"
        end   = min(f"{ym}-{calendar.monthrange(y, m)[1]:02d}", today)

        station = uh.normalize_ecowitt(uh.fetch_ecowitt(start, end))
        if not station:
            empty_months.append(ym)
            print(f"  {ym}: Ecowitt brez podatkov")
            continue

        m_days = m_fields = 0
        for date, rec in station.items():
            if not date.startswith(ym):
                continue
            cur = hist.get(date)
            # Dopolnimo le obstoječe dni prave postaje — klasifikacije ne spreminjamo.
            if not cur or cur.get("src") != "station":
                continue
            added = False
            for f in EXTRA:
                if rec.get(f) is not None and cur.get(f) is None:
                    cur[f] = rec[f]
                    m_fields += 1
                    added = True
            if added:
                m_days += 1

        n_days += m_days
        n_fields += m_fields
        if m_days:
            print(f"  {ym}: dopolnjenih {m_days} dni (+{m_fields} polj)")
        else:
            empty_months.append(ym)
            print(f"  {ym}: ni dodatnih polj (postaja brez senzorja / brez retencije)")

    print(f"\nSkupaj: {n_days} dni dopolnjenih, {n_fields} polj dodanih.")
    if empty_months:
        print(f"Meseci brez dodatkov: {', '.join(empty_months)}")

    if DRY:
        print("\n--dry-run: history.json NI bil spremenjen.")
        return
    if not n_fields:
        print("\nNič za zapisati — history.json nespremenjen.")
        return

    out = {k: hist[k] for k in sorted(hist)}
    json.dump(out, open(hp, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"\n✓ history.json zapisan ({len(out)} dni).")


if __name__ == "__main__":
    main()
