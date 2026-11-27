#!/usr/bin/env python3
"""
tools/log_claef_snow.py — dnevni zajem napovedi snega C-LAEF AlpeAdria 1 km (in ICON-D2, ECMWF IFS za
primerjavo) za ARSO postaje v okolici Rečice, od zdaj naprej.

Zakaj: C-LAEF je od junija 2026 operativen, od septembra odprt (GeoSphere `nwp-v2-1h-1km`, v Open-Meteo
`geosphere_claef_austria`), a napovedi snega NAZAJ v času ni. Ali je res boljši od ICON-D2 pri snegu v naši
dolini, pove samo dnevnik napovedi, kakršne so bile dan–tri dni prej, primerjan z izmerjeno višino odeje
ARSO (`data/arso-snow-live.csv`). Vsak dan zamujenega zajema je izgubljen. Ocena: tools/ai/eval_claef_snow.py.

Piše data/claef-snow-log.csv: ena vrstica na (issued_at, valid_at, postaja, model) z
  snow_new_cm  vsota urnega modelskega novega snega v lokalnem dnevu (cm, Open-Meteo `snowfall`)
  depth07_raw  višina snega ob 7:00 lokalno (ura odčitka ARSO), SUROVA vrednost iz odgovora
  depth_unit   enota, kakršno je vrnil Open-Meteo (ICON-D2 in IFS »m«). **C-LAEF višine snega prek Open-Meteo
               NE vrne** (27. 11. 2026: `snow_depth` povsod prazen, enota »undefined«; v GeoSphere API v2 parametra
               `sd` ni): za C-LAEF je zato mogoče ocenjevati samo `snow_new_cm`, višina ostane prazna
  cell_elev_m  višina modelske celice, alt_m višina postaje: razlika več sto metrov je glavni vir napake.

Samo zunanje vrednosti Open-Meteo in ARSO; notranjih meritev ne bere (glej pravilo na vrhu CLAUDE.md).
Ob nedosegljivem viru (429!) skript konča z 0 in ne spremeni ničesar.

Usage:
  python3 tools/log_claef_snow.py
"""
import csv, datetime, json, os, sys, time, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "claef-snow-log.csv")
ARSO_PATH = os.path.join(ROOT, "data", "arso-snow-live.csv")
TZ = ZoneInfo("Europe/Ljubljana")
UA = {"User-Agent": "Meteorec-ClaefSnowLog/1.0 https://meteorec.si"}
# ARSO postaje (oznake iz živega vira) z izmerjeno višino odeje; koordinate in višina se preberejo iz
# data/arso-snow-live.csv (ISTE kot pri ARSO), da napovedi in meritev ne ločijo ugibane koordinate.
STATIONS = ["GORNJ-GRA_", "RADEG-NDA_", "LOGAR-DOL_", "JEZERSKO_", "PAVLI-SED_", "KRVAVEC_", "ROGLA_", "URSLJ-GOR_"]
MODELS = ["geosphere_claef_austria", "icon_d2", "ecmwf_ifs025"]
LEADS = (1, 2, 3)
DAYS = max(LEADS) + 1
READ_HOUR = 7                      # ARSO odčitek višine odeje (7:00 po lokalnem času)
FIELDS = ["issued_at", "valid_at", "lead_days", "station", "alt_m", "model", "cell_elev_m",
          "snow_new_cm", "depth07_raw", "depth_unit"]
RETRY_S = (5, 20, 45)


def read_stations(path=ARSO_PATH):
    """{id: (lat, lon, alt_m)} iz najnovejše vrstice vsake postaje v dnevniku ARSO; manjkajoče izpusti."""
    out = {}
    try:
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["id"] in STATIONS:
                    try:
                        out[r["id"]] = (float(r["lat"]), float(r["lon"]), float(r["alt_m"]))
                    except (TypeError, ValueError):
                        pass
    except FileNotFoundError:
        pass
    return out


def fetch(st):
    """Odgovor Open-Meteo za vse postaje naenkrat (en klic: kvota je skupna z ostalimi karticami)."""
    ids = [i for i in STATIONS if i in st]
    q = urllib.parse.urlencode({
        "latitude": ",".join(str(st[i][0]) for i in ids), "longitude": ",".join(str(st[i][1]) for i in ids),
        "hourly": "snowfall,snow_depth", "models": ",".join(MODELS),
        "forecast_days": DAYS, "timezone": "Europe/Ljubljana"})
    last = None
    for wait in (0,) + RETRY_S:
        time.sleep(wait)
        try:
            req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + q, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.load(r)
            return ids, (d if isinstance(d, list) else [d])
        except Exception as e:                      # noqa: BLE001 - omrežje/API (429), prehodno
            last = e
    raise RuntimeError(last)


def _num(x):
    return None if x is None else float(x)


def summarize(ids, locs, st, issued):
    """Vrstice za vodilne čase LEADS: {(valid_at, station, model): vrstica}."""
    out = {}
    for sid, loc in zip(ids, locs):
        h = loc.get("hourly") or {}
        units = loc.get("hourly_units") or {}
        times = h.get("time") or []
        for m in MODELS:
            sf, sd = h.get(f"snowfall_{m}"), h.get(f"snow_depth_{m}")
            if sf is None and sd is None:
                continue
            days = {}
            for i, ts in enumerate(times):
                d = days.setdefault(ts[:10], {"sf": [], "sd7": None})
                if sf and i < len(sf) and sf[i] is not None:
                    d["sf"].append(float(sf[i]))
                if sd and i < len(sd) and sd[i] is not None and int(ts[11:13]) == READ_HOUR:
                    d["sd7"] = float(sd[i])
            for day, d in days.items():
                lead = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(issued)).days
                if lead not in LEADS or (not d["sf"] and d["sd7"] is None):
                    continue
                out[(day, sid, m)] = {
                    "issued_at": issued, "valid_at": day, "lead_days": lead, "station": sid,
                    "alt_m": st[sid][2], "model": m, "cell_elev_m": loc.get("elevation", ""),
                    # dan z manj kot 20 urami snega ni popoln dan (npr. C-LAEF sega 60 h): vsota bi bila prenizka
                    "snow_new_cm": round(sum(d["sf"]), 2) if len(d["sf"]) >= 20 else "",
                    "depth07_raw": "" if d["sd7"] is None else round(d["sd7"], 4),
                    "depth_unit": units.get(f"snow_depth_{m}", ""),
                }
    return out


def main():
    issued = datetime.datetime.now(TZ).date().isoformat()
    st = read_stations()
    if not st:
        print("⚠ ni postaj ARSO (data/arso-snow-live.csv) — preskočeno.", file=sys.stderr)
        return 0
    rows, seen = [], set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                seen.add((r["issued_at"], r["valid_at"], r["station"], r["model"]))
    try:
        ids, locs = fetch(st)
    except Exception as e:                          # omrežje/API: dnevnik ostane nedotaknjen
        print(f"⚠ napoved snega ni dosegljiva ({e}) — preskočeno.", file=sys.stderr)
        return 0
    new = [r for k, r in sorted(summarize(ids, locs, st, issued).items()) if (issued,) + k not in seen]
    if not new:
        print("Ni novih vrstic.")
        return 0
    rows += new
    rows.sort(key=lambda r: (r["issued_at"], r["valid_at"], r["station"], r["model"]))
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"✓ {len(new)} novih vrstic ({issued}), skupaj {len(rows)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
