#!/usr/bin/env python3
"""
tools/predict_sneg_mos.py -- živa napoved MTR sneg (proksi) za D+1..D+5 in beleženje v dnevnik.

Vzame model/sneg-mos.json (tools/train_sneg_mos.py), živo napoved štirih modelov Open-Meteo
(isti `fetch_live_multi` kot MTR) in zapiše:
  napoved-snega.json         -- zadnja napoved (SAMO podatek; nobena stran je še ne prikazuje)
  data/sneg-forward-log.csv  -- vsaka osvežitev se doda (issued_at, valid_at), za pošteno preverjanje naprej

Verjetnost pomeni: »dan s padavinami pri hladnem zraku« (proksi), NE opazovan sneg in NE debelina snega.
Glej train_sneg_mos.py. Zunaj sezone (oktober-april) napovedi ni; datoteka se enkrat na dan zapiše s
praznim seznamom, da varuh svežine ne javi okvare.

Uporaba:
  python3 tools/predict_sneg_mos.py
  python3 tools/predict_sneg_mos.py --no-write
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_sneg_mos as tsm  # noqa: E402

ROOT = tsm.ROOT
OUT_PATH = os.path.join(ROOT, "napoved-snega.json")
LOG_PATH = os.path.join(ROOT, "data", "sneg-forward-log.csv")
LOG_FIELDS = ["issued_at", "valid_at", "lead_days", "hours_before", "p_snow", "p_proxy", "tavg", "prec_mm",
              "n_models", "model_version"]
LJ = ZoneInfo("Europe/Ljubljana")
NOTE = ("MTR sneg -- POSKUSNI model. p_snow = možnost merljivega snega (nov sneg >= 1 cm ob jutranjem odčitku) na ARSO postaji Gornji Grad "
        "(428 m, 9 km od Rečice); model je naučen na opazovanjih te postaje 2019-2026 (Vir: Agencija Republike Slovenije za okolje). "
        "stations = enaka ocena za druge postaje v dolini (Luče, Radegunda 794 m, Solčava). "
        "p_proxy = verjetnost »mokrega hladnega dne« v Rečici (padavine >= 0,2 mm in T povp. <= 1 °C), na katerem je naučen osnovni model. "
        "Postaja Meteorec snega ne meri; ni napoved debeline snega, ni uradno opozorilo.")


def load_model(path=tsm.MODEL_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_models(models):
    """{datum: {model: (tmax, tmin, padavine)}} iz žive napovedi (kot MTR: dnevni ekstrem po lokalnem času)."""
    import predict_recica_mos as pm   # uvoz šele tu: potegne train_recica_mos, test ga ne rabi
    raw = pm.fetch_live_multi(models, forecast_days=max(tsm.LEADS) + 2)   # +2: danes in rezerva
    out = {}
    for day, e in raw.items():
        for m in models:
            if m in e["tmax"] and m in e["tmin"] and m in (e.get("prec") or {}):
                out.setdefault(day, {})[m] = (e["tmax"][m], e["tmin"][m], e["prec"][m])
    return out


def predict_days(model, per_day, today):
    days = []
    for lead in tsm.LEADS:
        entry = (model.get("leads") or {}).get(str(lead))
        target = today + dt.timedelta(days=lead)
        if not entry or target.month not in model.get("season_months", tsm.SEASON):
            continue
        f = tsm.day_features(per_day.get(target.isoformat()) or {})
        if f is None:
            continue
        pp = tsm.predict_p(entry, f)
        po = tsm.predict_obs(entry, f)
        stations = {tsm.VALLEY_STATIONS[sid]["name"]: round(p, 3)
                    for sid, p in tsm.predict_obs_stations(entry, f).items() if sid in tsm.VALLEY_STATIONS}
        days.append({
            "date": target.isoformat(), "lead": lead,
            "p_snow": round(po if po is not None else pp, 3), "p_proxy": round(pp, 2),
            "basis": "observed" if po is not None else "proxy", "stations": stations,
            "tavg": round(f["tavg"], 1), "prec_mm": round(f["prec"], 1), "n_models": f["n_models"],
        })
    return days


def append_log(payload, path=LOG_PATH, now=None):
    issued = payload["generated_at"]
    now = now or dt.datetime.strptime(issued, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    seen = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            old_rows = list(csv.DictReader(f))
        seen = {(r["issued_at"], r["valid_at"]) for r in old_rows}
        if old_rows and set(old_rows[0].keys()) != set(LOG_FIELDS):      # nov stolpec (p_proxy): preseli star zapis
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
                w.writeheader()
                for r in old_rows:
                    w.writerow({k: r.get(k, "") for k in LOG_FIELDS})
    rows = []
    for d in payload["days"]:
        if (issued, d["date"]) in seen:
            continue
        start = dt.datetime.combine(dt.date.fromisoformat(d["date"]), dt.time(0, 0), tzinfo=LJ)
        rows.append({"issued_at": issued, "valid_at": d["date"], "lead_days": d["lead"],
                     "hours_before": round((start - now).total_seconds() / 3600, 1),
                     "p_snow": d["p_snow"], "p_proxy": d["p_proxy"], "tavg": d["tavg"], "prec_mm": d["prec_mm"],
                     "n_models": d["n_models"], "model_version": payload["model_version"]})
    if not rows:
        return 0
    new_file = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def heartbeat_due(path, today_iso):
    """Zunaj sezone zapišemo prazno datoteko največ enkrat na dan (varuh svežine)."""
    try:
        old = json.load(open(path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    return not (old.get("in_season") is False and str(old.get("generated_at", ""))[:10] == today_iso)


def build_payload(model, days, in_season, now):
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": model.get("model_version"),
        "trained_at": model.get("trained_at"),
        "in_season": in_season,
        "target": model.get("target"),
        "note": NOTE,
        "days": days,
    }


def main():
    ap = argparse.ArgumentParser(description="Živa napoved MTR sneg (proksi).")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--log", default=LOG_PATH)
    args = ap.parse_args()

    try:
        model = load_model()
    except (OSError, json.JSONDecodeError) as e:
        print(f"✗ Modela ni mogoče prebrati ({e}) -- najprej poženi tools/train_sneg_mos.py", file=sys.stderr)
        return 0   # CI naj zaradi tega ne pade
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(LJ).date()
    season = model.get("season_months", tsm.SEASON)
    # Sezona je presoja ciljnih dni: v zadnjih dneh aprila je D+1 še v sezoni, D+3 že ne.
    in_season = any((today + dt.timedelta(days=l)).month in season for l in tsm.LEADS)

    if not in_season:
        if not args.no_write and heartbeat_due(args.out, now.strftime("%Y-%m-%d")):
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(build_payload(model, [], False, now), f, ensure_ascii=False, indent=2)
                f.write("\n")
            print("Zunaj sezone: zapisana prazna datoteka (utrip).")
        else:
            print("Zunaj sezone: nič za napovedati.")
        return 0

    try:
        per_day = fetch_models(model.get("models") or tsm.MODELS)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as e:
        print(f"✗ Open-Meteo ni dosegljiv ({e}) -- napoved ni osvežena", file=sys.stderr)
        return 0
    days = predict_days(model, per_day, today)
    if not days:
        print("✗ Premalo modelov za noben dan -- napoved ni osvežena", file=sys.stderr)
        return 0
    payload = build_payload(model, days, True, now)
    for d in days:
        print(f"  {d['date']} (D+{d['lead']}): merljiv sneg {int(round(d['p_snow'] * 100))} % (proksi {int(round(d['p_proxy'] * 100))} %) "
              f"[T povp. modelov {d['tavg']} °C, padavine {d['prec_mm']} mm, modelov {d['n_models']}]")
    if args.no_write:
        print("(--no-write)")
        return 0
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"→ {os.path.relpath(args.out, ROOT)}: {len(days)} dni")
    try:
        print(f"→ {os.path.relpath(args.log, ROOT)}: {append_log(payload, args.log, now)} vrstic")
    except (OSError, ValueError, KeyError) as e:       # dnevnik je dodatek, ne pogoj
        print(f"⚠ dnevnik ni zapisan ({e})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
