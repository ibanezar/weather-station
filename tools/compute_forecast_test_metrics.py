#!/usr/bin/env python3
"""
tools/compute_forecast_test_metrics.py — Faza 3 v brief-u za /test-napovedi/.

Vzame data/forecast-archive.csv (napovedi po viru/modelu/vodilnem času, zgradi
ga tools/build_forecast_archive.py) in history.json (dejanske meritve IREICA1)
in izračuna:
  - MAE, bias, RMSE, delež dni z napako >3 °C — za Tmax in Tmin, ločeno po
    (model, lead_days)
  - kontingenčno tabelo za padavine (prag 0,2 mm in 5 mm) -> POD, FAR, CSI, bias ratio
  - dve izhodišči (baseline): klimatologija (povprečje za koledarski dan ±7 dni,
    iz cele postajne zgodovine) in persistenca ("jutri = danes")
  - skill score = 1 − MAE_model / MAE_klimatologija, po (model, lead_days)

QC meritev (Faza 1c): uporabljene so samo vrstice iz history.json s
src "station" ali "wu" (prava postaja, isti fizični senzor — "wu" je zgolj
starejša pot nalaganja prek Weather Underground, glej update_history.py).
Dnevi z izpuščenim Tmax/Tmin ali fizikalno nemogočo vrednostjo (Tmax<Tmin,
izven [-25, 45] °C) so zavrnjeni. Vrzeli/zataknjen senzor na urni ravni NISO
preverjeni tu — history.json je dnevni agregat; ta nadzor že delno velja
implicitno (nepopoln dan brez vseh REQUIRED polj v update_history.py sploh ne
postane "station" zapis), toda eksplicitno urno preverjanje ">10 % manjkajočih"
in "zataknjen senzor >6h" na tem arhivu ni izvedljivo brez ločenega urnega
zajema — glej opombo v izpisu.

Piše data/test-napovedi.json (Faza 4 izhod) in izpiše surove številke na
stdout (korak 5 v "Vrstnem redu dela" brief-a: ustavi se tu, preden greš na
frontend).

Usage:
  python3 tools/compute_forecast_test_metrics.py
"""
import csv, datetime, json, os, statistics as st, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_PATH = os.path.join(ROOT, "data", "forecast-archive.csv")
FORWARD_LOG_PATH = os.path.join(ROOT, "data", "forecast-forward-log.csv")
HISTORY_PATH = os.path.join(ROOT, "history.json")
OUT_PATH = os.path.join(ROOT, "data", "test-napovedi.json")

# Pet virov z arhivom vodilnega časa nazaj (Open-Meteo Previous Runs API) —
# glavna primerjava na strani, dovolj dolga zgodovina za zanesljiv rezultat.
MODEL_LABELS = {
    "ecmwf_ifs025": "ECMWF IFS",
    "icon_seamless": "ICON",
    "gfs_seamless": "GFS",
    "meteofrance_arpege_europe": "ARPEGE",
    "best_match": "Best Match",
}
# ARSO in Yr/MET Norway nimata arhiva preteklih napovedi (Faza 1b) -- beležimo
# ju sproti (tools/log_forward_forecasts.py) od datuma prvega zagona naprej.
# Stran ju prikaže ločeno, dokler nimata dovolj razrešenih dni.
FORWARD_LABELS = {
    "arso": "ARSO",
    "yr": "Yr (MET Norway)",
}
LEADS = list(range(1, 8))
CLIMO_WINDOW = 7      # +/- dni okoli koledarskega dne za klimatologijo
MIN_CLIMO_SAMPLES = 15
WET_THRESHOLDS = (0.2, 5.0)


