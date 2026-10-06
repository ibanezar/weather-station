#!/usr/bin/env python3
"""
tools/log_ensemble_forecasts.py — dnevni zajem ansamblov (ECMWF ENS, ICON-EPS,
GEFS) za Rečico, od zdaj naprej.

Zakaj: ansambli nimajo arhiva preteklih napovedi (Open-Meteo Previous Runs jih
ne zna), zato se zgodovina, na kateri se bo dalo naučiti pravo verjetnostno
napoved (zmrzal, padavine nad pragom), nabira samo s tekočim beleženjem. Vsak
dan zamujenega zajema je izgubljen za vedno.

Piše data/ensemble-forward-log.csv: ena vrstica na (model, issued_at, valid_at)
z razponom članov za Tmax/Tmin, povprečjem padavin in deleži članov
(p_wet: dnevna vsota >= 0,2 mm; p_frost: Tmin <= 0 °C). Surovih članov ne
hranimo (CSV bi zrasel ~50x). Samo za učenje/preverjanje — na strani se ne
prikazuje. Ob nedosegljivem viru skript konča z 0 in ne spremeni ničesar.

Usage:
  python3 tools/log_ensemble_forecasts.py
"""
import csv, datetime, json, os, re, sys, urllib.parse, urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "data", "ensemble-forward-log.csv")
LAT, LON = 46.325779, 14.921137
TZ = ZoneInfo("Europe/Ljubljana")
UA = {"User-Agent": "Meteorec-EnsembleLog/1.0 https://meteorec.si"}
MODELS = ["ecmwf_ifs025", "icon_seamless", "gfs025"]   # Open-Meteo ensemble model ids
WET_MM, DAYS = 0.2, 8
FIELDS = ["model", "issued_at", "valid_at", "lead_days", "n_members",
          "tmax_p10", "tmax_p50", "tmax_p90", "tmax_mean",
          "tmin_p10", "tmin_p50", "tmin_p90", "tmin_mean",
          "precip_mean", "p_wet", "p_frost"]
KEY_RE = re.compile(r"^(temperature_2m|precipitation)(?:_member\d+)?_(.+)$")


def fetch():
    q = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON, "hourly": "temperature_2m,precipitation",
        "models": ",".join(MODELS), "forecast_days": DAYS, "timezone": "Europe/Ljubljana"})
    req = urllib.request.Request("https://ensemble-api.open-meteo.com/v1/ensemble?" + q, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def pct(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summarize(data, issued):
    """{(model, valid_at): row} from the raw hourly members."""
    h = data.get("hourly") or {}
    times = h.get("time") or []
    series = {}    # (model_suffix, member_key) -> {var: [values]}
    for key, vals in h.items():
        m = KEY_RE.match(key)
        if not m:
            continue
        var, suffix = m.groups()
        member = key[len(var) + 1:-len(suffix) - 1] or "control"
        series.setdefault(suffix, {}).setdefault(member, {})[var] = vals
    # model names the API appends differ from the request ids -> map by prefix
    alias = {"ecmwf_ifs025": "ecmwf_ifs025_ensemble", "icon_seamless": "icon_seamless_eps", "gfs025": "ncep_gefs025"}
    out = {}
    for model in MODELS:
        members = series.get(alias.get(model, model)) or {}
        days = {}
        for mem, v in members.items():
            t, p = v.get("temperature_2m") or [], v.get("precipitation") or []
            per = {}
            for i, ts in enumerate(times):
                d = per.setdefault(ts[:10], {"t": [], "p": 0.0, "np": 0})
                if i < len(t) and t[i] is not None:
                    d["t"].append(t[i])
                if i < len(p) and p[i] is not None:
                    d["p"] += p[i]
                    d["np"] += 1
            for day, d in per.items():
                if len(d["t"]) >= 22:     # complete local day only
                    days.setdefault(day, []).append((max(d["t"]), min(d["t"]), d["p"]))
        for day, ms in days.items():
            lead = (datetime.date.fromisoformat(day) - datetime.date.fromisoformat(issued)).days
            if lead < 1 or len(ms) < 5:
                continue
            tx, tn, pr = [m[0] for m in ms], [m[1] for m in ms], [m[2] for m in ms]
            out[(model, day)] = {
                "model": model, "issued_at": issued, "valid_at": day, "lead_days": lead,
                "n_members": len(ms),
                "tmax_p10": round(pct(tx, .1), 1), "tmax_p50": round(pct(tx, .5), 1),
                "tmax_p90": round(pct(tx, .9), 1), "tmax_mean": round(sum(tx) / len(tx), 1),
                "tmin_p10": round(pct(tn, .1), 1), "tmin_p50": round(pct(tn, .5), 1),
                "tmin_p90": round(pct(tn, .9), 1), "tmin_mean": round(sum(tn) / len(tn), 1),
                "precip_mean": round(sum(pr) / len(pr), 1),
                "p_wet": round(sum(1 for x in pr if x >= WET_MM) / len(pr), 3),
                "p_frost": round(sum(1 for x in tn if x <= 0.0) / len(tn), 3),
            }
    return out


def main():
    issued = datetime.datetime.now(TZ).date().isoformat()
    rows, seen = [], set()
    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                seen.add((r["model"], r["issued_at"], r["valid_at"]))
    try:
        data = fetch()
    except Exception as e:                       # network/API: leave the log untouched
        print(f"⚠ ansambli niso dosegljivi ({e}) — preskočeno.", file=sys.stderr)
        return 0
    new = [r for (m, d), r in sorted(summarize(data, issued).items()) if (m, issued, d) not in seen]
    if not new:
        print("Ni novih vrstic.")
        return 0
    rows += new
    rows.sort(key=lambda r: (r["model"], r["issued_at"], r["valid_at"]))
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    print(f"✓ {len(new)} novih vrstic ({issued}), skupaj {len(rows)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
