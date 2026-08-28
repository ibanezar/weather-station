#!/usr/bin/env python3
"""
tools/fetch_hydrants.py — hidranti in odvzemna mesta za MeteoGasilec (P1).

Vir: OpenStreetMap prek javnega Overpass strežnika (overpass-api.de).
OSM opozarja, da so javni Overpass strežniki namenjeni manjšim projektom in se
lahko preobremenijo — zato TA skript teče ENKRAT DNEVNO (znotraj
gasilec-forecast.yml, ni ločenega delavnega toka) in piše statičen
meteogasilec/hidranti.json, ki ga stran samo bere. Noben odjemalec (brskalnik)
Overpass ne kliče neposredno.

Geografski obseg je namenoma REGIONALEN, ne nacionalen: Zgornja Savinjska
dolina (Solčava–Luče–Ljubno ob Savinji–Rečica ob Savinji–Mozirje–Nazarje–
Gornji Grad) — isti lokalni značaj kot preostanek strani (ena postaja, ena
dolina). GPS na /meteogasilec/intervencija/ (vreme) ostaja neomejen na
poljubno lokacijo v Sloveniji — samo hidranti so vezani na dolino.

Ob napaki (Overpass nedosegljiv, timeout, neveljaven odgovor) skript izpiše
opozorilo na stderr in KONČA Z 0, ne da bi prepisal obstoječo datoteko — isto
načelo kot tools/inject_forecast.py ("raje stara napoved kot prazna stran").

Glavni javni strežnik overpass-api.de zna zavračati zahteve iz podatkovnih
centrov (opaženo pri gradnji — connection reset, medtem ko isti klic na
overpass.openstreetmap.fr uspe). GitHub Actions gostuje na podobnih IP
razponih, zato skript poskusi VEČ zrcal po vrsti (OVERPASS_MIRRORS) in
obdrži staro datoteko šele, če odpovejo vsa.

Tri stanja hidranta (🟢 preverjeno / 🟡 samo OSM / 🔴 nedelujoče) gredo prek
ročne kalibracijske tabele HYDRANT_OVERRIDES spodaj — isti vzorec kot
CALIBRATION v tools/import_species_db.py. Brez vnosa je hidrant "osm" (🟡).

Uporaba:
  python3 tools/fetch_hydrants.py                # povpraša Overpass, zapiše JSON
  python3 tools/fetch_hydrants.py --no-write      # samo izpis
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_seo_pages as seo  # noqa: E402 — ROOT

ROOT = seo.ROOT
OUT_JSON = os.path.join(ROOT, "meteogasilec", "hidranti.json")

# south, west, north, east — Zgornja Savinjska dolina z majhno rezervo okrog
# skrajnih krajev (Solčava na severu, Gornji Grad na jugozahodu).
BBOX = (46.26, 14.60, 46.45, 15.05)

# Zaporedje javnih zrcal — prvo, ki uspe, zmaga. Vrstni red: zrcalo, ki se je
# pri gradnji izkazalo za zanesljivega iz podatkovnih centrov, je prvo.
OVERPASS_MIRRORS = [
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "Meteorec/1.0 (meteorec.si; hidranti za /meteogasilec/)"

EMERGENCY_TYPES = ["fire_hydrant", "suction_point", "water_tank"]

TYPE_LABELS = {
    "fire_hydrant": "Hidrant",
    "suction_point": "Sesalno mesto",
    "water_tank": "Požarni rezervoar",
}

# Ročna kalibracija posameznih hidrantov — ključ je OSM id ("node/12345" ali
# "way/12345"). Prazna od začetka; vsak vnos potrebuje "razlog" (isto pravilo
# kot CALIBRATION v import_species_db.py — popravek gre vanjo šele, ko je
# preverjen na terenu, ne na slepo).
HYDRANT_OVERRIDES = {
    # "node/1234567": {"status": "verified", "razlog": "PGD Rečica preveril 2026"},
}

STATUS_LABELS = {
    "verified": "preverjeno",
    "osm": "samo OSM",
    "broken": "nedelujoče/nedostopno",
}


def build_query():
    s, w, n, e = BBOX
    bbox = f"{s},{w},{n},{e}"
    types = "|".join(EMERGENCY_TYPES)
    return f'[out:json][timeout:25];nwr["emergency"~"^({types})$"]({bbox});out center tags;'


def fetch_overpass():
    data = build_query().encode("utf-8")
    last_err = None
    for url in OVERPASS_MIRRORS:
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "text/plain", "User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            print(f"  ⚠ {url}: {e}", file=sys.stderr)
            last_err = e
    raise last_err


def normalize(overpass_json):
    items = []
    for el in overpass_json.get("elements") or []:
        etype = el.get("type")
        eid = el.get("id")
        if etype is None or eid is None:
            continue
        osm_id = f"{etype}/{eid}"
        lat = el.get("lat")
        lon = el.get("lon")
        if lat is None or lon is None:
            center = el.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags") or {}
        emergency = tags.get("emergency")
        if emergency not in EMERGENCY_TYPES:
            continue
        override = HYDRANT_OVERRIDES.get(osm_id, {})
        items.append({
            "id": osm_id,
            "type": emergency,
            "label": TYPE_LABELS.get(emergency, emergency),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "status": override.get("status", "osm"),
            "tags": {
                "diameter": tags.get("fire_hydrant:diameter"),
                "pressure": tags.get("fire_hydrant:pressure"),
                "flow_rate": tags.get("flow_rate") or tags.get("fire_hydrant:flow_rate"),
                "hydrant_type": tags.get("fire_hydrant:type"),
                "water_source": tags.get("water_source"),
            },
        })
    return items


def main():
    ap = argparse.ArgumentParser(description="Hidranti/odvzemna mesta (OSM) za /meteogasilec/")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    print(f"Povprašujem Overpass za bbox {BBOX} (Zgornja Savinjska dolina) …")
    try:
        raw = fetch_overpass()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        print(f"⚠ Overpass nedosegljiv, obdržim obstoječ meteogasilec/hidranti.json: {e}", file=sys.stderr)
        sys.exit(0)

    items = normalize(raw)
    if not items:
        print("⚠ Overpass ni vrnil nobenega hidranta — obdržim obstoječo datoteko.", file=sys.stderr)
        sys.exit(0)

    payload = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "bbox": list(BBOX),
        "count": len(items),
        "items": items,
    }

    counts = {}
    for it in items:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    print(f"Najdenih {len(items)} vnosov: " + ", ".join(f"{TYPE_LABELS[k]} {v}" for k, v in counts.items()))

    if not args.no_write:
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"→ {OUT_JSON}")


if __name__ == "__main__":
    main()
