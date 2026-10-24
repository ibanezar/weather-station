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

DRUGI VHOD (--aifs)
  Poskusno se poleg privzetega Open-Meteo vzame še ECMWF AIFS (AI model, ki ga
  Windy prikazuje kot podaljšek modela ECMWF) — ne kot zamenjava vhoda, ampak
  kot dodatne značilke: njegova Tmax/Tmin in razlika do privzetega modela. Ker
  se arhiv AIFS začne 2025-02-20, je učno okno s tem vhodom krajše; osnovo je
  treba za pošteno primerjavo pognati na istem oknu:

    python3 tools/train_recica_mos.py --from 2025-02-20 --report          # osnova
    python3 tools/train_recica_mos.py --from 2025-02-20 --aifs --report   # z AIFS

  Izid poskusa je zapisan v docs/model-recica.md.

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
# Dodatni pragovi dnevne vsote (mm): ključ v koeficientih -> prag. Isti vhodi kot `pop`, drug cilj.
POP_THRESHOLDS = {"pop1": 1.0, "pop5": 5.0}

# ECMWF AIFS — AI model, ki ga ECMWF poganja operativno od 25. 2. 2025 (Windy ga
# prikazuje kot 15-dnevni podaljšek modela ECMWF). Z --aifs ga vzamemo kot drugi
# vhod poleg privzetega Open-Meteo: ne kot zamenjavo, ampak kot dodatne značilke.
# Arhiv Open-Meteo zanj se začne 20. 2. 2025, zato je učno okno s tem vhodom
# bistveno krajše — primerjava z osnovo mora zato teči na istem oknu.
AIFS_MODEL = "ecmwf_aifs025_single"
AIFS_START = "2025-02-20"

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

# Dodatek pri --aifs. Razlika med modeloma (d*) je tu bolj zanimiva od golih
# vrednosti AIFS: kadar se globalni AI model in seamless razideta, je negotovost
# večja in popravek naj bo drugačen.
AIFS_TEMP_FEATURES = ["aifs_tmax", "aifs_tmin", "aifs_dtmax", "aifs_dtmin"]
AIFS_POP_FEATURES = ["aifs_sqrt_prec", "aifs_wet_frac"]

# Dodatek pri --use-bias: avtokorelirana pristranskost modela kot prediktor.
# Zgrajena IZKLJUČNO iz D+1 arhiva (glej build_bias_series) — "kako zelo se je
# Open-Meteo pred kratkim motil" je stanje, ki ga poznamo šele za včerajšnji in
# starejše dni, ne glede na to, za kateri vodilni čas napovedujemo danes. Ločeno
# za tmax/tmin, ker se model za vsak cilj uči na svoji napaki (glej err_stats).
BIAS_FEATURES = ["err_lag1", "err_ma3", "err_ma7", "is_err_missing"]

# Dodatek pri --use-cond: pogojni/režimski prediktorji in interakcije.
# windcloud_n = nočni veter × nočna oblačnost — jasna in mirna noč (oba nizka)
# napove močno radiacijsko inverzijo, oblačna in vetrovna pa popravek blizu nič;
# to je ista fizika kot `coldpool` zgoraj, samo kot množinski (ne uteženi) člen.
# sin_x_own/cos_x_own = sezonska interakcija z LASTNIM ciljem — SAMO pri tmin
# (glej temp_vector): obstoječa sin_x_tmax/cos_x_tmax v TEMP_FEATURES zgoraj
# vedno uporabita om_tmax, tudi pri učenju tmin, zato je pri tmin to dodatek,
# ne zamenjava; pri tmax bi bila dobesedna kopija istih dveh stolpcev in samo
# odvečen, nestabilen parameter (glej opombo v temp_vector).
COND_FEATURES = ["windmax", "radsum", "windcloud_n", "sin_x_own_tmin_only", "cos_x_own_tmin_only"]

