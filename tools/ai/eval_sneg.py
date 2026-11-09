#!/usr/bin/env python3
"""
Prototip: MTR sneg -- ali se iz dnevnih napovedi modelov da napovedati »snežni dan v dolini« (Rečica)?

Postaja IREICA1 snega NE meri, zato je cilj PROKSI, in tako tudi piše povsod, kjer se rezultat pokaže:
    snežni dan (proksi) = dnevna vsota padavin >= 0,2 mm IN dnevno povprečje temperature zraka <= PRAG_T_AVG.
To je »mokri hladni dan«, ne opazovan sneg; dež pri 1 °C in sneg pri 2 °C proksi zgreši. Prag je izbira, zato
skript izpiše tudi občutljivost na prag (0,5 / 1,0 / 1,5 °C).

Vhod: data/forecast-archive.csv (napovedi N dni prej, pet modelov, od 2024-05) in history.json (meritve postaje,
brez dni `era5`). Brez omrežja. Sezona: oktober-april. Preverjanje: izpuščanje celotne zime (zima 2024/25 <->
2025/26), ker sta v arhivu napovedi samo dve; dnevi iste zime niso neodvisni (sosednji dnevi imajo isto vreme),
zato je izpuščanje zime edino pošteno merilo.

Primerja:
  klim   -- delež snežnih dni v učni zimi (brez znanja o vremenu)
  pravilo -- surov best_match: padavine >= 0,5 mm IN povprečna temperatura <= PRAG_PRAVILO (enostaven prag)
  logit2 -- logistična regresija na [popravljena T povp. modelov, log1p(povpr. padavine)]
  logit3 -- isto + delež modelov z >= 0,2 mm

usage: eval_sneg.py [--prag 1.0] [--leads 1 2 3]
"""
import argparse
import csv
import json
import math
import os
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODELS = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
MIN_MODELS = 3
WET_MM = 0.2          # isti prag kot WET_DAY_MM v verify_forecasts.py
SEASON = {10, 11, 12, 1, 2, 3, 4}


def season_year(d):
    """Zima 2024/25 -> 2024."""
    y, m = int(d[:4]), int(d[5:7])
    return y if m >= 7 else y - 1


