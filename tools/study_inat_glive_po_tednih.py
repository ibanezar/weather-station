#!/usr/bin/env python3
"""
tools/study_inat_glive_po_tednih.py -- kdaj v letu Slovenci fotografirajo glive? (iNaturalist)

ENKRATNA analiza za članek o vrhu gobarske sezone, ni del cevovoda. Piše samo AGREGATE (število
opažanj po tednih), posameznih opažanj ne bere in ne hrani (licence so po opažanju različne).

Metoda: za vsak teden (julij-november, od 2020; teden se začne 1. 7. in teče po 7 dni) poizvedbe
`total_results` na iNaturalist API (place_id 8228 = Slovenija, brez filtra kakovosti):
  - vse (vsa opažanja vseh organizmov),
  - fungi (taxon_id 47170 = kraljestvo gliv, vključno z lišaji, plesnimi, kvasovkami, zaprtotrosnicami),
  - basidio (taxon_id 47169 = deblo Basidiomycota: prave gobe, trdoživke, rje, snetjave),
  - agarico (taxon_id 50814 = razred Agaricomycetes: klobučnice, trdoživke, bokalčki; to večina
    ljudi razume pod »gobe«).
POZOR: oznaka 47169 NI »Fungi«, ampak Basidiomycota (kraljestvo je 47170); napaka v prvi različici
tega skripta (označeno kot Fungi) je bila odkrita 14. 10. 2026.
Delež = skupina / vse. Ker je opazovalcev iz leta v leto več, absolutna števila med leti niso
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
GROUPS = {"fungi": 47170, "basidio": 47169, "agarico": 50814}
SLOVENIJA = 8228
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
            w = weeks.setdefault(k, {})
            if "glive" in w:       # prva različica: »glive« je bil v resnici Basidiomycota
                w["basidio"] = w.pop("glive")
            if "vse" not in w:
                w["vse"] = count(k, e.isoformat())
                time.sleep(0.7)
            for g, tid in GROUPS.items():
                if g not in w:
                    w[g] = count(k, e.isoformat(), tid)
                    time.sleep(0.7)
            d = e + dt.timedelta(1)
    summary = {}
    for g in GROUPS:
        summary[g] = {}
        for y in sorted({int(k[:4]) for k in weeks}):
            ws = sorted((k, v) for k, v in weeks.items() if k.startswith(str(y)))
            top = max(ws, key=lambda kv: kv[1][g])
            cand = [kv for kv in ws if kv[1]["vse"] >= MIN_ALL]
            top_s = max(cand, key=lambda kv: kv[1][g] / kv[1]["vse"])
            months = {}
            for k, v in ws:
                a = months.setdefault(int(k[5:7]), [0, 0])
                a[0] += v[g]
                a[1] += v["vse"]
            summary[g][str(y)] = {
                "teden_z_najvec": {"zacetek": top[0], "stevilo": top[1][g]},
                "teden_z_najvecjim_delezem": {"zacetek": top_s[0], "delez": round(100 * top_s[1][g] / top_s[1]["vse"])},
                "delez_po_mesecih": {str(m): round(100 * a[0] / a[1]) for m, a in sorted(months.items()) if a[1]},
                "skupaj": sum(v[g] for _, v in ws),
                "zadnji_teden": ws[-1][0],
            }
    out = {"_meta": {"vir": "iNaturalist API, place_id 8228; skupine: fungi 47170, basidio 47169, agarico 50814",
                     "opomba": "agregati po tednih; teden se začne 1. 7. + 7n dni; zadnji teden je podcenjen (zamuda nalaganja)",
                     "generirano": dt.date.today().isoformat()},
           "tedni": dict(sorted(weeks.items())), "povzetek": summary}
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("zapisano", OUT, len(weeks), "tednov")


if __name__ == "__main__":
    main()
