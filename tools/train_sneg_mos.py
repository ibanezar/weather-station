#!/usr/bin/env python3
"""
tools/train_sneg_mos.py -- MTR sneg (v0.x): verjetnost »snežnega dne« v dolini (Rečica) za D+1..D+3.

POMEMBNO -- cilj je PROKSI. Postaja IREICA1 snega ne meri. Snežni dan (proksi) = dnevna vsota padavin
>= WET_MM IN dnevno povprečje temperature zraka <= PRAG_T_AVG. To je »mokri hladni dan«, ne opazovan sneg.
Model zato NE napoveduje debeline snega, ne ali sneg obleži in ne razlikuje dežja pri 1 °C od snega pri 2 °C.
Povsod, kjer se številka pokaže, mora to pisati. Ko bo na voljo prava resnica (urni zapis z mokrim
termometrom, ARSO snežne meritve), se spremeni samo `load_truth()`.

Vhod (brez omrežja, vse v repozitoriju):
  data/forecast-archive.csv -- napovedi N dni prej (previous_dayN) za pet modelov, dnevni Tmax/Tmin/padavine
  history.json              -- meritve postaje (samo zunanja polja; dnevi `era5` so reanaliza in se ne štejejo)

Model: ločena logistična regresija (L2) za vsak vodilni čas na treh značilkah: povprečje (Tmax+Tmin)/2 čez
modele, log1p(povprečne padavine) in temperatura × delež modelov z dežjem (temperatura šteje samo, kadar
pada). Malo značilk, ker ima zima ~20 proksi dogodkov: več bi se naučilo šum. Obliko sem izbral med petimi
variantami (osnovna 2 značilki, + delež mokrih, + interakcija …); interakcija je dala +0,02 do +0,04 Brierjevega
skilla, kar je na 39 dogodkih znotraj šuma -- izbira je fizikalna, ne najboljša številka.
Preverjanje: izpuščanje cele zime (dnevi iste zime niso neodvisni). Verjetnosti iz izpuščenih zim (OOF) so
osnova za kalibracijsko premico (a + b·z, b stisnjen proti 1): surov logit je pri visokih verjetnostih
preveč samozavesten.

Uporaba:
  python3 tools/train_sneg_mos.py            # zapiše model/sneg-mos.json
  python3 tools/train_sneg_mos.py --no-write
"""
import argparse
import csv
import datetime as dt
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "model", "sneg-mos.json")
ARCHIVE_PATH = os.path.join(ROOT, "data", "forecast-archive.csv")
HISTORY_PATH = os.path.join(ROOT, "history.json")

MODEL_VERSION = "0.1"
MODELS = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
MIN_MODELS = 3
LEADS = (1, 2, 3)
WET_MM = 0.2          # isti prag kot WET_DAY_MM v verify_forecasts.py
PRAG_T_AVG = 1.0      # naša izbira; občutljivost je v tools/ai/eval_sneg.py
SEASON = (10, 11, 12, 1, 2, 3, 4)
RIDGE = 0.1           # ob 0,01 / 0,1 / 1 je OOF skill enak na 0,003; zima ima ~20 dogodkov
CAL_PRIOR = 2.0       # moč stiskanja kalibracijskega naklona b proti 1
MIN_TRAIN_EVENTS = 5


def season_year(d):
    """Zima 2024/25 -> 2024."""
    y, m = int(d[:4]), int(d[5:7])
    return y if m >= 7 else y - 1


def is_snow_day(precip_mm, tavg, prag=PRAG_T_AVG):
    """Proksi za sneg v dolini. Edino mesto, kjer je definiran."""
    return 1 if (precip_mm is not None and tavg is not None and precip_mm >= WET_MM and tavg <= prag) else 0


# ---------------------------------------------------------------------------------------------- podatki
def load_truth(prag=PRAG_T_AVG, path=HISTORY_PATH):
    """{datum: (padavine, T povp., proksi)} iz meritev postaje. Samo zunanja polja."""
    hist = json.load(open(path, encoding="utf-8"))
    out = {}
    for d, v in hist.items():
        if v.get("src") == "era5" or v.get("precipTotal") is None or v.get("tempAvg") is None:
            continue
        out[d] = (v["precipTotal"], v["tempAvg"], is_snow_day(v["precipTotal"], v["tempAvg"], prag))
    return out


