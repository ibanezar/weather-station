#!/usr/bin/env python3
"""
tools/verify_sneg.py -- preverjanje MTR sneg (proksi) proti meritvam postaje, NAPREJ v času.

Primerja zabeležene napovedi (data/sneg-forward-log.csv) z dejanskim proksijem (padavine in T povp. iz
history.json, dnevi `era5` se ne štejejo). To je edino pošteno merilo: model je učen na arhivu napovedi,
ta skript meri samo napovedi, nastale po uvedbi.

Za vsak (ciljni dan, vodilni čas) vzame najzgodnejšo izdajo v svojem razredu (vodilni čas = ceil(hours_before/24)),
ker je model učen na napovedi izpred N dni (previous_dayN), ne na napovedi tik pred dogodkom.

NAPOVEDI SO PROKSIJA (p_proxy, »mokri hladni dan« v Rečici): nanj se nanaša edina resnica, ki jo ima postaja. Kalibracija na opazovan sneg (p_snow)
se tu ne preverja; potrebovala bi sveže ARSO dnevne serije (data.xml ima zamik ~2 dni). Rezultat: data/sneg-verification.json. Do MIN_EVENTS dogodkov na vodilni čas je rezultat »zgoden« in se NE
tolmači. Primerjava je z deležem snežnih dni v učnem obdobju (klimatologija modela).

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
            p = float(r.get("p_proxy") or "")      # proksi je merljiv z meritvami postaje; p_snow (opazovanja ARSO) ne
        except (ValueError, TypeError, KeyError):
            continue                               # starejše vrstice (pred v0.3) nimajo p_proxy
        if hb <= 0:
            continue    # dan že teče: ni napoved za ta vodilni čas
        lead = math.ceil(hb / 24)
        key = (r["valid_at"], lead)
        if key not in best or hb > best[key][0]:
            best[key] = (hb, p, r["issued_at"])
    return best


def evaluate(best, truth, model):
    out = {}
    for lead in tsm.LEADS:
        pairs = [(p, truth[v][2]) for (v, l), (_, p, _) in sorted(best.items()) if l == lead and v in truth]
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


def main():
    if not os.path.exists(LOG_PATH):
        print("Dnevnika napovedi še ni -- nič za preveriti.")
        return 0
    model = json.load(open(tsm.MODEL_PATH, encoding="utf-8"))
    truth = tsm.load_truth()
    with open(LOG_PATH, encoding="utf-8", newline="") as f:
        best = pick_issues(list(csv.DictReader(f)))
    leads = evaluate(best, truth, model)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": model.get("model_version"),
        "target": model.get("target"),
        "min_events": MIN_EVENTS,
        "note": ("Meri se proksi (mokri hladni dan), ne opazovan sneg. Pod min_events dogodki na vodilni čas "
                 "je rezultat zgoden in se ne tolmači."),
        "leads": leads,
    }
    for k, r in leads.items():
        print(f"  D+{k}: n = {r['n']}, dogodkov {r['events']}" + (" (zgodno)" if r["preliminary"] else "")
              + (f", Brier {r.get('brier')} proti klim. {r.get('brier_clim')}" if r["n"] else ""))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"→ {os.path.relpath(OUT_PATH, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
