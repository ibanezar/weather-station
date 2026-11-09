#!/usr/bin/env python3
"""
tools/sneg_nizine_data.py -- prenos in izračun podatkov za članek »Sneg v nižinah od četrtka naprej« (9. 11. 2026).

Namenjen je samo temu članku (tools/generate_sneg_nizine_post.py). Prenese:
  - determinične modele za Rečico (ECMWF IFS, AIFS, ICON-EU, GFS, ARPEGE, UKMO, GEM) -- Open-Meteo,
  - ansamble ECMWF ENS (51 članov), ICON-EPS (40), GEFS (31), GEM (21) -- Open-Meteo ensemble API,
za Rečico na petih višinah in za 19 krajev po Sloveniji, ter izračuna, kar potrebuje stran. Posnetek zapiše v
data/sneg-nizine-1109.json (commitan, da je članek ponovljiv brez omrežja).

Meja dež/sneg je NAŠA poenostavitev (glej PRAG_*): ansambli v Open-Meteo nimajo temperature mokrega termometra,
model ne pozna temperature tal, zato »sneži« ni isto kot »obleži«. Članek to pove.
Notranjih meritev postaje skript ne uporablja (postaje sploh ne bere).

Usage:
    python3 tools/sneg_nizine_data.py          # prenese in zapiše data/sneg-nizine-1109.json
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sneg-nizine-1109.json")
UA = "meteorec.si article generator (+https://meteorec.si)"
LAT, LON = 46.325779, 14.921137          # postaja IREICA1 (isti kot generate_seo_pages.LAT/LON)
START = datetime.datetime(2026, 11, 12, 0)   # četrtek 0.00 po lokalnem času
N_HOURS = 5 * 24                             # do vključno ponedeljka 16. 11. 23.00
ELEVS = [366, 500, 700, 900, 1200]

# meja dež/sneg po temperaturi zraka na višini kraja (naša poenostavitev)
PRAG_SNEG = 1.5      # padavina pri T <= 1,5 °C šteje za »sneži« (delež snega >= 0,5)
PRAG_MRAZ = 0.5      # pri T <= 0,5 °C je ves padavinski del sneg
PRAG_DEZ = 2.5       # pri T >= 2,5 °C je ves dež
FRONT_T = 3.0        # ohladitev »prispe«, ko T zraka pade na 3 °C ali manj
PADAVINA_MIN = 0.1   # mm na uro, pod tem je ura suha
CM_NA_MM = 1.0       # 10:1 (isto kot SNOW_RATIO_CM_PER_MM v winter_engine.py)

DET_MODELS = [
    ("ecmwf_ifs025", "ECMWF IFS"), ("ecmwf_aifs025_single", "ECMWF AIFS"), ("icon_eu", "ICON-EU"),
    ("gfs_seamless", "GFS"), ("arpege_europe", "ARPEGE"), ("ukmo_seamless", "UKMO"), ("gem_seamless", "GEM"),
]
ENS = [("ecmwf_ifs025", "ECMWF ENS"), ("icon_seamless", "ICON-EPS"), ("gfs025", "GEFS"), ("gem_global", "GEM ENS")]

# kraji po Sloveniji: (ime, kratko ime, lat, lon, višina m). Višine so približne višine središča kraja.
TOWNS = [
    ("Maribor", 46.554, 15.646, 270), ("Ptuj", 46.420, 15.870, 232), ("Murska Sobota", 46.662, 16.166, 188),
    ("Slovenj Gradec", 46.510, 15.081, 410), ("Celje", 46.230, 15.267, 241), ("Velenje", 46.359, 15.111, 390),
    ("Rečica ob Savinji", 46.326, 14.921, 366), ("Gornji Grad", 46.296, 14.808, 431), ("Solčava", 46.420, 14.692, 644),
    ("Kranj", 46.239, 14.356, 385), ("Bled", 46.369, 14.114, 475), ("Kamnik", 46.222, 14.612, 382),
    ("Ljubljana", 46.051, 14.506, 295), ("Novo mesto", 45.803, 15.168, 190), ("Krško", 45.959, 15.492, 155),
    ("Kočevje", 45.642, 14.858, 460), ("Postojna", 45.775, 14.214, 533), ("Nova Gorica", 45.956, 13.648, 93),
    ("Koper", 45.548, 13.730, 5), ("Bovec", 46.337, 13.553, 435),
]


def _get(url, params, tries=4):
    q = urllib.parse.urlencode(params, safe=",")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url + "?" + q, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def hours():
    return [(START + datetime.timedelta(hours=i)).strftime("%Y-%m-%dT%H:00") for i in range(N_HOURS)]


def _slice(h, key, idx):
    arr = h.get(key)
    return [None if arr is None or arr[i] is None else arr[i] for i in idx]


def _idx(times):
    want = hours()
    pos = {t: i for i, t in enumerate(times)}
    return [pos.get(t) for t in want]


def _cols(h, base, idx):
    """Vsi stolpci spremenljivke (kontrola + člani) za izbrane ure; vrne seznam serij."""
    keys = [k for k in h if k == base or k.startswith(base + "_member")]
    out = []
    for k in sorted(keys):
        arr = h[k]
        out.append([None if (i is None or arr[i] is None) else arr[i] for i in idx])
    return out


def frac_snow(t):
    """Delež padavine, ki je sneg, pri temperaturi zraka t (°C). Linearno od 0,5 do 2,5 °C."""
    if t is None:
        return None
    if t <= PRAG_MRAZ:
        return 1.0
    if t >= PRAG_DEZ:
        return 0.0
    return (PRAG_DEZ - t) / (PRAG_DEZ - PRAG_MRAZ)


def fetch():
    out = {"fetched_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "start": START.isoformat(timespec="minutes"), "n_hours": N_HOURS, "elevs": ELEVS}
    base = {"timezone": "Europe/Ljubljana", "forecast_days": 8}

    # 1) determinični modeli, Rečica, vse višine
    det = {}
    for mid, label in DET_MODELS:
        lats = ",".join([str(LAT)] * len(ELEVS))
        lons = ",".join([str(LON)] * len(ELEVS))
        try:
            r = _get("https://api.open-meteo.com/v1/forecast", dict(
                base, latitude=lats, longitude=lons, elevation=",".join(map(str, ELEVS)), models=mid,
                hourly="temperature_2m,precipitation,temperature_850hPa"))
        except Exception as e:  # noqa: BLE001
            print("  ⚠ det", mid, e)
            continue
        r = r if isinstance(r, list) else [r]
        per = {}
        for el, loc in zip(ELEVS, r):
            h = loc["hourly"]
            idx = _idx(h["time"])
            per[str(el)] = {"t": _slice(h, "temperature_2m", idx), "p": _slice(h, "precipitation", idx),
                            "t850": _slice(h, "temperature_850hPa", idx)}
        for el_, v_ in per.items():
            v_["flags"] = hour_flags(v_["t"], v_["p"])
        det[mid] = {"label": label, "elev": per}
        print("  det", mid, "ok")
    out["det"] = det

    # 2) ansambli, Rečica, vse višine: shranimo T in padavine po članih (za izračun), v posnetek pa gredo samo izpeljave
    ens_raw = {}
    for mid, label in ENS:
        lats = ",".join([str(LAT)] * len(ELEVS))
        lons = ",".join([str(LON)] * len(ELEVS))
        r = _get("https://ensemble-api.open-meteo.com/v1/ensemble", dict(
            base, latitude=lats, longitude=lons, elevation=",".join(map(str, ELEVS)), models=mid,
            hourly="temperature_2m,precipitation"))
        r = r if isinstance(r, list) else [r]
        per = {}
        for el, loc in zip(ELEVS, r):
            h = loc["hourly"]
            idx = _idx(h["time"])
            per[el] = {"t": _cols(h, "temperature_2m", idx), "p": _cols(h, "precipitation", idx)}
        ens_raw[mid] = {"label": label, "per": per}
        print("  ens", mid, len(per[ELEVS[0]]["t"]), "članov")
    out["_ens_raw"] = ens_raw

    # 3) ansambli za kraje
    towns_raw = {}
    for mid, label in ENS:
        lats = ",".join(str(t[1]) for t in TOWNS)
        lons = ",".join(str(t[2]) for t in TOWNS)
        r = _get("https://ensemble-api.open-meteo.com/v1/ensemble", dict(
            base, latitude=lats, longitude=lons, elevation=",".join(str(t[3]) for t in TOWNS), models=mid,
            hourly="temperature_2m,precipitation"))
        r = r if isinstance(r, list) else [r]
        per = {}
        for t, loc in zip(TOWNS, r):
            h = loc["hourly"]
            idx = _idx(h["time"])
            per[t[0]] = {"t": _cols(h, "temperature_2m", idx), "p": _cols(h, "precipitation", idx)}
        towns_raw[mid] = per
        print("  kraji", mid, "ok")
    out["_towns_raw"] = towns_raw
    return out


# ───────────────────────── izračuni ─────────────────────────

def member_stats(ts, ps, lo, hi):
    """Za enega člana v oknu ur [lo, hi): (ure s snegom ali dežjem s snegom, cm snega, mm padavin, najnižja T)."""
    snow_h = 0
    cm = 0.0
    mm = 0.0
    tmin = None
    for i in range(lo, hi):
        t, p = ts[i], ps[i]
        if t is None or p is None:
            continue
        mm += p
        tmin = t if tmin is None else min(tmin, t)
        if p >= PADAVINA_MIN:
            f = frac_snow(t)
            cm += p * f * CM_NA_MM
            if f > 0:
                snow_h += 1
    return snow_h, cm, mm, tmin


def hour_flags(ts, ps):
    """Po urah: 1 = sneži, 2 = dež s snegom (mešano), 3 = dež, 0 = suho, None = ni podatka."""
    out = []
    for t, p in zip(ts, ps):
        if t is None or p is None:
            out.append(None)
        elif p < PADAVINA_MIN:
            out.append(0)
        else:
            f = frac_snow(t)
            out.append(1 if f >= 0.5 else (2 if f > 0 else 3))
    return out


def pct(n, d):
    return round(100 * n / d) if d else None


def q(sorted_vals, p):
    """Kvantil iz že urejenega seznama (najbližji rang)."""
    n = len(sorted_vals)
    return sorted_vals[min(n - 1, max(0, int(n * p)))]


def win_summary(stats):
    """stats: seznam (ure_snega, cm, mm, tmin) po članih -> povzetek okna."""
    stats = [x for x in stats if x[2] is not None]
    n = len(stats)
    cms = sorted(x[1] for x in stats)
    mms = sorted(x[2] for x in stats)
    return {"n": n, "any": pct(sum(1 for x in stats if x[0] >= 1), n),
            "cm1": pct(sum(1 for x in stats if x[1] >= 1), n),
            "cm5": pct(sum(1 for x in stats if x[1] >= 5), n),
            "med": round(q(cms, .5), 1), "p90": round(q(cms, .9), 1),
            "mm10": round(q(mms, .1)), "mm50": round(q(mms, .5)), "mm90": round(q(mms, .9)),
            "frost": pct(sum(1 for x in stats if x[3] is not None and x[3] <= 0), n),
            "tmin10": round(q(sorted(x[3] for x in stats if x[3] is not None), .1), 1),
            "tmin50": round(q(sorted(x[3] for x in stats if x[3] is not None), .5), 1)}


def window_idx(h0):
    """Okna v urah od četrtka 0.00. Ključ -> (od, do) z izključnim koncem."""
    return {
        "thu": (0, 24), "thufri": (0, 48), "fri": (24, 48), "night": (24 + 18, 48 + 8),  # petek 18.00 do sobota 8.00
        "sat": (48, 72), "sun": (72, 96), "all": (0, 120),
    }


def derive(raw):
    """Iz surovih ansamblov izračuna, kar rabi stran. Vrne slovar brez surovih serij."""
    ens_raw, towns_raw = raw["_ens_raw"], raw["_towns_raw"]
    W = window_idx(0)
    res = {"systems": {}, "pooled": {}, "hourly": {}, "front": {}, "towns": {}}

    sys_ids = [m for m, _ in ENS]
    # a) po višinah in oknih: delež članov z ≥ 1 uro snega, z ≥ 1 cm, z ≥ 5 cm; mediana in 90. percentil cm
    for el in ELEVS:
        res["systems"][str(el)] = {}
        pooled_members = {k: [] for k in W}
        for mid in sys_ids:
            per = ens_raw[mid]["per"][el]
            ts_all, ps_all = per["t"], per["p"]
            r = {}
            for wk, (lo, hi) in W.items():
                stats = [member_stats(ts, ps, lo, hi) for ts, ps in zip(ts_all, ps_all)]
                r[wk] = win_summary(stats)
                pooled_members[wk] += stats
            res["systems"][str(el)][mid] = r
        pooled = {wk: win_summary(pooled_members[wk]) for wk in W}
        res["pooled"][str(el)] = pooled

    # b) po urah in višinah: delež članov, pri katerih v tej uri sneži / mešano / dež / suho (po sistemih)
    for el in ELEVS:
        res["hourly"][str(el)] = {}
        for mid in sys_ids + ["all"]:
            if mid == "all":
                per = {"t": [x for m in sys_ids for x in ens_raw[m]["per"][el]["t"]],
                       "p": [x for m in sys_ids for x in ens_raw[m]["per"][el]["p"]]}
            else:
                per = ens_raw[mid]["per"][el]
            flags = [hour_flags(ts, ps) for ts, ps in zip(per["t"], per["p"])]
            rows = {"snow": [], "mix": [], "rain": [], "t50": [], "t10": [], "t90": [], "p50": [], "p90": []}
            for h in range(raw["n_hours"]):
                col = [f[h] for f in flags if f[h] is not None]
                n = len(col)
                for key, code in (("snow", 1), ("mix", 2), ("rain", 3)):
                    rows[key].append(pct(sum(1 for c in col if c == code), n))
                tv = sorted(ts[h] for ts in per["t"] if ts[h] is not None)
                pv = sorted(ps[h] for ps in per["p"] if ps[h] is not None)
                if tv:
                    rows["t10"].append(round(tv[int(len(tv) * 0.1)], 1))
                    rows["t50"].append(round(tv[len(tv) // 2], 1))
                    rows["t90"].append(round(tv[min(len(tv) - 1, int(len(tv) * 0.9))], 1))
                else:
                    rows["t10"].append(None); rows["t50"].append(None); rows["t90"].append(None)
                if pv:
                    rows["p50"].append(round(pv[len(pv) // 2], 2))
                    rows["p90"].append(round(pv[min(len(pv) - 1, int(len(pv) * 0.9))], 2))
                else:
                    rows["p50"].append(None); rows["p90"].append(None)
            res["hourly"][str(el)][mid] = rows

    # c) čas prihoda ohladitve (T zraka na 366 m pade na ≤ 3 °C po petkovem jutru) in padavine v 48 urah za tem
    for mid in sys_ids:
        per = ens_raw[mid]["per"][ELEVS[0]]
        arr, behind, cms = [], [], []
        for ts, ps in zip(per["t"], per["p"]):
            cms.append(round(member_stats(ts, ps, 0, 120)[1], 1))
            k = next((h for h in range(24, 120) if ts[h] is not None and ts[h] <= FRONT_T), None)
            arr.append(k)
            behind.append(None if k is None else round(sum(p for p in ps[k:k + 48] if p is not None), 1))
        ok = sorted(a for a in arr if a is not None)
        res["front"][mid] = {"n": len(arr), "arrive_h": arr, "behind_mm": behind, "cm": cms,
                              "median_arrive_h": ok[len(ok) // 2] if ok else None}

    # d) kraji: delež članov po urah (po sistemih), snega in mešano
    for t in TOWNS:
        name = t[0]
        res["towns"][name] = {"elev": t[3], "lat": t[1], "lon": t[2], "sys": {}}
        for mid in sys_ids:
            per = towns_raw[mid][name]
            flags = [hour_flags(ts, ps) for ts, ps in zip(per["t"], per["p"])]
            snow, mix = [], []
            for h in range(raw["n_hours"]):
                col = [f[h] for f in flags if f[h] is not None]
                n = len(col)
                snow.append(pct(sum(1 for c in col if c == 1), n))
                mix.append(pct(sum(1 for c in col if c == 2), n))
            res["towns"][name]["sys"][mid] = {"snow": snow, "mix": mix, "n": len(flags)}
        # skupen delež (vsi člani)
        pooled_snow, pooled_mix = [], []
        for h in range(raw["n_hours"]):
            tot = snow_n = mix_n = 0
            for mid in sys_ids:
                per = towns_raw[mid][name]
                for ts, ps in zip(per["t"], per["p"]):
                    f = hour_flags([ts[h]], [ps[h]])[0]
                    if f is None:
                        continue
                    tot += 1
                    snow_n += f == 1
                    mix_n += f == 2
            pooled_snow.append(pct(snow_n, tot))
            pooled_mix.append(pct(mix_n, tot))
        cum1 = []
        members = [(ts, ps) for mid in sys_ids for ts, ps in zip(towns_raw[mid][name]["t"], towns_raw[mid][name]["p"])]
        acc = [0.0] * len(members)
        for h in range(raw["n_hours"]):
            for j, (ts, ps) in enumerate(members):
                t_, p_ = ts[h], ps[h]
                if t_ is not None and p_ is not None and p_ >= PADAVINA_MIN:
                    acc[j] += p_ * frac_snow(t_) * CM_NA_MM
            cum1.append(pct(sum(1 for a_ in acc if a_ >= 1), len(acc)))
        res["towns"][name]["pooled"] = {"snow": pooled_snow, "mix": pooled_mix, "cum1": cum1}
        # skupaj cm in verjetnost ≥ 1 cm v oknu »noč na soboto + sobota dopoldne« (petek 18.00 – sobota 12.00) in vse
        for wk, (lo, hi) in (("night", W["night"]), ("all", W["all"])):
            st = []
            for mid in sys_ids:
                per = towns_raw[mid][name]
                st += [member_stats(ts, ps, lo, hi) for ts, ps in zip(per["t"], per["p"])]
            n = len(st)
            res["towns"][name]["pooled_" + wk] = {
                "any": pct(sum(1 for s in st if s[0] >= 1), n), "cm1": pct(sum(1 for s in st if s[1] >= 1), n),
                "cm5": pct(sum(1 for s in st if s[1] >= 5), n)}
    return res


def main():
    raw = fetch()
    res = derive(raw)
    raw.pop("_ens_raw")
    raw.pop("_towns_raw")
    raw.update(res)
    raw["thr"] = {"sneg": PRAG_SNEG, "mraz": PRAG_MRAZ, "dez": PRAG_DEZ, "padavina_min": PADAVINA_MIN, "cm_na_mm": CM_NA_MM}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, separators=(",", ":"))
    print("✓", os.path.relpath(OUT, ROOT), round(os.path.getsize(OUT) / 1024), "kB")


if __name__ == "__main__":
    sys.exit(main())
