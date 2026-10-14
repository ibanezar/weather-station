#!/usr/bin/env python3
"""
tools/study_inat_glive_po_tednih.py -- kdaj v letu Slovenci fotografirajo glive? (iNaturalist)

ENKRATNA analiza za članek o vrhu gobarske sezone, ni del cevovoda. Piše samo AGREGATE (število
opažanj po tednih), posameznih opažanj ne bere in ne hrani (licence so po opažanju različne).

Metoda: za vsak teden (julij-november, od 2020; teden se začne 1. 7. in teče po 7 dni) dve poizvedbi
`total_results` na iNaturalist API (place_id 8228 = Slovenija, brez filtra kakovosti):
  - vse (vsa opažanja vseh organizmov),
  - glive (taxon_id 47169 = Fungi).
Delež gliv = glive / vse. Ker je opazovalcev iz leta v leto več, absolutna števila med leti niso
primerljiva; primerljiva sta ČAS vrha in DELEŽ. Delež ima svojo pristranskost: ko novembra upade
opazovanje žuželk in rastlin, delež gliv zraste, ne da bi jih bilo več. Zato sta v povzetku oba
kazalnika: teden z največ glivami (število) in teden z največjim deležem (≥ 150 vseh opažanj).
Zadnji (tekoči) teden je podcenjen, ker opazovalci opažanja nalagajo z zamudo.

Usage: python3 tools/study_inat_glive_po_tednih.py
Obstoječe tedne v `data/inat-glive-po-tednih.json` ne ponavlja (zaradi zamude nalaganja jih po
potrebi izbriši ročno).
"""
import datetime as dt
import json
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "inat-glive-po-tednih.json")
UA = "meteorec-bot/1.0 (+https://meteorec.si/o-postaji.html)"
FUNGI, SLOVENIJA = 47169, 8228
FIRST_YEAR = 2020
MIN_ALL = 150


def count(d1, d2, taxon=None):
    q = {"place_id": SLOVENIJA, "d1": d1, "d2": d2, "per_page": 0}
    if taxon:
        q["taxon_id"] = taxon
    url = "https://api.inaturalist.org/v1/observations?" + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=60))["total_results"]
        except Exception:
            time.sleep(3 * (i + 1))
    raise SystemExit("iNaturalist ne odgovarja: " + url)


def main():
    data = json.load(open(OUT)) if os.path.exists(OUT) else {}
    weeks = data.get("tedni", {})
    last_full = dt.date.today() - dt.timedelta(days=1)
    for y in range(FIRST_YEAR, last_full.year + 1):
        d = dt.date(y, 7, 1)
        while d <= dt.date(y, 11, 30):
            e = d + dt.timedelta(6)
            if e > last_full:
                break
            k = d.isoformat()
            if k not in weeks:
                weeks[k] = {"vse": count(k, e.isoformat()), "glive": count(k, e.isoformat(), FUNGI)}
                time.sleep(0.7)
            d = e + dt.timedelta(1)
    summary = {}
    for y in sorted({int(k[:4]) for k in weeks}):
        ws = sorted((k, v) for k, v in weeks.items() if k.startswith(str(y)))
        top = max(ws, key=lambda kv: kv[1]["glive"])
        cand = [kv for kv in ws if kv[1]["vse"] >= MIN_ALL]
        top_s = max(cand, key=lambda kv: kv[1]["glive"] / kv[1]["vse"])
        months = {}
        for k, v in ws:
            m = int(k[5:7])
            a = months.setdefault(m, [0, 0])
            a[0] += v["glive"]
            a[1] += v["vse"]
        summary[str(y)] = {
            "teden_z_najvec_glivami": {"zacetek": top[0], "glive": top[1]["glive"]},
            "teden_z_najvecjim_delezem": {"zacetek": top_s[0], "delez": round(100 * top_s[1]["glive"] / top_s[1]["vse"])},
            "delez_po_mesecih": {str(m): round(100 * a[0] / a[1]) for m, a in sorted(months.items()) if a[1]},
            "skupaj_glive": sum(v["glive"] for _, v in ws),
            "zadnji_teden": ws[-1][0],
        }
    out = {"_meta": {"vir": "iNaturalist API, place_id 8228, taxon_id 47169 (Fungi)",
                     "opomba": "agregati po tednih; teden se začne 1. 7. + 7n dni; zadnji teden je podcenjen (zamuda nalaganja)",
                     "generirano": dt.date.today().isoformat()},
           "tedni": dict(sorted(weeks.items())), "povzetek": summary}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("zapisano", OUT, len(weeks), "tednov")


if __name__ == "__main__":
    main()