def load_observations():
    """history.json -> {date: {tmax, tmin, precip}} samo za QC-veljavne dni prave postaje."""
    hist = json.load(open(HISTORY_PATH, encoding="utf-8"))
    obs = {}
    rejected = []
    for d, v in hist.items():
        if v.get("src") not in ("station", "wu"):
            continue
        tmax, tmin, precip = v.get("tempHigh"), v.get("tempLow"), v.get("precipTotal")
        if tmax is None or tmin is None:
            rejected.append((d, "manjka Tmax/Tmin"))
            continue
        if tmax < tmin:
            rejected.append((d, f"Tmax<Tmin ({tmax}<{tmin})"))
            continue
        if not (-25 <= tmax <= 45) or not (-25 <= tmin <= 45):
            rejected.append((d, f"izven fizikalnega obsega ({tmin}..{tmax})"))
            continue
        obs[d] = {"tmax": tmax, "tmin": tmin, "precip": precip if precip is not None else 0.0}
    return obs, rejected


def load_forecasts():
    """Bere data/forecast-archive.csv (arhivsko, pet Open-Meteo virov) IN
    data/forecast-forward-log.csv (sprotno, ARSO/Yr — če datoteka že obstaja).
    Ista shema vrstic, zato gresta v isti slovar."""
    rows = defaultdict(list)  # (model, lead) -> list of rows
    for path in (ARCHIVE_PATH, FORWARD_LOG_PATH):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                r["lead_days"] = int(r["lead_days"])
                r["tmax_c"] = float(r["tmax_c"]) if r["tmax_c"] not in ("", None) else None
                r["tmin_c"] = float(r["tmin_c"]) if r["tmin_c"] not in ("", None) else None
                r["precip_mm"] = float(r["precip_mm"]) if r["precip_mm"] not in ("", None) else None
                rows[(r["model"], r["lead_days"])].append(r)
    return rows


def doy(date_str):
    return datetime.date.fromisoformat(date_str).timetuple().tm_yday


def build_climatology(obs):
    """Za vsak koledarski dan (1..366): povprečni Tmax/Tmin iz vseh let znotraj
    okna CLIMO_WINDOW dni (krožno čez novo leto)."""
    by_doy_tmax = defaultdict(list)
    by_doy_tmin = defaultdict(list)
    for d, v in obs.items():
        by_doy_tmax[doy(d)].append(v["tmax"])
        by_doy_tmin[doy(d)].append(v["tmin"])

    climo = {}
    for target in range(1, 367):
        tmax_vals, tmin_vals = [], []
        for off in range(-CLIMO_WINDOW, CLIMO_WINDOW + 1):
            k = ((target - 1 + off) % 366) + 1
            tmax_vals.extend(by_doy_tmax.get(k, []))
            tmin_vals.extend(by_doy_tmin.get(k, []))
        climo[target] = {
            "tmax": st.mean(tmax_vals) if len(tmax_vals) >= MIN_CLIMO_SAMPLES else None,
            "tmin": st.mean(tmin_vals) if len(tmin_vals) >= MIN_CLIMO_SAMPLES else None,
            "n": len(tmax_vals),
        }
    return climo


def climo_predict(climo, date_str):
    c = climo.get(doy(date_str))
    if not c:
        return None, None
    return c["tmax"], c["tmin"]


def persistence_predict(obs, date_str):
    prev = (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=1)).isoformat()
    p = obs.get(prev)
    if not p:
        return None, None
    return p["tmax"], p["tmin"]


def err_stats(errs):
    if not errs:
        return {"n": 0}
    abs_errs = [abs(e) for e in errs]
    return {
        "n": len(errs),
        "mae": round(st.mean(abs_errs), 2),
        "bias": round(st.mean(errs), 2),
        "rmse": round((st.mean(e * e for e in errs)) ** 0.5, 2),
        "pct_gt3": round(100 * sum(1 for e in abs_errs if e > 3) / len(abs_errs), 1),
    }


