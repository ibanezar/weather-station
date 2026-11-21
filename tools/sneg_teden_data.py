#!/usr/bin/env python3
"""
tools/sneg_teden_data.py -- prenos in izračun podatkov za članek »Sneg prihodnji teden« (21. 11. 2026).

Namenjen je samo temu članku (tools/generate_sneg_teden_post.py). Prenese:
  - determinične modele za Rečico (ECMWF IFS, AIFS, ICON-EU, GFS, ARPEGE, UKMO, GEM) -- Open-Meteo,
  - ansamble ECMWF ENS (51 članov), ICON-EPS (40), GEFS (31), GEM (21) -- Open-Meteo ensemble API,
za Rečico na štirih višinah, in zapiše izpeljave (brez surovih članov) v data/sneg-teden-1121.json.

Meja dež/sneg je NAŠA poenostavitev (PRAG_*), kot v članku z 9. 11. (tools/sneg_nizine_data.py):
ansambli v Open-Meteo nimajo temperature mokrega termometra, model ne pozna temperature tal,
zato »sneži« ni isto kot »obleži«. Notranjih meritev postaje skript ne bere (postaje sploh ne bere).

Usage:
    python3 tools/sneg_teden_data.py
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sneg_nizine_data import (frac_snow, hour_flags, pct, q, PRAG_MRAZ, PRAG_DEZ, PADAVINA_MIN, CM_NA_MM,  # noqa: E402,F401
                              DET_MODELS, ENS)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sneg-teden-1121.json")
UA = "meteorec.si article generator (+https://meteorec.si)"
LAT, LON = 46.325779, 14.921137          # postaja IREICA1
START = datetime.datetime(2026, 11, 22, 0)    # nedelja 0.00 po lokalnem času (da je vidno, kaj je pred tednom)
N_HOURS = 8 * 24                              # do vključno nedelje 29. 11. 23.00
ELEVS = [366, 700, 1000, 1400]
DAYS = [(START + datetime.timedelta(days=i)).date().isoformat() for i in range(8)]   # 22.-29. 11.


def _get(url, params, tries=4):
    q_ = urllib.parse.urlencode(params, safe=",")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url + "?" + q_, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def hours():
    return [(START + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(N_HOURS)]


def _idx(times):
    pos = {t: i for i, t in enumerate(times)}
    return [pos.get(t) for t in hours()]


def _cols(h, base, idx):
    keys = sorted(k for k in h if k == base or k.startswith(base + "_member"))
    return [[None if (i is None or h[k][i] is None) else h[k][i] for i in idx] for k in keys]


def _series(h, key, idx):
    arr = h.get(key)
    return [None if (arr is None or i is None or arr[i] is None) else arr[i] for i in idx]


def day_stats(ts, ps, lo, hi):
    """(ure z napovedanim snegom, cm snega, mm padavin, najnižja T, najvišja T) za člana v urah [lo, hi)."""
    snow_h, cm, mm, tmin, tmax = 0, 0.0, 0.0, None, None
    for i in range(lo, hi):
        t, p = ts[i], ps[i]
        if t is None or p is None:
            continue
        mm += p
        tmin = t if tmin is None else min(tmin, t)
        tmax = t if tmax is None else max(tmax, t)
        if p >= PADAVINA_MIN:
            f = frac_snow(t)
            cm += p * f * CM_NA_MM
            if f > 0:
                snow_h += 1
    return snow_h, cm, mm, tmin, tmax


def summarize(stats):
    stats = [s for s in stats if s[2] is not None and s[3] is not None]
    n = len(stats)
    if n == 0:
        return None      # sistem za ta dan nima podatka
    cms = sorted(s[1] for s in stats)
    mms = sorted(s[2] for s in stats)
    tm = sorted(s[3] for s in stats)
    tx = sorted(s[4] for s in stats)
    return {"n": n, "any": pct(sum(1 for s in stats if s[0] >= 1), n), "cm1": pct(sum(1 for s in stats if s[1] >= 1), n),
            "cm3": pct(sum(1 for s in stats if s[1] >= 3), n), "cm5": pct(sum(1 for s in stats if s[1] >= 5), n),
            "cm10": pct(sum(1 for s in stats if s[1] >= 10), n), "tmax50": round(q(tx, .5), 1),
            "med": round(q(cms, .5), 1), "p10": round(q(cms, .1), 1), "p90": round(q(cms, .9), 1),
            "mm50": round(q(mms, .5), 1), "tmin50": round(q(tm, .5), 1)}


def fetch():
    out = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "start": START.isoformat(timespec="minutes"), "n_hours": N_HOURS, "elevs": ELEVS, "days": DAYS}
    base = {"timezone": "Europe/Ljubljana", "forecast_days": 9}
    lats = ",".join([str(LAT)] * len(ELEVS))
    lons = ",".join([str(LON)] * len(ELEVS))
    els = ",".join(map(str, ELEVS))

    # 1) ansambli
    raw = {}
    for mid, label in ENS:
        r = _get("https://ensemble-api.open-meteo.com/v1/ensemble", dict(
            base, latitude=lats, longitude=lons, elevation=els, models=mid, hourly="temperature_2m,precipitation"))
        r = r if isinstance(r, list) else [r]
        per = {}
        for el, loc in zip(ELEVS, r):
            h = loc["hourly"]
            idx = _idx(h["time"])
            per[el] = {"t": _cols(h, "temperature_2m", idx), "p": _cols(h, "precipitation", idx)}
        raw[mid] = {"label": label, "per": per}
        print("  ens", mid, len(per[ELEVS[0]]["t"]), "članov")

    res = {"days": {}, "systems": {}, "hourly": {}, "windows": {}, "first": {}}
    for el in ELEVS:
        res["days"][str(el)] = {}
        res["systems"][str(el)] = {}
        pooled_by_day = {d: [] for d in DAYS}
        for mid, label in ENS:
            per = raw[mid]["per"][el]
            res["systems"][str(el)][mid] = {"label": label, "days": {}}
            for k, d in enumerate(DAYS):
                st = [day_stats(ts, ps, 24 * k, 24 * k + 24) for ts, ps in zip(per["t"], per["p"])]
                res["systems"][str(el)][mid]["days"][d] = summarize(st)
                pooled_by_day[d] += st
        for d in DAYS:
            res["days"][str(el)][d] = summarize(pooled_by_day[d])
            for mid, _ in ENS:
                if res["systems"][str(el)][mid]["days"][d] is None:
                    print("  ⚠ brez podatka:", el, mid, d)
        # po urah: delež članov, pri katerih v tej uri sneži / dež s snegom / dež; mediana in razpon temperature
        allt = [x for mid, _ in ENS for x in raw[mid]["per"][el]["t"]]
        allp = [x for mid, _ in ENS for x in raw[mid]["per"][el]["p"]]
        flags = [hour_flags(ts, ps) for ts, ps in zip(allt, allp)]
        rows = {"snow": [], "mix": [], "rain": [], "t10": [], "t50": [], "t90": []}
        for h in range(N_HOURS):
            col = [f[h] for f in flags if f[h] is not None]
            n = len(col)
            for key, code in (("snow", 1), ("mix", 2), ("rain", 3)):
                rows[key].append(pct(sum(1 for c in col if c == code), n))
            tv = sorted(ts[h] for ts in allt if ts[h] is not None)
            rows["t10"].append(round(tv[int(len(tv) * .1)], 1))
            rows["t50"].append(round(tv[len(tv) // 2], 1))
            rows["t90"].append(round(tv[min(len(tv) - 1, int(len(tv) * .9))], 1))
        res["hourly"][str(el)] = rows
        # skupna okna (ure od nedelje 0.00): sre-čet 25.-26., sre-pet 25.-27., pon-sob 23.-28. (ICON-EPS sega do sobote, zato ne do nedelje)
        res["windows"][str(el)] = {}
        for wk, (lo, hi) in {"sre_cet": (72, 120), "sre_pet": (72, 144), "pon_sob": (24, 168)}.items():
            st = [day_stats(ts, ps, lo, hi) for ts, ps in zip(allt, allp)]
            res["windows"][str(el)][wk] = summarize(st)
    # prvi sneg v Rečici (366 m) po torkovem opoldnevu: ura prve padavine s snegom (delež snega >= 0,5) pri članih, ki jo imajo do četrtka 12.00
    firsts = []
    allt = [x for mid, _ in ENS for x in raw[mid]["per"][366]["t"]]
    allp = [x for mid, _ in ENS for x in raw[mid]["per"][366]["p"]]
    for ts, ps in zip(allt, allp):
        k = next((h for h in range(60, 132) if ts[h] is not None and ps[h] is not None and ps[h] >= PADAVINA_MIN and frac_snow(ts[h]) >= .5), None)
        firsts.append(k)
    got = sorted(k for k in firsts if k is not None)
    res["first"] = {"n": len(firsts), "with_snow": len(got), "h10": got[int(len(got) * .1)], "h50": got[len(got) // 2], "h90": got[min(len(got) - 1, int(len(got) * .9))]}
    out["ens"] = res
    out["members"] = {mid: len(raw[mid]["per"][ELEVS[0]]["t"]) for mid, _ in ENS}

    # 2) determinični modeli (Rečica, 366 in 700 m)
    det = {}
    dels = [366, 700]
    for mid, label in DET_MODELS + [("best_match", "Open-Meteo (osnovni model strani)")]:
        try:
            r = _get("https://api.open-meteo.com/v1/forecast", dict(
                base, latitude=",".join([str(LAT)] * 2), longitude=",".join([str(LON)] * 2), elevation=",".join(map(str, dels)),
                models=mid, hourly="temperature_2m,precipitation"))
        except Exception as e:  # noqa: BLE001
            print("  ⚠ det", mid, e)
            continue
        r = r if isinstance(r, list) else [r]
        per = {}
        for el, loc in zip(dels, r):
            h = loc["hourly"]
            idx = _idx(h["time"])
            t, p = _series(h, "temperature_2m", idx), _series(h, "precipitation", idx)
            days = {}
            for k, d in enumerate(DAYS):
                sl = slice(24 * k, 24 * k + 24)
                if any(x is None for x in t[sl]) or any(x is None for x in p[sl]):
                    days[d] = None      # model za ta dan nima podatka (npr. ICON-EU sega manj daleč)
                    continue
                s = day_stats(t, p, 24 * k, 24 * k + 24)
                days[d] = {"cm": round(s[1], 1), "mm": round(s[2], 1), "tmin": round(s[3], 1), "tmax": round(s[4], 1)}
            per[str(el)] = days
        det[mid] = {"label": label, "elev": per}
        print("  det", mid, "ok")
    out["det"] = det
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("✓ posnetek:", os.path.relpath(OUT, ROOT), round(os.path.getsize(OUT) / 1024), "kB")


if __name__ == "__main__":
    fetch()
