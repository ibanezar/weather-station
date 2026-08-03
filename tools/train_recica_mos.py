#!/usr/bin/env python3
"""
tools/train_recica_mos.py — uči MTR, lastni napovedni model za Rečico (MOS).

MOS = Model Output Statistics: model ne napoveduje vremena iz nič, ampak se iz
meritev te postaje nauči, kako se dno doline sistematično razlikuje od tega, kar
za to točko računa Open-Meteo. Sinoptiko prispeva Open-Meteo, lokalno popravo
naša postaja.

Zakaj sploh deluje: postaja je podnevi topleje in ponoči hladneje od modelske
mreže, ob jasnih in mirnih nočeh pa se na dnu doline nabere hladen zrak in je
razlika največja. To je ponovljiv, iz značilk izračunljiv vzorec — ne šum.

UČNI PODATKI
  * historical-forecast-api.open-meteo.com — *_previous_dayN, torej napoved,
    kakršna je resnično bila N dni prej. To je edini pošten vhod: ERA5 arhiv bi
    modelu povedal, kakšno je vreme *bilo*, in bi veščino močno precenil.
    Te spremenljivke segajo do ~2024-01, ne dlje.
  * history.json — meritve postaje kot resnica. Samo dnevi s src "station" ali
    "wu"; dnevi "era5" so model in ne smejo v učenje.

MODEL
  * grebenska regresija za tmax in tmin, posebej za vsak vodilni čas D+1..D+3
  * logistična regresija za verjetnost padavin (moker dan ≥ 0,2 mm)
  * količine padavin NE napovedujemo — poskus je pokazal ~5 % izboljšave, kar je
    v okviru šuma. Za količino ostane Open-Meteo in to na strani tudi piše.

VEŠČINA se meri z izpuščanjem celega leta (nikoli naključni razbit set —
sosednji dnevi so odvisni in bi veščino napihnili) in se zapiše v model.

Uporaba:
  python3 tools/train_recica_mos.py            # nauči in zapiši model/recica-mos.json
  python3 tools/train_recica_mos.py --report   # samo izpiši veščino, ne piši
  python3 tools/train_recica_mos.py --no-cache # brez lokalnega predpomnilnika
"""
import argparse
import datetime as dt
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(ROOT, "history.json")
MODEL_DIR = os.path.join(ROOT, "model")
MODEL_PATH = os.path.join(MODEL_DIR, "recica-mos.json")
CACHE_PATH = os.path.join(ROOT, "tools", ".mos_cache.json")

LAT, LON = 46.325779, 14.921137
TZ = "Europe/Ljubljana"
UA = {"User-Agent": "Mozilla/5.0 (compatible; Meteorec-MOS/1.0; +https://meteorec.si)"}

MODEL_VERSION = "1.0"
LEADS = (1, 2, 3)
TRAIN_START = "2024-01-01"   # prej *_previous_dayN ni na voljo
RIDGE_LAMBDA = 2.0
WET_DAY_MM = 0.2             # prag za "moker dan"

# Urne spremenljivke, iz katerih gradimo dnevne značilke. Isti seznam uporablja
# tools/predict_recica_mos.py za živo napoved — kar se tu spremeni, se mora tam
# spremeniti samo po sebi (uvozi ga od tod).
HOURLY_VARS = [
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "relative_humidity_2m",
    "pressure_msl",
    "shortwave_radiation",
]

NIGHT_HOURS = set(range(0, 9))    # 00–08, ko se dolina ohlaja
DAY_HOURS = set(range(10, 19))    # 10–18, ko sonce greje

# Imena značilk — vrstni red je pogodba med učenjem in napovedovanjem.
TEMP_FEATURES = [
    "bias", "om_tmax", "om_tmin", "cloud", "cloud_n", "wind", "wind_n", "rh",
    "pres_anom", "rad100", "prec_cap", "sin_doy", "cos_doy",
    "coldpool", "sin_x_tmax", "cos_x_tmax",
]
POP_FEATURES = [
    "bias", "sqrt_prec", "wet_frac", "rh100", "cloud100", "pres_anom10",
    "tmax30", "sin_doy", "cos_doy",
]