def contingency(pairs, thr):
    hit = fa = miss = cn = 0
    for pred, act in pairs:
        p, a = pred >= thr, act >= thr
        if p and a: hit += 1
        elif p and not a: fa += 1
        elif not p and a: miss += 1
        else: cn += 1
    n = hit + fa + miss + cn
    if n == 0:
        return None
    pod = hit / (hit + miss) if (hit + miss) else None
    far = fa / (hit + fa) if (hit + fa) else None
    csi = hit / (hit + fa + miss) if (hit + fa + miss) else None
    bias_ratio = (hit + fa) / (hit + miss) if (hit + miss) else None
    return {
        "n": n, "hit": hit, "false_alarm": fa, "miss": miss, "correct_negative": cn,
        "pod": round(pod, 3) if pod is not None else None,
        "far": round(far, 3) if far is not None else None,
        "csi": round(csi, 3) if csi is not None else None,
        "bias_ratio": round(bias_ratio, 3) if bias_ratio is not None else None,
    }


def main():
    obs, rejected = load_observations()
    fc_by_key = load_forecasts()
    climo = build_climatology(obs)

    print(f"Meritve (QC): {len(obs)} veljavnih dni, {len(rejected)} zavrnjenih.")
    if rejected:
        for d, why in rejected[:10]:
            print(f"    zavrnjen {d}: {why}")
        if len(rejected) > 10:
            print(f"    ... in še {len(rejected) - 10}")
    print("  Opomba: QC tu deluje na dnevnih agregatih (history.json). Urno "
          "preverjanje '>10 % manjkajočih ur' in 'zataknjen senzor >6h' zahteva "
          "ločen urni zajem in ni del tega prehoda — Ecowitt API za ta račun "
          "vrača polno 5-min ločljivost le za zadnjih ~90 dni, starejši dnevi "
          "so na strežniku že podvzorčeni (6 točk/dan), zato jih ni mogoče "
          "naknadno urno preveriti.")

    # ── Climatology & persistence kot samostojna "vira" (isto merilo) ──────
    climo_errs_tmax, climo_errs_tmin = [], []
    pers_errs_tmax, pers_errs_tmin = [], []
    for d, o in obs.items():
        ctmax, ctmin = climo_predict(climo, d)
        if ctmax is not None:
            climo_errs_tmax.append(ctmax - o["tmax"])
        if ctmin is not None:
            climo_errs_tmin.append(ctmin - o["tmin"])
        ptmax, ptmin = persistence_predict(obs, d)
        if ptmax is not None:
            pers_errs_tmax.append(ptmax - o["tmax"])
        if ptmin is not None:
            pers_errs_tmin.append(ptmin - o["tmin"])

    climo_stats = {"tmax": err_stats(climo_errs_tmax), "tmin": err_stats(climo_errs_tmin)}
    pers_stats = {"tmax": err_stats(pers_errs_tmax), "tmin": err_stats(pers_errs_tmin)}

    print(f"\nKlimatologija (izhodišče): Tmax MAE={climo_stats['tmax'].get('mae')} °C "
          f"(n={climo_stats['tmax'].get('n')}), Tmin MAE={climo_stats['tmin'].get('mae')} °C")
    print(f"Persistenca ('jutri=danes'): Tmax MAE={pers_stats['tmax'].get('mae')} °C "
          f"(n={pers_stats['tmax'].get('n')}), Tmin MAE={pers_stats['tmin'].get('mae')} °C")

    # ── Po (model, lead_days) ───────────────────────────────────────────────
    def score_source(model):
        """Izračuna results[model] za vse vodilne čase; vrne (per_lead, zero_crossing_lead, n_total)."""
        per_lead = {}
        zero_lead = None
        n_total = 0
        for lead in LEADS:
            rows = fc_by_key.get((model, lead), [])
            pairs_tmax, pairs_tmin = [], []
            precip_pairs = []
            for r in rows:
                o = obs.get(r["valid_at"])
                if not o:
                    continue
                if r["tmax_c"] is not None:
                    pairs_tmax.append(r["tmax_c"] - o["tmax"])
                if r["tmin_c"] is not None:
                    pairs_tmin.append(r["tmin_c"] - o["tmin"])
                if r["precip_mm"] is not None:
                    precip_pairs.append((r["precip_mm"], o["precip"]))

            tmax_stats = err_stats(pairs_tmax)
            tmin_stats = err_stats(pairs_tmin)
            precip_ct = {str(t): contingency(precip_pairs, t) for t in WET_THRESHOLDS}
            n_total += tmax_stats.get("n", 0)

            skill_tmax = None
            if tmax_stats.get("mae") is not None and climo_stats["tmax"].get("mae"):
                skill_tmax = round(1 - tmax_stats["mae"] / climo_stats["tmax"]["mae"], 3)
                if skill_tmax <= 0 and zero_lead is None:
                    zero_lead = lead

            per_lead[lead] = {
                "tmax": tmax_stats, "tmin": tmin_stats,
                "precip_contingency": precip_ct,
                "skill_tmax_vs_climatology": skill_tmax,
            }
            if tmax_stats.get("n"):
                print("{:<16} {:>4}  {:>6}  {:>7} {:>7} {:>7} {:>6}   {:>7} {:>7} {:>7} {:>6}   {:>7}".format(
                    model, lead, tmax_stats["n"],
                    tmax_stats.get("mae"), tmax_stats.get("bias"), tmax_stats.get("rmse"), tmax_stats.get("pct_gt3"),
                    tmin_stats.get("mae"), tmin_stats.get("bias"), tmin_stats.get("rmse"), tmin_stats.get("pct_gt3"),
                    skill_tmax))
        return per_lead, zero_lead, n_total

    print("\n{:<16} {:>4}  {:>6}  {:>7} {:>7} {:>7} {:>6}   {:>7} {:>7} {:>7} {:>6}   {:>7}".format(
        "model", "lead", "n", "MAE_tx", "bias_tx", "RMSE_tx", ">3°C%",
        "MAE_tn", "bias_tn", "RMSE_tn", ">3°C%", "skill_tx"))

    results = {}
    zero_crossing = {}
    compared_dates = set()
    for model in MODEL_LABELS:
        per_lead, zero_lead, _ = score_source(model)
        results[model] = per_lead
        if zero_lead is not None:
            zero_crossing[model] = zero_lead
        for lead in LEADS:
            for r in fc_by_key.get((model, lead), []):
                if r["valid_at"] in obs:
                    compared_dates.add(r["valid_at"])
    n_compared_days = len(compared_dates)
    print(f"\nDatumi z vsaj eno primerjavo (kateri koli vir/vodilni čas): {n_compared_days}")

    print("\nDan, ko napoved (Tmax) pade na raven klimatologije (skill <= 0):")
    for model in MODEL_LABELS:
        lead = zero_crossing.get(model)
        print(f"  {MODEL_LABELS[model]:<16} {'D+' + str(lead) if lead else 'ni doseženo v D+1..D+7 vzorcu'}")

    # ARSO in Yr -- sprotno beleženje od tools/log_forward_forecasts.py, brez
    # arhiva nazaj (Faza 1b). Vseeno gresta skozi isto merilo, samo n_total
    # pove strani, ali je smiselno prikazati številke ali samo "zbiranje se
    # je začelo" (isto besedilo kot tocnost-napovedi ob n_days==0).
    print("\nSprotno beleženi viri (ARSO, Yr) -- brez arhiva za nazaj:")
    forward_results = {}
    forward_n = {}
    for model in FORWARD_LABELS:
        per_lead, _, n_total = score_source(model)
        forward_results[model] = per_lead
        forward_n[model] = n_total
        print(f"  {FORWARD_LABELS[model]:<16} {n_total} razrešenih napovedi (vseh vodilnih časov skupaj)")

    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "n_obs_days": len(obs),
        "n_obs_rejected": len(rejected),
        "n_compared_days": n_compared_days,
        "climatology": climo_stats,
        "persistence": pers_stats,
        "models": MODEL_LABELS,
        "results": results,
        "zero_crossing_lead_days": zero_crossing,
        "forward_models": FORWARD_LABELS,
        "forward_results": forward_results,
        "forward_n": forward_n,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✓ {OUT_PATH} zapisan.")


if __name__ == "__main__":
    main()