def load_archive(path=ARCHIVE_PATH):
    """{vodilni čas: {datum: {model: (tmax, tmin, padavine)}}}."""
    by = defaultdict(lambda: defaultdict(dict))
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["model"] not in MODELS:
                continue
            try:
                by[int(r["lead_days"])][r["valid_at"]][r["model"]] = (
                    float(r["tmax_c"]), float(r["tmin_c"]), float(r["precip_mm"]))
            except (ValueError, TypeError):
                continue
    return by


def day_features(models):
    """Značilke enega dne iz {model: (tmax, tmin, padavine)} ali None, kadar je modelov premalo.
    Ista funkcija za učenje in napoved -- dva prepisa bi se razšla (kot daily_features pri MTR)."""
    models = {m: v for m, v in models.items() if m in MODELS and None not in v}
    if len(models) < MIN_MODELS:
        return None
    precs = [p for _, _, p in models.values()]
    bm = models.get("best_match")
    tavg = float(np.mean([(a + b) / 2 for a, b, _ in models.values()]))
    return {
        "tavg": tavg,
        "prec": float(np.mean(precs)),
        "wetfrac": sum(p >= WET_MM for p in precs) / len(precs),
        "bm_tavg": (bm[0] + bm[1]) / 2 if bm else tavg,
        "bm_prec": bm[2] if bm else float(np.mean(precs)),
        "n_models": len(models),
    }


def vector(f):
    # T šteje samo, kadar pada: interakcija T × delež modelov z dežjem (fizikalni razlog, ne iskanje najboljše številke).
    return [1.0, f["tavg"], math.log1p(f["prec"]), f["tavg"] * f["wetfrac"]]


def samples_for(lead, truth, by):
    out = []
    for d, models in sorted(by[lead].items()):
        if d not in truth or int(d[5:7]) not in SEASON:
            continue
        f = day_features(models)
        if f is None:
            continue
        f.update(date=d, winter=season_year(d), y=truth[d][2], obs_t=truth[d][1])
        out.append(f)
    return out


# ---------------------------------------------------------------------------------------------- matematika
def _sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def _newton(X, y, pen, target, it=100):
    """Dušen Newton za L2-kaznovano logistično izgubo: korak se prepolovi, dokler izguba ne pade.
    Brez dušenja je kalibracija ob zelo samozavestnem logitu divergirala (b ~ 700)."""
    def loss(w):
        z = X @ w
        ll = np.sum(np.logaddexp(0, z) - y * z)
        d = w - target
        return ll + 0.5 * d @ pen @ d

    w = target.copy()
    cur = loss(w)
    for _ in range(it):
        p = _sigmoid(X @ w)
        g = X.T @ (p - y) + pen @ (w - target)
        H = (X.T * (p * (1 - p))) @ X + pen + np.eye(X.shape[1]) * 1e-6
        step = np.linalg.solve(H, g)
        t = 1.0
        while t > 1e-6:
            cand = w - t * step
            new = loss(cand)
            if new <= cur + 1e-12:
                break
            t /= 2
        else:
            break
        w, done = cand, abs(cur - new) < 1e-10
        cur = new
        if done:
            break
    return w


def fit_logit(X, y, ridge=RIDGE):
    """Logistična regresija z L2 (presečišče brez kazni)."""
    pen = np.eye(X.shape[1]) * ridge
    pen[0, 0] = 0.0
    return _newton(X, y, pen, np.zeros(X.shape[1]))


def fit_calibration(z, y, prior=CAL_PRIOR):
    """p = sigmoid(a + b·z); a je stisnjen proti 0, b proti 1 (malo dogodkov)."""
    z, y = np.asarray(z, float), np.asarray(y, float)
    X = np.column_stack([np.ones_like(z), z])
    w = _newton(X, y, np.eye(2) * prior, np.array([0.0, 1.0]))
    return float(w[0]), float(w[1])