# ── Zajem ───────────────────────────────────────────────────────────────────
def _get_json(url, timeout=240, tries=4):
    """Open-Meteo arhiv občasno prekine rokovanje TLS — poskusi večkrat."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, OSError) as e:
            last = e
            print(f"    ponovni poskus ({i + 1}/{tries}): {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"zajem ni uspel: {last}")


def fetch_archived_forecasts(lead, start, end):
    """Vrne {datum: {spremenljivka: [(ura, vrednost), ...]}} za napoved izpred
    `lead` dni. Zajema po letih, ker je enoletni odgovor še obvladljiv."""
    hourly = ",".join(f"{v}_previous_day{lead}" for v in HOURLY_VARS)
    rows = {}
    y0 = int(start[:4])
    y1 = int(end[:4])
    for year in range(y0, y1 + 1):
        a = max(start, f"{year}-01-01")
        b = min(end, f"{year}-12-31")
        if a > b:
            continue
        q = urllib.parse.urlencode({
            "latitude": LAT, "longitude": LON,
            "start_date": a, "end_date": b,
            "hourly": hourly, "timezone": TZ,
        })
        print(f"  D+{lead} {a} → {b} …")
        data = _get_json("https://historical-forecast-api.open-meteo.com/v1/forecast?" + q)
        h = data.get("hourly") or {}
        times = h.get("time") or []
        for i, ts in enumerate(times):
            day, hour = ts[:10], int(ts[11:13])
            rec = rows.setdefault(day, {v: [] for v in HOURLY_VARS})
            for v in HOURLY_VARS:
                val = (h.get(f"{v}_previous_day{lead}") or [])[i] if h.get(f"{v}_previous_day{lead}") else None
                if val is not None:
                    rec[v].append((hour, val))
    return rows


# ── Značilke ────────────────────────────────────────────────────────────────
def _mean(pairs, hours=None):
    xs = [v for h, v in pairs if hours is None or h in hours]
    return sum(xs) / len(xs) if xs else None


def daily_features(series, day):
    """Urne serije enega dne → dnevne značilke. Ista funkcija se uporabi pri
    učenju (arhiv napovedi) in pri napovedovanju (živa napoved) — dva prepisa bi
    se prej ali slej razšla in model bi tiho dobival druge vhode, kot jih pozna.

    `series` = {spremenljivka: [(ura, vrednost), ...]}, `day` = "YYYY-MM-DD".
    Vrne None, kadar dan ni dovolj popoln.
    """
    temp = series.get("temperature_2m") or []
    if len(temp) < 20:
        return None

    f = {}
    f["om_tmax"] = max(v for _, v in temp)
    f["om_tmin"] = min(v for _, v in temp)
    prec = series.get("precipitation") or []
    f["om_prec"] = sum(v for _, v in prec)
    f["wet_hours"] = sum(1 for _, v in prec if v >= 0.1)
    f["cloud"] = _mean(series.get("cloud_cover") or [])
    f["cloud_n"] = _mean(series.get("cloud_cover") or [], NIGHT_HOURS)
    f["wind"] = _mean(series.get("wind_speed_10m") or [])
    f["wind_n"] = _mean(series.get("wind_speed_10m") or [], NIGHT_HOURS)
    f["rh"] = _mean(series.get("relative_humidity_2m") or [])
    f["pres"] = _mean(series.get("pressure_msl") or [])
    f["rad"] = _mean(series.get("shortwave_radiation") or [], DAY_HOURS)
    if any(f[k] is None for k in ("cloud", "cloud_n", "wind", "wind_n", "rh", "pres", "rad")):
        return None

    doy = dt.date.fromisoformat(day).timetuple().tm_yday
    f["sin_doy"] = math.sin(2 * math.pi * doy / 365.25)
    f["cos_doy"] = math.cos(2 * math.pi * doy / 365.25)
    return f


def temp_vector(f):
    """Načrtovalna vrstica za temperaturo. `coldpool` je jedro modela: ob jasni
    (nizka nočna oblačnost) in mirni (nizek nočni veter) noči gre proti 1 in
    ujame nabiranje hladnega zraka na dnu doline, ki ga mreža ne razreši."""
    coldpool = (100 - f["cloud_n"]) / 100 * (1 / (1 + f["wind_n"]))
    return [
        1.0,
        f["om_tmax"], f["om_tmin"], f["cloud"], f["cloud_n"], f["wind"], f["wind_n"],
        f["rh"], f["pres"] - 1013, f["rad"] / 100, min(f["om_prec"], 30),
        f["sin_doy"], f["cos_doy"],
        coldpool, f["sin_doy"] * f["om_tmax"], f["cos_doy"] * f["om_tmax"],
    ]


def pop_vector(f):
    return [
        1.0,
        math.sqrt(min(f["om_prec"], 50)), f["wet_hours"] / 24, f["rh"] / 100,
        f["cloud"] / 100, (f["pres"] - 1013) / 10, f["om_tmax"] / 30,
        f["sin_doy"], f["cos_doy"],
    ]


# ── Regresija (čisti Python, brez numpy) ────────────────────────────────────
def solve_ridge(X, y, lam, weights=None):
    """Grebenska regresija prek normalnih enačb in Gauss-Jordanove eliminacije.
    Pri ~16 značilkah in ~900 vzorcih je to milisekunde dela in se izogne
    odvisnosti od numpy, ki je nima nobeno drugo orodje v tem repozitoriju.
    Odsek (prvi stolpec) se ne kaznuje."""
    n = len(X[0])
    A = [[0.0] * n for _ in range(n)]
    b = [0.0] * n
    for k, (xi, yi) in enumerate(zip(X, y)):
        w = 1.0 if weights is None else weights[k]
        for i in range(n):
            b[i] += w * xi[i] * yi
            xiw = w * xi[i]
            for j in range(n):
                A[i][j] += xiw * xi[j]
    for i in range(1, n):
        A[i][i] += lam

    M = [A[i][:] + [b[i]] for i in range(n)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        if abs(M[c][c]) < 1e-12:
            continue
        for r in range(n):
            if r == c:
                continue
            fct = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= fct * M[c][k]
    return [M[i][n] / M[i][i] if abs(M[i][i]) > 1e-12 else 0.0 for i in range(n)]


def solve_logistic(X, y, lam=1.0, iters=25):
    """Logistična regresija po Newton-Raphsonu (IRLS) — vsak korak je ena utežena
    grebenska regresija, tako da se solve_ridge ponovno uporabi."""
    n = len(X[0])
    w = [0.0] * n
    for _ in range(iters):
        z = []
        weights = []
        for xi in X:
            eta = sum(wi * xj for wi, xj in zip(w, xi))
            eta = max(-30.0, min(30.0, eta))
            p = 1 / (1 + math.exp(-eta))
            p = min(max(p, 1e-6), 1 - 1e-6)
            weights.append(p * (1 - p))
            z.append(eta)
        # delovni odziv: eta + (y - p) / (p(1-p))
        work = []
        for xi, yi, eta, wt in zip(X, y, z, weights):
            p = 1 / (1 + math.exp(-max(-30.0, min(30.0, eta))))
            work.append(eta + (yi - p) / wt)
        new = solve_ridge(X, work, lam, weights)
        if max(abs(a - b) for a, b in zip(new, w)) < 1e-7:
            w = new
            break
        w = new
    return w


def predict_linear(coefs, vec):
    return sum(c * v for c, v in zip(coefs, vec))


def predict_prob(coefs, vec):
    eta = max(-30.0, min(30.0, predict_linear(coefs, vec)))
    return 1 / (1 + math.exp(-eta))


# ── Učni vzorci ─────────────────────────────────────────────────────────────
def load_history():
    with open(HISTORY_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_samples(rows, hist):
    """Poveže dnevne značilke z izmerjenim dnem. Dnevi z izvorom "era5" so
    modelska ocena in ne meritev — v učenju bi model učili lastnega vhoda."""
    samples = []
    for day in sorted(rows):
        obs = hist.get(day)
        if not obs or obs.get("src") not in ("station", "wu"):
            continue
        if obs.get("tempHigh") is None or obs.get("tempLow") is None:
            continue
        f = daily_features(rows[day], day)
        if f is None:
            continue
        samples.append({
            "date": day,
            "f": f,
            "tmax": obs["tempHigh"],
            "tmin": obs["tempLow"],
            "wet": 1.0 if (obs.get("precipTotal") or 0) >= WET_DAY_MM else 0.0,
        })
    return samples


# ── Veščina ─────────────────────────────────────────────────────────────────
def blocked_cv(samples, target, om_key):
    """MAE modela in surovega Open-Meteo pri izpuščanju celega leta.

    Naključna delitev bi tu lagala: vreme je iz dneva v dan močno odvisno, zato
    bi imel testni dan skoraj vedno svojega soseda v učni množici."""
    years = sorted({s["date"][:4] for s in samples})
    om_err, mos_err, per_year = [], [], {}
    for hold in years:
        tr = [s for s in samples if s["date"][:4] != hold]
        te = [s for s in samples if s["date"][:4] == hold]
        if not tr or not te:
            continue
        coefs = solve_ridge([temp_vector(s["f"]) for s in tr],
                            [s[target] for s in tr], RIDGE_LAMBDA)
        eo, em = [], []
        for s in te:
            pred = predict_linear(coefs, temp_vector(s["f"]))
            em.append(abs(pred - s[target]))
            eo.append(abs(s["f"][om_key] - s[target]))
        per_year[hold] = {"n": len(te),
                          "open_meteo": round(sum(eo) / len(eo), 2),
                          "meteorec": round(sum(em) / len(em), 2)}
        om_err += eo
        mos_err += em
    if not om_err:
        return None
    a = sum(om_err) / len(om_err)
    b = sum(mos_err) / len(mos_err)
    return {
        "n": len(om_err),
        "mae_open_meteo": round(a, 2),
        "mae_meteorec": round(b, 2),
        "improvement_pct": round(100 * (a - b) / a, 1) if a else 0.0,
        "per_year": per_year,
    }


def blocked_cv_pop(samples):
    """Brierjeva ocena za verjetnost padavin, proti klimatologiji učne množice."""
    years = sorted({s["date"][:4] for s in samples})
    brier, base = [], []
    for hold in years:
        tr = [s for s in samples if s["date"][:4] != hold]
        te = [s for s in samples if s["date"][:4] == hold]
        if not tr or not te:
            continue
        coefs = solve_logistic([pop_vector(s["f"]) for s in tr], [s["wet"] for s in tr])
        clim = sum(s["wet"] for s in tr) / len(tr)
        for s in te:
            p = predict_prob(coefs, pop_vector(s["f"]))
            brier.append((p - s["wet"]) ** 2)
            base.append((clim - s["wet"]) ** 2)
    if not brier:
        return None
    b = sum(brier) / len(brier)
    c = sum(base) / len(base)
    return {
        "n": len(brier),
        "brier": round(b, 3),
        "brier_climatology": round(c, 3),
        "skill_score": round(1 - b / c, 3) if c else 0.0,
    }


def residual_sd(samples, coefs, target):
    """Standardni odklon ostankov — pas negotovosti na kartici."""
    errs = [predict_linear(coefs, temp_vector(s["f"])) - s[target] for s in samples]
    if len(errs) < 2:
        return None
    mean = sum(errs) / len(errs)
    var = sum((e - mean) ** 2 for e in errs) / (len(errs) - 1)
    return round(math.sqrt(var), 2)


# ── Predpomnilnik ───────────────────────────────────────────────────────────
def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def _rows_to_cache(rows):
    return {d: {v: [[h, x] for h, x in pairs] for v, pairs in s.items()} for d, s in rows.items()}


def _rows_from_cache(blob):
    return {d: {v: [(int(h), x) for h, x in pairs] for v, pairs in s.items()} for d, s in blob.items()}


# ── Glavni tok ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Uči lokalni MOS model za Rečico.")
    ap.add_argument("--from", dest="start", default=TRAIN_START)
    ap.add_argument("--to", dest="end", default=None)
    ap.add_argument("--report", action="store_true", help="samo izpiši veščino")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    end = args.end or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    hist = load_history()
    cache = {} if args.no_cache else load_cache()

    model = {
        "model_version": MODEL_VERSION,
        "trained_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_range": {"from": args.start, "to": end},
        "station": {"lat": LAT, "lon": LON, "name": "Rečica ob Savinji (IREICA1)"},
        "hourly_vars": HOURLY_VARS,
        "temp_features": TEMP_FEATURES,
        "pop_features": POP_FEATURES,
        "wet_day_mm": WET_DAY_MM,
        "ridge_lambda": RIDGE_LAMBDA,
        "leads": {},
    }

    for lead in LEADS:
        key = f"lead{lead}:{args.start}:{end}"
        if key in cache:
            print(f"D+{lead}: iz predpomnilnika")
            rows = _rows_from_cache(cache[key])
        else:
            print(f"D+{lead}: zajemam arhiv napovedi")
            try:
                rows = fetch_archived_forecasts(lead, args.start, end)
            except RuntimeError as e:
                # Vodilni čas, ki ga ni bilo mogoče pobrati, preprosto izpustimo.
                # Prejšnji so že izračunani in bi jih vržena napaka vzela s seboj.
                print(f"  ⚠ D+{lead} preskočen: {e}", file=sys.stderr)
                continue
            if not args.no_cache:
                # Shrani takoj po vsakem vodilnem času: zajem traja minute in
                # prekinjen tek bi sicer vrgel stran vse, kar je že pobral.
                cache[key] = _rows_to_cache(rows)
                save_cache(cache)

        samples = build_samples(rows, hist)
        if len(samples) < 200:
            print(f"  ⚠ premalo vzorcev za D+{lead} ({len(samples)}) — vodilni čas izpuščen",
                  file=sys.stderr)
            continue
        print(f"  vzorcev: {len(samples)}  ({samples[0]['date']} → {samples[-1]['date']})")

        entry = {"n_samples": len(samples),
                 "date_range": {"from": samples[0]["date"], "to": samples[-1]["date"]},
                 "skill": {}, "coefficients": {}, "residual_sd": {}}

        for target, om_key in (("tmax", "om_tmax"), ("tmin", "om_tmin")):
            skill = blocked_cv(samples, target, om_key)
            coefs = solve_ridge([temp_vector(s["f"]) for s in samples],
                                [s[target] for s in samples], RIDGE_LAMBDA)
            entry["skill"][target] = skill
            entry["coefficients"][target] = [round(c, 6) for c in coefs]
            entry["residual_sd"][target] = residual_sd(samples, coefs, target)
            if skill:
                print(f"  {target}: Open-Meteo {skill['mae_open_meteo']} °C → "
                      f"naš {skill['mae_meteorec']} °C  ({skill['improvement_pct']:+.1f} %)")

        pop_skill = blocked_cv_pop(samples)
        pop_coefs = solve_logistic([pop_vector(s["f"]) for s in samples],
                                   [s["wet"] for s in samples])
        entry["skill"]["pop"] = pop_skill
        entry["coefficients"]["pop"] = [round(c, 6) for c in pop_coefs]
        if pop_skill:
            print(f"  padavine: Brier {pop_skill['brier']} proti klimatologiji "
                  f"{pop_skill['brier_climatology']} (veščina {pop_skill['skill_score']})")

        model["leads"][str(lead)] = entry

    if not model["leads"]:
        print("✗ Nobenega vodilnega časa ni bilo mogoče naučiti.", file=sys.stderr)
        return 1

    if args.report:
        print("\n(--report: model ni zapisan)")
        return 0

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n→ {os.path.relpath(MODEL_PATH, ROOT)}: vodilni časi {', '.join(model['leads'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