# Regularizacija se od uvedbe izbira z notranjo časovno validacijo (glej
# select_lambda), ne več fiksno. RIDGE_LAMBDA ostane kot rezervna vrednost, če
# zgodovine za izbiro zmanjka (npr. prvi meseci učne množice).
LAMBDA_GRID = [0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
INNER_FOLDS = 3     # notranjih mesečnih rezin za izbiro lambda
MIN_TRAIN_MONTHS = 3  # najmanj mesecev zgodovine, preden se sploh oceni prvi mesec
OUTER_FOLDS = 12    # zaporednih mesečnih rezin za zunanjo (poročano) veščino


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


def fetch_archived_forecasts(lead, start, end, model=None, variables=None):
    """Vrne {datum: {spremenljivka: [(ura, vrednost), ...]}} za napoved izpred
    `lead` dni. Zajema po letih, ker je enoletni odgovor še obvladljiv.

    Brez `model` je to privzeti seamless Open-Meteo; z `model` en sam imenovan
    model (pri nas AIFS). `variables` (privzeto HOURLY_VARS) omogoča ločen zajem
    dodatnih spremenljivk (veter: WIND_EXTRA_VARS), da temperaturni zajem ostane
    nespremenjen."""
    variables = variables or HOURLY_VARS
    hourly = ",".join(f"{v}_previous_day{lead}" for v in variables)
    rows = {}
    y0 = int(start[:4])
    y1 = int(end[:4])
    for year in range(y0, y1 + 1):
        a = max(start, f"{year}-01-01")
        b = min(end, f"{year}-12-31")
        if a > b:
            continue
        params = {
            "latitude": LAT, "longitude": LON,
            "start_date": a, "end_date": b,
            "hourly": hourly, "timezone": TZ,
        }
        if model:
            params["models"] = model
        q = urllib.parse.urlencode(params)
        print(f"  D+{lead} {a} → {b}{f' [{model}]' if model else ''} …")
        data = _get_json("https://historical-forecast-api.open-meteo.com/v1/forecast?" + q)
        h = data.get("hourly") or {}
        times = h.get("time") or []
        for i, ts in enumerate(times):
            day, hour = ts[:10], int(ts[11:13])
            rec = rows.setdefault(day, {v: [] for v in variables})
            for v in variables:
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

    # Pogojni/režimski prediktorji (--use-cond, glej COND_FEATURES): dnevni
    # sunek namesto povprečja in dnevna energijska vsota obsevanja namesto
    # samo dnevnega povprečja. Iz istih serij kot "wind"/"rad" zgoraj, zato ni
    # dodatnega klica Open-Meteo.
    wind_pairs = series.get("wind_speed_10m") or []
    f["windmax"] = max(v for _, v in wind_pairs) if wind_pairs else None
    f["radsum"] = sum(v for _, v in (series.get("shortwave_radiation") or []))

    doy = dt.date.fromisoformat(day).timetuple().tm_yday
    f["sin_doy"] = math.sin(2 * math.pi * doy / 365.25)
    f["cos_doy"] = math.cos(2 * math.pi * doy / 365.25)
    return f


def merge_aifs(f, af):
    """Doda značilke drugega vhoda (AIFS) k dnevnim značilkam privzetega modela.
    `af` je izhod daily_features() nad arhivom AIFS — ista funkcija, druga mreža.
    Vrne None, kadar AIFS za ta dan nima uporabnega dneva; klicatelj tak dan
    izpusti, da model ne dobi napol praznega vhoda."""
    if f is None or af is None:
        return None
    g = dict(f)
    g["aifs_tmax"] = af["om_tmax"]
    g["aifs_tmin"] = af["om_tmin"]
    g["aifs_dtmax"] = af["om_tmax"] - f["om_tmax"]
    g["aifs_dtmin"] = af["om_tmin"] - f["om_tmin"]
    g["aifs_prec"] = af["om_prec"]
    g["aifs_wet_hours"] = af["wet_hours"]
    return g


def temp_vector(f, target, with_aifs=False, use_bias=False, use_cond=False, use_multi=False):
    """Načrtovalna vrstica za temperaturo. `coldpool` je jedro modela: ob jasni
    (nizka nočna oblačnost) in mirni (nizek nočni veter) noči gre proti 1 in
    ujame nabiranje hladnega zraka na dnu doline, ki ga mreža ne razreši.

    Prvih 16 stolpcev (do `coldpool`/`sin_x_tmax`/`cos_x_tmax`) je NESPREMENJENIH
    od uvedbe modela — pri `use_bias=use_cond=False` je vrnjeni vektor bit za
    bitom enak prejšnjemu `temp_vector(f, with_aifs)`, kar "obstoječi MTR" v
    primerjavi (tools/validate_recica_mos.py) naredi resnično obstoječega.

    `target` ("tmax"/"tmin") pove, čigave err_* značilke (--use-bias) in čigav
    "lasten" napovedani T (--use-cond, sin_x_own/cos_x_own) uporabiti — model za
    tmax in model za tmin sta ločena regresija, zato tudi ločena vhoda za te
    dele. Vrstni red: baza → aifs → bias → cond (ista pogodba mora veljati pri
    učenju in napovedovanju, glej predict_recica_mos.py)."""
    coldpool = (100 - f["cloud_n"]) / 100 * (1 / (1 + f["wind_n"]))
    v = [
        1.0,
        f["om_tmax"], f["om_tmin"], f["cloud"], f["cloud_n"], f["wind"], f["wind_n"],
        f["rh"], f["pres"] - 1013, f["rad"] / 100, min(f["om_prec"], 30),
        f["sin_doy"], f["cos_doy"],
        coldpool, f["sin_doy"] * f["om_tmax"], f["cos_doy"] * f["om_tmax"],
    ]
    if with_aifs:
        v += [f["aifs_tmax"], f["aifs_tmin"], f["aifs_dtmax"], f["aifs_dtmin"]]
    if use_bias:
        v += [
            f[f"err_lag1_{target}"], f[f"err_ma3_{target}"], f[f"err_ma7_{target}"],
            f[f"is_err_missing_{target}"],
        ]
    if use_cond:
        windcloud_n = f["wind_n"] * f["cloud_n"] / 100
        v += [f["windmax"], f["radsum"] / 1000, windcloud_n]
        # sin_x_own/cos_x_own SAMO za tmin: za tmax bi bila to dobesedna kopija
        # sin_x_tmax/cos_x_tmax iz baze zgoraj (own == om_tmax) — odvečen,
        # neidentificiran parameter, ki je pri walk-forward oceni po sezonah
        # (kratka učna zgodovina, malo preteklih jeseni) nestabilno "izbiral"
        # med dvema enakima stolpcema in k jesenski regresiji prispeval slabšo
        # ekstrapolacijo (glej data/mtr-validation-report.md). Za tmin je
        # interakcija z om_tmin resnično nova informacija, ki je v bazi ni.
        if target == "tmin":
            v += [f["sin_doy"] * f["om_tmin"], f["cos_doy"] * f["om_tmin"]]
    if use_multi:
        v += multi_vector(f, target)
    return v


# Dodatek pri --multi-tmax/--multi-tmin: dnevna Tmax/Tmin DRUGIH modelov (IFS, GFS, ICON,
# ARPEGE) iz data/forecast-archive.csv kot razlike do privzetega Open-Meteo, plus razlika
# povprečja in razpršenost vseh vhodov. Izmerjeno (tools/ai/eval_mtr2_hourly.py, uparjen
# bootstrap): Tmax D+2 −0,08 °C, D+3 −0,12 °C resnično; Tmin šum. Zato samo za tmax.
MULTI_MODELS = ["ecmwf_ifs025", "gfs_seamless", "icon_seamless", "meteofrance_arpege_europe"]
MULTI_FEATURES = ["d_ifs", "d_gfs", "d_icon", "d_arpege", "d_mean", "spread"]
ARCHIVE_CSV = os.path.join(ROOT, "data", "forecast-archive.csv")


def load_multi_archive(path=ARCHIVE_CSV, leads=None):
    """{(lead, day): {"tmax": {model: v}, "tmin": {model: v}}} iz arhiva napovedi po modelih."""
    import csv
    out = {}
    leads = set(leads or LEADS)
    with open(path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["model"] not in MULTI_MODELS or int(r["lead_days"]) not in leads:
                continue
            e = out.setdefault((int(r["lead_days"]), r["valid_at"]), {"tmax": {}, "tmin": {}})
            for k in ("tmax", "tmin"):
                v = r.get(f"{k}_c")
                if v not in (None, ""):
                    e[k][r["model"]] = float(v)
    return out


def multi_vector(f, target):
    """Značilke drugih modelov za en cilj. Manjkajoči model: razlika 0 (nevtralno)."""
    vals = (f.get("mm") or {}).get(target) or {}
    om = f["om_" + target]
    have = [vals[m] for m in MULTI_MODELS if vals.get(m) is not None]
    diffs = [(vals[m] - om) if vals.get(m) is not None else 0.0 for m in MULTI_MODELS]
    allv = have + [om]
    mean = sum(allv) / len(allv)
    sd = math.sqrt(sum((x - mean) ** 2 for x in allv) / len(allv))
    return diffs + [mean - om, sd]


# ── Veter in sunki v dolini (24. 10. 2026) ───────────────────────────────────
# Postaja stoji na zavetrnem dnu doline: model povprečni veter precenjuje za ~2× (razmerje postaja/model 0,50,
# korelacija 0,75). Povprečni veter popravi že skala (mediana razmerja; ridge ni značilno boljši), sunke pa
# ridge v log1p prostoru z značilkami spodaj (D+1/D+2 značilno boljši od skale in log-linearne osnove; D+3 šum).
# Zajem dodatnih spremenljivk je LOČEN od HOURLY_VARS (temperaturni model in njegov zajem se ne spremenita);
# manjkajoči veter ne sme podreti učenja temperature. Rezultat: docs/model-recica.md, tools/ai/eval_mtr7_wind.py.
WIND_EXTRA_VARS = ["wind_gusts_10m", "wind_direction_10m"]
WIND_TARGETS = {"mean": "windspeedAvg", "gust": "windgustHigh"}   # polja v history.json (IREICA1, km/h)
WIND_FEATURES = ["bias", "log_wmean", "log_wmax", "log_wnight", "log_wday", "log_gmax", "log_gmean_day",
                 "dir_x", "dir_y", "cloud", "cloud_n", "rad100", "pres_anom10", "sin_doy", "cos_doy"]
WIND_LAMBDA_GRID = [0.1, 0.5, 2.0, 8.0, 32.0]
WIND_INNER_FOLDS = 3
WIND_MIN_OM = 0.5     # km/h: pod tem razmerje obs/om ni stabilno (veter blizu 0)
WIND_MIN_SAMPLES = 200


def _log1p(x):
    return math.log1p(max(x, 0.0))


def wind_columns(series):
    """Urne serije enega dne ({spremenljivka: [(ura, vrednost), ...]}) → dnevne vrednosti vetra ali None.
    Potrebuje wind_speed_10m (HOURLY_VARS) in wind_gusts_10m + wind_direction_10m (WIND_EXTRA_VARS), po vsaj 20 ur
    hitrosti in sunkov. ISTA funkcija pri učenju in pri napovedi (isto načelo kot daily_features)."""
    g = lambda k: [(int(h), v) for h, v in (series.get(k) or [])]
    w, gu, di = g("wind_speed_10m"), g("wind_gusts_10m"), dict(g("wind_direction_10m"))
    if len(w) < 20 or len(gu) < 20:
        return None
    wn = [v for h, v in w if h in NIGHT_HOURS]
    wd = [v for h, v in w if h in DAY_HOURS]
    gd = [v for h, v in gu if h in DAY_HOURS]
    if not wn or not wd or not gd:
        return None
    tot = sum(v for _, v in w)
    ex = sum(v * math.sin(math.radians(di[h])) for h, v in w if h in di) / tot if tot > 0 else 0.0
    ey = sum(v * math.cos(math.radians(di[h])) for h, v in w if h in di) / tot if tot > 0 else 0.0
    return {"wmean": tot / len(w), "wmax": max(v for _, v in w), "wn": sum(wn) / len(wn),
            "wd": sum(wd) / len(wd), "gmax": max(v for _, v in gu), "gmean_d": sum(gd) / len(gd),
            "ex": ex, "ey": ey}


def wind_vector(c, f):
    """Načrtovalna vrstica za sunke (vrstni red = WIND_FEATURES). `c` = wind_columns, `f` = daily_features."""
    return [1.0, _log1p(c["wmean"]), _log1p(c["wmax"]), _log1p(c["wn"]), _log1p(c["wd"]), _log1p(c["gmax"]),
            _log1p(c["gmean_d"]), c["ex"], c["ey"], f["cloud"] / 100, f["cloud_n"] / 100, f["rad"] / 100,
            (f["pres"] - 1013) / 10, f["sin_doy"], f["cos_doy"]]


def build_wind_samples(samples, merged_rows, hist):
    """Iz že zgrajenih temperaturnih vzorcev (datum + daily_features) naredi vetrovne: doda stolpce vetra in
    izmerjeni povprečni veter in največji sunek postaje. Dan brez stolpcev ali meritve odpade."""
    out = []
    for s in samples:
        o = hist.get(s["date"]) or {}
        c = wind_columns(merged_rows.get(s["date"]) or {})
        if c is None or o.get(WIND_TARGETS["mean"]) is None or o.get(WIND_TARGETS["gust"]) is None:
            continue
        out.append({"date": s["date"], "f": s["f"], "c": c,
                    "mean": float(o[WIND_TARGETS["mean"]]), "gust": float(o[WIND_TARGETS["gust"]])})
    return out


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])


