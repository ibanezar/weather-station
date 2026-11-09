#!/usr/bin/env python3
"""
tools/verify_sneg.py -- preverjanje MTR sneg (proksi) proti meritvam postaje, NAPREJ v času.

Primerja zabeležene napovedi (data/sneg-forward-log.csv) z dejanskim proksijem (padavine in T povp. iz
history.json, dnevi `era5` se ne štejejo). To je edino pošteno merilo: model je učen na arhivu napovedi,
ta skript meri samo napovedi, nastale po uvedbi.

Za vsak (ciljni dan, vodilni čas) vzame najzgodnejšo izdajo v svojem razredu (vodilni čas = ceil(hours_before/24)),
ker je model učen na napovedi izpred N dni (previous_dayN), ne na napovedi tik pred dogodkom.

Preverjata se DVE napovedi (data/sneg-verification.json):
  leads -- p_proxy (»mokri hladni dan« v Rečici): resnica je postaja IREICA1.
  snow  -- p_snow (od v0.4: nov sneg >= 1 cm na ARSO postaji Gornji Grad): resnica so serije data/arso-sneg-postaje/daily-1748.json, ki jih
           osvežuje tools/refresh_arso_sneg.py (arhiv zaostaja nekaj dni, zato se preverjajo samo dnevi, ki jih arhiv že ima). Vrstice
           dnevnika izdaj pred v0.4 se preskočijo: p_snow takrat ni imel tega pomena.
Do MIN_EVENTS dogodkov na vodilni čas je rezultat »zgoden« in se NE tolmači. Primerjava je z deležem snežnih dni v učnem obdobju (klimatologija modela).

Uporaba:
  python3 tools/verify_sneg.py
"""
import csv
import datetime as dt
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_sneg_mos as tsm  # noqa: E402

ROOT = tsm.ROOT
LOG_PATH = os.path.join(ROOT, "data", "sneg-forward-log.csv")
OUT_PATH = os.path.join(ROOT, "data", "sneg-verification.json")
MIN_EVENTS = 15
BINS = [(0, .05), (.05, .15), (.15, .3), (.3, .5), (.5, .75), (.75, 1.01)]


def pick_issues(rows):
    """{(valid_at, lead): vrstica} -- najzgodnejša izdaja (največ ur vnaprej) v razredu vodilnega časa."""
    best = {}
    for r in rows:
        try:
            hb = float(r["hours_before"])
            p = float(r.get("p_proxy") or "")      # proksi je merljiv z meritvami postaje; p_snow se preverja posebej (evaluate_snow)
        except (ValueError, TypeError, KeyError):
            continue                               # starejše vrstice (pred v0.3) nimajo p_proxy
        if hb <= 0:
            continue    # dan že teče: ni napoved za ta vodilni čas
        lead = math.ceil(hb / 24)
        key = (r["valid_at"], lead)
        if key not in best or hb > best[key][0]:
            best[key] = (hb, p, r["issued_at"], r.get("p_snow"), r.get("model_version"))
    return best


def evaluate(best, truth, model):
    out = {}
    for lead in tsm.LEADS:
        pairs = [(p, truth[v][2]) for (v, l), (_, p, *_) in sorted(best.items()) if l == lead and v in truth]
        entry = (model.get("leads") or {}).get(str(lead)) or {}
        clim = entry.get("prevalence")
        n, ev = len(pairs), sum(y for _, y in pairs)
        res = {"n": n, "events": ev, "preliminary": ev < MIN_EVENTS}
        if n:
            b = sum((p - y) ** 2 for p, y in pairs) / n
            res["brier"] = round(b, 4)
            if clim is not None:
                bc = sum((clim - y) ** 2 for _, y in pairs) / n
                res["brier_clim"] = round(bc, 4)
                res["skill"] = round(1 - b / bc, 3) if bc > 0 else None
            res["bins"] = []
            for lo, hi in BINS:
                sel = [(p, y) for p, y in pairs if lo <= p < hi]
                if sel:
                    res["bins"].append({"from": lo, "to": min(hi, 1.0), "n": len(sel),
                                        "forecast": round(sum(p for p, _ in sel) / len(sel), 3),
                                        "observed": round(sum(y for _, y in sel) / len(sel), 3)})
        out[str(lead)] = res
    return out


