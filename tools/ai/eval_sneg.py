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
  logit2 -- logistična regresija na [T povp. modelov, log1p(povpr. padavine)] (osnovna dva)
  logit3 -- model v produkciji (tools/train_sneg_mos.py): + temperatura × delež modelov z dežjem
Značilke, proksi in prileganje so v tools/train_sneg_mos.py (ena kopija); tu je samo primerjava.

usage: eval_sneg.py [--prag 1.0] [--leads 1 2 3]
"""
import argparse
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import train_sneg_mos as tsm  # noqa: E402  (značilke, proksi in prileganje so skupni z modelom)

WET_MM = tsm.WET_MM
auc, brier, fit_logit = tsm.auc, tsm.brier, tsm.fit_logit


def load(prag_t):
    return tsm.load_truth(prag_t), tsm.load_archive()


def samples_for(lead, truth, by):
    return tsm.samples_for(lead, truth, by)


def design(rows, kind):
    X = np.array([tsm.vector(r) for r in rows], dtype=float)
    return X if kind == "logit3" else X[:, :3]    # logit2 = osnovni dve značilki, logit3 = model v produkciji


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
