#!/usr/bin/env python3
"""
Nadomesti ERA5 ocene za zgodnje dni (2019-11-07 … 2021-03-16) s pravimi
izmerjenimi vrednostmi iz Weather Underground.

Postaja IREICA1 je v Ecowitt oblak detajlne (pod-dnevne) podatke začela pošiljati
šele 2021-03-17, zato Ecowitt izvoz za zgodnejše obdobje nima dnevnega min/max.
WU pa za isto postajo hrani dnevni high/low/avg že od zagona (2019-11), zato
so to prave meritve, ne model.

    python3 tools/backfill_wu_early.py            # zapiše
    python3 tools/backfill_wu_early.py --dry-run  # samo poročilo

Posodobi le dneve v razponu, ki so trenutno src="era5". Dneve, ki jih WU nima,
pusti pri obstoječi ERA5 vrednosti.
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry-run" in sys.argv

WU_KEY = "619a8bb3ba4d42069a8bb3ba4d02061f"
STATION = "IREICA1"
START, END = "2019-11-07", "2021-03-16"   # zgodnji blok brez min/max v Ecowitt


def wu_daily(date_iso):
    """Vrne (avg, low, high) iz WU ali None."""
    d = date_iso.replace("-", "")
    url = (f"https://api.weather.com/v2/pws/history/daily?stationId={STATION}"
           f"&format=json&units=m&date={d}&apiKey={WU_KEY}&numericPrecision=decimal")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            j = json.load(r)
    except Exception as e:
        print(f"  ⚠ {date_iso}: napaka {e!r}")
        return None
    obs = j.get("observations") or []
    if not obs:
        return None
    m = obs[0].get("metric", {})
    hi, lo, av = m.get("tempHigh"), m.get("tempLow"), m.get("tempAvg")
    if hi is None or lo is None:
        return None
    return (av, lo, hi)


def main():
    hp = os.path.join(ROOT, "history.json")
    hist = json.load(open(hp, encoding="utf-8"))

    targets = sorted(d for d, v in hist.items()
                     if START <= d <= END and v.get("src") == "era5")
    print(f"Ciljni dnevi (era5 v {START}…{END}): {len(targets)}")

    n_wu = n_skip = 0
    for date in targets:
        res = wu_daily(date)
        if res is None:
            n_skip += 1
            continue
        av, lo, hi = res
        v = hist[date]
        v["tempLow"]  = round(float(lo), 1)
        v["tempHigh"] = round(float(hi), 1)
        if av is not None:
            v["tempAvg"] = round(float(av), 1)
        v["src"] = "wu"
        n_wu += 1
        time.sleep(0.05)

    print(f"Posodobljeno iz WU: {n_wu}")
    print(f"Brez WU (ostane ERA5): {n_skip}")

    if DRY:
        print("\n--dry-run: history.json NI bil spremenjen.")
        return

    out = {k: hist[k] for k in sorted(hist)}
    json.dump(out, open(hp, "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print(f"\n✓ history.json zapisan ({len(out)} dni).")


if __name__ == "__main__":
    main()
