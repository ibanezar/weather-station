#!/usr/bin/env python3
"""
tools/predict_recica_mos.py — dnevna napoved MTR, lastnega modela za Rečico.

Vzame koeficiente iz model/recica-mos.json (nauči jih tools/train_recica_mos.py),
pobere živo napoved Open-Meteo in jo prevede v napoved za dno doline: Tmax, Tmin
in verjetnost padavin za D+1 do D+3.

Količine padavin namenoma ne popravljamo — poskus je pokazal ~5 % izboljšave, kar
je v okviru šuma. Količina, ki jo zapišemo, je surova vrednost Open-Meteo in je
tako tudi označena.

Značilke gradi ista funkcija kot učenje (`train_recica_mos.daily_features`).
Dva ločena prepisa bi se prej ali slej razšla in model bi tiho dobival druge
vhode, kot jih pozna — zato uvoz in ne kopija.

Izhod: napoved-modela.json v korenu (javna, bere jo kartica v app.js in
tools/verify_forecasts.py, ki napoved vpiše na semafor točnosti).

Uporaba:
  python3 tools/predict_recica_mos.py
  python3 tools/predict_recica_mos.py --no-write
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_recica_mos as mos  # noqa: E402

ROOT = mos.ROOT
OUT_PATH = os.path.join(ROOT, "napoved-modela.json")
UA = mos.UA


def fetch_live_forecast(model_id=None):
    """Živa napoved Open-Meteo, urno, za danes + 3 dni naprej. Brez `model_id`
    je to privzeti seamless; z njim en sam imenovan model (AIFS), kadar se je
    model učil z drugim vhodom."""
    params = {
        "latitude": mos.LAT, "longitude": mos.LON,
        "hourly": ",".join(mos.HOURLY_VARS),
        "timezone": mos.TZ,
        "forecast_days": 4,
    }
    if model_id:
        params["models"] = model_id
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request("https://api.open-meteo.com/v1/forecast?" + q, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)

    rows = {}
    h = data.get("hourly") or {}
    times = h.get("time") or []
    for i, ts in enumerate(times):
        day, hour = ts[:10], int(ts[11:13])
        rec = rows.setdefault(day, {v: [] for v in mos.HOURLY_VARS})
        for v in mos.HOURLY_VARS:
            series = h.get(v) or []
            val = series[i] if i < len(series) else None
            if val is not None:
                rec[v].append((hour, val))
    return rows


# Frost-night probability: P(Tmin <= 0 C) = Phi(-tmin / (K * sd)). The card's sd is the
# in-sample residual sd, ~5-15 % below the out-of-sample one, hence K. Walk-forward check
# (tools/ai/eval_frost.py, 366 days, 99 frost nights): Brier 0.066-0.077 vs 0.197 climatology.
FROST_SD_K = 1.15
# The band on the card is pred +- 1.2816 * sd, labelled P10-P90. With the in-sample sd it
# covered 76-81 % of unseen days (366-day walk-forward, tools/ai/eval_mtr_calibration.py);
# x1.05 gives 78-84 %, closest to the nominal 80 %. Applied here, not in training, so the
# model file keeps the raw residual sd. p_frost uses the raw sd with its own factor above.
SD_OOS_K = 1.05
# Night regime (backtest: MTR minus Open-Meteo Tmin was -1.5 C on clear calm nights,
# -0.5 C on overcast ones; observed minus Open-Meteo agreed: -1.5 / -0.8).
CLEAR_CLOUD_N, CALM_WIND_N, OVERCAST_CLOUD_N = 30, 8, 70


def frost_probability(tmin, sd, k=FROST_SD_K):
    """Probability that the night minimum is <= 0 C, from the normal approximation."""
    if tmin is None or not sd or sd <= 0:
        return None
    return 0.5 * (1 + math.erf((0.0 - tmin) / (k * sd) / math.sqrt(2)))


def night_regime(cloud_n, wind_n):
    """'clear_calm' | 'overcast' | 'mixed' - the codes the card turns into a sentence."""
    if cloud_n < CLEAR_CLOUD_N and wind_n < CALM_WIND_N:
        return "clear_calm"
    if cloud_n > OVERCAST_CLOUD_N:
        return "overcast"
    return "mixed"


def fetch_live_multi(models):
    """{day: {"tmax": {model: v}, "tmin": {model: v}}} iz žive napovedi drugih modelov.
    Dnevni ekstrem iz urnih vrednosti po lokalnem času (kot arhiv napovedi); model, ki
    ga ni mogoče prebrati, preprosto manjka (multi_vector ga obravnava kot nevtralnega)."""
    out = {}
    for m in models:
        try:
            rows = fetch_live_forecast(m)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, OSError) as e:
            print(f"  ⚠ model {m} ni dosegljiv ({e}) — izpuščen", file=sys.stderr)
            continue
        for day, series in rows.items():
            temp = [v for _, v in (series.get("temperature_2m") or [])]
            if len(temp) < 20:
                continue
            e = out.setdefault(day, {"tmax": {}, "tmin": {}})
            e["tmax"][m] = max(temp)
            e["tmin"][m] = min(temp)
    return out


def load_model():
    with open(mos.MODEL_PATH, encoding="utf-8") as f:
        return json.load(f)


def predict_day(model, lead, feats):
    """Napoved enega dne. Vrne None, kadar model tega vodilnega časa nima —
    train_recica_mos.py vodilni čas izpusti, če ni prestal preverjanja."""
    entry = (model.get("leads") or {}).get(str(lead))
    if not entry:
        return None

    with_aifs = bool(model.get("uses_aifs"))
    # Slovar po cilju, ne en sam bool — model se lahko za tmax/tmin uči z
    # različnimi zastavicami (glej --use-bias-tmax/--use-bias-tmin v
    # train_recica_mos.py).
    uses_bias = model.get("uses_bias_features") or {}
    uses_cond = model.get("uses_cond_features") or {}
    out = {}
    raw_sds = {}
    for target in ("tmax", "tmin"):
        coefs = entry["coefficients"].get(target)
        if not coefs:
            return None
        tvec = mos.temp_vector(feats, target, with_aifs,
                               bool(uses_bias.get(target)), bool(uses_cond.get(target)),
                               bool((model.get("uses_multi_features") or {}).get(target)))
        out[target] = round(mos.predict_linear(coefs, tvec), 1)
        raw_sd = entry["residual_sd"].get(target)
        out[f"{target}_sd"] = round(raw_sd * SD_OOS_K, 2) if raw_sd else raw_sd
        raw_sds[target] = raw_sd
        skill = (entry.get("skill") or {}).get(target) or {}
        out[f"{target}_mae"] = skill.get("mae_meteorec")
        out[f"{target}_improvement_pct"] = skill.get("improvement_pct")

    pop_coefs = entry["coefficients"].get("pop")
    out["pop"] = round(mos.predict_prob(pop_coefs, mos.pop_vector(feats, with_aifs)), 2) if pop_coefs else None

    p_frost = frost_probability(out["tmin"], raw_sds.get("tmin"))
    out["p_frost"] = round(p_frost, 2) if p_frost is not None else None
    out["night_regime"] = night_regime(feats["cloud_n"], feats["wind_n"])

    # Surovi Open-Meteo za primerjavo — kartica prikaže razliko, ker je prav ta
    # razlika tisto, kar je model prispeval.
    out["om_tmax"] = round(feats["om_tmax"], 1)
    out["om_tmin"] = round(feats["om_tmin"], 1)
    out["om_precip"] = round(feats["om_prec"], 1)
    out["d_tmax"] = round(out["tmax"] - out["om_tmax"], 1)
    out["d_tmin"] = round(out["tmin"] - out["om_tmin"], 1)
    return out


def main():
    ap = argparse.ArgumentParser(description="Napoved lokalnega MOS modela.")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    try:
        model = load_model()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"✗ Modela ni mogoče prebrati ({e}) — najprej poženi "
              f"tools/train_recica_mos.py", file=sys.stderr)
        return 0  # CI naj zaradi tega ne pade; prejšnja napoved ostane

    try:
        rows = fetch_live_forecast()
        # Model, naučen z drugim vhodom, ga mora dobiti tudi v napovedi — sicer
        # bi mu manjkale značilke, ki jih ima v koeficientih.
        aifs_rows = fetch_live_forecast(model.get("aifs_model") or mos.AIFS_MODEL) \
            if model.get("uses_aifs") else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError) as e:
        print(f"✗ Open-Meteo ni dosegljiv ({e}) — napoved ni osvežena", file=sys.stderr)
        return 0

    today = dt.date.today()

    # Avtokorelirana pristranskost (err_lag1/ma3/ma7, glej train_recica_mos.
    # build_bias_series/err_stats): pri živi napovedi je "danes" izdaja za VSE
    # vodilne čase hkrati, zato zadošča en majhen izsek D+1 arhiva za zadnjih
    # ~10 dni (dovolj za ma7 + varnostna rezerva), ne glede na to, koliko
    # vodilnih časov napovedujemo.
    bias_series = None
    if any((model.get("uses_bias_features") or {}).values()):
        try:
            hist = mos.load_history()
            b_start = (today - dt.timedelta(days=10)).isoformat()
            b_end = (today - dt.timedelta(days=1)).isoformat()
            lead1_rows = mos.fetch_archived_forecasts(1, b_start, b_end)
            bias_series = mos.build_bias_series(lead1_rows, hist)
        except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, json.JSONDecodeError, OSError, FileNotFoundError) as e:
            print(f"✗ Arhiv za pristranskost ni dosegljiv ({e}) — napoved ni osvežena",
                  file=sys.stderr)
            return 0

    multi_live = None
    if any((model.get("uses_multi_features") or {}).values()):
        multi_live = fetch_live_multi(model.get("multi_models") or mos.MULTI_MODELS)
        if not any(len(v["tmax"]) >= 2 for v in multi_live.values()):
            print("✗ Drugi modeli niso dosegljivi (model je naučen z njimi) — napoved ni osvežena",
                  file=sys.stderr)
            return 0

    days = []
    for lead in mos.LEADS:
        target = (today + dt.timedelta(days=lead)).isoformat()
        series = rows.get(target)
        if not series:
            continue
        feats = mos.daily_features(series, target)
        if feats is None:
            continue
        if aifs_rows is not None:
            feats = mos.merge_aifs(feats, mos.daily_features(aifs_rows.get(target) or {}, target))
            if feats is None:
                continue
        if bias_series is not None:
            for t in ("tmax", "tmin"):
                lag1, ma3, ma7, missing = mos.err_stats(bias_series[t], target, lead)
                feats[f"err_lag1_{t}"] = lag1
                feats[f"err_ma3_{t}"] = ma3
                feats[f"err_ma7_{t}"] = ma7
                feats[f"is_err_missing_{t}"] = missing
        if multi_live is not None:
            feats["mm"] = multi_live.get(target)
            if not feats["mm"] or len(feats["mm"]["tmax"]) < 2:
                continue    # premalo drugih modelov za ta dan
        pred = predict_day(model, lead, feats)
        if pred is None:
            continue
        pred["date"] = target
        pred["lead"] = lead
        days.append(pred)

    if not days:
        print("✗ Ni bilo mogoče izračunati nobenega dne.", file=sys.stderr)
        return 0

    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": model.get("model_version"),
        "trained_at": model.get("trained_at"),
        "train_range": model.get("train_range"),
        "station": model.get("station"),
        "note": ("MTR (Meteorec) — poskusni lokalni model (MOS): Open-Meteo kot vhod, "
                 "popravek za dno doline naučen na meritvah postaje. Količina padavin je "
                 "surova vrednost Open-Meteo — te MTR ne popravlja."),
        "days": days,
    }

    for d in days:
        print(f"  {d['date']} (D+{d['lead']}): {d['tmax']} / {d['tmin']} °C "
              f"(Open-Meteo {d['om_tmax']} / {d['om_tmin']}, razlika "
              f"{d['d_tmax']:+.1f} / {d['d_tmin']:+.1f}), dež {int((d['pop'] or 0) * 100)} %")

    if args.no_write:
        print("(--no-write: datoteka ni zapisana)")
        return 0

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"→ {os.path.relpath(OUT_PATH, ROOT)}: {len(days)} dni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
