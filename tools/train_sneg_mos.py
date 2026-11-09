#!/usr/bin/env python3
"""
tools/train_sneg_mos.py -- MTR sneg (v0.x): verjetnost »snežnega dne« v dolini (Rečica) za D+1..D+3.

POMEMBNO -- cilj je PROKSI. Postaja IREICA1 snega ne meri. Snežni dan (proksi) = dnevna vsota padavin
>= WET_MM IN dnevno povprečje temperature zraka <= PRAG_T_AVG. To je »mokri hladni dan«, ne opazovan sneg.
Model zato NE napoveduje debeline snega, ne ali sneg obleži in ne razlikuje dežja pri 1 °C od snega pri 2 °C.
Povsod, kjer se številka pokaže, mora to pisati. Vodilni časi D+1..D+5 (pri D+6 skill ni boljši od D+5). Ko bo na voljo prava resnica (urni zapis z mokrim
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

MODEL_VERSION = "0.4"
MODELS = ["best_match", "ecmwf_ifs025", "gfs_seamless", "icon_seamless"]
MIN_MODELS = 3
LEADS = (1, 2, 3, 4, 5)   # D+4/D+5: skill +0,12/+0,10, surov prag pod klimatologijo (eval_sneg.py)
WET_MM = 0.2          # isti prag kot WET_DAY_MM v verify_forecasts.py
PRAG_T_AVG = 1.0      # naša izbira; občutljivost je v tools/ai/eval_sneg.py
SEASON = (10, 11, 12, 1, 2, 3, 4)
RIDGE = 0.1           # ob 0,01 / 0,1 / 1 je OOF skill enak na 0,003; zima ima ~20 dogodkov
CAL_PRIOR = 2.0       # moč stiskanja kalibracijskega naklona b proti 1
MIN_TRAIN_EVENTS = 5

# Opazovan sneg (9. 11. 2026, v0.4): dnevne serije ARSO padavinskih postaj v Zgornji Savinjski dolini (arhivski ID-ji iz
# izvoza iz ARSO arhiva meritev: Filip). Podatki so v data/arso-sneg-postaje/daily-<id>.json, septembra 2019 do danes,
# ki jih osvežuje tools/refresh_arso_sneg.py (Vir: Agencija Republike Slovenije za okolje).
# Višina je zapisana samo, kjer jo je mogoče preveriti v ARSO viru (observationAms_si_latest.xml): Gornji Grad 428 m, Radegunda 794 m.
# Gornji Grad je glavna postaja: dolina, 9 km od Rečice (366 m), najbližja po višini.
VALLEY_STATIONS = {
    "1748": {"name": "Gornji Grad", "alt_m": 428},
    "1749": {"name": "Luče", "alt_m": None},
    "1747": {"name": "Radegunda", "alt_m": 794},
    "1750": {"name": "Solčava", "alt_m": None},
}
OBS_PRIMARY = "1748"
# Prejšnja izbira (v0.3): pet postaj brez znanih imen, izbranih po korelaciji padavin; ostaja samo za eval_snowfall_openmeteo.py.
OBS_STATIONS_LEGACY = ("1651", "1652", "1801", "3002", "3152")
OBS_DIR = os.path.join(ROOT, "data", "arso-sneg-postaje")
OBS_NEW_SNOW_CM = 1.0     # »merljiv sneg«: nov sneg >= 1 cm ob jutranjem odčitku istega dne


def season_year(d):
    """Zima 2024/25 -> 2024."""
    y, m = int(d[:4]), int(d[5:7])
    return y if m >= 7 else y - 1


def is_snow_day(precip_mm, tavg, prag=PRAG_T_AVG):
    """Proksi za sneg v dolini. Edino mesto, kjer je definiran."""
    return 1 if (precip_mm is not None and tavg is not None and precip_mm >= WET_MM and tavg <= prag) else 0


# ---------------------------------------------------------------------------------------------- podatki
def load_observed(directory=OBS_DIR, stations=tuple(VALLEY_STATIONS)):
    """{postaja: {datum: novi sneg (cm)}} iz shranjenih ARSO dnevnih serij. Manjka postaja -> izpuščena; brez nobene -> {}."""
    out = {}
    for sid in stations:
        path = os.path.join(directory, f"daily-{sid}.json")
        if not os.path.exists(path):
            continue
        days = json.load(open(path, encoding="utf-8")).get("days") or []
        series = {d: new for d, depth, new, pr in days if new is not None}
        if series:
            out[sid] = series
    return out


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


def fit_obs_calibration(z, y, **_):
    """p_obs = sigmoid(a + z): samo intercept (naklon fiksen na 1). Z dvema parametroma (a, b) je bil skill pri izpuščeni zimi
    nestabilen (-0,11..+0,19), z interceptom pri vseh vodilnih časih pozitiven (+0,04..+0,24): 34 dogodkov in dve zimi ne
    prenesejo več. Vrne (a, 1,0)."""
    z, y = np.asarray(z, float), np.asarray(y, float)
    a = 0.0
    for _ in range(60):
        p = _sigmoid(a + z)
        step = np.sum(p - y) / (np.sum(p * (1 - p)) + 1e-9)
        a -= step
        if abs(step) < 1e-10:
            break
    return float(a), 1.0


def obs_x(precip_mm, tavg):
    """Vektor značilk za OPAZOVAN dan: isti `vector()` kot pri napovedi, delež mokrih modelov je 0 ali 1."""
    return vector({"tavg": float(tavg), "prec": float(precip_mm), "wetfrac": 1.0 if precip_mm >= WET_MM else 0.0})


def obs_rows(series, truth):
    """Opazovalni nabor: dnevi sezone, ko imamo meritev IREICA1 (padavine, T povp.) IN odčitek postaje (nov sneg, cm)."""
    out = []
    for d, (p, ta, _) in truth.items():
        v = series.get(d)
        if v is None or int(d[5:7]) not in SEASON:
            continue
        out.append({"date": d, "winter": season_year(d), "x": obs_x(p, ta), "y": 1.0 if v >= OBS_NEW_SNOW_CM else 0.0})
    return out


def shrink_logit(z, shrink, prevalence):
    """Logit skrčen proti pogostosti snega na postaji: z' = z_klim + shrink · (z − z_klim). Preslikava meritev → sneg ne ve,
    da so napovedi z vodilnim časom slabše; naklon kalibracije osnovnega modela (proksi, isti vodilni čas) to pove, zato se
    napoved proti D+5 krči proti klimatologiji (brez krčenja je bil razred >= 50 % pri D+5 napovedan 77 %, dejansko 44 %)."""
    zc = math.log(prevalence / (1 - prevalence))
    return zc + shrink * (z - zc)


def fit_obs_pp(series, truth):
    """Preslikava meritev v Rečici (T povp., padavine) v »nov sneg >= 1 cm na postaji«, naučena na VSEH zimah opazovanj
    (v0.4). Prej (v0.3) je bila kalibracija prilagojena na ~2 zimi arhiva napovedi (34 dogodkov); opazovanj je sedem zim.
    Vrne None, kadar je dogodkov premalo."""
    rows = obs_rows(series, truth)
    y = np.array([r["y"] for r in rows], float)
    if len(rows) < 100 or y.sum() < 2 * MIN_TRAIN_EVENTS:
        return None
    w = fit_logit(np.array([r["x"] for r in rows]), y)
    return {"coefficients": [round(float(x), 5) for x in w], "n": int(len(rows)), "events": int(y.sum()),
            "prevalence": round(float(y.mean()), 4), "winters": sorted({r["winter"] for r in rows})}


def obs_pp_cv(series, truth, lead_rows, shrink=1.0):
    """Preverjanje z izpuščanjem zime: preslikava, naučena na opazovanjih OSTALIH zim, napove sneg iz NAPOVEDANIH vhodov
    (modeli, vodilni čas) izpuščene zime. Napoved je torej ocenjena na vhodih, kot jih bo imela v živo, ne na meritvah."""
    rows = obs_rows(series, truth)
    P, Y, C = [], [], []
    for w in sorted({r["winter"] for r in lead_rows}):
        tr = [r for r in rows if r["winter"] != w]
        y_tr = np.array([r["y"] for r in tr], float)
        if y_tr.sum() < MIN_TRAIN_EVENTS:
            continue
        wts = fit_logit(np.array([r["x"] for r in tr]), y_tr)
        for r in lead_rows:
            v = series.get(r["date"])
            if r["winter"] != w or v is None:
                continue
            P.append(float(_sigmoid(shrink_logit(float(np.array(vector(r)) @ wts), shrink, float(y_tr.mean())))))
            Y.append(1.0 if v >= OBS_NEW_SNOW_CM else 0.0)
            C.append(float(y_tr.mean()))
    if not Y or sum(Y) == 0:
        return {}
    base = brier(C, Y)
    return {"n": len(Y), "events": int(sum(Y)), "brier": round(brier(P, Y), 4), "brier_clim": round(base, 4),
            "skill": round(1 - brier(P, Y) / base, 3) if base > 0 else None, "auc": round(auc(P, Y), 3),
            "mean_pred": round(float(np.mean(P)), 4), "mean_obs": round(float(np.mean(Y)), 4)}


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


def predict_obs_stations(entry, f):
    """{id postaje: verjetnost, da bo na njej zapadlo >= 1 cm novega snega}. Prazno, kadar model opazovanj ni imel."""
    z_vec = np.array(vector(f))
    return {sid: float(_sigmoid(shrink_logit(float(np.array(m["coefficients"]) @ z_vec), m.get("shrink", 1.0), m["prevalence"])))
            for sid, m in (entry.get("obs_pp") or {}).items()}


def predict_obs(entry, f):
    """Verjetnost merljivega snega na glavni postaji (Gornji Grad). None, kadar je model nima (stari model ali ni podatkov)."""
    return predict_obs_stations(entry, f).get(OBS_PRIMARY)


def predict_p(entry, f):
    """Verjetnost snežnega dne iz zapisa vodilnega časa v modelu."""
    z = float(np.array(entry["coefficients"]) @ np.array(vector(f)))
    cal = entry.get("calibration") or {}
    return float(_sigmoid(cal.get("a", 0.0) + cal.get("b", 1.0) * z))


# ---------------------------------------------------------------------------------------------- učenje
def train(truth=None, by=None, observed=None):
    truth = truth if truth is not None else load_truth()
    observed = observed if observed is not None else load_observed()
    by = by if by is not None else load_archive()
    obs_models = {sid: fit_obs_pp(series, truth) for sid, series in observed.items() if sid in VALLEY_STATIONS}
    obs_models = {sid: m for sid, m in obs_models.items() if m}
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
        if obs_models:
            shrink = round(min(1.0, max(0.3, b)), 4)      # b = naklon kalibracije osnovnega modela za ta vodilni čas
            leads[str(lead)]["obs_pp"] = {
                sid: dict(m, name=VALLEY_STATIONS[sid]["name"], shrink=shrink, cv=obs_pp_cv(observed[sid], truth, rows, shrink))
                for sid, m in obs_models.items()}
        dates += [r["date"] for r in rows]
    return {
        "model_version": MODEL_VERSION,
        "trained_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_range": {"from": min(dates), "to": max(dates)} if dates else None,
        "target": {
            "name": "snežni dan (proksi)",
            "definition": f"padavine >= {WET_MM} mm IN povprečna temperatura zraka <= {PRAG_T_AVG} °C",
            "caveat": "Postaja snega ne meri; osnovni model napoveduje mokri hladni dan (proksi).",
        },
        "observed_target": {
            "name": "merljiv sneg (opazovanje)",
            "definition": f"nov sneg >= {OBS_NEW_SNOW_CM:g} cm ob jutranjem odčitku na ARSO postaji (glavna: {VALLEY_STATIONS[OBS_PRIMARY]['name']})",
            "caveat": "Postaja ni v Rečici; verjetnost velja za njeno lego, ne za točko v Rečici. Postaja Meteorec snega ne meri.",
            "primary": OBS_PRIMARY,
            "stations": {sid: {"name": VALLEY_STATIONS[sid]["name"], "alt_m": VALLEY_STATIONS[sid]["alt_m"]} for sid in obs_models},
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
        for sid, m in (e.get("obs_pp") or {}).items():
            c2 = m["cv"]
            print(f"       sneg {m['name']} ({sid}): n = {m['n']}, dogodkov {m['events']} ({m['prevalence']:.3f}); zima izpuščena na napovedanih vhodih: "
                  f"Brier {c2.get('brier')} proti klim. {c2.get('brier_clim')} (skill {c2.get('skill')}, AUC {c2.get('auc')}, "
                  f"povpr. napoved {c2.get('mean_pred')} proti dejanski {c2.get('mean_obs')}, dogodkov {c2.get('events')})")
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
