#!/usr/bin/env python3
"""
Poskusi nad MTR v1 (24. 10. 2026): ali novi vhodi Open-Meteo izboljšajo Tmax/Tmin?

  eval_mtr4.py V1_CACHE.json PROFILE.json [since=2025-10-01]

V1_CACHE, PROFILE = izhod tools/ai/fetch_profile_cache.py (--v1 / prvi argument).
Metoda je ista kot v eval_mtr3.py (walk-forward po mesecih, lambda iz notranje validacije,
produkcijske zastavice: tmin = bias + cond, tmax = multi, primerjava na ISTIH dneh, uparjen
7-dnevni blokovni bootstrap); walk(), boot() in make_vec() so uvoženi od tam.

Kandidati (dodatni stolpci k produkcijskemu vektorju):
  prof   stabilnost iz višinskih nivojev: T925 − T2m ponoči, T850 − T2m podnevi, T850, veter 925 hPa
  cloud3 oblačnost po slojih (nizka ponoči/podnevi, srednja, visoka)
  snow   višina snega in vlaga tal
  blh    višina mejne plasti
  all    prof + cloud3 + snow + blh
  sun    trajanje sončnega obsevanja (sunshine_duration_previous_dayN)
  stab   samo stabilnost (T925 − T2m ponoči, T850 − T2m podnevi), brez ravni T850 in vetra
  ctrl   KONTROLA uhajanja: zlepljena Tmax/Tmin istega dne iz iste serije (čisti nowcast, brez
         profila). Če ctrl doseže enak dobitek kot prof, je dobitek uhajanje, ne informacija profila.

PRAVICA DO ZAKLJUČKA: za prof/cloud3/snow/blh arhiv `*_previous_dayN` ne obstaja (glej
fetch_profile_cache.py), zato so to ZLEPLJENE serije blizu analize: pri učenju IN pri oceni so
vhodi boljši od tistih, ki bi jih model res dobil dan prej. Rezultat je ZGORNJA MEJA informacije.
  - brez dobitka tudi tu  → ideja je mrtva, ne zbiraj podatkov;
  - dobitek tu            → upravičeno je začeti beležiti prave napovedi izpred 1-3 dni,
                            pošten rezultat pa pride šele z zbranim arhivom.
Samo `sun` je prava napoved izpred N dni in je zato pošten rezultat.
Vzorec zimskih mesecev je v oknu 2025-10 → danes ENA zima; stolpec »zima« je orientacija, ne dokaz.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import train_recica_mos as t   # noqa: E402
import eval_mtr3 as e3         # noqa: E402
import log_profile_forecasts as lp   # noqa: E402

WINTER = {11, 12, 1, 2}


def groups_from_columns(c):
    """Dnevni stolpci (log_profile_forecasts.daily_columns) → skupine vhodov za eval.
    Enaka preslikava velja za zlepljene serije (fetch_profile_cache) in za zapis pravih napovedi."""
    out = {}
    if None not in (c["inv_n"], c["lapse_d"], c["t850_d"], c["w925_n"]):
        out["prof"] = [c["inv_n"] / 5, c["lapse_d"] / 10, c["t850_d"] / 10, c["w925_n"] / 20]
    if None not in (c["inv_n"], c["lapse_d"]):
        out["stab"] = [c["inv_n"] / 5, c["lapse_d"] / 10]
    out["ctrl"] = [c["t2_max"] / 10, c["t2_min"] / 10]
    out["_snow_max"] = c["snow_max"]
    if None not in (c["low_n"], c["low_d"], c["mid_d"], c["high_d"]):
        out["cloud3"] = [c["low_n"] / 100, c["low_d"] / 100, c["mid_d"] / 100, c["high_d"] / 100]
    if c["snow_max"] is not None and c["soil_mean"] is not None:
        out["snow"] = [min(c["snow_max"], 0.3) * 3, 1.0 if c["snow_max"] > 0.01 else 0.0,
                       (c["soil_mean"] - 0.3) * 5]
    if c["blh_max"] is not None:
        out["blh"] = [c["blh_max"] / 1000]
    return out


def profile_features(rec):
    """Urne serije enega dne ([[ura, vrednost], ...] po spremenljivki) → skupine vhodov
    (prof / cloud3 / snow / blh / stab / ctrl) ali None, če dan nima dovolj ur temperature.
    Agregacija je v lp.daily_columns(), isti kot pri beleženju pravih napovedi."""
    cols = lp.daily_columns(rec)
    return None if cols is None else groups_from_columns(cols)


def sun_features(pairs):
    """Sekunde sonca v uri → ure sonca podnevi (10–18) in celi dan (/10)."""
    if not pairs or len(pairs) < 20:
        return None
    day = sum(v for h, v in pairs if h in t.DAY_HOURS) / 3600
    tot = sum(v for _, v in pairs) / 3600
    return [day / 9, tot / 12]


def build_extra(groups):
    def fn(f, target):
        v = []
        for g in groups:
            v += f["x"][g]
        return v
    return fn


CANDIDATES = {
    "base": None,
    "prof": ("prof",),
    "cloud3": ("cloud3",),
    "snow": ("snow",),
    "blh": ("blh",),
    "stab": ("stab",),
    "ctrl": ("ctrl",),
    "all": ("prof", "cloud3", "snow", "blh"),
    "sun": ("sun",),
    "all+sun": ("prof", "cloud3", "snow", "blh", "sun"),
}
NEEDED = ("prof", "cloud3", "snow", "blh", "sun", "stab", "ctrl")


def main():
    cache = json.load(open(sys.argv[1]))
    blob = json.load(open(sys.argv[2]))
    since = sys.argv[3] if len(sys.argv) > 3 else "2025-10-01"
    only = set(sys.argv[4].split(",")) | {"base"} if len(sys.argv) > 4 else None
    prof_days = {d: profile_features(rec) for d, rec in blob["profile"].items()}
    hist = t.load_history()
    multi = t.load_multi_archive()
    rows = {l: t._rows_from_cache(cache[str(l)]) for l in t.LEADS}
    bias = t.build_bias_series(rows[1], hist)
    base_t = t.temp_vector
    print("OPOZORILO: prof/cloud3/snow/blh so zlepljene serije blizu analize (zgornja meja); "
          "samo `sun` je prava napoved izpred N dni.\n")

    for tg in ("tmax", "tmin"):
        for lead in t.LEADS:
            smp = t.build_samples(rows[lead], hist, lead, bias, None, multi)
            if tg == "tmax":
                smp = [s for s in smp if s["f"].get("mm")]
            sun_rows = blob["sun"][str(lead)]
            kept, miss = [], {k: 0 for k in NEEDED}
            for s in smp:
                x = dict(prof_days.get(s["date"]) or {})
                sf = sun_features(sun_rows.get(s["date"]))
                if sf is not None:
                    x["sun"] = sf
                bad = [k for k in NEEDED if k not in x]
                for k in bad:
                    miss[k] += 1
                if not bad:
                    s["f"]["x"] = x
                    kept.append(s)
            if lead == 1 and tg == "tmax":
                sn = [s["f"]["x"]["_snow_max"] for s in kept]
                print(f"dni s snegom > 1 cm v vzorcu: {sum(1 for v in sn if v and v > 0.01)} od {len(sn)}")
                print(f"vzorci: {len(smp)} → {len(kept)} z vsemi vhodi; manjka po skupini: {miss}\n")
            kw = dict(use_bias=(tg == "tmin"), use_cond=(tg == "tmin"), use_multi=(tg == "tmax"))
            res = {}
            for name, groups in CANDIDATES.items():
                if only and name not in only:
                    continue
                t.temp_vector = e3.make_vec(build_extra(groups) if groups else None)
                try:
                    res[name] = e3.walk(kept, tg, since, **kw)
                finally:
                    t.temp_vector = base_t
            b = {r[0]: r for r in res["base"]}
            for name, r in res.items():
                e = {x[0]: x for x in r}
                days = sorted(set(b) & set(e))
                if not days:
                    continue
                eb = np.array([abs(b[d][1] - b[d][2]) for d in days])
                ec = np.array([abs(e[d][1] - e[d][2]) for d in days])
                mean, (lo, hi) = e3.boot(eb - ec)
                wi = np.array([int(d[5:7]) in WINTER for d in days])
                wtxt = f"zima n={int(wi.sum()):3d} diff={(eb - ec)[wi].mean():+.3f}" if wi.sum() >= 7 else "zima n<7"
                flag = "" if name == "base" else ("REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum")
                tag = "" if name in ("base", "sun") else " [zg. meja]"
                print(f"{tg} D+{lead} {name:8s} n={len(days)} MAE={ec.mean():.3f} "
                      f"(om {np.mean([abs(b[d][3] - b[d][2]) for d in days]):.3f}) diff={mean:+.3f} "
                      f"CI[{lo:+.3f},{hi:+.3f}] {flag:5s} | {wtxt}{tag}", flush=True)
            print()


if __name__ == "__main__":
    main()