def load(prag_t):
    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    truth = {}
    for d, v in hist.items():
        if v.get("src") == "era5" or v.get("precipTotal") is None or v.get("tempAvg") is None:
            continue
        truth[d] = (v["precipTotal"], v["tempAvg"], 1 if (v["precipTotal"] >= WET_MM and v["tempAvg"] <= prag_t) else 0)
    by = defaultdict(lambda: defaultdict(dict))   # lead -> date -> model -> (tmax,tmin,prec)
    with open(os.path.join(ROOT, "data", "forecast-archive.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["model"] not in MODELS:
                continue
            try:
                by[int(r["lead_days"])][r["valid_at"]][r["model"]] = (float(r["tmax_c"]), float(r["tmin_c"]), float(r["precip_mm"]))
            except (ValueError, TypeError):
                continue
    return truth, by


def samples_for(lead, truth, by):
    out = []
    for d, models in sorted(by[lead].items()):
        if d not in truth or int(d[5:7]) not in SEASON or len(models) < MIN_MODELS:
            continue
        tavg = float(np.mean([(a + b) / 2 for a, b, _ in models.values()]))
        precs = [p for _, _, p in models.values()]
        out.append({
            "date": d, "winter": season_year(d), "tavg": tavg,
            "prec": float(np.mean(precs)), "wetfrac": sum(p >= WET_MM for p in precs) / len(precs),
            "bm_tavg": (models["best_match"][0] + models["best_match"][1]) / 2 if "best_match" in models else tavg,
            "bm_prec": models["best_match"][2] if "best_match" in models else float(np.mean(precs)),
            "y": truth[d][2], "obs_t": truth[d][1],
        })
    return out


def design(rows, kind):
    cols = [[1.0] * len(rows), [r["tavg"] for r in rows], [math.log1p(r["prec"]) for r in rows]]
    if kind == "logit3":
        cols.append([r["wetfrac"] for r in rows])
    return np.array(cols, dtype=float).T


def fit_logit(X, y, ridge=1.0, it=60):
    """Logistična regresija z L2 (brez presečišča), Newton. Ridge je pomemben: zima ima ~20 dogodkov."""
    w = np.zeros(X.shape[1])
    pen = np.eye(X.shape[1]) * ridge
    pen[0, 0] = 0.0
    for _ in range(it):
        z = X @ w
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        g = X.T @ (p - y) + pen @ w
        H = (X.T * (p * (1 - p))) @ X + pen + np.eye(X.shape[1]) * 1e-6
        step = np.linalg.solve(H, g)
        w -= step
        if np.max(np.abs(step)) < 1e-8:
            break
    return w


def auc(p, y):
    p, y = np.asarray(p), np.asarray(y)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return gt / (len(pos) * len(neg))


def brier(p, y):
    p, y = np.asarray(p), np.asarray(y)
    return float(np.mean((p - y) ** 2))


def evaluate(rows, pravilo_t):
    winters = sorted({r["winter"] for r in rows})
    pred = {k: [] for k in ("klim", "pravilo", "logit2", "logit3")}
    ys, meta = [], []
    for w in winters:
        tr = [r for r in rows if r["winter"] != w]
        te = [r for r in rows if r["winter"] == w]
        if sum(r["y"] for r in tr) < 5 or not te:
            continue
        ytr = np.array([r["y"] for r in tr], float)
        base = float(ytr.mean())
        pred["klim"] += [base] * len(te)
        pred["pravilo"] += [1.0 if (r["bm_prec"] >= 0.5 and r["bm_tavg"] <= pravilo_t) else 0.0 for r in te]
        for kind in ("logit2", "logit3"):
            wts = fit_logit(design(tr, kind), ytr)
            z = design(te, kind) @ wts
            pred[kind] += list(1 / (1 + np.exp(-z)))
        ys += [r["y"] for r in te]
        meta += [(w, r["date"]) for r in te]
    return pred, np.array(ys, float), meta


def report(lead, rows, pravilo_t):
    pred, y, meta = evaluate(rows, pravilo_t)
    if len(y) == 0:
        print(f"D+{lead}: premalo podatkov")
        return None
    clim = brier(pred["klim"], y)
    print(f"\nD+{lead}: n = {len(y)} dni, snežnih (proksi) = {int(y.sum())}, zimi {sorted({m[0] for m in meta})}")
    res = {}
    for k in ("klim", "pravilo", "logit2", "logit3"):
        p = np.array(pred[k])
        b = brier(p, y)
        line = f"  {k:8s} Brier {b:.3f}  skill {1 - b / clim:+.2f}"
        if k != "klim":
            line += f"  AUC {auc(p, y):.2f}"
            hit = p >= 0.5
            tp = int((hit & (y == 1)).sum())
            fp = int((hit & (y == 0)).sum())
            fn = int((~hit & (y == 1)).sum())
            line += f"  p>=0,5: zadetkov {tp}, napačnih alarmov {fp}, zgrešenih {fn}"
        print(line)
        res[k] = b
    return res


def calibration(rows, pravilo_t):
    pred, y, _ = evaluate(rows, pravilo_t)
    p = np.array(pred["logit2"])
    print("  zanesljivost logit2 (napovedana -> dejanski delež):")
    for lo, hi in [(0, .05), (.05, .15), (.15, .3), (.3, .5), (.5, .75), (.75, 1.01)]:
        m = (p >= lo) & (p < hi)
        if m.sum():
            print(f"    {lo:.2f}-{min(hi, 1):.2f}: n = {int(m.sum()):3d}  napovedano {p[m].mean():.2f}  dejansko {y[m].mean():.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prag", type=float, default=1.0)
    ap.add_argument("--leads", type=int, nargs="*", default=[1, 2, 3])
    a = ap.parse_args()
    for prag in sorted({0.5, a.prag, 1.5}):
        truth, by = load(prag)
        print(f"\n===== proksi: padavine >= {WET_MM} mm in T povp. <= {prag} °C =====")
        for lead in a.leads:
            rows = samples_for(lead, truth, by)
            report(lead, rows, prag)
            if prag == a.prag:
                calibration(rows, prag)
