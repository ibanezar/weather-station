#!/usr/bin/env python3
"""
tools/analiza_suse.py — lokalni SPI (Standardized Precipitation Index) za
Rečico ob Savinji, iz Open-Meteo ERA5 arhiva padavin.

Postajina lastna zgodovina (history.json) sega šele od nov. 2019 — prekratka
in preveč lokalna za trditev "rekordna suša v Sloveniji". Ta skripta zato
namesto tega prenese dolg niz dnevnih padavin (ERA5 reanaliza, isti vir kot
`backfill_minmax.py`) za točko postaje in izračuna standardni SPI za 1-, 3- in
6-mesečna drseča okna, po uveljavljeni metodi (Thom 1966: gama porazdelitev,
prilagojena ločeno po mesecih) — načelno isto, kar za Slovenijo objavljata
ARSO/agromet in EDO (European Drought Observatory), le na naši točki namesto
na državni mreži postaj.

Za trditev o REKORDU CELE SLOVENIJE to NI dovolj — zanjo je treba ARSO-jev
uradni SPI (agromet.mkgp.gov.si) ali EDO. Ta skripta pove, ali gre za rekord
suše NA TEJ TOČKI (Rečica ob Savinji), kar je lahko lokalna zgodba za članek,
ne pa trditev o celi državi.

Skripta ne piše nobene objavljene datoteke — samo izpiše številke. Prenešeni
arhiv (počasen klic, ~30+ let dnevnih podatkov) predpomni v
tools/.drought_cache.json, da ne kliče API-ja vsakič znova.

Uporaba:
  python3 tools/analiza_suse.py                    # SPI do zadnjega popolnega meseca
  python3 tools/analiza_suse.py --start 1991-01-01  # daljši/krajši niz
  python3 tools/analiza_suse.py --no-cache
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_PATH = os.path.join(ROOT, "tools", ".drought_cache.json")

# Ista točka kot train_recica_mos.py / backfill_minmax.py (postaja IREICA1).
LAT, LON = 46.325779, 14.921137

DEFAULT_START = "1991-01-01"  # WMO priporoča vsaj 30 let za oceno parametrov SPI
WINDOWS = (1, 3, 6)

MES_NOM = ["", "januar", "februar", "marec", "april", "maj", "junij", "julij",
           "avgust", "september", "oktober", "november", "december"]


# ---------------------------------------------------------------- prenos ----

def fetch_daily_precip(start, end):
    """{'YYYY-MM-DD': mm} iz Open-Meteo ERA5 arhiva za LAT/LON."""
    params = urllib.parse.urlencode({
        "latitude": LAT, "longitude": LON,
        "start_date": start, "end_date": end,
        "daily": "precipitation_sum",
        "timezone": "Europe/Ljubljana",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.load(r)
    days = data["daily"]["time"]
    vals = data["daily"]["precipitation_sum"]
    return {d: (v if v is not None else 0.0) for d, v in zip(days, vals)}


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def get_daily_precip(start, end, use_cache=True):
    cache = load_cache() if use_cache else {}
    key = f"{start}_{end}"
    if key in cache:
        return cache[key]
    print(f"Prenašam ERA5 padavine {start} … {end} (Open-Meteo archive-api) …",
          file=sys.stderr)
    daily = fetch_daily_precip(start, end)
    if use_cache:
        cache = {key: daily}  # en sam vnos — starejši razponi so brez koristi
        save_cache(cache)
    return daily


# ---------------------------------------------------------------- statistika --

def inv_norm_cdf(p):
    """Standardna normalna kvantilna funkcija (Acklamov racionalni približek)."""
    if not 0.0 < p < 1.0:
        raise ValueError("p mora biti med 0 in 1")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def lower_incomplete_gamma_reg(a, x):
    """Regularizirana spodnja nepopolna gama funkcija P(a, x), Numerical
    Recipes gser/gcf (vrsta za x < a+1, veriga ulomkov sicer)."""
    if x <= 0:
        return 0.0
    gln = math.lgamma(a)
    if x < a + 1.0:
        ap = a
        term = 1.0 / a
        total = term
        for _ in range(200):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        return total * math.exp(-x + a * math.log(x) - gln)
    # veriga ulomkov za Q(a, x), P = 1 - Q
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    q = math.exp(-x + a * math.log(x) - gln) * h
    return 1.0 - q


def fit_gamma_thom(values):
    """Thom (1966) MLE-približek parametrov gama porazdelitve (alpha, beta)
    za pozitivne vrednosti (padavine)."""
    n = len(values)
    xbar = sum(values) / n
    a_stat = math.log(xbar) - sum(math.log(v) for v in values) / n
    alpha = (1 + math.sqrt(1 + 4 * a_stat / 3)) / (4 * a_stat)
    beta = xbar / alpha
    return alpha, beta


def spi_for_series(all_values, current_value):
    """SPI vrednosti za current_value glede na gama porazdelitev, prilagojeno
    na all_values (isti koledarski mesec/okno čez vsa leta, current_value
    vključen)."""
    zeros = [v for v in all_values if v <= 0]
    positives = [v for v in all_values if v > 0]
    q = len(zeros) / len(all_values)
    if not positives:
        return None
    alpha, beta = fit_gamma_thom(positives)

    def spi(v):
        if v <= 0:
            h = q
        else:
            g = lower_incomplete_gamma_reg(alpha, v / beta)
            h = q + (1 - q) * g
        h = min(max(h, 1e-6), 1 - 1e-6)
        return inv_norm_cdf(h)

    return spi(current_value)


# ---------------------------------------------------------------- glavno ----

def rolling_sums(daily, window_months, end_date):
    """{(year, month): vsota padavin zadnjih window_months polnih mesecev, ki
    se konča s tem mesecem (vključno)} — samo za pare, kjer imamo polne
    podatke za celotno okno."""
    # najprej mesečne vsote
    monthly = {}
    for d, v in daily.items():
        y, m = int(d[:4]), int(d[5:7])
        monthly[(y, m)] = monthly.get((y, m), 0.0) + v

    def add_months(y, m, delta):
        idx = (y * 12 + (m - 1)) + delta
        return idx // 12, idx % 12 + 1

    out = {}
    y0, m0 = int(end_date[:4]), int(end_date[5:7])
    y, m = 1900, 1
    # sprehodi se čez vse mesece, ki jih imamo
    all_months = sorted(monthly.keys())
    for (y, m) in all_months:
        if (y, m) > (y0, m0):
            continue
        keys = [add_months(y, m, -i) for i in range(window_months)]
        if all(k in monthly for k in keys):
            out[(y, m)] = sum(monthly[k] for k in keys)
    return out


def last_complete_month(daily):
    days = sorted(daily.keys())
    last = days[-1]
    y, m, d = int(last[:4]), int(last[5:7]), int(last[8:10])
    # zadnji dan meseca last ni nujno popoln mesec -> vzemi prejšnji mesec,
    # razen če je last res zadnji dan v mesecu
    import calendar
    if d < calendar.monthrange(y, m)[1]:
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return y, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=None)
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    end = args.end or dt.date.today().isoformat()
    daily = get_daily_precip(args.start, end, use_cache=not args.no_cache)

    y0, m0 = last_complete_month(daily)
    end_label = f"{MES_NOM[m0]} {y0}"
    print(f"Zadnji polni mesec v nizu: {end_label}")
    print(f"Niz: {args.start} … {end}  ({len(daily)} dni)\n")

    for w in WINDOWS:
        sums = rolling_sums(daily, w, f"{y0:04d}-{m0:02d}-28")
        cur_key = (y0, m0)
        if cur_key not in sums:
            print(f"SPI-{w}: premalo podatkov za {end_label}")
            continue
        # primerjaj samo isti koledarski mesec čez vsa leta (sezonskost)
        same_month = {y: v for (y, m), v in sums.items() if m == m0}
        values = list(same_month.values())
        current = same_month[y0]
        spi = spi_for_series(values, current)
        rank = 1 + sum(1 for v in values if v < current)  # 1 = najbolj suho
        n_years = len(values)
        is_record = rank == 1
        print(f"SPI-{w} ({w}-mes. drseča vsota padavin, konec {end_label}):")
        print(f"  letošnja vsota:  {current:.1f} mm")
        print(f"  SPI:             {spi:+.2f}"
              f"  ({'skrajno suho' if spi <= -2 else 'zelo suho' if spi <= -1.5 else 'zmerno suho' if spi <= -1 else 'ni suša' if spi > -1 else ''})")
        print(f"  rang:            {rank}. najbolj suh od {n_years} let z meritvami "
              f"({args.start[:4]}–{y0})")
        if is_record:
            print(f"  → REKORD: najbolj sušno obdobje {end_label} v celotnem nizu za ta koledarski mesec.")
        print()

    print("Opomba: to je SPI za točko postaje (Rečica ob Savinji), izračunan iz "
          "ERA5 reanalize po Thomovi (1966) metodi — meteorološka (padavinska) "
          "suša, brez upoštevanja izhlapevanja/temperature (SPEI). Za trditev o "
          "rekordu na ravni cele Slovenije je treba ARSO-jev uradni SPI "
          "(agromet.mkgp.gov.si) ali EDO (European Drought Observatory), ne te "
          "skripte.")


if __name__ == "__main__":
    main()