def fit_wind_ratio(samples):
    """Skala povprečnega vetra: mediana obs/om na dnevih z vetrom nad WIND_MIN_OM."""
    r = [s["mean"] / s["c"]["wmean"] for s in samples if s["c"]["wmean"] > WIND_MIN_OM]
    return _median(r) if r else 1.0


def select_wind_lambda(samples):
    months = sorted({s["date"][:7] for s in samples})
    if len(months) <= WIND_INNER_FOLDS:
        return 2.0
    best, best_mae = 2.0, None
    for lam in WIND_LAMBDA_GRID:
        errs = []
        for tm in months[-WIND_INNER_FOLDS:]:
            tr = [s for s in samples if s["date"][:7] < tm]
            te = [s for s in samples if s["date"][:7] == tm]
            if not tr or not te:
                continue
            co = solve_ridge([wind_vector(s["c"], s["f"]) for s in tr], [_log1p(s["gust"]) for s in tr], lam)
            errs += [abs(math.expm1(predict_linear(co, wind_vector(s["c"], s["f"]))) - s["gust"]) for s in te]
        if errs and (best_mae is None or sum(errs) / len(errs) < best_mae):
            best_mae, best = sum(errs) / len(errs), lam
    return best


def fit_wind_gust(samples):
    """(koeficienti, lambda) ridge modela sunkov v log1p prostoru."""
    lam = select_wind_lambda(samples)
    co = solve_ridge([wind_vector(s["c"], s["f"]) for s in samples], [_log1p(s["gust"]) for s in samples], lam)
    return co, lam


