#!/usr/bin/env python3
"""
tools/study_napoved_po_dneh.py -- kako hitro pada vrednost napovedi z vodilnim časom? (IREICA1)

ENKRATNA analiza za članek o sedmem dnevu napovedi, ni del cevovoda. Piše samo agregate v
`data/napoved-po-dneh.json`.

Zakaj ne kar `data/test-napovedi.json`: tam je persistenca samo »jutri = danes« (D+1), kar se ne
sme primerjati z D+7. Tu so izhodišča POŠTENA za vsak vodilni čas, na ISTIH dneh:
  - klimatologija: povprečje ±7 dni okoli koledarskega dne v VSEH drugih letih (brez leta,
    ki ga ocenjujemo -- sicer bi klimatologija »vedela« za ta dan),
  - persistenca za D+k: meritev k dni prej.
Modela IFS in GFS imata arhiv za vseh 7 dni na istih dneh; ICON nima D+7 in ima med D+1 in D+2
sumljiv skok napake Tmin (1,5 -> 2,4 °C), zato ni jedro primerjave (v izhod gre samo Tmax).
Napoved = arhiv `data/forecast-archive.csv` (Open-Meteo Previous Runs: kaj je model napovedal
k dni prej), meritev = `history.json` (tempHigh/tempLow/precipTotal). Notranjih meritev ne bere.

Usage: python3 tools/study_napoved_po_dneh.py
"""
import collections
import csv
import datetime as dt
import json
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_MODELS = ["ecmwf_ifs025", "gfs_seamless"]
LEADS = range(1, 8)
WET_MM = 0.2          # isti prag kot WET_DAY_MM v verify_forecasts.py
D = dt.date.fromisoformat


def main():
    hist = json.load(open(os.path.join(ROOT, "history.json")))
    obs = {d: (v["tempHigh"], v["tempLow"], v.get("precipTotal") or 0.0)
           for d, v in hist.items() if v.get("tempHigh") is not None and v.get("tempLow") is not None}
    years = collections.defaultdict(set)
    for d in obs:
        years[D(d).year].add(d)

    def clim(date, idx):
        d = D(date)
        vals = []
        for y in years:
            if y == d.year:
                continue
            for k in range(-7, 8):
                try:
                    dd = dt.date(y, d.month, d.day) + dt.timedelta(k)
                except ValueError:
                    continue
                o = obs.get(dd.isoformat())
                if o:
                    vals.append(o[idx])
        return st.mean(vals) if len(vals) >= 20 else None

    rows = collections.defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "forecast-archive.csv"))):
        if r["tmax_c"] and r["tmin_c"] and r["precip_mm"] != "":
            rows[(r["model"], int(r["lead_days"]))][r["valid_at"]] = (
                float(r["tmax_c"]), float(r["tmin_c"]), float(r["precip_mm"]))

    out = {"_meta": {"vir_napovedi": "data/forecast-archive.csv (Open-Meteo Previous Runs)",
                     "vir_meritev": "history.json (IREICA1)", "modeli": CORE_MODELS,
                     "klimatologija": "±7 dni, brez ocenjevanega leta",
                     "popravek": "ena konstanta na vodilni čas, povprečna napaka v drugih letih (arhiv obsega le 2024-2026)", "prag_dezja_mm": WET_MM},
           "leads": {}}
    for k in LEADS:
        common = set(obs)
        for m in CORE_MODELS:
            common &= set(rows[(m, k)])
        common = [d for d in sorted(common) if clim(d, 0) is not None
                  and (D(d) - dt.timedelta(days=k)).isoformat() in obs]
        n = len(common)
        res = {"n": n, "od": common[0], "do": common[-1]}
        for idx, nm in ((0, "tmax"), (1, "tmin")):
            def pack(errs, signed=None):
                o = {"mae": round(st.mean(errs), 2), "pct_gt3": round(100 * sum(e > 3 for e in errs) / len(errs), 1)}
                return o
            cl = [abs(obs[d][idx] - clim(d, idx)) for d in common]
            pe = [abs(obs[d][idx] - obs[(D(d) - dt.timedelta(days=k)).isoformat()][idx]) for d in common]
            block = {"klimatologija": pack(cl), "persistenca": pack(pe)}
            for m in CORE_MODELS:
                e = [abs(obs[d][idx] - rows[(m, k)][d][idx]) for d in common]
                b = [rows[(m, k)][d][idx] - obs[d][idx] for d in common]
                o = pack(e)
                o["skill"] = round(1 - st.mean(e) / st.mean(cl), 2)
                o["bias"] = round(st.mean(b), 2)
                # en sam popravek na vodilni čas = povprečna napaka v DRUGIH letih (leave-one-year-out)
                by_year = collections.defaultdict(list)
                for d, bb in zip(common, b):
                    by_year[D(d).year].append(bb)
                ec = []
                for d, bb in zip(common, b):
                    others = [x for yy, l in by_year.items() if yy != D(d).year for x in l]
                    ec.append(abs(bb - st.mean(others)))
                o["mae_s_popravkom"] = round(st.mean(ec), 2)
                block[m] = o
            res[nm] = block
        rain = {}
        for m in CORE_MODELS:
            hit = fa = miss = cn = 0
            for d in common:
                p, a = rows[(m, k)][d][2] >= WET_MM, obs[d][2] >= WET_MM
                hit += p and a
                fa += p and not a
                miss += (not p) and a
                cn += (not p) and (not a)
            rain[m] = {"napovedan_dez": hit + fa, "dez_res": hit, "ni_bilo_dezja": fa,
                       "delez_zgresenih_alarmov": round(100 * fa / (hit + fa), 1) if hit + fa else None,
                       "delez_zamujenega_dezja": round(100 * miss / (hit + miss), 1) if hit + miss else None}
        res["dez"] = rain
        out["leads"][str(k)] = res
    # smer napake pri D+1: delež dni v »tipično« smer in pristranskost po letnih časih
    season = {12: "zima", 1: "zima", 2: "zima", 3: "pomlad", 4: "pomlad", 5: "pomlad",
              6: "poletje", 7: "poletje", 8: "poletje", 9: "jesen", 10: "jesen", 11: "jesen"}
    smer = {}
    for m in CORE_MODELS:
        days = sorted(set(obs) & set(rows[(m, 1)]))
        smer[m] = {"n": len(days)}
        for idx, nm, sign in ((0, "tmax", -1), (1, "tmin", 1)):
            errs = [rows[(m, 1)][d][idx] - obs[d][idx] for d in days]
            by = collections.defaultdict(list)
            for d, e in zip(days, errs):
                by[season[int(d[5:7])]].append(e)
            smer[m][nm] = {"delez_dni_v_tipicno_smer": round(100 * sum(e * sign > 0 for e in errs) / len(errs)),
                           "bias_po_letnih_casih": {k: round(st.mean(v), 2) for k, v in by.items()}}
    out["smer_d1"] = smer
    p = os.path.join(ROOT, "data", "napoved-po-dneh.json")
    json.dump(out, open(p, "w"), ensure_ascii=False, indent=1)
    print("zapisano", p)


if __name__ == "__main__":
    main()
