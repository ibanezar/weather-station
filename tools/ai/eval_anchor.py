#!/usr/bin/env python3
"""
Merjenje izzvenevanja popravka »meritev − model« v urah (2. 11. 2026).

  eval_anchor.py [--from 2026-07-13] [--lead 1]        (potrebuje omrežje: poganjaj na GitHubovem tekaču)

Zakaj: junaška krivulja na naslovnici (app.js, anchorHours) zasidra napoved ur na zadnjo meritev in
popravek linearno izzveni v ANCHOR_HOURS = 6 urah. Ta številka je po zgledu Črnivca in NI izmerjena.
Open-Meteo nima arhiva napovedi, izdanih »pred nekaj urami«, zato je najbližji pošten približek napoved
`previous_dayN` (izdana N dni prej), primerjana z urnimi meritvami IREICA1 (`data/hourly-observations.csv`).

Za vsako uro t0 in zamik k = 1..12: e(t) = model(t) − meritev(t). Ocenimo optimalno utež
w_k = cov(e(t0), e(t0+k)) / var(e(t0)) (najmanjši kvadrati skozi izhodišče) in MAE popravljene napovedi
model(t0+k) − w·e(t0) za w iz izbranih oblik: brez popravka, linearno izzvenevanje čez 3/6/9/12 h, optimalna
w_k. Izpis pove, katera oblika je najbližja izmerjeni in koliko MAE se pridobi.

Omejitve, ki jih izpis ponovi: (1) napaka napovedi izpred dneva ni isto kot napaka napovedi, izdane ob
t0, zato je to ocena PERSISTENCE napake, ne dokaz koristi; (2) ~110 dni urnih meritev; (3) en kraj.
Če se kaj spremeni, ne spreminjaj ANCHOR_HOURS brez ponovitve.
"""
import argparse, csv, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))

SHAPES = {"brez": None, "lin3": 3, "lin6": 6, "lin9": 9, "lin12": 12}
KS = range(1, 13)


def load_obs(since):
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "hourly-observations.csv"), encoding="utf-8")):
        if r["quality_flag"] == "ok" and r["temp_c"] != "" and r["valid_at_local"] >= since:
            out[r["valid_at_local"]] = float(r["temp_c"])
    return out


def load_fc(lead, since, end):
    import train_recica_mos as t
    rows = t.fetch_archived_forecasts(lead, since[:10], end[:10], variables=["temperature_2m"])
    out = {}
    for day, rec in rows.items():
        for h, v in rec["temperature_2m"]:
            out[f"{day}T{h:02d}:00"] = v
    return out


def stamp(ts, k):
    import datetime as dt
    return (dt.datetime.fromisoformat(ts) + dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:00")


def analyse(obs, fc):
    err = {ts: fc[ts] - obs[ts] for ts in obs if ts in fc}
    keys = sorted(err)
    res = {k: [] for k in KS}
    for ts in keys:
        e0 = err[ts]
        for k in KS:
            ts_k = stamp(ts, k)
            if ts_k in err:
                res[k].append((e0, err[ts_k]))
    print(f"urnih parov napaka(t0) – napaka(t0+k): {len(keys)} ur z napako")
    print(f"{'k [h]':>5} {'n':>6} {'w_opt':>6} {'MAE brez':>9} " + " ".join(f"{s:>8}" for s in list(SHAPES)[1:]) + f" {'w_opt':>8}")
    tot = {s: [] for s in SHAPES}
    tot["opt"] = []
    for k in KS:
        a = np.array(res[k])
        if len(a) < 200:
            continue
        e0, ek = a[:, 0], a[:, 1]
        w = float(np.dot(e0, ek) / np.dot(e0, e0))
        row = [np.abs(ek).mean()]
        tot["brez"].append(np.abs(ek))
        for s, hrs in list(SHAPES.items())[1:]:
            wk = max(0.0, 1 - k / hrs)
            m = np.abs(ek - wk * e0)
            row.append(m.mean())
            tot[s].append(m)
        mo = np.abs(ek - w * e0)
        tot["opt"].append(mo)
        print(f"{k:5d} {len(a):6d} {w:6.2f} {row[0]:9.3f} " + " ".join(f"{x:8.3f}" for x in row[1:]) + f" {mo.mean():8.3f}")
    print("\nPovprečje čez k = 1..12 (MAE °C):")
    for s in tot:
        if tot[s]:
            print(f"  {s:<6} {np.concatenate(tot[s]).mean():.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="since", default="2026-07-13")
    ap.add_argument("--lead", type=int, default=1)
    a = ap.parse_args()
    obs = load_obs(a.since)
    if not obs:
        sys.exit("ni urnih meritev")
    end = max(obs)
    fc = load_fc(a.lead, a.since, end)
    analyse(obs, fc)


if __name__ == "__main__":
    main()
