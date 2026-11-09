#!/usr/bin/env python3
"""
Ali je Open-Meteo `snowfall` (napoved, ki je bila resnično izdana N dni prej) uporaben vhod za MTR sneg?

Teče v GitHub Actions (previous-runs-api.open-meteo.com iz razvojnega peskovnika ni dosegljiv).
1. Razpoložljivost: za vsak model in vodilni čas pove, koliko urnih vrednosti `snowfall_previous_dayN` in
   `snow_depth_previous_dayN` ni null (docs/model-recica.md: višina snega v arhivu je bila null).
2. Skill: dnevna vsota napovedanega snega (povprečje modelov) proti opazovanemu novemu snegu >= 1 cm na petih
   ARSO postajah (data/arso-sneg-postaje/) in proti osnovnemu logitu modela (train_sneg_mos). AUC in tabela zadetkov.
Piše data/sneg-snowfall-eval.json. Notranjih meritev ne bere. Vir opazovanj: Agencija Republike Slovenije za okolje.
"""
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import train_sneg_mos as tsm  # noqa: E402

LAT, LON = 46.325779, 14.921137
MODELS = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
LEADS = (1, 2, 3, 4, 5)
START, END = "2024-10-01", "2026-04-30"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-MOS/1.0; +https://meteorec.si)"}


def fetch(model):
    vars_ = ",".join(f"{v}_previous_day{n}" for v in ("snowfall", "snow_depth") for n in LEADS)
    q = urllib.parse.urlencode({"latitude": LAT, "longitude": LON, "hourly": vars_, "models": model,
                                "start_date": START, "end_date": END, "timezone": "Europe/Ljubljana"})
    for i in range(4):
        try:
            req = urllib.request.Request("https://previous-runs-api.open-meteo.com/v1/forecast?" + q, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except Exception as e:      # noqa: BLE001
            print(f"  {model}: poskus {i + 1} ni uspel ({e})")
            time.sleep(10 * (i + 1))
    return None


def auc(p, y):
    p, y = np.asarray(p, float), np.asarray(y, float)
    pos, neg = p[y == 1], p[y == 0]
    if not len(pos) or not len(neg):
        return None
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))


def main():
    out = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "range": [START, END],
           "availability": {}, "skill": {}}
    daily = {}          # (model, lead) -> {datum: vsota snowfall cm}
    for m in MODELS:
        d = fetch(m)
        time.sleep(2)
        if not d or "hourly" not in d:
            out["availability"][m] = "ni odgovora"
            print(m, "ni odgovora")
            continue
        h = d["hourly"]
        times = h["time"]
        av = {}
        for n in LEADS:
            for v in ("snowfall", "snow_depth"):
                arr = h.get(f"{v}_previous_day{n}") or []
                nn = sum(1 for x in arr if x is not None)
                nz = sum(1 for x in arr if x)
                av[f"{v}_d{n}"] = {"non_null": nn, "of": len(times), "non_zero": nz}
            sf = h.get(f"snowfall_previous_day{n}") or []
            acc = defaultdict(float)
            seen = defaultdict(int)
            for t, x in zip(times, sf):
                if x is not None:
                    acc[t[:10]] += x
                    seen[t[:10]] += 1
            daily[(m, n)] = {k: v for k, v in acc.items() if seen[k] >= 20}
        out["availability"][m] = av
        print(m, {k: (v["non_null"], v["non_zero"]) for k, v in av.items() if k.endswith("d1") or k.endswith("d3")})

    observed = tsm.load_observed(stations=tsm.OBS_STATIONS_LEGACY)
    truth = tsm.load_truth()
    by = tsm.load_archive()
    for lead in LEADS:
        rows = tsm.samples_for(lead, truth, by)
        z_oof, _, idx = tsm.oof_logits(rows)
        zmap = {rows[i]["date"]: z for z, i in zip(z_oof, idx)}
        zs, sf_mean, sf_max, ys, ws = [], [], [], [], []
        for date, z in zmap.items():
            vals = [daily[(m, lead)].get(date) for m in MODELS if (m, lead) in daily]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            for series in observed.values():
                v = series.get(date)
                if v is None:
                    continue
                zs.append(z)
                sf_mean.append(float(np.mean(vals)))
                sf_max.append(float(max(vals)))
                ys.append(1 if v >= tsm.OBS_NEW_SNOW_CM else 0)
                ws.append(tsm.season_year(date))
        ys_a = np.array(ys)
        res = {"n": len(ys), "events": int(ys_a.sum()),
               "auc_osnovni_logit": auc(zs, ys), "auc_snowfall_povprecje": auc(sf_mean, ys), "auc_snowfall_max": auc(sf_max, ys),
               "dni_snowfall_nad_0": int(sum(1 for x in sf_mean if x > 0.05))}
        pred = np.array(sf_mean) > 0.05
        res["snowfall>0: zadetkov/napacnih alarmov/zgresenih"] = [int((pred & (ys_a == 1)).sum()), int((pred & (ys_a == 0)).sum()),
                                                                  int((~pred & (ys_a == 1)).sum())]
        # kombinacija: osnovni logit (samo intercept, kot v produkciji) proti logit + zastavica snowfall > 0 (izpuščena zima)
        z_a, f_a, w_a = np.array(zs), (np.array(sf_mean) > 0.05).astype(float), np.array(ws)
        pa, pb, tr, base = [], [], [], []
        for w in sorted(set(ws)):
            te, trn = w_a == w, w_a != w
            if ys_a[trn].sum() < 5 or not te.any():
                continue
            a, _ = tsm.fit_obs_calibration(z_a[trn], ys_a[trn])
            X = np.column_stack([np.ones(trn.sum()), z_a[trn], f_a[trn]])
            pen = np.eye(3) * 0.5
            pen[0, 0] = 0.0
            wb = tsm._newton(X, ys_a[trn].astype(float), pen, np.array([0.0, 1.0, 0.0]))
            pa += list(tsm._sigmoid(a + z_a[te]))
            pb += list(tsm._sigmoid(wb[0] + wb[1] * z_a[te] + wb[2] * f_a[te]))
            tr += list(ys_a[te])
            base += [float(ys_a[trn].mean())] * int(te.sum())
        if tr:
            b0 = tsm.brier(base, tr)
            res["izpuscena_zima"] = {"skill_osnovni": round(1 - tsm.brier(pa, tr) / b0, 3), "skill_z_snowfall": round(1 - tsm.brier(pb, tr) / b0, 3),
                                     "auc_osnovni": round(auc(pa, tr), 3), "auc_z_snowfall": round(auc(pb, tr), 3)}
        out["skill"][f"D+{lead}"] = res
        print(f"D+{lead}:", json.dumps(res, ensure_ascii=False))
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    with open(os.path.join(ROOT, "data", "sneg-snowfall-eval.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
