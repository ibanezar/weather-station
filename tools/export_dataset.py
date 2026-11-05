#!/usr/bin/env python3
"""
tools/export_dataset.py — dnevni podatki postaje IREICA1 kot CSV za citiranje in iskalnike podatkov.

Zakaj: `history.json` je slovar po datumih z internimi polji (`src`), CSV je oblika, ki jo razumejo Google Dataset Search,
Zenodo, Kaggle in vsak razisko­valec. Izvoz je izpeljan iz `history.json` (nikoli ročno) in se osvežuje v `update-history.yml`.

Kaj je v njem — in česa ni:
  - SAMO zunanje meritve postaje IREICA1 (temperatura, padavine, veter, vlaga). Notranjih meritev ni (CLAUDE.md, zasebnost).
  - Dnevi z `src == "era5"` so IZPUŠČENI: to je reanaliza, ne meritev postaje (v `history.json` jih je nekaj dni, ko postaja ni
    delovala); v zbirki, ki se imenuje »meritve postaje«, jim ni mesta.
  - Polja brez vrednosti so prazna (ne 0).

Enote: °C, mm, km/h, %. Datum je lokalni dan (Europe/Ljubljana). Licenca CC BY 4.0.

Piše podatki/ireica1-dnevni-podatki.csv.

Usage:
  python3 tools/export_dataset.py
"""
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY = os.path.join(ROOT, "history.json")
OUT = os.path.join(ROOT, "podatki", "ireica1-dnevni-podatki.csv")

# (stolpec CSV, ključ v history.json). Imena so angleška: zbirko berejo tudi tuji iskalniki in orodja.
COLUMNS = [("date", None), ("temp_max_c", "tempHigh"), ("temp_min_c", "tempLow"), ("temp_avg_c", "tempAvg"),
           ("precip_mm", "precipTotal"), ("wind_max_kmh", "windspeedHigh"), ("wind_avg_kmh", "windspeedAvg"),
           ("humidity_avg_pct", "humidityAvg")]
EXCLUDE_SRC = {"era5"}


def build_rows(hist):
    """history.json (slovar po datumih) → vrstice CSV; dnevi iz reanalize so izpuščeni."""
    rows = []
    for day in sorted(hist):
        rec = hist[day] or {}
        if rec.get("src") in EXCLUDE_SRC:
            continue
        row = [day]
        for _, key in COLUMNS[1:]:
            v = rec.get(key)
            row.append("" if v is None else f"{float(v):g}")
        rows.append(row)
    return rows


def write_csv(rows, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow([c for c, _ in COLUMNS])
        w.writerows(rows)


def main():
    with open(HISTORY, encoding="utf-8") as f:
        hist = json.load(f)
    rows = build_rows(hist)
    write_csv(rows)
    print(f"✓ {os.path.relpath(OUT, ROOT)}: {len(rows)} dni ({rows[0][0]} … {rows[-1][0]}), izpuščenih iz reanalize: {len(hist) - len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