def predict_wind_gust(coefs, c, f):
    return max(math.expm1(predict_linear(coefs, wind_vector(c, f))), 0.0)


def walk_forward_wind(samples, kind, outer_folds=OUTER_FOLDS, min_train_months=MIN_TRAIN_MONTHS):
    """MAE (km/h) surovega Open-Meteo, skale in modela pri walk-forward po mesecih (kot walk_forward_cv:
    učenje samo iz mesecev pred testnim). `kind` = "mean" (model = skala) ali "gust" (model = ridge).
    Vrne None, kadar ni dovolj zgodovine."""
    months = sorted({s["date"][:7] for s in samples})
    if len(months) <= min_train_months:
        return None
    om_key = "wmean" if kind == "mean" else "gmax"
    errs = {"om": [], "scalar": [], "model": []}
    bias = {"om": [], "model": []}
    for tm in months[-outer_folds:]:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        if len(tr) < 100 or not te:
            continue
        r = _median([s[kind] / s["c"][om_key] for s in tr if s["c"][om_key] > WIND_MIN_OM] or [1.0])
        co = fit_wind_gust(tr)[0] if kind == "gust" else None
        for s in te:
            om = s["c"][om_key]
            model = r * om if kind == "mean" else predict_wind_gust(co, s["c"], s["f"])
            errs["om"].append(abs(om - s[kind]))
            errs["scalar"].append(abs(r * om - s[kind]))
            errs["model"].append(abs(model - s[kind]))
            bias["om"].append(om - s[kind])
            bias["model"].append(model - s[kind])
    if not errs["om"]:
        return None
    mae = {k: sum(v) / len(v) for k, v in errs.items()}
    return {"n": len(errs["om"]), "mae_open_meteo": round(mae["om"], 2), "mae_scalar": round(mae["scalar"], 2),
            "mae_meteorec": round(mae["model"], 2),
            "improvement_pct": round(100 * (1 - mae["model"] / mae["om"]), 1) if mae["om"] else None,
            "bias_open_meteo": round(sum(bias["om"]) / len(bias["om"]), 2),
            "bias_meteorec": round(sum(bias["model"]) / len(bias["model"]), 2)}


# ── Avtokorelirana pristranskost (--use-bias) ───────────────────────────────
def build_bias_series(lead1_rows, hist):
    """Časovna vrsta napake D+1 napovedi: izmerjeno − napovedano, ločeno za
    tmax/tmin. To je EDINI vir za err_lag1/ma3/ma7 (glej err_stats), ne glede na
    to, za kateri vodilni čas trenutno učimo ali napovedujemo — "kako zelo se je
    model pred kratkim motil" je stanje, ki ga poznamo šele za pretekle,
    razrešene dni, in D+1 je najsvežji tak vir (D+2/D+3 bi zahtevala čakanje
    še en/dva dneva na razrešitev, torej manj svežo informacijo).

    `lead1_rows` je izhod fetch_archived_forecasts(1, ...). Dan brez postajne
    meritve (izpad, era5) ali brez popolne napovedi preprosto ni v vrsti — to
    build_samples() prek err_stats() sam zazna kot vrzel (is_err_missing)."""
    err_tmax, err_tmin = {}, {}
    for day in lead1_rows:
        obs = hist.get(day)
        if not obs or obs.get("src") not in ("station", "wu"):
            continue
        if obs.get("tempHigh") is None or obs.get("tempLow") is None:
            continue
        f = daily_features(lead1_rows[day], day)
        if f is None:
            continue
        err_tmax[day] = obs["tempHigh"] - f["om_tmax"]
        err_tmin[day] = obs["tempLow"] - f["om_tmin"]
    return {"tmax": err_tmax, "tmin": err_tmin}


def err_stats(series, day, lead):
    """(err_lag1, err_ma3, err_ma7, is_err_missing) za napoved dneva `day` pri
    vodilnem času `lead`, brez uhajanja prihodnosti.

    Napoved za `day` pri vodilnem času `lead` je (bila) izdana `lead` dni pred
    `day` — torej je zadnji dan, ki je ob izdaji gotovo že končan in izmerjen,
    `day - lead - 1`. To velja enotno za učenje (arhiv, poljubna pretekla
    kombinacija dneva in vodilnega časa) in za živo napoved (izdaja je vedno
    "danes", `day - lead` = danes za vsak `lead`, glej predict_recica_mos.py).

    Manjkajoče vrednosti (začetek niza, izpad postaje/arhiva): NE vstavljamo
    ničle tiho — err_lag1/ma3/ma7 nastavimo na KLIMATOLOŠKO povprečje
    pristranskosti (povprečje vseh ŽE ZNANIH — strogo pred `end` — dni v
    `series`), is_err_missing pa doda indikator, model pa se iz njega nauči,
    kdaj značilki ne zaupati.

    Prvotno je bila tu ničla: pri tmin je dolgoročno povprečje pristranskosti
    ~−0,9 °C, pri tmax ~+0,8 °C, zato je ničla is_err_missing prisilila, da je
    sam prevzel to razliko — velik koeficient (≈ ∓1 °C), ki je bil dober za
    redke posamezne manjkajoče dni v učni množici (~1–2 %), ob resničnem
    večdnevnem izpadu pa (20.–23. 11. 2025, glej data/mtr-validation-report.md
    — jesenska regresija) dni tik po njem narobe popravil (napaka do 8,87 °C).
    Klimatologija je nevtralna vrednost brez te napetosti; is_err_missing
    lahko ostane majhen in izraža samo dodatno negotovost, ne osnovnega nivoja
    pristranskosti."""
    end = dt.date.fromisoformat(day) - dt.timedelta(days=lead + 1)
    window7 = [series.get((end - dt.timedelta(days=i)).isoformat()) for i in range(7)]
    if any(v is None for v in window7):
        cutoff = end.isoformat()
        known = [v for d, v in series.items() if d < cutoff]
        clim = sum(known) / len(known) if known else 0.0
        return clim, clim, clim, 1.0
    lag1 = window7[0]
    ma3 = sum(window7[:3]) / 3
    ma7 = sum(window7) / 7
    return lag1, ma3, ma7, 0.0