def auc(p, y):
    p, y = np.asarray(p), np.asarray(y)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()
    return float(gt / (len(pos) * len(neg)))


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def oof_logits(rows):
    """Logiti iz izpuščenih zim (vsaka zima napovedana z modelom, naučenim na ostalih)."""
    z, ys, idx = [], [], []
    for w in sorted({r["winter"] for r in rows}):
        tr = [r for r in rows if r["winter"] != w]
        te = [(i, r) for i, r in enumerate(rows) if r["winter"] == w]
        if sum(r["y"] for r in tr) < MIN_TRAIN_EVENTS or not te:
            continue
        wts = fit_logit(np.array([vector(r) for r in tr]), np.array([r["y"] for r in tr], float))
        for i, r in te:
            z.append(float(np.array(vector(r)) @ wts))
            ys.append(r["y"])
            idx.append(i)
    return np.array(z), np.array(ys, float), idx


def predict_p(entry, f):
    """Verjetnost snežnega dne iz zapisa vodilnega časa v modelu."""
    z = float(np.array(entry["coefficients"]) @ np.array(vector(f)))
    cal = entry.get("calibration") or {}
    return float(_sigmoid(cal.get("a", 0.0) + cal.get("b", 1.0) * z))


# ---------------------------------------------------------------------------------------------- učenje
def train(truth=None, by=None):
    truth = truth if truth is not None else load_truth()
    by = by if by is not None else load_archive()
    leads, dates = {}, []
    for lead in LEADS:
        rows = samples_for(lead, truth, by)
        y = np.array([r["y"] for r in rows], float)
        if len(rows) < 100 or y.sum() < 2 * MIN_TRAIN_EVENTS:
            print(f"  D+{lead}: premalo podatkov ({len(rows)} dni, {int(y.sum())} dogodkov) -- izpuščen")
            continue
        X = np.array([vector(r) for r in rows])
        w = fit_logit(X, y)
        z, yo, _ = oof_logits(rows)
        a, b = fit_calibration(z, yo) if len(z) else (0.0, 1.0)
        clim = float(y.mean())
        cv = {"n": int(len(yo)), "events": int(yo.sum())}
        if len(z):
            p_raw, p_cal = _sigmoid(z), _sigmoid(a + b * z)
            base = brier([clim] * len(yo), yo)
            cv.update(brier_clim=round(base, 4), brier_raw=round(brier(p_raw, yo), 4),
                      brier_cal=round(brier(p_cal, yo), 4), skill_cal=round(1 - brier(p_cal, yo) / base, 3),
                      auc=round(auc(p_cal, yo), 3),
                      note="kalibracija je prilagojena na istih OOF napovedih, zato je brier_cal rahlo optimističen")
        leads[str(lead)] = {
            "names": ["1", "tavg_modelov", "log1p_padavine_modelov", "tavg_x_delez_mokrih_modelov"],
            "coefficients": [round(float(x), 5) for x in w],
            "calibration": {"a": round(a, 4), "b": round(b, 4)},
            "n": int(len(rows)), "events": int(y.sum()), "prevalence": round(clim, 4),
            "cv": cv,
        }
        dates += [r["date"] for r in rows]
    return {
        "model_version": MODEL_VERSION,
        "trained_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_range": {"from": min(dates), "to": max(dates)} if dates else None,
        "target": {
            "name": "snežni dan (proksi)",
            "definition": f"padavine >= {WET_MM} mm IN povprečna temperatura zraka <= {PRAG_T_AVG} °C",
            "caveat": "Postaja snega ne meri; to je mokri hladni dan, ne opazovan sneg.",
        },
        "season_months": list(SEASON), "models": MODELS, "min_models": MIN_MODELS,
        "ridge": RIDGE, "cal_prior": CAL_PRIOR,
        "leads": leads,
    }


def main():
    ap = argparse.ArgumentParser(description="Učenje MTR sneg (proksi).")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    model = train()
    if not model["leads"]:
        print("✗ Nobenega vodilnega časa ni bilo mogoče naučiti.", file=sys.stderr)
        return 1
    for k, e in model["leads"].items():
        cv = e["cv"]
        print(f"  D+{k}: n = {e['n']}, dogodkov {e['events']}, koef {e['coefficients']}, kalibracija "
              f"a = {e['calibration']['a']}, b = {e['calibration']['b']}; OOF Brier {cv.get('brier_cal')} "
              f"proti klim. {cv.get('brier_clim')} (skill {cv.get('skill_cal')}, AUC {cv.get('auc')})")
    if a.no_write:
        print("(--no-write)")
        return 0
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"→ {os.path.relpath(MODEL_PATH, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
