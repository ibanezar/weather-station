#!/usr/bin/env python3
"""
tools/study_zime.py — »So zime še kar so bile?« (12. 10. 2026).

ENKRATNA študija, ne del cevovoda. Zapiše SAMO agregate po zimah v data/zime.json.

Viri:
  * NOAA GHCN-Daily (ECA&D/ARSO podatki): Ljubljana Bežigrad (SIM00014015, 299 m, od 1901),
    Šmartno pri Slovenj Gradcu (SIE00115136, 444 m, od 1961) — dnevni TMAX/TMIN; za Ljubljano
    še SNWD (višina snežne odeje, cm).
  * ARSO Črnivec (848 m, od 2021): snežna odeja iz data/crnivec-arso.json (predpomnilnik crnivec.si).
  * lastna postaja IREICA1 (history.json, od novembra 2019). Notranjih meritev ne bere.

Zima = december–februar (zima 2012/13 ima oznako 2012); zima velja, če ima ≥ 95 % dni obeh
temperatur. Snežna odeja: GHCN za Ljubljano hrani SAMO dneve z odejo (ničle ni), zato je dan
brez zapisa v zimi, ki ima kje v sezoni (1. 11.–31. 3.) vsaj en zapis, dan brez odeje; zimi
brez katerega koli zapisa (2004/05) ne štejemo (ni podatka ali odeje ni bilo — ne vemo).
Preverjeno 12. 10. 2026: odeja se v zapisih skoraj vedno konča pri 1–3 cm (postopno kopnenje), luknje
1–2 dni sredi odeje ≥ 5 cm so štiri v 30 letih — izpuščene so ničle, ne podatki. Zapisi se začnejo
1. 1. 1996 (že 36 cm), zato je zima 1995/96 okrnjena in gre samo v `snow_ljubljana_partial`.

Usage: python3 tools/study_zime.py [--cache DIR]
"""
import datetime
import json
import os
import statistics as st
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "zime.json")
BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/"
STATIONS = {"ljubljana": ("SIM00014015", "Ljubljana Bežigrad", 299),
            "smartno": ("SIE00115136", "Šmartno pri Slovenj Gradcu", 444)}


def fetch(sid, cache):
    path = os.path.join(cache, sid + ".dly")
    if not os.path.exists(path):
        req = urllib.request.Request(BASE + sid + ".dly", headers={"User-Agent": "meteorec-research"})
        with urllib.request.urlopen(req, timeout=120) as r:
            open(path, "wb").write(r.read())
    return path


def read(path, el, qc=False):
    """Dnevne vrednosti elementa. qc=True izpusti vrednosti z zastavico kakovosti (Q, npr. O = osamelec, G = vrzel) —
    samo za snežno odejo (poletni zapisi 1–5 cm, 128 cm aprila). Pri temperaturah ne: GHCN kot osamelce označi tudi
    resnične ekstreme (februar 1929), brez njih bi zima 1928/29 izpadla."""
    out = {}
    for l in open(path):
        if l[17:21] != el:
            continue
        y, m = int(l[11:15]), int(l[15:17])
        for i in range(31):
            v = int(l[21 + 8 * i:26 + 8 * i])
            if v == -9999 or (qc and l[27 + 8 * i] != " "):
                continue
            try:
                out[datetime.date(y, m, i + 1).isoformat()] = v / 10      # °C ali cm (GHCN: desetinke °C, mm)
            except ValueError:
                pass
    return out


def days(a, b):
    d = a
    while d <= b:
        yield d.isoformat()
        d += datetime.timedelta(1)


def djf(w):
    return list(days(datetime.date(w, 12, 1), datetime.date(w + 1, 3, 1) - datetime.timedelta(1)))


