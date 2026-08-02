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


def fetch_live_forecast():
    """Živa napoved Open-Meteo, urno, za danes + 3 dni naprej."""
    q = urllib.parse.urlencode({
        "latitude": mos.LAT, "longitude": mos.LON,
        "hourly": ",".join(mos.HOURLY_VARS),
        "timezone": mos.TZ,
        "forecast_days": 4,
    })
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


def load_model():
    with open(mos.MODEL_PATH, encoding="utf-8") as f:
        return json.load(f)


def predict_day(model, lead, feats):
    """Napoved enega dne. Vrne None, kadar model tega vodilnega časa nima —
    train_recica_mos.py vodilni čas izpusti, če ni prestal preverjanja."""
    entry = (model.get("leads") or {}).get(str(lead))
    if not entry:
        return None

    tvec = mos.temp_vector(feats)
    out = {}
    for target in ("tmax", "tmin"):
        coefs = entry["coefficients"].get(target)
        if not coefs:
            return None
        out[target] = round(mos.predict_linear(coefs, tvec), 1)
        out[f"{target}_sd"] = entry["residual_sd"].get(target)
        skill = (entry.get("skill") or {}).get(target) or {}
        out[f"{target}_mae"] = skill.get("mae_meteorec")

    pop_coefs = entry["coefficients"].get("pop")
    out["pop"] = round(mos.predict_prob(pop_coefs, mos.pop_vector(feats)), 2) if pop_coefs else None

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
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError, OSError) as e:
        print(f"✗ Open-Meteo ni dosegljiv ({e}) — napoved ni osvežena", file=sys.stderr)
        return 0

    today = dt.date.today()
    days = []
    for lead in mos.LEADS:
        target = (today + dt.timedelta(days=lead)).isoformat()
        series = rows.get(target)
        if not series:
            continue
        feats = mos.daily_features(series, target)
        if feats is None:
            continue
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