SNOW_MIN_VERSION = 0.4      # od te različice modela p_snow pomeni sneg na Gornjem Gradu


def evaluate_snow(best, series, model):
    """p_snow proti novemu snegu >= 1 cm na glavni postaji. {vodilni čas: {n, events, preliminary, brier, brier_clim, skill, ...}}."""
    out = {}
    for lead in tsm.LEADS:
        entry = (model.get("leads") or {}).get(str(lead)) or {}
        clim = ((entry.get("obs_pp") or {}).get(tsm.OBS_PRIMARY) or {}).get("prevalence")
        pairs = []
        for (v, l), (_, _, _, ps, ver) in sorted(best.items()):
            try:
                if l != lead or float(ver) < SNOW_MIN_VERSION or v not in series or series[v] is None:
                    continue
                pairs.append((float(ps), 1.0 if series[v] >= tsm.OBS_NEW_SNOW_CM else 0.0))
            except (TypeError, ValueError):
                continue
        n, ev = len(pairs), int(sum(y for _, y in pairs))
        res = {"n": n, "events": ev, "preliminary": ev < MIN_EVENTS}
        if n:
            b = sum((p - y) ** 2 for p, y in pairs) / n
            res.update(brier=round(b, 4), mean_forecast=round(sum(p for p, _ in pairs) / n, 4),
                       mean_observed=round(ev / n, 4))
            if clim is not None:
                bc = sum((clim - y) ** 2 for _, y in pairs) / n
                res["brier_clim"] = round(bc, 4)
                res["skill"] = round(1 - b / bc, 3) if bc > 0 else None
        out[str(lead)] = res
    return out


def main():
    if not os.path.exists(LOG_PATH):
        print("Dnevnika napovedi še ni -- nič za preveriti.")
        return 0
    model = json.load(open(tsm.MODEL_PATH, encoding="utf-8"))
    truth = tsm.load_truth()
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        best = pick_issues(list(csv.DictReader(f)))
    leads = evaluate(best, truth, model)
    series = tsm.load_observed(stations=(tsm.OBS_PRIMARY,)).get(tsm.OBS_PRIMARY, {})
    snow = evaluate_snow(best, series, model)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": model.get("model_version"),
        "target": model.get("target"),
        "min_events": MIN_EVENTS,
        "note": ("leads: proksi (mokri hladni dan, resnica IREICA1). snow: p_snow proti novemu snegu na ARSO postaji Gornji Grad. "
                 "Pod min_events dogodki na vodilni čas je rezultat zgoden in se ne tolmači."),
        "leads": leads,
        "snow": {"station": tsm.VALLEY_STATIONS[tsm.OBS_PRIMARY]["name"], "id": tsm.OBS_PRIMARY,
                 "definition": f"nov sneg >= {tsm.OBS_NEW_SNOW_CM:g} cm ob jutranjem odčitku (ARSO arhiv)",
                 "min_model_version": SNOW_MIN_VERSION, "leads": snow},
    }
    for k, r in leads.items():
        print(f"  proksi D+{k}: n = {r['n']}, dogodkov {r['events']}" + (" (zgodno)" if r["preliminary"] else "")
              + (f", Brier {r.get('brier')} proti klim. {r.get('brier_clim')}" if r["n"] else ""))
    for k, r in snow.items():
        print(f"  sneg {payload['snow']['station']} D+{k}: n = {r['n']}, dogodkov {r['events']}" + (" (zgodno)" if r["preliminary"] else "")
              + (f", Brier {r.get('brier')} proti klim. {r.get('brier_clim')}" if r["n"] else ""))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"→ {os.path.relpath(OUT_PATH, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
