#!/usr/bin/env python3
"""
tools/ai/eval_claef_snow.py — ali je C-LAEF AlpeAdria 1 km pri snegu v naši dolini boljši od ICON-D2 in IFS?

Primerja napovedi iz data/claef-snow-log.csv (tools/log_claef_snow.py) z izmerjeno višino snežne odeje ARSO
(data/arso-snow-live.csv) ob 7:00 lokalno, po modelu in vodilnem času. Dva pogleda:
  1. VIŠINA ODEJE (samo ICON-D2 in IFS): MAE, pristranskost, delež zadetkov »je sneg ≥ 1 cm / ni«.
  2. NOVI SNEG (vsi modeli): modelska vsota novega snega v lokalnem dnevu proti pozitivnemu prirastku izmerjene
     odeje med dvema zaporednima jutroma; delež zadetkov »novi sneg ≥ 1 cm / ni«. Prirastek odeje je približek
     (tajanje in sesedanje ga zmanjšata, okno 7:00–7:00 ni enako koledarskemu dnevu), zato je to pregled, ne resnica.
Namenoma NE trdi nič pod MIN_DAYS dni (isto načelo kot eval_live_refresh): beleženje teče od 27. 11. 2026,
sklepa torej ni pred ~15. 12.

C-LAEF višine snega NE ponuja: v Open-Meteo je `snow_depth` za `geosphere_claef_austria` prazen (preverjeno 27. 11. 2026,
56 vrstic dnevnika), v GeoSphere API v2 parametra `sd` ni (samo `sf`, `rain`, `tp`, `snowlmt`). Trditve »C-LAEF je
najnatančnejši pri višini snega« zato s temi viri ni mogoče preveriti; mogoče je preveriti novi sneg.

Usage:
  python3 tools/ai/eval_claef_snow.py
"""
import csv, datetime, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "data", "claef-snow-log.csv")
ARSO = os.path.join(ROOT, "data", "arso-snow-live.csv")
MIN_DAYS = 15
READ_FROM_UTC = 5.5        # odčitek ARSO ob 7:00 CET (6:00 UTC) je v živem viru od ~6:50 UTC naprej (sezona okt–apr)
READ_WINDOW_H = 8.5        # beležimo nekajkrat na dan: vzamemo prvi odčitek v oknu 5:30–14:00 UTC


def _t(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)


def observed(path=ARSO):
    """{(postaja, datum): višina odeje cm} — prvi odčitek dneva v oknu 5:30–14:00 UTC (po jutranjem odčitku ARSO)."""
    best = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["snow_cm"] in ("", None):
                continue
            t = _t(r["valid_utc"])
            gap = t.hour + t.minute / 60 - READ_FROM_UTC      # ur po začetku okna
            k = (r["id"], t.date().isoformat())
            if 0 <= gap <= READ_WINDOW_H and (k not in best or gap < best[k][0]):
                best[k] = (gap, float(r["snow_cm"]))
    return {k: v[1] for k, v in best.items()}


def pairs(log=LOG, arso=ARSO):
    """(višina odeje, novi sneg): {(model, lead): [(napoved cm, meritev cm, datum)]} za vsako."""
    obs = observed(arso)
    depth, new = defaultdict(list), defaultdict(list)
    with open(log, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            o = obs.get((r["station"], r["valid_at"]))
            if o is None:
                continue
            lead, m = int(r["lead_days"]), r["model"]
            if r["depth07_raw"] != "" and r["depth_unit"] == "m":
                depth[(m, lead)].append((float(r["depth07_raw"]) * 100, o, r["valid_at"]))
            prev = (datetime.date.fromisoformat(r["valid_at"]) - datetime.timedelta(days=1)).isoformat()
            o0 = obs.get((r["station"], prev))
            if r["snow_new_cm"] != "" and o0 is not None:
                new[(m, lead)].append((float(r["snow_new_cm"]), max(0.0, o - o0), r["valid_at"]))
    return depth, new


def _table(title, P):
    print(title)
    print(f"{'model':26s} lead {'N':>4s} {'MAE cm':>7s} {'bias cm':>8s} {'zadetki ≥1 cm':>14s}")
    for (m, lead), v in sorted(P.items()):
        n = len(v)
        mae = sum(abs(a - b) for a, b, _ in v) / n
        bias = sum(a - b for a, b, _ in v) / n
        hit = sum((a >= 1) == (b >= 1) for a, b, _ in v) / n
        print(f"{m:26s} {lead:4d} {n:4d} {mae:7.1f} {bias:8.1f} {hit:13.0%}")
    print()


def main():
    if not (os.path.exists(LOG) and os.path.exists(ARSO)):
        print("Ni dnevnika napovedi ali meritev ARSO.")
        return 0
    depth, new = pairs()
    days = {d for P in (depth, new) for v in P.values() for _, _, d in v}
    if not days:
        print("Ni parov napoved–meritev (dnevnik ARSO še nima jutranjih odčitkov za dneve napovedi).")
        return 0
    print(f"Dni z meritvijo: {len(days)} (potrebno ≥ {MIN_DAYS} za sklep)\n")
    if depth:
        _table("Višina snežne odeje ob 7:00 (C-LAEF je ne ponuja)", depth)
    if new:
        _table("Novi sneg: modelska vsota dneva proti prirastku odeje", new)
    if len(days) < MIN_DAYS:
        print(f"Premalo dni ({len(days)} < {MIN_DAYS}): to je pregled, ne sklep. Ne trdi, kateri model je boljši.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