def pop_vector(f, with_aifs=False):
    v = [
        1.0,
        math.sqrt(min(f["om_prec"], 50)), f["wet_hours"] / 24, f["rh"] / 100,
        f["cloud"] / 100, (f["pres"] - 1013) / 10, f["om_tmax"] / 30,
        f["sin_doy"], f["cos_doy"],
    ]
    if with_aifs:
        v += [math.sqrt(min(f["aifs_prec"], 50)), f["aifs_wet_hours"] / 24]
    return v


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


def build_samples(rows, hist, lead, bias_series=None, aifs_rows=None, multi=None):
    """Poveže dnevne značilke z izmerjenim dnem. Dnevi z izvorom "era5" so
    modelska ocena in ne meritev — v učenju bi model učili lastnega vhoda.

    Z `aifs_rows` se vsakemu dnevu pripnejo še značilke drugega vhoda; dan, ki
    ga v tem arhivu ni, odpade.

    Z `bias_series` (glej build_bias_series) se vsakemu dnevu pripnejo err_lag1/
    ma3/ma7/is_err_missing, ločeno za tmax in tmin (glej err_stats) — `lead`
    pove, kateri vodilni čas se tu uči, kar določi, koliko dni nazaj so te
    značilke smele "videti"."""
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
        if aifs_rows is not None:
            af = daily_features(aifs_rows.get(day) or {}, day)
            f = merge_aifs(f, af)
            if f is None:
                continue
        if bias_series is not None:
            for target in ("tmax", "tmin"):
                lag1, ma3, ma7, missing = err_stats(bias_series[target], day, lead)
                f[f"err_lag1_{target}"] = lag1
                f[f"err_ma3_{target}"] = ma3
                f[f"err_ma7_{target}"] = ma7
                f[f"is_err_missing_{target}"] = missing
        if multi is not None:
            # Dan brez arhiva drugih modelov dobi mm=None; učni vzorci za cilj z --multi-* ga izpustijo.
            f["mm"] = multi.get((lead, day))
        samples.append({
            "date": day,
            "f": f,
            "tmax": obs["tempHigh"],
            "tmin": obs["tempLow"],
            "wet": 1.0 if (obs.get("precipTotal") or 0) >= WET_DAY_MM else 0.0,
            "mm": obs.get("precipTotal") or 0.0,
        })
    return samples


# ── Veščina ─────────────────────────────────────────────────────────────────
# Meteorološka sezona koledarskega meseca (za per_season razčlenitev spodaj).
_SEASON_OF_MONTH = {
    12: "zima", 1: "zima", 2: "zima",
    3: "pomlad", 4: "pomlad", 5: "pomlad",
    6: "poletje", 7: "poletje", 8: "poletje",
    9: "jesen", 10: "jesen", 11: "jesen",
}


def _season_of(date_str):
    return _SEASON_OF_MONTH[int(date_str[5:7])]


def select_lambda(samples, target, with_aifs=False, use_bias=False, use_cond=False,
                   grid=LAMBDA_GRID, inner_folds=INNER_FOLDS, use_multi=False):
    """Izbere regularizacijo (lambda) z NOTRANJO časovno validacijo znotraj
    `samples` — nikoli na zunanjem testnem nizu, ki bo pozneje meril veščino
    tega izbora (glej walk_forward_cv). Zadnjih `inner_folds` mesecev te množice
    služi kot notranji test, vsak proti vsemu, kar mu je strogo pred njim."""
    months = sorted({s["date"][:7] for s in samples})
    if len(months) <= inner_folds:
        return RIDGE_LAMBDA  # premalo zgodovine za notranjo izbiro — rezervna vrednost
    test_months = months[-inner_folds:]
    best_lam, best_mae = RIDGE_LAMBDA, None
    for lam in grid:
        errs = []
        for tm in test_months:
            tr = [s for s in samples if s["date"][:7] < tm]
            te = [s for s in samples if s["date"][:7] == tm]
            if not tr or not te:
                continue
            coefs = solve_ridge([temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi) for s in tr],
                                [s[target] for s in tr], lam)
            errs += [abs(predict_linear(coefs, temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi))
                         - s[target]) for s in te]
        if errs:
            mae = sum(errs) / len(errs)
            if best_mae is None or mae < best_mae:
                best_mae, best_lam = mae, lam
    return best_lam


def walk_forward_cv(samples, target, om_key, with_aifs=False, use_bias=False, use_cond=False,
                     outer_folds=OUTER_FOLDS, min_train_months=MIN_TRAIN_MONTHS, use_multi=False):
    """MAE modela in surovega Open-Meteo pri WALK-FORWARD validaciji: zaporedne
    mesečne rezine, učenje SAMO na tem, kar je pred testnim mesecem — v
    nasprotju s prejšnjim izpuščanjem celega leta (blocked_cv), ki je testni
    mesec včasih napovedovala iz let, ki so sledila (uhajanje prihodnosti).

    Regularizacija se izbere posebej za vsako rezino, izključno iz podatkov
    pred njo (select_lambda) — testni mesec je od te izbire popolnoma
    izoliran."""
    months = sorted({s["date"][:7] for s in samples})
    if len(months) <= min_train_months:
        return None
    test_months = months[min_train_months:][-outer_folds:]
    om_err, mos_err, per_month = [], [], {}
    season_errs = {}
    for tm in test_months:
        tr = [s for s in samples if s["date"][:7] < tm]
        te = [s for s in samples if s["date"][:7] == tm]
        if not tr or not te:
            continue
        lam = select_lambda(tr, target, with_aifs, use_bias, use_cond, use_multi=use_multi)
        coefs = solve_ridge([temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi) for s in tr],
                            [s[target] for s in tr], lam)
        eo, em = [], []
        for s in te:
            pred = predict_linear(coefs, temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi))
            e_om, e_mos = abs(s["f"][om_key] - s[target]), abs(pred - s[target])
            eo.append(e_om)
            em.append(e_mos)
            se = season_errs.setdefault(_season_of(s["date"]), {"om": [], "mos": []})
            se["om"].append(e_om)
            se["mos"].append(e_mos)
        per_month[tm] = {"n": len(te), "lambda": lam,
                          "open_meteo": round(sum(eo) / len(eo), 2),
                          "meteorec": round(sum(em) / len(em), 2)}
        om_err += eo
        mos_err += em
    if not om_err:
        return None

    def _skill(eo, em):
        a, b = sum(eo) / len(eo), sum(em) / len(em)
        return {
            "n": len(eo), "mae_open_meteo": round(a, 2), "mae_meteorec": round(b, 2),
            "rmse_open_meteo": round(math.sqrt(sum(e * e for e in eo) / len(eo)), 2),
            "rmse_meteorec": round(math.sqrt(sum(e * e for e in em) / len(em)), 2),
            "improvement_pct": round(100 * (a - b) / a, 1) if a else 0.0,
        }

    out = _skill(om_err, mos_err)
    out["per_month"] = per_month
    out["per_season"] = {s: _skill(v["om"], v["mos"]) for s, v in season_errs.items()}
    return out


