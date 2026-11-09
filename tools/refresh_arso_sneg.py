#!/usr/bin/env python3
"""
tools/refresh_arso_sneg.py -- osveži dnevne serije ARSO padavinskih postaj v Zgornji Savinjski dolini (višina snežne odeje, novi sneg, padavine).

Arhivski ID-ji (iz izvoza iz ARSO arhiva meritev) so v train_sneg_mos.VALLEY_STATIONS (Gornji Grad 1748, Luče 1749, Radegunda 1747, Solčava 1750);
Gomilsko (3145, Spodnja Savinjska dolina) je nižinska primerjava, ki je model ne uporablja. Zapiše data/arso-sneg-postaje/daily-<id>.json
(isti zapis kot prej: {"fields": [...], "days": [[datum, višina odeje, novi sneg, padavine], ...]}) in osvezeno.json (čas osvežitve za varuha svežine).
Obstoječi dnevi se NE brišejo: nova vrednost prepiše staro samo, kadar ni prazna. Arhiv zaostaja nekaj dni; zadnji dnevi so prazni, dokler jih ARSO ne vnese.

Uporaba (teče v Actions, meteo.arso.gov.si iz razvojnega peskovnika ni dosegljiv):
  python3 tools/refresh_arso_sneg.py
Vir: Agencija Republike Slovenije za okolje.
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import arso_snow_stations as a   # noqa: E402
import train_sneg_mos as tsm     # noqa: E402

FIRST = "2019-09-01"
EXTRA = {"3145": "Gomilsko"}     # nižinska primerjava (ni v modelu)
FIELDS = ["date", "snow_depth_cm", "new_snow_cm", "precip_mm"]
MANIFEST = os.path.join(tsm.OBS_DIR, "osvezeno.json")


def path_for(sid, directory=tsm.OBS_DIR):
    return os.path.join(directory, f"daily-{sid}.json")


def merge(old_days, fresh):
    """old_days: [[datum, odeja, novi, padavine], ...]; fresh: {datum: [padavine, odeja, novi]} (vrstni red spremenljivk 85, 88, 89).
    Vrne novi seznam dni (urejen). Prazna nova vrednost ne prepiše stare."""
    cur = {d: list(rest) for d, *rest in old_days}
    for d, (p, depth, new) in fresh.items():
        row = cur.setdefault(d, [None, None, None])
        for i, v in enumerate((depth, new, p)):
            if v is not None:
                row[i] = v
    return [[d] + cur[d] for d in sorted(cur)]


def last_value_date(days):
    got = [d for d, depth, new, _ in days if depth is not None or new is not None]
    return max(got) if got else None


def write_manifest(directory=tsm.OBS_DIR, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    last = {}
    for sid in list(tsm.VALLEY_STATIONS) + list(EXTRA):
        p = path_for(sid, directory)
        if os.path.exists(p):
            last[sid] = last_value_date(json.load(open(p, encoding="utf-8")).get("days") or [])
    with open(os.path.join(directory, "osvezeno.json"), "w", encoding="utf-8") as f:
        json.dump({"generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "last_value_date": last,
                   "source": "ARSO arhiv meritev (webmet/archive/data.xml), spremenljivke 85, 88, 89"}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return last


def main():
    ids = list(tsm.VALLEY_STATIONS) + list(EXTRA)
    today = dt.date.today().isoformat()
    st, text = a.data_xml(",".join(ids), FIRST, today)
    if st != 200 or not text:
        print(f"✗ ARSO arhiv ni dosegljiv (HTTP {st}) -- serije niso osvežene", file=sys.stderr)
        return 0                      # CI naj zaradi tega ne pade
    multi = a.parse_multi(text)
    changed = 0
    for sid in ids:
        fresh = multi.get(sid) or {}
        if not any(v is not None for row in fresh.values() for v in row):
            print(f"  {sid}: arhiv ni vrnil vrednosti -- ohranjeno")
            continue
        p = path_for(sid)
        old = json.load(open(p, encoding="utf-8")).get("days") if os.path.exists(p) else []
        days = merge(old or [], fresh)
        if days != (old or []):
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"fields": FIELDS, "days": days}, f, ensure_ascii=False, separators=(",", ":"))
            changed += 1
        name = tsm.VALLEY_STATIONS.get(sid, {}).get("name") or EXTRA.get(sid)
        print(f"  {sid} {name}: {len(days)} dni, zadnja vrednost {last_value_date(days)}")
    last = write_manifest()
    print(f"→ {changed} datotek spremenjenih; zadnji dnevi z vrednostjo: {last}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
