#!/usr/bin/env python3
"""
tools/log_mtr_accuracy.py — dnevni log MTR proti surovemu Open-Meteo, D+1 in D+2.

/tocnost-napovedi/ (verify_forecasts.py) meri D+1, dan za dnem, in ga ne
podvajamo. Ta log je zanj dodatek, ne zamenjava: beleži tudi D+2 in piše v svojo
vrsto (data/mtr-accuracy-log.csv), iz katere tools/compute_mtr_accuracy_metrics.py
izračuna rolling 30-dnevni MAE za zavihek "Trendi" (/trendi/).

Napoved za oba vodilna časa je že v napoved-modela.json (piše ga
tools/predict_recica_mos.py, ki mora teči PRED tem skriptom) — tam je za vsak
dan tudi surovi Open-Meteo (om_tmax/om_tmin), zato tu ni novega zajema.

Dvostopenjsko, isti vzorec kot verify_forecasts.py:
  1. RESOLVE — čakajoče napovedi, katerih ciljni dan je zdaj v history.json,
     dobijo dejansko vrednost in gredo v trajni dnevnik (append-only CSV).
  2. LOG — nova napoved za D+1 in D+2 iz napoved-modela.json gre v čakalno
     vrsto, da se razreši čez 1 oz. 2 dni.

State:
  tools/.mtr_accuracy_pending.json  — čakajoče napovedi
  data/mtr-accuracy-log.csv         — razrešeni zapisi (javno, dodajanje samo)

Uporaba:
  python3 tools/log_mtr_accuracy.py
  python3 tools/log_mtr_accuracy.py --backfill   # enkraten uvoz D+1 iz
                                                  # forecast_verification.json
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDING_PATH = os.path.join(ROOT, "tools", ".mtr_accuracy_pending.json")
LOG_PATH = os.path.join(ROOT, "data", "mtr-accuracy-log.csv")
MODEL_FORECAST_PATH = os.path.join(ROOT, "napoved-modela.json")
HISTORY_PATH = os.path.join(ROOT, "history.json")
VERIFICATION_PATH = os.path.join(ROOT, "forecast_verification.json")

CSV_FIELDS = [
    "date", "lead", "made_at",
    "mtr_tmax", "mtr_tmin", "om_tmax", "om_tmin",
    "actual_tmax", "actual_tmin",
    "err_mtr_tmax", "err_mtr_tmin", "err_om_tmax", "err_om_tmin",
]
LEADS = (1, 2)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_history():
    return load_json(HISTORY_PATH, {})


def existing_keys():
    """(date, lead) parov, ki so že v CSV — prepreči podvojeno vrstico ob
    ponovnem zagonu istega dne."""
    keys = set()
    if not os.path.exists(LOG_PATH):
        return keys
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            keys.add((row["date"], int(row["lead"])))
    return keys


def err(pred, actual):
    if pred is None or actual is None:
        return None
    return round(abs(pred - actual), 2)


def append_rows(rows):
    if not rows:
        return
    is_new = not os.path.exists(LOG_PATH)
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if is_new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def resolve_pending(pending, hist, logged_keys):
    still_pending = []
    new_rows = []
    for entry in pending:
        target = entry["target_date"]
        lead = entry["lead"]
        actual = hist.get(target)
        if not actual or actual.get("src") not in ("station", "wu") or \
                actual.get("tempHigh") is None or actual.get("tempLow") is None:
            made = entry.get("made_at", target)
            try:
                age = (dt.date.today() - dt.date.fromisoformat(made)).days
            except ValueError:
                age = 0
            if age <= 7:
                still_pending.append(entry)
            continue

        if (target, lead) in logged_keys:
            continue

        actual_tmax, actual_tmin = actual["tempHigh"], actual["tempLow"]
        row = {
            "date": target, "lead": lead, "made_at": entry.get("made_at"),
            "mtr_tmax": entry.get("mtr_tmax"), "mtr_tmin": entry.get("mtr_tmin"),
            "om_tmax": entry.get("om_tmax"), "om_tmin": entry.get("om_tmin"),
            "actual_tmax": actual_tmax, "actual_tmin": actual_tmin,
            "err_mtr_tmax": err(entry.get("mtr_tmax"), actual_tmax),
            "err_mtr_tmin": err(entry.get("mtr_tmin"), actual_tmin),
            "err_om_tmax": err(entry.get("om_tmax"), actual_tmax),
            "err_om_tmin": err(entry.get("om_tmin"), actual_tmin),
        }
        new_rows.append(row)
        logged_keys.add((target, lead))
    return still_pending, new_rows


def log_new(pending, logged_keys, today_iso):
    data = load_json(MODEL_FORECAST_PATH, None)
    if not data:
        print("  ⚠ napoved-modela.json manjka — nič novega za zabeležiti.", file=sys.stderr)
        return pending, 0

    stamp = (data.get("generated_at") or "")[:10]
    if stamp != today_iso:
        print(f"  ⚠ napoved-modela.json je z dne {stamp or '?'}, ne od danes — preskočeno.",
              file=sys.stderr)
        return pending, 0

    pending_keys = {(e["target_date"], e["lead"]) for e in pending}
    added = 0
    for day in data.get("days", []):
        lead = day.get("lead")
        target = day.get("date")
        if lead not in LEADS or not target:
            continue
        key = (target, lead)
        if key in pending_keys or key in logged_keys:
            continue
        pending.append({
            "target_date": target, "lead": lead, "made_at": today_iso,
            "mtr_tmax": day.get("tmax"), "mtr_tmin": day.get("tmin"),
            "om_tmax": day.get("om_tmax"), "om_tmin": day.get("om_tmin"),
        })
        pending_keys.add(key)
        added += 1
    return pending, added


def backfill():
    """Enkraten uvoz obstoječih D+1 zapisov iz forecast_verification.json (že
    teče dan za dnem prek verify_forecasts.py) — da rolling graf na /trendi/ ne
    začne prazen, čeprav D+2 dnevnik šele od danes teče naprej."""
    verification = load_json(VERIFICATION_PATH, {})
    logged_keys = existing_keys()
    rows = []
    for target, record in sorted(verification.items()):
        meteorec = record.get("meteorec")
        om = record.get("open_meteo")
        actual = record.get("actual") or {}
        if not meteorec or meteorec.get("lead") != 1 or not om:
            continue
        if (target, 1) in logged_keys:
            continue
        actual_tmax, actual_tmin = actual.get("tmax"), actual.get("tmin")
        rows.append({
            "date": target, "lead": 1, "made_at": record.get("made_at"),
            "mtr_tmax": meteorec.get("tmax"), "mtr_tmin": meteorec.get("tmin"),
            "om_tmax": om.get("tmax"), "om_tmin": om.get("tmin"),
            "actual_tmax": actual_tmax, "actual_tmin": actual_tmin,
            "err_mtr_tmax": meteorec.get("err_tmax"), "err_mtr_tmin": meteorec.get("err_tmin"),
            "err_om_tmax": om.get("err_tmax"), "err_om_tmin": om.get("err_tmin"),
        })
        logged_keys.add((target, 1))
    append_rows(rows)
    print(f"--backfill: {len(rows)} D+1 vrstic uvoženih iz forecast_verification.json.")


def main():
    ap = argparse.ArgumentParser(description="Dnevni log MTR proti Open-Meteo (D+1, D+2).")
    ap.add_argument("--backfill", action="store_true",
                     help="enkraten uvoz obstoječih D+1 dni iz forecast_verification.json")
    args = ap.parse_args()

    if args.backfill:
        backfill()
        return 0

    today_iso = dt.date.today().isoformat()
    hist = load_history()
    pending = load_json(PENDING_PATH, [])
    logged_keys = existing_keys()

    still_pending, new_rows = resolve_pending(pending, hist, logged_keys)
    append_rows(new_rows)
    print(f"[{today_iso}] Razrešenih zapisov: {len(new_rows)}, v čakalni vrsti: {len(still_pending)}")

    still_pending, added = log_new(still_pending, logged_keys, today_iso)
    if added:
        print(f"  Zabeleženih novih napovedi: {added}")

    save_json(PENDING_PATH, still_pending)
    return 0


if __name__ == "__main__":
    sys.exit(main())
