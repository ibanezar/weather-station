#!/usr/bin/env python3
"""
Poskus (2. 11. 2026): ali »izbirnik modela« po meteoblue mLM pomaga za Rečico?

  eval_selector.py [since=2024-07-01] [--lead N]

mLM (https://content.meteoblue.com/en/research-education/specifications/data-sources/post-processing/
meteoblue-learning-multimodel-mlm/) iz skupine modelov izbere tistega, ki je najbolje simuliral zadnje
meritve, in nadaljuje z njim. Tu isto idejo preizkusimo na IREICA1: ali je napaka modela v zadnjih N
dneh dober napovednik, kateri model bo jutri najboljši?

Vhod: `data/forecast-archive.csv` (pravi `previous_dayN`, brez uhajanja informacije) in `history.json`
(samo dnevi `station`/`wu`, ne `era5`). Brez omrežja.

Informacija ob izdaji: napoved vodilnega časa L za dan D je izdana na D−L; izmerjen je dan največ
D−L−1. Okno napak izbirnika seže torej do D−L−1 (konzervativno).

Metode (vse za Tmax in Tmin posebej):
  single:<model>   surov model
  mean4            povprečje IFS, GFS, ICON, ARPEGE
  fixed            model z najmanjšo MAE na VSEH dneh do D−L−1 (razširjajoče okno)
  sel<N>           model z najmanjšo MAE v zadnjih N izmerjenih dneh (mLM)
  sel<N>+bc        isti model, od njega odštejemo njegovo povprečno napako (predznačeno) v oknu
  mean4+bc<N>      povprečje štirih modelov, odštejemo njegovo povprečno napako v zadnjih N dneh
  invw<N>          povprečje modelov z utežjo 1/MAE v oknu

Ocena: MAE na skupnih dneh, uparjen 7-dnevni blokovni bootstrap razlike proti `fixed` in proti
`best_match` (kot eval_mtr3.py). MTR (ridge z multi-značilkami in napakami zadnjih dni) tu NI
primerjan: potrebuje urni predpomnilnik Open-Meteo; njegovo objavljeno MAE glej docs/model-recica.md.
"""
import csv, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_arpege_europe", "best_match"]
CORE4 = MODELS[:4]
WINDOWS = (3, 7, 14, 30)
MIN_DAYS = 3          # najmanj izmerjenih dni v oknu, sicer metoda tega dne ne napove
BLOCK, REPS = 7, 4000
rng = np.random.default_rng(7)


def boot(d):
    n = len(d)
    nb = int(np.ceil(n / BLOCK))
    st = rng.integers(0, n - BLOCK + 1, size=(REPS, nb))
    idx = (st[:, :, None] + np.arange(BLOCK)).reshape(REPS, -1)[:, :n]
    m = d[idx].mean(axis=1)
    return d.mean(), np.percentile(m, [2.5, 97.5])


def load(lead):
    """({model: {datum: {tmax, tmin}}}, {datum: {tmax, tmin}} meritve)."""
    fc = {m: {} for m in MODELS}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "forecast-archive.csv"), encoding="utf-8")):
        if r["model"] in fc and int(r["lead_days"]) == lead and r["tmax_c"] != "" and r["tmin_c"] != "":
            fc[r["model"]][r["valid_at"]] = {"tmax": float(r["tmax_c"]), "tmin": float(r["tmin_c"])}
    hist = json.load(open(os.path.join(ROOT, "history.json"), encoding="utf-8"))
    obs = {}
    for d, o in hist.items():
        if o.get("src") in ("station", "wu") and o.get("tempHigh") is not None and o.get("tempLow") is not None:
            obs[d] = {"tmax": o["tempHigh"], "tmin": o["tempLow"]}
    return fc, obs


def day_add(d, n):
    import datetime as dt
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def run(lead, since):
    fc, obs = load(lead)
    # dnevi, ko imajo VSI štirje glavni modeli + best_match napoved in je meritev
    days = sorted(d for d in obs if all(d in fc[m] for m in MODELS))
    out = {tg: {} for tg in ("tmax", "tmin")}
    for tg in out:
        for D in days:
            if D < since:
                continue
            last = day_add(D, -lead - 1)                      # zadnji izmerjeni dan ob izdaji
            known = [d for d in days if d <= last]
            if len(known) < MIN_DAYS:
                continue
            y = obs[D][tg]
            f = {m: fc[m][D][tg] for m in MODELS}
            preds = {"single:" + m: f[m] for m in MODELS}
            m4 = float(np.mean([f[m] for m in CORE4]))
            preds["mean4"] = m4

            def err_of(m, win):
                return np.array([fc[m][d][tg] - obs[d][tg] for d in win])

            allmae = {m: np.abs(err_of(m, known)).mean() for m in CORE4}
            preds["fixed"] = f[min(allmae, key=allmae.get)]
            for N in WINDOWS:
                win = known[-N:]
                if len(win) < MIN_DAYS:
                    continue
                e = {m: err_of(m, win) for m in CORE4}
                mae = {m: np.abs(e[m]).mean() for m in CORE4}
                best = min(mae, key=mae.get)
                preds[f"sel{N}"] = f[best]
                preds[f"sel{N}+bc"] = f[best] - e[best].mean()
                w = {m: 1 / max(mae[m], 0.1) for m in CORE4}
                preds[f"invw{N}"] = sum(w[m] * f[m] for m in CORE4) / sum(w.values())
                e4 = np.array([np.mean([fc[m][d][tg] for m in CORE4]) - obs[d][tg] for d in win])
                preds[f"mean4+bc{N}"] = m4 - e4.mean()
            for k, v in preds.items():
                out[tg].setdefault(k, []).append((D, v, y))
    return out


def report(lead, since):
    res = run(lead, since)
    print(f"\n=== vodilni čas D+{lead}, od {since} ===")
    for tg in ("tmax", "tmin"):
        r = res[tg]
        common = sorted(set.intersection(*[{x[0] for x in v} for v in r.values()]))
        if len(common) < 60:
            print(f"{tg}: premalo skupnih dni ({len(common)})")
            continue
        ae = {k: np.array([abs(p - y) for d, p, y in v if d in set(common)]) for k, v in r.items()}
        ref = ae["fixed"]
        bm = ae["single:best_match"]
        print(f"\n{tg.upper()}  (n = {len(common)} dni)   razlika = MAE(ref) − MAE(metoda), > 0 pomeni boljša od ref")
        print(f"{'metoda':<26}{'MAE':>6}  {'vs fixed':>9}  {'95 % interval':>16}  {'vs best_match':>13}")
        for k in sorted(ae, key=lambda k: ae[k].mean()):
            m, (lo, hi) = boot(ref - ae[k])
            m2, _ = boot(bm - ae[k])
            flag = "" if k == "fixed" else ("REAL+" if lo > 0 else "WORSE" if hi < 0 else "šum")
            print(f"{k:<26}{ae[k].mean():6.3f}  {m:+9.3f}  [{lo:+.3f}, {hi:+.3f}]  {m2:+13.3f}  {flag}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    since = args[0] if args else "2024-07-01"
    leads = (1, 2, 3)
    if "--lead" in sys.argv:
        leads = (int(sys.argv[sys.argv.index("--lead") + 1]),)
    for lead in leads:
        report(lead, since)


if __name__ == "__main__":
    main()