def blocked_cv_pop(samples, with_aifs=False, thr_mm=None):
    """Brierjeva ocena za verjetnost padavin, proti klimatologiji učne množice.
    `thr_mm`: prag dnevne vsote namesto mokrega dne (pop1, pop5)."""
    def y_of(s):
        return s["wet"] if thr_mm is None else (1.0 if s["mm"] >= thr_mm else 0.0)
    years = sorted({s["date"][:4] for s in samples})
    brier, base = [], []
    for hold in years:
        tr = [s for s in samples if s["date"][:4] != hold]
        te = [s for s in samples if s["date"][:4] == hold]
        if not tr or not te:
            continue
        ytr = [y_of(s) for s in tr]
        if sum(ytr) < 5:   # leto brez dovolj pozitivnih primerov ne da smiselne rezine
            continue
        coefs = solve_logistic([pop_vector(s["f"], with_aifs) for s in tr], ytr)
        clim = sum(ytr) / len(tr)
        for s in te:
            p = predict_prob(coefs, pop_vector(s["f"], with_aifs))
            brier.append((p - y_of(s)) ** 2)
            base.append((clim - y_of(s)) ** 2)
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


def residual_sd(samples, coefs, target, with_aifs=False, use_bias=False, use_cond=False, use_multi=False):
    """Standardni odklon ostankov — pas negotovosti na kartici."""
    errs = [predict_linear(coefs, temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi)) - s[target]
            for s in samples]
    if len(errs) < 2:
        return None
    mean = sum(errs) / len(errs)
    var = sum((e - mean) ** 2 for e in errs) / (len(errs) - 1)
    return round(math.sqrt(var), 2)


# Režim noči (jasna in mirna / oblačna / vmes): ena definicija za napovedovalnik (razlaga na kartici)
# in za sd ostankov po režimu. predict_recica_mos.py jo uvozi od tu.
CLEAR_CLOUD_N, CALM_WIND_N, OVERCAST_CLOUD_N = 30, 8, 70
REGIMES = ("clear_calm", "overcast", "mixed")
REGIME_MIN_N = 40   # pod tem številom učnih dni razred nima svoje sd (velja globalna)


def night_regime(cloud_n, wind_n):
    """'clear_calm' | 'overcast' | 'mixed' - the codes the card turns into a sentence."""
    if cloud_n < CLEAR_CLOUD_N and wind_n < CALM_WIND_N:
        return "clear_calm"
    if cloud_n > OVERCAST_CLOUD_N:
        return "overcast"
    return "mixed"