def winter_stats(tx, tn, w):
    ds = djf(w)
    ok = [x for x in ds if x in tx and x in tn]
    if len(ok) < 0.95 * len(ds):
        return None
    return {"tmean": round(st.mean((tx[x] + tn[x]) / 2 for x in ok), 2),
            "frost": sum(tn[x] < 0 for x in ok), "ice": sum(tx[x] < 0 for x in ok),
            "hard": sum(tn[x] <= -10 for x in ok), "mild": sum(tx[x] >= 5 for x in ok), "n": len(ok),
            "months": {m: round(st.mean((tx[x] + tn[x]) / 2 for x in ok if x[5:7] == m), 2) for m in ("12", "01", "02")}}


def snow_stats(sn, w):
    season = list(days(datetime.date(w, 11, 1), datetime.date(w + 1, 3, 31)))
    pres = [d for d in season if d in sn]
    if not pres:
        return None
    run = best = 0
    prev = None
    for d in pres:
        dd = datetime.date.fromisoformat(d)
        run = run + 1 if prev and (dd - prev).days == 1 else 1
        best, prev = max(best, run), dd
    return {"days": len(pres), "longest": best, "max_cm": round(max(sn[d] for d in pres), 1)}


def own_station():
    h = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    tx = {d: v["tempHigh"] for d, v in h.items() if v.get("tempHigh") is not None}
    tn = {d: v["tempLow"] for d, v in h.items() if v.get("tempLow") is not None}
    out = {}
    for w in range(2019, 2026):
        s = winter_stats(tx, tn, w)
        if s:
            out[w] = s
    return out


def crnivec():
    """ARSO Črnivec (id 3391, 848 m, od 2021) iz predpomnilnika crnivec.si (data/crnivec-arso.json):
    dnevi s snežno odejo od 1. 11. do 31. 3. po sezonah; samo cele sezone."""
    c = json.load(open(os.path.join(ROOT, "data", "crnivec-arso.json"), encoding="utf-8"))
    out = {}
    for d, depth, new, _ in c["days"]:
        dt = datetime.date.fromisoformat(d)
        if not (dt.month >= 11 or dt.month <= 3):
            continue
        w = dt.year if dt.month >= 11 else dt.year - 1
        s = out.setdefault(w, {"n": 0, "days": 0, "longest": 0, "max_cm": 0, "new_cm": 0, "_run": 0})
        s["n"] += 1
        if depth:
            s["days"] += 1
            s["_run"] += 1
            s["longest"] = max(s["longest"], s["_run"])
            s["max_cm"] = max(s["max_cm"], depth)
        else:
            s["_run"] = 0
        s["new_cm"] += new or 0
    return {w: {k: v for k, v in s.items() if k != "_run"} for w, s in out.items() if s["n"] >= 150}


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else "/tmp"
    D = {"generated": datetime.date.today().isoformat(), "stations": {}, "snow_ljubljana": {}, "own": {}}
    for key, (sid, name, elev) in STATIONS.items():
        p = fetch(sid, cache)
        tx, tn = read(p, "TMAX"), read(p, "TMIN")
        w = {y: s for y in range(1900, 2026) if (s := winter_stats(tx, tn, y))}
        D["stations"][key] = {"id": sid, "name": name, "elev_m": elev, "winters": w}
        if key == "ljubljana":
            sn = read(p, "SNWD", qc=True)
            first = min(sn)                    # prvi zapis odeje (1996-01-01): zima, ki se začne prej, je okrnjena
            D["snow_ljubljana"] = {y: s for y in range(1990, 2026)
                                   if datetime.date(y, 11, 1).isoformat() >= first[:8] + "01" and (s := snow_stats(sn, y))}
            w0 = int(first[:4]) - 1
            part = snow_stats(sn, w0)
            D["snow_ljubljana_partial"] = {w0: part | {"from": first, "depth_first_cm": sn[first]}} if part else {}
    D["own"] = own_station()
    D["crnivec"] = crnivec()
    json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("zapisano", OUT)


if __name__ == "__main__":
    main()
