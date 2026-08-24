#!/usr/bin/env python3
"""
tools/log_hourly_observations.py — urni zajem meritev IREICA1 za prihodnjo
analizo "pristranskost po urah dneva" na /test-napovedi/ (Faza 4, graf #2 v
brief-u).

Zakaj ločeno od history.json: to je DNEVNI arhiv (Tmax/Tmin/povprečje), za
urno pristranskost pa je treba urne vrednosti. Ecowitt device/history vrne
polno 5-min ločljivost samo za zadnja ~90 dni (starejše poizvedbe vrnejo
strežniško že podvzorčene točke — preverjeno ob gradnji tega orodja, glej
opombo v compute_forecast_test_metrics.py) -- zato tega ni mogoče zapolniti
za nazaj kot data/forecast-archive.csv, ampak samo od zdaj naprej, dan za
dnem, ko je VČERAJŠNJI dan (dokončan) še znotraj tega okna.

Piše data/hourly-observations.csv (valid_at_local, temp_c, precip_mm,
humidity_pct, quality_flag). Drži samo zadnjih HOLD_DAYS dni (isto načelo kot
story karte/alert log drugod v repozitoriju) -- za bias-po-urah je dovolj,
neomejena rast pa ni potrebna.

Usage:
  python3 tools/log_hourly_observations.py
"""
import csv, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_history as uh  # noqa: E402  (fetch_ecowitt, _ew_list, _pick, TZ)

ROOT = uh.ROOT
LOG_PATH = os.path.join(ROOT, "data", "hourly-observations.csv")
FIELDS = ["valid_at_local", "temp_c", "precip_mm", "humidity_pct", "quality_flag"]
HOLD_DAYS = 400  # dovolj za "isti mesec/sezona lani", brez neomejene rasti


def hourly_from_ecowitt(data, day_iso):
    """Surov Ecowitt 'data' objekt (en dan) -> {ura (0..23): {temp, precip, hum}}."""
    if not data:
        return {}
    buckets = {h: {"t": [], "p": [], "h": []} for h in range(24)}

    def hour_of(ts):
        return uh.datetime.fromtimestamp(int(ts), uh.TZ).hour

    for ts, v in (uh._ew_list(data, "outdoor", "temperature") or {}).items():
        val = uh._pick(v, ["avg", "value", "max"])
        if val is not None:
            buckets[hour_of(ts)]["t"].append(val)
    for ts, v in (uh._ew_list(data, "outdoor", "humidity") or {}).items():
        val = uh._pick(v, ["avg", "value", "max"])
        if val is not None:
            buckets[hour_of(ts)]["h"].append(val)
    for ts, v in (uh._ew_list(data, "rainfall", "daily") or {}).items():
        # kumulativni dnevni seštevek -- razlika med zaporednima točkama je
        # padavine V TEM INTERVALU, ne skupaj od polnoči do te ure.
        val = uh._pick(v, ["total", "max", "value"])
        if val is not None:
            buckets[hour_of(ts)]["p"].append(val)

    out = {}
    for h, b in buckets.items():
        if not b["t"]:
            continue
        precip_hourly = None
        if len(b["p"]) >= 2:
            precip_hourly = round(max(0.0, max(b["p"]) - min(b["p"])), 1)
        elif b["p"]:
            precip_hourly = 0.0
        out[h] = {
            "temp_c": round(sum(b["t"]) / len(b["t"]), 1),
            "precip_mm": precip_hourly,
            "humidity_pct": round(sum(b["h"]) / len(b["h"]), 1) if b["h"] else None,
        }
    return out


def load_existing():
    seen, rows = set(), []
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                rows.append(row)
                seen.add(row["valid_at_local"])
    return rows, seen


def save(rows):
    rows.sort(key=lambda r: r["valid_at_local"])
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main():
    yesterday = (datetime.datetime.now(uh.TZ).date() - datetime.timedelta(days=1)).isoformat()
    rows, seen = load_existing()

    if any(r.startswith(yesterday) for r in seen):
        print(f"{yesterday} je že zabeležen, preskačem zajem.")
    else:
        data = uh.fetch_ecowitt(yesterday, yesterday)
        if not data:
            print(f"⚠ Ecowitt ni vrnil podatkov za {yesterday}.", file=sys.stderr)
        else:
            hourly = hourly_from_ecowitt(data, yesterday)
            n_hours = len(hourly)
            flag = "ok" if n_hours >= 22 else ("partial" if n_hours >= 12 else "sparse")
            added = 0
            for h in range(24):
                b = hourly.get(h)
                if not b:
                    continue
                key = f"{yesterday}T{h:02d}:00"
                if key in seen:
                    continue
                rows.append({
                    "valid_at_local": key, "temp_c": b["temp_c"],
                    "precip_mm": b["precip_mm"] if b["precip_mm"] is not None else "",
                    "humidity_pct": b["humidity_pct"] if b["humidity_pct"] is not None else "",
                    "quality_flag": flag,
                })
                added += 1
            print(f"✓ {yesterday}: {n_hours}/24 ur ({flag}), {added} novih vrstic.")

    cutoff = (datetime.date.today() - datetime.timedelta(days=HOLD_DAYS)).isoformat()
    before = len(rows)
    rows = [r for r in rows if r["valid_at_local"][:10] >= cutoff]
    if len(rows) != before:
        print(f"  počiščenih {before - len(rows)} vrstic, starejših od {HOLD_DAYS} dni.")

    save(rows)
    print(f"✓ data/hourly-observations.csv: {len(rows)} vrstic ({len(rows) // 24} dni pribl.)")


if __name__ == "__main__":
    main()