def residual_sd_by_regime(samples, coefs, target, with_aifs=False, use_bias=False, use_cond=False,
                          use_multi=False):
    """sd ostankov po režimu noči. Razred z manj kot REGIME_MIN_N dnevi je izpuščen.
    Walk-forward (tools/ai/eval_mtr_sd.py, 383 dni): pri Tmax izenači pokritost P10-P90 med
    razredi (jasne noči 89-92 % → 72-79 %, oblačne 74-75 % → 80-81 %) in nekoliko izboljša
    logaritemsko oceno; pri Tmin brez razlike, zato se tam ne uporablja."""
    by = {}
    for s in samples:
        e = predict_linear(coefs, temp_vector(s["f"], target, with_aifs, use_bias, use_cond, use_multi)) - s[target]
        by.setdefault(night_regime(s["f"]["cloud_n"], s["f"]["wind_n"]), []).append(e)
    out = {}
    for k in REGIMES:
        v = by.get(k) or []
        if len(v) >= REGIME_MIN_N:
            m = sum(v) / len(v)
            out[k] = round(math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1)), 2)
    return out


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
    ap.add_argument("--aifs", action="store_true",
                    help="dodaj ECMWF AIFS kot drugi vhod (učno okno se skrajša na arhiv AIFS)")
    # Ločeno po cilju (ne en sam --use-bias/--use-cond): validacija
    # (data/mtr-validation-report.md) je pokazala, da +bias/+cond pri tminu
    # izboljša na celotnem obdobju za vse vodilne čase, pri tmaxu pa v sezoni
    # "jesen" poslabša (premalo pretekle zgodovine te sezone) — zato mora biti
    # mogoče vklopiti eno brez druge.
    ap.add_argument("--use-bias-tmax", action="store_true",
                    help="dodaj avtokorelirano pristranskost (err_lag1/ma3/ma7) k modelu tmax")
    ap.add_argument("--use-bias-tmin", action="store_true",
                    help="dodaj avtokorelirano pristranskost (err_lag1/ma3/ma7) k modelu tmin")
    ap.add_argument("--use-cond-tmax", action="store_true",
                    help="dodaj pogojne/režimske prediktorje (glej COND_FEATURES) k modelu tmax")
    ap.add_argument("--use-cond-tmin", action="store_true",
                    help="dodaj pogojne/režimske prediktorje (glej COND_FEATURES) k modelu tmin")
    ap.add_argument("--multi-tmax", action="store_true",
                    help="dodaj Tmax drugih modelov (IFS, GFS, ICON, ARPEGE; data/forecast-archive.csv) k modelu tmax")
    ap.add_argument("--multi-tmin", action="store_true",
                    help="dodaj Tmin drugih modelov k modelu tmin (poskusno: pri Tmin je dobiček šum)")
    ap.add_argument("--out", default=None, help="druga izhodna pot (za poskuse)")
    args = ap.parse_args()
    use_bias_for = {"tmax": args.use_bias_tmax, "tmin": args.use_bias_tmin}
    use_cond_for = {"tmax": args.use_cond_tmax, "tmin": args.use_cond_tmin}
    any_bias = any(use_bias_for.values())
    use_multi_for = {"tmax": args.multi_tmax, "tmin": args.multi_tmin}

    end = args.end or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    # Z AIFS se učno okno samo po sebi skrči na to, kar arhiv sploh ima. Brez
    # tega bi prvi dve leti tiho odpadli šele pri sestavljanju vzorcev in bi
    # izpis kazal učno okno, ki ga ni bilo.
    if args.aifs and args.start < AIFS_START:
        print(f"--aifs: učno okno se začne {AIFS_START} (prej arhiva AIFS ni)")
        args.start = AIFS_START
    hist = load_history()
    cache = {} if args.no_cache else load_cache()

    model = {
        "model_version": MODEL_VERSION,
        "trained_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "train_range": {"from": args.start, "to": end},
        "station": {"lat": LAT, "lon": LON, "name": "Rečica ob Savinji (IREICA1)"},
        "hourly_vars": HOURLY_VARS,
        "uses_aifs": bool(args.aifs),
        "aifs_model": AIFS_MODEL if args.aifs else None,
        # Slovar po cilju (tmax/tmin) — ne en sam bool, ker se lahko vklopita
        # neodvisno (glej opombo pri --use-bias-tmax/--use-bias-tmin zgoraj).
        "uses_bias_features": dict(use_bias_for),
        "uses_cond_features": dict(use_cond_for),
        "uses_multi_features": dict(use_multi_for),
        "multi_models": MULTI_MODELS if any(use_multi_for.values()) else [],
        "temp_features": {
            target: (TEMP_FEATURES + (AIFS_TEMP_FEATURES if args.aifs else [])
                     + (BIAS_FEATURES if use_bias_for[target] else [])
                     + (COND_FEATURES if use_cond_for[target] else [])
                     + (MULTI_FEATURES if use_multi_for[target] else []))
            for target in ("tmax", "tmin")
        },
        "pop_features": POP_FEATURES + (AIFS_POP_FEATURES if args.aifs else []),
        "wind_extra_vars": WIND_EXTRA_VARS,
        "wind_features": WIND_FEATURES,
        "wet_day_mm": WET_DAY_MM,
        "pop_thresholds_mm": POP_THRESHOLDS,
        "ridge_lambda": RIDGE_LAMBDA,  # rezervna vrednost; dejanska je od uvedbe select_lambda po ciljih spodaj
        "leads": {},
    }

    def archive_rows(lead, model_id=None):
        """Arhiv napovedi za en vodilni čas, s predpomnilnikom. Vrne None, kadar
        zajem ni uspel — klicatelj tak vodilni čas izpusti."""
        key = f"lead{lead}:{args.start}:{end}" + (f":{model_id}" if model_id else "")
        if key in cache:
            print(f"D+{lead}{f' [{model_id}]' if model_id else ''}: iz predpomnilnika")
            return _rows_from_cache(cache[key])
        print(f"D+{lead}{f' [{model_id}]' if model_id else ''}: zajemam arhiv napovedi")
        try:
            rows = fetch_archived_forecasts(lead, args.start, end, model=model_id)
        except RuntimeError as e:
            # Vodilni čas, ki ga ni bilo mogoče pobrati, preprosto izpustimo.
            # Prejšnji so že izračunani in bi jih vržena napaka vzela s seboj.
            print(f"  ⚠ D+{lead} preskočen: {e}", file=sys.stderr)
            return None
        if not args.no_cache:
            # Shrani takoj po vsakem vodilnem času: zajem traja minute in
            # prekinjen tek bi sicer vrgel stran vse, kar je že pobral.
            cache[key] = _rows_to_cache(rows)
            save_cache(cache)
        return rows

    def wind_archive(lead):
        """Arhiv napovedi sunkov in smeri za en vodilni čas (ločen zajem, svoj ključ v predpomnilniku).
        Vrne None, kadar zajem ni uspel — veter se tedaj izpusti, temperatura ostane."""
        key = f"wind{lead}:{args.start}:{end}"
        if key in cache:
            return _rows_from_cache(cache[key])
        print(f"D+{lead}: zajemam arhiv napovedi vetra (sunki, smer)")
        try:
            wrows = fetch_archived_forecasts(lead, args.start, end, variables=WIND_EXTRA_VARS)
        except RuntimeError as e:
            print(f"  ⚠ veter D+{lead} preskočen: {e}", file=sys.stderr)
            return None
        if not args.no_cache:
            cache[key] = _rows_to_cache(wrows)
            save_cache(cache)
        return wrows

    bias_series = None
    if any_bias:
        # D+1 arhiv je EDINI vir pristranskosti (glej build_bias_series) — vedno
        # ta, ne glede na to, kateri vodilni čas se v zanki spodaj ravno uči.
        lead1_rows = archive_rows(1)
        if lead1_rows is None:
            print("✗ --use-bias-tmax/--use-bias-tmin zahteva D+1 arhiv, ta pa ni dosegljiv.",
                  file=sys.stderr)
            return 1
        bias_series = build_bias_series(lead1_rows, hist)
        print(f"  pristranskost izračunana za {len(bias_series['tmax'])} dni")

    multi_arch = load_multi_archive() if any(use_multi_for.values()) else None

    for lead in LEADS:
        rows = archive_rows(lead)
        if rows is None:
            continue
        aifs_rows = None
        if args.aifs:
            aifs_rows = archive_rows(lead, AIFS_MODEL)
            if aifs_rows is None:
                continue

        samples = build_samples(rows, hist, lead, bias_series, aifs_rows, multi_arch)
        if len(samples) < 200:
            print(f"  ⚠ premalo vzorcev za D+{lead} ({len(samples)}) — vodilni čas izpuščen",
                  file=sys.stderr)
            continue
        print(f"  vzorcev: {len(samples)}  ({samples[0]['date']} → {samples[-1]['date']})")

        entry = {"n_samples": len(samples),
                 "date_range": {"from": samples[0]["date"], "to": samples[-1]["date"]},
                 "skill": {}, "coefficients": {}, "residual_sd": {}, "residual_sd_regime": {},
                 "lambda": {}}

        for target, om_key in (("tmax", "om_tmax"), ("tmin", "om_tmin")):
            use_bias, use_cond = use_bias_for[target], use_cond_for[target]
            use_multi = use_multi_for[target]
            # Cilj z --multi-*: samo dnevi, za katere arhiv drugih modelov obstaja.
            tsamples = [s for s in samples if s["f"].get("mm")] if use_multi else samples
            if use_multi and len(tsamples) < 200:
                print(f"  ⚠ {target}: premalo vzorcev z arhivom modelov ({len(tsamples)})", file=sys.stderr)
                continue
            skill = walk_forward_cv(tsamples, target, om_key, args.aifs, use_bias, use_cond,
                                    use_multi=use_multi)
            # Končna lambda za objavljene koeficiente: izbrana z isto notranjo
            # časovno validacijo, tokrat na CELI učni množici (kar bo v produkciji
            # dejansko na voljo), ne na eni izmed zunanjih rezin zgoraj.
            lam = select_lambda(tsamples, target, args.aifs, use_bias, use_cond, use_multi=use_multi)
            coefs = solve_ridge([temp_vector(s["f"], target, args.aifs, use_bias, use_cond, use_multi)
                                 for s in tsamples],
                                [s[target] for s in tsamples], lam)
            entry["skill"][target] = skill
            entry["coefficients"][target] = [round(c, 6) for c in coefs]
            entry["lambda"][target] = lam
            entry["residual_sd"][target] = residual_sd(tsamples, coefs, target, args.aifs,
                                                        use_bias, use_cond, use_multi)
            if target == "tmax":
                entry["residual_sd_regime"][target] = residual_sd_by_regime(
                    tsamples, coefs, target, args.aifs, use_bias, use_cond, use_multi)
            if skill:
                print(f"  {target}: Open-Meteo {skill['mae_open_meteo']} °C → "
                      f"naš {skill['mae_meteorec']} °C  ({skill['improvement_pct']:+.1f} %, λ={lam})")

        pop_skill = blocked_cv_pop(samples, args.aifs)
        pop_coefs = solve_logistic([pop_vector(s["f"], args.aifs) for s in samples],
                                   [s["wet"] for s in samples])
        entry["skill"]["pop"] = pop_skill
        entry["coefficients"]["pop"] = [round(c, 6) for c in pop_coefs]
        if pop_skill:
            print(f"  padavine: Brier {pop_skill['brier']} proti klimatologiji "
                  f"{pop_skill['brier_climatology']} (veščina {pop_skill['skill_score']})")

        # Verjetnost, da dnevna vsota doseže 1 oz. 5 mm. Količine same ne napovedujemo (glej
        # docs/model-recica.md); prag je odgovor, ki ga šum še dopušča. Brez veščine ni koeficientov.
        for key, thr in POP_THRESHOLDS.items():
            ys = [1.0 if s["mm"] >= thr else 0.0 for s in samples]
            sk = blocked_cv_pop(samples, args.aifs, thr)
            if sum(ys) < 30 or not sk or sk["skill_score"] <= 0:
                print(f"  {key} (≥ {thr:g} mm): izpuščeno (pozitivnih {int(sum(ys))}, veščina "
                      f"{sk['skill_score'] if sk else None})")
                continue
            cf = solve_logistic([pop_vector(s["f"], args.aifs) for s in samples], ys)
            entry["skill"][key] = sk
            entry["coefficients"][key] = [round(c, 6) for c in cf]
            print(f"  {key} (≥ {thr:g} mm): Brier {sk['brier']} proti klimatologiji "
                  f"{sk['brier_climatology']} (veščina {sk['skill_score']})")

        # Veter in sunki (glej opombo pri WIND_EXTRA_VARS): povprečni veter = skala, sunki = ridge v log1p.
        # Sunki se objavijo samo, če so v walk-forward boljši od surovega Open-Meteo; ob nedosegljivem
        # zajemu ali premalo dneh se veter izpusti, temperatura in padavine ostanejo.
        wrows = wind_archive(lead)
        if wrows:
            merged = {d: {**rows[d], **wrows.get(d, {})} for d in rows}
            wsamples = build_wind_samples(samples, merged, hist)
            if len(wsamples) >= WIND_MIN_SAMPLES:
                wind = {"mean": {"method": "scalar", "ratio": round(fit_wind_ratio(wsamples), 4),
                                 "skill": walk_forward_wind(wsamples, "mean")}}
                gskill = walk_forward_wind(wsamples, "gust")
                if gskill and gskill["mae_meteorec"] < gskill["mae_open_meteo"]:
                    gco, glam = fit_wind_gust(wsamples)
                    wind["gust"] = {"method": "ridge_log1p", "coefficients": [round(c, 6) for c in gco],
                                    "lambda": glam, "skill": gskill}
                entry["wind"] = wind
                ms, gs = wind["mean"]["skill"], gskill
                print(f"  veter ({len(wsamples)} dni): povprečni Open-Meteo {ms and ms['mae_open_meteo']} → "
                      f"skala {ms and ms['mae_meteorec']} km/h (×{wind['mean']['ratio']}); sunki Open-Meteo "
                      f"{gs and gs['mae_open_meteo']} → naš {gs and gs['mae_meteorec']} km/h"
                      f"{'' if 'gust' in wind else ' (sunki izpuščeni: ni boljše od surovega)'}")
            else:
                print(f"  ⚠ veter: premalo dni z meritvijo in napovedjo ({len(wsamples)})", file=sys.stderr)

        model["leads"][str(lead)] = entry

    if not model["leads"]:
        print("✗ Nobenega vodilnega časa ni bilo mogoče naučiti.", file=sys.stderr)
        return 1

    if args.report:
        print("\n(--report: model ni zapisan)")
        return 0

    out_path = args.out or MODEL_PATH
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n→ {os.path.relpath(out_path, ROOT)}: vodilni časi {', '.join(model['leads'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
