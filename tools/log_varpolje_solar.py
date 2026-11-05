#!/usr/bin/env python3
"""
tools/log_varpolje_solar.py — dnevni prenos sevanja sosednje postaje (IREICA7, Varpolje) iz workerja v repozitorij.

Zakaj: model obzorja se na IREICA1 ne ujema (sevanje skoči mediano +126 min po izračunanem prvem žarku; CLAUDE.md, »Sonce v
dolini in jutro v dolini«). Domneva je senca bližnjega objekta ali drevesa ob senzorju. Varpolje (~1,6 km, isto dno doline)
objavlja sončno sevanje, a samo TRENUTNO vrednost; worker (`_cronVarpoljeSolar`) ga vsakih 5 minut zapiše v R2 (zadnjih 72 h),
ta skript pa ga enkrat na dan prenese v `data/varpolje-solar-5min.csv`. `tools/eval_sonce_varpolje.py` nato primerja čas prvega
žarka obeh postaj.

Sosed je GOST (CLAUDE.md, »Sosednja postaja Varpolje«): podatek gre samo v to primerjavo; ne v history.json, ne v učenje MTR,
ne na semafor. Zapis ima SAMO sevanje, UV in zunanjo temperaturo; notranjega bloka ni ne v workerju ne tu.

Piše data/varpolje-solar-5min.csv (date, time_local, solar_wm2, uv, temp_c); čas je lokalni (Europe/Ljubljana), zaokrožen
NAVZDOL na 5 minut (kot solar-5min.csv IREICA1). Drži zadnjih HOLD_DAYS dni.

Usage:
  python3 tools/log_varpolje_solar.py
"""
import csv
import datetime
import json
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "varpolje-solar-5min.csv")
WORKER = "https://weatherireica1.filip-eremita.workers.dev"
WORKER_UA = "Mozilla/5.0 (compatible; meteorec-bot/1.0; +https://meteorec.si/o-postaji.html)"
FIELDS = ["date", "time_local", "solar_wm2", "uv", "temp_c"]
HOLD_DAYS = 120
TZ = ZoneInfo("Europe/Ljubljana")


def rows_from_payload(payload):
    """Odgovor workerja → seznam vrstic (dict, ključi FIELDS). Neveljavne vrstice se preskočijo."""
    out = {}
    for r in (payload or {}).get("rows") or []:
        try:
            t, sol, uv, tc = r[0], r[1], r[2], r[3]
            if sol is None or not (0 <= float(sol) <= 1600):
                continue
            dt = datetime.datetime.fromtimestamp(int(t), tz=datetime.timezone.utc).astimezone(TZ)
        except (TypeError, ValueError, IndexError):
            continue
        minute = (dt.hour * 60 + dt.minute) // 5 * 5
        key = (dt.date().isoformat(), f"{minute // 60:02d}:{minute % 60:02d}")
        out[key] = {"date": key[0], "time_local": key[1], "solar_wm2": f"{float(sol):.1f}",
                    "uv": "" if uv is None else f"{float(uv):g}", "temp_c": "" if tc is None else f"{float(tc):.1f}"}
    return list(out.values())


def merge(existing, new, today=None):
    """Združi obstoječe in nove vrstice (novejše prepišejo isti 5-minutni kos), obdrži HOLD_DAYS dni, uredi po času."""
    by = {(r["date"], r["time_local"]): r for r in existing}
    for r in new:
        by[(r["date"], r["time_local"])] = r
    today = today or datetime.date.today()
    cutoff = (today - datetime.timedelta(days=HOLD_DAYS)).isoformat()
    return [by[k] for k in sorted(by) if k[0] >= cutoff]


def read_csv(path=OUT_PATH):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(rows, path=OUT_PATH):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def fetch_payload():
    req = urllib.request.Request(WORKER + "/varpolje-solar.json", headers={"User-Agent": WORKER_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    try:
        payload = fetch_payload()
    except Exception as e:  # noqa: BLE001 — omrežje: stari zapis ostane
        print(f"⚠ /varpolje-solar.json ni dosegljiv ({type(e).__name__}: {e}); zapis ostane, kot je.")
        return 0
    if not payload.get("ok"):
        print("⚠ worker je javil ok=false; zapis ostane, kot je.")
        return 0
    new = rows_from_payload(payload)
    old = read_csv()
    merged = merge(old, new)
    write_csv(merged)
    print(f"✓ varpolje-solar-5min.csv: {len(old)} → {len(merged)} vrstic (iz workerja {len(new)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
