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
  python3 tools/log_hourly_observations.py              # yesterday
  python3 tools/log_hourly_observations.py --backfill 85  # one-off: fill new channels for the last ~85 days
"""
import csv, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update_history as uh  # noqa: E402  (fetch_ecowitt, _ew_list, _pick, TZ)

ROOT = uh.ROOT
LOG_PATH = os.path.join(ROOT, "data", "hourly-observations.csv")
FIELDS = ["valid_at_local", "temp_c", "precip_mm", "humidity_pct", "quality_flag",
          "dewpoint_c", "wind_kmh", "gust_kmh", "pressure_hpa", "solar_wm2"]
# Extra OUTDOOR channels (added 2026-10-06 for a future hourly forecast-correction
# model). (path in Ecowitt response, preferred keys, aggregation). Indoor blocks are
# never read here -- see the privacy rule at the top of CLAUDE.md.
EXTRA = {
    "dewpoint_c":   (("outdoor", "dew_point"), ["avg", "value", "max"], "mean"),
    "wind_kmh":     (("wind", "wind_speed"), ["avg", "value", "max"], "mean"),
    "gust_kmh":     (("wind", "wind_gust"), ["max", "avg", "value"], "max"),
    "pressure_hpa": (("pressure", "relative"), ["avg", "value", "max"], "mean"),
    "solar_wm2":    (("solar_and_uvi", "solar"), ["avg", "value", "max"], "mean"),
}
SOLAR_MAX_WM2 = 1500  # sensor glitches above this are dropped
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

    extra = {k: {h: [] for h in range(24)} for k in EXTRA}
    for k, (path, keys, _agg) in EXTRA.items():
        for ts, v in (uh._ew_list(data, *path) or {}).items():
            val = uh._pick(v, keys)
            if val is None or (k == "solar_wm2" and val > SOLAR_MAX_WM2):
                continue
            extra[k][hour_of(ts)].append(val)

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
        for k, (_path, _keys, agg) in EXTRA.items():
            xs = extra[k][h]
            out[h][k] = (round(max(xs) if agg == "max" else sum(xs) / len(xs), 1) if xs else None)
    return out


def make_row(key, b, flag):
    row = {"valid_at_local": key, "temp_c": b["temp_c"],
           "precip_mm": b["precip_mm"] if b["precip_mm"] is not None else "",
           "humidity_pct": b["humidity_pct"] if b["humidity_pct"] is not None else "",
           "quality_flag": flag}
    for k in EXTRA:
        row[k] = b[k] if b.get(k) is not None else ""
    return row


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


def ingest_day(day, rows, seen, data):
    """Add the day's hours to `rows`; for hours already logged (before the extra
    channels existed) fill ONLY the empty extra columns -- never overwrite."""
    hourly = hourly_from_ecowitt(data, day)
    n_hours = len(hourly)
    flag = "ok" if n_hours >= 22 else ("partial" if n_hours >= 12 else "sparse")
    by_key = {r["valid_at_local"]: r for r in rows}
    added = filled = 0
    for h in range(24):
        b = hourly.get(h)
        if not b:
            continue
        key = f"{day}T{h:02d}:00"
        if key in by_key:
            r = by_key[key]
            if any(not r.get(k) for k in EXTRA):
                for k in EXTRA:
                    if not r.get(k) and b.get(k) is not None:
                        r[k] = b[k]
                        filled += 1
            continue
        rows.append(make_row(key, b, flag))
        seen.add(key)
        added += 1
    return n_hours, flag, added, filled


def main():
    backfill = 0
    if "--backfill" in sys.argv:
        # Ecowitt only keeps 5-min resolution ~90 days back; stay inside that.
        backfill = min(int(sys.argv[sys.argv.index("--backfill") + 1]), 85)
    today = datetime.datetime.now(uh.TZ).date()
    days = [(today - datetime.timedelta(days=d)).isoformat() for d in range(backfill, 0, -1)] \
        if backfill else [(today - datetime.timedelta(days=1)).isoformat()]
    rows, seen = load_existing()

    for day in days:
        have = [r for r in rows if r["valid_at_local"].startswith(day)]
        complete = len(have) >= 22 and all(r.get("dewpoint_c") not in (None, "") for r in have)
        if complete:
            print(f"{day} je že zabeležen, preskačem zajem.")
            continue
        data = uh.fetch_ecowitt(day, day)
        if not data:
            print(f"⚠ Ecowitt ni vrnil podatkov za {day}.", file=sys.stderr)
            continue
        n_hours, flag, added, filled = ingest_day(day, rows, seen, data)
        print(f"✓ {day}: {n_hours}/24 ur ({flag}), {added} novih vrstic, {filled} dopolnjenih polj.")

    cutoff = (datetime.date.today() - datetime.timedelta(days=HOLD_DAYS)).isoformat()
    before = len(rows)
    rows = [r for r in rows if r["valid_at_local"][:10] >= cutoff]
    if len(rows) != before:
        print(f"  počiščenih {before - len(rows)} vrstic, starejših od {HOLD_DAYS} dni.")

    save(rows)
    print(f"✓ data/hourly-observations.csv: {len(rows)} vrstic ({len(rows) // 24} dni pribl.)")


if __name__ == "__main__":
    main()
