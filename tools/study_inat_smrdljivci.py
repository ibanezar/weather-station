#!/usr/bin/env python3
"""
tools/study_inat_smrdljivci.py — smrdljivci (iNaturalist) × vreme postaje IREICA1.

ENKRATNA študija za članek »Smrdljivcev je čedalje več?« (11. 10. 2026), ne del cevovoda.
Zapiše SAMO agregate v data/inat-smrdljivci.json — posameznih opažanj ne hrani in ne objavlja
(licence so po opažanju različne; isto načelo kot tools/study_inat_lag.py).

Kaj izračuna
  1. Opažanja po letih za enako obdobje (1. 1. do dneva zaustavitve), da nepolno leto ni v
     slabšem položaju: marmorirana smrdljivka (Halyomorpha halys), vsi smrdljivci (Pentatomidae),
     vse žuželke (Insecta), vsa opažanja. Število opazovalcev iNaturalist v Sloveniji strmo raste,
     zato so merilo deleži, ne surova števila.
  2. Isto za jesensko okno 15. 9.–10. 10.
  3. Sezonski potek po mesecih (vsa leta): Halyomorpha proti ostalim smrdljivcem.
  4. Vreme: v oknu 1. 10.–5. 11. so opažanja na dan, ko je bila najvišja temperatura na postaji
     nad pragom, primerjana z ostalimi dnevi. Kontrola so OSTALI smrdljivci: tudi ti so ob toplih
     dneh pogosteje fotografirani, ker so ljudje takrat zunaj.
  5. Letni kazalniki postaje (vsota stopinjskih dni apr–sep, poletno povprečje) ob jesenskem oknu.

Usage:
    python3 tools/study_inat_smrdljivci.py [--cutoff MM-DD] [--out data/inat-smrdljivci.json]
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = "meteorec-bot/1.0 (+https://meteorec.si/o-postaji.html)"
API = "https://api.inaturalist.org/v1/observations"
PLACE_SLOVENIA = 8228
TAXA = {"halys": 81923, "penta": 47742, "insecta": 47158}
FIRST_YEAR = 2018
WEATHER_WINDOW = ((10, 1), (11, 5))
THRESHOLDS = (15, 18)          # °C, najvišja temperatura dneva
MIN_SEASON_DAYS = 175          # apr–sep: leto brez skoraj polne sezone se ne šteje


def get(url, tries=5):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            wait = 5 * (k + 1) * (3 if "429" in str(e) else 1)
            print(f"  ⚠ {str(e)[:60]} — čakam {wait} s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit(f"✗ ne uspe: {url[:100]}")


def count(**q):
    q = {"place_id": PLACE_SLOVENIA, "per_page": 0, **q}
    return get(API + "?" + "&".join(f"{k}={v}" for k, v in q.items()))["total_results"]


def observers(taxon_id, d1, d2):
    """Število RAZLIČNIH opazovalcev (samo število, ne kdo) — 15 opažanj enega človeka ni isto kot 15 ljudi."""
    ids, page = set(), 1
    while True:
        r = get(f"{API}?place_id={PLACE_SLOVENIA}&taxon_id={taxon_id}&d1={d1}&d2={d2}&per_page=200&page={page}"
                f"&fields=user.id")
        ids |= {o["user"]["id"] for o in r["results"] if o.get("user")}
        if page * 200 >= r["total_results"]:
            return len(ids)
        page += 1


def fetch_dates(taxon_id, last):
    """(datum, ime taksona) za raziskovalno kakovost in odprto lokacijo; v pomnilniku, ne na disku."""
    rows, page = [], 1
    while True:
        q = (f"place_id={PLACE_SLOVENIA}&taxon_id={taxon_id}&per_page=200&page={page}&order_by=observed_on"
             f"&order=asc&quality_grade=research&geoprivacy=open&d2={last}&fields=observed_on,taxon.name")
        r = get(API + "?" + q)
        for o in r["results"]:
            if o.get("observed_on"):
                rows.append((dt.date.fromisoformat(o["observed_on"]), o["taxon"]["name"]))
        if page * 200 >= r["total_results"]:
            return rows
        page += 1
        time.sleep(1)


def rate_ratio(a, n1, b, n0):
    """Razmerje stopenj (a/n1)/(b/n0) z 95 % intervalom (log, Poisson). Dnevna opažanja se kopičijo
    pri istem opazovalcu, zato je pravi interval širši od tega — v članku je tako tudi povedano."""
    if min(a, b, n1, n0) <= 0:
        return None
    rr = (a / n1) / (b / n0)
    se = math.sqrt(1 / a + 1 / b)
    return {"rr": rr, "lo": math.exp(math.log(rr) - 1.96 * se), "hi": math.exp(math.log(rr) + 1.96 * se)}


def spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else None


def main():
    ap = argparse.ArgumentParser()
    yesterday = dt.date.today() - dt.timedelta(days=1)
    ap.add_argument("--cutoff", default=yesterday.strftime("%m-%d"))
    ap.add_argument("--year", type=int, default=yesterday.year)
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "inat-smrdljivci.json"))
    a = ap.parse_args()
    cm, cd = map(int, a.cutoff.split("-"))
    last_year = a.year
    last = dt.date(last_year, cm, cd)

    out = {"generated": dt.date.today().isoformat(), "cutoff": a.cutoff, "last_year": last_year,
           "place": "Slovenija (iNaturalist place 8228)", "taxa": TAXA,
           "autumn_window": ["09-15", "10-10"]}

    # 1+2: enako obdobje po letih
    ytd, autumn = {}, {}
    for y in range(FIRST_YEAR, last_year + 1):
        d1, d2 = f"{y}-01-01", f"{y}-{a.cutoff}"
        ytd[y] = {k: count(taxon_id=t, d1=d1, d2=d2) for k, t in TAXA.items()}
        ytd[y]["vse"] = count(d1=d1, d2=d2)
        w1, w2 = f"{y}-09-15", f"{y}-10-10"
        autumn[y] = {k: count(taxon_id=t, d1=w1, d2=w2) for k, t in TAXA.items()}
        autumn[y]["halys_observers"] = observers(TAXA["halys"], w1, w2)
        print(y, ytd[y], autumn[y])
    out["ytd"], out["autumn"] = ytd, autumn

    # 3: sezonski potek (vsa leta, vse kakovosti)
    month = {}
    for k in ("halys", "penta"):
        h = get(f"{API}/histogram?place_id={PLACE_SLOVENIA}&taxon_id={TAXA[k]}&date_field=observed"
                f"&interval=month_of_year")["results"]["month_of_year"]
        month[k] = [h.get(str(m), 0) for m in range(1, 13)]
    month["ostali"] = [p - h for p, h in zip(month["penta"], month["halys"])]
    out["month"] = month

    # 4: vreme — opažanja na dan z meritvijo postaje
    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    rows = fetch_dates(TAXA["penta"], last.isoformat())     # vključuje Halyomorpha (podtakson)
    halys_c, other_c = {}, {}
    for d, name in rows:
        tgt = halys_c if name == "Halyomorpha halys" else other_c
        tgt[d] = tgt.get(d, 0) + 1
    (m1, d1_), (m2, d2_) = WEATHER_WINDOW
    weather = {"window": [f"{m1:02d}-{d1_:02d}", f"{m2:02d}-{d2_:02d}"], "n_obs_halys": 0,
               "n_obs_ostali": 0, "thr": {}}
    days = []
    d = dt.date(2019, 11, 7)
    while d <= last:
        v = hist.get(d.isoformat())
        if (m1, d1_) <= (d.month, d.day) <= (m2, d2_) and v and v.get("tempHigh") is not None:
            days.append((d, v["tempHigh"]))
        d += dt.timedelta(days=1)
    weather["n_days"] = len(days)
    for thr in THRESHOLDS:
        res = {}
        for label, cond in (("hladno", lambda t, thr=thr: t < thr), ("toplo", lambda t, thr=thr: t >= thr)):
            ds = [x for x, t in days if cond(t)]
            res[label] = {"dni": len(ds), "halys": sum(halys_c.get(x, 0) for x in ds),
                          "ostali": sum(other_c.get(x, 0) for x in ds)}
        for k in ("halys", "ostali"):
            res["rr_" + k] = rate_ratio(res["toplo"][k], res["toplo"]["dni"], res["hladno"][k], res["hladno"]["dni"])
        weather["thr"][str(thr)] = res
    weather["n_obs_halys"] = sum(halys_c.get(x, 0) for x, _ in days)
    weather["n_obs_ostali"] = sum(other_c.get(x, 0) for x, _ in days)
    out["weather"] = weather

    # 5: letni kazalniki postaje
    years = {}
    for y in range(2020, last_year + 1):
        season = [v for dd, v in hist.items() if f"{y}-04-01" <= dd <= f"{y}-09-30"]
        summer = [v for dd, v in hist.items() if f"{y}-06-01" <= dd <= f"{y}-08-31"]
        if len(season) < MIN_SEASON_DAYS or not summer:
            continue
        gdd = sum(max(0.0, (v["tempHigh"] + v["tempLow"]) / 2 - 10) for v in season)
        years[y] = {"gdd": round(gdd), "poletje": round(sum(v["tempAvg"] for v in summer) / len(summer), 1)}
        win = [v["tempHigh"] for dd, v in hist.items() if f"{y}-09-15" <= dd <= f"{y}-10-10"
               and v.get("tempHigh") is not None]
        if len(win) >= 20:
            years[y]["jesen_tmax"] = round(sum(win) / len(win), 1)
    out["station_years"] = years
    ys = [y for y in years if y in autumn]
    per1000 = [1000 * autumn[y]["halys"] / max(1, autumn[y]["insecta"]) for y in ys]
    out["spearman_gdd_halys_autumn"] = {"n": len(ys), "rho": spearman([years[y]["gdd"] for y in ys], per1000)}

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("✓", a.out)
    print(json.dumps(weather, ensure_ascii=False, indent=1))
    print(out["station_years"], out["spearman_gdd_halys_autumn"])


if __name__ == "__main__":
    main()
