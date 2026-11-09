#!/usr/bin/env python3
"""
tools/log_arso_snow_live.py -- beleženje živih ARSO opazovanj (višina snežne odeje `snow`, T, padavine) za postaje v okolici Rečice.

Zakaj: IREICA1 snega ne meri, ARSO arhiv (data.xml) za avtomatski postaji Gornji Grad (GORNJ-GRA_, 428 m) in Radegunda
(RADEG-NDA_, 794 m) nima znanega ID-ja, živi vir `observationAms_si_latest.xml` pa za obe nosi polje `snow`. Vsak tek doda
vrstico na postajo (samo ko je opazovanje novo) v data/arso-snow-live.csv. Sneg je tako dolinska resnica za preverjanje
MTR sneg NAPREJ v času. Teče v Actions (meteo.arso.gov.si iz razvojnega peskovnika ni dosegljiv).
Vir: Agencija Republike Slovenije za okolje. Notranjih meritev ne bere.

Uporaba:
  python3 tools/log_arso_snow_live.py            # zapiše v data/arso-snow-live.csv
  python3 tools/log_arso_snow_live.py --list     # samo izpiše postaje v radiju
"""
import argparse
import csv
import datetime as dt
import math
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://meteo.arso.gov.si/uploads/probase/www/observ/surface/text/sl/observationAms_si_latest.xml"
UA = {"User-Agent": "meteorec.si snow-log (+https://meteorec.si)"}
LOG_PATH = os.path.join(ROOT, "data", "arso-snow-live.csv")
HOME = (46.3306, 14.9120)          # Rečica ob Savinji
RADIUS_KM = 35.0
FIELDS = ["valid_utc", "id", "name", "alt_m", "lat", "lon", "t", "snow_cm", "rr_mm", "tp_12h_mm"]
WANT = {"t": "t", "snow": "snow_cm", "rr_val": "rr_mm", "tp_12h_acc": "tp_12h_mm"}


def km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def num(v):
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


def parse_utc(s):
    """'09.11.2026 13:10 UTC' -> '2026-11-09T13:10Z' (None, če oblika ni taka)."""
    try:
        return dt.datetime.strptime((s or "").replace("UTC", "").strip(), "%d.%m.%Y %H:%M").strftime("%Y-%m-%dT%H:%MZ")
    except ValueError:
        return None


def parse_stations(text, home=HOME, radius=RADIUS_KM):
    """Vrne seznam slovarjev postaj v radiju (z dnevnikom vrednosti; manjkajoče je None)."""
    root = ET.fromstring(text)
    out = []
    for md in root.iter("metData"):
        g = lambda tag: (md.findtext(tag) or "").strip()
        lat, lon = num(g("domain_lat")), num(g("domain_lon"))
        if lat is None or lon is None or km(home[0], home[1], lat, lon) > radius:
            continue
        row = {"valid_utc": parse_utc(g("tsValid_issued_UTC")) or parse_utc(g("validEnd")),
               "id": g("domain_meteosiId"), "name": g("domain_longTitle") or g("domain_title"),
               "alt_m": num(g("domain_altitude")), "lat": lat, "lon": lon,
               "km": round(km(home[0], home[1], lat, lon), 1), "type": g("domain_meteosiType")}
        for tag, col in WANT.items():
            row[col] = num(g(tag))
        out.append(row)
    return sorted(out, key=lambda r: r["km"])


def append_log(rows, path=LOG_PATH):
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            seen = {(r["valid_utc"], r["id"]) for r in csv.DictReader(f)}
    new = [r for r in rows if r["valid_utc"] and (r["valid_utc"], r["id"]) not in seen]
    if not new:
        return 0
    new_file = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for r in new:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in FIELDS})
    return len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--radius", type=float, default=RADIUS_KM)
    ap.add_argument("--log", default=LOG_PATH)
    a = ap.parse_args()
    try:
        req = urllib.request.Request(URL, headers=UA)
        with urllib.request.urlopen(req, timeout=90) as r:
            text = r.read().decode("utf-8", "replace")
        rows = parse_stations(text, radius=a.radius)
    except (urllib.error.URLError, TimeoutError, OSError, ET.ParseError) as e:
        print(f"✗ ARSO vir ni dosegljiv ({e})", file=sys.stderr)
        return 0                      # CI naj zaradi tega ne pade
    print(f"postaj v {a.radius:.0f} km: {len(rows)}")
    for r in rows:
        print(f"  {r['km']:5.1f} km  {r['id']:<12} {r['name']:<24} {r['type'] or '':<16} {r['alt_m']!s:>6} m  "
              f"snow={r['snow_cm']}  t={r['t']}  rr={r['rr_mm']}  tp12={r['tp_12h_mm']}  [{r['valid_utc']}]")
    if a.list:
        return 0
    print(f"→ {os.path.relpath(a.log, ROOT)}: {append_log(rows, a.log)} vrstic")
    return 0


if __name__ == "__main__":
    sys.exit(main())
